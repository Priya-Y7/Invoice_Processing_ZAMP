from decimal import Decimal

from rapidfuzz import fuzz

from ..util import D, inr, norm_name
from .base import StageResult, chk

NAME = "Three-way numeric check"


def _band(pct, cfg):
    if pct <= cfg.price_tolerance_auto_pct:
        return "pass"
    return "warn" if pct <= cfg.price_tolerance_review_pct else "fail"


def run(ctx):
    r = StageResult()
    c = r.checks
    cfg, ex = ctx.cfg, ctx.ex
    F = ex["fields"]
    tol = D(cfg.gst_tolerance_inr)
    lines = ex["line_items"]
    sub, tax, total = D(F.get("subtotal")), D(F.get("tax_total")), D(F.get("total_amount"))
    num = {}
    # R7.1 line arithmetic
    if lines:
        bad = [l for l in lines if abs(D(l["quantity"]) * D(l["unit_price"]) - D(l["amount"])) > tol]
        c.append(chk("R7.1", "Line arithmetic", "warn" if bad else "pass",
                     (f"{len(bad)} line(s) where quantity x unit price differs from amount: {bad[0]['description']}") if bad
                     else f"quantity x unit price equals amount on all {len(lines)} line(s)"))
        ssum = sum((D(l["amount"]) for l in lines), D(0))
        if sub is not None:
            ok = abs(ssum - sub) <= tol
            c.append(chk("R7.2", "Lines add up to subtotal", "pass" if ok else "warn",
                         f"Lines sum to {inr(ssum)}; subtotal printed {inr(sub)}"))
    # R7.3
    if total is None or sub is None:
        c.append(chk("R7.3", "Subtotal + tax = total", "fail",
                     "The total amount could not be read reliably, so subtotal + tax cannot be verified" if total is None
                     else "Subtotal missing, cannot verify the total"))
    else:
        calc = sub + (tax or D(0))
        ok = abs(calc - total) <= tol
        c.append(chk("R7.3", "Subtotal + tax = total", "pass" if ok else "fail",
                     f"{inr(sub)} + {inr(tax or 0)} = {inr(calc)}; invoice total {inr(total)}"))
    # R7.4 tax type
    types = {t["type"] for t in ex["tax_lines"]}
    vstate = (ctx.vendor.state_code if ctx.vendor else (F.get("vendor_gstin") or "")[:2]) or ""
    if types:
        intra = vstate == cfg.buyer_state
        want = {"CGST", "SGST"} if intra else {"IGST"}
        ok = types == want
        c.append(chk("R7.4", "Tax type is right", "pass" if ok else "warn",
                     f"Vendor state {vstate} vs buyer state {cfg.buyer_state}: expected {' + '.join(sorted(want))}; invoice charges {' + '.join(sorted(types))}"))
    # R7.5 tax rate and amount
    rate = D(ctx.po.gst_rate_pct if ctx.po else 18)
    if sub is not None and tax is not None:
        exp = (sub * rate / 100).quantize(Decimal("0.01"))
        ok = abs(exp - tax) <= tol
        c.append(chk("R7.5", "Tax rate and amount", "pass" if ok else "warn",
                     f"{rate}% of {inr(sub)} = {inr(exp)}; invoice tax {inr(tax)}"))
    # PO based
    po = ctx.po
    if po is not None:
        plines = ctx.db.po_lines(po.po_number)
        worst, notes = ("pass", 0.0), []
        for l in lines:
            m = max(plines, key=lambda p: fuzz.token_set_ratio(norm_name(l["description"]), norm_name(p.description)), default=None)
            if m is None or fuzz.token_set_ratio(norm_name(l["description"]), norm_name(m.description)) < 60:
                continue
            if D(l["quantity"]) == 1 and m.quantity > 1:
                notes.append(f"'{l['description']}' is a bundled line; compared in total (R7.7)")
                continue
            pv = (D(l["unit_price"]) - D(m.unit_price)) / D(m.unit_price) * 100
            res = _band(float(abs(pv)) if pv > 0 else 0.0, cfg)
            qty_over = l["quantity"] > m.quantity
            if qty_over:
                res = "fail" if (l["quantity"] - m.quantity) / m.quantity * 100 > cfg.price_tolerance_review_pct else max(res, "warn", key=lambda x: ["pass", "warn", "fail"].index(x))
            notes.append(f"'{l['description']}': {inr(l['unit_price'])} vs PO {inr(m.unit_price)} ({float(pv):+.1f}%)"
                         + (f"; quantity {l['quantity']:g} > PO {m.quantity:g}" if qty_over else ""))
            if ["pass", "warn", "fail"].index(res) > ["pass", "warn", "fail"].index(worst[0]):
                worst = (res, float(pv))
        c.append(chk("R7.6", "Line price within tolerance", worst[0],
                     "; ".join(notes) if notes else "No invoice line could be compared to a PO line"))
        B = ctx.db.billed_to_date(po.po_number)
        N = D(po.net_amount)
        S = sub if sub is not None else sum((D(l["amount"]) for l in lines), D(0))
        over = max(D(0), B + S - N) / N * 100
        res = _band(float(over), cfg)
        c.append(chk("R7.7", "Cumulative PO overrun", res,
                     f"{po.po_number} is {inr(N)} and {inr(B)} is already billed, leaving {inr(N - B)}; this invoice bills {inr(S)}, "
                     f"so the balance would be {inr(N - B - S)} (overrun {float(over):.1f}% of the PO)"))
        num.update({"po_net": float(N), "billed_before": float(B), "invoice_subtotal": float(S),
                    "remaining_before": float(N - B), "remaining_after": float(N - B - S), "overrun_pct": round(float(over), 2)})
        c.append(chk("R7.8", "Currency matches PO", "pass", f"Invoice and PO both in {po.currency}"))
    if total is not None:
        hv = total > D(cfg.auto_approve_max_amount_inr)
        c.append(chk("R7.9", "High-value invoice", "warn" if hv else "pass",
                     f"Total {inr(total)} " + (f"is above the {inr(cfg.auto_approve_max_amount_inr)} limit" if hv else f"is within the {inr(cfg.auto_approve_max_amount_inr)} limit")))
    r.data = num
    bad = [x for x in c if x["result"] != "pass"]
    r.summary = ("All numeric checks pass" + (f"; PO balance after this invoice {inr(num['remaining_after'])}" if "remaining_after" in num else "")
                 if not bad else f"{len(bad)} numeric check(s) flagged: " + ", ".join(x["rule"] for x in bad))
    return r.finalise()
