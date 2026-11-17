import datetime as dt
import hashlib
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from rapidfuzz import fuzz

D0 = Decimal("0")


def D(x):
    if x is None or x == "":
        return None
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x).replace(",", "").strip())
    except InvalidOperation:
        return None


def q2(x):
    return D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fnum(x):
    return None if x is None else float(x)


def inr(x, symbol=True):
    """Indian digit grouping: 118000 -> ₹1,18,000.00"""
    if x is None:
        return "—"
    x = q2(x)
    sign = "-" if x < 0 else ""
    whole, frac = f"{abs(x):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return f"{sign}{'₹' if symbol else ''}{whole}.{frac}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm_number(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


_SUFFIX = re.compile(r"\b(pvt|private|ltd|limited|llp|llc|inc|co|company|corp|and|&)\b\.?", re.I)


def norm_name(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_score(a, b):
    return fuzz.token_set_ratio(norm_name(a), norm_name(b))


def levenshtein(a, b):
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def parse_date(s):
    if not s:
        return None
    from dateutil import parser as dp
    if isinstance(s, (dt.date, dt.datetime)):
        return s if isinstance(s, dt.date) and not isinstance(s, dt.datetime) else s.date()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s.strip()):
        return dt.date.fromisoformat(s.strip())
    s = s.strip().replace(".", "/") if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{2,4}", s.strip()) else s.strip()
    try:
        return dp.parse(s, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


def jdump(o):
    import json

    def default(x):
        if isinstance(x, Decimal):
            return float(x)
        if isinstance(x, (dt.date, dt.datetime)):
            return x.isoformat()
        raise TypeError(type(x))
    return json.dumps(o, default=default)
