#!/usr/bin/env bash
# Try Ollama on your Intel graphics chip, and keep it ONLY if it is clearly faster and really in use.
#
#   bash ollama-gpu.sh bench     measure CPU vs graphics with the same prompt, keep the faster one
#   bash ollama-gpu.sh on        turn the graphics chip on
#   bash ollama-gpu.sh off       back to the CPU (the default)
#   bash ollama-gpu.sh status    what is set right now
#
# Ollama skips integrated graphics by default because on many laptops it isn't faster. This setting is
# experimental: if anything misbehaves, "off" puts everything back. It only adds one small file
# (/etc/systemd/system/ollama.service.d/shika-igpu.conf); nothing else on the system is touched.
set -u
API="${OLLAMA_API:-http://127.0.0.1:11434}"
CONF_DIR="${OLLAMA_GPU_CONF_DIR:-/etc/systemd/system/ollama.service.d}"
CONF="$CONF_DIR/shika-igpu.conf"
SUDO="${SUDO-sudo}"
MODEL="${OLLAMA_MODEL:-$(grep -oP '^OLLAMA_MODEL = "\K[^"]+' "$HOME/.local/share/shika/shika.py" 2>/dev/null || echo qwen2.5:1.5b)}"
PROMPT="Input: i has went to the market yesterday and buyed apples and we r launching something cool soon its gonna help u get stuff done\nOutput:"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
FASTER_BY=0.85          # the graphics chip must take less than 85% of the CPU's time to be worth keeping

enabled() { [ -f "$CONF" ]; }

wait_up() {
    for _ in $(seq 1 40); do
        curl -sf "$API/api/tags" >/dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

set_state() {            # on | off
    if [ "$1" = on ]; then
        $SUDO mkdir -p "$CONF_DIR" || return 1
        printf '[Service]\nEnvironment="OLLAMA_IGPU_ENABLE=1"\n' | $SUDO tee "$CONF" >/dev/null || return 1
    else
        $SUDO rm -f "$CONF" || return 1
    fi
    $SUDO systemctl daemon-reload || return 1
    $SUDO systemctl restart ollama || return 1
    wait_up
}

generate() {             # -> seconds taken (stdout); the answer is left in $TMP
    local body
    body=$(printf '{"model":"%s","prompt":"%s","stream":false,"keep_alive":"10m","options":{"temperature":0,"num_predict":60}}' "$MODEL" "$PROMPT")
    curl -s -m 180 -o "$TMP" -w '%{time_total}' "$API/api/generate" -d "$body" 2>/dev/null | tr ',' '.'
}

measure() {              # warm-up call, then 3 timed calls -> "average-seconds sensible(yes|no)" on stdout
    local t sum=0 ok=yes i
    generate >/dev/null
    for i in 1 2 3; do
        t=$(generate)
        grep -qi 'market' "$TMP" || ok=no        # the answer must be a real, sensible reply
        sum=$(awk -v a="$sum" -v b="${t:-0}" 'BEGIN{print a+b}')
    done
    awk -v s="$sum" -v ok="$ok" 'BEGIN{printf "%.2f %s", s/3, ok}'
}

where() { ollama ps 2>/dev/null | awk 'NR==2'; }
on_gpu() { where | grep -qi 'GPU'; }

case "${1:-bench}" in
    on)     set_state on  && echo "Graphics chip ON. Check it with: ollama ps   (look for GPU in the PROCESSOR column)" ;;
    off)    set_state off && echo "Graphics chip OFF (CPU only, the default)." ;;
    status) if enabled; then echo "Graphics chip: ON ($CONF)"; else echo "Graphics chip: OFF (default)"; fi ;;
    bench)
        wait_up || { echo "Ollama isn't answering. Start it with: sudo systemctl start ollama"; exit 1; }
        echo "Model: $MODEL   (this takes about a minute; it restarts Ollama once)"
        first=$(enabled && echo gpu || echo cpu)
        echo "Measuring with the $first ..."
        read -r a a_ok <<< "$(measure)"; a_gpu=no; on_gpu && a_gpu=yes
        second=$([ "$first" = gpu ] && echo cpu || echo gpu)
        set_state "$([ "$second" = gpu ] && echo on || echo off)" || { echo "Couldn't restart Ollama. Run: bash $0 off"; exit 1; }
        echo "Measuring with the $second ..."
        read -r b b_ok <<< "$(measure)"; b_gpu=no; on_gpu && b_gpu=yes
        if [ "$first" = gpu ]; then gpu=$a; gpu_ok=$a_ok; gpu_used=$a_gpu; cpu=$b; else gpu=$b; gpu_ok=$b_ok; gpu_used=$b_gpu; cpu=$a; fi
        echo
        echo "  CPU only        : $cpu s per cleanup"
        echo "  Graphics chip   : $gpu s per cleanup   (answer sensible: $gpu_ok, really using the GPU: $gpu_used)"
        if [ "$gpu_ok" = yes ] && [ "$gpu_used" = yes ] && awk -v g="$gpu" -v c="$cpu" -v f="$FASTER_BY" 'BEGIN{exit !(g < f*c)}'; then
            set_state on  && echo "=> Graphics chip is clearly faster: KEPT ON."
        else
            set_state off && echo "=> Not clearly faster (or not really in use, or its answers looked wrong): back to CPU only."
        fi
        ;;
    *) sed -n '2,13p' "$0"; exit 2 ;;
esac
