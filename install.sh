#!/usr/bin/env bash
# =====================================================================
#  Klipper-Voice - installer
#
#  Usage:  cd ~/Klipper-Voice && ./install.sh [options]
#
#  -l LANG    language: en de es fr it pl pt_BR pt_PT ...
#             (without -l the installer asks; see languages/*.json)
#  -v VOICE   other piper voice for that language
#             list: https://huggingface.co/rhasspy/piper-voices
#  -c DIR     printer_data folder                (default: ~/printer_data)
#  -n         do not download a piper voice (espeak only)
#  -h         help
#
#  Safe to run again: it never deletes or overwrites your own
#  configuration files.
# =====================================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRINTER_DATA="${HOME}/printer_data"
LANG_CODE=""
VOICE=""
NO_VOICE=0
VENV="${HOME}/klipper-voice-env"
VOICES="${HOME}/klipper-voice-voices"
SERVICE="klipper-voice"

green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*" >&2; }
step()   { printf '\n\033[1m== %s\033[0m\n' "$*"; }

usage() { sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while getopts "l:v:c:nh" opt; do
  case "$opt" in
    l) LANG_CODE="$OPTARG" ;;
    v) VOICE="$OPTARG" ;;
    c) PRINTER_DATA="$OPTARG" ;;
    n) NO_VOICE=1 ;;
    h|*) usage ;;
  esac
done

render() { python3 "${REPO}/tools/render_config.py" "$@"; }

# ---------------------------------------------------------------------
# Language (it picks the voice synthesizer model and the phrases)
if [ -z "$LANG_CODE" ]; then
  mapfile -t LANGS < <(render list)
  if [ -t 0 ]; then
    echo "Which language should the printer speak?"
    i=1
    for l in "${LANGS[@]}"; do
      IFS=$'\t' read -r code name voice <<<"$l"
      # pad by characters, not bytes (printf %-22s misaligns "Español")
      pad=$((22 - ${#name})); [ "$pad" -gt 0 ] || pad=1
      printf '  %2d) %s%*s (%s, voice %s)\n' "$i" "$name" "$pad" "" "$code" "$voice"
      i=$((i + 1))
    done
    read -r -p "Number [1]: " choice
    choice="${choice:-1}"
    if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#LANGS[@]}" ]; then
      red "Invalid choice."; exit 1
    fi
    LANG_CODE="$(cut -f1 <<<"${LANGS[$((choice - 1))]}")"
  else
    LANG_CODE="en"
  fi
fi
if [ ! -f "${REPO}/languages/${LANG_CODE}.json" ]; then
  red "Unknown language '${LANG_CODE}'. Available: $(render list | cut -f1 | tr '\n' ' ')"
  exit 1
fi
: "${VOICE:=$(render get "$LANG_CODE" voice)}"
green "Language: ${LANG_CODE} - voice ${VOICE}"

CONFIG="${PRINTER_DATA}/config"

if [ "$(id -u)" -eq 0 ]; then
  red "Do not run as root. Run as the Klipper user (sudo is requested when needed)."
  exit 1
fi
if [ ! -d "$CONFIG" ]; then
  red "${CONFIG} not found. Point to your printer_data folder with -c."
  exit 1
fi

# ---------------------------------------------------------------------
step "1/7 System packages"
sudo apt-get update -q
sudo apt-get install -y -q alsa-utils espeak-ng sox libsox-fmt-all python3-venv python3-pip

# ---------------------------------------------------------------------
step "2/7 Sound (audio group and volume)"
if ! id -nG "$USER" | grep -qw audio; then
  sudo usermod -aG audio "$USER"
  yellow "Added ${USER} to the audio group (the service already uses it; your SSH session only after logging in again)."
fi
# Headless Debian often ships with the mixer muted.
for ctl in Master Speaker PCM Headphone; do
  amixer -q sset "$ctl" 100% unmute 2>/dev/null || true
done
sudo alsactl store 2>/dev/null || true
# Intel HDA cards power down after a few idle seconds and "pop" when they
# wake up for the next message: keep them powered.
if [ -e /sys/module/snd_hda_intel/parameters/power_save ]; then
  echo "options snd_hda_intel power_save=0 power_save_controller=N" | \
    sudo tee /etc/modprobe.d/klipper-voice.conf >/dev/null
  echo 0 | sudo tee /sys/module/snd_hda_intel/parameters/power_save >/dev/null
  echo N | sudo tee /sys/module/snd_hda_intel/parameters/power_save_controller >/dev/null 2>&1 || true
  green "Sound card power saving off (no pops between messages)."
fi
aplay -l 2>/dev/null | grep -E '^card' || yellow "Warning: aplay found no sound card."

# ---------------------------------------------------------------------
step "3/7 Python environment (piper + websockets) in ${VENV}"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
# piper needs onnxruntime, which has no build for 32-bit ARM (armv6/armv7):
# requirements.txt skips it there, and if it still fails we go on with
# espeak only instead of aborting the whole install.
if ! "$VENV/bin/pip" install -q -r "$REPO/requirements.txt"; then
  yellow "Could not install piper on this system ($(uname -m)); installing websockets only."
  "$VENV/bin/pip" install -q "websockets>=12"
fi
if ! "$VENV/bin/python3" -c "import piper" 2>/dev/null; then
  yellow "piper is not available on this system ($(uname -m)): the service will use espeak."
  NO_VOICE=1
fi

# ---------------------------------------------------------------------
step "4/7 Voice"
if [ "$NO_VOICE" -eq 1 ]; then
  yellow "No piper voice: the service will use espeak (you may set 'engine = espeak' in klipper-voice.conf)."
elif [ -s "$VOICES/voice.onnx" ] && [ -s "$VOICES/voice.onnx.json" ] && \
     [ "$(cat "$VOICES/NAME" 2>/dev/null)" = "$VOICE" ]; then
  green "Voice ${VOICE} already installed."
else
  # en_US-lessac-medium -> en/en_US/lessac/medium/en_US-lessac-medium.onnx
  # piper's own downloader fails on names with accents (e.g. tugão);
  # here the URL is percent-encoded instead.
  URL="$(python3 - "$VOICE" <<'PY'
import sys, urllib.parse
name = sys.argv[1]
locale, rest = name.split("-", 1)
speaker, quality = rest.rsplit("-", 1)
lang = locale.split("_")[0]
path = f"{lang}/{locale}/{speaker}/{quality}/{name}"
print("https://huggingface.co/rhasspy/piper-voices/resolve/main/" + urllib.parse.quote(path))
PY
)"
  mkdir -p "$VOICES"
  echo "Downloading ${URL}.onnx"
  if curl -fL --progress-bar -o "$VOICES/voice.onnx.tmp" "${URL}.onnx" && \
     curl -fsSL -o "$VOICES/voice.onnx.json.tmp" "${URL}.onnx.json"; then
    mv "$VOICES/voice.onnx.tmp" "$VOICES/voice.onnx"
    mv "$VOICES/voice.onnx.json.tmp" "$VOICES/voice.onnx.json"
    echo "$VOICE" > "$VOICES/NAME"
    green "Voice ${VOICE} installed (saved as voice.onnx)."
  else
    rm -f "$VOICES"/*.tmp
    red "Could not download voice ${VOICE}. The service will use espeak."
    red "Pick another voice with -v (see https://huggingface.co/rhasspy/piper-voices) and run install.sh again."
  fi
fi

# ---------------------------------------------------------------------
step "5/7 Configuration files in ${CONFIG}"
# Repository macros: symlink (updated with git)
if [ -L "$CONFIG/Voice" ] || [ ! -e "$CONFIG/Voice" ]; then
  ln -sfn "$REPO/Configuration" "$CONFIG/Voice"
  green "Linked ${CONFIG}/Voice -> ${REPO}/Configuration"
else
  red "${CONFIG}/Voice already exists and is not a symlink. Left untouched."
fi
# User files: only if they do not exist yet
for f in klipper-voice.conf Voice_Messages.cfg Voice_Settings.cfg; do
  if [ -e "$CONFIG/$f" ]; then
    yellow "${f} already exists - kept (delete it to recreate it in another language)."
  else
    render render "$LANG_CODE" "$REPO/templates/$f.in" "$CONFIG/$f"
    green "Created ${CONFIG}/${f} (${LANG_CODE})"
  fi
done
# Sound folders: the service plays whatever is inside (any name; wav, mp3,
# ogg, flac...; one at random if there are several). Default sounds are
# generated with sox; replace them with your own.
SOUNDS="$CONFIG/voice_sounds"
mkdir -p "$SOUNDS"
# Older installs had loose files: alert.wav -> pause/, done.wav -> done/,
# chime.wav -> introcall/ (an old error.wav is left where it is, unused)
for pair in pause:alert done:done introcall:chime; do
  dir="${pair%%:*}"; old="${pair##*:}"
  mkdir -p "$SOUNDS/$dir"
  if [ -e "$SOUNDS/$old.wav" ]; then mv -n "$SOUNDS/$old.wav" "$SOUNDS/$dir/"; fi
done
has_sound() { find "$1" -maxdepth 1 -type f | grep -qiE '\.(wav|mp3|ogg|oga|flac|opus|aiff?)$'; }
has_sound "$SOUNDS/done" || sox -q -n -r 22050 "$SOUNDS/done/done.wav" \
  synth 0.15 sine 660 vol 0.6 : synth 0.15 sine 880 vol 0.6 : synth 0.4 sine 1320 vol 0.6 fade 0 0.4 0.3
has_sound "$SOUNDS/pause" || sox -q -n -r 22050 "$SOUNDS/pause/pause.wav" \
  synth 0.2 sine 880 vol 0.6 : synth 0.1 sine 880 vol 0 : synth 0.2 sine 880 vol 0.6
# Intro call before each message (G-E-C, like a shopping centre announcement)
if ! has_sound "$SOUNDS/introcall"; then
  T="$(mktemp -d)"
  sox -q -n -r 22050 "$T/1.wav" synth 0.55 sine 784 fade q 0.005 0.55 0.5 vol 0.5
  sox -q -n -r 22050 "$T/2.wav" synth 0.55 sine 659 fade q 0.005 0.55 0.5 vol 0.5
  sox -q -n -r 22050 "$T/3.wav" synth 1.2 sine 523 fade q 0.005 1.2 1.15 vol 0.5
  sox -q "$T/1.wav" "$T/2.wav" "$T/3.wav" "$SOUNDS/introcall/introcall.wav"
  rm -rf "$T"
fi
green "Sounds in ${SOUNDS} (folders pause, done, introcall)"

# ---------------------------------------------------------------------
step "6/7 systemd service '${SERVICE}'"
sudo tee "/etc/systemd/system/${SERVICE}.service" >/dev/null <<EOF
[Unit]
Description=Klipper-Voice - spoken announcements for Klipper
After=moonraker.service sound.target
Wants=moonraker.service

[Service]
User=${USER}
SupplementaryGroups=audio
ExecStart="${VENV}/bin/python3" "${REPO}/klipper_voice/klipper_voice.py" "${CONFIG}/klipper-voice.conf"
Restart=always
RestartSec=5
Nice=10
CPUQuota=100%

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null 2>&1
sudo systemctl restart "$SERVICE"

# Let Moonraker manage the service (restart button in Mainsail/Fluidd)
ASVC="${PRINTER_DATA}/moonraker.asvc"
if [ -f "$ASVC" ] && ! grep -qx "$SERVICE" "$ASVC"; then
  echo "$SERVICE" >> "$ASVC"
  yellow "Added '${SERVICE}' to moonraker.asvc (restart Moonraker for it to show up)."
fi

# ---------------------------------------------------------------------
step "7/7 Check"
sleep 3
if systemctl is-active --quiet "$SERVICE"; then
  green "Service ${SERVICE} is running. You should have heard the startup phrase."
else
  red "The service did not start. See: journalctl -u ${SERVICE} -n 30 --no-pager"
fi

cat <<EOF

$(green "Installation complete.")

Left for you to do (once):

 1. Add to printer.cfg:
      [include Voice/Voice.cfg]
      [include Voice_Messages.cfg]
      [include Voice_Settings.cfg]

    Optional add-on (manual bed screws + probe only):
      [include Voice/Bed_Level_Voice.cfg]

 2. Restart Klipper and type in the console:  VOICE

    What the printer says: Voice_Messages.cfg. Volume and speed:
    Voice_Settings.cfg. Edit, then Save & Restart.

 3. For updates from Mainsail/Fluidd, add to moonraker.conf:
      [update_manager klipper-voice]
      type: git_repo
      primary_branch: main
      path: ${REPO}
      origin: https://github.com/3devangelist/Klipper-Voice.git
      virtualenv: ${VENV}
      requirements: requirements.txt
      managed_services: ${SERVICE}

 4. Hook the voice into your own macros (see README.md and PROMPT_AI.md).
EOF
