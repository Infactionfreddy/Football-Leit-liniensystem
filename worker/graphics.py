"""Field-Graphics: Bilder (Team-Logos etc.) perspektivisch auf den Rasen warpen,
mit optionaler Okklusion (hinter Spielern)."""
from __future__ import annotations

import os
import numpy as np
import cv2

import homography as hg


_IMAGE_CACHE = {}


def load_rgba(path):
    """Bild als BGRA laden (Alpha ergaenzen, falls keins vorhanden). Gecacht."""
    if path in _IMAGE_CACHE:
        return _IMAGE_CACHE[path]
    if not os.path.exists(path):
        raise FileNotFoundError(f"Grafik nicht gefunden: {path}")
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Grafik nicht lesbar: {path}")
    if img.ndim == 2:  # Graustufen
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:  # BGR ohne Alpha
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    _IMAGE_CACHE[path] = img
    return img


def world_quad(center_yard, width_yards, height_yards, rotation_deg=0.0):
    """Vier Weltecken (Yards) eines Bild-Rechtecks um center_yard, optional gedreht.
    Reihenfolge: oben-links, oben-rechts, unten-rechts, unten-links."""
    cx, cy = center_yard
    hw, hh = width_yards / 2.0, height_yards / 2.0
    local = np.array([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]], np.float64)
    if rotation_deg:
        r = np.radians(rotation_deg)
        c, s = np.cos(r), np.sin(r)
        local = local @ np.array([[c, -s], [s, c]], np.float64).T
    return local + np.array([cx, cy], np.float64)


def warp_onto_field(frame_bgr, H, image_bgra, center_yard, width_yards,
                    height_yards=None, rotation_deg=0.0, opacity=1.0,
                    field=None):
    """Warpt image_bgra perspektivisch aufs Feld und komponiert ins Bild.

    field: optionale Rasen-Maske (HxW, 255=Feld). Wenn gesetzt, wird die Grafik
    nur auf Rasenpixeln gezeichnet -> liegt hinter Spielern.
    """
    h_img, w_img = image_bgra.shape[:2]
    if height_yards is None:  # Seitenverhaeltnis des Bildes beibehalten
        height_yards = width_yards * (h_img / w_img)

    src = np.array([[0, 0], [w_img, 0], [w_img, h_img], [0, h_img]], np.float32)
    dst_world = world_quad(center_yard, width_yards, height_yards, rotation_deg)
    dst_img = hg.project_points(H, dst_world).astype(np.float32)

    M = cv2.getPerspectiveTransform(src, dst_img)
    Hh, Ww = frame_bgr.shape[:2]
    warped = cv2.warpPerspective(image_bgra, M, (Ww, Hh),
                                 flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))

    alpha = (warped[:, :, 3].astype(np.float32) / 255.0) * float(opacity)
    if field is not None:
        alpha *= (field.astype(np.float32) / 255.0)
    alpha = alpha[:, :, None]

    bgr = warped[:, :, :3].astype(np.float32)
    out = frame_bgr.astype(np.float32) * (1.0 - alpha) + bgr * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def render_field_graphics(frame_bgr, H, items, field=None, assets_root="."):
    """Rendert eine Liste von Field-Graphics (aus config.fieldGraphics)."""
    for it in items:
        if not it.get("enabled", True) or it.get("type") != "logo":
            continue
        path = it["image"]
        if not os.path.isabs(path):
            path = os.path.join(assets_root, path)
        img = load_rgba(path)
        frame_bgr = warp_onto_field(
            frame_bgr, H, img,
            center_yard=it.get("centerYard", [60, 26.65]),
            width_yards=float(it.get("widthYards", 10)),
            height_yards=(float(it["heightYards"]) if it.get("heightYards") else None),
            rotation_deg=float(it.get("rotationDeg", 0.0)),
            opacity=float(it.get("opacity", 1.0)),
            field=field if it.get("occlude", True) else None,
        )
    return frame_bgr
