#!/usr/bin/env python3
"""
Renders the user files for every language and checks them the way Klipper
reads them: every variable_* value must be a Python literal, every phrase
must be there. Run:  python3 tests/test_languages.py
"""

import ast
import configparser
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "tools", "render_config.py")
TEMPLATES = ("klipper-voice.conf", "Voice_Messages.cfg", "Voice_Settings.cfg")
# phrases in Voice_Messages.cfg: 2 service + 12 print events + 16 leveling
PHRASES = 2 + 12 + 16


def render(lang, template, dst):
    subprocess.run([sys.executable, RENDER, "render", lang,
                    os.path.join(ROOT, "templates", template + ".in"), dst],
                   check=True)


def main():
    langs = sorted(f[:-5] for f in os.listdir(os.path.join(ROOT, "languages"))
                   if f.endswith(".json"))
    keys = None
    out = tempfile.mkdtemp()
    for lang in langs:
        data = json.load(open(os.path.join(ROOT, "languages", lang + ".json"),
                              encoding="utf-8"))
        flat = sorted(list(data) + [f"events.{k}" for k in data["events"]]
                      + [f"leveling.{k}" for k in data["leveling"]])
        assert keys in (None, flat), f"{lang}: keys differ from the others"
        keys = flat
        for tpl in TEMPLATES:
            dst = os.path.join(out, f"{lang}-{tpl}")
            render(lang, tpl, dst)
            cp = configparser.RawConfigParser(
                inline_comment_prefixes=("#", ";"), strict=True)
            cp.read(dst, encoding="utf-8")
            for sec in cp.sections():
                for k, val in cp.items(sec):
                    if k.startswith("variable_"):
                        ast.literal_eval(val)          # what Klipper does
            if tpl == "Voice_Messages.cfg":
                msgs = {k[9:]: ast.literal_eval(v)
                        for k, v in cp.items("gcode_macro _VOICE_MESSAGES")
                        if k.startswith("variable_")}
                assert len(msgs) == PHRASES, f"{lang}: {len(msgs)} phrases"
                assert all(isinstance(m, str) and m for m in msgs.values()), lang
                assert not any(c in m for m in msgs.values() for c in ";#"), \
                    f"{lang}: ; or # in a phrase"
            if tpl == "Voice_Settings.cfg":
                s = cp["gcode_macro _VOICE_SETTINGS"]
                assert float(s["variable_speed"]) > 0, lang
            if tpl == "klipper-voice.conf":
                assert not cp.has_option("events", "complete"), lang
        print(f"ok  {lang}")
    print(f"ALL {len(langs)} LANGUAGES OK")


if __name__ == "__main__":
    main()
