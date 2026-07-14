"""Bildbasiertes Kamera-Tracking: Homographie Feld->Bild pro Frame nachfuehren.

Kernidee (wie bei bildbasierten Broadcast-AR-Systemen): Zwischen aufeinander
folgenden Frames wird eine Warp-Homographie dH (Bild_t-1 -> Bild_t) aus
Feature-Matches geschaetzt. Damit gilt:  H_t (Welt->Bild_t) = dH @ H_{t-1}.

Grenzen (ehrlich): reines Frame-zu-Frame-Chaining DRIFTET langsam, weil sich
kleine Fehler aufsummieren. Broadcast-robuste Systeme verankern zusaetzlich pro
Frame an einem Feldmodell (erkannte Yard-/Seitenlinien) -> siehe reanchor-Hook.
Dieses Modul liefert die tragende Basis und eine ehrliche Drift-Messung.
"""
from __future__ import annotations

import numpy as np
import cv2


class PitchTracker:
    def __init__(self, ref_gray, H0, max_features=1200, min_inliers=25,
                 downscale=1.0):
        """H0: Homographie Welt(Yards)->Bild fuer den Referenzframe."""
        self.H = np.asarray(H0, dtype=np.float64)
        self.min_inliers = min_inliers
        self.downscale = downscale
        self.orb = cv2.ORB_create(max_features)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.prev = self._prep(ref_gray)
        self.prev_kp, self.prev_des = self.orb.detectAndCompute(self.prev, None)
        self.last_inliers = 0
        self.lost = False

    def _prep(self, gray):
        if gray.ndim == 3:
            gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        if self.downscale != 1.0:
            gray = cv2.resize(gray, None, fx=self.downscale, fy=self.downscale)
        return gray

    def update(self, frame_or_gray):
        """Neuen Frame verarbeiten, aktualisierte H (Welt->Bild) zurueckgeben.

        Bei zu wenigen/instabilen Matches wird H gehalten (kein Sprung) und
        self.lost gesetzt.
        """
        cur = self._prep(frame_or_gray)
        kp, des = self.orb.detectAndCompute(cur, None)
        if des is None or self.prev_des is None or len(kp) < 8:
            self.lost = True
            return self.H

        matches = self.matcher.match(self.prev_des, des)
        if len(matches) < 8:
            self.lost = True
            self._roll(cur, kp, des)
            return self.H

        matches = sorted(matches, key=lambda m: m.distance)
        src = np.float32([self.prev_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        dH, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
        inliers = int(mask.sum()) if mask is not None else 0
        self.last_inliers = inliers
        if dH is None or inliers < self.min_inliers:
            self.lost = True
            self._roll(cur, kp, des)
            return self.H

        # Downscale-Korrektur: dH gilt im skalierten Raum -> in Vollaufloesung bringen.
        if self.downscale != 1.0:
            s = self.downscale
            S = np.array([[s, 0, 0], [0, s, 0], [0, 0, 1]], np.float64)
            dH = np.linalg.inv(S) @ dH @ S

        self.H = dH @ self.H
        self.lost = False
        self._roll(cur, kp, des)
        return self.H

    def _roll(self, cur, kp, des):
        self.prev, self.prev_kp, self.prev_des = cur, kp, des

    def reanchor(self, H_model):
        """Optionaler Hook: absolute Verankerung aus einem Feldmodell-Fit
        (erkannte Yard-/Seitenlinien) gegen Drift. Hier bewusst offen gelassen –
        das ist der Schritt Richtung broadcast-robust (Phase 3)."""
        if H_model is not None:
            self.H = np.asarray(H_model, dtype=np.float64)
