"""Okklusion: die Linie nur auf rasenfarbene Pixel malen, damit sie HINTER
Spielern zu liegen scheint."""
from __future__ import annotations

import numpy as np
import cv2


def field_mask(frame_bgr, hsv_lower, hsv_upper, morph_kernel=5):
    """Binaere Maske der Rasenpixel (255 = Feld)."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower, np.uint8), np.array(hsv_upper, np.uint8))
    if morph_kernel and morph_kernel > 1:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel, morph_kernel))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)   # Rauschen weg
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)  # Loecher zu
    return mask


def rasterize_line(shape_hw, image_quad):
    """Gefuelltes Yard-Linien-Polygon (255 innerhalb) in Bildaufloesung."""
    mask = np.zeros(shape_hw, np.uint8)
    poly = np.round(image_quad).astype(np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(mask, [poly], 255)
    return mask


def composite(frame_bgr, line_mask, field, color_bgr, softness_px=2):
    """Zeichnet die Linie dort, wo line_mask UND field gesetzt sind.

    Weiche Kanten via Gauss-Blur der kombinierten Maske als Alpha.
    """
    draw = cv2.bitwise_and(line_mask, field)
    if softness_px and softness_px > 0:
        k = softness_px * 2 + 1
        alpha = cv2.GaussianBlur(draw, (k, k), 0).astype(np.float32) / 255.0
    else:
        alpha = (draw > 0).astype(np.float32)
    alpha = alpha[:, :, None]  # HxWx1
    color = np.array(color_bgr, np.float32).reshape(1, 1, 3)
    out = frame_bgr.astype(np.float32) * (1.0 - alpha) + color * alpha
    return np.clip(out, 0, 255).astype(np.uint8)
