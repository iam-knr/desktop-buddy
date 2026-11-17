# Summit desk + Shika v3.18

## Install
    cd summit && ./install.sh
Then log out and back in once (needed only the first time, for push-to-talk).

## Add the widgets
Right-click desktop > Add or Manage Widgets > search "Summit":
Summit Tasks & Reminders, Summit Sticky Note (add as many as you like), Summit Focus Timer.
Suggested spots: Tasks & Reminders in the empty sky top-right, Focus timer top-centre,
notes on the dark hill bottom-left. Shika keeps his corner.

## Tasks & reminders
Type, optionally pick a time chip (or type "6:45 pm"), then "+ Task" or "Remind me".
Anything with a time makes Shika run to the middle of the screen and bark. Tap him = done,
double-tap = snooze 10 min. Tasks stay in the list (ticked) after; reminders disappear.
Swap the bark: put any .wav at ~/.config/shika/bark.wav.

## The Shika app
App Launcher > "Shika" (or "Open Shika" in the scratchpad, or say "open Shika").
Every dictation and every scratchpad note is kept there as its own titled entry.
Search, rename, edit, copy, delete (click Delete twice). "Shika Pup" in the launcher wakes the dog.

## Versions
Closing the scratchpad, pressing ＋ New in it, erasing a sticky note, or editing a sticky
note again after a 10-minute break keeps the old text as v1, v2, v3… in the Shika app.
Open an entry > History menu > pick a version > Restore. "Save version" makes one by hand.
Sticky notes: ↗ opens that note in the Shika app. A full guide is inside the app (📖 Guide).

## Floating focus timer
Focus widget > "Pop out": a mini timer floats above every app. Drag it anywhere; it
remembers the spot. ✕ puts it away.

## Voice (all offline)
| Do this | What happens |
|---|---|
| Hold Right Ctrl, talk, let go | Text is typed where your cursor is (or into the scratchpad if it's open and active) |
| Hold Right Alt, talk, let go | Shika runs a command |
Say "new line" / "new paragraph" while dictating for line breaks.

Commands: "open firefox", "open file manager", "remind me at 5 to call Rahul",
"remind me in 20 minutes to drink water", "remind me tomorrow at 9 to send the invoice",
"add task upload session recording", "add task call Rahul at 5" (task that barks),
"note GA4 case study idea" (saved to the Shika app), "open scratchpad", "open Shika",
"search DV360 line item setup", "lofi beats on YouTube", "volume up", "mute",
"lock screen", "what time is it", "sleep", "play ball", "climb", "treat".

## Optional shortcuts
System Settings > Keyboard > Shortcuts > Add New > Application > pick a Shika entry > OK >
click it, press your keys > Apply. Suggested: Scratchpad Meta+Alt+N, Shika Meta+Alt+S,
Dictate (toggle) Meta+Alt+D, Command (toggle) Meta+Alt+C, Shika Pup Meta+Alt+P.
(Plain Meta+D and Meta+P are already used by Plasma.) Full steps are in the app's Guide.

## Tuning
The settings sit at the top of the program file. Edit the copy inside your unzipped folder, not the installed one:

    summit/shika/shika.py        <- edit this one
    ./install.sh                 <- then run this to apply it

Installing copies that file over ~/.local/share/shika/shika.py, so an edit made only in the installed copy is lost
the next time you run install.sh.
Common settings: DICTATE_KEY / COMMAND_KEY, HOLD_MS, WHISPER_MODEL ("small.en" = more accurate, slower), SIZE, FPS.

## Characters and names (new in 3.18)
Shika app > 🐾 Characters. Fifteen characters: three pups (Shika, Frost the husky, Domino the dalmatian) and twelve
other pet companions (cat, fox, panda, bunny, bear, tiger, raccoon, pig, frog, penguin, lion, koala). Click a card to switch.
Each character keeps its own name: type one and press Save name, or Reset to go back to the default.
By voice (hold Right Alt): "be a panda", "switch to Frost", "call yourself Momo", "surprise me", "open characters".
The name also works as a wake word, so "Momo, open firefox" works.
The reminder panel (right-click the pup) has a 🐾 Characters and names button too.

## Taskbar awareness (new in 3.18)
Shika asks Plasma where its panels are (side, thickness, auto-hide) every few seconds and stands on the real floor:
on top of a bottom taskbar, clear of a side or top one, and on the screen edge when the taskbar hides itself.
If you move or resize the taskbar, he steps onto the new floor by himself.
Turn it off with the "Stand on my taskbar" box on the Characters page (setting "taskbar_aware" in ~/.config/shika/settings.json).
Limits: the panel is treated as full width, even when it is a short floating dock. If Plasma can't be asked, he falls
back to what Qt reports plus the old fixed 58 px gap on the right (TASKBAR_RIGHT).
Sidebar > 🩺 Check my setup shows what he found.

## Uninstall
    ./uninstall.sh                 # removes the pup, autostart, launcher entries, widgets, Python environment, keyboard rules
    ./uninstall.sh --purge-data    # the same, then (after you type DELETE) your notes, dictations, reminders and settings

## Damaged data files
If a data file can't be read, Shika renames it to <name>.corrupt-<date> instead of overwriting it, and tells you.
library.json, reminders.json and settings.json also get one backup copy (<name>.bak) at most once an hour,
made only while the file is still good. Restore by copying the .bak or .corrupt file back over the original while Shika is closed.

## Where your data lives
~/.local/share/summit/  library.json (dictations + scratchpad notes), notes.json (sticky notes), focus.json
~/.config/shika/        reminders.json (tasks and reminders, shared by Shika and the widget)
All writes are atomic + fsync'd. Back up these two folders and you have everything.

## If something misbehaves
Widget errors:   journalctl --user -f | grep -i summit
Shika errors:    ~/.config/shika/error.log


## Edit selected text by voice (fix grammar / make it formal / make it shorter …)
Select text in any app, hold Right Alt, say it. Shika copies the selection (Ctrl+Insert first, which is safe in
terminals), edits it, checks the result, and pastes it over the selection. Ctrl+Z undoes it.
If it doesn't work, the bubble says which step failed. Sidebar > 🩺 Check my setup > "Test keys + clipboard"
shows which copy key works on your desktop. Every step is logged in ~/.config/shika/debug.log.

## Faster Shika AI on the Intel graphics chip (optional, experimental)
    bash tools/ollama-gpu.sh bench      # measures CPU vs graphics with the same prompt, keeps the faster one
    bash tools/ollama-gpu.sh off        # back to the CPU (the default); also: on, status
It keeps the graphics chip only if it answers correctly, is really in use, and is at least 15% faster.

## Tests
    bash tests/run.sh      # runs Shika's real code headless: closing, editing, dictation, widgets, parsers, keys, taps, characters
    python3 tests/preview_chars.py out.svg     # draws all 15 characters in 8 poses, no Qt needed; open out.svg in a browser

## Closing things by voice
"close tab" also means "close the current tab", "close the tab you opened", "close the youtube tab", "tab band karo".
"close youtube" / "close gmail" close that TAB (never the whole browser). "close chrome" / "chrome band karo" close the app:
Shika says "band kar raha hoon…", then checks a moment later and tells you if it really closed.
