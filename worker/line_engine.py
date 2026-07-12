#!/usr/bin/env python3
"""Linien-Engine (Data-Plane).

Hauptschleife: Frame lesen -> (Tracking) -> Yard-Linie projizieren -> Rasen-Maske ->
Compositing -> ausgeben. Der heisse State (an/aus, Yard-Position, Farbe) wird aus
config/state.<camera>.json gepollt und ist damit live vom Node-Server steuerbar.

Beispiele:
  python worker/line_engine.py --config config/config.json --camera cam1 --sink window
  python worker/line_engine.py --config config/config.json --camera cam1 \
         --source-override "ndi://KAMERA (Cam 1)" --sink ndi
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import homography as hg           # noqa: E402
import occlusion as occ          # noqa: E402
import graphics as gfx           # noqa: E402
import hud                       # noqa: E402
from io_sources import open_source  # noqa: E402
from io_sinks import open_sink      # noqa: E402


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_camera(config, cam_id):
    for cam in config.get("cameras", []):
        if cam["id"] == cam_id:
            return cam
    raise SystemExit(f"Kamera '{cam_id}' nicht in Config gefunden")


def state_path(config_path, cam_id):
    return os.path.join(os.path.dirname(config_path), f"state.{cam_id}.json")


def gamestate_path(config_path):
    """Geteilter Spielstand (Down & Distance, Strafen) fuer alle Kameras."""
    return os.path.join(os.path.dirname(config_path), "gamestate.json")


def read_state(path, defaults):
    try:
        with open(path, "r", encoding="utf-8") as f:
            s = json.load(f)
            return {**defaults, **s}
    except (FileNotFoundError, json.JSONDecodeError):
        return defaults


def main():
    ap = argparse.ArgumentParser(description="Football Leit-Liniensystem Engine")
    ap.add_argument("--config", required=True)
    ap.add_argument("--camera", required=True)
    ap.add_argument("--sink", default="window", choices=["window", "file", "ndi"])
    ap.add_argument("--source-override", default=None,
                    help="Quelle ueberschreiben, z.B. 'ndi://KAMERA (Cam 1)' oder 'device:0'")
    ap.add_argument("--out", default="out/line.mp4")
    ap.add_argument("--loop", action="store_true",
                    help="Video-Datei in Schleife abspielen (fake Live-Feed)")
    ap.add_argument("--max-frames", type=int, default=0, help="Nach N Frames stoppen (0 = unbegrenzt)")
    ap.add_argument("--state-poll", type=int, default=5, help="State alle N Frames neu lesen")
    args = ap.parse_args()

    config = load_json(args.config)
    cam = find_camera(config, args.camera)

    field_cfg = config.get("field", {})
    field_width = float(field_cfg.get("width", 53.3))
    line_cfg = config.get("line", {})
    occ_cfg = config.get("occlusion", {})
    teams = config.get("teams", {})
    field_graphics = config.get("fieldGraphics", [])
    overlays = config.get("overlays", {})
    assets_root = os.path.dirname(os.path.abspath(args.config))
    assets_root = os.path.dirname(assets_root)  # Projektwurzel

    # Homographie aus Kalibrierung (fixed).
    cal = cam.get("calibration") or {}
    if not cal.get("imagePoints"):
        raise SystemExit("Keine Kalibrierpunkte – bitte zuerst in der UI kalibrieren.")
    H = hg.compute_homography(cal["worldPoints"], cal["imagePoints"])

    tracked = cam.get("mode") == "tracked"
    ref_gray = None  # fuer spaeteres optisches Tracking

    # Quelle / Ziel
    spec = args.source_override or cam.get("source", {}).get("path") \
        or cam.get("source", {}).get("name")
    if cam.get("source", {}).get("type") == "ndi" and not args.source_override:
        spec = "ndi://" + cam["source"].get("name", "")
    src = open_source(spec, loop=args.loop)
    sink_name = cam.get("output", {}).get("name", f"LINE-{args.camera.upper()}")
    sink = open_sink(args.sink, name=sink_name, out_path=args.out)

    st_path = state_path(args.config, args.camera)
    defaults = {
        "enabled": True,
        "yardPosition": float(line_cfg.get("yardPosition", 45.0)),
        "colorBGR": line_cfg.get("colorBGR", [0, 220, 255]),
        "showGraphics": True,
        "showScorebug": True,
    }
    state = read_state(st_path, defaults)

    # Geteilter Spielstand (Down & Distance, Strafen, LOS/First-Down).
    gs_path = gamestate_path(args.config)
    gs_defaults = config.get("gameState", {
        "possession": "home", "down": 1, "distance": 10,
        "losYard": 45.0, "firstDownYard": 55.0,
        "penalty": {"active": False, "text": "", "team": "home"},
    })
    gamestate = read_state(gs_path, gs_defaults)

    print(f"[{args.camera}] Engine gestartet  quelle={spec}  sink={args.sink}  "
          f"mode={cam.get('mode')}", flush=True)

    hsv_lo = occ_cfg.get("fieldHsvLower", [33, 40, 40])
    hsv_hi = occ_cfg.get("fieldHsvUpper", [90, 255, 255])
    morph = int(occ_cfg.get("morphKernel", 5))
    width_yards = float(line_cfg.get("widthYards", 0.35))
    softness = int(line_cfg.get("softnessPx", 2))

    frame_no = 0
    try:
        while True:
            ok, frame = src.read()
            if not ok or frame is None:
                print(f"[{args.camera}] keine Frames mehr – Ende", flush=True)
                break

            if frame_no % args.state_poll == 0:
                state = read_state(st_path, defaults)
                gamestate = read_state(gs_path, gs_defaults)

            if tracked:
                gray = None  # cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if ref_gray is None:
                    ref_gray = gray
                H = hg.track_update(H, ref_gray, gray)

            if state.get("enabled", True):
                # Rasen-Maske einmal berechnen (fuer Linien UND Logos = Okklusion).
                field_msk = occ.field_mask(frame, hsv_lo, hsv_hi, morph)

                # 1) Team-Logos aufs Feld (hinter Spielern).
                if state.get("showGraphics", True) and field_graphics:
                    frame = gfx.render_field_graphics(
                        frame, H, field_graphics, field=field_msk, assets_root=assets_root)

                # 2) Line of Scrimmage (blau) + First-Down-Line (gelb) aus Spielstand.
                los_cfg = overlays.get("lineOfScrimmage", {})
                fd_cfg = overlays.get("firstDownLine", {"enabled": True})

                def draw_line(yard, color):
                    quad = hg.yard_line_quad(float(yard), field_width, width_yards)
                    lm = occ.rasterize_line(frame.shape[:2], hg.project_points(H, quad))
                    return occ.composite(frame, lm, field_msk, color, softness)

                if los_cfg.get("enabled", True):
                    frame = draw_line(gamestate.get("losYard", 45.0),
                                      los_cfg.get("colorBGR", [255, 90, 0]))
                if fd_cfg.get("enabled", True):
                    fd_yard = gamestate.get("firstDownYard", state.get("yardPosition", 55.0))
                    frame = draw_line(fd_yard, state.get("colorBGR", [0, 220, 255]))

                # 3) Scorebug + Strafen-Banner (Bildschirm-Overlay, ins Feed gebrannt).
                if state.get("showScorebug", True) and overlays.get("scorebug", {}).get("enabled", True):
                    frame = hud.render_scorebug(frame, gamestate, teams, overlays)

            if not sink.write(frame):  # WindowSink: ESC -> False
                break
            frame_no += 1
            if args.max_frames and frame_no >= args.max_frames:
                print(f"[{args.camera}] max-frames erreicht", flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        src.release()
        sink.release()
        print(f"[{args.camera}] gestoppt nach {frame_no} Frames", flush=True)


if __name__ == "__main__":
    main()
