#!/usr/bin/env python3
"""
klipper_voice.py - makes the Klipper host speak (Klipper-Voice)

Connects to Moonraker and:
  - announces the printer's main events on its own, with your own phrases:
      print start, nozzle heating / nozzle hot, bed heating / bed hot,
      progress every N %, paused (repeated every N minutes until resumed),
      resumed, complete, cancelled, error and Klipper shutdowns
  - speaks console lines starting with "SAY:"          (SAY macro)
  - plays sounds from lines starting with "SOUND:"     (PLAY_SOUND macro)
  - obeys "VOICE_CTL:" off | on | stop | test | repeat <sec> <text>
                       | set <event> <text> | reset | speed [value]
                       | volume [value]
    ("set" lets the slicer's start G-code give any event its own phrase
     for the current print; "speed" and "volume" change length_scale and
     volume live and save them in the config file)

The phrases live in Voice_Messages.cfg ([gcode_macro _VOICE_MESSAGES],
read from Klipper: edit, then Save & Restart). The other settings live in
~/printer_data/config/klipper-voice.conf; after editing it, restart the
"klipper-voice" service. Phrases still found in the conf are used when
Voice_Messages.cfg does not have them.

Rules:
  - every request is spoken to the end (never cut mid-sentence);
  - requests are spoken in order; if more than "queue" requests pile up,
    the oldest are dropped (they are stale by then);
  - the piper voice is loaded once at startup, so speech starts quickly.

Usage: klipper_voice.py [path/to/klipper-voice.conf]
"""

import asyncio
import collections
import configparser
import datetime
import json
import os
import random
import re
import shlex
import subprocess
import sys
import time
import wave

import websockets

VERSION = "1.8.0"
DEFAULT_CONF = "~/printer_data/config/klipper-voice.conf"

EVENTS = ("start", "nozzle_heating", "nozzle_hot", "bed_heating", "bed_hot",
          "progress", "paused", "resumed", "complete", "cancelled", "error",
          "shutdown")
ERROR_EVENTS = ("error", "shutdown")
# Events that wait while "start" is pending, so they are spoken after it
HELD_EVENTS = ("nozzle_heating", "nozzle_hot", "bed_heating", "bed_hot",
               "progress")
# VOICE_SET lines older than this when a print starts were typed outside a
# print and are dropped (newer ones may have raced ahead of the state change)
OVERRIDE_GRACE = 10
# A print "error" this soon after a Klipper shutdown is not spoken twice
SHUTDOWN_WINDOW = 15
# VOICE_SPEED limits (length_scale: 1.0 = normal, higher = slower)
SPEED_MIN, SPEED_MAX = 0.5, 3.0
# Klipper objects holding the phrases (Voice_Messages.cfg) and the
# volume / speed (Voice_Settings.cfg)
MESSAGES = "gcode_macro _VOICE_MESSAGES"
SETTINGS = "gcode_macro _VOICE_SETTINGS"
# Sound files picked from the voice_sounds/<name>/ folders (sox reads them)
AUDIO_EXT = (".wav", ".mp3", ".ogg", ".oga", ".flac", ".opus", ".aiff",
             ".aif")
# Older sound names -> the folder that replaced them
SOUND_ALIASES = {"alert": "pause", "error": "pause", "chime": "introcall"}
# Seconds to wait for Klipper before the startup phrase is spoken anyway
STARTUP_WAIT = 30

DEFAULTS = {
    "general": {
        "moonraker": "ws://127.0.0.1:7125/websocket",
        "startup": "Voice ready",
        "test": "",                             # empty: use "startup"
        "queue": "3",
    },
    "voice": {
        "engine": "piper",                      # piper | espeak | text
        "model": "~/klipper-voice-voices/voice.onnx",
        "length_scale": "1.2",
        "volume": "100",                        # 0..100, voice and sounds
        "effects": ("highpass 250 compand 0.05,0.2 "
                    "6:-70,-60,-30,-15,-15,-6,0,-3 -3 -90 0.1 gain -n -1"),
        "espeak": "espeak-ng -v en -s 165 -a 140",
        "device": "",
    },
    "sounds": {
        "folder": "~/printer_data/config/voice_sounds",
        # introcall / introcall_gap: attention sound before each message
        # (older confs call them chime / chime_gap)
    },
    "events": {
        "start": "Print starting",
        "start_delay": "3",
        "nozzle_heating": "Nozzle heating",
        "nozzle_hot": "Nozzle hot",
        "bed_heating": "Bed heating",
        "bed_hot": "Bed hot",
        "progress": "{p} percent complete",
        "progress_step": "10",
        "paused": "sound:pause | Printer paused for filament reload or colour change",
        "paused_repeat_minutes": "5",
        "resumed": "Resuming print",
        "complete": "sound:done | Print complete",
        "cancelled": "Print cancelled",
        "error": "sound:pause | Print error",
        "shutdown": "sound:pause | Warning, Klipper has stopped",
        "say_error_message": "no",
        "heating_min_delta": "10",
        "hot_margin": "3",
    },
    "night": {
        "enabled": "no",
        "start": "23:00",
        "end": "08:00",
        "allow_errors": "yes",
    },
}

PREFIX_SAY = "SAY:"
PREFIX_SOUND = "SOUND:"
PREFIX_CTL = "VOICE_CTL:"

# Klipper object -> event prefix
HEATERS = {"extruder": "nozzle", "heater_bed": "bed"}


def log(*args):
    print(*args, flush=True)


def expand(p):
    return os.path.expanduser(p.strip())


def items_of(value):
    """'sound:done | Print complete' -> ['sound:done', 'Print complete']"""
    return [i.strip() for i in (value or "").split("|") if i.strip()]


def clock(txt):
    h, m = txt.strip().split(":")
    return datetime.time(int(h), int(m))


class KlipperVoice:
    def __init__(self, conf_file):
        self.cp = configparser.ConfigParser(interpolation=None)
        self.cp.read_dict(DEFAULTS)
        found = self.cp.read(expand(conf_file), encoding="utf-8")
        self.conf_file = found[0] if found else None
        log(f"Klipper-Voice v{VERSION}; config: "
            f"{self.conf_file or 'none (using defaults)'}")

        self.engine = self.cp.get("voice", "engine").strip().lower()
        self.length_scale = self.cp.getfloat("voice", "length_scale")
        self.volume = min(100, max(0, self.cp.getint("voice", "volume")))
        # espeak speed (-s, words per minute) follows length_scale changes
        # made with VOICE_SPEED, relative to the values in the config file
        m = re.search(r"-s\s+(\d+)", self.cp.get("voice", "espeak"))
        self.espeak_base = (int(m.group(1)) if m else 175, self.length_scale)
        self.device = self.cp.get("voice", "device").strip()
        self.effects = self.cp.get("voice", "effects").split()
        self.sound_dir = expand(self.cp.get("sounds", "folder"))
        self.chime = self.cp.get("sounds", "introcall", fallback=self.cp.get(
            "sounds", "chime", fallback="")).strip()
        self.chime_gap = self.cp.getfloat(
            "sounds", "introcall_gap",
            fallback=self.cp.getfloat("sounds", "chime_gap", fallback=60))
        self.last_spoken = float("-inf")  # when the last message ended
        self.wav = f"/tmp/klipper-voice-{os.getuid()}.wav"
        self.queue = collections.deque(
            maxlen=max(1, self.cp.getint("general", "queue")))
        self.progress_step = self.cp.getfloat("events", "progress_step")
        self.pause_repeat = 60 * self.cp.getfloat(
            "events", "paused_repeat_minutes")
        self.heat_delta = self.cp.getfloat("events", "heating_min_delta")
        self.hot_margin = self.cp.getfloat("events", "hot_margin")
        self.start_delay = self.cp.getfloat("events", "start_delay")

        self.synthesize = None
        self.has_request = asyncio.Event()
        self.muted = False
        self.repeater = None              # repeating task (pause / SAY_REPEAT)
        self.overrides = {}               # event -> phrase, from VOICE_SET
        self.messages = {}                # phrases from Voice_Messages.cfg
        self.klipper_settings = False     # Voice_Settings.cfg has volume...
        self.settings_file = os.path.join(os.path.dirname(
            self.conf_file or expand(DEFAULT_CONF)), "Voice_Settings.cfg")
        self.startup_pending = True       # startup phrase not spoken yet
        self.overrides_at = float("-inf")  # time of the last VOICE_SET
        self.start_task = None            # pending "start" announcement
        self.held = None                  # events waiting for "start"
        self.print_state = None
        self.last_progress = 0.0          # last announced progress step (%)
        self.heaters = {h: {"target": 0.0, "temperature": 0.0,
                            "heating": False} for h in HEATERS}
        self.last_shutdown = float("-inf")
        self.ws = None
        self.next_id = 1
        self.subscribe_ids = set()

    # ---------------------------------------------------------- audio
    def load_piper(self):
        try:
            from piper import PiperVoice, SynthesisConfig
            voice = PiperVoice.load(expand(self.cp.get("voice", "model")))

            def _synthesize(text):
                cfg = SynthesisConfig(length_scale=self.length_scale)
                with wave.open(self.wav, "wb") as f:
                    voice.synthesize_wav(text, f, syn_config=cfg)

            self.synthesize = _synthesize
            log("Piper loaded")
        except Exception as e:                       # noqa: BLE001
            log(f"Piper unavailable ({e}); falling back to espeak")
            self.engine = "espeak"

    def aplay(self):
        cmd = ["aplay", "-q"]
        if self.device:
            cmd += ["-D", self.device]
        return cmd

    def pipe(self, *cmds):
        """cmd1 | cmd2 | ..., waiting for all of them to finish."""
        procs, prev = [], None
        for i, cmd in enumerate(cmds):
            last = i == len(cmds) - 1
            p = subprocess.Popen(cmd, stdin=prev,
                                 stdout=subprocess.DEVNULL if last
                                 else subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
            if prev:
                prev.close()
            prev = p.stdout
            procs.append(p)
        for p in reversed(procs):
            p.wait()

    def vol(self):
        """sox effect for the volume option (100 = as is)."""
        return ["vol", f"{self.volume / 100:.2f}"]

    def find_sound(self, name):
        """"done" -> a file from voice_sounds/done/ (any name, wav, mp3,
        ogg...; one at random if there are several). A file name also
        works; "done.wav" falls back to the done/ folder, and the older
        names alert / error / chime to pause / pause / introcall."""
        path = name if os.path.isabs(name) else os.path.join(
            self.sound_dir, name)
        if os.path.isfile(path):
            return path
        folder = path if os.path.isdir(path) else os.path.splitext(path)[0]
        alias = SOUND_ALIASES.get(os.path.basename(folder).lower())
        if not os.path.isdir(folder) and alias:
            folder = os.path.join(os.path.dirname(folder), alias)
        if os.path.isdir(folder):
            files = sorted(f for f in os.listdir(folder)
                           if f.lower().endswith(AUDIO_EXT)
                           and os.path.isfile(os.path.join(folder, f)))
            if files:
                return os.path.join(folder, random.choice(files))
            log(f"No sound files in {folder}")
            return None
        log(f"Sound not found: {path}")
        return None

    def play_item(self, item):
        """Runs in a worker thread: plays a sound or speaks a text."""
        if item.lower().startswith("sound:"):
            path = self.find_sound(item[6:].strip())
            if not path:
                return
            if self.engine == "text":
                log(f"[sound] {path}")
                return
            self.pipe(["sox", "-q", path, "-t", "wav", "-"] + self.vol(),
                      self.aplay())
            return

        if self.engine == "text":
            log(f"[say] {item}")
        elif self.engine == "piper":
            self.synthesize(item)
            self.pipe(["sox", "-q", self.wav, "-t", "wav", "-"]
                      + self.effects + self.vol(), self.aplay())
        else:
            wpm, ls = self.espeak_base
            speed = ["-s", str(round(wpm * ls / self.length_scale))]
            self.pipe(shlex.split(self.cp.get("voice", "espeak")) + speed
                      + ["--stdout", item],
                      ["sox", "-q", "-t", "wav", "-", "-t", "wav", "-"]
                      + self.vol(), self.aplay())

    async def speaker(self):
        loop = asyncio.get_running_loop()
        while True:
            await self.has_request.wait()
            while self.queue:
                items, is_error = self.queue.popleft()
                items = self.with_chime(items)
                for item in items:
                    if not self.allowed(is_error):
                        break
                    try:
                        await loop.run_in_executor(None, self.play_item, item)
                    except Exception as e:           # noqa: BLE001
                        log(f"Error playing '{item}': {e}")
                self.last_spoken = time.monotonic()
            self.has_request.clear()

    def with_chime(self, items):
        """Puts the attention sound before a message, unless the message
        brings its own sound or follows the previous one within chime_gap
        seconds (bed leveling, several phrases in a row)."""
        if not self.chime or items[0].lower().startswith("sound:") or \
                time.monotonic() - self.last_spoken < self.chime_gap:
            return items
        return ["sound:" + self.chime] + items

    # -------------------------------------------------------- filters
    def is_night(self):
        if not self.cp.getboolean("night", "enabled"):
            return False
        start = clock(self.cp.get("night", "start"))
        end = clock(self.cp.get("night", "end"))
        now = datetime.datetime.now().time()
        if start <= end:
            return start <= now < end
        return now >= start or now < end

    def allowed(self, is_error):
        if is_error:
            return not self.is_night() or self.cp.getboolean(
                "night", "allow_errors")
        return not self.muted and not self.is_night()

    def request(self, items, is_error=False):
        if not items or not self.allowed(is_error):
            return
        entry = (list(items), is_error)
        if self.queue and self.queue[-1] == entry:
            return                                   # same phrase queued
        self.queue.append(entry)
        self.has_request.set()

    # --------------------------------------------------------- repeat
    def stop_repeat(self):
        if self.repeater:
            self.repeater.cancel()
            self.repeater = None

    async def _repeat(self, seconds, items, first_now=True):
        if not first_now:
            await asyncio.sleep(seconds)
        while True:
            self.request(items)
            await asyncio.sleep(seconds)

    def start_repeat(self, seconds, items, first_now=True):
        self.stop_repeat()
        if items and seconds > 0:
            self.repeater = asyncio.create_task(
                self._repeat(max(5.0, seconds), items, first_now))

    def control(self, text):
        parts = text.split(None, 2)
        cmd = parts[0].lower() if parts else ""
        if cmd == "off":
            self.muted = True
            self.stop_repeat()
            log("Voice muted (errors are still spoken)")
        elif cmd == "on":
            self.muted = False
            log("Voice unmuted")
        elif cmd == "stop":
            self.stop_repeat()
        elif cmd == "test":
            self.request(self.test_items())
        elif cmd == "repeat" and len(parts) == 3:
            try:
                seconds = float(parts[1])
            except ValueError:
                log(f"VOICE_CTL repeat: invalid interval '{parts[1]}'")
                return
            self.start_repeat(seconds, items_of(parts[2]))
        elif cmd == "set" and len(parts) >= 2:
            event = parts[1].lower()
            if event not in EVENTS:
                log(f"VOICE_SET: unknown event '{event}' "
                    f"(valid: {', '.join(EVENTS)})")
                return
            self.overrides[event] = parts[2] if len(parts) == 3 else ""
            self.overrides_at = time.monotonic()
            log(f"VOICE_SET {event} = '{self.overrides[event]}' "
                "(until the end of this print)")
        elif cmd == "reset":
            self.overrides.clear()
            log("VOICE_SET overrides cleared")
        elif cmd == "speed":
            self.set_speed(parts[1] if len(parts) > 1 else "")
        elif cmd == "volume":
            self.set_volume(parts[1] if len(parts) > 1 else "")
        else:
            log(f"Unknown VOICE_CTL: '{text}'")

    def set_speed(self, value):
        """VOICE_SPEED: no value reports it; a value applies it now, saves
        it (Voice_Settings.cfg, else the conf) and speaks the test phrase."""
        if not value:
            self.console(f"Voice speed: {self.length_scale:g}"
                         " - 1.0 normal, higher = slower")
            return
        try:
            speed = float(value)
        except ValueError:
            self.console(f"VOICE_SPEED: invalid value '{value}'")
            return
        self.length_scale = round(min(SPEED_MAX, max(SPEED_MIN, speed)), 2)
        where = self.persist("speed", f"{self.length_scale:g}",
                             "voice", "length_scale")
        self.console(f"Voice speed: {self.length_scale:g} ({where})")
        self.request(self.test_items())

    def set_volume(self, value):
        """VOICE_VOLUME: like set_speed, for the volume (0..100)."""
        if not value:
            self.console(f"Voice volume: {self.volume} (0..100)")
            return
        try:
            volume = round(float(value))
        except ValueError:
            self.console(f"VOICE_VOLUME: invalid value '{value}'")
            return
        self.volume = min(100, max(0, volume))
        where = self.persist("volume", str(self.volume), "voice", "volume")
        self.console(f"Voice volume: {self.volume} ({where})")
        self.request(self.test_items())

    def apply_settings(self, values):
        """volume / speed from [gcode_macro _VOICE_SETTINGS]."""
        try:
            if "volume" in values:
                self.volume = min(100, max(0, round(float(values["volume"]))))
            if "speed" in values:
                self.length_scale = min(SPEED_MAX, max(
                    SPEED_MIN, float(values["speed"])))
        except (TypeError, ValueError) as e:
            log(f"Voice_Settings.cfg: invalid volume/speed ({e})")

    def persist(self, var, value, section, key):
        """Saves a VOICE_VOLUME / VOICE_SPEED value where it lives:
        Voice_Settings.cfg (also updated in Klipper's memory), or the conf
        on installs without it. Returns where, for the console."""
        if self.klipper_settings:
            self.klipper_script(f"SET_GCODE_VARIABLE MACRO=_VOICE_SETTINGS "
                                f"VARIABLE={var} VALUE={value}")
            if self.save_variable(var, value):
                return "saved in Voice_Settings.cfg"
            return "not saved: variable_%s missing in Voice_Settings.cfg" % var
        if self.save_option(section, key, value):
            return "saved in klipper-voice.conf"
        return "not saved"

    def save_variable(self, var, value):
        """Rewrites "variable_<var>: ..." inside [gcode_macro _VOICE_SETTINGS]
        of Voice_Settings.cfg, keeping any comment after the value."""
        try:
            with open(self.settings_file, encoding="utf-8") as f:
                lines = f.readlines()
            current = None
            for i, line in enumerate(lines):
                head = re.match(r"\s*\[([^\]]+)\]", line)
                if head:
                    current = head.group(1).strip()
                    continue
                m = re.match(rf"(\s*variable_{var}\s*:\s*)\S+(.*)", line)
                if current == SETTINGS and m:
                    lines[i] = f"{m.group(1)}{value}{m.group(2)}\n"
                    break
            else:
                return False
            with open(self.settings_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except OSError as e:
            log(f"Could not save {var} to {self.settings_file}: {e}")
            return False

    def test_items(self):
        """VOICE_TEST phrase: "test", else "startup", else a fixed one."""
        return (items_of(self.text("test", "general"))
                or items_of(self.text("startup", "general"))
                or ["Voice test"])

    def text(self, name, section):
        """A phrase: Voice_Messages.cfg first, then the conf file."""
        if name in self.messages:
            return str(self.messages[name])
        return self.cp.get(section, name, fallback="")

    def say_startup(self):
        if self.startup_pending:
            self.startup_pending = False
            self.request(items_of(self.text("startup", "general")))

    async def startup_fallback(self):
        """Klipper not ready in time: speak the startup phrase anyway."""
        await asyncio.sleep(STARTUP_WAIT)
        self.say_startup()

    def save_option(self, section, key, value):
        """Rewrites "key = ..." inside [section] of the config file, keeping
        everything else (comments included); adds the line right after
        [section] if the key is not there yet. Returns True if saved."""
        if not self.conf_file:
            return False
        try:
            with open(self.conf_file, encoding="utf-8") as f:
                lines = f.readlines()
            current, header = None, None
            for i, line in enumerate(lines):
                head = re.match(r"\s*\[([^\]]+)\]", line)
                if head:
                    current = head.group(1).strip()
                    if current == section:
                        header = i
                elif current == section and re.match(
                        rf"\s*{re.escape(key)}\s*[=:]", line):
                    lines[i] = f"{key} = {value}\n"
                    break
            else:
                if header is None:
                    return False
                lines.insert(header + 1, f"{key} = {value}\n")
            with open(self.conf_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except OSError as e:
            log(f"Could not save {key} to {self.conf_file}: {e}")
            return False

    def console(self, text):
        """Shows a line in the Klipper console (Mainsail/Fluidd)."""
        log(text)
        self.klipper_script("RESPOND MSG=\"%s\"" % text.replace('"', "'"))

    def klipper_script(self, script):
        if self.ws:
            asyncio.create_task(self.send_quiet(
                "printer.gcode.script", {"script": script}))

    async def send_quiet(self, method, params):
        try:
            await self.send(method, params)
        except websockets.exceptions.WebSocketException:
            pass

    # --------------------------------------------------------- events
    def phrase(self, name):
        if name in self.overrides:
            return self.overrides[name]
        return self.text(name, "events")

    def event(self, name, extra=None, **fmt):
        if self.held is not None and name in HELD_EVENTS:
            self.held.append((name, extra, fmt))     # spoken after "start"
            return []
        is_error = name in ERROR_EVENTS
        text = self.phrase(name)
        if fmt:
            for k, v in fmt.items():
                # {p} in the config file, %p from the slicer (where {}
                # is taken by the slicer's own placeholders)
                text = text.replace("{" + k + "}", str(v)).replace(
                    "%" + k, str(v))
        items = items_of(text)
        if extra and self.cp.getboolean("events", "say_error_message"):
            items.append(extra)
        if items:
            log(f"Event: {name}")
            self.request(items, is_error)
        return items

    def end_of_print(self, name):
        self.stop_repeat()
        if name != "error" or \
                time.monotonic() - self.last_shutdown > SHUTDOWN_WINDOW:
            self.event(name)
        self.overrides.clear()                       # VOICE_SET is per print

    async def _start(self):
        """The "start" event waits start_delay seconds, so VOICE_SET lines
        from the slicer's start G-code arrive first. Heater and progress events in
        the meantime are held and spoken after it."""
        await asyncio.sleep(self.start_delay)
        held, self.held, self.start_task = self.held or [], None, None
        self.event("start")
        for name, extra, fmt in held:
            self.event(name, extra, **fmt)

    def cancel_start(self):
        if self.start_task:
            self.start_task.cancel()
            self.start_task = None
        self.held = None

    def transition(self, new):
        old, self.print_state = self.print_state, new
        if old is None or old == new:
            return
        if new != "printing":
            self.cancel_start()
        if new == "printing":
            self.stop_repeat()
            if old == "paused":
                self.event("resumed")
            else:
                self.last_progress = 0.0
                if time.monotonic() - self.overrides_at > OVERRIDE_GRACE:
                    self.overrides.clear()           # left from outside a print
                self.cancel_start()
                if self.start_delay > 0:
                    self.held = []
                    self.start_task = asyncio.create_task(self._start())
                else:
                    self.event("start")
        elif new == "paused":
            items = self.event("paused")
            if self.pause_repeat > 0:
                self.start_repeat(self.pause_repeat, items, first_now=False)
        elif new in ("complete", "cancelled", "error"):
            self.end_of_print(new)

    def progress(self, value):
        """value 0..1 from display_status (follows M73 from the slicer)."""
        if self.print_state != "printing" or self.progress_step <= 0:
            return
        pct = value * 100.0
        step = int(pct // self.progress_step) * self.progress_step
        if step > self.last_progress and step < 100:
            self.last_progress = step
            self.event("progress", p=int(step) if step == int(step) else step)

    def heater(self, name, changes, announce=True):
        h = self.heaters[name]
        old_target = h["target"]
        h.update({k: float(v) for k, v in changes.items()
                  if k in ("target", "temperature")})
        prefix = HEATERS[name]
        if h["target"] <= 0:
            h["heating"] = False
            return
        if h["target"] != old_target:
            if h["target"] - h["temperature"] >= self.heat_delta:
                h["heating"] = True
                if announce:
                    self.event(prefix + "_heating")
            elif h["temperature"] >= h["target"] - self.hot_margin:
                h["heating"] = False
        if h["heating"] and h["temperature"] >= h["target"] - self.hot_margin:
            h["heating"] = False
            if announce:
                self.event(prefix + "_hot")

    def shutdown(self, message=None):
        now = time.monotonic()
        if now - self.last_shutdown < 15:
            return
        self.last_shutdown = now
        self.stop_repeat()
        self.event("shutdown", extra=message)

    # ------------------------------------------------------ moonraker
    async def send(self, method, params=None):
        rid = self.next_id
        self.next_id += 1
        await self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid,
                                       "method": method,
                                       "params": params or {}}))
        return rid

    async def subscribe(self):
        objects = {"print_stats": ["state"],
                   "display_status": ["progress"],
                   "webhooks": ["state", "state_message"]}
        for h in HEATERS:
            objects[h] = ["target", "temperature"]
        objects[MESSAGES] = None                     # all its variables
        objects[SETTINGS] = None
        try:
            rid = await self.send("printer.objects.subscribe",
                                  {"objects": objects})
            self.subscribe_ids.add(rid)
        except websockets.exceptions.WebSocketException:
            pass

    def initial_status(self, status):
        """Subscription reply: store current state without announcing."""
        self.print_state = status.get("print_stats", {}).get(
            "state", self.print_state)
        prog = status.get("display_status", {}).get("progress")
        if prog is not None and self.progress_step > 0:
            self.last_progress = int(prog * 100 // self.progress_step) \
                * self.progress_step
        for h in HEATERS:
            if h in status:
                self.heater(h, status[h], announce=False)
                hs = self.heaters[h]
                hs["heating"] = hs["target"] - hs["temperature"] > \
                    self.hot_margin and hs["target"] > 0
        # phrases as Klipper loaded them (Save & Restart applies edits)
        self.messages = dict(status.get(MESSAGES) or {})
        log(f"Phrases: {len(self.messages)} from Voice_Messages.cfg"
            if self.messages else
            "Phrases: from klipper-voice.conf (no Voice_Messages.cfg)")
        settings = status.get(SETTINGS) or {}
        self.klipper_settings = "volume" in settings or "speed" in settings
        if self.klipper_settings:
            self.apply_settings(settings)
            log(f"Volume {self.volume}, speed {self.length_scale:g} "
                "from Voice_Settings.cfg")
        self.say_startup()

    def console_line(self, line):
        if not isinstance(line, str):
            return
        if line.startswith(PREFIX_SAY):
            text = line[len(PREFIX_SAY):].strip()
            if text:
                log("SAY:", text)
                self.request(items_of(text))
        elif line.startswith(PREFIX_SOUND):
            name = line[len(PREFIX_SOUND):].strip()
            if name:
                log("SOUND:", name)
                self.request(["sound:" + name])
        elif line.startswith(PREFIX_CTL):
            self.control(line[len(PREFIX_CTL):].strip())

    def handle(self, msg):
        if msg.get("id") in self.subscribe_ids:
            self.subscribe_ids.discard(msg["id"])
            status = (msg.get("result") or {}).get("status")
            if status:
                self.initial_status(status)
            return
        method = msg.get("method")
        params = msg.get("params") or []
        if method == "notify_gcode_response":
            for line in params:
                self.console_line(line)
        elif method == "notify_status_update" and params:
            changes = params[0]
            # shutdown first: the print "error" in the same update is then
            # recognised as part of it and not spoken twice
            wh = changes.get("webhooks", {})
            if wh.get("state") in ("shutdown", "error"):
                self.shutdown(wh.get("state_message"))
            state = changes.get("print_stats", {}).get("state")
            if state:
                self.transition(state)
            for h in HEATERS:
                if h in changes:
                    self.heater(h, changes[h])
            prog = changes.get("display_status", {}).get("progress")
            if prog is not None:
                self.progress(prog)
            if MESSAGES in changes:                  # SET_GCODE_VARIABLE
                self.messages.update(changes[MESSAGES])
            if SETTINGS in changes:
                self.apply_settings(changes[SETTINGS])
        elif method == "notify_klippy_ready":
            asyncio.create_task(self.subscribe())
        elif method == "notify_klippy_shutdown":
            self.shutdown()
        elif method == "notify_klippy_disconnected":
            self.cancel_start()
            self.print_state = None

    async def listen(self):
        url = self.cp.get("general", "moonraker").strip()
        delay = 2
        while True:
            try:
                async with websockets.connect(url, ping_interval=20,
                                              max_size=None) as ws:
                    self.ws = ws
                    delay = 2
                    await self.send("server.connection.identify", {
                        "client_name": "Klipper-Voice", "version": VERSION,
                        "type": "other",
                        "url": "https://github.com/3devangelist/Klipper-Voice"})
                    await self.subscribe()
                    log("Connected to Moonraker")
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except ValueError:
                            continue
                        self.handle(msg)
            except (OSError, websockets.exceptions.WebSocketException) as e:
                log(f"No connection to Moonraker ({e}); retrying in {delay} s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def run(self):
        if self.engine == "piper":
            self.load_piper()
        asyncio.create_task(self.speaker())
        # the startup phrase is spoken once Klipper's phrases are known
        asyncio.create_task(self.startup_fallback())
        await self.listen()


def main():
    conf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONF
    try:
        asyncio.run(KlipperVoice(conf).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
