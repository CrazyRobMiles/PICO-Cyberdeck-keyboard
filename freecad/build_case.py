"""
Builds the keyboard case and keytops from a layout JSON file.

Run it inside FreeCAD as a macro (Macro > Macros... > select this file >
Execute). A file dialog asks for the layout JSON. It can also run headless:

    set CYBERDECK_LAYOUT=D:\\GitHub\\PICO-Cyberdeck-keyboard\\layouts\\cyberdeck40.json
    "C:\\Program Files\\FreeCAD 1.0\\bin\\freecadcmd.exe" freecad\\build_case.py

The parts that are made (and exported as STL to output/<name>/):

- Tray.stl     the bottom of the case. The PCB sits on a ledge around its
               edge and on standoffs at the mounting holes. There is a slot
               in the wall for the Pico's USB socket.
- Plate.stl    the top plate. It has a hole for each key, a rib round its
               edge that clamps the PCB down onto the ledge, and pillars that
               the fixing screws go into. It is exported upside down, ready to
               print top face down with the rib and pillars pointing up.
- Keycaps.stl  all the keytops, spaced out and upside down for printing, top
               face on the build plate. Each keytop rests on its switch plunger
               and has a lip (the flange) round its bottom that stops it
               falling out through its hole in the plate. The lip joins the
               keytop with a tapered shoulder, which prints upside down without
               support and seats against the matching slope in the plate hole.
               With case.legend set to "inlay" (the default) each keytop has
               letter shaped holes in its top surface.
- KeycapLegends.stl
               the letters that fill those holes, in exactly the same
               positions. Load both files into the slicer together as one
               object with two parts (see "Two colour keytops" in the
               README) and give each part a different filament.
- MockPCB.stl  a printed stand-in for the real PCB, for trying out a layout
               before having boards made. It is the same shape as the PCB,
               with a low fence round each switch position to hold a PTS645
               switch where it would be soldered, and a hole under each switch
               leg so that wires can be soldered on to try the switches. The
               fences lean in at the top to grip the switches (mock_pcb in
               the layout sets how much).
- SwitchGripTest.stl
               a small plate with six switch fences, each gripping by a
               different amount (labelled in mm), for finding the grip that
               holds the switches best on your printer.

The case is assembled by putting the PCB in the tray, the keytops into the
plate, the plate on top, then fixing it all together with M2 self tapping
screws from underneath.

The document also contains reference models of the PCB, switches and Pico
so that you can check how everything fits.
"""

import json
import math
import os
import sys

import FreeCAD as App
import Mesh
import Part
from FreeCAD import Vector

try:
    _this_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _this_dir = r"D:\GitHub\PICO-Cyberdeck-keyboard\freecad"
_repo_dir = os.path.dirname(_this_dir)
if os.path.join(_repo_dir, "common") not in sys.path:
    sys.path.insert(0, os.path.join(_repo_dir, "common"))

import importlib
import keyboard_layout as kl
importlib.reload(kl)
import parts_list
importlib.reload(parts_list)

# Extra space between keytops when they are laid out for printing
PRINT_SPACING = 3.0

# The mock PCB's fences round each switch are set in the layout's mock_pcb
# section. The switch grip test plate tries these amounts of grip:
GRIP_TEST_VALUES = (0.0, 0.05, 0.1, 0.15, 0.2, 0.25)
MOCK_WIRE_HOLE = 1.0         # under each switch leg


class CaseBuilder:

    def __init__(self, layout):
        self.layout = layout
        self.case = layout["case"]
        self.z = kl.stack(layout)
        self.bx, self.by, self.bw, self.bh = kl.board_rect(layout)

    # ----- coordinate conversion -----
    # FreeCAD has Y going up, so the layout is flipped over, putting the
    # board's bottom left corner at the origin.

    def fc(self, x, y):
        return x - self.bx, (self.by + self.bh) - y

    def fc_rect(self, x, y, w, h):
        fx, fy = self.fc(x, y + h)
        return fx, fy, w, h

    # ----- shape helpers -----

    @staticmethod
    def rounded_box(x, y, w, h, z0, z1, r):
        box = Part.makeBox(w, h, z1 - z0, Vector(x, y, z0))
        r = min(r, w / 2 - 0.01, h / 2 - 0.01)
        if r > 0.05:
            vertical = [e for e in box.Edges
                        if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
            box = box.makeFillet(r, vertical)
        return box

    def placed_box(self, cx, cy, w, h, z0, z1, rotation=0, r=0):
        """A box centred on a layout position, rotated like the key."""
        box = self.rounded_box(-w / 2, -h / 2, w, h, z0, z1, r)
        box.rotate(Vector(0, 0, 0), Vector(0, 0, 1), rotation)
        fx, fy = self.fc(cx, cy)
        box.translate(Vector(fx, fy, 0))
        return box

    def cylinder(self, x, y, d, z0, z1):
        fx, fy = self.fc(x, y)
        return Part.makeCylinder(d / 2, z1 - z0, Vector(fx, fy, z0))

    def board_box(self, grow, z0, z1):
        r = max(0.0, self.layout["board"]["corner_radius"] + grow)
        return self.rounded_box(-grow, -grow, self.bw + 2 * grow, self.bh + 2 * grow, z0, z1, r)

    def pico_box(self, grow, z0, z1):
        c = self.layout["controller"]
        return self.placed_box(c["x"], c["y"], kl.PICO_WIDTH + 2 * grow, kl.PICO_LENGTH + 2 * grow,
                               z0, z1, c["rotation"])

    def usb_cutout(self, z_centre):
        """A slot from the Pico USB socket out through the wall."""
        (ux, uy), (dx, dy) = kl.pico_usb(self.layout)
        length = 20.0
        cx, cy = ux + dx * (length / 2 - 3), uy + dy * (length / 2 - 3)
        rotation = self.layout["controller"]["rotation"]
        return self.placed_box(cx, cy, 12.0, length, z_centre - 4.0, z_centre + 4.0, rotation, r=1.0)

    # ----- the parts -----

    def tray(self):
        c, z = self.case, self.z
        wall_out = c["clearance"] + c["wall"]
        tray = self.board_box(wall_out, z["case_bottom"], z["plate_bottom"])
        tray = tray.cut(self.board_box(c["clearance"], z["floor_top"], z["plate_bottom"] + 1))
        # ledge round the edge of the cavity for the PCB to sit on
        ledge = self.board_box(c["clearance"] + 0.01, z["floor_top"] - 0.01, z["pcb_bottom"])
        ledge = ledge.cut(self.board_box(-c["ledge"], z["floor_top"] - 1, z["pcb_bottom"] + 1))
        if self.layout["controller"]["side"] == "back":
            ledge = ledge.cut(self.pico_box(0.5, z["floor_top"] - 1, z["pcb_bottom"] + 1))
        tray = tray.fuse(ledge)
        for hole in self.layout["board"]["mounting_holes"]:
            tray = tray.fuse(self.cylinder(hole["x"], hole["y"], c["standoff_diameter"],
                                           z["floor_top"] - 0.01, z["pcb_bottom"]))
        for hole in self.layout["board"]["mounting_holes"]:
            # clearance hole for the screw, and a countersink for its head
            tray = tray.cut(self.cylinder(hole["x"], hole["y"], c["hole_diameter"] + 0.2,
                                          z["case_bottom"] - 1, z["pcb_bottom"] + 1))
            fx, fy = self.fc(hole["x"], hole["y"])
            cone = Part.makeCone(2.1, (c["hole_diameter"] + 0.2) / 2, 1.0, Vector(fx, fy, z["case_bottom"] - 0.01))
            tray = tray.cut(cone)
        if self.layout["controller"]["side"] == "back":
            usb_z = -(kl.PICO_THICKNESS + kl.PICO_PART_HEIGHT / 2)
        else:
            usb_z = z["pcb_top"] + kl.PICO_THICKNESS + kl.PICO_PART_HEIGHT / 2
        tray = tray.cut(self.usb_cutout(usb_z))
        return tray.removeSplitter()

    def plate(self):
        c, z = self.case, self.z
        wall_out = c["clearance"] + c["wall"]
        plate = self.board_box(wall_out, z["plate_bottom"], z["plate_top"])
        # rib that fits inside the tray walls and presses on the edge of the PCB
        rib = self.board_box(c["clearance"] - 0.2, z["pcb_top"], z["plate_bottom"] + 0.01)
        rib = rib.cut(self.board_box(-c["ledge"], z["pcb_top"] - 1, z["plate_bottom"] + 1))
        if self.layout["controller"]["side"] == "front":
            rib = rib.cut(self.pico_box(0.5, z["pcb_top"] - 1, z["plate_bottom"] + 1))
        plate = plate.fuse(rib)
        for hole in self.layout["board"]["mounting_holes"]:
            plate = plate.fuse(self.cylinder(hole["x"], hole["y"], c["standoff_diameter"],
                                             z["pcb_top"], z["plate_bottom"] + 0.01))
        # Each hole is the shape of its keytop, key_clearance bigger all
        # round, so the lower part of the hole slopes like the keytop's
        # shoulder, which seats against it.
        slab = Part.makeBox(10000, 10000, z["plate_top"] + 2 - z["plate_bottom"],
                            Vector(-5000, -5000, z["plate_bottom"] - 0.01))
        holes = [self.key_profile(key, c["key_clearance"], z["plate_top"] + 1, c["plunger_gap"]).common(slab)
                 for key in self.layout["keys"]]
        if holes:
            plate = plate.cut(Part.makeCompound(holes))
        for hole in self.layout["board"]["mounting_holes"]:
            plate = plate.cut(self.cylinder(hole["x"], hole["y"], c["screw_pilot"],
                                            z["pcb_top"] - 1, z["plate_top"] - 0.8))
        if self.layout["controller"]["side"] == "front":
            # window for a Pico on the front, and a slot for its USB socket
            plate = plate.cut(self.pico_box(0.5, z["pcb_top"] - 1, z["plate_top"] + 1))
            plate = plate.cut(self.usb_cutout(z["pcb_top"] + kl.PICO_THICKNESS + kl.PICO_PART_HEIGHT / 2))
        return plate.removeSplitter()

    @staticmethod
    def rounded_rect_wire(w, h, r, z):
        """A rounded rectangle centred on the origin at height z, always made
        of the same eight edges so that two of them can be lofted together."""
        x, y = w / 2, h / 2
        k = r * (1 - math.sqrt(0.5))
        V = lambda px, py: Vector(px, py, z)
        edges = [
            Part.makeLine(V(-x + r, -y), V(x - r, -y)),
            Part.Arc(V(x - r, -y), V(x - k, -y + k), V(x, -y + r)).toShape(),
            Part.makeLine(V(x, -y + r), V(x, y - r)),
            Part.Arc(V(x, y - r), V(x - k, y - k), V(x - r, y)).toShape(),
            Part.makeLine(V(x - r, y), V(-x + r, y)),
            Part.Arc(V(-x + r, y), V(-x + k, y - k), V(-x, y - r)).toShape(),
            Part.makeLine(V(-x, y - r), V(-x, -y + r)),
            Part.Arc(V(-x, -y + r), V(-x + k, -y + k), V(-x + r, -y)).toShape(),
        ]
        return Part.Wire(edges)

    def key_profile(self, key, grow, z_top, lift=0.0):
        """The tapered shoulder and the body of a keytop, made bigger all
        round by grow, from the top of the flange's straight band up to
        z_top, and raised by lift. The shoulder slopes in from the flange to
        the body at flange_angle, so it prints upside down without support."""
        c, z = self.case, self.z
        w, h = kl.keycap_size(self.layout, key)
        r = self.cap_radius(key) + grow
        f = c["flange"]
        low = self.rounded_rect_wire(w + 2 * (f + grow), h + 2 * (f + grow), r + f, z["flange_top"] + lift)
        high = self.rounded_rect_wire(w + 2 * grow, h + 2 * grow, r, z["shoulder_top"] + lift)
        shoulder = Part.makeLoft([low, high], True, True)
        body = self.rounded_box(-w / 2 - grow, -h / 2 - grow, w + 2 * grow, h + 2 * grow,
                                z["shoulder_top"] + lift - 0.01, z_top, r)
        shape = shoulder.fuse(body).removeSplitter()
        return self.local_shape(shape, key["x"], key["y"], key.get("rotation", 0))

    def cap_radius(self, key):
        w, h = kl.keycap_size(self.layout, key)
        return min(1.0, min(w, h) / 4)

    def keycap(self, key):
        """One keytop, in its assembled position. Returns (keytop, letters).
        letters is None unless the legend is "inlay", when it is the solid
        letters that fill the letter shaped holes in the top of the keytop."""
        c, z = self.case, self.z
        rot = key.get("rotation", 0)
        w, h = kl.keycap_size(self.layout, key)
        fw, fh = kl.keycap_flange_size(self.layout, key)
        r = self.cap_radius(key)
        # a straight band round the bottom, then the tapered shoulder and the body
        cap = self.placed_box(key["x"], key["y"], fw, fh, z["cap_bottom"], z["flange_top"], rot, r + c["flange"])
        cap = cap.fuse(self.key_profile(key, 0, z["cap_top"]))
        letters = None
        if c["legend"] in ("engrave", "inlay") and key.get("label"):
            inlay = c["legend"] == "inlay"
            # An engraving is cut with letters that stick out of the top, but
            # inlaid letters must be exactly the same shape as their holes.
            legend = self.legend(key, w, h, c["legend_depth"] + (0 if inlay else 1))
            if legend is not None:
                cap = cap.cut(legend)
                if inlay:
                    letters = legend
        return cap.removeSplitter(), letters

    def legend(self, key, w, h, height):
        """The key's label as solid letters, centred on the keytop, with
        their top face legend_depth above the keytop surface less height."""
        c, z = self.case, self.z
        font = c["font"]
        if not os.path.exists(font):
            print("Font %s not found - keytops have no legends" % font)
            c["legend"] = "none"
            return None
        def make_text(size):
            faces = []
            for wires in Part.makeWireString(key["label"], font, size, 0):
                if wires:
                    faces.append(Part.makeFace(wires, "Part::FaceMakerBullseye"))
            return Part.makeCompound(faces)

        try:
            size = h * 0.45
            for _ in range(6):
                text = make_text(size)
                bb = text.BoundBox
                if bb.XLength <= w * 0.8 and bb.YLength <= h * 0.8:
                    break
                size *= 0.8
            # Small glyphs such as . , and ^ are too tiny to read (or print)
            # at letter size, so make them bigger
            smallest = 0.3 * h
            if max(bb.XLength, bb.YLength) < smallest:
                size *= min(2.5, smallest / max(bb.XLength, bb.YLength, 0.01))
                text = make_text(size)
                bb = text.BoundBox
            text.translate(Vector(-bb.Center.x, -bb.Center.y, 0))
            solid = text.extrude(Vector(0, 0, height))
            solid.rotate(Vector(0, 0, 0), Vector(0, 0, 1), key.get("rotation", 0))
            fx, fy = self.fc(key["x"], key["y"])
            solid.translate(Vector(fx, fy, z["cap_top"] - c["legend_depth"]))
            return solid
        except Exception as e:
            print("Could not make legend for %s: %s" % (key["id"], e))
            return None

    def print_layout(self, shapes):
        """Keytops (or their letters) turned upside down, so that the top of
        the keytops is on the build plate at Z=0, and spaced apart for
        printing. This gives a smooth top surface, and the tapered shoulder
        prints without support. shapes holds one shape (or None) per key.
        The keytops and letters are moved in exactly the same way, so that
        the letters stay in their holes."""
        out = []
        g = self.layout["grid"]
        sx = (g["pitch_x"] + PRINT_SPACING) / g["pitch_x"]
        sy = (g["pitch_y"] + PRINT_SPACING) / g["pitch_y"]
        for key, shape in zip(self.layout["keys"], shapes):
            if shape is None:
                continue
            moved = shape.copy()
            fx, fy = self.fc(key["x"], key["y"])
            moved.translate(Vector(fx * (sx - 1), fy * (sy - 1), 0))
            # turn over about the X axis, top face down at Z=0
            moved.rotate(Vector(0, 0, 0), Vector(1, 0, 0), 180)
            moved.translate(Vector(0, 0, self.z["cap_top"]))
            out.append(moved)
        return Part.makeCompound(out)

    # ----- reference models (not printed) -----

    def pcb(self):
        z = self.z
        pcb = self.board_box(0, z["pcb_bottom"], z["pcb_top"])
        for hole in self.layout["board"]["mounting_holes"]:
            pcb = pcb.cut(self.cylinder(hole["x"], hole["y"], hole["d"], -1, z["pcb_top"] + 1))
        return pcb

    def switches(self):
        z = self.z
        sw = kl.switch_info(self.layout)
        parts = []
        for key in self.layout["keys"]:
            for sx, sy in kl.switch_positions(self.layout, key):
                parts.append(self.placed_box(sx, sy, sw["body"], sw["body"], z["pcb_top"],
                                             z["switch_body_top"], key.get("rotation", 0)))
                parts.append(self.cylinder(sx, sy, sw["plunger_diameter"], z["switch_body_top"],
                                           z["plunger_top"]))
        return Part.makeCompound(parts)

    def local_shape(self, shape, x, y, rotation):
        """Move a shape built round the origin to a layout position."""
        shape.rotate(Vector(0, 0, 0), Vector(0, 0, 1), rotation)
        fx, fy = self.fc(x, y)
        shape.translate(Vector(fx, fy, 0))
        return shape

    def mock_pcb(self):
        """A printable stand-in for the PCB. Each switch sits on its top
        surface, as if soldered, held in place by a fence round its body. The
        fence has gaps for the switch legs, which sit over holes that wires
        can be threaded through and soldered to."""
        z = self.z
        board = self.board_box(0, z["pcb_bottom"], z["pcb_top"])
        for hole in self.layout["board"]["mounting_holes"]:
            board = board.cut(self.cylinder(hole["x"], hole["y"], hole["d"] + 0.2, -1, z["pcb_top"] + 1))
        fence = self.switch_fence(self.layout["mock_pcb"]["grip"], z["pcb_top"])
        fences, holes = [], []
        for key in self.layout["keys"]:
            rot = key.get("rotation", 0)
            for sx, sy in kl.switch_positions(self.layout, key):
                fences.append(self.local_shape(fence.copy(), sx, sy, rot))
                for hole in self.wire_holes(z["pcb_top"]):
                    holes.append(self.local_shape(hole, sx, sy, rot))
        board = board.fuse(fences)
        board = board.cut(Part.makeCompound(holes))
        return board.removeSplitter()

    @staticmethod
    def wire_holes(z_top):
        """Holes under the four switch legs, round the origin."""
        return [Part.makeCylinder(MOCK_WIRE_HOLE / 2, z_top + 2, Vector(px, py, -1))
                for px in (-3.98, 3.98) for py in (-2.25, 2.25)]

    @staticmethod
    def square_wire(half, z):
        pts = [Vector(-half, -half, z), Vector(half, -half, z), Vector(half, half, z),
               Vector(-half, half, z), Vector(-half, -half, z)]
        return Part.makePolygon(pts)

    def switch_fence(self, grip, z_base):
        """A fence that holds a switch, round the origin, standing on z_base.
        Its inside leans in, from body_clearance round the switch body at the
        bottom to grip smaller than the body near the top, so the walls flex
        and hold the switch. A chamfer at the top guides the switch in. The
        sides the legs come out of (+-X, at +-2.25mm) have gaps for them."""
        m = self.layout["mock_pcb"]
        body = kl.switch_info(self.layout)["body"] / 2
        bottom = body + m["body_clearance"]
        top = body - grip
        outer = bottom + m["fence_wall"]
        z_top = z_base + m["fence_height"]
        z_chamfer = z_top - m["lead_in"]
        ring = Part.makeBox(2 * outer, 2 * outer, m["fence_height"] + 0.01,
                            Vector(-outer, -outer, z_base - 0.01))
        lean = Part.makeLoft([self.square_wire(bottom, z_base - 0.02), self.square_wire(top, z_chamfer)], True, True)
        chamfer = Part.makeLoft([self.square_wire(top, z_chamfer),
                                 self.square_wire(top + m["lead_in"] + 0.01, z_top + 0.01)], True, True)
        fence = ring.cut(lean.fuse(chamfer))
        # gaps for the legs, which leave the body at board level
        for sx in (-1, 1):
            for sy in (-1, 1):
                x0 = body - 0.5 if sx > 0 else -outer - 1
                y0 = 1.25 if sy > 0 else -2.85
                fence = fence.cut(Part.makeBox(outer + 1 - (body - 0.5), 1.6, m["fence_height"] + 1,
                                               Vector(x0, y0, z_base - 0.5)))
        return fence.removeSplitter()

    def grip_test_plate(self):
        """A small plate with a fence for each grip amount in GRIP_TEST_VALUES,
        labelled with the amount, for finding the grip that holds a switch
        best on your printer. Then set mock_pcb.grip in the layout."""
        thickness = self.layout["board"]["thickness"]
        pitch = 12.0
        width = pitch * len(GRIP_TEST_VALUES)
        depth = 20.0
        plate = self.rounded_box(0, 0, width, depth, 0, thickness, 2.0)
        fences, holes = [], []
        for n, grip in enumerate(GRIP_TEST_VALUES):
            x, y = pitch * (n + 0.5), 12.5
            fence = self.switch_fence(grip, thickness)
            fence.translate(Vector(x, y, 0))
            fences.append(fence)
            for hole in self.wire_holes(thickness):
                hole.translate(Vector(x, y, 0))
                holes.append(hole)
            label = self.label_solid("%g" % grip, x, 3.2, thickness, 3.0, 0.6)
            if label is not None:
                fences.append(label)
        plate = plate.fuse(fences).cut(Part.makeCompound(holes))
        return plate.removeSplitter()

    def label_solid(self, text, x, y, z, size, height):
        """Raised text centred on (x, y), standing on z."""
        font = self.case["font"]
        if not os.path.exists(font):
            return None
        faces = []
        for wires in Part.makeWireString(text, font, size, 0):
            if wires:
                faces.append(Part.makeFace(wires, "Part::FaceMakerBullseye"))
        shape = Part.makeCompound(faces)
        bb = shape.BoundBox
        shape.translate(Vector(x - bb.Center.x, y - bb.Center.y, z - 0.01))
        return shape.extrude(Vector(0, 0, height + 0.01))

    def pico(self):
        z = self.z
        if self.layout["controller"]["side"] == "back":
            return self.pico_box(0, -kl.PICO_THICKNESS, 0)
        return self.pico_box(0, z["pcb_top"], z["pcb_top"] + kl.PICO_THICKNESS)


def add_part(doc, name, shape, colour=None, visible=True):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if App.GuiUp:
        if colour:
            obj.ViewObject.ShapeColor = colour
        obj.ViewObject.Visibility = visible
    return obj


def build(layout_path):
    layout = kl.load(layout_path)
    problems = kl.validate(layout)
    for level, msg, _ in problems:
        print("%s: %s" % (level.upper(), msg))
    out_dir = os.path.join(_repo_dir, "output", layout["name"])
    os.makedirs(out_dir, exist_ok=True)

    doc_name = "Keyboard_" + "".join(ch if ch.isalnum() else "_" for ch in layout["name"])
    if doc_name in App.listDocuments():
        App.closeDocument(doc_name)
    doc = App.newDocument(doc_name)

    b = CaseBuilder(layout)
    print("Building tray")
    tray = add_part(doc, "Tray", b.tray(), (0.25, 0.25, 0.3))
    print("Building plate")
    plate = add_part(doc, "Plate", b.plate(), (0.3, 0.3, 0.35))
    print("Building %d keycaps" % len(layout["keys"]))
    caps, letters = zip(*[b.keycap(k) for k in layout["keys"]])
    add_part(doc, "Keycaps", Part.makeCompound(caps), (0.85, 0.85, 0.8))
    print_obj = add_part(doc, "KeycapsForPrinting", b.print_layout(caps), visible=False)
    have_letters = any(l is not None for l in letters)
    if have_letters:
        add_part(doc, "KeycapLegends", Part.makeCompound([l for l in letters if l is not None]),
                 (0.1, 0.1, 0.1))
        letters_obj = add_part(doc, "KeycapLegendsForPrinting", b.print_layout(letters), visible=False)
    add_part(doc, "PCB", b.pcb(), (0.1, 0.5, 0.2))
    add_part(doc, "Switches", b.switches(), (0.2, 0.2, 0.2))
    print("Building mock PCB")
    mock = b.mock_pcb()
    add_part(doc, "MockPCB", mock, (0.8, 0.5, 0.2), visible=False)
    mock_print = mock.copy()
    mock_print.translate(Vector(0, 0, -mock_print.BoundBox.ZMin))
    mock_print_obj = add_part(doc, "MockPCBForPrinting", mock_print, visible=False)
    add_part(doc, "Pico", b.pico(), (0.1, 0.6, 0.1))
    doc.recompute()

    Mesh.export([tray], os.path.join(out_dir, "Tray.stl"))
    # The rib and pillars hang below the plate, so it prints upside down
    plate_print = plate.Shape.copy()
    plate_print.rotate(plate_print.BoundBox.Center, Vector(1, 0, 0), 180)
    plate_print.translate(Vector(0, 0, -plate_print.BoundBox.ZMin))
    plate_print_obj = add_part(doc, "PlateForPrinting", plate_print, visible=False)
    Mesh.export([plate_print_obj], os.path.join(out_dir, "Plate.stl"))
    Mesh.export([print_obj], os.path.join(out_dir, "Keycaps.stl"))
    Mesh.export([mock_print_obj], os.path.join(out_dir, "MockPCB.stl"))
    grip_obj = add_part(doc, "SwitchGripTest", b.grip_test_plate(), visible=False)
    Mesh.export([grip_obj], os.path.join(out_dir, "SwitchGripTest.stl"))
    legends_path = os.path.join(out_dir, "KeycapLegends.stl")
    if have_letters:
        Mesh.export([letters_obj], legends_path)
    elif os.path.exists(legends_path):
        os.remove(legends_path)   # left over from an earlier inlay build
    doc.saveAs(os.path.join(out_dir, layout["name"] + "_case.FCStd"))

    # Record how much plastic each print needs, for the parts list
    volumes = {"Tray.stl": tray.Shape.Volume, "Plate.stl": plate.Shape.Volume,
               "Keycaps.stl": print_obj.Shape.Volume, "MockPCB.stl": mock_print_obj.Shape.Volume,
               "SwitchGripTest.stl": grip_obj.Shape.Volume}
    if have_letters:
        volumes["KeycapLegends.stl"] = letters_obj.Shape.Volume
    with open(os.path.join(out_dir, "prints.json"), "w", encoding="utf-8") as f:
        json.dump({k: round(v, 1) for k, v in volumes.items()}, f, indent=2)
    for written in parts_list.write_parts_list(layout, out_dir, volumes):
        print("Written", written)

    w, h, d = kl.case_size(layout)
    screw, room = kl.screw_length(layout)
    print("Case is %.1f x %.1f x %.1fmm" % (w, h, d))
    print("Fixing screws: M2 x %smm self tapping (up to %.1fmm fits)" % (screw, room))
    print("STL files written to", out_dir)

    if App.GuiUp:
        import FreeCADGui
        FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
        FreeCADGui.SendMsgToActiveView("ViewFit")
    return doc


def _ask_for_layout():
    if not App.GuiUp:
        return None
    from PySide import QtGui
    path, _ = QtGui.QFileDialog.getOpenFileName(None, "Choose keyboard layout",
                                                os.path.join(_repo_dir, "layouts"),
                                                "Keyboard layout (*.json)")
    return path or None


_layout_path = os.environ.get("CYBERDECK_LAYOUT") or _ask_for_layout()
if _layout_path:
    build(_layout_path)
else:
    print("No layout chosen (set CYBERDECK_LAYOUT when running headless)")
