"""Edit-selected-text commands, end to end: spoken phrase -> copy -> Shika AI + safety checks -> paste.
Includes every way it can go wrong on a real desktop (copy fails, clipboard unreadable, AI down or misbehaving)."""
import re, os, json, time
from boot import *
from PyQt6 import _base
import fake_ollama
R = []
def check(n, c, d=""): R.append((n, bool(c), d))

# ---------------------------------------------------------------- what people actually say
YES = {"fix grammar": "fix", "Fix grammar.": "fix", "fix the grammar": "fix", "Fix my grammar": "fix", "please fix the grammar": "fix",
       "can you fix the grammar": "fix", "fix grammar please": "fix", "fix the grammar in this": "fix", "proofread": "fix",
       "proof read this": "fix", "correct this": "fix", "fix grammer": "fix", "grammar check": "fix", "fix it": "fix",
       "check my spelling": "fix", "spell check": "fix", "fix spelling and grammar": "fix",
       "make it formal": "formal", "make it more formal": "formal", "make this sound professional": "formal",
       "Make it professional.": "formal", "formalize it": "formal", "make it formal please": "formal",
       "make it shorter": "shorter", "make it short": "shorter", "make this shorter": "shorter", "shorten it": "shorter",
       "make it a bit shorter": "shorter", "make it concise": "shorter", "shorten": "shorter", "trim it": "shorter",
       "hey make it shorter": "shorter", "make it friendly": "casual", "make it casual": "casual", "make it polite": "polite",
       "make it clearer": "clear", "simplify this": "clear", "expand this": "longer", "turn this into bullet points": "bullets",
       "make this into a list": "bullets", "turn it into an email": "email", "summarize this": "summary",
       "translate this to hindi": "translate", "rewrite this in a funny way": "rewrite"}
for phrase, kind in YES.items():
    r = shika.match_edit(shika.spoken_clean(phrase).lower().rstrip(".!?, "))
    check(f"phrase '{phrase}' -> {kind}", r and r[0] == kind, r)
for phrase in ("open gmail", "make a note", "fix", "close it", "note fix grammar tomorrow", "remind me to fix the grammar", "play it", "make", "short"):
    check(f"'{phrase}' is not an edit command", shika.match_edit(phrase) is None, shika.match_edit(phrase))

# ---------------------------------------------------------------- the pipeline
pup = make_pup()
srv = fake_ollama.start()
REPLY = {}
def reply(p, sysm, f):
    src = p.split("Input: ", 1)[1].rsplit("\nOutput:", 1)[0].strip() if "Input: " in p else p
    return REPLY.get(src, src)
fake_ollama.MODE["reply"] = reply

def run(phrase, selection, **flags):
    reset_world()
    pup.typer.pasted.clear(); pup.typer.combos.clear(); pup.bubble_text = ""
    FAKE.selection = selection
    for k, v in flags.items(): setattr(FAKE, k, v)
    pup.voice_command(phrase); wait_edit(pup)
    return pup.bubble_text
def leaked(): return "⟦shika" in FAKE.clip or "⟦shika" in FAKE.primary

SEL = "i has went to the market yesterday and buyed apples"
FIX = "I went to the market yesterday and bought apples."
REPLY[SEL] = FIX

msg = run("Fix grammar.", SEL)
check("happy path: fixed text pasted over the selection", pup.typer.pasted == [FIX], pup.typer.pasted)
check("happy path: first copy key is Ctrl+Insert (safe in terminals)", pup.typer.combos[:1] == [("KEY_LEFTCTRL", "KEY_INSERT")], pup.typer.combos)
check("happy path: bubble says done + how to undo", "ho gaya" in msg and "Ctrl+Z" in msg, msg)
e = pup.library.entries[-1]
check("happy path: both versions kept in the app", e["kind"] == "note" and e["title"].startswith("Edited:") and e["text"] == FIX
      and e["versions"][0]["text"] == SEL and e["versions"][0]["reason"] == "as spoken", e)
check("happy path: your own clipboard comes back", FAKE.clip == "old clipboard", FAKE.clip)
check("happy path: no marker left behind, not busy", not leaked() and not pup.edit_busy, (FAKE.clip, pup.edit_busy))

msg = run("fix grammar", SEL, copy_keys={("KEY_LEFTCTRL", "KEY_C")})
check("app ignores Ctrl+Insert: Ctrl+C is the second try", pup.typer.combos[:2] == [("KEY_LEFTCTRL", "KEY_INSERT"), ("KEY_LEFTCTRL", "KEY_C")]
      and pup.typer.pasted == [FIX], (pup.typer.combos, pup.typer.pasted))

msg = run("fix grammar", None)
check("nothing selected: says so, pastes nothing", "nahi mila" in msg and not pup.typer.pasted, (msg, pup.typer.pasted))
check("nothing selected: the OLD clipboard is never edited", pup.library.entries[-1]["title"].startswith("Edited:") is False
      or "old clipboard" not in pup.library.entries[-1]["text"], pup.library.entries[-1])
check("nothing selected: clipboard restored, no marker", FAKE.clip == "old clipboard" and not leaked(), FAKE.clip)

REPLY["we r launching soon"] = "We are launching soon."
msg = run("fix grammar", None, copy_works=False); FAKE.primary = ""
FAKE.reset(); FAKE.selection = None; FAKE.copy_works = False; FAKE.primary = "we r launching soon"
pup.typer.pasted.clear(); pup.voice_command("fix grammar"); wait_edit(pup)
check("copy fails but text is highlighted: mouse selection is used", pup.typer.pasted == ["We are launching soon."], (pup.typer.pasted, pup.bubble_text))

msg = run("fix grammar", SEL, wlpaste_ok=False)
check("clipboard unreadable: points to Check my setup, pastes nothing", "Check my setup" in msg and not pup.typer.pasted, (msg, pup.typer.pasted))
check("clipboard unreadable: still not busy afterwards", not pup.edit_busy, "")

# ---- Shika AI misbehaving: the text is only replaced when the answer passes the checks
HEY = "hey can u send me the file asap thx"
OKF = "Could you please send me the file as soon as possible? Thank you."
REPLY[HEY] = 'Sure! Here is the formal version:\n"' + OKF + '"'
msg = run("make it formal", HEY)
check("chatty answer is cleaned, no stray quote", pup.typer.pasted == [OKF], pup.typer.pasted)
REPLY["meet at 5 pm on friday"] = "Let us meet at 6 pm on Friday."
msg = run("make it formal", "meet at 5 pm on friday")
check("AI changed a number: refused, text untouched", not pup.typer.pasted and "waisa hi rakha" in msg, (pup.typer.pasted, msg))
LONG = "I just wanted to reach out and let you know that we will be a little late to the meeting because of heavy traffic."
REPLY[LONG] = LONG + " We apologise sincerely for any inconvenience this may cause to everybody involved."
msg = run("make it shorter", LONG)
check("'shorter' that is longer: refused", not pup.typer.pasted, pup.typer.pasted)
REPLY[LONG] = "We'll be a little late to the meeting because of heavy traffic."
msg = run("shorten it", LONG)
check("'shorter' that is shorter: pasted", pup.typer.pasted == [REPLY[LONG]], pup.typer.pasted)
REPLY["I went home."] = "I went home."
msg = run("fix grammar", "I went home.")
check("nothing to change: says so, pastes nothing", "kuch badalna nahi" in msg and not pup.typer.pasted, (msg, pup.typer.pasted))
REPLY["buy milk, eggs and bread"] = "- Buy milk\n- Eggs\n- Bread"
msg = run("turn this into bullet points", "buy milk, eggs and bread")
check("bullets: pasted as a list", pup.typer.pasted == ["- Buy milk\n- Eggs\n- Bread"], pup.typer.pasted)

# ---- guards
reset_world(); pup.edit_busy = True; pup.typer.combos.clear(); pup.voice_command("fix grammar")
check("second command while one is running: asked to wait, nothing pressed", "ruko" in pup.bubble_text and not pup.typer.combos, (pup.bubble_text, pup.typer.combos))
pup.edit_busy = False
reset_world(); pup.typer.ui = False; pup.voice_command("fix grammar")
check("no keyboard permission: clear message", "keyboard access" in pup.bubble_text, pup.bubble_text); pup.typer.ui = True
shika.shutil.which = lambda n: None if n in ("wl-copy", "wl-paste") else "/usr/bin/" + n
reset_world(); pup.voice_command("fix grammar")
check("wl-clipboard missing: says how to install it", "wl-clipboard" in pup.bubble_text, pup.bubble_text)
shika.shutil.which = lambda n: "/usr/bin/" + n

# ---- through the real voice path: Right Alt -> Whisper -> command -> edit
reset_world(); FAKE.selection = SEL; pup.typer.pasted.clear()
dictate(pup, [Seg(" Fix grammar.")], mode="command"); wait_edit(pup)
check("whole voice path: held key + 'Fix grammar.' edits the selection", pup.typer.pasted == [FIX], (pup.typer.pasted, pup.bubble_text))

# ---- Shika AI switched off: the rules still fix the basics, the rest explains itself
srv.shutdown(); srv.server_close()
msg = run("fix grammar", "i think we r ready")
check("no AI: 'fix grammar' still works with the rules", pup.typer.pasted == ["I think we r ready."] and "basic" in msg, (pup.typer.pasted, msg))
msg = run("make it formal", HEY)
check("no AI: 'make it formal' explains it needs Shika AI", not pup.typer.pasted and "Shika AI" in msg, (pup.typer.pasted, msg))
log = open(os.path.join(HOME, ".config/shika/debug.log")).read()
check("every step is written to debug.log", "edit[fix] copy sent=True" in log and "edit[formal]" in log, log[-400:])

# ---- 🩺 Check my setup: which copy key works on this desktop
sc = pup.setup_check
def keytest(**flags):
    reset_world(); sc.active = []; FAKE.selection = "hello shika"
    for k, v in flags.items(): setattr(FAKE, k, v)
    sc.test_keys(); _base.flush()
    return [r for r in sc.active if r["name"].startswith("Keys reach apps")]
r = keytest()
check("setup check: Ctrl+Insert works -> says so", r and r[0]["ok"] and "Ctrl+Insert" in r[0]["detail"], r)
r = keytest(copy_keys={("KEY_LEFTCTRL", "KEY_C")})
check("setup check: only Ctrl+C works -> still passes, says Ctrl+C", r and r[0]["ok"] and "Ctrl+C" in r[0]["detail"], r)
r = keytest(copy_works=False)
check("setup check: nothing copies -> fails with advice", r and r[0]["ok"] is False and r[0]["fix"], r)
check("setup check: your clipboard is put back", FAKE.clip == "old clipboard", FAKE.clip)

for n, ok, d in R:
    if not ok: print("FAIL", n, "\n     ", str(d)[:600])
print(f"\n{sum(1 for x in R if x[1])}/{len(R)} checks passed")
