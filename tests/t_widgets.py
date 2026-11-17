"""Desktop widgets (tasks, sticky notes, focus timer, clock): python3 t_widgets.py [linux|mac|win]"""
import os, sys, json, time, datetime, types
OSN = sys.argv[1] if len(sys.argv) > 1 else "linux"
if OSN != "linux":
    os.environ["SHIKA_OS"] = OSN
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fakes_cross import *
    import subprocess, webbrowser
from boot import *
if OSN == "win":
    mv = types.ModuleType("msvcrt"); mv.LK_NBLCK, mv.LK_UNLCK, mv.locking = 2, 0, lambda *a: None; sys.modules["msvcrt"] = mv
from PyQt6 import _base
S = shika
R = []
def check(n, c, d=""): R.append((n, bool(c), d))
pup = S.Pup(manual_launch=True) if OSN != "linux" else make_pup()

# ---- the time parser
base = datetime.datetime(2026, 11, 17, 14, 0).timestamp()          # Tue 2 pm
def at(h, m=0, d=0):
    return (datetime.datetime(2026, 11, 17, h, m) + datetime.timedelta(days=d)).timestamp()
P = S.parse_clock
check("blank is 'no time'", P("", base) == 0 and P("   ", base) == 0)
check("6:45 pm", P("6:45 pm", base) == at(18, 45))
check("6.45pm and 6 p.m.", P("6.45pm", base) == at(18, 45) and P("6 p.m.", base) == at(18))
check("18:45", P("18:45", base) == at(18, 45))
check("bare 6 picks the next 6 (evening today)", P("6", base) == at(18))
check("bare 1 is tomorrow 1 am, 1 pm already passed", P("1", base) == at(13, 0, 1) or P("1", base) == at(1, 0, 1), P("1", base))
check("tmrw 5:30 pm", P("tmrw 5:30 pm", base) == at(17, 30, 1))
check("tomorrow 9 means 9 am", P("tomorrow 9", base) == at(9, 0, 1))
check("today 9 pm", P("today 9 pm", base) == at(21))
check("garbage is refused", P("soon", base) == -1 and P("25:00", base) == -1 and P("13 pm", base) == -1 and P("7:75", base) == -1)
check("labels", S.when_label(base + 30, base) == "in 1 min" and S.when_label(base - 5, base) == "overdue"
      and S.when_label(at(18, 45), base) == "6:45 PM" and S.when_label(at(9, 0, 1), base) == "Tmrw 9:00 AM")

# ---- manager and flags
W = pup.widgets
check("manager starts empty", W.live == {})

# ---- tasks
t = W.show("tasks")
check("tasks widget opens and is remembered", t.isVisible() and pup.settings["widgets"]["tasks"]["open"] is True)
t.text.setText("Upload session recording"); t.add("task")
check("task is saved in the shared file", any(r["text"] == "Upload session recording" and r["kind"] == "task" and not r["due"]
      for r in json.load(open(S.REMINDERS_FILE))))
t.text.setText("Call Rahul"); t.time.setText("6:45 pm"); t.add("reminder")
rem = [r for r in json.load(open(S.REMINDERS_FILE)) if r["text"] == "Call Rahul"][0]
check("reminder keeps its time", rem["kind"] == "reminder" and rem["due"] > time.time() - 1, rem)
t.text.setText("Water"); t.time.setText(""); t.add("reminder")
check("a reminder without a time is refused", not [r for r in json.load(open(S.REMINDERS_FILE)) if r["text"] == "Water"])
t.text.setText("Stretch"); t.pick_when(2); t.repeat_idx = 2; t.add("reminder")
st = [r for r in json.load(open(S.REMINDERS_FILE)) if r["text"] == "Stretch"][0]
check("+1 hr chip and daily repeat", 3500 < st["due"] - time.time() < 3700 and st["repeat"] == 1440, st)
t.text.setText("bad time"); t.time.setText("whenever"); t.add("task")
check("an unreadable time is refused", not [r for r in json.load(open(S.REMINDERS_FILE)) if r["text"] == "bad time"])
t.time.setText("")
tid = [r for r in pup.reminders if r["text"] == "Upload session recording"][0]["id"]
t.patch(tid, done=True)
check("tick a task", [r for r in json.load(open(S.REMINDERS_FILE)) if r["id"] == tid][0]["done"] is True)
t.clear_done()
check("clear done removes ticked tasks only", not [r for r in json.load(open(S.REMINDERS_FILE)) if r["id"] == tid]
      and any(r["text"] == "Call Rahul" for r in json.load(open(S.REMINDERS_FILE))))
t.remove(rem["id"])
check("delete", not [r for r in json.load(open(S.REMINDERS_FILE)) if r["id"] == rem["id"]])
# another program (voice, the Plasma widget) edits the file: the widget picks it up
with open(S.REMINDERS_FILE, "w") as f:
    json.dump([{"id": "x1", "kind": "task", "text": "From the voice command", "due": None, "done": False}], f)
os.utime(S.REMINDERS_FILE, (time.time() + 5, time.time() + 5))
t.poll()
check("outside edits show up", [x["text"] for x in t.items()] == ["From the voice command"], t.items())

# ---- sticky notes
k = W.new_note()
n = W.live[k]
check("first note is note-d1 and is open", k == "note-d1" and n.isVisible())
n.edit.setPlainText("GA4 case study idea"); n.save()
check("note text is in notes.json", json.load(open(S.STICKY_FILE))["note-d1"]["text"] == "GA4 case study idea")
e = pup.library.get("sticky:note-d1")
check("and in the Shika app as a sticky entry", e and e["text"] == "GA4 case study idea" and e["kind"] == "sticky", e)
n.set_tint(1)
check("tint is saved", json.load(open(S.STICKY_FILE))["note-d1"]["tint"] == 1)
k2 = W.new_note()
check("second note gets its own id", k2 == "note-d2")
n.bin()
check("first press of the bin only asks", "note-d1" in json.load(open(S.STICKY_FILE)) and n.confirm)
n.bin()
e = pup.library.get("sticky:note-d1")
check("second press erases it from disk", "note-d1" not in json.load(open(S.STICKY_FILE)) and not n.isVisible())
check("the text stays in the app as a version", e and e.get("removed") and e["versions"] and e["versions"][-1]["reason"] == "erased from desktop", e)
check("erased note is forgotten", "note-d1" not in pup.settings["widgets"])
W.live["note-d2"].edit.setPlainText("second"); W.live["note-d2"].save()

# ---- focus timer
f = W.show("focus")
f.choose(1)
check("45 min preset", f.st["choice"] == 1 and round(f.remaining() / 60000) == 45, f.st)
f.toggle()
check("start", f.st["running"] and f.st["endsAt"] > time.time() * 1000)
f.toggle()
check("pause keeps the time", not f.st["running"] and 44 * 60000 < f.st["leftMs"] <= 45 * 60000)
f.toggle(); f.write(endsAt=time.time() * 1000 - 5); f.render()
check("finishing adds a session and starts the break", f.st["sessions"] == 1 and f.st["mode"] == "break" and not f.st["running"]
      and f.st["leftMs"] == 5 * 60000, f.st)
f.write(sessions=4); f.switch("break")
check("every 4th break is long", f.st["leftMs"] == 15 * 60000, f.st)
f.switch("focus"); f.reset()
check("reset", f.st["leftMs"] == 45 * 60000 and not f.st["running"])
f.pop_out()
check("pop out turns on the mini timer's flag", json.load(open(S.FOCUS_FILE))["popout"] is True)
other = json.load(open(S.FOCUS_FILE)); other["running"] = True; other["endsAt"] = time.time() * 1000 + 60000; other["updated"] = time.time() * 1000 + 1
json.dump(other, open(S.FOCUS_FILE, "w")); os.utime(S.FOCUS_FILE, (time.time() + 9, time.time() + 9))
f.poll()
check("changes from the mini timer show up", f.st["running"] is True)
f.write(running=False)

# ---- clock
c = W.show("clock")
check("12-hour text", c.clock_text(datetime.datetime(2026, 11, 17, 15, 5)) .startswith("3<span") and c.clock_text(datetime.datetime(2026, 11, 17, 0, 7)).startswith("12<span"))
c.set_opt("hour24", True)
check("24-hour text and it is remembered", c.clock_text(datetime.datetime(2026, 11, 17, 7, 5)).startswith("07<span")
      and pup.settings["widgets"]["clock"]["hour24"] is True)
pup.reminders[:] = [{"id": "a", "kind": "reminder", "text": "Call Rahul", "due": time.time() + 1800, "done": False}]
check("next reminder line", "Call Rahul" in c.next_text() and "in 30 min" in c.next_text(), c.next_text())
c.set_opt("show_next", False)
check("next reminder can be hidden", "Call Rahul" not in c.next_text())
c.render()

# ---- dragging remembers the spot
class Ev:
    def __init__(s, x, y): s.p = S.QPoint(x, y)
    def globalPosition(s): return types.SimpleNamespace(toPoint=lambda: s.p)
f.drag_from = None
f.remember(pos=[120, 80])
check("position is stored per widget", pup.settings["widgets"]["focus"]["pos"] == [120, 80])

# ---- restore after a restart
pup.widgets.hide_all()
check("hide all closes everything", not any(w.isVisible() for w in W.live.values()))
check("closing is remembered", pup.settings["widgets"]["tasks"]["open"] is False)
W.show("clock"); W.show("note-d2")
pup2 = S.Pup(manual_launch=True) if OSN != "linux" else make_pup()
pup2.widgets.restore(); _base.flush()
check("a new pup brings back the open ones", sorted(k for k, w in pup2.widgets.live.items() if w.isVisible()) == ["clock", "note-d2"],
      {k: w.isVisible() for k, w in pup2.widgets.live.items()})
check("the note's text came back", pup2.widgets.live["note-d2"].edit.toPlainText() == "second")

# ---- voice
def say(phrase):
    reset_world() if OSN == "linux" else None
    pup.widgets.hide_all(); pup.voice_command(phrase); _base.flush()
for phrase, key in (("show tasks widget", "tasks"), ("open the focus timer", "focus"), ("show clock widget", "clock"), ("open my to do list", "tasks")):
    say(phrase)
    check(f"'{phrase}'", key in pup.widgets.live and pup.widgets.live[key].isVisible(), phrase)
say("add a sticky note")
check("'add a sticky note'", any(k.startswith("note-d") and w.isVisible() for k, w in pup.widgets.live.items()))
say("open widgets")
check("'open widgets' shows the three", all(pup.widgets.live[k].isVisible() for k in ("tasks", "focus", "clock")))
pup.voice_command("hide all widgets"); _base.flush()
check("'hide all widgets'", not any(w.isVisible() for w in pup.widgets.live.values()))
say("open clock")
check("'open clock' alone is left to the system Clock app", not pup.widgets.live["clock"].isVisible())

for n_, ok, d in R:
    if not ok: print("FAIL", n_, "\n     ", str(d)[:500])
print(f"[{OSN}] {sum(1 for x in R if x[1])}/{len(R)} checks passed")
