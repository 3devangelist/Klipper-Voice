# Klipper-Voice

Make your Klipper printer **talk**. Every important moment of a print is spoken aloud through the host's own speaker (PC, mini PC or Raspberry Pi with audio out), in your language and with your own phrases:

> "Bed heating" … "Bed hot" … "Nozzle heating" … "Nozzle hot" … "10 percent complete" … "20 percent complete" … "Printer paused" *(repeated every 5 minutes until you are back)* … "Print complete"

- **Automatic events, no macro changes:** print start, nozzle and bed heating / hot, progress every 10 %, pause, resume, complete, cancel, error and Klipper shutdowns.
- **Your phrases:** everything the printer says is in one simple file, `Voice_Messages.cfg`. The **slicer** can also give any event its own phrase for a single print (`VOICE_SET`).
- **Never miss a pause:** while the printer waits for filament or a colour change, it reminds you every N minutes.
- **Your own messages** from any macro or from the slicer's custom G-code: `SAY MSG="..."`.
- **8 languages ready**, chosen at install time: English, Deutsch, Español, Français, Italiano, Polski, Português (Brasil), Português (Portugal). Adding one more is a single JSON file.
- Natural, offline voices ([piper](https://github.com/OHF-Voice/piper1-gpl)), with espeak-ng as fallback. Only open-source tools: piper, espeak-ng, sox, ALSA.
- Optional add-on for printers with manual bed screws and a probe: voice-guided bed leveling.

```
Klipper ──► Moonraker ──► klipper_voice.py (systemd service)
  print state, heaters,        │  watches events, picks the phrase
  progress, SAY/VOICE_SET      ▼
                        piper / espeak-ng → sox → aplay → speaker
```

Klipper never touches the sound card: the service listens to Moonraker as a separate process, at low priority and limited to one CPU core. If the voice hangs, your print is not affected.

## Requirements

- Klipper + Moonraker (KIAUH or similar), with Mainsail or Fluidd;
- Debian, Raspberry Pi OS or Armbian;
- an audio output on the host (internal speaker, jack, USB or HDMI);
- ~200 MB of disk (Python environment + one voice).

On 32-bit ARM (armv6/armv7, e.g. 32-bit Raspberry Pi OS) piper cannot be installed, so the printer speaks with espeak. A 64-bit system gives you the natural voices.

## Installation

```bash
cd ~
git clone https://github.com/3devangelist/Klipper-Voice.git
cd Klipper-Voice
./install.sh
```

The installer **asks which language** the printer should speak. The language decides which voice model is downloaded for the synthesizer and which phrases are written into your config.

```
Which language should the printer speak?
   1) English                (en, voice en_US-lessac-medium)
   2) Deutsch                (de, voice de_DE-thorsten-medium)
   ...
   8) Português (Portugal)   (pt_PT, voice pt_PT-tugão-medium)
Number [1]:
```

Options for unattended installs:

- `-l pt_PT`: choose the language without the question;
- `-v en_GB-alba-medium`: another voice from [piper-voices](https://huggingface.co/rhasspy/piper-voices);
- `-c ~/printer_data`: another printer_data folder;
- `-n`: no natural voice, espeak only.

The installer:

1. installs `alsa-utils`, `espeak-ng`, `sox` and `python3-venv`;
2. unmutes the sound card, saves the volume and, on Intel cards, turns off the power saving that makes them pop;
3. creates the Python environment `~/klipper-voice-env` with piper;
4. downloads the voice to `~/klipper-voice-voices/`. If the download fails, the service falls back to espeak;
5. links `~/printer_data/config/Voice` → `~/Klipper-Voice/Configuration`;
6. creates **once**, in your language, `Voice_Messages.cfg` (what the printer says), `Voice_Settings.cfg` (volume, speed and the bed leveling add-on), `klipper-voice.conf` (timings, intro call, night mode) and the sound folders in `voice_sounds/`;
7. creates and starts the `klipper-voice` service, which speaks its startup phrase.

It is safe to run again: your files are never overwritten. To switch language, delete `Voice_Messages.cfg`, `Voice_Settings.cfg` and `klipper-voice.conf` and run `./install.sh -l <code>`.

### After installing (once)

In `printer.cfg`:

```ini
[include Voice/Voice.cfg]
[include Voice_Messages.cfg]
[include Voice_Settings.cfg]
```

Restart Klipper and type `VOICE_TEST` in the console. From then on the automatic events already work.

Too loud, too fast? Set them in `Voice_Settings.cfg`, like any other Klipper setting, then Save & Restart:

```ini
[gcode_macro _VOICE_SETTINGS]
variable_volume: 70       # 0..100
variable_speed: 1.6       # 1.0 normal, higher = slower
```

Or tune them by ear from the console: `VOICE_VOLUME VOLUME=70`, `VOICE_SPEED SPEED=1.6`. Each change is applied at once and saved in the same file. Each language starts with its own speed.

For updates from Mainsail/Fluidd, add to `moonraker.conf` (the section name must be `klipper-voice`, the same as the service, or Moonraker rejects `managed_services`):

```ini
[update_manager klipper-voice]
type: git_repo
primary_branch: main
path: ~/Klipper-Voice
origin: https://github.com/3devangelist/Klipper-Voice.git
virtualenv: ~/klipper-voice-env
requirements: requirements.txt
managed_services: klipper-voice
```

## What the printer says (`Voice_Messages.cfg`)

All the phrases are in one file, `Voice_Messages.cfg`, next to `printer.cfg`. Open it in Mainsail/Fluidd, change any phrase between the quotes, then **Save & Restart**:

```ini
[gcode_macro _VOICE_MESSAGES]
variable_startup: "Ender 6 connected!"
variable_complete: "sound:done | Your part is ready"
variable_progress: "{p} percent done"
variable_start: ""
```

- Keep the quotes. `""` keeps that message silent.
- `sound:done | text` plays a sound from the folder `voice_sounds/done/`, then the text. Use `|` to chain sounds and phrases.
- Never use `;` or `#` inside a phrase.
- The bed leveling phrases are at the end of the same file.

## Automatic events

The service watches the printer through Moonraker and speaks on its own:

| Event | When | Default phrase (en) |
|---|---|---|
| `start` | a print starts | Print started |
| `bed_heating` / `bed_hot` | bed target set / reached | Bed heating / Bed hot |
| `nozzle_heating` / `nozzle_hot` | nozzle target set / reached | Nozzle heating / Nozzle hot |
| `progress` | every `progress_step` % (default 10) | {p} percent complete |
| `paused` | pause (runout, M600, PAUSE), repeated every `paused_repeat_minutes` (default 5) | Printer paused |
| `resumed` | print resumes | Resuming print |
| `complete` / `cancelled` | end of print | Print complete / Print cancelled |
| `error` / `shutdown` | print error / Klipper stopped (a shutdown mid-print says only the `shutdown` phrase) | Print error / Warning, Klipper has stopped |

The timings are in `~/printer_data/config/klipper-voice.conf` (after editing it, restart the `klipper-voice` service):

```ini
[events]
progress_step = 25
paused_repeat_minutes = 3
```

- Each message starts with an **intro call**, an attention sound like in a shopping centre (`introcall` in `[sounds]`, empty = off). It is skipped when the message brings its own sound, or when the previous one ended less than `introcall_gap` seconds ago (60 by default), so bed leveling and phrases in a row are not interrupted.

## Your own sounds (`voice_sounds/`)

One folder per sound, next to `printer.cfg`:

| Folder | Played |
|---|---|
| `pause/` | when the printer needs you: pause (filament runout, colour change), print error, Klipper stopped |
| `done/` | print complete |
| `introcall/` | before each message (the intro call) |

Upload any audio file into a folder from Mainsail/Fluidd: any name, wav, mp3, ogg or flac. Put several and one is picked at random each time. An empty folder stays silent and the phrase is still spoken. The installer fills each folder with a simple default sound.
- Progress follows `M73` if your slicer emits it, otherwise the file position.
- Heating is only announced for real heat-ups, at least `heating_min_delta` degrees, so small temperature changes during a print stay silent.

Other options, all commented in the file: night mode (silent at night, errors still spoken), voice engine (`piper`, `espeak`, or `text` to test without audio), sound card and sound processing. Volume and speed are in `Voice_Settings.cfg`.

## Phrases from the slicer

Klipper runs the slicer's custom G-code like any other G-code, so the slicer can talk too.

**Give an event its own phrase for this print** with `VOICE_SET`, for example in the *Machine start G-code*. The phrase applies until the print ends, then the config phrases return. A `VOICE_SET` typed in the console outside a print is dropped when the next print starts.

```gcode
VOICE_SET EVENT=complete MSG="The bracket for the robot is ready"
VOICE_SET EVENT=progress MSG="%p percent of the bracket"
VOICE_SET EVENT=start MSG=""
```

- Put the `VOICE_SET` lines at the **top** of the start G-code. The `start` phrase waits `start_delay` seconds (default 3) so they arrive in time, and heating phrases in those seconds are spoken after it.
- `MSG=""` silences that event for this print.
- In the slicer, write `%p` for the percentage, because `{}` belongs to the slicer's own placeholders.
- You can use the slicer's placeholders in the phrase. In OrcaSlicer, for example: `VOICE_SET EVENT=complete MSG="[input_filename_base] is ready"`.

**Say something at a specific moment** with `SAY`, for example in the *Layer change G-code*:

```gcode
{if layer_num == 1}SAY MSG="First layer done"{endif}
```

**Or take over the heating phrases yourself.** Set `variable_bed_heating`, `variable_bed_hot`, `variable_nozzle_heating` and `variable_nozzle_hot` to `""` in `Voice_Messages.cfg`, then in the start G-code:

```gcode
SAY MSG="Bed heating"
M190 S[bed_temperature_initial_layer_single]
SAY MSG="Bed hot, nozzle heating"
M109 S[nozzle_temperature_initial_layer]
SAY MSG="Nozzle hot"
```

## Commands for your macros and the slicer

| Command | Does |
|---|---|
| `SAY MSG="text"` | speaks the text |
| `PLAY_SOUND FILE=done` | plays a sound from a `voice_sounds` folder (or a file: `FILE=my.mp3`) |
| `SAY_REPEAT SEC=60 MSG="text"` | repeats until `SAY_STOP` or the print resumes |
| `SAY_STOP` | stops the repetition |
| `VOICE_SET EVENT=... MSG="..."` | phrase for an automatic event, for this print |
| `VOICE_RESET` | back to the phrases in `Voice_Messages.cfg` |
| `VOICE_VOLUME VOLUME=70` | volume 0..100 for voice and sounds. Applied at once, saved in `Voice_Settings.cfg`, and a sample phrase is spoken. Without `VOLUME` it shows the current value |
| `VOICE_SPEED SPEED=1.4` | speaking speed: 1.0 normal, higher = slower. Applied at once, saved in `Voice_Settings.cfg`, and a sample phrase is spoken. Without `SPEED` it shows the current value |
| `VOICE_OFF` / `VOICE_ON` | mute / unmute (errors are always spoken) |
| `VOICE_TEST` | speaks the test phrase (`variable_test` in `Voice_Messages.cfg`) |

**Two rules:**

- Never use `;` or `#` inside `MSG`: Klipper treats them as comments. Double quotes inside `MSG` become single quotes.
- Phrases are spoken in order, one at a time. If more than 3 pile up, the oldest are dropped. Set `queue` in the conf to change that.

For help hooking the voice into your own macros, **[PROMPT_AI.md](PROMPT_AI.md)** has a ready-made prompt to paste into your AI assistant.

## Adding a language

1. Copy `languages/en.json` to `languages/<code>.json`, for example `nl.json`.
2. Translate the phrases. Pick a `voice` from [piper-voices](https://huggingface.co/rhasspy/piper-voices) and an `espeak` language code.
3. It then shows up in the installer's list. Pull requests are welcome.

## Optional add-on: voice-guided bed leveling

For printers with **manual bed screws and a probe**. Printers with automatic leveling (Z tilt, quad gantry, load cell...) or without a probe don't need it.

To use it, add to `printer.cfg` (next to the `Voice_Settings.cfg` include you already have):

```ini
[include Voice/Bed_Level_Voice.cfg]
```

Then run it:

```
BED_LEVEL_VOICE                 ; heat, soak, home and start
BED_LEVEL_VOICE BED=80 SOAK=5   ; other temperature / soak (minutes)
BED_LEVEL_VOICE SOAK=0          ; no soak (testing)
BED_LEVEL_VOICE_STOP            ; abort
```

The probe parks over each screw, probing continuously, and keeps saying how much to turn: "Tighten 45 degrees", "Loosen 1 turn and 30 degrees" or "OK". It then moves to the next screw by itself and finishes with a verification pass. Degrees come from the screw pitch: M4 is 0.7 mm per turn, so 0.1 mm ≈ 51°.

Before using it, fill in `Voice_Settings.cfg`:

- `variable_screws`: **nozzle** coordinates with the probe over each screw, the `[screws_tilt_adjust]` convention. Nozzle = screw − probe offset.
- `variable_pitch`: M3 = 0.5, M4 = 0.7, M5 = 0.8.
- `variable_invert: 1` if "Tighten" raises the bed.

## Troubleshooting

| Problem | Fix |
|---|---|
| No sound | `aplay -l` to see the card; `alsamixer` (F6 picks the card, M unmutes); `sudo alsactl store` |
| The voice says nothing | `journalctl -u klipper-voice -f` and type `VOICE_TEST`; the log shows every event and phrase |
| `RESPOND` error | `[respond]` is missing; `Voice.cfg` already includes it, check `[include Voice/Voice.cfg]` |
| Voice too quiet / too loud | `variable_volume` in `Voice_Settings.cfg`, or `VOICE_VOLUME VOLUME=70` from the console; check the volume in `alsamixer`; `effects` in the conf already normalises to −1 dB |
| A pop or noise now and then | Intel sound cards power down when idle and pop when they wake up. `install.sh` turns that off (`/etc/modprobe.d/klipper-voice.conf`); run it again on older installs |
| Robotic voice | piper voice missing or failed to load: see the log, run `./install.sh -v <voice>` |
| Old phrases after a change | `Voice_Messages.cfg`: Save & Restart (Klipper). `klipper-voice.conf`: `sudo systemctl restart klipper-voice`; `pgrep -af klipper_voice.py` must show a single process |
| Sound on the wrong output (e.g. HDMI) | `device = plughw:1,0` in the conf (numbers from `aplay -l`) |

## Uninstall

```bash
~/Klipper-Voice/uninstall.sh
```

Your files (`Voice_Messages.cfg`, `klipper-voice.conf`, `Voice_Settings.cfg`, `voice_sounds/`) are kept. Then remove the `[include Voice/...]` lines from `printer.cfg`.

## Credits and licence

Created by Ricardo Pereira for an Ender 6 in Vila Nova de Gaia, Portugal - vivecoded with Claude.

"CLAUDE"
Adiciona aqui um texto a explicar de onde a ideia nasceu
problemas na impressora por instabilidade de pacotes e problemas no cartão SD mudei de cartão 2 vezes no ultimo ano!
comprei um pc mini hp por 80 euros  HP 800 G2 MINI CORE i3-6100T 6-GEN 4GB 128GB SSD
quando estava a configurar o sistema lembreime que tinha placa de som e uma pequena coluna e neste contexto nasceu este sistema

Corrige este texto e coloca direito 


Repository layout inspired by [KAMP](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging).

Licence: GPL-3.0. Each piper voice carries its own licence; see its model card in piper-voices.
