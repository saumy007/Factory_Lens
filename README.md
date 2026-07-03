# Factory VSM Overlay — Isaac Sim Extension

An NVIDIA Omniverse Isaac Sim extension that renders **floating, screen-style information cards above 3D objects** in a factory simulation. Each card displays Value Stream Mapping (VSM) metrics — Processing Time, Value Time, and Process Completion — and is fully editable from an in-app control panel: rename stations, edit metric values, and change header/text/background colors without touching code.

Built for and tested on **Isaac Sim 5.0.0** (Kit 107.3.1).

---

## Table of Contents

- [What It Does](#what-it-does)
- [Why It Exists](#why-it-exists)
- [Features](#features)
- [How It Works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)

---

## What It Does

This extension draws a **heads-up information card hovering above each machine** (or any prim) in your Isaac Sim scene. Each card behaves like a small monitor floating over the equipment, showing the metrics that matter for a factory floor:

- **Processing Time** — total time a unit spends at the station
- **Value Time** — the portion of that time that adds value
- **Process Completion** — completion percentage for the station

The cards are **camera-aware**: the text always faces the viewer and stays anchored above its target object as you orbit, pan, and zoom the viewport.

A companion **control panel window** lets you edit every card live — names, metric values, and colors — and refresh the overlay with a single click.

---

## Why It Exists

Factory-floor simulations in Isaac Sim are excellent for visualizing equipment, robots, and human operators, but the simulator has **no built-in way to overlay process data onto the 3D scene**. Lean-manufacturing tools like Value Stream Mapping normally live in spreadsheets and static diagrams, disconnected from the actual layout.

This extension closes that gap. It puts the **VSM data directly on the equipment in 3D space**, so a viewer can look at the factory and immediately see which station is the bottleneck, how long each process takes, and how much of that time is value-adding. It turns a visual simulation into a **decision-support tool** for process engineers, plant managers, and anyone analyzing flow and throughput.

It is designed to be **generic** — the overlay anchors to any prim type (Mesh, Xform, Cone, conveyor, imported CAD machine), so it works on any scene, not just one specific factory.

---

## Features

- **Floating info cards** anchored above any 3D object via world-space bounding-box placement
- **Works on any prim type** — Mesh, Xform, and nested geometry are all supported
- **Camera-tracked** — cards stay glued above their object and face the camera as you navigate
- **Screen-style background** — a semi-transparent dark card with a border, evoking a small monitor
- **Fully editable control panel** — rename stations, edit metrics, and pick colors at runtime
- **Per-card color control** — independent header, text, and background colors
- **Auto-sizing cards** — card height adapts to the number of metric lines
- **Reusable** — point it at any set of prim paths to label any scene

---

## How It Works

The extension combines three Omniverse subsystems:

1. **Bounding-box placement.** For each target prim, it computes the world-space bounding box (`UsdGeom.BBoxCache`) and places the card just above the object's top center. Because this uses the rendered bounds rather than the prim's origin, cards sit correctly above objects regardless of how their pivot was authored or how the model was scaled.

2. **Scene overlay rendering.** Cards are drawn with `omni.ui.scene` — text labels (`sc.Label`) and rectangles (`sc.Rectangle`) placed on transforms in 3D space. Labels are screen-facing by default, so they remain readable from any angle.

3. **Per-frame camera synchronization.** An update-event subscription reads the active viewport's projection and view matrices every frame and feeds them into the scene view, keeping the 3D-anchored cards correctly projected onto the screen as the camera moves.

The control panel is a standard `omni.ui.Window` whose fields write back into the extension's data model; clicking **Apply / Refresh Overlay** re-reads the fields and redraws the cards.

---

## Requirements

- **NVIDIA Omniverse Isaac Sim 5.0.0** (Kit 107.3.1) — may work on nearby versions with minor API adjustments
- A GPU and driver setup capable of running Isaac Sim's RTX renderer
- A scene containing the prims you want to label

---

## Installation

There are two common ways to add this extension to Isaac Sim.

### Option A — Add the local folder as an extension search path (recommended)

1. **Clone the repository** to a location on disk:

   ```bash
  https://github.com/saumy007/Factory_Lens
   ```

   This gives you a folder such as `.../my.company.template/exts/my.company.template/`.

2. **Launch Isaac Sim.**

3. Open the **Extensions** window: `Window > Extensions`.

4. Click the **gear / settings icon** in the Extensions window to open the extension search paths.

5. **Add a new search path** pointing to the `exts` folder inside the cloned repo, for example:

   ```
   /home/<user>/<path>/my.company.template/exts
   ```

6. Back in the Extensions list, **search** for the extension by name (e.g. `my.company.template`).

7. **Enable** it with the toggle. The control-panel window appears on startup.

8. *(Optional)* Enable **Autoload** so the extension starts with Isaac Sim automatically.

### Option B — Drop into an existing extensions directory

Copy the `my.company.template` extension folder into a directory already on Isaac Sim's extension search path, then enable it from `Window > Extensions` as in steps 6–7 above.

---

## Usage

1. **Open or build your factory scene** in Isaac Sim and note the **prim paths** of the objects you want to label (visible in the **Stage** panel).

2. **Enable the extension** (see Installation). The **VSM Overlay Control** window opens.

3. If the overlay does not appear immediately at startup (e.g., the viewport was not ready), click **Apply / Refresh Overlay** once the scene is loaded.

4. **Edit any card** from the control panel:
   - Change the **Name** field to rename a station.
   - Edit the **metric** fields (Processing Time, Value Time, Completion).
   - Use the **color pickers** to set header, text, and background colors.
   - Adjust **Hover Height** to raise or lower all cards.

5. Click **Apply / Refresh Overlay** to redraw with your changes.

6. **Navigate the viewport** — cards stay anchored above their objects and face the camera.

---

## Configuration

The set of labeled prims and their default values is defined in the extension's data model at startup (the `self._machines` dictionary in `extension.py`). Each entry maps a **prim path** to a configuration containing the display label, a dictionary of metrics, and three colors (header, text, background).

To label **your own** objects, edit the prim paths in that dictionary to match the paths in your scene's Stage tree, or extend the control panel to add/remove entries at runtime.

Colors are stored as packed **ABGR** integers (alpha, blue, green, red). The control panel's color pickers handle the conversion automatically, so you normally do not need to edit raw hex values.

---

## Project Structure

```
my.company.template/
└── exts/
    └── my.company.template/
        ├── config/
        │   └── extension.toml          # extension manifest (name, version, module entry)
        └── my/
            └── company/
                └── template/
                    ├── __init__.py     # imports the extension class
                    └── extension.py    # extension logic: control panel + overlay
```

> **Note on the extension class name:** the class defined in `extension.py` must match the name imported in `__init__.py`. If you rename the class, update the `from .extension import <ClassName>` line in `__init__.py` to match, or the extension will fail to load.

---

## Troubleshooting

**Extension fails to load with `cannot import name ... from ... extension`**
The class name in `extension.py` does not match the name imported in `__init__.py`. Make the two identical, save, then disable and re-enable the extension.

**Control panel opens but no cards appear in the viewport**
Click **Apply / Refresh Overlay** after the scene has fully loaded. If still nothing shows, confirm the prim paths in the configuration match paths that exist in your Stage tree.

**Cards appear in the wrong place (beside or inside objects)**
This is usually an up-axis or scale issue. The placement assumes a Y-up scene. Verify your scene's up-axis and adjust the hover height; for very large or very small scenes, tune the card dimensions.

**Cards do not track the camera (stay fixed on screen)**
The per-frame camera synchronization did not bind to the active viewport. Make sure a viewport is open and focused, then refresh the overlay.

**A prim is found but no card appears for it**
The prim may have an empty bounding box (no directly renderable geometry on that prim). Point the overlay at a child prim that has geometry, or at a prim whose bounds enclose the object.

---

## Roadmap

Planned enhancements:

- **Live metrics** — drive Processing Time and completion from the running simulation rather than static values, so cards update in real time.
- **Bottleneck highlighting** — automatically color the slowest station to flag it as the constraint.
- **Add/remove cards from the UI** — manage the labeled prim set entirely from the control panel.
- **Persistence** — save and load card configurations with the scene.

---

## License

Specify your chosen license here (for example, MIT or Apache 2.0). Add a `LICENSE` file to the repository root.

---

## Acknowledgements

Built on NVIDIA Omniverse Isaac Sim and the `omni.ui` / `omni.ui.scene` UI framework.
