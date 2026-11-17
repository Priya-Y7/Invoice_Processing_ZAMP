"""Generate the ten sample invoice PDFs (S01-S10) used by the demo.

Run from the backend folder:  python scripts/make_samples.py
Three layout templates (A clean itemised, B GST per line, C lump sum) so that
extraction is genuinely non-trivial. S07 is rendered to an image, degraded and
saved as an image-only PDF (no text layer) to simulate a bad scan.
"""
import csv
import io
import os
import random
import sys
from datetime import date, timedelta

import fitz  # pymupdf
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seed")
OUT = os.path.join(ROOT, "data", "samples")
BUYER = {"name": "Helix Retail Pvt Ltd", "gstin": "27AAACH1111A1Z7",
         "addr": "Plot 7, Bandra Kurla Complex, Mumbai 400051"}
BUYER_STATE = "27"


def inr(x):
    """Indian digit grouping with two decimals: 1,00,000.00"""
    s = f"{abs(x):.2f}"
    whole, dec = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return f"{whole}.{dec}"


def load_vendors():
    with open(os.path.join(SEED, "vendors.csv"), newline="") as f:
        return {r["vendor_id"]: r for r in csv.DictReader(f)}


def fmt_date(d, style):
    if style == "A":
        return d.strftime("%d %b %Y")
    if style == "B":
        return d.strftime("%d/%m/%Y")
    return d.strftime("%d-%b-%Y")


def tax_lines(vendor, subtotal, rate=18.0, wrong_type=False):
    """Return [(type, rate, amount)] following GST place-of-supply rules."""
    same_state = vendor["state_code"] == BUYER_STATE
    if wrong_type:
        same_state = not same_state
    if same_state:
        half = rate / 2
        amt = round(subtotal * half / 100, 2)
        return [("CGST", half, amt), ("SGST", half, amt)]
    return [("IGST", rate, round(subtotal * rate / 100, 2))]


# --------------------------------------------------------------------------
# Templates. Each returns regions {"invoice_no": bbox, "total": bbox} in PDF
# points (x0, y_bottom, x1, y_top) so S07 can smudge exactly those areas.
# --------------------------------------------------------------------------
def head(c, v, title="TAX INVOICE"):
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(297, 805, title)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, 772, v["legal_name"])
    c.setFont("Helvetica", 9.5)
    c.drawString(40, 757, v["address"])
    c.drawString(40, 744, f"GSTIN: {v['gstin']}")


def bill_to(c, y):
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Bill To:")
    c.setFont("Helvetica", 9.5)
    c.drawString(40, y - 14, BUYER["name"])
    c.drawString(40, y - 27, BUYER["addr"])
    c.drawString(40, y - 40, f"GSTIN: {BUYER['gstin']}")


def bank(c, v, y):
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Bank Details")
    c.setFont("Helvetica", 9.5)
    c.drawString(40, y - 14, f"Account Name: {v['bank_account_holder']}")
    c.drawString(40, y - 27, f"A/C No: {v['bank_account_no']}")
    c.drawString(40, y - 40, f"IFSC: {v['ifsc']}")
    c.drawString(40, y - 62, "Payment terms: 30 days from invoice date. Subject to Mumbai jurisdiction.")


def meta(c, labels, values, y0):
    """Vertical label: value lines. Returns bbox of the first value (invoice no)."""
    c.setFont("Helvetica", 10)
    bbox = None
    for i, (lab, val) in enumerate(zip(labels, values)):
        if val is None:
            continue
        y = y0 - 15 * i
        c.drawString(40, y, f"{lab}:")
        x = 40 + stringWidth(f"{lab}: ", "Helvetica", 10)
        c.drawString(x, y, str(val))
        if i == 0:
            bbox = (x - 2, y - 3, x + stringWidth(str(val), "Helvetica", 10) + 4, y + 11)
    return bbox


def right_line(c, y, label, value, bold=False):
    f = "Helvetica-Bold" if bold else "Helvetica"
    c.setFont(f, 10)
    c.drawString(330, y, label)
    s = inr(value)
    w = stringWidth(s, f, 10)
    c.drawString(555 - w, y, s)
    return (555 - w - 3, y - 3, 557, y + 11)


def template_A(c, inv, v):
    head(c, v)
    bb = meta(c, ["Invoice No", "Invoice Date", "Due Date", "PO Reference"],
              [inv["number"], fmt_date(inv["date"], "A"), fmt_date(inv["date"] + timedelta(days=30), "A"),
               inv.get("po")], 715)
    bill_to(c, 640)
    y = 575
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Description"); c.drawString(330, y, "Qty")
    c.drawString(390, y, "Unit Price"); c.drawString(490, y, "Amount")
    c.line(40, y - 4, 555, y - 4)
    c.setFont("Helvetica", 10)
    for ln in inv["lines"]:
        y -= 18
        c.drawString(40, y, ln["desc"]); c.drawString(330, y, f"{ln['qty']:g}")
        c.drawRightString(470, y, inr(ln["unit"])); c.drawRightString(555, y, inr(ln["qty"] * ln["unit"]))
    y -= 32
    regs = {"invoice_no": bb}
    right_line(c, y, "Subtotal", inv["subtotal"]); y -= 16
    for t, r, a in inv["taxes"]:
        right_line(c, y, f"{t} @ {r:g}%", a); y -= 16
    regs["total"] = right_line(c, y, "Total Amount", inv["total"], bold=True)
    bank(c, v, y - 50)
    return regs


def template_B(c, inv, v):
    head(c, v, "INVOICE")
    c.rect(36, 690, 523, 38, stroke=1, fill=0)
    bb = meta(c, ["Bill No.", "Dated", "Order Ref."],
              [inv["number"], fmt_date(inv["date"], "B"), inv.get("po")], 715)
    bill_to(c, 650)
    y = 585
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Description"); c.drawString(290, y, "Qty"); c.drawString(340, y, "Rate")
    c.drawString(420, y, "Amount"); c.drawString(500, y, "GST %")
    c.line(40, y - 4, 555, y - 4)
    c.setFont("Helvetica", 10)
    rate_total = sum(r for _, r, _ in inv["taxes"])
    for ln in inv["lines"]:
        y -= 18
        c.drawString(40, y, ln["desc"]); c.drawString(290, y, f"{ln['qty']:g}")
        c.drawRightString(400, y, inr(ln["unit"])); c.drawRightString(480, y, inr(ln["qty"] * ln["unit"]))
        c.drawString(505, y, f"{rate_total:g}%")
    y -= 32
    right_line(c, y, "Taxable Value", inv["subtotal"]); y -= 16
    for t, r, a in inv["taxes"]:
        right_line(c, y, f"{t} @ {r:g}%", a); y -= 16
    right_line(c, y, "Total GST", inv["tax_total"]); y -= 16
    regs = {"invoice_no": bb, "total": right_line(c, y, "Grand Total", inv["total"], bold=True)}
    bank(c, v, y - 50)
    return regs


def template_C(c, inv, v):
    head(c, v, "INVOICE")
    bb = meta(c, ["Invoice #", "Date", "Your PO"],
              [inv["number"], fmt_date(inv["date"], "C"), inv.get("po")], 715)
    bill_to(c, 655)
    y = 590
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Description"); c.drawString(490, y, "Amount")
    c.line(40, y - 4, 555, y - 4)
    c.setFont("Helvetica", 10)
    y -= 20
    c.drawString(40, y, inv["lines"][0]["desc"])
    c.drawRightString(555, y, inr(inv["subtotal"]))
    y -= 40
    right_line(c, y, "Total before tax", inv["subtotal"]); y -= 16
    for t, r, a in inv["taxes"]:
        right_line(c, y, f"{t} ({r:g}%)", a); y -= 16
    regs = {"invoice_no": bb, "total": right_line(c, y, "Amount Payable", inv["total"], bold=True)}
    bank(c, v, y - 50)
    return regs


TEMPLATES = {"A": template_A, "B": template_B, "C": template_C}


def build(spec, vendors):
    v = vendors[spec["vendor"]]
    lines = spec["lines"]
    subtotal = round(sum(l["qty"] * l["unit"] for l in lines), 2)
    taxes = tax_lines(v, subtotal, wrong_type=spec.get("wrong_tax", False))
    tax_total = round(sum(a for _, _, a in taxes), 2)
    inv = dict(spec, subtotal=subtotal, taxes=taxes, tax_total=tax_total,
               total=round(subtotal + tax_total, 2))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(spec["number"] or "invoice")
    regs = TEMPLATES[spec["template"]](c, inv, v)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, 40, "This is a computer generated invoice (synthetic demo data).")
    c.save()
    return buf.getvalue(), regs, inv


def degrade_to_scan(pdf_bytes, regs, seed=7):
    """Rasterise, smudge the invoice number, blur the total, rotate, add noise."""
    rnd = np.random.default_rng(seed)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    dpi = 200
    pix = doc[0].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    s = dpi / 72.0
    H = pix.height

    def box(b):  # pdf points -> pixels (origin top-left)
        x0, yb, x1, yt = b
        return (int(x0 * s), int(H - yt * s), int(x1 * s), int(H - yb * s))

    # invoice number: solid smudge over the value
    x0, y0, x1, y1 = box(regs["invoice_no"])
    arr = np.array(img)
    arr[y0 - 2:y1 + 2, x0 - 4:x1 + 6] = (70, 70, 70)
    img = Image.fromarray(arr)
    # total: heavy blur (still partly visible, low confidence)
    x0, y0, x1, y1 = box(regs["total"])
    crop = img.crop((x0 - 4, y0 - 2, x1 + 4, y1 + 2)).filter(ImageFilter.GaussianBlur(5.5))
    img.paste(crop, (x0 - 4, y0 - 2))
    # slight overall softness, rotation, noise
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img = img.rotate(1.5, resample=Image.BICUBIC, fillcolor=(250, 250, 248), expand=False)
    arr = np.array(img).astype(np.int16)
    arr += rnd.normal(0, 9, arr.shape).astype(np.int16)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    out = io.BytesIO()
    img.save(out, format="PDF", resolution=dpi)
    return out.getvalue()


def D(y, m, d):
    return date(y, m, d)


SPECS = [
    dict(code="S01_happy_path", vendor="V001", template="A", number="INV-SOS-0412", date=D(2026, 11, 3),
         po="PO-2026-1001", lines=[dict(desc="A4 paper ream", qty=500, unit=120.0),
                                   dict(desc="Printer toner cartridge", qty=20, unit=2000.0)]),
    dict(code="S02_price_variance", vendor="V001", template="A", number="INV-SOS-0419", date=D(2026, 11, 6),
         po="PO-2026-1008", lines=[dict(desc="Ergonomic office chairs", qty=25, unit=2080.0)]),
    dict(code="S03_split_po_inv2", vendor="V002", template="B", number="INV-BWL-7802", date=D(2026, 11, 5),
         po="PO-2026-1002", lines=[dict(desc="Freight consignment Q4 2026", qty=20, unit=5000.0)]),
    dict(code="S04_split_po_inv3", vendor="V002", template="B", number="INV-BWL-7840", date=D(2026, 11, 12),
         po="PO-2026-1002", lines=[dict(desc="Freight consignment Q4 2026", qty=19, unit=5000.0)]),
    dict(code="S05_implied_po", vendor="V003", template="A", number="INV-TF-2291", date=D(2026, 11, 7),
         po=None, lines=[dict(desc="Network switch installation and cabling", qty=1, unit=42500.0)]),
    dict(code="S06_duplicate_reformatted", vendor="V006", template="C", number="INV/MFS/2210", date=D(2026, 10, 28),
         po="PO-2026-1006", lines=[dict(desc="Facility housekeeping Oct-Nov", qty=1, unit=75000.0)]),
    dict(code="S07_scanned_incomplete", vendor="V004", template="A", number="INV-GLP-1187", date=D(2026, 11, 9),
         po="PO-2026-1005", scan=True, lines=[dict(desc="Corrugated cartons 3-ply", qty=3000, unit=20.0)]),
    dict(code="S08_blocked_vendor", vendor="V005", template="A", number="INV-OIT-0098", date=D(2026, 11, 8),
         po="PO-2026-1007", lines=[dict(desc="Industrial hand tools", qty=100, unit=900.0)]),
    dict(code="S09_closed_po", vendor="V001", template="C", number="INV-SOS-0431", date=D(2026, 11, 10),
         po="PO-2026-0950", lines=[dict(desc="Printer consumables bundle", qty=15, unit=1000.0)]),
    dict(code="S10_wrong_tax_type", vendor="V003", template="B", number="INV-TF-2305", date=D(2026, 11, 11),
         po="PO-2026-1003", wrong_tax=True,
         lines=[dict(desc="Annual laptop maintenance contract", qty=1, unit=85000.0)]),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    vendors = load_vendors()
    for spec in SPECS:
        data, regs, inv = build(spec, vendors)
        if spec.get("scan"):
            data = degrade_to_scan(data, regs)
        path = os.path.join(OUT, spec["code"] + ".pdf")
        with open(path, "wb") as f:
            f.write(data)
        print(f"{spec['code']:32s} {inv['number']:14s} subtotal {inv['subtotal']:>12,.2f} total {inv['total']:>12,.2f}")


if __name__ == "__main__":
    main()
