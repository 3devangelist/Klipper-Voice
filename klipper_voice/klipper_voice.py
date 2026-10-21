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
                       | set <event> <text> | reset
    ("set" lets the slicer's start G-code give any event its own phrase
     for the current print)

All settings live in ~/printer_data/config/klipper-voice.conf (editable
from Mainsail/Fluidd). After editing, restart the "klipper-voice" service.

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
import shlex
import subprocess
import sys
import time
import wave

import websockets

VERSION = "1.2.0"
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

DEFAULTS = {
    "general": {
        "moonraker": "ws://127.0.0.1:7125/websocket",
        "startup": "Voice ready",
        "queue": "3",
    },
    "voice": {
        "engine": "piper",                      # piper | espeak | text
        "model": "~/klipper-voice-voices/voice.onnx",
        "length_scale": "1.2",
        "effects": ("highpass 250 compand 0.05,0.2 "
                    "6:-70,-60,-30,-15,-15,-6,0,-3 -3 -90 0.1 gain -n -1"),
        "espeak": "espeak-ng -v en -s 165 -a 140",
        "device": "",
    },
    "sounds": {
        "folder": "~/printer_data/config/voice_sounds",
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
        "paused": "sound:alert.wav | Printer paused for filament reload or colour change",
        "paused_repeat_minutes": "5",
        "resumed": "Resuming print",
        "complete": "sound:done.wav | Print complete",
        "cancelled": "Print cancelled",
        "error": "sound:error.wav | Print error",
        "shutdown": "sound:error.wav | Warning, Klipper has stopped",
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
    """'sound:done.wav | Print complete' -> ['sound:done.wav', 'Print complete']"""
    return [i.strip() for i in (value or "").split("|") if i.strip()]


def clock(txt):
    h, m = txt.strip().split(":")
    return datetime.time(int(h), int(m))


class KlipperVoice:
    def __init__(self, conf_file):
        self.cp = configparser.ConfigParser(interpolation=None)
        self.cp.read_dict(DEFAULTS)
        found = self.cp.read(expand(conf_file), encoding="utf-8")
        log(f"Klipper-Voice v{VERSION}; config: "
            f"{found[0] if found else 'none (using defaults)'}")

        self.engine = self.cp.get("voice", "engine").strip().lower()
        self.device = self.cp.get("voice", "device").strip()
        self.effects = self.cp.get("voice", "effects").split()
        self.sound_dir = expand(self.cp.get("sounds", "folder"))
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
            cfg = SynthesisConfig(
                length_scale=self.cp.getfloat("voice", "length_scale"))

            def _synthesize(text):
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

    def pipe(self, source, sink):
        """source | sink, waiting for both to finish."""
        p1 = subprocess.Popen(source, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(sink, stdin=p1.stdout,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        p1.stdout.close()
        p2.wait()
        p1.wait()

    def play_item(self, item):
        """Runs in a worker thread: plays a sound or speaks a text."""
        if item.lower().startswith("sound:"):
            name = item[6:].strip()
            path = name if os.path.isabs(name) else os.path.join(
                self.sound_dir, name)
            if not os.path.isfile(path):
                log(f"Sound not found: {path}")
                return
            if self.engine == "text":
                log(f"[sound] {path}")
                return
            self.pipe(["sox", "-q", path, "-t", "wav", "-"], self.aplay())
            return

        if self.engine == "text":
            log(f"[say] {item}")
        elif self.engine == "piper":
            self.synthesize(item)
            self.pipe(["sox", "-q", self.wav, "-t", "wav", "-"]
                      + self.effects, self.aplay())
        else:
            self.pipe(shlex.split(self.cp.get("voice", "espeak"))
                      + ["--stdout", item], self.aplay())

    async def speaker(self):
        loop = asyncio.get_running_loop()
        while True:
            await self.has_request.wait()
            while self.queue:
                items, is_error = self.queue.popleft()
                for item in items:
                    if not self.allowed(is_error):
                        break
                    try:
                        await loop.run_in_executor(None, self.play_item, item)
                    except Exception as e:           # noqa: BLE001
                        log(f"Error playing '{item}': {e}")
            self.has_request.clear()

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
            self.request(items_of(self.cp.get("general", "startup"))
                         or ["Voice test"])
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
        else:
            log(f"Unknown VOICE_CTL: '{text}'")

    # --------------------------------------------------------- events
    def phrase(self, name):
        if name in self.overrides:
            return self.overrides[name]
        return self.cp.get("events", name, fallback="")

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
        startup = self.cp.get("general", "startup").strip()
        if startup:
            self.request(items_of(startup))
        await self.listen()


def main():
    conf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONF
    try:
        asyncio.run(KlipperVoice(conf).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
