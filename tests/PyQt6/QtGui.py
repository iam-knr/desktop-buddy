from ._base import _Any
class QPainter(_Any): pass
class QColor(_Any):
    def __init__(self, *a): self.a = a
class QPen(_Any): pass
class QPainterPath(_Any): pass
class QFont(_Any): pass
class QRegion(_Any): pass
class QIcon(_Any): pass
class QFontMetrics(_Any): pass
class QImage(_Any): pass
class QLinearGradient(_Any): pass
class _Clip:
    text_ = ""
    def setText(self, t, *m): _Clip.text_ = t
    def text(self, *m): return _Clip.text_
    class Mode: Selection = 1; Clipboard = 0
class QGuiApplication(_Any):
    @staticmethod
    def clipboard(): return _Clip()
    @staticmethod
    def primaryScreen(): return _Any()
    @staticmethod
    def screenAt(p): return _Any()
    @staticmethod
    def screens(): return []
class QCursor(_Any):
    @staticmethod
    def pos():
        from .QtCore import QPoint
        return QPoint(500, 500)
