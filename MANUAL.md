# Klipper-Voice — User manual

**English** | [Português](MANUAL.pt.md)

This manual shows how to use Klipper-Voice day to day from Mainsail. To install it, see the [README](README.md). Everything here is done from the browser; you do not need SSH.

> [!WARNING]
> **Still to be tested.** The screenshots come from the only setup tested so far: an x86 mini PC with Debian 13 and Mainsail. Raspberry Pi and Fluidd have not been tested yet; in Fluidd the menus have other names, but the files are the same. Only the Portuguese (Portugal) phrases were checked by a native speaker; the other languages were written with AI help. Corrections are welcome in an [issue](https://github.com/3devangelist/Klipper-Voice/issues).

## Contents

1. [What you will hear](#1-what-you-will-hear)
2. [Test the voice](#2-test-the-voice)
3. [Where everything is](#3-where-everything-is)
4. [Change what the printer says](#4-change-what-the-printer-says)
5. [Volume and speed](#5-volume-and-speed)
6. [Your own sounds](#6-your-own-sounds)
7. [Phrases from the slicer and your macros](#7-phrases-from-the-slicer-and-your-macros)
8. [Example macros](#8-example-macros)
9. [The macro buttons](#9-the-macro-buttons)
10. [Restart the voice](#10-restart-the-voice)
11. [Updates](#11-updates)
12. [Voice-guided bed leveling](#12-voice-guided-bed-leveling)
13. [If something is wrong](#13-if-something-is-wrong)

## 1. What you will hear

Once installed, the printer speaks on its own. You do not have to change any macro.

| Moment | Example (English) |
|---|---|
| Klipper-Voice starts | Printer connected! |
| A print starts | Print started |
| Bed / nozzle heating, then hot | Bed heating … Bed hot … Nozzle heating … Nozzle hot |
| Every 10 % | 10 percent complete |
| Pause (filament runout, colour change) | *pause sound* + Printer paused, repeated every 5 minutes until you are back |
| Print resumes | Resuming print |
| Print complete | *done sound* + Print complete |
| Print cancelled | Print cancelled |
| Error, or Klipper stops | *pause sound* + Print error / Warning, Klipper has stopped |

Before each message you hear a short **intro call** (a shopping-centre "ding-dong"), so you know something is coming. It is not played when messages come one right after the other, for example during bed leveling.

## 2. Test the voice

Open **Console** and type **`VOICE`**. The printer says its test phrase, and the console shows the volume, the speed and whether the voice is on.

`VOICE` is the only command you need to control the voice; everything else is a parameter of it (sections 5 and 7).

![Console with the voice commands](docs/images/console-voice-commands.png)

## 3. Where everything is

Open **Machine**. Klipper-Voice uses these files and folders, next to `printer.cfg`:

![Machine page: the Klipper-Voice files](docs/images/machine-config-files.png)

| File / folder | What it holds |
|---|---|
| `Voice_Messages.cfg` | **what the printer says**: every phrase |
| `Voice_Settings.cfg` | **volume and speed**, plus the bed leveling settings |
| `voice_sounds/` | **the sounds**: one folder per sound |
| `klipper-voice.conf` | technical settings (timings, intro call, night mode). Usually you never touch it |
| `Voice/` | the program's own macros. **Do not edit**: they are replaced on every update |

On the right, **Update Manager** shows `klipper-voice`, so you can update it like Klipper and Mainsail.

## 4. Change what the printer says

1. In **Machine**, click **`Voice_Messages.cfg`**.
2. Change the text **between the quotes**.
3. Click **SAVE & RESTART** (top right).

![Editing Voice_Messages.cfg](docs/images/editor-voice-messages.png)

Simple rules:

- **Keep the quotes:** `variable_complete: "Your part is ready"`.
- **Empty quotes = silent:** `variable_start: ""` means the start of a print is not announced.
- **A sound before the text:** `"sound:done | Your part is ready"` plays a sound from the `voice_sounds/done/` folder, then speaks the text.
- **Percentage:** in `variable_progress`, `{p}` becomes the number: `"{p} percent done"`.
- **Never use `;` or `#`** inside a phrase. Klipper reads them as the start of a comment and cuts the phrase.
- **Your printer's name:** for example `variable_startup: "Ender 6 connected!"`.

The bed leveling phrases are at the end of the same file.

> [!CAUTION]
> **A missing quote stops Klipper.** `Voice_Messages.cfg` is read by Klipper like `printer.cfg`, so a broken line, such as a missing quote, keeps Klipper from starting until it is fixed. Klipper shows the file and the line with the problem: open `Voice_Messages.cfg` again, fix that line, then click **SAVE & RESTART**. This is the price of keeping every phrase in one simple file you can edit from Mainsail.

## 5. Volume and speed

They are at the top of **`Voice_Settings.cfg`**:

![Volume and speed in Voice_Settings.cfg](docs/images/editor-voice-settings.png)

- `variable_volume`: 0 to 100, for the voice and every sound.
- `variable_speed`: 1.0 is normal speed; a higher number is slower (1.5, 1.75…).

Change the number, then click **SAVE & RESTART**.

**Faster, by ear, from the Console:**

```
VOICE VOLUME=70
VOICE SPEED=1.6
VOICE VOLUME=70 SPEED=1.6
```

The change is applied at once and the printer says its test phrase, so you hear the result. The value is also saved in `Voice_Settings.cfg`, so it stays after a restart.

## 6. Your own sounds

`voice_sounds/` has one folder per sound:

![The sound folders](docs/images/voice-sounds-folders.png)

| Folder | Played |
|---|---|
| `pause/` | when the printer needs you: pause, filament runout, colour change, error, Klipper stopped |
| `done/` | print complete |
| `introcall/` | before each message (the "ding-dong") |

To change a sound:

1. Open the folder, for example `done`.
2. Click the **upload** button (marked in orange) and choose your file.

![Uploading a sound into the done folder](docs/images/voice-sounds-upload.png)

- **Any name** and **any common format**: mp3, wav, ogg, flac…
- **Several files in the same folder?** One is picked at random each time.
- **To go back to the old sound**, delete yours and leave the original file.
- An **empty folder** plays no sound, but the phrase is still spoken.
- MIDI files (`.mid`) are not supported. Convert them to mp3 first.

## 7. Phrases from the slicer and your macros

Your slicer's custom G-code, and your own macros, can talk too.

**Say something:**

```gcode
SAY MSG="First layer done"
```

**Give an event its own phrase, only for this print**, for example at the very top of the slicer's *Start G-code*:

```gcode
VOICE EVENT=complete MSG="The bracket for the robot is ready"
VOICE EVENT=progress MSG="%p percent of the bracket"
```

- In the slicer, write `%p` for the percentage (the slicer uses `{}` for itself).
- `MSG=""` keeps that event silent for this print.
- When the print ends, the phrases from `Voice_Messages.cfg` come back.

**All the commands:**

| Command | What it does |
|---|---|
| `SAY MSG="text"` | speaks the text |
| `PLAY_SOUND FILE=done` | plays a sound from a `voice_sounds` folder |
| `SAY_REPEAT SEC=60 MSG="Filament needed"` | repeats until `SAY_STOP`, or until a print starts or resumes |
| `SAY_STOP` | stops the repetition |
| `VOICE` | test phrase + volume, speed and on/off in the console |
| `VOICE VOLUME=70` / `VOICE SPEED=1.6` | volume / speed (section 5) |
| `VOICE MUTE=1` / `VOICE MUTE=0` | mutes / unmutes the voice (errors are always spoken) |
| `VOICE EVENT=complete MSG="..."` | own phrase for an event, for this print |
| `VOICE RESET=1` | cancels the `VOICE EVENT=` phrases |

Klipper only accepts `NAME=value` parameters, so it is `VOICE MUTE=1`, not `VOICE OFF`.

## 8. Example macros

Copy these into your own macros file (for example `macros.cfg`), never into the `Voice/` folder. Change the phrases to your language, then **SAVE & RESTART**. The automatic events (print start, heating, pause, end…) are already spoken: do not add `SAY` for them, or you will hear them twice.

**Stages of your start macro.** Add `SAY` lines to the `START_PRINT` you already have, without changing anything else:

```ini
[gcode_macro START_PRINT]
gcode:
    # ... your lines ...
    SAY MSG="Homing"
    G28
    SAY MSG="Meshing the bed"
    BED_MESH_CALIBRATE
    SAY MSG="Purging"
    # ... your purge line ...
```

**Load and unload filament:**

```ini
[gcode_macro LOAD_FILAMENT]
gcode:
    SAY MSG="Loading filament"
    M83
    G1 E50 F300
    G1 E25 F150
    SAY MSG="Filament loaded"

[gcode_macro UNLOAD_FILAMENT]
gcode:
    SAY MSG="Unloading filament"
    M83
    G1 E10 F300
    G1 E-60 F1200
    SAY MSG="Filament out, you can pull it"
```

The extruder must be hot first. Adjust the lengths to your printer.

**Say why it paused.** The pause is already announced; this adds the reason when the runout sensor triggers:

```ini
[filament_switch_sensor filament]
switch_pin: ^PA4            # your pin
pause_on_runout: True
runout_gcode:
    SAY MSG="The filament ran out"
```

**Remind me to take the part out.** At the end of your `END_PRINT`, it repeats every 5 minutes until you start the next print, or until `SAY_STOP`:

```ini
[gcode_macro END_PRINT]
gcode:
    # ... your lines ...
    SAY_REPEAT SEC=300 MSG="The part is ready to take out"
```

**Calibrations.** Klipper waits for `PID_CALIBRATE` to finish before the next line, so the second `SAY` comes at the end:

```ini
[gcode_macro PID_BED]
gcode:
    SAY MSG="Bed PID calibration started"
    PID_CALIBRATE HEATER=heater_bed TARGET=60
    SAY MSG="Bed PID done, remember to save the config"
```

**Night button.** Two buttons in the Macros panel to mute and unmute the voice:

```ini
[gcode_macro NIGHT]
gcode:
    VOICE MUTE=1

[gcode_macro DAY]
gcode:
    VOICE MUTE=0
```

For a fixed schedule, night mode in `klipper-voice.conf` (`[night]`) does it on its own.

**In the slicer** (Start G-code), give this print's end its own phrase. In OrcaSlicer:

```gcode
VOICE EVENT=complete MSG="[input_filename_base] is ready"
```

**Layer change G-code**, to hear when the first layer is done:

```gcode
{if layer_num == 1}SAY MSG="First layer done"{endif}
```

Need help hooking the voice into your own macros? [PROMPT_AI.md](PROMPT_AI.md) has a ready-made prompt to paste into your AI assistant.

## 9. The macro buttons

In **Dashboard → Macros** the voice has one **VOICE** button. Click it for the test phrase; click its arrow to fill in **VOLUME**, **SPEED**, **MUTE**, **EVENT**, **MSG** or **RESET**. `SAY`, `PLAY_SOUND`, `SAY_REPEAT` and `SAY_STOP` have their own buttons.

![The macro buttons](docs/images/macros-panel.png)

## 10. Restart the voice

Click the **power** icon (top right) → **Service Control → Klipper-voice** → restart (↻).

![Restarting the Klipper-voice service](docs/images/services-menu.png)

You only need this after editing `klipper-voice.conf`. For `Voice_Messages.cfg` and `Voice_Settings.cfg`, **SAVE & RESTART** is enough.

## 11. Updates

In **Machine → Update Manager**, `klipper-voice` is updated like Klipper and Mainsail. Your files (`Voice_Messages.cfg`, `Voice_Settings.cfg`, `klipper-voice.conf` and `voice_sounds/`) are never overwritten.

## 12. Voice-guided bed leveling

This is only for printers with **manual bed screws and a probe**. Setting it up is explained in the [README](README.md#optional-add-on-voice-guided-bed-leveling).

1. Click **BED LEVEL VOICE**. The printer heats the bed, waits, homes, and probes the first screw (the reference).
2. Above each of the other screws it keeps telling you what to do, for example *"Tighten 45 degrees"*, *"Loosen 1 turn and 30 degrees"* or *"OK"*. Turn the screw while it talks.
3. After two "OK" in a row it moves to the next screw by itself, and at the end it checks every screw again.
4. **BED LEVEL VOICE STOP** aborts at any time.

## 13. If something is wrong

| Problem | What to do |
|---|---|
| It says nothing | Type `VOICE`. If there is still silence, restart the voice (section 10) and check the speaker volume |
| A phrase did not change | Did you click **SAVE & RESTART**? Check the quotes and that there is no `;` or `#` |
| Klipper shows an error after editing | A quote is probably missing. Open the file again and fix that line |
| Too loud / too quiet | `VOICE VOLUME=…` |
| Too fast / too slow | `VOICE SPEED=…` |

More cases are in the [README](README.md#troubleshooting).
