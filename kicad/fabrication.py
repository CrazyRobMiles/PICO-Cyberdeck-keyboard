"""
Makes the files for having a keyboard PCB made, for example by PCBWay.

build_pcb.py calls this after saving the board. It uses kicad-cli (which
comes with KiCad) to write output/<name>/fabrication/:

- <name>_gerbers.zip   the Gerber and drill files - upload this to order boards
- <name>_bom_top.xlsx, <name>_bom_bottom.xlsx
                       parts to fit on each side of the board, for assembly
                       (optional), laid out like PCBWay's sample BOM, with
                       the same as .csv files
- <name>_positions_top.csv, <name>_positions_bottom.csv
                       where each part goes on each side, for assembly
- <name>_assembly.zip  the Gerbers, BOM and positions together, for an assembly
                       order form with a single upload box
- ORDERING.md          the settings to use on the order form, for this board

The Gerbers have the copper, solder mask, silkscreen and paste (for a stencil)
layers of both sides and the board outline. The drill files are Excellon in
mm, with plated and non plated holes in separate files. There is also an
IPC-D-356 netlist, which the maker uses to test the bare boards. These are
the same files, with the same settings, as the PCBWay plugin for KiCad makes.
"""

import csv
import glob
import os
import re
import shutil
import subprocess
import sys
import zipfile

import pcbnew

import keyboard_layout as kl
import schematic

GERBER_LAYERS = ["F.Cu", "B.Cu", "F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen",
                 "F.Mask", "B.Mask", "Edge.Cuts"]


def find_kicad_cli():
    candidates = [os.path.join(os.path.dirname(sys.executable), "kicad-cli.exe"),
                  os.path.join(os.path.dirname(sys.executable), "kicad-cli"),
                  r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
                  shutil.which("kicad-cli") or ""]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    raise RuntimeError("Cannot find kicad-cli, which comes with KiCad")


def run(cli, *args):
    result = subprocess.run([cli] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("kicad-cli %s failed:\n%s%s" % (" ".join(args[:3]), result.stdout, result.stderr))


def board_facts(board):
    """Sizes the order form asks for, measured from the board."""
    mm = pcbnew.ToMM
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    drills = [mm(v.GetDrillValue()) for v in vias]
    plated = [mm(p.GetDrillSize().x) for p in board.GetPads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    unplated = [mm(p.GetDrillSize().x) for p in board.GetPads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    return {
        "min_track": min((mm(t.GetWidth()) for t in tracks), default=0),
        "tracks": len(tracks), "vias": len(vias),
        "min_hole": min(drills + plated + unplated, default=0),
        "plated_holes": len(drills) + len(plated), "unplated_holes": len(unplated),
        "smd_parts": sum(1 for fp in board.GetFootprints() if not fp.IsBoardOnly()),
    }


SIDES = (("top", "front"), ("bottom", "back"))


def bom_parts(layout):
    """The parts to fit, as (side, designators, manufacturer, part number,
    description, package, type, notes). side is "top" or "bottom"."""
    keys = layout["keys"]
    switches = [ref for refs in schematic.switch_refs(layout) for ref in refs]
    parts = [("top", switches, "C&K", kl.switch_part_number(layout),
              "Tactile switch, 6 x 6mm, %.1fmm high, %sgf" % (layout["switch"]["height"],
                                                               kl.switch_force_grams(layout)),
              "6x6mm SMD gull wing", "SMD", "")]
    if layout["matrix"]["diodes"]:
        parts.append(("top", ["D%d" % (n + 1) for n in range(len(keys))], "Diodes Inc (or equivalent)",
                      "1N4148W-7-F", "1N4148W small signal diode", "SOD-123", "SMD",
                      "Cathode band to pad 1 (marked on the silkscreen)"))
    if layout["controller"]["side"] == "back":
        parts.append(("bottom", ["U1"], "Raspberry Pi", "SC0915", "Raspberry Pi Pico", "Castellated module",
                      "SMD", "Soldered flat by its castellations (no header pins). USB socket to the board edge "
                             "as shown on the silkscreen"))
    else:
        parts.append(("top", ["U1"], "Raspberry Pi", "SC0915", "Raspberry Pi Pico, on 2 x 20 way header pins",
                      "Module on 2.54mm headers", "thru-hole", "Fit on header pins, USB socket to the board edge"))
    return parts


def write_boms(layout, out_dir):
    """Writes a BOM for each side of the board that has parts on it:
    <name>_bom_top.xlsx/.csv and <name>_bom_bottom.xlsx/.csv. Returns the
    sides written."""
    name = layout["name"]
    written = []
    for side, _ in SIDES:
        rows = []
        for part_side, refs, maker, mpn, description, package, kind, notes in bom_parts(layout):
            if part_side == side:
                rows.append([len(rows) + 1, ",".join(refs), len(refs), maker, mpn, description, package, kind, notes])
        base = os.path.join(out_dir, "%s_bom_%s" % (name, side))
        if not rows:
            continue
        with open(base + ".csv", "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([BOM_HEADINGS] + rows)
        write_bom_xlsx(base + ".xlsx", "%s BOM - %s side (%d keys)" % (name, side.upper(), len(layout["keys"])),
                       rows)
        written.append(side)
    return written


# The column headings of PCBWay's sample BOM. * marks the columns they need.
BOM_HEADINGS = ["Item #", "*Designator", "*Qty", "Manufacturer", "*Mfg Part #", "Description / Value",
                "*Package/Footprint", "Type", "Your Instructions / Notes"]
BOM_WIDTHS = [7, 40, 6, 22, 24, 40, 22, 8, 44]


def write_bom_xlsx(path, title, rows):
    """Writes the BOM as an Excel workbook laid out like PCBWay's sample:
    the title on row 2, the column headings on row 6 and the parts from row
    7. KiCad's Python has no spreadsheet library, so this writes the .xlsx
    file (a zip of XML files) directly."""
    from xml.sax.saxutils import escape

    def cell(ref, value, style=0):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return '<c r="%s" s="%d"><v>%s</v></c>' % (ref, style, value)
        return '<c r="%s" s="%d" t="inlineStr"><is><t>%s</t></is></c>' % (ref, style, escape(str(value)))

    def col(n):
        return "ABCDEFGHI"[n]

    sheet_rows = ['<row r="2">%s</row>' % cell("D2", title, 2),
                  '<row r="6">%s</row>' % "".join(cell("%s6" % col(i), h, 1) for i, h in enumerate(BOM_HEADINGS))]
    for r, values in enumerate(rows, start=7):
        sheet_rows.append('<row r="%d">%s</row>' % (
            r, "".join(cell("%s%d" % (col(i), r), v) for i, v in enumerate(values) if v != "")))
    cols = "".join('<col min="%d" max="%d" width="%d" customWidth="1"/>' % (i + 1, i + 1, w)
                   for i, w in enumerate(BOM_WIDTHS))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<cols>%s</cols><sheetData>%s</sheetData><mergeCells count="1"><mergeCell ref="D2:F4"/></mergeCells>'
             '</worksheet>' % (cols, "".join(sheet_rows)))
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="11"/><name val="Calibri"/></font>'
              '<font><b/><sz val="14"/><name val="Calibri"/></font></fonts>'
              '<fills count="2"><fill><patternFill patternType="none"/></fill>'
              '<fill><patternFill patternType="gray125"/></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
              '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
              '</styleSheet>')
    files = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="BOM" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
            'Target="styles.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
        "xl/styles.xml": styles,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)


def write_ordering_notes(layout, facts, path, zip_name):
    _, _, width, height = kl.board_rect(layout)
    lines = [
        "# Ordering the %s PCB" % layout["name"],
        "",
        "Made by kicad/build_pcb.py. Upload `%s` to the board maker's quote page" % zip_name,
        "(for PCBWay: PCB Instant Quote, then upload the Gerber file), and check these settings:",
        "",
        "| Setting | Choose |",
        "|---|---|",
        "| Layers | 2 |",
        "| Board size | %.1f x %.1f mm |" % (width, height),
        "| Quantity | 5 (usually the minimum) |",
        "| Material | FR-4 |",
        "| Thickness | **%.1f mm** - the case is designed for this |" % layout["board"]["thickness"],
        "| Min track / spacing | 6/6 mil or larger (this board: %.2f mm tracks, %.2f mm gaps) |" % (
            facts["min_track"], layout["routing"]["clearance"]),
        "| Min hole size | 0.3 mm (this board's smallest hole: %.2f mm) |" % facts["min_hole"],
        "| Solder mask | any colour |",
        "| Silkscreen | any colour that shows on the mask |",
        "| Surface finish | HASL lead free, or ENIG for flatter pads |",
        "| Via process | Tenting vias |",
        "| Finished copper | 1 oz |",
        "",
        "The board has %d tracks, %d vias, %d plated and %d non plated (mounting) holes." % (
            facts["tracks"], facts["vias"], facts["plated_holes"], facts["unplated_holes"]),
        "",
        "## Stencil",
        "",
        "To solder the switches and diodes yourself with solder paste, add a stencil for the",
        "top side to the order. It is made from the F.Paste layer, which is in the zip.",
        "",
        "## Assembly (optional)",
        "",
        "To have the parts fitted, use the maker's PCB assembly quote form (not the plain",
        "PCB quote). There is a BOM and a position (centroid, pick and place) file for",
        "each side of the board that has parts on it:",
        "",
        "| Side | BOM | Positions | Parts |",
        "|---|---|---|---|",
    ] + [
        "| %s | `%s_bom_%s.xlsx` | `%s_positions_%s.csv` | %s |" % (
            side.capitalize(), layout["name"], side, layout["name"], side,
            ", ".join("%d x %s" % (len(refs), description.split(",")[0])
                      for part_side, refs, _, _, description, _, _, _ in bom_parts(layout) if part_side == side))
        for side, _ in SIDES
        if any(p[0] == side for p in bom_parts(layout))
    ] + [
        "",
        "If the form has only one upload box, upload `%s_assembly.zip`, which holds the" % layout["name"],
        "Gerbers, drill files, netlist, BOMs and positions together.",
        "",
        "The switches are %s (%sgf press force, set in the layout)." % (
            kl.switch_part_number(layout), kl.switch_force_grams(layout)),
    ] + ([
        "",
        "The Raspberry Pi Pico (U1) is on the bottom, soldered flat by its castellations.",
        "Fitting both sides costs more than one. To solder the Picos yourself, upload",
        "only the top BOM and positions, and order a top side assembly. The maker may",
        "also ask you to send the Picos (consigned parts).",
    ] if layout["controller"]["side"] == "back" else []) + [
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_fabrication_files(layout, board, board_path):
    """Writes the fabrication folder. Returns the path of the Gerber zip."""
    cli = find_kicad_cli()
    name = layout["name"]
    out_dir = os.path.join(os.path.dirname(board_path), "fabrication")
    plots = os.path.join(out_dir, "gerbers")
    if os.path.isdir(plots):
        shutil.rmtree(plots)
    os.makedirs(plots)

    # Settings as the PCBWay plugin uses them: KiCad file names, silkscreen
    # trimmed off the pads, separate plated and non plated drill files, and
    # an IPC-D-356 netlist for the maker's electrical test of the boards
    run(cli, "pcb", "export", "gerbers", "--layers", ",".join(GERBER_LAYERS), "--subtract-soldermask",
        "--no-protel-ext", "--output", plots + os.sep, board_path)
    run(cli, "pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2",
        "--output", plots + os.sep, board_path)
    pcbnew.IPC356D_WRITER(board).Write(os.path.join(plots, "%s-netlist.ipc" % name))

    zip_path = os.path.join(out_dir, "%s_gerbers.zip" % name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(plots, "*"))):
            z.write(f, os.path.basename(f))

    # Files from before the BOM was split by side
    for old in ("_bom.csv", "_bom.xlsx", "_positions.csv", "_bom_bottom.csv", "_bom_bottom.xlsx",
                "_positions_bottom.csv"):
        if os.path.exists(os.path.join(out_dir, name + old)):
            os.remove(os.path.join(out_dir, name + old))

    sides = write_boms(layout, out_dir)

    # Positions for assembly, one file per side, without the mounting holes
    for side, cli_side in SIDES:
        if side not in sides:
            continue
        raw = os.path.join(out_dir, "positions_raw.csv")
        run(cli, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", cli_side,
            "--output", raw, board_path)
        with open(raw, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        os.remove(raw)
        keep = [rows[0]] + [r for r in rows[1:] if r and re.match(r"(SW|D|U)\d+$", r[0])]
        with open(os.path.join(out_dir, "%s_positions_%s.csv" % (name, side)), "w", encoding="utf-8",
                  newline="") as f:
            csv.writer(f).writerows(keep)

    # Everything for an assembly order in one zip, for order forms with a
    # single upload box
    assembly_path = os.path.join(out_dir, "%s_assembly.zip" % name)
    with zipfile.ZipFile(assembly_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(plots, "*"))):
            z.write(f, os.path.basename(f))
        for side in sides:
            for f in ("%s_bom_%s.xlsx" % (name, side), "%s_positions_%s.csv" % (name, side)):
                z.write(os.path.join(out_dir, f), f)

    write_ordering_notes(layout, board_facts(board), os.path.join(out_dir, "ORDERING.md"),
                         os.path.basename(zip_path))
    return zip_path
