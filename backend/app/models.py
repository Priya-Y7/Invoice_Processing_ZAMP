import datetime as dt
from sqlalchemy import (Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
                        create_engine, event)
from sqlalchemy.orm import declarative_base, sessionmaker

import os
import threading
from collections import OrderedDict

from sqlalchemy.orm import sessionmaker as _sessionmaker

from .config import DATA_DIR, DB_URL, WS

Base = declarative_base()


def _make_engine(url):
    e = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)

    @event.listens_for(e, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()
    return e


engine = _make_engine(DB_URL)          # the single local database
_engines = OrderedDict()               # private per-visitor databases (hosted demo)
_elock = threading.Lock()


def engine_for(ws):
    if not ws:
        return engine
    with _elock:
        e = _engines.get(ws)
        if e is None:
            os.makedirs(os.path.join(DATA_DIR, "ws"), exist_ok=True)
            e = _engines[ws] = _make_engine("sqlite:///" + os.path.join(DATA_DIR, "ws", ws + ".db"))
            while len(_engines) > 150:
                _engines.popitem(last=False)[1].dispose()
        else:
            _engines.move_to_end(ws)
        return e


def Session(*a, **k):
    """A session on the current workspace's database."""
    return _sessionmaker(bind=engine_for(WS.get()), expire_on_commit=False, future=True)(*a, **k)


class Vendor(Base):
    __tablename__ = "vendors"
    vendor_id = Column(String, primary_key=True)
    legal_name = Column(String, nullable=False)
    gstin = Column(String)
    state_code = Column(String)
    address = Column(String)
    bank_account_holder = Column(String)
    bank_account_no = Column(String)
    ifsc = Column(String)
    approval_status = Column(String, default="Approved")
    payment_terms_days = Column(Integer, default=30)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    po_number = Column(String, primary_key=True)
    vendor_id = Column(String, ForeignKey("vendors.vendor_id"))
    issue_date = Column(Date)
    status = Column(String, default="Open")
    currency = Column(String, default="INR")
    net_amount = Column(Numeric(14, 2))
    gst_rate_pct = Column(Float, default=18.0)
    description = Column(String)


class POLine(Base):
    __tablename__ = "po_lines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    po_number = Column(String, ForeignKey("purchase_orders.po_number"))
    line_no = Column(Integer)
    description = Column(String)
    quantity = Column(Float)
    unit_price = Column(Numeric(14, 2))


class Invoice(Base):
    __tablename__ = "invoices"
    invoice_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    vendor_id = Column(String, index=True)
    invoice_number = Column(String)
    invoice_number_norm = Column(String, index=True)
    invoice_date = Column(Date)
    po_number = Column(String, index=True)
    subtotal = Column(Numeric(14, 2))
    tax_total = Column(Numeric(14, 2))
    total = Column(Numeric(14, 2))
    decision = Column(String)
    file_hash = Column(String, index=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"
    run_id = Column(String, primary_key=True)
    filename = Column(String)
    file_hash = Column(String, index=True)
    status = Column(String, default="queued")
    decision = Column(String)
    final_decision = Column(String)
    reason = Column(Text)
    reason_source = Column(String)
    vendor_name = Column(String)
    invoice_number = Column(String)
    total = Column(Float)
    po_number = Column(String)
    top_rule = Column(String)
    total_ms = Column(Integer)
    overall_confidence = Column(Float)
    result_json = Column(Text)
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    finished_at = Column(DateTime)


class RunEvent(Base):
    __tablename__ = "run_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    seq = Column(Integer)
    stage_no = Column(Integer)
    stage_name = Column(String)
    status = Column(String)
    summary = Column(Text)
    detail_json = Column(Text)
    duration_ms = Column(Integer)
    ts = Column(DateTime, default=dt.datetime.utcnow)


class Override(Base):
    __tablename__ = "overrides"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    action = Column(String)
    note = Column(Text)
    user = Column(String, default="AP Manager")
    ts = Column(DateTime, default=dt.datetime.utcnow)


class ExceptionItem(Base):
    __tablename__ = "exceptions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, index=True)
    kind = Column(String)            # Review | Reject
    status = Column(String, default="Open")   # Open | In progress | Resolved
    assignee = Column(String, default="AP Manager")
    note = Column(Text)
    vendor_message = Column(Text)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    resolved_at = Column(DateTime)


def init_db():
    Base.metadata.create_all(engine_for(WS.get()))
