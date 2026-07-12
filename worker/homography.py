"""Homographie Feld <-> Bild und Yard-Linien-Geometrie.

Feldkoordinaten in Yards: X entlang der Feldlaenge (0..120 inkl. Endzonen),
Y ueber die Breite (0..53.3). Massgebliche Berechnung via cv2.findHomography.
"""
from __future__ import annotations

import numpy as np
import cv2


def compute_homography(world_points, image_points):
    """3x3-Homographie, die Weltpunkte (Yards) auf Bildpunkte (Pixel) abbildet."""
    w = np.asarray(world_points, dtype=np.float64)
    i = np.asarray(image_points, dtype=np.float64)
    if len(w) < 4 or len(w) != len(i):
        raise ValueError("Mindestens 4 gleich viele Welt-/Bildpunkte noetig")
    if len(w) == 4:
        H = cv2.getPerspectiveTransform(w.astype(np.float32), i.astype(np.float32))
    else:
        H, _ = cv2.findHomography(w, i, method=cv2.RANSAC)
        if H is None:
            raise ValueError("Homographie nicht berechenbar (Punkte kollinear?)")
    return H


def yard_line_quad(yard, field_width, width_yards):
    """Vier Weltecken (Yards) des Yard-Linien-Rechtecks."""
    half = width_yards / 2.0
    return np.array([
        [yard - half, 0.0],
        [yard + half, 0.0],
        [yard + half, field_width],
        [yard - half, field_width],
    ], dtype=np.float64)


def project_points(H, world_pts):
    """Projiziert Nx2-Weltpunkte auf Nx2-Bildpixel."""
    pts = np.asarray(world_pts, dtype=np.float64).reshape(-1, 1, 2)
    out = cv2.perspectiveTransform(pts, H)
    return out.reshape(-1, 2)


def track_update(H_ref, ref_gray, cur_gray):
    """Erweiterungspunkt fuer FREI gefuehrte Kameras (mode=tracked).

    Idee: Optical-Flow/Feature-Matching zwischen Referenz-Keyframe und aktuellem
    Frame liefert eine Warp-Homographie dH; die aktualisierte Feld->Bild-Matrix ist
    dann dH @ H_ref. Fuer feste Kameras (mode=fixed) wird dies nicht aufgerufen.

    Rueckgabe hier: unveraendertes H_ref (No-Op-Platzhalter fuer Phase 3).
    """
    return H_ref
