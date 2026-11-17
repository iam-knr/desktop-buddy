import traceback, re
from boot import *
from PyQt6 import _base
import fake_ollama
from datetime import datetime, timedelta
R = []
def check(n, c, d=""): R.append((n, bool(c), d))
pup = make_pup()

# --- reminder phrasing battery (fixed 'now' = Thu 5 Nov 12:00)
now = datetime(2026, 11, 5, 12, 0)
P = [("set a reminder for a meeting for tmrw 5.30 pm", "meeting", "Fri 06 17:30"),
     ("Reminder to call Mohit tmrw 5.30 pm.", "call Mohit", "Fri 06 17:30"),
     ("Remainder to call Mohit tomorrow 5.30 PM", "call Mohit", "Fri 06 17:30"),
     ("Add a reminder to call Mohit tomorrow at 5:30 p.m.", "call Mohit", "Fri 06 17:30"),
     ("remind me at 5 to call Rahul", "call Rahul", "Thu 05 17:00"),
     ("remind me in 20 minutes to drink water", "drink water", "Thu 05 12:20"),
     ("remind me tomorrow to send the invoice", "send the invoice", "Fri 06 09:00"),
     ("remind me on friday at 3 to submit the report", "submit the report", "Fri 06 15:00"),
     ("remind me next monday at 10 am about the batch", "the batch", "Mon 09 10:00"),
     ("remind me on 12th november at 11 am for the client call", "the client call", "Thu 12 11:00"),
     ("remind me november 20 at 4 pm to renew the domain", "renew the domain", "Fri 20 16:00"),
     ("remind me to call 3 clients at 4 pm", "call 3 clients", "Thu 05 16:00"),
     ("remind me at quarter to six to leave", None, "Thu 05 17:45"),
     ("remind me tonight to call mom", "call mom", "Thu 05 20:00"),
     ("remind me to buy milk", "buy milk", "None")]
for t, what, when in P:
    w, d = shika.parse_reminder(shika.spoken_clean(t), now=now)
    got = datetime.fromtimestamp(d).strftime("%a %d %H:%M") if d else "None"
    check(f"parse: {t}", got == when and (what is None or w == what), (w, got))

# --- web / media / control routing
W = [("Open YouTube in Chrome profile 1.", ("chrome", "profile 1", "https://www.youtube.com")),
     ("open gmail in firefox", ("firefox", None, "https://mail.google.com")),
     ("open google ads", (None, None, "https://ads.google.com")),
     ("open google analytics", (None, None, "https://analytics.google.com")),
     ("open adsmentor dot in in chrome", ("chrome", None, "https://adsmentor.in")),
     ("search DV360 line items", (None, None, "https://www.google.com/search?q=dv360+line+items")),
     ("open file manager", None)]
for t, want in W:
    r = shika.parse_web_command(t)
    got = (r["browser"], r["profile"], r["url"]) if r else None
    check(f"web: {t}", got == want, got)
M = [("play kesariya on youtube", ("play", "youtube", "kesariya")), ("arijit singh songs bajao", ("play", "youtube", "arijit singh songs")),
     ("search lofi beats on youtube", ("search", "youtube", "lofi beats")), ("play believer on spotify", ("play", "spotify", "believer")),
     ("play ball", None), ("play music", None), ("pause", None)]
for t, want in M:
    r = shika.parse_media_command(t)
    got = (r["mode"], r["platform"], r["query"]) if r else None
    check(f"media: {t}", got == want, got)

# --- selected-text edit, full path with the AI
srv = fake_ollama.start()
fake_ollama.MODE["reply"] = lambda p, s, f: "I went to the market yesterday."
orig_run = subprocess.run
def run_with_selection(cmd, *a, **k):
    if isinstance(cmd, list) and cmd[:2] == ["wl-paste", "-n"]:
        return types.SimpleNamespace(returncode=0, stdout="i has went to the market yesterday", stderr="")
    return orig_run(cmd, *a, **k)
shika.subprocess.run = run_with_selection
pup.voice_command("fix grammar")
time.sleep(1.0); _base.flush()
check("edit: copies selection, pastes the fix", pup.typer.pasted and pup.typer.pasted[-1] == "I went to the market yesterday.", pup.typer.pasted)
check("edit: both kept in the app", pup.library.entries[-1]["text"] == "I went to the market yesterday."
      and pup.library.entries[-1]["versions"][0]["text"].startswith("i has went"), pup.library.entries[-1])
srv.shutdown(); srv.server_close()
pup.typer.pasted.clear()
pup.voice_command("fix grammar"); time.sleep(0.5); _base.flush()
check("edit without AI: 'fix grammar' still works (rules)", pup.typer.pasted and pup.typer.pasted[-1].startswith("I has went"), pup.typer.pasted)
pup.typer.pasted.clear()
pup.voice_command("make it formal"); time.sleep(0.5); _base.flush()
check("edit without AI: explains it needs Shika AI", not pup.typer.pasted and "Shika AI" in pup.bubble_text, pup.bubble_text)
shika.subprocess.run = orig_run

# --- floating focus timer shares state with the widget
ff = pup.focus_float
json.dump({"mode": "focus", "running": True, "endsAt": time.time() * 1000 + 60000, "leftMs": 60000, "total": 1500000,
           "popout": True, "updated": time.time() * 1000}, open(shika.FOCUS_FILE, "w"))
os.utime(shika.FOCUS_FILE, None); ff.mtime = None; ff.poll()
check("pop-out shows when widget asks", ff.isVisible(), "")
ff.toggle_run()
check("pause from pop-out writes the file", json.load(open(shika.FOCUS_FILE))["running"] is False, "")
ff.close_float()
check("close pop-out tells the widget", json.load(open(shika.FOCUS_FILE))["popout"] is False and not ff.isVisible(), "")

# --- summitctl (what the widgets call)
ctl = ["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "summitctl.py")]
enc = lambda o: urllib.parse.quote(json.dumps(o))
import urllib.parse
r = lambda *a: json.loads(orig_run(ctl + list(a), capture_output=True, text=True, env=dict(os.environ)).stdout or "null")
r("item-add", enc({"kind": "task", "text": "Prep GA4 slides", "due": None}))
r("item-add", enc({"kind": "reminder", "text": "Call Mohit", "due": time.time() + 3600, "repeat": 60}))
items = r("get", "items")["items"]
check("widget: task + reminder added", any(i["text"] == "Prep GA4 slides" and i["kind"] == "task" for i in items)
      and any(i["text"] == "Call Mohit" and i.get("repeat") == 60 for i in items), items)
tid = next(i["id"] for i in items if i["text"] == "Prep GA4 slides")
r("item-update", urllib.parse.quote(tid), enc({"done": True}))
r("clear-done")
check("widget: tick + clear done", not any(i["text"] == "Prep GA4 slides" for i in r("get", "items")["items"]), "")
pup.reload_reminders()
check("Shika sees widget reminders", any(x["text"] == "Call Mohit" for x in pup.reminders), "")
r("note-set", "note-9", enc({"text": "sticky words", "tint": 1}))
r("note-del", "note-9", enc({"text": "sticky words final"}))
pup.library.poll()
e = pup.library.get("sticky:note-9")
check("sticky note mirrored + kept after erase", e and e.get("removed") and e["versions"][-1]["text"] == "sticky words final", e)
r("set", "focus", enc({"mode": "break", "updated": 1}))
check("focus state round-trips", r("get", "focus")["mode"] == "break", "")

for n, ok, d in R:
    if not ok: print("FAIL", n, "\n     ", str(d)[:500])
print(f"\n{sum(1 for x in R if x[1])}/{len(R)} checks passed")
