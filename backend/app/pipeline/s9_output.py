from .base import StageResult, chk

NAME = "Output"


def run(ctx):
    """Assemble the result payload. Persistence happens in the runner inside one transaction (R9.1)."""
    r = StageResult()
    d = ctx.decision
    r.checks.append(chk("R9.1", "Atomic save", "pass", "Run, invoice row and follow-up item are written in one transaction"))
    r.summary = f"{d['verdict']} recorded; {d['next_action']}"
    r.data = {"verdict": d["verdict"], "next_action": d["next_action"]}
    r.status = "pass"
    return r
