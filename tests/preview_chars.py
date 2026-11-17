"""Draws every character in several poses to an SVG sheet, with no Qt installed.

    python3 preview_chars.py [out.svg] [char_id ...]

It loads the real shika.py with a tiny painter that writes SVG, so what you see is what the pup's own
drawing code produces. Open the SVG in any browser.
"""
import os, sys, math, time, importlib.util, types, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["HOME"] = tempfile.mkdtemp(prefix="shika-prev-")
sys.path.insert(0, HERE)
from PyQt6 import QtGui, QtCore            # the fake Qt used by the tests


class Name(str):
    """Qt.Something.Else -> the string 'Qt.Something.Else' (hashable, comparable, can be OR-ed)."""
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return Name(self + "." + k)
    def __or__(self, o): return Name(self + "|" + o)
    __ror__ = __or__
    def __call__(self, *a, **k): return Name(self)


class PointF:
    def __init__(self, x=0, y=0):
        if isinstance(x, PointF):
            x, y = x._x, x._y
        self._x, self._y = float(x), float(y)
    def x(self): return self._x
    def y(self): return self._y
    def __add__(self, o): return PointF(self._x + o._x, self._y + o._y)
    def __sub__(self, o): return PointF(self._x - o._x, self._y - o._y)
    def __mul__(self, k): return PointF(self._x * k, self._y * k)
    def __iadd__(self, o): return self + o


class RectF:
    def __init__(self, x=0, y=0, w=0, h=0):
        self._x, self._y, self._w, self._h = float(x), float(y), float(w), float(h)
    def x(self): return self._x
    def y(self): return self._y
    def width(self): return self._w
    def height(self): return self._h
    def bottom(self): return self._y + self._h
    def right(self): return self._x + self._w


class Color:
    def __init__(self, r=0, g=0, b=0, a=255):
        if isinstance(r, Color):
            r, g, b, a = r.r, r.g, r.b, r.a
        self.r, self.g, self.b, self.a = int(r), int(g), int(b), int(a)
    def setAlpha(self, a): self.a = int(a)
    def css(self): return f"rgb({self.r},{self.g},{self.b})"
    def op(self): return round(self.a / 255, 3)


class Pen:
    def __init__(self, c=None, w=1):
        self.c, self.w = c if isinstance(c, Color) else None, w
    def setCapStyle(self, *a): pass
    def setJoinStyle(self, *a): pass


class Path:
    def __init__(self, start=None):
        self.d = []
        self.cur = (0.0, 0.0)
        if isinstance(start, PointF):
            self.moveTo(start)
    def _pt(self, a, b=None):
        return (a.x(), a.y()) if isinstance(a, PointF) else (float(a), float(b))
    def moveTo(self, a, b=None):
        self.cur = self._pt(a, b); self.d.append("M%.2f %.2f" % self.cur)
    def lineTo(self, a, b=None):
        self.cur = self._pt(a, b); self.d.append("L%.2f %.2f" % self.cur)
    def quadTo(self, c, e, *rest):
        if not isinstance(c, PointF):                      # quadTo(cx, cy, ex, ey)
            c, e = PointF(c, e), PointF(*rest)
        self.cur = (e.x(), e.y()); self.d.append("Q%.2f %.2f %.2f %.2f" % (c.x(), c.y(), e.x(), e.y()))
    def closeSubpath(self): self.d.append("Z")
    def addEllipse(self, c, rx, ry):
        x, y = c.x(), c.y()
        self.d.append("M%.2f %.2f A%.2f %.2f 0 1 0 %.2f %.2f A%.2f %.2f 0 1 0 %.2f %.2f Z" %
                      (x - rx, y, rx, ry, x + rx, y, rx, ry, x - rx, y))
    def united(self, o):
        n = Path(); n.d = self.d + o.d; return n
    def svg(self): return " ".join(self.d)


_CLIPS = [0]                                          # clip ids must be unique across the whole sheet


class Painter:
    def __init__(self, *a):
        self.out, self.levels, self.pen, self.brush = [], [[]], None, None
    # state
    def setRenderHint(self, *a): pass
    def setFont(self, f=None, *a): self.font_px = getattr(f, 'px', 8)
    def setPen(self, p): self.pen = Pen(p, 1) if isinstance(p, Color) else (p if isinstance(p, Pen) else None)
    def setBrush(self, b): self.brush = b if isinstance(b, Color) else None
    def setOpacity(self, o): self._open(f'<g opacity="{o:.3f}">')
    def end(self): pass
    # groups
    def _open(self, tag): self.out.append(tag); self.levels[-1].append(1)
    def save(self): self.levels.append([])
    def restore(self):
        for _ in self.levels.pop(): self.out.append("</g>")
    def translate(self, x, y=None):
        if isinstance(x, PointF): x, y = x.x(), x.y()
        self._open(f'<g transform="translate({x:.2f} {y:.2f})">')
    def rotate(self, a): self._open(f'<g transform="rotate({a:.2f})">')
    def scale(self, sx, sy): self._open(f'<g transform="scale({sx:.3f} {sy:.3f})">')
    def setClipPath(self, path):
        _CLIPS[0] += 1
        n = _CLIPS[0]
        self.out.append(f'<clipPath id="c{n}"><path d="{path.svg()}"/></clipPath>')
        self._open(f'<g clip-path="url(#c{n})">')
    # shapes
    def _paint(self):
        a = ""
        if self.brush is not None:
            a += f' fill="{self.brush.css()}" fill-opacity="{self.brush.op()}"'
        else:
            a += ' fill="none"'
        if self.pen is not None and self.pen.c is not None:
            a += (f' stroke="{self.pen.c.css()}" stroke-opacity="{self.pen.c.op()}" stroke-width="{self.pen.w}"'
                  ' stroke-linecap="round" stroke-linejoin="round"')
        return a
    def drawEllipse(self, c, rx=None, ry=None):
        if isinstance(c, RectF):
            self.out.append(f'<ellipse cx="{c.x() + c.width() / 2:.2f}" cy="{c.y() + c.height() / 2:.2f}" '
                            f'rx="{c.width() / 2:.2f}" ry="{c.height() / 2:.2f}"{self._paint()}/>')
        else:
            self.out.append(f'<ellipse cx="{c.x():.2f}" cy="{c.y():.2f}" rx="{rx:.2f}" ry="{ry:.2f}"{self._paint()}/>')
    def drawRoundedRect(self, r, rx, ry):
        self.out.append(f'<rect x="{r.x():.2f}" y="{r.y():.2f}" width="{r.width():.2f}" height="{r.height():.2f}" '
                        f'rx="{rx:.2f}" ry="{ry:.2f}"{self._paint()}/>')
    def drawLine(self, a, b):
        self.out.append(f'<line x1="{a.x():.2f}" y1="{a.y():.2f}" x2="{b.x():.2f}" y2="{b.y():.2f}"{self._paint()}/>')
    def drawPath(self, path):
        self.out.append(f'<path d="{path.svg()}"{self._paint()}/>')
    def drawText(self, *a):
        self.font_px = getattr(self, "font_px", 8)
        if len(a) == 3 and isinstance(a[0], RectF) and self.pen is not None and self.pen.c is not None:
            r, txt = a[0], a[2]
            self.out.append(f'<text x="{r.x() + r.width() / 2:.2f}" y="{r.y() + r.height() / 2:.2f}" fill="{self.pen.c.css()}" '
                            f'font-size="{self.font_px}" font-weight="800" text-anchor="middle" dominant-baseline="central" '
                            f'font-family="Helvetica, Arial, sans-serif">{txt}</text>')


class Font:
    def __init__(self, *a): self.px = 8
    def setBold(self, *a): pass
    def setWeight(self, *a): pass
    def setPixelSize(self, n): self.px = n
    def setPointSize(self, n): self.px = n
    def setPointSizeF(self, n): self.px = n


QtGui.QFont = Font
QtGui.QColor, QtGui.QPen, QtGui.QPainterPath, QtGui.QPainter = Color, Pen, Path, Painter
QtCore.QPointF = QtCore.QPoint = PointF
QtCore.QRectF = RectF
QtCore.Qt = Name("Qt")

spec = importlib.util.spec_from_file_location("shika", os.path.join(HERE, "..", "shika", "shika.py"))
shika = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shika)


class Dummy(shika.PupArt):
    def __init__(self, cid, **kw):
        self.char_id, self.s = cid, 1.0
        self.__dict__.update(kw)
    def anchor(self): return 0, 0


POSES = [("stand", dict(state="idle")),
         ("sit, happy", dict(state="sit", happy_until=time.time() + 1e6)),
         ("loves you", dict(state="sit", hovered=True, hover_pos=PointF(40, -20))),
         ("sleep", dict(state="sleep")),
         ("bow", dict(state="bow")),
         ("sulk", dict(state="sulk")),
         ("cry", dict(state="sad")),
         ("bark", dict(state="alert"))]


def sheet(ids, path):
    cw, ch, left = 150, 120, 96
    W, H = left + cw * len(POSES), 30 + ch * len(ids)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           f'<rect width="{W}" height="{H}" fill="#1b1b1e"/>']
    for j, (label, _) in enumerate(POSES):
        out.append(f'<text x="{left + j * cw + cw / 2}" y="18" fill="#bbb" font-size="12" text-anchor="middle" '
                   f'font-family="sans-serif">{label}</text>')
    for i, cid in enumerate(ids):
        out.append(f'<text x="10" y="{30 + i * ch + 66}" fill="#eee" font-size="13" font-family="sans-serif">'
                   f'{shika.CHAR_BY_ID[cid]["name"]} · {shika.CHAR_BY_ID[cid]["species"]}</text>')
        for j, (label, kw) in enumerate(POSES):
            d = Dummy(cid, **kw)
            d.t = 10 + j * 7
            d.wag = 1.0
            p = Painter()
            d.draw_pup(p)
            while p.levels[0]:
                p.levels[0].pop(); p.out.append("</g>")
            x, y = left + j * cw + cw / 2 - 6, 30 + i * ch + 100
            out.append(f'<g transform="translate({x} {y}) scale(1.25)">' + "".join(p.out) + "</g>")
    out.append("</svg>")
    open(path, "w", encoding="utf-8").write("\n".join(out))


if __name__ == "__main__":
    args = sys.argv[1:]
    dest = args[0] if args else os.path.join(HERE, "characters.svg")
    ids = args[1:] or [c["id"] for c in shika.CHARACTERS]
    sheet(ids, dest)
    print("wrote", dest, "with", len(ids), "characters")
