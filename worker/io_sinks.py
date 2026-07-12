"""Ausgaenge: Fenster (Test), Datei, NDI-Sender (neuer Feed 'LINE-CAMx').

Der NDI-Sender ist bewusst ein NEUER Feed und laesst bestehende NDI-Quellen
unberuehrt.
"""
from __future__ import annotations

import cv2


class VideoSink:
    def write(self, frame_bgr):
        raise NotImplementedError

    def release(self):
        pass


class WindowSink(VideoSink):
    def __init__(self, title="LINE"):
        self.title = title

    def write(self, frame_bgr):
        cv2.imshow(self.title, frame_bgr)
        # 1ms warten; ESC bricht ab.
        return cv2.waitKey(1) & 0xFF != 27

    def release(self):
        cv2.destroyAllWindows()


class FileSink(VideoSink):
    def __init__(self, path, fps=50.0):
        self.path = path
        self.fps = fps
        self.writer = None

    def write(self, frame_bgr):
        if self.writer is None:
            h, w = frame_bgr.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(self.path, fourcc, self.fps, (w, h))
        self.writer.write(frame_bgr)
        return True

    def release(self):
        if self.writer is not None:
            self.writer.release()


class NdiSink(VideoSink):
    """NDI-Ausgang via cyndilib (optional)."""

    def __init__(self, name="LINE-CAM1", fps=50):
        try:
            from cyndilib.sender import Sender
            from cyndilib.video_frame import VideoSendFrame
            from cyndilib.wrapper.ndi_structs import FourCC
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("NDI benoetigt 'cyndilib' (pip install cyndilib)") from e

        self._FourCC = FourCC
        self.sender = Sender(name)
        self.frame = VideoSendFrame()
        self.frame.set_frame_rate((fps, 1))
        self.sender.set_video_frame(self.frame)
        self._configured = False
        self.sender.open()

    def write(self, frame_bgr):
        import numpy as np
        h, w = frame_bgr.shape[:2]
        if not self._configured:
            self.frame.set_resolution(w, h)
            self.frame.set_fourcc(self._FourCC.BGRA)
            self._configured = True
        bgra = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2BGRA)
        self.sender.write_video(np.ascontiguousarray(bgra))
        return True

    def release(self):
        try:
            self.sender.close()
        except Exception:
            pass


def open_sink(kind, name="LINE-CAM1", fps=50.0, out_path="out/line.mp4"):
    if kind == "ndi":
        return NdiSink(name=name, fps=int(fps))
    if kind == "file":
        return FileSink(out_path, fps=fps)
    return WindowSink(title=name)
