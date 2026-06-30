# Technical Documentation — Factory VSM Overlay

This document describes the internal architecture, data model, drawing pipeline, and extension points of the Factory VSM Overlay extension for NVIDIA Omniverse Isaac Sim 5.0.

---

## 1. Architecture overview

The extension follows a clean separation between **data** (what to display) and **rendering** (how to display it):

```
┌─────────────────────────────────────────────┐
│  Control Panel (omni.ui Window)             │
│  - Editable name / metric / color widgets    │
│  - "Apply / Refresh" button                   │
└───────────────┬─────────────────────────────┘
                │ reads widget values on Apply
                ▼
┌─────────────────────────────────────────────┐
│  Machine config dict  (self._machines)       │
│  path -> {label, metrics, colors}            │
└───────────────┬─────────────────────────────┘
                │ consumed by overlay builder
                ▼
┌─────────────────────────────────────────────┐
│  Overlay builder (_rebuild_overlay)          │
│  - bbox anchor per prim                       │
│  - omni.ui.scene cards                         │
└───────────────┬─────────────────────────────┘
                │ projected each frame
                ▼
┌─────────────────────────────────────────────┐
│  Camera sync (update event subscription)     │
│  - feeds viewport proj/view into SceneView    │
└─────────────────────────────────────────────┘
```

The extension lifecycle is governed by `omni.ext.IExt`:

- `on_startup(ext_id)` — builds the control panel, then builds the initial overlay.
- `on_shutdown()` — unsubscribes the camera-sync callback, clears the scene, destroys the window.

---

## 2. Data model

Each annotated machine is one entry in `self._machines`, keyed by USD prim path:

```python
"/scene/scene_01": {
    "label": "SMT Pick & Place",      # header text (editable)
    "metrics": {                       # ordered VSM readouts (editable)
        "Processing Time": "45s",
        "Value Time": "30s",
        "Completion": "92%",
    },
    "header_color": 0xFF00FFFF,        # ABGR packed int
    "text_color":   0xFFFFFFFF,
    "bg_color":     0xCC202020,        # alpha < FF => semi-transparent screen
}
```

**Color encoding.** `omni.ui.scene` expects colors as 32-bit **ABGR** integers (`0xAABBGGRR`), *not* RGBA. The high byte is alpha. Helper conversions live in `_build_color_picker()` (unpack ABGR → RGBA floats for the picker) and `_color_widget_to_abgr()` (pack RGBA floats → ABGR int on read-back).

---

## 3. Anchoring: placing a card above any prim

Placement uses the prim's **world-space bounding box**, which makes it agnostic to prim type, scale, and pivot:

```python
bbox_cache = UsdGeom.BBoxCache(0, [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
rng = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
mn, mx = rng.GetMin(), rng.GetMax()
anchor = Gf.Vec3d((mn[0]+mx[0])/2.0,    # X center
                  mx[1] + margin,        # top in Y (scene is Y-up) + margin
                  (mn[2]+mx[2])/2.0)     # Z center
```

Key points:

- `ComputeWorldBound` works on `Mesh`, `Xform`, and other `UsdGeomImageable` prims, so the same code annotates a machine group or a single cone.
- The scene is **Y-up**; the card is lifted along **+Y**. For a Z-up scene, lift along `mx[2]` instead.
- `rng.IsEmpty()` is checked; prims with no renderable geometry fall back to their xform translation (or are skipped, depending on build).

---

## 4. Drawing the card

Cards are drawn with the `omni.ui.scene` (`sc`) immediate-mode API inside the active viewport's overlay frame:

```python
with viewport_window.get_frame("vsm_overlay"):
    self._scene_view = sc.SceneView()
    with self._scene_view.scene:
        with sc.Transform(transform=sc.Matrix44.get_translation_matrix(*anchor)):
            sc.Rectangle(card_w, card_h, color=bg_color)        # screen background
            sc.Rectangle(card_w, card_h, color=0xFF000000,      # border
                         wireframe=True, thickness=2)
            sc.Label(label, alignment=ui.Alignment.CENTER,
                     color=header_color, size=22)               # header
            # ... metric lines stacked downward via nested Transforms
```

Notes:

- **Screen-aligned labels.** `sc.Label` faces the camera by default, so text stays readable from any orbit angle while the anchor stays fixed in world space.
- **Card sizing.** `card_h` scales with the number of metric lines: `card_h = 0.6 + n_lines * 0.35` (world units). `card_w` is fixed (default `3.0`) and can be tuned per scene scale.
- **Layering.** The background rectangle is offset slightly behind the text along the local axis to avoid z-fighting with labels.

---

## 5. Camera synchronization

`get_frame()` alone does **not** bind the `SceneView` projection to the viewport camera on Isaac Sim 5.0; without an explicit sync the cards render into an unprojected space and are invisible. The fix is a per-frame update subscription:

```python
viewport_api = get_active_viewport()

def _on_update(e):
    proj = viewport_api.projection                 # 4x4 projection
    view = viewport_api.transform.GetInverse()     # world-to-camera
    self._scene_view.projection = [v for row in proj for v in row]
    self._scene_view.view       = [v for row in view for v in row]

self._update_sub = omni.kit.app.get_app() \
    .get_update_event_stream() \
    .create_subscription_to_pop(_on_update, name="vsm_camera_sync")
```

`viewport_api.transform` is the camera-to-world matrix; its inverse is the view matrix the `SceneView` needs. Both matrices are flattened row-major to 16-float lists. The subscription is stored so it can be cleanly unsubscribed in `on_shutdown` and on each rebuild (preventing duplicate callbacks).

---

## 6. Edit → apply cycle

1. The control panel builds one collapsible section per machine, each holding a `StringField` for the name, `StringField`s for metrics, and `ColorWidget`s for colors.
2. On **Apply**, `_on_apply()` iterates `self._field_widgets`, reading each widget's model value back into `self._machines`.
3. `_rebuild_overlay()` clears the previous `SceneView` scene and redraws from the updated config.
4. `_setup_camera_sync()` re-establishes the per-frame projection feed.

Reading a `ColorWidget` back requires walking its child item models:

```python
model = color_widget.model
children = model.get_item_children()
r = model.get_item_value_model(children[0]).get_value_as_float()
g = model.get_item_value_model(children[1]).get_value_as_float()
b = model.get_item_value_model(children[2]).get_value_as_float()
a = model.get_item_value_model(children[3]).get_value_as_float() if len(children) > 3 else 1.0
```

---

## 7. Extension manifest (`extension.toml`)

The manifest must declare the Python module and any Kit dependencies. Minimum relevant fields:

```toml
[package]
version = "1.0.0"
title = "Factory VSM Overlay"
description = "Hovering, editable VSM metric cards above factory machines."
category = "Simulation"

[dependencies]
"omni.ui" = {}
"omni.usd" = {}
"omni.kit.viewport.utility" = {}

[[python.module]]
name = "my.company.template"
```

The `name` under `[[python.module]]` must match the package directory, and the class imported in `__init__.py` must match the class defined in `extension.py`.

---

## 8. Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImportError: cannot import name 'X'` | Class name in `extension.py` does not match the name imported in `__init__.py` | Make both identical; save; toggle the extension off/on |
| Labels drawn (log confirms) but invisible | Camera sync not bound | Ensure the update subscription feeds `projection`/`view` each frame |
| Card appears beside, not above, the machine | Wrong up-axis | Lift along the scene's up-axis (Y vs. Z) |
| Card too large/small | World-unit sizing vs. scene scale | Tune `card_w`, `card_h`, and `Hover Height` |
| `BBOX IS EMPTY` warning | Prim has no renderable geometry directly | Target a child mesh, or rely on the xform-translation fallback |
| `'SceneView' has no attribute 'projection'` | Kit build API variance | Use the viewport scene-registry binding instead of bare `SceneView` |

---

## 9. Extending to live data

The metric strings are static today but the design anticipates live values. To drive them from simulation:

1. Replace the literal metric strings with values pulled from your station logic each tick (e.g., a counter incremented in a physics/update callback).
2. Call a lightweight "update labels" routine on a timer rather than a full `_rebuild_overlay()` — update only the `sc.Label` text where the API allows, or throttle full rebuilds to a few times per second.
3. Add bottleneck logic: compare per-station processing times and set `header_color` to a warning color for the slowest station before drawing.

---

## 10. References

- NVIDIA Omniverse Isaac Sim Documentation — https://docs.isaacsim.omniverse.nvidia.com/
- `omni.ui.scene` API — Kit SDK documentation
- USD `UsdGeom.BBoxCache` — https://openusd.org/release/api/class_usd_geom_b_box_cache.html
