"""CameraManager: fuehrt pro Kamera eine eigene Engine (eigener Tracker, eigene
Kalibrierung, eigener NDI-Ausgang). Der Spielstand (Down & Distance, Strafen,
LOS/First-Down) ist GLOBAL und wird an alle Kameras verteilt – so zeigt jede
Kamera dieselbe First-Down-Linie aus ihrer eigenen Perspektive.

Signalfluss:  N Kameras rein -> je [Track -> Linien/Logos] -> je NDI-Feed an VMix.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from engine import EngineThread


def source_spec(cam):
    src = cam.get("source", {})
    if src.get("type") == "ndi":
        return "ndi://" + src.get("name", "")
    return src.get("path") or "device:0"


class CameraManager(QObject):
    # cam_id, program(ndarray), preview(ndarray)
    frames = Signal(str, object, object)
    # cam_id, status(dict)
    camStatus = Signal(str, dict)
    # cam_id, message
    camError = Signal(str, str)

    def __init__(self, config, assets_root, parent=None):
        super().__init__(parent)
        self.config = config
        self.assets_root = assets_root
        self.engines = {}   # cam_id -> EngineThread
        self.fps = 50.0
        self.loop = True
        for cam in config.get("cameras", []):
            self._make_engine(cam)

    def _make_engine(self, cam):
        cam_id = cam["id"]
        eng = EngineThread(self)
        eng.framesReady.connect(lambda p, v, cid=cam_id: self.frames.emit(cid, p, v))
        eng.status.connect(lambda st, cid=cam_id: self.camStatus.emit(cid, st))
        eng.error.connect(lambda m, cid=cam_id: self.camError.emit(cid, m))
        self.engines[cam_id] = eng
        self._configure_engine(cam)
        return eng

    def _configure_engine(self, cam):
        cam_id = cam["id"]
        eng = self.engines[cam_id]
        eng.configure(self.config, source_spec(cam), assets_root=self.assets_root,
                      fps=self.fps, loop=self.loop)
        eng.set_cfg(self.config)
        eng.set_tracking(cam.get("mode") == "tracked")
        cal = cam.get("calibration", {})
        if cal.get("imagePoints") and len(cal["imagePoints"]) >= 4:
            try:
                eng.set_calibration(cal["worldPoints"], cal["imagePoints"])
            except Exception:
                pass

    def ids(self):
        return list(self.engines.keys())

    def camera(self, cam_id):
        return next((c for c in self.config.get("cameras", []) if c["id"] == cam_id), None)

    # ---- Globaler Spielstand an ALLE Kameras ----
    def set_gamestate_preview(self, gs):
        for e in self.engines.values():
            e.set_preview_state(gs)

    def set_gamestate_program(self, gs):
        for e in self.engines.values():
            e.set_program_state(gs)

    def set_cfg(self, cfg):
        self.config = cfg
        for e in self.engines.values():
            e.set_cfg(cfg)

    def set_flags(self, show_graphics=None, show_scorebug=None):
        for e in self.engines.values():
            e.set_flags(show_graphics, show_scorebug)

    # ---- Pro Kamera ----
    def set_calibration(self, cam_id, world_points, image_points):
        self.engines[cam_id].set_calibration(world_points, image_points)

    def set_tracking(self, cam_id, enabled):
        self.engines[cam_id].set_tracking(enabled)

    def set_source(self, cam_id, spec):
        self.engines[cam_id].configure(self.config, spec, assets_root=self.assets_root,
                                       fps=self.fps, loop=self.loop)

    def set_ndi(self, cam_id, enabled, name=None):
        self.engines[cam_id].set_ndi(enabled, name)

    def set_ndi_all(self, enabled):
        for cid in self.ids():
            cam = self.camera(cid)
            name = cam.get("output", {}).get("name", f"LINE-{cid.upper()}")
            self.engines[cid].set_ndi(enabled, name)

    # ---- Start/Stop ----
    def start(self, cam_id, ndi_out=True):
        eng = self.engines[cam_id]
        if eng.isRunning():
            return
        cam = self.camera(cam_id)
        self._configure_engine(cam)
        if ndi_out:
            eng.set_ndi(True, cam.get("output", {}).get("name", f"LINE-{cam_id.upper()}"))
        eng.start()

    def stop(self, cam_id):
        eng = self.engines[cam_id]
        eng.stop(); eng.wait(1500)

    def start_all(self, ndi_out=True):
        for cid in self.ids():
            self.start(cid, ndi_out=ndi_out)

    def stop_all(self):
        for cid in self.ids():
            self.stop(cid)

    def is_running(self, cam_id):
        return self.engines[cam_id].isRunning()

    def any_running(self):
        return any(e.isRunning() for e in self.engines.values())
