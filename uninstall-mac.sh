#!/usr/bin/env bash
# Removes Shika from a Mac. Your notes, dictations, reminders and settings are KEPT unless you add --purge-data.
PURGE=0; [[ " $* " == *" --purge-data "* ]] && PURGE=1
launchctl bootout "gui/$(id -u)/in.adsmentor.shika" 2>/dev/null || true
pkill -f "ShikaApp/shika.py" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/in.adsmentor.shika.plist"
rm -rf "$HOME/Applications/Shika.app" "$HOME/Library/Application Support/ShikaApp"
echo "Removed the program, Shika.app and the start-at-login entry."
if [ "$PURGE" = 1 ]; then
    read -r -p "Type DELETE to also delete your notes, dictations, reminders and settings: " A
    if [ "$A" = "DELETE" ]; then rm -rf "$HOME/Library/Application Support/Shika" "$HOME/Library/Application Support/Summit"; echo "Data deleted."; else echo "Data kept."; fi
else
    echo "Kept your data in ~/Library/Application Support/Shika and .../Summit (add --purge-data to delete it)."
fi
echo "In System Settings > Privacy & Security you can also remove Shika from Microphone, Input Monitoring and Accessibility."
