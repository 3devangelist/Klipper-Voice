#!/usr/bin/env python3
"""
render_config.py - builds the user config files for one language.

    render_config.py list                       -> "code<TAB>name<TAB>voice" per language
    render_config.py get <lang> <field>         -> prints one field (voice, espeak...)
    render_config.py render <lang> <template> <output>

Languages live in languages/<code>.json. To add a language, copy en.json,
translate the phrases and pick a voice from
https://huggingface.co/rhasspy/piper-voices
"""

import json
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_DIR = os.path.join(ROOT, "languages")


def load(code):
    with open(os.path.join(LANG_DIR, code + ".json"), encoding="utf-8") as f:
        return json.load(f)


def values(d):
    v = {
        "NAME": d["name"], "VOICE": d["voice"], "ESPEAK": d["espeak"],
        "LENGTH_SCALE": str(d["length_scale"]), "STARTUP": d["startup"],
        "TEST": d["test"],
        # the voice service's speaking-state file (install.sh sets it)
        "BUSY_FILE": os.environ.get("KV_BUSY_FILE", os.path.expanduser(
            "~/printer_data/comms/klipper-voice-busy")),
        "NEXT_STEPS": d["next_steps"],
    }
    for k, t in d["events"].items():
        v["EV_" + k.upper()] = t
    for k, t in d["leveling"].items():
        v["LV_" + k.upper()] = t
    for i, t in enumerate(d["screw_names"], 1):
        v[f"SCREW{i}"] = t
    return v


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        codes = sorted(f[:-5] for f in os.listdir(LANG_DIR)
                       if f.endswith(".json"))
        # English first, then alphabetical
        codes.sort(key=lambda c: (c != "en", c))
        for c in codes:
            d = load(c)
            print(f"{c}\t{d['name']}\t{d['voice']}")
    elif cmd == "get" and len(sys.argv) == 4:
        print(load(sys.argv[2])[sys.argv[3]])
    elif cmd == "render" and len(sys.argv) == 5:
        v = values(load(sys.argv[2]))
        with open(sys.argv[3], encoding="utf-8") as f:
            text = f.read()
        for k, t in v.items():
            text = text.replace("@" + k + "@", t)
        missing = sorted(set(re.findall(r"@([A-Z0-9_]+)@", text)))
        if missing:
            sys.exit(f"Missing translations: {', '.join(missing)}")
        with open(sys.argv[4], "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
