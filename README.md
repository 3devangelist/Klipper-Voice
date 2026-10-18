# Klipper-Voice

Make your Klipper printer **talk**: natural-sounding spoken announcements through the host's own speaker (PC, mini PC or Raspberry Pi with audio out).

- Announces print start, complete, pause, cancel and errors, plus Klipper shutdowns, on its own. No macro changes needed.
- Simple macros for your own use: `SAY MSG="..."`, `PLAY_SOUND`, `SAY_REPEAT`...
- **Voice-guided bed leveling** (`BED_LEVEL_VOICE`): the probe parks over each screw and keeps saying "Tighten 45 degrees", "Loosen 1 turn and 30 degrees" or "OK", then moves to the next screw by itself.
- Any language [piper](https://github.com/OHF-Voice/piper1-gpl) has a voice for. English and European Portuguese settings are included.
- Built only on open-source tools: piper (natural voice), espeak-ng, sox and ALSA.

```
Klipper (macros) ──RESPOND PREFIX="SAY:"──► Moonraker (websocket)
                                                  │
                            klipper_voice.py (systemd service)
                                                  │
                         piper (voice kept in memory) / espeak-ng
                                                  │
                    sox (cut bass, compress, normalise) → aplay
```

Klipper never touches the sound card: it only writes console messages. The voice runs as a separate process, at low priority and limited to one CPU core. If the voice hangs, your print is not affected.

## Requirements

- Klipper + Moonraker (KIAUH or similar), with Mainsail or Fluidd;
- Debian, Raspberry Pi OS or Armbian;
- an audio output on the host (internal speaker, jack, USB or HDMI);
- ~200 MB of disk (Python environment + voice).

## Installation

```bash
cd ~
git clone https://github.com/3devangelist/Klipper-Voice.git
cd Klipper-Voice
./install.sh            # English
./install.sh -l pt      # European Portuguese
```

Options:

- `-v en_GB-alba-medium`: any other voice from [piper-voices](https://huggingface.co/rhasspy/piper-voices);
- `-c ~/printer_data`: another printer_data folder;
- `-n`: no natural voice, espeak only.

The installer:

1. installs `alsa-utils`, `espeak-ng`, `sox` and `python3-venv`;
2. unmutes the sound card and saves the volume;
3. creates the Python environment `~/klipper-voice-env` with piper;
4. downloads the voice to `~/klipper-voice-voices/`;
5. links `~/printer_data/config/Voice` → `~/Klipper-Voice/Configuration` and copies **once** your own files: `klipper-voice.conf`, `Voice_Settings.cfg` and `voice_sounds/`;
6. creates and starts the `klipper-voice` service, which speaks its startup phrase.

It is safe to run again: your settings are never overwritten.

### After installing (once)

In `printer.cfg`:

```ini
[include Voice/Voice.cfg]
[include Voice/Bed_Level_Voice.cfg]   # optional: voice-guided bed leveling
[include Voice_Settings.cfg]          # only if you use bed leveling
```

Restart Klipper and type `VOICE_TEST` in the console.

For updates from Mainsail/Fluidd, add to `moonraker.conf`:

```ini
[update_manager Klipper-Voice]
type: git_repo
primary_branch: main
path: ~/Klipper-Voice
origin: https://github.com/3devangelist/Klipper-Voice.git
virtualenv: ~/klipper-voice-env
requirements: requirements.txt
managed_services: klipper-voice
```

## Using the voice in your macros

| Command | Does |
|---|---|
| `SAY MSG="text"` | speaks the text |
| `PLAY_SOUND FILE=done.wav` | plays a sound from `voice_sounds` (wav, mp3, ogg...) |
| `SAY_REPEAT SEC=60 MSG="text"` | repeats until `SAY_STOP` or the print resumes |
| `SAY_STOP` | stops the repetition |
| `VOICE_OFF` / `VOICE_ON` | mute / unmute (errors are always spoken) |
| `VOICE_TEST` | speaks the startup phrase |

Examples:

```ini
[gcode_macro START_PRINT]
gcode:
    SAY MSG="Heating the bed"
    M190 S{params.BED}
    SAY MSG="Meshing"
    BED_MESH_CALIBRATE
    ...

[filament_switch_sensor runout]
runout_gcode:
    SAY_REPEAT SEC=60 MSG="sound:alert.wav | Filament runout"
```

Every machine has its own macros, so this part is yours. For help, **[PROMPT_AI.md](PROMPT_AI.md)** has a ready-made prompt to paste into your AI assistant. It asks for the right files and only proposes additions, never changing your macro logic.

**Two rules:**

- If several messages arrive while the voice is speaking, only the most recent is spoken next. With two `SAY` lines in a row and nothing in between, you only hear the second one.
- Never use `;` or `#` inside `MSG`: Klipper treats them as comments. Use `|` to chain sounds and phrases.

## Automatic events and settings (`klipper-voice.conf`)

Edit `~/printer_data/config/klipper-voice.conf` from Mainsail/Fluidd, then restart the `klipper-voice` service.

```ini
[events]
complete = sound:done.wav | Print complete
error = sound:error.wav | Print error
shutdown = sound:error.wav | Warning, Klipper has stopped
start =

[night]
enabled = yes
```

An empty event (like `start =`) stays silent. With `enabled = yes`, night mode keeps quiet between 23:00 and 08:00.

Other options, all commented in the file: voice engine (`piper`, `espeak`, or `text` for testing without audio), speaking speed, sound card and sound processing.

## Voice-guided bed leveling

```
BED_LEVEL_VOICE                 ; heat, soak, home and start
BED_LEVEL_VOICE BED=80 SOAK=5   ; other temperature / soak (minutes)
BED_LEVEL_VOICE SOAK=0          ; no soak (testing)
BED_LEVEL_VOICE_STOP            ; abort
```

1. Probes the 1st screw: the reference, never adjusted.
2. Parks over the next screw, probing continuously, and says how much to turn. Degrees come from the screw pitch (M4: 0.7 mm per turn, so 0.1 mm ≈ 51°), rounded to 5°.
3. After 2 "OK" readings in a row it moves on to the next screw.
4. Finishes with a verification pass and goes round again if any screw drifted.

Before using it, fill in `Voice_Settings.cfg` for your machine:

- `variable_screws`: **nozzle** coordinates with the probe over each screw, the `[screws_tilt_adjust]` convention. Nozzle = screw − probe offset.
- `variable_pitch`: M3 = 0.5, M4 = 0.7, M5 = 0.8.
- `variable_invert: 1` if "Tighten" raises the bed.
- `variable_txt_*`: the spoken phrases, in your language.

To check the direction, run `BED_LEVEL_VOICE SOAK=0`, tighten screw 2 a little and watch whether the mm value in the console goes down.

## Troubleshooting

| Problem | Fix |
|---|---|
| No sound | `aplay -l` to see the card; `alsamixer` (F6 picks the card, M unmutes); `sudo alsactl store` |
| The voice says nothing | `journalctl -u klipper-voice -f` and type `VOICE_TEST`; you should see the request in the log |
| `RESPOND` error | `[respond]` is missing; `Voice.cfg` already includes it, check `[include Voice/Voice.cfg]` |
| Voice too quiet | check the volume in `alsamixer`; `effects` in the conf already normalises to −1 dB |
| Old voice after a config change | `sudo systemctl restart klipper-voice`; `pgrep -af klipper_voice.py` must show a single process |
| Sound on the wrong output (e.g. HDMI) | `device = plughw:1,0` in the conf (numbers from `aplay -l`) |
| piper's downloader fails with `UnicodeEncodeError` | voice names with accents (e.g. `tugão`); `install.sh` already works around it |

Diagnostics:

```bash
systemctl status klipper-voice --no-pager
journalctl -u klipper-voice -f
```

## Uninstall

```bash
~/Klipper-Voice/uninstall.sh
```

Your files (`klipper-voice.conf`, `Voice_Settings.cfg`, `voice_sounds/`) are kept. Then remove the `[include Voice/...]` lines from `printer.cfg`.

## Credits and licence

Created by Ricardo Pereira (Mazecreative) for an Ender 6 in Vila Nova de Gaia, Portugal. Repository layout inspired by [KAMP](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging).

Licence: GPL-3.0. Each piper voice carries its own licence; see its model card in piper-voices.
