"""
PICO Cyberdeck keyboard designer.

A GUI for creating the layout JSON files that kicad/build_pcb.py and
freecad/build_case.py turn into a PCB and a 3D printable case.

Run it with any Python 3 (it only needs tkinter, which comes with Python):

    python designer/keyboard_designer.py [layout.json]

Mouse
    click                 select a key, mounting hole or the Pico
    shift+click           add to / remove from the selection
    drag                  move the selection (snaps to the snap distance)
    drag on empty space   select the keys in a rectangle
    double click          add a key
    right click           menu (add key, add mounting hole, delete, rotate)
    wheel                 zoom
Keys
    arrows                nudge the selection
    Delete                delete the selection
    Ctrl+D                duplicate the selected keys
    [ and ]               rotate the selected keys by 5 degrees
    Ctrl+Z / Ctrl+Y       undo / redo
    Ctrl+S                save
"""

import copy
import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

_this_dir = os.path.dirname(os.path.abspath(__file__))
_repo_dir = os.path.dirname(_this_dir)
sys.path.insert(0, os.path.join(_repo_dir, "common"))

import keyboard_layout as kl
import parts_list

COLOURS = {
    "background": "#20242a",
    "case": "#3a3f48",
    "board": "#1d6b3a",
    "board_edge": "#5fd38d",
    "key_area": "#2a8a4c",
    "cap": "#efe9dc",
    "cap_text": "#202020",
    "switch": "#555555",
    "diode": "#303030",
    "pico_back": "#7fb8ff",
    "pico_front": "#2f7d32",
    "hole": "#c0c0c0",
    "selected": "#2f9bff",
    "error": "#ff4040",
    "usb": "#e0e0e0",
}


def get_path(d, path):
    for p in path:
        d = d[p]
    return d


def set_path(d, path, value):
    for p in path[:-1]:
        d = d[p]
    d[path[-1]] = value


def parse_switches(text):
    """Switch offsets along a key, in key units, e.g. "-0.5, 0.5"."""
    return kl.parse_offsets(text) or [0.0]


def format_value(value):
    if isinstance(value, list):
        return ", ".join("%g" % v for v in value)
    return str(value)


def parse_pins(text):
    pins = []
    for part in text.replace(";", ",").split(","):
        part = part.strip().upper().replace("GP", "")
        if part:
            pins.append(int(part))
    return pins


def format_pins(pins):
    return ", ".join("GP%d" % p for p in pins)


class StaggerChooser(ttk.Frame):
    """A preset list plus an entry for the stagger of each row, in key units."""

    def __init__(self, parent, preset="None (ortholinear)"):
        super().__init__(parent)
        ttk.Label(self, text="Row stagger").grid(row=0, column=0, sticky="w")
        self.preset = tk.StringVar(value=preset)
        box = ttk.Combobox(self, textvariable=self.preset, values=list(kl.STAGGER_PRESETS),
                           state="readonly", width=36)
        box.grid(row=0, column=1, sticky="w", padx=4)
        box.bind("<<ComboboxSelected>>", self.preset_chosen)
        ttk.Label(self, text="Units per row").grid(row=1, column=0, sticky="w")
        self.offsets = tk.StringVar()
        ttk.Entry(self, textvariable=self.offsets, width=38).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Label(self, foreground="#777", text=(
            "How far each row moves right, top row first, e.g. 0, 0.25, 0.75")).grid(
            row=2, column=0, columnspan=2, sticky="w")
        self.preset_chosen()

    def preset_chosen(self, event=None):
        self.offsets.set(", ".join("%g" % v for v in kl.STAGGER_PRESETS[self.preset.get()]))

    def get(self):
        return kl.parse_offsets(self.offsets.get())


class StaggerDialog(tk.Toplevel):
    """Stagger the rows of keys that are already in the layout."""

    def __init__(self, parent, count, selected):
        super().__init__(parent)
        self.title("Stagger rows")
        self.result = None
        self.transient(parent)
        ttk.Label(self, text="Move the rows of the %d %skeys:" % (count, "selected " if selected else "")
                  ).pack(padx=8, pady=6, anchor="w")
        self.chooser = StaggerChooser(self, "Standard (QWERTY, ASDF, ZXCV rows)")
        self.chooser.pack(padx=8, anchor="w")
        buttons = ttk.Frame(self)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="OK", command=self.ok).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        self.grab_set()

    def ok(self):
        try:
            self.result = self.chooser.get()
        except ValueError:
            messagebox.showerror("Stagger rows", "The stagger should be numbers separated by commas", parent=self)
            return
        self.destroy()


class RowsDialog(tk.Toplevel):
    """Type in rows of keys to add to (or replace) the layout."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add rows of keys")
        self.result = None
        self.transient(parent)
        ttk.Label(self, justify="left", text=(
            "One line per row. Separate keys with spaces.\n"
            "Give a key a width with a colon:  Space:2\n"
            "An underscore is a 1u gap, _:0.5 a half unit gap.\n"
            "Stagger rows like a normal keyboard by making the first key wider\n"
            "(Tab:1.5, Caps:1.75, Shift:2.25), or by choosing a row stagger below.")).pack(padx=8, pady=6, anchor="w")
        self.text = tk.Text(self, width=70, height=8, font=("Consolas", 11))
        self.text.insert("1.0", "Esc Q W E R T Y U I O P Bksp\n"
                                "Tab A S D F G H J K L ; Ent\n"
                                "Shift Z X C V B N M , . / '\n"
                                "Ctrl Fn Gui Alt _ Space:2 _ Left Down Up Right\n")
        self.text.pack(padx=8, fill="both", expand=True)
        self.stagger = StaggerChooser(self)
        self.stagger.pack(padx=8, pady=4, anchor="w")
        self.replace = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Replace the existing keys", variable=self.replace).pack(padx=8, anchor="w")
        buttons = ttk.Frame(self)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="OK", command=self.ok).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        self.grab_set()
        self.text.focus_set()

    def ok(self):
        try:
            self.result = (kl.parse_rows(self.text.get("1.0", "end")), self.replace.get(), self.stagger.get())
        except ValueError:
            messagebox.showerror("Add rows", "Key widths and the stagger should be numbers", parent=self)
            return
        self.destroy()


class Designer(tk.Tk):

    def __init__(self, path=None):
        super().__init__()
        self.geometry("1400x860")
        self.layout = kl.example_layout()
        self.path = None
        self.selection = set()
        self.undo_stack = []
        self.redo_stack = []
        self.scale = 5.0
        self.view = (0.0, 0.0)       # layout coordinates at the canvas origin
        self.drag = None
        self.problems = []
        self.problem_ids = set()
        self.field_vars = {}
        self.key_vars = {}
        self.key_shown = {}

        self.build_menu()
        self.build_ui()
        self.bind_keys()
        if path:
            self.open_file(path)
        else:
            self.after(50, self.fit_view)
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def build_menu(self):
        menu = tk.Menu(self)
        f = tk.Menu(menu, tearoff=False)
        f.add_command(label="New (empty)", command=self.new_empty)
        f.add_command(label="New from example (grid)", command=self.new_example)
        f.add_command(label="New from example (staggered)", command=self.new_staggered_example)
        f.add_command(label="New from example (staggered with number row)", command=self.new_numbers_example)
        f.add_command(label="New switch test keyboard", command=self.new_switch_test)
        f.add_command(label="New numeric keypad", command=self.new_numpad)
        f.add_command(label="Open...", command=self.open_dialog, accelerator="Ctrl+O")
        f.add_command(label="Save", command=self.save, accelerator="Ctrl+S")
        f.add_command(label="Save as...", command=self.save_as)
        f.add_separator()
        f.add_command(label="Make parts list", command=self.make_parts_list)
        f.add_separator()
        f.add_command(label="Exit", command=self.destroy)
        menu.add_cascade(label="File", menu=f)
        e = tk.Menu(menu, tearoff=False)
        e.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        e.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        e.add_separator()
        e.add_command(label="Add rows of keys...", command=self.add_rows)
        e.add_command(label="Stagger rows...", command=self.stagger)
        e.add_command(label="Select all keys", command=self.select_all, accelerator="Ctrl+A")
        e.add_command(label="Delete selection", command=self.delete_selection, accelerator="Del")
        e.add_command(label="Duplicate keys", command=self.duplicate, accelerator="Ctrl+D")
        e.add_command(label="Snap selection to grid", command=self.snap_selection)
        menu.add_cascade(label="Edit", menu=e)
        v = tk.Menu(menu, tearoff=False)
        v.add_command(label="Fit to window", command=self.fit_view, accelerator="F")
        self.show_case = tk.BooleanVar(value=True)
        self.show_parts = tk.BooleanVar(value=True)
        v.add_checkbutton(label="Show case outline", variable=self.show_case, command=self.redraw)
        v.add_checkbutton(label="Show switches and diodes", variable=self.show_parts, command=self.redraw)
        menu.add_cascade(label="View", menu=v)
        self.config(menu=menu)

    def build_ui(self):
        main = ttk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        self.canvas = tk.Canvas(left, background=COLOURS["background"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.status = ttk.Label(left, anchor="w", font=("Segoe UI", 10))
        self.status.pack(fill="x", padx=4, pady=2)
        problems_frame = ttk.Frame(left)
        problems_frame.pack(fill="x")
        self.problem_list = tk.Listbox(problems_frame, height=6, font=("Segoe UI", 9))
        self.problem_list.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(problems_frame, command=self.problem_list.yview)
        sb.pack(side="right", fill="y")
        self.problem_list.config(yscrollcommand=sb.set)
        self.problem_list.bind("<<ListboxSelect>>", self.problem_clicked)
        main.add(left, weight=4)

        right = ttk.Notebook(main, width=330)
        main.add(right, weight=1)
        self.build_key_tab(right)
        self.build_board_tab(right)
        self.build_controller_tab(right)
        self.build_case_tab(right)
        self.build_holes_tab(right)

        c = self.canvas
        c.bind("<Configure>", lambda e: self.redraw())
        c.bind("<ButtonPress-1>", self.mouse_down)
        c.bind("<B1-Motion>", self.mouse_drag)
        c.bind("<ButtonRelease-1>", self.mouse_up)
        c.bind("<Double-Button-1>", self.double_click)
        c.bind("<Button-3>", self.context_menu)
        c.bind("<MouseWheel>", self.wheel)
        c.bind("<ButtonPress-2>", self.pan_start)
        c.bind("<B2-Motion>", self.pan_drag)

    def form(self, parent, fields, columns=1):
        """Build labelled entries bound to paths in the layout.
        fields: (label, path, kind) where kind is float, int, str, bool or a
        tuple of choices."""
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=6, pady=4)
        for n, (label, path, kind) in enumerate(fields):
            r, col = divmod(n, columns)
            ttk.Label(frame, text=label).grid(row=r, column=col * 2, sticky="w", padx=(0, 4), pady=1)
            if kind is bool:
                var = tk.BooleanVar()
                w = ttk.Checkbutton(frame, variable=var, command=lambda p=path: self.field_changed(p))
            elif isinstance(kind, tuple):
                var = tk.StringVar()
                w = ttk.Combobox(frame, textvariable=var, values=kind, width=10)
                w.bind("<<ComboboxSelected>>", lambda e, p=path: self.field_changed(p))
                w.bind("<Return>", lambda e, p=path: self.field_changed(p))
                w.bind("<FocusOut>", lambda e, p=path: self.field_changed(p))
            else:
                var = tk.StringVar()
                w = ttk.Entry(frame, textvariable=var, width=12)
                w.bind("<Return>", lambda e, p=path: self.field_changed(p))
                w.bind("<FocusOut>", lambda e, p=path: self.field_changed(p))
            w.grid(row=r, column=col * 2 + 1, sticky="we", pady=1)
            self.field_vars[path] = (var, kind, w)
        return frame

    def build_key_tab(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Key")
        self.key_title = ttk.Label(tab, text="No key selected", font=("Segoe UI", 10, "bold"))
        self.key_title.pack(anchor="w", padx=6, pady=(6, 0))
        frame = ttk.Frame(tab)
        frame.pack(fill="x", padx=6, pady=4)
        fields = [("Label", "label", str), ("Keycode", "keycode", kl.KEYCODES),
                  ("Fn keycode", "fn_keycode", [""] + kl.KEYCODES),
                  ("Width (u)", "w", float), ("Height (u)", "h", float),
                  ("X (mm)", "x", float), ("Y (mm)", "y", float), ("Rotation", "rotation", float),
                  ("Switches (u)", "switches", parse_switches),
                  ("Matrix row", "row", int), ("Matrix col", "col", int)]
        for r, (label, name, kind) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", padx=(0, 4), pady=1)
            var = tk.StringVar()
            if isinstance(kind, list):
                w = ttk.Combobox(frame, textvariable=var, values=kind, width=18)
                w.bind("<<ComboboxSelected>>", lambda e: self.key_field_changed())
            else:
                w = ttk.Entry(frame, textvariable=var, width=20)
            w.bind("<Return>", lambda e: self.key_field_changed())
            w.bind("<FocusOut>", lambda e: self.key_field_changed())
            w.grid(row=r, column=1, sticky="we", pady=1)
            self.key_vars[name] = (var, kind if not isinstance(kind, list) else str, w)
        ttk.Label(tab, foreground="#777", wraplength=300, justify="left", text=(
            "Switches lists where the key's switches are, in key units from its middle: "
            "0 is one switch in the middle, -0.5, 0.5 is two switches a key apart. "
            "Right click a key for quick settings. "
            "With several keys selected, any value you change is applied to all of them. "
            "Row and column are set automatically while 'Auto assign matrix' is ticked "
            "(Pico tab).")).pack(anchor="w", padx=6)
        b = ttk.Frame(tab)
        b.pack(fill="x", padx=6, pady=6)
        ttk.Button(b, text="Add key", command=lambda: self.add_key()).pack(side="left")
        ttk.Button(b, text="Duplicate", command=self.duplicate).pack(side="left", padx=4)
        ttk.Button(b, text="Delete", command=self.delete_selection).pack(side="left")
        ttk.Button(tab, text="Add rows of keys...", command=self.add_rows).pack(anchor="w", padx=6)

    def build_board_tab(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Board")
        self.form(tab, [
            ("Name", ("name",), str),
            ("Key pitch X", ("grid", "pitch_x"), float),
            ("Key pitch Y", ("grid", "pitch_y"), float),
            ("Snap", ("grid", "snap"), float),
        ])
        ttk.Separator(tab).pack(fill="x", pady=4)
        self.form(tab, [
            ("Auto size", ("board", "auto_size"), bool),
            ("Margin top", ("board", "margin", "top"), float),
            ("Margin bottom", ("board", "margin", "bottom"), float),
            ("Margin left", ("board", "margin", "left"), float),
            ("Margin right", ("board", "margin", "right"), float),
        ])
        ttk.Label(tab, text="Fixed board (when auto size is off):", foreground="#777").pack(anchor="w", padx=6)
        self.form(tab, [
            ("X", ("board", "x"), float), ("Y", ("board", "y"), float),
            ("Width", ("board", "width"), float), ("Height", ("board", "height"), float),
        ], columns=2)
        ttk.Button(tab, text="Fix board at current size", command=self.freeze_board).pack(anchor="w", padx=6)
        ttk.Separator(tab).pack(fill="x", pady=4)
        self.form(tab, [
            ("Corner radius", ("board", "corner_radius"), float),
            ("PCB thickness", ("board", "thickness"), float),
        ])

    def build_controller_tab(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Pico")
        self.form(tab, [
            ("Side", ("controller", "side"), ("back", "front")),
            ("Rotation", ("controller", "rotation"), ("0", "90", "180", "270")),
            ("X (centre)", ("controller", "x"), float),
            ("Y (centre)", ("controller", "y"), float),
        ])
        ttk.Label(tab, foreground="#777", wraplength=300, justify="left", text=(
            "Rotation 0 has the USB socket at the top. Put the USB end against a board edge "
            "so the case gets a slot for the cable. On the back, the Pico is soldered flat by "
            "its castellations and can sit under the keys.")).pack(anchor="w", padx=6)
        ttk.Separator(tab).pack(fill="x", pady=6)
        ttk.Label(tab, text="Key matrix", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=6)
        self.form(tab, [
            ("Diodes", ("matrix", "diodes"), bool),
            ("Auto assign matrix", ("matrix", "auto"), bool),
            ("Reserved GPIO", ("matrix", "reserved_pins"), "pins"),
            ("Row GPIO", ("matrix", "row_pins"), "pins"),
            ("Column GPIO", ("matrix", "col_pins"), "pins"),
        ])
        for path in (("matrix", "reserved_pins"), ("matrix", "row_pins"), ("matrix", "col_pins")):
            self.field_vars[path][2].config(width=30)
        ttk.Button(tab, text="Assign matrix now", command=self.assign_matrix).pack(anchor="w", padx=6, pady=4)
        self.matrix_label = ttk.Label(tab, justify="left", wraplength=300)
        self.matrix_label.pack(anchor="w", padx=6)

    def build_case_tab(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Case")
        heights = tuple(str(h) for h in kl.SWITCHES["PTS645"]["heights"])
        self.form(tab, [
            ("Switch height", ("switch", "height"), heights),
            ("Switch force", ("switch", "force"), ("L", "M", "H", "K")),
            ("Max case width", ("case", "max_width"), float),
            ("Wall", ("case", "wall"), float),
            ("Floor", ("case", "floor"), float),
            ("PCB to wall gap", ("case", "clearance"), float),
            ("Space under PCB", ("case", "back_clearance"), float),
            ("Plate thickness", ("case", "plate_thickness"), float),
            ("Key gap (plate web)", ("case", "key_gap"), float),
            ("Key clearance", ("case", "key_clearance"), float),
            ("Key protrusion", ("case", "key_protrusion"), float),
            ("Keycap flange", ("case", "flange"), float),
            ("Flange angle", ("case", "flange_angle"), float),
            ("Flange thickness", ("case", "flange_thickness"), float),
            ("Gap above switches", ("case", "plunger_gap"), float),
            ("Mock PCB fence height", ("mock_pcb", "fence_height"), float),
            ("Mock PCB grip", ("mock_pcb", "grip"), float),
            ("On top pillar height", ("pillars", "on_top_height"), float),
            ("Edge ledge/rib", ("case", "ledge"), float),
            ("Legends", ("case", "legend"), ("inlay", "engrave", "none")),
            ("Legend depth", ("case", "legend_depth"), float),
            ("Font file", ("case", "font"), str),
        ])
        self.field_vars[("case", "font")][2].config(width=30)
        self.case_label = ttk.Label(tab, justify="left", wraplength=300)
        self.case_label.pack(anchor="w", padx=6, pady=6)

    def build_holes_tab(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Holes")
        self.form(tab, [
            ("Hole diameter", ("case", "hole_diameter"), float),
            ("Standoff diameter", ("case", "standoff_diameter"), float),
            ("Screw pilot hole", ("case", "screw_pilot"), float),
        ])
        ttk.Label(tab, foreground="#777", wraplength=300, justify="left", text=(
            "Mounting holes fix the top plate to the tray, through the PCB. Right click on the "
            "board to add one and drag them to move them. They need a clear space about "
            "6mm across: in a board margin or in a gap between keys.")).pack(anchor="w", padx=6)
        self.hole_list = tk.Listbox(tab, height=10)
        self.hole_list.pack(fill="x", padx=6, pady=4)
        self.hole_list.bind("<<ListboxSelect>>", self.hole_list_clicked)
        b = ttk.Frame(tab)
        b.pack(fill="x", padx=6)
        ttk.Button(b, text="Add hole", command=lambda: self.add_hole()).pack(side="left")
        ttk.Button(b, text="Delete", command=self.delete_selection).pack(side="left", padx=4)

    def bind_keys(self):
        def unless_typing(fn):
            def handler(event):
                if isinstance(event.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
                    return
                fn(event)
            return handler
        self.bind("<Control-z>", lambda e: self.undo())
        self.bind("<Control-y>", lambda e: self.redo())
        self.bind("<Control-s>", lambda e: self.save())
        self.bind("<Control-o>", lambda e: self.open_dialog())
        self.bind("<Control-a>", unless_typing(lambda e: self.select_all()))
        self.bind("<Control-d>", unless_typing(lambda e: self.duplicate()))
        self.bind("<Delete>", unless_typing(lambda e: self.delete_selection()))
        self.bind("<f>", unless_typing(lambda e: self.fit_view()))
        self.bind("<bracketleft>", unless_typing(lambda e: self.rotate_selection(5)))
        self.bind("<bracketright>", unless_typing(lambda e: self.rotate_selection(-5)))
        for key, d in (("Left", (-1, 0)), ("Right", (1, 0)), ("Up", (0, -1)), ("Down", (0, 1))):
            self.bind("<%s>" % key, unless_typing(lambda e, d=d: self.nudge(*d)))

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------

    def set_layout(self, layout, path):
        self.layout = kl.normalise(layout)
        self.path = path
        self.selection = set()
        self.undo_stack = []
        self.redo_stack = []
        self.refresh()
        self.fit_view()

    def new_empty(self):
        layout = kl.new_layout()
        layout["name"] = "keyboard"
        self.set_layout(layout, None)

    def new_example(self):
        self.set_layout(kl.example_layout(), None)

    def new_numpad(self):
        self.set_layout(kl.numpad_layout(), None)

    def new_switch_test(self):
        self.set_layout(kl.switch_test_layout(), None)

    def new_numbers_example(self):
        self.set_layout(kl.staggered_numbers_layout(), None)

    def new_staggered_example(self):
        self.set_layout(kl.staggered_example_layout(), None)

    def open_dialog(self):
        path = filedialog.askopenfilename(initialdir=os.path.join(_repo_dir, "layouts"),
                                          filetypes=[("Keyboard layout", "*.json")])
        if path:
            self.open_file(path)

    def open_file(self, path):
        try:
            self.set_layout(kl.load(path), path)
        except Exception as e:
            messagebox.showerror("Open", "Could not open %s\n\n%s" % (path, e))

    def save(self):
        if not self.path:
            return self.save_as()
        self.commit_focus()
        kl.save(self.layout, self.path)
        self.refresh()
        errors = [p for p in self.problems if p[0] == "error"]
        if errors:
            self.status.config(text="Saved %s - but it has %d errors" % (self.path, len(errors)))

    def save_as(self):
        path = filedialog.asksaveasfilename(initialdir=os.path.join(_repo_dir, "layouts"),
                                            initialfile=self.layout["name"] + ".json",
                                            defaultextension=".json",
                                            filetypes=[("Keyboard layout", "*.json")])
        if path:
            self.path = path
            self.save()

    def make_parts_list(self):
        """Write the parts list for this layout to output/<name>/."""
        self.commit_focus()
        errors = [p for p in kl.validate(self.layout) if p[0] == "error"]
        md_path, csv_path = parts_list.write_parts_list(self.layout)
        message = "Parts list written to\n%s\n%s" % (md_path, csv_path)
        if errors:
            message += "\n\nThe layout has %d errors, so the list may change." % len(errors)
        if not parts_list.load_print_volumes(self.layout):
            message += "\n\nBuild the case in FreeCAD to add the filament needed for each part."
        messagebox.showinfo("Parts list", message)

    def commit_focus(self):
        """Make sure an entry that is being typed in is applied."""
        w = self.focus_get()
        if w is not None:
            self.canvas.focus_set()

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def checkpoint(self):
        self.undo_stack.append(json.dumps(self.layout))
        if len(self.undo_stack) > 200:
            self.undo_stack.pop(0)
        self.redo_stack = []

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(json.dumps(self.layout))
            self.layout = json.loads(self.undo_stack.pop())
            self.prune_selection()
            self.refresh()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(json.dumps(self.layout))
            self.layout = json.loads(self.redo_stack.pop())
            self.prune_selection()
            self.refresh()

    # ------------------------------------------------------------------
    # Model changes
    # ------------------------------------------------------------------

    def keys_changed(self):
        if self.layout["matrix"]["auto"]:
            kl.auto_matrix(self.layout)

    def key_by_id(self, kid):
        for k in self.layout["keys"]:
            if k["id"] == kid:
                return k
        return None

    def selected_keys(self):
        return [k for k in self.layout["keys"] if k["id"] in self.selection]

    def selected_holes(self):
        holes = self.layout["board"]["mounting_holes"]
        return [holes[i] for i in range(len(holes)) if "H%d" % (i + 1) in self.selection]

    def prune_selection(self):
        ids = {k["id"] for k in self.layout["keys"]}
        ids |= {"H%d" % (i + 1) for i in range(len(self.layout["board"]["mounting_holes"]))}
        ids.add("pico")
        self.selection &= ids

    def new_key_id(self):
        used = {k["id"] for k in self.layout["keys"]}
        n = len(self.layout["keys"]) + 1
        while "K%d" % n in used:
            n += 1
        return "K%d" % n

    def snap(self, v):
        s = self.layout["grid"]["snap"]
        return round(v / s) * s if s > 0 else v

    def add_key(self, x=None, y=None):
        g = self.layout["grid"]
        if x is None:
            bx, by, bw, bh = kl.board_rect(self.layout)
            x, y = bx + bw + g["pitch_x"], by + g["pitch_y"] / 2
        self.checkpoint()
        key = {"id": self.new_key_id(), "label": "", "keycode": "", "fn_keycode": "",
               "x": self.snap(x), "y": self.snap(y), "w": 1.0, "h": 1.0, "rotation": 0}
        self.layout["keys"].append(key)
        self.keys_changed()
        self.selection = {key["id"]}
        self.refresh()

    def add_hole(self, x=None, y=None):
        if x is None:
            bx, by, bw, bh = kl.board_rect(self.layout)
            x, y = bx + bw / 2, by + 3
        self.checkpoint()
        holes = self.layout["board"]["mounting_holes"]
        holes.append({"x": self.snap(x), "y": self.snap(y), "d": self.layout["case"]["hole_diameter"]})
        self.selection = {"H%d" % len(holes)}
        self.refresh()

    def add_rows(self):
        dlg = RowsDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        rows, replace, stagger = dlg.result
        self.checkpoint()
        if replace:
            self.layout["keys"] = []
            x0, y0 = 0.0, 0.0
        else:
            bx, by, bw, bh = kl.board_rect(self.layout)
            x0, y0 = bx + self.layout["board"]["margin"]["left"], by + bh
        before = len(self.layout["keys"])
        kl.add_key_rows(self.layout, rows, x0, y0)
        # make sure the new ids are unique
        used = {k["id"] for k in self.layout["keys"][:before]}
        for k in self.layout["keys"][before:]:
            if k["id"] in used:
                k["id"] = self.new_key_id()
            used.add(k["id"])
            k.setdefault("fn_keycode", "")
        kl.stagger_rows(self.layout, stagger, self.layout["keys"][before:])
        if replace and self.layout["keys"]:
            # Pico on the back, centred, with its USB socket at the top edge
            x0, y0, x1, y1 = kl.bounds(sum((kl.key_polygon(self.layout, k) for k in self.layout["keys"]), []))
            self.layout["controller"].update({
                "side": "back", "rotation": 0, "x": round((x0 + x1) / 2, 3),
                "y": y0 - self.layout["board"]["margin"]["top"] + kl.PICO_LENGTH / 2})
        self.keys_changed()
        self.selection = {k["id"] for k in self.layout["keys"][before:]}
        self.refresh()
        self.fit_view()

    def stagger(self):
        """Stagger the rows of the selected keys, or of all the keys."""
        keys = self.selected_keys() or self.layout["keys"]
        if not keys:
            return
        dlg = StaggerDialog(self, len(keys), bool(self.selected_keys()))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        self.checkpoint()
        kl.stagger_rows(self.layout, dlg.result, keys)
        self.keys_changed()
        self.refresh()
        self.fit_view()

    def delete_selection(self):
        if not self.selection:
            return
        self.checkpoint()
        self.layout["keys"] = [k for k in self.layout["keys"] if k["id"] not in self.selection]
        holes = self.layout["board"]["mounting_holes"]
        self.layout["board"]["mounting_holes"] = [h for i, h in enumerate(holes)
                                                  if "H%d" % (i + 1) not in self.selection]
        self.selection = set()
        self.keys_changed()
        self.refresh()

    def duplicate(self):
        keys = self.selected_keys()
        if not keys:
            return
        self.checkpoint()
        x0, y0, x1, y1 = kl.bounds(sum((kl.key_polygon(self.layout, k) for k in keys), []))
        new = set()
        for k in keys:
            c = copy.deepcopy(k)
            c["id"] = self.new_key_id()
            c["y"] = k["y"] + (y1 - y0)
            self.layout["keys"].append(c)
            new.add(c["id"])
        self.selection = new
        self.keys_changed()
        self.refresh()

    def select_all(self):
        self.selection = {k["id"] for k in self.layout["keys"]}
        self.refresh()

    def move_selection(self, dx, dy, originals=None):
        for k in self.layout["keys"]:
            if k["id"] in self.selection:
                ox, oy = originals[k["id"]] if originals else (k["x"], k["y"])
                k["x"], k["y"] = round(ox + dx, 3), round(oy + dy, 3)
        for i, h in enumerate(self.layout["board"]["mounting_holes"]):
            hid = "H%d" % (i + 1)
            if hid in self.selection:
                ox, oy = originals[hid] if originals else (h["x"], h["y"])
                h["x"], h["y"] = round(ox + dx, 3), round(oy + dy, 3)
        if "pico" in self.selection:
            c = self.layout["controller"]
            ox, oy = originals["pico"] if originals else (c["x"], c["y"])
            c["x"], c["y"] = round(ox + dx, 3), round(oy + dy, 3)

    def nudge(self, dx, dy):
        if not self.selection:
            return
        self.checkpoint()
        s = self.layout["grid"]["snap"] or 0.5
        self.move_selection(dx * s, dy * s)
        self.keys_changed()
        self.refresh()

    def snap_selection(self):
        self.checkpoint()
        for k in self.selected_keys():
            k["x"], k["y"] = self.snap(k["x"]), self.snap(k["y"])
        self.keys_changed()
        self.refresh()

    def set_switches(self, count):
        """Give the selected keys one switch in the middle, or two switches
        half a unit in from each end (keys under 2u are too short for two)."""
        keys = self.selected_keys()
        if not keys:
            return
        self.checkpoint()
        for k in keys:
            end = (k["w"] - 1) / 2
            k["switches"] = [-end, end] if count == 2 and k["w"] >= 2 else [0.0]
        self.refresh()

    def rotate_selection(self, degrees):
        """Rotate the selected keys, or reset their rotation if degrees is None."""
        keys = self.selected_keys()
        if not keys:
            return
        self.checkpoint()
        for k in keys:
            k["rotation"] = 0 if degrees is None else (k.get("rotation", 0) + degrees) % 360
        self.refresh()

    def scale_positions(self, axis, ratio):
        """Changing the key pitch spreads the keys and holes out (or in) to match."""
        for item in self.layout["keys"] + self.layout["board"]["mounting_holes"]:
            item[axis] = round(item[axis] * ratio, 3)
        if axis == "x":
            self.layout["controller"]["x"] = round(self.layout["controller"]["x"] * ratio, 3)

    def freeze_board(self):
        self.checkpoint()
        x, y, w, h = kl.board_rect(self.layout)
        b = self.layout["board"]
        b.update({"auto_size": False, "x": round(x, 3), "y": round(y, 3),
                  "width": round(w, 3), "height": round(h, 3)})
        self.refresh()

    def assign_matrix(self):
        self.checkpoint()
        kl.auto_matrix(self.layout)
        self.refresh()

    # ------------------------------------------------------------------
    # Form handling
    # ------------------------------------------------------------------

    def field_changed(self, path):
        var, kind, _ = self.field_vars[path]
        try:
            current = get_path(self.layout, path)
            if kind is bool:
                value = bool(var.get())
            elif kind == "pins":
                value = parse_pins(var.get())
            elif kind is str:
                value = var.get()
            elif isinstance(kind, tuple):
                value = var.get()
                if isinstance(current, (int, float)) and not isinstance(current, bool):
                    value = float(value)
                    if value == int(value):
                        value = int(value) if isinstance(current, int) else value
            else:
                value = kind(var.get())
        except (ValueError, KeyError):
            self.show_fields()
            return
        if value == current:
            return
        self.checkpoint()
        set_path(self.layout, path, value)
        if path in (("grid", "pitch_x"), ("grid", "pitch_y")) and current > 0:
            self.scale_positions(path[1][-1], value / current)
        if path[0] in ("grid", "case") or path == ("matrix", "reserved_pins") or \
                (path == ("matrix", "auto") and value):
            self.keys_changed()
        self.refresh()

    def key_field_changed(self):
        keys = self.selected_keys()
        if not keys:
            return
        changes = {}
        for name, (var, kind, _) in self.key_vars.items():
            text = var.get()
            if text == self.key_shown.get(name):
                continue
            try:
                changes[name] = kind(text) if kind is not str else text
            except ValueError:
                continue
        if not changes:
            return
        self.checkpoint()
        for k in keys:
            for name, value in changes.items():
                if name in ("x", "y", "label", "row", "col") and len(keys) > 1:
                    continue
                k[name] = value
            if "label" in changes and "keycode" not in changes and len(keys) == 1:
                guess = kl.guess_keycode(k["label"])
                if guess:
                    k["keycode"] = guess
        if any(n in changes for n in ("x", "y", "w", "h")):
            self.keys_changed()
        self.refresh()

    def show_fields(self):
        for path, (var, kind, _) in self.field_vars.items():
            value = get_path(self.layout, path)
            if kind is bool:
                var.set(bool(value))
            elif kind == "pins":
                var.set(format_pins(value))
            else:
                var.set(str(value))
        board_fixed = not self.layout["board"]["auto_size"]
        for name in ("x", "y", "width", "height"):
            self.field_vars[("board", name)][2].config(state="normal" if board_fixed else "disabled")
        auto = self.layout["matrix"]["auto"]
        for name in ("row_pins", "col_pins"):
            self.field_vars[("matrix", name)][2].config(state="disabled" if auto else "normal")

        keys = self.selected_keys()
        self.key_shown = {}
        for name, (var, kind, w) in self.key_vars.items():
            if not keys:
                var.set("")
                w.config(state="disabled")
                continue
            values = {format_value(k.get(name, "")) for k in keys}
            text = values.pop() if len(values) == 1 else ""
            var.set(text)
            self.key_shown[name] = text
            single_only = name in ("x", "y", "label", "row", "col")
            locked = name in ("row", "col") and self.layout["matrix"]["auto"]
            w.config(state="disabled" if (single_only and len(keys) > 1) or locked else "normal")
        if not keys:
            self.key_title.config(text="No key selected")
        elif len(keys) == 1:
            self.key_title.config(text="Key %s" % keys[0]["id"])
        else:
            self.key_title.config(text="%d keys selected" % len(keys))

        self.hole_list.delete(0, "end")
        for i, h in enumerate(self.layout["board"]["mounting_holes"]):
            self.hole_list.insert("end", "H%d   x %.2f   y %.2f   d %.2f" % (i + 1, h["x"], h["y"], h["d"]))
            if "H%d" % (i + 1) in self.selection:
                self.hole_list.selection_set(i)

    # ------------------------------------------------------------------
    # Refresh: validation, status and drawing
    # ------------------------------------------------------------------

    def refresh(self):
        self.problems = kl.validate(self.layout)
        self.problem_ids = set()
        for level, _, ids in self.problems:
            if level == "error":
                self.problem_ids.update(ids)
        self.show_fields()
        self.show_status()
        self.redraw()

    def show_status(self):
        L = self.layout
        bx, by, bw, bh = kl.board_rect(L)
        cw, ch, cd = kl.case_size(L)
        nrows, ncols = kl.matrix_size(L)
        name = os.path.basename(self.path) if self.path else "(not saved)"
        self.title("Cyberdeck keyboard designer - %s" % name)
        wide = "  TOO WIDE" if cw >= L["case"]["max_width"] else ""
        self.status.config(text="%d keys   board %.1f x %.1f mm   case %.1f x %.1f x %.1f mm (%.2f in wide)%s   "
                                "matrix %d x %d" % (len(L["keys"]), bw, bh, cw, ch, cd, cw / 25.4, wide,
                                                     nrows, ncols),
                           foreground="#c00000" if wide else "")
        self.problem_list.delete(0, "end")
        for level, msg, _ in self.problems:
            self.problem_list.insert("end", ("ERROR    " if level == "error" else "Warning  ") + msg)
            self.problem_list.itemconfig("end", foreground="#c00000" if level == "error" else "#a06000")
        if not self.problems:
            self.problem_list.insert("end", "No problems found")
        m = L["matrix"]
        self.matrix_label.config(text="%d rows x %d columns = %d positions for %d keys\nUses %d of the Pico's %d GPIO pins"
                                      % (nrows, ncols, nrows * ncols, len(L["keys"]),
                                         len(m["row_pins"]) + len(m["col_pins"]), len(kl.PICO_GPIO)))
        s = kl.stack(L)
        screw, room = kl.screw_length(L)
        self.case_label.config(text=(
            "Case %.1f x %.1f x %.1f mm\n"
            "Keytops %.1fmm above the plate, plate top at %.1fmm\n"
            "Fixing screws: M2 x %s self tapping (room for %.1fmm)\n"
            "Keycap size (1u): %.2f x %.2f mm" % (
                cw, ch, cd, L["case"]["key_protrusion"], s["plate_top"] - s["case_bottom"], screw, room,
                *kl.keycap_size(L, {"w": 1, "h": 1}))))

    def to_screen(self, x, y):
        return (x - self.view[0]) * self.scale, (y - self.view[1]) * self.scale

    def to_layout(self, sx, sy):
        return sx / self.scale + self.view[0], sy / self.scale + self.view[1]

    def poly(self, points, **kw):
        flat = []
        for x, y in points:
            flat += self.to_screen(x, y)
        return self.canvas.create_polygon(flat, **kw)

    def rect(self, x, y, w, h, **kw):
        x0, y0 = self.to_screen(x, y)
        x1, y1 = self.to_screen(x + w, y + h)
        return self.canvas.create_rectangle(x0, y0, x1, y1, **kw)

    def fit_view(self):
        self.update_idletasks()
        cw, ch = max(self.canvas.winfo_width(), 200), max(self.canvas.winfo_height(), 200)
        x, y, w, h = kl.case_rect(self.layout)
        pad = 10
        self.scale = min(cw / (w + 2 * pad), ch / (h + 2 * pad))
        self.view = (x + w / 2 - cw / self.scale / 2, y + h / 2 - ch / self.scale / 2)
        self.redraw()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        L = self.layout
        if self.show_case.get():
            cx, cy, cw, ch = kl.case_rect(L)
            self.rect(cx, cy, cw, ch, fill=COLOURS["case"], outline="")
            limit = L["case"]["max_width"]
            width_ok = cw < limit
            sx0, sy0 = self.to_screen(cx, cy + ch)
            sx1, _ = self.to_screen(cx + cw, cy + ch)
            colour = "#aaaaaa" if width_ok else COLOURS["error"]
            c.create_line(sx0, sy0 + 12, sx1, sy0 + 12, fill=colour, arrow="both")
            c.create_text((sx0 + sx1) / 2, sy0 + 24, fill=colour, font=("Segoe UI", 9),
                          text="case %.1f mm (%.2f in) - limit %.1f mm" % (cw, cw / 25.4, limit))
        bx, by, bw, bh = kl.board_rect(L)
        self.rect(bx, by, bw, bh, fill=COLOURS["board"], outline=COLOURS["board_edge"], width=2)

        pico_tag = None
        if L["controller"]["side"] == "back":
            pico_tag = self.draw_pico()

        for k in L["keys"]:
            self.draw_key(k)

        for i, h in enumerate(L["board"]["mounting_holes"]):
            hid = "H%d" % (i + 1)
            r = L["case"]["standoff_diameter"] / 2 * self.scale
            sx, sy = self.to_screen(h["x"], h["y"])
            outline = COLOURS["selected"] if hid in self.selection else \
                COLOURS["error"] if hid in self.problem_ids else COLOURS["hole"]
            c.create_oval(sx - r, sy - r, sx + r, sy + r, outline=outline, width=2, dash=(3, 2))
            r2 = h["d"] / 2 * self.scale
            c.create_oval(sx - r2, sy - r2, sx + r2, sy + r2, fill="#101010", outline=COLOURS["hole"])

        if L["controller"]["side"] == "front":
            self.draw_pico()

        if self.drag and self.drag.get("band"):
            x0, y0, x1, y1 = self.drag["band"]
            c.create_rectangle(x0, y0, x1, y1, outline=COLOURS["selected"], dash=(4, 2))

    def draw_pico(self):
        L = self.layout
        back = L["controller"]["side"] == "back"
        selected = "pico" in self.selection
        outline = COLOURS["selected"] if selected else COLOURS["error"] if "pico" in self.problem_ids \
            else COLOURS["pico_back"]
        if back:
            self.poly(kl.pico_polygon(L), fill="", outline=outline, width=2, dash=(6, 3))
        else:
            self.poly(kl.pico_polygon(L), fill=COLOURS["pico_front"], outline=outline, width=2)
        (ux, uy), (dx, dy) = kl.pico_usb(L)
        rot = L["controller"]["rotation"]
        cx, cy = ux + dx * (kl.PICO_USB_OVERHANG - 2.6) / 2, uy + dy * (kl.PICO_USB_OVERHANG - 2.6) / 2
        self.poly(kl.rect_corners(cx, cy, 8.0, 2.6 + kl.PICO_USB_OVERHANG, rot), fill=COLOURS["usb"], outline="")
        sx, sy = self.to_screen(L["controller"]["x"], L["controller"]["y"])
        self.canvas.create_text(sx, sy, text="Pico (%s)" % L["controller"]["side"], fill=outline,
                                font=("Segoe UI", max(7, int(self.scale * 1.6)), "bold"),
                                angle=L["controller"]["rotation"] + 90)

    def draw_key(self, k):
        L = self.layout
        c = self.canvas
        sel = k["id"] in self.selection
        bad = k["id"] in self.problem_ids
        self.poly(kl.key_polygon(L, k, "area"), fill="", outline=COLOURS["key_area"], dash=(2, 3))
        if self.show_parts.get():
            for yard in kl.switch_polygons(L, k):
                self.poly(yard, fill="", outline=COLOURS["switch"])
            if L["matrix"]["diodes"]:
                self.poly(kl.diode_polygon(L, k), fill=COLOURS["diode"], outline="#777777")
        outline = COLOURS["selected"] if sel else COLOURS["error"] if bad else "#8a8473"
        self.poly(kl.key_polygon(L, k, "cap"), fill=COLOURS["cap"], outline=outline, width=3 if sel or bad else 1)
        if self.show_parts.get():
            # mark where the key's switch plungers are
            r = kl.switch_info(L)["plunger_diameter"] / 2 * self.scale
            for px, py in kl.switch_positions(L, k):
                qx, qy = self.to_screen(px, py)
                c.create_oval(qx - r, qy - r, qx + r, qy + r, outline="#b8b0a0", dash=(2, 2))
        sx, sy = self.to_screen(k["x"], k["y"])
        cw, ch = kl.keycap_size(L, k)
        text_len = max(1, len(k["label"] or "?"))
        size = max(6, int(min(ch * 0.28, cw * 0.75 / text_len) * self.scale))
        c.create_text(sx, sy, text=k["label"] or "?", fill=COLOURS["cap_text"], font=("Segoe UI", size, "bold"),
                      angle=k.get("rotation", 0))
        if "row" in k and self.scale > 4:
            ox, oy = kl.rotate(0, -kl.keycap_size(L, k)[1] / 2 + 1.2, k.get("rotation", 0))
            tx, ty = self.to_screen(k["x"] + ox, k["y"] + oy)
            c.create_text(tx, ty, text="%d,%d" % (k["row"], k["col"]), fill="#7a7466",
                          font=("Segoe UI", max(6, int(self.scale * 1.0))), angle=k.get("rotation", 0))

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def hit(self, sx, sy):
        x, y = self.to_layout(sx, sy)
        L = self.layout
        pt = kl.circle_points(x, y, 0.01, 4)
        for i, h in enumerate(L["board"]["mounting_holes"]):
            if math.hypot(h["x"] - x, h["y"] - y) <= L["case"]["standoff_diameter"] / 2:
                return "H%d" % (i + 1)
        if L["controller"]["side"] == "front" and kl.polygons_overlap(pt, kl.pico_polygon(L)):
            return "pico"
        for k in reversed(L["keys"]):
            if kl.polygons_overlap(pt, kl.key_polygon(L, k, "area")):
                return k["id"]
        if kl.polygons_overlap(pt, kl.pico_polygon(L)):
            return "pico"
        return None

    def mouse_down(self, event):
        self.canvas.focus_set()
        item = self.hit(event.x, event.y)
        shift = event.state & 0x1
        if item is None:
            if not shift:
                self.selection = set()
            self.drag = {"band": (event.x, event.y, event.x, event.y), "base": set(self.selection)}
            self.refresh()
            return
        if shift:
            self.selection ^= {item}
        elif item not in self.selection:
            self.selection = {item}
        originals = {}
        for k in self.layout["keys"]:
            originals[k["id"]] = (k["x"], k["y"])
        for i, h in enumerate(self.layout["board"]["mounting_holes"]):
            originals["H%d" % (i + 1)] = (h["x"], h["y"])
        originals["pico"] = (self.layout["controller"]["x"], self.layout["controller"]["y"])
        self.drag = {"start": self.to_layout(event.x, event.y), "originals": originals,
                     "snapshot": json.dumps(self.layout), "moved": False, "anchor": item}
        self.refresh()

    def mouse_drag(self, event):
        if not self.drag:
            return
        if "band" in self.drag:
            x0, y0, _, _ = self.drag["band"]
            self.drag["band"] = (x0, y0, event.x, event.y)
            lx0, ly0 = self.to_layout(min(x0, event.x), min(y0, event.y))
            lx1, ly1 = self.to_layout(max(x0, event.x), max(y0, event.y))
            inside = {k["id"] for k in self.layout["keys"]
                      if lx0 <= k["x"] <= lx1 and ly0 <= k["y"] <= ly1}
            self.selection = self.drag["base"] | inside
            self.redraw()
            return
        x, y = self.to_layout(event.x, event.y)
        # move in steps of the snap distance, so keys stay on their pitch
        dx = self.snap(x - self.drag["start"][0])
        dy = self.snap(y - self.drag["start"][1])
        if dx or dy or self.drag["moved"]:
            self.drag["moved"] = True
            self.move_selection(dx, dy, self.drag["originals"])
            self.redraw()

    def mouse_up(self, event):
        if not self.drag:
            return
        if self.drag.get("moved"):
            self.undo_stack.append(self.drag["snapshot"])
            self.redo_stack = []
            self.keys_changed()
        self.drag = None
        self.refresh()

    def double_click(self, event):
        if self.hit(event.x, event.y) is None:
            self.add_key(*self.to_layout(event.x, event.y))

    def context_menu(self, event):
        x, y = self.to_layout(event.x, event.y)
        item = self.hit(event.x, event.y)
        if item and item not in self.selection:
            self.selection = {item}
            self.refresh()
        m = tk.Menu(self, tearoff=False)
        m.add_command(label="Add key here", command=lambda: self.add_key(x, y))
        m.add_command(label="Add mounting hole here", command=lambda: self.add_hole(x, y))
        m.add_command(label="Add rows of keys...", command=self.add_rows)
        m.add_command(label="Stagger rows...", command=self.stagger)
        if self.selection:
            m.add_separator()
            m.add_command(label="Rotate keys 90", command=lambda: self.rotate_selection(90))
            m.add_command(label="Rotate keys -15", command=lambda: self.rotate_selection(-15))
            m.add_command(label="Rotate keys 15", command=lambda: self.rotate_selection(15))
            m.add_command(label="Reset key rotation", command=lambda: self.rotate_selection(None))
            m.add_command(label="One switch (in the middle)", command=lambda: self.set_switches(1))
            m.add_command(label="Two switches (one near each end)", command=lambda: self.set_switches(2))
            m.add_command(label="Duplicate keys", command=self.duplicate)
            m.add_command(label="Delete", command=self.delete_selection)
        if "pico" in self.selection:
            m.add_separator()
            m.add_command(label="Rotate Pico 90", command=self.rotate_pico)
            m.add_command(label="Move Pico to %s" % ("front" if self.layout["controller"]["side"] == "back"
                                                     else "back"), command=self.flip_pico)
        m.tk_popup(event.x_root, event.y_root)

    def rotate_pico(self):
        self.checkpoint()
        c = self.layout["controller"]
        c["rotation"] = (c["rotation"] + 90) % 360
        self.refresh()

    def flip_pico(self):
        self.checkpoint()
        c = self.layout["controller"]
        c["side"] = "front" if c["side"] == "back" else "back"
        self.refresh()

    def wheel(self, event):
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        x, y = self.to_layout(event.x, event.y)
        self.scale = max(0.5, min(60, self.scale * factor))
        self.view = (x - event.x / self.scale, y - event.y / self.scale)
        self.redraw()

    def pan_start(self, event):
        self.pan = (event.x, event.y, self.view)

    def pan_drag(self, event):
        x0, y0, (vx, vy) = self.pan
        self.view = (vx - (event.x - x0) / self.scale, vy - (event.y - y0) / self.scale)
        self.redraw()

    def problem_clicked(self, event):
        sel = self.problem_list.curselection()
        if sel and sel[0] < len(self.problems):
            ids = set(self.problems[sel[0]][2])
            if ids:
                self.selection = ids
                self.show_fields()
                self.redraw()

    def hole_list_clicked(self, event):
        sel = self.hole_list.curselection()
        if sel:
            self.selection = {"H%d" % (sel[0] + 1)}
            self.redraw()


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = Designer(sys.argv[1] if len(sys.argv) > 1 else None)
    app.mainloop()
