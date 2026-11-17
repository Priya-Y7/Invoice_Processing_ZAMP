from ..util import levenshtein, norm_number, parse_date
from ..models import Run
from .base import StageResult, chk

NAME = "Duplicate check"


def run(ctx):
    r = StageResult()
    c = r.checks
    cfg = ctx.cfg
    F = ctx.ex["fields"]
    vendor = ctx.vendor
    num = norm_number(F.get("invoice_number"))
    total = F.get("total_amount")
    inv_date = parse_date(F.get("invoice_date")) if F.get("invoice_date") else None
    hist = ctx.db.invoices_for_vendor(vendor.vendor_id) if vendor else []
    d1 = next((h for h in hist if num and h.invoice_number_norm == num), None)
    d3 = next((h for h in hist if total is not None and h.total is not None and abs(float(h.total) - float(total)) < 0.5
               and h.invoice_date and inv_date and abs((h.invoice_date - inv_date).days) <= cfg.duplicate_window_days
               and h is not d1), None)
    d4 = next((h for h in hist if num and h.invoice_number_norm and h.invoice_number_norm != num
               and levenshtein(h.invoice_number_norm, num) <= 1 and total is not None and h.total is not None
               and abs(float(h.total) - float(total)) < 0.5), None)
    prior = ctx.file.get("seen_run")
    sig = {"D1": False, "D2": False, "D3": False, "D4": False}
    if d1:
        sig["D1"] = True
        c.append(chk("R5.1", "Same vendor and invoice number", "fail",
                     f"Invoice {d1.invoice_number} from this vendor was already processed ({d1.invoice_date}, total {float(d1.total):,.2f}); '{F.get('invoice_number')}' normalises to the same number {num}"))
    else:
        c.append(chk("R5.1", "Same vendor and invoice number", "pass", "No earlier invoice with this number from this vendor" if num else "No invoice number to compare"))
    if prior:
        sig["D2"] = True
        c.append(chk("R5.2", "Identical file", "fail", f"The identical file (same SHA-256) was already processed in run {prior}"))
    else:
        c.append(chk("R5.2", "Identical file", "pass", "File hash not seen before"))
    if d3 and not (sig["D1"] or sig["D2"]):
        sig["D3"] = True
        c.append(chk("R5.3", "Same amount within 90 days", "warn",
                     f"{d3.invoice_number} has the same total {float(d3.total):,.2f} within {cfg.duplicate_window_days} days: probable duplicate or a repeat charge"))
    else:
        c.append(chk("R5.3", "Same amount within 90 days", "pass", "No same-amount invoice in the window"))
    if d4 and not (sig["D1"] or sig["D2"] or sig["D3"]):
        sig["D4"] = True
        c.append(chk("R5.4", "Near-identical invoice number", "warn",
                     f"Invoice number differs from {d4.invoice_number} by one character and the total is identical: probable duplicate with a typo"))
    else:
        c.append(chk("R5.4", "Near-identical invoice number", "pass", "No near-identical invoice number"))
    r.data = {"signals": sig, "matched_invoice": (d1 or d3 or d4).invoice_number if (d1 or d3 or d4) else None}
    fired = [k for k, v in sig.items() if v]
    r.summary = ("Duplicate signals: " + ", ".join(fired)) if fired else "No duplicate found"
    return r.finalise()
