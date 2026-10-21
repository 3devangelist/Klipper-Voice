#!/usr/bin/env python3
"""
Tests for klipper_voice.py, without Klipper, Moonraker or a speaker.

Moonraker messages are fed straight into handle() and every phrase that
would be spoken is collected in a list. Run:  python3 tests/test_klipper_voice.py
"""

import asyncio
import os
import sys
import tempfile
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "klipper_voice"))
# no websockets needed: the tests never connect
sys.modules["websockets"] = types.SimpleNamespace(
    exceptions=types.SimpleNamespace(WebSocketException=Exception))
os.getuid = getattr(os, "getuid", lambda: 0)          # Windows

import klipper_voice as kv                            # noqa: E402

spoken = []


def make():
    """A service with default phrases that collects what it would say."""
    v = kv.KlipperVoice(os.path.join(tempfile.mkdtemp(), "none.conf"))
    v.engine = "text"
    v.request = lambda items, is_error=False: spoken.append(" | ".join(items))
    v.start_delay = 0.3
    return v


def listen(v):
    v.request = lambda items, is_error=False: spoken.append(" | ".join(items))
    return v


def upd(v, **changes):
    v.handle({"method": "notify_status_update", "params": [changes]})


def line(v, text):
    v.handle({"method": "notify_gcode_response", "params": [text]})


def check(name, got, expected):
    assert got == expected, f"{name}: got {got!r}, expected {expected!r}"
    print(f"ok  {name}")


async def test_print_events():
    # VOICE_SET start after the state change still silences "start";
    # bed heating during the start delay is spoken after it
    v = make(); v.print_state = "standby"
    upd(v, print_stats={"state": "printing"})
    line(v, "VOICE_CTL: set start")
    line(v, "VOICE_CTL: set complete Bracket ready")
    upd(v, heater_bed={"target": 60, "temperature": 20})
    await asyncio.sleep(0.5)
    check("VOICE_SET silences start", spoken, ["Bed heating"])
    spoken.clear()
    upd(v, print_stats={"state": "complete"})
    check("VOICE_SET phrase for complete", spoken, ["Bracket ready"])
    spoken.clear()

    # heating held during the start delay, spoken after "start"
    v = make(); v.print_state = "standby"
    upd(v, print_stats={"state": "printing"})
    upd(v, heater_bed={"target": 60, "temperature": 20})
    check("nothing during start delay", spoken, [])
    await asyncio.sleep(0.5)
    check("start, then heating", spoken, ["Print started", "Bed heating"])
    spoken.clear()

    # a VOICE_SET typed outside a print is dropped at the next start
    v = make(); v.print_state = "standby"
    line(v, "VOICE_CTL: set start Old phrase")
    v.overrides_at -= 60
    upd(v, print_stats={"state": "printing"})
    await asyncio.sleep(0.5)
    check("stale VOICE_SET dropped", spoken, ["Print started"])
    spoken.clear()

    # shutdown mid-print: only the shutdown phrase, not error + shutdown
    upd(v, webhooks={"state": "shutdown", "state_message": "MCU lost"},
        print_stats={"state": "error"})
    check("shutdown spoken once", spoken,
          ["sound:pause | Warning, Klipper has stopped"])
    spoken.clear()

    v = make(); v.print_state = "printing"
    upd(v, print_stats={"state": "error"})
    check("print error", spoken, ["sound:pause | Print error"])
    spoken.clear()

    # cancelled during the start delay: no start phrase afterwards
    v = make(); v.print_state = "standby"
    upd(v, print_stats={"state": "printing"})
    upd(v, print_stats={"state": "cancelled"})
    await asyncio.sleep(0.5)
    check("cancel during start delay", spoken, ["Print cancelled"])
    spoken.clear()


def test_speed_and_volume_in_conf():
    conf = os.path.join(tempfile.mkdtemp(), "kv.conf")
    with open(conf, "w", encoding="utf-8") as f:
        f.write("[general]\nstartup = Voz pronta\n\n[voice]\n# 1.0 = normal\n"
                "length_scale = 1.4\nengine = text\n\n[other]\nlength_scale = 9\n")
    v = listen(kv.KlipperVoice(conf))
    line(v, "VOICE_CTL: speed 1.7")
    check("VOICE_SPEED applied", (v.length_scale, spoken), (1.7, ["Voz pronta"]))
    txt = open(conf, encoding="utf-8").read()
    check("VOICE_SPEED saved, comments kept",
          ("length_scale = 1.7\n" in txt, "length_scale = 9" in txt,
           "# 1.0 = normal" in txt), (True, True, True))
    line(v, "VOICE_CTL: speed 10")
    check("VOICE_SPEED clamped", v.length_scale, 3.0)
    line(v, "VOICE_CTL: speed abc")
    check("VOICE_SPEED invalid ignored", v.length_scale, 3.0)
    line(v, "VOICE_CTL: speed")
    w = make(); w.length_scale = 2.4
    wpm, ls = w.espeak_base
    check("espeak speed follows", round(wpm * ls / w.length_scale), 82)

    spoken.clear()
    v = listen(kv.KlipperVoice(conf))
    check("default volume", (v.volume, v.vol()), (100, ["vol", "1.00"]))
    line(v, "VOICE_CTL: volume 60")
    check("VOICE_VOLUME applied", (v.volume, v.vol()), (60, ["vol", "0.60"]))
    check("VOICE_VOLUME line added",
          "[voice]\nvolume = 60\n" in open(conf, encoding="utf-8").read(), True)
    line(v, "VOICE_CTL: volume 70")
    txt = open(conf, encoding="utf-8").read()
    check("VOICE_VOLUME line replaced",
          (txt.count("volume = "), "volume = 70" in txt), (1, True))
    line(v, "VOICE_CTL: volume 150"); check("volume max", v.volume, 100)
    line(v, "VOICE_CTL: volume -5"); check("volume min", v.volume, 0)
    line(v, "VOICE_CTL: volume x"); check("volume invalid", v.volume, 0)
    check("volume reloaded", kv.KlipperVoice(conf).volume, 0)

    out = conf + ".out"
    v.pipe([sys.executable, "-c", "print('abc')"],
           [sys.executable, "-c",
            "import sys; sys.stdout.write(sys.stdin.read().upper())"],
           [sys.executable, "-c",
            "import sys; open(sys.argv[1], 'w').write(sys.stdin.read())", out])
    check("three-command pipe", open(out).read().strip(), "ABC")


def test_intro_call():
    v = make(); v.chime = "introcall"; v.chime_gap = 10
    check("intro call added", v.with_chime(["Hello"]),
          ["sound:introcall", "Hello"])
    check("not before an own sound", v.with_chime(["sound:done", "Done"]),
          ["sound:done", "Done"])
    v.last_spoken = time.monotonic() - 4                # bed leveling
    check("not within the gap", v.with_chime(["Aperta 45 graus"]),
          ["Aperta 45 graus"])
    v.last_spoken = time.monotonic() - 30
    check("again after the gap", v.with_chime(["Hello"])[0], "sound:introcall")
    v.chime = ""
    check("off", v.with_chime(["Hello"]), ["Hello"])


def test_voice_messages():
    spoken.clear()
    v = make(); v.print_state = "printing"
    v.initial_status({"print_stats": {"state": "printing"},
                      kv.MESSAGES: {"startup": "Ola", "test": "Teste",
                                    "complete": "Peca pronta", "cancelled": ""}})
    check("startup from Voice_Messages.cfg", spoken, ["Ola"])
    v.initial_status({kv.MESSAGES: {"startup": "Ola"}})
    check("startup only once", spoken, ["Ola"])
    spoken.clear()
    v.initial_status({kv.MESSAGES: {"complete": "Peca pronta", "cancelled": "",
                                    "test": "Teste"}})
    v.print_state = "printing"
    upd(v, print_stats={"state": "complete"})
    check("event phrase from Voice_Messages.cfg", spoken, ["Peca pronta"])
    v.print_state = "printing"; spoken.clear()
    upd(v, print_stats={"state": "cancelled"})
    check('"" is silent', spoken, [])
    line(v, "VOICE_CTL: test")
    check("VOICE_TEST", spoken, ["Teste"])
    spoken.clear()
    upd(v, **{kv.MESSAGES: {"test": "Novo teste"}})
    line(v, "VOICE_CTL: test")
    check("SET_GCODE_VARIABLE followed", spoken, ["Novo teste"])
    spoken.clear()
    v.print_state = "printing"
    upd(v, print_stats={"state": "error"})
    check("missing phrase falls back to the conf", spoken,
          ["sound:pause | Print error"])
    spoken.clear()


def test_voice_settings():
    d = tempfile.mkdtemp()
    conf = os.path.join(d, "klipper-voice.conf")
    open(conf, "w", encoding="utf-8").write("[voice]\nengine = text\n")
    sfile = os.path.join(d, "Voice_Settings.cfg")
    open(sfile, "w", encoding="utf-8").write(
        "[gcode_macro _VOICE_SETTINGS]\n# Volume\nvariable_volume: 100\n"
        "variable_speed: 1.4    # slower\ngcode:\n\n"
        "[gcode_macro _BLV_CONFIG]\nvariable_speed_xy: 6000\n"
        "variable_volume: 5\ngcode:\n")
    v = kv.KlipperVoice(conf)
    v.request = lambda items, is_error=False: None
    check("settings file found", v.settings_file, sfile)
    v.initial_status({kv.SETTINGS: {"volume": 80, "speed": 1.75}})
    check("volume/speed from Klipper",
          (v.klipper_settings, v.volume, v.length_scale), (True, 80, 1.75))
    line(v, "VOICE_CTL: volume 60")
    line(v, "VOICE_CTL: speed 1.5")
    txt = open(sfile, encoding="utf-8").read()
    check("saved in Voice_Settings.cfg, comment kept",
          ("variable_volume: 60\n" in txt,
           "variable_speed: 1.5    # slower\n" in txt), (True, True))
    check("other sections untouched",
          ("variable_volume: 5\n" in txt, "variable_speed_xy: 6000" in txt),
          (True, True))
    check("conf untouched",
          "volume" in open(conf, encoding="utf-8").read(), False)
    upd(v, **{kv.SETTINGS: {"volume": 30}})
    check("SET_GCODE_VARIABLE followed", v.volume, 30)
    v.initial_status({})
    check("no _VOICE_SETTINGS", v.klipper_settings, False)
    line(v, "VOICE_CTL: volume 40")
    check("then saved in the conf",
          "volume = 40" in open(conf, encoding="utf-8").read(), True)


def test_sound_folders():
    sd = tempfile.mkdtemp()
    for folder, files in {"pause": ["beep.mp3"],
                          "done": ["a.wav", "b.ogg", "notes.txt"],
                          "introcall": []}.items():
        os.makedirs(os.path.join(sd, folder))
        for f in files:
            open(os.path.join(sd, folder, f), "w").close()
    open(os.path.join(sd, "solo.mp3"), "w").close()
    v = make(); v.sound_dir = sd
    check("any name in the folder", v.find_sound("pause").endswith("beep.mp3"),
          True)
    picks = {os.path.basename(v.find_sound("done")) for _ in range(60)}
    check("random pick, audio only", picks, {"a.wav", "b.ogg"})
    check("done.wav -> done/",
          os.path.dirname(v.find_sound("done.wav")), os.path.join(sd, "done"))
    check("alert.wav -> pause/", v.find_sound("alert.wav").endswith("beep.mp3"),
          True)
    check("error -> pause/", v.find_sound("error").endswith("beep.mp3"), True)
    check("plain file", v.find_sound("solo.mp3").endswith("solo.mp3"), True)
    check("empty folder", v.find_sound("introcall"), None)
    check("chime.wav -> introcall/", v.find_sound("chime.wav"), None)
    check("missing", v.find_sound("nothing"), None)


def main():
    asyncio.run(test_print_events())
    test_speed_and_volume_in_conf()
    test_intro_call()
    test_voice_messages()
    test_voice_settings()
    test_sound_folders()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
