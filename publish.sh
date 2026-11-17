#!/usr/bin/env bash
# One-time publish: creates the public GitHub repo and pushes this folder. Needs git and the GitHub CLI (gh).
set -e
cd "$(dirname "$0")"
command -v gh >/dev/null || { echo "Install the GitHub CLI first: https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login
[ -d .git ] || git init -b main
git add -A
git commit -m "Shika AI: voice-driven desktop companion for Linux, macOS and Windows" || true
gh repo create desktop-buddy --public --source=. --remote=origin --push \
  --description "Shika AI: voice-driven desktop companion and offline voice assistant for Linux, macOS and Windows. Push-to-talk dictation (faster-whisper), voice commands, reminders, 15 pet characters. Python + PyQt6."
gh repo edit --add-topic desktop-companion --add-topic voice-assistant --add-topic offline-voice-assistant \
  --add-topic speech-to-text --add-topic dictation --add-topic push-to-talk --add-topic faster-whisper --add-topic whisper \
  --add-topic pyqt6 --add-topic python --add-topic ollama --add-topic local-ai --add-topic kde-plasma --add-topic linux \
  --add-topic macos --add-topic windows --add-topic cross-platform --add-topic productivity --add-topic shika-ai --add-topic reminders --add-topic privacy
echo "Done: https://github.com/iam-knr/desktop-buddy"
