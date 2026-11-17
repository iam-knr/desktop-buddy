#!/usr/bin/env bash
# Summit desk + Shika v3 (voice). Safe to re-run: it updates in place and never
# touches your tasks, notes, reminders or scratchpad.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
SHIKA="$HOME/.local/share/shika"
SUMMIT="$HOME/.local/share/summit"
VENV="$SHIKA/venv"

echo "==> 1/6  System packages (asks for your password once)"
sudo apt install -y python3-pyqt6 python3-venv python3-evdev python3-numpy \
    sound-theme-freedesktop libglib2.0-bin libnotify-bin pulseaudio-utils wl-clipboard \
    qml6-module-qtquick-shapes libqt6svg6 playerctl

sudo apt install -y fonts-bebas-neue >/dev/null 2>&1 || echo "    (Bebas Neue font not in your repos; Summit Clock will use another condensed font)"

echo "==> 2/6  Keyboard access for push-to-talk and typing"
# Read Right Ctrl / Right Alt holds, and send one Shift+Insert to paste dictated text.
echo 'KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' \
    | sudo tee /etc/udev/rules.d/80-shika-uinput.rules >/dev/null
echo uinput | sudo tee /etc/modules-load.d/shika-uinput.conf >/dev/null
sudo modprobe uinput || true
sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=uinput || true
RELOGIN=0
if ! id -nG "$USER" | grep -qw input; then
    sudo usermod -aG input "$USER"
    RELOGIN=1
fi

echo "==> 3/6  Offline speech engine (one-time download, about 500 MB)"
mkdir -p "$SHIKA" "$SUMMIT"
[ -x "$VENV/bin/python3" ] || python3 -m venv --system-site-packages "$VENV"
# downloads can fail on a bad connection: never let that stop the rest of the update
"$VENV/bin/pip" install --quiet --upgrade pip || true
"$VENV/bin/pip" install --quiet --upgrade faster-whisper \
    || echo "    WARNING: couldn't update the speech engine right now (internet?). The old one stays."
MODEL=$(grep -oP '^WHISPER_MODEL = "\K[^"]+' "$DIR/shika/shika.py")
echo "    fetching the $MODEL model..."
"$VENV/bin/python3" -c "from faster_whisper import WhisperModel; WhisperModel('$MODEL', device='cpu', compute_type='int8')" \
    || echo "    WARNING: couldn't download $MODEL right now. Shika uses the smaller model until you re-run install.sh."

echo "==> 4/6  Shika"
pkill -f "mochi.py" 2>/dev/null || true
pkill -f "shika.py" 2>/dev/null || true
sleep 1
rm -f ~/.config/autostart/mochi.desktop ~/.local/share/applications/mochi.desktop
mkdir -p ~/.local/share/applications ~/.config/autostart
cp "$DIR/shika/shika.py" "$SHIKA/shika.py"
cp "$DIR/shika/bark.wav" "$SHIKA/bark.wav"     # your own bark? drop it at ~/.config/shika/bark.wav
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICONS"
cp "$DIR/shika/shika-icon.svg" "$ICONS/shika.svg"
RUN="env QT_QPA_PLATFORM=xcb $VENV/bin/python3 $SHIKA/shika.py"
entry() {  # name, comment, args, icon
cat << DESK
[Desktop Entry]
Type=Application
Name=$1
Comment=$2
Exec=$RUN $3
Icon=$4
Categories=Utility;
Keywords=dog;pet;pup;reminder;voice;dictation;scratchpad;
DESK
}
entry "Shika" "Your dictations, notes and guide" "--dashboard" shika > ~/.local/share/applications/shika.desktop
entry "Shika Pup" "Wake your desktop pup" "" shika > ~/.local/share/applications/shika-pup.desktop
entry "Shika" "Your desktop pup" "--autostart" shika > ~/.config/autostart/shika.desktop
entry "Shika Scratchpad" "Voice scratchpad" "--scratchpad" document-edit > ~/.local/share/applications/shika-scratchpad.desktop
entry "Shika Dictate (toggle)" "Start/stop dictation" "--dictate" audio-input-microphone > ~/.local/share/applications/shika-dictate.desktop
entry "Shika Command (toggle)" "Start/stop a voice command" "--command" audio-input-microphone > ~/.local/share/applications/shika-command.desktop

echo "StartupWMClass=shika.py" >> ~/.local/share/applications/shika.desktop
touch "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true   # refresh the launcher

echo "==> 5/6  Summit widgets"
cp "$DIR/summitctl.py" "$SUMMIT/summitctl.py"
BUILD=$(mktemp -d)
UPDATED=0
# v1 had a separate Reminders widget; it's merged into Tasks & Reminders now
kpackagetool6 -t Plasma/Applet -r in.adsmentor.summit.reminders >/dev/null 2>&1 && UPDATED=1 || true
for w in tasks notes focus clock; do
    cp -r "$DIR/plasmoids/$w" "$BUILD/$w"
    cp "$DIR"/common/*.qml "$BUILD/$w/contents/ui/"
    if ! kpackagetool6 -t Plasma/Applet -i "$BUILD/$w" >/dev/null 2>&1; then
        kpackagetool6 -t Plasma/Applet -u "$BUILD/$w" >/dev/null
        UPDATED=1
    fi
    echo "    installed Summit $w"
done
rm -rf "$BUILD"
if [ "$UPDATED" = 1 ]; then
    echo "    restarting the desktop so the updated widgets load (your data is safe)"
    systemctl --user restart plasma-plasmashell.service || true
fi

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
    echo "==> Smart cleanup: local AI model (about 1 GB, one time)"
    command -v curl >/dev/null || sudo apt install -y curl
    command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
    MODEL=$(grep -oP '^OLLAMA_MODEL = "\K[^"]+' "$DIR/shika/shika.py")
    sudo systemctl start ollama 2>/dev/null || true
    for i in $(seq 1 30); do                     # a fresh install needs a few seconds to start up
        curl -s http://127.0.0.1:11434 >/dev/null && break
        sleep 1
    done
    ollama pull "$MODEL" || echo "    Couldn't download the model yet. Run: ollama pull $MODEL"
fi

echo "==> 6/6  Starting Shika"
nohup $RUN >/dev/null 2>&1 &
sleep 3
WANT=$(grep -oP '^VERSION = "\K[^"]+' "$DIR/shika/shika.py")
HAVE=$(grep -oP '^VERSION = "\K[^"]+' "$SHIKA/shika.py")
echo
if [ "$WANT" != "$HAVE" ]; then
    echo "PROBLEM: the zip has Shika $WANT but $HAVE is installed. Send Claude a screenshot of this window."
elif ! pgrep -f "share/shika/shika.py" >/dev/null; then
    echo "PROBLEM: Shika $HAVE is installed but didn't start. Send Claude: tail -30 ~/.config/shika/error.log"
else
    echo "Done: Shika $HAVE is installed and running."
fi
echo "Right-click the desktop > Add or Manage Widgets > search \"Summit\"."
if [ "$RELOGIN" = 1 ]; then
    echo
    echo "IMPORTANT: log out and back in once. Push-to-talk and typing start working after that."
fi
