"""
Makes the parts list (bill of materials) for a keyboard from its layout.

Everything is worked out from the layout JSON: the number of switches
(including the extra switches under long keys), diodes, keytops of each size,
fixing screws and their length, the PCB size, and how the Pico is mounted.
If the FreeCAD build has been run, it leaves the volume of each printed part
in output/<name>/prints.json, and the list includes how much filament each
part needs.

Run it on the PC with any Python 3:

    python common/parts_list.py layouts/cyberdeck_staggered.json

It writes output/<name>/parts_list.md (to read or share) and
output/<name>/parts_list.csv (to load into a spreadsheet for ordering). The
designer (File > Make parts list) and freecad/build_case.py also write them.
"""

import csv
import json
import os
import sys
from collections import Counter

try:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _this_dir = r"D:\GitHub\PICO-Cyberdeck-keyboard\common"
_repo_dir = os.path.dirname(_this_dir)
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

import keyboard_layout as kl

PLA_DENSITY = 1.24     # g per cubic cm

PRINTS = [
    # file, description, colour
    ("Tray.stl", "Bottom of the case. Print the right way up.", "Case colour"),
    ("Plate.stl", "Top plate. Exported upside down: print top face down.", "Case colour"),
    ("Keycaps.stl", "Keytops. Exported upside down: print top face down.", "Key colour"),
    ("KeycapLegends.stl", "Letters for the keytops. Load with Keycaps.stl as one object.", "Legend colour"),
]
MOCK_PCB = ("MockPCB.stl", "Optional: printed stand-in for the PCB, for test builds.", "Any")
GRIP_TEST = ("SwitchGripTest.stl", "Optional: finds the mock PCB fence grip that holds the switches best.", "Any")
PILLARS_ON_TOP = ("PillarsOnTop.stl", "Optional: pillars to fix the PCB on top of a plate in another case.", "Any")
PILLARS_UNDERNEATH = ("PillarsUnderneath.stl",
                      "Optional: pillars to fix the PCB under a panel cut with Cutout.stl.", "Any")


def output_dir(layout):
    return os.path.join(_repo_dir, "output", layout["name"])


def load_print_volumes(layout):
    """Volumes (cubic mm) of the printed parts, if the FreeCAD build has been run."""
    path = os.path.join(output_dir(layout), "prints.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def keytop_sizes(layout):
    """Counter of (width, height, switches) for the keytops."""
    sizes = Counter()
    for key in layout["keys"]:
        sizes[(key["w"], key["h"], len(key.get("switches") or [0]))] += 1
    return sizes


def parts_list(layout, volumes=None):
    """Returns a list of sections, each (title, rows). A row is a dict with
    qty, part, description and notes."""
    if volumes is None:
        volumes = load_print_volumes(layout)
    keys = layout["keys"]
    sw = kl.switch_info(layout)
    switches = sum(len(k.get("switches") or [0]) for k in keys)
    multi = [k for k in keys if len(k.get("switches") or [0]) > 1]
    holes = layout["board"]["mounting_holes"]
    bx, by, bw, bh = kl.board_rect(layout)
    cw, ch, cd = kl.case_size(layout)
    screw, room = kl.screw_length(layout)
    ctrl = layout["controller"]
    nrows, ncols = kl.matrix_size(layout)

    def row(qty, part, description, notes=""):
        return {"qty": qty, "part": part, "description": description, "notes": notes}

    electronics = [
        row(1, "PCB",
            "2 layer, %.1fmm thick, %.1f x %.1fmm" % (layout["board"]["thickness"], bw, bh),
            "Make Gerbers from output/%s/%s.kicad_pcb in KiCad" % (layout["name"], layout["name"])),
        row(switches, "Tactile switch",
            "C&K %s: PTS645, 6 x 6mm, surface mount (gull wing legs), %.1fmm high, %sgf" % (
                kl.switch_part_number(layout), layout["switch"]["height"], kl.switch_force_grams(layout)),
            ("%d keys x 1 switch" % (len(keys) - len(multi))) +
            ("" if not multi else ", %d long keys x %s switches" %
             (len(multi), "/".join(sorted({str(len(k["switches"])) for k in multi}))))),
    ]
    if layout["matrix"]["diodes"]:
        electronics.append(row(len(keys), "Diode", "1N4148W, SOD-123 package", "One per key"))
    if ctrl["side"] == "back":
        electronics.append(row(1, "Raspberry Pi Pico", "Pico (or Pico W)",
                               "Soldered flat to the back of the PCB by its castellations - no header pins"))
    else:
        electronics.append(row(1, "Raspberry Pi Pico", "Pico (or Pico W)", "Fitted on the front with header pins"))
        electronics.append(row(2, "Header pins", "20 way, 2.54mm pitch", "To fit the Pico"))
    electronics.append(row(1, "USB cable", "Micro USB", "Connects the keyboard to the computer"))

    hardware = []
    if holes:
        hardware.append(row(len(holes), "Screw",
                            "M2 x %smm self tapping, countersunk head" % screw,
                            "Up to %.1fmm long fits. Through the case floor and PCB into the plate" % room))

    legend = layout["case"]["legend"]
    prints = []
    for name, description, colour in PRINTS + [MOCK_PCB, GRIP_TEST, PILLARS_ON_TOP, PILLARS_UNDERNEATH]:
        if name == "KeycapLegends.stl" and legend != "inlay":
            continue
        qty = 1
        notes = colour
        volume = volumes.get(name)
        if volume:
            grams = volume / 1000 * PLA_DENSITY
            notes += ", %.1f cm3 solid (up to %s PLA)" % (volume / 1000, "%.1fg" % grams if grams < 10 else "%.0fg" % grams)
        prints.append(row(qty, name, description, notes))

    keytops = []
    for (w, h, n), count in sorted(keytop_sizes(layout).items()):
        cap_w, cap_h = kl.keycap_size(layout, {"w": w, "h": h})
        size = "%gu" % w if h == 1 else "%gu x %gu" % (w, h)
        keytops.append(row(count, "Keytop %s" % size, "%.1f x %.1fmm" % (cap_w, cap_h),
                           "%d switches" % n if n > 1 else ""))

    summary = [
        row("", "Keys", "%d keys, %d switches" % (len(keys), switches), ""),
        row("", "Case", "%.1f x %.1f x %.1fmm" % (cw, ch, cd), ""),
        row("", "Key matrix", "%d rows x %d columns, GPIO %s" %
            (nrows, ncols, ", ".join("GP%d" % p for p in layout["matrix"]["row_pins"] + layout["matrix"]["col_pins"])),
            ""),
    ]
    sections = [("Electronics", electronics), ("Hardware", hardware), ("3D printed parts", prints),
                ("Keytops (in Keycaps.stl)", keytops), ("Summary", summary)]
    return [(title, rows) for title, rows in sections if rows]


def to_markdown(layout, sections, volumes_known):
    lines = ["# Parts list: %s" % layout["name"], ""]
    lines.append("Made from the layout file by common/parts_list.py.")
    if not volumes_known:
        lines.append("Run freecad/build_case.py to add the amount of filament for each printed part.")
    lines.append("")
    for title, rows in sections:
        lines += ["## %s" % title, "", "| Qty | Part | Description | Notes |", "|---|---|---|---|"]
        for r in rows:
            lines.append("| %s | %s | %s | %s |" % (r["qty"], r["part"], r["description"], r["notes"]))
        lines.append("")
    return "\n".join(lines)


def write_parts_list(layout, out_dir=None, volumes=None):
    """Writes parts_list.md and parts_list.csv. Returns their paths."""
    out_dir = out_dir or output_dir(layout)
    os.makedirs(out_dir, exist_ok=True)
    if volumes is None:
        volumes = load_print_volumes(layout)
    sections = parts_list(layout, volumes)
    md_path = os.path.join(out_dir, "parts_list.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(layout, sections, bool(volumes)))
    csv_path = os.path.join(out_dir, "parts_list.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Section", "Qty", "Part", "Description", "Notes"])
        for title, rows in sections:
            for r in rows:
                writer.writerow([title, r["qty"], r["part"], r["description"], r["notes"]])
    return md_path, csv_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python common/parts_list.py layout.json [layout.json ...]")
        sys.exit(1)
    for path in sys.argv[1:]:
        for written in write_parts_list(kl.load(path)):
            print("Written", written)
