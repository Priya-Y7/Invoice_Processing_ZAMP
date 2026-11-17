import datetime as dt

from rapidfuzz import fuzz

from ..util import D, norm_name, parse_date
from .base import StageResult, chk

NAME = "PO match"


def _desc_sim(a, b):
    return fuzz.token_set_ratio(norm_name(a), norm_name(b)) / 100.0


def score_po(ctx, po):
    """Confidence = 0.35 A + 0.35 D + 0.20 L + 0.10 T (spec Stage 6)."""
    cfg, ex = ctx.cfg, ctx.ex
    sub = D(ex["fields"].get("subtotal")) or sum((i["amount"] or 0 for i in ex["line_items"]), D(0))
    sub = D(sub) or D(0)
    remaining = ctx.db.remaining(po)
    if remaining > 0 and sub > 0:
        a = max(0.0, 1.0 - float(abs(sub - remaining) / max(remaining, sub)))
    else:
        a = 0.0
    inv_text = " ".join(i["description"] for i in ex["line_items"]) or (ex["fields"].get("vendor_name") or "")
    plines = ctx.db.po_lines(po.po_number)
    po_text = (po.description or "") + " " + " ".join(p.description for p in plines)
    d = _desc_sim(inv_text, po_text)
    if ex["line_items"]:
        hit = sum(1 for i in ex["line_items"] if any(_desc_sim(i["description"], p.description) >= 0.70 for p in plines))
        l = hit / len(ex["line_items"])
    else:
        l = 0.0
    inv_date = parse_date(ex["fields"].get("invoice_date")) if ex["fields"].get("invoice_date") else None
    if inv_date and po.issue_date:
        gap = (inv_date - po.issue_date).days
        t = 1.0 if 0 <= gap <= 180 else 0.5 if gap > 180 else 0.0
    else:
        t = 0.5
    w = cfg
    conf = w.po_weight_amount * a + w.po_weight_description * d + w.po_weight_lines * l + 0.10 * t
    return {"po_number": po.po_number, "confidence": round(conf, 3), "amount": round(a, 3), "description": round(d, 3),
            "lines": round(l, 3), "timing": round(t, 3), "remaining": float(remaining), "net_amount": float(po.net_amount),
            "status": po.status, "po_description": po.description}


def run(ctx):
    r = StageResult()
    c = r.checks
    cfg, F = ctx.cfg, ctx.ex["fields"]
    vendor = ctx.vendor
    if vendor is None:
        r.status = "skipped"
        r.summary = "Skipped: vendor unknown, no PO to match against"
        return r
    vpos = ctx.db.pos_for_vendor(vendor.vendor_id)
    printed = F.get("po_reference")
    cands = sorted((score_po(ctx, po) for po in vpos if po.status == "Open" or po.po_number == printed),
                   key=lambda x: -x["confidence"])
    r.data = {"printed": printed, "candidates": cands[:4]}
    po = None
    inferred = False
    if printed:
        po = ctx.db.po(printed)
        if po is None:
            c.append(chk("R6.1", "Printed PO exists", "warn", f"{printed} is not in the PO table; trying to infer the PO"))
        else:
            c.append(chk("R6.1", "Printed PO exists", "pass", f"{printed} found ({po.description})"))
    else:
        c.append(chk("R6.1", "Printed PO exists", "warn", "No PO reference on the invoice; inferring from amount, description and dates"))
    if po is not None:
        c.append(chk("R6.2", "PO is open", "pass" if po.status == "Open" else "fail",
                     f"{po.po_number} is {po.status}" + ("" if po.status == "Open" else ": fully billed, no further invoices accepted")))
        c.append(chk("R6.3", "PO belongs to vendor", "pass" if po.vendor_id == vendor.vendor_id else "fail",
                     f"{po.po_number} was issued to {po.vendor_id}" + ("" if po.vendor_id == vendor.vendor_id else f", not to {vendor.vendor_id}")))
        mine = next((x for x in cands if x["po_number"] == po.po_number), None) or score_po(ctx, po)
        others = [x for x in cands if x["po_number"] != po.po_number and x["status"] == "Open"]
        if mine["confidence"] < 0.40 and others and others[0]["confidence"] >= cfg.po_infer_min:
            c.append(chk("R6.6", "Printed PO plausible", "warn",
                         f"Printed {po.po_number} scores {mine['confidence']:.2f} but {others[0]['po_number']} scores {others[0]['confidence']:.2f}: the printed PO may be wrong"))
        else:
            c.append(chk("R6.6", "Printed PO plausible", "pass", f"Printed PO scores {mine['confidence']:.2f} against the invoice"))
        r.data["match_confidence"] = mine["confidence"]
    else:
        open_c = [x for x in cands if x["status"] == "Open"]
        if not open_c:
            c.append(chk("R6.5", "Vendor has a candidate PO", "fail", f"{vendor.legal_name} has no open purchase order"))
        else:
            best = open_c[0]
            lead = best["confidence"] - (open_c[1]["confidence"] if len(open_c) > 1 else 0.0)
            ok = best["confidence"] >= cfg.po_infer_min and lead >= cfg.po_infer_margin
            c.append(chk("R6.4", "Inferred PO is unambiguous", "pass" if ok else "fail",
                         f"Best candidate {best['po_number']} scores {best['confidence']:.2f} (needs >= {cfg.po_infer_min}), lead {lead:.2f} (needs >= {cfg.po_infer_margin})"))
            if ok:
                po, inferred = ctx.db.po(best["po_number"]), True
                r.data["match_confidence"] = best["confidence"]
                r.data["lead"] = round(lead, 3)
    ctx.po, ctx.po_inferred = po, inferred
    r.data.update({"matched_po": po.po_number if po else None, "inferred": inferred})
    if po:
        r.data["remaining_before"] = float(ctx.db.remaining(po))
        r.data["po_net"] = float(po.net_amount)
        r.summary = (f"Matched {po.po_number}" + (" (inferred, not printed on the invoice)" if inferred else " (printed on the invoice)")
                     + f"; remaining balance {float(ctx.db.remaining(po)):,.2f}")
    else:
        r.summary = "No purchase order could be matched"
    return r.finalise()
