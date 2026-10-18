#!/usr/bin/env python3
"""
klipper_voice.py - makes the Klipper host speak (Klipper-Voice)

Connects to Moonraker and:
  - speaks console lines starting with "SAY:"          (SAY macro)
  - plays sounds from lines starting with "SOUND:"     (PLAY_SOUND macro)
  - obeys "VOICE_CTL:" off | on | stop | test | repeat <sec> <text>
  - announces print events on its own (start, complete, pause, resume,
    cancel, error) and Klipper shutdowns - no macro changes needed

All settings live in ~/printer_data/config/klipper-voice.conf (editable
from Mainsail/Fluidd). After editing, restart the "klipper-voice" service.

Rules:
  - every request is spoken to the end (never cut mid-sentence);
  - if several requests arrive while speaking, only the most recent one
    is spoken next (older ones are stale);
  - the piper voice is loaded once at startup, so speech starts quickly.

Usage: klipper_voice.py [path/to/klipper-voice.conf]
"""

import asyncio
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

VERSION = "1.0.0"
DEFAULT_CONF = "~/printer_data/config/klipper-voice.conf"

DEFAULTS = {
    "general": {
        "moonraker": "ws://127.0.0.1:7125/websocket",
        "startup": "Voice ready",
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
        "start": "",
        "complete": "sound:done.wav | Print complete",
        "cancelled": "Print cancelled",
        "paused": "sound:alert.wav | Print paused",
        "resumed": "Resuming print",
        "error": "sound:error.wav | Print error",
        "shutdown": "sound:error.wav | Warning, Klipper has stopped",
        "say_error_message": "no",
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

        self.synthesize = None
        self.pending = None               # (items, is_error), most recent
        self.has_request = asyncio.Event()
        self.muted = False
        self.repeater = None              # SAY_REPEAT task
        self.print_state = None
        self.last_shutdown = 0.0
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
            self.has_request.clear()
            request, self.pending = self.pending, None
            if not request:
                continue
            items, is_error = request
            for item in items:
                if not self.allowed(is_error):
                    break
                try:
                    await loop.run_in_executor(None, self.play_item, item)
                except Exception as e:               # noqa: BLE001
                    log(f"Error playing '{item}': {e}")

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
        self.pending = (items, is_error)
        self.has_request.set()

    # --------------------------------------------------------- repeat
    def stop_repeat(self):
        if self.repeater:
            self.repeater.cancel()
            self.repeater = None

    async def _repeat(self, seconds, items):
        while True:
            self.request(items)
            await asyncio.sleep(seconds)

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
                seconds = max(5.0, float(parts[1]))
            except ValueError:
                log(f"VOICE_CTL repeat: invalid interval '{parts[1]}'")
                return
            self.stop_repeat()
            self.repeater = asyncio.create_task(
                self._repeat(seconds, items_of(parts[2])))
        else:
            log(f"Unknown VOICE_CTL: '{text}'")

    # --------------------------------------------------------- events
    def event(self, name, is_error=False, extra=None):
        items = items_of(self.cp.get("events", name, fallback=""))
        if extra and self.cp.getboolean("events", "say_error_message"):
            items.append(extra)
        if items:
            log(f"Event: {name}")
            self.request(items, is_error)

    def transition(self, new):
        old, self.print_state = self.print_state, new
        if old is None or old == new:
            return
        if new == "printing":
            self.stop_repeat()
            self.event("resumed" if old == "paused" else "start")
        elif new == "paused":
            self.event("paused")
        elif new == "complete":
            self.stop_repeat()
            self.event("complete")
        elif new == "cancelled":
            self.stop_repeat()
            self.event("cancelled")
        elif new == "error":
            self.stop_repeat()
            self.event("error", is_error=True)

    def shutdown(self, message=None):
        now = time.monotonic()
        if now - self.last_shutdown < 15:
            return
        self.last_shutdown = now
        self.stop_repeat()
        self.event("shutdown", is_error=True, extra=message)

    # ------------------------------------------------------ moonraker
    async def send(self, method, params=None):
        rid = self.next_id
        self.next_id += 1
        await self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid,
                                       "method": method,
                                       "params": params or {}}))
        return rid

    async def subscribe(self):
        try:
            rid = await self.send("printer.objects.subscribe", {
                "objects": {"print_stats": ["state"],
                            "webhooks": ["state", "state_message"]}})
            self.subscribe_ids.add(rid)
        except websockets.exceptions.WebSocketException:
            pass

    def initial_status(self, status):
        """Subscription reply: store current state without announcing."""
        self.print_state = status.get("print_stats", {}).get(
            "state", self.print_state)

    def console_line(self, line):
        if not isinstance(line, str):
            return
        if line.startswith(PREFIX_SAY):
            text = line[len(PREFIX_SAY):].strip()
            if text:
                log("SAY:", text)
                self.request([text])
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
            state = changes.get("print_stats", {}).get("state")
            if state:
                self.transition(state)
            wh = changes.get("webhooks", {})
            if wh.get("state") in ("shutdown", "error"):
                self.shutdown(wh.get("state_message"))
        elif method == "notify_klippy_ready":
            asyncio.create_task(self.subscribe())
        elif method == "notify_klippy_shutdown":
            self.shutdown()
        elif method == "notify_klippy_disconnected":
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
