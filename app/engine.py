"""Live-Engine als QThread: liest die Quelle, komponiert PROGRAM und PREVIEW aus
demselben Frame und schickt beide Bilder an die GUI. Nutzt dieselbe
Render-Pipeline wie die Headless-CLI (worker/render.py)."""
from __future__ import annotations

import os
import sys
import time
import copy

import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

# worker/ auf den Importpfad legen (gemeinsame CV-Module).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))

import homography as hg          # noqa: E402
import render as rnd             # noqa: E402
from tracking import PitchTracker  # noqa: E402
from io_sources import open_source  # noqa: E402

try:
    from io_sinks import NdiSink  # optional
except Exception:  # pragma: no cover
    NdiSink = None


class EngineThread(QThread):
    # program(ndarray BGR), preview(ndarray BGR), status(dict)
    framesReady = Signal(object, object)
    status = Signal(dict)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._running = False
        self._spec = None
        self._loop = True
        self._fps = 50.0
        self._cfg = {}
        self._H = None
        self._assets_root = ROOT
        self._program_gs = {}
        self._preview_gs = {}
        self._show_graphics = True
        self._show_scorebug = True
        self._ndi_enabled = False
        self._ndi_name = "LINE-PROGRAM"
        self._ndi = None
        self._tracking = False
        self._calib_epoch = 0  # zaehlt bei jeder Neukalibrierung hoch -> Tracker-Reset

    # ---- Setter (aus dem GUI-Thread aufgerufen) ----
    def configure(self, cfg, spec, assets_root=None, fps=50.0, loop=True):
        with QMutexLocker(self._mutex):
            self._cfg = cfg
            self._spec = spec
            self._fps = float(fps)
            self._loop = bool(loop)
            if assets_root:
                self._assets_root = assets_root

    def set_calibration(self, world_points, image_points):
        H = hg.compute_homography(world_points, image_points)
        with QMutexLocker(self._mutex):
            self._H = H
            self._calib_epoch += 1  # Tracker beim naechsten Frame neu verankern

    def set_tracking(self, enabled):
        with QMutexLocker(self._mutex):
            self._tracking = bool(enabled)
            self._calib_epoch += 1  # Moduswechsel -> Tracker neu initialisieren

    def set_program_state(self, gs):
        with QMutexLocker(self._mutex):
            self._program_gs = copy.deepcopy(gs)

    def set_preview_state(self, gs):
        with QMutexLocker(self._mutex):
            self._preview_gs = copy.deepcopy(gs)

    def set_flags(self, show_graphics=None, show_scorebug=None):
        with QMutexLocker(self._mutex):
            if show_graphics is not None:
                self._show_graphics = show_graphics
            if show_scorebug is not None:
                self._show_scorebug = show_scorebug

    def set_cfg(self, cfg):
        with QMutexLocker(self._mutex):
            self._cfg = cfg

    def set_ndi(self, enabled, name=None):
        with QMutexLocker(self._mutex):
            self._ndi_enabled = enabled
            if name:
                self._ndi_name = name

    def stop(self):
        self._running = False

    # ---- Thread-Schleife ----
    def run(self):
        with QMutexLocker(self._mutex):
            spec, loop, fps = self._spec, self._loop, self._fps
        if not spec:
            self.error.emit("Keine Quelle konfiguriert")
            return
        try:
            src = open_source(spec, loop=loop)
        except Exception as e:
            self.error.emit(f"Quelle konnte nicht geoeffnet werden: {e}")
            return

        self._running = True
        period = 1.0 / max(1.0, fps)
        n, t_stat = 0, time.time()
        tracker = None
        tracker_epoch = -1
        try:
            while self._running:
                t0 = time.time()
                ok, frame = src.read()
                if not ok or frame is None:
                    self.error.emit("Keine Frames mehr")
                    break
                tally = None

                with QMutexLocker(self._mutex):
                    cfg = self._cfg
                    H = self._H
                    prog_gs = self._program_gs
                    prev_gs = self._preview_gs
                    sg, ss = self._show_graphics, self._show_scorebug
                    ndi_on, ndi_name = self._ndi_enabled, self._ndi_name
                    tracking, epoch = self._tracking, self._calib_epoch

                if H is None:
                    # Ohne Kalibrierung nur das Rohbild spiegeln.
                    self.framesReady.emit(frame.copy(), frame.copy())
                else:
                    # Kamera-Tracking: Homographie pro Frame nachfuehren.
                    if tracking:
                        if tracker is None or epoch != tracker_epoch:
                            tracker = PitchTracker(frame, H)
                            tracker_epoch = epoch
                            H_use, tally = H, "TRACK init"
                        else:
                            H_use = tracker.update(frame)
                            tally = "TRACK lost" if tracker.lost else f"TRACK {tracker.last_inliers}"
                    else:
                        tracker = None
                        H_use, tally = H, None
                    H = H_use
                    mask = rnd.field_mask_from_cfg(frame, cfg)
                    program, _ = rnd.compose(frame.copy(), H, cfg, prog_gs,
                                             show_graphics=sg, show_scorebug=ss,
                                             assets_root=self._assets_root, field=mask)
                    preview, _ = rnd.compose(frame.copy(), H, cfg, prev_gs,
                                             show_graphics=sg, show_scorebug=ss,
                                             assets_root=self._assets_root, field=mask)
                    self.framesReady.emit(program, preview)

                    if ndi_on and NdiSink is not None:
                        self._ensure_ndi(ndi_name, fps).write(program)
                    elif not ndi_on and self._ndi is not None:
                        self._release_ndi()

                n += 1
                if time.time() - t_stat >= 1.0:
                    self.status.emit({"fps": n / (time.time() - t_stat), "track": tally})
                    n, t_stat = 0, time.time()

                dt = period - (time.time() - t0)
                if dt > 0:
                    self.msleep(int(dt * 1000))
        finally:
            src.release()
            self._release_ndi()
            self._running = False

    def _ensure_ndi(self, name, fps):
        if self._ndi is None:
            self._ndi = NdiSink(name=name, fps=int(fps))
        return self._ndi

    def _release_ndi(self):
        if self._ndi is not None:
            try:
                self._ndi.release()
            finally:
                self._ndi = None
