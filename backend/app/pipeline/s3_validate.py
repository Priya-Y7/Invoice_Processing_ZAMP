import datetime as dt
import re

from ..util import D, parse_date
from .base import StageResult, chk

NAME = "Validate completeness"
GSTIN_FMT = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_FMT = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PLACEHOLDER = {"NA", "N/A", "NONE", "NULL", "0000", "0", "XXXX"}


def today(cfg):
    if cfg.reference_date:
        return dt.date.fromisoformat(cfg.reference_date)
    return dt.date.today()


def run(ctx):
    r = StageResult()
    c = r.checks
    cfg, ex = ctx.cfg, ctx.ex
    F = ex["fields"]
    required = [("invoice_number", "Invoice number"), ("invoice_date", "Invoice date"),
                ("vendor_name", "Vendor name"), ("total_amount", "Total amount")]
    missing = [lbl for k, lbl in required if F.get(k) is None]
    c.append(chk("R3.1", "Required fields present", "fail" if missing else "pass",
                 f"Missing: {', '.join(missing)}" if missing else "Invoice number, date, vendor name and total all present"))
    inv = F.get("invoice_number")
    if inv is not None:
        bad = (not re.fullmatch(r"[A-Za-z0-9/\- ]{1,25}", inv)) or inv.upper().replace("-", "") in PLACEHOLDER
        c.append(chk("R3.2", "Invoice number format", "fail" if bad else "pass",
                     f"'{inv}' is not a valid invoice number" if bad else f"'{inv}' looks valid"))
    d = parse_date(F.get("invoice_date")) if F.get("invoice_date") else None
    if d:
        t = today(cfg)
        due = parse_date(F.get("due_date")) if F.get("due_date") else None
        if d > t + dt.timedelta(days=1):
            res, det = "fail", f"Invoice date {d.isoformat()} is in the future"
        elif (t - d).days > cfg.stale_days:
            res, det = "warn", f"Invoice date {d.isoformat()} is {(t - d).days} days old (limit {cfg.stale_days})"
        elif due and due < d:
            res, det = "warn", f"Due date {due.isoformat()} is before invoice date"
        else:
            res, det = "pass", f"Invoice date {d.isoformat()} is {(t - d).days} days old"
        c.append(chk("R3.3", "Invoice date is sensible", res, det))
    g = F.get("vendor_gstin")
    if g:
        ok = bool(GSTIN_FMT.match(g)) and 1 <= int(g[:2]) <= 38
        c.append(chk("R3.4", "Vendor GSTIN format", "pass" if ok else "fail",
                     f"{g} is well formed" if ok else f"{g} is not a valid GSTIN"))
    tot = F.get("total_amount")
    if tot is not None:
        c.append(chk("R3.5", "Total amount valid", "pass" if D(tot) > 0 else "fail",
                     f"Total {D(tot):,.2f} INR" if D(tot) > 0 else "Total must be greater than zero"))
    ifsc = ex["bank"].get("ifsc")
    if ifsc:
        c.append(chk("R3.6", "IFSC format", "pass" if IFSC_FMT.match(ifsc) else "warn", f"IFSC {ifsc}"))
    bg = F.get("buyer_gstin")
    if bg:
        ok = bg == cfg.buyer_gstin
        c.append(chk("R3.7", "Billed to Helix Retail", "pass" if ok else "fail",
                     f"Bill-to GSTIN {bg} matches {cfg.buyer_name}" if ok else f"Bill-to GSTIN {bg} is not {cfg.buyer_gstin}: billed to the wrong company"))
    if ex["line_items"]:
        bad = [i for i in ex["line_items"] if not i["description"] or i["amount"] is None]
        c.append(chk("R3.8", "Line items complete", "warn" if bad else "pass",
                     f"{len(bad)} line(s) incomplete" if bad else f"{len(ex['line_items'])} line item(s) complete"))
    unc = [k for k in cfg.critical_fields if F.get(k) is not None and ex["confidence"].get(k, 0) < cfg.min_confidence_critical]
    c.append(chk("R3.9", "Critical field confidence", "warn" if unc else "pass",
                 ("Uncertain: " + ", ".join(f"{k} ({ex['confidence'][k]:.2f})" for k in unc)) if unc
                 else f"All critical fields read with confidence >= {cfg.min_confidence_critical:.2f}"))
    r.data = {"missing": missing, "uncertain": unc}
    if missing:
        r.data["vendor_request"] = ("Please resend the invoice with the following clearly legible: " + ", ".join(missing) + ".")
    r.summary = (f"{len(missing)} required field(s) missing: {', '.join(missing)}" if missing else
                 "All required fields present" + (f"; uncertain: {', '.join(unc)}" if unc else ""))
    return r.finalise()
