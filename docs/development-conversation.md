# Development conversation

The conversation with Claude (Claude Code, in VS Code) in which this repository
was designed and built, from the first request to the latest change. It
includes every message from Rob and every reply, with one line for each
action taken along the way (files read and written, builds and checks run).
The raw outputs of those actions, and notes the editor attached to messages,
are left out.

---

## 1. Rob

> i want to design a pcb for a cyberdeck which uses small surface mount switches. I've already built a keyboard midi device (https://github.com/CrazyRobMiles/PICO-Chord-keyboard) which uses Python code to position keys and build the 3D printable case. I want something similar for a small keyboard less than 6 inches accross. The repository contains a Gerbers.zip file for device which also uses a PICO and microswitches. I want to use the same microswitches as used in this device. The designer will include programs that create the keyboard PCB (running inside KiCad) and the case and keytops running inside FreeCAD). The Custard Cream Case project: D:\GitHub\custard-cream-case contains examples of code running in Kicad. I also want a Python program that runs on the PC and allows me to generate JSON files that describe the keyboard layout and size using a GUI. The JSON files will be consumed by KiCAD and FreeCAD to make the required artefacts.

I'll start by looking at what's here: the README, the Gerbers, and the Custard Cream Case KiCad scripts.

<details><summary>3 actions</summary>

- Inspect repo, gerbers, and reference project
- Survey reference projects
- Find KiCad scripting examples and chord case macro

</details>

No `pcbnew` code in custard-cream-case (it's FreeCAD). Let me search for KiCad scripting elsewhere and dig into the Gerbers to identify the switch footprint.

<details><summary>2 actions</summary>

- Search for pcbnew scripts across repos
- Extract gerbers and view drill, edge, paste

</details>

The Gerbers include component attributes, so I can recover the switch pad geometry directly.

<details><summary>5 actions</summary>

- Parse gerber pads by component
- Check installed KiCad switch footprints
- Compare candidate footprint pad positions
- Check FreeCAD install, Pico footprint, pcbnew python
- Check FreeCAD script conventions and footprint pads

</details>

I've got what I need on the parts. Before writing the Pico footprint generator, I'll check how the existing RPi_Pico_SMD_TH footprint handles the castellations.

<details><summary>2 actions</summary>

- Inspect Pico SMD/TH footprint pads
- Wrote common/keyboard_layout.py

</details>

Next I'll add a helper that builds key rows from text. The GUI's "grid fill" and the example layout will both use it.

<details><summary>2 actions</summary>

- Edited common/keyboard_layout.py
- Generate and validate example layout

</details>

The example layout passes validation: a 149 × 60 × 15.9 mm case, a 4×12 matrix on GP0–GP15, and M2×14 screws. Now the KiCad PCB builder.

<details><summary>2 actions</summary>

- Wrote kicad/build_pcb.py
- Run PCB builder with KiCad Python

</details>

The board was written. Next I'll check it with KiCad's DRC and render it so I can look at the placement.

<details><summary>5 actions</summary>

- Run DRC and export SVG of board
- Inspect remaining DRC violation details
- Measure library footprint courtyards
- Measure library footprint courtyards
- Apply fixes, rebuild PCB, rerun DRC

</details>

Only cosmetic silkscreen issues are left; the 232 unconnected items are expected because nothing is routed yet. I'll tidy those up, then render the board to check placement visually.

<details><summary>4 actions</summary>

- Rebuild, DRC, export SVG, check converter
- Show remaining DRC, screenshot SVG via Edge
- Read output/cyberdeck40/board.png
- Inset Pico silkscreen outline

</details>

Now the FreeCAD case builder. It follows the same pattern as custard-cream-case: a `sys.path` bootstrap, Part solids, and `Mesh.export` to an output folder.

<details><summary>2 actions</summary>

- Wrote freecad/build_case.py
- Run case builder headless in FreeCAD

</details>

It builds in about 11 seconds. Now I'll check the geometry the way custard-cream-case does: each printed part should be one connected solid, and no two parts should overlap in the assembled position.

<details><summary>1 action</summary>

- Check solids validity and part interference

</details>

Every part is a single valid solid, and no pair overlaps (tray/plate/PCB/switches/Pico/keycaps). The keycaps have legends cut. I'll render the STLs to eyeball the design.

<details><summary>5 actions</summary>

- Check matplotlib availability
- Render iso and cross-section views
- Read a working file
- Read a working file
- Add keycodes, row parser, matrix options

</details>

Now the GUI itself.

<details><summary>1 action</summary>

- Wrote designer/keyboard_designer.py

</details>

I'll tidy up two clumsy bits before testing: the bolted-on rotate method and the Pico-centring expression in `add_rows`.

<details><summary>1 action</summary>

- Tidy designer and compile-check

</details>

Now I'll drive the GUI from a test harness: load it, exercise the edits, save, and take a screenshot.

<details><summary>4 actions</summary>

- Drive GUI programmatically and screenshot
- Read a working file
- Fix drag snap, pitch scaling, rerun GUI test
- Check pitch change result

</details>

Changing the pitch to 12.5 mm now spreads the keys out correctly, and the validator flags the case as too wide (161 mm), as it should. Screenshot:

<details><summary>1 action</summary>

- Read a working file

</details>

The designer works. One cosmetic fix: longer labels like "Bksp" and "Shft" spill past their caps, so the label font should shrink to fit the width.

<details><summary>2 actions</summary>

- Scale key label font to fit
- Read a working file

</details>

Next I'll test the code paths the example doesn't touch: rotated keys, a Pico on the front at 90°, and the rows parser. I'll run that layout through KiCad and FreeCAD too.

<details><summary>1 action</summary>

- Create test layout with rotation and front Pico

</details>

The validator correctly caught the rotated space bar hitting "G". I'll move the bottom row down 2 mm and rebuild.

<details><summary>5 actions</summary>

- Build PCB and case for test layout, verify
- Fix Pico silk, rerun DRC both boards, render
- Read a working file
- Wrote firmware/code.py
- Clean test output, add gitignore, compile check

</details>

Now the README.

<details><summary>1 action</summary>

- Wrote README.md

</details>

I've built the whole toolchain and run it end to end on an example keyboard. Nothing is committed yet.

**The switch:** the switch pads in your Gerbers sit at ±3.98, ±2.25 mm and are 1.55 × 1.3 mm. That exactly matches KiCad's `Button_Switch_SMD:SW_SPST_PTS645` footprint (C&K PTS645 6×6 mm SMD), so that's what the PCB uses.

**Custard Cream Case:** it turned out to contain only FreeCAD scripts, no KiCad code. I followed its FreeCAD conventions, and the KiCad script uses KiCad 8's own `pcbnew` Python module.

**What's in the repo:**

| File | Runs in | Does |
|---|---|---|
| [common/keyboard_layout.py](common/keyboard_layout.py) | anything | Shared JSON format, defaults, part dimensions, geometry, key matrix assignment and validation. All the other programs import it, so they always agree. |
| [designer/keyboard_designer.py](designer/keyboard_designer.py) | Python on the PC (tkinter, nothing to install) | GUI to drag keys, holes and the Pico around, edit labels and keycodes, type in rows of keys, undo/redo. A live problems list flags overlaps, a case over 6", pin clashes and so on. |
| [kicad/build_pcb.py](kicad/build_pcb.py) | KiCad's Python, or the KiCad scripting console | Writes a `.kicad_pcb` with the outline, switches, diodes, Pico and mounting holes, all placed and connected to their nets. |
| [freecad/build_case.py](freecad/build_case.py) | FreeCAD macro, or headless `freecadcmd` | Makes the tray, top plate and keycaps (with engraved legends) and exports the STLs. |
| [firmware/code.py](firmware/code.py) | CircuitPython on the Pico | Reads the same JSON, so the wiring and keycodes always match the board. |
| [layouts/cyberdeck40.json](layouts/cyberdeck40.json) | — | Example: 45 keys in 4×12, case 149 × 60 × 15.9 mm (5.87"). |

**Design choices worth checking:**
- **Pico on the back:** the KiCad script generates the Pico footprint itself. On the back it's soldered flat by its castellations, with no through-holes. My first version used through-holes, and DRC showed them shorting into the front switch pads. Without them the Pico can sit right under the keys.
- **Diodes:** one SOD-123 diode per key, on the front in the gap between rows, so all the surface-mount parts are on one side.
- **Keycaps:** each one has a lip that's caught under the top plate and rests on its switch plunger.
- **Fixing:** the PCB is clamped between a ledge in the tray and a rib under the plate. M2×14 self-tapping screws go in from underneath.
- **Not covered by tests:** the GUI's mouse panning, the right-click menu and the file and "Add rows" dialogs. The firmware hasn't been run on a Pico either.

**How I checked it:**
- **KiCad:** DRC on the example board and on a second test board (rotated keys, Pico on the front) is clean. The only exceptions are the expected "U1 not in a library" note for the generated Pico footprint and the unrouted connections.
- **FreeCAD:** the tray and plate are each one valid solid. No two parts (tray, plate, PCB, switches, Pico, 45 keycaps) overlap, and cross-sections show the stack as designed.
- **Designer:** I drove it from a script (select, drag, edit, multi-edit, undo/redo, holes, box select, save) and checked screenshots.

**Still to do:**
- **Routing:** the PCB comes out placed but not routed. Route it by hand or with KiCad's Freerouting plugin.
- **Fit:** nothing has been printed yet. The clearance numbers (keycap gap, flange play, legend depth) are first guesses, and they're all on the designer's Case tab.

The README covers the workflow, the JSON format and the assembly. Generated files go to `output/`, which is in `.gitignore`.

---

## 2. Rob

> I'd like the keyboard to be 170mm wide. Can we have the option to have rows offset as they would in a "proper" keyboard.

I'll make three changes:

- **Width limit:** turn the hard-coded 6" limit into a layout setting (`case.max_width`), defaulting to 170 mm.
- **Row stagger:** add a stagger option that works when typing in rows and on existing keys.
- **New example:** add a properly staggered layout that uses the extra width.

<details><summary>8 actions</summary>

- Find width limit uses and row grouping code
- Add width setting, stagger functions, staggered example
- Inspect broken lines
- Read common/keyboard_layout.py
- Edited common/keyboard_layout.py
- Read common/keyboard_layout.py
- Edited common/keyboard_layout.py
- Validate staggered example

</details>

Status: the staggered example layout is in, 167 mm wide. I'm fixing a mounting hole that clashes with a bottom-row diode, then I'll add the stagger controls to the designer.

<details><summary>2 actions</summary>

- Edited common/keyboard_layout.py
- Save layouts and test stagger on ortho example

</details>

Both layouts validate. Applying the standard stagger to the ortholinear example gives a 157.6 mm case with no problems. Now the designer UI.

<details><summary>2 actions</summary>

- Locate GUI code to change
- Read designer/keyboard_designer.py

</details>

Now the designer edits: a stagger chooser in the "Add rows" dialog, a "Stagger rows..." command for existing keys, a staggered example, and the width limit as a setting.

<details><summary>3 actions</summary>

- Add stagger UI and width setting to designer
- Inspect bytes of the unmatched lines
- Debug string matching

</details>

The file is CRLF on disk (Git Bash's grep didn't report it). I'll re-run the edit reading with normal newline handling and write LF.

<details><summary>2 actions</summary>

- No-op check
- Apply designer edits and normalise line endings

</details>

Escaped newlines in my edit script are being turned into real line breaks before they reach Python. I'll fix those strings directly, and also check why the files are longer than I expect.

<details><summary>4 actions</summary>

- Inspect file layout and broken strings
- Read designer/keyboard_designer.py
- Edited designer/keyboard_designer.py
- Compile all sources and check line endings

</details>

Everything compiles. Next I'll test the new dialogs by driving them from a script, and screenshot the staggered example.

<details><summary>2 actions</summary>

- Test stagger dialogs and staggered example in GUI
- Read a working file

</details>

That's a proper staggered layout: Q 1.5u in, A 1.75u, Z 2.25u. The case is 167 mm wide, the matrix is 4×13 with 17 pins, and there are no problems. Now the PCB and case for it:

<details><summary>1 action</summary>

- Build and verify staggered PCB and case

</details>

All clean. Last step is the README.

<details><summary>1 action</summary>

- Update README for width limit and stagger

</details>

The keyboard can now be up to 170 mm wide, and rows can be offset like a normal keyboard. A new staggered example builds cleanly in both KiCad and FreeCAD.

**Width limit.** The 6" limit is now a setting, `case.max_width`, which defaults to 170 mm. You can change it as "Max case width" on the Case tab, and anything wider is flagged as an error.

**Staggered rows.** You can get them two ways:
1. **Wider keys at the start of each row**, as on a real keyboard. In "Add rows of keys" you type rows like `Tab:1.5 Q W E …`, `Caps:1.75 A S D …` and `Shift:2.25 Z X C …`.
2. **Moving whole rows sideways.** The "Add rows of keys" dialog now has a **Row stagger** setting. A new **Edit > Stagger rows...** (also on the right-click menu) does the same to existing keys: the selected ones, or all keys if nothing is selected.
   - The presets are "Standard" (0, 0.25, 0.75u), "Standard with number row" (0, 0.5, 0.75, 1.25u) and "Half key (brick)".
   - You can also type your own values. Rows past the end of the list don't move, so the bottom row of modifiers stays put. Undo works, and the key matrix is reassigned afterwards.

**New example: [layouts/cyberdeck_staggered.json](layouts/cyberdeck_staggered.json)**, also under File > New from example (staggered).
- 44 keys on a 12 mm pitch (bigger keys than the 11.5 mm grid version). It's staggered like a real keyboard, with Q, A and Z at 1.5, 1.75 and 2.25 units in.
- The case is 167 × 65 × 15.9 mm, and the matrix is 4×13, using GP0–GP16.
- The number row, `'`, `/`, Home/End and PgUp/PgDn are on the Fn layer.
- The Pico sits on the back with its USB at the top edge. The four mounting holes are in the top and bottom margins.

For that example:
- **Designer:** shows no problems.
- **KiCad:** DRC is clean apart from the usual note about the generated Pico footprint and the unrouted tracks.
- **FreeCAD:** the tray and plate are single valid solids, and no parts overlap.
- **Grid example:** [layouts/cyberdeck40.json](layouts/cyberdeck40.json) is unchanged apart from the new width setting.

**Two things to know:**
- **Space bar:** it is 4u (about 46 mm) with a single switch in the middle, like every key, so it will rock a little if you press near an end.
- **Column wiring:** with a stagger, the column traces run at a slight slant on the PCB.

I also converted the source files to consistent LF line endings and updated the README.

---

## 3. Rob

> I'd like a 3D printable keyboard case with holes for each of the keys. Behind the hole will sit a keycap that rests on top of the key switch. Each keycap will be printed in two colours so for a complete keyboard. Take a look at Example 21 party tags in D:\GitHub\Python-in-FreeCAD for how to merge text into 3D printed objects. For the keyboard I want two STL files, one containing the keycaps with letter holes in, and the other containing the letters to go into those holes.

I'll start by reading the party tags example to see how it merges the text.

<details><summary>7 actions</summary>

- Find Example 21 party tags
- List examples and search for party tags
- Read Party Tags example
- Read embedded text notes and current legend code
- Read freecad/build_case.py
- Read freecad/build_case.py
- Add inlay legend mode and legends STL export

</details>

The code changes are in. Next I'll switch both example layouts to two-colour inlay, then build and check the two STLs.

<details><summary>1 action</summary>

- Switch layouts to inlay and build case

</details>

Both STLs are written. Now I'll check they really fit together: no overlap, letters plus keycaps equal solid keycaps, the letters flush with the top, and every key has a legend.

<details><summary>6 actions</summary>

- Verify inlay letters exactly fill keycap holes
- Render two-colour keycap top view
- Read a working file
- Edited freecad/build_case.py
- Rebuild both cases, recheck inlay fit and overlaps
- Read a working file

</details>

`,` and `.` are now about 1.5 mm and readable. Last step is the README: two-colour printing instructions and the new legend option.

<details><summary>5 actions</summary>

- Find README legend references
- Document two colour keytops in README
- Get Python-in-FreeCAD repo URL for README link
- Point README link at GitHub repo
- Final compile check and list STLs

</details>

The keycaps now come out as two STL files for two-colour printing: `Keycaps.stl` (keycaps with letter-shaped holes) and `KeycapLegends.stl` (the letters that fill them). I've generated both for the two example layouts, but haven't test-printed them yet.

The case with a hole per key was already in place. `Plate.stl` has a hole for every key. Behind each hole sits a keycap whose lip catches under the plate and which rests on its switch.

**How the letters work:** it follows the Party Tags method. Each key's label is made into solid letters 0.6 mm deep (three 0.2 mm layers), level with the top of the keycap. The script cuts those letters out of the keycap and keeps them as a separate part. Both files are laid out the same way for printing, so they share coordinates and the letters sit exactly in their holes.

**Printing:** as in the Python-in-FreeCAD tag example:
1. Drag both STLs into the slicer together.
2. Answer **Yes** to "Load as a single object with multiple parts".
3. Give the `KeycapLegends` part the second filament.

The keycaps print flange down, so the letters are the last few layers.

**Checks:**
- **Fit:** on all 44 keys of the staggered layout, letters and keycaps don't overlap, and together they make up exactly the plain keycaps. Every key has a legend.
- **Meshes:** both STLs are clean closed meshes in matching positions.
- **Case:** the plate, tray and keycaps still don't clash.
- **Legibility:** a top-view render showed the letters clear. The `.` and `,` came out under 1 mm, so small symbols are now scaled up to about 1.5 mm.

**Other changes:**
- `inlay` is now the default legend style, and both example layouts use it. `engrave` (one colour, sunken letters) and `none` are still options on the designer's Case tab. Neither of those makes the letters file.
- I used `Part.makeWireString` for the text rather than `Draft.makeShapeString` as in the example. It produces the same letter shapes without adding temporary objects to the document.
- The README has a new "Two colour keytops" section with the slicer steps and a link to the Party Tags example.

The 0.6 mm depth and the letter sizes are first guesses. Both are settings if a test print looks too thin or too bold.

---

## 4. Rob

> At the moment there are no tracks on the circuit. Can these be added?

Adding tracks means autorouting. The usual tool is Freerouting, a Java autorouter that KiCad hands the board to as a Specctra DSN file. First I'll check whether Java or Freerouting are already on this machine.

<details><summary>3 actions</summary>

- Check for Java and Freerouting
- Read partial output and check Java installs
- Probe pcbnew API for vias and HitTest

</details>

The API has what I need. Here's the router:

<details><summary>4 actions</summary>

- Wrote kicad/autoroute.py
- Separate track occupancy, fix corner test
- Read kicad/build_pcb.py
- Integrate router and run on staggered layout

</details>

Everything routed on the first pass in under 4 seconds. Now the real test is KiCad's DRC:

<details><summary>1 action</summary>

- Run DRC on routed board

</details>

DRC passes with zero clearance violations and zero unconnected items. The only message is the usual one about the generated Pico footprint. I'll render the copper to see how the routing looks.

<details><summary>3 actions</summary>

- Export copper layers to PNG via Edge
- Retry screenshot with output
- Read output/cyberdeck_staggered/both.png

</details>

That's too small to judge, so I'll render it larger.

<details><summary>3 actions</summary>

- Render routed board larger
- Read output/cyberdeck_staggered/both.png
- Route and DRC the other layouts

</details>

Both route completely with clean DRC. As a stress test I'll squeeze the staggered layout down to the tightest pitch the switches allow, which leaves much less room between rows.

<details><summary>1 action</summary>

- Stress test routing at 10.4mm pitch

</details>

The tightest pitch also routes completely with clean DRC, in about 3 seconds. I'll delete the test files and update the docs, which still say the board comes out unrouted.

<details><summary>4 actions</summary>

- Remove test outputs and find docs to update
- View README sections to edit
- Update README and docstring, add routing to layouts
- Add routing to README schema, rebuild boards

</details>

The board now comes out fully routed. On both example layouts, KiCad's DRC reports no clearance errors and no unconnected connections, and routing takes about 4 seconds.

There's no Java or Freerouting on your machine, so rather than install them I wrote a small autorouter, [kicad/autoroute.py](kicad/autoroute.py). `build_pcb.py` now runs it automatically after placing the parts, so building the board still needs only KiCad.

**How it routes:**
- **Grid:** it works on a 0.5 mm grid on the front and back copper. It finds each connection with a path search and uses vias to change sides.
- **Clearance:** it keeps 0.2 mm from every pad of another net, using KiCad's own pad shapes, and 0.5 mm from the board edge.
- **Rows and columns:** the front prefers horizontal tracks and the back vertical ones. The rows end up on the front, running between the rows of switches through the diodes. The columns run up and down the back.
- **Under the Pico:** nothing goes on the back under the Pico, where its own test pads would touch the tracks.
- **Failures:** if a connection can't be made, it routes again with the failed nets first. If anything is still left, it prints a warning and leaves that connection for you to draw by hand.

I also tested it on a front-mounted, rotated Pico layout and on a squeezed 10.4 mm pitch (the tightest the switches allow). Both routed completely with clean DRC.

**Two changes to know about:**
- **GND:** the Pico's GND pins are no longer on a net. Nothing on the board needs ground and the Pico joins its own GND pins internally. Without this change, KiCad would want them wired together.
- **Track style:** all tracks are horizontal and vertical with square corners. They're electrically fine but not as neat as hand routing.

Track width, clearance, via size (0.6 / 0.3 mm, JLCPCB standard), grid and costs are in a new `routing` section of the layout. Set `"enabled": false` to get an unrouted board. The README has a new "Tracks" section.

I regenerated both example boards. If you have `cyberdeck_staggered.kicad_pcb` open in KiCad, reload it to see the tracks.

<details><summary>1 action</summary>

- Read finished background search output

</details>

The slow background search I started earlier has finished. It confirms there's no Java or Freerouting anywhere on your machine, so nothing changes: the built-in router is still the way the board gets its tracks.

---

## 5. Rob

> is there enough clearance around the keycaps when they are fitted into the plate?

I'll measure the actual gaps in the generated model rather than rely on the design numbers. For each keycap that means the gap to its plate hole, to the plate underside, to its neighbours, to the switch, and to the rib and screw pillars.

<details><summary>1 action</summary>

- Measure real keycap clearances in the model

</details>

**Short answer:** in the CAD model, yes, nothing touches. On a real FDM print, though, the sideways gap is tighter than I'd like, and the lip that holds each keycap in is thin.

Measured from the generated staggered model:

| Gap | Value | Verdict |
|---|---|---|
| Keycap side to plate hole | 0.25 mm per side | **Tight for FDM** |
| Lip that reaches under the plate (retention) | 0.35 mm per side | **Thin** |
| Free play between lip top and plate underside | 0.30 mm | OK (switch travel is 0.25 mm) |
| Keycap underside to switch body | 1.5 mm | Plenty |
| Keycap lip to neighbouring keycap | 0.9 mm | OK |
| Keycap to plate rib and screw pillars | 0.95 mm | OK |
| Keycap to diodes (about 1.35 mm tall) | about 3.6 mm | Plenty |

**Why 0.25 mm is a worry:**
- **Print error:** FDM prints holes about 0.1–0.2 mm small and outside edges about 0.1 mm big. With both parts printed, a nominal 0.25 mm gap can shrink to almost nothing, so keys may stick or rub.
- **Elephant foot:** the plate prints top face down, so its first layers squash slightly and narrow the hole edges on the visible top face.

The lip only overlaps the plate by 0.35 mm, and making the gap bigger eats into that overlap. Keys could then be pulled or shaken out.

**What I'd change (defaults):**
- `key_clearance` 0.25 → **0.35 mm**
- `flange` (the lip) 0.6 → **0.9 mm**

That gives a 0.55 mm overlap under the plate and a 0.5 mm gap between neighbouring lips. A 1u keycap shrinks slightly, from 9.9 to 9.7 mm on the 12 mm pitch. Both values are already on the designer's Case tab if you'd rather tune them after a test print. Printing one row of keys plus a strip of plate first is a cheap way to find the right fit for your printer.

**One mistake of mine this turned up:** the README says to print the plate "the right way up". That's wrong: the rib and screw pillars hang below the plate, so printed that way the whole plate would be a 6 mm overhang. It needs to print top face down, with the rib and pillars pointing up. I'd also make `Plate.stl` export already flipped, so it drops onto the slicer bed the right way.

Shall I make those changes: the new defaults, a flipped `Plate.stl` and corrected print notes?

---

## 6. Rob

> make the changes please

<details><summary>2 actions</summary>

- Locate defaults, README and export lines
- Apply new clearance defaults, flipped plate export, docs

</details>

Both layouts still validate. Next I'll rebuild both cases and re-measure the gaps. I'll also check that the exported plate lies flat with its top face on the bed.

<details><summary>1 action</summary>

- Rebuild cases, re-measure clearances, check plate orientation

</details>

I've made all three changes and rebuilt both cases. The new measurements match the plan:

| Gap | Before | Now |
|---|---|---|
| Keycap side to plate hole | 0.25 mm | **0.35 mm** |
| Lip reaching under the plate | 0.35 mm | **0.55 mm** |
| Keycap lip to neighbouring keycap | 0.9 mm | 0.5 mm |
| Keycap to rib and screw pillars | 0.95 mm | 0.75 mm |
| Free play under the plate | 0.3 mm | 0.3 mm |

- **Clearances:** the new defaults are `key_clearance` 0.35 mm and `flange` (the lip) 0.9 mm. Both example layouts use them and still pass validation. The 1u keycap is now 9.7 mm on the 12 mm pitch (9.2 mm on the 11.5 mm grid layout).
- **Plate print orientation:** `Plate.stl` is now exported upside down, ready to print top face down with the rib and pillars pointing up. I checked it sits at Z=0 with the whole top face on the bed (holes excepted), and it's the same solid as the assembled plate. The FreeCAD model also has a hidden `PlateForPrinting` object showing it this way round.
- **README:** corrected the print orientation notes, explained the clearance and lip values, and updated the keycap sizes and example JSON.

There are still no overlaps between tray, plate, PCB, switches and keycaps. The two-colour keycaps and letters still fit exactly on all 44 keys.

These clearances are still estimates until something is printed. A row of keycaps and a strip of plate is a quick test. If the keys rattle or stick, adjust the two values on the designer's Case tab.

---

## 7. Rob

> I'm concerned that for long keys (shift, space) a single central swtich will not work. If the user presses one side of the key it will pivot abut the swtich but not press it. I want to investigate this with a view to perhaps putting more than one switch unders some keys. Can you make me a very small test keyboard which just contains a number of keys of different lengths. Can you add a 3d printable mock circuit board with spaces where I can put switches as if they were soldered onto it. I want to assemble the keyboard around this mock keyboard so that I can test how well the keys work.

This needs one new capability in the shared model: a key with more than one switch under it. So far every key has exactly one switch in the middle. Here's the plan:

1. **Model:** add a per-key `switches` list, giving switch positions along the key in key units from its centre (`[0]` is the current single switch). KiCad, FreeCAD, validation and the designer all learn to handle it. Extra switches on a key are wired in parallel, so pressing any of them registers the key.
2. **Mock PCB:** FreeCAD makes a printable board with the outline, thickness and holes of the real one. Each switch gets a low locating fence that holds it in place sitting on the board surface, at the height it would be if soldered. Small holes under each leg let you solder wires on if you want to test the switches electrically.
3. **Test keyboard:** a small layout with 1u, 1.5u, 2u, 2.25u, 2.75u and 4u keys. Each long key comes once with a single central switch and once with a switch near each end, so you can compare them directly.

I'll start with the model.

<details><summary>2 actions</summary>

- Find switch geometry code in model
- Add switch positions to model

</details>

Now validation needs to check every switch, not just the first. It should also catch two switches on one key that are too close together, and a switch placed off the end of its key.

<details><summary>1 action</summary>

- Validate all switches per key and test

</details>

One replacement contains a backslash line-continuation that got mangled on the way to Python, and nothing was written. I'll apply the other three again and do that one with a direct edit.

<details><summary>4 actions</summary>

- Apply validation edits without backslash
- Read common/keyboard_layout.py
- Edited common/keyboard_layout.py
- Test multi-switch validation

</details>

Validation works: a two-switch space bar is accepted, while switches too close together or off the end are caught. Next, KiCad gets one footprint per switch, wired in parallel.

<details><summary>2 actions</summary>

- View KiCad switch placement code
- Place one footprint per switch in KiCad

</details>

Now FreeCAD: reference switch models at every switch position, and the new mock PCB.

<details><summary>3 actions</summary>

- View FreeCAD switch model code
- View docstring part list
- Add mock PCB and multi-switch models to FreeCAD

</details>

Now the test layout itself. Each long key appears twice, once with one switch and once with two, so you can compare them side by side:

<details><summary>1 action</summary>

- Create and validate the switch test layout

</details>

`add_key_rows` doesn't give new keys a `switches` entry; only loading a file fills it in. I'll make new keys get the default too.

<details><summary>6 actions</summary>

- Fix default switches and validate test layout
- Build test case and verify mock PCB fit
- Measure fence clearance; build and DRC test PCB
- Locate designer key field code
- Read key field code sections
- Add switches field and menu to designer

</details>

The designer changes compile. I'll add the test keyboard to the File menu, then drive the designer from a script to check the new field and menu.

<details><summary>2 actions</summary>

- Add menu entry and test designer switches field
- Read a working file

</details>

It works, but the keycaps hide the switch outlines, so you can't see where the switches are. I'll draw a small marker on top of each key at every switch position.

<details><summary>5 actions</summary>

- Find label drawing line
- Read designer/keyboard_designer.py
- Edited designer/keyboard_designer.py
- Re-run designer test and screenshot
- Read a working file

</details>

The switch positions now show as dashed circles on each key. I'll check the existing examples still build unchanged and render the mock PCB to look at the fences.

<details><summary>2 actions</summary>

- Rebuild examples, DRC, and render mock PCB
- Read a working file

</details>

That 3D render is muddy, so I'll draw a plain top view instead: the board with its wire holes, the fences, and switch bodies shown as dashed outlines.

<details><summary>6 actions</summary>

- Render mock PCB top view in 2D
- Read a working file
- List README sections
- Read README output list and key schema
- Document multi-switch keys, test keyboard and mock PCB
- Resave layouts with switches field

</details>

The test keyboard is ready to print: 12 keys of different lengths, a mock PCB that holds the switches as if soldered, and the usual tray, plate and two-colour keycaps.

To make this possible, keys can now have more than one switch. Each key has a `switches` list giving positions along the key: `[0]` is one switch in the middle (the default), and `[-1.5, 1.5]` puts a 4u key's switches half a unit in from each end. The switches of one key are wired in parallel and share its matrix position, so the firmware needs no change. The KiCad board, case, validation and designer all follow the list.

**The test keyboard** ([layouts/switch_test.json](layouts/switch_test.json), also **File > New switch test keyboard**):
- **Keys:** 1u, 1.5u, 2u, 2.25u, 2.75u and 4u. Every key of 2u or longer comes twice: one with a single central switch, and one with two switches, labelled `x2`. 1u and 1.5u are too short for two switches side by side, since each switch needs 10.15 mm.
- **Size:** the case is 92 × 65 mm, and the keys type A to L.
- **Files:** `output/switch_test/` has `MockPCB.stl`, `Tray.stl`, `Plate.stl`, `Keycaps.stl` and `KeycapLegends.stl`.

**The mock PCB** (`MockPCB.stl`, now made for any layout):
- **Fit:** it has the real board's outline, 1.6 mm thickness and mounting holes, so it fits the tray and plate in the same way.
- **Fences:** each switch position has a 1 mm high fence round the body, with gaps for the legs. A PTS645 drops in and sits on the surface at its soldered height, with 0.15 mm all round. That should be a snug fit, but printers vary, so a dab of glue may help.
- **Wire holes:** a 1 mm hole under each leg lets you solder wires on if you want the keys to type.

**What I checked in the model:**
- **Clearances:** the switches sit in their fences with no overlaps against the mock board, tray, plate or keycaps.
- **Plungers:** every keycap rests on all of its plungers (two for the `x2` keys).
- **Real PCB:** the test layout also builds as a real board and routes with clean DRC, so you could have proper boards made for it instead.
- **Examples:** both existing examples still build and pass DRC unchanged.
- **Designer:** the new **Switches** field and the right-click **One switch / Two switches** menu work, and switch positions show as dashed circles on each key. Switches placed too close together or past the end of a key are reported as problems.

**One thing the test won't show:** a key with two switches pressed in the middle may need both switches to give way, and they won't click at exactly the same moment. That's worth trying as well as pressing near the ends.

The README has a new "Trying out long keys" section. If two switches work better, set `switches` on the long keys in your real layout.

---

## 8. Rob

> I want to change the way that the keys are retained. At the moment they have a flange on the back which means that they must be printd with the flange on the back plate, meaning that the legends on a key are formed on the top, which is not very smooth. I want to print the keys with their top surface on the base plate but I don't want to use support. Can you therefore change the flange so that it is tapered rather than just sticking out which would mean that it could be printed upside down using overhangs. Also give the holes in the keyboard plate the same angled sides as the keys so that they don't tend to stick.

Here's how I'll change it.

**Keycap:** the flat flange becomes a tapered shoulder. Going down the key, the body widens at 45° out to the full flange width, then a short vertical band runs down to the bottom edge. Printed upside down (top face on the bed), the shoulder is just a 45° overhang, so no support is needed. The legends end up in the first layers against the bed, which gives the smooth top you want.

**Plate hole:** its lower part gets the same 45° slope, matching the keycap profile with `key_clearance` all round. The shoulder seats against the sloped wall rather than a flat edge, which centres the key and stops it sticking. With these surfaces parallel, the key's free play up and down works out to `key_clearance × tan(angle)`, so 0.35 mm.

**Export:** the keycap and legend STLs will come out flipped, ready to print top face down.

I'll start with the shared model: the angle setting, the shoulder height in the stack, and validation.

<details><summary>3 actions</summary>

- Locate flange settings and stack
- Read the lines to change
- Add taper settings and validation to model

</details>

The model is consistent: the shoulder ends at 8.5 mm, below the plate top at 9.4 mm, and the web between holes is still 0.4 mm wide at the plate underside. Now the FreeCAD shapes.

<details><summary>6 actions</summary>

- Read keycap, plate hole and print layout code
- Read freecad/build_case.py
- Build tapered keycaps and plate holes, flip print
- Build tapered test case and verify fit and printability
- List downward-facing faces in print layout
- Remove sliver ledge, rebuild and recheck

</details>

The sliver is gone. The only downward faces left are the letter-pocket floors that the letters fill. Next I'll draw a cross-section of a key in its hole to check the shape by eye.

<details><summary>7 actions</summary>

- Render cross-section of tapered key in plate
- Read a working file
- Rebuild full examples and verify taper and inlay
- Find README text about flange and printing
- Read README fit and print sections
- Update README, resave layouts, find designer field
- Add flange angle to designer Case tab and test

</details>

The keycaps now print upside down, top face on the bed, with no support. The plate holes have matching sloped sides. I've rebuilt all three layouts; nothing has been printed yet.

**Keycap shape:** round the bottom there's still a 1 mm straight band. Above it, instead of a flat ledge, the lip now slopes in at 45° to the body of the key. Printed upside down, that slope is just a 45° overhang. The legends end up in the first 0.6 mm on the bed, so the key tops come out smooth and the letters flush. `Keycaps.stl` and `KeycapLegends.stl` are exported already flipped and still line up for two-colour printing.

**Plate holes:** each hole is now the keytop's own shape with 0.35 mm clearance all round, so its lower part slopes at the same 45°. A key pushed up by its switch seats on the slope, which centres it rather than catching on an edge.

**Checks on all three layouts:**
- **Fit:** nothing overlaps. At rest every key has a 0.25 mm gap to the plate, which is the 0.35 mm clearance measured across the slope.
- **Seating:** every key moves up 0.35 mm before it seats, and it touches on the sloped shoulder, not a flat edge.
- **Overhangs:** in the flipped print layout, nothing faces down flatter than 45° except the floors of the letter pockets, which the letters fill as they print first.
- **Two-colour fit:** the letters still exactly fill their pockets on all 44 keys of the staggered layout.

**Trade-offs:**
- **Rattle:** the key's up-and-down free play now comes from the side clearance and the slope (0.35 × tan 45°), not `flange_clearance`. It's 0.35 mm, a little more than the old 0.3 mm. Reducing `key_clearance` reduces it, but makes sticking more likely.
- **Thinner plate webs:** the sloped holes eat into the plate between keys. On the 12 mm pitch the web is still 1.6 mm wide at the top, but only 0.4 mm at the underside.

There's a new `flange_angle` setting (default 45°) on the designer's Case tab. The designer warns if the angle won't print upside down, if the shoulder is too tall for the plate, or if neighbouring sloped holes meet under the plate. The README's fit and printing notes are updated.

The switch test keyboard has the new keys too. Printing it is a good way to check the fit before doing a full keyboard.

---

## 9. Rob

> Test print went well. Only problem is that when the mock pcb is pushed up against the front panel the switches are pressed in. We need to either reduce the thickness of the keys or increase the height of the front plate by a mm or so. Putting two switches on the same key works well, but we will need to modify the debouce code to stop double entry.

Glad the test print went well. Both problems are fixable.

**Switches pressed in.** In the current design each keytop rests on its plunger with only 0.35 mm of free play before it seats against the plate. A tact switch clicks after just 0.25 mm of travel, so normal print tolerances in the keytops, mock PCB and plate can easily use that up. I'll add a `plunger_gap` setting (default 1.0 mm) that lifts the plate and its sloped holes 1 mm further above the switches. The keytops get 1 mm taller so they still stand 2 mm proud. The case grows 1 mm, from 15.9 to 16.9 mm.

**Double entry.** The two switches under a key are wired in parallel, so electrically they're one switch. If you press off-centre, or the key rocks, one switch can open a moment before the other closes. The firmware sees that as a release followed by a new press. The fix is to delay releases: a key only counts as released once it has stayed open for about 50 ms. A press that arrives during that window is treated as the same keystroke.

I'll start with the height.

<details><summary>5 actions</summary>

- Locate stack and hole profile code
- Read key_profile
- Add plunger_gap to stack and plate holes
- Add designer field, resave and validate layouts
- Rebuild cases and check seating lift

</details>

On all three layouts the keys now rise 1.35 mm before seating on the slope, up from 0.35 mm, and nothing overlaps. That's 1.1 mm more than the 0.25 mm switch travel. Now the firmware.

<details><summary>7 actions</summary>

- Read firmware/code.py
- Wrote firmware/code.py
- Tidy pressed signature, add firmware defaults to layouts
- Simulate firmware debounce scenarios on PC
- Find README parts to update
- Read the shoulder paragraph
- Read remaining parts referencing old heights

</details>

Updating the README with the new heights, the gap setting and the firmware debouncing, then I'm done.

<details><summary>1 action</summary>

- Update README heights, gap and firmware notes

</details>

Both fixes are in, and I've rebuilt all three layouts.

**Switches pressed in:** I raised the plate by 1 mm rather than making the keys thinner. Only the gap between the switches and the plate was the problem, and thinner keys would have needed the lip and shoulder moved as well.
- **Gap setting:** a new `plunger_gap` setting, default 1.0 mm, lifts the plate and the sloped parts of its holes above the switches. It's "Gap above switches" on the designer's Case tab.
- **Free play:** a keytop can now rise 1.35 mm before it seats, instead of 0.35 mm. A PTS645 clicks after 0.25 mm of travel.
- **Keytops:** they're 1 mm taller, so they still stand 2 mm proud of the plate.
- **Case:** 1 mm taller, now 16.9 mm. It still takes M2 × 14 mm screws.
- **Mock PCB:** unchanged, since it sits in the tray as before.
- **Checks:** on all three layouts nothing overlaps, and every key seats on its sloped shoulder only after rising 1.35 mm. The keytops still print upside down without support.

**Double entry:** [firmware/code.py](firmware/code.py) now holds back each release for 50 ms. If the key closes again within that time, it's treated as the same key press. If your CircuitPython supports it, `keypad` also ignores any change shorter than three 10 ms scans.

I ran the firmware on the PC with fake CircuitPython modules. I haven't run it on a Pico yet.
- **Rocking key:** a two-switch key that opens for 15 ms in the middle of a press types once.
- **Bouncy press:** a slow press whose contacts bounce several times types once.
- **Double tap:** a real double tap 100 ms apart still types twice.
- **Fn layer:** still works.
- **Older CircuitPython:** without `debounce_threshold` it falls back cleanly.

The cost is that every key reports its release 50 ms late, which you won't notice when typing. Both timings are in a new `firmware` section of the layout file (`release_hold_ms` and `debounce_scans`), so you can tune them without editing the code. Copy the updated `switch_test.json` to the Pico as `layout.json` along with the new `code.py`.

The new part needed for your test keyboard is `Plate.stl`. `Keycaps.stl` and `KeycapLegends.stl` have changed too, because the keytops are 1 mm taller. `Tray.stl` and `MockPCB.stl` are the same as before. The README covers the new gap, the heights and the debouncing.

---

## 10. Rob

> Would it be possible to make a Micro Python version of the code

Yes, this is possible. MicroPython can act as a USB keyboard on the Pico through micropython-lib's `usb-device-keyboard` package, which needs MicroPython 1.23 or later. You have a clone of micropython-lib, so I'll check that library's exact API first.

<details><summary>4 actions</summary>

- Read micropython-lib USB keyboard API
- Read modifier encoding and example
- Read rest of keyboard example
- Wrote firmware/micropython/main.py

</details>

One simplification before testing. Comparing the keys to send against what was last sent is enough on its own, so I'll drop the separate "changed" bookkeeping.

<details><summary>2 actions</summary>

- Simplify MicroPython send logic
- Simulate MicroPython firmware with real HID driver

</details>

That's a gap in my fake modules (`usb.device` wasn't attached to `usb`), not in the firmware. Fixing the harness:

<details><summary>4 actions</summary>

- Fix fake module wiring and rerun simulation
- Find firmware mentions in README
- Document MicroPython firmware in README
- Check backslash path survived

</details>

Yes, there's now a MicroPython version: [firmware/micropython/main.py](firmware/micropython/main.py). I tested it on the PC with simulated hardware and the real keyboard driver, but haven't run it on a Pico yet.

It needs **MicroPython 1.23 or later** (the first version that can act as a USB keyboard) and micropython-lib's `usb-device-keyboard` package. To install:

```
mpremote mip install usb-device-keyboard
mpremote cp firmware/micropython/main.py :main.py
mpremote cp layouts/switch_test.json :layout.json
```

Reset the Pico and it becomes a keyboard. It keeps its USB serial port, so mpremote and Thonny still connect, and Ctrl-C stops it.

It does the same job as the CircuitPython version and reads the same `layout.json`, including the Fn layer and the `firmware` debounce settings. The differences:
- **Scanning:** MicroPython has no `keypad` module, so it scans the matrix itself every 10 ms. Each row is driven low in turn, and the columns are read with pull-ups, which suits the diodes.
- **Keycodes:** the layout's adafruit-style names (like `LEFT_SHIFT` or `FORWARD_SLASH`) are translated to HID codes in the file. Modifiers go out as modifier bits, as the library expects.
- **Debouncing:** a key must read the same on 3 scans in a row, and each release is held back 50 ms, which stops the double entry on two-switch keys.

To test it on the PC, I loaded the real `keyboard.py` from your micropython-lib clone and faked only the USB send, the pins and the clock. That checks the actual 8-byte reports the Pico would send:
- **Rocking key:** a two-switch key that opens for 15 ms mid-press types once.
- **Bouncing contacts:** one keystroke.
- **Double tap:** a real double tap 100 ms apart types twice.
- **Fn and Shift:** Fn plus a key sends its Fn code, and Shift goes out as a modifier alongside the letter.
- **Glitch:** a 2 ms glitch is ignored.

A press reaches the computer about 20 ms after the switch closes, and a release about 70 ms after it opens.

Your micropython-lib clone is from July 2024, so if the driver has changed since, check `mip` installs a compatible one. The README's "Program it" step now covers both firmwares.

---

## 11. Rob

> Does the keyboard incorporate proper behaviour of shift and control keys?

Let me check rather than guess. One thing in the code I just wrote worries me: releases are held back 50 ms, and that includes Shift, Ctrl and Fn. I'll simulate fast typing of "Ab", where Shift is let go just before b is pressed.

<details><summary>1 action</summary>

- Simulate fast Shift and Fn release timing

</details>

**Mostly yes, but there's a real bug, and I introduced it with the last change.**

**What works.** In both firmwares Shift, Ctrl, Alt and GUI are sent as proper modifiers and stay held for as long as you hold the key. Shift+A gives "A", Ctrl+C copies, Ctrl+Shift combinations work, and the computer handles Caps Lock as normal. The diodes let any combination of keys be held at once, up to the USB limit of 6 ordinary keys plus all the modifiers. A key pressed while Fn is held keeps its Fn code until you let it go, even if you release Fn first.

**The bug.** The 50 ms release hold that stops double entry on two-switch keys applies to every key, including Shift, Ctrl and Fn. When you type quickly, the gap between letting go of Shift and pressing the next key is often under 50 ms. The simulation confirms it:

- **Shift:** typing "Ab" with b pressed 20 ms after Shift is let go sends modifier byte 2 with the second letter. So it comes out as "AB".
- **Fn:** letting go of Fn and pressing a key 20 ms later still sends the key's Fn code (ONE instead of B).

Ctrl and Alt have the same problem, which could turn a fast Ctrl+C then "v" into Ctrl+V.

**The fix** is simple: release modifiers and Fn straight away, and keep the release hold only for ordinary keys. That's where double entry actually causes trouble. A modifier with two switches, like your 2.25u Shift, could then flicker off for a few milliseconds if it rocks. That only matters if a letter is pressed in that exact instant, which is far less likely than the fast-typing problem.

**One limitation that isn't a bug:** a key's `fn_keycode` is a single key, so the Fn layer can't send a character that needs Shift, such as `!` or `?`. You'd hold Shift as well. I could add combinations like `"SHIFT+ONE"` if you want symbols on the Fn layer.

Shall I make the fix in both the CircuitPython and MicroPython firmware and re-run the simulations?

---

## 12. Rob

> Does the keyboard handle the fact that CTRL and SHIFT will be held down when other keys are pressed?

Yes, holding modifiers while pressing other keys works. I'll confirm with a quick simulation holding two modifiers at once: Ctrl and Shift held, then two letters tapped.

<details><summary>1 action</summary>

- Simulate Ctrl+Shift held with key taps

</details>

**Yes.** Ctrl and Shift (and Alt and GUI) stay held for as long as you hold them, and every key pressed meanwhile is sent with them applied. The simulation confirms it with both held together:

| Time | What's held | Report sent to the computer |
|---|---|---|
| 30 ms | Ctrl + Shift pressed | modifiers = Ctrl + Shift, no keys |
| 120 ms | D tapped | Ctrl + Shift + D |
| 220 ms | D let go, E tapped | Ctrl + Shift + E |
| 320 ms | E let go | Ctrl + Shift, no keys |
| 470 ms | Ctrl and Shift let go | nothing held |

The computer sees Ctrl+Shift+D and Ctrl+Shift+E, exactly as with a normal keyboard.

**How it works:**
- **Reports:** the keyboard doesn't send characters. Every report says which keys are down *right now*: a modifier byte for Ctrl, Shift, Alt and GUI, plus up to 6 ordinary keys. A held Shift stays set in every report until you let go, and the computer applies it to whatever else is pressed. CircuitPython's `Keyboard.press()` / `release()` and MicroPython's `send_keys()` both work this way.
- **Diodes:** each key has its own diode, so holding Ctrl, Shift and a letter together reads correctly, with no phantom keys. Without diodes, three keys held at the corners of a rectangle in the matrix could make a fourth appear pressed.
- **Limits:** up to 6 ordinary keys at once, plus any number of modifiers. That's the standard USB keyboard limit and plenty for shortcuts.

The problem I raised in my last reply is still there, though. It's about letting go of the modifiers, not holding them: their release is delayed 50 ms, so in fast typing the next letter can still get Shift or Ctrl. I haven't changed anything yet. Shall I make that fix (release modifiers and Fn immediately) in both firmwares?

---

## 13. Rob

> Perhaps a better way to handle multiple switches for the same key would be to ignore switch closures if another switch for that key is already closed and do away with the timeout.

That logic is right, but the hardware already does it. On the PCB, the two switches under a key are wired **in parallel** to the same matrix position. The key reads as pressed while *either* switch is closed, and a second switch closing while the first is already closed changes nothing. The firmware never sees two separate switches, so it has nothing to ignore.

That means the double entry you saw must come from a moment when **neither** switch is closed, for example:
- **Rocking:** the end you pressed first lifts and opens just before the other end closes.
- **Bounce:** a switch bounces open as it first closes, before the second switch has made contact.

At that moment the key really is fully open. No rule about "another switch is already closed" can tell it apart from a genuine release, whether done in hardware or software. Something time-based is still needed to bridge the gap. The question is how to keep it from causing trouble.

**What I'd suggest instead**

Keep a short time filter, but only where it's needed:
- **Only on keys with more than one switch.** The firmware reads `layout.json`, which lists each key's switches, so it knows which keys those are. Letters and other single-switch keys go back to plain, quick debouncing.
- **Never on Shift, Ctrl, Alt, GUI or Fn.** They're released the moment they open, which fixes the "Ab" comes out as "AB" problem. A two-switch Shift might flicker off for a few milliseconds if it rocks. That only matters if a letter is pressed in that exact instant.

In practice the filter would apply only to keys like a two-switch Space, Enter or Backspace, where a 50 ms delay on release is unnoticeable.

**If you want your exact scheme**

You could give each switch its own matrix position and diode, so the firmware sees every switch separately and treats the key as down while any of them is closed. The matrices have room: the staggered layout has 52 positions for 44 keys. But it adds wiring, and it still double-types in the moment when neither switch is closed, so it would need the same short filter anyway.

How did you wire the two switches in your test? Were they in parallel on one input, as the PCB design has them, or on separate pins? If they were separate, the firmware would have seen two keys, and that alone would explain the double entry. Then your approach, or simply wiring them in parallel, would fix it with no filter at all.

---

## 14. Rob

> Sorry. The wiring already solves the problem. Having extra inputs for keys just adds more complication than we need. And if the user holds down s1 presses s2 releases s1 and releases s2 we get the behaviour we want with no software.

You're right, and that covers the realistic case: pressing and releasing a long key, even unevenly, keeps at least one switch closed the whole time. So the 50 ms release hold I added isn't needed. Worse, it causes the Shift/Ctrl/Fn bug.

I'll take it out of both firmwares and go back to ordinary switch debouncing only, made quicker: scans every 5 ms, and a change must be seen on 2 scans in a row (10 ms). PTS645 contact bounce lasts a few milliseconds, so that's plenty, and it keeps Shift releases prompt.

<details><summary>1 action</summary>

- Find release hold references everywhere

</details>

I'll rewrite the CircuitPython firmware, which is now simpler.

<details><summary>1 action</summary>

- Wrote firmware/code.py

</details>

Now the MicroPython version: I'll remove the release hold, scan every 5 ms, and default to 2 debounce scans.

<details><summary>2 actions</summary>

- Read MicroPython sections to change
- Remove release hold from MicroPython, model and layouts

</details>

Both firmwares compile, and the layouts now just have `debounce_scans: 2`. Re-running the simulations: the MicroPython one with real scanning, and the CircuitPython one with scripted keypad events.

<details><summary>3 actions</summary>

- Re-run both firmware simulations
- Read README debounce text
- Update README debounce description

</details>

Agreed, and it's a better design. I've removed the release timeout from both firmwares.

**What changed:**
- **Firmware:** [firmware/code.py](firmware/code.py) (CircuitPython) and [firmware/micropython/main.py](firmware/micropython/main.py) now send each press and release straight away. Multi-switch keys get no special handling. The CircuitPython version is back to a short, simple loop.
- **Debouncing:** only ordinary switch debouncing is left. The matrix is scanned every 5 ms, and a change must be seen on 2 scans in a row. That handles contact bounce while getting presses and releases to the computer within about 5–10 ms.
- **Layouts:** the `firmware` section is now just `{"debounce_scans": 2}`. Older layout files that still have `release_hold_ms` are tidied up when loaded.
- **README:** explains that the parallel wiring keeps a long key down while any of its switches is closed, with no software involved.

**Bugs fixed:** this also fixes both problems found earlier, confirmed in the simulation:
- **Fast "Ab":** typing "Ab" quickly now gives "Ab". Shift is released 5 ms after you let go, so the second letter goes out unshifted.
- **Fn release:** letting go of Fn and pressing a key straight away now sends the key's normal code.

Holding Ctrl and Shift together while tapping letters still sends the combinations, and short contact bounce is still ignored.

Copy the new firmware file and your layout to the Pico to try it.

---

## 15. Rob

> can you add a parts list for each deck. The list should be generated programatically from the keyboard layout

Yes. I'll generate the parts list from the layout file, so it always matches the keyboard: number of switches (including extra switches on long keys), diodes, Pico mounting, screw count and length, PCB size, and keytop sizes.

- **The function** goes in the shared model.
- **Running it:** a small command-line script on the PC, plus a designer menu entry.
- **Output:** Markdown (for reading or sharing) and CSV (for ordering), saved in `output/<name>/` with the other generated files.
- **Filament:** the FreeCAD build will also record the volume of each printed part, so the list can include filament quantities once the case has been built.

<details><summary>2 actions</summary>

- Check screw length helper and FreeCAD exports
- Read FreeCAD export block

</details>

First the parts list module. It's plain Python, so the designer, a command line and the FreeCAD build can all use it.

<details><summary>1 action</summary>

- Wrote common/parts_list.py

</details>

Next, the FreeCAD build. It records each printed part's volume in `prints.json`, then refreshes the parts list.

<details><summary>1 action</summary>

- Record print volumes and write parts list from FreeCAD

</details>

Now the designer menu entry. It saves the layout first, so the list matches what's on screen.

<details><summary>1 action</summary>

- Add Make parts list to designer

</details>

Same backslash mangling as before: the escaped newlines in my edit script arrived as real line breaks. I'll fix the strings directly.

<details><summary>7 actions</summary>

- Read designer/keyboard_designer.py
- Edited designer/keyboard_designer.py
- Build all cases and show generated parts list
- Fix small gram display, regenerate and inspect lists
- Test designer Make parts list menu
- Find README insertion points
- Add Parts list section to README

</details>

Each keyboard now gets a parts list made from its layout file, and I've generated it for all three: `output/cyberdeck_staggered/`, `output/cyberdeck40/` and `output/switch_test/`. Each has a `parts_list.md` to read or share and a `parts_list.csv` to open in a spreadsheet for ordering.

**What's in it (all worked out from the layout):**
- **Electronics:**
  - PCB, with its size.
  - PTS645 switches at the chosen height, counting the extra switches under long keys. The switch test shows "16: 8 keys × 1 switch, 4 long keys × 2 switches".
  - One 1N4148W diode per key.
  - The Pico and how it's mounted: soldered flat by its castellations on the back, or with 2 header strips on the front.
  - A USB cable.
- **Hardware:** the fixing screws, how many and how long (4 × M2 × 14 mm countersunk self-tapping for the examples).
- **Printed parts:** each STL with its colour role (case, key or legend), print orientation and filament amount. The mock PCB is listed as optional.
- **Keytops:** a count of each size, with sizes in mm, and the two-switch versions listed separately.
- **Summary:** keys and switches, case size, and the GPIO pins the matrix uses.

**Three ways to make it:**
- In the designer, with **File > Make parts list**.
- Automatically, every time `freecad/build_case.py` builds the case.
- From a command prompt: `python common/parts_list.py layouts/cyberdeck_staggered.json`

The filament amounts come from the FreeCAD build, which now records each printed part's volume in `prints.json`. They're for solid parts, so they're an upper limit. For the staggered keyboard that's up to 41 g for the tray, 17 g for the plate, 39 g for the keytops and 0.3 g for the legends. Your slicer will give the real figure for your infill. A list made before the case has been built just leaves the filament amounts out.

**On the switch:** the list names the C&K PTS645 series, SMD version, at the layout's height, rather than an exact part number. The full part number also encodes the press force, which you'll want to choose when ordering.

The README has a new "Parts list" section.

---

## 16. Rob

> the mock keyboard pcb is very good, but the walls don't hold the switches in position. Can you make a version with higher walls that taper in slightly to grip the switch and then make a tiny test plate that I can use to test the grip.

Here's the plan:

- **Taller fences:** 2.5 mm instead of 1 mm. That's still well below the 3.5 mm switch body and clear of the keytops, which are 5 mm above the board.
- **Grip:** the inner walls lean in, from 0.15 mm clearance at the base to slightly *smaller* than the switch at the top, so the walls flex and hold the body. I'll start with 0.1 mm of overlap per side.
- **Lead-in:** a small chamfer at the top of each wall so the switch pushes in easily.
- **Leg gaps:** these stay full height, because the legs leave the body at board level.
- **Test plate:** a separate `SwitchGripTest.stl`, a small strip with six fences gripping by different amounts (0 to 0.25 mm), each labelled with raised numbers. Find the one that holds best, then set that grip value for the mock PCB.

The fence settings move into the layout file so you can change them without editing code.

<details><summary>2 actions</summary>

- Read current mock PCB code
- Add gripping fences, grip test plate and settings

</details>

The shell choked on that long inline script. I'll put the edit script in a file and run it from there instead.

<details><summary>8 actions</summary>

- Wrote a working script
- Run edit script, compile, update layouts
- Build and measure gripping fences and test plate
- Render grip test plate top view and section
- Read a working file
- Rebuild full keyboards, check mock, find README text
- Edited README.md
- Add mock_pcb to README schema, check parts list

</details>

The mock PCB now has taller fences that lean in to grip the switches, and there's a small test plate for finding the best grip on your printer. I've rebuilt all three keyboards.

**New fences** (on every mock PCB):
- **Height:** 2.5 mm instead of 1 mm. That's below the 3.5 mm switch body and well clear of the keytops.
- **Lean:** the inside leans in, from 0.15 mm clear of the switch body at the board to 0.1 mm *smaller* than the body near the top. The walls flex and grip the switch.
- **Lead-in:** a 0.4 mm chamfer at the top guides the switch in.
- **Legs:** the gaps for the legs run the full height, since the legs leave the body at board level.

Measured on the model, the opening narrows from 6.27 mm at the board to 5.82 mm about 2 mm up, against a 6.0 mm switch. The leg gaps are clear, and the mock PCB doesn't touch the tray, plate or keytops on any of the three layouts.

**Grip test plate** (`SwitchGripTest.stl`, 72 × 20 mm, about 3 g):
- **Fences:** six fences gripping by 0, 0.05, 0.1, 0.15, 0.2 and 0.25 mm, each labelled with raised numbers.
- **Testing:** push a switch into each one and pick the one that holds it firmly but still lets it sit fully down on the plate.
- **Using the result:** set that number as **Mock PCB grip** on the designer's Case tab, then rebuild the case to get a mock PCB with that grip.

It's in each keyboard's output folder, for example `output/switch_test/SwitchGripTest.stl`. It's the same in every folder.

The fence settings are now in a `mock_pcb` section of the layout: height, wall thickness, bottom clearance, grip and lead-in. The designer shows the height and grip, and warns if the fences get too tall or too short to grip. The parts list includes the test plate as an optional print, and the README is updated.

---

## 17. Rob

> fence size 0 works the best. Can you make a new mock pcb with that fence size.

Grip 0 means the fence narrows to exactly the switch size (6.0 mm) near the top, with no overlap. Since that tested best on your printer, I'll make it the default and set it in all three layouts, then rebuild.

<details><summary>1 action</summary>

- Set grip 0, rebuild mock PCBs and measure

</details>

The new mock PCBs are built: the fence opening narrows from 6.28 mm at the board to 6.01 mm near the top, the same as the switch. Last, the README still says the default grip is 0.1 mm:

<details><summary>1 action</summary>

- Update README for grip 0 default

</details>

The new mock PCB with grip 0 is ready: `output/switch_test/MockPCB.stl`.

Grip 0 is now the default for all keyboards, and I've set it in all three layouts and rebuilt their mock PCBs. For the full keyboards they're in `output/cyberdeck_staggered/` and `output/cyberdeck40/`.

Measured on the rebuilt mock PCB, each fence opening narrows from 6.28 mm at the board to 6.01 mm about 2 mm up, the same as the 6.0 mm switch. It still grips in practice because printed openings come out slightly small, as your test showed. The leg gaps are clear, and the mock PCB doesn't touch the tray, plate or keytops.

The README now says grip 0 is the tested default. `SwitchGripTest.stl` is still there if you change printer or filament and want to re-check.

---

## 18. Rob

> It turns out that putting the key on two switches makes it twice as hard to press, as you end up having press down two sitches. From tests I think that keys up to 4u are fine.  Our keyboard is not constrained by depth, so could you remove the double switch keys (using only a single central swtich) add new a keyboad design based on cyberdeck_starggered a top row containing numbers.

Understood. Here's what I'll change:

1. **Single switches everywhere.** No layout will use two switches on a key. I'll change the switch test keyboard to one centrally switched key of each length. I'll keep the ability to put several switches under a key, in case it's ever useful, but the designer will now warn that it makes a key harder to press. It will also warn about keys longer than 4u, which your tests found is the limit for a single switch.
2. **New layout, based on `cyberdeck_staggered`,** with a number row on top, using the extra room front to back:

   ```
   Esc  1  2  3  4  5  6  7  8  9  0  -  =
   Tab:1.5 Q W E R T Y U I O P Bksp:1.5
   Caps:1.75 A S D F G H J K L ; Ent:1.25
   Shift:2.25 Z X C V B N M , . Shift:1.75
   Ctrl:1.5 Gui:1.25 Alt:1.25 Space:4 Fn < v ^ >
   ```

   The number row is 13u wide like the other rows, staggered half a key left of the Q row as on a full-size keyboard. Esc moves to the top-left, and the old Esc position becomes Caps Lock. On the Fn layer, the number row gives F1–F12 and Fn+Esc gives `` ` ``. The other symbols stay where they were on the Fn layer, except that Q–P no longer need to give digits.

<details><summary>1 action</summary>

- Read staggered and switch test layout generators

</details>

I'll write the changes as a script file, since the shell mangles long inline edits.

<details><summary>10 actions</summary>

- Wrote a working script
- Apply edits and validate number-row layout
- Find switch test hole placement
- Read common/keyboard_layout.py
- Read common/keyboard_layout.py
- Edited common/keyboard_layout.py
- Validate and save switch test and numbers layouts
- Build and verify PCB and case for new layouts
- Screenshot number-row layout in designer
- Read a working file

</details>

The new keyboard looks right in the designer, with no problems reported. Now the README:

<details><summary>1 action</summary>

- Read README layout and long keys sections

</details>

Rewriting both README sections to match the test results and the new layout:

<details><summary>3 actions</summary>

- Wrote a working script
- Apply README rewrite and review
- Check README escape, Fn layer and parts list

</details>

Every key now has a single central switch, and there's a new keyboard with a number row.

**New keyboard: [layouts/cyberdeck_numbers.json](layouts/cyberdeck_numbers.json)** (also **File > New from example (staggered with number row)** in the designer)

```
Esc  1  2  3  4  5  6  7  8  9  0  -  =
Tab  Q  W  E  R  T  Y  U  I  O  P  Bksp
Caps  A  S  D  F  G  H  J  K  L  ;  Ent
Shift  Z  X  C  V  B  N  M  ,  .  Shift
Ctrl Gui Alt    Space(4u)    Fn  <  v  ^  >
```

- **Size:** 57 keys, same width as `cyberdeck_staggered`, 12 mm deeper for the extra row. The case is 167 × 77 × 16.9 mm.
- **Number row:** it starts half a key to the left of the Q row, as on a full-size keyboard. Esc moves to the top-left, and Caps Lock takes its old place.
- **Fn layer:**
  - The number row gives F1–F12, and Fn+Esc gives `` ` ``.
  - Fn+O, P and L give `[`, `]` and `\`.
  - Fn+; gives `'`, Fn+. gives `/`, and Fn+Bksp is Delete.
  - The arrow keys give Home, End, Page Up and Page Down.
- **Wiring:** a 5 × 13 matrix using 18 of the Pico's pins. The Pico is on the back with its USB socket at the top edge.
- **Build checks:** the PCB routes completely with clean DRC. The case, keytops and mock PCB build with no overlaps, and every key seats only after rising 1.35 mm. The parts list is generated: 57 switches, 57 diodes and 4 screws.
- **Files:** in `output/cyberdeck_numbers/`: the PCB, the printed parts (including the mock PCB with grip 0) and the parts list.

**Double-switch keys removed:**
- **Switch test keyboard:** now one key each of 1u, 1.5u, 2u, 2.25u, 2.75u and 4u, all with one central switch. Without the second row it's 92 × 41 mm, with the Pico lying along the back and its USB socket at the right-hand end. I've rebuilt it in `output/switch_test/` and it checks out the same way.
- **Your other layouts:** none of them ever used two switches.
- **Designer warnings:** a key with more than one switch is flagged as harder to press, and a key longer than 4u as likely to rock.
- **The option itself:** I kept the ability to put several switches under a key, in case it's ever useful. The README now records the test results: two switches are twice as hard to press, and one switch works up to 4u.

---

## 19. Rob

> can you generate a KiCad schematic for each of the keyboards alongside the other Kicad files

Failed to refresh OAuth token: another Claude Code process is refreshing it or exited mid-refresh. This is usually transient; retry in a minute, and if it persists close other Claude Code processes or sign in again

---

## 20. Rob

> can you generate a KiCad schematic for each of the keyboards alongside the other Kicad files

KiCad's Python API only covers the PCB editor, so I'll write the schematic files directly in KiCad's file format. Here's the plan:

- **Content:** each key gets its switch and diode drawn like a cell in the matrix, and the Pico has the rows and columns connected to its GPIO pins. Net labels do the joining, rather than long wires.
- **Matching the PCB:** symbols get the same references (SW1, D1, U1), footprints and net names (`ROW0`, `COL3`, `K_K12`) as the PCB. I'll also link each PCB footprint to its schematic symbol, so KiCad treats the two files as one project. That means *Update PCB from Schematic* works and you can cross-probe between them.
- **Checking:** KiCad's electrical rules check (ERC) on each schematic, plus the PCB rules check that compares it against its schematic.

First I'll see which library symbols are available, including whether KiCad 8 ships a Pico symbol.

<details><summary>3 actions</summary>

- Find switch, diode and Pico symbols
- Inspect Pico, switch and diode symbol details
- Get pin positions and check CLI options

</details>

Both are plain base symbols, and `kicad-cli` can run ERC and the schematic-to-PCB comparison, so I can check the result automatically. Now the schematic writer:

<details><summary>4 actions</summary>

- Wrote kicad/schematic.py
- Check pcbnew API and find code to change
- Wrote a working script
- Apply build_pcb edits and check escapes

</details>

Now I'll build the small switch test keyboard first and run three checks: ERC on the schematic, the usual DRC, and DRC with the schematic-to-PCB comparison.

<details><summary>1 action</summary>

- Build switch test, run ERC and DRC with parity

</details>

The footprint library calls fail when KiCad runs headless: the library plugin isn't loaded. I'll look for a lower-level way to save a footprint.

<details><summary>2 actions</summary>

- Probe pcbnew IO plugin API
- Test saving footprint with KiCad SEXPR IO directly

</details>

Using KiCad's file writer directly works. Switching to it, then rebuilding:

<details><summary>10 actions</summary>

- Rebuild switch test and run ERC and parity DRC
- Find Pico pin connection code
- Read kicad/build_pcb.py
- Edited kicad/build_pcb.py
- Rebuild all four and run ERC and parity DRC
- Export schematic SVG and screenshot
- Read a working file
- Retry schematic screenshot
- Read a working file
- Keep diode fields horizontal, hide diode value

</details>

The same backslash mangling again, and nothing was written. I'll make these edits directly in the file instead.

<details><summary>7 actions</summary>

- Read kicad/schematic.py
- Edited kicad/schematic.py
- Edited kicad/schematic.py
- Edited kicad/schematic.py
- Rebuild, recheck, render zoomed schematic
- Retry zoomed screenshot
- Read a working file

</details>

That's clean: each cell is a switch with its column label, a labelled link to its diode, and the diode down to its row. I'll rebuild all four keyboards with the fix and re-run every check.

<details><summary>6 actions</summary>

- Rebuild remaining keyboards and run all checks
- Read README PCB section and workflow step
- Wrote a working script
- Update README and check build_pcb docstring
- Read kicad/build_pcb.py
- Edited kicad/build_pcb.py

</details>

Each keyboard now has a KiCad schematic alongside its PCB, and I've generated it for all four. Each `output/<name>/` folder is a complete KiCad project: open `<name>.kicad_pro`. `build_pcb.py` writes the schematic every time it builds the board, using the new [kicad/schematic.py](kicad/schematic.py).

**What the schematic shows:**
- **Key matrix:** one cell per key, placed at its row and column. The switch is labelled with the key's label (Esc, Q, Shift…), and its diode runs down to the row line.
- **Wiring:** the rows and columns are joined with global labels (`ROW0`, `COL3`), and each switch-to-diode link is labelled `K_<key id>`, so every net has the same name as on the PCB.
- **Pico:** its row and column pins are labelled, and every other pin has a no-connect flag.
- **Notes:** the key count, matrix size, parts, and a reminder that the sheet is generated from the layout.

**It works as one project with the PCB:**
- **Shared details:** references, values, footprints and net names all match the PCB, and each footprint is linked to its symbol. Cross-probing and *Update PCB from Schematic* both work.
- **Pico libraries:** KiCad has no Pico symbol, so each project gets small libraries of its own: `Cyberdeck.kicad_sym` for the symbol and `Cyberdeck.pretty` for the footprints, already set up in the project. This also removed the old "footprint not in library" DRC message.
- **Unused Pico pins:** the PCB now gives them the same placeholder "unconnected" nets that the schematic's no-connect flags create, so the two match pin for pin.
- **Mounting holes:** marked as board-only, since they aren't in the schematic.

**Checks, on all four keyboards:** KiCad's electrical rules check on the schematic and the PCB design rules check (DRC) both report nothing at all. The comparison of schematic against PCB found no mismatches, and all connections are routed.

Change the layout and rebuild rather than editing the schematic, since each build rewrites it. The README has a new "Schematic" section.

---

## 21. Rob

> What would I have to add to my KiCad installation for you to be able to autoroute the board?

**Nothing.** Every board is already autorouted when you run `build_pcb.py`. That's the router I wrote, [kicad/autoroute.py](kicad/autoroute.py), which runs inside KiCad's own Python, so it needs nothing extra installed. On all four keyboards it connects everything, with no DRC errors.

Its limitation is the style of the result. It only lays tracks horizontally and vertically on a 0.5 mm grid, with square corners. That's electrically fine, but not as neat as hand routing, and it can use more vias than necessary.

**If you'd like better-looking routing, the tool to add is Freerouting.** It's the usual open-source autorouter used with KiCad. It routes at 45°, optimises track lengths and vias, and does a final clean-up pass.

To let me run it from the build script, you'd need:

1. **Java.** Freerouting 2.x needs Java 21 or later. There's no Java on this machine at the moment (I checked when I first did the routing). Any recent OpenJDK will do, for example Eclipse Temurin 21 from adoptium.net.
2. **The Freerouting program** (`freerouting-<version>.jar`) from the releases page at github.com/freerouting/freerouting. I just need to know where you save it. The Windows installer there may include its own Java, which would cover step 1 as well, but I haven't confirmed that for the current release.

Optionally, the **Freerouting plugin** from KiCad's *Plugin and Content Manager* adds a button in the PCB editor, so you can re-route by hand. I don't need it, because I'd run Freerouting directly.

**How I'd use it:** export the board from KiCad in Specctra format, run Freerouting on it without its window, then import the routed result back into the board. I'd add a `routing.engine` setting to the layout with `builtin` or `freerouting`. If Freerouting isn't found or doesn't finish, the build would fall back to the built-in router so it always produces a routed board. I'd then compare the two results with DRC.

If you install Java and download the jar, let me know where they are and I'll add the option.

---

## 22. Rob

> Are the surface mount diodes T4 packaged?

Probably, but "T4" is a **marking code**, not a package. It's the code printed on the body of a 1N4148W, and several common packages carry it, so the marking alone doesn't confirm a fit.

**What the board is designed for:** the PCB uses the **1N4148W in a SOD-123 package** (KiCad footprint `Diode_SMD:D_SOD-123`, pad centres 3.3 mm apart). The usual SOD-123 1N4148W, as sold by LCSC, Diodes Inc and others, is marked **T4**. So if yours came as 1N4148W SOD-123, they're exactly the part the board expects.

**Where to be careful:** the smaller **1N4148WS in SOD-323** is often marked **T4** as well. It's noticeably smaller and wouldn't sit properly on the SOD-123 pads.

**How to tell which you have:**

| Package | Overall length (including the leads) | Body | Part number |
|---|---|---|---|
| SOD-123 (what the board uses) | about 3.7 mm | about 2.7 × 1.6 mm | 1N4148W |
| SOD-323 (smaller) | about 2.5 mm | about 1.7 × 1.25 mm | 1N4148WS |

So if a diode is about 3.7 mm long, it fits the board as it is. If it's about 2.5 mm, it's the smaller package. Either way, the band on the body marks the cathode, which goes to the row line. On the PCB that's pad 1, the end marked by the line on the silkscreen.

If yours turn out to be SOD-323, I can add a diode package setting to the layout. That would switch the footprint, the parts list, the schematic and the clearance checks to suit. A smaller diode actually leaves a little more room between the rows of switches.

---

## 23. Rob

> How would I go about submitting a board to a company like PCBWay for fabrication

In outline: you turn the KiCad board into a set of manufacturing files (Gerbers and drill files), zip them, upload the zip to PCBWay's quote page, check a few settings, and order. Your boards are ordinary 2-layer designs, so the default options cover nearly everything.

**1. Check the board.** Open `output/<name>/<name>.kicad_pro` in KiCad, open the PCB, and run **Inspect > Design Rules Checker**. The build already checks this, so it should come up clean.

**2. Make the Gerbers and drill files.** In the PCB editor:
- **File > Plot.** Choose format **Gerber** and pick an output folder, for example `gerbers/`. Tick these layers: **F.Cu, B.Cu, F.Silkscreen, B.Silkscreen, F.Mask, B.Mask, F.Paste, B.Paste, Edge.Cuts.** Leave the other settings at their defaults and click **Plot**.
- Then click **Generate Drill Files…** in the same window. Choose format Excellon, units mm, and the same folder. Click **Generate Drill File**. This writes separate files for plated and non-plated holes (the mounting holes are non-plated), which is what PCBWay expects.
- **Zip the folder.** The Gerbers.zip already in your repo is exactly this kind of package.

The simpler route is PCBWay's own **"PCBWay Fabrication Toolkit"** plugin from KiCad's *Plugin and Content Manager*. It adds a toolbar button that makes the correct zip in one click, plus the assembly files if you want them.

**3. Upload and quote.** On pcbway.com go to **PCB Instant Quote**, choose the quick order, and upload the zip. It reads the board size and layer count from the files. Check these settings:

| Setting | What to choose |
|---|---|
| Layers | 2 |
| Size | filled in from the files (e.g. 162 × 72 mm for `cyberdeck_numbers`) |
| Quantity | 5 is the usual minimum and costs barely more than 1 |
| Material / thickness | FR-4, **1.6 mm**. The case is designed around this thickness, so don't change it. |
| Min track / spacing | 6/6 mil. The board uses 0.25 mm tracks and 0.2 mm gaps, about 10/8 mil, so it's well inside standard limits. |
| Min hole size | 0.3 mm (the vias) |
| Surface finish | HASL lead-free is cheapest. ENIG gives flatter pads, which makes the small surface-mount parts easier to solder. |
| Via treatment | Tented |
| Copper | 1 oz |
| Solder mask / silkscreen | any colour you like |

Submit it. PCBWay's engineers review the files, usually within a few hours, and then you pay and it's made and shipped.

**4. Soldering the parts.** You have two choices:
- **Solder them yourself.** Add a **stencil** to the order. It's made from the paste layers and makes solder paste on the switch and diode pads quick and even.
- **Have PCBWay assemble them.** They'd also need a parts list with manufacturer part numbers and a component position file (the Fabrication Toolkit makes both). Either way you'd solder the Pico yourself afterwards, flat by its castellations.

I can add this to the build if you like. `kicad-cli` can export the Gerbers, drill files and component positions, so `build_pcb.py` could write a ready-to-upload `<name>_gerbers.zip` for each keyboard. I'd check the zip by re-importing it, so you'd just upload the file.

---

## 24. Rob

> Please add this to the build. I've added the PCBWay plugin to KiCad

Thanks. I'll look at what the PCBWay plugin produces, so the build's output matches what PCBWay expects. Then I'll have `kicad-cli` generate the same files automatically on every build.

<details><summary>5 actions</summary>

- Find installed PCBWay plugin
- Locate KiCad 3rd-party plugin directory
- Read partial output and KiCad config
- List installed KiCad packages and plugin folder
- Show installed packages file and user folders

</details>

KiCad 8's package list is empty, so the plugin may have gone into a different KiCad version or folder. Checking:

<details><summary>9 actions</summary>

- Check other KiCad versions for the plugin
- Look for the plugin under OneDrive
- Inspect OneDrive KiCad folders
- Check kicad-cli export options
- Wrote kicad/fabrication.py
- Wire fabrication into build and test on switch test
- Fix size, rebuild all, verify Gerber zips
- Fix outline check and rerun
- Repair check script and rerun

</details>

All four zips check out: the board outline in the Gerbers is exactly the design size, and every hole is accounted for. I'll document it in the README.

<details><summary>2 actions</summary>

- Wrote a working script
- Update README and show numbers ordering notes

</details>

Every board build now also writes a ready-to-upload set of fabrication files. I've generated them for all four keyboards.

**What you get:** `build_pcb.py` writes a `fabrication/` folder next to each board, for example `output/cyberdeck_numbers/fabrication/`:

| File | Use |
|---|---|
| `<name>_gerbers.zip` | **Upload this to PCBWay.** It contains the copper, solder mask, silkscreen and paste layers for both sides, the board outline, and the drill files. |
| `ORDERING.md` | The quote-form settings for that board: 2 layers, size (162 × 72 mm for the number-row keyboard), 1.6 mm thick, smallest track, gap and hole, finish and so on. |
| `<name>_bom.csv`, `<name>_positions.csv` | Only needed if PCBWay fits the switches and diodes. The Pico is marked "do not place", since you solder it by hand. |
| `gerbers/` | The same files unzipped, for looking at in KiCad's Gerber Viewer. |

**Checks:** I compared each zip against its board. The outline in the Gerbers is exactly the design size, and the drill files have exactly as many holes as the board has vias and mounting holes. All the expected layers and the Gerber job file (2 layers, 1.6 mm) are there.

**To order:** on PCBWay go to *PCB Instant Quote*, upload the zip, check the settings against `ORDERING.md`, and submit it for review.

**Things to check before ordering:**
- **Switch part number:** the BOM names the PTS645 series without a full part number, because you need to choose the press force.
- **Diode part number:** it suggests `1N4148W-7-F` (a SOD-123 part), from memory rather than a datasheet lookup. Check it before ordering assembly.

**The PCBWay plugin:** I couldn't find it in this KiCad 8 installation. Its package list is empty and there's no plugin folder, so it may need KiCad restarting to finish installing. The build doesn't use it, because `kicad-cli` makes the same kind of files, but it's handy if you ever change a board by hand.

The README has a new "Having the boards made" section.

<details><summary>5 actions</summary>

- Read finished plugin search output
- List plugins in the found KiCad folders
- Inspect PCBWay plugin export settings
- Read plugin gerber and drill settings
- Match plugin settings, add IPC netlist, rebuild and check

</details>

All four zips rebuilt and passed the same checks, now with the netlist included. Last, a README touch-up to mention the netlist and say the plugin uses the same settings:

<details><summary>1 action</summary>

- Note netlist and plugin match in README

</details>

I found the PCBWay plugin after all. KiCad keeps its add-ons in `OneDrive\Documents2\KiCad\8.0\3rdparty\plugins`, which I hadn't searched. I've changed the build so its zip matches the plugin's.

I read the plugin's code to see exactly what it exports. Its files were almost the same as the build's, with two differences, which I've now matched:
- **File names:** the Gerbers now use KiCad's own names (`…-F_Cu.gbr`) instead of the older Protel-style extensions (`.gtl`, `.gbl`…). PCBWay accepts either, but now they're identical to a hand export.
- **Electrical test file:** the zip now includes an IPC-D-356 netlist. PCBWay uses it to test the bare boards for shorts and breaks.

Everything else already agreed with the plugin: silkscreen trimmed off the pads, separate drill files for plated and non-plated holes, and the board outline.

I rebuilt all four keyboards and re-checked the zips. Each has all 15 files, the outline is exactly the design size, and the drill files have exactly the right number of holes. So `output/<name>/fabrication/<name>_gerbers.zip` is the same as what you'd get from the plugin's button, ready to upload. The plugin is still useful if you ever edit a board by hand in KiCad.

---

## 25. Rob

> how do I go about telling pcbway about the components to be fitted to the board if I want them to make it.

You order assembly on the same quote as the bare boards, and give PCBWay two extra files. The build already makes both, in the `fabrication` folder next to `ORDERING.md`:

- **`<name>_bom.csv`**: the bill of materials, saying *what* to fit. It's in PCBWay's own column layout: designators, quantity, manufacturer, part number, package, SMD or through-hole, and notes. There are three lines: the switches, the diodes, and the Pico marked **Do not place**.
- **`<name>_positions.csv`**: the position file, saying *where* each part goes. It gives the position, rotation and side for every switch and diode, in the same coordinates as the Gerbers, so they line up. The Pico is left out on purpose.

**Ordering, step by step**

1. **Board details:** on *PCB Instant Quote*, fill in the board as usual (2 layers, 1.6 mm…) and upload the Gerber zip.
2. **Turn on assembly:** tick **PCB Assembly** on the same page. It asks for:
   - **Assembly type:** **Turnkey** means PCBWay buys the parts. **Kitted** or **consigned** means you post them the parts. **Combo** is a mix.
   - **Sides:** **top side only**. Every part they'd fit is on the front. The Pico on the back is yours to solder.
   - **Unique parts:** **2** (switches and diodes).
   - **SMD parts per board:** 2 × number of keys. That's 114 for `cyberdeck_numbers` (57 switches + 57 diodes).
   - **Through-hole parts:** **0**.
3. **Upload the BOM and position files** when it asks for them, after you add assembly to the cart or in the assembly order details.
4. **Review:** PCBWay's engineers check the files, price the parts and quote you. They often email questions, and sometimes a photo of the first board to confirm part orientation before they make the rest. The one that matters here is the **diodes**: the band (cathode) goes to pad 1, marked by the line on the silkscreen. The BOM notes say so.
5. **Pay and receive.** The boards arrive with the switches and diodes fitted. You then solder the Pico flat on the back by its castellations.

**Before you upload the BOM, fill in the switch part number.**
- **Switch:** it currently says "PTS645 series, SMD" because the full part number encodes the **height** (5.0 mm in your layouts) and the **press force**. The force is your choice, and turnkey assembly needs an exact part number. Choose it on C&K's datasheet or a supplier like LCSC, Mouser or Digi-Key, and make sure it's the **SMD (gull-wing)** version at the right height.
- **Diode:** `1N4148W-7-F` is a SOD-123 part, but check the listing before ordering.

**Turnkey or consigned?** PTS645 SMD switches aren't the cheapest switch, and on turnkey orders PCBWay adds its sourcing cost. You already have PTS645s and T4 diodes, so **consigned** (posting them your parts) can be cheaper. Send a few spares, since machines waste some parts.

I could add the switch's exact part number as a setting in the layout. It would then appear in the BOM, the parts list and the schematic, so the files are complete for turnkey ordering without any hand editing. If you tell me which press force you want, I'll fill it in.

---

## 26. Rob

> I can't see where to add the BOM files

I can't see PCBWay's website from here, and their pages change from time to time, so I'll describe how assembly ordering usually works there rather than give exact clicks.

**The usual catch:** the ordinary *PCB Instant Quote* page is for bare boards only, and has nowhere to upload a BOM. Assembly has its own quote form:

1. From the top menu, go to **PCB Assembly** and then its quote page (called something like *Quote Now* or *Instant Quote*). Don't use the plain PCB quote.
2. That form asks for the assembly details (turnkey or kitted, top side, number of unique parts, SMD count…) together with the board details. It has its own upload boxes: one for the **Gerber** zip, one for the **BOM**, and one for the **centroid / pick-and-place** file. Upload `<name>_bom.csv` as the BOM and `<name>_positions.csv` as the centroid file.
3. On some versions of the site, the BOM and centroid upload happens **after** you click *Add to cart*: the cart entry shows an *Upload files* button, or asks for them while the engineers review the order. If you've already added a bare PCB to the cart, you may need to start again from the assembly quote form instead.

If the form only offers **one** upload box, PCBWay accepts a single zip containing the Gerbers, BOM and centroid file together. If you still can't find it, their live chat is quick, and you can email the BOM and positions files to your sales rep with your order number. Assembly orders are reviewed by a person anyway.

I can make that single zip part of the build, so `fabrication/` also contains `<name>_assembly.zip` (Gerbers, drill files, netlist, BOM and positions). Then whichever upload box you find, the same file works. Shall I add it?

---

## 27. Rob

> yes please

<details><summary>5 actions</summary>

- Locate code to extend in fabrication.py
- Read kicad/fabrication.py
- Edited kicad/fabrication.py
- Edited kicad/fabrication.py
- Rebuild all and verify assembly zips

</details>

Now the README table:

<details><summary>1 action</summary>

- Document assembly zip in README

</details>

Each keyboard's `fabrication` folder now also has an assembly zip: the one for your number-row keyboard is `output/cyberdeck_numbers/fabrication/cyberdeck_numbers_assembly.zip`.

It contains everything from the Gerber zip (Gerbers, drill files and netlist) plus the BOM and the positions file. If the assembly form gives you a single upload box, upload this. If it has separate boxes, use the Gerber zip, `_bom.csv` and `_positions.csv` as before.

I rebuilt all four keyboards and checked each assembly zip. It has 17 files, its Gerber files are byte-for-byte identical to the Gerber zip, and the BOM and positions match the board. For `cyberdeck_numbers` that's 114 parts placed (57 switches and 57 diodes), with the Pico left for you to fit.

`ORDERING.md` now explains which zip to use where. It also reminds you to use the **PCB Assembly** quote form rather than the plain PCB quote. The README is updated too.

Before ordering assembly, the switch's exact part number still needs filling in on the BOM's switch line, since it depends on the press force you choose.

---

## 28. Rob

> can we settle for medium switch press force

Yes. To put an exact part number in the BOM, I need C&K's ordering code for the medium-force, 5.0 mm, surface-mount PTS645. I'm not certain enough of it from memory, so I'll check the datasheet.

<details><summary>1 action</summary>

- Searched the web for "C&K PTS645 SMT part number 5.0mm 160gf PTS645SM50SMTR92 LFS"

</details>

That confirms `PTS645SM50SMTR92 LFS` is the 160 gf, 5.0 mm, gull-wing surface-mount version. To see whether 160 gf counts as the medium force, I'll check the datasheet's force options.

<details><summary>7 actions</summary>

- Fetched https://www.ckswitches.com/media/1471/pts645.pdf
- Fetched https://www.littelfuse.com/assetdocs/littelfuse-ck-tactile-pts645-series-datasheet?assetguid=d58fc8a8-f6e1-4527-ab68-27635e632e39
- Searched the web for "PTS645 operating force options 100gf 130gf 160gf 260gf SK SM SL SH code"
- Locate switch data and its uses
- Read kicad/schematic.py
- Wrote a working script
- Apply force edits and test part numbers

</details>

API Error: 529 Overloaded. This is a server-side issue, usually temporary — try again in a moment. If it persists, check https://status.claude.com.

---

## 29. Rob

> continue?

Yes. The force setting is in and all four layouts give `PTS645SM50SMTR92 LFS`. Now I'll rebuild every board (schematic, BOM and parts list included) and re-run ERC, DRC and the schematic comparison.

<details><summary>2 actions</summary>

- Rebuild all boards, check, show switch part number
- Confirm BOM part number in other boards

</details>

The other three are correct, and their assembly zips contain the updated BOM. Next, the README: it still says to choose the press force before ordering, and its layout example needs the new setting.

<details><summary>2 actions</summary>

- Find README force mentions
- Update README for switch force setting

</details>

Medium force is now the default for all four keyboards, so their switches are **`PTS645SM50SMTR92 LFS`**: 160 gf, 5.0 mm high, gull-wing surface mount on tape and reel. The press-force letters, from the datasheet summary and distributor listings, are L = 130 gf, **M = 160 gf**, H = 200 gf and K = 260 gf. A distributor listing confirms that exact part number is the 160 gf, 5.0 mm, gull-wing version.

**What changed:**
- **Layout setting:** each layout has `switch.force` (default `M`), also shown as *Switch force* on the designer's Case tab. The part number is built from the force and the switch height, so choosing 4.3 mm and K would give `PTS645SK43SMTR92 LFS`. The designer reports an error if the force letter isn't L, M, H or K.
- **Where it shows:**
  - The assembly BOM (no more "choose the press force" note).
  - The parts list.
  - `ORDERING.md`.
  - The schematic: a note, plus a hidden MPN field on every switch, and on the diodes too.
- **Checks:** all four boards rebuilt with ERC, DRC and the schematic comparison all clean, and the README is updated.

**Needs a re-run:** Windows wouldn't let me overwrite `output/cyberdeck_numbers/fabrication/cyberdeck_numbers_bom.csv`. That usually means it's open in another program, probably Excel. That keyboard's BOM, `ORDERING.md` and assembly zip still have the old wording. Close the file and run

```
"C:\Program Files\KiCad\8.0\bin\python.exe" kicad\build_pcb.py layouts\cyberdeck_numbers.json
```

or ask me to rebuild it. The other three keyboards' BOMs and assembly zips are already updated and correct.

Sources:
- [Newark: PTS645SM50SMTR 92 LFS, 160gf tactile switch](https://www.newark.com/c-k-components/pts645sm50smtr-92-lfs/tactile-switch-160gf-0-05a-12vdc/dp/35AH5239)
- [TrustedParts: PTS645SM50SMTR92 LFS](https://www.trustedparts.com/en/part/ck-switches/PTS645SM50SMTR92%20LFS)
- [Digi-Key: PTS645 series datasheet](https://www.digikey.co.uk/en/datasheets/ck/ckpts645)

---

## 30. Rob

> I've put a sample BOM in: "C:\Users\robmi\OneDrive\Sample_BOM_PCBWay.xlsx"

I'll read PCBWay's sample to see the exact columns and layout they expect, then make the build's BOM match it.

<details><summary>2 actions</summary>

- Check openpyxl and the sample file
- Read PCBWay sample BOM workbook contents

</details>

Windows won't let me open it, probably because it's open in Excel (or OneDrive is still syncing it). I'll try reading a copy.

<details><summary>4 actions</summary>

- Copy the sample BOM to a temp file
- Read sample BOM contents from the copy
- Read kicad/fabrication.py
- Edited kicad/fabrication.py

</details>

Next, the assembly zip and `ORDERING.md` should point to the Excel BOM. I'll find where they're written.

<details><summary>2 actions</summary>

- Find BOM references in fabrication.py
- Point notes and assembly zip at the xlsx BOM

</details>

That docstring reads awkwardly, so I'll tidy it:

<details><summary>3 actions</summary>

- Edited kicad/fabrication.py
- Rebuild all and list fabrication files
- Open generated BOM xlsx in Excel and read cells

</details>

Excel opens both cleanly, and the layout matches PCBWay's sample cell for cell. Last, the README:

<details><summary>1 action</summary>

- Update README BOM description

</details>

Each keyboard's `fabrication` folder now has a BOM laid out like PCBWay's sample. For your number-row keyboard it's `output/cyberdeck_numbers/fabrication/cyberdeck_numbers_bom.xlsx`.

**How it matches the sample:**
- **File type:** an Excel `.xlsx`, like their template. The CSV is still there as well.
- **Layout:** the title is in the merged D2 cell, the column headings are on row 6 with their exact wording (asterisks included), and the parts start on row 7.
- **The Pico:** its Type is **`DNS`** (do not stuff), the code their sample uses for parts not to fit, with a note that you'll solder it by hand.

The rows are:

| # | Designator | Qty | Manufacturer | Mfg Part # | Package | Type |
|---|---|---|---|---|---|---|
| 1 | SW1–SW57 | 57 | C&K | PTS645SM50SMTR92 LFS | 6x6mm SMD gull wing | SMD |
| 2 | D1–D57 | 57 | Diodes Inc (or equivalent) | 1N4148W-7-F | SOD-123 | SMD |
| 3 | U1 | 1 | Raspberry Pi | SC0915 | Castellated module | DNS |

**Checks:**
- **Excel:** I opened the generated files in Excel, hidden and read-only. They load cleanly, the cells are where the sample has them, the headings are bold and the quantities are numbers.
- **Assembly zip:** it now contains the `.xlsx` BOM instead of the CSV.
- **Notes and README:** `ORDERING.md` now says to upload `<name>_bom.xlsx` as the BOM, and the README is updated.

All four keyboards are rebuilt. The `cyberdeck_numbers` BOM that was locked earlier has been written this time, so its BOM, `ORDERING.md` and assembly zip are all up to date.

---

## 31. Rob

> Can you remove the Pico from the

Your message was cut off after "remove the Pico from the". I think you mean **the BOM**, so the BOM lists only the switches and diodes, with no `DNS` line for the Pico. It's already left out of the positions file.

Is that right? Or did you mean somewhere else: the parts list, the schematic, or the board itself?

---

## 32. Rob

> Sorry. Can you create two BOM files, one for the top of the board and the other for the bottom.

Here's how I'll split it:

- **Top BOM and positions:** the switches and diodes, which are on the front.
- **Bottom BOM and positions:** the Raspberry Pi Pico, which is on the back. It will be listed as a part to fit, Type SMD, mounted by its castellations, rather than `DNS`, and it goes into the bottom positions file. PCBWay can then fit it too. If you'd rather solder the Picos yourself, just upload only the top files.
- **Pico on the front:** if a layout puts the Pico on the front, it goes in the top BOM with header pins, and the bottom files are left out because there's nothing on that side.

<details><summary>2 actions</summary>

- Read BOM, positions and notes code
- Wrote a working script

</details>

Two things to tidy before running it: the positions filter is clumsy, and I've duplicated a function that `schematic.py` already has. I'll fix both in the script, then apply it.

<details><summary>1 action</summary>

- Tidy edit script, apply it, add imports

</details>

It compiles, and the generated filter line is correct (those warnings were only about my edit script). Rebuilding all four keyboards and checking the per-side files:

<details><summary>2 actions</summary>

- Rebuild and verify per-side BOMs and positions
- Test front-mounted Pico and show ordering notes

</details>

Front-mounted Pico works as intended: one top BOM, Pico included as through-hole, no bottom files. Now the Excel check on the new spreadsheets:

<details><summary>1 action</summary>

- Open top and bottom BOM xlsx in Excel

</details>

Last, the README's file table still describes a single BOM:

<details><summary>1 action</summary>

- Update README for per-side BOMs

</details>

The build now writes separate BOM and position files for the top and bottom of the board. All four keyboards are rebuilt.

**Files in each `fabrication` folder** (`cyberdeck_numbers` shown):

| Side | BOM | Positions | Parts |
|---|---|---|---|
| Top | `cyberdeck_numbers_bom_top.xlsx` | `cyberdeck_numbers_positions_top.csv` | 57 × `PTS645SM50SMTR92 LFS` switches, 57 × `1N4148W-7-F` diodes |
| Bottom | `cyberdeck_numbers_bom_bottom.xlsx` | `cyberdeck_numbers_positions_bottom.csv` | 1 × Raspberry Pi Pico (`SC0915`) |

- **BOM layout:** both BOMs follow PCBWay's sample layout, with a `.csv` copy of each. The title says which side it's for.
- **Assembly zip:** it now contains all four files.
- **Old files:** the single-BOM files from before have been removed.

**The Pico's entry has changed.** It used to be marked `DNS` (don't fit). Now it's a part to fit on the bottom: type SMD, soldered flat by its castellations, with a note about which way round it goes. It's also in the bottom positions file, so PCBWay can fit it. If you'd rather solder the Picos yourself, upload only the top files and order a top-side assembly. Fitting both sides costs more, and they may ask you to send the Picos. `ORDERING.md` explains this.

If a layout puts the Pico on the front, it appears in the top BOM as a through-hole part on header pins, and no bottom files are written. I tested that with a throwaway layout.

**Checks:**
- **Matching:** on all four keyboards, each BOM lists exactly the parts in its positions file, and every top part is marked "top" (every bottom part "bottom") in the positions files.
- **Excel:** the new spreadsheets open cleanly, with the right titles and rows.

The README is updated.

---

## 33. Rob

> I'd like to add an additional output element for each keyboard, and that is a cutout shape that can be used to cut a hole in a case into which the keyboard is being placed. This is already generated when the case top is created, can we write it out as an STL alongisde the other keyboard elements.

I'll take this to mean the case's outside outline, the rounded rectangle that the plate is made from. That's the shape of the hole the whole keyboard drops into. The plan:

- **The file:** `Cutout.stl`, that outline grown by a small clearance so the keyboard is an easy fit, as a solid the full height of the keyboard case.
- **Position:** it uses the same coordinates as `Tray.stl` and `Plate.stl`, so it lines up if you import them together. Subtract it from your cyberdeck case to make the hole.
- **Clearance:** a new setting, `case.cutout_clearance`, defaulting to 0.3 mm a side.

<details><summary>4 actions</summary>

- Locate plate outline, export and settings code
- Wrote a working script
- Apply edits and build all four cases
- Verify cutout size and clearance against case

</details>

All four check out: each cutout is 0.6 mm bigger than its case in both directions (0.3 mm a side), the same height, and contains the whole case. Now the README:

<details><summary>2 actions</summary>

- Find README spots to update
- Document Cutout.stl in README

</details>

Each keyboard's output folder now has a **`Cutout.stl`** alongside the other parts, for example `output/cyberdeck_numbers/Cutout.stl`.

I've taken "the cutout" to mean the outside outline of the keyboard case: the rounded rectangle the plate is made from, which is the hole the whole keyboard drops into. If you meant the pattern of key holes instead, say so and I'll export that too.

**What it is:**
- **Shape:** the case outline, 0.3 mm bigger all round, as a solid the full height of the keyboard case (16.9 mm).
- **Position:** the same coordinates as `Tray.stl` and `Plate.stl`. Import them together to line it up, then subtract it from your cyberdeck case. It's a cutting shape, not something to print.
- **Clearance:** set by a new `case.cutout_clearance` setting (default 0.3 mm), shown as *Cutout clearance* on the designer's Case tab.

**Checks, on all four keyboards:**
- **Size:** each cutout is 0.6 mm bigger than its case in both directions (167.6 × 77.6 mm for `cyberdeck_numbers`) and the same height.
- **Fit:** the tray and plate sit entirely inside it, with exactly 0.3 mm to spare at the sides.
- **Mesh:** the STL is a clean closed solid.

**USB cable:** the keyboard's USB socket comes out through the side of the tray, so your cyberdeck case will need a way in for the cable. The cutout doesn't include one.

The README is updated, and the cutout is also a hidden object in the FreeCAD model.

---

## 34. Rob

> The cutout should mirror the holes for the keys. The idea is that I want to use it to cut a hole in the case which I can then put the keyboard PCB behind.

Understood, I misread it. The cutout should be the **key holes**: the same shapes that cut the holes in the keyboard's top plate, sloped lower edges included. You subtract it from your case's panel, and that panel then does the plate's job: the keytops sit in its holes, held in by their lips, with the PCB mounted behind.

I'll make `Cutout.stl` the set of key-hole cutters:
- **Shape:** each cutter is the exact plate-hole shape, so the panel's holes come out the same as the plate's. Each one runs 1 mm past both faces of the plate so it cuts cleanly through.
- **Position:** the same coordinates as `Plate.stl`, so it lines up with the plate.
- **Clearance setting:** the outline cutout's `cutout_clearance` setting isn't needed any more, so I'll remove it.

I'll also work out the distance from the panel's underside to the PCB, since that's what you'll need to mount the PCB behind it.

<details><summary>4 actions</summary>

- Read plate hole and cutout code
- Wrote a working script
- Apply key-hole cutout edits and update layouts
- Rebuild and test cutout against the plate

</details>

The cutout now reproduces the plate's key holes exactly. On all four keyboards, a plain panel with `Cutout.stl` subtracted came out **identical to the real plate**, down to the sloped edges of every hole.

**What `Cutout.stl` is now:** one cutter per key (57 for `cyberdeck_numbers`), each the exact shape of that key's plate hole. Each cutter reaches 1 mm above the plate's top face and 0.3 mm below its underside, so it cuts cleanly through a panel of the same thickness.

**Checks, on all four keyboards:**
- **Exact match:** the cut panel differs from the plate by 0.0000 mm³.
- **Fit:** the keytops fit the cut panel's holes without touching it.
- **Retention:** lifted, every keytop seats against the cut panel's sloped edges at 1.35 mm, exactly as with the plate, so the panel holds the keys in.
- **File:** the STL is a clean solid.

**Using it in your case:**
- **Panel thickness:** make the panel **1.5 mm thick**, the same as the plate. If your case wall is thicker, set `case.plate_thickness` (Case tab, *Plate thickness*) to match and rebuild. The holes, slopes and keytop heights then all adjust, and the keytops still stand 2 mm proud.
- **Lining it up:** place the cutters so the plate's underside, 1 mm above the cutters' top, is level with the panel's top face. Then subtract.
- **PCB spacing:** mount the PCB so the panel's **underside is 7.3 mm above the PCB's top surface** (8.9 mm above its underside). That's the spacing the switches, keytops and free play are designed around. The standoffs, and where the PCB's 4 mounting holes go, are up to your case design.
- **Printing:** print the panel either way up. The hole slopes are 45°, so they need no support.

**Removed:** `case.cutout_clearance`, which belonged to the outline version, is gone from the layouts and the designer.

---

## 35. Rob

> Along with the mock device, can you also make two sets of mounting pillars for the keyboard. One to be used to attach the keyboard on top of a plate and the other to attach the keyboard underneath the plate. The on top pillars should be 4mm high. the underneath ones should be the length to keep the keyboard the correct distance from the plate to provide room for the keys and keycaps.

Here's the plan. Both sets are plain tubes, one per mounting hole (4 for each keyboard), with a 1.8 mm pilot hole right through for M2 self-tapping screws:
- **On top** (`PillarsOnTop.stl`): 4 mm high. They go between your plate and the underside of the keyboard PCB.
- **Underneath** (`PillarsUnderneath.stl`): **7.3 mm** high. They go between the underside of your panel and the top of the PCB. That's the same spacing the keyboard's own plate uses: room for the switches, keytops and their free play, and it suits the panel made with `Cutout.stl`.

One problem with 4 mm: with the Pico soldered flat on the back of the PCB, the Pico itself plus its USB socket stand about 4.2 mm proud of the PCB. So on 4 mm pillars the Pico would press on your plate. I'll make the height a setting, defaulting to 4 mm as you asked, and the designer will warn about it. A 5 mm height would clear it, or a cutout in your plate under the Pico.

<details><summary>7 actions</summary>

- Locate insertion points for pillars
- Wrote a working script
- Apply pillar edits and build all cases
- Check pillars in place and STL validity
- Read README cutout paragraph
- Wrote a working script
- Fix wording, apply README, confirm cutter heights

</details>

Each keyboard's output folder now has two sets of mounting pillars alongside the mock PCB. I've built them for all four keyboards, and the parts list includes both sets as optional prints.

| File | Pillars | Height | Use |
|---|---|---|---|
| `PillarsOnTop.stl` | one per mounting hole (4) | **4.0 mm** | between your plate and the underside of the PCB or mock PCB |
| `PillarsUnderneath.stl` | one per mounting hole (4) | **7.3 mm** | between the underside of your panel (cut with `Cutout.stl`) and the top of the PCB |

- **Shape:** both sets are 5 mm tubes, the same as the keyboard's own standoffs, with a 1.8 mm pilot hole right through for M2 self-tapping screws from either end. They're laid out in a row, standing up, ready to print.
- **Underneath length:** 7.3 mm holds the PCB exactly where it sits under the keyboard's own plate, so the switches, keytops and their free play all fit. It's worked out from the layout, so it follows any changes to the switch height or gaps. Placed at the mounting holes, these pillars clear the keytops (0.75 mm at the closest), the switches and the Pico, and occupy exactly the space of the plate's own built-in pillars.

**The Pico and the 4 mm pillars:** the Pico soldered on the back stands about 4.2 mm proud of the PCB, so on 4 mm pillars it would press on your plate. The designer and the build both warn about this. Either raise *On top pillar height* (Case tab, `pillars.on_top_height`) to 4.5 mm or more, or cut a hole in your plate under the Pico.

**A correction to my last reply about `Cutout.stl`:** I gave the alignment wrongly. Line the cutters up so their **top is 1 mm above your panel's top face**. Their bottom is then 0.3 mm below the panel's underside. I've checked this against the model.

**README:** the "fitting the keyboard into another case" section still described the old outline cutout. It now covers the key-hole cutout, both sets of pillars and the Pico clearance, and the leftover `cutout_clearance` setting is gone.

---

## 36. Rob

> The pilars are not positioned correctly. They need to be placed at the same position as the mounting holes on the keyboard pcb

Understood. I laid them out in a row as if for printing. I'll instead put each pillar exactly over its mounting hole, in the same coordinates as `MockPCB.stl`, `Plate.stl` and `Cutout.stl`, so everything lines up when imported together:
- **Underneath pillars:** standing on top of the PCB, up to where the panel's underside goes.
- **On-top pillars:** below the PCB, from the plate up to the PCB's underside.

They'll still print as they are: upright tubes flat on the bed.

<details><summary>5 actions</summary>

- Read pillars code
- Edited freecad/build_case.py
- Place pillars at holes and rebuild all
- Check pillar STL positions against mock PCB holes
- Show check output and errors

</details>

No output at all, so the script must be failing silently. Running it again without filtering:

<details><summary>1 action</summary>

- Run check with full output

</details>

---

## 37. Rob

> [Request interrupted by user for tool use]

---

## 38. Rob

> Do the keyboard cuts have the keybord legends in them? If so, can we create simple key shapes for the keyboard cutter.

No, the cutters have no legends in them. Each one in `Cutout.stl` is built only from its key's outline shape: the straight-sided top part, and the sloped lower part that the keytop's shoulder seats against. The legend lettering is cut only into the keytops themselves (`Keycaps.stl`), with the matching letters in `KeycapLegends.stl`. The cutters never go through that step, so they're already the simple key shapes you're after.

If you're seeing lettering, you may have `Keycaps.stl` open rather than `Cutout.stl`. They're in the same folder and both are rows of key shapes. If it really is in `Cutout.stl`, tell me which keyboard's folder it's in and I'll look.

The pillar change from your last message is in place and rebuilt for all four keyboards. Each pillar is now centred over a mounting hole, in the same coordinates as `MockPCB.stl`, `Plate.stl` and `Cutout.stl`:
- **Underneath pillars:** stand on the PCB and reach up to where the panel's underside goes.
- **On-top pillars:** sit under the PCB.

You stopped my check of the STL files before it ran, so I haven't yet confirmed they line up with the mock PCB's holes. Shall I run that check now?

---

## 39. Rob

> Can you make a numeric keyboard I can use for testing prints. I want four rows of three keys, not staggered. Digits 1 to 9 in the top three rows, the bottom row should be DEL, 0 and RETURN.  Add it as a new layout and then create all the files.

I'll add it as a new layout, `numpad`. The keys are 1u on the same 12 mm pitch as your main keyboards, so test prints match the real thing:

```
 1    2    3
 4    5    6
 7    8    9
DEL   0   RET
```

- **Labels:** `RETURN` would be too small to read on a 1u key, so I'll label it **RET**. It sends Enter (the Return key), and DEL sends Delete.
- **Pico:** on the back, with its USB at the top edge, as on the other keyboards.
- **Mounting holes:** a 3-key-wide board has no room for them in the usual margins, so the side margins are a bit wider and the four holes go there, beside the rows.

<details><summary>7 actions</summary>

- Find where to add the numpad layout
- Wrote a working script
- Add numpad layout and validate it
- Fix digit keycodes and check other layouts
- Build numpad PCB, fabrication files and case
- Run fit, mock PCB and legend checks on numpad
- Check numpad legends and parts list

</details>

All 12 keytops have their legends, fitting their pockets exactly. Last, the README's list of example layouts:

<details><summary>1 action</summary>

- Add numpad to README example layouts

</details>

The numeric keypad is ready, with all its files in `output/numpad/`. The layout is [layouts/numpad.json](layouts/numpad.json), also available as **File > New numeric keypad** in the designer.

```
 1    2    3
 4    5    6
 7    8    9
DEL   0   RET
```

- **Keys:** 1u on the same 12 mm pitch as your main keyboards, so test prints behave like the real thing. RET sends Enter and DEL sends Delete. I used "RET" because "RETURN" would be unreadably small on a 1u key.
- **Size:** board 48 × 57 mm, case 53 × 62 × 16.9 mm. The Pico is on the back with its USB at the top edge, and a 4 × 3 matrix uses 7 pins.
- **Mounting holes:** the four holes sit in slightly wider side margins, beside the rows.

**Files:**
- **Printing:** `Tray.stl`, `Plate.stl`, `Keycaps.stl`, `KeycapLegends.stl`, `MockPCB.stl`, `SwitchGripTest.stl`, `PillarsOnTop.stl`, `PillarsUnderneath.stl`.
- **Fitting into another case:** `Cutout.stl`.
- **KiCad:** project (`numpad.kicad_pcb`, `numpad.kicad_sch`, project libraries), plus `fabrication/` with the Gerber zip, top and bottom BOMs, position files, assembly zip and `ORDERING.md`.
- **Other:** `parts_list.md` / `.csv` (12 switches, 12 diodes, 4 screws) and the FreeCAD model.

**Checks:**
- **PCB:** fully routed, with no ERC errors, DRC violations or schematic mismatches. The Gerber zip has the right outline and every hole.
- **Case:** nothing overlaps, every key seats only after rising 1.35 mm, and the keytops print upside down without support.
- **Legends:** all 12 keytops have them, fitting their pockets exactly.
- **Mock PCB:** clear of the tray, plate and keytops.

**A bug fixed along the way:** adding keys by label gave the digit keys the keycode `1` instead of `ONE`, so the firmware wouldn't have typed them. It's fixed, and I checked that none of your other layouts were affected.

The only warning is the one every layout now shows: 4 mm on-top pillars leave no room for the Pico underneath. That only matters if you mount the keypad on top of a plate. The README lists the new layout.

---

## 40. Rob

> can I have more detail on the installation for the micropython device. The description uses mpremote but I'd rather copy files onto the device by hand.

MicroPython has no USB drive, unlike CircuitPython, so "by hand" means copying the files through a tool's file browser. Thonny does this, and it's already installed on this PC. I'll check exactly which library files the keyboard driver needs, using your micropython-lib clone.

<details><summary>4 actions</summary>

- List files and dependencies of USB keyboard packages
- Read current MicroPython install text
- Wrote a working script
- Apply README and docstring updates, check details

</details>

The `machine.USBDevice` error hint matches what the driver actually uses. One thing to check: my grep didn't find the Windows paths, so I'll make sure they came out with single backslashes.

<details><summary>1 action</summary>

- Check paths in new README text

</details>

The README now has a new section, **"Installing the MicroPython firmware"**, describing how to install everything by hand with Thonny (already on this PC). The mpremote commands are kept at the end as an alternative.

**The five steps:**
1. **Put MicroPython 1.23 or later on the Pico.** Download the `.uf2` for your board from micropython.org (`RPI_PICO` or `RPI_PICO_W`). Hold BOOTSEL while plugging in, then copy the `.uf2` onto the `RPI-RP2` drive.
2. **Connect Thonny.** Choose *Tools > Options > Interpreter > MicroPython (Raspberry Pi Pico)*, then turn on *View > Files*.
3. **Copy the USB keyboard driver.** It's four files from micropython-lib, all going in one folder on the Pico:

   | On the Pico | From micropython-lib |
   |---|---|
   | `/lib/usb/device/__init__.py` | `micropython/usb/usb-device/usb/device/` |
   | `/lib/usb/device/core.py` | `micropython/usb/usb-device/usb/device/` |
   | `/lib/usb/device/hid.py` | `micropython/usb/usb-device-hid/usb/device/` |
   | `/lib/usb/device/keyboard.py` | `micropython/usb/usb-device-keyboard/usb/device/` |

   Make the `lib` → `usb` → `device` folders on the Pico (right-click, *New directory...*), then upload the four files into the last one. These are exactly the files `mip install usb-device-keyboard` would install. I checked the package definitions in your micropython-lib clone.
4. **Copy the firmware and layout.** Upload `firmware\micropython\main.py` to `/`, and upload your layout (e.g. `numpad.json`). Then rename the layout to `layout.json` on the Pico, because that's the name the firmware looks for.
5. **Start it.** Unplug and replug the Pico. It appears as a keyboard.

The README also covers:
- **Changing files later:** press Thonny's *Stop* to halt the keyboard program, copy the files, then replug the Pico.
- **If it doesn't type:** run `main.py` from Thonny to see the error. The README lists what the common ones mean: driver files missing or in the wrong folder, `layout.json` missing or misnamed, an unknown keycode, or a MicroPython version older than 1.23.

The installation notes at the top of `firmware/micropython/main.py` now list the same files.

I haven't followed these steps on a real Pico, and the Thonny menu names are from memory, so treat the exact wording as a guide. Your micropython-lib clone is from July 2024, so take the driver files from the current GitHub copy if you can. It's more likely to match a recent MicroPython release.

If you'd rather not fetch files from micropython-lib at all, I can put a copy of the four driver files in the repository at `firmware/micropython/lib/usb/device/`. They're MIT-licensed, so that's allowed, and you'd just copy the whole `lib` folder across.

---

## 41. Rob

> The keyboard works well. Thank you. One question: what is supposed to happen when the FN key is pressed. At the moment it just seems to lock the keyboard.

Holding Fn is meant to work like Shift for the extra layer. While you hold it, each key sends its *Fn* code instead of its normal one, if it has one. Fn sends nothing to the computer by itself, and the keyboard should return to normal the moment you let go. It certainly shouldn't lock up, so let me look at the firmware. The MicroPython file has also changed since I last saw it.

<details><summary>4 actions</summary>

- Read firmware/micropython/main.py
- Check the earlier simulation harness exists
- Wrote a working script
- Simulate Fn key behaviour with cyberdeck_numbers layout

</details>

The firmware does the right thing with Fn on your layout. The simulation used your actual `main.py`, your `cyberdeck_numbers.json` (Fn is at row 4, column 8) and the real micropython-lib keyboard driver:

| What I pressed | What it sent to the computer |
|---|---|
| Tap Fn on its own, then A | nothing for Fn, then **A** |
| Hold Fn, tap 1 | **F1** |
| Hold Fn, tap A (A has no Fn code) | **A** |
| Hold Fn, tap 1, let go of Fn, then tap A | **F1**, then **A** |

**What Fn is meant to do:** it's a hold key, like Shift. On its own it sends nothing. While you hold it:
- **Number row:** gives F1–F12, and Esc gives `` ` ``.
- **Letter keys:** O, P and L give `[`, `]` and `\`; `;` gives `'`; `.` gives `/`.
- **Other keys:** Bksp is Delete, and the arrows give Home, End, Page Up and Page Down.
- **Everything else:** types as normal.

Letting go of Fn returns everything to normal straight away.

**So why the lock-up?** The software handles Fn correctly, so it's more likely something physical, or a mismatch with what's on the Pico:
- **Fn switch or wiring.** If Fn's switch is shorting, or its diode is missing or backwards (easy to do on a hand-wired mock PCB), several keys can appear pressed at once. Past 6 keys, a USB keyboard sends an "too many keys" error report, which makes the computer ignore all typing until the keys clear. That would look exactly like the keyboard locking.
- **The Pico's layout file isn't the one I tested.** For example, a different layout, or one where another key shares Fn's matrix position.
- **The F-keys.** If you hold Fn while pressing number keys, the F-keys might trigger something on your computer that looks like the keyboard stopping.

A few questions:
- Is this the PCBWay-made board, or the mock PCB with hand wiring?
- Does it recover by itself when you let go of Fn, or only after replugging?
- Does it happen when you tap Fn on its own, or only with other keys?

I can also add a debug switch to `main.py`: set `DEBUG = True` and it prints every key press and release, plus what it sends, to Thonny's Shell. Pressing Fn would then show straight away whether its release is seen and whether extra keys suddenly appear.

---

## 42. Rob

> I'm using the built keyboard from pcbway. I never hand wired anything. A debug switch that doesn't engage the usb keyboard, but just prints key legends, would be very useful.

That rules out wiring, so a debug mode is the right next step. Here's how it will work:

- **Turning it on:** set `DEBUG = True` near the top of `main.py`. The Pico then doesn't become a USB keyboard at all. It just scans the keys and prints to Thonny's Shell.
- **What it prints:** each key's legend, row and column as it goes down and up. It also prints which keys are held after every change, and what a keyboard would send, by name. So if pressing Fn makes extra keys appear, or its release never arrives, you'll see it straight away.
- **Empty positions:** a matrix position with no key on it is reported as such, which would reveal a short.

<details><summary>6 actions</summary>

- Read firmware/micropython/main.py
- Edited firmware/micropython/main.py
- Edited firmware/micropython/main.py
- Edited firmware/micropython/main.py
- Test normal and debug modes in simulation
- Document debug mode in README

</details>

[firmware/micropython/main.py](firmware/micropython/main.py) now has a debug switch.

**To use it:** in Thonny, open `main.py` from the Pico and change `DEBUG = False` (near the top) to `DEBUG = True`. Save it, then run it with the green Run button. The Pico doesn't become a USB keyboard at all, so nothing gets typed. It just scans the keys and prints to the Shell. For example, this is the simulated output for Shift, Fn and 1 held together:

```
down  Fn (row 4, col 8)
      keys down: Shift (row 3, col 1), Fn (row 4, col 8)
      would send: LEFT_SHIFT (Fn held)
down  1 (row 0, col 1)
      keys down: 1 (row 0, col 1), Shift (row 3, col 1), Fn (row 4, col 8)
      would send: LEFT_SHIFT, F1 (Fn held)
up    Fn (row 4, col 8)
```

Each press and release shows the key's legend with its row and column. After every change it lists every key currently down, and what a keyboard would send, by name, with "(Fn held)" when Fn is active. A press at a matrix position with no key on it shows as "(no key here)". Press Stop to end it, and set `DEBUG` back to `False` to use the keyboard again. In debug mode the USB keyboard driver isn't even loaded.

I tested it in the same simulation as before. Debug mode gives output like the example above, and normal mode sends exactly what it did before.

**For the Fn problem, look for:**
- **Fn's `up` line never appearing** after you let go: a switch or soldering fault on that key.
- **Extra keys appearing** in "keys down" when you press Fn: more than 6 at once would make the computer ignore the keyboard.
- **Nothing odd at all:** then the lock-up is most likely the computer reacting to an F-key, for example if you held Fn while pressing a number.

I kept your change to read `/cyberdeck_numbers.json`. The README's troubleshooting section now describes the debug switch.

---

## 43. Rob

> Can you save this entire conversation as a markdown document and add it to this repository please

The session's full transcript is stored by Claude Code on this PC, so I'll convert that to Markdown rather than write it out from memory. First, finding it:

<details><summary>3 actions</summary>

- Locate and inspect the session transcript
- Wrote a working script
- Convert transcript and check for private notes

</details>

