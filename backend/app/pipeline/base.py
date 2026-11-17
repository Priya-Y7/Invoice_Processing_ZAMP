from dataclasses import dataclass, field
from typing import Any, Optional


def chk(rule, label, result, detail, cid=None):
    return {"id": cid or rule, "rule": rule, "label": label, "result": result, "detail": detail}


@dataclass
class StageResult:
    status: str = "pass"
    summary: str = ""
    checks: list = field(default_factory=list)
    data: dict = field(default_factory=dict)
    duration_ms: int = 0

    def finalise(self):
        rs = [c["result"] for c in self.checks]
        if self.status in ("error", "skipped"):
            return self
        self.status = "fail" if "fail" in rs else "warn" if "warn" in rs else "pass"
        return self


@dataclass
class Ctx:
    run_id: str
    filename: str
    data: bytes
    cfg: Any
    db: Any
    results: dict = field(default_factory=dict)
    file: dict = field(default_factory=dict)
    ex: Optional[dict] = None          # parsed extraction {fields, confidence, line_items, tax_lines, bank}
    vendor: Any = None
    po: Any = None
    po_inferred: bool = False
    po_info: dict = field(default_factory=dict)
    numeric: dict = field(default_factory=dict)
    decision: dict = field(default_factory=dict)
    ended: bool = False                # Stage 1 hard stop

    def f(self, key):
        return (self.ex or {}).get("fields", {}).get(key)

    def conf(self, key):
        return (self.ex or {}).get("confidence", {}).get(key, 0.0)
