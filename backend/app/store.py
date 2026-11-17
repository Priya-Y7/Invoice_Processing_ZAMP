"""Thin read helpers over the SQLAlchemy session used by the pipeline stages."""
from decimal import Decimal

from sqlalchemy import func

from .models import Invoice, POLine, PurchaseOrder, Run, Vendor
from .util import D


class DB:
    def __init__(self, session):
        self.s = session

    def run_with_hash(self, sha, exclude_run):
        r = self.s.query(Run).filter(Run.file_hash == sha, Run.run_id != exclude_run,
                                     Run.status == "done").order_by(Run.started_at).first()
        return r.run_id if r else None

    def vendors(self):
        return self.s.query(Vendor).all()

    def all_pos(self):
        return self.s.query(PurchaseOrder).all()

    def pos_for_vendor(self, vendor_id):
        return self.s.query(PurchaseOrder).filter(PurchaseOrder.vendor_id == vendor_id).all()

    def po(self, po_number):
        return self.s.get(PurchaseOrder, po_number)

    def po_lines(self, po_number):
        return self.s.query(POLine).filter(POLine.po_number == po_number).order_by(POLine.line_no).all()

    def billed_to_date(self, po_number):
        tot = self.s.query(func.coalesce(func.sum(Invoice.subtotal), 0)).filter(
            Invoice.po_number == po_number, Invoice.decision == "Approve").scalar()
        return D(tot or 0)

    def remaining(self, po):
        return D(po.net_amount) - self.billed_to_date(po.po_number)

    def invoices_for_vendor(self, vendor_id):
        return self.s.query(Invoice).filter(Invoice.vendor_id == vendor_id).all()
