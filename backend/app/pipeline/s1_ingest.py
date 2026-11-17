import io

from ..util import sha256
from .base import StageResult, chk

NAME = "Ingest"


def run(ctx):
    cfg, data = ctx.cfg, ctx.data
    r = StageResult()
    c = r.checks
    ok_pdf = data[:5] == b"%PDF-" and ctx.filename.lower().endswith(".pdf")
    c.append(chk("R1.1", "Readable PDF", "pass" if ok_pdf else "fail",
                 "Valid PDF header" if ok_pdf else "This file is not a readable PDF"))
    size_mb = len(data) / 1048576
    c.append(chk("R1.2", "File size", "pass" if size_mb <= cfg.max_file_mb else "fail",
                 f"{size_mb:.2f} MB (limit {cfg.max_file_mb} MB)"))
    if not ok_pdf:
        r.summary = "This file is not a readable PDF"
        ctx.ended = True
        return r.finalise()
    import fitz
    pages, encrypted = 0, False
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        encrypted = bool(doc.needs_pass)
        pages = doc.page_count
    except Exception:
        c[0] = chk("R1.1", "Readable PDF", "fail", "The PDF could not be opened (corrupt file)")
        r.summary = "This file is not a readable PDF"
        ctx.ended = True
        return r.finalise()
    c.append(chk("R1.4", "Not password protected", "fail" if encrypted else "pass",
                 "Password-protected: ask the vendor for an unprotected copy" if encrypted else "Not encrypted"))
    if encrypted:
        r.summary = "PDF is password-protected; ask the vendor for an unprotected copy"
        ctx.ended = True
        return r.finalise()
    read_pages = min(pages, cfg.max_pages)
    c.append(chk("R1.3", "Page count", "warn" if pages > cfg.max_pages else "pass",
                 f"{pages} pages" + (f"; reading the first {cfg.max_pages}" if pages > cfg.max_pages else "")))
    chars = 0
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            chars = sum(len((p.extract_text() or "").strip()) for p in pdf.pages[:read_pages])
    except Exception:
        chars = 0
    density = chars / max(1, read_pages)
    doc_type = "text" if density >= cfg.min_text_density else "scan"
    c.append(chk("R1.5", "Reading path", "pass",
                 f"{density:.0f} characters per page => {'text layer found, reading text' if doc_type == 'text' else 'no text layer, reading by OCR'}"))
    sha = sha256(data)
    seen = ctx.db.run_with_hash(sha, ctx.run_id)
    c.append(chk("R1.6", "File not seen before", "warn" if seen else "pass",
                 f"Identical file already processed in run {seen}" if seen else "First time this file is seen"))
    ctx.file = {"name": ctx.filename, "size_kb": round(len(data) / 1024, 1), "pages": pages, "sha256": sha,
                "doc_type": doc_type, "density": round(density, 1), "seen_run": seen}
    r.summary = f"{ctx.filename} · {pages} page{'s' if pages != 1 else ''} · {round(len(data)/1024)} KB · " + \
                ("text layer found" if doc_type == "text" else "no text layer, will use OCR")
    r.data = ctx.file
    return r.finalise()
