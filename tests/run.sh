#!/usr/bin/env bash
# Runs Shika's real code headless (fake Qt, fake keyboard, fake Ollama) and checks every wiring.
cd "$(dirname "$0")"
fail=0
for t in t_close.py t_edit.py t_all.py t_more.py t_keys.py t_tap.py t_chars.py; do
    echo "== $t"; timeout 300 python3 "$t" | tail -25 || fail=1
done
for os_name in mac win; do
    echo "== t_cross.py $os_name"; timeout 300 python3 t_cross.py $os_name | tail -25 || fail=1
done
for os_name in linux mac win; do
    echo "== t_widgets.py $os_name"; timeout 300 python3 t_widgets.py $os_name | tail -25 || fail=1
done
