"""A tiny fake of the PyQt6 surface Shika uses, so the real code paths can run headless in tests."""
import threading

class _Any:
    """Permissive stand-in: every attribute exists, calls return _Any, maths returns 0."""
    def __init__(self, *a, **k): pass
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Any()
    def __call__(self, *a, **k): return _Any()
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __len__(self): return 0
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __index__(self): return 0
    def __str__(self): return ""
    def __or__(self, o): return _Any()
    __ror__ = __and__ = __rand__ = __or__
    def _num(self, *a): return 0
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __truediv__ = __rtruediv__ = _num
    __floordiv__ = __rfloordiv__ = __mod__ = __neg__ = __pos__ = __abs__ = _num
    def __lt__(self, o): return False
    __le__ = __gt__ = __ge__ = __lt__
    def __eq__(self, o): return self is o
    def __hash__(self): return id(self)

class _BoundSignal:
    def __init__(self): self.slots = []; self.blocked = False
    def connect(self, f): self.slots.append(f)
    def disconnect(self, *a): self.slots.clear()
    def emit(self, *a):
        for f in list(self.slots):
            try:
                f(*a)
            except TypeError:
                f()

class pyqtSignal:
    def __init__(self, *types): self.name = None
    def __set_name__(self, owner, name): self.name = name
    def __get__(self, obj, objtype=None):
        if obj is None: return self
        key = "_sig_" + self.name
        if key not in obj.__dict__:
            obj.__dict__[key] = _BoundSignal()
        return obj.__dict__[key]

def _sig(obj, name):
    key = "_sig_" + name
    if key not in obj.__dict__:
        obj.__dict__[key] = _BoundSignal()
    return obj.__dict__[key]

class QObject(_Any):
    def __init__(self, *a, **k):
        for name, val in k.items():
            if callable(val) and name in ("timeout", "clicked", "textChanged", "triggered"):
                _sig(self, name).connect(val)
    def blockSignals(self, b):
        self.__dict__["_blocked"] = b
        return False

PENDING = []          # (fire_at_order, callback) queued by QTimer.singleShot
LOCK = threading.Lock()

class QTimer(QObject):
    def __init__(self, parent=None, singleShot=False, timeout=None, **k):
        self._single = singleShot; self._active = False
        if timeout: _sig(self, "timeout").connect(timeout)
    @property
    def timeout(self): return _sig(self, "timeout")
    def start(self, *a):
        self._active = True
        if self._single:
            with LOCK: PENDING.append(self._fire)
    def _fire(self):
        if self._active:
            self._active = False
            _sig(self, "timeout").emit()
    def stop(self): self._active = False
    def isActive(self): return self._active
    def setSingleShot(self, b): self._single = b
    @staticmethod
    def singleShot(ms, fn, *rest):
        if rest: fn = rest[0]
        with LOCK: PENDING.append(fn)

def flush(rounds=10):
    for _ in range(rounds):
        with LOCK:
            batch = PENDING[:]; PENDING.clear()
        if not batch: return
        for fn in batch: fn()
