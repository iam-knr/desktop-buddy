#!/usr/bin/env python3
"""summitctl: tiny storage helper for the Summit Plasma widgets.

Every write goes to a temp file, is fsync'd, then atomically renamed over the
real file, so a crash or power cut leaves either the old or the new version,
never a half-written one. Text arrives URL-encoded so nothing can break the shell.

  get items | notes | focus
  item-add <json>           item-update <id> <json>    item-del <id>    clear-done
  note-set <id> <json>      note-del <id> [<json last text>]
  open-shika [<entry id>]
  set focus <json>
  notify <title> <body>     sound     launch-shika     open-shika

Tasks and reminders share one list in Shika's file (~/.config/shika/reminders.json):
every item has kind "task" or "reminder"; anything with a due time makes Shika bark.
"""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse

DATA = os.path.expanduser("~/.local/share/summit")
SHIKA_REMINDERS = os.path.expanduser("~/.config/shika/reminders.json")
OLD_TASKS = os.path.join(DATA, "tasks.json")
LIBRARY = os.path.join(DATA, "library.json")
SESSION_GAP = 600          # editing a sticky note again after 10 min keeps the old text as a version
MAX_VERSIONS = 30
FILES = {
    "notes": os.path.join(DATA, "notes.json"),
    "focus": os.path.join(DATA, "focus.json"),
}
DEFAULTS = {"notes": {}, "focus": {}}


def dec(s):
    return json.loads(urllib.parse.unquote(s))


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except ValueError:                       # damaged file: set it aside so the next save can't overwrite it
        try:
            if os.path.getsize(path) > 0:
                os.replace(path, f"{path}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        except OSError:
            pass
        return default
    except Exception:
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(os.path.dirname(path), os.O_RDONLY)
        os.fsync(fd)
        os.close(fd)
    except OSError:
        pass


class Locked:
    """Exclusive lock shared with Shika, so two writers never clobber each other."""
    def __init__(self, path):
        self.lock_path = path + ".lock"

    def __enter__(self):
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        self.f = open(self.lock_path, "w")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *a):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def shika_running():
    try:
        return subprocess.run(["pgrep", "-f", "share/shika/shika.py"], capture_output=True).returncode == 0
    except Exception:
        return False


def sound():
    files = ["/usr/share/sounds/ocean/stereo/completion-success.oga",
             "/usr/share/sounds/freedesktop/stereo/complete.oga",
             "/usr/share/sounds/freedesktop/stereo/bell.oga"]
    snd = next((f for f in files if os.path.exists(f)), None)
    player = next((p for p in ("pw-play", "paplay") if shutil.which(p)), None)
    if snd and player:
        subprocess.Popen([player, snd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def migrate_tasks():
    """v1 kept tasks in their own file; fold them into the shared list once."""
    if not os.path.exists(OLD_TASKS):
        return
    with Locked(SHIKA_REMINDERS):
        items = load(SHIKA_REMINDERS, [])
        for t in load(OLD_TASKS, {}).get("items", []):
            items.append({"id": "t" + str(t.get("id", time.time())), "kind": "task",
                          "text": t.get("text", ""), "due": None, "done": bool(t.get("done")),
                          "urgent": bool(t.get("urgent"))})
        save(SHIKA_REMINDERS, items)
        os.replace(OLD_TASKS, OLD_TASKS + ".migrated")


def push_version(e, reason):
    vs = e.setdefault("versions", [])
    if not e.get("text", "").strip():
        return
    if vs and vs[-1]["text"] == e["text"] and vs[-1].get("title", "") == e.get("title", ""):
        return
    vs.append({"n": (vs[-1]["n"] + 1) if vs else 1, "title": e.get("title", ""), "text": e["text"],
               "saved": time.time(), "reason": reason})
    del vs[:-MAX_VERSIONS]


def mirror_sticky(nid, text, erased=False):
    """Every sticky note is also an entry in the Shika app, with versions."""
    eid = "sticky:" + nid
    with Locked(LIBRARY):
        entries = load(LIBRARY, [])
        e = next((x for x in entries if x.get("id") == eid), None)
        now = time.time()
        if e is None:
            if not text.strip():
                return
            e = {"id": eid, "kind": "sticky", "title": "", "text": text, "created": now,
                 "updated": now, "versions": []}
            entries.append(e)
        elif erased:
            e["text"] = text or e.get("text", "")
            push_version(e, "erased from desktop")
            e["removed"] = True
            e["updated"] = now
        elif text != e.get("text"):
            if e.get("removed") or now - e.get("updated", now) > SESSION_GAP:
                push_version(e, "earlier session")
            e["text"] = text
            e["updated"] = now
            e.pop("removed", None)
        else:
            return
        save(LIBRARY, entries)


def shika_python():
    base = os.path.expanduser("~/.local/share/shika")
    py = os.path.join(base, "venv/bin/python3")
    return (py if os.path.exists(py) else "python3"), os.path.join(base, "shika.py")


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    cmd, args = argv[0], argv[1:]
    out = None

    if cmd == "get":
        kind = args[0]
        if kind == "items":
            migrate_tasks()
            items = []
            for r in load(SHIKA_REMINDERS, []):
                r.setdefault("kind", "reminder")
                if r["kind"] == "task" or not r.get("done"):     # finished reminders disappear
                    items.append(r)
            out = {"items": items, "shika": shika_running(), "now": time.time()}
        else:
            out = load(FILES[kind], DEFAULTS[kind])

    elif cmd == "set" and args[0] == "focus":
        with Locked(FILES["focus"]):
            save(FILES["focus"], dec(args[1]))

    elif cmd == "item-add":
        r = dec(args[0])
        kind = "task" if r.get("kind") == "task" else "reminder"
        item = {"id": f"{time.time():.6f}", "kind": kind, "text": str(r["text"])[:300],
                "due": float(r["due"]) if r.get("due") else None, "done": False,
                "urgent": bool(r.get("urgent"))}
        if r.get("repeat") and item["due"]:
            item["repeat"] = int(r["repeat"])
        with Locked(SHIKA_REMINDERS):
            items = load(SHIKA_REMINDERS, [])
            items.append(item)
            save(SHIKA_REMINDERS, items)

    elif cmd == "item-update":
        rid, patch = urllib.parse.unquote(args[0]), dec(args[1])
        allowed = {k: patch[k] for k in ("done", "urgent", "text") if k in patch}
        with Locked(SHIKA_REMINDERS):
            items = load(SHIKA_REMINDERS, [])
            for r in items:
                if r.get("id") == rid:
                    r.update(allowed)
            save(SHIKA_REMINDERS, items)

    elif cmd in ("item-del", "rem-del"):
        rid = urllib.parse.unquote(args[0])
        with Locked(SHIKA_REMINDERS):
            save(SHIKA_REMINDERS, [r for r in load(SHIKA_REMINDERS, []) if r.get("id") != rid])

    elif cmd == "clear-done":
        with Locked(SHIKA_REMINDERS):
            save(SHIKA_REMINDERS, [r for r in load(SHIKA_REMINDERS, [])
                                   if not (r.get("kind") == "task" and r.get("done"))])

    elif cmd == "note-set":
        with Locked(FILES["notes"]):
            notes = load(FILES["notes"], {})
            note = dec(args[1])
            note["updated"] = time.time()
            notes[urllib.parse.unquote(args[0])] = note
            save(FILES["notes"], notes)
        mirror_sticky(urllib.parse.unquote(args[0]), str(note.get("text", "")))

    elif cmd == "note-del":
        with Locked(FILES["notes"]):
            notes = load(FILES["notes"], {})
            gone = notes.pop(urllib.parse.unquote(args[0]), None) or {}
            save(FILES["notes"], notes)
        last = dec(args[1]).get("text", "") if len(args) > 1 else gone.get("text", "")
        mirror_sticky(urllib.parse.unquote(args[0]), last or gone.get("text", ""), erased=True)

    elif cmd == "notify":
        title, body = urllib.parse.unquote(args[0]), urllib.parse.unquote(args[1])
        if shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "-a", "Summit", "-i", "chronometer", title, body])
        sound()

    elif cmd == "launch-shika" and shika_running():
        pass                                      # already up; don't wake him needlessly

    elif cmd in ("launch-shika", "open-shika"):
        py, script = shika_python()
        env = dict(os.environ, QT_QPA_PLATFORM="xcb")
        extra = []
        if cmd == "open-shika":
            extra = [f"--open={urllib.parse.unquote(args[0])}"] if args else ["--dashboard"]
        subprocess.Popen([py, script] + extra, env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    elif cmd == "sound":
        sound()

    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 1

    print(json.dumps(out if out is not None else {"ok": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
