import os, sys, types, threading, time
from boot import *
# a fake evdev with one keyboard whose events we feed through a pipe
ec = types.SimpleNamespace(EV_KEY=1, KEY_A=30, KEY_C=46, ecodes={"KEY_RIGHTCTRL": 97, "KEY_RIGHTALT": 100})
r, w = os.pipe()
queue = []
class Dev:
    name = "AT Translated Set 2 keyboard"
    def capabilities(self): return {1: [30, 46, 97, 100]}
    def fileno(self): return r
    def read(self):
        os.read(r, 1)
        return [queue.pop(0)]
    def close(self): pass
evdev = types.SimpleNamespace(ecodes=ec, list_devices=lambda: ["/dev/input/event3"], InputDevice=lambda p: Dev())
sys.modules["evdev"] = evdev
kw = shika.KeyWatcher()
got = []
kw.pressed.connect(lambda m: got.append(("press", m)))
kw.released.connect(lambda m: got.append(("release", m)))
kw.cancelled.connect(lambda m: got.append(("cancel", m)))
def send(code, val):
    queue.append(types.SimpleNamespace(type=1, code=code, value=val)); os.write(w, b"x"); time.sleep(0.05)
send(97, 1); send(97, 2); send(97, 0)                  # hold + autorepeat + release Right Ctrl
send(100, 1); send(46, 1); send(46, 0); send(100, 0)   # Right Alt + C combo -> cancelled, no release
send(30, 1); send(30, 0)                               # ordinary key: nothing
time.sleep(0.2)
want = [("press", "dictate"), ("release", "dictate"), ("press", "command"), ("cancel", "command")]
print("keys OK" if kw.ok and got == want else f"keys FAIL {kw.ok} {got}")
