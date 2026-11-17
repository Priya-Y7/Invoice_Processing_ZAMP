from ..rules import ORDER, RULES, level_of
from ..util import inr
from .base import StageResult, chk

NAME = "Decide"

ACTIONS = {
    "R3.1": "Ask the vendor to resend with the missing fields legible",
    "R3.2": "Confirm the invoice number with the vendor",
    "R3.3": "Check the invoice date with the vendor",
    "R3.4": "Verify the vendor GSTIN on the invoice",
    "R3.5": "Verify the invoice total",
    "R3.9": "Compare the uncertain fields against the PDF image",
    "R2.5": "Compare the extracted values against the PDF image",
    "R4.1": "Confirm the vendor identity in the vendor master",
    "R4.5": "Verify the bank details with the vendor before any payment",
    "R5.3": "Check whether this is a repeat charge or a duplicate",
    "R5.4": "Check whether this invoice number is a typo of an earlier one",
    "R6.6": "Confirm which PO this invoice belongs to",
    "R7.1": "Re-check line arithmetic with the vendor",
    "R7.2": "Re-check the line totals against the subtotal",
    "R7.3": "Verify the total amount on the original document",
    "R7.4": "Ask the vendor to reissue with the correct tax type",
    "R7.5": "Verify the GST rate and tax amount",
    "R7.6": "Check the unit price against the PO",
    "R7.7": "Approve the over-run against the PO or ask for a credit note",
    "R7.9": "High-value invoice: manager sign-off required",
    "R8.2": "Confirm the PO the system inferred",
    "R8.3": "Re-read the uncertain critical fields",
    "R8.4": "High-value invoice: manager sign-off required",
}


def _verdict_sentence(ctx, verdict, findings):
    F = ctx.ex["fields"]
    vend = ctx.vendor.legal_name if ctx.vendor else (F.get("vendor_name") or "unknown vendor")
    inv = F.get("invoice_number") or "(number unreadable)"
    tot = ("total " + inr(F.get("total_amount"))) if F.get("total_amount") is not None else "total unreadable"
    who = f"Invoice {inv} from {vend}, {tot}."
    if verdict == "Approve":
        n = ctx.numeric or {}
        po = ctx.po.po_number if ctx.po else "its PO"
        tail = (f"Approve: vendor is approved, {po} matched, no duplicate found and the numbers agree"
                + (f"; PO balance moves from {inr(n['remaining_before'])} to {inr(n['remaining_after'])}" if "remaining_after" in n else "") + ".")
        return f"{tail} {who}"
    body = " ".join(f"{f['detail'].rstrip('.')} ({f['rule']})." for f in findings[:4])
    more = f" Plus {len(findings) - 4} more finding(s)." if len(findings) > 4 else ""
    return f"{verdict}: {body}{more} {who}"


def run(ctx):
    r = StageResult()
    findings = []
    for no in range(1, 8):
        res = ctx.results.get(no)
        if not res:
            continue
        if res.status == "error":
            findings.append({"rule": "R8.5", "label": f"Stage {no} error", "result": "error", "level": "REVIEW",
                             "detail": res.summary or f"Stage {no} failed unexpectedly; routed to a human", "stage": no})
            continue
        for ck in res.checks:
            lvl = level_of(ck["rule"], ck["result"])
            if lvl:
                findings.append({**ck, "level": lvl, "stage": no})
    # explicit gates (R8.2, R8.3, R8.4)
    if ctx.po_inferred:
        findings.append({"rule": "R8.2", "label": "Inferred PO", "result": "warn", "level": "REVIEW", "stage": 8,
                         "detail": f"The invoice did not print a PO; {ctx.po.po_number} was inferred, so a human must confirm it"})
    unc = [k for k in ctx.cfg.critical_fields if ctx.f(k) is not None and ctx.conf(k) < ctx.cfg.min_confidence_critical]
    if unc:
        findings.append({"rule": "R8.3", "label": "Uncertain critical field", "result": "warn", "level": "REVIEW", "stage": 8,
                         "detail": "Critical field(s) read with confidence below " + f"{ctx.cfg.min_confidence_critical:.2f}: " + ", ".join(unc)})
    tot = ctx.f("total_amount")
    if tot is not None and float(tot) > ctx.cfg.auto_approve_max_amount_inr and not any(f["rule"] == "R7.9" for f in findings):
        findings.append({"rule": "R8.4", "label": "High value", "result": "warn", "level": "REVIEW", "stage": 8,
                         "detail": f"Total {inr(tot)} is above the auto-approve limit"})
    findings.sort(key=lambda f: (ORDER[f["level"]], f["stage"]))
    rej = [f for f in findings if f["level"] == "REJECT"]
    rev = [f for f in findings if f["level"] == "REVIEW"]
    if rej:
        verdict = "Reject"
    elif rev:
        verdict = "Review"
    else:
        verdict = "Approve"
    deciding = rej if verdict == "Reject" else rev if verdict == "Review" else []
    info = [f for f in findings if f["level"] == "INFO"]
    reason = _verdict_sentence(ctx, verdict, deciding or info)
    trail = [{"rule": f["rule"], "level": f["level"], "stage": f["stage"], "label": f["label"], "detail": f["detail"]} for f in findings]
    what_to_check = []
    if verdict == "Review":
        seen = set()
        for f in rev:
            a = ACTIONS.get(f["rule"])
            if a and a not in seen:
                what_to_check.append({"rule": f["rule"], "action": a, "detail": f["detail"]})
                seen.add(a)
    vendor_msg = None
    if verdict == "Reject" or (verdict == "Review" and ctx.results.get(3) and ctx.results[3].data.get("vendor_request")):
        vendor_msg = _vendor_message(ctx, verdict, rej, ctx.results.get(3).data.get("vendor_request") if ctx.results.get(3) else None)
    next_action = {"Approve": "Ready to post for payment", "Review": "Assigned to the AP manager's queue",
                   "Reject": "Return to the vendor with the drafted message"}[verdict]
    ctx.decision = {"verdict": verdict, "reason": reason, "reason_source": "template", "trail": trail,
                    "top_rule": (deciding[0]["rule"] if deciding else None), "next_action": next_action,
                    "what_to_check": what_to_check, "vendor_message": vendor_msg}
    r.checks.append(chk("R8.1", "Decision order applied", "pass",
                        f"{len(rej)} reject-level, {len(rev)} review-level, {len(info)} info finding(s) => {verdict}"))
    r.data = ctx.decision
    r.summary = f"{verdict}: " + (f"{deciding[0]['rule']} {deciding[0]['label']}" if deciding else "no blocking findings")
    r.status = {"Approve": "pass", "Review": "warn", "Reject": "fail"}[verdict]
    return r


def _vendor_message(ctx, verdict, rej, request):
    F = ctx.ex["fields"]
    vend = ctx.vendor.legal_name if ctx.vendor else (F.get("vendor_name") or "Vendor")
    inv = F.get("invoice_number") or "(number not legible)"
    lines = [f"Dear {vend} accounts team,", "",
             f"We have reviewed invoice {inv} dated {F.get('invoice_date') or 'n/a'} and cannot process it for payment."]
    if rej:
        lines.append("Reason(s):")
        lines += [f"  - {f['detail'].rstrip('.')}." for f in rej[:4]]
    if request:
        lines += ["", request]
    lines += ["", "Please resend a corrected invoice quoting the correct purchase order number. If you believe this is an error, reply to this message.", "", "Regards,", f"Accounts Payable, {ctx.cfg.buyer_name}"]
    return "\n".join(lines)
