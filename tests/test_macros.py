#!/usr/bin/env python3
"""
Renders the macros in Configuration/Voice.cfg the way Klipper does (same
Jinja2 delimiters) and checks the console lines they send to the service.
Needs jinja2 (pip install jinja2). Run:  python3 tests/test_macros.py
"""

import configparser
import os
import re

import jinja2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}")


class MacroError(Exception):
    pass


def raise_error(msg):
    raise MacroError(msg)


def load_macros():
    cp = configparser.RawConfigParser(strict=False)
    cp.read(os.path.join(ROOT, "Configuration", "Voice.cfg"), encoding="utf-8")
    return {s.split(None, 1)[1]: cp.get(s, "gcode")
            for s in cp.sections() if s.startswith("gcode_macro ")}


MACROS = load_macros()


def render(name, printer=None, **params):
    return ENV.from_string(MACROS[name]).render(
        params={k.upper(): str(v) for k, v in params.items()},
        printer=printer or {}, action_raise_error=raise_error)


def run(name, **params):
    """The RESPOND lines a macro would send, as 'PREFIX text'."""
    lines = []
    for ln in render(name, **params).splitlines():
        m = re.match(r'\s*RESPOND PREFIX="([^"]+)" MSG="(.*)"\s*$', ln)
        if m:
            lines.append(f"{m.group(1)} {m.group(2)}")
    return lines


def commands(name, printer=None, **params):
    """Every G-code line a macro would run (comments dropped)."""
    return [ln.strip() for ln in render(name, printer, **params).splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def check(name, got, expected):
    assert got == expected, f"{name}: got {got!r}, expected {expected!r}"
    print(f"ok  {name}")


def main():
    check("only the expected macros",
          sorted(MACROS), ["PLAY_SOUND", "SAY", "SAY_REPEAT", "SAY_STOP", "VOICE"])

    C = "VOICE_CTL:"
    check("VOICE alone", run("VOICE"), [f"{C} status", f"{C} test"])
    check("VOICE VOLUME", run("VOICE", volume=70), [f"{C} volume 70.0"])
    check("VOICE SPEED", run("VOICE", speed=1.6), [f"{C} speed 1.6"])
    check("VOICE VOLUME + SPEED: one sample phrase",
          run("VOICE", volume=70, speed=1.6),
          [f"{C} volume 70.0 quiet", f"{C} speed 1.6"])
    check("VOICE MUTE=1", run("VOICE", mute=1), [f"{C} off"])
    check("VOICE MUTE=0", run("VOICE", mute=0), [f"{C} on"])
    check("VOICE EVENT + MSG",
          run("VOICE", event="Complete", msg='The "bracket" is ready'),
          [f"{C} set complete The 'bracket' is ready"])
    check("VOICE EVENT without MSG = silent",
          run("VOICE", event="start"), [f"{C} set start "])
    check("VOICE RESET=1", run("VOICE", reset=1), [f"{C} reset"])
    check("VOICE RESET=0 does nothing", run("VOICE", reset=0), [])
    try:
        run("VOICE", msg="hello")
        raise AssertionError("VOICE MSG= without EVENT= should fail")
    except MacroError:
        print("ok  VOICE MSG without EVENT is an error")

    check("SAY", run("SAY", msg='Hi "there"'), ["SAY: Hi 'there'"])
    check("SAY empty", run("SAY"), [])
    check("SAY without WAIT does not wait",
          commands("SAY", msg="Ola"), ['RESPOND PREFIX="SAY:" MSG="Ola"'])
    check("SAY WAIT=1 with the _voice sensor waits exactly",
          commands("SAY", printer={"temperature_sensor _voice": {}},
                   msg="sound:introcall | Obtenção de zero", wait=1),
          ['RESPOND PREFIX="SAY:" MSG="sound:introcall | Obtenção de zero"',
           "G4 P1500",
           'TEMPERATURE_WAIT SENSOR="temperature_sensor _voice" MAXIMUM=1'])
    # without the sensor: 3.5 s + 2.5 s per sound + 0.07 s/letter * speed
    est = commands("SAY", printer={"gcode_macro _VOICE_SETTINGS": {"speed": 2.0}},
                   msg="sound:introcall | abcdefghij", wait=1)
    check("SAY WAIT=1 without the sensor: estimated dwell", est[-1], "G4 P7400")
    est = commands("SAY", msg="abcdefghij", wait=1)       # default speed 1.2
    check("SAY WAIT=1, no settings either", est[-1], "G4 P4340")
    check("PLAY_SOUND", run("PLAY_SOUND", file="done"), ["SOUND: done"])
    check("SAY_REPEAT", run("SAY_REPEAT", sec=30, msg="sound:pause | Filament"),
          [f"{C} repeat 30.0 sound:pause | Filament"])
    check("SAY_STOP", run("SAY_STOP"), [f"{C} stop"])
    print("ALL MACRO TESTS PASSED")


if __name__ == "__main__":
    main()
