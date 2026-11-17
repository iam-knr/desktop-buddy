"""15 characters, naming, voice commands, taskbar awareness, and the damaged-file guard."""
import os, re, json, glob, importlib.util
from boot import *
from PyQt6 import _base
R = []
def check(n, c, d=""): R.append((n, bool(c), d))
pup = make_pup()
S = shika

# ---- the cast: 3 pups + 12 other buddies, all different
cast = S.CHARACTERS
check("15 characters", len(cast) == 15, len(cast))
check("3 pups + 12 other buddies", [c["group"] for c in cast].count("pup") == 3 and [c["group"] for c in cast].count("buddy") == 12)
check("ids, names and species are all different", len({c["id"] for c in cast}) == 15 and len({c["name"] for c in cast}) == 15
      and len({c["species"] for c in cast}) == 15)
check("the 12 buddies are 12 different kinds", len({c["species"] for c in cast if c["group"] == "buddy"}) == 12)
looks = {c["id"]: S.look_for(c["id"]) for c in cast}
check("every look builds", all(k.fur is not None and k.ear is not None for k in looks.values()))
sigs = {(k.spec["fur"], k.ears, k.tail, k.face, tuple(sorted(k.extras))) for k in looks.values()}
check("no two characters share the same look", len(sigs) == 15, len(sigs))

# ---- drawing: every character, every pose, no crash
class P(S.PupArt):
    pass
bad = []
for c in cast:
    for st in ("idle", "walk", "sit", "sleep", "bow", "sulk", "sad", "bonk", "alert", "rub", "paw", "hop", "eat", "listen"):
        d = P(); d.char_id, d.state, d.state_t, d.t, d.wag, d.phase = c["id"], st, 20, 15, 1.0, 0.5
        try:
            d.draw_pup(S.QPainter())
        except Exception as ex:
            bad.append((c["id"], st, repr(ex)))
check("draw_pup works for 15 characters x 14 poses", not bad, bad[:3])
check("the live pup draws too", (lambda: (setattr(pup, "state", "idle"), pup.draw_pup(S.QPainter())))() or True)

# ---- names
check("default name", pup.pet_name() == "Shika" and pup.char_id == "shika")
check("clean_name trims and caps", S.clean_name('  "Momo!!"  ') == "Momo" and len(S.clean_name("x" * 60)) == S.MAX_NAME
      and S.clean_name("Bruno please") == "Bruno")
pup.set_pet_name("Momo")
check("rename sticks", pup.pet_name() == "Momo" and json.load(open(S.SETTINGS_FILE))["names"] == {"shika": "Momo"})
pup.set_character("bamboo", say=False)
check("each character keeps its own name", pup.pet_name() == "Bamboo" and pup.name_for("shika") == "Momo")
check("character is saved", json.load(open(S.SETTINGS_FILE))["character"] == "bamboo")
pup.set_pet_name("")
check("empty name resets to the default", pup.pet_name() == "Bamboo" and "bamboo" not in json.load(open(S.SETTINGS_FILE))["names"])
check("unknown id is refused", pup.set_character("dragon") is False and pup.char_id == "bamboo")
pup2 = make_pup()
check("a new pup starts as the saved character, with the saved names", pup2.char_id == "bamboo" and pup2.name_for("shika") == "Momo")

# ---- spoken words
M = S.match_character
check("aliases", M("a husky pup") == "frost" and M("the panda please") == "bamboo" and M("kitten") == "miso"
      and M("dalmatian") == "domino" and M("rabbit") == "biscuit")
check("custom names are understood", M("momo", {"koko": "Momo"}) == "koko" and M("momo") is None)
check("plain words are not characters", M("quiet") is None and M("right back") is None and M("chrome") is None)

def say(phrase):
    reset_world(); pup.bubble_text = ""
    pup.voice_command(phrase); _base.flush()
    return pup.bubble_text
for phrase, want in (("be a panda", "bamboo"), ("switch to Frost", "frost"), ("change to the dalmatian", "domino"),
                     ("become a lion", "leo"), ("turn into a penguin", "pingu"), ("Switch to the husky.", "frost"),
                     ("hey shika be a frog", "ribbit"), ("please change yourself to a koala", "koko")):
    pup.set_character("shika", say=False)
    say(phrase)
    check(f"'{phrase}' -> {want}", pup.char_id == want, pup.char_id)
pup.set_character("shika", say=False)
say("be quiet"); say("switch to chrome"); say("be right back")
check("other 'be/switch' phrases change nothing", pup.char_id == "shika")
say("call yourself Momo")
check("'call yourself Momo'", pup.pet_name() == "Momo", pup.pet_name())
say("your name is Mister Bean")
check("two-word name gets capitals", pup.pet_name() == "Mister Bean", pup.pet_name())
pup.set_pet_name("Momo")
say("Momo, be a cat")
check("his name works as a wake word", pup.char_id == "miso", pup.char_id)
check("the old name 'shika' still works", (say("shika, be a bear"), pup.char_id)[1] == "bruno")
before = pup.char_id
say("surprise me")
check("'surprise me' picks a different one", pup.char_id != before)
opened = []
pup.dashboard.show_app = lambda eid=None: opened.append("app")
say("open characters")
check("'open characters' opens the page", opened and pup.dashboard.pages.currentIndex() == 2, opened)
check("Characters is in the sidebar", any(k == "characters" for _, k in pup.dashboard.nav))
check("the page was built with 15 cards", len(pup.dashboard.chars_page.cards) == 15)
check("old commands still work", (say("open shika"), opened.count("app"))[1] == 2)

# ---- taskbar awareness
check("panel_insets: bottom taskbar", S.panel_insets([{"loc": "bottom", "h": 44, "hide": "none", "scr": 0}], 0) == (0, 0, 0, 44))
check("panel_insets: auto-hide counts for nothing", S.panel_insets([{"loc": "bottom", "h": 44, "hide": "autohide", "scr": 0}], 0) == (0, 0, 0, 0))
check("panel_insets: floating adds its gap", S.panel_insets([{"loc": "bottom", "h": 44, "fl": 1, "scr": 0}], 0)[3] == 52)
check("panel_insets: other screen ignored", S.panel_insets([{"loc": "bottom", "h": 44, "scr": 1}], 0) == (0, 0, 0, 0))
check("panel_insets: all four sides", S.panel_insets([{"loc": "left", "h": 40}, {"loc": "top", "h": 30}, {"loc": "right", "h": 58}, {"loc": "bottom", "h": 44}]) == (40, 30, 58, 44))
check("describe: bottom", "bottom, 44 px" in S.describe_panels([{"loc": "bottom", "h": 44, "scr": 0}], 0))
check("describe: hidden", "hides itself" in S.describe_panels([{"loc": "bottom", "h": 44, "hide": "autohide", "scr": 0}], 0))
check("describe: none", "No taskbar" in S.describe_panels([], 0))

reset_world()
HANDLERS.append(lambda cmd, k: (0, "('[{\"loc\":\"bottom\",\"h\":44,\"hide\":\"none\",\"fl\":0,\"scr\":0}]\\n',)\n")
                if isinstance(cmd, list) and "org.kde.plasmashell" in cmd else None)
got = S.read_panels()
check("read_panels parses Plasma's answer", got == [{"loc": "bottom", "h": 44, "hide": "none", "fl": 0, "scr": 0}], got)
HANDLERS.clear(); HANDLERS.append(lambda cmd, k: (1, "", "no such service") if isinstance(cmd, list) and "org.kde.plasmashell" in cmd else None)
check("read_panels says None when Plasma can't be asked", S.read_panels() is None)
HANDLERS.clear(); HANDLERS.append(lambda cmd, k: (0, "('garbage',)\n") if isinstance(cmd, list) and "org.kde.plasmashell" in cmd else None)
check("read_panels survives garbage", S.read_panels() is None)
reset_world()

class Rc:                                           # a real rectangle, like QRect
    def __init__(s, x, y, w, h): s._x, s._y, s._w, s._h = x, y, w, h
    def x(s): return s._x
    def y(s): return s._y
    def width(s): return s._w
    def height(s): return s._h
    def left(s): return s._x
    def top(s): return s._y
    def right(s): return s._x + s._w - 1
    def bottom(s): return s._y + s._h - 1
class Scr:
    def __init__(s, avail=None): s.g, s.a = Rc(0, 0, 1920, 1080), avail or Rc(0, 0, 1920, 1080)
    def geometry(s): return s.g
    def availableGeometry(s): return s.a
class Gui:
    scr = Scr()
    @staticmethod
    def screenAt(p): return Gui.scr
    @staticmethod
    def primaryScreen(): return Gui.scr
    @staticmethod
    def screens(): return [Gui.scr]
S.QGuiApplication, S.QRect = Gui, Rc
pup.settings["taskbar_aware"] = True
pup.panels, pup.panels_ok = [], False
check("no panel info, nothing reserved by Qt: old right-side gap", pup.area().right() == 1919 - S.TASKBAR_RIGHT and pup.area().bottom() == 1079)
pup.panels, pup.panels_ok = [{"loc": "bottom", "h": 44, "hide": "none", "scr": 0}], True
check("bottom taskbar: floor is its top edge", pup.area().bottom() == 1035 and pup.area().right() == 1919 and pup.ground() == 1035, (pup.area().bottom(), pup.ground()))
pup.panels = [{"loc": "bottom", "h": 44, "hide": "autohide", "scr": 0}]
check("hidden taskbar: floor is the screen edge", pup.area().bottom() == 1079)
pup.panels = [{"loc": "right", "h": 58, "hide": "none", "scr": 0}]
check("side taskbar: stays clear of it", pup.area().right() == 1861 and pup.area().bottom() == 1079)
pup.panels = [{"loc": "bottom", "h": 44, "scr": 0}, {"loc": "top", "h": 30, "scr": 0}]
check("top and bottom panels together", pup.area().top() == 30 and pup.area().bottom() == 1035)
Gui.scr = Scr(Rc(0, 0, 1920, 1000))                 # Qt already reserves 80 px, bigger than the 44 px panel
pup.panels = [{"loc": "bottom", "h": 44, "scr": 0}]
check("Qt's own number wins when it is larger (no double counting)", pup.area().bottom() == 999, pup.area().bottom())
Gui.scr = Scr()
pup.settings["taskbar_aware"] = False
check("switch off: panel info ignored", pup.area().bottom() == 1079 and pup.area().right() == 1919 - S.TASKBAR_RIGHT)
pup.settings["taskbar_aware"] = True

# standing on a taskbar that appears, resizes, and goes away
pup.panels, pup.panels_ok, pup.panel_sig = [], True, None
pup.hop, pup.dragging, pup.state = None, False, "idle"
pup.in_corner = False
pup._floor_seen = pup.area().bottom()
pup.py = pup.base_y = pup._floor_seen
pup.set_panels([{"loc": "bottom", "h": 44, "hide": "none", "fl": 0, "scr": 0}])
check("taskbar appears: he steps up onto it", pup.py == 1035 and pup.base_y == 1035, pup.py)
pup.set_panels([{"loc": "bottom", "h": 70, "hide": "none", "fl": 0, "scr": 0}])
check("taskbar grows: he rides up with it", pup.py == 1009, pup.py)
pup.set_panels([{"loc": "bottom", "h": 70, "hide": "autohide", "fl": 0, "scr": 0}])
check("taskbar hides: he drops to the screen edge", pup.py == 1079, pup.py)
pup.in_corner = True
pup.set_panels([{"loc": "bottom", "h": 44, "hide": "none", "fl": 0, "scr": 0}])
check("corner spot follows the taskbar", pup.py == 1035 and pup.corner_y() == 1035 and abs(pup.px - pup.corner_x()) < 1)
pup.py, pup.hop = 600, {"x": 1}
before = pup._floor_seen
pup.set_panels([{"loc": "bottom", "h": 20, "hide": "none", "fl": 0, "scr": 0}])
check("mid-jump: he is left alone", pup.py == 600 and pup._floor_seen == before)
pup.hop = None
pup.set_panels(None)
check("Plasma not answering keeps the last known panels", pup.panels_ok and pup.panels[0]["h"] == 20)
check("status text", "Taskbar found at the bottom, 20 px" in pup.panel_status(), pup.panel_status())
pup.set_taskbar_aware(False)
check("toggle off is saved", json.load(open(S.SETTINGS_FILE))["taskbar_aware"] is False and "off" in pup.panel_status())
pup.set_taskbar_aware(True)
check("toggle on is saved", json.load(open(S.SETTINGS_FILE))["taskbar_aware"] is True)
diag = {d["name"]: d for d in pup.run_diagnostics()}
check("setup check has a taskbar line", any("Taskbar" in n for n in diag), list(diag)[:4])

# ---- damaged files are set aside, never overwritten; hourly backup of the last good copy
os.makedirs(S.SUMMIT, exist_ok=True)
open(S.LIBRARY_FILE, "w").write('[{"id": "1", "kind": "note", "title": "precious", "text": "my notes", ')   # cut off mid-write
pup.library.entries = []
pup.library.add("note", "hello after the crash")
aside = glob.glob(S.LIBRARY_FILE + ".corrupt-*")
check("damaged library.json is kept, not overwritten", len(aside) == 1 and "precious" in open(aside[0]).read(), aside)
check("the new note was still saved", any(e["text"] == "hello after the crash" for e in json.load(open(S.LIBRARY_FILE))))
pup.library.add("note", "second")
check("a backup of the good file now exists", os.path.exists(S.LIBRARY_FILE + ".bak") and isinstance(json.load(open(S.LIBRARY_FILE + ".bak")), list))
bak_before = open(S.LIBRARY_FILE + ".bak").read()
pup.library.add("note", "third")
check("backup is not rewritten more than once an hour", open(S.LIBRARY_FILE + ".bak").read() == bak_before)
open(S.LIBRARY_FILE, "w").write("not json at all")
S.rolling_backup(S.LIBRARY_FILE, every=0)
check("a damaged file is never copied over the good backup", open(S.LIBRARY_FILE + ".bak").read() == bak_before)
open(S.SETTINGS_FILE, "w").write("{ broken")
check("damaged settings.json -> defaults + file kept", S.load_json(S.SETTINGS_FILE, {"d": 1}) == {"d": 1}
      and glob.glob(S.SETTINGS_FILE + ".corrupt-*"))
open(S.SETTINGS_FILE, "w").write("")
check("an empty file is not 'damaged'", S.load_json(S.SETTINGS_FILE, 5) == 5 and len(glob.glob(S.SETTINGS_FILE + ".corrupt-*")) == 1)
check("a missing file is just the default", S.load_json("/nonexistent/x.json", 7) == 7)

spec = importlib.util.spec_from_file_location("summitctl", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "summitctl.py"))
ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
p = os.path.join(S.SUMMIT, "notes.json")
open(p, "w").write("{oops")
check("summitctl also sets a damaged file aside", ctl.load(p, {}) == {} and glob.glob(p + ".corrupt-*") and not os.path.exists(p))

# ---- install / uninstall scripts
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
un = open(os.path.join(base, "uninstall.sh")).read()
ins = open(os.path.join(base, "install.sh")).read()
check("uninstall removes every widget install.sh adds", all(f"in.adsmentor.summit.$w" in un for _ in [0]) and
      all(w in re.search(r"for w in ([^;]*); do", un).group(1).split() for w in re.search(r"for w in (tasks[^;]*); do", ins).group(1).split()))
check("uninstall removes autostart, launcher entries, program files, rules",
      all(x in un for x in ("autostart/shika.desktop", "shika-pup.desktop", "shika-command.desktop", ".local/share/shika",
                            "80-shika-uinput.rules", "pkill")))
check("uninstall keeps data unless asked", "--purge-data" in un and "DELETE" in un)
import subprocess as sp
check("uninstall.sh has valid bash syntax", sp.run(["bash", "-n", os.path.join(base, "uninstall.sh")]).returncode == 0)

for n, ok, d in R:
    if not ok: print("FAIL", n, "\n     ", str(d)[:500])
print(f"\n{sum(1 for x in R if x[1])}/{len(R)} checks passed")
