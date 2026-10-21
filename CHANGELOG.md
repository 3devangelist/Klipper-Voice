# Changelog

## v1.9.0 — 2026-10-21

### One `VOICE` command

The voice controls are now a single command with parameters, and a single **VOICE** button in Mainsail's Macros panel:

| Before (v1.8.0) | Now |
|---|---|
| `VOICE_TEST` | `VOICE` (also shows volume, speed and on/off) |
| `VOICE_VOLUME VOLUME=70` | `VOICE VOLUME=70` |
| `VOICE_SPEED SPEED=1.6` | `VOICE SPEED=1.6` (or both: `VOICE VOLUME=70 SPEED=1.6`) |
| `VOICE_OFF` / `VOICE_ON` | `VOICE MUTE=1` / `VOICE MUTE=0` |
| `VOICE_SET EVENT=complete MSG="..."` | `VOICE EVENT=complete MSG="..."` |
| `VOICE_RESET` | `VOICE RESET=1` |

**Breaking change:** the old commands are gone. If your slicer's G-code or your own macros use them, change them as in the table. `SAY`, `PLAY_SOUND`, `SAY_REPEAT` and `SAY_STOP` stay the same.

### Clearer voice

- New default sound processing (`effects`): lighter compression that keeps the body of the voice. Chosen by ear on the Ender 6 speaker.
- Every option now starts with `gain -6`. The old default had no headroom, and its filters clipped (distorted) a little, which made the voice harder to understand.
- `klipper-voice.conf` lists four options in its comments (light, small speaker, clear consonants, pure), so each user can pick the one that suits their speaker. Existing installs keep their own `effects` line: copy the new one from the README if you want it.

### Also new

- The user manual has a section of **example macros** ready to copy: start stages, load and unload filament, runout reason, "take the part out" reminder, calibrations, night button, slicer lines.
- `tests/test_macros.py` renders the macros the way Klipper does and checks what they send.

## v1.8.0 — 2026-10-21

The first release meant for other users: install it with `git clone` + `./install.sh`, and from then on use it from Mainsail alone. A step-by-step [user manual](MANUAL.md) (also [in Portuguese](MANUAL.pt.md)) shows how.

### Everything you edit lives in Klipper files

- **`Voice_Messages.cfg`** holds every phrase the printer says, one per line. Edit it in Mainsail, then Save & Restart.
- **`Voice_Settings.cfg`** holds the volume and the speaking speed (`[gcode_macro _VOICE_SETTINGS]`), plus the bed leveling settings.
- **`voice_sounds/`** has one folder per sound: `pause/`, `done/`, `introcall/`. Drop in any wav, mp3, ogg or flac, with any name; with several files, one is picked at random.

### New

- Automatic events without macro changes: print start, nozzle and bed heating / hot, progress every 10 %, pause (repeated until you are back), resume, complete, cancel, error and Klipper shutdowns.
- **Intro call**: a shopping-centre "ding-dong" before each message, skipped when messages come in a row (for example during bed leveling).
- `VOICE_VOLUME` and `VOICE_SPEED` from the console: applied at once, saved in `Voice_Settings.cfg`.
- `VOICE_SET` / `VOICE_RESET`: give any event its own phrase for one print, from the slicer.
- `VOICE_TEST` speaks a clear test phrase in your language.
- 8 languages chosen at install time: English, Deutsch, Español, Français, Italiano, Polski, Português (Brasil), Português (Portugal).
- Voice-guided bed leveling (`BED_LEVEL_VOICE`) for printers with manual screws and a probe.
- Mainsail/Fluidd update manager support (`[update_manager klipper-voice]`).
- Tests in `tests/`, run automatically on GitHub for every push.

### Fixed

- `./install.sh` failed with "Permission denied" (scripts are now executable).
- A `VOICE_SET` for `start` in the slicer's start G-code arrived too late; `start` now waits `start_delay` seconds.
- On 32-bit ARM the install no longer aborts: it continues with espeak.
- Intel sound cards no longer pop between messages (the installer turns off their power saving).
- A shutdown in the middle of a print is announced once, not as an error plus a shutdown.
- Double quotes inside `MSG` no longer break the macros.

### Known limits

- Tested on one setup only: x86 mini PC, Debian 13, Mainsail, Portuguese (Portugal). Raspberry Pi and Fluidd are still to be tested.
- Phrases other than Portuguese (Portugal) were written with AI help and wait for a native speaker's review.
- A broken line in `Voice_Messages.cfg` (for example a missing quote) keeps Klipper from starting until it is fixed.
