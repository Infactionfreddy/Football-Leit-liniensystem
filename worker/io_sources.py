"""Eingangsquellen: Video-Datei, Webcam/Capture-Device, NDI.

Datei/Device laufen ueber OpenCV (immer verfuegbar). NDI ist optional (cyndilib).
Eine DeckLink-Karte erscheint unter vielen Systemen als normales Video-Device und
ist dann via ``device:<index>`` direkt nutzbar; andernfalls per Blackmagic-Tools
als NDI ausgeben und ``ndi://<name>`` verwenden.
"""
from __future__ import annotations

import cv2


class VideoSource:
    def read(self):
        """-> (ok: bool, frame_bgr)"""
        raise NotImplementedError

    def release(self):
        pass


class CvSource(VideoSource):
    """Video-Datei oder Capture-Device via OpenCV."""

    def __init__(self, spec, loop=False):
        if spec.startswith("device:"):
            self.cap = cv2.VideoCapture(int(spec.split(":", 1)[1]))
            self.loop = False
        else:
            self.cap = cv2.VideoCapture(spec)
            self.loop = loop  # Datei optional in Schleife (fake Live-Feed)
        if not self.cap.isOpened():
            raise RuntimeError(f"Quelle nicht zu oeffnen: {spec}")

    def read(self):
        ok, frame = self.cap.read()
        if not ok and self.loop:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        return ok, frame

    def release(self):
        self.cap.release()


class NdiSource(VideoSource):
    """NDI-Eingang via cyndilib (optional)."""

    def __init__(self, source_name):
        try:
            from cyndilib.finder import Finder
            from cyndilib.receiver import Receiver
            from cyndilib.video_frame import VideoFrameSync
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("NDI benoetigt 'cyndilib' (pip install cyndilib)") from e

        self.finder = Finder()
        self.finder.open()
        self.finder.wait_for_sources(5)
        src = None
        for s in self.finder.get_source_names():
            if source_name.lower() in s.lower():
                src = self.finder.get_source(s)
                break
        if src is None:
            raise RuntimeError(f"NDI-Quelle nicht gefunden: {source_name}")

        self.receiver = Receiver()
        self.video = VideoFrameSync()
        self.receiver.frame_sync.set_video_frame(self.video)
        self.receiver.set_source(src)

    def read(self):
        import numpy as np
        self.receiver.frame_sync.capture_video()
        data = self.video.get_array()
        if data is None or data.size == 0:
            return False, None
        h, w = self.video.get_resolution()
        frame = data.reshape(h, w, 4)  # NDI liefert BGRA
        return True, frame[:, :, :3].copy()


def open_source(spec, loop=False):
    """spec-Beispiele: 'recordings/cam1.mp4', 'device:0', 'ndi://KAMERA (Cam 1)'."""
    if spec.startswith("ndi://"):
        return NdiSource(spec[len("ndi://"):])
    return CvSource(spec, loop=loop)


def list_ndi_sources(timeout=3.0):
    """Verfuegbare NDI-Quellen im Netz auflisten (fuer die Kamera-Auswahl).

    Rueckgabe: Liste von Quell-Namen (Strings). Leer, wenn cyndilib fehlt oder
    keine Quelle gefunden wird.
    """
    try:
        from cyndilib.finder import Finder
    except ImportError:
        return []
    try:
        finder = Finder()
        finder.open()
        finder.wait_for_sources(timeout)
        names = list(finder.get_source_names())
        finder.close()
        return names
    except Exception:
        return []
