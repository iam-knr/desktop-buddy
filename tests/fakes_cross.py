"""Fake pynput and sounddevice so Mac and Windows code paths load on Linux."""
import types, sys
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
