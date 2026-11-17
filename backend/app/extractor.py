"""Local invoice extractor: pdfplumber text (digital) or PyMuPDF + Tesseract OCR (scans).

Both paths produce a list of Lines (text + per-word confidence); a single label-driven parser
turns the lines into the structured extraction with a confidence per field. No LLM is called.
"""
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal

from .util import D, parse_date

GSTIN_RE = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9][Z2][A-Z0-9])\b")
GSTIN_LOOSE = re.compile(r"\b(\d{2}[A-Z0-9]{13})\b")
IFSC_RE = re.compile(r"\b([A-Z]{4}[0O][A-Z0-9]{6})\b")
PO_RE = re.compile(r"\bPO[-\s]?\d{4}[-\s]?\d{3,5}\b", re.I)
NUM_RE = re.compile(r"(?<![\w/])[\d][\d,]*(?:\.\d+)?(?![\w/-])")
MONEY_TOKEN = re.compile(r"^[₹Rs.]*\s*-?[\d][\d,]*(?:\.\d{1,2})?$")

L_INVNO = r"(?:invoice\s*(?:no|number|num|#)|inv\.?\s*(?:no|#)|bill\s*(?:no|number|#))"
L_DATE = r"(?:invoice\s*date|bill\s*date|dated|date)"
L_DUE = r"(?:due\s*date|payment\s*due)"
L_PO = r"(?:po\s*reference|po\s*ref|po\s*no|po\s*number|purchase\s*order|order\s*ref|your\s*po|po)"
L_SUB = r"(?:sub\s*total|taxable\s*(?:value|amount)|total\s*before\s*tax|net\s*amount|amount\s*before\s*tax)"
L_TOTAL = r"(?:total\s*amount|grand\s*total|amount\s*payable|invoice\s*total|total\s*payable|total\s*invoice\s*value|net\s*payable)"
TAX_RE = re.compile(r"^(CGST|SGST|IGST|UTGST|CESS)\b[^\d%]*?\(?\s*@?\s*(\d+(?:\.\d+)?)\s*%?\)?\s+(?:₹|Rs\.?)?\s*([\d,]+(?:\.\d+)?)\s*$", re.I)


@dataclass
class Word:
    text: str
    conf: float  # 0..1


@dataclass
class Line:
    text: str
    words: list = field(default_factory=list)
    page: int = 1

    def conf_of_tail(self, value: str) -> float:
        n = len(value.split())
        if not self.words or n == 0:
            return 1.0
        tail = self.words[-n:]
        return min(w.conf for w in tail)


def _line_from_text(t, page, conf=0.99):
    return Line(t, [Word(w, conf) for w in t.split()], page)


def read_pages(data: bytes, filename: str, cfg):
    """Return (mode, page_count, lines, info) - mode is 'text' or 'scan'."""
    import pdfplumber
    info = {"text_chars_per_page": [], "ocr": None}
    if not filename.lower().endswith(".pdf"):
        return _read_image(data, info)
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        n = len(pdf.pages)
        texts = [(p.extract_text() or "") for p in pdf.pages[: cfg.max_pages]]
    info["text_chars_per_page"] = [len(t.strip()) for t in texts]
    density = sum(info["text_chars_per_page"]) / max(1, len(texts))
    info["density"] = round(density, 1)
    if density >= cfg.min_text_density:
        lines = []
        for pi, t in enumerate(texts, 1):
            for raw in t.splitlines():
                if raw.strip():
                    lines.append(_line_from_text(raw.strip(), pi))
        return "text", n, lines, info
    return _ocr_pdf(data, n, cfg, info)


def _read_image(data, info):
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert("RGB")
    lines, meta = _ocr_images([img])
    info["ocr"] = meta
    return "scan", 1, lines, info


def _ocr_pdf(data, n, cfg, info):
    import fitz
    from PIL import Image
    doc = fitz.open(stream=data, filetype="pdf")
    imgs = []
    for i in range(min(len(doc), cfg.max_pages)):
        pix = doc[i].get_pixmap(dpi=200)
        imgs.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    lines, meta = _ocr_images(imgs)
    info["ocr"] = meta
    return "scan", n, lines, info


def _ocr_images(imgs):
    import pytesseract
    lines, confs = [], []
    for pi, img in enumerate(imgs, 1):
        d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 6")
        groups = {}
        for i, txt in enumerate(d["text"]):
            txt = txt.strip()
            c = float(d["conf"][i])
            if not txt or c < 0:
                continue
            key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
            groups.setdefault(key, []).append(Word(txt, c / 100.0))
            confs.append(c / 100.0)
        for key in sorted(groups):
            ws = groups[key]
            lines.append(Line(" ".join(w.text for w in ws), ws, pi))
    return lines, {"words": len(confs), "mean_conf": round(sum(confs) / max(1, len(confs)), 3)}


# ───────────────────────── field parsing ─────────────────────────

def _label_value(lines, label_re, value_re=r"(.+?)"):
    """Find 'label [:] value' on one line. Returns (value, conf, line) or None."""
    rx = re.compile(rf"^\W*{label_re}\W*?\s*[:\-]?\s*{value_re}\s*$", re.I)
    for ln in lines:
        m = rx.match(ln.text)
        if m and m.group(1).strip():
            v = m.group(1).strip(" :-|")
            if v:
                return v, ln.conf_of_tail(v), ln
    return None


def _money(tok):
    t = tok.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(" ", "")
    return D(t)


def _last_money(text):
    toks = text.split()
    for tok in reversed(toks):
        if MONEY_TOKEN.match(tok.replace("₹", "")):
            return _money(tok), tok
    return None, None


def _find_amount(lines, label_re, idx_hint=None):
    rx = re.compile(rf"^\W*{label_re}\b", re.I)
    for ln in lines:
        if rx.match(ln.text):
            amt, tok = _last_money(ln.text)
            if amt is not None:
                conf = ln.words[-1].conf if ln.words else 1.0
                # token-level confidence of the number itself
                for w in reversed(ln.words):
                    if w.text.replace("₹", "") == tok.replace("₹", ""):
                        conf = w.conf
                        break
                return amt, conf
            # label found but number unreadable
            return None, min((w.conf for w in ln.words[-2:]), default=0.0)
    return None, 0.0


def parse(lines, mode):
    out = {"fields": {}, "confidence": {}, "line_items": [], "tax_lines": [], "bank": {}, "notes": []}
    F, C = out["fields"], out["confidence"]
    scale = 1.0 if mode == "text" else 0.97

    def put(k, v, c):
        F[k] = v
        C[k] = round(min(c, 1.0) * (scale if v is not None else 1), 3) if v is not None else 0.0

    # invoice number
    r = _label_value(lines, L_INVNO, r"([A-Za-z0-9][A-Za-z0-9/\-_.]{1,30})")
    inv = None
    if r:
        v, c, _ = r
        v = v.rstrip(".")
        if len(v) >= 4 and re.search(r"\d", v) and not re.fullmatch(r"[A-Za-z]+", v):
            inv = (v, c)
    put("invoice_number", inv[0] if inv else None, inv[1] if inv else 0)

    # dates
    r = _label_value(lines, L_DATE, r"(\d{1,2}[\s/\-.][A-Za-z0-9]{1,9}[\s/\-.]\d{2,4})")
    d = parse_date(r[0]) if r else None
    put("invoice_date", d.isoformat() if d else None, r[1] if r and d else 0)
    r = _label_value(lines, L_DUE, r"(\d{1,2}[\s/\-.][A-Za-z0-9]{1,9}[\s/\-.]\d{2,4})")
    d = parse_date(r[0]) if r else None
    put("due_date", d.isoformat() if d else None, r[1] if r and d else 0)

    # PO reference
    po = None
    r = _label_value(lines, L_PO, r"(PO[-\s]?\d{4}[-\s]?\d{3,5})")
    if r:
        po = (re.sub(r"\s", "-", r[0].upper()), r[1])
    else:
        for ln in lines:
            m = PO_RE.search(ln.text)
            if m:
                po = (re.sub(r"\s", "-", m.group(0).upper()), ln.conf_of_tail(m.group(0)))
                break
    put("po_reference", po[0] if po else None, po[1] if po else 0)

    # vendor name = first non-title line
    vendor = None
    for ln in lines[:6]:
        t = ln.text.strip()
        if re.fullmatch(r"(tax\s+)?invoice|bill|original( for recipient)?", t, re.I):
            continue
        if len(t) >= 4 and re.search(r"[A-Za-z]{3}", t):
            vendor = (t, min((w.conf for w in ln.words), default=1.0))
            break
    put("vendor_name", vendor[0] if vendor else None, vendor[1] if vendor else 0)

    # GSTINs: first = vendor, one after 'Bill To' = buyer
    gst = []
    for i, ln in enumerate(lines):
        m = GSTIN_RE.search(ln.text) or (GSTIN_LOOSE.search(ln.text) if re.search(r"gstin", ln.text, re.I) else None)
        if m:
            gst.append((m.group(1), ln.conf_of_tail(m.group(1)), i))
    bill_to_idx = next((i for i, ln in enumerate(lines) if re.match(r"^\W*bill\s*to", ln.text, re.I)), None)
    vg = next((g for g in gst if bill_to_idx is None or g[2] < bill_to_idx), None)
    bg = next((g for g in gst if bill_to_idx is not None and g[2] > bill_to_idx), None)
    put("vendor_gstin", vg[0] if vg else None, vg[1] if vg else 0)
    put("buyer_gstin", bg[0] if bg else None, bg[1] if bg else 0)
    if bill_to_idx is not None and bill_to_idx + 1 < len(lines):
        put("buyer_name", lines[bill_to_idx + 1].text, 0.95)
    else:
        put("buyer_name", None, 0)

    # totals
    sub, sc = _find_amount(lines, L_SUB)
    put("subtotal", sub, sc)
    total, tc = _find_amount(lines, L_TOTAL)
    put("total_amount", total, tc)

    # tax lines
    for ln in lines:
        m = TAX_RE.match(ln.text.replace("₹", "").strip())
        if m:
            amt = D(m.group(3))
            out["tax_lines"].append({"type": m.group(1).upper(), "rate": float(m.group(2)), "amount": amt,
                                     "conf": ln.words[-1].conf if ln.words else 1.0})
    tax_total = sum((t["amount"] for t in out["tax_lines"]), Decimal("0")) if out["tax_lines"] else None
    put("tax_total", tax_total, min((t["conf"] for t in out["tax_lines"]), default=1.0))

    # line items: between header row and first totals line
    hdr = next((i for i, ln in enumerate(lines) if re.match(r"^\W*description\b", ln.text, re.I)), None)
    end = next((i for i, ln in enumerate(lines) if i > (hdr or 0) and re.match(rf"^\W*{L_SUB}\b", ln.text, re.I)), None)
    if hdr is not None and end is not None:
        hdr_txt = lines[hdr].text.lower()
        has_qty = "qty" in hdr_txt
        has_gstpct = "gst" in hdr_txt
        for ln in lines[hdr + 1:end]:
            toks = ln.text.split()
            nums = []
            max_nums = 3 + (1 if has_gstpct else 0) if has_qty else 2 + (1 if has_gstpct else 0)
            while toks and len(nums) < max_nums and (MONEY_TOKEN.match(toks[-1]) or re.fullmatch(r"\d+(?:\.\d+)?%", toks[-1])):
                nums.insert(0, toks.pop())
            if not toks or not nums:
                continue
            desc = " ".join(toks)
            if has_gstpct and nums and nums[-1].endswith("%"):
                nums = nums[:-1]
            vals = [_money(n) for n in nums]
            if has_qty and len(vals) >= 3:
                qty, price, amt = vals[-3], vals[-2], vals[-1]
            elif len(vals) >= 2 and not has_qty:
                qty, price, amt = Decimal(1), vals[-2], vals[-1]
            else:
                qty, price, amt = Decimal(1), vals[-1], vals[-1]
            out["line_items"].append({"description": desc, "quantity": float(qty), "unit_price": price,
                                      "amount": amt, "conf": min((w.conf for w in ln.words[-len(nums):]), default=1.0)})

    # bank
    for ln in lines:
        m = re.search(r"(?:a\W?[/I|l]\W?c|account)\s*(?:no|number)?\W*\s*(\d{9,18})\b", ln.text, re.I)
        if m and "account" not in out["bank"]:
            out["bank"]["account"] = m.group(1)
            out["bank"]["account_conf"] = ln.conf_of_tail(m.group(1))
        m = re.search(r"\bIFSC\b\W*([A-Z0-9]{11})\b", ln.text, re.I)
        if m and "ifsc" not in out["bank"]:
            ifsc = m.group(1).upper()
            if len(ifsc) == 11 and ifsc[4] == "O":
                ifsc = ifsc[:4] + "0" + ifsc[5:]
            out["bank"]["ifsc"] = ifsc
            out["bank"]["ifsc_conf"] = ln.conf_of_tail(m.group(1))
    return out


def overall_confidence(parsed, cfg):
    crit = {k: parsed["confidence"].get(k, 0.0) for k in cfg.critical_fields}
    present = {k: v for k, v in crit.items() if parsed["fields"].get(k) is not None}
    vals = [v for v in parsed["confidence"].values() if v > 0]
    critical_min = min(present.values()) if present else 0.0
    # missing fields are reported by Stage 3 (R3.1); critical_min covers the fields that were read
    overall = round(sum(vals) / len(vals), 3) if vals else 0.0
    return overall, round(critical_min, 3), crit
