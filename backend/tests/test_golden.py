"""Golden tests: the ten sample invoices must give the expected verdicts and rules (spec Section 5.4/6)."""
import glob
import json
import os
import sys

import pytest

os.environ["UI_PACING_MS"] = "0"
os.environ.setdefault("DATA_DIR", "/tmp/invoiceiq_test")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.models import Run, Session  # noqa: E402
from app.pipeline import runner  # noqa: E402
from app.seed import seed  # noqa: E402

BASE = os.path.dirname(os.path.dirname(__file__))
EXPECT = {
    "S01": ("Approve", set()), "S02": ("Review", {"R7.6", "R7.7"}), "S03": ("Approve", set()),
    "S04": ("Review", {"R7.7"}), "S05": ("Review", {"R8.2"}), "S06": ("Reject", {"R5.1"}),
    "S07": ("Review", {"R3.1"}), "S08": ("Reject", {"R4.2"}), "S09": ("Reject", {"R6.2", "R7.7"}),
    "S10": ("Review", {"R7.4"}),
}
RESULTS = {}


@pytest.fixture(scope="module", autouse=True)
def _run_all():
    seed()
    for f in sorted(glob.glob(os.path.join(BASE, "data/samples/*.pdf"))):
        code = os.path.basename(f)[:3]
        rid = "t_" + code
        with Session() as s:
            s.add(Run(run_id=rid, filename=os.path.basename(f)))
            s.commit()
        runner.process(rid, os.path.basename(f), open(f, "rb").read())
        with Session() as s:
            RESULTS[code] = json.loads(s.get(Run, rid).result_json)
    yield


@pytest.mark.parametrize("code", sorted(EXPECT))
def test_verdict_and_rules(code):
    verdict, rules = EXPECT[code]
    d = RESULTS[code]["decision"]
    assert d["verdict"] == verdict
    fired = {t["rule"] for t in d["trail"] if t["level"] in ("REJECT", "REVIEW")}
    assert rules <= fired, f"{code}: expected rules {rules} in {fired}"


def test_all_nine_stages_ran():
    for code, r in RESULTS.items():
        assert [s["stage_no"] for s in r["stages"]] == list(range(1, 10)), code


def test_split_po_balance_moves():
    assert RESULTS["S03"]["numeric"]["remaining_before"] == 180000
    assert RESULTS["S03"]["numeric"]["remaining_after"] == 80000
    assert RESULTS["S04"]["numeric"]["remaining_before"] == 80000
    assert round(RESULTS["S04"]["numeric"]["overrun_pct"], 1) == 5.0


def test_implied_po_is_pr_1004():
    assert RESULTS["S05"]["po"]["matched_po"] == "PO-2026-1004" and RESULTS["S05"]["po"]["inferred"]


def test_scan_path_and_missing_fields():
    r = RESULTS["S07"]
    assert r["extraction"]["source"] == "scanned_image"
    assert r["extraction"]["fields"]["invoice_number"] is None
    assert r["extraction"]["fields"]["total_amount"] is None


def test_duplicate_found_despite_new_format():
    assert RESULTS["S06"]["extraction"]["fields"]["invoice_number"] == "INV/MFS/2210"


def test_resubmitting_same_file_is_rejected_as_duplicate():
    f = os.path.join(BASE, "data/samples/S01_happy_path.pdf")
    with Session() as s:
        s.add(Run(run_id="t_dup", filename="S01_happy_path.pdf"))
        s.commit()
    runner.process("t_dup", "S01_happy_path.pdf", open(f, "rb").read())
    with Session() as s:
        d = json.loads(s.get(Run, "t_dup").result_json)["decision"]
    assert d["verdict"] == "Reject" and d["top_rule"] in ("R5.1", "R5.2")
