import asyncio
import contextvars
import csv
import datetime as dt
import io
import json
import os
import re
import threading
import time
import uuid
import zipfile
from collections import Counter, defaultdict

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import reports
from .config import DATA_DIR, MULTI, SAMPLES_DIR, STATIC_DIR, UPLOAD_DIR, WS, cfg
from .models import (ExceptionItem, Invoice, Override, POLine, PurchaseOrder, Run, RunEvent, Session, Vendor, init_db)
from .pipeline import runner
from .rules import RULES
from .seed import seed, seed_if_empty
from .store import DB
from . import analytics as _analytics

app = FastAPI(title="InvoiceIQ", version="1.1")
app.include_router(_analytics.router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SAMPLES = [
    ("S01", "S01_happy_path.pdf", "Clean invoice, explicit PO, everything matches", "Approve"),
    ("S02", "S02_price_variance.pdf", "Unit price 4% above PO", "Review"),
    ("S03", "S03_split_po_inv2.pdf", "Split PO: 2nd invoice, fits remaining balance", "Approve"),
    ("S04", "S04_split_po_inv3.pdf", "Split PO: 3rd invoice overruns the balance by 5%", "Review"),
    ("S05", "S05_implied_po.pdf", "No PO printed; system infers the PO", "Review"),
    ("S06", "S06_duplicate_reformatted.pdf", "Same invoice, new layout and number style", "Reject"),
    ("S07", "S07_scanned_incomplete.pdf", "Image-only scan, missing number, unclear total", "Review"),
    ("S08", "S08_blocked_vendor.pdf", "Vendor is blocked in the master", "Reject"),
    ("S09", "S09_closed_po.pdf", "Bills against a closed, fully billed PO", "Reject"),
    ("S10", "S10_wrong_tax_type.pdf", "Inter-state vendor charges CGST+SGST", "Review"),
]
EDGE = {"S03": "Split PO", "S04": "Split PO", "S05": "Implied PO", "S06": "Duplicate", "S07": "Scanned / incomplete"}


@app.on_event("startup")
def _startup():
    init_db()
    seed_if_empty()
    if MULTI:   # tidy private workspaces nobody has opened for a week
        d = os.path.join(DATA_DIR, "ws")
        if os.path.isdir(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                try:
                    if time.time() - os.path.getmtime(fp) > 7 * 86400:
                        os.remove(fp)
                except OSError:
                    pass


if MULTI:
    from starlette.concurrency import run_in_threadpool

    _ready = set()

    def _ensure_ws(ws):
        if ws not in _ready:
            init_db()
            seed_if_empty()
            _ready.add(ws)

    @app.middleware("http")
    async def _workspace(request, call_next):
        """Every browser gets a private workspace, remembered in a cookie."""
        path = request.url.path
        if path.startswith("/assets") or path == "/healthz":
            return await call_next(request)
        ws = request.cookies.get("iq_ws", "")
        new = not re.fullmatch(r"[0-9a-f]{24}", ws)
        if new:
            ws = uuid.uuid4().hex[:24]
        token = WS.set(ws)
        try:
            if path.startswith("/api/"):
                await run_in_threadpool(_ensure_ws, ws)
            resp = await call_next(request)
            if new:
                resp.set_cookie("iq_ws", ws, max_age=30 * 86400, httponly=True, samesite="lax")
            return resp
        finally:
            WS.reset(token)


# ───────────────────────── helpers ─────────────────────────
def _run_row(r):
    return {"run_id": r.run_id, "filename": r.filename, "status": r.status, "decision": r.decision,
            "final_decision": r.final_decision, "reason": r.reason, "vendor_name": r.vendor_name,
            "invoice_number": r.invoice_number, "total": r.total, "po_number": r.po_number, "top_rule": r.top_rule,
            "total_ms": r.total_ms, "confidence": r.overall_confidence,
            "started_at": r.started_at.isoformat() + "Z" if r.started_at else None,
            "finished_at": r.finished_at.isoformat() + "Z" if r.finished_at else None}


def _start(filename, data):
    run_id = "r_" + dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:4]
    with open(os.path.join(UPLOAD_DIR, run_id + ".pdf"), "wb") as f:
        f.write(data)
    with Session() as s:
        s.add(Run(run_id=run_id, filename=filename, status="queued"))
        s.commit()
    runner.publish(run_id, {"type": "queued", "run_id": run_id, "filename": filename})
    ctx = contextvars.copy_context()   # the background run keeps the caller's workspace
    threading.Thread(target=ctx.run, args=(runner.process, run_id, filename, data), daemon=True).start()
    return run_id


# ───────────────────────── runs ─────────────────────────
@app.post("/api/runs")
async def create_run(file: UploadFile = File(...)):
    data = await file.read(cfg.max_file_mb * 1048576 + 1)
    if len(data) > cfg.max_file_mb * 1048576:
        raise HTTPException(413, f"File is larger than {cfg.max_file_mb} MB (rule R1.2)")
    if not data:
        raise HTTPException(400, "The file is empty")
    return {"run_id": _start(file.filename or "upload.pdf", data)}


@app.get("/api/samples")
def list_samples():
    return [{"code": c, "filename": f, "description": d, "expected": e, "edge_case": EDGE.get(c)} for c, f, d, e in SAMPLES]


@app.get("/api/samples.zip")
def samples_zip():
    """All sample invoices in one zip, with a guide listing the expected verdict for each."""
    guide = ["InvoiceIQ sample invoices", "=" * 26, "",
             "Upload them one at a time on the Upload & Run page.",
             "Run S03 before S04 so the PO balance falls first. Use Reset demo data (Reference Data page) to start over.", "",
             "File | What it tests | Expected", "-" * 60]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for code, fn, desc, exp in SAMPLES:
            z.write(os.path.join(SAMPLES_DIR, fn), fn)
            edge = f" [edge case: {EDGE[code]}]" if code in EDGE else ""
            guide.append(f"{fn} | {desc}{edge} | {exp}")
        z.writestr("README.txt", "\n".join(guide) + "\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": "attachment; filename=invoiceiq_sample_invoices.zip"})


@app.post("/api/samples/{name}")
def run_sample(name: str):
    m = next((x for x in SAMPLES if x[0] == name.upper() or x[1] == name or x[1].rsplit(".", 1)[0] == name), None)
    if not m:
        raise HTTPException(404, "Unknown sample")
    with open(os.path.join(SAMPLES_DIR, m[1]), "rb") as f:
        data = f.read()
    return {"run_id": _start(m[1], data), "code": m[0]}


@app.get("/api/samples/{name}/file")
def sample_file(name: str):
    m = next((x for x in SAMPLES if x[0] == name.upper() or x[1] == name), None)
    if not m:
        raise HTTPException(404)
    return FileResponse(os.path.join(SAMPLES_DIR, m[1]), media_type="application/pdf", filename=m[1])


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    async def gen():
        i = 0
        if not runner.has_events(run_id):
            with Session() as s:
                r = s.get(Run, run_id)
                if r is None:
                    yield "event: error\ndata: {\"error\":\"unknown run\"}\n\n"
                    return
                evs = s.query(RunEvent).filter_by(run_id=run_id).order_by(RunEvent.seq).all()
                for e in evs:
                    d = json.loads(e.detail_json or "{}")
                    yield "data: " + json.dumps({"type": "stage_result", "run_id": run_id, "stage_no": e.stage_no, "stage_name": e.stage_name,
                                                 "status": e.status, "summary": e.summary, "checks": d.get("checks", []),
                                                 "data": d.get("data", {}), "duration_ms": e.duration_ms}) + "\n\n"
                yield "data: " + json.dumps({"type": "run_completed", "run_id": run_id, "decision": r.decision, "reason": r.reason,
                                             "total_ms": r.total_ms, "top_rule": r.top_rule}) + "\n\n"
            return
        idle = 0
        while True:
            batch = runner.events_since(run_id, i)
            for ev in batch:
                i += 1
                yield "data: " + json.dumps(ev) + "\n\n"
                if ev["type"] == "run_completed":
                    return
            idle = 0 if batch else idle + 1
            if idle > 1800:
                return
            await asyncio.sleep(0.08)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@app.get("/api/runs/export.csv")
def export_csv():
    with Session() as s:
        rows = s.query(Run).filter(Run.status != "queued").order_by(Run.started_at).all()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["run_id", "file", "vendor", "invoice_number", "po_number", "total_inr", "pipeline_decision", "final_decision",
                    "top_rule", "confidence", "run_ms", "reason", "started_at_utc"])
        for r in rows:
            w.writerow([r.run_id, r.filename, r.vendor_name, r.invoice_number, r.po_number, r.total, r.decision, r.final_decision,
                        r.top_rule, r.overall_confidence, r.total_ms, r.reason, r.started_at.isoformat() if r.started_at else ""])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=invoiceiq_runs.csv"})


@app.get("/api/runs")
def list_runs(decision: str = None, q: str = None, limit: int = 200):
    with Session() as s:
        qry = s.query(Run).filter(Run.status.in_(["done", "error", "running", "queued"])).order_by(Run.started_at.desc())
        rows = qry.limit(limit).all()
        out = [_run_row(r) for r in rows]
    if decision:
        out = [r for r in out if (r["final_decision"] or r["decision"]) == decision]
    if q:
        ql = q.lower()
        out = [r for r in out if ql in " ".join(str(v or "") for v in (r["filename"], r["vendor_name"], r["invoice_number"], r["po_number"])).lower()]
    return out


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with Session() as s:
        r = s.get(Run, run_id)
        if not r:
            raise HTTPException(404)
        out = _run_row(r)
        out["result"] = json.loads(r.result_json) if r.result_json else None
        out["overrides"] = [{"action": o.action, "note": o.note, "user": o.user, "ts": o.ts.isoformat() + "Z"}
                            for o in s.query(Override).filter_by(run_id=run_id).order_by(Override.ts)]
        ex = s.query(ExceptionItem).filter_by(run_id=run_id).first()
        out["exception"] = None if not ex else {"id": ex.id, "status": ex.status, "assignee": ex.assignee, "kind": ex.kind}
        return out


@app.get("/api/runs/{run_id}/page.png")
def page_image(run_id: str, page: int = 1):
    path = os.path.join(UPLOAD_DIR, run_id + ".pdf")
    if not os.path.exists(path):
        raise HTTPException(404)
    import fitz
    doc = fitz.open(path)
    pix = doc[max(0, min(page - 1, doc.page_count - 1))].get_pixmap(dpi=110)
    return Response(pix.tobytes("png"), media_type="image/png")


@app.get("/api/runs/{run_id}/file")
def run_file(run_id: str):
    path = os.path.join(UPLOAD_DIR, run_id + ".pdf")
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="application/pdf")


def _load(run_id):
    with Session() as s:
        r = s.get(Run, run_id)
        if not r or not r.result_json:
            raise HTTPException(404, "Run not finished")
        return r, json.loads(r.result_json)


@app.get("/api/runs/{run_id}/report.pdf")
def report_pdf(run_id: str):
    r, res = _load(run_id)
    return Response(reports.run_report(r, res), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=invoiceiq_report_{run_id}.pdf"})


@app.get("/api/runs/{run_id}/vendor-letter.pdf")
def letter_pdf(run_id: str):
    r, res = _load(run_id)
    return Response(reports.vendor_letter(r, res), media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=vendor_letter_{run_id}.pdf"})


@app.post("/api/runs/{run_id}/override")
def override(run_id: str, body: dict = Body(...)):
    action, note = body.get("action"), (body.get("note") or "").strip()
    if action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")
    if len(note) < 10:
        raise HTTPException(400, "A note of at least 10 characters is required (R9.2)")
    with Session() as s:
        r = s.get(Run, run_id)
        if not r:
            raise HTTPException(404)
        if r.decision != "Review" or r.final_decision != "Review":
            raise HTTPException(409, "Overrides are only allowed on Review items (R9.2)")
        new = "Approve" if action == "approve" else "Reject"
        r.final_decision = new
        s.add(Override(run_id=run_id, action=action, note=note))
        inv = s.query(Invoice).filter_by(run_id=run_id).first()
        if inv:
            inv.decision = new   # recalculates the PO balance because balance derives from Approve rows (R9.3)
        ex = s.query(ExceptionItem).filter_by(run_id=run_id).first()
        if ex:
            ex.status, ex.resolved_at = "Resolved", dt.datetime.utcnow()
        s.commit()
    return get_run(run_id)


# ───────────────────────── stats ─────────────────────────
@app.get("/api/stats")
def stats():
    with Session() as s:
        runs = s.query(Run).filter(Run.status == "done").order_by(Run.started_at).all()
        exs = s.query(ExceptionItem).all()
        n = len(runs)
        cnt = Counter((r.final_decision or r.decision) for r in runs)
        pipe = Counter(r.decision for r in runs)
        causes = Counter(r.top_rule for r in runs if r.decision != "Approve" and r.top_rule)
        by_day = defaultdict(lambda: {"Approve": 0, "Review": 0, "Reject": 0})
        for r in runs:
            by_day[r.started_at.strftime("%d %b")][r.final_decision or r.decision] += 1
        value = defaultdict(float)
        for r in runs:
            value[r.final_decision or r.decision] += r.total or 0
        vend = defaultdict(lambda: {"Approve": 0, "Review": 0, "Reject": 0})
        for r in runs:
            vend[r.vendor_name or "Unknown"][r.final_decision or r.decision] += 1
        today = dt.datetime.utcnow().date()
        return {
            "total": n, "approve": cnt["Approve"], "review": cnt["Review"], "reject": cnt["Reject"],
            "auto_approval_rate": round(pipe["Approve"] / n * 100, 1) if n else 0,
            "avg_ms": int(sum(r.total_ms or 0 for r in runs) / n) if n else 0,
            "value_processed": sum(r.total or 0 for r in runs),
            "value_by_decision": dict(value),
            "causes": [{"rule": k, "name": RULES.get(k, {}).get("name", k), "count": v} for k, v in causes.most_common(8)],
            "trend": [{"day": k, **v} for k, v in by_day.items()],
            "by_vendor": [{"vendor": k, **v} for k, v in vend.items()],
            "exceptions": {"open": sum(1 for e in exs if e.status == "Open"), "in_progress": sum(1 for e in exs if e.status == "In progress"),
                           "resolved_today": sum(1 for e in exs if e.status == "Resolved" and e.resolved_at and e.resolved_at.date() == today),
                           "overdue": sum(1 for e in exs if e.status != "Resolved" and e.created_at and (dt.datetime.utcnow() - e.created_at).total_seconds() > 3600 * 24)},
            "overrides": s.query(Override).count(),
        }


@app.get("/api/matrix")
def matrix():
    """Exception matrix: vendors x causes (top_rule) for non-approved runs."""
    with Session() as s:
        runs = s.query(Run).filter(Run.status == "done", Run.decision != "Approve").all()
    vendors = sorted({r.vendor_name or "Unknown" for r in runs})
    rules = sorted({r.top_rule for r in runs if r.top_rule})
    cells = defaultdict(int)
    for r in runs:
        cells[(r.vendor_name or "Unknown", r.top_rule)] += 1
    return {"vendors": vendors, "rules": [{"rule": x, "name": RULES.get(x, {}).get("name", x)} for x in rules],
            "cells": [{"vendor": v, "rule": x, "count": cells[(v, x)]} for v in vendors for x in rules if cells[(v, x)]]}


# ───────────────────────── exceptions ─────────────────────────
@app.get("/api/exceptions")
def exceptions():
    with Session() as s:
        out = []
        for e in s.query(ExceptionItem).order_by(ExceptionItem.created_at.desc()).all():
            r = s.get(Run, e.run_id)
            out.append({"id": e.id, "run_id": e.run_id, "kind": e.kind, "status": e.status, "assignee": e.assignee, "note": e.note,
                        "created_at": e.created_at.isoformat() + "Z", "vendor_name": r.vendor_name, "invoice_number": r.invoice_number,
                        "total": r.total, "reason": r.reason, "top_rule": r.top_rule, "filename": r.filename,
                        "final_decision": r.final_decision})
        return out


@app.patch("/api/exceptions/{eid}")
def patch_exception(eid: int, body: dict = Body(...)):
    with Session() as s:
        e = s.get(ExceptionItem, eid)
        if not e:
            raise HTTPException(404)
        if body.get("status") in ("Open", "In progress", "Resolved"):
            e.status = body["status"]
            e.resolved_at = dt.datetime.utcnow() if e.status == "Resolved" else None
        if "assignee" in body:
            e.assignee = body["assignee"]
        if "note" in body:
            e.note = body["note"]
        s.commit()
    return {"ok": True}


# ───────────────────────── reference data / config ─────────────────────────
@app.get("/api/vendors")
def vendors():
    with Session() as s:
        return [{c: getattr(v, c) for c in ("vendor_id", "legal_name", "gstin", "state_code", "address", "bank_account_no", "ifsc",
                                            "approval_status", "payment_terms_days")} for v in s.query(Vendor).order_by(Vendor.vendor_id)]


@app.get("/api/pos")
def pos():
    with Session() as s:
        db = DB(s)
        out = []
        for p in s.query(PurchaseOrder).order_by(PurchaseOrder.po_number):
            billed = float(db.billed_to_date(p.po_number))
            out.append({"po_number": p.po_number, "vendor_id": p.vendor_id, "issue_date": p.issue_date.isoformat(), "status": p.status,
                        "net_amount": float(p.net_amount), "billed": billed, "remaining": float(p.net_amount) - billed,
                        "description": p.description, "gst_rate_pct": p.gst_rate_pct,
                        "lines": [{"description": l.description, "quantity": l.quantity, "unit_price": float(l.unit_price)}
                                  for l in db.po_lines(p.po_number)]})
        return out


@app.get("/api/invoices")
def invoices():
    with Session() as s:
        return [{"invoice_number": i.invoice_number, "vendor_id": i.vendor_id, "invoice_date": i.invoice_date.isoformat() if i.invoice_date else None,
                 "po_number": i.po_number, "subtotal": float(i.subtotal or 0), "total": float(i.total or 0), "decision": i.decision,
                 "source": "run" if i.run_id else "seed history"} for i in s.query(Invoice).order_by(Invoice.invoice_id)]


@app.get("/api/rules")
def rules():
    return list(RULES.values())


@app.get("/api/config")
def get_config():
    return cfg.as_dict()


@app.put("/api/config")
def put_config(body: dict = Body(...)):
    try:
        cfg.update(body)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid value: {e}")
    return cfg.as_dict()


@app.post("/api/config/reset")
def reset_config():
    cfg.reload_defaults()
    return cfg.as_dict()


@app.post("/api/reset")
def reset():
    if not MULTI:
        runner.clear_events()
    seed(reset=True)
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True, "extraction": "local"}


# ───────────────────────── static front end ─────────────────────────
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        p = os.path.join(STATIC_DIR, full_path)
        nc = {"Cache-Control": "no-cache, must-revalidate"}   # always load the newest page; hashed /assets files cache normally
        if full_path and os.path.isfile(p):
            return FileResponse(p, headers=nc)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"), headers=nc)
