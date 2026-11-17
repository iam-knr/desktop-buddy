#!/usr/bin/env bash
# Shika for macOS. Safe to run again: it updates in place and never touches your notes or reminders.
#   ./install-mac.sh                  install or update
#   ./install-mac.sh --with-ollama    install Shika AI (local language model) without asking
#   ./install-mac.sh --no-ai          skip Shika AI. Without a prompt in a terminal it asks you.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Library/Application Support/ShikaApp"
VENV="$APP_DIR/venv"
BUNDLE="$HOME/Applications/Shika.app"
PLIST="$HOME/Library/LaunchAgents/in.adsmentor.shika.plist"

echo "==> 1/5  Python"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
    if command -v brew >/dev/null; then
        echo "    installing Python with Homebrew"
        brew install python
        PY=python3
    else
        echo "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ (or install Homebrew from https://brew.sh), then run this again."
        exit 1
    fi
fi
echo "    using $($PY --version)"

echo "==> 2/5  Shika's private Python environment (one-time download, a few hundred MB)"
mkdir -p "$APP_DIR"
[ -x "$VENV/bin/python3" ] || "$PY" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip || true
"$VENV/bin/pip" install --quiet --upgrade -r "$DIR/requirements-desktop.txt" \
    || { echo "PROBLEM: the packages did not install. Check your internet and run this again."; exit 1; }

echo "==> 3/5  Offline speech model (one-time, about 500 MB)"
cp "$DIR/shika/shika.py" "$APP_DIR/shika.py"
cp "$DIR/shika/bark.wav" "$APP_DIR/bark.wav"
cp "$DIR/shika/shika-icon.svg" "$APP_DIR/shika-icon.svg"
MODEL=$(grep -o '^WHISPER_MODEL = "[^"]*"' "$DIR/shika/shika.py" | cut -d'"' -f2)
"$VENV/bin/python3" -c "from faster_whisper import WhisperModel; WhisperModel('$MODEL', device='cpu', compute_type='int8')" \
    || echo "    WARNING: could not download $MODEL now. Shika will try again the first time you talk to him."

echo "==> 4/5  Shika.app (no Dock icon) and start at login"
pkill -f "ShikaApp/shika.py" 2>/dev/null || true
sleep 1
mkdir -p "$BUNDLE/Contents/MacOS"
cat > "$BUNDLE/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Shika</string>
  <key>CFBundleDisplayName</key><string>Shika</string>
  <key>CFBundleIdentifier</key><string>in.adsmentor.shika</string>
  <key>CFBundleExecutable</key><string>Shika</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>Shika listens while you hold the talk key.</string>
  <key>NSAppleEventsUsageDescription</key><string>Shika closes and switches apps when you ask.</string>
</dict></plist>
PL
cat > "$BUNDLE/Contents/MacOS/Shika" <<SH
#!/bin/bash
exec "$VENV/bin/python3" "$APP_DIR/shika.py" "\$@"
SH
chmod +x "$BUNDLE/Contents/MacOS/Shika"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>in.adsmentor.shika</string>
  <key>ProgramArguments</key><array>
    <string>$BUNDLE/Contents/MacOS/Shika</string><string>--autostart</string>
  </array>
  <key>RunAtLoad</key><true/>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/in.adsmentor.shika" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || true

WANT_AI=0
if [[ " $* " == *" --with-ollama "* ]]; then
    WANT_AI=1
elif [[ " $* " == *" --no-ai "* ]]; then
    WANT_AI=0
elif [ -t 0 ]; then
    read -r -p "Install Shika AI, the local language model for text cleanup (about 1 GB)? [Y/n] " ANS
    case "${ANS:-Y}" in [Yy]*) WANT_AI=1 ;; esac
fi

if [ "$WANT_AI" = 1 ]; then
    echo "==> Optional: local AI model"
    command -v ollama >/dev/null || { command -v brew >/dev/null && brew install ollama || echo "    Install Ollama from https://ollama.com"; }
    MODEL=$(grep -o '^OLLAMA_MODEL = "[^"]*"' "$DIR/shika/shika.py" | cut -d'"' -f2)
    (command -v ollama >/dev/null && (ollama serve >/dev/null 2>&1 & sleep 3; ollama pull "$MODEL")) || true
fi

echo "==> 5/5  Starting Shika"
open "$BUNDLE" --args --autostart || true
sleep 3
echo
if pgrep -f "ShikaApp/shika.py" >/dev/null; then echo "Done: Shika is running."; else
    echo "PROBLEM: Shika did not start. Look at: tail -30 \"$HOME/Library/Application Support/Shika/error.log\""; fi
cat <<'TXT'

ONE-TIME PERMISSIONS (macOS asks, or you add them by hand):
  System Settings > Privacy & Security
    Microphone          allow Shika
    Input Monitoring    add Shika.app (in ~/Applications)   <- needed to see the Right Ctrl / Right Option hold
    Accessibility       add Shika.app                       <- needed to paste text and press shortcuts
  Then quit and reopen Shika (right-click the pup > Turn Shika off, then open Shika from Launchpad or Spotlight).
Hold Right Ctrl to dictate, Right Option to give a command.
TXT
