import os, sys, tempfile, importlib.util, subprocess, types, json, time, threading
HOME = tempfile.mkdtemp(prefix="shika-home-")
os.environ["HOME"] = HOME
sys.path.insert(0, os.path.dirname(__file__))
from PyQt6 import _base

calls = {"popen": [], "run": []}
HANDLERS = []          # fn(cmd, kwargs) -> None | (returncode, stdout[, stderr]); first answer wins
COMBO_HOOKS = []       # fn(keys_tuple) called whenever Shika presses a key combo

class FakeClip:
    def __init__(self): self.reset()
    def reset(self):
        self.clip, self.primary, self.selection = "old clipboard", "", None   # selection = what is highlighted in the app
        self.copy_works, self.wlpaste_ok = True, True
        self.copy_keys = {("KEY_LEFTCTRL", "KEY_INSERT"), ("KEY_LEFTCTRL", "KEY_C")}   # which copy shortcuts the app accepts
FAKE = FakeClip()
_real_run = subprocess.run
_real_popen = subprocess.Popen
class FakeProc:
    def __init__(self, *a, **k): calls["popen"].append(a[0] if a else k.get("args")); self.returncode = 0
    def wait(self, *a): return 0
def fake_run(cmd, *a, **k):
    calls["run"].append(cmd)
    for h in list(HANDLERS):
        r = h(cmd, k)
        if r is not None:
            return types.SimpleNamespace(returncode=r[0], stdout=r[1], stderr=(r[2] if len(r) > 2 else ""))
    if isinstance(cmd, list) and cmd and cmd[0] in ("python3", "bash", "sh"):
        subprocess.Popen = _real_popen
        try:
            return _real_run(cmd, *a, **k)
        finally:
            subprocess.Popen = FakeProc
    r = types.SimpleNamespace(returncode=0, stdout="", stderr="")
    if isinstance(cmd, list) and cmd[:2] == ["wpctl", "get-volume"]:
        r.stdout = "Volume: 0.60\n"
    if isinstance(cmd, list) and cmd[:1] == ["pgrep"]:
        r.returncode = 1                                   # like a real desktop: nothing matches unless a test says otherwise
    if isinstance(cmd, list) and cmd[:1] == ["wl-paste"]:
        if not FAKE.wlpaste_ok:
            r.returncode, r.stderr = 1, "wl-paste: no clipboard"
        elif "-p" in cmd:
            r.stdout = FAKE.primary
        elif "--list-types" in cmd:
            r.stdout = "text/plain\n"
        else:
            r.stdout = FAKE.clip
    if isinstance(cmd, list) and cmd[:1] == ["wl-copy"]:
        if "--clear" in cmd: FAKE.clip = ""
        elif "--primary" in cmd: FAKE.primary = k.get("input") or ""
        else: FAKE.clip = k.get("input") or ""
    return r
subprocess.Popen = FakeProc
subprocess.run = fake_run

spec = importlib.util.spec_from_file_location("shika", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shika", "shika.py"))
shika = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shika)
shika.shutil.which = lambda n: "/usr/bin/" + n      # pretend every tool is installed

class FakeTyper:
    def __init__(self): self.pasted = []; self.combos = []; self.ui = True; self.error = ""
    def paste(self, t): self.pasted.append(t); FAKE.clip = t; return True
    def combo(self, keys):
        k = tuple(keys); self.combos.append(k)
        if k in FAKE.copy_keys and FAKE.copy_works and FAKE.selection is not None:
            FAKE.clip = FAKE.selection                       # a copy shortcut copies what is selected
        for h in list(COMBO_HOOKS): h(k)
        return True
    def clip_get(self): return FAKE.clip
    def clip_set(self, t, primary=False):
        if primary: FAKE.primary = t
        else: FAKE.clip = t
    def clip_clear(self): FAKE.clip = ""

def make_pup():
    pup = shika.Pup(manual_launch=True)
    pup.typer = FakeTyper()
    return pup

class Seg:
    def __init__(self, text, nsp=0.05, lp=-0.3, cr=1.4):
        self.text, self.no_speech_prob, self.avg_logprob, self.compression_ratio = text, nsp, lp, cr

class FakeModel:
    def __init__(self): self.next = []
    def transcribe(self, audio, **k): return iter(self.next), None

def dictate(pup, segs, mode="dictate"):
    """Run the real press -> commit -> release -> transcribe -> type path with fake audio."""
    pup.stt.model = FakeModel()
    pup.stt.model_name = shika.SPEEDS.get(pup.stt.speed, shika.SPEEDS["balanced"])["model"]
    pup.stt.model.next = segs
    pup.voice_press(mode)
    pup.voice_commit()
    pup.recorder.buf = bytearray(b"\x01\x00" * 16000)      # one second of 'audio'
    pup.recorder.stop = lambda: bytes(pup.recorder.buf)
    done = threading.Event()
    pup.stt.done.connect(lambda *a: done.set())
    pup.voice_stop()
    done.wait(30)
    _base.flush()
    return pup


def reset_world():
    """Back to a clean desktop: clipboard, D-Bus answers, remembered close/shortcut preferences."""
    FAKE.reset(); HANDLERS.clear(); COMBO_HOOKS.clear()
    calls["popen"].clear(); calls["run"].clear()
    shika.KGA_ORDER[:] = [0, 1]

def wait_edit(pup, timeout=8):
    t0 = time.time()
    while getattr(pup, "edit_busy", False) and time.time() - t0 < timeout:
        time.sleep(0.05); _base.flush()
    _base.flush()
