import omni.ext
import omni.ui as ui
import omni.usd
import carb
from pxr import UsdGeom, Gf
from omni.ui import scene as sc
from omni.kit.viewport.utility import get_active_viewport_window, get_active_viewport
import omni.kit.app


class MyTemplateExtension(omni.ext.IExt):


    def on_startup(self, ext_id: str):
        carb.log_info("[vsm.overlay] Extension startup")

        # ---- Default machine data: editable label + metrics + colors ----
        # Each entry: prim_path -> config dict
        self._machines = {
            "/scene/scene_01": {
                "label": "SMT Pick & Place",
                "metrics": {"Processing Time": "45s", "Value Time": "30s", "Completion": "92%"},
                "header_color": 0xFF00FFFF,   # ABGR cyan
                "text_color": 0xFFFFFFFF,     # white
                "bg_color": 0xCC202020,       # dark screen, semi-transparent
            },
            "/scene/scene_02": {
                "label": "Reflow Oven",
                "metrics": {"Processing Time": "60s", "Value Time": "40s", "Completion": "85%"},
                "header_color": 0xFF00FF00,
                "text_color": 0xFFFFFFFF,
                "bg_color": 0xCC202020,
            },
            "/scene/scene_03": {
                "label": "AOI Inspection",
                "metrics": {"Processing Time": "30s", "Value Time": "25s", "Completion": "97%"},
                "header_color": 0xFF00FFFF,
                "text_color": 0xFFFFFFFF,
                "bg_color": 0xCC202020,
            },
            "/scene/sssssss": {
                "label": "Packaging",
                "metrics": {"Processing Time": "50s", "Value Time": "35s", "Completion": "88%"},
                "header_color": 0xFF00FFFF,
                "text_color": 0xFFFFFFFF,
                "bg_color": 0xCC202020,
            },
            "/scene/Cone": {
                "label": "Station 5",
                "metrics": {"Processing Time": "50s", "Value Time": "35s", "Completion": "88%"},
                "header_color": 0xFFFF8800,
                "text_color": 0xFFFFFFFF,
                "bg_color": 0xCC202020,
            },
        }

        self._extra_margin = 2.0
        self._scene_view = None
        self._update_sub = None
        self._field_widgets = {}  # for reading edits back

        self._build_control_panel()
        self._rebuild_overlay()

    # ============================================================
    #  CONTROL PANEL (the editable UI window)
    # ============================================================
    def _build_control_panel(self):
        self._window = ui.Window("VSM Overlay Control", width=420, height=600)
        with self._window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=10, height=0):
                    ui.Label("Factory VSM Overlay", height=28,
                             style={"font_size": 20, "color": 0xFF00D9FF})
                    ui.Separator(height=2)

                    # Global hover height control
                    with ui.HStack(height=26, spacing=6):
                        ui.Label("Hover Height:", width=110)
                        margin_field = ui.FloatField(width=80)
                        margin_field.model.set_value(self._extra_margin)

                        def on_margin_changed(m):
                            self._extra_margin = m.get_value_as_float()
                        margin_field.model.add_value_changed_fn(on_margin_changed)

                    ui.Separator(height=2)

                    # Per-machine editable blocks
                    for path, cfg in self._machines.items():
                        self._build_machine_editor(path, cfg)
                        ui.Separator(height=2)

                    # Apply button
                    ui.Button("Apply / Refresh Overlay", height=40,
                              clicked_fn=self._on_apply,
                              style={"background_color": 0xFF006699,
                                     "font_size": 16})

    def _build_machine_editor(self, path, cfg):
        """Builds an editable section for one machine."""
        with ui.CollapsableFrame(f"{cfg['label']}  ({path})", height=0):
            with ui.VStack(spacing=6, height=0):
                widgets = {}

                # Editable display name
                with ui.HStack(height=26, spacing=6):
                    ui.Label("Name:", width=90)
                    name_field = ui.StringField(height=24)
                    name_field.model.set_value(cfg["label"])
                    widgets["label"] = name_field

                # Editable metrics
                for metric_key in list(cfg["metrics"].keys()):
                    with ui.HStack(height=26, spacing=6):
                        ui.Label(f"{metric_key}:", width=120)
                        mfield = ui.StringField(height=24)
                        mfield.model.set_value(cfg["metrics"][metric_key])
                        widgets[f"metric::{metric_key}"] = mfield

                # Color editors (RGB sliders -> packed ABGR)
                ui.Label("Header Color:", height=20)
                widgets["header_color"] = self._build_color_picker(cfg["header_color"])

                ui.Label("Text Color:", height=20)
                widgets["text_color"] = self._build_color_picker(cfg["text_color"])

                ui.Label("Screen Background:", height=20)
                widgets["bg_color"] = self._build_color_picker(cfg["bg_color"], has_alpha=True)

                self._field_widgets[path] = widgets

    def _build_color_picker(self, initial_abgr, has_alpha=False):
        """Returns an omni.ui.ColorWidget; converts to/from ABGR ints."""
        # Unpack ABGR int -> r,g,b,a floats (0..1)
        a = ((initial_abgr >> 24) & 0xFF) / 255.0
        b = ((initial_abgr >> 16) & 0xFF) / 255.0
        g = ((initial_abgr >> 8) & 0xFF) / 255.0
        r = (initial_abgr & 0xFF) / 255.0
        with ui.HStack(height=24, spacing=4):
            cw = ui.ColorWidget(r, g, b, a, width=60)
        return cw

    # ============================================================
    #  READ EDITS BACK + REBUILD
    # ============================================================
    def _on_apply(self):
        """Read all UI fields back into self._machines, then rebuild overlay."""
        for path, widgets in self._field_widgets.items():
            cfg = self._machines[path]

            # Name
            cfg["label"] = widgets["label"].model.get_value_as_string()

            # Metrics
            new_metrics = {}
            for wkey, widget in widgets.items():
                if wkey.startswith("metric::"):
                    metric_name = wkey.split("::", 1)[1]
                    new_metrics[metric_name] = widget.model.get_value_as_string()
            cfg["metrics"] = new_metrics

            # Colors
            cfg["header_color"] = self._color_widget_to_abgr(widgets["header_color"])
            cfg["text_color"] = self._color_widget_to_abgr(widgets["text_color"])
            cfg["bg_color"] = self._color_widget_to_abgr(widgets["bg_color"])

        self._rebuild_overlay()
        carb.log_info("[vsm.overlay] Overlay refreshed from UI edits")

    def _color_widget_to_abgr(self, color_widget):
        """Read a ui.ColorWidget's 4 child float models -> packed ABGR int."""
        model = color_widget.model
        children = model.get_item_children()
        r = model.get_item_value_model(children[0]).get_value_as_float()
        g = model.get_item_value_model(children[1]).get_value_as_float()
        b = model.get_item_value_model(children[2]).get_value_as_float()
        a = model.get_item_value_model(children[3]).get_value_as_float() if len(children) > 3 else 1.0
        return (int(a*255) << 24) | (int(b*255) << 16) | (int(g*255) << 8) | int(r*255)

    # ============================================================
    #  OVERLAY DRAWING
    # ============================================================
    def _get_top_center(self, path):
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid():
            carb.log_warn(f"[vsm.overlay] prim not found: {path}")
            return None
        bbox_cache = UsdGeom.BBoxCache(0, [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
        rng = bbox_cache.ComputeWorldBound(prim).ComputeAlignedRange()
        if rng.IsEmpty():
            return None
        mn, mx = rng.GetMin(), rng.GetMax()
        return Gf.Vec3d((mn[0]+mx[0])/2.0, mx[1]+self._extra_margin, (mn[2]+mx[2])/2.0)

    def _rebuild_overlay(self):
        viewport_window = get_active_viewport_window()
        if viewport_window is None:
            carb.log_error("[vsm.overlay] No active viewport")
            return

        # Clear previous
        if self._scene_view:
            try:
                self._scene_view.scene.clear()
            except Exception:
                pass

        with viewport_window.get_frame("vsm_overlay"):
            self._scene_view = sc.SceneView()
            with self._scene_view.scene:
                for path, cfg in self._machines.items():
                    pos = self._get_top_center(path)
                    if pos is None:
                        continue
                    self._draw_label_card(pos, cfg)

        # Camera sync
        self._setup_camera_sync()

    def _draw_label_card(self, pos, cfg):
        """Draws a screen-like card: background rect + header + metric lines."""
        metrics = cfg["metrics"]
        n_lines = len(metrics)

        with sc.Transform(transform=sc.Matrix44.get_translation_matrix(pos[0], pos[1], pos[2])):
            # ---- Background rectangle (the "computer screen") ----
            # Width/height in world units; tune to taste
            card_w = 3.0
            card_h = 0.6 + n_lines * 0.35
            # sc.Rectangle is screen-facing; draw it slightly behind text
            with sc.Transform(transform=sc.Matrix44.get_translation_matrix(0, 0.1, -0.01)):
                sc.Rectangle(card_w, card_h,
                             color=cfg["bg_color"],
                             thickness=0)
                # Border for screen-like look
                sc.Rectangle(card_w, card_h,
                             color=0xFF000000, wireframe=True, thickness=2)

            # ---- Header (machine name) ----
            with sc.Transform(transform=sc.Matrix44.get_translation_matrix(0, card_h/2 - 0.2, 0)):
                sc.Label(cfg["label"], alignment=ui.Alignment.CENTER,
                         color=cfg["header_color"], size=22)

            # ---- Metric lines ----
            y = card_h/2 - 0.55
            for k, v in metrics.items():
                with sc.Transform(transform=sc.Matrix44.get_translation_matrix(0, y, 0)):
                    sc.Label(f"{k}: {v}", alignment=ui.Alignment.CENTER,
                             color=cfg["text_color"], size=16)
                y -= 0.35

    def _setup_camera_sync(self):
        if self._update_sub:
            self._update_sub.unsubscribe()
            self._update_sub = None

        viewport_api = get_active_viewport()

        def _on_update(e):
            try:
                proj = viewport_api.projection
                view = viewport_api.transform.GetInverse()
                self._scene_view.projection = [v for row in proj for v in row]
                self._scene_view.view = [v for row in view for v in row]
            except Exception:
                pass

        self._update_sub = omni.kit.app.get_app().get_update_event_stream() \
            .create_subscription_to_pop(_on_update, name="vsm_camera_sync")

    # ============================================================
    def on_shutdown(self):
        carb.log_info("[vsm.overlay] Extension shutdown")
        if self._update_sub:
            self._update_sub.unsubscribe()
            self._update_sub = None
        if self._scene_view:
            try:
                self._scene_view.scene.clear()
            except Exception:
                pass
            self._scene_view = None
        if self._window:
            self._window.destroy()
            self._window = None