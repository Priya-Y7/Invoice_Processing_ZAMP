"""Load the three seed CSVs (plus po_lines) into the database."""
import csv
import datetime as dt
import os
import re
import shutil

from .config import SEED_DIR, UPLOAD_DIR
from .models import (Base, ExceptionItem, Invoice, Override, POLine, PurchaseOrder, Run, RunEvent, Session,
                     Vendor, engine, init_db)


def norm_number(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _rows(name):
    with open(os.path.join(SEED_DIR, name), newline="") as f:
        return list(csv.DictReader(f))


def seed(reset=True):
    init_db()
    with Session() as s:
        if reset:
            run_ids = [r[0] for r in s.query(Run.run_id).all()]
            for m in (Override, ExceptionItem, RunEvent, Run, Invoice, POLine, PurchaseOrder, Vendor):
                s.query(m).delete()
            s.commit()
            for rid in run_ids:   # only this workspace's uploaded files
                try:
                    os.remove(os.path.join(UPLOAD_DIR, rid + ".pdf"))
                except OSError:
                    pass
            os.makedirs(UPLOAD_DIR, exist_ok=True)
        for r in _rows("vendors.csv"):
            s.add(Vendor(**{**r, "payment_terms_days": int(r["payment_terms_days"])}))
        for r in _rows("purchase_orders.csv"):
            s.add(PurchaseOrder(po_number=r["po_number"], vendor_id=r["vendor_id"],
                                issue_date=dt.date.fromisoformat(r["issue_date"]), status=r["status"],
                                currency=r["currency"], net_amount=r["net_amount"],
                                gst_rate_pct=float(r["gst_rate_pct"]), description=r["description"]))
        for r in _rows("po_lines.csv"):
            s.add(POLine(po_number=r["po_number"], line_no=int(r["line_no"]), description=r["description"],
                         quantity=float(r["quantity"]), unit_price=r["unit_price"]))
        for r in _rows("invoice_history.csv"):
            s.add(Invoice(vendor_id=r["vendor_id"], invoice_number=r["invoice_number"],
                          invoice_number_norm=norm_number(r["invoice_number"]),
                          invoice_date=dt.date.fromisoformat(r["invoice_date"]), po_number=r["po_number"],
                          subtotal=r["subtotal"], tax_total=r["tax_total"], total=r["total"],
                          decision=r["decision"], run_id=None, file_hash=None))
        s.commit()


def seed_if_empty():
    init_db()
    with Session() as s:
        if s.query(Vendor).count() == 0:
            pass
        else:
            return
    seed(reset=False)


if __name__ == "__main__":
    seed()
    print("seeded")
