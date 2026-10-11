"""
Writes a KiCad schematic for a keyboard layout.

KiCad's Python API only covers the PCB editor, so this writes the .kicad_sch
file directly. build_pcb.py calls it, so the schematic goes next to the PCB
in output/<name>/, with the same file name, making them one KiCad project.

The schematic matches the PCB that build_pcb.py makes:

- every key is drawn as a cell of the key matrix, at its row and column:
  its switch (SW), and its diode (D) from the switch to the row line
- the rows and columns are joined with global labels (ROW0, COL3, ...),
  and the link between each switch and its diode is labelled K_<key id>,
  so every net has the same name as on the PCB
- the Pico (U1) has a label on each GPIO pin the matrix uses, and a no
  connect flag on every other pin
- references, values and footprints are the same as on the PCB, and each
  symbol's UUID comes from the layout name and its reference, so build_pcb.py
  can link every footprint to its symbol. Cross probing and Update PCB from
  Schematic then work, and DRC's schematic parity check passes.

The switch and diode symbols are KiCad's own (Switch:SW_Push and Device:D),
copied into the schematic. KiCad has no Raspberry Pi Pico symbol, so the
project gets its own library, Cyberdeck.kicad_sym, with one to match the
footprint.

Don't edit the schematic by hand - change the layout and build again.
"""

import datetime
import os
import re
import uuid

import keyboard_layout as kl

PAPER = ("A3", 420.0, 297.0)
CELL_W = 27.94          # matrix cell size on the sheet
CELL_H = 25.4
MATRIX_X = 33.02        # centre of the switch in the first column
MATRIX_Y = 38.1
DIODE_DX = 7.62         # diode is to the right of the switch, and below it
DIODE_DY = 7.62

_NAMESPACE = uuid.UUID("6f1d3a52-7c2b-4b8e-9d0a-5c1e2f3a4b5c")

SWITCH_LIB = ("Switch", "SW_Push")
DIODE_LIB = ("Device", "D")
SWITCH_FOOTPRINT = "Button_Switch_SMD:SW_SPST_PTS645"
DIODE_FOOTPRINT = "Diode_SMD:D_SOD-123"
PICO_LIB_NAME = "Cyberdeck"
PICO_SYMBOL = "RPi_Pico"


def symbol_uuid(layout, ref):
    """The UUID of a symbol. build_pcb.py uses this to link footprints to symbols."""
    return str(uuid.uuid5(_NAMESPACE, "%s/%s" % (layout["name"], ref)))


def pico_footprint_name(layout):
    """Soldered flat on the back it has no through holes; on the front it has
    through holes for header pins too."""
    return "RPi_Pico_SMD" if layout["controller"]["side"] == "back" else "RPi_Pico_SMD_TH"


def switch_refs(layout):
    """The references of every key's switches. The first switch of key n is
    SWn; any extra switches under long keys are numbered after the last key."""
    extra = len(layout["keys"])
    refs = []
    for n, key in enumerate(layout["keys"]):
        key_refs = ["SW%d" % (n + 1)]
        for _ in (key.get("switches") or [0])[1:]:
            extra += 1
            key_refs.append("SW%d" % extra)
        refs.append(key_refs)
    return refs


def pico_pin_names():
    names = {}
    for gpio, pin in kl.PICO_PIN_FOR_GPIO.items():
        names[pin] = "GP%d" % gpio
    for pin in kl.PICO_GND_PINS:
        names[pin] = "GND"
    names.update(kl.PICO_OTHER_PINS)
    return names


# ---------------------------------------------------------------------------
# S-expression helpers
# ---------------------------------------------------------------------------

def q(text):
    return '"%s"' % str(text).replace("\\", "\\\\").replace('"', '\\"')


def num(v):
    v = round(v, 4)
    return ("%.4f" % v).rstrip("0").rstrip(".") if v != int(v) else str(int(v))


def font(hide=False, justify=None):
    extra = ""
    if justify:
        extra += " (justify %s)" % justify
    if hide:
        extra += " (hide yes)"
    return "(effects (font (size 1.27 1.27))%s)" % extra


def new_uuid(*parts):
    return str(uuid.uuid5(_NAMESPACE, "/".join(str(p) for p in parts)))


def library_symbol(lib, name):
    """The text of a symbol from KiCad's own libraries, renamed lib:name as
    a schematic's lib_symbols needs."""
    path = os.path.join(kicad_symbol_dir(), lib + ".kicad_sym")
    text = open(path, encoding="utf-8").read()
    start = text.index('\t(symbol "%s"' % name)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                block = text[start:i + 1].strip()
                return block.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (lib, name), 1)
    raise ValueError("%s:%s not found" % (lib, name))


def library_pins(block):
    """{pin number: (x, y)} of a symbol's pins, in symbol coordinates."""
    pins = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) [-\d.]+\).*?\(number "(\w+)"', block, re.S):
        pins[m.group(3)] = (float(m.group(1)), float(m.group(2)))
    return pins


def kicad_symbol_dir():
    candidates = [os.environ.get("KICAD8_SYMBOL_DIR", ""),
                  r"C:\Program Files\KiCad\8.0\share\kicad\symbols"]
    try:
        import sys
        candidates.insert(1, os.path.join(os.path.dirname(sys.executable), "..", "share", "kicad", "symbols"))
    except Exception:
        pass
    for c in candidates:
        if c and os.path.exists(os.path.join(c, "Switch.kicad_sym")):
            return c
    raise RuntimeError("Cannot find the KiCad symbol libraries - set KICAD8_SYMBOL_DIR")


# ---------------------------------------------------------------------------
# The Pico symbol
# ---------------------------------------------------------------------------

PICO_PIN_X = 15.24       # pin ends are this far either side of the middle
PICO_BODY = 12.7


def pico_pin_position(pin):
    """Where a Pico pin's end is, in symbol coordinates (Y up). Pins 1-20
    run down the left, 21-40 up the right, as on the board."""
    if pin <= 20:
        return -PICO_PIN_X, 24.13 - (pin - 1) * 2.54
    return PICO_PIN_X, -24.13 + (pin - 21) * 2.54


def pico_symbol(name):
    names = pico_pin_names()
    types = {"GND": "power_in", "3V3": "power_out", "VBUS": "power_out", "VSYS": "power_in",
             "ADC_VREF": "power_in", "RUN": "input", "3V3_EN": "input"}
    pins = []
    for pin in range(1, 41):
        x, y = pico_pin_position(pin)
        pins.append('(pin %s line (at %s %s %d) (length 2.54) (name %s %s) (number %s %s))' % (
            types.get(names[pin], "bidirectional"), num(x), num(y), 0 if x < 0 else 180,
            q(names[pin]), font(), q(pin), font()))
    short = name.split(":")[-1]
    return "\n".join([
        '(symbol %s (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)' % q(name),
        '  (property "Reference" "U" (at 0 27.94 0) %s)' % font(),
        '  (property "Value" "Raspberry Pi Pico" (at 0 -27.94 0) %s)' % font(),
        '  (property "Footprint" "" (at 0 0 0) %s)' % font(hide=True),
        '  (property "Datasheet" "https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf" (at 0 0 0) %s)' %
        font(hide=True),
        '  (property "Description" "Raspberry Pi Pico, pins numbered as on the board" (at 0 0 0) %s)' %
        font(hide=True),
        '  (symbol %s (rectangle (start %s 26.67) (end %s -26.67) (stroke (width 0.254) (type default))'
        ' (fill (type background))))' % (q(short + "_0_1"), num(-PICO_BODY), num(PICO_BODY)),
        '  (symbol %s' % q(short + "_1_1"),
        "\n".join("    " + p for p in pins),
        "  )",
        ")",
    ])


def write_symbol_library(out_dir):
    """Cyberdeck.kicad_sym, holding the Pico symbol, and a sym-lib-table that
    makes it part of the project."""
    path = os.path.join(out_dir, PICO_LIB_NAME + ".kicad_sym")
    with open(path, "w", encoding="utf-8") as f:
        f.write('(kicad_symbol_lib (version 20231120) (generator "cyberdeck") (generator_version "8.0")\n')
        f.write(pico_symbol(PICO_SYMBOL) + "\n)\n")
    with open(os.path.join(out_dir, "sym-lib-table"), "w", encoding="utf-8") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")'
                '(options "")(descr "PICO Cyberdeck keyboard parts"))\n)\n' % (PICO_LIB_NAME, PICO_LIB_NAME))
    return path


# ---------------------------------------------------------------------------
# The schematic
# ---------------------------------------------------------------------------

class Sheet:

    def __init__(self, layout):
        self.layout = layout
        self.root = new_uuid(layout["name"], "root sheet")
        self.items = []

    def symbol(self, lib_id, ref, value, footprint, x, y, angle, pins, ref_at, value_at, hide_value=False,
               mpn=""):
        """ref_at and value_at are where the reference and value go. Their
        text is kept horizontal whichever way the symbol is turned."""
        sid = symbol_uuid(self.layout, ref)
        # a field's angle turns with its symbol, so undo the symbol's turn
        text_angle = (360 - angle) % 360 if angle in (90, 270) else 0
        justify = "left" if angle in (90, 270) else None
        pin_text = " ".join('(pin %s (uuid "%s"))' % (q(p), new_uuid(sid, p)) for p in pins)
        self.items.append(
            '(symbol (lib_id %s) (at %s %s %d) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes)'
            ' (dnp no) (uuid "%s")\n'
            '  (property "Reference" %s (at %s %s %d) %s)\n'
            '  (property "Value" %s (at %s %s %d) %s)\n'
            '  (property "Footprint" %s (at %s %s 0) %s)\n'
            '  (property "Datasheet" "~" (at %s %s 0) %s)\n'
            '  (property "MPN" %s (at %s %s 0) %s)\n'
            '  %s\n'
            '  (instances (project %s (path "/%s" (reference %s) (unit 1))))\n)' % (
                q(lib_id), num(x), num(y), angle, sid,
                q(ref), num(ref_at[0]), num(ref_at[1]), text_angle, font(justify=justify),
                q(value), num(value_at[0]), num(value_at[1]), text_angle, font(hide=hide_value, justify=justify),
                q(footprint), num(x), num(y), font(hide=True),
                num(x), num(y), font(hide=True),
                q(mpn), num(x), num(y), font(hide=True),
                pin_text, q(self.layout["name"]), self.root, q(ref)))

    def wire(self, x1, y1, x2, y2):
        self.items.append('(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid "%s"))' % (
            num(x1), num(y1), num(x2), num(y2), new_uuid("wire", x1, y1, x2, y2)))

    def label(self, name, x, y, angle):
        justify = "right" if angle in (180, 270) else "left"
        self.items.append(
            '(global_label %s (shape passive) (at %s %s %d) (fields_autoplaced yes) %s (uuid "%s")\n'
            '  (property "Intersheetrefs" "${INTERSHEET_REFS}" (at %s %s 0) %s))' % (
                q(name), num(x), num(y), angle, font(justify=justify), new_uuid("label", name, x, y),
                num(x), num(y), font(hide=True, justify=justify)))

    def no_connect(self, x, y):
        self.items.append('(no_connect (at %s %s) (uuid "%s"))' % (num(x), num(y), new_uuid("nc", x, y)))

    def text(self, text, x, y, size=1.27):
        self.items.append('(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size %s %s)) (justify left))'
                          ' (uuid "%s"))' % (q(text), num(x), num(y), num(size), num(size),
                                             new_uuid("text", text, x, y)))


def place(at, pin, angle):
    """Sheet position of a symbol pin. Symbols use Y up, the sheet Y down,
    and a symbol's angle turns it anticlockwise."""
    px, py = pin
    if angle == 90:
        px, py = -py, px
    elif angle == 180:
        px, py = -px, -py
    elif angle == 270:
        px, py = py, -px
    return at[0] + px, at[1] - py


def write_schematic(layout, out_dir):
    """Writes <name>.kicad_sch, Cyberdeck.kicad_sym and sym-lib-table to
    out_dir. Returns the schematic's path."""
    os.makedirs(out_dir, exist_ok=True)
    write_symbol_library(out_dir)
    sheet = Sheet(layout)
    switch_block = library_symbol(*SWITCH_LIB)
    diode_block = library_symbol(*DIODE_LIB)
    sw_pins = library_pins(switch_block)
    d_pins = library_pins(diode_block)
    switch_id = "%s:%s" % SWITCH_LIB
    diode_id = "%s:%s" % DIODE_LIB
    pico_id = "%s:%s" % (PICO_LIB_NAME, PICO_SYMBOL)
    use_diodes = layout["matrix"]["diodes"]

    # The key matrix, a cell for every key at its row and column
    extra_switches = []
    for n, (key, refs) in enumerate(zip(layout["keys"], switch_refs(layout))):
        cx = MATRIX_X + key["col"] * CELL_W
        cy = MATRIX_Y + key["row"] * CELL_H
        row_net = "ROW%d" % key["row"]
        col_net = "COL%d" % key["col"]
        key_net = "K_%s" % key["id"] if use_diodes else row_net
        label = key["label"] or key["id"]
        sheet.symbol(switch_id, refs[0], label, SWITCH_FOOTPRINT, cx, cy, 0, ["1", "2"],
                     (cx, cy - 3.81), (cx, cy + 2.54), mpn=kl.switch_part_number(layout))
        p1 = place((cx, cy), sw_pins["1"], 0)
        p2 = place((cx, cy), sw_pins["2"], 0)
        sheet.label(col_net, p1[0], p1[1], 180)
        if use_diodes:
            dx, dy = cx + DIODE_DX, cy + DIODE_DY
            # turned 90 degrees: anode (pin 2) at the top, cathode (pin 1) below
            sheet.symbol(diode_id, "D%d" % (n + 1), "1N4148W", DIODE_FOOTPRINT, dx, dy, 90, ["1", "2"],
                         (dx + 2.54, dy), (dx + 2.54, dy + 2.54), hide_value=True, mpn="1N4148W-7-F")
            anode = place((dx, dy), d_pins["2"], 90)
            cathode = place((dx, dy), d_pins["1"], 90)
            sheet.wire(p2[0], p2[1], anode[0], p2[1])
            sheet.wire(anode[0], p2[1], anode[0], anode[1])
            sheet.label(key_net, anode[0], p2[1], 90)
            sheet.label(row_net, cathode[0], cathode[1], 0)
        else:
            sheet.label(row_net, p2[0], p2[1], 0)
        for ref in refs[1:]:
            extra_switches.append((ref, label, col_net, key_net))

    # The Pico, with labels on the matrix pins
    pico_at = (MATRIX_X + 2 * CELL_W, MATRIX_Y + 5 * CELL_H + 55.88)
    sheet.symbol(pico_id, "U1", "Raspberry Pi Pico", "%s:%s" % (PICO_LIB_NAME, pico_footprint_name(layout)),
                 pico_at[0], pico_at[1], 0, [str(p) for p in range(1, 41)],
                 (pico_at[0], pico_at[1] - 29.21), (pico_at[0], pico_at[1] + 29.21))
    nets = {}
    for r, gpio in enumerate(layout["matrix"]["row_pins"]):
        nets[kl.PICO_PIN_FOR_GPIO[gpio]] = "ROW%d" % r
    for c, gpio in enumerate(layout["matrix"]["col_pins"]):
        nets[kl.PICO_PIN_FOR_GPIO[gpio]] = "COL%d" % c
    for pin in range(1, 41):
        x, y = place(pico_at, pico_pin_position(pin), 0)
        if pin in nets:
            sheet.label(nets[pin], x, y, 180 if pin <= 20 else 0)
        else:
            sheet.no_connect(x, y)

    # Any extra switches under long keys, wired in parallel with the key's first switch
    ex, ey = MATRIX_X + 7 * CELL_W, MATRIX_Y + 5 * CELL_H + 33.02
    if extra_switches:
        sheet.text("Extra switches under long keys, in parallel with each key's first switch", ex - 10.16, ey - 7.62)
    for i, (ref, label, col_net, key_net) in enumerate(extra_switches):
        x, y = ex + (i % 4) * CELL_W * 1.5, ey + (i // 4) * 12.7
        sheet.symbol(switch_id, ref, label, SWITCH_FOOTPRINT, x, y, 0, ["1", "2"], (x, y - 3.81), (x, y + 2.54),
                     mpn=kl.switch_part_number(layout))
        p1 = place((x, y), sw_pins["1"], 0)
        p2 = place((x, y), sw_pins["2"], 0)
        sheet.label(col_net, p1[0], p1[1], 180)
        sheet.label(key_net, p2[0], p2[1], 0)

    # Notes
    nrows, ncols = kl.matrix_size(layout)
    notes_x, notes_y = MATRIX_X + 4.5 * CELL_W, MATRIX_Y + 5 * CELL_H + 12.7
    lines = [
        "%s: %d keys, %d x %d key matrix" % (layout["name"], len(layout["keys"]), nrows, ncols),
        "Each key: COLn - switch - diode (anode to the switch) - ROWn, for keypad columns_to_anodes=True",
        "Switches: C&K %s (PTS645 SMD, %.1fmm, %sgf).  Diodes: 1N4148W, SOD-123." % (
            kl.switch_part_number(layout), layout["switch"]["height"], kl.switch_force_grams(layout)),
        "Pico mounted on the %s of the board. GND and power pins unused (the Pico is powered by USB)." %
        layout["controller"]["side"],
        "Generated from the layout by kicad/build_pcb.py - change the layout, not this sheet.",
    ]
    for i, line in enumerate(lines):
        sheet.text(line, notes_x, notes_y + i * 3.81, 1.524 if i == 0 else 1.27)

    lib_symbols = [switch_block, diode_block, pico_symbol(pico_id)]
    today = datetime.date.today().isoformat()
    text = "\n".join([
        '(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")',
        '(uuid "%s")' % sheet.root,
        '(paper "%s")' % PAPER[0],
        '(title_block (title %s) (date "%s") (comment 1 "PICO Cyberdeck keyboard")'
        ' (comment 2 "Generated from the layout JSON by kicad/build_pcb.py"))' % (q(layout["name"]), today),
        "(lib_symbols",
        "\n".join(lib_symbols),
        ")",
        "\n".join(sheet.items),
        '(sheet_instances (path "/" (page "1")))',
        ")",
    ])
    path = os.path.join(out_dir, layout["name"] + ".kicad_sch")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return path
