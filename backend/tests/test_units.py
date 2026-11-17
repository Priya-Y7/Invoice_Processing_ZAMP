import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DATA_DIR", "/tmp/invoiceiq_test")

from app.rules import level_of  # noqa: E402
from app.util import inr, levenshtein, name_score, norm_number, parse_date  # noqa: E402


def test_inr_grouping():
    assert inr(Decimal("118000")) == "₹1,18,000.00"
    assert inr(Decimal("12345678.5")) == "₹1,23,45,678.50"
    assert inr(Decimal("999")) == "₹999.00"


def test_invoice_number_normalisation():
    assert norm_number("INV/MFS/2210") == norm_number("inv-mfs-2210") == norm_number("INV MFS 2210") == "INVMFS2210"


def test_levenshtein():
    assert levenshtein("INVBWL7802", "INVBWL7803") == 1
    assert levenshtein("abc", "abc") == 0


def test_vendor_name_fuzzy():
    assert name_score("Sharma Office Supplies Pvt. Ltd.", "Sharma Office Supplies Pvt Ltd") >= 92
    assert name_score("Orion Tools", "Sharma Office Supplies Pvt Ltd") < 80


def test_dates():
    assert parse_date("03 Nov 2026").isoformat() == "2026-11-03"
    assert parse_date("05/11/2026").isoformat() == "2026-11-05"
    assert parse_date("28-Oct-2026").isoformat() == "2026-10-28"
    assert parse_date("2026-11-12").isoformat() == "2026-11-12"


def test_fail_safe_unknown_rule_is_review():
    assert level_of("R99.9", "fail") == "REVIEW"
    assert level_of("R7.7", "error") == "REVIEW"
    assert level_of("R4.2", "fail") == "REJECT"
    assert level_of("R4.2", "pass") is None
