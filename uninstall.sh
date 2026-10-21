#!/usr/bin/env bash
# Klipper-Voice - uninstaller
# Removes the service, the Python environment, the voices and the Voice/ link.
# Does NOT delete your files: klipper-voice.conf, Voice_Settings.cfg, voice_sounds/.
# Remember to remove the [include Voice/...] lines from printer.cfg.
set -euo pipefail

PRINTER_DATA="${1:-$HOME/printer_data}"
SERVICE="klipper-voice"

sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/${SERVICE}.service" /etc/modprobe.d/klipper-voice.conf
sudo systemctl daemon-reload
pkill -f klipper_voice.py 2>/dev/null || true

[ -L "$PRINTER_DATA/config/Voice" ] && rm "$PRINTER_DATA/config/Voice"
[ -f "$PRINTER_DATA/moonraker.asvc" ] && sed -i "/^${SERVICE}\$/d" "$PRINTER_DATA/moonraker.asvc"
rm -rf "$HOME/klipper-voice-env" "$HOME/klipper-voice-voices"

echo "Klipper-Voice removed."
echo "Kept (delete by hand if you want): $PRINTER_DATA/config/klipper-voice.conf, Voice_Settings.cfg, voice_sounds/"
echo "Remove the [include Voice/...] lines from printer.cfg and [update_manager klipper-voice] from moonraker.conf."
