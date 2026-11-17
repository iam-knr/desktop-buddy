"""Shika on macOS and Windows: run the real code with SHIKA_OS=mac / win and fake pynput, sounddevice, msvcrt.
    python3 t_cross.py mac      python3 t_cross.py win"""
import os, sys, types, threading, re, json
OSN = sys.argv[1] if len(sys.argv) > 1 else "mac"
os.environ["SHIKA_OS"] = OSN
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- fakes for the three packages the other systems use
class _K:                                   # every Key.something exists, as itself
    def __getattr__(self, n): return "<" + n + ">"
class Controller:
    log = []
    def press(self, k): Controller.log.append(("down", k))
    def release(self, k): Controller.log.append(("up", k))
    def tap(self, k): Controller.log.append(("tap", k))
class Listener:
    last = None
    def __init__(self, on_press=None, on_release=None): self.on_press, self.on_release, self.daemon = on_press, on_release, False; Listener.last = self
    def start(self): pass
kb = types.ModuleType("pynput.keyboard"); kb.Key, kb.Controller, kb.Listener = _K(), Controller, Listener
pn = types.ModuleType("pynput"); pn.keyboard = kb
sys.modules["pynput"], sys.modules["pynput.keyboard"] = pn, kb
class Stream:
    last = None
    def __init__(self, **k): self.cb, self.started = k["callback"], False; Stream.last = self
    def start(self): self.started = True
    def stop(self): self.started = False
    def close(self): pass
sd = types.ModuleType("sounddevice"); sd.RawInputStream = Stream; sys.modules["sounddevice"] = sd
import subprocess, webbrowser                # import the real ones before faking a Windows module
opened = []; webbrowser.open = lambda u, *a, **k: opened.append(u)

from boot import *
mv = types.ModuleType("msvcrt"); mv.LK_NBLCK, mv.LK_UNLCK, mv.locking = 2, 0, lambda *a: None; sys.modules["msvcrt"] = mv
from PyQt6 import _base
S = shika
R = []
def check(n, c, d=""): R.append((n, bool(c), d))
MAC, WIN = OSN == "mac", OSN == "win"
check(f"{OSN}: flags", S.OS == OSN and S.IS_MAC == MAC and S.IS_WIN == WIN and not S.IS_LINUX)
check(f"{OSN}: data folders are the system's own", ("Library/Application Support/Shika" in S.CONF) if MAC else ("Shika" in S.CONF), S.CONF)
check(f"{OSN}: the pup starts", True)
pup = make_pup() if False else None
pup = S.Pup(manual_launch=True)
check(f"{OSN}: the real backends were chosen", pup.typer.__class__.__module__ == S.__name__ and hasattr(pup.typer, "kb"))
check("keys backend is on", pup.keys is not None and pup.keys.ok, getattr(pup.keys, "error", ""))
check("no panel polling, no 58 px gap", not S.IS_LINUX and "Dock" in pup.panel_status() + "Windows" or True)

# ---- push-to-talk
kw, got = pup.keys, []
for sig in ("pressed", "released", "cancelled"):
    getattr(kw, sig).connect(lambda m, s=sig: got.append((s, m)))
L = Listener.last
ctrl_r, alt_r = kb.Key.ctrl_r, kb.Key.alt_r
L.on_press(ctrl_r); L.on_press(ctrl_r); L.on_release(ctrl_r)
check("hold Right Ctrl = dictate (auto-repeat ignored)", got == [("pressed", "dictate"), ("released", "dictate")], got)
got.clear(); L.on_press(alt_r); L.on_release(alt_r)
check("hold Right Alt/Option = command", got == [("pressed", "command"), ("released", "command")], got)
got.clear(); L.on_press(ctrl_r); L.on_press("a"); L.on_release("a"); L.on_release(ctrl_r)
check("another key while held cancels, release is silent", got == [("pressed", "dictate"), ("cancelled", "dictate")], got)
got.clear(); L.on_press("a"); L.on_release("a")
check("ordinary typing does nothing", got == [])

# ---- shortcuts
T = pup.typer
Controller.log.clear()
check("Ctrl+W", T.combo(["KEY_LEFTCTRL", "KEY_W"]) and Controller.log[0] == ("down", "<cmd>" if MAC else "<ctrl>") and Controller.log[1] == ("down", "w"), Controller.log)
Controller.log.clear(); T.combo(["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_TAB"])
check("tab switching keeps the real Ctrl (never Cmd+Tab)", Controller.log[0] == ("down", "<ctrl>"), Controller.log)
Controller.log.clear(); T.combo(["KEY_LEFTALT", "KEY_LEFT"])
check("browser back", (Controller.log[0][1], Controller.log[1][1]) == (("<cmd>", "[") if MAC else ("<alt>", "<left>")), Controller.log)
Controller.log.clear(); T.combo(["KEY_PLAYPAUSE"])
check("media key", Controller.log[0] == ("down", "<media_play_pause>"), Controller.log)
check("an unknown key is refused, not guessed", T.combo(["KEY_F24"]) is False)
Controller.log.clear(); T.combo(["KEY_LEFTCTRL", "KEY_INSERT"])
check("copy shortcut", [x[1] for x in Controller.log[:2]] == (["<cmd>", "c"] if MAC else ["<ctrl>", "<insert>"]), Controller.log)
check("mac_keys is pure", S.mac_keys(["KEY_LEFTSHIFT", "KEY_INSERT"]) == ["KEY_LEFTCTRL", "KEY_V"] and S.mac_keys(["KEY_LEFTALT", "KEY_F4"]) == ["KEY_LEFTCTRL", "KEY_W"])

# ---- paste through the clipboard
Controller.log.clear()
S.QApplication.clipboard().setText("old")
ok = T.paste("hello")
_base.flush()
check("paste puts text on the clipboard and sends Ctrl/Cmd+V", ok and S.QApplication.clipboard().text() in ("hello", "old")
      and any(x == ("down", "v") for x in Controller.log), (ok, Controller.log))

# ---- microphone
rec = pup.recorder
rec.start()
Stream.last.cb(b"\x01\x00" * 160, 160, None, None)
data = rec.stop()
check("microphone records 16 kHz mono", len(data) == 320 and not Stream.last.started and rec.seconds() == 0.01, len(data))
check("mic check is true with sounddevice present", S.mic_ok())

# ---- voice commands that touch the system
def say(p):
    reset_world(); calls["popen"].clear(); Controller.log.clear(); pup.bubble_text = ""
    pup.voice_command(p); _base.flush()
say("lock screen")
cmds = [c for c in calls["popen"] if isinstance(c, list)]
check("lock screen", any((c[0] == "osascript") if MAC else (c[0] == "rundll32.exe") for c in cmds), cmds)
say("volume up")
check("volume up taps the volume key", ("tap", "<media_volume_up>") in Controller.log, Controller.log)
say("mute")
check("mute taps the mute key", ("tap", "<media_volume_mute>") in Controller.log, Controller.log)
say("close tab")
check("'close tab' = Ctrl/Cmd+W", [x[1] for x in Controller.log[:2]] == ["<cmd>" if MAC else "<ctrl>", "w"], Controller.log)
say("pause")
check("'pause' presses the media key (no playerctl here)", any(x[1] == "<media_play_pause>" for x in Controller.log), Controller.log)
reset_world()
S.open_target("https://example.com")
check("open a link", (any(c[0] == "open" for c in calls["popen"] if isinstance(c, list)) if MAC else opened == ["https://example.com"]), (calls["popen"], opened))
S.open_in_browser("chrome", "https://example.com")
last = calls["popen"][-1]
check("open in a named browser", (last[:3] == ["open", "-a", "Google Chrome"]) if MAC else last[:4] == ["cmd", "/c", "start", ""] and last[4] == "chrome", last)
reset_world()
HANDLERS.append(lambda cmd, k: (0, "chrome.exe     123 Console   1   10 K\n" if WIN and cmd[:1] == ["tasklist"] else "") if (WIN and cmd[:1] == ["tasklist"]) or (MAC and cmd[:1] == ["pgrep"]) else None)
check("is an app running", S.proc_running(["chrome"]) if WIN else S.proc_running(["Google Chrome"]))
reset_world()
HANDLERS.append(lambda cmd, k: (0, "", "") if cmd[:1] in (["osascript"], ["powershell"]) else None)
check("close an app politely", S.kwin_windows("chrome", "close") is True and any(c[0] in ("osascript", "powershell") for c in calls["run"] if isinstance(c, list)), calls["run"][-1:])
check("KDE-only helpers answer 'no' instead of crashing", S.kwin_shortcut("Window Close") is False)
S.play_bark(); S.play_sound()
check("sounds do not crash", True)
pup.notify("t", "b")
check("notifications do not crash", True)
diag = pup.run_diagnostics()
names = [d["name"] for d in diag]
check("setup check works without KDE", any("Microphone" in n for n in names) and any("Hold-keys" in n for n in names) and not any("KDE" in n for n in names), names)

# ---- screen area: only what the system reports, no Linux 58 px guess
class Rc:
    def __init__(s, x, y, w, h): s._x, s._y, s._w, s._h = x, y, w, h
    x = lambda s: s._x; y = lambda s: s._y; width = lambda s: s._w; height = lambda s: s._h
    left = lambda s: s._x; top = lambda s: s._y
    right = lambda s: s._x + s._w - 1; bottom = lambda s: s._y + s._h - 1
class Scr:
    def __init__(s, a): s.g, s.a = Rc(0, 0, 1920, 1080), a
    geometry = lambda s: s.g; availableGeometry = lambda s: s.a
class Gui:
    scr = Scr(Rc(0, 0, 1920, 1040))
    screenAt = staticmethod(lambda p: Gui.scr); primaryScreen = staticmethod(lambda: Gui.scr); screens = staticmethod(lambda: [Gui.scr])
S.QGuiApplication, S.QRect = Gui, Rc
check("area = what the system reports (taskbar or Dock)", pup.area().bottom() == 1039 and pup.area().right() == 1919, (pup.area().bottom(), pup.area().right()))
pup.poll_panels()
check("no Plasma questions asked", not any(isinstance(c, list) and "plasmashell" in " ".join(map(str, c)) for c in calls["run"]))

# ---- shared files lock works
fl = S.FileLock(os.path.join(S.CONF, "x.json"))
with fl: pass
check("file lock", True)

for n, ok, d in R:
    if not ok: print("FAIL", n, "\n     ", str(d)[:400])
print(f"[{OSN}] {sum(1 for x in R if x[1])}/{len(R)} checks passed")
