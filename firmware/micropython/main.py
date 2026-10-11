"""
MicroPython firmware for a PICO Cyberdeck keyboard.

This does the same job as the CircuitPython firmware (firmware/code.py) and
reads the same layout JSON, so the wiring and key codes always match the PCB.

It needs MicroPython 1.23 or later, which can act as a USB device, plus the
usb-device-keyboard package from micropython-lib. To install:

1. Put MicroPython (1.23 or later) on the Pico.
2. Install the keyboard driver:
       mpremote mip install usb-device-keyboard
3. Copy this file and your layout to the Pico:
       mpremote cp firmware/micropython/main.py :main.py
       mpremote cp layouts/switch_test.json :layout.json
4. Reset the Pico. It becomes a USB keyboard, and keeps its USB serial port
   so that mpremote and Thonny can still connect (press Ctrl-C to stop it).

Keycodes in the layout are the adafruit_hid Keycode names used by the
designer, translated here into HID codes. A key with the keycode FN is a
function key: while it is held, keys send their fn_keycode (if they have one).

Scanning and debouncing
-----------------------
Every SCAN_MS each row is driven low in turn, and the columns (pulled up)
are read. A pressed key pulls its column low through its diode, whose anode
is on the column side. A key only changes state once it has read the same on
debounce_scans scans in a row. The layout's "firmware" section sets it:
    "firmware": {"debounce_scans": 2}

Keys with more than one switch need nothing special here: their switches are
wired in parallel, so the key is down for as long as any of them is closed.
"""

import json
import time

import usb.device
from machine import Pin
from usb.device.keyboard import KeyboardInterface

SCAN_MS = 5

# HID usage codes for the adafruit_hid Keycode names used in the layout.
# Modifiers are negative, as usb.device.keyboard expects.
HID_CODES = {
    "ENTER": 0x28, "ESCAPE": 0x29, "BACKSPACE": 0x2A, "TAB": 0x2B, "SPACE": 0x2C, "SPACEBAR": 0x2C,
    "MINUS": 0x2D, "EQUALS": 0x2E, "LEFT_BRACKET": 0x2F, "RIGHT_BRACKET": 0x30, "BACKSLASH": 0x31,
    "POUND": 0x32, "SEMICOLON": 0x33, "QUOTE": 0x34, "GRAVE_ACCENT": 0x35, "COMMA": 0x36,
    "PERIOD": 0x37, "FORWARD_SLASH": 0x38, "CAPS_LOCK": 0x39,
    "PRINT_SCREEN": 0x46, "SCROLL_LOCK": 0x47, "PAUSE": 0x48, "INSERT": 0x49, "HOME": 0x4A,
    "PAGE_UP": 0x4B, "DELETE": 0x4C, "END": 0x4D, "PAGE_DOWN": 0x4E, "RIGHT_ARROW": 0x4F,
    "LEFT_ARROW": 0x50, "DOWN_ARROW": 0x51, "UP_ARROW": 0x52, "APPLICATION": 0x65,
    "LEFT_CONTROL": -0x01, "LEFT_SHIFT": -0x02, "LEFT_ALT": -0x04, "LEFT_GUI": -0x08,
    "RIGHT_CONTROL": -0x10, "RIGHT_SHIFT": -0x20, "RIGHT_ALT": -0x40, "RIGHT_GUI": -0x80,
}
for _n, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    HID_CODES[_c] = 0x04 + _n
for _n, _name in enumerate(("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "ZERO")):
    HID_CODES[_name] = 0x1E + _n
for _n in range(12):
    HID_CODES["F%d" % (_n + 1)] = 0x3A + _n


def keycode(name):
    if not name or name == "FN":
        return None
    code = HID_CODES.get(name)
    if code is None:
        print("Unknown keycode", name)
    return code


class Matrix:
    """Scans the key matrix and debounces it. scan() returns a list of
    (key number, pressed) changes, numbered row * columns + column."""

    def __init__(self, row_gpio, col_gpio, debounce_scans):
        self.rows = [Pin(g, Pin.OUT, value=1) for g in row_gpio]
        self.cols = [Pin(g, Pin.IN, Pin.PULL_UP) for g in col_gpio]
        size = len(self.rows) * len(self.cols)
        self.state = bytearray(size)      # debounced state, 1 = pressed
        self.count = bytearray(size)      # scans the raw state has disagreed with it
        self.debounce_scans = max(1, debounce_scans)

    def scan(self):
        changes = []
        n = 0
        for row in self.rows:
            row.value(0)
            time.sleep_us(5)              # let the column lines settle
            for col in self.cols:
                raw = 1 if col.value() == 0 else 0
                if raw == self.state[n]:
                    self.count[n] = 0
                else:
                    self.count[n] += 1
                    if self.count[n] >= self.debounce_scans:
                        self.state[n] = raw
                        self.count[n] = 0
                        changes.append((n, raw == 1))
                n += 1
            row.value(1)
        return changes


class KeyHandler:
    """Keeps track of which keys are down. down_codes() gives the keys to send."""

    def __init__(self, keymap):
        self.keymap = keymap              # key number -> (normal code, fn code, is fn key)
        self.down = {}                    # key number -> the code chosen when it went down
        self.fn_held = set()

    def pressed(self, number):
        entry = self.keymap.get(number)
        if entry is None or number in self.down:
            return
        normal, fn, is_fn = entry
        if is_fn:
            self.fn_held.add(number)
            self.down[number] = None
            return
        self.down[number] = fn if (self.fn_held and fn is not None) else normal

    def released(self, number):
        # the code chosen when the key went down is released, even if Fn has changed since
        self.fn_held.discard(number)
        self.down.pop(number, None)

    def down_codes(self):
        return [code for code in self.down.values() if code is not None]


def main():
    with open("/layout.json") as f:
        layout = json.load(f)

    matrix_info = layout["matrix"]
    columns = len(matrix_info["col_pins"])
    keymap = {}
    for key in layout["keys"]:
        number = key["row"] * columns + key["col"]
        keymap[number] = (keycode(key.get("keycode")), keycode(key.get("fn_keycode")),
                          key.get("keycode") == "FN")
    debounce_scans = layout.get("firmware", {}).get("debounce_scans", 2)
    matrix = Matrix(matrix_info["row_pins"], matrix_info["col_pins"], debounce_scans)
    handler = KeyHandler(keymap)
    del layout

    keyboard = KeyboardInterface()
    # builtin_driver keeps the USB serial port, so the REPL still works
    usb.device.get().init(keyboard, builtin_driver=True)

    sent = None
    next_scan = time.ticks_ms()
    while True:
        for number, is_pressed in matrix.scan():
            if is_pressed:
                handler.pressed(number)
            else:
                handler.released(number)
        if keyboard.is_open():
            codes = handler.down_codes()
            if codes != sent and keyboard.send_keys(codes):
                sent = codes
        next_scan = time.ticks_add(next_scan, SCAN_MS)
        wait = time.ticks_diff(next_scan, time.ticks_ms())
        if wait > 0:
            time.sleep_ms(wait)
        else:
            next_scan = time.ticks_ms()


main()
