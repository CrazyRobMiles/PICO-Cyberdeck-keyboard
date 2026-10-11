"""
Builds the keyboard PCB from a layout JSON file.

It creates the board outline, places a PTS645 switch for every key (on the
front), an SOD-123 matrix diode below each switch (also on the front), the
Raspberry Pi Pico (front or back) and the mounting holes, and connects them
all with nets: COLn -> switch -> diode anode, diode cathode -> ROWn, and
ROWn/COLn to the Pico GPIO pins in the layout. Then autoroute.py adds the
tracks (unless routing.enabled is false in the layout).

It also writes the matching schematic (see schematic.py), and the project's
own libraries for the Pico symbol and footprints, so that output/<name>/ is
a complete KiCad project, and the files for having the board made in
output/<name>/fabrication/ (see fabrication.py).

Run it in either of these ways:

1. From a command prompt, using the Python that comes with KiCad:

     "C:\\Program Files\\KiCad\\8.0\\bin\\python.exe" kicad\\build_pcb.py layouts\\cyberdeck40.json

   This writes output\\<name>\\<name>.kicad_pcb (or give a second argument
   with the output file name).

2. Inside the KiCad PCB editor: Tools > Scripting Console, then

     exec(open(r"D:\\GitHub\\PICO-Cyberdeck-keyboard\\kicad\\build_pcb.py").read())

   A file dialog asks for the layout JSON. The board is written next to the
   other outputs; open it with File > Open.
"""

import os
import sys

import pcbnew

try:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _this_dir = r"D:\GitHub\PICO-Cyberdeck-keyboard\kicad"
_repo_dir = os.path.dirname(_this_dir)
sys.path.insert(0, os.path.join(_repo_dir, "common"))

import importlib
import keyboard_layout as kl
importlib.reload(kl)
sys.path.insert(0, _this_dir)
import autoroute
importlib.reload(autoroute)
import schematic
importlib.reload(schematic)
import fabrication
importlib.reload(fabrication)

# Where on the KiCad page the top left corner of the board goes
PAGE_OFFSET = (30.0, 30.0)


def mm(v):
    return pcbnew.FromMM(v)


class Builder:

    def __init__(self, layout):
        self.layout = layout
        self.board = pcbnew.BOARD()
        self.nets = {}
        bx, by, bw, bh = kl.board_rect(layout)
        self.origin = (PAGE_OFFSET[0] - bx, PAGE_OFFSET[1] - by)
        self.footprint_dir = self.find_footprint_dir()

    # ----- helpers -----

    def pos(self, x, y):
        return pcbnew.VECTOR2I(mm(x + self.origin[0]), mm(y + self.origin[1]))

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self.nets[name] = n
        return self.nets[name]

    @staticmethod
    def find_footprint_dir():
        candidates = [os.environ.get("KICAD8_FOOTPRINT_DIR", "")]
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "..", "share", "kicad", "footprints"))
        candidates.append(r"C:\Program Files\KiCad\8.0\share\kicad\footprints")
        for c in candidates:
            if c and os.path.isdir(os.path.join(c, "Button_Switch_SMD.pretty")):
                return os.path.abspath(c)
        raise RuntimeError("Cannot find the KiCad footprint libraries - set KICAD8_FOOTPRINT_DIR")

    def load_footprint(self, lib, name):
        fp = pcbnew.FootprintLoad(os.path.join(self.footprint_dir, lib + ".pretty"), name)
        if fp is None:
            raise RuntimeError("Footprint %s:%s not found" % (lib, name))
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        return fp

    def link(self, fp, ref):
        """Link a footprint to its symbol in the schematic, which
        schematic.py gives a UUID made from the layout name and reference."""
        fp.SetPath(pcbnew.KIID_PATH("/" + schematic.symbol_uuid(self.layout, ref)))
        fp.SetSheetname("/")
        fp.SetSheetfile(self.layout["name"] + ".kicad_sch")

    def place(self, fp, x, y, rotation, back=False):
        self.board.Add(fp)
        fp.SetPosition(self.pos(x, y))
        fp.SetOrientationDegrees(rotation)
        if back:
            fp.Flip(fp.GetPosition(), False)

    def connect(self, fp, pad_number, net_name):
        for pad in fp.Pads():
            if pad.GetNumber() == str(pad_number):
                pad.SetNet(self.net(net_name))

    def edge_line(self, x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        s.SetStart(self.pos(x1, y1))
        s.SetEnd(self.pos(x2, y2))
        self.board.Add(s)

    def edge_arc(self, start, mid, end):
        s = pcbnew.PCB_SHAPE(self.board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        s.SetArcGeometry(self.pos(*start), self.pos(*mid), self.pos(*end))
        self.board.Add(s)

    def text(self, string, x, y, layer, size=1.0):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(string)
        t.SetPosition(self.pos(x, y))
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(size * 0.15))
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        self.board.Add(t)

    # ----- the board -----

    def build(self):
        self.outline()
        self.switches()
        self.controller()
        self.mounting_holes()
        self.title()
        return self.board

    def outline(self):
        x, y, w, h = kl.board_rect(self.layout)
        r = min(self.layout["board"]["corner_radius"], w / 2, h / 2)
        x1, y1 = x + w, y + h
        if r <= 0:
            for a, b in (((x, y), (x1, y)), ((x1, y), (x1, y1)), ((x1, y1), (x, y1)), ((x, y1), (x, y))):
                self.edge_line(a[0], a[1], b[0], b[1])
            return
        k = r * (1 - 0.70710678)
        self.edge_line(x + r, y, x1 - r, y)
        self.edge_arc((x1 - r, y), (x1 - k, y + k), (x1, y + r))
        self.edge_line(x1, y + r, x1, y1 - r)
        self.edge_arc((x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1))
        self.edge_line(x1 - r, y1, x + r, y1)
        self.edge_arc((x + r, y1), (x + k, y1 - k), (x, y1 - r))
        self.edge_line(x, y1 - r, x, y + r)
        self.edge_arc((x, y + r), (x + k, y + k), (x + r, y))

    def switches(self):
        sw = kl.switch_info(self.layout)
        use_diodes = self.layout["matrix"]["diodes"]
        refs = schematic.switch_refs(self.layout)
        for n, key in enumerate(self.layout["keys"]):
            row_net = "ROW%d" % key["row"]
            col_net = "COL%d" % key["col"]
            key_net = "K_%s" % key["id"] if use_diodes else row_net
            # A long key can have several switches. They are wired in
            # parallel, so pressing any of them presses the key.
            positions = kl.switch_positions(self.layout, key)
            for (sx, sy), ref in zip(positions, refs[n]):
                fp = self.load_footprint(sw["footprint_lib"], sw["footprint"])
                fp.SetReference(ref)
                self.link(fp, ref)
                fp.SetValue(key["label"] or key["id"])
                self.place(fp, sx, sy, key.get("rotation", 0))
                # Put the reference in the middle of the switch, clear of the diode
                fp.Reference().SetPosition(self.pos(sx, sy))
                fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
                fp.Reference().SetTextThickness(mm(0.12))
                self.connect(fp, 1, col_net)
                self.connect(fp, 2, key_net)
            if use_diodes:
                d = self.load_footprint(kl.DIODE["footprint_lib"], kl.DIODE["footprint"])
                d.SetReference("D%d" % (n + 1))
                self.link(d, "D%d" % (n + 1))
                d.SetValue("1N4148W")
                d.Reference().SetVisible(False)
                dx, dy, dr = kl.diode_position(self.layout, key)
                # pad 1 (cathode, the banded end) goes to the row
                self.place(d, dx, dy, dr)
                self.connect(d, 2, key_net)
                self.connect(d, 1, row_net)

    def pico_footprint(self, through_holes):
        """A Pico footprint with long rectangular pads under the castellations
        (for soldering it flat) and, optionally, through holes for headers.
        A Pico on the back of the board is soldered flat by its castellations
        and has no through holes, so that the switches can sit on top of it."""
        fp = pcbnew.FOOTPRINT(self.board)
        fp.SetFPID(pcbnew.LIB_ID(schematic.PICO_LIB_NAME,
                                 "RPi_Pico_SMD_TH" if through_holes else "RPi_Pico_SMD"))
        fp.SetReference("U1")
        fp.SetValue("Raspberry Pi Pico")
        names = {}
        for gpio, pin in kl.PICO_PIN_FOR_GPIO.items():
            names[pin] = "GP%d" % gpio
        for pin in kl.PICO_GND_PINS:
            names[pin] = "GND"
        names.update(kl.PICO_OTHER_PINS)
        for pin in range(1, 41):
            px, py = kl.pico_pin_position(pin)
            if through_holes:
                th = pcbnew.PAD(fp)
                th.SetNumber(str(pin))
                th.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
                th.SetShape(pcbnew.PAD_SHAPE_RECT if pin == 1 else pcbnew.PAD_SHAPE_OVAL)
                th.SetSize(pcbnew.VECTOR2I(mm(1.7), mm(1.7)))
                th.SetDrillSize(pcbnew.VECTOR2I(mm(1.02), mm(1.02)))
                th.SetLayerSet(pcbnew.PAD.PTHMask())
                th.SetPosition(pcbnew.VECTOR2I(mm(px), mm(py)))
                fp.Add(th)
            smd = pcbnew.PAD(fp)
            smd.SetNumber(str(pin))
            smd.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            smd.SetShape(pcbnew.PAD_SHAPE_RECT)
            smd.SetSize(pcbnew.VECTOR2I(mm(3.5), mm(1.7)))
            smd.SetLayerSet(pcbnew.PAD.SMDMask())
            smd.SetPosition(pcbnew.VECTOR2I(mm(px + (0.9 if px > 0 else -0.9)), mm(py)))
            fp.Add(smd)
            label = pcbnew.PCB_TEXT(fp)
            label.SetText(names[pin])
            label.SetLayer(pcbnew.F_Fab)
            label.SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
            label.SetTextThickness(mm(0.1))
            label.SetPosition(pcbnew.VECTOR2I(mm(px - 2.8 if px < 0 else px + 2.8), mm(py)))
            fp.Add(label)
        hw, hl = kl.PICO_WIDTH / 2, kl.PICO_LENGTH / 2
        for layer, grow, width in ((pcbnew.F_Fab, 0, 0.1), (pcbnew.F_CrtYd, 0.5, 0.05)):
            box = pcbnew.PCB_SHAPE(fp)
            box.SetShape(pcbnew.SHAPE_T_RECT)
            box.SetLayer(layer)
            box.SetWidth(mm(width))
            box.SetStart(pcbnew.VECTOR2I(mm(-hw - grow), mm(-hl - grow)))
            box.SetEnd(pcbnew.VECTOR2I(mm(hw + grow), mm(hl + grow)))
            fp.Add(box)
        # silkscreen across the ends only - the sides are covered by pads
        for y in (-hl + 0.3, hl - 0.3):
            line = pcbnew.PCB_SHAPE(fp)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetLayer(pcbnew.F_SilkS)
            line.SetWidth(mm(0.12))
            line.SetStart(pcbnew.VECTOR2I(mm(-6.5), mm(y)))
            line.SetEnd(pcbnew.VECTOR2I(mm(6.5), mm(y)))
            fp.Add(line)
        usb = pcbnew.PCB_SHAPE(fp)
        usb.SetShape(pcbnew.SHAPE_T_RECT)
        usb.SetLayer(pcbnew.F_Fab)
        usb.SetWidth(mm(0.12))
        usb.SetStart(pcbnew.VECTOR2I(mm(-4), mm(-hl - kl.PICO_USB_OVERHANG)))
        usb.SetEnd(pcbnew.VECTOR2I(mm(4), mm(-hl + 4)))
        fp.Add(usb)
        return fp, names

    def write_footprint_library(self, out_dir):
        """Save the Pico footprints into a project footprint library,
        Cyberdeck.pretty, with an fp-lib-table that makes it part of the
        project, so KiCad can find them."""
        lib = os.path.join(out_dir, schematic.PICO_LIB_NAME + ".pretty")
        io = pcbnew.PCB_IO_KICAD_SEXPR()   # works when KiCad is running headless, too
        if not os.path.isdir(lib):
            io.CreateLibrary(lib)
        for through_holes in (False, True):
            fp, _ = self.pico_footprint(through_holes)
            io.FootprintSave(lib, fp)
        with open(os.path.join(out_dir, "fp-lib-table"), "w", encoding="utf-8") as f:
            f.write('(fp_lib_table\n  (version 7)\n  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")'
                    '(options "")(descr "PICO Cyberdeck keyboard parts"))\n)\n' %
                    (schematic.PICO_LIB_NAME, schematic.PICO_LIB_NAME))

    def controller(self):
        c = self.layout["controller"]
        fp, names = self.pico_footprint(through_holes=(c["side"] == "front"))
        self.link(fp, "U1")
        self.place(fp, c["x"], c["y"], c["rotation"], back=(c["side"] == "back"))
        m = self.layout["matrix"]
        used = {}
        for r, gpio in enumerate(m["row_pins"]):
            used[kl.PICO_PIN_FOR_GPIO[gpio]] = "ROW%d" % r
        for col, gpio in enumerate(m["col_pins"]):
            used[kl.PICO_PIN_FOR_GPIO[gpio]] = "COL%d" % col
        # The other pins are unconnected - nothing on this board needs ground
        # or power, and the Pico connects its own GND pins together. They get
        # the "unconnected" nets that KiCad gives pins with a no connect flag
        # in the schematic, so the PCB matches the schematic.
        for pin in range(1, 41):
            self.connect(fp, pin, used.get(pin, "unconnected-(U1-%s-Pad%d)" % (names[pin], pin)))

    def mounting_holes(self):
        c = self.layout["case"]
        for n, hole in enumerate(self.layout["board"]["mounting_holes"]):
            fp = self.load_footprint("MountingHole", "MountingHole_2.2mm_M2")
            fp.SetReference("H%d" % (n + 1))
            fp.Reference().SetVisible(False)
            # mounting holes are not in the schematic
            fp.SetBoardOnly(True)
            pad_d = hole.get("d", c["hole_diameter"])
            if abs(pad_d - 2.2) > 0.01:
                for pad in fp.Pads():
                    pad.SetDrillSize(pcbnew.VECTOR2I(mm(pad_d), mm(pad_d)))
                    pad.SetSize(pcbnew.VECTOR2I(mm(pad_d), mm(pad_d)))
            self.place(fp, hole["x"], hole["y"], 0)

    def route(self):
        """Add the tracks with the autorouter. Returns the number of
        connections that could not be made."""
        settings = dict(self.layout["routing"])
        settings["corner_radius"] = self.layout["board"]["corner_radius"]
        x, y, w, h = kl.board_rect(self.layout)
        page_rect = (x + self.origin[0], y + self.origin[1], w, h)
        keepouts = []
        c = self.layout["controller"]
        if c["side"] == "back":
            # Keep tracks and vias out from under a Pico soldered flat on the
            # back, where its own test points and vias would touch them.
            # The pads along its edges are still reachable from outside.
            pts = kl.rect_corners(c["x"] + self.origin[0], c["y"] + self.origin[1],
                                  kl.PICO_ROW_SPACING - 3.0, kl.PICO_LENGTH, c["rotation"])
            bx0, by0, bx1, by1 = kl.bounds(pts)
            keepouts.append((bx0, by0, bx1, by1, [autoroute.BACK]))
        router = autoroute.Router(self.board, page_rect, settings, keepouts)
        order = []
        nets = self.board.GetNetsByName()
        for prefix in ("K_", "COL", "ROW"):
            order += sorted(self.board.FindNet(str(name)).GetNetCode() for name in nets.keys()
                            if str(name).startswith(prefix))
        return router.route(order)

    def title(self):
        x, y, w, h = kl.board_rect(self.layout)
        self.text(self.layout["name"], x + w / 2, y + h - 1.2, pcbnew.B_SilkS, 1.2)
        tb = self.board.GetTitleBlock()
        tb.SetTitle(self.layout["name"])
        tb.SetComment(0, "Generated by PICO-Cyberdeck-keyboard build_pcb.py")


def build(layout_path, out_path=None):
    layout = kl.load(layout_path)
    for level, msg, _ in kl.validate(layout):
        print("%s: %s" % (level.upper(), msg))
    if any(k.get("row") is None or k.get("col") is None for k in layout["keys"]):
        print("Keys have no matrix positions - assigning them automatically")
        kl.auto_matrix(layout)
    if out_path is None:
        out_dir = os.path.join(_repo_dir, "output", layout["name"])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, layout["name"] + ".kicad_pcb")
    builder = Builder(layout)
    board = builder.build()
    if layout["routing"]["enabled"]:
        failed = builder.route()
        if failed:
            print("WARNING: %d connections could not be routed - finish them by hand in KiCad" % failed)
        else:
            print("All connections routed")
    board.SetFileName(out_path)
    pcbnew.SaveBoard(out_path, board)
    out_dir = os.path.dirname(out_path)
    builder.write_footprint_library(out_dir)
    print("Written", schematic.write_schematic(layout, out_dir))
    print("Written", fabrication.write_fabrication_files(layout, board, out_path))
    print("Written %s (%d keys)" % (out_path, len(layout["keys"])))
    return out_path


def _ask_for_layout():
    import wx
    with wx.FileDialog(None, "Choose keyboard layout", defaultDir=os.path.join(_repo_dir, "layouts"),
                       wildcard="Keyboard layout (*.json)|*.json",
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
        if dlg.ShowModal() != wx.ID_OK:
            return None
        return dlg.GetPath()


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1].lower().endswith(".json"):
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
else:
    # Running inside the KiCad scripting console
    _path = _ask_for_layout()
    if _path:
        _out = build(_path)
        print("Now open it with File > Open:", _out)
