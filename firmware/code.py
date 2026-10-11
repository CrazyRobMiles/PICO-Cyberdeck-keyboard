"""
CircuitPython firmware for a PICO Cyberdeck keyboard.

It reads the same layout JSON that the designer makes, so the wiring and the
key codes always match the PCB. To install:

1. Put CircuitPython on the Pico.
2. Copy the adafruit_hid library into CIRCUITPY/lib.
3. Copy this file to CIRCUITPY/code.py.
4. Copy your layout JSON to CIRCUITPY/layout.json.

Keycodes are adafruit_hid Keycode names. A key with the keycode FN is a
function key: while it is held, keys send their fn_keycode (if they have one).

Keys with more than one switch need nothing special here: their switches are
wired in parallel, so the key is down for as long as any of them is closed.

Debouncing
----------
The matrix is scanned every 5ms, and keypad only reports a change once it
has been seen on debounce_scans scans in a row (on CircuitPython versions
that support debounce_threshold). The layout's "firmware" section sets it:
    "firmware": {"debounce_scans": 2}
"""

import json

import board
import keypad
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

SCAN_INTERVAL = 0.005


def keycode(name):
    if not name or name == "FN":
        return None
    code = getattr(Keycode, name, None)
    if code is None:
        print("Unknown keycode", name)
    return code


def make_matrix(row_pins, col_pins, debounce_scans):
    # The diode anodes are on the column side of each switch
    try:
        return keypad.KeyMatrix(row_pins, col_pins, columns_to_anodes=True,
                                interval=SCAN_INTERVAL, debounce_threshold=debounce_scans)
    except TypeError:
        # older CircuitPython without debounce_threshold
        return keypad.KeyMatrix(row_pins, col_pins, columns_to_anodes=True, interval=SCAN_INTERVAL)


def main():
    with open("/layout.json") as f:
        layout = json.load(f)

    matrix_info = layout["matrix"]
    row_pins = [getattr(board, "GP%d" % p) for p in matrix_info["row_pins"]]
    col_pins = [getattr(board, "GP%d" % p) for p in matrix_info["col_pins"]]
    columns = len(col_pins)

    # key number (as reported by keypad) -> (normal code, fn code, is fn key)
    keymap = {}
    for key in layout["keys"]:
        number = key["row"] * columns + key["col"]
        keymap[number] = (keycode(key.get("keycode")), keycode(key.get("fn_keycode")),
                          key.get("keycode") == "FN")
    debounce_scans = layout.get("firmware", {}).get("debounce_scans", 2)
    del layout

    keys = make_matrix(row_pins, col_pins, debounce_scans)
    keyboard = Keyboard(usb_hid.devices)
    fn_held = set()
    down = {}   # key number -> the code that was sent when it went down

    while True:
        event = keys.events.get()
        if event is None:
            continue
        entry = keymap.get(event.key_number)
        if entry is None:
            continue
        normal, fn, is_fn = entry
        if is_fn:
            if event.pressed:
                fn_held.add(event.key_number)
            else:
                fn_held.discard(event.key_number)
            continue
        if event.pressed:
            code = fn if (fn_held and fn is not None) else normal
            if code is not None:
                down[event.key_number] = code
                keyboard.press(code)
        else:
            # release the code that was sent, even if Fn has changed since
            code = down.pop(event.key_number, None)
            if code is not None:
                keyboard.release(code)


if __name__ == "__main__":
    main()
