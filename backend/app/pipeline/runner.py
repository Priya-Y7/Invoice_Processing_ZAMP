"""Runs the nine stages for one run, emits events, persists everything."""
import datetime as dt
import json
import threading
import time
import traceback

from ..config import UPLOAD_DIR, cfg
from ..models import ExceptionItem, Invoice, Run, RunEvent, Session
from ..store import DB
from ..util import D, fnum, jdump, norm_number, parse_date
from . import STAGES
from .base import Ctx, StageResult

# ── in-memory event bus (replayed to late SSE subscribers; DB holds the durable copy) ──
_events = {}
_lock = threading.Lock()


def publish(run_id, ev):
    with _lock:
        _events.setdefault(run_id, []).append(ev)


def events_since(run_id, i):
    with _lock:
        return list(_events.get(run_id, [])[i:])


def has_events(run_id):
    return run_id in _events


def clear_events():
    with _lock:
        _events.clear()


def _ev(run_id, typ, **kw):
    ev = {"type": typ, "run_id": run_id, "ts": dt.datetime.utcnow().isoformat() + "Z", **kw}
    publish(run_id, ev)
    return ev


def _stage_dict(no, mod, res):
    return {"stage_no": no, "stage_name": mod.NAME, "status": res.status, "summary": res.summary,
            "checks": res.checks, "data": json.loads(jdump(res.data)), "duration_ms": res.duration_ms}


_serial = threading.Lock()   # runs are processed one at a time so PO balances stay correct (split-PO sequences)


def process(run_id, filename, data):
    with _serial:
        _process(run_id, filename, data)


def _process(run_id, filename, data):
    """Entry point (called in a worker thread)."""
    sess = Session()
    t0 = time.time()
    ctx = Ctx(run_id=run_id, filename=filename, data=data, cfg=cfg, db=DB(sess))
    pace = cfg.ui_pacing_ms / 1000.0
    stages_out = []
    try:
        run = sess.get(Run, run_id)
        run.status = "running"
        sess.commit()
        _ev(run_id, "run_started", filename=filename)
        for no, mod in STAGES:
            _ev(run_id, "stage_started", stage_no=no, stage_name=mod.NAME)
            s0 = time.time()
            skip = False
            if ctx.ended and no > 1:
                skip = True
            elif no in (3, 4, 5, 6, 7) and (ctx.ex is None or ctx.results.get(2) is None or ctx.results[2].status in ("error",)):
                skip = True
            elif no in (3, 4, 5, 6, 7) and ctx.results[2].status == "fail":
                skip = True
            if skip:
                res = StageResult(status="skipped", summary="Skipped: no usable input from earlier stages")
            else:
                try:
                    res = mod.run(ctx)
                except Exception as e:  # per-stage isolation (spec 2.7)
                    traceback.print_exc()
                    res = StageResult(status="error", summary=f"Stage crashed: {type(e).__name__}: {e}")
            time.sleep(pace * (0.6 if skip else 1.0))
            res.duration_ms = int((time.time() - s0) * 1000)
            ctx.results[no] = res
            sd = _stage_dict(no, mod, res)
            stages_out.append(sd)
            _ev(run_id, "stage_result", **sd)
            _ev(run_id, "stage_finished", stage_no=no, status=res.status, duration_ms=res.duration_ms)
            if no == 1 and ctx.ended:
                pass
        if ctx.ended and not ctx.decision:
            reason = ctx.results[1].summary or "File could not be read"
            ctx.decision = {"verdict": "Reject", "reason": f"Reject: {reason}.", "reason_source": "template", "trail": [],
                            "top_rule": next((c["rule"] for c in ctx.results[1].checks if c["result"] == "fail"), "R1.1"),
                            "next_action": "Return to the vendor", "what_to_check": [],
                            "vendor_message": "Dear vendor, the file you sent could not be opened as a PDF. Please resend an unprotected PDF copy of the invoice.\n\nRegards,\nAccounts Payable"}
        elif not ctx.decision:
            ctx.decision = {"verdict": "Review", "reason": "Review: extraction unavailable, a person must read this invoice.",
                            "reason_source": "template", "trail": [{"rule": "R8.5", "level": "REVIEW", "stage": 8, "label": "Fail-safe",
                                                                     "detail": "Extraction unavailable"}],
                            "top_rule": "R8.5", "next_action": "Assigned to the AP manager's queue", "what_to_check": [], "vendor_message": None}
        total_ms = int((time.time() - t0) * 1000)
        _persist(sess, ctx, stages_out, total_ms)
        _ev(run_id, "run_completed", decision=ctx.decision["verdict"], reason=ctx.decision["reason"], total_ms=total_ms,
            top_rule=ctx.decision.get("top_rule"))
    except Exception as e:
        traceback.print_exc()
        sess.rollback()
        run = sess.get(Run, run_id)
        run.status = "error"
        run.decision = "Review"
        run.final_decision = "Review"
        run.reason = f"Review: the pipeline failed unexpectedly ({type(e).__name__}). A person must read this invoice."
        run.finished_at = dt.datetime.utcnow()
        sess.commit()
        _ev(run_id, "run_completed", decision="Review", reason=run.reason, total_ms=int((time.time() - t0) * 1000))
    finally:
        sess.close()


def _persist(sess, ctx, stages_out, total_ms):
    """One transaction: run row, events, invoice row, follow-up item (R9.1)."""
    d = ctx.decision
    F = (ctx.ex or {}).get("fields", {})
    run = sess.get(Run, ctx.run_id)
    result = {
        "run_id": ctx.run_id, "filename": ctx.filename, "file": ctx.file,
        "extraction": None if not ctx.ex else {
            "fields": F, "confidence": ctx.ex["confidence"], "line_items": ctx.ex["line_items"],
            "tax_lines": ctx.ex["tax_lines"], "bank": ctx.ex["bank"], "source": ctx.ex.get("source"),
            "overall_confidence": ctx.ex.get("overall_confidence"), "critical_min": ctx.ex.get("critical_min"),
            "raw_text": ctx.ex.get("raw_text", "")[:4000]},
        "vendor": ctx.results[4].data if ctx.results.get(4) else None,
        "po": ctx.results[6].data if ctx.results.get(6) else None,
        "numeric": ctx.results[7].data if ctx.results.get(7) else None,
        "decision": d, "stages": stages_out, "total_ms": total_ms,
    }
    run.status = "done"
    run.decision = d["verdict"]
    run.final_decision = d["verdict"]
    run.reason = d["reason"]
    run.reason_source = d["reason_source"]
    run.vendor_name = (ctx.vendor.legal_name if ctx.vendor else F.get("vendor_name"))
    run.invoice_number = F.get("invoice_number")
    run.total = fnum(D(F.get("total_amount")))
    run.po_number = ctx.po.po_number if ctx.po else F.get("po_reference")
    run.top_rule = d.get("top_rule")
    run.total_ms = total_ms
    run.overall_confidence = (ctx.ex or {}).get("overall_confidence")
    run.file_hash = ctx.file.get("sha256")
    run.result_json = jdump(result)
    run.finished_at = dt.datetime.utcnow()
    for i, sd in enumerate(stages_out):
        sess.add(RunEvent(run_id=ctx.run_id, seq=i, stage_no=sd["stage_no"], stage_name=sd["stage_name"], status=sd["status"],
                          summary=sd["summary"], detail_json=jdump({"checks": sd["checks"], "data": sd["data"]}),
                          duration_ms=sd["duration_ms"]))
    if ctx.ex and F.get("invoice_number") is not None or (ctx.ex and F.get("total_amount") is not None):
        sess.add(Invoice(run_id=ctx.run_id, vendor_id=ctx.vendor.vendor_id if ctx.vendor else None,
                         invoice_number=F.get("invoice_number"), invoice_number_norm=norm_number(F.get("invoice_number")),
                         invoice_date=parse_date(F.get("invoice_date")) if F.get("invoice_date") else None,
                         po_number=ctx.po.po_number if ctx.po else None, subtotal=F.get("subtotal"), tax_total=F.get("tax_total"),
                         total=F.get("total_amount"), decision=d["verdict"], file_hash=ctx.file.get("sha256")))
    if d["verdict"] in ("Review", "Reject"):
        sess.add(ExceptionItem(run_id=ctx.run_id, kind=d["verdict"], note="; ".join(w["action"] for w in d.get("what_to_check", [])[:3]) or None,
                               vendor_message=d.get("vendor_message")))
    sess.commit()
