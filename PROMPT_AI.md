# Prompt for your AI assistant

Klipper-Voice installs generically. Hooking the voice into **your** macros and measuring **your** bed screws is up to you. To get help, copy the text between the lines into the AI assistant you use and give it the files it asks for. It works in any language: write to it in yours.

---

```text
Help me integrate "Klipper-Voice" into my Klipper 3D printer.
Reply in the language I write to you in. Spoken phrases must be in that language too.

## How Klipper-Voice works (already installed)
- A separate Linux service ("klipper-voice") is connected to Moonraker and speaks through the host speaker.
- Klipper macros do NOT touch the audio: they only write console messages that the service picks up.
- Available commands (macros from Voice/Voice.cfg, already included):
  - SAY MSG="text"                  -> speaks the text
  - PLAY_SOUND FILE=done.wav        -> plays a sound from ~/printer_data/config/voice_sounds
  - SAY_REPEAT SEC=60 MSG="text"    -> repeats until SAY_STOP or until the print resumes
  - SAY_STOP                        -> stops the repetition
  - VOICE_OFF / VOICE_ON            -> mute / unmute (errors are always spoken)
  - Sounds and text can be combined in SAY_REPEAT: MSG="sound:alert.wav | Filament runout"
  - VOICE_SET EVENT=<event> MSG="text" -> own phrase for an automatic event during the current print
    (good for the slicer's start G-code; in the slicer use %p for the progress percentage)
  - VOICE_RESET                     -> back to the phrases in klipper-voice.conf
- The service ALREADY announces on its own, without macros: print start, nozzle heating / hot,
  bed heating / hot, progress every 10 %, paused (repeated every 5 minutes until resumed), resumed,
  complete, cancelled, error and Klipper shutdowns. Those phrases are in klipper-voice.conf, [events].
  Do NOT add SAY for those events in macros, or the phrase will be spoken twice. To change them,
  edit klipper-voice.conf or use VOICE_SET; to replace one with my own SAY lines, empty it in the conf.
- Phrases are spoken in order; if more than 3 pile up, the oldest are dropped.
- Voice-guided bed leveling (Voice/Bed_Level_Voice.cfg): BED_LEVEL_VOICE. The machine settings and
  spoken phrases are in [gcode_macro _BLV_CONFIG], file Voice_Settings.cfg.

## What I want
1. Hook the voice into my macros and my slicer's custom G-code where it makes sense, for example:
   - START_PRINT stages that are not automatic events ("Meshing", "Purging");
   - VOICE_SET lines in the slicer's start G-code to personalise events for each print;
   - end of calibrations, filament load / unload macros.
2. Fill in Voice_Settings.cfg for my machine (if I use voice-guided leveling).

## Before proposing changes, ask me for
- printer.cfg, my macro files (e.g. macros.cfg) and the [include] lines they contain;
- the probe type and its offsets (x_offset, y_offset);
- the bed size and how many leveling screws it has;
- the bed screw thread (M3, M4 or M5), if I know it.

## Rules
- Do not change the logic of my macros: only ADD SAY / PLAY_SOUND / SAY_REPEAT / SAY_STOP lines.
- For each change, show the block before and after and say which file it goes in.
- Never touch the #*# <---------------------- SAVE_CONFIG ----------------------> section or anything below it.
- Never edit files inside the Voice/ folder (they are updated with the repository).
- Never use ";" or "#" inside MSG: in Klipper they start a comment and cut the phrase.
- Short phrases (up to 8 words), no symbols or abbreviations. Numbers may be digits.
- Remind me to make a backup first and to restart Klipper afterwards.

## Screw coordinates (variable_screws)
- They are the NOZZLE coordinates when the PROBE is over each screw (same convention as Klipper's
  [screws_tilt_adjust]):  nozzle X = screw X − x_offset ;  nozzle Y = screw Y − y_offset.
- If I already have [screws_tilt_adjust] configured, use those coordinates.
- Make sure all positions are within the X and Y limits in printer.cfg.
- Pitch: M3 = 0.5 | M4 = 0.7 | M5 = 0.8 mm per turn.
- Explain how to check the direction: run BED_LEVEL_VOICE SOAK=0, tighten screw 2 a little and see
  whether the reading (mm, in the console) goes down. If "Tighten" raises the bed, set variable_invert: 1.
- If my language is not English, translate the variable_txt_* phrases.

## At the end
Give me a short test list: VOICE_TEST; a short print to hear the events; simulate a filament runout;
BED_LEVEL_VOICE SOAK=0.
```

---

**Tip:** if you use an assistant with SSH access to the machine (e.g. Claude Code), ask it to show you the changes and apply them yourself.
