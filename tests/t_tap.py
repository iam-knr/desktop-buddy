from boot import *
from PyQt6 import _base
pup = make_pup()
pup.stt.run = lambda *a: (_ for _ in ()).throw(AssertionError("should not transcribe"))
calls["run"].clear()
pup.voice_press("dictate"); pup.voice_stop()                          # a quick tap
ok1 = not any(isinstance(c, list) and c[:2] == ["wpctl", "set-volume"] for c in calls["run"]) and pup.voice_mode is None
pup.voice_press("dictate"); pup.voice_commit(); pup.voice_cancel()    # Right Ctrl + C combo after a hold
ok2 = pup.ducked is None and not pup.listening and pup.voice_mode is None
pup.settings["ducked_from"] = 0.5; shika.save_json(shika.SETTINGS_FILE, pup.settings)
pup2 = make_pup()                                                     # restart after a crash mid-listen
ok3 = any(isinstance(c, list) and c[:2] == ["wpctl", "set-volume"] and c[-1] == "0.500" for c in calls["run"]) and "ducked_from" not in pup2.settings
print("tap ignored:", ok1, "| combo cancels cleanly:", ok2, "| volume restored after crash:", ok3)
