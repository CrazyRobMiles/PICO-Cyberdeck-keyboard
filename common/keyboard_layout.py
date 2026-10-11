"""
Shared model for the PICO Cyberdeck keyboard layout JSON.

This file is plain Python (no third party libraries) so that it can be
imported by all three programs that use the layout:

- designer/keyboard_designer.py  (PC GUI that creates and edits the JSON)
- kicad/build_pcb.py             (runs with KiCad's Python and makes the PCB)
- freecad/build_case.py          (runs inside FreeCAD and makes the case)

Coordinates
-----------
All dimensions are millimetres. Layout coordinates use the same convention
as KiCad: X increases to the right, Y increases DOWN the board, seen from the
front (key side). Key positions are the centre of the key (which is also the
centre of its switch). Rotation is in degrees, counter-clockwise as seen from
the front.

The board outline can be sized automatically to fit the keys (board.auto_size)
or set explicitly. Either way, board_rect() returns the rectangle that the
other programs should use.
"""

import copy
import json
import math

FORMAT = "pico-cyberdeck-keyboard"
VERSION = 1

# Tests found that a key with one switch in the middle presses properly at
# either end up to this length (in key units)
MAX_SINGLE_SWITCH_WIDTH = 4.0

# Default limit on the width of the finished case (case.max_width)
MAX_CASE_WIDTH = 170.0

# ---------------------------------------------------------------------------
# Hardware data
# ---------------------------------------------------------------------------

# C&K PTS645 6x6mm SMD tactile switch - the same switch (and KiCad footprint)
# as used on the Cheesebox PCB. Pads are at (+-3.98, +-2.25), 1.55 x 1.3mm.
# Pads "1" are the top pair, pads "2" the bottom pair.
SWITCHES = {
    "PTS645": {
        "footprint_lib": "Button_Switch_SMD",
        "footprint": "SW_SPST_PTS645",
        "body": 6.0,             # square body size
        "body_height": 3.5,      # height of the body above the PCB
        "heights": [4.3, 5.0, 7.0, 9.5],  # available overall heights (to top of plunger)
        # press force: the letter in the part number, and grams force
        "forces": {"L": 130, "M": 160, "H": 200, "K": 260},
        "plunger_diameter": 3.5,
        "pad_extent": (9.53, 5.8),   # width/height of the area covered by the pads
        "courtyard": (10.15, 6.85),   # from the KiCad footprint
    }
}

# SOD-123 matrix diode. KiCad pad 1 is the cathode, pad 2 the anode.
DIODE = {
    "footprint_lib": "Diode_SMD",
    "footprint": "D_SOD-123",
    "courtyard": (4.75, 2.35),
}

# Raspberry Pi Pico
PICO_WIDTH = 21.0
PICO_LENGTH = 51.0
PICO_PIN_PITCH = 2.54
PICO_ROW_SPACING = 17.78
PICO_USB_OVERHANG = 1.3      # the USB socket sticks out past the board edge
PICO_THICKNESS = 1.0
PICO_PART_HEIGHT = 3.2       # tallest part on the Pico (USB socket) above its PCB

# GPIO numbers that are brought out to pins, and the pin each one is on
PICO_PIN_FOR_GPIO = {
    0: 1, 1: 2, 2: 4, 3: 5, 4: 6, 5: 7, 6: 9, 7: 10, 8: 11, 9: 12,
    10: 14, 11: 15, 12: 16, 13: 17, 14: 19, 15: 20, 16: 21, 17: 22,
    18: 24, 19: 25, 20: 26, 21: 27, 22: 29, 26: 31, 27: 32, 28: 34,
}
PICO_GPIO = sorted(PICO_PIN_FOR_GPIO.keys())
PICO_GND_PINS = [3, 8, 13, 18, 23, 28, 33, 38]
PICO_OTHER_PINS = {30: "RUN", 35: "ADC_VREF", 36: "3V3", 37: "3V3_EN", 39: "VSYS", 40: "VBUS"}


def pico_pin_position(pin):
    """Position of a Pico pin relative to the Pico centre, Pico unrotated
    (USB end at the top, i.e. -Y), seen from the Pico's component side."""
    if pin <= 20:
        return (-PICO_ROW_SPACING / 2, -24.13 + (pin - 1) * PICO_PIN_PITCH)
    return (PICO_ROW_SPACING / 2, 24.13 - (pin - 21) * PICO_PIN_PITCH)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULTS = {
    "format": FORMAT,
    "version": VERSION,
    "name": "cyberdeck",
    "units": "mm",
    "switch": {
        "type": "PTS645",
        "height": 5.0,
        "force": "M",        # L 130gf, M 160gf (medium), H 200gf, K 260gf
    },
    "grid": {
        "pitch_x": 11.5,     # size of a 1u key position
        "pitch_y": 11.5,
        "snap": 0.5,         # designer snap distance
    },
    "keys": [],
    "board": {
        "auto_size": True,
        # margins around the keys (and controller) when auto sizing
        "margin": {"top": 6.0, "right": 3.0, "bottom": 3.0, "left": 3.0},
        # explicit rectangle - used when auto_size is False
        "x": 0.0, "y": 0.0, "width": 100.0, "height": 50.0,
        "corner_radius": 2.0,
        "thickness": 1.6,
        "mounting_holes": [],
    },
    "controller": {
        "type": "pico",
        "side": "back",      # "front" or "back"
        "x": 0.0, "y": 0.0,  # centre of the Pico
        "rotation": 0,       # 0 = USB end towards -Y (top edge of the board)
    },
    "matrix": {
        "diodes": True,
        "auto": True,        # re-assign the matrix whenever the keys change
        "reserved_pins": [], # GPIO numbers the matrix must not use
        "row_pins": [],      # GPIO numbers
        "col_pins": [],
    },
    "routing": {
        "enabled": True,          # add the tracks with kicad/autoroute.py
        "grid": 0.5,              # routing grid
        "track_width": 0.25,
        "clearance": 0.2,
        "edge_clearance": 0.5,    # from the board edge
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "via_cost": 8,            # how many grid steps a via is worth
        "wrong_way_cost": 3,      # cost of a vertical step on the front or horizontal on the back
    },
    "mock_pcb": {
        # The printed stand-in for the PCB has a fence round each switch
        "fence_height": 2.5,      # the switch body is 3.5mm high
        "fence_wall": 0.8,
        "body_clearance": 0.15,   # gap between the switch body and the fence at the bottom
        "grip": 0.0,              # how much smaller than the switch the fence is at the top (each side) - 0 tested best
        "lead_in": 0.4,           # chamfer at the top of the fence to guide the switch in
    },
    "firmware": {
        "debounce_scans": 2,      # a key change must be seen on this many 5ms scans in a row
    },
    "case": {
        "max_width": MAX_CASE_WIDTH,  # the case must be narrower than this
        "wall": 2.0,              # side wall thickness
        "floor": 1.5,             # floor thickness
        "clearance": 0.5,         # gap between the PCB edge and the wall
        "back_clearance": 5.0,    # space under the PCB (room for the Pico)
        "plate_thickness": 1.5,   # top plate thickness
        "key_gap": 1.6,           # plate web between neighbouring key holes
        "key_clearance": 0.35,    # gap between a keycap and its hole (each side) - allows for FDM printing
        "key_protrusion": 2.0,    # how far the keytops stand above the plate
        "flange": 0.9,            # how far the retaining lip sticks out round the keycap
        "flange_angle": 45.0,     # slope of the tapered shoulder above the lip, degrees from flat
        "flange_thickness": 1.0,  # height of the straight band at the bottom of the lip
        "flange_clearance": 0.3,  # gap between the top of that band and the underside of the plate
        "plunger_gap": 1.0,       # extra room between a keytop resting on its switch and the plate,
                                  # so print tolerances can't leave the switches pressed in
        "corner_radius": 3.0,
        "hole_diameter": 2.2,     # PCB mounting hole (M2)
        "standoff_diameter": 5.0,
        "screw_pilot": 1.8,       # self tapping hole in the top plate pillars
        "ledge": 1.5,             # width of the support ledge/rib at the PCB edge
        "legend": "inlay",        # "inlay" (two colour), "engrave" or "none"
        "legend_depth": 0.6,      # 3 layers at 0.2mm
        "font": "C:/Windows/Fonts/arialbd.ttf",
    },
}


def _merge(defaults, values):
    """Deep merge values over defaults, returning a new dictionary."""
    result = copy.deepcopy(defaults)
    for k, v in values.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def new_layout():
    return copy.deepcopy(DEFAULTS)


def normalise(layout):
    """Fill in anything missing from a layout with the defaults."""
    layout = _merge(DEFAULTS, layout)
    layout["firmware"].pop("release_hold_ms", None)   # no longer used
    for i, key in enumerate(layout["keys"]):
        key.setdefault("id", "K%d" % (i + 1))
        key.setdefault("label", "")
        key.setdefault("keycode", "")
        key.setdefault("fn_keycode", "")
        key.setdefault("switches", [0.0])
        key.setdefault("w", 1.0)
        key.setdefault("h", 1.0)
        key.setdefault("rotation", 0)
        key.setdefault("x", 0.0)
        key.setdefault("y", 0.0)
    for hole in layout["board"]["mounting_holes"]:
        hole.setdefault("d", layout["case"]["hole_diameter"])
    return layout


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    if layout.get("format") != FORMAT:
        raise ValueError("%s is not a %s file" % (path, FORMAT))
    return normalise(layout)


def save(layout, path):
    out = copy.deepcopy(layout)
    out["format"] = FORMAT
    out["version"] = VERSION
    # Store the derived board size too, so it is easy to read the JSON
    x, y, w, h = board_rect(layout)
    out["derived"] = {
        "board_rect": [round(x, 3), round(y, 3), round(w, 3), round(h, 3)],
        "case_size": [round(v, 3) for v in case_size(layout)],
        "stack": {k: round(v, 3) for k, v in stack(layout).items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def rotate(dx, dy, degrees):
    """Rotate an offset counter-clockwise as seen on screen (Y down)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return (dx * c + dy * s, -dx * s + dy * c)


def rect_corners(cx, cy, w, h, degrees=0):
    pts = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        rx, ry = rotate(dx, dy, degrees)
        pts.append((cx + rx, cy + ry))
    return pts


def circle_points(cx, cy, r, n=16):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def polygons_overlap(a, b):
    """Separating axis test for two convex polygons."""
    for poly in (a, b):
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            nx, ny = y1 - y2, x2 - x1
            pa = [nx * x + ny * y for x, y in a]
            pb = [nx * x + ny * y for x, y in b]
            if max(pa) <= min(pb) + 1e-9 or max(pb) <= min(pa) + 1e-9:
                return False
    return True


def bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_rect(px, py, rect):
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h


# ---------------------------------------------------------------------------
# Derived geometry
# ---------------------------------------------------------------------------

def switch_part_number(layout):
    """C&K part number of the surface mount (gull wing) PTS645 with the
    layout's height and press force, e.g. PTS645SM50SMTR92 LFS for 5.0mm and
    medium (160gf) force."""
    sw = layout["switch"]
    return "PTS645S%s%02dSMTR92 LFS" % (sw["force"], round(sw["height"] * 10))


def switch_force_grams(layout):
    return switch_info(layout)["forces"].get(layout["switch"]["force"])


def switch_info(layout):
    return SWITCHES[layout["switch"]["type"]]


def key_area_size(layout, key):
    """Size of the space allocated to a key (w x h units of pitch)."""
    g = layout["grid"]
    return key["w"] * g["pitch_x"], key["h"] * g["pitch_y"]


def keycap_size(layout, key):
    """Size of the visible keytop - its hole in the plate is key_clearance bigger all round."""
    c = layout["case"]
    w, h = key_area_size(layout, key)
    shrink = c["key_gap"] + 2 * c["key_clearance"]
    return w - shrink, h - shrink


def keycap_hole_size(layout, key):
    c = layout["case"]
    w, h = keycap_size(layout, key)
    return w + 2 * c["key_clearance"], h + 2 * c["key_clearance"]


def taper_height(layout):
    """Height of the tapered shoulder between a keycap's lip and its body.
    The plate holes have the same slope, so the shoulder seats against it."""
    c = layout["case"]
    return c["flange"] * math.tan(math.radians(c["flange_angle"]))


def keycap_hole_bottom_size(layout, key):
    """Size of a plate hole at the underside of the plate, where its sloped
    sides are widest."""
    c = layout["case"]
    w, h = keycap_hole_size(layout, key)
    grow = max(0.0, taper_height(layout) - c["flange_clearance"]) / math.tan(math.radians(c["flange_angle"]))
    return w + 2 * grow, h + 2 * grow


def keycap_flange_size(layout, key):
    c = layout["case"]
    w, h = keycap_size(layout, key)
    return w + 2 * c["flange"], h + 2 * c["flange"]


def switch_positions(layout, key):
    """Centres of the key's switches, in layout coordinates. key["switches"]
    lists their offsets along the key from its centre, in key units, so the
    default [0] is one switch in the middle and [-1.5, 1.5] puts the switches
    of a 4u space bar 1.5 units either side of the middle."""
    pitch = layout["grid"]["pitch_x"]
    out = []
    for offset in key.get("switches") or [0.0]:
        dx, dy = rotate(offset * pitch, 0, key.get("rotation", 0))
        out.append((key["x"] + dx, key["y"] + dy))
    return out


def switch_polygons(layout, key, kind="courtyard"):
    """Outlines of each of the key's switches. kind is switch (the pads) or
    courtyard (the space the switch needs)."""
    w, h = switch_info(layout)["pad_extent" if kind == "switch" else "courtyard"]
    return [rect_corners(x, y, w, h, key.get("rotation", 0)) for x, y in switch_positions(layout, key)]


def key_polygon(layout, key, kind="area"):
    """Outline of a key. kind is one of area, cap, hole, flange, switch, courtyard.
    For switch and courtyard this is the key's first switch - use
    switch_polygons() for all of them."""
    if kind == "area":
        w, h = key_area_size(layout, key)
    elif kind == "cap":
        w, h = keycap_size(layout, key)
    elif kind == "hole":
        w, h = keycap_hole_size(layout, key)
    elif kind == "flange":
        w, h = keycap_flange_size(layout, key)
    elif kind == "hole_bottom":
        w, h = keycap_hole_bottom_size(layout, key)
    elif kind in ("switch", "courtyard"):
        return switch_polygons(layout, key, kind)[0]
    else:
        raise ValueError(kind)
    return rect_corners(key["x"], key["y"], w, h, key.get("rotation", 0))


def diode_position(layout, key):
    """Diodes sit on the front of the board, on the bottom edge of their key's
    space - which is the middle of the gap between two rows of switches."""
    _, ah = key_area_size(layout, key)
    dx, dy = rotate(0, ah / 2, key.get("rotation", 0))
    return key["x"] + dx, key["y"] + dy, key.get("rotation", 0)


def diode_polygon(layout, key):
    x, y, r = diode_position(layout, key)
    w, h = DIODE["courtyard"]
    return rect_corners(x, y, w, h, r)


def pico_polygon(layout, margin=0.0):
    c = layout["controller"]
    return rect_corners(c["x"], c["y"], PICO_WIDTH + 2 * margin, PICO_LENGTH + 2 * margin, c["rotation"])


def pico_usb(layout):
    """Returns ((x, y), (dx, dy)): the point where the USB socket leaves the
    Pico board edge, and the unit direction it points in."""
    c = layout["controller"]
    dx, dy = rotate(0, -1, c["rotation"])
    return (c["x"] + dx * PICO_LENGTH / 2, c["y"] + dy * PICO_LENGTH / 2), (dx, dy)


def hole_polygon(layout, hole, diameter=None):
    d = diameter if diameter is not None else layout["case"]["standoff_diameter"]
    return circle_points(hole["x"], hole["y"], d / 2)


def content_bounds(layout):
    """Bounds of everything that must fit on the board."""
    pts = []
    for key in layout["keys"]:
        pts += key_polygon(layout, key, "area")
    if layout["keys"]:
        pts += pico_polygon(layout)
    if not pts:
        return 0, 0, 0, 0
    return bounds(pts)


def board_rect(layout):
    """(x, y, width, height) of the PCB outline in layout coordinates."""
    b = layout["board"]
    if not b["auto_size"] or not layout["keys"]:
        return b["x"], b["y"], b["width"], b["height"]
    m = b["margin"]
    # Fit the keys plus margins. The Pico is allowed to sit right at an edge
    # (its USB socket needs to reach the edge), so it only extends the board
    # where it would otherwise stick out.
    kpts = []
    for key in layout["keys"]:
        kpts += key_polygon(layout, key, "area")
    x0, y0, x1, y1 = bounds(kpts)
    x0, y0, x1, y1 = x0 - m["left"], y0 - m["top"], x1 + m["right"], y1 + m["bottom"]
    px0, py0, px1, py1 = bounds(pico_polygon(layout))
    x0, y0, x1, y1 = min(x0, px0), min(y0, py0), max(x1, px1), max(y1, py1)
    return x0, y0, x1 - x0, y1 - y0


def case_rect(layout):
    x, y, w, h = board_rect(layout)
    c = layout["case"]
    grow = c["clearance"] + c["wall"]
    return x - grow, y - grow, w + 2 * grow, h + 2 * grow


def stack(layout):
    """Heights (Z) of everything, with Z=0 at the underside of the PCB."""
    c = layout["case"]
    t = layout["board"]["thickness"]
    s = {}
    s["case_bottom"] = -(c["back_clearance"] + c["floor"])
    s["floor_top"] = -c["back_clearance"]
    s["pcb_bottom"] = 0.0
    s["pcb_top"] = t
    s["switch_body_top"] = t + switch_info(layout)["body_height"]
    s["plunger_top"] = t + layout["switch"]["height"]
    s["cap_bottom"] = s["plunger_top"]
    s["flange_top"] = s["cap_bottom"] + c["flange_thickness"]
    s["shoulder_top"] = s["flange_top"] + taper_height(layout)
    # The plate (and the sloped sides of its holes) are plunger_gap higher
    # than a keytop resting on its switch, so a key can rise plunger_gap plus
    # the clearance on its slope before it seats against the plate.
    s["plate_bottom"] = s["flange_top"] + c["flange_clearance"] + c["plunger_gap"]
    s["plate_top"] = s["plate_bottom"] + c["plate_thickness"]
    s["cap_top"] = s["plate_top"] + c["key_protrusion"]
    return s


def case_size(layout):
    _, _, w, h = case_rect(layout)
    s = stack(layout)
    return w, h, s["plate_top"] - s["case_bottom"]


def screw_length(layout):
    """Longest standard screw that will fit, fixing from underneath through the
    floor, standoff and PCB into the pillar under the top plate."""
    s = stack(layout)
    available = (s["plate_top"] - 0.8) - s["case_bottom"]
    best = None
    for length in (6, 8, 10, 12, 14, 16, 20, 25):
        if length <= available - 0.5:
            best = length
    return best, available


# ---------------------------------------------------------------------------
# Building layouts
# ---------------------------------------------------------------------------

def add_key_rows(layout, rows, x0=0.0, y0=0.0):
    """Add rows of keys. Each row is a list of entries which can be:
       None                 - a 1u gap
       ("gap", w)           - a gap w units wide
       "Q"                  - a 1u key, label and keycode Q
       ("Space", "SPACE", 2) - label, keycode, width in units
    """
    g = layout["grid"]
    n = len(layout["keys"])
    for r, row in enumerate(rows):
        x = x0
        for entry in row:
            if entry is None:
                x += g["pitch_x"]
                continue
            if isinstance(entry, tuple) and entry[0] == "gap":
                x += entry[1] * g["pitch_x"]
                continue
            if isinstance(entry, str):
                label, code, w = entry, entry.upper(), 1.0
            else:
                label, code, w = entry
            n += 1
            layout["keys"].append({
                "id": "K%d" % n, "label": label, "keycode": code,
                "x": round(x + w * g["pitch_x"] / 2, 3),
                "y": round(y0 + r * g["pitch_y"] + g["pitch_y"] / 2, 3),
                "w": w, "h": 1.0, "rotation": 0, "switches": [0.0],
            })
            x += w * g["pitch_x"]


# Keycode names are the names in the CircuitPython adafruit_hid Keycode class.
# FN is handled by the firmware: hold it to get each key's fn_keycode.
KEYCODES = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)] +
    ["ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "ZERO"] +
    ["ENTER", "ESCAPE", "BACKSPACE", "TAB", "SPACE", "MINUS", "EQUALS", "LEFT_BRACKET",
     "RIGHT_BRACKET", "BACKSLASH", "POUND", "SEMICOLON", "QUOTE", "GRAVE_ACCENT", "COMMA",
     "PERIOD", "FORWARD_SLASH", "CAPS_LOCK"] +
    ["F%d" % n for n in range(1, 13)] +
    ["PRINT_SCREEN", "SCROLL_LOCK", "PAUSE", "INSERT", "HOME", "PAGE_UP", "DELETE", "END",
     "PAGE_DOWN", "RIGHT_ARROW", "LEFT_ARROW", "DOWN_ARROW", "UP_ARROW", "APPLICATION",
     "LEFT_CONTROL", "LEFT_SHIFT", "LEFT_ALT", "LEFT_GUI", "RIGHT_CONTROL", "RIGHT_SHIFT",
     "RIGHT_ALT", "RIGHT_GUI", "FN"]
)

_LABEL_KEYCODES = {
    "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR", "5": "FIVE", "6": "SIX", "7": "SEVEN",
    "8": "EIGHT", "9": "NINE", "0": "ZERO", "-": "MINUS", "=": "EQUALS", "[": "LEFT_BRACKET",
    "]": "RIGHT_BRACKET", "\\": "BACKSLASH", ";": "SEMICOLON", "'": "QUOTE", "`": "GRAVE_ACCENT",
    ",": "COMMA", ".": "PERIOD", "/": "FORWARD_SLASH", "#": "POUND",
    "ESC": "ESCAPE", "BKSP": "BACKSPACE", "BS": "BACKSPACE", "DEL": "DELETE", "ENT": "ENTER",
    "RET": "ENTER", "RETURN": "ENTER", "SPC": "SPACE", "SHIFT": "LEFT_SHIFT", "SHFT": "LEFT_SHIFT",
    "CTRL": "LEFT_CONTROL", "CTL": "LEFT_CONTROL", "ALT": "LEFT_ALT", "GUI": "LEFT_GUI",
    "WIN": "LEFT_GUI", "CMD": "LEFT_GUI", "CAPS": "CAPS_LOCK", "INS": "INSERT", "PGUP": "PAGE_UP",
    "PGDN": "PAGE_DOWN", "<": "LEFT_ARROW", ">": "RIGHT_ARROW", "^": "UP_ARROW", "V": "V",
    "LEFT": "LEFT_ARROW", "RIGHT": "RIGHT_ARROW", "UP": "UP_ARROW", "DOWN": "DOWN_ARROW",
}


def guess_keycode(label):
    up = label.strip().upper()
    if up in _LABEL_KEYCODES:
        return _LABEL_KEYCODES[up]
    if up in KEYCODES:
        return up
    return ""


def parse_rows(text):
    """Turn text into rows for add_key_rows. One line per row, keys separated
    by spaces. A key can have a width: Space:2. An underscore is a 1u gap,
    and _:0.5 is a half unit gap."""
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = []
        for token in line.split():
            label, _, width = token.partition(":")
            w = float(width) if width else 1.0
            if label == "_":
                row.append(("gap", w))
            else:
                row.append((label, guess_keycode(label), w))
        rows.append(row)
    return rows


# Row stagger presets: how far (in key units) each row is moved right,
# top row first. Rows beyond the end of the list are not moved.
STAGGER_PRESETS = {
    "None (ortholinear)": [],
    "Standard (QWERTY, ASDF, ZXCV rows)": [0, 0.25, 0.75],
    "Standard with number row": [0, 0.5, 0.75, 1.25],
    "Half key (brick)": [0, 0.5, 0, 0.5, 0],
}


def stagger_rows(layout, offsets, keys=None):
    """Move each row of keys right by offsets[row] key units (top row first).
    keys limits this to some of the keys - by default all of them are moved."""
    keys = layout["keys"] if keys is None else keys
    pitch = layout["grid"]["pitch_x"]
    for r, row in enumerate(group_rows(layout, keys)):
        if r < len(offsets) and offsets[r]:
            for key in row:
                key["x"] = round(key["x"] + offsets[r] * pitch, 3)


def parse_offsets(text):
    return [float(v) for v in text.replace(";", ",").split(",") if v.strip()]


def example_layout():
    """A 4 x 12 cyberdeck keyboard with the Pico on the back, USB at the top."""
    layout = new_layout()
    layout["name"] = "cyberdeck40"
    add_key_rows(layout, [
        [("Esc", "ESCAPE", 1), "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", ("Bksp", "BACKSPACE", 1)],
        [("Tab", "TAB", 1), "A", "S", "D", "F", "G", "H", "J", "K", "L", (";", "SEMICOLON", 1),
         ("Ent", "ENTER", 1)],
        [("Shft", "LEFT_SHIFT", 1), "Z", "X", "C", "V", "B", "N", "M", (",", "COMMA", 1), (".", "PERIOD", 1),
         ("/", "FORWARD_SLASH", 1), ("'", "QUOTE", 1)],
        [("Ctl", "LEFT_CONTROL", 1), ("Fn", "FN", 1), ("Gui", "LEFT_GUI", 1), ("Alt", "LEFT_ALT", 1), None,
         ("Space", "SPACE", 2), None, ("<", "LEFT_ARROW", 1), ("v", "DOWN_ARROW", 1), ("^", "UP_ARROW", 1),
         (">", "RIGHT_ARROW", 1)],
    ])
    g = layout["grid"]
    centre_x = 6 * g["pitch_x"]
    top = -layout["board"]["margin"]["top"]
    # Pico on the back, centred, with its USB socket at the top edge of the board
    layout["controller"].update({"side": "back", "rotation": 0, "x": centre_x, "y": top + PICO_LENGTH / 2})
    # Two holes in the top margin and two in the gaps beside the space bar
    row3_y = 3.5 * g["pitch_y"]
    layout["board"]["mounting_holes"] = [
        {"x": 2 * g["pitch_x"], "y": top / 2, "d": layout["case"]["hole_diameter"]},
        {"x": 10 * g["pitch_x"], "y": top / 2, "d": layout["case"]["hole_diameter"]},
        {"x": 4.5 * g["pitch_x"], "y": row3_y, "d": layout["case"]["hole_diameter"]},
        {"x": 7.5 * g["pitch_x"], "y": row3_y, "d": layout["case"]["hole_diameter"]},
    ]
    auto_matrix(layout)
    return layout


_STAGGERED_ROWS = [
    "Tab:1.5 Q W E R T Y U I O P Bksp:1.5",
    "Esc:1.75 A S D F G H J K L ; Ent:1.25",
    "Shift:2.25 Z X C V B N M , . Shift:1.75",
    "Ctrl:1.5 Gui:1.25 Alt:1.25 Space:4 Fn < v ^ >",
]


def staggered_example_layout():
    """A 'proper' staggered 4 row keyboard, 13 units wide on a 12mm pitch,
    which fits a 170mm case. The stagger comes from the wide modifier keys at
    the start of each row, as on a full size keyboard: Q is 1.5u in, A 1.75u
    and Z 2.25u. The numbers are on the Fn layer."""
    fn = {"Q": "ONE", "W": "TWO", "E": "THREE", "R": "FOUR", "T": "FIVE", "Y": "SIX", "U": "SEVEN",
          "I": "EIGHT", "O": "NINE", "P": "ZERO", "Bksp": "DELETE", ";": "QUOTE", ".": "FORWARD_SLASH",
          ",": "MINUS", "Esc": "GRAVE_ACCENT", "<": "HOME", ">": "END", "^": "PAGE_UP", "v": "PAGE_DOWN"}
    return _staggered_layout("cyberdeck_staggered", _STAGGERED_ROWS, fn)


def staggered_numbers_layout():
    """The staggered keyboard with a number row on top, 5 rows deep. The
    number row starts half a key to the left of the Q row, as on a full size
    keyboard. Esc moves to the start of the number row and Caps Lock takes
    its old place. The Fn layer gives F1 to F12 on the number row."""
    rows = ["Esc 1 2 3 4 5 6 7 8 9 0 - ="] + _STAGGERED_ROWS
    rows[2] = rows[2].replace("Esc:1.75", "Caps:1.75")
    fn = {"Esc": "GRAVE_ACCENT", "-": "F11", "=": "F12", "Bksp": "DELETE", ";": "QUOTE",
          ".": "FORWARD_SLASH", "O": "LEFT_BRACKET", "P": "RIGHT_BRACKET", "L": "BACKSLASH",
          "<": "HOME", ">": "END", "^": "PAGE_UP", "v": "PAGE_DOWN"}
    for n, digit in enumerate("1234567890"):
        fn[digit] = "F%d" % (n + 1)
    return _staggered_layout("cyberdeck_numbers", rows, fn)


def _staggered_layout(name, rows, fn):
    layout = new_layout()
    layout["name"] = name
    layout["grid"]["pitch_x"] = 12.0
    layout["grid"]["pitch_y"] = 12.0
    layout["board"]["margin"].update({"top": 6.0, "bottom": 6.0})
    add_key_rows(layout, parse_rows("\n".join(rows)))
    for key in layout["keys"]:
        key["fn_keycode"] = fn.get(key["label"], "")
    shifts = [k for k in layout["keys"] if k["label"] == "Shift"]
    shifts[-1]["keycode"] = "RIGHT_SHIFT"
    g = layout["grid"]
    width = 13 * g["pitch_x"]
    top = -layout["board"]["margin"]["top"]
    bottom = len(rows) * g["pitch_y"] + layout["board"]["margin"]["bottom"]
    layout["controller"].update({"side": "back", "rotation": 0, "x": width / 2, "y": top + PICO_LENGTH / 2})
    d = layout["case"]["hole_diameter"]
    # The bottom holes go between two keys, clear of the diodes below the bottom row
    bottom_y = bottom - layout["board"]["margin"]["bottom"] / 2
    layout["board"]["mounting_holes"] = [
        {"x": width * 0.15, "y": top / 2, "d": d},
        {"x": width * 0.85, "y": top / 2, "d": d},
        {"x": 1.5 * g["pitch_x"], "y": bottom_y, "d": d},
        {"x": 12 * g["pitch_x"], "y": bottom_y, "d": d},
    ]
    auto_matrix(layout)
    return layout


def switch_test_layout():
    """A small keyboard for trying out keys of different lengths, each with
    one switch in the middle. Each key's label says how long it is.
    (Tests with two switches under a long key found it twice as hard to
    press, and that one central switch works for keys up to 4u.)"""
    layout = new_layout()
    layout["name"] = "switch_test"
    layout["grid"]["pitch_x"] = 12.0
    layout["grid"]["pitch_y"] = 12.0
    layout["board"]["margin"].update({"top": 6.0, "bottom": 6.0})
    widths = [[1, 1.5, 2, 2.25], [2.75, 4]]
    add_key_rows(layout, [[("%gu" % w, "", w) for w in row] for row in widths])
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for n, key in enumerate(layout["keys"]):
        key["keycode"] = letters[n]
    g = layout["grid"]
    width = 6.75 * g["pitch_x"]
    top = -layout["board"]["margin"]["top"]
    depth = len(widths) * g["pitch_y"]
    bottom_y = depth + layout["board"]["margin"]["bottom"] / 2
    # The Pico lies along the board under the keys, USB socket at the right hand edge
    right = width + layout["board"]["margin"]["right"]
    layout["controller"].update({"side": "back", "rotation": 270, "x": right - PICO_LENGTH / 2, "y": depth / 2})
    d = layout["case"]["hole_diameter"]
    layout["board"]["mounting_holes"] = [
        {"x": width * 0.15, "y": top / 2, "d": d},
        {"x": width * 0.85, "y": top / 2, "d": d},
        {"x": 6.0, "y": bottom_y, "d": d},
        {"x": width - 6.0, "y": bottom_y, "d": d},
    ]
    auto_matrix(layout)
    return layout


# ---------------------------------------------------------------------------
# Key matrix
# ---------------------------------------------------------------------------

def group_rows(layout, keys):
    """Split keys into rows (bands of keys at about the same height), top
    row first. Keys within half a pitch of each other vertically share a row."""
    rows = []
    for key in sorted(keys, key=lambda k: (k["y"], k["x"])):
        if rows and key["y"] - rows[-1][0]["y"] < layout["grid"]["pitch_y"] / 2:
            rows[-1].append(key)
        else:
            rows.append([key])
    return rows


def auto_matrix(layout, reserved_gpio=None):
    """Allocate a row and column to every key, and GPIO pins to every row and
    column. Rows are bands of keys at the same height, columns follow X
    position so that the column wiring runs roughly vertically."""
    keys = layout["keys"]
    if not keys:
        layout["matrix"]["row_pins"] = []
        layout["matrix"]["col_pins"] = []
        return
    g = layout["grid"]
    rows = group_rows(layout, keys)
    min_x = min(k["x"] - key_area_size(layout, k)[0] / 2 for k in keys)
    ncols = 0
    for r, row in enumerate(rows):
        used = set()
        for key in sorted(row, key=lambda k: k["x"]):
            col = max(0, int(math.floor((key["x"] - min_x) / g["pitch_x"])))
            while col in used:
                col += 1
            used.add(col)
            key["row"] = r
            key["col"] = col
            ncols = max(ncols, col + 1)
    # Remove empty columns
    used_cols = sorted({k["col"] for k in keys})
    remap = {c: i for i, c in enumerate(used_cols)}
    for k in keys:
        k["col"] = remap[k["col"]]
    ncols = len(used_cols)
    if reserved_gpio is None:
        reserved_gpio = layout["matrix"].get("reserved_pins", [])
    free = [p for p in PICO_GPIO if p not in reserved_gpio]
    nrows = len(rows)
    layout["matrix"]["row_pins"] = free[:nrows]
    layout["matrix"]["col_pins"] = free[nrows:nrows + ncols]


def matrix_size(layout):
    keys = layout["keys"]
    if not keys or any("row" not in k or "col" not in k for k in keys):
        return 0, 0
    return max(k["row"] for k in keys) + 1, max(k["col"] for k in keys) + 1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(layout):
    """Returns a list of (level, message, ids) where level is "error" or
    "warning" and ids lists the keys/holes/"pico" concerned."""
    problems = []

    def add(level, msg, *ids):
        problems.append((level, msg, list(ids)))

    keys = layout["keys"]
    holes = layout["board"]["mounting_holes"]
    ctrl = layout["controller"]
    rect = board_rect(layout)
    cw, ch, cd = case_size(layout)

    limit = layout["case"]["max_width"]
    if cw >= limit:
        add("error", "Case is %.1fmm wide - must be less than %.1fmm (%.2f in)" % (cw, limit, limit / 25.4))

    ids = [k["id"] for k in keys]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        add("error", "Duplicate key id %s" % dup, dup)

    def any_overlap(polys_a, polys_b):
        return any(polygons_overlap(pa, pb) for pa in polys_a for pb in polys_b)

    # Each key's own switches
    for k in keys:
        if len(k.get("switches") or [0]) > 1:
            add("warning", "Key %s has %d switches, which makes it that many times harder to press" %
                (k["id"], len(k["switches"])), k["id"])
        elif k["w"] > MAX_SINGLE_SWITCH_WIDTH or k["h"] > MAX_SINGLE_SWITCH_WIDTH:
            add("warning", "Key %s is longer than %gu, so it may rock about its switch if pressed at an end" %
                (k["id"], MAX_SINGLE_SWITCH_WIDTH), k["id"])
        yards = switch_polygons(layout, k)
        for i in range(len(yards)):
            if any(polygons_overlap(yards[i], other) for other in yards[i + 1:]):
                add("error", "The switches under key %s are too close together" % k["id"], k["id"])
                break
        cap = key_polygon(layout, k, "cap")
        for sx, sy in switch_positions(layout, k):
            if not polygons_overlap(circle_points(sx, sy, 0.01, 4), cap):
                add("error", "A switch under key %s is beyond the end of the key" % k["id"], k["id"])
                break

    # Key against key
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if polygons_overlap(key_polygon(layout, a, "hole"), key_polygon(layout, b, "hole")):
                add("error", "Keys %s and %s overlap" % (a["id"], b["id"]), a["id"], b["id"])
            elif polygons_overlap(key_polygon(layout, a, "flange"), key_polygon(layout, b, "flange")):
                add("error", "Keycap flanges of %s and %s collide - increase key gap or reduce flange" %
                    (a["id"], b["id"]), a["id"], b["id"])
            elif any_overlap(switch_polygons(layout, a), switch_polygons(layout, b)):
                add("error", "Switches %s and %s are too close" % (a["id"], b["id"]), a["id"], b["id"])
            if layout["matrix"]["diodes"]:
                for p, q in ((a, b), (b, a)):
                    if any_overlap([diode_polygon(layout, p)], switch_polygons(layout, q)):
                        add("error", "Diode for %s hits switch %s" % (p["id"], q["id"]), p["id"], q["id"])

    # Keys must be on the board, inside the edge support rib
    inner = (rect[0] + layout["case"]["ledge"], rect[1] + layout["case"]["ledge"],
             rect[2] - 2 * layout["case"]["ledge"], rect[3] - 2 * layout["case"]["ledge"])
    for k in keys:
        outline = key_polygon(layout, k, "flange")
        if layout["matrix"]["diodes"]:
            outline = outline + diode_polygon(layout, k)
        for px, py in outline:
            if not point_in_rect(px, py, inner):
                add("error", "Key %s (or its diode) is too close to the edge of the board" % k["id"], k["id"])
                break

    # Mounting holes
    for n, hole in enumerate(holes):
        hid = "H%d" % (n + 1)
        hp = hole_polygon(layout, hole)
        if not point_in_rect(hole["x"], hole["y"], rect):
            add("error", "Mounting hole %s is off the board" % hid, hid)
        for k in keys:
            if polygons_overlap(hp, key_polygon(layout, k, "flange")) or \
                    any_overlap([hp], switch_polygons(layout, k)):
                add("error", "Mounting hole %s hits key %s" % (hid, k["id"]), hid, k["id"])
            elif layout["matrix"]["diodes"] and polygons_overlap(hp, diode_polygon(layout, k)):
                add("error", "Mounting hole %s hits the diode for %s" % (hid, k["id"]), hid, k["id"])
        if polygons_overlap(hp, pico_polygon(layout)):
            add("error", "Mounting hole %s hits the Pico" % hid, hid, "pico")
    if len(holes) < 2:
        add("warning", "Add at least two mounting holes to fix the top plate to the case")

    # Pico
    ppoly = pico_polygon(layout)
    if ctrl["side"] == "front":
        for k in keys:
            if polygons_overlap(ppoly, key_polygon(layout, k, "flange")):
                add("error", "Pico is under key %s" % k["id"], "pico", k["id"])
    for px, py in ppoly:
        if not point_in_rect(px, py, (rect[0] - 0.01, rect[1] - 0.01, rect[2] + 0.02, rect[3] + 0.02)):
            add("error", "Pico hangs off the board", "pico")
            break
    (ux, uy), _ = pico_usb(layout)
    edge_dist = min(abs(ux - rect[0]), abs(ux - rect[0] - rect[2]), abs(uy - rect[1]), abs(uy - rect[1] - rect[3]))
    if edge_dist > 0.5:
        add("warning", "Pico USB socket is %.1fmm from the board edge - it will not reach the case wall" % edge_dist,
            "pico")
    s = stack(layout)
    if ctrl["side"] == "back" and layout["case"]["back_clearance"] < PICO_THICKNESS + PICO_PART_HEIGHT + 0.3:
        add("error", "back_clearance is too small for a Pico mounted on the back")

    # Matrix
    m = layout["matrix"]
    nrows, ncols = matrix_size(layout)
    if keys and (nrows == 0 or ncols == 0):
        add("error", "Keys have no matrix positions - run Auto matrix")
    else:
        seen = {}
        for k in keys:
            rc = (k["row"], k["col"])
            if rc in seen:
                add("error", "Keys %s and %s share matrix position %s" % (seen[rc], k["id"], rc), seen[rc], k["id"])
            seen[rc] = k["id"]
        if len(m["row_pins"]) < nrows:
            add("error", "Matrix needs %d row pins, %d set" % (nrows, len(m["row_pins"])))
        if len(m["col_pins"]) < ncols:
            add("error", "Matrix needs %d column pins, %d set" % (ncols, len(m["col_pins"])))
        pins = list(m["row_pins"]) + list(m["col_pins"])
        for p in pins:
            if p not in PICO_PIN_FOR_GPIO:
                add("error", "GP%s is not a usable Pico GPIO" % p)
        for p in sorted({p for p in pins if pins.count(p) > 1}):
            add("error", "GP%s is used more than once" % p)
        if not m["diodes"] and len(keys) > 0 and nrows > 1:
            add("warning", "Without diodes, pressing three keys at once can produce ghost key presses")

    c = layout["case"]
    if not 20 <= c["flange_angle"] <= 70:
        add("warning", "A flange angle of %g degrees will not print well upside down - 45 is best" % c["flange_angle"])
    if s["shoulder_top"] + c["plunger_gap"] > s["plate_top"] - 0.3:
        add("error", "The keycap shoulder is too tall for the plate - make the flange or its angle smaller, "
                     "or the plate thicker")
    if c["flange_clearance"] >= taper_height(layout):
        add("warning", "flange_clearance is bigger than the shoulder is tall, so the plate holes have no slope")
    if keys:
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if polygons_overlap(key_polygon(layout, a, "hole_bottom"), key_polygon(layout, b, "hole_bottom")):
                    add("warning", "The sloped holes for %s and %s meet under the plate, leaving a sharp edge - "
                                   "increase the key gap" % (a["id"], b["id"]), a["id"], b["id"])
                    break
            else:
                continue
            break

    mock = layout["mock_pcb"]
    if mock["fence_height"] > switch_info(layout)["body_height"] - 0.3:
        add("warning", "The mock PCB fences are nearly as tall as the switches - keep them under %.1fmm" %
            (switch_info(layout)["body_height"] - 0.3))
    if mock["fence_height"] < mock["lead_in"] + 0.5:
        add("warning", "The mock PCB fences are too low to grip the switches")

    if s["plunger_top"] - s["switch_body_top"] < 0.4:
        add("warning", "Switch plunger is very short - keycaps may bottom out on the switch body")
    if layout["switch"]["force"] not in switch_info(layout)["forces"]:
        add("error", "Switch force must be one of %s" % ", ".join(
            "%s (%dgf)" % kv for kv in switch_info(layout)["forces"].items()))
    if layout["switch"]["height"] not in switch_info(layout)["heights"]:
        add("warning", "Switch height %.1fmm is not a standard PTS645 height %s" %
            (layout["switch"]["height"], switch_info(layout)["heights"]))
    return problems
