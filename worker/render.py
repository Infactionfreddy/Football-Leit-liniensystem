"""Gemeinsames Per-Frame-Rendering fuer Headless-Engine UND Desktop-App.

Eine einzige Quelle der Wahrheit: Logos -> Line of Scrimmage (blau) ->
First-Down-Line (gelb) -> Scorebug/Strafen. So rendern CLI und GUI identisch.
"""
from __future__ import annotations

import homography as hg
import occlusion as occ
import graphics as gfx
import hud


def field_mask_from_cfg(frame_bgr, cfg):
    occ_cfg = cfg.get("occlusion", {})
    return occ.field_mask(
        frame_bgr,
        occ_cfg.get("fieldHsvLower", [33, 40, 40]),
        occ_cfg.get("fieldHsvUpper", [90, 255, 255]),
        int(occ_cfg.get("morphKernel", 5)),
    )


def compose(frame_bgr, H, cfg, gamestate, *, show_graphics=True,
            show_scorebug=True, assets_root=".", field=None):
    """Komponiert ein Ausgabebild.

    frame_bgr wird NICHT in-place veraendert (occ/gfx geben neue Arrays zurueck).
    field: optionale vorberechnete Rasen-Maske (spart Doppelberechnung bei
    Preview+Program aus demselben Quellframe).
    """
    field_cfg = cfg.get("field", {})
    field_width = float(field_cfg.get("width", 53.3))
    line_cfg = cfg.get("line", {})
    overlays = cfg.get("overlays", {})
    teams = cfg.get("teams", {})
    field_graphics = cfg.get("fieldGraphics", [])
    width_yards = float(line_cfg.get("widthYards", 0.35))
    softness = int(line_cfg.get("softnessPx", 2))

    if field is None:
        field = field_mask_from_cfg(frame_bgr, cfg)

    out = frame_bgr

    # 1) Team-Logos aufs Feld (hinter Spielern).
    if show_graphics and field_graphics:
        out = gfx.render_field_graphics(out, H, field_graphics, field=field,
                                        assets_root=assets_root)

    # 2) Line of Scrimmage (blau) + First-Down-Line (gelb).
    los_cfg = overlays.get("lineOfScrimmage", {})
    fd_cfg = overlays.get("firstDownLine", {"enabled": True})

    def draw_line(yard, color):
        quad = hg.yard_line_quad(float(yard), field_width, width_yards)
        lm = occ.rasterize_line(out.shape[:2], hg.project_points(H, quad))
        return occ.composite(out, lm, field, color, softness)

    if los_cfg.get("enabled", True):
        out = draw_line(gamestate.get("losYard", 45.0),
                        los_cfg.get("colorBGR", [255, 90, 0]))
    if fd_cfg.get("enabled", True):
        fd_yard = gamestate.get("firstDownYard", line_cfg.get("yardPosition", 55.0))
        out = draw_line(fd_yard, line_cfg.get("colorBGR", [0, 220, 255]))

    # 3) Scorebug + Strafen-Banner (Bildschirm-Overlay).
    if show_scorebug and overlays.get("scorebug", {}).get("enabled", True):
        out = hud.render_scorebug(out, gamestate, teams, overlays)

    return out, field
