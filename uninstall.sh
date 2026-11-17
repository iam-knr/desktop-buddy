#!/usr/bin/env bash
# Removes everything install.sh put on this computer:
#   the running pup, the autostart entry, the launcher entries, the Python environment,
#   the Summit widgets (tasks, notes, focus, clock) and the keyboard rules.
# Your notes, dictations, reminders and settings are KEPT. To delete them as well, run:
#   ./uninstall.sh --purge-data
# Safe to run twice.

PURGE=0
[[ " $* " == *" --purge-data "* ]] && PURGE=1

echo "==> Stopping Shika"
pkill -f "share/shika/shika.py" 2>/dev/null || true
pkill -f "shika.py" 2>/dev/null || true
sleep 1

echo "==> Removing the widgets"
REMOVED=0
for w in tasks reminders notes focus clock; do          # "reminders" is the old v1 widget
    kpackagetool6 -t Plasma/Applet -r "in.adsmentor.summit.$w" >/dev/null 2>&1 && REMOVED=1
done

echo "==> Removing launcher and autostart entries"
rm -f ~/.config/autostart/shika.desktop ~/.config/autostart/mochi.desktop
rm -f ~/.local/share/applications/shika.desktop ~/.local/share/applications/shika-pup.desktop \
      ~/.local/share/applications/shika-scratchpad.desktop ~/.local/share/applications/shika-dictate.desktop \
      ~/.local/share/applications/shika-command.desktop ~/.local/share/applications/mochi.desktop
rm -f ~/.local/share/icons/hicolor/scalable/apps/shika.svg

echo "==> Removing the program files and the Python environment"
rm -rf ~/.local/share/shika
rm -f ~/.local/share/summit/summitctl.py
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true   # refresh the launcher

echo "==> Removing the keyboard rules (asks for your password)"
sudo rm -f /etc/udev/rules.d/80-shika-uinput.rules /etc/modules-load.d/shika-uinput.conf
sudo udevadm control --reload-rules 2>/dev/null || true

if [ "$REMOVED" = 1 ]; then
    echo "==> Restarting the desktop so the removed widgets disappear"
    systemctl --user restart plasma-plasmashell.service 2>/dev/null || true
fi

if [ "$PURGE" = 1 ]; then
    echo
    echo "You asked to delete your data too: dictations, notes, reminders, settings and their backups."
    read -r -p "Type DELETE to confirm: " ANSWER
    if [ "$ANSWER" = "DELETE" ]; then
        rm -rf ~/.local/share/summit ~/.config/shika
        echo "Your data is deleted."
    else
        echo "Nothing typed, so your data is kept."
    fi
else
    echo
    echo "Kept your data (delete it yourself, or re-run with --purge-data):"
    echo "    ~/.local/share/summit   dictations, notes, sticky notes"
    echo "    ~/.config/shika         reminders and settings"
fi
echo "To also leave the 'input' group: sudo gpasswd -d $USER input"
echo "Done."
