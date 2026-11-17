import contextvars
import os
import threading
from collections import OrderedDict

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))
SEED_DIR = os.path.join(BASE, "data", "seed")
SAMPLES_DIR = os.path.join(BASE, "data", "samples")
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(DATA_DIR, "invoiceiq.db"))
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(BASE, "static"))
# WORKSPACES=per_visitor gives every browser its own private, freshly seeded workspace (used on the hosted demo).
MULTI = os.environ.get("WORKSPACES", "") == "per_visitor"
WS = contextvars.ContextVar("ws", default="")   # id of the workspace serving the current request ("" = the single local one)
EXTRACTION_MODE = os.environ.get("EXTRACTION_MODE", "local")  # local | claude (optional)
_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


class _Cfg:
    """Attribute access to config.yaml values, editable at runtime from the UI."""

    def __init__(self):
        self._lock = threading.Lock()
        self.reload_defaults()

    def reload_defaults(self):
        with open(_DEFAULT_PATH) as f:
            self._v = yaml.safe_load(f)
        if os.environ.get("UI_PACING_MS"):
            self._v["ui_pacing_ms"] = int(os.environ["UI_PACING_MS"])

    def __getattr__(self, k):
        try:
            return self.__dict__["_v"][k]
        except KeyError:
            raise AttributeError(k)

    def as_dict(self):
        return dict(self._v)

    def update(self, values):
        with self._lock:
            for k, v in values.items():
                if k in self._v and not isinstance(self._v[k], list):
                    cur = self._v[k]
                    self._v[k] = int(float(v)) if isinstance(cur, int) and not isinstance(cur, bool) else type(cur)(v)


class _CfgProxy:
    """cfg.<name> resolves against the current workspace's own settings."""

    def __init__(self):
        self._by = OrderedDict()
        self._l = threading.Lock()

    def _cur(self):
        ws = WS.get()
        with self._l:
            c = self._by.get(ws)
            if c is None:
                c = self._by[ws] = _Cfg()
                while len(self._by) > 300:
                    self._by.popitem(last=False)
            else:
                self._by.move_to_end(ws)
            return c

    def __getattr__(self, k):
        return getattr(self._cur(), k)

    def as_dict(self):
        return self._cur().as_dict()

    def update(self, values):
        return self._cur().update(values)

    def reload_defaults(self):
        return self._cur().reload_defaults()


cfg = _CfgProxy()
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
