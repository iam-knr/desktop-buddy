#!/usr/bin/env python3
"""Shika: a tiny desktop pup for KDE Plasma.

  tap             pet (4 slow taps = zoomies)
  double-tap      trick
  triple-tap      chappal! (he cries: "tu bache ko maarta he")
  hold            shake hands
  hover 5s        belly rubs, hearts, melts into a puddle of love
  scroll on him   chin scratches
  middle-click    treat
  right-click     reminders panel, treats, climb, "Turn Shika off"
  drag            pick up; drop him in the bottom-right corner while he's
                  out playing and he sulks ("bache ko daat tha he tu")
  shake on drag   dizzy

Voice (v3): hold Right Ctrl to dictate anywhere, hold Right Alt to give Shika a command.
The Shika app (launcher: "Shika") keeps every dictation and scratchpad note.
Tasks and reminders are shared with the Summit desktop widget; anything with a time barks.

While you work, Shika naps in the bottom-right corner. If he's out roaming when
you start typing, he says "mujhe utha lena kaam ke baad" and curls up right there.
When you step away (or tap him) he plays: zoomies, ball, tail chasing, play
bows, chasing your cursor, and climbing the left edge with ladders + platforms.
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta

# "linux", "mac" or "win". SHIKA_OS can force one (the tests do).
OS = os.environ.get("SHIKA_OS") or {"darwin": "mac", "win32": "win"}.get(sys.platform, "linux")
IS_LINUX, IS_MAC, IS_WIN = OS == "linux", OS == "mac", OS == "win"

if IS_LINUX:
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PyQt6.QtCore import (Qt, QTimer, QPointF, QRectF, QPoint, QRect, QDateTime, QTime, QEvent,
                          QObject, QProcess, QSize, pyqtSignal)
from PyQt6.QtGui import (QPainter, QColor, QPen, QPainterPath, QFont, QRegion, QIcon,
                         QFontMetrics, QGuiApplication, QCursor)
from PyQt6.QtWidgets import (QApplication, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QDateTimeEdit, QPushButton, QCheckBox,
                             QPlainTextEdit, QListWidget, QListWidgetItem,
                             QComboBox, QStackedWidget, QTextBrowser, QGridLayout, QScrollArea)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

NAME = "Shika"
VERSION = "3.18"
SIZE = 1.0                 # 0.75 small, 1.0 medium, 1.35 large
TASKBAR_RIGHT = 58         # px kept clear on the right for your side taskbar (0 = none)
FREE_AFTER = 60            # seconds without keyboard/mouse use = you're on a break
PLAY_TIME = 90             # seconds he stays playful after you tap him
RUB_AFTER = 5              # seconds of hovering before belly-rub mode
WORK_NAP_IN_PLACE = True   # True: naps where he is when you start working; False: goes to corner
CHATTY = True              # random little Hinglish lines while playing
FPS = 30

LINE_BONK = "tu bache ko maarta he 😭"
LINE_SCOLD = "bache ko daat tha he tu 😤"
LINE_WORK = "mujhe utha lena kaam ke baad 🥺"
RUB_LINES = ["hehe... ❤️", "aur karo na 🥺", "haan wahi... wahi 🥰", "pyaar hai tumse 💕",
             "best hooman ever 💖", "mmm... 😌💗", "kabhi mat rukna ❤️❤️"]
FORGIVE_LINES = ["theek hai... maaf kiya 🥺❤️", "pakka sorry? okay 🐶💕", "hmph... chalo theek hai ❤️"]
CHATTER = {
    "morning": ["good morning! ☀️", "chai pi li? ☕", "aaj kya plan hai? 🐾"],
    "day": ["khelo na mere saath! 🎾", "bhook lagi hai... treat? 🦴", "main cute hoon na? 🥺",
            "pani pi lo, hydrate karo 💧", "thoda stretch kar lo 🙆"],
    "evening": ["walk pe chalein? 🐕", "aaj ka kaam khatam? 🎉", "treat time? 🦴"],
    "night": ["so jao ab... 😴", "itni raat ko kaam? 🥱", "kal karna, abhi so jao 🌙"],
}
LADDER_H = 120             # height of one ladder section (px at SIZE 1.0)
WOOD = QColor(176, 116, 64)
WOOD_DARK = QColor(120, 74, 36)
PINK = QColor(255, 92, 138)
TEAR = QColor(120, 190, 255)
SLIPPER = QColor(40, 120, 220)

FUR = QColor(232, 138, 60)
FUR_SHADE = QColor(204, 112, 44)
EAR = QColor(122, 64, 30)
CREAM = QColor(255, 237, 210)
LINE = QColor(60, 33, 18)
EYE = QColor(38, 20, 10)
RED = QColor(225, 29, 46)
GOLD = QColor(255, 196, 64)
BELT_RED = QColor(206, 30, 44)         # the chest belt that carries the pet's name
BELT_TEXT = QColor(255, 224, 40)
INK = QColor(12, 12, 12)
WHITE = QColor(250, 250, 250)

if IS_WIN:
    CONF = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Shika")
    SUMMIT_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Summit")
elif IS_MAC:
    CONF = os.path.expanduser("~/Library/Application Support/Shika")
    SUMMIT_DIR = os.path.expanduser("~/Library/Application Support/Summit")
else:
    CONF = os.path.expanduser("~/.config/shika")
    SUMMIT_DIR = os.path.expanduser("~/.local/share/summit")
OLD_CONF = os.path.expanduser("~/.config/mochi")
SETTINGS_FILE = os.path.join(CONF, "settings.json")
REMINDERS_FILE = os.path.join(CONF, "reminders.json")
SOCKET = "shika-pup"

if IS_LINUX:
    FLAGS = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.Tool | Qt.WindowType.X11BypassWindowManagerHint)
elif IS_MAC:        # a Tool window would vanish whenever another app is in front
    FLAGS = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.NoDropShadowWindowHint)
else:
    FLAGS = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint)

FUN_EMOTES = ["dots", "q", "note", "smile"]


# --------------------------------------------------------------------------- characters
# Every character is plain data. One painter (PupArt) draws all of them on the same body.
#   ears:   floppy | floppy_s | point | round | long | none
#   tail:   dog | curl | fox | cat | puff | stub | ring | pig | tuft | none
#   face:   dog | small | cheeks | white | snout | none          (muzzle or face patch)
#   extras: blaze browdots whiskers stripes bodystripes spots patches mask beak bulge widemouth mane bignose teeth
# Colours are (r, g, b). Optional keys: inner mark nose eye hl leg paw tailtip snout ear_r tailw eyes
def _spec(cid, group, species, name, fur, shade, ear, cream, collar, **kw):
    d = dict(id=cid, group=group, species=species, name=name, fur=fur, shade=shade, ear=ear, cream=cream,
             collar=collar)
    d.update(kw)
    return d


CHARACTERS = [
    # ---- 3 pups
    _spec("shika", "pup", "orange pup", "Shika", (232, 138, 60), (204, 112, 44), (122, 64, 30), (255, 237, 210),
          (225, 29, 46), ears="floppy", tail="dog", face="dog", extras=("blaze",)),
    _spec("frost", "pup", "husky pup", "Frost", (122, 134, 152), (98, 110, 130), (84, 94, 112), (246, 248, 252),
          (40, 120, 220), inner=(255, 215, 220), nose=(30, 30, 36), eye=(60, 120, 205),
          ears="point", tail="curl", face="dog", extras=("browdots",)),
    _spec("domino", "pup", "dalmatian pup", "Domino", (250, 248, 244), (228, 224, 220), (35, 35, 40), (255, 255, 255),
          (60, 170, 110), mark=(35, 35, 40), nose=(30, 30, 30), tailtip=(35, 35, 40),
          ears="floppy", tail="dog", face="dog", extras=("spots",)),
    # ---- 12 other pet companions
    _spec("miso", "buddy", "cat", "Miso", (150, 152, 165), (124, 126, 140), (150, 152, 165), (235, 235, 242),
          (230, 80, 120), inner=(255, 170, 185), mark=(100, 102, 116), nose=(255, 150, 165),
          ears="point", tail="cat", face="small", extras=("whiskers", "stripes")),
    _spec("rusty", "buddy", "fox", "Rusty", (240, 128, 40), (212, 102, 28), (62, 38, 28), (255, 244, 230),
          (70, 150, 190), inner=(255, 236, 215), mark=(62, 38, 28), nose=(40, 30, 30), leg=(84, 52, 36),
          paw=(84, 52, 36), tailtip=(255, 250, 240), ears="point", tail="fox", face="cheeks"),
    _spec("bamboo", "buddy", "panda", "Bamboo", (248, 248, 248), (225, 225, 228), (30, 30, 34), (255, 255, 255),
          (90, 190, 100), inner=(70, 70, 78), mark=(30, 30, 34), nose=(30, 30, 34), eye=(250, 250, 250),
          hl=(25, 25, 28), leg=(30, 30, 34), paw=(60, 60, 66), ears="round", ear_r=6.8, tail="stub",
          face="small", extras=("patches",)),
    _spec("biscuit", "buddy", "bunny", "Biscuit", (250, 244, 244), (232, 222, 228), (250, 244, 244), (255, 232, 238),
          (255, 150, 60), inner=(255, 170, 190), mark=(210, 190, 200), nose=(255, 150, 170),
          ears="long", tail="puff", face="small", extras=("whiskers", "teeth")),
    _spec("bruno", "buddy", "bear", "Bruno", (140, 92, 58), (112, 70, 42), (112, 70, 42), (214, 178, 132),
          (200, 50, 60), inner=(200, 160, 120), mark=(80, 50, 30), nose=(35, 25, 20),
          ears="round", ear_r=6.4, tail="stub", face="dog"),
    _spec("raja", "buddy", "tiger", "Raja", (240, 150, 45), (212, 122, 28), (240, 150, 45), (255, 242, 220),
          (40, 150, 200), inner=(255, 240, 215), mark=(45, 28, 18), nose=(210, 110, 110),
          ears="round", ear_r=6.2, tail="ring", tailw=0.75, tailtip=(45, 28, 18), face="small",
          extras=("stripes", "bodystripes", "whiskers")),
    _spec("bandit", "buddy", "raccoon", "Bandit", (146, 148, 158), (120, 122, 132), (84, 86, 96), (226, 228, 234),
          (230, 170, 40), inner=(226, 228, 234), mark=(46, 48, 58), nose=(30, 30, 34), eye=(250, 250, 250),
          hl=(25, 25, 28), leg=(84, 86, 96), paw=(84, 86, 96), tailtip=(46, 48, 58),
          ears="round", ear_r=6.0, tail="ring", face="small", extras=("mask",)),
    _spec("chops", "buddy", "pig", "Chops", (255, 174, 194), (240, 146, 170), (244, 140, 166), (255, 206, 218),
          (120, 90, 200), inner=(255, 200, 212), mark=(240, 120, 150), nose=(214, 100, 130), snout=(255, 150, 175),
          ears="floppy_s", tail="pig", face="snout"),
    _spec("ribbit", "buddy", "frog", "Ribbit", (98, 196, 92), (70, 164, 70), (98, 196, 92), (226, 240, 170),
          (255, 110, 60), mark=(60, 140, 60), nose=(50, 120, 50), eyes=(9.5, -10.0),
          ears="none", tail="none", face="small", extras=("bulge", "widemouth")),
    _spec("pingu", "buddy", "penguin", "Pingu", (34, 44, 76), (24, 32, 58), (34, 44, 76), (250, 250, 252),
          (230, 60, 70), mark=(34, 44, 76), nose=(255, 150, 40), paw=(255, 150, 40),
          ears="none", tail="stub", face="white", extras=("beak",)),
    _spec("leo", "buddy", "lion", "Leo", (232, 170, 70), (204, 140, 45), (160, 100, 40), (255, 232, 190),
          (200, 50, 60), inner=(255, 225, 180), mark=(140, 84, 30), nose=(80, 45, 30), tailtip=(140, 84, 30),
          ears="round", ear_r=5.6, tail="tuft", face="dog", extras=("mane",)),
    _spec("koko", "buddy", "koala", "Koko", (150, 156, 170), (126, 132, 146), (150, 156, 170), (232, 234, 240),
          (90, 170, 90), inner=(240, 240, 245), mark=(120, 126, 140), nose=(40, 40, 48),
          ears="round", ear_r=9.2, tail="none", face="small", extras=("bignose",)),
]
CHAR_BY_ID = {c["id"]: c for c in CHARACTERS}
MAX_NAME = 20
# spoken words -> character id ("be a panda", "switch to the husky")
CHAR_ALIASES = {
    "pup": "shika", "puppy": "shika", "dog": "shika", "orange pup": "shika", "orange dog": "shika",
    "husky": "frost", "husky pup": "frost", "wolf": "frost",
    "dalmatian": "domino", "dalmation": "domino", "spotty dog": "domino", "spotted dog": "domino",
    "cat": "miso", "kitten": "miso", "kitty": "miso", "fox": "rusty", "panda": "bamboo",
    "bunny": "biscuit", "rabbit": "biscuit", "bear": "bruno", "teddy": "bruno", "tiger": "raja",
    "raccoon": "bandit", "pig": "chops", "piggy": "chops", "frog": "ribbit", "penguin": "pingu",
    "lion": "leo", "koala": "koko",
}


def _col(t, default=None):
    t = t or default
    return QColor(*t) if t else None


class Look:
    """One character's colours and traits, ready for the painter."""
    def __init__(self, spec):
        g = spec.get
        self.id, self.spec = spec["id"], spec
        self.fur, self.shade = _col(spec["fur"]), _col(spec["shade"])
        self.ear, self.cream, self.collar = _col(spec["ear"]), _col(spec["cream"]), _col(spec["collar"])
        self.inner = _col(g("inner"), spec["cream"])
        self.mark = _col(g("mark"), (60, 33, 18))
        self.nose = _col(g("nose"), (38, 20, 10))
        self.eye = _col(g("eye"), (38, 20, 10))
        self.hl = _col(g("hl"), (250, 250, 250))
        ec = g("eye")                                        # the darker ring seen when he looks at you lovingly
        self.iris = _col(tuple(int(v * 0.55) for v in ec) if ec and sum(ec) / 3 < 200 else ((70, 70, 76) if ec else (110, 60, 30)))
        leg = g("leg")
        self.leg = _col(leg or spec["fur"])
        self.leg_shade = _col(tuple(int(v * 0.84) for v in leg) if leg else spec["shade"])
        self.paw = _col(g("paw"), spec["cream"])
        self.tailtip = _col(g("tailtip"), spec["cream"])
        self.snout = _col(g("snout"), spec["cream"])
        self.ears, self.tail, self.face = g("ears", "floppy"), g("tail", "dog"), g("face", "dog")
        self.extras = frozenset(g("extras", ()))
        self.ear_r, self.tailw = g("ear_r", 7.0), g("tailw", 1.0)
        self.eye_dx, self.eye_dy = g("eyes", (7.5, -1.0))
        self.mdy = 5 if self.face == "snout" else 4 if "bignose" in self.extras else 0   # mouth sits lower
        self.mw = 1.7 if "widemouth" in self.extras else 1.0                              # mouth is wider


_LOOKS = {}


def look_for(cid):
    k = _LOOKS.get(cid)
    if k is None:
        k = _LOOKS[cid] = Look(CHAR_BY_ID.get(cid) or CHAR_BY_ID["shika"])
    return k


def clean_name(text):
    """A name someone typed or said: one line, no stray punctuation, at most 20 letters."""
    t = re.sub(r"\s+", " ", str(text or "")).strip(" \t.,!?;:\"'“”")
    t = re.sub(r"(?i)\s+(?:please|ok|okay|thanks|thank you)$", "", t).strip(" .,!?")
    return t[:MAX_NAME].strip()


def match_character(text, names=None):
    """'a panda', 'the husky', 'frost' -> character id, or None. `names` = {id: custom name}."""
    t = " " + re.sub(r"[^a-z ]", " ", str(text).lower()) + " "
    t = re.sub(r"\s+", " ", t)
    pairs = [(n.lower(), cid) for cid, n in (names or {}).items() if n and re.sub(r"[^a-z]", "", n.lower())]
    pairs += [(c["name"].lower(), c["id"]) for c in CHARACTERS] + [(c["species"], c["id"]) for c in CHARACTERS]
    pairs += list(CHAR_ALIASES.items())
    for word, cid in sorted(pairs, key=lambda x: -len(x[0])):
        w = re.sub(r"[^a-z ]", "", word)
        if w and re.search(rf" {re.escape(w)} ", t):
            return cid
    return None


def migrate_old_config():
    if not os.path.isdir(CONF) and os.path.isdir(OLD_CONF):
        shutil.copytree(OLD_CONF, CONF)


def quarantine(path):
    """A data file that can't be read is renamed, never overwritten: your notes may still be in it."""
    dest = f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        os.replace(path, dest)
    except OSError:
        return None
    dlog(f"unreadable file set aside: {dest}")
    if shutil.which("notify-send"):
        subprocess.Popen(["notify-send", "-a", NAME, "-i", "dialog-warning", f"{NAME}: a data file was damaged",
                          f"It was kept as {os.path.basename(dest)} next to the original. Nothing was deleted."],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def rolling_backup(path, every=3600):
    """Keep one copy of the last good file (path.bak), refreshed at most once an hour."""
    bak = path + ".bak"
    try:
        if os.path.getsize(path) < 2 or (os.path.exists(bak) and time.time() - os.path.getmtime(bak) < every):
            return
        with open(path) as f:
            json.load(f)                                     # never back up a damaged file over a good copy
        shutil.copyfile(path, bak)
    except (OSError, ValueError):
        pass


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except ValueError:                                       # not valid JSON (or not valid text)
        try:
            if os.path.getsize(path) > 0:
                quarantine(path)
        except OSError:
            pass
        return default
    except Exception:
        return default


def save_json(path, data):
    os.makedirs(CONF, exist_ok=True)
    rolling_backup(path)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def pen(color, width):
    p = QPen(color, width)
    p.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return p


def nice_time(ts):
    d = datetime.fromtimestamp(ts)
    now = datetime.now()
    clock = d.strftime("%I:%M %p").lstrip("0")
    if d.date() == now.date():
        return f"Today {clock}"
    if d.date() == (now + timedelta(days=1)).date():
        return f"Tomorrow {clock}"
    return d.strftime("%a %d %b, ") + clock


def play_sound():
    if not IS_LINUX:
        QApplication.beep()
        return
    files = ["/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
             "/usr/share/sounds/ocean/stereo/alarm-clock-elapsed.oga",
             "/usr/share/sounds/freedesktop/stereo/complete.oga",
             "/usr/share/sounds/ocean/stereo/completion-success.oga"]
    snd = next((f for f in files if os.path.exists(f)), None)
    player = next((p for p in ("pw-play", "paplay") if shutil.which(p)), None)
    if snd and player:
        subprocess.Popen([player, snd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        QApplication.beep()


def play_bark():
    if not IS_LINUX:
        snd = next((f for f in BARK_FILES if os.path.exists(f)), None)
        if not (snd and play_file(snd)):
            QApplication.beep()
        return
    snd = next((f for f in BARK_FILES if os.path.exists(f)), None)
    player = next((p for p in ("pw-play", "paplay", "aplay") if shutil.which(p)), None)
    if snd and player:
        subprocess.Popen([player, snd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        play_sound()


# --------------------------------------------------------------------------- ball
class Ball(QWidget):
    def __init__(self):
        super().__init__(None, FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(26, 26)
        self.angle = 0.0

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(13, 13)
        p.rotate(self.angle)
        p.setPen(pen(LINE, 2.2))
        p.setBrush(RED)
        p.drawEllipse(QPointF(0, 0), 10, 10)
        p.setPen(pen(WHITE, 2.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(-14, -6, 20, 20), 20 * 16, 70 * 16)
        p.drawArc(QRectF(-6, -14, 20, 20), 200 * 16, 70 * 16)


# --------------------------------------------------------------------------- props
class Prop(QWidget):
    """Little overlay things Shika uses: a ladder, a wall platform, a treat bone."""

    def __init__(self, kind, s):
        super().__init__(None, FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.kind, self.s = kind, s
        if kind == "bone":
            self.resize(int(30 * s), int(18 * s))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s, w, h = self.s, self.width(), self.height()
        if self.kind == "ladder":
            p.setPen(pen(WOOD_DARK, 2 * s))
            p.setBrush(WOOD)
            rail = 5 * s
            p.drawRoundedRect(QRectF(1, 1, rail, h - 2), 2, 2)
            p.drawRoundedRect(QRectF(w - rail - 1, 1, rail, h - 2), 2, 2)
            p.setPen(pen(WOOD_DARK, 3.2 * s))
            y = h - 10 * s
            while y > 4 * s:
                p.drawLine(QPointF(rail + 1, y), QPointF(w - rail - 1, y))
                y -= 15 * s
        elif self.kind == "platform":
            plank = 10 * s
            p.setPen(pen(WOOD_DARK, 2 * s))
            p.setBrush(WOOD_DARK)
            br = QPainterPath(QPointF(1, plank))
            br.lineTo(26 * s, plank)
            br.lineTo(1, h - 1)
            br.closeSubpath()
            p.drawPath(br)
            p.setBrush(WOOD)
            p.drawRoundedRect(QRectF(1, 1, w - 2, plank), 3 * s, 3 * s)
            p.setPen(pen(QColor(150, 98, 52), 1.2 * s))
            p.drawLine(QPointF(8 * s, plank * 0.5), QPointF(w - 10 * s, plank * 0.5))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(70, 70, 70))
            for nx in (6 * s, w - 7 * s):
                p.drawEllipse(QPointF(nx, plank * 0.5), 1.6 * s, 1.6 * s)
        elif self.kind == "bone":
            p.translate(w / 2, h / 2)
            p.rotate(-12)
            p.setPen(pen(LINE, 1.8 * s))
            p.setBrush(CREAM)
            path = QPainterPath()
            path.addRoundedRect(QRectF(-9 * s, -3 * s, 18 * s, 6 * s), 2 * s, 2 * s)
            for bx in (-10 * s, 10 * s):
                for by in (-3 * s, 3 * s):
                    c = QPainterPath()
                    c.addEllipse(QPointF(bx, by), 3.6 * s, 3.6 * s)
                    path = path.united(c)
            p.drawPath(path)


# --------------------------------------------------------------------------- panel
PANEL_CSS = """
#card { background:#0b0b0b; border:2px solid #e11d2e; border-radius:14px; }
QLabel { color:#f0f0f0; }
QLabel#title { font-size:15px; font-weight:800; }
QLabel#muted { color:#8f8f8f; font-size:11px; }
QLabel#warn { color:#ff6b6b; font-size:11px; font-weight:700; }
QLabel#item { color:#e8e8e8; }
QLineEdit, QDateTimeEdit { background:#161616; color:#ffffff; border:1px solid #333;
    border-radius:8px; padding:7px 9px; selection-background-color:#e11d2e; }
QLineEdit:focus, QDateTimeEdit:focus { border:1px solid #e11d2e; }
QPushButton { background:#1c1c1c; color:#f0f0f0; border:1px solid #2e2e2e;
    border-radius:8px; padding:6px 8px; font-weight:600; }
QPushButton:hover { border-color:#e11d2e; }
QPushButton#primary { background:#e11d2e; border:none; color:#ffffff; padding:9px; font-weight:800; }
QPushButton#primary:hover { background:#f2303f; }
QPushButton#ghost { background:transparent; border:none; color:#9a9a9a; padding:4px; }
QPushButton#ghost:hover { color:#e11d2e; }
QPushButton#x { background:transparent; border:none; color:#777777; padding:0 4px; font-size:14px; }
QPushButton#x:hover { color:#e11d2e; }
QCheckBox { color:#d6d6d6; spacing:8px; }
QCheckBox::indicator { width:16px; height:16px; border-radius:4px; border:1px solid #444; background:#161616; }
QCheckBox::indicator:checked { background:#e11d2e; border-color:#e11d2e; }
QCalendarWidget QWidget { background:#111111; color:#eeeeee; alternate-background-color:#161616; }
QCalendarWidget QAbstractItemView { selection-background-color:#e11d2e; selection-color:#ffffff; }
QCalendarWidget QToolButton { color:#eeeeee; background:transparent; font-weight:700; }
"""


class ReminderPanel(QWidget):
    def __init__(self, pup):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.pup = pup
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(PANEL_CSS)
        self.setFixedWidth(340)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 10)
        lay.setSpacing(9)

        top = QHBoxLayout()
        title = QLabel(f"🐾  Remind me…   <span style='color:#666;font-size:10px'>v{VERSION}</span>")
        title.setObjectName("title")
        close = QPushButton("✕")
        close.setObjectName("x")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.hide)
        top.addWidget(title, 1)
        top.addWidget(close)
        lay.addLayout(top)

        self.text = QLineEdit()
        self.text.setPlaceholderText("What should I remind you about?")
        self.text.returnPressed.connect(self.save)
        lay.addWidget(self.text)

        dl = QLabel("Deadline")
        dl.setObjectName("muted")
        lay.addWidget(dl)
        self.when = QDateTimeEdit()
        self.when.setCalendarPopup(True)
        self.when.setDisplayFormat("ddd d MMM yyyy  ·  h:mm AP")
        lay.addWidget(self.when)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        for label, fn in (("+15 min", lambda: self.add_min(15)), ("+1 hr", lambda: self.add_min(60)),
                          ("8 PM", self.tonight), ("Tmrw 9 AM", self.tomorrow)):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            chips.addWidget(b)
        lay.addLayout(chips)

        self.sound = QCheckBox("🔊  Bark out loud when it's due")
        self.sound.toggled.connect(self.pup.set_sound)
        lay.addWidget(self.sound)

        self.msg = QLabel("")
        self.msg.setObjectName("warn")
        self.msg.hide()
        lay.addWidget(self.msg)

        save = QPushButton("Set reminder")
        save.setObjectName("primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.save)
        lay.addWidget(save)

        fun = QHBoxLayout()
        fun.setSpacing(6)
        for label, fn in (("🦴 Treat", self.pup.give_treat), ("🪜 Climb", self.pup.order_climb),
                          ("⚽ Ball", self.pup.order_ball), ("😴 Sleep", self.pup.order_sleep),
                          ("🏠 App", lambda: self.pup.open_dashboard())):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, f=fn: (self.hide(), f()))
            fun.addWidget(b)
        lay.addLayout(fun)
        wrow = QHBoxLayout()
        wrow.setSpacing(6)
        for label, fn in (("✅ Tasks", lambda: self.pup.widgets.toggle("tasks")), ("🗒 Note", self.pup.widgets.new_note),
                          ("⏱ Focus", lambda: self.pup.widgets.toggle("focus")), ("🕒 Clock", lambda: self.pup.widgets.toggle("clock"))):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, f=fn: (self.hide(), f()))
            wrow.addWidget(b)
        lay.addLayout(wrow)
        more = QPushButton("🐾  Characters and names")
        more.setCursor(Qt.CursorShape.PointingHandCursor)
        more.clicked.connect(lambda: (self.hide(), self.pup.open_characters()))
        lay.addWidget(more)

        up = QLabel("Upcoming")
        up.setObjectName("muted")
        lay.addWidget(up)
        self.list_holder = QVBoxLayout()
        self.list_holder.setSpacing(4)
        lay.addLayout(self.list_holder)
        self.list_widget = None

        off = QPushButton(f"💤  Turn {NAME} off")
        off.setObjectName("ghost")
        off.setCursor(Qt.CursorShape.PointingHandCursor)
        off.clicked.connect(self.turn_off)
        lay.addWidget(off, alignment=Qt.AlignmentFlag.AlignHCenter)
        hint = QLabel("tap · 2× trick · 3× chappal · hold = paw · hover 5s = rubs\n"
                      "scroll = scratch · middle-click = treat · drag to corner = sulk\n"
                      f"Wake {NAME} anytime: App Launcher → “{NAME} Pup”.\n"
                      "Reminders still pop up while off.\n"
                      "🎤 hold Right Ctrl = dictate · hold Right Alt = command")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)

    def changeEvent(self, e):
        if e.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            QTimer.singleShot(200, self.maybe_close)
        super().changeEvent(e)

    def maybe_close(self):
        if (self.isVisible() and not self.isActiveWindow()
                and QApplication.activePopupWidget() is None):
            self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def focus_text(self):
        self.raise_()
        self.activateWindow()
        self.text.setFocus()

    def add_min(self, m):
        self.when.setDateTime(QDateTime.currentDateTime().addSecs(m * 60))

    def tonight(self):
        now = QDateTime.currentDateTime()
        t = QDateTime(now.date(), QTime(20, 0))
        self.when.setDateTime(t if t > now else t.addDays(1))

    def tomorrow(self):
        self.when.setDateTime(QDateTime(QDateTime.currentDateTime().date().addDays(1), QTime(9, 0)))

    def warn(self, text):
        self.msg.setText(text)
        self.msg.show()
        self.adjustSize()

    def save(self):
        text = self.text.text().strip()
        if not text:
            self.warn("Tell me what to remind you about 🐶")
            self.text.setFocus()
            return
        due = self.when.dateTime().toSecsSinceEpoch()
        if due <= time.time():
            self.warn("That time has already passed! Pick a later one.")
            return
        self.pup.add_reminder(text, due)
        self.hide()

    def turn_off(self):
        self.hide()
        self.pup.turn_off()

    def rebuild_list(self):
        if self.list_widget:
            self.list_holder.removeWidget(self.list_widget)
            self.list_widget.hide()
            self.list_widget.deleteLater()
        self.list_widget = QWidget()
        lay = QVBoxLayout(self.list_widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        items = self.pup.pending()
        if not items:
            e = QLabel("Nothing yet. I'll keep watch!")
            e.setObjectName("muted")
            lay.addWidget(e)
        for r in items[:5]:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{r['text']}</b><br><span style='color:#e11d2e'>{nice_time(r['due'])}</span>")
            lbl.setObjectName("item")
            lbl.setWordWrap(True)
            x = QPushButton("✕")
            x.setObjectName("x")
            x.setCursor(Qt.CursorShape.PointingHandCursor)
            x.clicked.connect(lambda _=False, rid=r["id"]: (self.pup.delete_reminder(rid), self.rebuild_list()))
            row.addWidget(lbl, 1)
            row.addWidget(x)
            lay.addLayout(row)
        if len(items) > 5:
            more = QLabel(f"+{len(items) - 5} more")
            more.setObjectName("muted")
            lay.addWidget(more)
        self.list_holder.addWidget(self.list_widget)
        self.list_widget.show()
        self.adjustSize()

    def open_near(self, gp):
        self.text.clear()
        self.msg.hide()
        now = QDateTime.currentDateTime().addSecs(30 * 60)
        now.setTime(QTime(now.time().hour(), (now.time().minute() // 5) * 5))
        self.when.setDateTime(now)
        self.sound.blockSignals(True)
        self.sound.setChecked(self.pup.settings.get("bark", True))
        self.sound.blockSignals(False)
        self.rebuild_list()
        self.adjustSize()
        scr = (QGuiApplication.screenAt(gp) or QGuiApplication.primaryScreen()).availableGeometry()
        x = max(scr.left() + 8, min(scr.right() - self.width() - 8, gp.x() - self.width() // 2))
        y = max(scr.top() + 8, gp.y() - self.height() - 24)
        self.move(x, y)
        self.show()
        self.focus_text()
        QTimer.singleShot(80, self.focus_text)


# --------------------------------------------------------------------------- pup
# =========================================================================== voice
# Wispr-Flow-style voice, fully offline (faster-whisper on the CPU).
#   hold Right Ctrl   dictate: speech is typed wherever your cursor is
#                     (straight into the scratchpad when it's the active window)
#   hold Right Alt    talk to Shika: "open firefox", "remind me at 5 to call Rahul",
#                     "add task upload recording", "note GA4 idea", "search ..."
# A quick tap or a shortcut combo (Right Ctrl+C) is ignored, only a real hold counts.
VOICE_ON = True
DICTATE_KEY = "KEY_RIGHTCTRL"
COMMAND_KEY = "KEY_RIGHTALT"
HOLD_MS = 350              # how long a key must be held before it counts as push-to-talk
MAX_RECORD_S = 90
WHISPER_MODEL = "small.en" # hears accents and fast speech much better than "base.en" (faster, less accurate)
SPEEDS = {   # Shika app sidebar > SPEED
    "fast":     {"model": "base.en",  "beam": 1, "ai_min_words": 25},   # quickest; fine for short, clear speech
    "balanced": {"model": "small.en", "beam": 1, "ai_min_words": 10},   # default
    "best":     {"model": "small.en", "beam": 3, "ai_min_words": 1},    # most accurate, slowest
}
WHISPER_LANG = "en"        # None = auto-detect (use with a multilingual model)
RESTORE_CLIPBOARD = True   # put your old clipboard back after dictation pastes
DUCK_TO = 0.08             # while you hold a voice key, other sound drops to 8% of its volume (1.0 = off)
LINE_MORE = "aur kuch chahiye to bulaana 🐾"
UINPUT_NAME = "shika-typer"
SUMMIT = SUMMIT_DIR
SCRATCH_FILE = os.path.join(SUMMIT, "scratchpad.txt")
LIBRARY_FILE = os.path.join(SUMMIT, "library.json")
STICKY_FILE = os.path.join(SUMMIT, "notes.json")
FOCUS_FILE = os.path.join(SUMMIT, "focus.json")
BARK_FILES = [os.path.join(CONF, "bark.wav"), os.path.join(CONF, "bark.oga"),
              os.path.expanduser("~/.local/share/shika/bark.wav"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "bark.wav")]   # first one found is used
APP_ALIASES = {"browser": "firefox", "terminal": "konsole", "files": "dolphin",
               "file manager": "dolphin", "settings": "system settings", "calculator": "kcalc",
               "text editor": "kate", "editor": "kate", "music": "elisa", "chrome": "google chrome"}


def child_env():
    """Apps we launch should run natively on Wayland, not inherit Shika's xcb setting."""
    env = dict(os.environ)
    env.pop("QT_QPA_PLATFORM", None)
    return env


def durable_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rolling_backup(path)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class FileLock:
    """Same lock file summitctl.py uses, so the widgets and Shika never clobber each other."""
    def __init__(self, path):
        self.path = path + ".lock"

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "w")
        if IS_WIN:
            import msvcrt
            self.f.write(" ")
            self.f.flush()
            while True:
                try:
                    self.f.seek(0)
                    msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.05)
        else:
            import fcntl
            fcntl.flock(self.f, fcntl.LOCK_EX)

    def __exit__(self, *a):
        if IS_WIN:
            import msvcrt
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl
            fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


class KeyWatcher(QObject):
    """Reads key press/release from /dev/input (needs the 'input' group) on a thread."""
    pressed = pyqtSignal(str)
    released = pyqtSignal(str)
    cancelled = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ok, self.error = False, ""
        try:
            import evdev
        except ImportError:
            self.error = "voice needs python evdev (re-run install.sh)"
            return
        self.evdev = evdev
        ec = evdev.ecodes
        self.keys = {ec.ecodes[DICTATE_KEY]: "dictate", ec.ecodes[COMMAND_KEY]: "command"}
        self.devs = []
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                if d.name != UINPUT_NAME and ec.KEY_A in d.capabilities().get(ec.EV_KEY, []):
                    self.devs.append(d)
                else:
                    d.close()
            except OSError:
                continue
        if not self.devs:
            self.error = "can't read the keyboard yet. Log out and back in once after installing."
            return
        self.ok = True
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        import selectors
        ec = self.evdev.ecodes
        sel = selectors.DefaultSelector()
        for d in self.devs:
            sel.register(d, selectors.EVENT_READ)
        held = None                                   # [mode, keycode, cancelled]
        while True:
            for key, _ in sel.select():
                try:
                    events = list(key.fileobj.read())
                except OSError:
                    sel.unregister(key.fileobj)
                    continue
                for e in events:
                    if e.type != ec.EV_KEY or e.value == 2:
                        continue
                    if e.value == 1:
                        if held is None and e.code in self.keys:
                            held = [self.keys[e.code], e.code, False]
                            self.pressed.emit(held[0])
                        elif held is not None and e.code != held[1] and not held[2]:
                            held[2] = True
                            self.cancelled.emit(held[0])
                    elif held is not None and e.code == held[1]:
                        if not held[2]:
                            self.released.emit(held[0])
                        held = None


class Recorder:
    """16 kHz mono mic capture through parec (works with PipeWire)."""
    def __init__(self):
        self.proc, self.buf = None, bytearray()

    def start(self):
        self.stop()
        self.buf = bytearray()
        self.proc = QProcess()
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.start("parec", ["--format=s16le", "--rate=16000", "--channels=1",
                                  "--raw", "--latency-msec=40"])

    def _read(self):
        if self.proc:
            self.buf.extend(bytes(self.proc.readAllStandardOutput()))

    def stop(self):
        if not self.proc:
            return b""
        self._read()
        self.proc.terminate()
        if not self.proc.waitForFinished(600):
            self.proc.kill()
        self._read()
        self.proc = None
        return bytes(self.buf)

    def seconds(self):
        return len(self.buf) / 32000.0


HALLUCINATIONS = {"thank you", "thanks for watching", "thank you for watching", "thank you so much for watching",
                  "please subscribe", "subscribe", "bye", "you", "i'm not sure what i'm saying",
                  "i don't know what i'm saying", "i'm sorry", "okay", "so", "amara.org"}


def drop_repeats(text):
    """Whisper sometimes loops on silence: 'X. X. X.' -> 'X.'"""
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    out, seen = [], {}
    for p in parts:
        key = re.sub(r"[^\w\s']", "", p).strip().lower()
        seen[key] = seen.get(key, 0) + 1
        if out and key == re.sub(r"[^\w\s']", "", out[-1]).strip().lower():
            continue                                   # same sentence twice in a row
        if seen[key] > 1 and len(key.split()) <= 8:
            continue                                   # a short sentence coming back again = a loop
        out.append(p)
    return " ".join(out)


def clean_transcript(segs):
    """Keep only segments Whisper is confident are speech, and strip its usual made-up lines."""
    kept = []
    for sg in segs:
        t = sg.text.strip()
        key = re.sub(r"[^\w\s']", "", t).strip().lower()
        unsure = getattr(sg, "no_speech_prob", 0) > 0.5 or getattr(sg, "avg_logprob", 0) < -1.0
        if not t or (unsure and (key in HALLUCINATIONS or len(key.split()) <= 6)):
            continue
        if getattr(sg, "compression_ratio", 0) > 2.4:   # "the the the the…"
            continue
        kept.append(t)
    text = drop_repeats(" ".join(kept))
    # a known made-up line at the very end, after real speech, goes too
    parts = re.split(r"(?<=[.!?])\s+", text)
    while len(parts) > 1 and re.sub(r"[^\w\s']", "", parts[-1]).strip().lower() in HALLUCINATIONS - {"thank you", "okay", "so"}:
        parts.pop()
    return " ".join(parts).strip()


class Transcriber(QObject):
    done = pyqtSignal(str, str, str)                 # mode, text, error

    def __init__(self):
        super().__init__()
        self.model = None
        self.lock = threading.Lock()
        self.raw, self.how, self.level = "", "off", "auto"
        self.speed, self.secs = "balanced", 0.0
        self.variants, self.default = {}, "formatted"

    def _ensure(self):
        want = SPEEDS.get(self.speed, SPEEDS["balanced"])["model"]
        if self.model is None or getattr(self, "model_name", None) != want:
            from faster_whisper import WhisperModel
            threads = max(2, min(8, (os.cpu_count() or 4) - 2))   # most of the CPU, leave some for the desktop
            try:
                self.model = WhisperModel(want, device="cpu", compute_type="int8", cpu_threads=threads)
                self.model_name = want
            except Exception:                      # bigger model not downloaded yet: use the one we have
                self.model = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=threads)
                self.model_name = want                 # don't retry the download on every dictation

    def warm(self):
        def go():
            try:
                with self.lock:
                    self._ensure()
            except Exception:
                pass
        threading.Thread(target=go, daemon=True).start()

    def run(self, mode, pcm):
        threading.Thread(target=self._work, args=(mode, pcm), daemon=True).start()

    def _work(self, mode, pcm):
        try:
            import numpy as np
            audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            if len(audio) < 16000 * 0.4:
                self.done.emit(mode, "", "")
                return
            with self.lock:
                self._ensure()
                words, _ = load_dictionary()
                t0 = time.time()
                opts = dict(language=WHISPER_LANG, beam_size=SPEEDS.get(self.speed, SPEEDS["balanced"])["beam"],
                            vad_filter=True, without_timestamps=True,
                            vad_parameters={"min_silence_duration_ms": 500},
                            condition_on_previous_text=False, no_speech_threshold=0.5,
                            compression_ratio_threshold=2.2, log_prob_threshold=-1.0)
                try:                                  # "hotwords" nudges spelling without inventing text
                    segs, _ = self.model.transcribe(audio, hotwords=", ".join(words[:60]) or None, **opts)
                    segs = list(segs)
                except TypeError:                     # older faster-whisper without hotwords
                    segs = list(self.model.transcribe(audio, **opts)[0])
                text = clean_transcript(segs)
            self.raw = text
            if mode == "dictate" and text:                     # cleanup runs here, off the UI thread
                level = self.level
                if level != "off" and len(text.split()) < SPEEDS.get(self.speed, SPEEDS["balanced"])["ai_min_words"] \
                        and not re.search(CORRECTION_CUES, text, re.I):
                    level = "light"                         # short and simple: rules are instant and enough
                self.variants, self.how = make_variants(text, level, deep=(self.speed == "best"))
                text = self.variants.get(self.default, text)
            self.secs = time.time() - t0
            self.done.emit(mode, text, "")
        except Exception as ex:
            self.done.emit(mode, "", f"{type(ex).__name__}: {ex}")


class Typer:
    """Pastes text at the cursor: clipboard + a virtual Shift+Insert from /dev/uinput.
    Works in any Wayland or X app, including terminals, and handles emoji/Hindi."""
    def __init__(self):
        self.ui, self.error = None, ""
        try:
            from evdev import UInput, ecodes as e
            self.e = e
            keys = ["KEY_LEFTSHIFT", "KEY_INSERT", "KEY_LEFTCTRL", "KEY_LEFTALT", "KEY_W", "KEY_T", "KEY_N",
                    "KEY_TAB", "KEY_LEFT", "KEY_RIGHT", "KEY_F5", "KEY_PLAYPAUSE", "KEY_NEXTSONG",
                    "KEY_PREVIOUSSONG", "KEY_C", "KEY_Z", "KEY_A", "KEY_F4", "KEY_F24", "KEY_LEFTMETA", "KEY_D"]
            # a key name this evdev doesn't know must never take typing down with it
            self.ui = UInput({e.EV_KEY: [e.ecodes[k] for k in keys if k in e.ecodes]}, name=UINPUT_NAME)
        except Exception as ex:
            self.error = str(ex)

    def combo(self, names):
        """Press keys together (Ctrl+W…) in whatever window is active. False if no keyboard access."""
        if not self.ui:
            return False
        e = self.e
        try:
            codes = [e.ecodes[n] for n in names]
        except KeyError:
            return False
        for c in codes:
            self.ui.write(e.EV_KEY, c, 1)
            self.ui.syn()
            time.sleep(0.01)
        for c in reversed(codes):
            self.ui.write(e.EV_KEY, c, 0)
            self.ui.syn()
            time.sleep(0.01)
        return True

    def clip_get(self):
        return self._clip_get()

    def clip_set(self, text, primary=False):
        self._clip_set(text, primary)

    def clip_clear(self):
        if shutil.which("wl-copy"):
            subprocess.run(["wl-copy", "--clear"], timeout=2)

    @staticmethod
    def _clip_get():
        try:
            if shutil.which("wl-paste"):
                types = subprocess.run(["wl-paste", "--list-types"], capture_output=True,
                                       text=True, timeout=1).stdout
                if "text/plain" not in types:
                    return None
                return subprocess.run(["wl-paste", "-n"], capture_output=True, text=True,
                                      timeout=1).stdout
        except Exception:
            pass
        return None

    @staticmethod
    def _clip_set(text, primary=False):
        if shutil.which("wl-copy"):
            args = ["wl-copy"] + (["--primary"] if primary else [])
            subprocess.run(args, input=text, text=True, timeout=2)
        else:
            cb = QApplication.clipboard()
            cb.setText(text, cb.Mode.Selection if primary else cb.Mode.Clipboard)

    def paste(self, text):
        """Returns True if it was pasted, False if it's only on the clipboard."""
        old = self._clip_get() if RESTORE_CLIPBOARD else None
        try:
            self._clip_set(text)
            self._clip_set(text, primary=True)
        except Exception:
            pass
        if not self.ui:
            return False
        e = self.e

        def press():
            for code, val in ((e.KEY_LEFTSHIFT, 1), (e.KEY_INSERT, 1), (e.KEY_INSERT, 0),
                              (e.KEY_LEFTSHIFT, 0)):
                self.ui.write(e.EV_KEY, code, val)
                self.ui.syn()
                time.sleep(0.008)
            if old is not None:
                QTimer.singleShot(900, lambda: self._clip_set(old))
        QTimer.singleShot(160, press)
        return True


# --------------------------------------------------------------------------- other operating systems
# Linux keeps its own code above (evdev, uinput, wl-clipboard, KWin). On macOS and Windows the same
# jobs are done here: pynput for keys, sounddevice for the microphone, Qt for the clipboard,
# osascript / PowerShell for apps and windows.
UI_RUN = None                       # set by the pup: run a function on the UI thread


def on_ui(fn, timeout=1.5):
    """Run fn on the UI thread and wait for its answer (Qt's clipboard must be used there)."""
    if UI_RUN is None or threading.current_thread() is threading.main_thread():
        return fn()
    box, ev = {}, threading.Event()

    def go():
        try:
            box["v"] = fn()
        finally:
            ev.set()
    UI_RUN(go)
    ev.wait(timeout)
    return box.get("v")


def _pynput_key(kb, name):
    """'KEY_LEFTCTRL' (the names Shika uses everywhere) -> a pynput key, or None if this OS has no such key."""
    K = kb.Key
    g = lambda a: getattr(K, a, None)
    table = {"KEY_LEFTCTRL": g("cmd") if IS_MAC else g("ctrl"), "REALCTRL": g("ctrl"), "KEY_RIGHTCTRL": g("ctrl_r"), "KEY_RIGHTALT": g("alt_r"),
             "KEY_LEFTSHIFT": g("shift"), "KEY_LEFTALT": g("alt"), "KEY_LEFTMETA": g("cmd"), "KEY_TAB": g("tab"),
             "KEY_LEFT": g("left"), "KEY_RIGHT": g("right"), "KEY_F5": g("f5"), "KEY_F4": g("f4"),
             "KEY_INSERT": g("insert"), "KEY_PLAYPAUSE": g("media_play_pause"), "KEY_NEXTSONG": g("media_next"),
             "KEY_PREVIOUSSONG": g("media_previous"), "KEY_VOLUMEUP": g("media_volume_up"),
             "KEY_VOLUMEDOWN": g("media_volume_down"), "KEY_MUTE": g("media_volume_mute"),
             "KEY_LEFTBRACE": "[", "KEY_RIGHTBRACE": "]"}
    if name in table:
        return table[name]
    m = re.fullmatch(r"KEY_([A-Z0-9])", name)
    return m.group(1).lower() if m else None


def mac_keys(names):
    """Linux shortcut -> the Mac one: Ctrl becomes Cmd, Alt+Left becomes Cmd+[, tab switching keeps real Ctrl."""
    n = list(names)
    fixes = {("KEY_LEFTCTRL", "KEY_INSERT"): ["KEY_LEFTCTRL", "KEY_C"], ("KEY_LEFTSHIFT", "KEY_INSERT"): ["KEY_LEFTCTRL", "KEY_V"],
             ("KEY_LEFTALT", "KEY_LEFT"): ["KEY_LEFTCTRL", "KEY_LEFTBRACE"],
             ("KEY_LEFTALT", "KEY_RIGHT"): ["KEY_LEFTCTRL", "KEY_RIGHTBRACE"], ("KEY_LEFTALT", "KEY_F4"): ["KEY_LEFTCTRL", "KEY_W"]}
    if tuple(n) in fixes:
        return fixes[tuple(n)]
    if "KEY_TAB" in n:
        return ["REALCTRL" if k == "KEY_LEFTCTRL" else k for k in n]
    return n


if not IS_LINUX:
    class KeyWatcher(QObject):
        """Right Ctrl / Right Alt (Right Option on a Mac) held down = push to talk. Uses pynput."""
        pressed = pyqtSignal(str)
        released = pyqtSignal(str)
        cancelled = pyqtSignal(str)

        def __init__(self):
            super().__init__()
            self.ok, self.error = False, ""
            try:
                from pynput import keyboard
            except Exception as ex:
                self.error = f"voice needs the pynput package ({ex}). Run the installer again."
                return
            names = {DICTATE_KEY: "dictate", COMMAND_KEY: "command"}
            self.keys = {}
            for ev, mode in names.items():
                k = _pynput_key(keyboard, ev)
                if k is not None:
                    self.keys[k] = mode
                if ev == "KEY_RIGHTALT" and getattr(keyboard.Key, "alt_gr", None) is not None:
                    self.keys[keyboard.Key.alt_gr] = mode          # Windows reports Right Alt as AltGr on some layouts
            self.held = None                                      # [mode, key, cancelled]
            try:
                self.listener = keyboard.Listener(on_press=self._press, on_release=self._release)
                self.listener.daemon = True
                self.listener.start()
            except Exception as ex:
                self.error = f"can't read the keyboard: {ex}"
                return
            self.ok = True

        def _press(self, key):
            if self.held is None:
                if key in self.keys:
                    self.held = [self.keys[key], key, False]
                    self.pressed.emit(self.held[0])
            elif key != self.held[1] and not self.held[2] and key not in self.keys:
                self.held[2] = True
                self.cancelled.emit(self.held[0])

        def _release(self, key):
            if self.held is not None and key == self.held[1]:
                if not self.held[2]:
                    self.released.emit(self.held[0])
                self.held = None

    class Recorder:
        """16 kHz mono mic capture through sounddevice."""
        def __init__(self):
            self.stream, self.buf, self.error = None, bytearray(), ""

        def start(self):
            self.stop()
            self.buf = bytearray()
            try:
                import sounddevice as sd

                def cb(indata, frames, t, status):
                    self.buf.extend(bytes(indata))
                self.stream = sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=640, callback=cb)
                self.stream.start()
            except Exception as ex:
                self.stream, self.error = None, str(ex)
                dlog(f"microphone: {ex}")

        def stop(self):
            s, self.stream = self.stream, None
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
            return bytes(self.buf)

        def seconds(self):
            return len(self.buf) / 32000.0

    class Typer:
        """Pastes text at the cursor: clipboard + Ctrl+V (Cmd+V on a Mac), and presses other shortcuts."""
        def __init__(self):
            self.ui, self.error = None, ""
            try:
                from pynput import keyboard
                self.kb = keyboard
                self.ui = keyboard.Controller()
            except Exception as ex:
                self.error = f"typing needs the pynput package ({ex})"

        def combo(self, names):
            """Press keys together (Ctrl+W…) in the active window. False if keys can't be sent."""
            if not self.ui:
                return False
            names = mac_keys(names) if IS_MAC else list(names)
            keys = [_pynput_key(self.kb, n) for n in names]
            if any(k is None for k in keys):
                return False
            try:
                for k in keys:
                    self.ui.press(k)
                    time.sleep(0.01)
                for k in reversed(keys):
                    self.ui.release(k)
                    time.sleep(0.01)
            except Exception as ex:
                dlog(f"keys {names}: {ex}")
                return False
            return True

        def clip_get(self):
            return self._clip_get()

        def clip_set(self, text, primary=False):
            if not primary:
                self._clip_set(text)

        def clip_clear(self):
            self._clip_set("")

        @staticmethod
        def _clip_get():
            try:
                return on_ui(lambda: QApplication.clipboard().text())
            except Exception:
                return None

        @staticmethod
        def _clip_set(text, primary=False):
            if not primary:
                on_ui(lambda: QApplication.clipboard().setText(text))

        def paste(self, text):
            """True if it was pasted, False if it's only on the clipboard."""
            old = self._clip_get() if RESTORE_CLIPBOARD else None
            try:
                self._clip_set(text)
            except Exception:
                pass
            if not self.ui:
                return False

            def press():
                self.combo(["KEY_LEFTCTRL", "KEY_V"])
                if old is not None:
                    QTimer.singleShot(900, lambda: self._clip_set(old))
            QTimer.singleShot(160, press)
            return True


def clip_tools_ok():
    return bool(shutil.which("wl-copy") and shutil.which("wl-paste")) if IS_LINUX else True


def clip_read(primary=False):
    """-> (return code, text, error): the clipboard (or the mouse highlight on Linux)."""
    if IS_LINUX:
        return run_capture(["wl-paste"] + (["-p"] if primary else []) + ["-n"], timeout=2)
    if primary:
        return 1, "", "no highlight clipboard on this system"
    t = Typer._clip_get()
    return (0, t, "") if t is not None else (1, "", "clipboard not readable")


def mic_ok():
    if IS_LINUX:
        return bool(shutil.which("parec"))
    try:
        import sounddevice  # noqa: F401
        return True
    except Exception:
        return False


def mic_help():
    return ("mic tool 'parec' is missing (sudo apt install pulseaudio-utils)" if IS_LINUX else
            "microphone support is missing (pip install sounddevice), or allow Shika to use the microphone in "
            + ("System Settings > Privacy & Security" if IS_MAC else "Settings > Privacy > Microphone"))


def open_target(target):
    """Open a web address, a file or a custom link with whatever the system uses for it."""
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if IS_LINUX:
        subprocess.Popen(["xdg-open", target], env=child_env(), start_new_session=True, **quiet)
    elif IS_MAC:
        subprocess.Popen(["open", target], **quiet)
    else:
        try:
            os.startfile(target)
        except Exception:
            import webbrowser
            webbrowser.open(target)


def launch_path(path):
    """Start an app found by find_app()."""
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if IS_LINUX:
        launcher = ["gio", "launch", path] if shutil.which("gio") else ["kioclient", "exec", path]
        subprocess.Popen(launcher, env=child_env(), start_new_session=True, **quiet)
    elif IS_MAC:
        subprocess.Popen(["open", path], **quiet)
    else:
        os.startfile(path)


BROWSER_APPS = {"chrome": ("Google Chrome", "chrome"), "firefox": ("Firefox", "firefox"),
                "brave": ("Brave Browser", "brave"), "edge": ("Microsoft Edge", "msedge"),
                "chromium": ("Chromium", "chromium")}


def open_in_browser(b, url):
    mac, win = BROWSER_APPS.get(b, (b, b))
    if IS_MAC:
        subprocess.Popen(["open", "-a", mac, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["cmd", "/c", "start", "", win, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_app(name):
    """Best match for a spoken app name: .desktop files on Linux, .app bundles on a Mac, Start Menu shortcuts on Windows."""
    if IS_LINUX:
        return _find_app_desktop(name)
    import difflib
    name = name.lower().strip()
    name = {"browser": "chrome", "terminal": "terminal", "files": "finder" if IS_MAC else "file explorer",
            "file manager": "finder" if IS_MAC else "file explorer", "settings": "system settings" if IS_MAC else "settings",
            "calculator": "calculator", "text editor": "textedit" if IS_MAC else "notepad",
            "music": "music" if IS_MAC else "media player"}.get(name, name)
    if IS_MAC:
        dirs, ext = ["/Applications", "/System/Applications", "/System/Applications/Utilities",
                     "/Applications/Utilities", os.path.expanduser("~/Applications")], ".app"
    else:
        dirs = [os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
                os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")]
        ext = ".lnk"
    best, best_score = None, 0.0
    for d in dirs:
        for root, subdirs, files in os.walk(d):
            if root.count(os.sep) - d.count(os.sep) > 2:
                subdirs[:] = []
            for entry in (subdirs if ext == ".app" else files):
                if not entry.lower().endswith(ext):
                    continue
                label = entry[:-len(ext)]
                cand = label.lower()
                score = difflib.SequenceMatcher(None, name, cand).ratio()
                if cand == name:
                    score = 1.5
                elif cand.startswith(name) or name in cand.split():
                    score = max(score, 0.9)
                if score > best_score:
                    best, best_score = (os.path.join(root, entry), label), score
            if ext == ".app":
                subdirs[:] = [s for s in subdirs if not s.lower().endswith(".app")]
    return best if best_score >= 0.6 else None


def proc_running(names, exact=False):
    """Is any of these programs running?"""
    for n in names:
        if IS_WIN:
            rc, out, _ = run_capture(["tasklist", "/FI", f"IMAGENAME eq {n}.exe", "/NH"], timeout=4)
            if rc == 0 and n.lower() in out.lower():
                return True
        elif run_capture(["pgrep", "-x" if exact else "-ix", n])[0] == 0:
            return True
    return False


APP_NAMES = {   # spoken key -> (Mac application name, Windows process name)
    "chrome": ("Google Chrome", "chrome"), "firefox": ("Firefox", "firefox"), "brave": ("Brave Browser", "brave"),
    "chromium": ("Chromium", "chromium"), "edge": ("Microsoft Edge", "msedge"), "dolphin": ("Finder", None),
    "konsole": ("Terminal", "WindowsTerminal"), "systemsettings": ("System Settings", "SystemSettings"),
    "kate": ("TextEdit", "notepad"), "elisa": ("Music", "Music.UI"), "kcalc": ("Calculator", "CalculatorApp")}


def _ps(script, timeout=8):
    return run_capture(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout)


def other_os_windows(key, action):
    """Close / minimize / bring forward every window of an app, the polite way (it gets to save and ask)."""
    mac, win = APP_NAMES.get(key, (key.title(), key))
    if IS_MAC:
        script = {"close": f'tell application "{mac}" to quit',
                  "focus": f'tell application "{mac}" to activate',
                  "minimize": f'tell application "System Events" to set visible of process "{mac}" to false'}[action]
        rc, out, err = run_capture(["osascript", "-e", script], timeout=6)
        dlog(f"osascript {action} {mac!r} rc={rc} {err[:120]}")
        return rc == 0
    if not win:
        return False
    show = {"minimize": 6, "focus": 9}.get(action)
    if action == "close":
        body = "$_.CloseMainWindow() | Out-Null"
    else:
        body = f"[W.U]::ShowWindow($_.MainWindowHandle, {show}) | Out-Null; [W.U]::SetForegroundWindow($_.MainWindowHandle) | Out-Null"
    ps = ("Add-Type -Name U -Namespace W -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool "
          "ShowWindow(IntPtr h,int c); [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr h);'; "
          f"$p = Get-Process | Where-Object {{ $_.MainWindowHandle -ne 0 -and ($_.ProcessName -like '*{win}*' -or $_.MainWindowTitle -like '*{key}*') }}; "
          f"if (-not $p) {{ exit 3 }}; $p | ForEach-Object {{ {body} }}")
    rc, out, err = _ps(ps)
    dlog(f"powershell {action} {win!r} rc={rc} {err[:120]}")
    return rc == 0


def lock_screen():
    if IS_MAC:
        subprocess.Popen(["osascript", "-e", 'tell application "System Events" to keystroke "q" using {control down, command down}'])
    elif IS_WIN:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    else:
        cmd = ["loginctl", "lock-session"]
        subprocess.Popen(cmd)


def volume_step(pup, kind):
    """volume up / down / mute on any system. True if a key or command went out."""
    if IS_LINUX:
        return False
    key = {"up": "KEY_VOLUMEUP", "down": "KEY_VOLUMEDOWN", "mute": "KEY_MUTE"}[kind]
    k = _pynput_key(pup.typer.kb, key) if pup.typer.ui else None
    if k is None:
        return False
    try:
        pup.typer.ui.tap(k)
        return True
    except Exception:
        return False


def system_notify(title, body):
    if IS_MAC:
        esc = lambda s: str(s).replace("\\", "\\\\").replace('"', '\\"')
        subprocess.Popen(["osascript", "-e", f'display notification "{esc(body)}" with title "{esc(title)}"'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        dlog(f"notify: {title}: {body}")          # Windows: the pup's own speech bubble is the notice


def play_file(path):
    if IS_MAC:
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    if IS_WIN:
        try:
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return True
        except Exception:
            return False
    return False


def set_ui_run(fn):
    global UI_RUN
    UI_RUN = fn


class Library(QObject):
    """Everything you dictate, scribble in the scratchpad, or write on a sticky note, as
    separate titled entries with version history (v1, v2…). Stored in
    ~/.local/share/summit/library.json; the sticky-note widgets write to it too, so every
    change happens under a shared lock and Shika re-reads the file when it changes."""
    changed = pyqtSignal()
    MAX_VERSIONS = 30

    def __init__(self):
        super().__init__()
        self.mtime = None
        self.entries = self._read()
        self._migrate()
        QTimer(self, timeout=self.poll).start(2000)

    @staticmethod
    def _read():
        data = load_json(LIBRARY_FILE, [])
        return data if isinstance(data, list) else []

    def _migrate(self):
        def fn(entries):
            if os.path.exists(SCRATCH_FILE):                      # v3.0 single scratchpad file
                try:
                    old = open(SCRATCH_FILE).read()
                except OSError:
                    old = ""
                if old.strip():
                    entries.append(self._make("note", old, "Old scratchpad"))
                os.replace(SCRATCH_FILE, SCRATCH_FILE + ".migrated")
            have = {e["id"] for e in entries}
            for nid, n in load_json(STICKY_FILE, {}).items():      # sticky notes from before v3.2
                if ("sticky:" + nid) not in have and (n.get("text") or "").strip():
                    e = self._make("sticky", n["text"])
                    e["id"] = "sticky:" + nid
                    entries.append(e)
        self._mutate(fn, quiet=True)

    @staticmethod
    def _make(kind, text, title=""):
        now = time.time()
        return {"id": f"{now:.6f}", "kind": kind, "title": title, "text": text,
                "created": now, "updated": now, "versions": []}

    def _mutate(self, fn, quiet=False):
        """Re-read the file, apply fn(entries), write it back, all under the shared lock."""
        try:
            with FileLock(LIBRARY_FILE):
                self.entries = self._read()
                result = fn(self.entries)
                durable_write(LIBRARY_FILE, json.dumps(self.entries, indent=1, ensure_ascii=False))
                self.mtime = os.path.getmtime(LIBRARY_FILE)
        except OSError as ex:
            log_errors(OSError, ex, None)
            return None
        if not quiet:
            self.changed.emit()
        return result

    def poll(self):
        try:
            mt = os.path.getmtime(LIBRARY_FILE)
        except OSError:
            return
        if mt != self.mtime:
            self.mtime = mt
            self.entries = self._read()
            self.changed.emit()

    def get(self, eid):
        return next((e for e in self.entries if e["id"] == eid), None)

    def add(self, kind, text, title="", spoken=None):
        e = self._make(kind, text, title)
        if spoken and spoken.strip() != text.strip():          # keep exactly what you said as v1
            e["versions"] = [{"n": 1, "title": "", "text": spoken, "saved": e["created"], "reason": "as spoken"}]
        self._mutate(lambda es: es.append(e))
        return e

    def update(self, eid, **fields):
        e = self.get(eid)
        if not e or all(e.get(k) == v for k, v in fields.items()):
            return

        def fn(es):
            for x in es:
                if x["id"] == eid:
                    x.update(fields)
                    x["updated"] = time.time()
                    x.pop("removed", None)
        self._mutate(fn)

    def delete(self, eid):
        self._mutate(lambda es: es.__setitem__(slice(None), [x for x in es if x["id"] != eid]))

    @classmethod
    def push_version(cls, e, reason):
        """Keep the entry's current text as the next version, unless it's empty or unchanged."""
        vs = e.setdefault("versions", [])
        if not e.get("text", "").strip():
            return False
        if vs and vs[-1]["text"] == e["text"] and vs[-1].get("title", "") == e.get("title", ""):
            return False
        n = (vs[-1]["n"] + 1) if vs else 1
        vs.append({"n": n, "title": e.get("title", ""), "text": e["text"], "saved": time.time(),
                   "reason": reason})
        del vs[:-cls.MAX_VERSIONS]
        return True

    def snapshot(self, eid, reason):
        def fn(es):
            for x in es:
                if x["id"] == eid:
                    return self.push_version(x, reason)
            return False
        if self.get(eid):
            return self._mutate(fn)
        return False

    def restore(self, eid, n):
        def fn(es):
            for x in es:
                if x["id"] != eid:
                    continue
                v = next((v for v in x.get("versions", []) if v["n"] == n), None)
                if v:
                    self.push_version(x, f"before restoring v{n}")
                    x["text"], x["title"] = v["text"], v.get("title", "")
                    x["updated"] = time.time()
        self._mutate(fn)

    @staticmethod
    def title_of(e):
        return e.get("title") or auto_title(e.get("text", ""))

    def stats(self):
        week_ago = time.time() - 7 * 86400
        dict_entries = [e for e in self.entries if e["kind"] == "dictation"]
        words = sum(len(e["text"].split()) for e in dict_entries)
        week = sum(len(e["text"].split()) for e in dict_entries if e["created"] > week_ago)
        notes = sum(1 for e in self.entries if e["kind"] in ("note", "sticky"))
        return len(dict_entries), words, week, notes


def auto_title(text):
    line = text.strip().split("\n", 1)[0]
    words = line.split()
    t = " ".join(words[:7])
    if len(words) > 7 or len(t) > 48:
        t = t[:48].rstrip() + "…"
    return t or "Untitled"


def short_when(ts):
    d = datetime.fromtimestamp(ts)
    if d.date() == datetime.now().date():
        return d.strftime("%I:%M %p").lstrip("0")
    if d.date() == (datetime.now() - timedelta(days=1)).date():
        return "Yesterday"
    return d.strftime("%d %b").lstrip("0")


GLASS_CSS = """
QWidget { color: #f2f2f3; font-size: 13px; }
#card, #shell { background: rgba(10,10,12,238); border: 1px solid rgba(255,255,255,26); border-radius: 16px; }
#side { background: rgba(255,255,255,6); border-right: 1px solid rgba(255,255,255,18); }
#mid { border-right: 1px solid rgba(255,255,255,18); }
QLabel#brand { font-size: 20px; letter-spacing: 6px; font-weight: 800; }
QLabel#caps { font-size: 11px; letter-spacing: 3px; font-weight: 700; }
QLabel#muted { color: rgba(255,255,255,125); font-size: 11px; }
QLabel#red { color: #e11d2e; font-size: 11px; }
QLabel#stat { color: #f2f2f3; font-size: 18px; font-weight: 700; }
QLabel#empty { color: rgba(255,255,255,90); font-size: 13px; }
QLineEdit { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,22); border-radius: 10px;
            padding: 7px 10px; selection-background-color: #e11d2e; }
QLineEdit:focus { border-color: #e11d2e; }
QLineEdit#bigtitle, QLineEdit#title { background: transparent; border: none; border-bottom: 1px solid rgba(255,255,255,22);
            border-radius: 0; font-size: 18px; font-weight: 700; padding: 4px 0; }
QLineEdit#title { font-size: 15px; }
QLineEdit#bigtitle:focus, QLineEdit#title:focus { border-bottom: 1px solid #e11d2e; }
QPlainTextEdit { background: transparent; border: none; font-size: 14px; selection-background-color: #e11d2e; }
QPushButton { background: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,24); border-radius: 12px;
              padding: 6px 12px; font-size: 12px; }
QPushButton:hover { border-color: #e11d2e; }
QPushButton#primary { background: #e11d2e; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #f2303f; }
QPushButton#nav { background: transparent; border: none; text-align: left; padding: 8px 10px; border-radius: 10px; font-size: 13px; }
QPushButton#nav:hover { background: rgba(255,255,255,10); }
QPushButton#nav:checked { background: rgba(225,29,46,46); color: #ffffff; }
QPushButton#danger { color: #ff8a93; }
QPushButton#danger:hover { border-color: #e11d2e; background: rgba(225,29,46,40); }
QPushButton#x { background: transparent; border: none; color: rgba(255,255,255,120); font-size: 14px; padding: 0 4px; }
QPushButton#x:hover { color: #e11d2e; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { border-radius: 10px; margin: 1px 6px; }
QListWidget::item:hover { background: rgba(255,255,255,8); }
QListWidget::item:selected { background: rgba(225,29,46,40); }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,40); border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class Scratchpad(QWidget):
    """Quick floating scratchpad. Every note it holds is an entry in the Shika app."""
    REOPEN_WITHIN = 2 * 3600       # reopen your last note if you touched it in the last 2 hours

    def __init__(self, lib, open_app):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.lib, self.open_app = lib, open_app
        self.entry_id, self.loading, self.drag_from = None, False, None
        self.setWindowTitle("Shika scratchpad")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(GLASS_CSS)
        self.resize(460, 360)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)
        top = QHBoxLayout()
        caps = QLabel("—  SCRATCHPAD")
        caps.setObjectName("caps")
        close = QPushButton("✕")
        close.setObjectName("x")
        close.clicked.connect(self.hide)
        top.addWidget(caps, 1)
        top.addWidget(close)
        lay.addLayout(top)
        self.title = QLineEdit()
        self.title.setObjectName("title")
        self.title.setPlaceholderText("Untitled note")
        self.title.textChanged.connect(self.on_edit)
        lay.addWidget(self.title)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Type, or hold Right Ctrl and talk.\nEvery note is kept in the Shika app.")
        self.edit.textChanged.connect(self.on_edit)
        lay.addWidget(self.edit, 1)
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        bottom.addWidget(self.status, 1)
        for label, fn, name in (("＋ New", self.new_note, ""), ("Copy", self.copy_all, ""),
                                ("Open Shika ↗", self.open_in_app, "primary")):
            b = QPushButton(label)
            b.setObjectName(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            bottom.addWidget(b)
        lay.addLayout(bottom)
        self.save_timer = QTimer(self, singleShot=True, timeout=self.save_now)
        lib.changed.connect(self.on_lib_changed)

    def load_entry(self, e):
        self.loading = True
        self.entry_id = e["id"] if e else None
        self.title.setText(e.get("title", "") if e else "")
        self.edit.setPlainText(e.get("text", "") if e else "")
        self.edit.moveCursor(self.edit.textCursor().MoveOperation.End)
        self.status.setText(f"saved · {short_when(e['updated'])}" if e else "new note")
        self.loading = False

    def on_edit(self):
        if self.loading:
            return
        self.status.setText("…")
        self.save_timer.start(600)

    def save_now(self):
        self.save_timer.stop()
        text, title = self.edit.toPlainText(), self.title.text().strip()
        if self.entry_id is None or not self.lib.get(self.entry_id):
            if not text.strip() and not title:
                return
            self.entry_id = self.lib.add("note", text, title)["id"]
        else:
            self.lib.update(self.entry_id, text=text, title=title)
        self.status.setText("saved to Shika")

    def on_lib_changed(self):
        if self.entry_id is None or self.save_timer.isActive():
            return
        e = self.lib.get(self.entry_id)
        if e is None:                                  # deleted in the app
            self.load_entry(None)
        elif (e["text"] != self.edit.toPlainText() or e.get("title", "") != self.title.text()) \
                and not self.isActiveWindow():
            self.load_entry(e)                         # edited in the app

    def close_version(self):
        """Closing (or starting a new note) keeps what you wrote as a version: v1, v2…"""
        self.save_now()
        if self.entry_id:
            self.lib.snapshot(self.entry_id, "scratchpad closed")

    def open_in_app(self):
        self.save_now()
        self.open_app(self.entry_id)

    def new_note(self):
        self.close_version()
        self.load_entry(None)
        self.edit.setFocus()

    def insert(self, text):
        cur = self.edit.textCursor()
        before = self.edit.toPlainText()[:cur.position()]
        if before and not before[-1].isspace():
            text = " " + text
        cur.insertText(text)
        self.edit.setTextCursor(cur)

    def copy_all(self):
        QApplication.clipboard().setText(self.edit.toPlainText())
        self.status.setText("copied")

    def toggle(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
            return
        if not self.isVisible():
            cur = self.lib.get(self.entry_id) if self.entry_id else None
            if cur is None:
                notes = sorted((e for e in self.lib.entries if e["kind"] == "note"),
                               key=lambda e: e["updated"], reverse=True)
                recent = notes[0] if notes and time.time() - notes[0]["updated"] < self.REOPEN_WITHIN else None
                self.load_entry(recent)
            scr = QGuiApplication.primaryScreen().availableGeometry()
            self.move(scr.center().x() - self.width() // 2, scr.top() + 120)
        self.show()
        self.raise_()
        self.activateWindow()
        self.edit.setFocus()

    def hideEvent(self, e):
        self.close_version()
        super().hideEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        self.drag_from = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_from is not None:
            self.move(e.globalPosition().toPoint() - self.drag_from)

    def mouseReleaseEvent(self, e):
        self.drag_from = None


GUIDE_HTML = """
<style>
 h1 { font-size: 22px; letter-spacing: 4px; margin: 0 0 4px 0; }
 h2 { font-size: 15px; color: #ffffff; margin: 22px 0 6px 0; letter-spacing: 1px; }
 p, li, td { font-size: 13px; color: #e6e6e8; line-height: 150%; }
 .m { color: #9a9aa0; }
 .k { background: #2a2a2e; color: #ffffff; padding: 1px 6px; border-radius: 4px; font-family: monospace; }
 .r { color: #ff5a68; }
 td { padding: 3px 14px 3px 0; vertical-align: top; }
</style>
<h1>SHIKA GUIDE</h1>
<p class="m">Everything your desk can do, in one place. Version """ + VERSION + """.</p>

<h2>🚀 Quick start</h2>
<table>
<tr><td><b>Find this app</b></td><td>App Launcher → type <b>Shika</b> → the dog icon. Right-click it → <i>Pin to Task Manager</i>
or <i>Add to Desktop</i> to keep it one click away.</td></tr>
<tr><td><b>Talk to type</b></td><td>Hold <span class="k">Right Ctrl</span>, speak, let go.</td></tr>
<tr><td><b>Ask Shika</b></td><td>Hold <span class="k">Right Alt</span>, speak, let go. The key is the wake-up: no need to say “Shika” first
(saying it is fine too).</td></tr>
<tr><td><b>Quick note</b></td><td>Launcher → <b>Shika Scratchpad</b>, or say “open scratchpad”.</td></tr>
<tr><td><b>Remind me</b></td><td>Type in the Tasks &amp; reminders widget, or say “reminder to call Mohit tmrw 5.30 pm”.</td></tr>
</table>

<h2>🔎 The launcher entries</h2>
<table>
<tr><td>🐶 <b>Shika</b></td><td>This app: dictations, notes, sticky notes, versions, this guide</td></tr>
<tr><td>🐶 <b>Shika Pup</b></td><td>Wakes the dog if you turned him off</td></tr>
<tr><td><b>Shika Scratchpad</b></td><td>The floating quick-note window</td></tr>
<tr><td><b>Shika Dictate / Command (toggle)</b></td><td>Press-once alternatives to holding a key, for keyboard shortcuts</td></tr>
</table>

<h2>🎤 Voice, fully offline</h2>
<table>
<tr><td><span class="k">Hold Right Ctrl</span></td><td>Dictate. Talk, let go, and the words are typed where your cursor is.
If the scratchpad is open and active, they go into it. Every dictation is also kept here under <b>Dictations</b>.</td></tr>
<tr><td><span class="k">Hold Right Alt</span></td><td>Give Shika a command (list below).</td></tr>
</table>
<p>While you hold either key, Shika wakes up, does a quick turn-around and sits with his head tilted, listening.
Any music or video playing drops to almost silent, and comes back the moment you let go
(<span class="k">DUCK_TO</span> at the top of shika.py sets how quiet; 1.0 turns it off).
When he's done he says <i>“aur kuch chahiye to bulaana”</i>.</p>
<p>Hold for a moment before talking. A quick tap, or a combo like Right Ctrl+C, is ignored.
While dictating, say <i>“new line”</i> or <i>“new paragraph”</i> for line breaks.</p>

<h2>🗣 Voice commands (hold Right Alt)</h2>
<table>
<tr><td>Tasks</td><td>“add task upload recording” · “add task call Rahul at 5” <span class="m">(barks at 5)</span></td></tr>
<tr><td>Reminders</td><td>“remind me at 6 to stretch” · “remind me in 20 minutes to drink water” ·
“set a reminder for the meeting tmrw 5:30 pm” · “reminder to call Mohit tmrw 5.30 pm” · “add a reminder…” · “set an alarm for 6 am tomorrow” · “remind me on friday at 3 to submit the report” ·
“remind me next monday at 10 am about the batch” · “remind me on 12th november at 11 am for the client call” ·
“remind me tonight / this evening / tomorrow morning …” · “at half past five” · “at quarter to six” · “at noon”</td></tr>
<tr><td>How times are read</td><td>A day with no time means 9 AM. “Tomorrow at 5” (no am/pm) means 5 PM; 7–11 means morning.
“At 5” today after 5 PM means tomorrow. If you give no day or time, Shika sets it for an hour later and says so.
Shika always shows and notifies exactly when he set it, so you can check.</td></tr>
<tr><td>Notes</td><td>“note GA4 case study idea” <span class="m">(saved here as a note)</span> · “open scratchpad” · “open Shika”</td></tr>
<tr><td>Apps</td><td>“open file manager” · “open terminal” · “open settings” · “open kate”</td></tr>
<tr><td>Browsers</td><td>“open chrome” · “open mozilla” / “open firefox” · “open chrome profile 1” ·
“open chrome with work profile” · “open firefox teaching profile”</td></tr>
<tr><td>Sites</td><td>“open youtube in chrome profile 1” · “open gmail in firefox” · “open meta ads manager in chrome profile 2” ·
“open google ads” · “open GA4” · “open tag manager” · “open DV360” · “open adsmentor dot in” · “open WhatsApp”</td></tr>
<tr><td>Search</td><td>“search DV360 line items” · “search lofi beats in chrome profile 2”</td></tr>
<tr><td>Music &amp; videos</td><td>“play Kesariya on YouTube” <span class="m">(starts the top video)</span> ·
“play Kesariya on YouTube in chrome profile 1” · “search lofi beats on YouTube” <span class="m">(results page)</span> ·
“Arijit Singh songs bajao” · “YouTube pe Kesariya chalao” · “play believer on Spotify” · “play lofi on YouTube Music” ·
“play the song Tum Hi Ho” <span class="m">(YouTube if you don't name a service)</span></td></tr>
<tr><td>Playback</td><td>“pause” · “play” / “resume” · “next song” · “previous song” · “gaana band karo”
<span class="m">(works for YouTube, Spotify and any player)</span></td></tr>
<tr><td>Close &amp; windows</td><td>“close this window” / “close it” / “band karo” · “close chrome” · “close mozilla” ·
“close the file manager” · “chrome band karo” · “minimize chrome” · “switch to firefox” · “maximize” · “full screen” ·
“show desktop” · “overview”</td></tr>
<tr><td>Browser tabs</td><td>“close tab” (also “close the current tab”, “close the tab you opened”, “close the youtube tab”, “tab band karo”) · “new tab” · “reopen closed tab” · “next tab” · “previous tab” · “go back” ·
“go forward” · “refresh”</td></tr>
<tr><td>Shika's windows</td><td>“close scratchpad” · “close Shika app” · “close the timer”</td></tr>
<tr><td>How closing works</td><td>Closing an app is the same as clicking its ✕: it can still ask you to save. “Close this window”,
tab and playback commands act on the window you were using when you held Right Alt. Saying “close youtube” or
“close gmail” closes that <i>tab</i>, not the whole browser. After “close chrome” Shika says “band kar raha hoon…” and a moment
later tells you whether it really closed. If you name something that isn't an app, he says so instead of pretending.</td></tr>
<tr><td>Profiles</td><td>Say the number or the name you see in the browser's profile picker. “Profile 1” first matches a
profile <i>named</i> Profile 1, then Chrome's “Profile 1” folder, then the 1st profile. Shika says which one he opened,
and lists your profiles if he can't find it.</td></tr>
<tr><td>System</td><td>“volume up” · “volume down” · “mute” · “lock screen” · “what time is it”</td></tr>
<tr><td>The pup</td><td>“sleep” · “play ball” · “climb” · “treat”</td></tr>
</table>

<h2>✨ Cleanup and formatting</h2>
<p>Everything you dictate is tidied before it's typed. Pick the level in this app's sidebar under <b>Cleanup</b>:</p>
<table>
<tr><td><b>✨ Shika AI</b></td><td>Shika's own AI, running on your laptop, fixes grammar, removes “um” and false starts,
applies self-corrections (<i>“at 4, no wait, 5”</i> → <i>at 5</i>), turns spoken lists into bullet points and keeps your tone,
Hinglish included. Nothing leaves the laptop. If Shika AI isn't installed or is slow, Shika uses Light instead.</td></tr>
<tr><td><b>Light (rules)</b></td><td>Instant: removes um/uh and repeated words, capitals, spacing,
spoken punctuation, “bullet point” lists, “scratch that”, day and month names.</td></tr>
<tr><td><b>Off</b></td><td>Types exactly what Whisper heard (only “new line” / “new paragraph” still work).</td></tr>
</table>
<p><b>Say these while dictating:</b> “comma” · “full stop” · “question mark” · “exclamation mark” · “colon” ·
“new line” · “new paragraph” · “bullet point …” · “open bracket … close bracket” · “scratch that” (deletes the last sentence) ·
“smiley face” · “thumbs up emoji”.</p>
<p><b>Three versions of every dictation.</b> After Shika types, a small <b>✨</b> chip appears just above your mouse
pointer for a few seconds. Hover it to see the versions and click one to swap the text you just dictated:</p>
<table>
<tr><td><b>✨ Formatted</b></td><td>Laid out for reading: steps you say with “first… then… finally…” become a numbered list,
three or more items become bullets, and a message gets its greeting and sign-off on their own lines.</td></tr>
<tr><td><b>Aa Simple</b></td><td>The same cleanup as clean, flowing sentences, no lists.</td></tr>
<tr><td><b>¶ Minimal</b></td><td>Almost exactly as you said it: only spoken punctuation, spacing and a capital at the start.</td></tr>
</table>
<p>Pick which one Shika types first in this app's sidebar under <b>FORMAT</b>. The chip appears after every dictation.
Switching works by undoing the paste, so use it right after dictating. Short sentences can look the same in two versions;
that just means there was nothing to lay out.
For example, <i>“for the workshop bring your laptop, a notebook, your Meta login and a charger”</i> becomes
“For the workshop bring:” followed by four bullets.</p>
<p><b>Shika AI can't make it worse.</b> Its version is only used if it passes checks: same meaning, about the same length,
no repeated sentences, nothing invented, and every number and time unchanged. Otherwise you get the rule-based version.
Each dictation in this app is labelled <i>SHIKA AI CLEANUP</i> or <i>LIGHT CLEANUP</i>.</p>
<p><b>Your original is kept.</b> In this app, every cleaned dictation has <i>v1 · as spoken</i> in its History menu.</p>
<p><b>Dictionary.</b> Sidebar → <b>Dictionary…</b> opens a simple text file. Add names and words Shika should always spell
your way (Mohit, Adsmentor, DV360), or fixes like <span class="k">ads mentor -&gt; Adsmentor</span>. It also helps the
speech engine hear those words correctly in the first place.</p>
<p><b>Edit any selected text by voice.</b> Select text in any app, hold <span class="k">Right Alt</span> and say:
“fix grammar” (also “fix my grammar”, “proofread”, “correct this”, “spell check”) · “make it formal” (“make it professional”) ·
“make it shorter” (“shorten it”, “make it short”, “trim it”) · “make it friendly” · “make it polite” · “make it clearer” ·
“expand this” · “turn this into bullet points” · “turn this into an email” · “summarize this” ·
“translate this to Hindi” · “rewrite this …”. “Please”, “can you” and “hey” in front are fine.
Shika copies your selection, edits it and pastes the result over it. <i>Ctrl+Z</i> brings your original back, and both
versions are kept in this app. Only “fix grammar” works without Shika AI (using the rules); the others need Shika AI.</p>
<p><b>Safety checks.</b> Your text is only replaced if the new version passes checks: numbers and times unchanged,
“shorter” really shorter, nothing invented, no chatty “Sure, here is…”. If it fails, Shika leaves your text alone and tells you.
He copies with Ctrl+Insert (safe in terminals) and only then Ctrl+C, and your own clipboard is put back afterwards.</p>
<p><b>If an edit doesn't work, the bubble says why:</b></p>
<table>
<tr><td>“select kiya hua text nahi mila”</td><td>Nothing could be copied. Select the text again, then hold Right Alt.</td></tr>
<tr><td>“clipboard padh nahi paaya”</td><td>The clipboard tool isn't answering. Open 🩺 Check my setup.</td></tr>
<tr><td>“keyboard access chahiye”</td><td>Restart the laptop once (the keyboard permission).</td></tr>
<tr><td>“iske liye Shika AI chahiye”</td><td>Shika AI isn't running: sidebar → CLEANUP → Shika AI, or run ./install.sh --with-ollama.</td></tr>
<tr><td>“Shika AI se ye nahi ho paaya”</td><td>The answer failed a safety check, so nothing changed. Try again.</td></tr>
<tr><td>“isme kuch badalna nahi tha”</td><td>The text was already fine.</td></tr>
</table>
<p>Still stuck? Sidebar → <b>🩺 Check my setup</b> → <b>Test keys + clipboard</b> shows which copy key works on your desktop.
Every step is also written to <span class="k">~/.config/shika/debug.log</span>.</p>
<p><b>Turn on Shika AI:</b> re-run the installer as <span class="k">./install.sh --with-ollama</span> (about 1 GB, once).
Shika AI runs on the free, open-source Ollama engine.</p>
<p><b>Speed</b> (sidebar → SPEED): <b>⚡ Fast</b> uses the smaller speech model and skips Shika AI unless you speak
25+ words; <b>Balanced</b> (default) uses the better model and Shika AI from 10 words; <b>🎯 Best accuracy</b> listens
more carefully and always uses Shika AI. Short, simple sentences always get the instant rules. Each dictation in this app
shows how many seconds it took, so you can compare.</p>

<h2>📝 Scratchpad</h2>
<p>A quick floating notepad. <b>＋ New</b> starts a separate note, <b>Open Shika ↗</b> jumps to that note here,
<span class="k">Esc</span> closes it. It saves as you type. Reopen within 2 hours and it continues your last note.</p>

<h2>🗂 This app</h2>
<p>Every dictation, scratchpad note and sticky note lives here as its own titled entry.
Use the sidebar to filter, the search box to find anything, and click a title to rename it.
<b>Copy</b> copies the text. <b>Delete</b> needs two clicks, and only that removes an entry for good.</p>

<h2>🕘 Versions (v1, v2, v3…)</h2>
<p>Nothing you close or erase is lost. A new version is kept automatically when you:</p>
<ul>
<li>close the scratchpad, or press ＋ New in it</li>
<li>erase a sticky note with its bin, or come back to edit it after a 10-minute break</li>
<li>press <b>Save version</b> on any entry here</li>
<li>restore an older version (your current text is kept first)</li>
</ul>
<p>Open the <b>History</b> menu above an entry to read any version, then <b>Restore</b> it if you want it back.
Up to 30 versions are kept per entry.</p>

<h2>✅ Tasks &amp; reminders widget</h2>
<p>Type, optionally pick a time chip or type a time like <i>6:45 pm</i>, then <b>＋ Task</b> or <b>⏰ Remind me</b>.
<span class="k">Enter</span> adds a reminder if you picked a time, otherwise a task. ↻ sets a repeat.
⚑ marks a task urgent (red, moved to the top).</p>
<p>Anything with a time makes Shika run to the middle of the screen and <b>bark</b>.
<b>Tap him</b> when it's done, <b>double-tap</b> to snooze 10 minutes. If the laptop was off, he catches up when you log in.
Tasks stay in the list, ticked. Reminders disappear.</p>

<h2>🗒 Sticky notes widget</h2>
<p>Add as many as you like. Each saves as you type and is mirrored here under <b>Sticky notes</b>.
The dots change the tint, <b>↗</b> opens that note here, and the bin (tap twice) erases it from the desktop.
The erased text stays here as a version.</p>

<h2>🕒 Summit Clock widget</h2>
<p>The time in tall condensed type like the wallpaper quote, with a red colon and AM/PM, the day in spaced capitals, and
the next thing Shika will bark about (a red dot when it's under 15 minutes away). Hover it for three toggles:
<b>Glass</b> (frosted card or bare text on the wallpaper), <b>24h</b>, and <b>Next</b> (show or hide the reminder line).
Drag its corner in edit mode to make it bigger. Put it in a panel instead and it becomes one line that fills the
panel's height: time, AM/PM and the day.</p>

<h2>⏱ Focus timer widget</h2>
<p><b>Start</b>/<b>Pause</b>, <b>Reset</b>, and tap the minutes to choose 25, 45, 60 or 15.
Breaks are 5 minutes, 15 after every 4 sessions. <b>⧉ Pop out</b> floats a mini timer above every app:
drag it anywhere, pause it there, close it with ✕.</p>

<h2>🐶 Pup gestures</h2>
<table>
<tr><td>Tap</td><td>pet (4 slow taps = zoomies)</td></tr>
<tr><td>Double-tap / triple-tap</td><td>trick / chappal</td></tr>
<tr><td>Hold</td><td>shake hands</td></tr>
<tr><td>Hover 5 s / scroll on him</td><td>belly rubs / chin scratches</td></tr>
<tr><td>Middle-click</td><td>treat</td></tr>
<tr><td>Right-click</td><td>menu: reminders, treat, climb, ball, sleep, 🏠 App, turn off, bark on/off</td></tr>
</table>

<h2>🐾 Characters, names and the taskbar</h2>
<p>Open 🐾 Characters in this app (or right-click the pup, then Characters and names). Pick one of 15: three pups (Shika, Frost the husky, Domino the dalmatian) and twelve other pet companions. Every character keeps its own name; type a new one and press Save name.</p>
<table>
<tr><td>“be a panda”, “switch to Frost”</td><td>change character</td></tr>
<tr><td>“call yourself Momo”</td><td>rename the one you have now</td></tr>
<tr><td>“surprise me”</td><td>a random character</td></tr>
<tr><td>“open characters”</td><td>open this page</td></tr>
</table>
<p>Your pet reads the Plasma taskbar (side, size, auto-hide) and stands on top of a bottom taskbar. Untick “Stand on my taskbar” on the Characters page to turn this off.</p>

<h2>⌨ Keyboard shortcuts (set them up once)</h2>
<p>The hold keys (<span class="k">Right Ctrl</span> dictate, <span class="k">Right Alt</span> command) work right away.
You can also give any Shika launcher entry its own key combo:</p>
<ol>
<li>Open <b>System Settings</b> → <b>Keyboard</b> → <b>Shortcuts</b>.</li>
<li>Click <b>Add New</b> (bottom of the list) → <b>Application…</b></li>
<li>Type <b>Shika</b>, pick the entry you want from the table below, click <b>OK</b>.</li>
<li>It appears in the list. Click it, then click the shortcut button and <b>press the key combo</b>.</li>
<li>Click <b>Apply</b> (bottom right). It works straight away, no restart.</li>
</ol>
<table>
<tr><td><b>Entry</b></td><td><b>Suggested keys</b></td><td><b>What it does</b></td></tr>
<tr><td>Shika Scratchpad</td><td><span class="k">Meta+Alt+N</span></td><td>Opens / closes the scratchpad</td></tr>
<tr><td>Shika</td><td><span class="k">Meta+Alt+S</span></td><td>Opens this app</td></tr>
<tr><td>Shika Dictate (toggle)</td><td><span class="k">Meta+Alt+D</span></td><td>Press once to start dictating, again to stop</td></tr>
<tr><td>Shika Command (toggle)</td><td><span class="k">Meta+Alt+C</span></td><td>Press once, say a command, press again</td></tr>
<tr><td>Shika Pup</td><td><span class="k">Meta+Alt+P</span></td><td>Wakes the dog if you turned him off</td></tr>
</table>
<p class="m">Why Meta+Alt? Plasma already uses many plain Meta combos (Meta+D shows the desktop, Meta+P switches displays).
Meta+Alt keeps all of Shika's keys together and clear of them. If a combo is taken, Plasma warns you:
pick another, or choose <i>Reassign</i> only if you don't need the old action.</p>
<p><b>To change or remove one later:</b> same page, click the entry, then click its shortcut to record a new one,
or use the <b>✕</b> next to it to clear it. To delete the entry, select it and press <b>Remove</b>. Apply.</p>
<p><b>To change the hold keys</b> (Right Ctrl / Right Alt): edit <span class="k">DICTATE_KEY</span> and
<span class="k">COMMAND_KEY</span> near the top of <span class="k">~/.local/share/shika/shika.py</span>
(for example <span class="k">"KEY_RIGHTMETA"</span>, or <span class="k">"KEY_F9"</span> if your F-keys work without Fn),
then re-run <span class="k">install.sh</span>. <span class="k">HOLD_MS</span> sets how long a hold must be (default 350 ms).</p>

<h2>💾 Where your data lives</h2>
<p><span class="k">~/.local/share/summit/</span> library.json (this app), notes.json (sticky notes), focus.json<br>
<span class="k">~/.config/shika/</span> reminders.json (tasks and reminders), settings.json<br>
Every save is written safely to disk, so crashes and power cuts don't lose work. Back up those two folders to keep everything.</p>

<h2>🛠 If something's off</h2>
<table>
<tr><td>Holding the keys does nothing</td><td>Restart the laptop once after installing, then check <span class="k">id -nG | grep -w input</span> shows <i>input</i>.</td></tr>
<tr><td>Text is copied but not typed</td><td>Same fix as above. Until then, press Ctrl+V yourself.</td></tr>
<tr><td>Nothing barks</td><td>Make sure Shika is running (launcher → Shika Pup) and “Bark out loud” is on in his right-click menu.
Use your own bark by saving a .wav at <span class="k">~/.config/shika/bark.wav</span>.</td></tr>
<tr><td>Errors</td><td>Shika: <span class="k">~/.config/shika/error.log</span> · widgets: <span class="k">journalctl --user -f | grep -i summit</span></td></tr>
<tr><td>Change hold keys or model</td><td>Edit DICTATE_KEY, COMMAND_KEY or WHISPER_MODEL at the top of
<span class="k">~/.local/share/shika/shika.py</span>, then re-run install.sh.</td></tr>
</table>
"""


# --------------------------------------------------------------------------- the painter
class PupArt:
    """Draws any character. Mixed into the live pup and into the portraits on the Characters page."""
    char_id = "shika"
    s, facing = 1.0, 1
    state, state_t, t = "idle", 0, 0
    phase = wag = 0.0
    running = False
    happy_until = dizzy_until = grumpy_until = peek_until = 0
    blink_left = 0
    tilt = 0.0
    hovered, hover_pos, alerting = False, None, None

    @property
    def look(self):
        return look_for(self.char_id)

    def rub_level(self):
        return 0

    @staticmethod
    def _bez(a, c, b, t):
        u = 1 - t
        return (u * u * a.x() + 2 * u * t * c.x() + t * t * b.x(), u * u * a.y() + 2 * u * t * c.y() + t * t * b.y())

    # ------------------------------------------------------------------ tail
    def draw_tail(self, p, K, base, ctrl, tip):
        kind = K.tail
        if kind == "none":
            return
        NB, NP = Qt.BrushStyle.NoBrush, Qt.PenStyle.NoPen
        if kind in ("puff", "stub"):
            cx, cy = self._bez(base, ctrl, tip, 0.18)
            p.setPen(pen(LINE, 2.2))
            p.setBrush(K.tailtip if kind == "puff" else K.fur)
            r = 6.4 if kind == "puff" else 4.6
            p.drawEllipse(QPointF(cx, cy), r, r)
            return
        p.setBrush(NB)
        if kind == "pig":                                    # a little curly tail
            cx, cy = base.x() - 5.5, base.y()
            sp = QPainterPath(base)
            for i in range(1, 41):
                a, r = i * 0.35, 5.5 - i * 0.1
                sp.lineTo(QPointF(cx + r * math.cos(a), cy + r * math.sin(a)))
            p.setPen(pen(LINE, 4.6))
            p.drawPath(sp)
            p.setPen(pen(K.fur, 2.4))
            p.drawPath(sp)
            return
        path = QPainterPath(base)
        path.quadTo(ctrl, tip)
        w_out, w_in = {"dog": (10, 5.5), "curl": (12, 7.5), "fox": (16, 11.5), "cat": (7, 3.6),
                       "ring": (15, 10.5), "tuft": (7, 3.6)}.get(kind, (10, 5.5))
        w_out, w_in = w_out * K.tailw, w_in * K.tailw
        p.setPen(pen(LINE, w_out))
        p.drawPath(path)
        p.setPen(pen(K.fur, w_in))
        p.drawPath(path)
        if kind == "ring":                                   # dark bands across the tail
            for t in (0.3, 0.52, 0.74):
                x, y = self._bez(base, ctrl, tip, t)
                dx = 2 * (1 - t) * (ctrl.x() - base.x()) + 2 * t * (tip.x() - ctrl.x())
                dy = 2 * (1 - t) * (ctrl.y() - base.y()) + 2 * t * (tip.y() - ctrl.y())
                d = math.hypot(dx, dy) or 1
                nx, ny = -dy / d * w_in / 2, dx / d * w_in / 2
                p.setPen(pen(K.mark, 3.0))
                p.drawLine(QPointF(x - nx, y - ny), QPointF(x + nx, y + ny))
            p.setPen(NP)
            p.setBrush(K.tailtip)
            p.drawEllipse(tip, w_in * 0.55, w_in * 0.55)
        elif kind == "fox":
            p.setPen(NP)
            p.setBrush(K.tailtip)
            p.drawEllipse(tip, 5.8, 5.8)
        elif kind == "curl":
            p.setPen(pen(LINE, 2.4))
            p.setBrush(K.fur)
            p.drawEllipse(tip, 4.6, 4.6)
            p.setPen(NP)
            p.setBrush(K.tailtip)
            p.drawEllipse(tip, 2.3, 2.3)
        elif kind == "tuft":
            p.setPen(pen(LINE, 2.0))
            p.setBrush(K.tailtip)
            p.drawEllipse(tip, 4.8, 5.4)
        elif kind == "dog":
            p.setPen(NP)
            p.setBrush(K.tailtip)
            p.drawEllipse(tip, 2.6, 2.6)

    # ------------------------------------------------------------------ whole body
    def draw_pup(self, p):
        K = self.look
        st = self.state
        happy = time.time() < self.happy_until
        line = pen(LINE, 3)
        breathe = math.sin(self.t * 0.08) * (1.2 if st == "sleep" else 0.7)
        moving = (st in ("walk", "ball") and (self.running or st == "walk")) or st in ("climb", "climbdown")
        rub2 = st == "rub" and self.rub_level() == 2

        if st == "sleep":
            pose = "sleep"
        elif rub2:
            pose = "flop"
        elif st in ("sit", "sulk", "sad", "rub", "paw", "bonk", "listen"):
            pose = "sit"
        elif st in ("bow", "stretch"):
            pose = "bow"
        elif st in ("hop", "held", "spin"):
            pose = "air"
        else:
            pose = "stand"

        # ---- tail (behind body)
        if pose == "sleep":
            base, ctrl, tip = QPointF(-25, -9), QPointF(-36, -1), QPointF(-18, -1.5)
        else:
            if pose == "flop":
                base, ang = QPointF(-26, -10), 25 + math.sin(self.wag * 1.4) * 30
            elif st in ("sulk", "sad", "bonk") and pose == "sit":
                base, ang = QPointF(-19, -10), -8 + math.sin(self.wag) * 3      # tail tucked
            elif pose == "sit":
                base, ang = QPointF(-19, -10), 12 + math.sin(self.wag) * 16
            elif pose == "bow":
                base, ang = QPointF(-24, -38), 70 + math.sin(self.wag) * 28
            else:
                base, ang = QPointF(-25, -27), 55 + math.sin(self.wag) * 22
            a = math.radians(ang)
            tip = base + QPointF(-math.cos(a) * 15, -math.sin(a) * 15)
            ctrl = base + QPointF(-12, -4)
        self.draw_tail(p, K, base, ctrl, tip)

        def leg(x, top, h, shade=False, lift=0.0):
            rect = QRectF(x - 4.6, top - lift, 9.2, h)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(K.leg_shade if shade else K.leg)
            p.drawRoundedRect(rect, 4.6, 4.6)
            p.setBrush(K.paw)
            p.drawEllipse(QPointF(x, rect.bottom() - 2.6), 4.2, 2.8)
            p.setPen(line)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect, 4.6, 4.6)

        # ---- legs + body
        if pose in ("stand", "air"):
            for i, lx in enumerate((-17, -7, 9, 18)):
                if pose == "air":
                    leg(lx, -12, 12 + (i % 2) * 2, shade=i in (1, 3))
                else:
                    lift = max(0.0, math.sin(self.phase + (i % 2) * math.pi)) * 4 if moving else 0
                    leg(lx, -13, 13, shade=i in (1, 3), lift=lift)
            body = QPainterPath()
            body.addEllipse(QPointF(-3, -22), 25, 14 + breathe)
            bob = math.sin(self.phase * 2) * 1.2 if moving else 0
            low = st in ("sniff", "eat")
            if st == "eat":
                bob += abs(math.sin(self.state_t * 0.5)) * 2.5
            elif st == "wait_treat":
                bob -= 3
            head_y = -36 + (bob if st == "eat" else 0) if low else -45 + bob
            head = QPointF(25 if low else 21, head_y)
            belly = QPointF(6, -13)
            collar = (QPointF(12, -32), 30)
            belt = (QPointF(-1, -21), -4, 26, 11)
        elif pose == "sit":
            p.setPen(line)
            p.setBrush(K.fur)
            p.drawEllipse(QPointF(-12, -10), 13, 10.5)
            body = QPainterPath()
            body.addEllipse(QPointF(-1, -27), 19, 19 + breathe)
            head = QPointF(13, -53)
            belly = QPointF(7, -24)
            collar = (QPointF(8, -39), 18)
            belt = (QPointF(0, -20), 3, 26, 11)
        elif pose == "bow":
            leg(-16, -17, 17, shade=True)
            leg(-6, -17, 17)
            p.save()
            p.translate(-3, -24)
            p.rotate(16)
            body = QPainterPath()
            body.addEllipse(QPointF(0, 0), 25, 13)
            p.setPen(line)
            p.setBrush(K.fur)
            p.drawPath(body)
            p.restore()
            body = None
            for lx in (12, 21):
                p.setPen(line)
                p.setBrush(K.leg)
                p.drawRoundedRect(QRectF(lx - 9, -6, 18, 6.5), 3.2, 3.2)
            head = QPointF(24, -28)
            belly = None
            collar = (QPointF(15, -20), 60)
            belt = (QPointF(7, -20), -14, 22, 9)
        else:  # sleep / flop
            body = QPainterPath()
            body.addEllipse(QPointF(-2, -11), 27, 11 + breathe * 0.6)
            head = QPointF(22, -18)
            belly = None
            collar = (QPointF(13, -12), 70)
            belt = (QPointF(8, -11), 0, 20, 9)

        if body is not None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(K.fur)
            p.drawPath(body)
            p.save()
            p.setClipPath(body)
            if belly is not None:
                p.setBrush(K.cream)
                p.drawEllipse(belly, 13, 7)
            if "bodystripes" in K.extras:                    # tiger stripes
                p.setPen(pen(K.mark, 3.4))
                for sx in (-18, -10, -2, 6, 14):
                    p.drawLine(QPointF(sx, -52), QPointF(sx + 3, -2))
            if "spots" in K.extras:                          # dalmatian spots
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(K.mark)
                for sx, sy, rx, ry in ((-14, -26, 3.6, 3.2), (-4, -32, 3.0, 3.4), (6, -25, 3.2, 3.0),
                                       (-9, -17, 2.6, 2.4), (14, -31, 2.6, 2.8), (1, -14, 2.4, 2.2),
                                       (-18, -19, 2.4, 2.8), (-10, -11, 3.0, 2.8), (8, -12, 3.2, 2.6),
                                       (-20, -9, 2.4, 2.2), (-2, -22, 2.4, 2.6)):
                    p.drawEllipse(QPointF(sx, sy), rx, ry)
            p.restore()
            p.setPen(line)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(body)

        if pose == "sit":
            if st == "rub":                          # happy back-leg kick
                kick = abs(math.sin(self.t * 0.55)) * 7
                p.setPen(line)
                p.setBrush(K.shade)
                p.drawEllipse(QPointF(-21 - kick * 0.3, -5 - kick), 6, 3.6)
            leg(5, -23, 23)
            if st == "paw":                          # shake hands!
                lift = min(1.0, self.state_t / 8)
                wave = math.sin(self.state_t * 0.35) * 8 if self.state_t > 10 else 0
                p.save()
                p.translate(14, -21)
                p.rotate(-115 * lift + wave)
                rect = QRectF(-4.6, 0, 9.2, 21)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(K.leg)
                p.drawRoundedRect(rect, 4.6, 4.6)
                p.setBrush(K.paw)
                p.drawEllipse(QPointF(0, rect.bottom() - 3), 4.4, 3.2)
                p.setBrush(QColor(255, 150, 160))
                for bx in (-2.2, 0, 2.2):
                    p.drawEllipse(QPointF(bx, rect.bottom() - 1.2), 0.9, 0.9)
                p.setPen(line)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(rect, 4.6, 4.6)
                p.restore()
            else:
                leg(14, -23, 23)
            p.setPen(line)
            p.setBrush(K.leg)
            p.drawEllipse(QPointF(-6, -3), 8.5, 3.8)
        elif pose == "flop":                         # paws in the air, kicking
            for i, px in enumerate((-16, -4, 6)):
                k = math.sin(self.t * 0.4 + i * 1.7) * 3
                p.setPen(line)
                p.setBrush(K.leg if i != 1 else K.leg_shade)
                p.drawEllipse(QPointF(px + k * 0.3, -25 - abs(k)), 3.8, 7)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(K.cream)
            p.drawEllipse(QPointF(2, -9), 14, 5)
        elif pose == "sleep":
            for px in (17, 29):
                p.setPen(line)
                p.setBrush(K.leg)
                p.drawEllipse(QPointF(px, -3.2), 7, 3.6)

        self.draw_belt(p, belt)

        # ---- collar
        p.save()
        p.translate(collar[0])
        p.rotate(collar[1])
        p.setPen(pen(LINE, 2.2))
        p.setBrush(K.collar)
        p.drawRoundedRect(QRectF(-3.8, -10, 7.6, 20), 3.4, 3.4)
        p.setBrush(GOLD)
        p.drawEllipse(QPointF(3.2, 7.5), 3, 3)
        p.restore()

        self.draw_head(p, head, pose, happy)

        if st == "bonk" and self.state_t < 44:
            self.draw_chappal(p, head)

    def belt_name(self):
        src = self if hasattr(self, "name_for") else getattr(getattr(self, "page", None), "pup", None)
        try:
            return clean_name(src.name_for(self.char_id)) or CHAR_BY_ID[self.char_id]["name"]
        except Exception:
            return CHAR_BY_ID.get(self.char_id, CHAR_BY_ID["shika"])["name"]

    def draw_belt(self, p, belt):
        """A red strap across the chest with the pet's name in yellow capitals."""
        if not getattr(self, "name_belt", True):
            return
        (c, ang, length, width) = belt
        text = self.belt_name().upper()
        p.save()
        p.translate(c)
        p.rotate(ang)
        p.setPen(pen(LINE, 2.0))
        p.setBrush(BELT_RED)
        p.drawRoundedRect(QRectF(-width / 2, -length / 2, width, length), 3.0, 3.0)
        p.rotate(90)                                       # the name runs down the strap
        if getattr(self, "facing", 1) < 0:                  # the whole pup is mirrored when he looks left: un-mirror the letters
            p.scale(1, -1)
        f = QFont("Inter")
        f.setBold(True)
        f.setPixelSize(max(3, int(min(width - 3.5, (length - 5) / max(1.0, len(text) * 0.66)))))
        p.setFont(f)
        p.setPen(pen(BELT_TEXT, 1))
        p.drawText(QRectF(-length / 2, -width / 2, length, width), Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    def draw_chappal(self, p, head):
        T = self.state_t
        hx, hy = head.x(), head.y()
        if T < 12:                                   # swooping down
            f = T / 12
            x, y, ang = hx + 34 - 30 * f, hy - 70 + 48 * f, -50 + 70 * f
        else:                                        # bounce off and fade
            f = min(1.0, (T - 12) / 32)
            x, y, ang = hx + 4 + 30 * f, hy - 22 - 40 * math.sin(math.pi * f * 0.8), 20 + 120 * f
        p.save()
        p.translate(x, y)
        p.rotate(ang)
        p.setOpacity(1.0 if T < 30 else max(0.0, 1 - (T - 30) / 14))
        p.setPen(pen(LINE, 2.2))
        p.setBrush(SLIPPER)
        p.drawRoundedRect(QRectF(-8, -17, 16, 34), 8, 8)
        p.setPen(pen(WHITE, 2.6))
        v = QPainterPath(QPointF(-6, -9))
        v.lineTo(0, -1)
        v.lineTo(6, -9)
        p.drawPath(v)
        p.restore()
        if 12 <= T < 22:                             # impact burst
            k = (T - 12) / 10
            p.setPen(pen(INK, 2.4))
            for i in range(8):
                a = i * math.pi / 4
                r0, r1 = 24 + 8 * k, 32 + 12 * k
                p.drawLine(QPointF(hx + math.cos(a) * r0, hy - 14 + math.sin(a) * r0 * 0.7),
                           QPointF(hx + math.cos(a) * r1, hy - 14 + math.sin(a) * r1 * 0.7))

    # ------------------------------------------------------------------ head pieces
    def _ears(self, p, K, hx, hy, tilt, flop, back):
        """Ears that sit behind the head (point, round, long) are drawn first; floppy ones go on top."""
        kind = K.ears
        if kind == "none" or (kind in ("point", "round", "long")) != back:
            return
        NP = Qt.PenStyle.NoPen
        p.setPen(pen(LINE, 2.4))
        for side in (-1, 1):
            if kind == "floppy":
                p.setBrush(K.ear)
                p.save()
                p.translate(hx + side * 16, hy - 11)
                p.rotate(-side * (tilt + flop))
                p.drawEllipse(QRectF(-5, -2, 10, 19))
                p.restore()
            elif kind == "floppy_s":
                p.setBrush(K.ear)
                p.save()
                p.translate(hx + side * 14, hy - 12)
                p.rotate(-side * (tilt * 0.7 + flop * 0.6 + 30))
                p.drawEllipse(QRectF(-4.6, -1, 9.2, 12.5))
                p.restore()
            elif kind == "point":
                spread = 6 + (tilt - 22) * 0.55 + flop * 0.3        # sleepy or upset: the ears fold outward
                p.save()
                p.translate(hx + side * 11.5, hy - 13.5)
                p.rotate(side * spread)
                tri = QPainterPath(QPointF(-7, 2))
                tri.lineTo(QPointF(0, -15))
                tri.lineTo(QPointF(7, 2))
                tri.closeSubpath()
                p.setBrush(K.ear)
                p.drawPath(tri)
                inner = QPainterPath(QPointF(-3.4, 0.5))
                inner.lineTo(QPointF(0, -9.5))
                inner.lineTo(QPointF(3.4, 0.5))
                inner.closeSubpath()
                p.setPen(NP)
                p.setBrush(K.inner)
                p.drawPath(inner)
                p.restore()
                p.setPen(pen(LINE, 2.4))
            elif kind == "round":
                r = K.ear_r
                droop = 2.5 if tilt > 30 else 0
                cx, cy = hx + side * (12 + r * 0.45 + droop * 0.6), hy - (9.5 + r * 0.65) + droop
                p.setBrush(K.ear)
                p.drawEllipse(QPointF(cx, cy), r, r)
                p.setPen(NP)
                p.setBrush(K.inner)
                p.drawEllipse(QPointF(cx, cy + 0.6), r * 0.55, r * 0.55)
                p.setPen(pen(LINE, 2.4))
            elif kind == "long":
                spread = 6 + (tilt - 14) * 0.9 + flop * 0.8
                p.save()
                p.translate(hx + side * 7.5, hy - 13)
                p.rotate(side * spread)
                p.setBrush(K.ear)
                p.drawEllipse(QRectF(-4.4, -26, 8.8, 28))
                p.setPen(NP)
                p.setBrush(K.inner)
                p.drawEllipse(QRectF(-2.3, -23, 4.6, 22))
                p.restore()
                p.setPen(pen(LINE, 2.4))

    def _nose(self, p, K, hx, hy):
        NP = Qt.PenStyle.NoPen
        p.setPen(NP)
        p.setBrush(K.nose)
        if K.face == "snout":                               # pig
            p.setPen(pen(LINE, 1.8))
            p.setBrush(K.snout)
            p.drawEllipse(QPointF(hx, hy + 6.5), 9.6, 7.2)
            p.setPen(NP)
            p.setBrush(K.nose)
            for sx in (-3.2, 3.2):
                p.drawEllipse(QPointF(hx + sx, hy + 6.5), 1.7, 2.6)
        elif "bignose" in K.extras:                         # koala
            p.drawEllipse(QPointF(hx, hy + 3.5), 5.4, 7.2)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(QPointF(hx - 1.8, hy + 1.2), 1.4, 1.9)
        elif "bulge" in K.extras:                           # frog nostrils
            for sx in (-2.6, 2.6):
                p.drawEllipse(QPointF(hx + sx, hy + 3.8), 1.1, 1.1)
        else:
            p.drawEllipse(QPointF(hx, hy + 4), 3.4, 2.4)

    def _beak(self, p, K, hx, hy, open_):
        p.setPen(pen(LINE, 1.8))
        if open_:
            p.setBrush(QColor(214, 96, 40))
            low = QPainterPath(QPointF(hx - 5, hy + 7))
            low.lineTo(QPointF(hx + 5, hy + 7))
            low.lineTo(QPointF(hx, hy + 13.5))
            low.closeSubpath()
            p.drawPath(low)
        up = 1.5 if open_ else 0
        p.setBrush(K.nose)
        top = QPainterPath(QPointF(hx - 6.4, hy + 2.2 - up))
        top.lineTo(QPointF(hx + 6.4, hy + 2.2 - up))
        top.lineTo(QPointF(hx, hy + 9.6 - up * 2.3))
        top.closeSubpath()
        p.drawPath(top)

    # ------------------------------------------------------------------ head
    def draw_head(self, p, c, pose, happy):
        K = self.look
        NP, NB = Qt.PenStyle.NoPen, Qt.BrushStyle.NoBrush
        dark = QColor(38, 20, 10)                            # the inside of a mouth, on every character
        hx, hy = c.x(), c.y()
        R = 20
        line = pen(LINE, 3)
        if abs(self.tilt) > 0.3:
            p.translate(hx, hy)
            p.rotate(self.tilt)
            p.translate(-hx, -hy)
        look = QPointF(0, 0)
        if self.hovered and self.hover_pos is not None:
            ax, ay = self.anchor()
            gx = (self.hover_pos.x() - ax) / self.s * self.facing - hx
            gy = (self.hover_pos.y() - ay) / self.s - hy
            d = math.hypot(gx, gy) or 1
            look = QPointF(gx / d * 1.4, gy / d * 1.4)
        st, now = self.state, time.time()
        hit = st == "bonk" and 12 <= self.state_t < 42
        dizzy = now < self.dizzy_until and not hit
        crying = (st == "bonk" and self.state_t >= 42) or st == "sad"
        angry = st == "sulk" or (pose == "sleep" and now < self.grumpy_until)
        bliss = st in ("rub", "eat") or pose == "flop"
        upset = hit or dizzy or crying or (angry and pose != "sleep")
        happy = (happy or bliss) and not upset
        peek = pose == "sleep" and now < self.peek_until
        adoring = ((self.hovered or st == "listen") and pose != "sleep" and not self.alerting
                   and not upset and not bliss)
        barking = self.state == "alert" and (self.t // 6) % 2 == 0
        flop = math.sin(self.wag * 0.9) * 8 if (happy or barking) else math.sin(self.t * 0.05) * 2
        if peek:
            flop += math.sin(self.t * 0.8) * 6
        tilt = 42 if (pose == "sleep" or upset) else (14 if adoring else 22)
        ear_flop = math.sin(self.t * 0.05) * 2 if upset else flop
        edx, edy = K.eye_dx, K.eye_dy
        mdy, mw = K.mdy, K.mw

        if "mane" in K.extras:                               # a lion's mane sits behind everything
            p.setPen(pen(LINE, 2.4))
            p.setBrush(K.mark)
            for k in range(10):
                a = k * math.pi / 5 + 0.3
                p.drawEllipse(QPointF(hx + math.cos(a) * 17.5, hy + math.sin(a) * 16), 9, 9)
            p.setPen(NP)
            p.drawEllipse(QPointF(hx, hy), 21, 19)
        self._ears(p, K, hx, hy, tilt, ear_flop, back=True)

        head = QPainterPath()
        head.addEllipse(QPointF(hx, hy), R, R * 0.9)
        p.setPen(NP)
        p.setBrush(K.fur)
        p.drawPath(head)
        p.save()
        p.setClipPath(head)
        p.setBrush(K.cream)
        f = K.face
        if f == "dog":
            p.drawEllipse(QPointF(hx, hy + 7), 14, 10)
        elif f == "small":
            p.drawEllipse(QPointF(hx, hy + 7.5), 9.5, 6.8)
        elif f == "cheeks":
            p.drawEllipse(QPointF(hx - 8.5, hy + 6.5), 9, 7)
            p.drawEllipse(QPointF(hx + 8.5, hy + 6.5), 9, 7)
            p.drawEllipse(QPointF(hx, hy + 10), 8, 6)
        elif f == "white":
            p.drawEllipse(QPointF(hx, hy + 3), 15.5, 14.5)
            p.drawEllipse(QPointF(hx - 8.5, hy - 4), 7.5, 8.5)
            p.drawEllipse(QPointF(hx + 8.5, hy - 4), 7.5, 8.5)
        if "blaze" in K.extras:
            p.setBrush(K.cream)
            p.drawEllipse(QPointF(hx, hy - 10), 3, 6)
        if "browdots" in K.extras:
            p.setBrush(K.cream)
            for side in (-1, 1):
                p.drawEllipse(QPointF(hx + side * 6.5, hy - 8.5), 2.5, 1.9)
        if "stripes" in K.extras:
            p.setPen(pen(K.mark, 2.2))
            for x0, x1 in ((-4, -3.5), (0, 0), (4, 3.5)):
                p.drawLine(QPointF(hx + x0, hy - 19), QPointF(hx + x1, hy - 11))
            for side in (-1, 1):
                p.drawLine(QPointF(hx + side * 19, hy - 1), QPointF(hx + side * 13, hy + 1))
                p.drawLine(QPointF(hx + side * 19, hy + 4), QPointF(hx + side * 13, hy + 5))
            p.setPen(NP)
        if "mask" in K.extras:                               # raccoon bandit mask
            p.setPen(NP)
            p.setBrush(K.mark)
            p.drawRoundedRect(QRectF(hx - 17, hy - 6.5, 34, 11.5), 5.5, 5.5)
        if "patches" in K.extras:                            # panda eye patches
            p.setPen(NP)
            p.setBrush(K.mark)
            for side in (-1, 1):
                p.save()
                p.translate(hx + side * (edx + 0.3), hy + edy + 0.5)
                p.rotate(-side * 24)
                p.drawEllipse(QPointF(0, 0), 5.6, 7.2)
                p.restore()
        if "spots" in K.extras:
            p.setPen(NP)
            p.setBrush(K.mark)
            p.drawEllipse(QPointF(hx - 12.5, hy - 7), 4.6, 5.2)
            p.drawEllipse(QPointF(hx + 13, hy + 2), 3.4, 3.8)
        p.restore()
        p.setPen(line)
        p.setBrush(NB)
        p.drawPath(head)

        if "bulge" in K.extras:                              # frog eyes pop out of the head
            for side in (-1, 1):
                bx, by = hx + side * edx, hy + edy - 0.5
                p.setPen(pen(LINE, 3))
                p.setBrush(K.fur)
                p.drawEllipse(QPointF(bx, by), 8.8, 8.8)
                p.setPen(NP)
                p.setBrush(WHITE)
                p.drawEllipse(QPointF(bx, by + 0.3), 6.2, 6.4)
        if "whiskers" in K.extras:
            p.setPen(pen(LINE, 1.1))
            p.setBrush(NB)
            for side in (-1, 1):
                for dy, lift in ((3, -4), (6.5, 0), (10, 4)):
                    p.drawLine(QPointF(hx + side * 12.5, hy + dy), QPointF(hx + side * 25, hy + dy + lift))
        self._ears(p, K, hx, hy, tilt, ear_flop, back=False)

        # eyes
        closed = pose == "sleep" or self.blink_left > 0
        EYE = K.eye
        for ex in (hx - edx, hx + edx):
            ey = hy + edy
            if hit:                                   # squeezed  > <
                d = 1 if ex < hx else -1
                p.setPen(pen(EYE, 2.3))
                p.setBrush(NB)
                v = QPainterPath(QPointF(ex - d * 3.2, ey - 3.2))
                v.lineTo(QPointF(ex + d * 3.2, ey))
                v.lineTo(QPointF(ex - d * 3.2, ey + 3.2))
                p.drawPath(v)
                continue
            if dizzy:                                 # spirally @ @
                p.setPen(pen(EYE, 1.6))
                p.setBrush(NB)
                sp = QPainterPath(QPointF(ex, ey))
                rot = self.t * 0.3
                for k in range(1, 22):
                    a = rot + k * 0.55
                    rr = k * 0.22
                    sp.lineTo(QPointF(ex + math.cos(a) * rr, ey + math.sin(a) * rr))
                p.drawPath(sp)
                continue
            if crying:                                # big wobbly teary eyes
                wob = math.sin(self.t * 0.6) * 0.3
                p.setPen(NP)
                p.setBrush(EYE)
                p.drawEllipse(QPointF(ex, ey + 0.5), 5.0 + wob, 5.4)
                p.setBrush(QColor(120, 170, 230, 170))
                p.drawEllipse(QPointF(ex, ey + 3.0), 4.2, 2.2)
                p.setBrush(K.hl)
                p.drawEllipse(QPointF(ex + 1.6, ey - 1.8), 2.0, 2.0)
                p.drawEllipse(QPointF(ex - 1.6, ey + 1.6), 1.0, 1.0)
                continue
            if angry and pose != "sleep":             # grumpy half-lidded
                p.setPen(NP)
                p.setBrush(EYE)
                p.drawEllipse(QPointF(ex, ey + 1), 3.8, 3.2)
                p.setBrush(K.hl)
                p.drawEllipse(QPointF(ex + 1.2, ey + 0.4), 1.1, 1.1)
                p.setPen(pen(EYE, 2.0))
                p.drawLine(QPointF(ex - 4.2, ey - 0.8), QPointF(ex + 4.2, ey - 0.8))
                continue
            if peek and ex > hx:
                p.setPen(NP)
                p.setBrush(EYE)
                p.drawEllipse(QPointF(ex, ey + 0.8), 3.6, 2.6)
                p.setBrush(K.hl)
                p.drawEllipse(QPointF(ex + 1.2, ey), 1.1, 1.1)
                continue
            if pose == "sleep":
                path = QPainterPath(QPointF(ex - 3.6, ey))
                path.quadTo(QPointF(ex, ey + 3.2), QPointF(ex + 3.6, ey))
                p.setPen(pen(EYE, 2))
                p.setBrush(NB)
                p.drawPath(path)
            elif happy or barking:
                path = QPainterPath(QPointF(ex - 3.6, ey + 1.5))
                path.quadTo(QPointF(ex, ey - 3.6), QPointF(ex + 3.6, ey + 1.5))
                p.setPen(pen(EYE, 2.3))
                p.setBrush(NB)
                p.drawPath(path)
            elif closed:
                p.setPen(pen(EYE, 2.2))
                p.drawLine(QPointF(ex - 3, ey), QPointF(ex + 3, ey))
            elif adoring:
                c0 = QPointF(ex, ey + 0.3) + look * 0.4
                p.setPen(NP)
                p.setBrush(EYE)
                p.drawEllipse(c0, 5.2, 5.6)
                p.setBrush(K.iris)
                p.drawEllipse(c0 + QPointF(0, 1.8), 3.6, 2.6)
                p.setBrush(K.hl)
                p.drawEllipse(c0 + QPointF(1.7, -2.0) + look * 0.5, 2.2, 2.2)
                p.drawEllipse(c0 + QPointF(-1.8, 2.0) + look * 0.5, 1.1, 1.1)
                tw = 0.5 + 0.5 * math.sin(self.t * 0.25 + ex)
                spark = QColor(255, 255, 255, int(150 + 105 * tw))
                p.setBrush(spark)
                cx, cy, k = c0.x() - 2.2, c0.y() - 2.6, 0.9 + 0.6 * tw
                star = QPainterPath(QPointF(cx, cy - 1.6 * k))
                for qx, qy in ((0.35, -0.35), (1.6, 0), (0.35, 0.35), (0, 1.6),
                               (-0.35, 0.35), (-1.6, 0), (-0.35, -0.35), (0, -1.6)):
                    star.lineTo(QPointF(cx + qx * k, cy + qy * k))
                p.drawPath(star)
            else:
                p.setPen(NP)
                p.setBrush(EYE)
                p.drawEllipse(QPointF(ex, ey) + look * 0.5, 4.2, 4.5)
                p.setBrush(K.hl)
                p.drawEllipse(QPointF(ex + 1.4, ey - 1.6) + look, 1.6, 1.6)
                p.drawEllipse(QPointF(ex - 1.3, ey + 1.5) + look, 0.8, 0.8)

        # brows
        if angry or crying:
            p.setPen(pen(EYE if ("patches" in K.extras or "mask" in K.extras) else LINE, 2.0))
            for side in (-1, 1):
                by = hy + edy - 6.5
                inner, outer = QPointF(hx + side * (edx - 4), by), QPointF(hx + side * (edx + 3.5), by)
                if angry:
                    inner += QPointF(0, 2.5)
                    outer += QPointF(0, -1.5)
                else:
                    inner += QPointF(0, -2.5)
                    outer += QPointF(0, 1.0)
                p.drawLine(inner, outer)

        # blush
        big = bliss and not upset
        blush = QColor(255, 105, 105, 190 if big else 150 if (happy or adoring) else 95)
        p.setPen(NP)
        p.setBrush(blush)
        bw, bh = (4.6, 2.8) if big else (3.4, 2.1)
        p.drawEllipse(QPointF(hx - 12.5, hy + 5.5), bw, bh)
        p.drawEllipse(QPointF(hx + 12.5, hy + 5.5), bw, bh)

        # tears
        if crying:
            for side in (-1, 1):
                for i in range(2):
                    k = ((self.t * 0.04) + i * 0.5 + (0.25 if side > 0 else 0)) % 1
                    col = QColor(TEAR)
                    col.setAlpha(int(230 * (1 - k)))
                    p.setBrush(col)
                    tx, ty = hx + side * edx + side * k * 3, hy + edy + 5 + k * 22
                    drop = QPainterPath(QPointF(tx, ty - 3))
                    drop.quadTo(QPointF(tx + 2.4, ty + 1), QPointF(tx, ty + 2.4))
                    drop.quadTo(QPointF(tx - 2.4, ty + 1), QPointF(tx, ty - 3))
                    p.drawPath(drop)

        # nose and mouth
        beak = "beak" in K.extras
        if upset:
            if beak:
                self._beak(p, K, hx, hy, open_=hit or crying)
            else:
                self._nose(p, K, hx, hy)
                p.setPen(pen(LINE, 1.7))
                p.setBrush(NB)
                m = QPainterPath(QPointF(hx - 4.4 * mw, hy + 11 + mdy))
                if crying or dizzy:                       # wobbly
                    m.quadTo(QPointF(hx - 2.2 * mw, hy + 8 + mdy), QPointF(hx, hy + 10 + mdy))
                    m.quadTo(QPointF(hx + 2.2 * mw, hy + 8 + mdy), QPointF(hx + 4.4 * mw, hy + 11 + mdy))
                elif hit:                                 # "ow!" mouth
                    p.setBrush(dark)
                    p.drawEllipse(QPointF(hx, hy + 10.5 + mdy), 2.6 * mw, 3.2)
                    m = None
                else:                                     # pout
                    m = QPainterPath(QPointF(hx - 3.2 * mw, hy + 10.5 + mdy))
                    m.quadTo(QPointF(hx, hy + 7.8 + mdy), QPointF(hx + 3.2 * mw, hy + 10.5 + mdy))
                if m is not None:
                    p.drawPath(m)
            if dizzy:
                self.draw_dizzy_stars(p, hx, hy)
            return
        opened = barking or ((happy or self.running) and pose != "sleep")
        if beak:
            self._beak(p, K, hx, hy, open_=opened)
            return
        if barking:
            p.setPen(pen(LINE, 1.8))
            p.setBrush(dark)
            p.drawEllipse(QPointF(hx, hy + 10.5 + mdy), 4.2 * mw, 3.8)
            p.setPen(NP)
            p.setBrush(RED)
            p.drawEllipse(QPointF(hx, hy + 12.4 + mdy), 2.6 * mw, 1.6)
        elif opened:
            p.setPen(pen(LINE, 1.5))
            p.setBrush(RED)
            p.drawRoundedRect(QRectF(hx - 2.6 * mw, hy + 8 + mdy, 5.4 * mw, 7), 2.7, 2.7)
        self._nose(p, K, hx, hy)
        if not barking:
            mouth = QPainterPath(QPointF(hx - 4.6 * mw, hy + 7 + mdy))
            mouth.quadTo(QPointF(hx - 2.3 * mw, hy + 9.8 + mdy), QPointF(hx, hy + 7 + mdy))
            mouth.quadTo(QPointF(hx + 2.3 * mw, hy + 9.8 + mdy), QPointF(hx + 4.6 * mw, hy + 7 + mdy))
            p.setPen(pen(LINE, 1.7))
            p.setBrush(NB)
            p.drawPath(mouth)
        if "teeth" in K.extras and not opened:            # bunny front teeth
            p.setPen(pen(LINE, 1.3))
            p.setBrush(WHITE)
            p.drawRoundedRect(QRectF(hx - 2.2, hy + 8.6, 4.4, 4.6), 1.2, 1.2)

    def draw_dizzy_stars(self, p, hx, hy):
        p.setPen(pen(LINE, 1.2))
        p.setBrush(GOLD)
        for i in range(3):
            a = self.t * 0.18 + i * 2 * math.pi / 3
            cx, cy = hx + math.cos(a) * 17, hy - 24 + math.sin(a) * 4.5
            k = 3.4 if math.sin(a) > 0 else 2.6
            star = QPainterPath(QPointF(cx, cy - k))
            for j in range(1, 10):
                ang = -math.pi / 2 + j * math.pi / 5
                rr = k if j % 2 == 0 else k * 0.45
                star.lineTo(cx + math.cos(ang) * rr, cy + math.sin(ang) * rr)
            star.closeSubpath()
            p.drawPath(star)


class CharCard(PupArt, QPushButton):
    """One character on the Characters page: a small live portrait you click to pick."""

    def __init__(self, cid, page):
        QPushButton.__init__(self)
        self.char_id, self.page = cid, page
        self.s, self.state, self.t = 1.1, "sit", 0
        self.happy_until = time.time() + 10 ** 7
        self.setObjectName("charcard")
        self.setCheckable(True)
        self.setFixedSize(122, 136)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.clicked.connect(lambda _=False: page.choose(cid))

    def anchor(self):
        return self.width() / 2, 94

    def tick(self):
        self.t += 1
        self.wag = self.t * 0.2
        if self.t % 80 == 0:
            self.blink_left = 4
        elif self.blink_left > 0:
            self.blink_left -= 1
        self.update()

    def enterEvent(self, e):
        self.hovered = True
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hovered, self.hover_pos = False, None
        super().leaveEvent(e)

    def mouseMoveEvent(self, e):
        self.hover_pos = e.position()
        super().mouseMoveEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.save()
        p.translate(self.width() / 2, 94)
        p.scale(self.s, self.s)
        self.draw_pup(p)
        p.restore()
        f = QFont()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(242, 242, 243))
        p.drawText(QRectF(0, 101, self.width(), 18), Qt.AlignmentFlag.AlignCenter, self.page.pup.name_for(self.char_id))
        f.setBold(False)
        f.setPixelSize(10)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 120))
        p.drawText(QRectF(0, 118, self.width(), 14), Qt.AlignmentFlag.AlignCenter, CHAR_BY_ID[self.char_id]["species"])
        p.end()


class CharacterPage(QFrame):
    """The 🐾 Characters page of the app: pick one of 15, give each its own name, taskbar setting."""

    def __init__(self, pup):
        super().__init__()
        self.pup = pup
        self.cards = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 24, 32, 18)
        lay.setSpacing(10)
        scroll.setWidget(body)

        title = QLabel("Characters")
        title.setStyleSheet("font-size: 20px; font-weight: 800;")
        lay.addWidget(title)
        sub = QLabel("Click a card to change who lives on your screen. Every character can have its own name.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        def section(text):
            lb = QLabel(text)
            lb.setObjectName("caps")
            lay.addSpacing(6)
            lay.addWidget(lb)
            grid = QGridLayout()
            grid.setSpacing(10)
            grid.setColumnStretch(6, 1)
            lay.addLayout(grid)
            return grid

        self.grids = []
        for text, group, per_row in (("PUPS", "pup", 6), ("MORE BUDDIES", "buddy", 6)):
            grid = section(text)
            made = []
            for i, c in enumerate([c for c in CHARACTERS if c["group"] == group]):
                card = CharCard(c["id"], self)
                self.cards[c["id"]] = card
                made.append(card)
                grid.addWidget(card, i // per_row, i % per_row)
            self.grids.append((grid, made))
        self._per = 6

        lay.addSpacing(8)
        self.name_title = QLabel("")
        self.name_title.setObjectName("caps")
        lay.addWidget(self.name_title)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(MAX_NAME)
        self.name_edit.returnPressed.connect(self.save_name)
        row.addWidget(self.name_edit, 1)
        for label, fn, oid in (("Save name", self.save_name, "primary"), ("Reset", self.reset_name, ""),
                               ("🎲  Surprise me", self.surprise, "")):
            b = QPushButton(label)
            if oid:
                b.setObjectName(oid)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, f=fn: f())
            row.addWidget(b)
        lay.addLayout(row)
        hint = QLabel("Or say it: “be a panda”, “switch to Frost”, “call yourself Momo”, “surprise me”, “open characters”.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        lay.addSpacing(10)
        cap = QLabel("TASKBAR")
        cap.setObjectName("caps")
        lay.addWidget(cap)
        self.aware = QCheckBox("Stand on my taskbar")
        self.aware.toggled.connect(lambda on: self.pup.set_taskbar_aware(on))
        lay.addWidget(self.aware)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addStretch(1)

        self.timer = QTimer(self, timeout=self.tick)

    def tick(self):
        for card in self.cards.values():
            card.tick()

    def reflow(self):
        """As many cards per row as fit, so the grid never runs off the right edge of the page."""
        per = max(2, min(6, (self.width() - 64 + 10) // 132))
        if per == self._per:
            return
        self._per = per
        for grid, cards in self.grids:
            for card in cards:
                grid.removeWidget(card)
            for i, card in enumerate(cards):
                grid.addWidget(card, i // per, i % per)

    def resizeEvent(self, e):
        self.reflow()
        super().resizeEvent(e)

    def showEvent(self, e):
        self.refresh()
        self.timer.start(90)
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def choose(self, cid):
        self.pup.set_character(cid)
        self.refresh()

    def save_name(self):
        n = self.pup.set_pet_name(self.name_edit.text())
        self.pup.speak(f"mera naam {n} hai 🐾", 3)
        self.refresh()

    def reset_name(self):
        self.pup.set_pet_name("")
        self.refresh(force=True)

    def surprise(self):
        self.pup.random_character()
        self.refresh()

    def refresh(self, force=False):
        pup = self.pup
        spec = CHAR_BY_ID.get(pup.char_id) or CHAR_BY_ID["shika"]
        for cid, card in self.cards.items():
            card.setChecked(cid == pup.char_id)
            card.update()
        self.name_title.setText(f"NAME OF YOUR {spec['species'].upper()}")
        self.name_edit.setPlaceholderText(spec["name"])
        if force or not self.name_edit.hasFocus():
            self.name_edit.setText(pup.pet_name())
        self.aware.blockSignals(True)
        self.aware.setChecked(bool(pup.settings.get("taskbar_aware", True)))
        self.aware.blockSignals(False)
        self.status.setText(pup.panel_status())


class Dashboard(QWidget):
    """The Shika app: every dictation, scratchpad note and sticky note, with versions,
    plus a built-in guide."""
    FILTERS = (("All", None), ("🎤  Dictations", "dictation"), ("📝  Notes", "note"),
               ("🗒  Sticky notes", "sticky"), ("🐾  Characters", "characters"), ("📖  Guide", "guide"))
    ICONS = {"dictation": "🎤", "note": "📝", "sticky": "🗒"}
    KIND_NAMES = {"dictation": "Dictation", "note": "Scratchpad note", "sticky": "Sticky note"}

    def __init__(self, lib, pup):
        super().__init__(None, Qt.WindowType.Window)
        self.lib, self.pup = lib, pup
        self.kind, self.current, self.loading, self.viewing = None, None, False, 0
        self.setWindowTitle("Shika")
        self.setStyleSheet(GLASS_CSS + "#shell { border-radius: 0; border: none; }"
                           "QComboBox { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,22);"
                           " border-radius: 10px; padding: 4px 10px; font-size: 12px; }"
                           "QComboBox QAbstractItemView { background: #141416; color: #f2f2f3;"
                           " selection-background-color: #e11d2e; }"
                           "QTextBrowser { background: transparent; border: none; }"
                           "QPushButton { min-height: 20px; } QComboBox { min-height: 20px; }"
                           "QPushButton#nav { min-height: 22px; }"
                           "QScrollArea { background: transparent; border: none; }"
                           "QScrollArea > QWidget > QWidget { background: transparent; }"
                           "QPushButton#charcard { background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,22);"
                           " border-radius: 14px; }"
                           "QPushButton#charcard:hover { border-color: rgba(255,255,255,80); }"
                           "QPushButton#charcard:checked { border: 2px solid #e11d2e; background: rgba(225,29,46,30); }")
        self.resize(1180, 800)
        self.setMinimumSize(1000, 600)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        shell = QFrame()
        shell.setObjectName("shell")
        outer.addWidget(shell)
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # ---- sidebar ----
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(236)
        side_out = QVBoxLayout(side)
        side_out.setContentsMargins(0, 0, 0, 0)
        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side_out.addWidget(side_scroll)
        side_in = QWidget()
        s = QVBoxLayout(side_in)
        s.setContentsMargins(20, 24, 20, 20)
        s.setSpacing(8)
        side_scroll.setWidget(side_in)
        brand = QLabel("SHIKA")
        brand.setObjectName("brand")
        s.addWidget(brand)
        sub = QLabel(f"YOUR VOICE NOTEBOOK  ·  v{VERSION}")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        s.addWidget(sub)
        s.addSpacing(14)
        self.nav = []
        for label, kind in self.FILTERS:
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setMinimumHeight(38)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=kind: self.set_filter(k))
            s.addWidget(b)
            self.nav.append((b, kind))
        self.nav[0][0].setChecked(True)
        s.addSpacing(16)
        self.stat_words = QLabel("0")
        self.stat_words.setObjectName("stat")
        s.addWidget(self.stat_words)
        lbl = QLabel("words dictated")
        lbl.setObjectName("muted")
        s.addWidget(lbl)
        self.stat_more = QLabel("")
        self.stat_more.setObjectName("muted")
        self.stat_more.setWordWrap(True)
        s.addWidget(self.stat_more)
        s.addSpacing(14)
        s.addStretch(1)
        new = QPushButton("＋  New note")
        new.setObjectName("primary")
        new.setMinimumHeight(38)
        new.clicked.connect(self.new_note)
        s.addWidget(new)
        pad = QPushButton("Quick scratchpad")
        pad.setMinimumHeight(36)
        pad.clicked.connect(lambda: self.pup.scratch.toggle())
        s.addWidget(pad)
        s.addSpacing(8)
        cl = QLabel("CLEANUP")
        cl.setObjectName("muted")
        s.addWidget(cl)
        self.cleanup = QComboBox()
        for label, key in (("✨ Shika AI", "auto"), ("Light rules", "light"), ("Off", "off")):
            self.cleanup.addItem(label, key)
        self.cleanup.setCurrentIndex(max(0, self.cleanup.findData(self.pup.settings.get("cleanup", "auto"))))
        self.cleanup.currentIndexChanged.connect(lambda i: self.pup.set_cleanup(self.cleanup.itemData(i)))
        s.addWidget(self.cleanup)
        s.addSpacing(4)
        fl = QLabel("FORMAT")
        fl.setObjectName("muted")
        s.addWidget(fl)
        self.fmt = QComboBox()
        for label, key in (("✨ Formatted", "formatted"), ("Aa Simple", "simple"), ("¶ Minimal", "minimal")):
            self.fmt.addItem(label, key)
        self.fmt.setCurrentIndex(max(0, self.fmt.findData(self.pup.settings.get("format", "formatted"))))
        self.fmt.currentIndexChanged.connect(lambda i: self.pup.set_format(self.fmt.itemData(i)))
        s.addWidget(self.fmt)
        s.addSpacing(4)
        sl = QLabel("SPEED")
        sl.setObjectName("muted")
        s.addWidget(sl)
        self.speed = QComboBox()
        for label, key in (("⚡ Fast", "fast"), ("Balanced", "balanced"), ("🎯 Best accuracy", "best")):
            self.speed.addItem(label, key)
        self.speed.setCurrentIndex(max(0, self.speed.findData(self.pup.settings.get("speed", "balanced"))))
        self.speed.currentIndexChanged.connect(lambda i: self.pup.set_speed(self.speed.itemData(i)))
        s.addWidget(self.speed)
        s.addSpacing(8)
        dic = QPushButton("Dictionary…")
        dic.setMinimumHeight(36)
        dic.clicked.connect(lambda: (load_dictionary(), open_target(DICTIONARY_FILE)))
        s.addWidget(dic)
        chk = QPushButton("🩺  Check my setup")
        chk.setMinimumHeight(36)
        chk.clicked.connect(lambda: self.pup.open_setup_check())
        s.addWidget(chk)
        s.addSpacing(8)
        self.wake_btn = QPushButton("🐶  Wake the pup")
        self.wake_btn.setMinimumHeight(36)
        self.wake_btn.clicked.connect(lambda: (self.pup.wake_from_launcher(), self.refresh()))
        s.addWidget(self.wake_btn)
        row.addWidget(side)

        # ---- pages: 0 = notebook, 1 = guide, 2 = characters ----
        self.pages = QStackedWidget()
        row.addWidget(self.pages, 1)
        book = QWidget()
        brow = QHBoxLayout(book)
        brow.setContentsMargins(0, 0, 0, 0)
        brow.setSpacing(0)
        self.pages.addWidget(book)
        guide = QTextBrowser()
        guide.setOpenExternalLinks(True)
        guide.setHtml(GUIDE_HTML)
        guide.setContentsMargins(0, 0, 0, 0)
        gwrap = QFrame()
        gl = QVBoxLayout(gwrap)
        gl.setContentsMargins(32, 24, 32, 18)
        gl.addWidget(guide)
        self.pages.addWidget(gwrap)
        self.chars_page = CharacterPage(self.pup)
        self.pages.addWidget(self.chars_page)

        mid = QFrame()
        mid.setObjectName("mid")
        mid.setFixedWidth(320)
        m = QVBoxLayout(mid)
        m.setContentsMargins(14, 20, 8, 14)
        m.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search everything…")
        self.search.textChanged.connect(self.refresh)
        m.addWidget(self.search)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.on_pick)
        m.addWidget(self.list, 1)
        brow.addWidget(mid)

        ed = QFrame()
        e = QVBoxLayout(ed)
        e.setContentsMargins(28, 22, 28, 18)
        e.setSpacing(10)
        top = QVBoxLayout()
        top.setSpacing(8)
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.meta.setWordWrap(True)
        top.addWidget(self.meta)
        self.history = QComboBox()
        self.history.setMinimumWidth(0)
        self.history.activated.connect(self.on_history)
        top.addWidget(self.history)
        e.addLayout(top)
        self.banner = QLabel("")
        self.banner.setObjectName("red")
        self.banner.setWordWrap(True)
        e.addWidget(self.banner)
        self.title = QLineEdit()
        self.title.setObjectName("bigtitle")
        self.title.setPlaceholderText("Untitled")
        self.title.textChanged.connect(self.on_edit)
        e.addWidget(self.title)
        self.body = QPlainTextEdit()
        self.body.textChanged.connect(self.on_edit)
        e.addWidget(self.body, 1)
        self.empty = QLabel("Nothing here yet.\nDictate with Right Ctrl, or start a new note.\n\n"
                            "New here? Open 📖 Guide in the sidebar.")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e.addWidget(self.empty, 1)
        self.count = QLabel("")
        self.count.setObjectName("muted")
        e.addWidget(self.count)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addStretch(1)
        self.restore_btn = QPushButton("Restore this version")
        self.restore_btn.setObjectName("primary")
        self.restore_btn.clicked.connect(self.restore_version)
        self.back_btn = QPushButton("Back to current")
        self.back_btn.clicked.connect(lambda: self.view_version(0))
        self.snap_btn = QPushButton("Save version")
        self.snap_btn.clicked.connect(self.save_version)
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self.copy_entry)
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("danger")
        self.del_btn.clicked.connect(self.delete_entry)
        for b in (self.restore_btn, self.back_btn, self.snap_btn, self.copy_btn, self.del_btn):
            b.setMinimumHeight(34)
            bar.addWidget(b)
        e.addLayout(bar)
        brow.addWidget(ed, 1)
        self.editor_parts = (self.meta, self.history, self.title, self.body, self.copy_btn,
                             self.del_btn, self.count, self.snap_btn)

        self.save_timer = QTimer(self, singleShot=True, timeout=self.save_now)
        self.del_timer = QTimer(self, singleShot=True, timeout=self.reset_delete)
        self.confirm = False
        lib.changed.connect(self.on_lib_changed)
        self.show_editor(None)

    # ---- list ----
    def set_filter(self, kind):
        for b, k in self.nav:
            b.setChecked(k == kind)
        if kind == "guide":
            self.save_now()
            self.pages.setCurrentIndex(1)
            return
        if kind == "characters":
            self.save_now()
            self.pages.setCurrentIndex(2)
            self.chars_page.refresh()
            return
        self.pages.setCurrentIndex(0)
        self.kind = kind
        self.refresh()

    def visible_entries(self):
        q = self.search.text().strip().lower()
        out = [e for e in self.lib.entries if (self.kind is None or e["kind"] == self.kind)
               and (not q or q in (e.get("title", "") + " " + e["text"]).lower())]
        return sorted(out, key=lambda e: e["updated"], reverse=True)

    def on_lib_changed(self):
        self.refresh()
        e = self.lib.get(self.current) if self.current else None
        if e and self.viewing == 0 and not self.save_timer.isActive() and not self.body.hasFocus() \
                and not self.title.hasFocus() and (e["text"] != self.body.toPlainText()
                                                   or e.get("title", "") != self.title.text()):
            self.show_editor(e)                    # changed elsewhere (sticky note, scratchpad)
        elif e:
            self.fill_history(e)

    def refresh(self):
        import html
        n, words, week, notes = self.lib.stats()
        self.stat_words.setText(f"{words:,}")
        self.stat_more.setText(f"{week:,} this week · {n} dictations · {notes} notes")
        self.wake_btn.setVisible(self.pup.isHidden())
        self.list.blockSignals(True)
        self.list.clear()
        pick = None
        for e in self.visible_entries():
            icon = self.ICONS.get(e["kind"], "📝")
            snippet = " ".join(e["text"].split())[:80] or "empty"
            nv = len(e.get("versions", []))
            vtag = f" · v{nv + 1}" if nv else ""
            gone = " · erased from desktop" if e.get("removed") else ""
            def clip(t, n):
                t = " ".join(str(t).split())
                return t if len(t) <= n else t[:n - 1].rstrip() + "…"
            when = short_when(e["updated"])
            title = html.escape(clip(Library.title_of(e), 26))
            second = html.escape(clip(f"{when}{vtag}{gone} · {snippet}", 40))
            lbl = QLabel(f"<div style='font-weight:700'>{icon}&nbsp; {title}</div>"
                         f"<div style='color:rgba(255,255,255,0.5);font-size:11px'>{second}</div>")
            lbl.setWordWrap(False)
            lbl.setContentsMargins(10, 8, 10, 8)
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, e["id"])
            it.setSizeHint(QSize(0, 66))
            self.list.addItem(it)
            self.list.setItemWidget(it, lbl)
            if e["id"] == self.current:
                pick = it
        if pick:
            self.list.setCurrentItem(pick)
        self.list.blockSignals(False)
        if self.current and not self.lib.get(self.current):
            self.show_editor(None)

    def on_pick(self, item, _prev=None):
        self.save_now()
        self.show_editor(self.lib.get(item.data(Qt.ItemDataRole.UserRole)) if item else None)

    # ---- editor ----
    def show_editor(self, e):
        self.loading = True
        self.current = e["id"] if e else None
        self.viewing = 0
        for w in self.editor_parts:
            w.setVisible(e is not None)
        self.restore_btn.hide()
        self.back_btn.hide()
        self.empty.setVisible(e is None)
        self.body.setReadOnly(False)
        self.title.setReadOnly(False)
        if e:
            made = datetime.fromtimestamp(e["created"]).strftime("%a %d %b %Y, %I:%M %p")
            how = {"smart": "  ·  SHIKA AI CLEANUP", "light": "  ·  LIGHT CLEANUP",
                   "off": "  ·  NO CLEANUP"}.get(e.get("cleanup"), "")
            if e.get("secs") is not None:
                how += f"  ·  {e['secs']:.1f} s"
            self.meta.setText(f"{self.KIND_NAMES.get(e['kind'], 'Note').upper()}  ·  {made}{how}")
            self.banner.setText("Erased from the desktop. Everything is still here, and in History."
                                if e.get("removed") else "")
            self.banner.setVisible(bool(e.get("removed")))
            self.title.setText(e.get("title", ""))
            self.title.setPlaceholderText(auto_title(e["text"]))
            self.body.setPlainText(e["text"])
            self.count.setText(f"{len(e['text'].split())} words")
            self.fill_history(e)
        else:
            self.banner.hide()
        self.reset_delete()
        self.loading = False

    def fill_history(self, e):
        self.history.blockSignals(True)
        self.history.clear()
        vs = e.get("versions", [])
        self.history.addItem(f"Current · v{len(vs) + 1}" if vs else "History · no older versions", 0)
        for v in reversed(vs):
            when = datetime.fromtimestamp(v["saved"]).strftime("%d %b, %I:%M %p").lstrip("0")
            self.history.addItem(f"v{v['n']} · {v.get('reason', '')} · {when}", v["n"])
        idx = self.history.findData(self.viewing)
        self.history.setCurrentIndex(max(0, idx))
        self.history.blockSignals(False)

    def on_history(self, idx):
        self.view_version(self.history.itemData(idx) or 0)

    def view_version(self, n):
        e = self.lib.get(self.current) if self.current else None
        if not e:
            return
        if n == 0:
            self.show_editor(e)
            return
        v = next((v for v in e.get("versions", []) if v["n"] == n), None)
        if not v:
            return
        self.save_now()
        self.loading = True
        self.viewing = n
        self.title.setText(v.get("title", ""))
        self.body.setPlainText(v["text"])
        self.title.setReadOnly(True)
        self.body.setReadOnly(True)
        self.banner.setText(f"Viewing v{n} ({v.get('reason', '')}). Read-only.")
        self.banner.show()
        self.count.setText(f"{len(v['text'].split())} words")
        self.restore_btn.show()
        self.back_btn.show()
        self.snap_btn.hide()
        self.del_btn.hide()
        self.loading = False

    def restore_version(self):
        if self.current and self.viewing:
            n = self.viewing
            self.lib.restore(self.current, n)
            self.show_editor(self.lib.get(self.current))

    def save_version(self):
        self.save_now()
        if self.current and self.lib.snapshot(self.current, "saved by you"):
            self.snap_btn.setText("Saved ✓")
        else:
            self.snap_btn.setText("No changes")
        QTimer.singleShot(1500, lambda: self.snap_btn.setText("Save version"))

    def on_edit(self):
        if self.loading or not self.current or self.viewing:
            return
        self.count.setText(f"{len(self.body.toPlainText().split())} words")
        self.save_timer.start(600)

    def save_now(self):
        self.save_timer.stop()
        if self.current and self.viewing == 0 and self.lib.get(self.current):
            self.lib.update(self.current, title=self.title.text().strip(), text=self.body.toPlainText())

    def new_note(self):
        self.save_now()
        e = self.lib.add("note", "", "")
        self.current = e["id"]
        if self.kind not in (None, "note"):
            self.set_filter(None)
        else:
            self.pages.setCurrentIndex(0)
            self.refresh()
        self.show_editor(e)
        self.title.setFocus()

    def copy_entry(self):
        QApplication.clipboard().setText(self.body.toPlainText())
        self.copy_btn.setText("Copied ✓")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy"))

    def delete_entry(self):
        if not self.current:
            return
        if not self.confirm:
            self.confirm = True
            self.del_btn.setText("Click again: deletes all versions")
            self.del_timer.start(3000)
            return
        row = self.list.currentRow()
        self.save_timer.stop()
        gone = self.current
        self.current = None
        self.lib.delete(gone)
        if self.list.count():
            self.list.setCurrentRow(min(row, self.list.count() - 1))
        else:
            self.show_editor(None)

    def reset_delete(self):
        self.confirm = False
        self.del_btn.setText("Delete")

    def show_app(self, eid=None, retry=True):
        self.lib.poll()
        if eid and not self.lib.get(eid) and retry:       # a sticky note may still be saving
            QTimer.singleShot(900, lambda: self.show_app(eid, retry=False))
            return
        if eid and self.lib.get(eid):
            self.save_now()
            self.search.clear()
            self.current = eid
            self.set_filter(None)
            self.show_editor(self.lib.get(eid))
        else:
            if self.pages.currentIndex() == 0:
                self.refresh()
            if self.current is None and self.list.count():
                self.list.setCurrentRow(0)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, e):
        self.save_now()
        e.ignore()
        self.hide()


class SetupCheck(QWidget):
    """🩺 Check my setup: says what works and what doesn't on THIS desktop, with the fix for each.
    The passive checks change nothing. The two test buttons really press keys and close a test window."""
    def __init__(self, pup):
        super().__init__(None, Qt.WindowType.Window)
        self.pup = pup
        self.results, self.active = [], []
        self.close_queue, self.close_results, self.test_win = [], {}, None
        self.setWindowTitle("Shika · Check my setup")
        self.setStyleSheet(GLASS_CSS + "#shell { border-radius: 0; border: none; } QTextBrowser { background: transparent; border: none; }")
        self.resize(720, 680)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("shell")
        outer.addWidget(card)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 16)
        lay.setSpacing(10)
        caps = QLabel("—  CHECK MY SETUP")
        caps.setObjectName("caps")
        lay.addWidget(caps)
        self.view = QTextBrowser()
        lay.addWidget(self.view, 1)
        hint = QLabel("Key test box (the test types into this):")
        hint.setObjectName("muted")
        lay.addWidget(hint)
        self.field = QLineEdit()
        self.field.setText("hello shika")
        lay.addWidget(self.field)
        row = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("muted")
        row.addWidget(self.status, 1)
        for label, fn, name in (("Re-check", self.run_passive, ""), ("Test keys + clipboard", self.test_keys, ""),
                                ("Test closing", self.test_close, ""), ("Copy report", self.copy_report, "primary")):
            b = QPushButton(label)
            b.setObjectName(name)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, f=fn: f())
            row.addWidget(b)
        lay.addLayout(row)

    # ---- passive checks
    def run_passive(self):
        self.status.setText("checking…")

        def work():
            res = self.pup.run_diagnostics()
            self.pup.ui_call.emit(lambda: self.show_results(res))
        threading.Thread(target=work, daemon=True).start()

    def show_results(self, res):
        self.results = res
        bad = sum(1 for r in res if r["ok"] is False)
        self.status.setText("everything passed ✅" if not bad else f"{bad} thing(s) need attention")
        dlog("setup check: " + "; ".join(f"{'OK' if r['ok'] else 'FAIL' if r['ok'] is False else 'info'} {r['name']}" for r in res))
        self.render()

    def set_active(self, name, ok, detail="", fix=""):
        self.active = [r for r in self.active if r["name"] != name] + [{"name": name, "ok": ok, "detail": detail, "fix": fix}]
        dlog(f"setup test: {'OK' if ok else 'FAIL' if ok is False else 'skipped'} {name} {detail}")
        self.render()

    def render(self):
        import html as H
        rows = []
        for r in self.results + self.active:
            icon = {True: "✅", False: "❌", None: "ℹ️"}[r["ok"]]
            det = (f"<div style='color:rgba(255,255,255,0.55);font-size:11px'>{H.escape(r.get('detail') or '')}</div>"
                   if r.get("detail") else "")
            fix = (f"<div style='color:#ff8a93;font-size:12px'>Fix: {H.escape(r['fix'])}</div>"
                   if r["ok"] is False and r.get("fix") else "")
            rows.append(f"<p style='margin:7px 0'>{icon}&nbsp; <b>{H.escape(r['name'])}</b>{det}{fix}</p>")
        body = "".join(rows) or "<p style='color:rgba(255,255,255,0.5)'>Checking…</p>"
        self.view.setHtml(f"<div style='font-size:13px'>{body}</div>")

    def report_text(self):
        lines = [f"Shika {VERSION} · {os.environ.get('XDG_SESSION_TYPE', '?')} · {time.strftime('%Y-%m-%d %H:%M')}"]
        for r in self.results + self.active:
            mark = {True: "OK  ", False: "FAIL", None: "info"}[r["ok"]]
            lines.append(f"[{mark}] {r['name']}" + (f" - {r['detail']}" if r.get("detail") else "")
                         + (f" - FIX: {r['fix']}" if r["ok"] is False and r.get("fix") else ""))
        return "\n".join(lines)

    def copy_report(self):
        QApplication.clipboard().setText(self.report_text())
        self.status.setText("report copied: paste it to Claude ✓")

    # ---- active test 1: do key presses reach an app, and does the clipboard follow?
    def test_keys(self):
        name = "Keys reach apps: select all + copy in the box below"
        p = self.pup
        if not p.typer.ui:
            self.set_active(name, False, p.typer.error or "no keyboard access", "Restart the laptop once after installing.")
            return
        if not clip_tools_ok():
            self.set_active(name, False, "wl-clipboard is not installed", "sudo apt install wl-clipboard")
            return
        self.field.setText("hello shika")
        self.field.setFocus()
        self.activateWindow()
        orig = p.typer.clip_get()
        marker = f"shika-key-test-{int(time.time())}"
        p.typer.clip_set(marker)
        self.status.setText("pressing Ctrl+A, then Ctrl+Insert (and Ctrl+C if needed)…")
        keys = [(["KEY_LEFTCTRL", "KEY_INSERT"], "Ctrl+Insert"), (["KEY_LEFTCTRL", "KEY_C"], "Ctrl+C")]

        def press(i=0):
            if i == 0:
                p.typer.combo(["KEY_LEFTCTRL", "KEY_A"])
                time.sleep(0.08)
            sent = p.typer.combo(keys[i][0])
            QTimer.singleShot(600, lambda: check(sent, i))

        def check(sent, i):
            rc, out, err = clip_read()
            got = out if rc == 0 else ""
            ok = got == "hello shika"
            if not ok and i == 0:                            # Shika's edit command does the same: second copy key
                p.typer.clip_set(marker)
                press(1)
                return
            self.set_active(name, ok,
                            f"worked: copying with {keys[i][1]} put the box's text on the clipboard" if ok else
                            f"keys sent={sent}, clipboard now: {got[:40]!r}",
                            "If keys were sent but nothing arrived, tell Claude: the compositor is ignoring Shika's virtual keyboard.")
            p._clip_restore(orig)
            self.status.setText("key test done")
        QTimer.singleShot(350, press)

    # ---- active test 2: really close a test window in each way
    def test_close(self):
        self.close_queue = ["script", "shortcut", "altf4"]
        self.close_results = {}
        self.status.setText("closing test windows…")
        self._next_close()

    def _next_close(self):
        if not self.close_queue:
            self._finish_close()
            return
        kind = self.close_queue.pop(0)
        w = QWidget(None, Qt.WindowType.Window)
        w.setWindowTitle("Shika close test")
        w.resize(300, 90)
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Shika is testing: this window should close by itself."))
        self.test_win = w
        w.show()
        w.raise_()
        w.activateWindow()
        QTimer.singleShot(900, lambda: self._close_fire(kind, w))

    def _close_fire(self, kind, w):
        if kind != "script" and not w.isActiveWindow():
            self.close_results[kind] = None                 # never risk closing some other window: skip
            w.close()
            QTimer.singleShot(200, self._next_close)
            return
        if kind == "script":
            kwin_windows("shika close test", "close")
        elif kind == "shortcut":
            kwin_shortcut("Window Close")
        else:
            self.pup.typer.combo(KEY_FALLBACK["Window Close"])
        QTimer.singleShot(1600, lambda: self._close_check(kind, w))

    def _close_check(self, kind, w):
        gone = not w.isVisible()
        self.close_results[kind] = gone
        if not gone:
            w.close()
        self._next_close()

    def _finish_close(self):
        r = self.close_results
        fix_script = "Shika then closes apps by quitting them politely instead (SIGTERM). Send Claude the copied report."
        self.set_active("Close an app by name ('close chrome') via KDE scripting", r.get("script"),
                        "the test window closed" if r.get("script") else "the test window stayed open", fix_script)
        self.set_active("Close this window ('close this window') via KDE shortcut", r.get("shortcut"),
                        {True: "the test window closed", False: "stayed open", None: "skipped: the test window did not get focus"}[r.get("shortcut")],
                        "Shika will use Alt+F4 instead.")
        self.set_active("Close this window via Alt+F4 keys", r.get("altf4"),
                        {True: "the test window closed", False: "stayed open", None: "skipped: the test window did not get focus"}[r.get("altf4")],
                        "Send Claude the copied report.")
        if r.get("shortcut"):
            self.pup.settings["close_via"] = "shortcut"
        elif r.get("altf4"):
            self.pup.settings["close_via"] = "altf4"
        save_json(SETTINGS_FILE, self.pup.settings)
        self.status.setText("closing test done: Shika now uses the way that worked")

    def closeEvent(self, e):
        e.ignore()
        self.hide()


class Ring(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(34, 34)
        self.progress, self.color = 0.0, RED

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(4, 4, 26, 26)
        p.setPen(pen(QColor(255, 255, 255, 40), 3.5))
        p.drawEllipse(r)
        p.setPen(pen(self.color, 3.5))
        p.drawArc(r, 90 * 16, -int(360 * 16 * max(0.003, min(1.0, self.progress))))


class FocusFloat(QWidget):
    """Mini focus timer that floats above every app. The Focus widget's "Pop out"
    turns it on; it shares ~/.local/share/summit/focus.json with the widget."""
    def __init__(self, pup):
        super().__init__(None, FLAGS)
        self.pup = pup
        self.state, self.mtime, self.drag_from, self.moved = {}, None, None, False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(GLASS_CSS + "#card { border-radius: 22px; }")
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(10)
        self.ring = Ring()
        lay.addWidget(self.ring)
        col = QVBoxLayout()
        col.setSpacing(0)
        self.mode = QLabel("FOCUS")
        self.mode.setObjectName("caps")
        self.time = QLabel("25:00")
        self.time.setStyleSheet("font-size: 20px; font-weight: 700;")
        col.addWidget(self.mode)
        col.addWidget(self.time)
        lay.addLayout(col)
        self.play = QPushButton("❚❚")
        self.play.setFixedWidth(40)
        self.play.clicked.connect(self.toggle_run)
        close = QPushButton("✕")
        close.setObjectName("x")
        close.clicked.connect(self.close_float)
        lay.addWidget(self.play)
        lay.addWidget(close)
        self.adjustSize()
        QTimer(self, timeout=self.poll).start(1000)
        self.ticker = QTimer(self, timeout=self.render)
        QTimer.singleShot(1500, self.poll)

    def remaining(self):
        st = self.state
        if st.get("running"):
            return max(0.0, st.get("endsAt", 0) - time.time() * 1000)
        return float(st.get("leftMs", 0))

    def poll(self):
        try:
            mt = os.path.getmtime(FOCUS_FILE)
        except OSError:
            return
        if mt == self.mtime:
            return
        self.mtime = mt
        self.state = load_json(FOCUS_FILE, {})
        if self.state.get("popout"):
            if not self.isVisible():
                self.place()
                self.show()
                self.ticker.start(250)
            self.raise_()
            self.render()
        elif self.isVisible():
            self.hide()
            self.ticker.stop()

    def place(self):
        pos = self.pup.settings.get("focus_pos")
        scr = QGuiApplication.primaryScreen().availableGeometry()
        if pos:
            self.move(int(pos[0]), int(pos[1]))
        else:
            self.move(scr.center().x() - self.width() // 2, scr.top() + 12)

    def render(self):
        st = self.state
        ms = self.remaining()
        s = int(math.ceil(ms / 1000))
        self.time.setText(f"{s // 60}:{s % 60:02d}")
        focus = st.get("mode", "focus") == "focus"
        self.mode.setText("FOCUS" if focus else "BREAK")
        self.ring.color = RED if focus else WHITE
        total = float(st.get("total") or 1)
        self.ring.progress = 1 - ms / total
        self.ring.update()
        self.play.setText("❚❚" if st.get("running") else "▶")
        self.raise_()

    def write(self, **changes):
        with FileLock(FOCUS_FILE):
            d = load_json(FOCUS_FILE, {})
            d.update(changes)
            d["updated"] = time.time() * 1000
            durable_write(FOCUS_FILE, json.dumps(d))
        self.state = d
        try:
            self.mtime = os.path.getmtime(FOCUS_FILE)
        except OSError:
            pass
        self.render()

    def toggle_run(self):
        if self.state.get("running"):
            self.write(running=False, leftMs=self.remaining())
        else:
            self.write(running=True, endsAt=time.time() * 1000 + self.remaining())

    def close_float(self):
        self.write(popout=False)
        self.hide()
        self.ticker.stop()

    def mousePressEvent(self, e):
        self.drag_from = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_from is not None:
            self.move(e.globalPosition().toPoint() - self.drag_from)
            self.moved = True

    def mouseReleaseEvent(self, e):
        self.drag_from = None
        if self.moved:
            self.moved = False
            self.pup.settings["focus_pos"] = [self.x(), self.y()]
            save_json(SETTINGS_FILE, self.pup.settings)


NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
             "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45,
             "forty five": 45, "fifty": 50, "sixty": 60, "ninety": 90}
HOUR_WORDS = {k: v for k, v in NUM_WORDS.items() if k not in ("a", "an") and v <= 12}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"


REMIND_RE = (r"(?:please\s+)?(?:(?:set|add|create|make|put|schedule|keep)\s+(?:up\s+)?(?:a\s+|an\s+|me\s+a\s+)?"
             r"(?:reminder|remainder|alarm|alert)|remind(?:\s+me)?|reminder|remainder|alarm)\b\s*[:,-]?\s*")


def spoken_clean(raw):
    s = raw.strip().strip("\"'").rstrip(".!?,").strip()
    s = re.sub(r"\b([ap])\.\s?m\b\.?", lambda m: m.group(1).lower() + "m", s, flags=re.I)
    s = re.sub(r"(\d)\s*([ap])m\b", r"\1 \2m", s, flags=re.I)              # 5pm -> 5 pm
    s = re.sub(r"\b(tmrw|tmrrw|tmr|tomm?orr?ow|2morrow)\b", "tomorrow", s, flags=re.I)
    s = re.sub(r"\b(o'?\s?clock)\b", "oclock", s, flags=re.I)
    return s


def _month(word):
    w = word.lower()[:3]
    return next(i + 1 for i, m in enumerate(MONTHS) if m.startswith(w))


def parse_reminder(s, now=None):
    """'remind me tomorrow at 5:30 pm about the meeting' -> ('the meeting', ts).
    ts is None when no day or time was said. Handles: in 20 minutes / an hour / half an hour,
    at 5, 5:30, 5.30, 5 30 pm, half past 5, quarter to 6, noon, midnight, tonight, this
    evening, tomorrow / tmrw, day after tomorrow, on friday, next monday, 12th november,
    november 12, and times written as words (five thirty pm)."""
    now = now or datetime.now()
    m = re.match(REMIND_RE + r"(?:(?:to|that|about|for|of)\b)?\s*", s, re.I)
    body = s[m.end():] if m else s
    body = re.sub(r"[,.]?\s*(?:as\s+a\s+)?(?:reminder|remainder)\s*$", "", body, flags=re.I)  # "..., reminder"
    # spoken hour words -> digits when they're clearly a time ("five thirty pm", "at six");
    # done on the original text (case-insensitive) so names like "Mohit" keep their capitals
    for w, n in sorted(HOUR_WORDS.items(), key=lambda kv: -len(kv[0])):
        body = re.sub(rf"\b(at|by|past|to)\s+{w}\b", rf"\1 {n}", body, flags=re.I)
        body = re.sub(rf"\b{w}(?=\s+(?:am|pm|oclock|thirty|fifteen|forty[- ]five|fifty)\b)", str(n), body, flags=re.I)
    body = re.sub(r"\b(\d{1,2})\s+(thirty|fifteen|forty[- ]five|fifty)\b",
                  lambda m: f"{m.group(1)}:{NUM_WORDS[m.group(2).lower().replace('-', ' ')]:02d}", body, flags=re.I)
    low = body.lower()
    spans = []

    def take(pat):
        m = re.search(pat, low)
        if m:
            spans.append(m.span())
        return m

    # ---- relative: in 20 minutes / in an hour / in half an hour / in 2 days
    if take(r"\bin\s+(?:a\s+)?half\s+(?:an\s+)?hour\b"):
        return _finish(body, low, spans, now + timedelta(minutes=30))
    m = take(r"\bin\s+(\d+|[a-z]+(?:[ -][a-z]+)?)\s+(minutes?|mins?|hours?|hrs?|days?)\b")
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUM_WORDS.get(m.group(1))
        if n:
            unit = m.group(2)[0]
            delta = timedelta(days=n) if unit == "d" else (timedelta(hours=n) if unit == "h"
                                                           else timedelta(minutes=n))
            return _finish(body, low, spans, now + delta)
        spans.pop()

    # ---- which day
    day = None
    if take(r"\bday\s+after\s+tomorrow\b"):
        day = now.date() + timedelta(days=2)
    elif take(r"\btomorrow\b"):
        day = now.date() + timedelta(days=1)
    elif take(r"\b(today|tonight|this\s+(?:morning|afternoon|evening))\b"):
        day = now.date()
    if day is None:
        m = take(rf"\b(?:on\s+)?(?:the\s+)?{_DAY}\s+(?:of\s+)?{_MON}\b")
        dd = mo = None
        if m:
            dd, mo = int(m.group(1)), _month(m.group(2))
        else:
            m = take(rf"\b(?:on\s+)?{_MON}\s+(?:the\s+)?{_DAY}\b")
            if m:
                dd, mo = int(m.group(2)), _month(m.group(1))
        if dd:
            try:
                d = now.date().replace(month=mo, day=dd)
                if d < now.date():
                    d = d.replace(year=d.year + 1)
                day = d
            except ValueError:
                pass
    if day is None:
        m = take(r"\b(?:on\s+|this\s+|next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b")
        if m:
            ahead = (WEEKDAYS.index(m.group(1)) - now.weekday()) % 7
            if "next" in low[m.start():m.end()] and ahead == 0:
                ahead = 7
            day = now.date() + timedelta(days=ahead)
            weekday_pick = True                       # said on that weekday and time passed: next week
        else:
            weekday_pick = False
    else:
        weekday_pick = False

    # ---- what time
    hour = minute = None
    ampm = None
    m = take(r"\b(?:at\s+|by\s+)?half\s+past\s+(\d{1,2})\b")
    if m:
        hour, minute = int(m.group(1)), 30
    if hour is None:
        m = take(r"\b(?:at\s+|by\s+)?quarter\s+(past|to)\s+(\d{1,2})\b")
        if m:
            hour = int(m.group(2)) - (1 if m.group(1) == "to" else 0)
            minute = 45 if m.group(1) == "to" else 15
            hour = hour or 12
    if hour is None:
        m = None
        pat = (r"\b(?:at\s+|by\s+|around\s+)?(\d{1,2})(?:[:.](\d{2})|\s+(\d{2})(?=\s*[ap]m\b))?"
               r"(?:\s*(am|pm|oclock)\b)?(?:\s+in\s+the\s+(morning|afternoon|evening|night))?(?![\d:.])")
        for c in re.finditer(pat, low):
            if any(a < c.end() and c.start() < b for a, b in spans):
                continue                                   # part of a date we already read
            # a bare number only counts as a time with at/by, minutes, am/pm or o'clock
            if c.group(2) or c.group(3) or c.group(4) or c.group(5) \
                    or re.match(r"(at|by|around)\b", low[c.start():]):
                m = c
                spans.append(c.span())
                break
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2) or m.group(3) or 0)
            ampm = m.group(4) if m.group(4) in ("am", "pm") else None
            part = m.group(5)
            if part == "morning":
                ampm = "am"
            elif part:
                ampm = "pm"
    if hour is None:
        if take(r"\b(noon|midday)\b"):
            hour, minute, ampm = 12, 0, "pm"
        elif take(r"\bmidnight\b"):
            hour, minute, ampm = 0, 0, None
            if day is None:
                day = now.date() + timedelta(days=1)
    if ampm is None and hour is not None and hour <= 12:
        if re.search(r"\b(tonight|evening|afternoon)\b", low):
            ampm = "pm"
        elif re.search(r"\bmorning\b", low):
            ampm = "am"
    if hour is None:                                       # a day but no time: sensible defaults
        if re.search(r"\btonight\b|\bthis\s+evening\b", low):
            hour, minute, ampm = 8, 0, "pm"
        elif re.search(r"\bthis\s+afternoon\b|\bafternoon\b", low):
            hour, minute, ampm = 2, 0, "pm"
        elif re.search(r"\bevening\b", low):
            hour, minute, ampm = 7, 0, "pm"
        elif day is not None:
            hour, minute, ampm = 9, 0, "am"
            take(r"\b(?:in\s+the\s+)?morning\b")
    if hour is None or hour > 23 or (minute or 0) > 59:
        return _finish(body, low, spans, None)
    minute = minute or 0

    if ampm:
        if hour > 12:
            ampm = None
        else:
            hour = hour % 12 + (12 if ampm == "pm" else 0)
    if ampm or hour > 12 or hour == 0:
        hours = [hour]
    elif day is not None and day != now.date():
        # another day, no am/pm: 7-11 means morning, 12 and 1-6 mean afternoon/evening
        hours = [hour if 7 <= hour <= 11 else (12 if hour == 12 else hour + 12)]
    else:
        hours = [hour, hour + 12] if hour < 12 else [hour]

    base_day = day or now.date()
    cands = [datetime.combine(base_day, datetime.min.time()).replace(hour=h, minute=minute) for h in hours]
    future = [c for c in cands if c > now]
    if not future:
        if day is not None and day != now.date():
            future = cands                                   # explicit future day
        elif weekday_pick:
            future = [c + timedelta(days=7) for c in cands]  # "on thursday" said on a Thursday evening
        else:
            future = [c + timedelta(days=1) for c in cands]  # "at 5" after 5 pm means tomorrow
    return _finish(body, low, spans, min(future))


def _finish(body, low, spans, due):
    """Cut the spoken date/time out of the text so only the task is left."""
    keep = list(low)
    for a, b in spans:
        for i in range(a, b):
            keep[i] = "\0"
    cut = "".join(keep)
    # map the cuts back onto the original-case text (lengths match except for word->digit swaps)
    text = body if len(body) == len(cut) else low
    out = "".join(ch for ch, k in zip(text, cut) if k != "\0")
    out = re.sub(r"\b(tonight|today|this\s+(?:morning|afternoon|evening))\b", " ", out, flags=re.I)
    out = re.sub(r"\s+", " ", out).strip(" ,.-")
    for _ in range(3):
        out = re.sub(r"^(?:to|that|about|for|of|a|an|on|at|by)\s+", "", out, flags=re.I)
        out = re.sub(r"\s+(?:to|at|on|by|for|of|from|in|the)$", "", out, flags=re.I).strip(" ,.-")
    if out and out[0].islower() and text is low:
        out = out[0].upper() + out[1:]
    return out, (due.timestamp() if due else None)


# ---------------------------------------------------------------- browsers & sites by voice
BROWSERS = {
    "chrome": {"bins": ["google-chrome-stable", "google-chrome"], "flatpak": "com.google.Chrome",
               "data": ["~/.config/google-chrome", "~/.var/app/com.google.Chrome/config/google-chrome"],
               "kind": "chromium", "label": "Chrome"},
    "chromium": {"bins": ["chromium", "chromium-browser"], "flatpak": "org.chromium.Chromium",
                 "data": ["~/.config/chromium", "~/snap/chromium/common/chromium"],
                 "kind": "chromium", "label": "Chromium"},
    "brave": {"bins": ["brave-browser", "brave"], "flatpak": "com.brave.Browser",
              "data": ["~/.config/BraveSoftware/Brave-Browser"], "kind": "chromium", "label": "Brave"},
    "edge": {"bins": ["microsoft-edge-stable", "microsoft-edge"], "flatpak": "com.microsoft.Edge",
             "data": ["~/.config/microsoft-edge"], "kind": "chromium", "label": "Edge"},
    "firefox": {"bins": ["firefox"], "flatpak": "org.mozilla.firefox",
                "data": ["~/snap/firefox/common/.mozilla/firefox", "~/.mozilla/firefox",
                         "~/.var/app/org.mozilla.firefox/.mozilla/firefox"],
                "kind": "firefox", "label": "Firefox"},
}
BROWSER_WORDS = [("google chrome", "chrome"), ("chrome", "chrome"), ("chromium", "chromium"),
                 ("brave", "brave"), ("microsoft edge", "edge"), ("edge", "edge"),
                 ("mozilla firefox", "firefox"), ("mozilla", "firefox"), ("firefox", "firefox"),
                 ("fire fox", "firefox")]
SITES = {
    "youtube": "https://www.youtube.com", "you tube": "https://www.youtube.com",
    "youtube studio": "https://studio.youtube.com", "gmail": "https://mail.google.com",
    "mail": "https://mail.google.com", "google": "https://www.google.com",
    "google drive": "https://drive.google.com", "drive": "https://drive.google.com",
    "google docs": "https://docs.google.com", "google sheets": "https://sheets.google.com",
    "sheets": "https://sheets.google.com", "google calendar": "https://calendar.google.com",
    "calendar": "https://calendar.google.com", "google meet": "https://meet.google.com",
    "meet": "https://meet.google.com", "google maps": "https://maps.google.com", "maps": "https://maps.google.com",
    "whatsapp": "https://web.whatsapp.com", "whatsapp web": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com", "facebook": "https://www.facebook.com",
    "linkedin": "https://www.linkedin.com", "twitter": "https://x.com", "x": "https://x.com",
    "chatgpt": "https://chatgpt.com", "chat gpt": "https://chatgpt.com", "claude": "https://claude.ai",
    "meta ads manager": "https://adsmanager.facebook.com", "meta ads": "https://adsmanager.facebook.com",
    "ads manager": "https://adsmanager.facebook.com", "facebook ads": "https://adsmanager.facebook.com",
    "meta business suite": "https://business.facebook.com", "business suite": "https://business.facebook.com",
    "business manager": "https://business.facebook.com", "events manager": "https://business.facebook.com/events_manager2",
    "google ads": "https://ads.google.com", "google analytics": "https://analytics.google.com",
    "analytics": "https://analytics.google.com", "ga4": "https://analytics.google.com",
    "tag manager": "https://tagmanager.google.com", "google tag manager": "https://tagmanager.google.com",
    "gtm": "https://tagmanager.google.com", "search console": "https://search.google.com/search-console",
    "dv360": "https://displayvideo.google.com", "dv 360": "https://displayvideo.google.com",
    "display and video 360": "https://displayvideo.google.com", "looker studio": "https://lookerstudio.google.com",
    "merchant center": "https://merchants.google.com", "canva": "https://www.canva.com",
    "github": "https://github.com", "netflix": "https://www.netflix.com", "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.in", "flipkart": "https://www.flipkart.com",
    "adsmentor": "https://adsmentor.in", "ads mentor": "https://adsmentor.in",
}
FILLER = r"\b(?:open|launch|start|go\s+to|show|run|in|on|with|using|and|then|the|my|a|an|please|browser|window|tab|new|for\s+me)\b"


def _profile_words(t):
    for w, n in sorted(HOUR_WORDS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b(profile|person|account)\s+{w}\b", rf"\1 {n}", t)
    t = re.sub(r"\b(first)\s+(profile|account)\b", r"profile 0", t)
    return t


def chromium_profiles(browser):
    """[(directory, display name)] from the browser's Local State file."""
    for d in BROWSERS[browser]["data"]:
        path = os.path.join(os.path.expanduser(d), "Local State")
        try:
            cache = json.load(open(path)).get("profile", {}).get("info_cache", {})
        except (OSError, ValueError):
            continue
        out = [(k, (v.get("name") or k)) for k, v in cache.items()]
        if out:
            return sorted(out, key=lambda kv: (kv[0] != "Default", kv[0]))
    return []


def firefox_profiles():
    """[(name, name)] from profiles.ini (snap, deb or flatpak Firefox)."""
    for d in BROWSERS["firefox"]["data"]:
        path = os.path.join(os.path.expanduser(d), "profiles.ini")
        try:
            txt = open(path).read()
        except OSError:
            continue
        names = re.findall(r"^\[Profile\d+\][^\[]*?^Name=(.+)$", txt, re.M)
        if names:
            return [(n.strip(), n.strip()) for n in names]
    return []


def pick_profile(browser, spoken):
    """Match "profile 1", "work", "default"… to a real profile. Returns (id, display name) or None."""
    import difflib
    profiles = chromium_profiles(browser) if BROWSERS[browser]["kind"] == "chromium" else firefox_profiles()
    if not profiles:
        return None
    sp = spoken.strip().lower()
    if sp in ("default", "main", "profile 0", "first", "personal default"):
        return profiles[0]
    for pid, name in profiles:                       # exact display name or folder name
        if sp in (name.lower(), pid.lower()):
            return pid, name
    m = re.fullmatch(r"(?:profile|person|account)?\s*(\d+)", sp)
    if m:
        n = int(m.group(1))
        for pid, name in profiles:
            if pid.lower() == f"profile {n}" or name.lower() in (f"person {n}", f"profile {n}"):
                return pid, name
        if 1 <= n <= len(profiles):                  # "profile 2" = the 2nd one
            return profiles[n - 1]
    best = max(profiles, key=lambda p: difflib.SequenceMatcher(None, sp, p[1].lower()).ratio())
    if difflib.SequenceMatcher(None, sp, best[1].lower()).ratio() >= 0.6 or sp in best[1].lower():
        return best
    return None


def browser_command(browser, profile_id=None, url=None):
    b = BROWSERS[browser]
    exe = next((shutil.which(x) for x in b["bins"] if shutil.which(x)), None)
    if exe:
        cmd = [exe]
    elif shutil.which("flatpak") and subprocess.run(["flatpak", "info", b["flatpak"]],
                                                    capture_output=True).returncode == 0:
        cmd = ["flatpak", "run", b["flatpak"]]
    else:
        return None
    if profile_id:
        cmd += [f"--profile-directory={profile_id}"] if b["kind"] == "chromium" else ["-P", profile_id]
    if url:
        cmd += ["--new-tab", url] if b["kind"] == "firefox" else [url]
    return cmd


def site_url(words):
    w = words.strip().lower()
    if not w:
        return None
    w = re.sub(r"\s+dot\s+", ".", w)
    if w in SITES:
        return SITES[w]
    if re.fullmatch(r"(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/\S*)?", w):
        return w if w.startswith("http") else "https://" + w
    w2 = re.sub(r"\s+(?:website|site|page|web)$", "", w)
    return SITES.get(w2)


def parse_web_command(s):
    """'open youtube in chrome profile 1' -> dict(browser, profile, url, query) or None
    when the sentence isn't about a browser or a website."""
    t = _profile_words(spoken_clean(s).lower())
    t = re.sub(r"[,!?]", " ", t)
    t = re.sub(r"\s+dot\s+(?=[a-z]{2,}\b)", ".", t)                 # "adsmentor dot in"
    domain = None
    m = re.search(r"\b(?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/\S*)?", t)
    if m:
        domain = m.group(0)
        t = t[:m.start()] + " " + t[m.end():]
    browser = None
    for word, key in BROWSER_WORDS:
        m = re.search(rf"\b{word}\b", t)
        if m:
            browser = key
            t = t[:m.start()] + " " + t[m.end():]
            break
    profile = None
    m = (re.search(r"\b(?:profile|person|account)\s+(\d+|[a-z][\w-]*(?:\s+[a-z][\w-]*)?)", t)
         or re.search(r"\b([a-z][\w-]*)\s+(?:profile|account)\b", t))
    if m:
        profile = m.group(1)
        if re.match(r"\d+$", profile):
            profile = "profile " + profile
        t = t[:m.start()] + " " + t[m.end():]
        profile = re.sub(FILLER, " ", profile).strip() or None
    query = None
    whole = re.sub(r"\s+", " ", re.sub(FILLER, " ", t)).strip()
    m = None if site_url(whole) else re.search(r"\b(?:search|google|look\s+up)(?:\s+for)?\s+(.+)", t)
    if m:                                       # ("open google ads" is the site, not a search for "ads")
        query = re.sub(FILLER + r"\s*$", "", m.group(1)).strip()
        t = t[:m.start()]
    rest = re.sub(r"\s+", " ", re.sub(FILLER, " ", t)).strip()
    url = site_url(rest)
    if domain and not rest:
        url = domain if domain.startswith("http") else "https://" + domain
    if query:
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    if not browser and not url:
        return None
    if not browser and profile:                     # "open youtube in profile 2" -> Chrome
        browser = "chrome"
    if browser and rest and not url:
        return None                                  # "open chrome extensions folder"... not ours
    return {"browser": browser, "profile": profile, "url": url}


# ---------------------------------------------------------------- windows, tabs, media by voice
KWIN_SHORTCUTS = [   # (spoken pattern, KWin shortcut name)
    (r"(?:close|shut)(?:\s+(?:this|the|current|that|active)?\s*(?:window|app|one|it)?)?|(?:ye\s+|isko\s+)?band\s+kar(?:o|\s+do)", "Window Close"),
    (r"minimi[sz]e\s+(?:this|the|current|that)?\s*(?:window|app|it)?", "Window Minimize"),
    (r"(?:maximi[sz]e|make\s+(?:it|this)\s+big(?:ger)?)\s*(?:this|the|current)?\s*(?:window|app|it)?", "Window Maximize"),
    (r"(?:full\s?screen|go\s+full\s?screen|exit\s+full\s?screen)", "Window Fullscreen"),
    (r"(?:show|peek\s+at)\s+(?:the\s+)?desktop|minimi[sz]e\s+(?:all|everything)", "Show Desktop"),
    (r"(?:show\s+)?(?:all\s+)?windows\s+overview|overview|show\s+all\s+windows", "Overview"),
]
CLOSE_TAB_RX = (r"(?:close|shut|kill|remove|exit)\s+(?:(?:this|the|that|current|active|my|open|opened|youtube|video|song|music|"
                r"browser|chrome|firefox)\s+)*(?:tab|page)(?:\s+(?:that\s+|which\s+)?(?:you|shika|i)\s+(?:just\s+|had\s+)?opened)?"
                r"(?:\s+(?:here|now))*"
                r"|(?:(?:ye|yeh|is|iss|current)\s+)?tab\s+(?:ko\s+)?(?:band|close)\s*(?:karo|kar\s+do|kardo)")
TAB_KEYS = [        # (spoken pattern, keys pressed together)
    (CLOSE_TAB_RX, ["KEY_LEFTCTRL", "KEY_W"]),
    (r"(?:open\s+)?(?:a\s+)?new\s+tab", ["KEY_LEFTCTRL", "KEY_T"]),
    (r"(?:re\s?open|restore|undo\s+close)\s+(?:the\s+)?(?:last\s+|closed\s+)?tab", ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_T"]),
    (r"next\s+tab", ["KEY_LEFTCTRL", "KEY_TAB"]),
    (r"(?:previous|last)\s+tab", ["KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_TAB"]),
    (r"(?:go\s+)?back", ["KEY_LEFTALT", "KEY_LEFT"]),
    (r"(?:go\s+)?forward", ["KEY_LEFTALT", "KEY_RIGHT"]),
    (r"(?:refresh|reload)(?:\s+(?:the\s+)?page)?", ["KEY_F5"]),
    (r"(?:new\s+window)", ["KEY_LEFTCTRL", "KEY_N"]),
]
MEDIA_KEYS = [      # (spoken pattern, playerctl verb, media key)
    (r"(?:pause|stop)(?:\s+(?:the\s+)?(?:music|song|video|it|this))?|ruko|gaana\s+band\s+karo", "pause", "KEY_PLAYPAUSE"),
    (r"(?:resume|continue|unpause|play)(?:\s+(?:the\s+)?(?:music|song|video|it|again))?", "play", "KEY_PLAYPAUSE"),
    (r"(?:next|skip)(?:\s+(?:the\s+)?(?:song|track|video|one))?|agla\s+gaana", "next", "KEY_NEXTSONG"),
    (r"(?:previous|last|go\s+back\s+a)\s+(?:song|track|video)|pichla\s+gaana", "previous", "KEY_PREVIOUSSONG"),
]
CLOSE_ALIASES = {"chrome": "chrome", "google chrome": "chrome", "mozilla": "firefox", "firefox": "firefox",
                 "mozilla firefox": "firefox", "brave": "brave", "chromium": "chromium", "edge": "edge",
                 "file manager": "dolphin", "files": "dolphin", "terminal": "konsole",
                 "settings": "systemsettings", "system settings": "systemsettings", "text editor": "kate",
                 "editor": "kate", "music": "elisa", "calculator": "kcalc"}
PROCESS_NAMES = {"chrome": ["chrome"], "firefox": ["firefox", "firefox-bin"], "brave": ["brave"],
                 "chromium": ["chromium", "chromium-browser"], "edge": ["msedge"], "dolphin": ["dolphin"],
                 "konsole": ["konsole"], "systemsettings": ["systemsettings"], "kate": ["kate"],
                 "elisa": ["elisa"], "kcalc": ["kcalc"]}

if not IS_LINUX:
    PROCESS_NAMES = {k: [v[0] if IS_MAC else v[1]] for k, v in APP_NAMES.items() if (v[0] if IS_MAC else v[1])}


KWIN_WINDOW_JS = """
const term = %s, action = %s;
const all = workspace.windowList ? workspace.windowList() : workspace.clientList();
const wins = all.filter(w => w.normalWindow && !w.skipTaskbar);
const cls = w => [w.resourceClass, w.resourceName, w.desktopFileName].join(" ").toLowerCase();
let hits = wins.filter(w => cls(w).includes(term));
if (!hits.length) hits = wins.filter(w => String(w.caption).toLowerCase().includes(term));
for (const w of hits) {
    if (action === "close") w.closeWindow();
    else if (action === "minimize") w.minimized = true;
    else if (action === "focus") {
        w.minimized = false;
        if ("activeWindow" in workspace) workspace.activeWindow = w; else workspace.activeClient = w;
    }
}
"""


DEBUG_LOG = os.path.join(CONF, "debug.log")


def dlog(msg):
    """One line per step in ~/.config/shika/debug.log, so 'it didn't work' can be traced to the exact step."""
    try:
        os.makedirs(CONF, exist_ok=True)
        if os.path.exists(DEBUG_LOG) and os.path.getsize(DEBUG_LOG) > 200000:
            os.replace(DEBUG_LOG, DEBUG_LOG + ".old")
        with open(DEBUG_LOG, "a") as f:
            f.write(time.strftime("%H:%M:%S ") + str(msg)[:400].replace("\n", " / ") + "\n")
    except OSError:
        pass


def run_capture(cmd, timeout=3, input=None):
    """Run a command and never raise. -> (return code, stdout, stderr), both untouched."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input)
        return r.returncode, r.stdout or "", r.stderr or ""
    except Exception as ex:
        return 1, "", f"{type(ex).__name__}: {ex}"


def run_quiet(cmd, timeout=3, input=None):
    """-> (return code, output text), for commands whose output we only log or show."""
    rc, out, err = run_capture(cmd, timeout, input)
    return rc, (out + err).strip()


KGA_ORDER = [0, 1]      # invokeShortcut flavours to try: 0 = name only, 1 = name + activation token (newer KDE)
GDBUS_KWIN = ["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path"]
KEY_FALLBACK = {"Window Close": ["KEY_LEFTALT", "KEY_F4"], "Show Desktop": ["KEY_LEFTMETA", "KEY_D"]}


def _later(seconds, fn):
    """Run fn after a delay on a background thread (safe to use from any thread, never blocks exit)."""
    t = threading.Timer(seconds, fn)
    t.daemon = True
    t.start()


def _gq(text):
    """Quote a string for gdbus's GVariant text syntax, so spaces and slashes can't be misread."""
    return "'" + str(text).replace("\\", "\\\\").replace("'", "\\'") + "'"


def kwin_shortcut(name):
    """Run one of KWin's own actions (Window Close, Show Desktop…) as if its shortcut was pressed.
    KDE versions differ on whether this call also wants an activation token, so both are tried."""
    base = ["gdbus", "call", "--session", "--dest", "org.kde.kglobalaccel", "--object-path", "/component/kwin",
            "--method", "org.kde.kglobalaccel.Component.invokeShortcut"]
    for style in list(KGA_ORDER):
        rc, out = run_quiet(base + [_gq(name)] + ([_gq("")] if style else []))
        dlog(f"shortcut {name!r} style={style} rc={rc} {out}")
        if rc == 0:
            if KGA_ORDER[0] != style:
                KGA_ORDER.reverse()                          # remember which flavour this desktop wants
            return True
    return False


def kwin_run_script(js, label="shika"):
    """Load a one-shot KWin script and make sure it really started. -> (ok, detail).
    Older code only checked that loading worked; a script that never ran looked like success."""
    stamp = f"{label}-{int(time.time() * 1000)}"
    path = os.path.join("/tmp", f"{stamp}-{os.getuid()}.js")
    try:
        with open(path, "w") as f:
            f.write(js)
    except OSError as ex:
        return False, f"can't write {path}: {ex}"
    rc, out = run_quiet(GDBUS_KWIN + ["/Scripting", "--method", "org.kde.kwin.Scripting.loadScript",
                                      _gq(path), _gq(stamp)])
    dlog(f"kwin loadScript rc={rc} {out}")
    m = re.search(r"(-?\d+)", out)
    if rc != 0 or not m or int(m.group(1)) < 0:
        _later(2.5, lambda: os.path.exists(path) and os.remove(path))
        return False, f"KDE would not load the script: {out}"
    sid = m.group(1)
    rc, out = run_quiet(GDBUS_KWIN + [f"/Scripting/Script{sid}", "--method", "org.kde.kwin.Script.run"])
    dlog(f"kwin script run rc={rc} {out}")
    if rc != 0:                                              # some KDE builds start scripts through /Scripting
        rc, out = run_quiet(GDBUS_KWIN + ["/Scripting", "--method", "org.kde.kwin.Scripting.start"])
        dlog(f"kwin Scripting.start rc={rc} {out}")
    _later(1.5, lambda: run_quiet(GDBUS_KWIN + ["/Scripting", "--method",
                                                "org.kde.kwin.Scripting.unloadScript", _gq(stamp)]))
    _later(2.5, lambda: os.path.exists(path) and os.remove(path))
    return rc == 0, ("started" if rc == 0 else f"KDE loaded the script but would not start it: {out}")


# ---- taskbar awareness: ask Plasma where its panels are, so Shika can stand on the real floor
PANEL_JS = ("print(JSON.stringify(panels().map(function (p) { return {loc: p.location, h: p.height, "
            "hide: p.hiding, fl: p.floating ? 1 : 0, scr: p.screen}; })));")
PANEL_WHERE = {"bottom": "bottom", "top": "top", "left": "left side", "right": "right side"}


def read_panels():
    """Every Plasma panel as {loc, h, hide, fl, scr}. -> list, or None when plasmashell cannot be asked."""
    rc, out, err = run_capture(["gdbus", "call", "--session", "--dest", "org.kde.plasmashell", "--object-path",
                                "/PlasmaShell", "--method", "org.kde.PlasmaShell.evaluateScript", _gq(PANEL_JS)],
                               timeout=4)
    if rc != 0:
        dlog(f"panels: plasmashell did not answer rc={rc} {err[:120]}")
        return None
    m = re.search(r"\[.*\]", out)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return None
    return [p for p in data if isinstance(p, dict)] if isinstance(data, list) else None


def panel_insets(panels, idx=None):
    """(left, top, right, bottom) pixels the visible panels take from one screen.
    A panel that hides itself takes nothing. A floating panel adds no fixed gap here: Plasma docks it flush
    to the screen edge whenever a window is maximized, so the live free area Qt reports decides the rest."""
    L = T = R = B = 0
    for p in panels or []:
        if idx is not None and p.get("scr", idx) not in (idx, -1):
            continue
        if p.get("hide") == "autohide":
            continue
        try:
            h = max(0, int(p.get("h") or 0))
        except (TypeError, ValueError):
            continue
        loc = p.get("loc")
        if loc == "bottom":
            B = max(B, h)
        elif loc == "top":
            T = max(T, h)
        elif loc == "left":
            L = max(L, h)
        elif loc == "right":
            R = max(R, h)
    return L, T, R, B


def describe_panels(panels, idx=None):
    """One plain sentence per panel, for the Characters page and the setup check."""
    mine = [p for p in panels or [] if idx is None or p.get("scr", idx) in (idx, -1)]
    if not mine:
        return "No taskbar found on this screen. Your pet stands on the bottom edge of the screen."
    out = []
    for p in mine:
        where, h = PANEL_WHERE.get(p.get("loc"), "edge"), int(p.get("h") or 0)
        if p.get("hide") == "autohide":
            out.append(f"The {where} taskbar hides itself, so your pet ignores it and uses the screen edge.")
        elif p.get("loc") == "bottom":
            extra = " (floating)" if p.get("fl") else ""
            out.append(f"Taskbar found at the bottom, {h} px tall{extra}. Your pet stands on top of it.")
        else:
            out.append(f"Taskbar found on the {where}, {h} px wide. Your pet keeps clear of it.")
    return " ".join(out)


def kwin_windows(term, action):
    """Close / minimize / focus every window of an app, the same as clicking its buttons
    (apps get to save and ask, nothing is killed). True only if KDE really ran the script."""
    ok, detail = kwin_run_script(KWIN_WINDOW_JS % (json.dumps(term.lower()), json.dumps(action)), "shika-win")
    dlog(f"kwin windows {term!r} {action} ok={ok} {detail}")
    return ok


def quit_processes(key):
    """Backup when KDE scripting can't be used: a polite SIGTERM, never SIGKILL."""
    hit = False
    for n in PROCESS_NAMES.get(key, [key]):
        rc, out = run_quiet(["pkill", "-TERM", "-x", n])
        dlog(f"pkill -TERM -x {n} rc={rc}")
        if rc == 0:
            hit = True
    return hit


def youtube_first(query, music=False):
    """First video for a search, read from YouTube's results page. None if offline or it changed."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query),
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/126.0 Safari/537.36", "Accept-Language": "en-IN,en;q=0.8"})
        html = urllib.request.urlopen(req, timeout=6).read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html) or re.search(r'"videoId":"([\w-]{11})"', html)
    if not m:
        return None
    return ("https://music.youtube.com/watch?v=" if music else "https://www.youtube.com/watch?v=") + m.group(1)


def split_browser(t):
    """Pull 'in chrome profile 1' / 'on firefox' out of a sentence. -> (rest, browser, profile)"""
    t = _profile_words(t)
    browser = profile = None
    for word, key in BROWSER_WORDS:
        m = re.search(rf"\b(?:in|on|with|using)?\s*{word}\b", t)
        if m:
            browser = key
            t = t[:m.start()] + " " + t[m.end():]
            break
    m = (re.search(r"\b(?:in|on|with|using)?\s*(?:the\s+)?(?:profile|person|account)\s+(\d+|[a-z][\w-]*)", t)
         or re.search(r"\b(?:in|on|with|using)?\s*(?:my\s+|the\s+)?([a-z][\w-]*)\s+(?:profile|account)\b", t))
    if m:
        profile = "profile " + m.group(1) if m.group(1).isdigit() else m.group(1)
        t = t[:m.start()] + " " + t[m.end():]
    if profile and not browser:
        browser = "chrome"
    return re.sub(r"\s+", " ", t).strip(" ,"), browser, profile


def parse_media_command(s):
    """'play kesariya on youtube in chrome profile 1', 'search lofi on youtube',
    'arijit singh songs bajao', 'play believer on spotify' -> dict or None."""
    t = spoken_clean(s).lower()
    t = re.sub(r"[,!?]", " ", t)
    if re.fullmatch(r"\s*(?:play\s+(?:with\s+)?(?:the\s+)?ball|play\s+fetch)\s*", t):
        return None                                   # that one's for the pup
    t, browser, profile = split_browser(t)
    platform = None
    m = re.search(r"\b(?:on|in|at|pe|par)\s+(youtube\s+music|yt\s+music|youtube|you\s+tube|spotify)\b", t)
    if m:
        platform = m.group(1)
        t = (t[:m.start()] + " " + t[m.end():]).strip()
    else:
        m = re.match(r"(youtube\s+music|youtube|you\s+tube|spotify)\s+(?:pe\s+|par\s+|par\s+)?(.+)", t)
        if m:
            platform, t = m.group(1), m.group(2)
    platform = {"you tube": "youtube", "yt music": "youtube music"}.get(platform, platform)
    mode = None
    m = re.match(r"(?:play|put\s+on|start\s+playing|listen\s+to|watch)\s+(.+)", t)
    if m:
        mode, q = "play", m.group(1)
    else:
        m = re.match(r"(.+?)\s+(?:chalao|bajao|lagao|play\s+karo|sunao)$", t)
        if m:
            mode, q = "play", m.group(1)
        else:
            m = re.match(r"(?:search|find|look\s+up|look\s+for|show\s+me)(?:\s+for)?\s+(.+)", t)
            if m and platform:
                mode, q = "search", m.group(1)
            elif platform and t:
                mode, q = "search" if platform != "spotify" else "play", t
    if not mode:
        return None
    q = re.sub(r"^(?:the\s+)?(?:song|video|music|gaana|gana)\s+", "", q.strip())
    q = re.sub(r"\s+(?:song|gaana|gana|video)$", "", q).strip()
    if not q or (mode == "play" and not platform and re.fullmatch(r"(?:the\s+)?(?:music|song|video|it|again)", q)):
        return None                                    # "play music" = resume, handled as a media key
    return {"mode": mode, "platform": platform or "youtube", "query": q, "browser": browser, "profile": profile}


# ---------------------------------------------------------------- cleanup & formatting (Wispr-style)
# Two levels, picked in the Shika app (sidebar: Cleanup):
#   light  rules on this laptop: filler words, spoken punctuation, lists, "scratch that",
#          repeated words, capitals, spacing, your dictionary. Instant, always available.
#   smart  a small local AI model through Ollama (if installed): real grammar fixes, self-corrections
#          ("4, no wait, 5"), lists, tidy paragraphs, keeps your tone and Hinglish. Falls back to light.
OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"      # small and quick on a CPU; "qwen2.5:3b" or "llama3.2:3b" = smarter, slower
DICTIONARY_FILE = os.path.join(CONF, "dictionary.txt")
DICTIONARY_TEMPLATE = """# Shika's dictionary: words he should always spell your way.
# One word or name per line, exactly as it should be written:
Adsmentor
DV360
GA4
Mohit
# Or fix something he keeps hearing wrong:  heard -> written
ads mentor -> Adsmentor
dv 360 -> DV360
g a 4 -> GA4
"""

SPOKEN_PUNCT = [
    (r"\s*\b(?:new paragraph|next paragraph)\b[.,]?\s*", "\n\n"),
    (r"\s*\b(?:new line|next line)\b[.,]?\s*", "\n"),
    (r"\s*\bcomma\b", ","), (r"\s*\b(?:full stop|period)\b", "."), (r"\s*\bquestion mark\b", "?"),
    (r"\s*\bexclamation (?:mark|point)\b", "!"), (r"\s*\bcolon\b", ":"), (r"\s*\bsemicolon\b", ";"),
    (r"\s*\b(?:dash|hyphen)\b\s*", " - "), (r"\s*\bopen (?:bracket|parenthesis)\s*", " ("),
    (r"\s*\bclose (?:bracket|parenthesis)\b", ")"), (r"\bopen quotes?\s*", "“"), (r"\s*\bclose quotes?\b", "”"),
    (r"\s*\bsmiley face\b", " 🙂"), (r"\s*\bheart emoji\b", " ❤️"), (r"\s*\bthumbs up emoji\b", " 👍"),
]


def load_dictionary():
    """-> (words, [(regex, replacement)])"""
    if not os.path.exists(DICTIONARY_FILE):
        try:
            os.makedirs(CONF, exist_ok=True)
            open(DICTIONARY_FILE, "w").write(DICTIONARY_TEMPLATE)
        except OSError:
            return [], []
    words, fixes = [], []
    for line in open(DICTIONARY_FILE, errors="ignore"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if "->" in line:
            heard, right = (x.strip() for x in line.split("->", 1))
            if heard and right:
                fixes.append((re.compile(rf"\b{re.escape(heard).replace(chr(92) + ' ', r'[\s-]?')}\b", re.I), right))
                words.append(right)
        else:
            words.append(line)
            fixes.append((re.compile(rf"\b{re.escape(line)}\b", re.I), line))      # fixes the capitals
    return list(dict.fromkeys(words)), fixes


CORRECTION_CUES = (r"(?:no[,]?\s+(?:wait|sorry|actually)|no[,]?\s+(?:change|make)\s+(?:it|that|this)(?:\s+to)?|"
                   r"(?:change|make)\s+(?:it|that|this)\s+to|no\s+no|wait\s+no|sorry|i\s+mean|actually\s+no|"
                   r"actually|or\s+rather|rather|make\s+(?:that|it)|correction|not\s+that)")


def _ampm_in(t):
    """'7 a.m.' -> '7 am' so the dots don't look like sentence ends while we work."""
    return re.sub(r"(\d)\s*([ap])\.\s?m\.?", lambda m: f"{m.group(1)} {m.group(2).lower()}m", t, flags=re.I)


def _ampm_out(t):
    return re.sub(r"(\d) ?([ap])m\b", lambda m: f"{m.group(1)} {m.group(2)}.m.", t)


def apply_self_corrections(t):
    """'tomorrow afternoon, sorry, tomorrow evening' -> 'tomorrow evening';
    'at 4, no wait, 5' -> 'at 5'. Only when the correction clearly lines up with what came before."""
    t = _ampm_in(t)
    for _ in range(3):
        m = re.search(rf"[,.]?\s*\b{CORRECTION_CUES}\b[,.:]?\s+", t, re.I)
        if not m:
            break
        before, after = t[:m.start()], t[m.end():]
        if re.match(r"\s*[.!?]", t[m.start():]) or not before.strip():
            before = before.rstrip(" .!?")                  # "7 am. No, change it to 8 am": fix the last sentence
        start = max(before.rfind("."), before.rfind("!"), before.rfind("?"), before.rfind("\n")) + 1
        clause = before[start:]
        words_after = re.findall(r"[\w']+", after)
        if not words_after or not clause.strip():
            break
        first = words_after[0].lower()
        # 1) the correction repeats a word from the clause: replace from that word onward
        hit = None
        for wm in re.finditer(r"[\w']+", clause):
            if wm.group(0).lower() == first:
                hit = wm
        if hit:
            t = before[:start] + clause[:hit.start()] + after
            continue
        # 2) a number replaces the last number ("at 4, no wait, 5")
        if re.match(r"\d", first):
            nums = list(re.finditer(r"\b\d[\d:.]*(?:\s*[ap]\.?m\.?)?", clause, re.I))
            if nums:
                n = nums[-1]
                end_num = re.match(r"\d[\d:]*(?:\s*[ap]m\b)?", after, re.I)
                own_tail = re.match(r"[^,.!?\n]*", after[end_num.end():]).group(0).strip()
                clause_tail = clause[n.end():].rstrip(" ,")
                if own_tail and clause_tail.strip().lower().startswith(own_tail.lower()):
                    # "2 tickets for Friday, sorry, 3 tickets": same words follow, keep the rest of the sentence
                    rest = after[end_num.end():]
                    rest = rest[re.match(r"[^,.!?\n]*", rest).end():]
                    t = before[:start] + clause[:n.start()] + end_num.group(0) + clause_tail + rest
                elif own_tail:          # the fix brings different words: use them
                    t = before[:start] + clause[:n.start()] + after
                else:                   # "3 pm tomorrow, no wait, 4 pm": swap just the number
                    t = before[:start] + clause[:n.start()] + end_num.group(0) + clause[n.end():].rstrip(" ,") \
                        + after[end_num.end():]
                continue
        # 3) ", I mean Mohit" / ", actually Tuesday": a 1–2 word fix swaps the last 1–2 words
        seg = re.match(r"([^,.!?\n]+)", after)
        fix = seg.group(1).strip() if seg else ""
        if m.group(0).lstrip().startswith(",") and fix and len(fix.split()) <= 2:
            cw = list(re.finditer(r"[\w']+", clause))
            n = len(fix.split())
            if len(cw) > n:
                cut = cw[-n].start()
                t = before[:start] + clause[:cut] + fix + after[seg.end():]
                continue
        break                                   # unclear: leave it for the AI or as spoken
    return _ampm_out(t)


def polish_light(text):
    t = " " + _ampm_in(text.strip()) + " "
    t = re.sub(r"(?i)[,.]?\s*\b(?:um+|uh+|uhm+|erm+|hmm+|ah+|er)\b[,.]?(?=\s)", "", t)      # fillers
    t = _ampm_in(apply_self_corrections(t))
    # "scratch that" / "delete that": drop everything back to the previous sentence end
    t = re.sub(r"(?i)(^|[.!?\n])[^.!?\n]*?[,.]?\s*\b(?:scratch that|delete that|strike that)\b[,.]?", r"\1", t)
    for pat, rep in SPOKEN_PUNCT:
        t = re.sub(pat, rep, t, flags=re.I)
    t = re.sub(r"(?i)\s*\b(?:bullet point|bullet|next point)\b[:,]?\s*", "\n- ", t)       # spoken lists
    t = re.sub(r"(?i)\b(\w+)(\s+\1\b)+", r"\1", t)                                         # "the the"
    t = re.sub(r"\bi\b", "I", t)
    t = re.sub(r"\bi'(m|ll|ve|d)\b", lambda m: "I'" + m.group(1), t)
    t = re.sub(r"[ \t]+([,.!?;:)])", r"\1", t)
    t = re.sub(r"([,.!?;:])(?=[^\s\d”)\n])", r"\1 ", t)
    t = re.sub(r"([,;:])\1+", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" *\n *", "\n", t).strip()
    t = re.sub(r"(^|[.!?]\s+|\n-?\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    t = re.sub(r"(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|june|"
               r"july|august|september|october|november|december)\b", lambda m: m.group(1).capitalize(), t)
    t = re.sub(r"([A-Za-z0-9)])\n- ", r"\1:\n- ", t, count=1)               # "The plan is" -> "The plan is:"
    last = t.rsplit("\n", 1)[-1]
    if len(t.split()) > 3 and t[-1:].isalnum() and not last.startswith("- "):
        t += "."
    t = _ampm_out(t)
    t = re.sub(r"([ap])\.m\.\.", r"\1.m.", t)              # "5 p.m.." -> "5 p.m."
    _, fixes = load_dictionary()
    for rx, right in fixes:
        t = rx.sub(right, t)
    return t


def ollama_ready():
    import urllib.request
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=0.8) as r:
            names = [m.get("name", "") for m in json.load(r).get("models", [])]
    except Exception:
        return False
    want = OLLAMA_MODEL if ":" in OLLAMA_MODEL else OLLAMA_MODEL + ":latest"
    return want in names


def ollama_warm():
    """Load the model in the background so it's ready by the time you stop talking."""
    import urllib.request

    def go():
        try:
            body = json.dumps({"model": OLLAMA_MODEL, "keep_alive": "15m"}).encode()
            urllib.request.urlopen(urllib.request.Request(OLLAMA_URL + "/api/generate", body,
                                                          {"Content-Type": "application/json"}), timeout=30).read()
        except Exception:
            pass
    threading.Thread(target=go, daemon=True).start()


def ollama(prompt, system, timeout=12, fmt=None, stop=None, num_predict=900):
    import urllib.request
    opts = {"temperature": 0, "num_predict": int(num_predict)}
    if stop:
        opts["stop"] = list(stop)
    req_body = {"model": OLLAMA_MODEL, "prompt": prompt, "system": system, "stream": False,
                "keep_alive": "15m", "options": opts}
    if fmt:
        req_body["format"] = fmt
    body = json.dumps(req_body).encode()
    req = urllib.request.Request(OLLAMA_URL + "/api/generate", body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r).get("response", "").strip()
    out = re.sub(r"^```\w*\n?|\n?```$", "", out).strip()
    if not fmt and len(out) > 1 and out[0] in '"“' and out[-1] in '"”':
        out = out[1:-1].strip()                              # only a quote that wraps the whole answer
    return out


CLEAN_SYSTEM = (
    "You clean up dictated text. Fix grammar, spelling, punctuation and capitalisation. Remove filler words "
    "(um, uh, like, you know) and false starts. Apply the speaker's self-corrections: in 'at 4, no wait, 5' keep "
    "only '5'; in 'tomorrow afternoon, sorry, tomorrow evening' keep only 'tomorrow evening'; cues include no wait, "
    "sorry, I mean, actually, rather; 'scratch that' deletes the sentence before it. The text comes from speech "
    "recognition, so fix words that were clearly misheard when the right word is obvious from context "
    "(\"All scheduled a meeting\" -> \"I'll schedule a meeting\", \"even 5\" -> \"evening 5\"). "
    "If the speaker lists several items, put each on its "
    "own line starting with '- '. Turn spoken punctuation ('comma', 'new line', 'question mark') into the real "
    "thing. Keep the speaker's own words, meaning, tone and language: Hinglish stays Hinglish, Hindi stays Hindi. "
    "Never add facts, greetings or sign-offs, never answer questions in the text, never explain. "
    "Reply with only the cleaned text.")


def polish(text, level):
    """Clean dictated text. Returns (text, how) where how is 'smart', 'light' or 'off'."""
    if level == "off" or not text.strip():
        return text, "off"
    light = polish_light(text)
    if level == "smart" or level == "auto":
        if ollama_ready():
            words, _ = load_dictionary()
            hint = f"\nAlways spell these exactly: {', '.join(words)}." if words else ""
            try:
                out = ollama(f"Dictated text:\n{text.strip()}", CLEAN_SYSTEM + hint)
                n_in, n_out = len(text.split()), len(out.split())
                if out and 0.35 * n_in <= n_out <= 1.6 * n_in + 4:       # refuse rewrites that grew or vanished
                    _, fixes = load_dictionary()
                    for rx, right in fixes:
                        out = rx.sub(right, out)
                    return out, "smart"
            except Exception:
                pass
    return light, "light"


VARIANTS = ("formatted", "simple", "minimal")
VARIANT_LABELS = {"formatted": "✨ Formatted", "simple": "Aa Simple", "minimal": "¶ Minimal"}
ORDINALS = r"(?:first(?:ly)?|second(?:ly)?|third(?:ly)?|fourth(?:ly)?|fifth(?:ly)?|next|then|after that|finally|lastly|" \
           r"step (?:one|two|three|four|five|\d)|number (?:one|two|three|four|five|\d)|point (?:one|two|three|four|five|\d))"


def polish_minimal(text):
    """As spoken: only spoken punctuation, 'new line', spacing and a capital at the start."""
    t = " " + text.strip() + " "
    for pat, rep_ in SPOKEN_PUNCT:
        t = re.sub(pat, rep_, t, flags=re.I)
    t = re.sub(r"[ \t]+([,.!?;:)])", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" *\n *", "\n", t).strip()
    return t[:1].upper() + t[1:]


def structure(text):
    """Rule-based layout for list-like speech: steps -> 1. 2. 3., enumerations -> bullets,
    greetings and sign-offs on their own lines."""
    t = text.strip()
    if not t or "\n- " in t or "\n1. " in t:
        return t
    # greeting / sign-off for messages
    t = re.sub(r"^((?:hi|hello|hey|dear|good (?:morning|afternoon|evening))\b[^,.!?\n]{0,30})[,.!]?\s+", r"\1,\n\n", t, flags=re.I)
    t = re.sub(r"[,.]?\s+((?:thanks|thank you|regards|best regards|cheers|warm regards)[^.!?\n]{0,25}[.!]?)$",
               r"\n\n\1", t, flags=re.I)
    # steps: "first ..., second ..., finally ..." (3+ markers, starting with a 'first')
    marks = [m for m in re.finditer(rf"(?:^|(?<=[\s.,;:!?]))(?:and\s+)?\b{ORDINALS}\b[,:]?\s+", t, flags=re.I)]
    strong = [m for m in marks if re.match(r"(?:and\s+)?(?:first|step (?:one|1)|number (?:one|1)|point (?:one|1))",
                                          m.group(0).strip(), re.I)]
    if len(marks) >= 3 and strong and strong[0].start() <= marks[0].start():
        intro = t[:marks[0].start()].strip(" ,;")
        items = [t[m.end():(marks[i + 1].start() if i + 1 < len(marks) else len(t))].strip(" ,;.")
                 for i, m in enumerate(marks)]
        tail = ""
        so = re.search(r"\n\n((?:thanks|thank you|regards|best regards|cheers|warm regards)[^\n]*)$", items[-1], re.I)
        if so:
            tail, items[-1] = "\n\n" + so.group(1), items[-1][:so.start()].strip(" ,;.")
        if all(items) and all(len(i.split()) <= 25 for i in items):
            body = "\n".join(f"{n}. {i[:1].upper() + i[1:]}" for n, i in enumerate(items, 1))
            if intro:
                intro = re.sub(r"\s*\b(?:are|is)$", r"\g<0>", intro.rstrip(".:")) + ":"
            t = (intro + "\n" if intro else "") + body + tail
            return re.sub(r"(^|\n)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    # enumerations: "... features: a, b, c, and d" / "... bring a, b, c and d" (3+ short items)
    LIST = r"((?:[^,.!?\n:]+,\s*){2,}(?:[^,.!?\n:]+?,?\s+(?:and|or)\s+)?[^,.!?\n:]+)[.!]?(?=\s|$)"
    KEYS = (r"need|needs|needed|include|includes|including|like|such as|are|is|list|items|things|buy|get|bring|"
            r"check|do|tasks?|points?|features?|steps?|options?|requirements?|goals?|topics?|agenda|has|have|"
            r"covers?|want|wants")
    t2 = t
    done = False
    for pat in (r"([^.!?\n]*:)\s*" + LIST,                                   # after a colon: most reliable
                rf"([^.!?\n]*\b(?:{KEYS}))\s+" + LIST):                         # after the last listing word
        for m in re.finditer(pat, t, flags=re.I):
            lead, lst = m.group(1), m.group(2)
            items = [re.sub(r"^(?:and|or)\s+", "", x.strip(), flags=re.I)
                     for x in re.split(r",\s*|\s+and\s+|\s+or\s+", lst) if x.strip()]
            items = [i for i in items if i]
            if len(items) < 3 or any(len(i.split()) > 6 for i in items):
                continue                                                         # not a real list: try the next spot
            block = lead.rstrip(" ,:") + ":\n" + "\n".join("- " + i[:1].upper() + i[1:] for i in items) + "\n"
            rest = t[m.end():].lstrip()
            t2 = t[:m.start()] + block + ("\n" + rest if rest else "")
            done = True
            break
        if done:
            break
    t2 = re.sub(r"\n{3,}", "\n\n", t2).strip()
    return re.sub(r"(^|\n)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t2)


CLEAN_FEWSHOT = (
    "You fix text that came from speech recognition. Your only job: correct grammar, spelling, punctuation and "
    "capital letters, remove filler words (um, uh, you know) and repeated words, and fix a word that was clearly "
    "misheard when the right word is obvious from the sentence. Keep the speaker's own words, meaning and tone. "
    "Hindi and Hinglish words stay exactly as they are. Never change numbers, times, names or amounts. Never add "
    "anything, never answer a question in the text, never explain. If the text is already correct, return it "
    "unchanged. Reply with the corrected text only.\n\n"
    "Input: um so we should uh meet at the office on friday\n"
    "Output: So we should meet at the office on Friday.\n\n"
    "Input: all scheduled a meeting with rahul tomorrow evening\n"
    "Output: I'll schedule a meeting with Rahul tomorrow evening.\n\n"
    "Input: i has went to the market yesterday and buyed apples\n"
    "Output: I went to the market yesterday and bought apples.\n\n"
    "Input: bhai kal ka session 6 baje hai laptop le aana\n"
    "Output: Bhai, kal ka session 6 baje hai. Laptop le aana.\n\n"
    "Input: can you send me the the report by five p.m.\n"
    "Output: Can you send me the report by five p.m.?\n\n"
    "Input: Please review the landing page before Thursday.\n"
    "Output: Please review the landing page before Thursday.")

LAYOUT_FEWSHOT = (
    "You lay out text for easy reading. If the text lists three or more things, put each on its own line starting "
    "with '- '. If it gives steps in order, put each on its own numbered line ('1. ', '2. '). If it is a message, put "
    "the greeting and the sign-off on their own lines. Keep every word exactly as written: change only line breaks "
    "and list markers. If there is nothing to lay out, return the text unchanged. Reply with the text only.\n\n"
    "Input: For the workshop bring your laptop, a notebook and a charger.\n"
    "Output: For the workshop bring:\n- Your laptop\n- A notebook\n- A charger\n\n"
    "Input: First open events manager, then create a pixel, finally install it.\n"
    "Output: 1. Open events manager\n2. Create a pixel\n3. Install it\n\n"
    "Input: I will call you tomorrow.\n"
    "Output: I will call you tomorrow.")


def apply_fixes(text):
    """Your dictionary and the fixes learned from voice training, applied to any text."""
    _, fixes = load_dictionary()
    for rx, right in fixes:
        text = rx.sub(lambda m, r=right: r, text)
    return text


def ai_cleanup(base, timeout=25):
    """Job 1 for the AI, and only this: grammar, spelling, fillers, clearly misheard words.
    Few worked examples + plain text out + temperature 0 = far fewer surprises than a long rulebook."""
    words, _ = load_dictionary()
    hint = f"\n\nAlways spell these exactly: {', '.join(words)}." if words else ""
    n = len(base.split())
    out = ollama(f"Input: {base.strip()}\nOutput:", CLEAN_FEWSHOT + hint, timeout=timeout,
                 stop=["\nInput:"], num_predict=min(700, int(n * 2.4) + 30))
    out = re.sub(r"^\s*Output:\s*", "", out).strip()
    if "\n" not in base:
        out = " ".join(out.split())                        # one paragraph in, one paragraph out
    return out


def ai_layout(text, timeout=25):
    """Optional job 2 (Best accuracy only): lay a list or steps out. Rules do this first and reliably."""
    out = ollama(f"Input: {text.strip()}\nOutput:", LAYOUT_FEWSHOT, timeout=timeout,
                 stop=["\nInput:"], num_predict=min(800, int(len(text.split()) * 3) + 40))
    return re.sub(r"^\s*Output:\s*", "", out).strip()


def _words(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def _nums(t):
    return sorted(re.findall(r"\d+(?:[:.]\d+)?", t))


def _unlist(t):
    return re.sub(r"(?m)^\s*(?:[-•*]|\d+[.)])\s+", "", t)


def ai_text_ok(src, out, allow_new=0.25):
    """The AI's text is only used if it is clearly the same message, tidied: no loops, about the
    same length, mostly the same words, every important word kept, and every number unchanged."""
    if not out or not out.strip():
        return False
    o = out.strip()
    if len(drop_repeats(o)) < 0.9 * len(o):
        return False                                     # it started repeating itself
    sw, ow = _words(src), _words(o)
    if not sw or not (0.6 * len(sw) <= len(ow) <= 1.35 * len(sw) + 3):
        return False
    sset, oset = set(sw), set(ow)
    if sum(1 for w in ow if w not in sset) > allow_new * len(ow) + 1:
        return False                                     # too many words it made up
    content = [w for w in sset if len(w) > 3 and w not in ("like", "just", "really", "basically", "actually")]
    if content and sum(1 for w in content if w in oset) < 0.75 * len(content):
        return False                                     # it dropped real content
    if _nums(src) != _nums(o):
        return False                                     # times, prices and counts must never change
    return True


def make_variants(raw, level, deep=False):
    """Always returns all three versions, -> ({'formatted','simple','minimal'}, how).
    minimal   = what you said: Whisper's text with spoken punctuation, spacing and a first capital
    simple    = rule cleanup (fillers, corrections, capitals, your learned fixes); Shika AI's version
                replaces it only if it passes every check in ai_text_ok
    formatted = the simple text laid out (lists, steps, greeting/sign-off) by rules; with deep=True
                (Best accuracy) the AI may lay out a list the rules missed, under the same checks"""
    minimal = polish_minimal(raw) if raw.strip() else ""
    if level == "off" or not raw.strip():
        return {v: minimal for v in VARIANTS}, "off"
    base = apply_fixes(drop_repeats(apply_self_corrections(raw)))   # sure-fire fixes first, so the AI can't undo them
    simple = polish_light(base)
    out = {"minimal": minimal, "simple": simple, "formatted": structure(simple)}
    how = "light"
    if level in ("auto", "smart") and ollama_ready():
        try:
            s = ai_cleanup(base)
            if s:
                s = polish_light(apply_fixes(drop_repeats(apply_self_corrections(s))))
            if s and ai_text_ok(simple, s):
                out["simple"] = s
                out["formatted"] = structure(s)
                how = "smart"
                if deep and out["formatted"] == s and len(s.split()) >= 20:
                    f = ai_layout(s)
                    if f and re.search(r"(?m)^(?:- |\d+\. )", f) and ai_text_ok(s, _unlist(f), allow_new=0.12):
                        out["formatted"] = f
        except Exception:
            pass
    return out, how


class VariantBar(QWidget):
    """A small ✨ chip that pops up just above where you're working after a dictation.
    Hover it to see the three versions; click one to swap the text you just dictated."""
    def __init__(self, pup):
        super().__init__(None, FLAGS)
        self.pup = pup
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(GLASS_CSS + "#card { border-radius: 16px; }"
                           "QPushButton { padding: 4px 10px; border-radius: 11px; font-size: 12px; }"
                           "QPushButton#on { background: rgba(225,29,46,70); border-color: #e11d2e; }"
                           "QPushButton#chip { padding: 4px 8px; font-size: 13px; }")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        lay.addWidget(card)
        row = QHBoxLayout(card)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)
        self.chip = QPushButton("✨")
        self.chip.setObjectName("chip")
        row.addWidget(self.chip)
        self.buttons = {}
        for v in VARIANTS:
            b = QPushButton(VARIANT_LABELS[v])
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=v: self.pick(k))
            b.hide()
            row.addWidget(b)
            self.buttons[v] = b
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("x")
        self.close_btn.clicked.connect(self.hide)
        self.close_btn.hide()
        row.addWidget(self.close_btn)
        self.variants, self.current, self.target, self.entry = {}, None, None, None
        self.timer = QTimer(self, singleShot=True, timeout=self.hide)

    def offer(self, variants, current, target, entry_id):
        """target: 'paste' (another app) or 'scratch' (Shika's scratchpad)."""
        self.variants, self.current, self.target, self.entry = variants, current, target, entry_id
        self.collapse()
        self.place()
        self.show()
        self.raise_()
        self.timer.start(12000)

    def place(self):
        p = QCursor.pos()
        scr = (QGuiApplication.screenAt(p) or QGuiApplication.primaryScreen()).availableGeometry()
        self.adjustSize()
        x = min(max(scr.left() + 8, p.x() - 20), scr.right() - self.width() - 8)
        y = p.y() - self.height() - 26                # just above the pointer, where you're working
        if y < scr.top() + 8:
            y = p.y() + 28
        self.move(x, y)

    def collapse(self):
        for v, b in self.buttons.items():
            b.hide()
        self.close_btn.hide()
        self.chip.setText("✨ " + VARIANT_LABELS[self.current].split(" ", 1)[1] if self.current else "✨")
        self.adjustSize()

    def expand(self):
        for v, b in self.buttons.items():
            b.setObjectName("on" if v == self.current else "")
            b.style().unpolish(b)
            b.style().polish(b)
            b.show()
        self.close_btn.show()
        self.chip.setText("✨")
        self.adjustSize()

    def enterEvent(self, e):
        self.timer.stop()
        self.expand()

    def leaveEvent(self, e):
        self.collapse()
        self.timer.start(6000)

    def pick(self, v):
        if v == self.current:
            return
        text = self.variants[v]
        if self.target == "scratch":
            self.pup.scratch.edit.undo()
            self.pup.scratch.insert(text)
        else:
            if not self.pup.typer.combo(["KEY_LEFTCTRL", "KEY_Z"]):    # undo the paste, then paste the new one
                return
            QTimer.singleShot(140, lambda: self.pup.typer.paste(text + ("" if text.endswith("\n") else " ")))
        if self.entry:
            self.pup.library.update(self.entry, text=text)
        self.current = v
        self.expand()
        self.timer.start(8000)


_POLITE_PRE = r"(?:(?:please|can you|could you|would you|can u|will you|hey|ok|okay|just|shika)[,]?\s+)*"
_POLITE_POST = (r"(?:\s+(?:in|of|for|on)\s+(?:this|it|that|the\s+(?:text|selection|selected\s+text|paragraph|"
                r"message|email|sentence)))?(?:[,]?\s+(?:please|for me|now|thanks|thank you|real quick))*")
EDIT_STYLES = [   # (spoken pattern, kind, instruction for the AI)
    (r"(?:fix|correct|check|improve|clean\s*up)\s+(?:my\s+|the\s+|this\s+)?(?:grammar|grammer|spelling|writing|text|"
     r"sentence|this|it)(?:\s+and\s+(?:spelling|grammar))?|grammar\s+(?:fix|check)|proof\s?read(?:\s+(?:this|it))?|"
     r"spell\s?check(?:\s+(?:this|it))?",
     "fix", "Fix grammar, spelling and punctuation only. Change nothing else."),
    (r"(?:make|turn)\s+(?:it|this|that)\s+(?:sound\s+)?(?:more\s+)?(?:formal|professional)|formali[sz]e(?:\s+(?:it|this))?",
     "formal", "Rewrite it in a professional, formal tone."),
    (r"(?:make|turn)\s+(?:it|this|that)\s+(?:sound\s+)?(?:more\s+)?(?:casual|friendly|warm(?:er)?|relaxed)",
     "casual", "Rewrite it in a friendly, casual tone."),
    (r"(?:make|turn)\s+(?:it|this|that)\s+(?:sound\s+)?(?:more\s+)?polite", "polite", "Rewrite it to be more polite."),
    (r"(?:make|turn)\s+(?:it|this|that)\s+(?:a\s+(?:bit|little)\s+)?(?:more\s+)?(?:short|shorter|concise|brief|crisp|tight)|"
     r"shorten(?:\s+(?:it|this))?|cut\s+(?:it|this)\s+down|trim\s+(?:it|this)",
     "shorter", "Make it shorter and more concise. Keep the key points."),
    (r"(?:make|turn)\s+(?:it|this|that)\s+(?:longer|more\s+detailed)|expand\s+(?:it|this)", "longer",
     "Expand it a little with more detail, same meaning."),
    (r"(?:make|turn)\s+(?:it|this|that)\s+(?:clear(?:er)?|simple|simpler)|simplify\s+(?:it|this)", "clear",
     "Rewrite it to be clearer and simpler."),
    (r"(?:turn|make|convert)\s+(?:it|this)\s+(?:into|to)\s+(?:a\s+)?(?:bullet(?:\s+points)?|list|points)|bullet\s+(?:it|this)",
     "bullets", "Turn it into a bullet list, one '- ' line per point."),
    (r"(?:turn|make|convert)\s+(?:it|this)\s+(?:into|to)\s+(?:an?\s+)?(?:email|mail)", "email",
     "Turn it into a short, clear email body."),
    (r"(?:summari[sz]e|sum\s+up)\s+(?:it|this)", "summary", "Summarise it in 1 to 3 sentences."),
    (r"translate\s+(?:it|this)\s+(?:in)?to\s+(\w+)", "translate", "Translate it to {0}."),
    (r"(?:rewrite|rephrase|reword)\s+(?:it|this)(?:\s+(.+))?", "rewrite", "Rewrite it {0}."),
]


def match_edit(low):
    """'make it formal' -> ('formal', 'Rewrite it in a professional, formal tone.') or None."""
    t = re.sub(rf"^{_POLITE_PRE}", "", low.strip().lower())
    t = re.sub(rf"{_POLITE_POST}$", "", t).strip()
    for pat, kind, instr in EDIT_STYLES:
        m = re.fullmatch(pat, t)
        if m:
            arg = next((g for g in m.groups() if g), "") if m.groups() else ""
            return kind, instr.format(arg).replace(" .", ".").replace("Rewrite it .", "Rewrite it better.")
    return None


EDIT_SHOTS = {   # one worked example per job: small models follow an example far better than a rule
    "formal": ("hey can u send me the file asap thx", "Could you please send me the file as soon as possible? Thank you."),
    "casual": ("I would like to inform you that the meeting has been postponed.", "Heads up, the meeting's been pushed back."),
    "polite": ("send the report now", "Could you please send the report when you get a chance?"),
    "shorter": ("I just wanted to reach out to let you know that we will be a little late to the meeting because of the traffic.",
                "We'll be a little late to the meeting because of traffic."),
    "longer": ("The webinar is on Friday.", "The webinar is on Friday, and we would love for you to join us."),
    "clear": ("The thing we discussed about the stuff for the campaign needs to be done by the date.",
              "The campaign tasks we discussed need to be finished by the deadline."),
    "bullets": ("We need a laptop, a notebook and a charger.", "- A laptop\n- A notebook\n- A charger"),
    "email": ("tell rahul the session is moved to 6 pm", "Hi Rahul,\n\nThe session has been moved to 6 pm.\n\nThanks"),
    "summary": ("Our team met on Monday to review the ad results. Spend was up, conversions were flat, and we agreed to "
                "test two new creatives next week.",
                "The team reviewed the ad results: spend rose, conversions stayed flat, and two new creatives will be tested next week."),
}


def clean_ai_reply(out):
    """Remove the chatter small models add: 'Output:' labels, 'Sure, here is…' lines, wrapping quotes."""
    out = re.sub(r"^\s*Output:\s*", "", out or "").strip()
    out = re.sub(r"(?i)^(?:sure|certainly|of course|okay|ok|here(?:'s| is| are))[^\n]*:\s*\n+", "", out).strip()
    out = out.strip("`").strip()
    if len(out) > 1 and out[0] in "\"“" and out[-1] in "\"”":
        out = out[1:-1].strip()
    return out


def edit_ok(kind, src, out):
    """An edit is only pasted over your text if it did what you asked and didn't damage anything."""
    if not out or not out.strip():
        return False
    if re.match(r"(?i)\s*(?:sure|certainly|i'm sorry|i cannot|as an ai)", out):
        return False
    sw, ow = len(src.split()), len(out.split())
    if kind == "fix":
        return ai_text_ok(src, out)
    if kind not in ("translate", "summary", "shorter", "bullets", "email"):
        if _nums(src) != _nums(out):
            return False
    elif kind != "translate" and not set(_nums(out)) <= set(_nums(src)):
        return False                                         # these may drop a number, never invent one
    if kind == "shorter":
        return 0.2 * sw <= ow <= max(1, 0.9 * sw)
    if kind == "longer":
        return 1.1 * sw <= ow <= 4 * sw + 10
    if kind == "summary":
        return 1 <= ow <= max(sw, 3)
    if kind == "bullets":
        return out.lstrip().startswith("- ") or "\n- " in out
    if kind == "email":
        return ow >= 3
    if kind == "translate":
        return True
    return 0.4 * sw - 1 <= ow <= 2.2 * sw + 6                # formal, casual, polite, clear, rewrite


def ai_edit(kind, instruction, sel):
    """Run one edit through Shika AI. -> checked text, or None if it wasn't good enough to use."""
    if kind == "fix":
        out = ai_cleanup(sel)
        return out if ai_text_ok(sel, out) else None
    words, _ = load_dictionary()
    system = ("You edit text the user selected. " + instruction + " Keep the language the text is in unless asked to "
              "translate. Keep names, numbers and facts. Never add commentary, quotes or labels. Reply with the new text only."
              + (f" Always spell these exactly: {', '.join(words)}." if words else ""))
    shot = EDIT_SHOTS.get(kind)
    if shot:
        system += f"\n\nInput: {shot[0]}\nOutput: {shot[1]}"
    n = len(sel.split())
    out = clean_ai_reply(ollama(f"Input: {sel.strip()}\nOutput:", system, timeout=30, stop=["\nInput:"],
                                num_predict=min(900, int(n * 3) + 60)))
    return out if edit_ok(kind, sel, out) else None


if not IS_LINUX:                       # no KDE here: the same jobs through osascript / PowerShell
    def kwin_shortcut(name):
        return False

    def kwin_windows(term, action):
        return other_os_windows(term, action)

    def quit_processes(key):
        return other_os_windows(key, "close")


def _find_app_desktop(name):
    """Best .desktop match for a spoken app name."""
    import difflib
    name = APP_ALIASES.get(name.lower().strip(), name.lower().strip())
    dirs = [os.path.expanduser("~/.local/share/applications"), "/usr/share/applications",
            "/usr/local/share/applications", "/var/lib/flatpak/exports/share/applications",
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/snapd/desktop/applications"]
    best, best_score = None, 0.0
    for d in dirs:
        try:
            files = os.listdir(d)
        except OSError:
            continue
        for fn in files:
            if not fn.endswith(".desktop"):
                continue
            path = os.path.join(d, fn)
            try:
                txt = open(path, errors="ignore").read()
            except OSError:
                continue
            main = txt.split("\n[", 1)[0]
            if re.search(r"^NoDisplay=true", main, re.M) or re.search(r"^Type=(?!Application)", main, re.M):
                continue
            m = re.search(r"^Name=(.+)$", main, re.M)
            label = (m.group(1) if m else fn).strip().lower()
            generic = re.search(r"^GenericName=(.+)$", main, re.M)
            for cand, weight in ((label, 1.0), (fn[:-8].split(".")[-1].lower(), 0.95),
                                 ((generic.group(1).strip().lower() if generic else ""), 0.8)):
                if not cand:
                    continue
                score = difflib.SequenceMatcher(None, name, cand).ratio() * weight
                if cand == name:
                    score = 1.5 * weight
                elif cand.startswith(name) or name in cand.split():
                    score = max(score, 0.9 * weight)
                if score > best_score:
                    best, best_score = (path, m.group(1).strip() if m else fn), score
    return best if best_score >= 0.6 else None



# =====================================================================================================
# Desktop widgets for every system: Tasks and reminders, Sticky notes, Focus timer, Clock.
# They are small floating windows that share the same files as the Plasma widgets, so on Linux you can use either.
# =====================================================================================================
WIDGET_CSS = GLASS_CSS + """
QLabel#clockbig { font-size: 64px; font-weight: 700; letter-spacing: 2px; }
QLabel#clocksmall { font-size: 12px; letter-spacing: 5px; color: rgba(255,255,255,150); font-weight: 700; }
QLabel#clocknext { font-size: 12px; color: rgba(255,255,255,140); }
QPushButton#chip { padding: 4px 8px; font-size: 11px; border-radius: 10px; }
QPushButton#chip:checked { background: rgba(225,29,46,70); border-color: #e11d2e; }
QPushButton#tick { background: transparent; border: 1px solid rgba(255,255,255,60); border-radius: 9px; min-width: 18px;
                   max-width: 18px; min-height: 18px; max-height: 18px; padding: 0; font-size: 11px; }
QPushButton#tick:checked { background: #e11d2e; border-color: #e11d2e; }
QComboBox { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,22); border-radius: 10px; padding: 5px 8px; }
"""

if IS_MAC:          # a Tool window would vanish whenever another app is in front
    WIDGET_FLAGS = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
else:               # no X11Bypass here: these windows take keyboard input
    WIDGET_FLAGS = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint

NOTE_TINTS = [("Smoke", "rgba(10,10,12,225)", "#8a8a90"), ("Ember", "rgba(52,8,13,225)", "#E11D2E"),
              ("Frost", "rgba(214,222,235,60)", "#F2F2F3")]
FOCUS_CHOICES = [25, 45, 60, 15]
REPEATS = [("Once", 0), ("Hourly", 60), ("Daily", 1440), ("Weekly", 10080)]


def parse_clock(text, now=None):
    """'6:45 pm', '18:45', '6', 'tmrw 5:30 pm', 'today 9' -> the next matching unix time, 0 for blank, -1 if not a time."""
    t = (text or "").strip().lower()
    if not t:
        return 0
    now = now if now is not None else time.time()
    t = re.sub(r"\b([ap])\.?\s?m\.?", r"\1m", t)
    day = -1
    dm = re.match(r"^(tmrw|tmr|tomorrow|tom|today)\s+", t)
    if dm:
        day = 0 if dm.group(1) == "today" else 1
        t = t[dm.end():]
    m = re.match(r"^(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?$", t)
    if not m:
        return -1
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if h > 23 or mi > 59 or (ap and h > 12):
        return -1
    if ap:
        options = [(h % 12) + (12 if ap == "pm" else 0)]
    elif day == 1 and h <= 12:
        options = [h if 7 <= h <= 11 else (12 if h == 12 else h + 12)]
    else:
        options = [h, h + 12] if h < 12 else [h]
    best = 0
    base = datetime.fromtimestamp(now)
    for hh in options:
        for dd in ([day] if day >= 0 else [0, 1]):
            d = (base + timedelta(days=dd)).replace(hour=hh, minute=mi, second=0, microsecond=0)
            ts = d.timestamp()
            if ts > now and (not best or ts < best):
                best = ts
    return best or -1


def when_label(due, now=None):
    now = now if now is not None else time.time()
    diff = due - now
    if diff < 0:
        return "overdue"
    if diff < 3600:
        return f"in {max(1, round(diff / 60))} min"
    d = datetime.fromtimestamp(due)
    t = d.strftime("%I:%M %p").lstrip("0")
    today = datetime.fromtimestamp(now).date()
    if d.date() == today:
        return t
    if d.date() == today + timedelta(days=1):
        return "Tmrw " + t
    return d.strftime("%a %d %b") + " · " + t


def focus_total_ms(st):
    if st.get("mode", "focus") == "focus":
        return FOCUS_CHOICES[int(st.get("choice") or 0) % len(FOCUS_CHOICES)] * 60000
    s = int(st.get("sessions") or 0)
    return (15 if s > 0 and s % 4 == 0 else 5) * 60000


def focus_write(**changes):
    with FileLock(FOCUS_FILE):
        d = load_json(FOCUS_FILE, {})
        d.update(changes)
        d["updated"] = time.time() * 1000
        durable_write(FOCUS_FILE, json.dumps(d))
    return d


def sticky_mirror(lib, nid, text, erased=False):
    """Every sticky note is also an entry in the Shika app, with versions (same rules as summitctl.py)."""
    eid = "sticky:" + nid

    def fn(es):
        e = next((x for x in es if x.get("id") == eid), None)
        now = time.time()
        if e is None:
            if not text.strip():
                return
            es.append({"id": eid, "kind": "sticky", "title": "", "text": text, "created": now, "updated": now, "versions": []})
        elif erased:
            e["text"] = text or e.get("text", "")
            Library.push_version(e, "erased from desktop")
            e["removed"] = True
            e["updated"] = now
        elif text != e.get("text"):
            if e.get("removed") or now - e.get("updated", now) > 600:
                Library.push_version(e, "earlier session")
            e["text"] = text
            e["updated"] = now
            e.pop("removed", None)
    lib._mutate(fn)


class WidgetBase(QWidget):
    """A frameless floating card. Drag it anywhere; it remembers where you left it."""
    KEY, TITLE, SIZE = "", "", (300, 200)

    def __init__(self, mgr, key=None):
        super().__init__(None, WIDGET_FLAGS)
        self.mgr, self.pup = mgr, mgr.pup
        self.key = key or self.KEY
        self.drag_from = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(WIDGET_CSS)
        self.setFixedSize(*self.SIZE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("card")
        outer.addWidget(self.card)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(16, 12, 16, 12)
        self.body.setSpacing(8)
        top = QHBoxLayout()
        self.title_label = QLabel(self.TITLE)
        self.title_label.setObjectName("caps")
        top.addWidget(self.title_label, 1)
        for text, fn in self.header_buttons():
            b = QPushButton(text)
            b.setObjectName("x")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(fn)
            top.addWidget(b)
        close = QPushButton("✕")
        close.setObjectName("x")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        self.body.addLayout(top)
        self.build()

    def header_buttons(self):
        return []

    def build(self):
        pass

    def state(self):
        return self.mgr.state(self.key)

    def remember(self, **kw):
        self.mgr.remember(self.key, **kw)

    def place(self):
        pos = self.state().get("pos")
        if pos:
            self.move(int(pos[0]), int(pos[1]))
        else:
            self.move(*self.mgr.default_pos(self))

    def open(self):
        self.place()
        self.show()
        self.raise_()
        self.remember(open=True)

    def dismiss(self):
        self.hide()
        self.remember(open=False)

    def mousePressEvent(self, e):
        self.drag_from = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_from is not None:
            self.move(e.globalPosition().toPoint() - self.drag_from)

    def mouseReleaseEvent(self, e):
        if self.drag_from is not None:
            self.drag_from = None
            self.remember(pos=[self.x(), self.y()])


class TasksWidget(WidgetBase):
    KEY, TITLE, SIZE = "tasks", "TASKS & REMINDERS", (350, 500)
    WHEN = ["No time", "+15 min", "+1 hr", "8 PM", "Tmrw 9 AM"]

    def build(self):
        self.when_idx, self.repeat_idx, self.mtime = 0, 0, None
        self.text = QLineEdit()
        self.text.setPlaceholderText("What needs doing?")
        self.text.returnPressed.connect(lambda: self.add("task"))
        self.body.addWidget(self.text)
        self.time = QLineEdit()
        self.time.setPlaceholderText("Time, e.g. 6:45 pm or tmrw 9 (optional for tasks)")
        self.time.returnPressed.connect(lambda: self.add("reminder"))
        self.body.addWidget(self.time)
        chips = QHBoxLayout()
        chips.setSpacing(5)
        self.chips = []
        for i, label in enumerate(self.WHEN):
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=i: self.pick_when(k))
            chips.addWidget(b)
            self.chips.append(b)
        self.body.addLayout(chips)
        row = QHBoxLayout()
        self.repeat = QComboBox()
        for label, _ in REPEATS:
            self.repeat.addItem(label)
        self.repeat.currentIndexChanged.connect(lambda i: setattr(self, "repeat_idx", max(0, int(i))))
        row.addWidget(self.repeat)
        t = QPushButton("+ Task")
        t.clicked.connect(lambda: self.add("task"))
        r = QPushButton("Remind me")
        r.setObjectName("primary")
        r.clicked.connect(lambda: self.add("reminder"))
        row.addWidget(t)
        row.addWidget(r)
        self.body.addLayout(row)
        self.msg = QLabel("")
        self.msg.setObjectName("red")
        self.body.addWidget(self.msg)
        holder = QWidget()
        self.rows = QVBoxLayout(holder)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.body.addWidget(scroll, 1)
        foot = QHBoxLayout()
        self.count = QLabel("")
        self.count.setObjectName("muted")
        clear = QPushButton("Clear done")
        clear.setObjectName("chip")
        clear.clicked.connect(self.clear_done)
        foot.addWidget(self.count, 1)
        foot.addWidget(clear)
        self.body.addLayout(foot)
        QTimer(self, timeout=self.poll).start(3000)
        self.refresh()

    def pick_when(self, i):
        self.when_idx = 0 if self.when_idx == i else i
        for k, b in enumerate(self.chips):
            b.setChecked(k == self.when_idx and self.when_idx != 0)

    def warn(self, text):
        self.msg.setText(text)
        QTimer.singleShot(4000, lambda: self.msg.setText(""))

    def chosen_due(self, now=None):
        """0 = no time, -1 = a typed time that could not be read."""
        now = now if now is not None else time.time()
        if self.time.text().strip():
            return parse_clock(self.time.text(), now)
        i = self.when_idx
        if i == 1:
            return now + 15 * 60
        if i == 2:
            return now + 60 * 60
        base = datetime.fromtimestamp(now)
        if i == 3:
            d = base.replace(hour=20, minute=0, second=0, microsecond=0)
            return (d if d.timestamp() > now else d + timedelta(days=1)).timestamp()
        if i == 4:
            return (base + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0).timestamp()
        return 0

    def add(self, kind):
        text = self.text.text().strip()
        if not text:
            self.warn("Type something first")
            return
        due = self.chosen_due()
        if due < 0:
            self.warn("Try 6:45 pm, 18:45 or tmrw 5:30 pm")
            return
        if kind == "reminder" and not due:
            self.warn("Pick a time for the reminder")
            return
        item = {"id": f"{time.time():.6f}", "kind": kind, "text": text[:300], "due": due or None, "done": False, "urgent": False}
        if due and REPEATS[self.repeat_idx][1]:
            item["repeat"] = REPEATS[self.repeat_idx][1]
        self.pup.edit_reminders(lambda rs: rs.append(item))
        self.text.setText("")
        self.time.setText("")
        self.pick_when(0)
        self.repeat.setCurrentIndex(0)
        self.refresh()

    def items(self):
        out = []
        for r in self.pup.reminders:
            r.setdefault("kind", "reminder")
            if r["kind"] == "task" or not r.get("done"):
                out.append(r)
        def rank(t):
            return 3 if t.get("done") else (0 if t.get("due") else (1 if t.get("urgent") else 2))
        return sorted(out, key=lambda t: (rank(t), t.get("due") or 0))

    def patch(self, rid, **fields):
        def fn(rs):
            for r in rs:
                if r.get("id") == rid:
                    r.update(fields)
        self.pup.edit_reminders(fn)
        self.refresh()

    def remove(self, rid):
        self.pup.delete_reminder(rid)
        self.refresh()

    def clear_done(self):
        self.pup.edit_reminders(lambda rs: rs.__setitem__(slice(None), [r for r in rs if not (r.get("kind") == "task" and r.get("done"))]))
        self.refresh()

    def poll(self):
        try:
            mt = os.path.getmtime(REMINDERS_FILE)
        except OSError:
            return
        if mt != self.mtime:
            self.pup.reload_reminders()
            self.refresh()

    def refresh(self):
        try:
            self.mtime = os.path.getmtime(REMINDERS_FILE)
        except OSError:
            self.mtime = None
        while self.rows.count():
            it = self.rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        items = self.items()
        now = time.time()
        for r in items:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            if r["kind"] == "task":
                tick = QPushButton("✓" if r.get("done") else "")
                tick.setObjectName("tick")
                tick.setCheckable(True)
                tick.setChecked(bool(r.get("done")))
                tick.clicked.connect(lambda _=False, rid=r["id"], d=not r.get("done"): self.patch(rid, done=d))
                lay.addWidget(tick)
            else:
                lay.addWidget(QLabel("⏰"))
            label = QLabel(r["text"])
            label.setWordWrap(True)
            if r.get("done"):
                label.setStyleSheet("color: rgba(255,255,255,90); text-decoration: line-through;")
            lay.addWidget(label, 1)
            if r.get("due") and not r.get("done"):
                due = QLabel(when_label(r["due"], now))
                due.setObjectName("red" if r["due"] < now else "muted")
                lay.addWidget(due)
            star = QPushButton("★" if r.get("urgent") else "☆")
            star.setObjectName("x")
            star.clicked.connect(lambda _=False, rid=r["id"], u=not r.get("urgent"): self.patch(rid, urgent=u))
            lay.addWidget(star)
            bin_ = QPushButton("✕")
            bin_.setObjectName("x")
            bin_.clicked.connect(lambda _=False, rid=r["id"]: self.remove(rid))
            lay.addWidget(bin_)
            self.rows.addWidget(row)
        if not items:
            e = QLabel("Nothing yet. Add a task above.")
            e.setObjectName("empty")
            self.rows.addWidget(e)
        self.rows.addStretch(1)
        open_n = sum(1 for r in items if not r.get("done"))
        self.count.setText(f"{open_n} open · {len(items) - open_n} done")


class NoteWidget(WidgetBase):
    TITLE, SIZE = "STICKY NOTE", (250, 240)

    def build(self):
        st = self.state()
        data = load_json(STICKY_FILE, {}).get(self.key, {})
        self.tint = int(data.get("tint") or 0) % len(NOTE_TINTS)
        self.loaded_text = data.get("text", "")
        self.confirm = False
        self.dots = QHBoxLayout()
        for i, (_n, _f, dot) in enumerate(NOTE_TINTS):
            b = QPushButton("●")
            b.setObjectName("x")
            b.setStyleSheet(f"color: {dot};")
            b.clicked.connect(lambda _=False, k=i: self.set_tint(k))
            self.dots.addWidget(b)
        self.dots.addStretch(1)
        self.body.addLayout(self.dots)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Write here…")
        self.edit.setPlainText(self.loaded_text)
        self.edit.textChanged.connect(self.changed)
        self.body.addWidget(self.edit, 1)
        self.saver = QTimer(self, singleShot=True, timeout=self.save)
        self.apply_tint()

    def header_buttons(self):
        return [("↗", self.open_in_app), ("🗑", self.bin)]

    def apply_tint(self):
        self.card.setStyleSheet(f"#card {{ background: {NOTE_TINTS[self.tint][1]}; }}")

    def set_tint(self, i):
        self.tint = i
        self.apply_tint()
        self.save()

    def changed(self):
        self.saver.start(600)

    def save(self):
        text = self.edit.toPlainText()
        with FileLock(STICKY_FILE):
            notes = load_json(STICKY_FILE, {})
            notes[self.key] = {"text": text, "tint": self.tint, "updated": time.time()}
            durable_write(STICKY_FILE, json.dumps(notes))
        sticky_mirror(self.pup.library, self.key, text)

    def open_in_app(self):
        self.save()
        self.pup.open_dashboard("sticky:" + self.key)

    def bin(self):
        if not self.confirm:
            self.confirm = True
            self.title_label.setText("PRESS 🗑 AGAIN TO ERASE")
            QTimer.singleShot(3000, self.unconfirm)
            return
        text = self.edit.toPlainText()
        with FileLock(STICKY_FILE):
            notes = load_json(STICKY_FILE, {})
            notes.pop(self.key, None)
            durable_write(STICKY_FILE, json.dumps(notes))
        sticky_mirror(self.pup.library, self.key, text, erased=True)
        self.mgr.forget_note(self.key)
        self.hide()

    def unconfirm(self):
        self.confirm = False
        self.title_label.setText(self.TITLE)

    def dismiss(self):
        if self.saver.isActive():
            self.saver.stop()
            self.save()
        super().dismiss()


class FocusWidget(WidgetBase):
    KEY, TITLE, SIZE = "focus", "FOCUS TIMER", (290, 330)

    def build(self):
        self.st, self.mtime = {}, None
        self.ring = Ring()
        self.ring.setFixedSize(110, 110)
        self.time = QLabel("25:00")
        self.time.setStyleSheet("font-size: 40px; font-weight: 700;")
        self.mode = QLabel("FOCUS")
        self.mode.setObjectName("caps")
        mid = QHBoxLayout()
        mid.addWidget(self.ring)
        col = QVBoxLayout()
        col.addWidget(self.mode)
        col.addWidget(self.time)
        self.sessions = QLabel("")
        self.sessions.setObjectName("muted")
        col.addWidget(self.sessions)
        mid.addLayout(col, 1)
        self.body.addLayout(mid)
        presets = QHBoxLayout()
        self.preset_buttons = []
        for i, m in enumerate(FOCUS_CHOICES):
            b = QPushButton(f"{m} min")
            b.setObjectName("chip")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=i: self.choose(k))
            presets.addWidget(b)
            self.preset_buttons.append(b)
        self.body.addLayout(presets)
        row = QHBoxLayout()
        self.play = QPushButton("▶  Start")
        self.play.setObjectName("primary")
        self.play.clicked.connect(self.toggle)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        brk = QPushButton("Break")
        brk.clicked.connect(lambda: self.switch("break"))
        row.addWidget(self.play, 1)
        row.addWidget(reset)
        row.addWidget(brk)
        self.body.addLayout(row)
        pop = QPushButton("Pop out a mini timer")
        pop.clicked.connect(self.pop_out)
        self.body.addWidget(pop)
        QTimer(self, timeout=self.poll).start(1500)
        self.ticker = QTimer(self, timeout=self.render)
        self.ticker.start(250)
        self.poll(force=True)

    def remaining(self):
        st = self.st
        if st.get("running"):
            return max(0.0, st.get("endsAt", 0) - time.time() * 1000)
        return float(st.get("leftMs") or focus_total_ms(st))

    def poll(self, force=False):
        try:
            mt = os.path.getmtime(FOCUS_FILE)
        except OSError:
            mt = None
        if mt == self.mtime and not force:
            return
        self.mtime = mt
        self.st = load_json(FOCUS_FILE, {})
        self.render()

    def write(self, **changes):
        self.st = focus_write(**changes)
        try:
            self.mtime = os.path.getmtime(FOCUS_FILE)
        except OSError:
            pass
        self.render()

    def choose(self, i):
        self.write(choice=i, mode="focus", running=False, leftMs=FOCUS_CHOICES[i] * 60000,
                   total=FOCUS_CHOICES[i] * 60000)

    def toggle(self):
        if self.st.get("running"):
            self.write(running=False, leftMs=self.remaining())
        else:
            self.write(running=True, endsAt=time.time() * 1000 + self.remaining(), total=focus_total_ms(self.st))

    def reset(self):
        self.write(running=False, leftMs=focus_total_ms(self.st), total=focus_total_ms(self.st))

    def switch(self, mode):
        probe = dict(self.st, mode=mode)
        self.write(mode=mode, running=False, leftMs=focus_total_ms(probe), total=focus_total_ms(probe))

    def finish(self):
        if self.st.get("mode", "focus") == "focus":
            self.write(running=False, sessions=int(self.st.get("sessions") or 0) + 1)
            self.pup.notify("Focus done 🎯", "Nice work. Take a short break.")
            self.pup.say("Focus done 🎯 take a short break", 6)
            self.switch("break")
        else:
            self.write(running=False)
            self.pup.notify("Break over", "Back to work.")
            self.pup.say("Break over, back to it 💪", 6)
            self.switch("focus")

    def pop_out(self):
        self.write(popout=True)
        self.pup.focus_float.poll()

    def render(self):
        st = self.st
        if st.get("running") and st.get("endsAt", 0) <= time.time() * 1000:
            self.finish()
            return
        ms = self.remaining()
        s = int(math.ceil(ms / 1000))
        self.time.setText(f"{s // 60}:{s % 60:02d}")
        focus = st.get("mode", "focus") == "focus"
        self.mode.setText("FOCUS" if focus else "BREAK")
        self.ring.color = RED if focus else WHITE
        total = float(st.get("total") or focus_total_ms(st) or 1)
        self.ring.progress = 1 - ms / total
        self.ring.update()
        self.play.setText("❚❚  Pause" if st.get("running") else "▶  Start")
        n = int(st.get("sessions") or 0)
        self.sessions.setText(f"{n} session{'s' if n != 1 else ''} done")
        for i, b in enumerate(self.preset_buttons):
            b.setChecked(focus and int(st.get("choice") or 0) == i)


class ClockWidget(WidgetBase):
    KEY, TITLE, SIZE = "clock", "", (330, 190)
    FONTS = ["Bebas Neue", "BebasNeue", "Oswald", "Anton", "League Gothic", "Fjalla One", "Impact"]

    def build(self):
        st = self.state()
        self.hour24 = bool(st.get("hour24", False))
        self.show_next = bool(st.get("show_next", True))
        self.clock = QLabel("")
        self.clock.setObjectName("clockbig")
        self.clock.setTextFormat(Qt.TextFormat.RichText)
        self.day = QLabel("")
        self.day.setObjectName("clocksmall")
        self.next = QLabel("")
        self.next.setObjectName("clocknext")
        self.body.addWidget(self.clock)
        self.body.addWidget(self.day)
        self.body.addWidget(self.next)
        row = QHBoxLayout()
        self.b24 = QPushButton("24h")
        self.b24.setObjectName("chip")
        self.b24.setCheckable(True)
        self.b24.setChecked(self.hour24)
        self.b24.clicked.connect(lambda: self.set_opt("hour24", self.b24.isChecked()))
        self.bnext = QPushButton("Next reminder")
        self.bnext.setObjectName("chip")
        self.bnext.setCheckable(True)
        self.bnext.setChecked(self.show_next)
        self.bnext.clicked.connect(lambda: self.set_opt("show_next", self.bnext.isChecked()))
        row.addWidget(self.b24)
        row.addWidget(self.bnext)
        row.addStretch(1)
        self.body.addLayout(row)
        QTimer(self, timeout=self.render).start(1000)
        self.render()

    def set_opt(self, key, val):
        setattr(self, "hour24" if key == "hour24" else "show_next", bool(val))
        self.remember(**{key: bool(val)})
        self.render()

    def clock_text(self, now=None):
        d = now if now is not None else datetime.now()
        h = d.hour if self.hour24 else (d.hour % 12 or 12)
        hh = f"{h:02d}" if self.hour24 else str(h)
        return f"{hh}<span style='color:#e11d2e'>:</span>{d.minute:02d}"

    def next_text(self, now=None):
        now = now if now is not None else time.time()
        timed = sorted((r for r in self.pup.reminders if r.get("due") and not r.get("done")), key=lambda r: r["due"])
        open_tasks = sum(1 for r in self.pup.reminders if r.get("kind") == "task" and not r.get("done"))
        if self.show_next and timed:
            return f"⏰ {timed[0]['text'][:34]}  ·  {when_label(timed[0]['due'], now)}"
        return f"{open_tasks} task{'s' if open_tasks != 1 else ''} open" if open_tasks else "Nothing due"

    def render(self):
        d = datetime.now()
        self.clock.setText(self.clock_text(d))
        self.day.setText(d.strftime("%A  ·  %d").upper())
        self.next.setText(self.next_text())


class DesktopWidgets:
    """Opens, closes and remembers the floating widgets. State lives in settings.json under "widgets"."""
    KINDS = {"tasks": TasksWidget, "focus": FocusWidget, "clock": ClockWidget}

    def __init__(self, pup):
        self.pup = pup
        self.live = {}

    def all_state(self):
        return self.pup.settings.setdefault("widgets", {})

    def state(self, key):
        return self.all_state().setdefault(key, {})

    def remember(self, key, **kw):
        self.state(key).update(kw)
        save_json(SETTINGS_FILE, self.pup.settings)

    def default_pos(self, w):
        try:
            r = QGuiApplication.primaryScreen().availableGeometry()
        except Exception:
            return (60, 60)
        n = len([k for k, v in self.live.items() if v is not w and v.isVisible()])
        return (r.right() - w.width() - 24 - 18 * n, r.top() + 24 + 34 * n)

    def get(self, key):
        w = self.live.get(key)
        if w is None:
            cls = NoteWidget if key.startswith("note-") else self.KINDS.get(key)
            if cls is None:
                return None
            w = cls(self, key) if cls is NoteWidget else cls(self)
            self.live[key] = w
        return w

    def toggle(self, key):
        w = self.get(key)
        if w is None:
            return False
        if w.isVisible():
            w.dismiss()
        else:
            w.open()
        return True

    def show(self, key):
        w = self.get(key)
        if w is not None:
            if w.isVisible():
                w.raise_()
            else:
                w.open()
        return w

    def new_note(self):
        ids = [int(k[6:]) for k in list(self.all_state()) + list(load_json(STICKY_FILE, {})) if re.fullmatch(r"note-d\d+", k)]
        key = f"note-d{max(ids, default=0) + 1}"
        self.live[key] = NoteWidget(self, key)
        self.live[key].open()
        return key

    def forget_note(self, key):
        self.all_state().pop(key, None)
        save_json(SETTINGS_FILE, self.pup.settings)
        self.live.pop(key, None)

    def hide_all(self):
        for w in list(self.live.values()):
            if w.isVisible():
                w.dismiss()

    def show_all(self):
        for key in ("tasks", "focus", "clock"):
            self.show(key)

    def restore(self):
        """At start-up: bring back the widgets that were open last time."""
        for key, st in list(self.all_state().items()):
            if isinstance(st, dict) and st.get("open"):
                try:
                    if key.startswith("note-d") and key not in load_json(STICKY_FILE, {}):
                        continue
                    self.show(key)
                except Exception as ex:
                    dlog(f"widgets: could not restore {key}: {ex}")

    def names(self):
        return sorted(self.KINDS)



class Pup(PupArt, QWidget):
    BASE_W, BASE_H = 300, 240
    web_ready = pyqtSignal(object)          # a song lookup finished on its thread
    ui_call = pyqtSignal(object)            # run a function on the UI thread

    def __init__(self, manual_launch):
        super().__init__(None, FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.s = SIZE
        self.resize(int(self.BASE_W * self.s), int(self.BASE_H * self.s))

        self.settings = load_json(SETTINGS_FILE, {"sound": False, "disabled": False})
        self.reminders = load_json(REMINDERS_FILE, [])
        if manual_launch:
            self.settings["disabled"] = False
            save_json(SETTINGS_FILE, self.settings)

        cid = self.settings.get("character", "shika")
        self.char_id = cid if cid in CHAR_BY_ID else "shika"
        self.panels, self.panels_ok, self.panel_sig, self.panel_busy = [], False, None, False
        self.px = self.py = 0
        self.in_corner = False
        r = self.area()
        self.in_corner = True
        self.px, self.py = self.corner_x(), self.corner_y()
        self._floor_seen = self.area().bottom()
        self.facing = -1
        self.state, self.state_t, self.t = "sleep", 0, 0
        self.phase = self.wag = 0.0
        self.blink_left = 0
        self.running = False
        self.target_x = self.px
        self.then = None
        self.hop = None
        self.base_y = self.py
        self.next_think = 2 * FPS
        self.bubble_text, self.bubble_until = "", 0
        self.emote_kind, self.emote_until, self.emote_t0 = "", 0, 0
        self.hearts = []
        self.happy_until = 0
        self.play_until = time.time() + 20       # a little hello on start
        self.idle_s, self.idle_known = 0.0, False
        self.idle_prev = None
        self.idle_unit = 1000.0
        self.taps = []
        self.zoom_left = 0
        self.alerting = None
        self.alert_sounds = 0
        self.alert_last_sound = 0
        self.press = None
        self.dragging = self.dbl = False
        self.mask_key = None
        self.hovered = False
        self.hover_pos = None
        self.hover_since = 0
        self.last_wiggle = 0
        self.peek_until = 0
        self.tilt = 0.0
        self.hover_left_at = 0
        self.rub_t0 = 0
        self.rub_next_line = 0
        self.last_touch = 0
        self.active_streak = 0
        self.cursor_prev, self.cursor_moved_at = None, time.time()
        self.work_nap = False
        self.bedtime = False
        self.work_said_at = 0
        self.grumpy_until = 0
        self.dizzy_until = 0
        self.was_roaming = False
        self.shake_marks, self.shake_sign, self.shake_last_x = [], 0, None
        self.clicks = 0
        self.paw_fired = False
        self.climb = None
        self.treat = None
        self.crumbs = []
        self.setMouseTracking(True)

        self.ball = Ball()
        self.ball_on = False
        self.ball_x = self.ball_vx = 0.0
        self.kicks = 0
        self.ball_hide_at = 0

        self.rem_mtime = None
        self.listening = False
        self.ducked = None
        self.panel = ReminderPanel(self)
        self.setup_voice()
        self.tap_timer = QTimer(self)
        self.tap_timer.setSingleShot(True)
        self.tap_timer.timeout.connect(self.resolve_clicks)
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(self.long_press)
        self.bone = Prop("bone", self.s)

        QTimer(self, timeout=self.tick).start(1000 // FPS)
        QTimer(self, timeout=self.poll_idle).start(2000)
        QTimer(self, timeout=self.check_reminders).start(10000)
        QTimer(self, timeout=self.poll_panels).start(6000)
        QTimer.singleShot(400, self.poll_panels)
        self.poll_idle()
        self.place()
        if not self.settings.get("disabled"):
            self.show()
            self.wake("smile")
        QTimer.singleShot(1500, self.check_reminders)

    # ---------- reminders file sync (shared with the Summit widgets) ----------
    def reload_reminders(self):
        try:
            mt = os.path.getmtime(REMINDERS_FILE)
        except OSError:
            return
        if mt != getattr(self, "rem_mtime", None):
            self.reminders = load_json(REMINDERS_FILE, self.reminders)
            self.rem_mtime = mt
            if self.panel.isVisible():
                self.panel.rebuild_list()

    def save_reminders(self):
        with FileLock(REMINDERS_FILE):
            save_json(REMINDERS_FILE, self.reminders)
        try:
            self.rem_mtime = os.path.getmtime(REMINDERS_FILE)
        except OSError:
            pass

    def edit_reminders(self, fn):
        """Re-read the file, apply fn(list), write it back, all under the shared lock."""
        with FileLock(REMINDERS_FILE):
            self.reminders = load_json(REMINDERS_FILE, self.reminders)
            fn(self.reminders)
            save_json(REMINDERS_FILE, self.reminders)
        try:
            self.rem_mtime = os.path.getmtime(REMINDERS_FILE)
        except OSError:
            pass

    @staticmethod
    def notify(title, body, icon="chronometer"):
        if not IS_LINUX:
            system_notify(title, body)
            return
        if shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "-a", NAME, "-i", icon, title, body],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ---------- voice ----------
    def setup_voice(self):
        self.library = Library()
        self.setup_check = SetupCheck(self)
        self.scratch = Scratchpad(self.library, self.open_dashboard)
        self.dashboard = Dashboard(self.library, self)
        self.focus_float = FocusFloat(self)
        self.widgets = DesktopWidgets(self)
        QTimer.singleShot(1500, self.widgets.restore)
        self.voice_mode = None          # "dictate" / "command" while recording
        self.voice_committed = False
        self.voice_toggle = False       # started from a shortcut instead of a held key
        self.voice_error_said = False
        self.recorder = Recorder()
        self.stt = Transcriber()
        self.stt.done.connect(self.on_transcribed)
        self.web_ready.connect(self.open_web)
        self.ui_call.connect(lambda fn: fn())
        set_ui_run(lambda fn: self.ui_call.emit(fn))
        self.stt.level = self.settings.get("cleanup", "auto")
        self.stt.speed = self.settings.get("speed", "balanced")
        self.stt.default = self.settings.get("format", "formatted")
        self.variant_bar = VariantBar(self)
        self.typer = Typer()
        self.keys = None
        if self.settings.get("ducked_from"):          # Shika stopped mid-listen last time: put the volume back
            self.ducked = float(self.settings["ducked_from"])
            self.duck_audio(False)
        self.hold_timer_v = QTimer(self, singleShot=True, timeout=self.voice_commit)
        self.max_timer_v = QTimer(self, singleShot=True, timeout=lambda: self.voice_stop())
        if not VOICE_ON:
            return
        self.keys = KeyWatcher()
        if self.keys.ok:
            self.keys.pressed.connect(self.voice_press)
            self.keys.released.connect(lambda m: self.voice_stop())
            self.keys.cancelled.connect(lambda m: self.voice_cancel())
        if mic_ok():
            QTimer.singleShot(8000, self.stt.warm)       # load the model early, off the UI thread

    def open_setup_check(self):
        sc = self.setup_check
        sc.show()
        sc.raise_()
        sc.activateWindow()
        sc.run_passive()

    def run_diagnostics_other(self):
        import glob
        R = []

        def add(name, ok, detail="", fix=""):
            R.append({"name": name, "ok": ok, "detail": str(detail)[:300], "fix": fix})
        add("Your system", None, f"{'macOS' if IS_MAC else 'Windows'} · Python {sys.version.split()[0]} · Shika {VERSION}")
        k = getattr(self, "keys", None)
        perm = ("System Settings > Privacy & Security: allow Terminal (or Python) under Input Monitoring AND Accessibility, "
                "then restart Shika" if IS_MAC else "Run Shika as a normal user. Some security tools block global key listeners.")
        add("Hold-keys: Right Ctrl and Right " + ("Option" if IS_MAC else "Alt") + " can be read", bool(k and k.ok),
            "" if (k and k.ok) else (k.error if k else "voice is switched off"), perm)
        add("Typing, paste and shortcut keys", bool(self.typer.ui), "" if self.typer.ui else self.typer.error,
            "pip install pynput" + ("; and allow Accessibility (see above)" if IS_MAC else ""))
        rc, out, err = clip_read()
        add("Clipboard read (dictation paste, 'fix grammar')", rc == 0, err, "Restart Shika.")
        add("Microphone", mic_ok(), "" if mic_ok() else mic_help(), mic_help())
        add("Taskbar / Dock", None, self.panel_status())
        add("Shika AI (local model)", ollama_ready(), OLLAMA_MODEL if ollama_ready() else "not answering",
            "Install Ollama from ollama.com, then run:  ollama pull " + OLLAMA_MODEL)
        hub = os.path.expanduser("~/.cache/huggingface/hub")
        for name in sorted({v["model"] for v in SPEEDS.values()}):
            have = bool(glob.glob(os.path.join(hub, f"models--*faster-whisper-{name}")))
            add(f"Speech model {name}", have, "downloaded" if have else "not downloaded yet",
                "Run the installer again: it downloads the model")
        return R

    def run_diagnostics(self):
        """Checks that change nothing. -> [{name, ok (True/False/None=info), detail, fix}]"""
        if not IS_LINUX:
            return self.run_diagnostics_other()
        import glob
        R = []

        def add(name, ok, detail="", fix=""):
            R.append({"name": name, "ok": ok, "detail": str(detail)[:300], "fix": fix})
        add("Your session", None, f"{os.environ.get('XDG_SESSION_TYPE', '?')} · Shika {VERSION}")
        k = getattr(self, "keys", None)
        add("Hold-keys: Right Ctrl and Right Alt can be read", bool(k and k.ok),
            "" if (k and k.ok) else (k.error if k else "voice is switched off"),
            "Restart the laptop once, then run:  id -nG | grep -w input   (it must print 'input')")
        add("Typing, paste and shortcut keys (uinput)", bool(self.typer.ui), "" if self.typer.ui else self.typer.error,
            "Restart once. Still failing? run:  ls -l /dev/uinput   (its group should be 'input')")
        rc, out = run_quiet(["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/KWin",
                             "--method", "org.freedesktop.DBus.Peer.Ping"])
        add("KDE window manager answers (D-Bus)", rc == 0, out, "sudo apt install libglib2.0-bin   (gives the gdbus tool)")
        ok, detail = kwin_run_script('print("shika self-test");', "shika-test")
        add("KDE window scripting starts (used by 'close chrome')", ok, detail,
            "Shika quits apps politely instead. Copy the report and send it to Claude.")
        rc, out = run_quiet(["gdbus", "introspect", "--session", "--dest", "org.kde.kglobalaccel",
                             "--object-path", "/component/kwin"])
        m = re.search(r"invokeShortcut\s*\(([^)]*)\)", out)
        flavour = ("name + token" if len(re.findall(r"\bin\s+s\b", m.group(1))) >= 2 else "name only") if m else ""
        add("KDE shortcuts answer (used by 'close this window')", bool(m), ("expects: " + flavour) if m else out,
            "Not fatal: Shika presses Alt+F4 instead.")
        add("Taskbar detection (Plasma panels)", self.panels_ok if self.settings.get("taskbar_aware", True) else None,
            self.panel_status(), "Not fatal: Shika uses the free area that Qt reports. Check that plasmashell is running.")
        tok = f"shika-check-{int(time.time())}"
        if shutil.which("wl-copy") and shutil.which("wl-paste"):
            old = self.typer.clip_get()
            self.typer.clip_set(tok)
            rc, out, err = clip_read()
            self._clip_restore(old)
            add("Clipboard read/write (dictation paste, 'fix grammar')", rc == 0 and out == tok,
                err or ("" if out == tok else f"read back {out[:40]!r}"), "sudo apt install wl-clipboard")
        else:
            add("Clipboard read/write (dictation paste, 'fix grammar')", False, "wl-clipboard is not installed",
                "sudo apt install wl-clipboard")
        if shutil.which("playerctl"):
            rc, out = run_quiet(["playerctl", "-l"])
            add("Music control (playerctl)", None, ("players: " + out.replace("\n", ", ")) if out
                else "no player is running right now: start a song to test 'pause'")
        else:
            add("Music control (playerctl)", False, "not installed", "sudo apt install playerctl")
        rc, src = run_quiet(["pactl", "get-default-source"])
        add("Microphone", bool(shutil.which("parec")) and rc == 0 and bool(src), src or "no default microphone found",
            "sudo apt install pulseaudio-utils, then pick an input in System Settings → Audio")
        add("Shika AI (local model)", ollama_ready(), OLLAMA_MODEL if ollama_ready() else "not answering",
            "./install.sh --with-ollama   or:   ollama pull " + OLLAMA_MODEL)
        hub = os.path.expanduser("~/.cache/huggingface/hub")
        for name in sorted({v["model"] for v in SPEEDS.values()}):
            have = bool(glob.glob(os.path.join(hub, f"models--*faster-whisper-{name}")))
            add(f"Speech model {name}", have, "downloaded" if have else "not downloaded yet",
                "re-run ./install.sh: it downloads the model")
        return R

    def open_dashboard(self, eid=None):
        self.dashboard.show_app(eid)

    def voice_press(self, mode):
        if self.voice_mode:
            return
        self.variant_bar.hide()
        if not mic_ok():
            self.voice_problem(mic_help())
            return
        self.voice_mode, self.voice_committed, self.voice_toggle = mode, False, False
        self.recorder.start()                       # record from the first ms, decide later
        self.hold_timer_v.start(HOLD_MS)

    def _duck_other(self, on):
        """Mac only: lower the system volume while you talk (Windows has no simple command for it)."""
        if not IS_MAC or DUCK_TO >= 1:
            return
        try:
            if on:
                if self.ducked is not None:
                    return
                rc, out, _ = run_capture(["osascript", "-e", "output volume of (get volume settings)"], timeout=2)
                v = float(out.strip()) / 100.0 if rc == 0 and out.strip().replace(".", "").isdigit() else 0
                if v <= 0.02:
                    return
                self.ducked = v
                self.settings["ducked_from"] = v
                save_json(SETTINGS_FILE, self.settings)
                run_capture(["osascript", "-e", f"set volume output volume {int(v * DUCK_TO * 100)}"], timeout=2)
            elif self.ducked is not None:
                run_capture(["osascript", "-e", f"set volume output volume {int(self.ducked * 100)}"], timeout=2)
                self.ducked = None
                self.settings.pop("ducked_from", None)
                save_json(SETTINGS_FILE, self.settings)
        except Exception:
            pass

    def duck_audio(self, on):
        """Turn everything else down while you talk, and back up the moment you let go."""
        if not IS_LINUX:
            return self._duck_other(on)
        if not shutil.which("wpctl") or DUCK_TO >= 1:
            return
        sink = "@DEFAULT_AUDIO_SINK@"
        try:
            if on:
                if self.ducked is not None:
                    return
                out = subprocess.run(["wpctl", "get-volume", sink], capture_output=True, text=True, timeout=1).stdout
                m = re.search(r"Volume:\s*([\d.]+)(\s*\[MUTED\])?", out)
                if not m or m.group(2) or float(m.group(1)) <= 0.02:
                    return
                self.ducked = float(m.group(1))
                self.settings["ducked_from"] = self.ducked
                save_json(SETTINGS_FILE, self.settings)
                subprocess.run(["wpctl", "set-volume", sink, f"{self.ducked * DUCK_TO:.3f}"], timeout=1)
            else:
                if self.ducked is None:
                    return
                subprocess.run(["wpctl", "set-volume", sink, f"{self.ducked:.3f}"], timeout=1)
                self.ducked = None
                self.settings.pop("ducked_from", None)
                save_json(SETTINGS_FILE, self.settings)
        except Exception:
            pass

    def start_listening_pose(self):
        """Wake up, a quick turn-around, then sit with his head tilted, all ears."""
        if self.isHidden() or self.alerting or self.dragging or self.climb or self.treat:
            return
        self.listening = True
        self.work_nap = self.bedtime = False
        self.grumpy_until = 0
        self.zoom_left = 0
        self.then = None
        self.hide_ball()
        if self.state in ("spin", "dance", "chase", "wiggle", "hop"):
            self.py = self.base_y
        self.base_y = self.py
        self.facing = -self.facing
        self.set_state("spin")

    def end_listening_pose(self):
        if not self.listening:
            return
        self.listening = False
        if self.state in ("listen", "spin"):
            self.py = self.base_y
            self.set_state("idle")

    def say_more(self):
        """After a voice job: 'aur kuch chahiye to bulaana', once his answer bubble has had its moment."""
        wait = max(0.0, self.bubble_until - time.time()) if self.bubble_text else 0.0
        wait = min(wait, 6.0)

        def go():
            if not self.voice_mode and not self.alerting and not self.isHidden():
                self.speak(LINE_MORE, 3)
        QTimer.singleShot(int((wait + 0.4) * 1000), go)

    def voice_commit(self):
        if not self.voice_mode:
            return
        self.voice_committed = True
        self.max_timer_v.start(MAX_RECORD_S * 1000)
        self.duck_audio(True)
        self.start_listening_pose()
        if self.voice_mode == "command" and self.typer.ui:
            # A lone Alt press-and-release opens the menu bar in Firefox & co. and steals the focus that Ctrl+C or
            # Ctrl+W need. A harmless extra key while Alt is down makes it Alt+F24 instead, which does nothing.
            self.typer.combo(["KEY_F24"])
        if self.stt.level != "off":
            ollama_warm()
        if self.voice_mode == "dictate":
            self.speak("bolo... likh raha hoon ✍️", 60)
        else:
            self.speak("haan bolo? 👂", 60)
            self.emote_kind = ""

    def voice_cancel(self):
        self.hold_timer_v.stop()
        self.max_timer_v.stop()
        self.recorder.stop()
        self.duck_audio(False)
        self.end_listening_pose()
        if self.voice_committed and not self.alerting:
            self.bubble_text = ""
        self.voice_mode = None

    def voice_toggle_from_shortcut(self, mode):
        """For a KDE shortcut: first press starts listening, second press stops."""
        if self.voice_mode:
            self.voice_stop()
            return
        self.voice_press(mode)
        if self.voice_mode:
            self.hold_timer_v.stop()
            self.voice_toggle = True
            self.voice_commit()

    def voice_stop(self):
        mode = self.voice_mode
        if not mode:
            return
        self.hold_timer_v.stop()
        self.max_timer_v.stop()
        pcm = self.recorder.stop()
        self.duck_audio(False)
        committed = self.voice_committed
        self.voice_mode = None
        if not committed:                           # a quick tap, not push-to-talk
            return
        if not self.alerting:
            self.bubble_text = ""
        self.emote("dots", 30)
        self.stt.run(mode, pcm)
        QTimer.singleShot(250, self.end_listening_pose)

    def voice_problem(self, text):
        self.speak("🎤 " + text, 6)
        if not self.voice_error_said:
            self.voice_error_said = True
            self.notify(f"{NAME} voice", text, "audio-input-microphone")

    def on_transcribed(self, mode, text, error):
        self.emote_kind = ""
        if error:
            log_errors(RuntimeError, RuntimeError(error), None)
            if "faster_whisper" in error or "No module" in error:
                self.voice_problem("speech engine not installed, re-run install.sh")
            else:
                self.voice_problem("couldn't understand the audio 😕")
            return
        if not text:
            self.emote("q", 1.5)
            return
        if mode == "dictate":
            self.dictate(text)
        else:
            self.voice_command(text)
        self.say_more()

    def set_speed(self, speed):
        self.settings["speed"] = speed
        save_json(SETTINGS_FILE, self.settings)
        self.stt.speed = speed
        self.stt.warm()                                 # load the new model now, not on your next dictation

    def set_format(self, fmt):
        self.settings["format"] = fmt
        save_json(SETTINGS_FILE, self.settings)
        self.stt.default = fmt

    def set_cleanup(self, level):
        self.settings["cleanup"] = level
        save_json(SETTINGS_FILE, self.settings)
        self.stt.level = level

    def dictate(self, text):
        if self.stt.how == "off":
            text = re.sub(r"\s*\b(new line|next line)\b[.,]?\s*", "\n", text, flags=re.I)
            text = re.sub(r"\s*\bnew paragraph\b[.,]?\s*", "\n\n", text, flags=re.I)
        entry = self.library.add("dictation", text.strip(), spoken=self.stt.raw)
        self.library.update(entry["id"], cleanup=self.stt.how, secs=round(self.stt.secs, 1))
        variants = dict(self.stt.variants) if self.stt.variants else {}
        current = self.stt.default if variants.get(self.stt.default) == text else None
        if self.scratch.isVisible() and self.scratch.isActiveWindow():
            self.scratch.insert(text)
            self.emote("check", 1.2)
            if variants and current:
                self.variant_bar.offer(variants, current, "scratch", entry["id"])
            return
        if self.typer.paste(text + ("" if text.endswith("\n") else " ")):
            self.emote("check", 1.2)
            if variants and current:
                QTimer.singleShot(300, lambda: self.variant_bar.offer(variants, current, "paste", entry["id"]))
        else:
            self.speak("copied! Ctrl+V dabao 📋", 3)
            self.notify(f"{NAME} dictation", "Text is on your clipboard. Typing needs one "
                        "log-out after install.", "edit-paste")

    def edit_selection(self, kind, instruction):
        """'fix grammar', 'make it formal'… on whatever text you have selected, in any app."""
        if getattr(self, "edit_busy", False):
            self.speak("ruko, pehla edit abhi chal raha hai ⏳", 2.5)
            return
        if not self.typer.ui:
            dlog("edit: no uinput")
            self.speak("keyboard access chahiye: laptop ek baar restart karo 🔑", 6)
            return
        if not clip_tools_ok():
            dlog("edit: wl-clipboard missing")
            self.speak("clipboard tool chahiye:\nsudo apt install wl-clipboard 📋", 6)
            return
        self.edit_busy = True
        self.speak("✍️ text dekh raha hoon…", 14)
        threading.Thread(target=self._edit_worker, args=(kind, instruction), daemon=True).start()

    def _clip_restore(self, orig):
        if orig is None:
            self.typer.clip_clear()
        else:
            self.typer.clip_set(orig)

    def _edit_read(self, sentinel, retry=None):
        """Wait for the copy to land. Returns (text, source). The clipboard is first set to a marker, so an
        old clipboard can never be mistaken for your selection. `retry` presses a second copy key if the
        first one hasn't produced anything after ~0.8 s."""
        cli_ok = False
        for i in range(14):
            if i == 7 and retry:
                retry()
            time.sleep(0.12)
            rc, out, err = clip_read()
            if rc == 0:
                cli_ok = True
                if out and out != sentinel:
                    return out, "copy"
        rc, out, err = clip_read(primary=True)   # text you just highlighted with the mouse
        if rc == 0 and out.strip():
            return out, "highlight"
        if not cli_ok:                                        # wl-paste itself is not answering: ask Qt's clipboard
            for _ in range(8):
                box, ev = {}, threading.Event()

                def read():
                    box["t"] = QApplication.clipboard().text()
                    ev.set()
                self.ui_call.emit(read)
                ev.wait(1.0)
                if box.get("t") and box["t"] != sentinel:
                    return box["t"], "qt"
                time.sleep(0.12)
        return "", ("empty" if cli_ok else "no-clipboard")

    def _edit_worker(self, kind, instruction):
        ui = lambda fn: self.ui_call.emit(fn)
        orig = None
        done = {"fired": False}

        def fail(msg):
            done["fired"] = True

            def go():
                self._clip_restore(orig)
                self.edit_busy = False
                self.speak(msg, 5)
            ui(go)
        try:
            orig = self.typer.clip_get()
            sentinel = f"\u200b\u27e6shika {time.time():.3f}\u27e7"
            self.typer.clip_set(sentinel)
            time.sleep(0.12)
            # Ctrl+Insert copies in browsers, Qt/GTK apps AND terminals. Ctrl+C would interrupt a program
            # running in a terminal, so it is only the second try.
            sent = self.typer.combo(["KEY_LEFTCTRL", "KEY_INSERT"])
            sel, src = self._edit_read(sentinel, retry=lambda: self.typer.combo(["KEY_LEFTCTRL", "KEY_C"]))
            dlog(f"edit[{kind}] copy sent={sent} read={src} chars={len(sel)}")
            if not sel.strip():
                if src == "no-clipboard":
                    return fail("clipboard padh nahi paaya 😕\n(🩺 Check my setup chalao)")
                return fail("select kiya hua text nahi mila 🖱️\nText select karo, phir Right Alt dabake bolo")
            out, how = None, "light"
            if ollama_ready():
                try:
                    out, how = ai_edit(kind, instruction, sel), "smart"
                except Exception as ex:
                    dlog(f"edit[{kind}] AI error {ex}")
                    out = None
                dlog(f"edit[{kind}] AI {'accepted' if out else 'rejected or failed'}")
            if not out and kind == "fix":
                out, how = polish_light(sel), "light"
            if not out:
                return fail("Shika AI se ye nahi ho paaya, text waisa hi rakha 🤷\n(Cleanup → Shika AI on hai?)"
                            if ollama_ready() else "iske liye Shika AI chahiye 🤖\n(Guide → Cleanup dekho)")
            final = out
            if final.strip() == sel.strip():
                return fail("isme kuch badalna nahi tha ✅")

            def paste():
                self.typer.paste(final)                       # replaces the selection (Ctrl+Z undoes it)
                self.library.add("note", final, "Edited: " + auto_title(sel), spoken=sel)
                QTimer.singleShot(1500, lambda: self._clip_restore(orig))   # your own clipboard comes back
                self.edit_busy = False
                self.speak("ho gaya ✅" + ("" if how == "smart" else " (basic fix)") + "\nGalat lage to Ctrl+Z", 4)
            done["fired"] = True
            ui(paste)
        except Exception as ex:
            dlog(f"edit[{kind}] crashed: {type(ex).__name__}: {ex}")
            if not done["fired"]:
                fail("edit mein dikkat aayi 😕\n(🩺 Check my setup chalao)")

    def open_web(self, web):
        b, prof, url = web["browser"], web["profile"], web["url"]
        quiet = dict(env=child_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
        said = web.get("said")
        if not IS_LINUX:
            if not b:
                open_target(url)
                self.speak(said or "khol raha hoon 🌐", 3)
            else:
                open_in_browser(b, url)
                self.speak((said or f"{BROWSERS[b]['label']} khol raha hoon 🚀")
                           + ("\n(browser profiles work on Linux only)" if prof else ""), 3.5)
            return
        if not b:
            subprocess.Popen(["xdg-open", url], **quiet)
            self.speak(said or "khol raha hoon 🌐", 3)
            return
        label = BROWSERS[b]["label"]
        picked = None
        if prof:
            picked = pick_profile(b, prof)
            if not picked:
                have = chromium_profiles(b) if BROWSERS[b]["kind"] == "chromium" else firefox_profiles()
                names = ", ".join(n for _, n in have[:6])
                self.speak(f"{label} mein '{prof}' profile nahi mila 🤷" + (f"\nhai: {names}" if names else ""), 6)
                return
        cmd = browser_command(b, picked[0] if picked else None, url)
        if not cmd:
            self.speak(f"{label} install nahi hai 🤷", 3)
            return
        subprocess.Popen(cmd, **quiet)
        where = f" · {picked[1]}" if picked else ""
        self.speak((said + f"\n{label}{where}") if said else f"{label}{where} khol raha hoon 🚀", 3.5)

    def play_media(self, cmd):
        q, plat = cmd["query"], cmd["platform"]
        base = {"browser": cmd["browser"], "profile": cmd["profile"]}
        if plat == "spotify":
            if not cmd["browser"] and (shutil.which("spotify") or find_app("spotify")):
                open_target("spotify:search:" + urllib.parse.quote(q))
                self.speak(f"Spotify pe '{q}' 🎧", 3)
            else:
                self.open_web(dict(base, url="https://open.spotify.com/search/" + urllib.parse.quote(q),
                                   said=f"Spotify pe '{q}' 🎧"))
            return
        music = plat == "youtube music"
        results = (("https://music.youtube.com/search?q=" if music else "https://www.youtube.com/results?search_query=")
                   + urllib.parse.quote_plus(q))
        if cmd["mode"] == "search":
            self.open_web(dict(base, url=results, said=f"🔎 '{q}' YouTube pe"))
            return
        self.speak(f"▶ '{q}' dhoondh raha hoon…", 8)

        def work():                                     # network lookup off the UI thread
            url = youtube_first(q, music)
            self.web_ready.emit(dict(base, url=url or results,
                                     said=f"▶ '{q}' chala raha hoon 🎵" if url else f"🔎 '{q}' ke results"))
        threading.Thread(target=work, daemon=True).start()

    def handle_control(self, low):
        """Close / minimize / switch windows, browser tab keys and music keys. True if handled."""
        say = lambda t, secs=3: self.speak(t, secs)
        no_keys = "keyboard access chahiye: laptop ek baar restart karo 🔑"
        low = re.sub(rf"^{_POLITE_PRE}", "", low.strip())                 # "please close the tab"
        low = re.sub(r"(?:[,]?\s+(?:please|now|thanks|thank you|for me))+$", "", low).strip()
        m = re.fullmatch(r"(?:close|hide|quit|exit)\s+(?:the\s+)?(scratch\s?pad|notepad|shika(?:\s+app)?|dashboard|"
                         r"(?:the\s+)?(?:focus\s+|floating\s+|pop\s?out\s+)?timer|guide)", low)
        if m:
            what = m.group(1)
            if "timer" in what:
                self.focus_float.close_float()
            elif re.match(r"scratch|notepad", what):
                self.scratch.hide()
            else:
                self.dashboard.close()
            self.emote("check", 1.2)
            return True
        for pat, keys in TAB_KEYS:
            if re.fullmatch(pat, low):
                sent = self.typer.combo(keys)
                dlog(f"tab/browser keys {keys} sent={sent}")
                if not sent:
                    say(no_keys, 5)
                elif keys == ["KEY_LEFTCTRL", "KEY_W"]:
                    say("tab band kar raha hoon ⌨️", 2)
                return True
        for pat, verb, key in MEDIA_KEYS:
            if re.fullmatch(pat, low):
                ok = False
                if IS_LINUX and shutil.which("playerctl"):
                    rc, out = run_quiet(["playerctl", "play" if verb == "play" else "pause" if verb == "pause" else verb])
                    dlog(f"playerctl {verb} rc={rc} {out}")
                    ok = rc == 0
                if not ok:                                   # no player answered: press the media key instead
                    ok = self.typer.combo([key])
                    dlog(f"media key {key} sent={ok}")
                if not ok:
                    say(no_keys, 5)
                    return True
                self.emote("note", 1.2)
                return True
        for pat, shortcut in KWIN_SHORTCUTS:
            if re.fullmatch(pat, low):
                if shortcut == "Window Close":
                    ok = self.close_active_window()
                else:
                    ok = kwin_shortcut(shortcut) or (shortcut in KEY_FALLBACK and self.typer.combo(KEY_FALLBACK[shortcut]))
                if not ok:
                    say("ye abhi nahi ho paaya 😕\n(🩺 Check my setup chalao)", 5)
                return True
        m = (re.fullmatch(r"(close|quit|exit|shut\s+down|minimi[sz]e|hide|switch\s+to|focus(?:\s+on)?|bring\s+up)\s+"
                          r"(?:the\s+|my\s+|all\s+)?(.+?)(?:\s+(?:app|apps|window|windows|browser))?", low)
             or re.fullmatch(r"()(.+?)\s+(?:band\s+karo|band\s+kar\s+do|close\s+karo)", low))
        if not m:
            return False
        verb, name = m.group(1), m.group(2).strip()
        action = ("minimize" if re.match(r"minimi|hide", verb) else
                  "focus" if re.match(r"switch|focus|bring", verb) else "close")
        # "close youtube" / "close gmail" / "close the tab…" mean the TAB. Closing the window would take every tab with it.
        if action == "close" and ((name in SITES and len(name) > 2) or re.search(r"\b(?:tab|tabs|page)\b", name)):
            sent = self.typer.combo(["KEY_LEFTCTRL", "KEY_W"])
            dlog(f"close {name!r} treated as the current tab, Ctrl+W sent={sent}")
            say("tab band kar raha hoon ⌨️" if sent else no_keys, 2 if sent else 5)
            return True
        key = CLOSE_ALIASES.get(name)
        found = None
        if not key:
            found = find_app(name)
            key = os.path.basename(found[0])[:-8].split(".")[-1].lower() if found else name
        procs = PROCESS_NAMES.get(key, [key])
        running = proc_running(procs)
        if not (CLOSE_ALIASES.get(name) or found or running):         # never pretend: that isn't an app
            dlog(f"app {action} {name!r}: no such app or process")
            say(f"'{name}' naam ka koi app nahi mila 🤷\nTab band karna ho to bolo: close tab", 5)
            return True
        ok = kwin_windows(key, action)
        how = "kde"
        if not ok and action == "close":
            ok = quit_processes(key)                         # KDE scripting is unavailable: quit it politely
            how = "sigterm"
        dlog(f"app {action} {name!r} key={key!r} ok={ok} via={how}")
        label = name.title() if len(name) > 3 else name.upper()
        if not ok:
            if action == "close":
                say(f"{label} band nahi ho paaya 😕\n(🩺 Check my setup chalao)", 5)
            else:
                say(f"'{name}' nahi mila 🤷", 2.5)
            return True
        if action != "close":
            say(f"{label} " + ("chhupa diya" if action == "minimize" else "aage le aaya") + " ✅", 2.5)
            return True
        say(f"{label} band kar raha hoon…", 3)

        def verdict():                                       # a moment later: did it really close?
            alive = proc_running(procs, exact=True)
            dlog(f"app close {name!r}: still running={alive}")
            msg = (f"{label} abhi bhi khula hai 🤔\nSave poochh raha hoga, ya dusri window khuli hai" if alive
                   else f"{label} band ho gaya ✅")
            self.ui_call.emit(lambda: self.speak(msg, 4))
        _later(1.8, verdict)
        return True

    def close_active_window(self):
        """'close this window'. Two independent ways, in the order that worked on this desktop last time."""
        ways = [("shortcut", lambda: kwin_shortcut("Window Close")),
                ("altf4", lambda: self.typer.combo(KEY_FALLBACK["Window Close"]))]
        if self.settings.get("close_via") == "altf4":
            ways.reverse()
        for name, fn in ways:
            ok = fn()
            dlog(f"close window via {name}: {ok}")
            if ok:
                return True
        return False

    def voice_command(self, raw):
        s = spoken_clean(raw)
        wake = "|".join(sorted({"shika", re.escape(self.pet_name().lower())}, key=len, reverse=True))
        s = re.sub(rf"^(?:hey\s+|ok\s+|okay\s+)?(?:{wake})[,!.\s]+", "", s, flags=re.I).strip()   # "Shika, open…"
        low = s.lower()
        say = lambda t, secs=3.5: self.speak(t, secs)

        if re.match(REMIND_RE, low) or re.search(r"[,.]?\s*(?:as\s+a\s+)?(?:reminder|remainder)$", low):
            what, due = parse_reminder(s)
            if not what and due and re.search(r"\balarm\b", low):
                what = "Alarm"
            if not what:
                say("kis cheez ka reminder? 🤔")
                return
            if due is None:
                due = time.time() + 3600
                say(f"time nahi bola, 1 ghante mein yaad dilaunga ⏰\n{what}", 5)
            else:
                say(f"⏰ {what}\n{nice_time(due)}", 4)
            self.add_reminder(what, due)
            self.notify(f"⏰ Reminder set: {what}", nice_time(due))
            return

        m = re.match(r"(?:add\s+(?:a\s+)?(?:new\s+)?task|new\s+task|add\s+to\s*do|to\s*do|task)\s*[:,]?\s+(.+)", s, re.I)
        if m:
            what, due = parse_reminder(m.group(1).strip())
            what = what or m.group(1).strip()
            self.add_reminder(what, due, kind="task")
            if due:
                self.notify(f"📋 Task set: {what}", nice_time(due))
            say(f"task added ✅\n{what}" + (f"\n🔔 {nice_time(due)}" if due else ""))
            return

        m = re.match(r"(?:take\s+a\s+note|note\s+down|write\s+down|note)\s*[:,]?\s+(.+)", s, re.I)
        if m:
            self.library.add("note", m.group(1).strip())
            self.emote("check", 2)
            say("Shika app mein save kiya 📝")
            return

        m = re.match(r"(?:please\s+)?(?:call\s+yourself|your\s+name\s+is|rename\s+(?:yourself|you|him|her)\s+(?:to|as)|"
                     r"change\s+your\s+name\s+to|(?:i'?ll|i\s+will|let'?s)\s+call\s+you)\s+(.+)", s, re.I)
        if m:
            n = clean_name(m.group(1)).title()
            if not n:
                say("kya naam rakhun? 🤔")
                return
            say(f"mera naam ab {self.set_pet_name(n)} hai 🐾", 4)
            return

        if re.fullmatch(r"(?:please\s+)?(?:surprise\s+me|(?:random|new|another)\s+(?:character|animal|pet|look)|"
                        r"change\s+(?:your\s+)?(?:character|animal|look|avatar))", low):
            self.random_character()
            return

        if re.fullmatch(r"(?:open|show)\s+(?:the\s+)?(?:characters?|pets?|animals?|avatars?)", low):
            self.open_characters()
            return

        m = re.fullmatch(r"(?:please\s+)?(?:(?:open|show|bring\s+up)\s+(?:the\s+|my\s+)?(?:(task|tasks|todo|to do|reminder|reminders)\s+(?:widget|list)|"
                         r"(focus|pomodoro)\s+(?:timer|widget)|(clock)\s+widget|(?:desktop\s+)?widgets)|"
                         r"(?:add|new|make|create)\s+(?:a\s+)?(sticky\s+note|sticky)|(hide|close)\s+(?:all\s+)?(?:the\s+)?widgets)", low)
        if m:
            if m.group(1):
                self.widgets.show("tasks")
            elif m.group(2):
                self.widgets.show("focus")
            elif m.group(3):
                self.widgets.show("clock")
            elif m.group(4):
                self.widgets.new_note()
            elif m.group(5):
                self.widgets.hide_all()
            else:
                self.widgets.show_all()
            say("theek hai 🧩", 2)
            return

        m = re.match(r"(?:please\s+)?(?:(?:switch|change|turn)\s+(?:yourself\s+)?(?:in)?to|(?:be|become)|turn\s+into)\s+(.+)", low)
        cid = match_character(m.group(1), self.names_map()) if m else None
        if cid:
            self.set_character(cid)
            return

        if re.fullmatch(r"(?:open\s+)?(?:the\s+)?(?:shika(?:\s+app)?|dashboard|my\s+notes|history)", low):
            self.open_dashboard()
            return

        if re.fullmatch(r"(?:open\s+|show\s+)?(?:the\s+)?(?:scratch\s?pad|notepad)", low):
            self.scratch.toggle()
            return

        if re.fullmatch(r"(?:please\s+)?(?:(?:check|test|diagnose|run)\s+(?:my\s+)?(?:set\s?up|shika|diagnostics?)|diagnostics?|"
                        r"diagnose(?:\s+shika)?)[.!?]*", low):
            self.open_setup_check()
            return

        edit = match_edit(re.sub(r"[.!?,]+$", "", low).strip())
        if edit:
            self.edit_selection(*edit)
            return

        media = parse_media_command(s)
        if media:
            self.play_media(media)
            return

        if self.handle_control(re.sub(r"[.!?,]+$", "", low).strip()):
            return

        if re.match(r"(?:open|launch|start|go\s+to|show|search|google|look\s+up|run)\b", low) \
                or re.search(r"\b(chrome|chromium|firefox|mozilla|brave|edge)\b", low):
            web = parse_web_command(s)
            if web:
                self.open_web(web)
                return

        m = re.match(r"(?:search|google|look\s+up)(?:\s+for)?\s+(.+)", s, re.I)
        if m:
            q = urllib.parse.quote_plus(m.group(1))
            open_target(f"https://www.google.com/search?q={q}")
            say("dhoondh raha hoon 🔎")
            return

        m = re.match(r"(?:open|launch|start|run)\s+(?:the\s+|my\s+)?(.+?)(?:\s+app)?$", s, re.I)
        if m:
            found = find_app(m.group(1))
            if not found:
                say(f"'{m.group(1)}' nahi mila 🤷")
                return
            path, label = found
            launch_path(path)
            say(f"{label} khol raha hoon 🚀", 2.5)
            return

        if re.search(r"\block\b.*\bscreen\b|\block (?:the )?(?:laptop|computer|pc)\b", low):
            lock_screen()
            return
        if not IS_LINUX:
            mv = re.search(r"\b(volume up|louder|volume down|quieter|unmute|mute)\b", low)
            if mv:
                w = mv.group(1)
                if volume_step(self, "mute" if "mute" in w else "up" if w in ("volume up", "louder") else "down"):
                    self.emote("note", 1.2)
                    return
        vol = {"volume up": ["5%+"], "louder": ["5%+"], "volume down": ["5%-"], "quieter": ["5%-"]}
        for phrase, arg in vol.items():
            if phrase in low and shutil.which("wpctl"):
                subprocess.Popen(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@"] + arg)
                self.emote("note", 1.2)
                return
        if re.search(r"\b(mute|unmute)\b", low) and shutil.which("wpctl"):
            subprocess.Popen(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
            return
        if re.search(r"\bwhat(?:'s| is)?\s+(?:the\s+)?time\b|\btime kya\b", low):
            say(datetime.now().strftime("abhi %I:%M %p hai ⌚").replace(" 0", " "))
            return

        if re.search(r"\b(go to )?sleep\b|\bso ja", low):
            self.order_sleep()
        elif re.search(r"\b(ball|fetch)\b", low):
            self.order_ball()
        elif re.search(r"\bclimb\b", low):
            self.order_climb()
        elif re.search(r"\btreat\b|\bbiscuit\b", low):
            self.give_treat()
        elif re.search(r"\b(wake up|come here|hello|hi) (shika)?\b", low) or low in ("shika", "hey shika"):
            self.wake_from_launcher()
        else:
            say(f"samjha nahi 🥺\n“{s}”", 4)

    # ---------- characters and names ----------
    def names_map(self):
        return {cid: n for cid, n in (self.settings.get("names") or {}).items() if cid in CHAR_BY_ID}

    def name_for(self, cid):
        spec = CHAR_BY_ID.get(cid) or CHAR_BY_ID["shika"]
        return clean_name(self.names_map().get(spec["id"])) or spec["name"]

    def pet_name(self):
        return self.name_for(self.char_id)

    def refresh_characters(self):
        page = getattr(getattr(self, "dashboard", None), "chars_page", None)
        if page is not None:
            page.refresh()
        self.update()

    def set_pet_name(self, text, cid=None):
        """Rename one character ('' goes back to its own name). -> the name now in use."""
        cid = cid if cid in CHAR_BY_ID else self.char_id
        n = clean_name(text)
        names = self.names_map()
        if n and n != CHAR_BY_ID[cid]["name"]:
            names[cid] = n
        else:
            names.pop(cid, None)
        self.settings["names"] = names
        save_json(SETTINGS_FILE, self.settings)
        self.refresh_characters()
        return self.name_for(cid)

    def set_character(self, cid, say=True):
        if cid not in CHAR_BY_ID:
            return False
        self.char_id = cid
        self.settings["character"] = cid
        save_json(SETTINGS_FILE, self.settings)
        self.happy_until = time.time() + 3
        self.refresh_characters()
        if say:
            self.speak(f"main {self.pet_name()} hoon 🐾", 3)
        return True

    def random_character(self):
        cid = random.choice([c["id"] for c in CHARACTERS if c["id"] != self.char_id])
        self.set_character(cid)
        return cid

    def open_characters(self):
        self.open_dashboard()
        self.dashboard.set_filter("characters")

    # ---------- taskbar awareness ----------
    def screen_index(self):
        try:
            scr = QGuiApplication.screenAt(QPoint(int(self.px), int(self.py) - 10)) or QGuiApplication.primaryScreen()
            return QGuiApplication.screens().index(scr)
        except Exception:
            return None

    def poll_panels(self):
        """Ask Plasma about its panels (off the UI thread). Runs at start and every few seconds."""
        if not IS_LINUX or not self.settings.get("taskbar_aware", True) or self.panel_busy:
            return
        self.panel_busy = True

        def work():
            try:
                res = read_panels()
            except Exception as ex:
                dlog(f"panels: read crashed {ex}")
                res = None
            self.ui_call.emit(lambda: self.set_panels(res))
        threading.Thread(target=work, daemon=True).start()

    def set_panels(self, res):
        self.panel_busy = False
        if res is None:
            return                                   # keep what we knew; plasmashell may be restarting
        sig = json.dumps(res, sort_keys=True)
        if sig != self.panel_sig or not self.panels_ok:
            self.panel_sig, self.panels, self.panels_ok = sig, res, True
            dlog(f"panels: {sig}")
            self.refresh_characters()
        try:
            scr = QGuiApplication.primaryScreen()
            dlog(f"floor: qt_bottom_inset={scr.geometry().bottom() - scr.availableGeometry().bottom()} "
                 f"area_bottom={self.area().bottom()} screen_bottom={scr.geometry().bottom()}")
        except Exception:
            pass
        self.reseat()

    def set_taskbar_aware(self, on):
        self.settings["taskbar_aware"] = bool(on)
        save_json(SETTINGS_FILE, self.settings)
        if on:
            self.poll_panels()
        self.reseat()
        self.refresh_characters()

    def panel_status(self):
        if not IS_LINUX:
            return ("Your pet stands above the " + ("Dock" if IS_MAC else "taskbar")
                    + " using the free screen area that " + ("macOS" if IS_MAC else "Windows") + " reports.")
        if not self.settings.get("taskbar_aware", True):
            return "Taskbar awareness is off. Your pet uses the free screen area that Qt reports."
        if not self.panels_ok:
            return ("Could not ask Plasma about its panels yet. Your pet uses the free screen area that Qt reports "
                    "and keeps clear of a side taskbar.")
        return describe_panels(self.panels, self.screen_index())

    def reseat(self):
        """The free screen area changed (panel moved, resized, hidden): stand on the new floor."""
        if self.hop or self.dragging or self.state == "held":
            return
        old, new = self._floor_seen, self.area().bottom()
        self._floor_seen = new
        if old != new and (self.in_corner or abs(self.py - old) <= 3 or self.py > new):
            self.py = self.base_y = new
        r = self.area()
        if self.in_corner:
            self.px = self.corner_x()
        else:
            self.px = max(r.left() + 50 * self.s, min(r.right() - 48 * self.s, self.px))
        self.place()
        self.update()

    # ---------- geometry ----------
    def area(self):
        """The free part of the screen: what Qt reports, plus every visible Plasma panel."""
        scr = (QGuiApplication.screenAt(QPoint(int(self.px), int(self.py) - 10))
               or QGuiApplication.primaryScreen())
        a, f = scr.availableGeometry(), scr.geometry()
        l, t = a.left() - f.left(), a.top() - f.top()
        r, b = f.right() - a.right(), f.bottom() - a.bottom()
        if self.settings.get("taskbar_aware", True) and self.panels_ok:
            pl, pt, pr, pb = panel_insets(self.panels, self.screen_index())
            l, t, r, b = max(l, pl), max(t, pt), max(r, pr), max(b, pb)
        elif IS_LINUX and TASKBAR_RIGHT and r <= 2:
            r = TASKBAR_RIGHT                # Plasma didn't report the side panel: keep clear of it ourselves
        return QRect(f.x() + l, f.y() + t, f.width() - l - r, f.height() - t - b)

    def full(self):
        scr = (QGuiApplication.screenAt(QPoint(int(self.px), int(self.py) - 10))
               or QGuiApplication.primaryScreen())
        return scr.geometry()

    def corner_x(self):
        """His home spot: bottom-right, right up against the taskbar (never on top of it)."""
        return self.area().right() - 44 * self.s

    def corner_y(self):
        """The floor of his home spot: the top of a bottom taskbar, or the screen edge when there is none."""
        return self.area().bottom()

    def ground(self):
        return self.area().bottom()

    def anchor(self):
        return self.width() / 2, self.height() - 10 * self.s

    def place(self):
        ax, ay = self.anchor()
        self.move(int(self.px - ax), int(self.py - ay))

    def on_ground(self):
        return abs(self.py - self.ground()) < 3

    def on_support(self):
        """On the floor, or standing on one of his ladder platforms."""
        if self.on_ground():
            return True
        c = self.climb
        return bool(c and c["segs"] and abs(self.py - c["segs"][-1]["top"]) < 3)

    # ---------- data ----------
    def pending(self):
        """Everything that will bark: undone tasks and reminders that have a time."""
        return sorted((r for r in self.reminders if not r.get("done") and r.get("due")),
                      key=lambda r: r["due"])

    def add_reminder(self, text, due, kind="reminder"):
        item = {"id": f"{time.time():.6f}", "kind": kind, "text": text, "due": due,
                "done": False, "urgent": False}
        self.edit_reminders(lambda rs: rs.append(item))
        self.happy_until = time.time() + 2
        self.add_hearts(2)
        self.emote("check", 2.5)

    def delete_reminder(self, rid):
        self.edit_reminders(lambda rs: rs.__setitem__(slice(None), [r for r in rs if r["id"] != rid]))

    def set_sound(self, on):
        self.settings["bark"] = bool(on)
        save_json(SETTINGS_FILE, self.settings)

    # ---------- on / off ----------
    def turn_off(self):
        self.settings["disabled"] = True
        save_json(SETTINGS_FILE, self.settings)
        self.hide_ball()
        self.end_climb()
        self.cancel_treat()
        self.emote("zzz", 3)
        self.go_corner_and_sleep()
        QTimer.singleShot(5000, self.hide_if_off)

    def hide_if_off(self):
        if self.settings.get("disabled") and not self.alerting:
            self.hide()
            self.hide_ball()

    def wake_from_launcher(self):
        self.settings["disabled"] = False
        save_json(SETTINGS_FILE, self.settings)
        self.show()
        self.raise_()
        self.play_until = time.time() + 30
        self.wake("heart")

    # ---------- idle detection ----------
    def poll_idle(self):
        cur = QCursor.pos()
        if self.cursor_prev is None or cur != self.cursor_prev:
            self.cursor_moved_at = time.time()
        self.cursor_prev = cur
        try:
            if not IS_LINUX:
                raise OSError("no idle service")      # falls back to "has the mouse moved lately?"
            out = subprocess.run(
                ["gdbus", "call", "--session", "--dest", "org.freedesktop.ScreenSaver",
                 "--object-path", "/org/freedesktop/ScreenSaver",
                 "--method", "org.freedesktop.ScreenSaver.GetSessionIdleTime"],
                capture_output=True, text=True, timeout=1).stdout
            v = int(re.search(r"(\d+)\s*,?\s*\)", out).group(1))
        except Exception:
            # no idle service: fall back to "has the mouse moved lately?"
            self.idle_known = False
            self.idle_s = time.time() - self.cursor_moved_at
            self.active_streak = self.active_streak + 1 if self.idle_s < 3 else 0
            return
        now = time.monotonic()
        if self.idle_prev and v > self.idle_prev[0]:
            rate = (v - self.idle_prev[0]) / max(0.1, now - self.idle_prev[1])
            self.idle_unit = 1000.0 if rate > 50 else 1.0
        self.idle_prev = (v, now)
        self.idle_s = v / self.idle_unit
        self.idle_known = True
        self.active_streak = self.active_streak + 1 if self.idle_s < 3 else 0

    def busy(self):
        if time.time() < self.play_until:
            return False
        return (not self.idle_known) or self.idle_s < FREE_AFTER

    def working(self):
        """You've been typing / mousing continuously for the last few seconds."""
        return self.active_streak >= 2 and time.time() - self.last_touch > 20

    def roaming(self):
        return (not self.in_corner and not self.alerting and not self.dragging and not self.hovered
                and self.state in ("walk", "ball", "idle", "sit", "sniff", "bow", "chase",
                                   "dance", "spin", "stretch", "wiggle"))

    def start_work_nap(self):
        if self.listening:
            return
        self.work_nap = True
        self.play_until = 0
        self.zoom_left = 0
        self.then = None
        self.hide_ball()
        self.speak(LINE_WORK, 4.5)
        if self.state not in ("idle", "sit"):
            if self.state in ("spin", "dance", "chase", "wiggle"):
                self.py = self.base_y
            self.set_state("idle")
        if not WORK_NAP_IN_PLACE:
            self.work_nap = False
            self.bedtime = False

    # ---------- reminders ----------
    def check_reminders(self):
        if self.alerting:
            return
        self.reload_reminders()
        now = time.time()
        for r in self.pending():
            if r["due"] <= now:
                self.start_alert(r)
                break

    def start_alert(self, r):
        self.alerting = r
        self.alert_sounds = 0
        self.alert_last_sound = 0
        self.panel.hide()
        if self.isHidden():
            self.show()
        self.raise_()
        self.hide_ball()
        self.end_climb()
        self.cancel_treat()
        self.work_nap = False
        self.bedtime = False
        self.grumpy_until = 0
        if self.state in ("spin", "dance", "chase", "wiggle", "bonk", "sad", "rub", "paw", "eat", "sulk"):
            self.py = min(self.py, self.ground())
            self.set_state("idle")
        late = time.time() - r["due"]
        head = ("📋 " if r.get("kind") == "task" else "⏰ ") + r["text"] + ("\n(was due " + nice_time(r["due"]) + ")" if late > 300 else "")
        self.emote_kind = ""
        self.say(head + "\n\ntap = done  ·  double-tap = snooze 10 min", 10 ** 7)
        self.notify(("📋 " if r.get("kind") == "task" else "⏰ ") + r["text"],
                    f"{self.pet_name()} is making noise by the screen. Tap when done.")
        mid = (self.area().left() + self.area().right()) / 2
        self.go_ground_x(mid, run=True, then=lambda: self.set_state("alert"))

    def finish_alert(self, done):
        r = self.alerting
        if not r:
            return
        def apply(rs):
            for x in rs:
                if x["id"] != r["id"]:
                    continue
                if not done:
                    x["due"] = time.time() + 600
                elif x.get("repeat"):                 # repeating: roll forward to the next future slot
                    step = int(x["repeat"]) * 60
                    while x["due"] <= time.time():
                        x["due"] += step
                else:
                    x["done"] = True
        self.edit_reminders(apply)
        self.alerting = None
        self.bubble_text = ""
        self.set_state("idle")
        self.base_y = self.py = self.area().bottom()
        if done:
            self.happy_until = time.time() + 3
            self.add_hearts(4)
            self.emote("check", 2.5)
        else:
            self.emote("clock", 2.5)
        self.play_until = time.time() + 20
        if self.settings.get("disabled"):
            QTimer.singleShot(3000, self.hide_if_off)
        QTimer.singleShot(3000, self.check_reminders)

    # ---------- actions ----------
    def set_state(self, st):
        self.state, self.state_t = st, 0
        if st not in ("walk", "ball"):
            self.running = False

    def say(self, text, secs=3.0):
        """Text bubble (reminder alerts use this directly)."""
        self.bubble_text, self.bubble_until = text, time.time() + secs

    def speak(self, text, secs=3.0):
        """Chatty bubble; never covers a reminder alert."""
        if self.alerting:
            return
        self.emote_kind = ""
        self.say(text, secs)

    def emote(self, kind, secs=2.0):
        if self.bubble_text:
            return
        self.emote_kind, self.emote_until, self.emote_t0 = kind, time.time() + secs, self.t

    def add_hearts(self, n=3, color=None):
        ax, ay = self.anchor()
        for _ in range(n):
            c = color if color is not None else WHITE
            if color == "mix":
                c = random.choice((PINK, RED, WHITE, QColor(255, 150, 190)))
            self.hearts.append([ax + random.choice((-1, 1)) * random.uniform(16, 30) * self.s,
                                ay - 66 * self.s - random.uniform(0, 10) * self.s,
                                random.randint(-8, 0), c])

    def walk_to(self, x, run=False, then=None):
        r = self.area()
        self.target_x = max(r.left() + 50 * self.s, min(self.corner_x(), x))
        self.running, self.then = run, then
        self.in_corner = False
        self.set_state("walk")
        self.running = run

    def hop_to(self, x, y, then=None, frames=10, height=14):
        self.hop = dict(sx=self.px, sy=self.py, ex=x, ey=y, T=frames, h=height * self.s)
        if abs(x - self.px) > 1:
            self.facing = 1 if x > self.px else -1
        self.then = then
        self.set_state("hop")

    def step_down(self, then=None):
        """Little hops down imaginary steps until he's back on the floor."""
        r = self.area()
        if self.py >= r.bottom() - 2:
            self.py = r.bottom()
            self.set_state("idle")
            if then:
                then()
            return
        nx = max(r.left() + 50 * self.s, min(r.right() - 48 * self.s, self.px + self.facing * 16 * self.s))
        ny = min(r.bottom(), self.py + 34 * self.s)
        self.hop_to(nx, ny, then=lambda: self.step_down(then))

    def settle_corner(self):
        self.in_corner = True
        fb = self.corner_y()
        if fb - self.py > 3:
            self.hop_to(self.corner_x(), fb, then=self.go_sleep)
        else:
            self.go_sleep()

    def leave_corner(self, then=None):
        """Little jump up from the very corner back onto the floor."""
        self.in_corner = False
        top = self.area().bottom()
        if self.py > top + 3:
            self.facing = -1
            self.hop_to(self.px - 26 * self.s, top, then=then, frames=12, height=18)
            return True
        return False

    def go_ground_x(self, x, run=False, then=None):
        if self.in_corner and self.leave_corner(lambda: self.walk_to(x, run, then)):
            return
        self.in_corner = False
        if self.on_ground():
            self.walk_to(x, run, then)
        else:
            self.step_down(then=lambda: self.walk_to(x, run, then))

    def arrive(self):
        cb, self.then = self.then, None
        if cb:
            cb()

    def go_sleep(self):
        self.facing = -1
        self.hide_ball()
        self.set_state("sleep")

    def go_corner_and_sleep(self):
        if self.in_corner and abs(self.px - self.corner_x()) < 4:
            self.go_sleep()
            return
        self.go_ground_x(self.corner_x(), then=self.settle_corner)

    def wake(self, kind="note", secs=2.0):
        self.emote(kind, secs)
        if self.in_corner and self.leave_corner(lambda: self.set_state("stretch")):
            return
        self.set_state("stretch")

    def hide_ball(self):
        self.ball_on = False
        self.ball.hide()

    # ---------- taps ----------
    CLIMB_STATES = ("ladder", "climb", "climbdown")

    def resolve_clicks(self):
        n, self.clicks = self.clicks, 0
        if n >= 3:
            self.triple_tap()
        elif n == 2:
            self.double_tap()
        elif n == 1:
            self.single_tap()

    def forgive(self):
        self.grumpy_until = 0
        self.speak(random.choice(FORGIVE_LINES), 3)
        self.happy_until = time.time() + 3
        self.add_hearts(4, "mix")
        if self.state == "sleep":
            self.wake("heart")
        elif self.state in ("sulk", "sad"):
            self.set_state("idle")

    def single_tap(self):
        now = time.time()
        if self.alerting:
            self.finish_alert(done=True)
            return
        self.last_touch = now
        self.play_until = max(self.play_until, now + PLAY_TIME)
        if now < self.grumpy_until or self.state in ("sulk", "sad"):
            self.forgive()
            return
        if self.state == "sleep":
            self.work_nap = False
            self.bedtime = False
            self.wake(random.choice(["smile", "note", "heart"]))
            if random.random() < 0.4:
                self.speak(random.choice(["hmm? uth gaya! 🐶", "khelna hai? 🎾", "*yawn* 🥱"]), 2.5)
            return
        self.taps = [t for t in self.taps if now - t < 3] + [now]
        if len(self.taps) >= 4 and self.state not in self.CLIMB_STATES and not self.climb:
            self.taps = []
            self.start_zoomies()
            return
        self.happy_until = now + 2.5
        self.add_hearts()
        self.emote("heart", 1.8)

    def double_tap(self):
        if self.alerting:
            self.finish_alert(done=False)
            return
        self.last_touch = time.time()
        self.play_until = max(self.play_until, time.time() + PLAY_TIME)
        if self.state == "sleep":
            self.work_nap = False
            self.bedtime = False
            self.grumpy_until = 0
            self.wake("excl")
            return
        if self.state in self.CLIMB_STATES or self.state in ("bonk", "sulk", "held", "hop"):
            self.emote("excl", 1.2)
            return
        self.base_y = self.py
        self.set_state(random.choice(["spin", "dance"]))

    def triple_tap(self):
        """Chappal time."""
        now = time.time()
        if self.alerting:
            self.finish_alert(done=True)
            return
        self.last_touch = now
        if self.state in self.CLIMB_STATES or self.state in ("hop", "held"):
            self.speak("abhi nahi, main busy hoon! 😤", 2.5)
            return
        self.play_until = max(self.play_until, now + PLAY_TIME)
        self.work_nap = False
        self.bedtime = False
        self.hide_ball()
        self.zoom_left = 0
        self.then = None
        self.bubble_text = ""
        if self.state in ("spin", "dance", "chase", "wiggle"):
            self.py = self.base_y
        self.base_y = self.py
        self.set_state("bonk")

    def long_press(self):
        if self.press is None or self.dragging or self.alerting:
            return
        if self.state in self.CLIMB_STATES or self.state in ("bonk", "hop", "held"):
            return
        self.paw_fired = True
        self.last_touch = time.time()
        self.play_until = max(self.play_until, time.time() + PLAY_TIME)
        self.work_nap = False
        self.bedtime = False
        if now_grumpy := time.time() < self.grumpy_until:
            self.grumpy_until = 0
        self.zoom_left = 0
        self.then = None
        if self.state in ("spin", "dance", "chase", "wiggle"):
            self.py = self.base_y
        self.set_state("paw")
        self.speak("haath milao! 🐾" if not now_grumpy else "okay okay... dosti? 🐾", 2.5)

    def start_zoomies(self):
        self.emote("excl", 1.5)
        self.zoom_left = 4
        self.zoom_next()

    def zoom_next(self):
        r = self.area()
        if self.zoom_left <= 0:
            self.set_state("sit")
            self.emote("sweat", 2.2)
            return
        self.zoom_left -= 1
        left, right = r.left() + 80 * self.s, r.right() - 80 * self.s
        target = left if self.px > (left + right) / 2 else right
        target += random.uniform(-60, 60)
        self.walk_to(target, run=True, then=self.zoom_next)

    def start_ball(self):
        r = self.area()
        self.ball_x = max(r.left() + 30, min(r.right() - 30, self.px + self.facing * 80 * self.s))
        self.ball_vx = 0.0
        self.kicks = 0
        self.ball_on = True
        self.ball_hide_at = 0
        self.ball.show()
        self.ball.raise_()
        self.raise_()
        self.emote("excl", 1.3)
        self.set_state("ball")

    # ---------- panel / middle-click orders ----------
    def wake_for_order(self):
        """Common prep for things you ask him to do. Returns False if he can't right now."""
        if self.alerting or self.dragging or self.isHidden():
            return False
        if self.state in self.CLIMB_STATES or self.state in ("hop", "held", "bonk"):
            return False
        now = time.time()
        self.last_touch = now
        self.play_until = max(self.play_until, now + PLAY_TIME)
        self.work_nap = False
        self.bedtime = False
        self.grumpy_until = 0
        self.zoom_left = 0
        if self.state in ("spin", "dance", "chase", "wiggle"):
            self.py = self.base_y
        return True

    def order_sleep(self):
        """Right-click → Sleep: off to his spot by the taskbar, stays asleep until you tap him."""
        if self.alerting or self.isHidden():
            return
        if self.state in self.CLIMB_STATES or self.state in ("hop", "held"):
            QTimer.singleShot(2500, self.order_sleep)        # let him finish the step first
            return
        if self.state in ("spin", "dance", "chase", "wiggle"):
            self.py = self.base_y
        self.bedtime = True
        self.play_until = 0
        self.zoom_left = 0
        self.then = None
        self.grumpy_until = 0
        self.work_nap = False
        self.hide_ball()
        self.cancel_treat()
        self.end_climb()
        self.speak(random.choice(["okay... good night 😴", "so jaata hoon 💤", "tap karke utha lena 🥱"]), 2.5)
        self.set_state("idle")
        self.go_corner_and_sleep()

    def order_ball(self):
        if not self.wake_for_order():
            return
        if self.climb or not self.on_ground():
            self.emote("excl", 1.2)
            return
        self.go_ground_x(self.px + self.facing * 10, then=self.start_ball)

    def order_climb(self):
        if not self.wake_for_order():
            return
        if self.climb:
            self.emote("smile", 1.5)
            return
        self.hide_ball()
        self.start_climb()

    def give_treat(self):
        if not self.wake_for_order():
            return
        self.cancel_treat()
        if not self.on_ground() or self.climb:
            # up on a platform: he catches it mid-air
            self.happy_until = time.time() + 3
            self.add_hearts(3, "mix")
            self.speak("catch! yum 😋", 2.5)
            return
        r = self.area()
        side = self.facing if random.random() < 0.7 else -self.facing
        x = self.px + side * random.uniform(110, 200) * self.s
        if x < r.left() + 60 * self.s or x > self.corner_x() - 10:
            x = self.px - side * random.uniform(110, 200) * self.s
        x = max(r.left() + 60 * self.s, min(self.corner_x() - 10, x))
        self.treat = dict(x=x, y=float(r.top() + 40), vy=0.0, landed=False)
        self.bone.move(int(x - self.bone.width() / 2), int(self.treat["y"]))
        self.bone.show()
        self.bone.raise_()
        self.raise_()
        self.emote("excl", 1.4)
        self.hide_ball()
        d = 1 if x > self.px else -1
        self.go_ground_x(x - d * 26 * self.s, run=True, then=self.eat_treat)

    def cancel_treat(self):
        self.treat = None
        self.bone.hide()

    def eat_treat(self):
        if not self.treat:
            return
        if not self.treat["landed"]:
            self.set_state("wait_treat")         # stare up at it until it lands
            return
        self.facing = 1 if self.treat["x"] >= self.px else -1
        self.cancel_treat()
        self.next_think = 2 * FPS
        self.set_state("eat")

    # ---------- ladder climbing ----------
    def start_climb(self):
        r = self.area()
        L = LADDER_H * self.s
        room = int((r.bottom() - r.top() - 230 * self.s) // L)
        levels = min(random.randint(2, 4), room)
        if levels < 1:
            return False
        self.climb = dict(levels=levels, level=0, L=L, segs=[], phase="up", x=r.left() + 50 * self.s)
        self.emote("q", 1.5)
        self.go_ground_x(self.climb["x"], then=self.climb_next)
        return True

    def climb_next(self):
        """Pull out a ladder, put a platform on the left border above it."""
        c = self.climb
        if not c:
            return
        r = self.area()
        base = self.py
        top = base - c["L"]
        ladder = Prop("ladder", self.s)
        plat = Prop("platform", self.s)
        pw, ph = int(96 * self.s), int(28 * self.s)
        plat.resize(pw, ph)
        plat.setMask(QRegion(0, 0, pw, ph))
        c["segs"].append(dict(ladder=ladder, plat=plat, base=base, top=top, left=r.left()))
        self.facing = -1
        self.emote("excl", 1.2)
        self.set_state("ladder")

    def place_seg(self, seg, grow, slide):
        s = self.s
        lw = int(32 * s)
        lh = max(2, int((seg["base"] - seg["top"] + 6 * s) * grow))
        lx = int(self.climb["x"] - lw / 2) if self.climb else int(self.px - lw / 2)
        seg["ladder"].setGeometry(lx, int(seg["base"] - lh), lw, lh)
        seg["ladder"].setMask(QRegion(0, 0, lw, lh))
        pw = seg["plat"].width()
        seg["plat"].move(int(seg["left"] - pw * (1 - slide)), int(seg["top"]))

    def pack_seg(self, seg):
        for w in (seg["ladder"], seg["plat"]):
            w.hide()
            w.deleteLater()

    def end_climb(self):
        if self.climb:
            for seg in self.climb["segs"]:
                self.pack_seg(seg)
            self.climb = None

    def climb_think(self):
        c = self.climb
        now = time.time()
        if c["phase"] == "up":
            if c["level"] == 0 and (abs(self.px - c["x"]) > 4 or not self.on_ground()):
                self.go_ground_x(c["x"], then=self.climb_next)
                return
            if c["level"] < c["levels"]:
                self.climb_next()
                return
            c["phase"] = "perch"
            self.set_state("sit")
            self.facing = 1
            self.happy_until = now + 2
            if random.random() < 0.6:
                self.speak(random.choice(["upar se sab dikhta hai! 😎", "dekho main kitna upar! 🏔️",
                                          "yahan se tumhari screen dikh rahi hai 👀"]), 3)
            else:
                self.emote("sparkle", 2)
            self.next_think = random.randint(6 * FPS, 10 * FPS)
            return
        if c["phase"] == "perch":
            c["phase"] = "down"
        if c["segs"]:
            self.facing = -1
            self.set_state("climbdown")
        else:
            self.climb = None
            self.emote("check", 2)
            self.next_think = 2 * FPS

    # ---------- brain ----------
    def think(self):
        if self.hovered or self.listening:
            return
        now = time.time()
        if self.busy():
            if self.work_nap and self.on_support():
                if self.state != "sleep":
                    self.go_sleep()
                return
            if self.climb and self.on_support():
                if self.state != "sleep":
                    self.go_sleep()
                return
            if self.climb:
                self.end_climb()
            if not self.on_ground():
                self.step_down()
                return
            cx = self.corner_x()
            if abs(self.px - cx) > 3 or not self.in_corner:
                self.hide_ball()
                self.walk_to(cx, then=self.settle_corner)
                if random.random() < 0.5:
                    self.emote("zzz", 2)
            elif self.state != "sleep":
                self.go_sleep()
            return

        if self.state == "sleep":
            if now < self.grumpy_until or self.bedtime:
                return
            if self.work_nap:
                self.work_nap = False
                self.wake("smile")
                self.speak(random.choice(["kaam khatam? chalo khelte hain! 🐶", "uth gaya! break time? 🎾"]), 3)
                return
            self.wake(random.choice(["note", "smile"]))
            return
        if self.in_corner and self.leave_corner(lambda: self.set_state("idle")):
            return
        if not self.on_support():
            self.end_climb()
            self.step_down()
            return
        if self.state_t < self.next_think:
            return
        if self.climb:
            self.climb_think()
            return
        r = self.area()
        roll = random.random()
        self.next_think = random.randint(3 * FPS, 7 * FPS)
        if roll < 0.18:
            self.walk_to(random.uniform(r.left() + 80, r.right() - 80),
                         then=lambda: self.set_state("idle"))
        elif roll < 0.26:
            self.set_state("sit")
        elif roll < 0.34:
            self.set_state("sniff")
        elif roll < 0.42:
            self.set_state("bow")
        elif roll < 0.49:
            self.base_y = self.py
            self.set_state("chase")
            self.emote("q", 1.6)
        elif roll < 0.61:
            self.start_ball()
        elif roll < 0.67:
            self.start_zoomies()
        elif roll < 0.76:
            if not self.start_climb():
                self.set_state("sit")
        elif roll < 0.85:
            self.chase_cursor()
        elif roll < 0.92 and CHATTY:
            self.chatter()
        else:
            self.emote(random.choice(FUN_EMOTES), 2)

    def chase_cursor(self):
        """Trot over to your mouse pointer if it's down near the floor."""
        cur = QCursor.pos()
        r = self.area()
        if r.contains(cur) and r.bottom() - cur.y() < 260 and abs(cur.x() - self.px) > 60:
            self.emote("excl", 1.2)
            self.walk_to(cur.x() - (40 if cur.x() > self.px else -40) * self.s, run=True,
                         then=lambda: (self.set_state("sniff"), self.emote("q", 1.5)))
        else:
            self.set_state("sit")
            self.emote(random.choice(["q", "dots"]), 1.8)

    def chatter(self):
        h = datetime.now().hour
        part = ("night" if h >= 23 or h < 5 else "morning" if h < 11
                else "day" if h < 17 else "evening")
        self.speak(random.choice(CHATTER[part]), 3)
        self.set_state("sit")

    # ---------- main loop ----------
    def tick(self):
        self.t += 1
        self.state_t += 1
        now = time.time()
        r = self.area()
        ground = self.ground()
        s = self.s
        happy = now < self.happy_until
        lively = (happy or self.running
                  or self.state in ("bow", "chase", "alert", "dance", "wiggle", "rub", "eat", "paw", "listen")
                  or (self.hovered and self.state not in ("sleep", "sulk", "sad", "bonk")))
        self.hover_tick(now)
        want_tilt = 13 if (self.hovered and self.state in ("idle", "sit", "sniff", "rub", "paw")) else 0
        if self.state == "rub":
            want_tilt = 13 + math.sin(self.t * 0.15) * 6
        if self.state == "listen":                     # curious head tilt, slowly switching sides
            want_tilt = 15 * (1 if math.sin(self.t * 0.035) >= 0 else -1) + math.sin(self.t * 0.2) * 2
        self.tilt += (want_tilt - self.tilt) * 0.15
        self.wag += 0.6 if lively else 0.18

        if self.blink_left > 0:
            self.blink_left -= 1
        elif random.random() < 0.012:
            self.blink_left = 4

        st = self.state
        if st == "walk":
            step = (4.4 if self.running else 1.5) * s
            dx = self.target_x - self.px
            self.py = ground
            if abs(dx) <= step:
                self.px = self.target_x
                self.set_state("idle")
                self.arrive()
            else:
                self.facing = 1 if dx > 0 else -1
                self.px += step * self.facing
                self.phase += 0.32 * (step / (1.5 * s)) ** 0.6
        elif st == "hop":
            h = self.hop
            f = min(1.0, self.state_t / h["T"])
            self.px = h["sx"] + (h["ex"] - h["sx"]) * f
            self.py = h["sy"] + (h["ey"] - h["sy"]) * f - math.sin(math.pi * f) * h["h"]
            if f >= 1:
                self.set_state("idle")
                self.arrive()
        elif st == "spin":
            f = min(1.0, self.state_t / (18 if self.listening else 26))
            self.py = self.base_y - math.sin(math.pi * f) * (18 if self.listening else 32) * s
            if f >= 1:
                self.py = self.base_y
                if self.listening:                     # quick turn done: sit and listen
                    self.set_state("listen")
                else:
                    self.happy_until = now + 2
                    self.add_hearts(2)
                    self.emote("sparkle", 2)
                    self.set_state("idle")
        elif st == "listen":
            self.py = self.base_y
            if not self.listening:
                self.set_state("idle")
        elif st == "dance":
            self.py = self.base_y - abs(math.sin(self.state_t * 0.3)) * 10 * s
            if self.state_t % 10 == 0:
                self.facing *= -1
            if self.state_t > 60:
                self.py = self.base_y
                self.happy_until = now + 2
                self.add_hearts(3)
                self.emote("note", 2)
                self.set_state("idle")
        elif st == "chase":
            if self.state_t % 5 == 0:
                self.facing *= -1
            self.py = self.base_y - abs(math.sin(self.state_t * 0.4)) * 5 * s
            if self.state_t > 70:
                self.py = self.base_y
                self.set_state("sit")
                self.emote("dots", 2)
        elif st == "wiggle":
            self.py = self.base_y - abs(math.sin(self.state_t * 0.5)) * 4 * s
            if self.state_t > 36:
                self.py = self.base_y
                self.set_state("idle")
        elif st == "bow":
            if self.state_t == 18:
                self.emote("excl", 1.6)
            if self.state_t > 60:
                self.set_state("idle")
        elif st in ("sniff", "stretch"):
            if self.state_t > (70 if st == "sniff" else 40):
                self.set_state("idle")
        elif st == "alert":
            self.py = ground - abs(math.sin(self.state_t * 0.25)) * 16 * s
            if self.settings.get("bark", True) and self.alert_sounds < 6 and now - self.alert_last_sound > 20:
                self.alert_sounds += 1
                self.alert_last_sound = now
                play_bark()
        elif st == "ball":
            self.py = ground
            dx = self.ball_x - self.px
            if abs(dx) > 22 * s:
                self.facing = 1 if dx > 0 else -1
                self.running = True
                self.px += 4.0 * s * self.facing
                self.phase += 0.45
            elif abs(self.ball_vx) < 1.2:
                self.kicks += 1
                if self.kicks > random.randint(3, 5):
                    self.set_state("sit")
                    self.emote("smile", 2)
                    self.ball_hide_at = now + 5
                else:
                    if self.ball_x < r.left() + 120:
                        self.facing = 1
                    elif self.ball_x > r.right() - 120:
                        self.facing = -1
                    self.ball_vx = self.facing * random.uniform(7, 11) * s
                    self.happy_until = now + 1
        elif st == "bonk":
            T = self.state_t
            if T == 12:                                   # whack!
                self.dizzy_until = now + 2.6
            if T == 20:
                self.speak(LINE_BONK, 4.5)
            if T > 105:
                self.set_state("sad")
        elif st == "sad":
            if self.state_t > 150:
                self.set_state("idle")
                self.emote("dots", 2)
        elif st == "sulk":
            if self.state_t == 155:
                self.bubble_text = ""
                self.emote("angry", 2.5)
            if self.state_t > 225:
                self.go_sleep()
        elif st == "rub":
            T = self.state_t
            if T % 9 == 0:
                self.add_hearts(1, "mix")
            if now > self.rub_next_line:
                self.rub_next_line = now + random.uniform(3.2, 4.5)
                self.speak(random.choice(RUB_LINES), 2.6)
            if not self.hovered and now - self.hover_left_at > 0.5:
                self.end_rub()
        elif st == "paw":
            if self.state_t == 45:
                self.happy_until = now + 2
                self.add_hearts(3, "mix")
            if self.state_t > 75:
                self.set_state("idle")
        elif st == "wait_treat":
            if not self.treat:
                self.set_state("idle")
            elif self.treat["landed"]:
                self.eat_treat()
        elif st == "eat":
            if self.state_t % 8 == 0 and self.state_t < 56:
                ax, ay = self.anchor()
                self.crumbs.append([ax + self.facing * 30 * s, ay - 14 * s,
                                    random.uniform(-1.5, 1.5) * s, -random.uniform(1, 2.5) * s, 0])
            if self.state_t > 64:
                self.happy_until = now + 3
                self.add_hearts(3, "mix")
                self.speak(random.choice(["yummy! 😋", "aur hai? 🥺🦴", "thank you hooman! 💖"]), 2.5)
                self.set_state("idle")
        elif st == "ladder":
            seg = self.climb["segs"][-1] if self.climb and self.climb["segs"] else None
            if not seg:
                self.set_state("idle")
            else:
                T = self.state_t
                grow = min(1.0, T / 30)
                slide = max(0.0, min(1.0, (T - 30) / 14))
                self.place_seg(seg, grow, slide)
                if T == 1:
                    seg["ladder"].show()
                    self.raise_()
                if T == 31:
                    seg["plat"].show()
                    self.raise_()
                if T >= 50:
                    self.set_state("climb")
        elif st == "climb":
            seg = self.climb["segs"][-1] if self.climb and self.climb["segs"] else None
            if not seg:
                self.set_state("idle")
            else:
                self.facing = -1
                self.py -= 1.6 * s
                self.phase += 0.3
                if self.py <= seg["top"]:
                    self.py = seg["top"]
                    self.climb["level"] += 1
                    self.set_state("idle")
                    self.next_think = 12
                    if self.climb["level"] >= self.climb["levels"]:
                        self.emote("sparkle", 2)
        elif st == "climbdown":
            seg = self.climb["segs"][-1] if self.climb and self.climb["segs"] else None
            if not seg:
                self.set_state("idle")
            else:
                self.facing = -1
                self.py += 2.0 * s
                self.phase += 0.35
                if self.py >= seg["base"]:
                    self.py = seg["base"]
                    self.pack_seg(seg)
                    self.climb["segs"].pop()
                    self.set_state("idle")
                    self.next_think = 8

        if self.treat and not self.treat["landed"]:
            t = self.treat
            t["vy"] += 0.9
            t["y"] += t["vy"]
            if t["y"] >= ground - self.bone.height():
                t["y"] = ground - self.bone.height()
                if t["vy"] > 4:
                    t["vy"] = -t["vy"] * 0.35
                else:
                    t["landed"] = True
            self.bone.move(int(t["x"] - self.bone.width() / 2), int(t["y"]))

        for c in self.crumbs:
            c[0] += c[2]
            c[1] += c[3]
            c[3] += 0.25 * s
            c[4] += 1
        self.crumbs = [c for c in self.crumbs if c[4] < 18]

        if (self.working() and self.roaming() and not self.work_nap
                and self.state not in self.CLIMB_STATES and not self.bubble_text
                and now - self.work_said_at > 90):
            self.work_said_at = now
            self.start_work_nap()

        if self.ball_on:
            self.ball_x += self.ball_vx
            self.ball_vx *= 0.965
            if self.ball_x < r.left() + 14:
                self.ball_x, self.ball_vx = r.left() + 14, abs(self.ball_vx) * 0.7
            elif self.ball_x > r.right() - 14:
                self.ball_x, self.ball_vx = r.right() - 14, -abs(self.ball_vx) * 0.7
            self.ball.angle += self.ball_vx * 6
            self.ball.move(int(self.ball_x - 13), int(ground - 26))
            self.ball.update()
            if self.ball_hide_at and now > self.ball_hide_at:
                self.hide_ball()

        if self.py > ground and not self.dragging:
            self.py = ground
        if (self.state in ("idle", "sit", "sleep") and not self.alerting
                and not self.isHidden() and not self.dragging):
            self.think()

        for h in self.hearts:
            h[2] += 1
            if h[2] > 0:
                h[1] -= 1.1 * s
                h[0] += math.sin(h[2] * 0.2) * 0.5
        self.hearts = [h for h in self.hearts if h[2] < 45]
        if len(self.hearts) > 40:
            self.hearts = self.hearts[-40:]
        if self.bubble_text and now > self.bubble_until:
            self.bubble_text = ""
        if self.emote_kind and now > self.emote_until:
            self.emote_kind = ""

        if not self.isHidden():
            self.place()
            self.update_mask()
            self.update()

    # ---------- hover / rubs ----------
    RUB_OK = ("idle", "sit", "sniff", "wiggle", "sleep", "stretch", "bow", "sad", "sulk")

    def enterEvent(self, e):
        now = time.time()
        if not (self.hover_left_at and now - self.hover_left_at < 0.6):
            self.hover_since = now                     # brief flickers don't reset the rub timer
        self.hovered = True
        self.hover_pos = e.position()
        if self.alerting:
            return
        if self.state == "sleep":
            self.peek_until = now + 2.5
            return
        if self.state == "walk" and not self.running:
            self.then = None
            self.set_state("idle")

    def leaveEvent(self, e):
        self.hovered = False
        self.hover_pos = None
        self.hover_left_at = time.time()

    def hover_tick(self, now):
        if not self.hovered or self.alerting or self.dragging or self.press is not None:
            return
        self.last_touch = now
        if self.state in self.RUB_OK and now - self.hover_since >= RUB_AFTER and self.on_support():
            self.start_rub()
            return
        if self.state == "sleep":
            if now > self.peek_until and random.random() < 0.01:
                self.peek_until = now + 1.5
            return
        if self.hover_pos is not None and self.state in ("idle", "sit", "sniff", "rub"):
            ax, _ = self.anchor()
            dx = self.hover_pos.x() - ax
            if abs(dx) > 12 * self.s:
                self.facing = 1 if dx > 0 else -1
        if (self.state in ("idle", "sit") and now - self.hover_since > 1.8
                and now - self.last_wiggle > 6):
            self.last_wiggle = now
            self.base_y = self.py
            self.set_state("wiggle")

    def start_rub(self):
        now = time.time()
        if self.state == "wiggle":
            self.py = self.base_y
        was_grumpy = now < self.grumpy_until or self.state in ("sulk", "sad")
        self.grumpy_until = 0
        self.work_nap = False
        self.bedtime = False
        self.then = None
        self.rub_t0 = now
        self.rub_next_line = now + 3.5
        self.play_until = max(self.play_until, now + PLAY_TIME)
        self.set_state("rub")
        self.add_hearts(5, "mix")
        self.speak("okay... sab maaf 🥺❤️" if was_grumpy else "hehe yahi chahiye tha 🥰❤️", 2.6)

    def end_rub(self):
        self.set_state("idle")
        self.happy_until = time.time() + 3
        self.add_hearts(3, "mix")
        self.emote("hearts", 2.2)
        self.next_think = 2 * FPS
        self.play_until = max(self.play_until, time.time() + PLAY_TIME)

    def rub_level(self):
        """1 = blissful sit, 2 = melted into a happy puddle (after ~10s of rubs)."""
        return 2 if self.state == "rub" and time.time() - self.rub_t0 > 5 else 1

    def wheelEvent(self, e):
        if self.alerting or self.state in self.CLIMB_STATES or self.state in ("held", "hop", "bonk"):
            return
        now = time.time()
        self.last_touch = now
        self.play_until = max(self.play_until, now + PLAY_TIME)
        if self.state == "sleep":
            self.peek_until = now + 2
        self.happy_until = now + 1.5
        if random.random() < 0.35:
            self.add_hearts(1, "mix")
        if self.state in ("idle", "sit") and now - self.last_wiggle > 1.5:
            self.last_wiggle = now
            self.base_y = self.py
            self.set_state("wiggle")
        self.emote("heart", 1.2)

    # ---------- input ----------
    def mousePressEvent(self, e):
        b = e.button()
        if b == Qt.MouseButton.LeftButton:
            self.press = e.globalPosition().toPoint()
            self.dragging = False
            self.paw_fired = False
            self.hold_timer.start(650)
        elif b == Qt.MouseButton.MiddleButton:
            self.give_treat()
        elif b == Qt.MouseButton.RightButton:
            if self.state == "sleep":
                self.peek_until = time.time() + 3
            self.panel.open_near(e.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, e):
        # Qt sends the 2nd click of a fast pair here instead of mousePressEvent;
        # we count clicks ourselves, so treat it like a normal press.
        self.mousePressEvent(e)

    def mouseMoveEvent(self, e):
        self.hover_pos = e.position()
        if self.press is None or self.alerting:
            return
        gp = e.globalPosition().toPoint()
        now = time.time()
        if not self.dragging and (gp - self.press).manhattanLength() > 8 and not self.paw_fired:
            self.dragging = True
            self.hold_timer.stop()
            self.tap_timer.stop()
            self.clicks = 0
            self.was_roaming = self.state not in ("sleep", "sulk") and not self.in_corner
            if self.state in ("spin", "dance", "chase", "wiggle"):
                self.py = self.base_y
            self.end_climb()
            self.cancel_treat()
            self.hide_ball()
            self.zoom_left = 0
            self.work_nap = False
            self.bedtime = False
            self.in_corner = False
            self.then = None
            self.last_touch = now
            self.play_until = max(self.play_until, now + PLAY_TIME)
            self.shake_marks, self.shake_sign, self.shake_last_x = [], 0, gp.x()
            self.set_state("held")
            self.emote("excl", 1.2)
        if self.dragging:
            self.px, self.py = gp.x(), gp.y() + 50 * self.s
            dx = gp.x() - (self.shake_last_x if self.shake_last_x is not None else gp.x())
            if abs(dx) > 10:
                sign = 1 if dx > 0 else -1
                if self.shake_sign and sign != self.shake_sign:
                    self.shake_marks = [t for t in self.shake_marks if now - t < 1.4] + [now]
                self.shake_sign = sign
                self.shake_last_x = gp.x()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self.hold_timer.stop()
        if self.dragging:
            self.dragging = False
            self.drop(e.globalPosition().toPoint())
        elif self.paw_fired:
            self.paw_fired = False
        else:
            self.hover_since = time.time()
            self.clicks += 1
            self.tap_timer.start(max(250, min(450, QApplication.doubleClickInterval())))
        self.press = None

    def drop(self, gp):
        s = self.s
        now = time.time()
        floor = self.corner_y()
        dizzy = len([t for t in self.shake_marks if now - t < 1.4]) >= 5
        corner = gp.x() > self.area().right() - 240 * s and gp.y() > floor - 230 * s
        if corner:
            self.in_corner = True
            then = self.start_sulk if self.was_roaming else self.go_sleep
            self.set_state("idle")
            self.hop_to(self.corner_x(), floor, then=then, frames=14, height=12)
            return
        r = self.area()
        self.px = max(r.left() + 50 * s, min(r.right() - 48 * s, self.px))
        self.set_state("idle")
        self.step_down(then=self.get_dizzy if dizzy else None)
        if dizzy:
            self.dizzy_until = now + 4

    def get_dizzy(self):
        self.dizzy_until = time.time() + 3
        self.set_state("sit")
        self.next_think = 3 * FPS
        self.speak("chakkar aa gaye... 😵", 3)

    def start_sulk(self):
        now = time.time()
        self.in_corner = True
        self.facing = 1                      # turns his back on you
        self.play_until = 0
        self.grumpy_until = now + 30
        self.set_state("sulk")
        self.speak(LINE_SCOLD, 5)

    # ---------- drawing ----------
    def update_mask(self):
        s = self.s
        ax, ay = self.anchor()
        pad = 60 if self.state in ("spin", "held", "rub", "climb", "climbdown", "bonk") else 54
        rects = [QRect(int(ax - pad * s), int(ay - 86 * s), int(2 * pad * s), int(98 * s))]
        if self.state == "bonk" or time.time() < self.dizzy_until:
            rects.append(QRect(int(ax - 64 * s), int(ay - 150 * s), int(128 * s), int(70 * s)))
        if self.crumbs:
            rects.append(QRect(int(ax - 80 * s), int(ay - 40 * s), int(160 * s), int(50 * s)))
        if self.hearts or self.alerting:
            rects.append(QRect(int(ax - 64 * s), int(ay - 134 * s), int(128 * s), int(52 * s)))
        if self.state == "sleep":
            rects.append(QRect(int(ax - 60 * s), int(ay - 92 * s), int(70 * s), int(60 * s)))
        if self.bubble_text:
            rects.append(self.bubble_rect().adjusted(-2, -2, 2, 12))
        elif self.emote_kind:
            rects.append(self.emote_rect().adjusted(-4, -4, 4, 12))
        key = tuple((r.x(), r.y(), r.width(), r.height()) for r in rects)
        if key != self.mask_key:
            self.mask_key = key
            region = QRegion()
            for r in rects:
                region = region.united(QRegion(r))
            self.setMask(region)

    def bubble_font(self):
        f = QFont("Inter", max(7, round(10 * self.s)))
        f.setBold(True)
        return f

    def bubble_rect(self):
        s = self.s
        ax, ay = self.anchor()
        fm = QFontMetrics(self.bubble_font())
        br = fm.boundingRect(QRect(0, 0, int(230 * s), 2000),
                             Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, self.bubble_text)
        w, h = br.width() + int(24 * s), br.height() + int(16 * s)
        hx = ax + self.facing * 20 * s
        x = max(4, min(self.width() - w - 4, hx - w / 2))
        y = ay - 80 * s - h
        return QRect(int(x), int(max(2, y)), int(w), int(h))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ax, ay = self.anchor()
        s = self.s

        p.save()
        p.translate(ax, ay)
        if self.state == "bonk" and 12 <= self.state_t < 30:          # squash from the whack
            k = math.sin(math.pi * (self.state_t - 12) / 18)
            p.scale(1 + 0.16 * k, 1 - 0.22 * k)
        p.scale(s * self.facing, s)
        if self.state in ("climb", "climbdown"):
            p.translate(0, -24)
            p.rotate(-72)
            p.translate(0, 24)
        if self.state == "spin":
            p.translate(0, -30)
            p.rotate(-360 * min(1.0, self.state_t / (18 if self.listening else 26)))
            p.translate(0, 30)
        if self.state == "wiggle":
            p.translate(math.sin(self.state_t * 0.9) * 2.2, 0)
        self.draw_pup(p)
        p.restore()

        if self.crumbs:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(214, 180, 130))
            for cx, cy, _, _, _ in self.crumbs:
                p.drawEllipse(QPointF(cx, cy), 1.8 * s, 1.8 * s)

        for x, y, age, col in self.hearts:
            if age >= 0:
                self.draw_heart(p, x, y, 7 * s, max(0, 255 - age * 5.6), col)

        if self.state == "alert" and (self.t // 8) % 2 == 0:
            f = QFont("Inter", max(8, round(16 * s)))
            f.setWeight(QFont.Weight.Black)
            p.setFont(f)
            p.setPen(INK)
            hx = ax + self.facing * 20 * s
            p.drawText(QPointF(hx - 34 * s, ay - 70 * s), "!")
            p.drawText(QPointF(hx + 28 * s, ay - 74 * s), "!")

        if self.state == "sleep":
            for i in range(3):
                k = (self.t * 0.02 + i / 3) % 1
                f = QFont("Inter", max(6, round((8 + i * 3) * s)))
                f.setBold(True)
                p.setFont(f)
                c = QColor(LINE)
                c.setAlpha(int(255 * (1 - k)))
                p.setPen(c)
                hx = ax + self.facing * 26 * s
                p.drawText(QPointF(hx + self.facing * (6 + k * 18) * s - 4 * s, ay - (36 + k * 44) * s), "z")

        if self.bubble_text:
            self.draw_bubble(p)
        elif self.emote_kind:
            self.draw_emote(p)

    @staticmethod
    def heart_path(x, y, size):
        path = QPainterPath()
        path.moveTo(x, y + size * 0.9)
        path.cubicTo(x - size * 1.6, y - size * 0.1, x - size * 0.7, y - size * 1.2, x, y - size * 0.35)
        path.cubicTo(x + size * 0.7, y - size * 1.2, x + size * 1.6, y - size * 0.1, x, y + size * 0.9)
        return path

    def draw_heart(self, p, x, y, size, alpha, color=WHITE):
        fill, edge = QColor(color), QColor(INK)
        fill.setAlpha(int(alpha))
        edge.setAlpha(int(alpha))
        p.setPen(pen(edge, 1.6 * self.s))
        p.setBrush(fill)
        p.drawPath(self.heart_path(x, y, size))

    def emote_rect(self):
        s = self.s
        ax, ay = self.anchor()
        w, h = 38 * s, 32 * s
        hx = ax + self.facing * 24 * s
        x = max(4, min(self.width() - w - 4, hx - w / 2 + self.facing * 10 * s))
        return QRect(int(x), int(ay - 80 * s - h), int(w), int(h))

    def bubble_shape(self, r, hx, radius, tail_w, tail_h):
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        tail = QPainterPath()
        tail.moveTo(hx - tail_w, r.bottom() - 1)
        tail.lineTo(hx - tail_w * 0.2, r.bottom() + tail_h)
        tail.lineTo(hx + tail_w * 0.6, r.bottom() - 1)
        tail.closeSubpath()
        return path.united(tail)

    def draw_emote(self, p):
        s = self.s
        ax, _ = self.anchor()
        age = self.t - self.emote_t0
        pop = min(1.0, age / 6)
        scale = 0.55 + 0.45 * (1 - (1 - pop) ** 3) + (0.06 * math.sin(pop * math.pi) if pop < 1 else 0)
        r = QRectF(self.emote_rect())
        bob = math.sin(self.t * 0.12) * 1.2 * s
        c = r.center() + QPointF(0, bob)
        p.save()
        p.translate(c)
        p.scale(scale, scale)
        p.translate(-c)
        hx = max(r.left() + 10 * s, min(r.right() - 10 * s, ax + self.facing * 24 * s))
        p.setPen(pen(INK, 2.2 * s))
        p.setBrush(WHITE)
        p.drawPath(self.bubble_shape(r.translated(0, bob), hx, 13 * s, 6 * s, 8 * s))
        self.draw_glyph(p, self.emote_kind, c.x(), c.y(), s)
        p.restore()

    def draw_glyph(self, p, kind, cx, cy, s):
        u = s
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(INK)
        if kind == "heart":
            beat = 1 + 0.08 * math.sin(self.t * 0.4)
            p.drawPath(self.heart_path(cx, cy - 1 * u, 7 * u * beat))
        elif kind == "note":
            p.setPen(pen(INK, 2.2 * u))
            p.drawLine(QPointF(cx + 3 * u, cy + 6 * u), QPointF(cx + 3 * u, cy - 8 * u))
            p.drawLine(QPointF(cx + 3 * u, cy - 8 * u), QPointF(cx + 8 * u, cy - 5 * u))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx - 0.5 * u, cy + 6 * u), 4 * u, 3 * u)
        elif kind in ("excl", "q", "zzz"):
            f = QFont("Inter", max(7, round((15 if kind != "zzz" else 11) * u)))
            f.setWeight(QFont.Weight.Black)
            p.setFont(f)
            p.setPen(INK)
            text = {"excl": "!", "q": "?", "zzz": "z Z"}[kind]
            p.drawText(QRectF(cx - 18 * u, cy - 14 * u, 36 * u, 28 * u),
                       Qt.AlignmentFlag.AlignCenter, text)
        elif kind == "dots":
            for i in range(3):
                on = (self.t // 6) % 4 > i
                p.setBrush(INK if on else QColor(170, 170, 170))
                p.drawEllipse(QPointF(cx + (i - 1) * 7 * u, cy), 2.4 * u, 2.4 * u)
        elif kind == "check":
            p.setPen(pen(INK, 3 * u))
            p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath(QPointF(cx - 7 * u, cy))
            path.lineTo(cx - 2 * u, cy + 5 * u)
            path.lineTo(cx + 8 * u, cy - 6 * u)
            p.drawPath(path)
        elif kind == "sparkle":
            for ox, oy, k in ((-3, 1, 1.0), (7, -6, 0.5)):
                kk = k * (0.85 + 0.15 * math.sin(self.t * 0.3 + ox))
                star = QPainterPath(QPointF(cx + ox * u, cy + (oy - 8 * kk) * u))
                for qx, qy in ((1.6, -1.6), (8, 0), (1.6, 1.6), (0, 8), (-1.6, 1.6), (-8, 0), (-1.6, -1.6), (0, -8)):
                    star.lineTo(cx + (ox + qx * kk) * u, cy + (oy + qy * kk) * u)
                p.drawPath(star)
        elif kind == "sweat":
            drop = QPainterPath(QPointF(cx, cy - 8 * u))
            drop.cubicTo(cx + 2 * u, cy - 3 * u, cx + 6 * u, cy + 1 * u, cx + 5 * u, cy + 4 * u)
            drop.cubicTo(cx + 4 * u, cy + 8 * u, cx - 4 * u, cy + 8 * u, cx - 5 * u, cy + 4 * u)
            drop.cubicTo(cx - 6 * u, cy + 1 * u, cx - 2 * u, cy - 3 * u, cx, cy - 8 * u)
            p.drawPath(drop)
            p.setBrush(WHITE)
            p.drawEllipse(QPointF(cx - 2 * u, cy + 2 * u), 1.4 * u, 1.8 * u)
        elif kind == "clock":
            p.setPen(pen(INK, 2.2 * u))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 8 * u, 8 * u)
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy - 5 * u))
            p.drawLine(QPointF(cx, cy), QPointF(cx + 4 * u, cy + 2 * u))
        elif kind == "hearts":
            for ox, oy, k, col in ((-4, 1, 5.5, PINK), (6, -4, 3.6, RED), (6, 6, 2.6, PINK)):
                beat = 1 + 0.1 * math.sin(self.t * 0.4 + ox)
                p.setBrush(col)
                p.drawPath(self.heart_path(cx + ox * u, cy + oy * u, k * u * beat))
        elif kind == "angry":                         # anime anger mark
            p.setPen(pen(RED, 2.6 * u))
            p.setBrush(Qt.BrushStyle.NoBrush)
            g = 2.2 * u
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                a = QPainterPath(QPointF(cx + sx * g, cy + sy * 7 * u))
                a.quadTo(cx + sx * g, cy + sy * g, cx + sx * 7 * u, cy + sy * g)
                p.drawPath(a)
        elif kind == "smile":
            p.setPen(pen(INK, 2.2 * u))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for ex in (-5, 5):
                a = QPainterPath(QPointF(cx + (ex - 3) * u, cy - 1 * u))
                a.quadTo(cx + ex * u, cy - 6 * u, cx + (ex + 3) * u, cy - 1 * u)
                p.drawPath(a)
            m = QPainterPath(QPointF(cx - 5 * u, cy + 3 * u))
            m.quadTo(cx, cy + 8 * u, cx + 5 * u, cy + 3 * u)
            p.drawPath(m)

    def draw_bubble(self, p):
        s = self.s
        ax, _ = self.anchor()
        r = QRectF(self.bubble_rect())
        hx = max(r.left() + 14 * s, min(r.right() - 14 * s, ax + self.facing * 20 * s))
        path = QPainterPath()
        path.addRoundedRect(r, 11 * s, 11 * s)
        tail = QPainterPath()
        tail.moveTo(hx - 7 * s, r.bottom() - 1)
        tail.lineTo(hx, r.bottom() + 9 * s)
        tail.lineTo(hx + 7 * s, r.bottom() - 1)
        tail.closeSubpath()
        p.setPen(pen(INK, (3 if self.alerting else 2.2) * s))
        p.setBrush(WHITE)
        p.drawPath(path.united(tail))
        p.setPen(INK)
        p.setFont(self.bubble_font())
        p.drawText(r, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter, self.bubble_text)


def log_errors(kind, value, tb):
    """Keep Shika alive on a bug (PyQt would abort) and write it to ~/.config/shika/error.log."""
    import traceback
    try:
        os.makedirs(CONF, exist_ok=True)
        with open(os.path.join(CONF, "error.log"), "a") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} v{VERSION}\n")
            traceback.print_exception(kind, value, tb, file=f)
    except Exception:
        pass


def main():
    sys.excepthook = log_errors
    app = QApplication(sys.argv)
    app.setApplicationName(NAME)
    app.setDesktopFileName("shika")                    # taskbar groups the window under the Shika launcher
    icon = next((p for p in (os.path.expanduser("~/.local/share/icons/hicolor/scalable/apps/shika.svg"),
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "shika-icon.svg"))
                 if os.path.exists(p)), "")
    app.setWindowIcon(QIcon(icon) if os.path.exists(icon) else QIcon.fromTheme("face-smile"))
    migrate_old_config()
    app.setQuitOnLastWindowClosed(False)

    sock = QLocalSocket()
    sock.connectToServer(SOCKET)
    msg = b"wake"
    for flag, word in (("--scratchpad", b"scratchpad"), ("--dictate", b"dictate"), ("--command", b"command"),
                       ("--dashboard", b"dashboard"), ("--widgets", b"widgets")):
        if flag in sys.argv:
            msg = word
    for a in sys.argv:
        if a.startswith("--open="):
            msg = b"open:" + a[7:].encode()
    if sock.waitForConnected(300):          # already running: pass the message on and leave
        sock.write(msg)
        sock.flush()
        sock.waitForBytesWritten(300)
        return

    QLocalServer.removeServer(SOCKET)
    server = QLocalServer()
    server.listen(SOCKET)
    pup = Pup(manual_launch="--autostart" not in sys.argv)

    def handle(word):
        if word == "scratchpad":
            pup.scratch.toggle()
        elif word == "dashboard":
            pup.open_dashboard()
        elif word == "widgets":
            pup.widgets.show_all()
        elif word.startswith("open:"):
            pup.open_dashboard(word[5:])
        elif word in ("dictate", "command"):
            pup.voice_toggle_from_shortcut(word)
        else:
            pup.wake_from_launcher()

    def on_conn():
        c = server.nextPendingConnection()
        if not c:
            return
        c.waitForReadyRead(300)
        word = bytes(c.readAll()).decode(errors="ignore").strip() or "wake"
        c.disconnectFromServer()
        handle(word)

    if msg != b"wake":
        QTimer.singleShot(1200, lambda: handle(msg.decode()))

    server.newConnection.connect(on_conn)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
