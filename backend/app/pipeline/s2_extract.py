from .. import extractor
from .base import StageResult, chk

NAME = "Extract"


def run(ctx):
    r = StageResult()
    mode, n, lines, info = extractor.read_pages(ctx.data, ctx.filename, ctx.cfg)
    ex = extractor.parse(lines, mode)
    overall, cmin, crit = extractor.overall_confidence(ex, ctx.cfg)
    ex["source"] = "text_pdf" if mode == "text" else "scanned_image"
    ex["overall_confidence"], ex["critical_min"], ex["critical"] = overall, cmin, crit
    ex["raw_text"] = "\n".join(l.text for l in lines)
    ex["read_info"] = info
    ctx.ex = ex
    F = ex["fields"]
    found = sum(1 for k in ("invoice_number", "invoice_date", "vendor_name", "po_reference", "subtotal", "total_amount")
                if F.get(k) is not None)
    r.checks.append(chk("R2.1", "Invoice record produced", "pass" if lines and found >= 2 else "fail",
                        f"{len(lines)} lines read via {'text layer' if mode == 'text' else 'OCR'}; {found} of 6 key fields found"))
    r.checks.append(chk("R2.3", "Dates are real dates", "pass" if (F.get("invoice_date") or "date" not in ex["raw_text"].lower()) else "warn",
                        f"Invoice date {F.get('invoice_date') or 'not read'}"))
    res = "pass"
    if cmin and cmin < ctx.cfg.min_confidence_critical:
        res = "warn"
    elif overall < 0.90:
        res = "warn"
    r.checks.append(chk("R2.5", "Extraction confidence", res,
                        f"Overall confidence {overall:.2f} (a clean read is 0.90 or more); lowest critical field {cmin:.2f} (needs {ctx.cfg.min_confidence_critical:.2f})"))
    r.data = {"source": ex["source"], "overall_confidence": overall, "critical_min": cmin}
    r.summary = (f"Read {'text layer' if mode == 'text' else 'scanned image by OCR'}; "
                 f"{found} key fields found, overall confidence {overall:.0%}")
    if not lines or found < 2:
        r.status = "fail"
        r.summary = "Extraction unavailable: nothing usable could be read"
    return r.finalise()
