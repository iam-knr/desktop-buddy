import traceback
from boot import *
from PyQt6 import _base
import fake_ollama
RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))

def case(fn):
    try:
        fn()
    except Exception:
        RESULTS.append((fn.__name__, False, traceback.format_exc()[-900:]))
    return fn

import re
def _w(t): return re.findall(r"[\w']+", t.lower())
pup = make_pup()
lib = pup.library
OFFERS = []
_orig_offer = pup.variant_bar.offer
def _rec_offer(*a):
    OFFERS.append(a); _orig_offer(*a)
pup.variant_bar.offer = _rec_offer
os.makedirs(os.path.join(HOME, ".config/google-chrome"), exist_ok=True)
json.dump({"profile": {"info_cache": {"Default": {"name": "Person 1"}, "Profile 1": {"name": "Adsmentor"}}}},
          open(os.path.join(HOME, ".config/google-chrome/Local State"), "w"))

# ---------------------------------------------------------------- dictation, rules only (no AI)
DICT_CASES = [
    ("I'll schedule a meeting tomorrow afternoon, sorry, tomorrow evening at 5 pm.",
     "I'll schedule a meeting tomorrow evening at 5 p.m.", None),
    ("Schedule a meeting tomorrow morning 7 a.m. No change it to 8 a.m.",
     "Schedule a meeting tomorrow morning 8 a.m.", None),
    ("Book the call for 3 pm, change it to 4 pm.", "Book the call for 4 p.m.", None),
    ("Um so we should meet at 4, no wait, 5 on friday.", "So we should meet at 5 on Friday.", None),
    ("For the workshop bring your laptop, a notebook, your Meta login and a charger.",
     None, "For the workshop bring:\n- Your laptop\n- A notebook\n- Your Meta login\n- A charger"),
    ("First open events manager, then create a new pixel, and finally install it on the site.",
     None, "1. Open events manager\n2. Create a new pixel\n3. Install it on the site"),
    ("Send it to Rahul, I mean Mohit.", "Send it to Mohit.", None),
    ("Bhai kal ka session 5 baje hai, no wait, 6 baje. Laptop le aana", "Bhai kal ka session 6 baje hai. Laptop le aana.", None),
    ("Book 2 tickets for Friday, sorry, 3 tickets.", "Book 3 tickets for Friday.", None),
    ("Hi Mohit comma the agenda for tomorrow's session is GA4 setup, Meta pixel, conversion API and reporting. Thanks",
     None, "Hi Mohit,\n\nThe agenda for tomorrow's session is:\n- GA4 setup\n- Meta pixel\n- Conversion API\n- Reporting\n\nThanks."),
    ("The call is at 3 pm tomorrow, no wait, 4 pm.", "The call is at 4 p.m. tomorrow.", None),
    ("To set up the pixel, first open events manager, then create a new pixel, and finally install it on the site.",
     None, "To set up the pixel:\n1. Open events manager\n2. Create a new pixel\n3. Install it on the site"),
    ("So we are planning to create an app that has the following features: task management, reminders, an interactive companion, and an AI tool. So we plan to launch tomorrow afternoon, 3pm.",
     None, "So we are planning to create an app that has the following features:\n- Task management\n- Reminders\n- An interactive companion\n- An AI tool\n\nSo we plan to launch tomorrow afternoon, 3 p.m."),
    ("Hi Mohit, the agenda is: GA4 setup, Meta pixel, conversion API and reporting. Thanks",
     None, "Hi Mohit,\n\nThe agenda is:\n- GA4 setup\n- Meta pixel\n- Conversion API\n- Reporting\n\nThanks."),
    ("I'm sorry I missed your call.", "I'm sorry I missed your call.", None),
]
@case
def dictation_rules():
    for spoken, want_simple, want_fmt in DICT_CASES:
        pup.typer.pasted.clear()
        dictate(pup, [Seg(" " + spoken)])
        v = pup.stt.variants
        check(f"3 versions exist: {spoken[:30]}", set(v) == {"formatted", "simple", "minimal"} and all(v.values()), v)
        if want_simple:
            check(f"simple: {spoken[:40]}", v["simple"] == want_simple, v["simple"])
        if want_fmt:
            check(f"formatted: {spoken[:40]}", v["formatted"] == want_fmt, v["formatted"])
        check(f"minimal keeps your words: {spoken[:30]}",
              _w(v["minimal"]) == _w(shika.polish_minimal(spoken)), v["minimal"])
        check(f"typed the default (formatted): {spoken[:30]}",
              pup.typer.pasted and pup.typer.pasted[-1].rstrip() == v["formatted"].rstrip(), pup.typer.pasted)
        e = lib.entries[-1]
        check(f"saved in app with cleanup label: {spoken[:30]}", e["kind"] == "dictation" and e.get("cleanup") == "light", e)
        check(f"'as spoken' kept: {spoken[:30]}",
              (e["versions"] and e["versions"][0]["reason"] == "as spoken") or e["text"].strip() == spoken.strip(), e)
        check(f"variant chip offered with all 3: {spoken[:30]}", OFFERS and set(OFFERS[-1][0]) == {"formatted", "simple", "minimal"}, OFFERS[-1:])
        OFFERS.clear()

@case
def variant_switching():
    pup.typer.pasted.clear(); pup.typer.combos.clear()
    dictate(pup, [Seg(" For the workshop bring your laptop, a notebook, your Meta login and a charger.")])
    bar = pup.variant_bar
    eid = lib.entries[-1]["id"]
    bar.pick("simple"); _base.flush()
    check("switch: undo pressed", ("KEY_LEFTCTRL", "KEY_Z") in pup.typer.combos, pup.typer.combos)
    check("switch: simple pasted", pup.typer.pasted[-1].rstrip() == pup.stt.variants["simple"], pup.typer.pasted)
    check("switch: app entry updated", lib.get(eid)["text"] == pup.stt.variants["simple"], lib.get(eid)["text"])
    bar.pick("minimal"); _base.flush()
    check("switch: minimal pasted", pup.typer.pasted[-1].rstrip() == pup.stt.variants["minimal"], pup.typer.pasted[-1])
    n = len(pup.typer.pasted); bar.pick("minimal"); _base.flush()
    check("switch: same version again does nothing", len(pup.typer.pasted) == n, "")

@case
def format_setting():
    for fmt in ("simple", "minimal", "formatted"):
        pup.set_format(fmt)
        dictate(pup, [Seg(" For the workshop bring your laptop, a notebook, your Meta login and a charger.")])
        check(f"FORMAT={fmt} types that version", pup.typer.pasted[-1].rstrip() == pup.stt.variants[fmt].rstrip(),
              (pup.typer.pasted[-1], pup.stt.variants[fmt]))
    pup.set_cleanup("off")
    dictate(pup, [Seg(" um so this is exactly what I said")])
    check("CLEANUP=off types as spoken", pup.typer.pasted[-1].rstrip() == "Um so this is exactly what I said",
          pup.typer.pasted[-1])
    pup.set_cleanup("auto")

# ---------------------------------------------------------------- made-up text from silence
@case
def hallucinations():
    dictate(pup, [Seg(" I will schedule a meeting tomorrow afternoon, sorry tomorrow evening at 5."),
                  Seg(" I'm not sure what I'm saying.", 0.7, -1.1), Seg(" I'm not sure what I'm saying.", 0.6, -0.9),
                  Seg(" I'm not sure what I'm saying.")])
    check("loop + made-up line removed", pup.stt.variants["simple"] == "I will schedule a meeting tomorrow evening at 5.",
          pup.stt.variants)
    dictate(pup, [Seg(" Send the report today."), Seg(" Thanks for watching!", 0.3, -0.8)])
    check("'Thanks for watching' removed", pup.stt.variants["simple"] == "Send the report today.", pup.stt.variants)
    n = len(pup.typer.pasted)
    dictate(pup, [Seg(" Thank you.", 0.8, -1.3)])
    check("pure silence types nothing", len(pup.typer.pasted) == n, pup.typer.pasted[n:])

# ---------------------------------------------------------------- with the AI (fake Ollama server)
srv = fake_ollama.start()
def ai(simple, formatted=None):
    """The fake model: a cleanup prompt gets `simple`, a layout prompt gets `formatted`, both as plain text."""
    def reply(p, sysm, f):
        if "lay out text" in sysm:
            return formatted if formatted is not None else p.split("Input:", 1)[1].rsplit("\nOutput:", 1)[0].strip()
        return simple
    fake_ollama.MODE["reply"] = reply
@case
def ai_good():
    ai("I'll schedule a meeting tomorrow evening at 5 p.m.")
    dictate(pup, [Seg(" All scheduled a meeting tomorrow afternoon, sorry, tomorrow evening at 5 pm.")])
    check("AI fix used when it passes checks", pup.stt.how == "smart" and pup.stt.variants["simple"].startswith("I'll schedule"),
          (pup.stt.how, pup.stt.variants))
    check("AI result labelled for the app", lib.entries[-1].get("cleanup") == "smart", lib.entries[-1])
    ai("For the workshop, bring your laptop, a notebook, your Meta login and a charger.")
    dictate(pup, [Seg(" For the workshop bring your laptop, a notebook, your Meta login and a charger.")])
    check("AI text + rule layout gives the bullet list", "\n- " in pup.stt.variants["formatted"] and pup.stt.how == "smart", pup.stt.variants)
@case
def ai_prompt_shape():
    seen = {}
    def spy(p, sysm, f):
        seen.update(p=p, s=sysm); return "Send the report today."
    fake_ollama.MODE["reply"] = spy
    shika.make_variants("um send the the report today", "auto")
    check("prompt is Input/Output few-shot", seen.get("p", "").startswith("Input: ") and seen["p"].endswith("\nOutput:"), seen.get("p"))
    check("system prompt carries worked examples", seen.get("s", "").count("Input:") >= 5 and "Output:" in seen["s"], "")
    check("no JSON mode any more", True, "")
@case
def ai_layout_pass():
    long = ("We should prepare the quarterly review deck and then book the venue for the offsite and finally "
            "confirm the catering with the vendor before Friday")
    ai(long + ".", "We should prepare the quarterly review deck\n- Book the venue for the offsite\n- Confirm the catering with the vendor before Friday")
    v, how = shika.make_variants(long, "auto", deep=False)
    check("layout pass is off in Balanced", "\n- " not in v["formatted"], v["formatted"])
    ai(long + ".", "We should:\n- Prepare the quarterly review deck\n- Book the venue for the offsite\n- Confirm the catering with the vendor before Friday")
    v, how = shika.make_variants(long, "auto", deep=True)
    check("Best accuracy lets the AI lay out a list the rules missed", "\n- " in v["formatted"] and how == "smart", v["formatted"])
    ai(long + ".", "We should:\n- Prepare the quarterly review deck\n- Book the venue and pay a deposit of 50 euros\n- Confirm the catering")
    v, how = shika.make_variants(long, "auto", deep=True)
    check("a layout that changes words is refused", "50" not in v["formatted"], v["formatted"])
@case
def ai_bad_rejected():
    bad = [("repeats itself", "We meet at 5. We meet at 5. We meet at 5. We meet at 5."),
           ("invents text", "Sure! Here is your cleaned text: we should meet at 5 on Friday, and also bring snacks for everyone."),
           ("changes a number", "So we should meet at 6 on Friday."),
           ("drops content", "Meet."),
           ("empty", "")]
    for why, reply in bad:
        ai(reply)
        dictate(pup, [Seg(" Um so we should meet at 4, no wait, 5 on friday.")])
        check(f"AI rejected when it {why}", pup.stt.how == "light" and pup.stt.variants["simple"] == "So we should meet at 5 on Friday.",
              (pup.stt.how, pup.stt.variants["simple"]))
    ai("Output: So we should meet at 5 on Friday.")
    dictate(pup, [Seg(" Um so we should meet at 4, no wait, 5 on friday.")])
    check("a stray 'Output:' label is stripped, text still used", pup.stt.variants["simple"] == "So we should meet at 5 on Friday.", pup.stt.variants["simple"])
srv.shutdown(); srv.server_close()

# ---------------------------------------------------------------- dictating into the scratchpad
@case
def scratchpad():
    pup.scratch.toggle(); pup.scratch.__dict__["_active"] = True
    before = pup.scratch.edit.toPlainText()
    dictate(pup, [Seg(" For the workshop bring your laptop, a notebook, your Meta login and a charger.")])
    check("dictation lands in scratchpad", pup.scratch.edit.toPlainText().endswith(pup.stt.variants["formatted"]),
          pup.scratch.edit.toPlainText())
    pup.variant_bar.pick("simple")
    check("scratchpad switch to simple", pup.scratch.edit.toPlainText().endswith(pup.stt.variants["simple"]),
          pup.scratch.edit.toPlainText())
    _base.flush()
    pup.scratch.hide(); pup.scratch.__dict__["_active"] = False
    notes = [e for e in lib.entries if e["kind"] == "note"]
    check("scratchpad note saved with a version on close", notes and notes[-1].get("versions"), notes[-1:] )

# ---------------------------------------------------------------- the Shika app
@case
def dashboard():
    d = pup.dashboard
    d.show_app(); _base.flush()
    check("app opens with entries listed", d.list.count() > 0, d.list.count())
    d.new_note(); d.title.setText("Plan"); d.body.setPlainText("draft one"); d.save_now()
    eid = d.current
    check("new note saved", lib.get(eid)["text"] == "draft one", lib.get(eid))
    d.save_version(); d.body.setPlainText("draft two"); d.save_now(); d.save_version()
    vs = lib.get(eid)["versions"]
    check("versions v1, v2 kept", [v["text"] for v in vs] == ["draft one", "draft two"], vs)
    d.view_version(1)
    check("viewing v1 is read-only text", d.body.toPlainText() == "draft one" and d.viewing == 1, d.body.toPlainText())
    d.restore_version()
    check("restore v1", lib.get(eid)["text"] == "draft one", lib.get(eid)["text"])
    d.set_filter("guide"); check("guide page opens", d.pages.currentIndex() == 1, "")
    d.set_filter("dictation"); check("dictations filter", all(lib.get(d.list._items[i].data(0))["kind"] == "dictation" for i in range(d.list.count())), "")
    d.set_filter(None)
    d.show_app(eid); check("open a specific entry", d.current == eid, d.current)
    d.delete_entry(); d.delete_entry()
    check("delete needs two clicks and removes it", lib.get(eid) is None, "")

# ---------------------------------------------------------------- reminders & tasks
@case
def reminders():
    pup.voice_command("reminder to call Mohit tomorrow at 5.30 pm")
    r = [x for x in pup.reminders if x["text"] == "call Mohit"]
    from datetime import datetime, timedelta
    ok = r and datetime.fromtimestamp(r[-1]["due"]).strftime("%H:%M") == "17:30" and \
        datetime.fromtimestamp(r[-1]["due"]).date() == (datetime.now() + timedelta(days=1)).date()
    check("voice reminder tmrw 5:30 pm", ok, r)
    pup.voice_command("add task upload recording at 6 pm")
    t = [x for x in pup.reminders if x.get("kind") == "task" and x["text"] == "upload recording"]
    check("voice task with time", t and t[-1]["due"], t)
    pup.add_reminder("drink water", time.time() - 5)
    pup.reminders[-1]["repeat"] = 60; pup.save_reminders()
    pup.check_reminders()
    check("due reminder starts the bark alert", pup.alerting and pup.alerting["text"] == "drink water", pup.alerting)
    pup.finish_alert(True)
    w = [x for x in pup.reminders if x["text"] == "drink water"][-1]
    check("repeating reminder rolls forward", not w["done"] and w["due"] > time.time(), w)

# ---------------------------------------------------------------- voice commands reach the right action
@case
def commands():
    def last_popen(): return calls["popen"][-1] if calls["popen"] else None
    tests = [
        ("open youtube in chrome profile 1", lambda: "https://www.youtube.com" in " ".join(map(str, last_popen() or []))),
        ("search lofi beats on youtube", lambda: "results?search_query=lofi" in " ".join(map(str, last_popen() or []))),
        ("open google ads", lambda: "ads.google.com" in " ".join(map(str, last_popen() or []))),
        ("next tab", lambda: pup.typer.combos[-1] == ("KEY_LEFTCTRL", "KEY_TAB")),
        ("close tab", lambda: pup.typer.combos[-1] == ("KEY_LEFTCTRL", "KEY_W")),
        ("pause", lambda: any("playerctl" in str(c) for c in calls["run"][-4:]) or ("KEY_PLAYPAUSE",) in pup.typer.combos[-2:]),
        ("close this window", lambda: any("Window Close" in str(c) for c in calls["run"][-3:])),
        ("close scratchpad", lambda: not pup.scratch.isVisible()),
        ("open scratchpad", lambda: pup.scratch.isVisible()),
        ("close scratchpad", lambda: not pup.scratch.isVisible()),
        ("open shika", lambda: pup.dashboard.isVisible()),
        ("note GA4 case study idea", lambda: lib.entries[-1]["text"] == "GA4 case study idea"),
        ("volume up", lambda: "wpctl" in str(last_popen())),
        ("what time is it", lambda: "abhi" in pup.bubble_text),
    ]
    for phrase, ok in tests:
        try:
            pup.alerting = None
            pup.voice_command(phrase); _base.flush()
            check(f"command: {phrase}", ok(), (last_popen(), pup.typer.combos[-1:] , pup.bubble_text))
        except Exception:
            check(f"command: {phrase}", False, traceback.format_exc()[-600:])
    reset_world(); pup.typer.combos.clear(); FAKE.selection = "i has went home"
    pup.voice_command("fix grammar"); wait_edit(pup)
    check("edit command copies with Ctrl+Insert first (safe in terminals)",
          pup.typer.combos and pup.typer.combos[0] == ("KEY_LEFTCTRL", "KEY_INSERT"), pup.typer.combos)

# ---------------------------------------------------------------- speed presets
@case
def speed():
    for sp, model in (("fast", "base.en"), ("balanced", "small.en"), ("best", "small.en")):
        pup.set_speed(sp)
        check(f"speed {sp}: setting saved", pup.stt.speed == sp and pup.settings["speed"] == sp, pup.stt.speed)
        check(f"speed {sp}: model", shika.SPEEDS[sp]["model"] == model, shika.SPEEDS[sp])
    pup.set_speed("balanced")
    srv2 = fake_ollama.start()
    ai("Send the report today.")
    dictate(pup, [Seg(" send the report today")])
    check("short simple sentence skips the AI (instant)", pup.stt.how == "light", pup.stt.how)
    check("time taken is recorded", "secs" in lib.entries[-1], lib.entries[-1])
    srv2.shutdown(); srv2.server_close()
    d = pup.dashboard; d.show_app(lib.entries[-1]["id"])
    check("app shows cleanup label + seconds", "LIGHT CLEANUP" in d.meta.text() and " s" in d.meta.text(), d.meta.text())
    labels = [d.cleanup.itemData(i) for i in range(d.cleanup.count())]
    check("cleanup menu says Shika AI", d.cleanup._items[0][0].startswith("✨ Shika AI") and "qwen" not in str(d.cleanup._items).lower(), d.cleanup._items)
    check("guide never shows the model's name", "qwen" not in shika.GUIDE_HTML.lower(), "")

# ---------------------------------------------------------------- listening: ducking, pose, follow-up line
@case
def listening():
    calls["run"].clear()
    pup.set_cleanup("light")
    pup.alerting = None; pup.climb = None; pup.treat = None; pup.dragging = False; pup.show()
    pup.voice_press("command"); pup.voice_commit()
    check("music turned down while holding", any(c[:2] == ["wpctl", "set-volume"] and c[-1] == "0.048" for c in calls["run"] if isinstance(c, list)),
          [c for c in calls["run"] if isinstance(c, list) and c[:1] == ["wpctl"]])
    check("pup turns around to listen", pup.listening and pup.state == "spin", pup.state)
    pup.stt.model = FakeModel(); pup.stt.model.next = [Seg(" what time is it")]
    pup.stt.model_name = shika.SPEEDS[pup.stt.speed]["model"]
    pup.recorder.stop = lambda: b"\x01\x00" * 16000
    ev = threading.Event(); pup.stt.done.connect(lambda *a: ev.set())
    pup.voice_stop(); ev.wait(10); _base.flush()
    check("volume restored on release", any(c[:2] == ["wpctl", "set-volume"] and c[-1] == "0.600" for c in calls["run"] if isinstance(c, list)), "")
    check("pup stops listening after", not pup.listening, pup.state)
    check("says 'aur kuch chahiye to bulaana'", pup.bubble_text == shika.LINE_MORE, pup.bubble_text)
    pup.set_cleanup("auto")

for n, ok, d in RESULTS:
    if not ok:
        print("FAIL", n, "\n     ", str(d)[:700])
print(f"\n{sum(1 for r in RESULTS if r[1])}/{len(RESULTS)} checks passed")
