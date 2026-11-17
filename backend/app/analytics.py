"""Read-only analytics endpoints: dashboard metrics, data readiness, waterfall, deep dives, activity feed.

Everything here is derived from rows that already exist (runs, invoices, POs, exceptions, overrides).
No new state is stored.
"""
import datetime as dt
import json
import re
from collections import Counter, defaultdict

from fastapi import APIRouter, HTTPException

from .config import cfg
from .models import ExceptionItem, Invoice, Override, POLine, PurchaseOrder, Run, Session, Vendor
from .rules import RULES
from .store import DB

router = APIRouter()

STAGES = ["Ingest", "Extract", "Validate", "Vendor", "Duplicate", "PO match", "Numbers", "Decide", "Output"]
MANUAL_MIN_PER_INVOICE = 10  # assumption used for the "time saved" card; shown in the UI as an assumption
GSTIN_RE = re.compile(r"^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _dec(r):
    return r.final_decision or r.decision


def _result(r):
    try:
        return json.loads(r.result_json) if r.result_json else {}
    except Exception:
        return {}


def _band(amount):
    a = amount or 0
    if a < 50_000:
        return "Under ₹50K"
    if a < 200_000:
        return "₹50K – 2L"
    if a < 500_000:
        return "₹2L – 5L"
    return "Above ₹5L"


BANDS = ["Under ₹50K", "₹50K – 2L", "₹2L – 5L", "Above ₹5L"]


def _iso(d):
    return d.isoformat() + "Z" if d else None


# ───────────────────────── dashboard analytics ─────────────────────────
def build_analytics(vendor: str = None):
    with Session() as s:
        runs = s.query(Run).filter(Run.status == "done").order_by(Run.started_at).all()
        ex = s.query(ExceptionItem).all()
        ex_by_run = {e.run_id: e for e in ex}
        ovr = s.query(Override).count()
    if vendor:
        runs = [r for r in runs if (r.vendor_name or "Unknown") == vendor]
    n = len(runs)
    parsed = [(r, _result(r)) for r in runs]
    cnt = Counter(_dec(r) for r in runs)
    pipe = Counter(r.decision for r in runs)
    value = defaultdict(float)
    for r in runs:
        value[_dec(r)] += r.total or 0

    # stage statistics
    stage = [{"no": i + 1, "name": STAGES[i], "ms_total": 0, "n": 0, "pass": 0, "warn": 0, "fail": 0, "error": 0, "skipped": 0} for i in range(9)]
    rule_hits = defaultdict(lambda: {"warn": 0, "fail": 0})
    field_conf = defaultdict(list)
    src = Counter()
    conf_vals = []
    for r, res in parsed:
        for st in res.get("stages", []):
            i = st["stage_no"] - 1
            if 0 <= i < 9:
                stage[i]["n"] += 1
                stage[i]["ms_total"] += st.get("duration_ms") or 0
                stage[i][st["status"]] = stage[i].get(st["status"], 0) + 1
            for c in st.get("checks", []):
                if c.get("result") in ("warn", "fail"):
                    rule_hits[c["id"]][c["result"]] += 1
        ext = res.get("extraction") or {}
        for k, v in (ext.get("confidence") or {}).items():
            if k in cfg.critical_fields:
                field_conf[k].append(v)
        src["Scanned (OCR)" if (res.get("file") or {}).get("doc_type") == "scan" else "Text PDF"] += 1
        if r.overall_confidence:
            conf_vals.append(r.overall_confidence)

    def bucket(v):
        return "< 0.70" if v < .7 else "0.70–0.80" if v < .8 else "0.80–0.90" if v < .9 else "0.90–0.95" if v < .95 else "≥ 0.95"
    hist = Counter(bucket(v) for v in conf_vals)
    conf_hist = [{"bucket": b, "count": hist.get(b, 0)} for b in ["< 0.70", "0.70–0.80", "0.80–0.90", "0.90–0.95", "≥ 0.95"]]

    # vendor risk
    vend = defaultdict(lambda: {"runs": 0, "Approve": 0, "Review": 0, "Reject": 0, "value": 0.0, "at_risk": 0.0, "rules": Counter()})
    for r in runs:
        v = vend[r.vendor_name or "Unknown"]
        v["runs"] += 1
        v[_dec(r)] += 1
        v["value"] += r.total or 0
        if _dec(r) != "Approve":
            v["at_risk"] += r.total or 0
            if r.top_rule:
                v["rules"][r.top_rule] += 1
    vendor_risk = []
    for k, v in vend.items():
        score = round((v["Review"] * 1 + v["Reject"] * 2) / (v["runs"] * 2) * 100)
        vendor_risk.append({"vendor": k, "runs": v["runs"], "approve": v["Approve"], "review": v["Review"], "reject": v["Reject"],
                            "value": v["value"], "at_risk": v["at_risk"], "risk_score": score,
                            "risk": "High" if score >= 60 else "Medium" if score >= 30 else "Low",
                            "top_rule": v["rules"].most_common(1)[0][0] if v["rules"] else None})
    vendor_risk.sort(key=lambda x: (-x["risk_score"], -x["at_risk"]))

    # amount bands
    bands = {b: {"band": b, "Approve": 0, "Review": 0, "Reject": 0} for b in BANDS}
    for r in runs:
        bands[_band(r.total)][_dec(r)] += 1

    by_day = defaultdict(lambda: {"Approve": 0, "Review": 0, "Reject": 0})
    for r in runs:
        by_day[r.started_at.strftime("%d %b")][_dec(r)] += 1
    today = dt.datetime.utcnow()
    open_ex = [e for e in ex if e.status != "Resolved"]
    value_at_risk = value["Review"] + value["Reject"]
    return {
        "total": n, "approve": cnt["Approve"], "review": cnt["Review"], "reject": cnt["Reject"],
        "touchless_rate": round(pipe["Approve"] / n * 100, 1) if n else 0,
        "exception_rate": round((n - pipe["Approve"]) / n * 100, 1) if n else 0,
        "value_processed": sum(r.total or 0 for r in runs), "value_by_decision": dict(value), "value_at_risk": value_at_risk,
        "avg_ms": int(sum(r.total_ms or 0 for r in runs) / n) if n else 0,
        "avg_confidence": round(sum(conf_vals) / len(conf_vals), 3) if conf_vals else 0,
        "time_saved_min": pipe["Approve"] * MANUAL_MIN_PER_INVOICE, "manual_min_assumption": MANUAL_MIN_PER_INVOICE,
        "duplicates_caught": sum(1 for r in runs if (r.top_rule or "").startswith("R5")),
        "ocr_runs": src["Scanned (OCR)"], "overrides": ovr,
        "open_exceptions": len(open_ex),
        "overdue": sum(1 for e in open_ex if e.created_at and (today - e.created_at).total_seconds() > 86400),
        "stage_stats": [{"no": x["no"], "name": x["name"], "avg_ms": int(x["ms_total"] / x["n"]) if x["n"] else 0, "n": x["n"],
                         "pass": x["pass"], "warn": x["warn"], "fail": x["fail"], "error": x["error"], "skipped": x["skipped"]} for x in stage],
        "rule_hits": sorted([{"rule": k, "name": RULES.get(k, {}).get("name", k), "warn": v["warn"], "fail": v["fail"], "count": v["warn"] + v["fail"]}
                             for k, v in rule_hits.items()], key=lambda x: -x["count"])[:12],
        "field_confidence": [{"field": k, "avg": round(sum(v) / len(v), 3), "min": round(min(v), 2)} for k, v in field_conf.items()],
        "confidence_hist": conf_hist, "source": [{"name": k, "value": v} for k, v in src.items()],
        "vendor_risk": vendor_risk, "bands": list(bands.values()),
        "trend": [{"day": k, **v} for k, v in by_day.items()],
        "vendors": sorted({r.vendor_name or "Unknown" for r in runs}),
        "top_flagged": [{"run_id": r.run_id, "invoice_number": r.invoice_number, "vendor": r.vendor_name, "total": r.total,
                         "decision": _dec(r), "top_rule": r.top_rule, "reason": r.reason,
                         "exception_status": ex_by_run[r.run_id].status if r.run_id in ex_by_run else None}
                        for r in sorted([r for r in runs if _dec(r) != "Approve"], key=lambda x: -(x.total or 0))[:10]],
        "last_run": None if not runs else {"run_id": runs[-1].run_id, "filename": runs[-1].filename, "decision": _dec(runs[-1]),
                                           "at": _iso(runs[-1].started_at), "invoice_number": runs[-1].invoice_number},
    }


@router.get("/api/analytics")
def analytics(vendor: str = None):
    return build_analytics(vendor)


# ───────────────────────── readiness (reference data health) ─────────────────────────
@router.get("/api/readiness")
def readiness():
    with Session() as s:
        db = DB(s)
        vendors = s.query(Vendor).all()
        pos = s.query(PurchaseOrder).all()
        lines = s.query(POLine).all()
        invs = s.query(Invoice).order_by(Invoice.invoice_id).all()
        vids = {v.vendor_id for v in vendors}
        lines_by_po = defaultdict(list)
        for l in lines:
            lines_by_po[l.po_number].append(l)
        billed = {p.po_number: float(db.billed_to_date(p.po_number)) for p in pos}

    log = []

    def add(file, check, ok, detail_ok, detail_bad, group):
        log.append({"file": file, "check": check, "status": "Pass" if ok else "Warning", "detail": detail_ok if ok else detail_bad, "group": group})
        return ok

    # --- vendors
    need = ["vendor_id", "legal_name", "gstin", "state_code", "bank_account_no", "ifsc", "approval_status"]
    miss = sum(1 for v in vendors for k in need if not getattr(v, k))
    add("Vendor master", "Required columns populated", miss == 0, f"All {len(need)} required columns filled for {len(vendors)} vendors", f"{miss} empty required cells", "Schema")
    bad_gst = [v.vendor_id for v in vendors if not GSTIN_RE.match(v.gstin or "")]
    add("Vendor master", "GSTIN format", not bad_gst, "Every GSTIN matches the 15-character pattern", f"Bad GSTIN: {', '.join(bad_gst)}", "Completeness")
    st_bad = [v.vendor_id for v in vendors if v.gstin and v.state_code and v.gstin[:2] != str(v.state_code)]
    add("Vendor master", "GSTIN state prefix equals state code", not st_bad, "State codes agree with GSTIN prefix", f"Mismatch for {', '.join(st_bad)}", "Consistency")
    nobank = [v.vendor_id for v in vendors if not (v.bank_account_no and v.ifsc)]
    add("Vendor master", "Bank details on file", not nobank, "Account number and IFSC present for all vendors", f"Missing for {', '.join(nobank)}", "Completeness")
    blocked = [v for v in vendors if v.approval_status != "Approved"]
    add("Vendor master", "Blocked vendors flagged", True, f"{len(blocked)} blocked vendor(s) will be rejected at Stage 4", "", "Consistency")
    # --- POs
    no_lines = [p.po_number for p in pos if not lines_by_po.get(p.po_number)]
    add("Purchase orders", "Every PO has line items", not no_lines, f"All {len(pos)} POs have at least one line", f"No lines: {', '.join(no_lines)}", "Completeness")
    mism = [p.po_number for p in pos if lines_by_po.get(p.po_number) and abs(sum((l.quantity or 0) * float(l.unit_price) for l in lines_by_po[p.po_number]) - float(p.net_amount)) > 1]
    add("Purchase orders", "Net amount equals sum of lines", not mism, "Line totals reconcile to PO net amount", f"Does not reconcile: {', '.join(mism)}", "Consistency")
    orphan = [p.po_number for p in pos if p.vendor_id not in vids]
    add("Purchase orders", "Vendor exists in master", not orphan, "Every PO links to a known vendor", f"Unknown vendor on {', '.join(orphan)}", "Consistency")
    ref = dt.date.fromisoformat(cfg.reference_date) if cfg.reference_date else dt.date.today()
    stale = [p.po_number for p in pos if p.status == "Open" and p.issue_date and (ref - p.issue_date).days > cfg.stale_days]
    add("Purchase orders", f"No open PO older than {cfg.stale_days} days", not stale, "No stale open POs", f"Stale open POs: {', '.join(stale)}", "Completeness")
    over = [p.po_number for p in pos if billed[p.po_number] > float(p.net_amount) * 1.02]
    add("Purchase orders", "No PO billed beyond its value", not over, "Billed amounts are within PO value", f"Over-billed: {', '.join(over)}", "Consistency")
    # --- invoice history
    orph_i = [i.invoice_number for i in invs if i.vendor_id and i.vendor_id not in vids]
    add("Invoice history", "Vendor exists in master", not orph_i, f"{len(invs)} historical invoices all link to a vendor", f"Unknown vendor on {', '.join(orph_i[:4])}", "Consistency")
    seen = Counter((i.vendor_id, i.invoice_number_norm) for i in invs if i.invoice_number_norm and not i.run_id)
    dup = [k for k, v in seen.items() if v > 1]
    add("Invoice history", "No duplicate invoice numbers", not dup, "No vendor has the same invoice number twice", f"{len(dup)} duplicated number(s) on record", "Consistency")
    miss_d = sum(1 for i in invs if not i.invoice_date)
    add("Invoice history", "Invoice dates present", miss_d == 0, "All records are dated (needed for the 90-day duplicate window)", f"{miss_d} records without date", "Completeness")
    add("Policy", "Thresholds within sensible bounds", 0 < cfg.price_tolerance_auto_pct <= cfg.price_tolerance_review_pct <= 25,
        f"Auto {cfg.price_tolerance_auto_pct}% ≤ Review {cfg.price_tolerance_review_pct}%", "Auto tolerance must be above 0 and not exceed the review tolerance", "Schema")
    add("Policy", "Buyer identity configured", bool(cfg.buyer_gstin and cfg.buyer_name), f"Billing entity: {cfg.buyer_name}", "Buyer name or GSTIN missing", "Schema")

    groups = {}
    for g in ("Schema", "Completeness", "Consistency"):
        rows = [x for x in log if x["group"] == g]
        groups[g] = round(100 * sum(1 for x in rows if x["status"] == "Pass") / len(rows)) if rows else 100
    score = round(sum(groups.values()) / 3)
    dates = [i.invoice_date for i in invs if i.invoice_date]
    open_pos = [p for p in pos if p.status == "Open"]
    cols_expected = {
        "vendors.csv": need + ["address", "bank_account_holder", "payment_terms_days"],
        "purchase_orders.csv": ["po_number", "vendor_id", "issue_date", "status", "currency", "net_amount", "gst_rate_pct", "description"],
        "po_lines.csv": ["po_number", "line_no", "description", "quantity", "unit_price"],
        "invoice_history.csv": ["invoice_number", "vendor_id", "invoice_date", "po_number", "subtotal", "tax_total", "total", "decision"],
    }
    cards = [
        {"key": "vendors", "code": "VM", "title": "Vendor master", "file": "vendors.csv", "rows": len(vendors), "cols": len(cols_expected["vendors.csv"]),
         "stats": [["Vendors", len(vendors)], ["Approved", len(vendors) - len(blocked)], ["Blocked", len(blocked)], ["States", len({v.state_code for v in vendors})]],
         "expected": cols_expected["vendors.csv"], "tab": "vendors"},
        {"key": "pos", "code": "PO", "title": "Purchase orders", "file": "purchase_orders.csv", "rows": len(pos), "cols": len(cols_expected["purchase_orders.csv"]),
         "stats": [["POs", len(pos)], ["Open", len(open_pos)], ["Open value", sum(float(p.net_amount) for p in open_pos)], ["Billed", sum(billed.values())]],
         "expected": cols_expected["purchase_orders.csv"], "tab": "pos"},
        {"key": "lines", "code": "PL", "title": "PO line items", "file": "po_lines.csv", "rows": len(lines), "cols": len(cols_expected["po_lines.csv"]),
         "stats": [["Lines", len(lines)], ["POs covered", len(lines_by_po)], ["Avg lines / PO", round(len(lines) / max(1, len(lines_by_po)), 1)], ["Units", sum(l.quantity or 0 for l in lines)]],
         "expected": cols_expected["po_lines.csv"], "tab": "pos"},
        {"key": "history", "code": "IH", "title": "Invoice history", "file": "invoice_history.csv", "rows": len(invs), "cols": len(cols_expected["invoice_history.csv"]),
         "stats": [["Invoices", len(invs)], ["From", min(dates).isoformat() if dates else "—"], ["To", max(dates).isoformat() if dates else "—"], ["Value", sum(float(i.total or 0) for i in invs)]],
         "expected": cols_expected["invoice_history.csv"], "tab": "invoices"},
        {"key": "policy", "code": "PC", "title": "Policy & thresholds", "file": "config.yaml", "rows": 1, "cols": len(cfg.as_dict()),
         "stats": [["Auto tol.", f"{cfg.price_tolerance_auto_pct}%"], ["Review tol.", f"{cfg.price_tolerance_review_pct}%"], ["Dup. window", f"{cfg.duplicate_window_days} d"], ["High value", cfg.auto_approve_max_amount_inr]],
         "expected": ["price_tolerance_auto_pct", "price_tolerance_review_pct", "duplicate_window_days", "min_confidence_critical", "auto_approve_max_amount_inr"], "tab": None},
        {"key": "rules", "code": "RT", "title": "Rule table", "file": "rules.py", "rows": len(RULES), "cols": 6,
         "stats": [["Rules", len(RULES)], ["Stages", 9], ["Reject-level", sum(1 for r in RULES.values() if r["fail"] == "REJECT")], ["Review-level", sum(1 for r in RULES.values() if "REVIEW" in (r["fail"], r["warn"]))]],
         "expected": ["id", "stage", "name", "fail", "warn", "description"], "tab": None},
    ]
    insights = [
        {"label": "Open PO value", "value": sum(float(p.net_amount) - billed[p.po_number] for p in open_pos), "kind": "inr", "sub": f"{len(open_pos)} open purchase orders"},
        {"label": "Blocked vendors", "value": len(blocked), "kind": "n", "sub": "Auto-rejected at Stage 4"},
        {"label": "History window", "value": f"{(max(dates) - min(dates)).days} days" if dates else "—", "kind": "text", "sub": "Used for duplicate detection"},
        {"label": "Stale open POs", "value": len(stale), "kind": "n", "sub": f"Older than {cfg.stale_days} days"},
    ]
    return {"score": score, "groups": groups, "log": log, "cards": cards, "insights": insights,
            "pass": sum(1 for x in log if x["status"] == "Pass"), "warnings": sum(1 for x in log if x["status"] == "Warning"),
            "ready": score >= 80}


# ───────────────────────── waterfall ─────────────────────────
@router.get("/api/waterfall")
def waterfall():
    with Session() as s:
        runs = s.query(Run).filter(Run.status == "done").order_by(Run.started_at).all()
    parsed = [(r, _result(r)) for r in runs]
    total_val = sum(r.total or 0 for r in runs)
    val = defaultdict(float)
    for r in runs:
        val[_dec(r)] += r.total or 0
    # A: value waterfall   received -> rejected -> held for review -> cleared for payment
    value_wf = [
        {"name": "Received", "base": 0, "value": total_val, "kind": "total"},
        {"name": "Rejected", "base": total_val - val["Reject"], "value": val["Reject"], "kind": "Reject"},
        {"name": "Held for review", "base": total_val - val["Reject"] - val["Review"], "value": val["Review"], "kind": "Review"},
        {"name": "Cleared for payment", "base": 0, "value": val["Approve"], "kind": "Approve"},
    ]
    # B: stage funnel
    funnel = [{"no": i + 1, "name": STAGES[i], "entered": 0, "clean": 0, "flagged": 0, "failed": 0} for i in range(9)]
    cells = defaultdict(list)   # (decision, stage_no) -> runs where the stage was not clean
    for r, res in parsed:
        for st in res.get("stages", []):
            i = st["stage_no"] - 1
            if not 0 <= i < 9:
                continue
            funnel[i]["entered"] += 1
            if st["status"] == "pass":
                funnel[i]["clean"] += 1
            elif st["status"] == "warn":
                funnel[i]["flagged"] += 1
            elif st["status"] in ("fail", "error"):
                funnel[i]["failed"] += 1
            if st["status"] in ("warn", "fail", "error"):
                cells[(_dec(r), st["stage_no"])].append({"run_id": r.run_id, "invoice_number": r.invoice_number, "vendor": r.vendor_name,
                                                          "total": r.total, "rule": r.top_rule, "stage_status": st["status"]})
    matrix = [{"decision": d, "stage_no": i, "stage": STAGES[i - 1], "count": len(cells[(d, i)]), "runs": cells[(d, i)]}
              for d in ("Reject", "Review", "Approve") for i in range(1, 8)]
    return {"value": value_wf, "funnel": funnel, "matrix": matrix, "total_runs": len(runs)}


# ───────────────────────── deep dives ─────────────────────────
@router.get("/api/vendors/{vendor_id}/profile")
def vendor_profile(vendor_id: str):
    with Session() as s:
        db = DB(s)
        v = s.get(Vendor, vendor_id)
        if not v:
            raise HTTPException(404)
        pos = s.query(PurchaseOrder).filter_by(vendor_id=vendor_id).order_by(PurchaseOrder.po_number).all()
        po_rows = []
        for p in pos:
            b = float(db.billed_to_date(p.po_number))
            po_rows.append({"po_number": p.po_number, "status": p.status, "net": float(p.net_amount), "billed": b, "remaining": float(p.net_amount) - b, "description": p.description})
        invs = s.query(Invoice).filter_by(vendor_id=vendor_id).order_by(Invoice.invoice_date).all()
        inv_rows = [{"invoice_number": i.invoice_number, "date": i.invoice_date.isoformat() if i.invoice_date else None, "po": i.po_number,
                     "total": float(i.total or 0), "decision": i.decision, "source": "run" if i.run_id else "history", "run_id": i.run_id} for i in invs]
        runs = s.query(Run).filter(Run.status == "done").all()
        mine = [r for r in runs if _result(r).get("vendor", {}).get("vendor_id") == vendor_id or (r.vendor_name or "") == v.legal_name]
        causes = Counter(r.top_rule for r in mine if _dec(r) != "Approve" and r.top_rule)
        cnt = Counter(_dec(r) for r in mine)
        return {"vendor": {c: getattr(v, c) for c in ("vendor_id", "legal_name", "gstin", "state_code", "address", "bank_account_holder",
                                                      "bank_account_no", "ifsc", "approval_status", "payment_terms_days")},
                "pos": po_rows, "invoices": inv_rows,
                "runs": [{"run_id": r.run_id, "invoice_number": r.invoice_number, "total": r.total, "decision": _dec(r), "top_rule": r.top_rule, "at": _iso(r.started_at)} for r in mine],
                "decisions": {"Approve": cnt["Approve"], "Review": cnt["Review"], "Reject": cnt["Reject"]},
                "causes": [{"rule": k, "name": RULES.get(k, {}).get("name", k), "count": c} for k, c in causes.most_common(5)],
                "totals": {"history_value": sum(i["total"] for i in inv_rows), "po_value": sum(p["net"] for p in po_rows), "billed": sum(p["billed"] for p in po_rows),
                           "open_balance": sum(p["remaining"] for p in po_rows if p["status"] == "Open")}}


@router.get("/api/pos/{po_number}/profile")
def po_profile(po_number: str):
    with Session() as s:
        db = DB(s)
        p = s.get(PurchaseOrder, po_number)
        if not p:
            raise HTTPException(404)
        v = s.get(Vendor, p.vendor_id)
        lines = [{"line_no": l.line_no, "description": l.description, "quantity": l.quantity, "unit_price": float(l.unit_price), "amount": l.quantity * float(l.unit_price)} for l in db.po_lines(po_number)]
        invs = s.query(Invoice).filter_by(po_number=po_number).order_by(Invoice.invoice_date, Invoice.invoice_id).all()
        net = float(p.net_amount)
        run_balance, steps = net, []
        for i in invs:
            sub = float(i.subtotal or 0)
            counted = i.decision == "Approve"
            if counted:
                run_balance -= sub
            steps.append({"invoice_number": i.invoice_number, "date": i.invoice_date.isoformat() if i.invoice_date else None, "subtotal": sub,
                          "decision": i.decision, "counted": counted, "balance_after": run_balance, "run_id": i.run_id,
                          "overrun_pct": round(max(0, -run_balance) / net * 100, 1) if net else 0})
        billed = float(db.billed_to_date(po_number))
        return {"po": {"po_number": p.po_number, "vendor_id": p.vendor_id, "vendor_name": v.legal_name if v else p.vendor_id, "status": p.status,
                       "issue_date": p.issue_date.isoformat(), "net": net, "gst_rate_pct": p.gst_rate_pct, "description": p.description,
                       "billed": billed, "remaining": net - billed, "utilisation_pct": round(billed / net * 100, 1) if net else 0},
                "lines": lines, "steps": steps}


@router.get("/api/lookups")
def lookups():
    with Session() as s:
        return {"vendors": [{"id": v.vendor_id, "name": v.legal_name} for v in s.query(Vendor).order_by(Vendor.vendor_id)],
                "pos": [{"id": p.po_number, "name": p.description} for p in s.query(PurchaseOrder).order_by(PurchaseOrder.po_number)]}


# ───────────────────────── action planning ─────────────────────────
OWNER = {1: "AP Clerk", 2: "AP Clerk", 3: "AP Clerk", 4: "Procurement", 5: "AP Manager", 6: "Procurement", 7: "Finance Controller", 8: "AP Manager", 9: "AP Manager"}
STD_TAT_H = {1: 4, 2: 4, 3: 8, 4: 24, 5: 8, 6: 24, 7: 24, 8: 8, 9: 8}


@router.get("/api/actions")
def actions():
    """Queue of non-approved invoices: the stage that stopped each one, who owns that stage, and a standard turnaround."""
    with Session() as s:
        runs = s.query(Run).filter(Run.status == "done").order_by(Run.started_at.desc()).all()
        ex = {e.run_id: e for e in s.query(ExceptionItem).all()}
    rows, now = [], dt.datetime.utcnow()
    for r in runs:
        d = _dec(r)
        if d == "Approve":
            continue
        e = ex.get(r.run_id)
        res = _result(r)
        stg = next((st for st in res.get("stages", []) if st["status"] in ("fail", "error")), None) or next((st for st in res.get("stages", []) if st["status"] == "warn" and st["stage_no"] < 8), None)
        sn = stg["stage_no"] if stg else 8
        age_h = (now - (e.created_at if e else r.started_at)).total_seconds() / 3600
        resolved = bool(e and e.status == "Resolved")
        rows.append({"exception_id": e.id if e else None, "reason": r.reason, "run_id": r.run_id, "invoice_number": r.invoice_number, "vendor": r.vendor_name, "total": r.total, "decision": d,
                     "stage_no": sn, "stage": STAGES[sn - 1], "rule": r.top_rule, "issue": RULES.get(r.top_rule, {}).get("name", r.top_rule) if r.top_rule else "—",
                     "owner": e.assignee if e else OWNER[sn], "stakeholder": OWNER[sn], "std_tat_h": STD_TAT_H[sn], "age_h": round(age_h, 1),
                     "overdue": (not resolved) and age_h > STD_TAT_H[sn], "status": e.status if e else "Open",
                     "priority": (2 if d == "Reject" else 1) * 1_000_000_000 + (r.total or 0)})
    rows.sort(key=lambda x: (x["status"] == "Resolved", -x["priority"]))
    for i, x in enumerate(rows, 1):
        x["rank"] = i
    live = [x for x in rows if x["status"] != "Resolved"]
    return {"rows": rows, "critical": sum(1 for x in live if x["decision"] == "Reject"), "moderate": sum(1 for x in live if x["decision"] == "Review"),
            "resolved": sum(1 for x in rows if x["status"] == "Resolved"), "value_at_risk": sum(x["total"] or 0 for x in live),
            "overdue": sum(1 for x in live if x["overdue"]),
            "buckets": [{"stage_no": i, "stage": STAGES[i - 1], "owner": OWNER[i], "std_tat_h": STD_TAT_H[i],
                         "count": sum(1 for x in live if x["stage_no"] == i), "value": sum(x["total"] or 0 for x in live if x["stage_no"] == i)}
                        for i in range(1, 10)]}


# ───────────────────────── activity feed ─────────────────────────
@router.get("/api/activity")
def activity(limit: int = 30):
    ev = []
    with Session() as s:
        for r in s.query(Run).filter(Run.status == "done").order_by(Run.finished_at.desc()).limit(40):
            ev.append({"ts": _iso(r.finished_at or r.started_at), "kind": "run", "run_id": r.run_id, "decision": r.decision,
                       "text": f"{r.invoice_number or r.filename} from {r.vendor_name or 'unknown vendor'} processed → {r.decision}", "rule": r.top_rule})
        for o in s.query(Override).order_by(Override.ts.desc()).limit(20):
            ev.append({"ts": _iso(o.ts), "kind": "override", "run_id": o.run_id, "text": f"{o.user} chose “{o.action}”" + (f": {o.note}" if o.note else ""), "decision": None, "rule": None})
        for e in s.query(ExceptionItem).filter(ExceptionItem.resolved_at.isnot(None)).order_by(ExceptionItem.resolved_at.desc()).limit(20):
            ev.append({"ts": _iso(e.resolved_at), "kind": "resolved", "run_id": e.run_id, "text": f"Exception resolved ({e.assignee})", "decision": None, "rule": None})
    ev.sort(key=lambda x: x["ts"] or "", reverse=True)
    return ev[:limit]


# ───────────────────────── reference guide (static content for Configuration page) ─────────────────────────
@router.get("/api/guide")
def guide():
    return {
        "stages": [{"no": i + 1, "name": n, "owner": OWNER[i + 1], "std_tat_h": STD_TAT_H[i + 1]} for i, n in enumerate(STAGES)],
        "formulas": [
            {"id": "decision", "title": "Decision order", "formula": "Reject > Review > Approve", "text": "Any REJECT-level finding rejects. Otherwise any REVIEW-level finding sends it to a person. Only a clean run, or one with INFO-level notes, is approved. Unknown rules and stage errors fail safe to Review."},
            {"id": "overrun", "title": "Cumulative PO overrun", "formula": "overrun % = max(0, billed + this invoice − PO net) ÷ PO net × 100", "text": f"At most {cfg.price_tolerance_auto_pct}% passes, up to {cfg.price_tolerance_review_pct}% goes to Review, above that is rejected. Billed counts only approved invoices, so split POs fall in the right order."},
            {"id": "po", "title": "PO inference score", "formula": f"{cfg.po_weight_amount}·Amount + {cfg.po_weight_description}·Description + {cfg.po_weight_lines}·Lines + {cfg.po_weight_timing}·Timing", "text": f"Used only when no PO is printed. Accepted at {cfg.po_infer_min} or more with a {cfg.po_infer_margin} lead over the runner-up, and always sent to Review (R8.2)."},
            {"id": "gst", "title": "GST type", "formula": "buyer state = vendor state → CGST + SGST, else IGST", "text": f"Buyer state is {cfg.buyer_state}. Tax lines must add up to the tax total within ₹{cfg.gst_tolerance_inr}."},
            {"id": "dup", "title": "Duplicate detection", "formula": "D1 number · D2 file hash · D3 vendor+total ≤ window · D4 Levenshtein ≤ 1 + total", "text": f"A reformatted re-send is caught by D3 or D4 even when the number looks different. Window: {cfg.duplicate_window_days} days."},
            {"id": "vendor", "title": "Vendor match", "formula": "token-set ratio ≥ 92 match · 80–91 warn", "text": "GSTIN match is exact. Names are fuzzy-matched; a GSTIN and name that point to different vendors is a Reject."},
            {"id": "conf", "title": "Extraction confidence", "formula": "critical field < 0.80 → Review", "text": "Text PDFs score from the text layer. Scans use OCR word confidence. A field that cannot be read confidently can never lead to auto-approval."},
        ],
        "metrics": [
            {"name": "Touchless rate", "formula": "Approved by the pipeline ÷ all processed × 100", "text": "Share of invoices that needed no human. The headline efficiency number."},
            {"name": "Exception rate", "formula": "(Review + Reject) ÷ all processed × 100", "text": "Share of invoices that landed in the action queue."},
            {"name": "Value at risk", "formula": "Σ total of Review and Reject invoices", "text": "Money held back from payment until someone resolves it."},
            {"name": "Time saved", "formula": f"touchless invoices × {MANUAL_MIN_PER_INVOICE} min", "text": "An assumption, not a measurement: ten minutes of manual handling per invoice."},
            {"name": "Vendor risk score", "formula": "(Review + 2 × Reject) ÷ (2 × runs) × 100", "text": "0–29 Low, 30–59 Medium, 60+ High. Based only on runs in this session."},
        ],
    }
