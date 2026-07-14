#!/usr/bin/env python3
"""Football Leit-Liniensystem – Desktop-Control (Windows/Linux).

Multi-Kamera: jede Kamera laeuft als eigene Pipeline (eigener Tracker, eigene
Kalibrierung, eigener NDI-Ausgang an VMix). Der Spielstand (Down & Distance,
Strafen, LOS/First-Down) ist global und speist alle Kameras. VMix schaltet die
fertigen Feeds LINE-CAMx um.

Layout (VMix-artig): Kopfleiste · fokussierte Kamera als PREVIEW|PROGRAM ·
Multiview aller Kameras · Funktions-Bar · Control-Tabs.
"""
from __future__ import annotations

import os
import sys
import json
import copy

import numpy as np
from PySide6.QtCore import Qt, Signal, QTimer, QTime
from PySide6.QtGui import QImage, QPixmap, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QTabWidget, QGroupBox, QTableWidget, QTableWidgetItem, QFileDialog,
    QHeaderView, QSizePolicy, QFrame, QFormLayout,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "worker"))

from manager import CameraManager, source_spec  # noqa: E402
from theme import QSS                            # noqa: E402
from io_sources import list_ndi_sources          # noqa: E402

CONFIG_DIR = os.path.join(ROOT, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
EXAMPLE_PATH = os.path.join(CONFIG_DIR, "example.config.json")
GAMESTATE_PATH = os.path.join(CONFIG_DIR, "gamestate.json")

PENALTIES = [
    "Halten (Holding), 10 Yards",
    "Falscher Start (False Start), 5 Yards",
    "Abseits (Offside), 5 Yards",
    "Pass Interference, Spot Foul",
    "Facemask, 15 Yards",
    "Persoenliches Foul (Personal Foul), 15 Yards",
]


def load_json(path, fallback=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return copy.deepcopy(fallback) if fallback is not None else None


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def bgr_to_qimage(frame):
    h, w = frame.shape[:2]
    rgb = np.ascontiguousarray(frame[:, :, ::-1])
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def field_label(text):
    lbl = QLabel(text.upper()); lbl.setObjectName("FieldLabel"); return lbl


class VideoPane(QLabel):
    """Videoflaeche; Klick liefert Bildkoordinaten (Kalibrierung)."""
    clicked = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setObjectName("MonPane")
        self.setMinimumSize(320, 180)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._img_w = self._img_h = 0

    def set_frame(self, frame):
        self._img_h, self._img_w = frame.shape[:2]
        pix = QPixmap.fromImage(bgr_to_qimage(frame))
        self.setPixmap(pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _disp_geometry(self):
        if not self._img_w:
            return None
        lw, lh = self.width(), self.height()
        s = min(lw / self._img_w, lh / self._img_h)
        return (lw - self._img_w * s) / 2, (lh - self._img_h * s) / 2, s

    def mousePressEvent(self, ev):
        g = self._disp_geometry()
        if g:
            ox, oy, s = g
            ix, iy = (ev.position().x() - ox) / s, (ev.position().y() - oy) / s
            if 0 <= ix <= self._img_w and 0 <= iy <= self._img_h:
                self.clicked.emit(ix, iy)


class Monitor(QFrame):
    def __init__(self, title, kind):
        super().__init__()
        self.setObjectName("Monitor")
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        header = QWidget(); header.setObjectName(f"MonHeader{kind}")
        hl = QHBoxLayout(header); hl.setContentsMargins(10, 0, 10, 0)
        self.title_lbl = QLabel(title.upper())
        f = self.title_lbl.font(); f.setPointSize(f.pointSize() + 1); f.setBold(True); self.title_lbl.setFont(f)
        self.sub = QLabel(""); self.sub.setObjectName("MonSub")
        hl.addWidget(self.title_lbl); hl.addStretch(); hl.addWidget(self.sub)
        header.setFixedHeight(28)
        self.pane = VideoPane()
        tally = QFrame(); tally.setObjectName(f"Tally{kind}"); tally.setFixedHeight(4)
        v.addWidget(header); v.addWidget(self.pane, 1); v.addWidget(tally)

    def set_frame(self, frame): self.pane.set_frame(frame)
    def set_sub(self, text): self.sub.setText(text)
    def set_title(self, text): self.title_lbl.setText(text.upper())


class MultiviewTile(QFrame):
    """Kleines Monitor-Kachel je Kamera in der Multiview."""
    clicked = Signal(str)

    def __init__(self, cam_id, name, ndi_name):
        super().__init__()
        self.cam_id = cam_id
        self.setObjectName("MviewTile")
        self.setMinimumSize(240, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(0)
        head = QWidget()
        hl = QHBoxLayout(head); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)
        self.name_lbl = QLabel(name); self.name_lbl.setObjectName("MviewHead")
        self.dot = QLabel("●"); self.dot.setStyleSheet("color:#5c6472; padding:0 6px;")
        hl.addWidget(self.name_lbl); hl.addStretch(); hl.addWidget(self.dot)
        self.pane = QLabel(); self.pane.setObjectName("MviewPane"); self.pane.setAlignment(Qt.AlignCenter)
        self.pane.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ndi_lbl = QLabel(f"NDI: {ndi_name}"); self.ndi_lbl.setObjectName("MviewNdi")
        v.addWidget(head); v.addWidget(self.pane, 1); v.addWidget(self.ndi_lbl)
        self.set_focused(False)

    def set_frame(self, frame):
        pix = QPixmap.fromImage(bgr_to_qimage(frame))
        self.pane.setPixmap(pix.scaled(self.pane.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_status(self, st):
        tr = st.get("track") or ""
        col = "#ff4a47" if "lost" in tr else ("#2ecc5a" if "TRACK" in tr else "#8b93a1")
        self.dot.setStyleSheet(f"color:{col}; padding:0 6px;")

    def set_focused(self, on):
        col = "#2f80ed" if on else "#31363f"
        self.setStyleSheet(f"#MviewTile {{ border:2px solid {col}; border-radius:4px; background:#1b1e24; }}")

    def mousePressEvent(self, ev):
        self.clicked.emit(self.cam_id)


class MultiviewWindow(QWidget):
    """Eigenes Fenster (Monitor 2): Kamera-Wand aller Feeds als Grid."""
    tileClicked = Signal(str)

    def __init__(self, cameras):
        super().__init__()
        self.setWindowTitle("Kameras – Multiview")
        v = QVBoxLayout(self); v.setContentsMargins(8, 8, 8, 8); v.setSpacing(8)
        head = QLabel("MULTIVIEW · KAMERAS   (F11 = Vollbild, Esc = Fenster)")
        head.setObjectName("XLabel")
        v.addWidget(head)
        grid = QGridLayout(); grid.setSpacing(8)
        self.tiles = {}
        n = max(1, len(cameras))
        cols = int(n ** 0.5)
        if cols * cols < n:
            cols += 1
        for i, cam in enumerate(cameras):
            ndi = cam.get("output", {}).get("name", f"LINE-{cam['id'].upper()}")
            tile = MultiviewTile(cam["id"], cam.get("name", cam["id"]), ndi)
            tile.clicked.connect(self.tileClicked)
            grid.addWidget(tile, i // cols, i % cols)
            self.tiles[cam["id"]] = tile
        v.addLayout(grid, 1)

    def set_frame(self, cam_id, frame):
        t = self.tiles.get(cam_id)
        if t:
            t.set_frame(frame)

    def set_status(self, cam_id, st):
        t = self.tiles.get(cam_id)
        if t:
            t.set_status(st)

    def set_focused(self, cam_id):
        for cid, t in self.tiles.items():
            t.set_focused(cid == cam_id)

    def place_on(self, screen, fullscreen=True):
        if screen is not None:
            self.setGeometry(screen.geometry())
        if fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
        self.raise_(); self.activateWindow()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif ev.key() == Qt.Key_Escape:
            self.showNormal()


class FullscreenOutput(QWidget):
    def __init__(self, screen=None):
        super().__init__()
        self.setWindowTitle("PROGRAM – Vollbild")
        self.setStyleSheet("background:#000;")
        self.label = QLabel(self); self.label.setAlignment(Qt.AlignCenter)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.label)
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()

    def set_frame(self, frame):
        pix = QPixmap.fromImage(bgr_to_qimage(frame))
        self.label.setPixmap(pix.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Escape, Qt.Key_F11):
            self.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Football Leit-Liniensystem – Control")
        self.resize(1440, 940)

        self.config = load_json(CONFIG_PATH) or load_json(EXAMPLE_PATH, {})
        cams = self.config.get("cameras") or [{"id": "cam1", "name": "Cam 1"}]
        self.focus_cam = cams[0]["id"]
        self.camera = cams[0]
        gs_default = self.config.get("gameState", {
            "possession": "home", "down": 1, "distance": 10, "goalToGo": False,
            "losYard": 45.0, "firstDownYard": 55.0, "quarter": 1, "clock": "15:00",
            "penalty": {"active": False, "text": "", "team": "home"},
        })
        self.program_gs = load_json(GAMESTATE_PATH, gs_default)
        self.preview_gs = copy.deepcopy(self.program_gs)
        self._calib_capture = False
        self._loading = False
        self._fs = None

        self.manager = CameraManager(self.config, ROOT, self)
        self.manager.frames.connect(self._on_frames)
        self.manager.camStatus.connect(self._on_status)
        self.manager.camError.connect(lambda cid, m: self.statusBar().showMessage(f"[{cid}] {m}", 6000))

        self.tiles = {}
        self._build_ui()

        # Zweites Fenster: Kamera-Multiview (Monitor 2)
        self.mview = MultiviewWindow(self.config.get("cameras", []))
        self.mview.tileClicked.connect(self._set_focus)
        self.tiles = self.mview.tiles
        self._set_focus(self.focus_cam)
        self._place_mview_initial()

        self._install_shortcuts()
        self.manager.set_gamestate_preview(self.preview_gs)
        self.manager.set_gamestate_program(self.program_gs)
        self._refresh_subs()

    def _place_mview_initial(self):
        screens = QApplication.screens()
        cur = self.screen()
        others = [s for s in screens if s is not cur] or screens
        if len(screens) > 1:
            self.mview.place_on(others[0], fullscreen=True)  # Kameras auf Monitor 2
        else:
            self.mview.resize(960, 620); self.mview.show()   # ein Monitor: eigenes Fenster

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(10, 8, 10, 8); root.setSpacing(8)
        root.addWidget(self._build_topbar())
        root.addWidget(self._build_monitors(), 4)
        root.addWidget(self._build_funcbar())
        root.addWidget(self._build_tabs(), 3)
        self.statusBar().showMessage("Bereit · Kameras in 'Quelle / Ausgang' pruefen, dann 'Start Alle'.")

    def _build_topbar(self):
        bar = QFrame(); bar.setObjectName("TopBar"); bar.setFixedHeight(46)
        h = QHBoxLayout(bar); h.setContentsMargins(12, 0, 12, 0)
        title = QLabel("FOOTBALL LEIT-LINIENSYSTEM  ·  CONTROL"); title.setObjectName("AppTitle")
        self.led = QLabel(); self.led.setFixedSize(11, 11); self._set_led(False)
        self.startBtn2 = QPushButton("▶  Start Alle"); self.startBtn2.setObjectName("Primary")
        self.startBtn2.clicked.connect(self.start_all)
        self.stopBtn2 = QPushButton("■  Stop Alle"); self.stopBtn2.setObjectName("Danger")
        self.stopBtn2.clicked.connect(self.stop_all)
        self.clock_lbl = QLabel("00:00:00"); self.clock_lbl.setObjectName("Clock")
        self.screenSel = QComboBox()
        for i in range(max(1, len(QApplication.screens()))):
            self.screenSel.addItem(f"Monitor {i + 1}")
        if len(QApplication.screens()) > 1:
            self.screenSel.setCurrentIndex(1)
        self.camWinBtn = QPushButton("🖵  Kameras anzeigen"); self.camWinBtn.clicked.connect(self._show_cameras)
        h.addWidget(title)
        h.addSpacing(14); h.addWidget(self.led); h.addWidget(QLabel("Engine"))
        h.addStretch()
        h.addWidget(self.camWinBtn); h.addWidget(self.screenSel)
        h.addSpacing(10); h.addWidget(self.startBtn2); h.addWidget(self.stopBtn2)
        h.addSpacing(14); h.addWidget(self.clock_lbl)
        t = QTimer(self); t.timeout.connect(lambda: self.clock_lbl.setText(QTime.currentTime().toString("HH:mm:ss"))); t.start(1000)
        return bar

    def _build_monitors(self):
        wrap = QWidget(); h = QHBoxLayout(wrap); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        self.preview_mon = Monitor("Preview", "Preview")
        self.program_mon = Monitor("Program", "Program")
        self.preview_mon.pane.clicked.connect(self._on_pane_click)
        h.addWidget(self.preview_mon, 5)
        h.addWidget(self._build_xbar(), 0)
        h.addWidget(self.program_mon, 5)
        return wrap

    def _build_xbar(self):
        bar = QFrame(); bar.setObjectName("XBar"); bar.setFixedWidth(150)
        v = QVBoxLayout(bar); v.setContentsMargins(12, 12, 12, 12); v.setSpacing(10)
        cap = QLabel("PVW → PGM"); cap.setObjectName("XLabel"); cap.setAlignment(Qt.AlignCenter)
        self.take_btn = QPushButton("TAKE"); self.take_btn.setObjectName("TakeBtn")
        self.take_btn.setToolTip("Spielstand auf alle Kameras schalten (Enter/Leertaste)")
        self.take_btn.clicked.connect(self.take)
        cut = QPushButton("CUT (sofort)"); cut.setObjectName("CutBtn"); cut.clicked.connect(self.take)
        self.fps_pill = QLabel("–  fps"); self.fps_pill.setObjectName("FpsPill"); self.fps_pill.setAlignment(Qt.AlignCenter)
        v.addStretch(); v.addWidget(cap); v.addWidget(self.take_btn); v.addWidget(cut)
        v.addSpacing(6); v.addWidget(self.fps_pill); v.addStretch()
        return bar

    def _build_funcbar(self):
        bar = QFrame(); bar.setObjectName("FuncBar"); bar.setFixedHeight(52)
        h = QHBoxLayout(bar); h.setContentsMargins(12, 0, 12, 0); h.setSpacing(8)
        b_new = QPushButton("Neue Serie  (1st && 10)"); b_new.clicked.connect(self._new_series)
        b_down = QPushButton("Naechster Down  ▸"); b_down.clicked.connect(self._next_down)
        self.flag_btn = QPushButton("⚑  Flag"); self.flag_btn.setObjectName("FlagBtn"); self.flag_btn.setCheckable(True)
        self.flag_btn.toggled.connect(self._toggle_flag_from_bar)
        self.gfx_btn = QPushButton("Logos"); self.gfx_btn.setCheckable(True); self.gfx_btn.setChecked(True)
        self.gfx_btn.toggled.connect(self._flags_from_bar)
        self.bug_btn = QPushButton("Scorebug"); self.bug_btn.setCheckable(True); self.bug_btn.setChecked(True)
        self.bug_btn.toggled.connect(self._flags_from_bar)
        b_fs = QPushButton("⛶  PGM Vollbild"); b_fs.clicked.connect(self.toggle_fullscreen)
        h.addWidget(b_new); h.addWidget(b_down); h.addSpacing(10); h.addWidget(self.flag_btn)
        h.addStretch(); h.addWidget(self.gfx_btn); h.addWidget(self.bug_btn); h.addSpacing(10); h.addWidget(b_fs)
        return bar

    def _build_tabs(self):
        tabs = QTabWidget()
        tabs.addTab(self._tab_game(), "SPIEL")
        tabs.addTab(self._tab_penalty(), "STRAFEN")
        tabs.addTab(self._tab_logos(), "LOGOS")
        tabs.addTab(self._tab_source(), "QUELLE / AUSGANG")
        tabs.addTab(self._tab_calib(), "KALIBRIERUNG")
        return tabs

    # ---------------- Tabs ----------------
    def _tab_game(self):
        w = QWidget(); outer = QHBoxLayout(w); outer.setSpacing(12)
        box_dd = QGroupBox("DOWN && DISTANCE"); g = QGridLayout(box_dd); g.setVerticalSpacing(8)
        self.possession = QComboBox(); self.possession.addItems(["home", "away"])
        self.down = QComboBox(); self.down.addItems(["1", "2", "3", "4"])
        self.distance = QSpinBox(); self.distance.setRange(0, 99)
        self.goalToGo = QCheckBox("Goal to Go")
        g.addWidget(field_label("Ballbesitz"), 0, 0); g.addWidget(self.possession, 1, 0)
        g.addWidget(field_label("Down"), 0, 1); g.addWidget(self.down, 1, 1)
        g.addWidget(field_label("Distance"), 0, 2); g.addWidget(self.distance, 1, 2)
        g.addWidget(self.goalToGo, 1, 3)
        g.addWidget(field_label("Preview"), 2, 0)
        self.dd_lbl = QLabel(); self.dd_lbl.setObjectName("DDPreview")
        g.addWidget(self.dd_lbl, 3, 0, 1, 4); g.setRowStretch(4, 1)

        box_line = QGroupBox("LINIEN (YARD) – global fuer alle Kameras"); f2 = QFormLayout(box_line); f2.setVerticalSpacing(8)
        self.losYard = QDoubleSpinBox(); self.losYard.setRange(0, 120); self.losYard.setSingleStep(0.5)
        self.firstDownYard = QDoubleSpinBox(); self.firstDownYard.setRange(0, 120); self.firstDownYard.setSingleStep(0.5)
        self.quarter = QSpinBox(); self.quarter.setRange(1, 5)
        self.clock = QLineEdit()
        f2.addRow(field_label("Line of Scrimmage (blau)"), self.losYard)
        f2.addRow(field_label("First-Down (gelb)"), self.firstDownYard)
        f2.addRow(field_label("Quarter"), self.quarter)
        f2.addRow(field_label("Clock"), self.clock)
        outer.addWidget(box_dd, 3); outer.addWidget(box_line, 2)

        for wdg in (self.possession, self.down):
            wdg.currentIndexChanged.connect(self._collect_preview)
        for wdg in (self.distance, self.quarter):
            wdg.valueChanged.connect(self._collect_preview)
        for wdg in (self.losYard, self.firstDownYard):
            wdg.valueChanged.connect(self._collect_preview)
        self.goalToGo.stateChanged.connect(self._collect_preview)
        self.clock.textChanged.connect(self._collect_preview)
        self._load_game_widgets(self.preview_gs)
        return w

    def _tab_penalty(self):
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        box = QGroupBox("STRAFE"); g = QGridLayout(box); g.setVerticalSpacing(8)
        self.penActive = QCheckBox("Strafe aktiv (Flag)")
        self.penTeam = QComboBox(); self.penTeam.addItems(["home", "away"])
        self.penText = QLineEdit(); self.penText.setPlaceholderText("z. B. Halten #75, 10 Yards")
        g.addWidget(self.penActive, 0, 0); g.addWidget(field_label("Team"), 0, 1); g.addWidget(self.penTeam, 0, 2)
        g.addWidget(field_label("Text"), 1, 0); g.addWidget(self.penText, 1, 1, 1, 3)
        box_q = QGroupBox("SCHNELLAUSWAHL"); quick = QGridLayout(box_q); quick.setSpacing(6)
        for i, p in enumerate(PENALTIES):
            b = QPushButton(p)
            b.clicked.connect(lambda _=False, t=p: (self.penText.setText(t), self.penActive.setChecked(True)))
            quick.addWidget(b, i // 3, i % 3)
        v.addWidget(box); v.addWidget(box_q); v.addStretch()
        self.penActive.stateChanged.connect(self._collect_preview)
        self.penTeam.currentIndexChanged.connect(self._collect_preview)
        self.penText.textChanged.connect(self._collect_preview)
        pen = self.preview_gs.get("penalty", {})
        self.penActive.setChecked(bool(pen.get("active")))
        self.penTeam.setCurrentText(pen.get("team", "home"))
        self.penText.setText(pen.get("text", ""))
        return w

    def _tab_logos(self):
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        box = QGroupBox("TEAM-LOGOS AUF DEM RASEN"); bv = QVBoxLayout(box)
        self.logo_table = QTableWidget(0, 6)
        self.logo_table.setHorizontalHeaderLabels(["ID", "an", "X (Yard)", "Y (Yard)", "Groesse", "Rot°"])
        self.logo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.logo_table.verticalHeader().setVisible(False)
        bv.addWidget(self.logo_table)
        hint = QLabel("Logos in assets/ (PNG mit Alpha). Aenderungen wirken sofort auf alle Kameras.")
        hint.setObjectName("SectionHint"); bv.addWidget(hint)
        v.addWidget(box)
        self._load_logo_table()
        self.logo_table.cellChanged.connect(self._logo_changed)
        return w

    def _tab_source(self):
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        box_cam = QGroupBox("FOKUSSIERTE KAMERA (fuer Quelle/Kalibrierung)"); cg = QGridLayout(box_cam); cg.setVerticalSpacing(8)
        self.cameraSel = QComboBox()
        for cam in self.config.get("cameras", []):
            self.cameraSel.addItem(f"{cam.get('name', cam['id'])}  ·  {cam['id']}", cam["id"])
        self.cameraSel.currentIndexChanged.connect(lambda: self._set_focus(self.cameraSel.currentData()))
        self.trackChk = QCheckBox("Kamera-Tracking (frei geführt)")
        self.trackChk.stateChanged.connect(lambda: self.manager.set_tracking(self.focus_cam, self.trackChk.isChecked()))
        cg.addWidget(field_label("Fokus"), 0, 0); cg.addWidget(self.cameraSel, 1, 0, 1, 2)
        cg.addWidget(self.trackChk, 1, 2)

        box = QGroupBox("QUELLE (fokussierte Kamera)"); g = QGridLayout(box); g.setVerticalSpacing(8)
        self.sourceEdit = QLineEdit(source_spec(self.camera))
        browse = QPushButton("Datei…"); browse.clicked.connect(self._browse_source)
        applysrc = QPushButton("Quelle übernehmen"); applysrc.clicked.connect(self._apply_source)
        self.loopChk = QCheckBox("Datei loopen"); self.loopChk.setChecked(True)
        self.fpsSpin = QDoubleSpinBox(); self.fpsSpin.setRange(1, 120); self.fpsSpin.setValue(50)
        g.addWidget(field_label("Quelle (Datei / device:0 / ndi://Name)"), 0, 0, 1, 3)
        g.addWidget(self.sourceEdit, 1, 0, 1, 2); g.addWidget(browse, 1, 2)
        g.addWidget(self.loopChk, 2, 0); g.addWidget(field_label("FPS"), 2, 1); g.addWidget(self.fpsSpin, 2, 2)
        self.ndiSrcSel = QComboBox(); self.ndiSrcSel.setMinimumWidth(220)
        disc = QPushButton("NDI-Quellen suchen"); disc.clicked.connect(self._discover_ndi)
        use = QPushButton("→ übernehmen"); use.clicked.connect(self._use_ndi_source)
        g.addWidget(field_label("NDI-Quellen im Netz"), 3, 0, 1, 3)
        g.addWidget(self.ndiSrcSel, 4, 0); g.addWidget(disc, 4, 1); g.addWidget(use, 4, 2)
        g.addWidget(applysrc, 5, 0, 1, 3)

        box_out = QGroupBox("PROGRAMM-AUSGABE AN VMIX – je Kamera ein NDI-Feed")
        og = QGridLayout(box_out); og.setVerticalSpacing(8)
        self.ndiChk = QCheckBox("NDI-Ausgänge aktiv (alle Kameras)"); self.ndiChk.setChecked(True)
        self.ndiChk.stateChanged.connect(lambda: self.manager.set_ndi_all(self.ndiChk.isChecked()))
        og.addWidget(self.ndiChk, 0, 0, 1, 3)
        feeds = ", ".join(c.get("output", {}).get("name", f"LINE-{c['id'].upper()}") for c in self.config.get("cameras", []))
        lab = QLabel(f"Feeds: {feeds}\nIn VMix jeden Sender als Input hinzufügen. SDI-Ausgang folgt über DeckLink/AJA.")
        lab.setObjectName("SectionHint"); og.addWidget(lab, 1, 0, 1, 3)

        v.addWidget(box_cam); v.addWidget(box); v.addWidget(box_out); v.addStretch()
        return w

    def _tab_calib(self):
        w = QWidget(); v = QVBoxLayout(w); v.setSpacing(10)
        self.calib_box = QGroupBox("REFERENZPUNKTE (fokussierte Kamera)"); bv = QVBoxLayout(self.calib_box)
        info = QLabel("'Aus Klick erfassen' aktivieren, in den PREVIEW-Monitor der fokussierten Kamera klicken, "
                      "Welt-Yards (X entlang Feldlaenge, Y ueber Breite) eintragen, dann berechnen.")
        info.setObjectName("SectionHint"); info.setWordWrap(True); bv.addWidget(info)
        row = QHBoxLayout()
        self.captureChk = QCheckBox("Aus Klick erfassen")
        self.captureChk.stateChanged.connect(lambda: setattr(self, "_calib_capture", self.captureChk.isChecked()))
        add = QPushButton("Zeile +"); add.clicked.connect(lambda: self._add_calib_row())
        rem = QPushButton("Zeile −")
        rem.clicked.connect(lambda: self.calib_table.removeRow(self.calib_table.rowCount() - 1) if self.calib_table.rowCount() else None)
        row.addWidget(self.captureChk); row.addWidget(add); row.addWidget(rem); row.addStretch()
        bv.addLayout(row)
        self.calib_table = QTableWidget(0, 4)
        self.calib_table.setHorizontalHeaderLabels(["Bild x", "Bild y", "Welt X (Yard)", "Welt Y (Yard)"])
        self.calib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.calib_table.verticalHeader().setVisible(False)
        bv.addWidget(self.calib_table)
        calc = QPushButton("Homographie berechnen & speichern"); calc.setObjectName("Primary")
        calc.clicked.connect(self._compute_calib); bv.addWidget(calc)
        v.addWidget(self.calib_box)
        self._load_calib_table()
        return w

    # ---------------- Fokus / Kamera ----------------
    def _set_focus(self, cam_id):
        if cam_id not in self.tiles:
            return
        self.focus_cam = cam_id
        self.camera = self.manager.camera(cam_id)
        for cid, tile in self.tiles.items():
            tile.set_focused(cid == cam_id)
        # Per-Kamera-Widgets nachziehen
        if hasattr(self, "cameraSel"):
            i = self.cameraSel.findData(cam_id)
            if i >= 0 and self.cameraSel.currentIndex() != i:
                self.cameraSel.blockSignals(True); self.cameraSel.setCurrentIndex(i); self.cameraSel.blockSignals(False)
            self.sourceEdit.setText(source_spec(self.camera))
            self.trackChk.blockSignals(True)
            self.trackChk.setChecked(self.camera.get("mode") == "tracked")
            self.trackChk.blockSignals(False)
        self.program_mon.set_title(f"Program · {self.camera.get('name', cam_id)}")
        self.preview_mon.set_title(f"Preview · {self.camera.get('name', cam_id)}")
        self._load_calib_table()
        self.statusBar().showMessage(f"Fokus: {self.camera.get('name', cam_id)}", 2500)

    # ---------------- Spielstand (global) ----------------
    def _load_game_widgets(self, gs):
        gs = copy.deepcopy(gs); self._loading = True
        self.possession.setCurrentText(gs.get("possession", "home"))
        self.down.setCurrentText(str(gs.get("down", 1)))
        self.distance.setValue(int(gs.get("distance", 10)))
        self.goalToGo.setChecked(bool(gs.get("goalToGo")))
        self.losYard.setValue(float(gs.get("losYard", 45)))
        self.firstDownYard.setValue(float(gs.get("firstDownYard", 55)))
        self.quarter.setValue(int(gs.get("quarter", 1)))
        self.clock.setText(str(gs.get("clock", "15:00")))
        self._loading = False; self._collect_preview()

    def _collect_preview(self):
        if self._loading:
            return
        self.preview_gs.update({
            "possession": self.possession.currentText(), "down": int(self.down.currentText()),
            "distance": self.distance.value(), "goalToGo": self.goalToGo.isChecked(),
            "losYard": self.losYard.value(), "firstDownYard": self.firstDownYard.value(),
            "quarter": self.quarter.value(), "clock": self.clock.text(),
        })
        if hasattr(self, "penActive"):
            self.preview_gs["penalty"] = {"active": self.penActive.isChecked(),
                                          "team": self.penTeam.currentText(), "text": self.penText.text()}
            if hasattr(self, "flag_btn") and self.flag_btn.isChecked() != self.penActive.isChecked():
                self.flag_btn.blockSignals(True); self.flag_btn.setChecked(self.penActive.isChecked()); self.flag_btn.blockSignals(False)
        self.manager.set_gamestate_preview(self.preview_gs)
        self._update_dd(); self._refresh_subs()

    def _update_dd(self):
        self.dd_lbl.setText(self._dd_of(self.preview_gs))

    def _dd_of(self, gs):
        ordm = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
        d = ordm.get(gs.get("down"), f"{gs.get('down')}th")
        return f"{d} & Goal" if gs.get("goalToGo") else f"{d} & {gs.get('distance')}"

    def _refresh_subs(self):
        self.preview_mon.set_sub(self._dd_of(self.preview_gs))
        self.program_mon.set_sub(self._dd_of(self.program_gs))

    def take(self):
        self.program_gs = copy.deepcopy(self.preview_gs)
        save_json(GAMESTATE_PATH, self.program_gs)
        self.manager.set_gamestate_program(self.program_gs)
        self._refresh_subs()
        self.statusBar().showMessage("TAKE · Spielstand auf alle Kameras.", 2500)

    def _next_down(self):
        self.down.setCurrentText(str(min(4, int(self.down.currentText()) + 1)))

    def _new_series(self):
        self.losYard.setValue(self.firstDownYard.value())
        self.firstDownYard.setValue(self.firstDownYard.value() + 10)
        self.down.setCurrentText("1"); self.distance.setValue(10)

    def _toggle_flag_from_bar(self, on):
        if hasattr(self, "penActive"):
            self.penActive.setChecked(on)

    def _flags_from_bar(self):
        self.manager.set_flags(self.gfx_btn.isChecked(), self.bug_btn.isChecked())

    # ---- Logos ----
    def _load_logo_table(self):
        items = self.config.get("fieldGraphics", [])
        self.logo_table.blockSignals(True); self.logo_table.setRowCount(len(items))
        for r, it in enumerate(items):
            cy = it.get("centerYard", [60, 26.65])
            vals = [it.get("id", f"logo{r}"), None, cy[0], cy[1], it.get("widthYards", 12), it.get("rotationDeg", 0)]
            for c, val in enumerate(vals):
                if c == 1:
                    chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    chk.setCheckState(Qt.Checked if it.get("enabled", True) else Qt.Unchecked)
                    self.logo_table.setItem(r, c, chk)
                else:
                    self.logo_table.setItem(r, c, QTableWidgetItem(str(val)))
        self.logo_table.blockSignals(False)

    def _logo_changed(self, *_):
        items = self.config.setdefault("fieldGraphics", [])
        for r in range(self.logo_table.rowCount()):
            if r >= len(items):
                continue
            try:
                items[r]["enabled"] = self.logo_table.item(r, 1).checkState() == Qt.Checked
                items[r]["centerYard"] = [float(self.logo_table.item(r, 2).text()), float(self.logo_table.item(r, 3).text())]
                sz = float(self.logo_table.item(r, 4).text())
                items[r]["widthYards"] = sz; items[r]["heightYards"] = sz
                items[r]["rotationDeg"] = float(self.logo_table.item(r, 5).text())
            except (ValueError, AttributeError):
                pass
        save_json(CONFIG_PATH, self.config)
        self.manager.set_cfg(self.config)

    # ---- Quelle ----
    def _browse_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Video waehlen", ROOT, "Video (*.mp4 *.mov *.mkv);;Alle (*)")
        if path:
            self.sourceEdit.setText(path)

    def _apply_source(self):
        spec = self.sourceEdit.text().strip()
        self.camera.setdefault("source", {})
        if spec.startswith("ndi://"):
            self.camera["source"] = {"type": "ndi", "name": spec[len("ndi://"):]}
        elif spec.startswith("device:"):
            self.camera["source"] = {"type": "device", "path": spec}
        else:
            self.camera["source"] = {"type": "file", "path": spec}
        save_json(CONFIG_PATH, self.config)
        was = self.manager.is_running(self.focus_cam)
        if was:
            self.manager.stop(self.focus_cam)
        self.manager.set_source(self.focus_cam, spec)
        if was:
            self.manager.start(self.focus_cam, ndi_out=self.ndiChk.isChecked())
        self.statusBar().showMessage(f"Quelle übernommen: {spec}", 3000)

    def _discover_ndi(self):
        self.statusBar().showMessage("Suche NDI-Quellen …"); QApplication.processEvents()
        names = list_ndi_sources(); self.ndiSrcSel.clear()
        if names:
            self.ndiSrcSel.addItems(names)
            self.statusBar().showMessage(f"{len(names)} NDI-Quelle(n) gefunden.", 4000)
        else:
            self.statusBar().showMessage("Keine NDI-Quellen (cyndilib installiert? NDI-Runtime aktiv?).", 6000)

    def _use_ndi_source(self):
        name = self.ndiSrcSel.currentText().strip()
        if name:
            self.sourceEdit.setText("ndi://" + name)

    # ---- Kalibrierung (fokussierte Kamera) ----
    def _load_calib_table(self):
        cal = self.camera.get("calibration", {})
        ip, wp = cal.get("imagePoints", []), cal.get("worldPoints", [])
        self.calib_table.setRowCount(len(ip))
        for r in range(len(ip)):
            for c, val in enumerate([ip[r][0], ip[r][1], wp[r][0] if r < len(wp) else 0, wp[r][1] if r < len(wp) else 0]):
                self.calib_table.setItem(r, c, QTableWidgetItem(str(val)))

    def _add_calib_row(self, ix=0.0, iy=0.0):
        r = self.calib_table.rowCount(); self.calib_table.insertRow(r)
        for c, val in enumerate([round(ix, 1), round(iy, 1), 0, 0]):
            self.calib_table.setItem(r, c, QTableWidgetItem(str(val)))

    def _on_pane_click(self, ix, iy):
        if self._calib_capture:
            self._add_calib_row(ix, iy)
            self.statusBar().showMessage(f"[{self.focus_cam}] Punkt: {ix:.0f}, {iy:.0f} – Welt-Yards eintragen.", 4000)

    def _compute_calib(self):
        ip, wp = [], []
        for r in range(self.calib_table.rowCount()):
            try:
                ip.append([float(self.calib_table.item(r, 0).text()), float(self.calib_table.item(r, 1).text())])
                wp.append([float(self.calib_table.item(r, 2).text()), float(self.calib_table.item(r, 3).text())])
            except (ValueError, AttributeError):
                continue
        if len(ip) < 4:
            self.statusBar().showMessage("Mindestens 4 Punkte noetig.", 4000); return
        try:
            self.manager.set_calibration(self.focus_cam, wp, ip)
        except Exception as e:
            self.statusBar().showMessage(f"Homographie-Fehler: {e}", 5000); return
        self.camera["calibration"] = {"imagePoints": ip, "worldPoints": wp}
        save_json(CONFIG_PATH, self.config)
        self.statusBar().showMessage(f"[{self.focus_cam}] Kalibrierung gespeichert & aktiv.", 4000)

    # ---- Vollbild ----
    def toggle_fullscreen(self):
        if self._fs is not None:
            self._fs.close(); self._fs = None; return
        screens = QApplication.screens()
        target = screens[1] if len(screens) > 1 else (screens[0] if screens else None)
        self._fs = FullscreenOutput(target)
        self._fs.destroyed.connect(lambda: setattr(self, "_fs", None))

    # ---- Engine-Steuerung ----
    def _install_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self.take)
        QShortcut(QKeySequence(Qt.Key_Enter), self, activated=self.take)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.take)
        QShortcut(QKeySequence(Qt.Key_F11), self, activated=self.toggle_fullscreen)

    def _set_led(self, on):
        self.led.setStyleSheet(f"background:{'#2ecc5a' if on else '#5c6472'}; border-radius:5px;")

    def _show_cameras(self):
        screens = QApplication.screens()
        idx = min(self.screenSel.currentIndex(), len(screens) - 1)
        self.mview.place_on(screens[idx] if screens else None, fullscreen=True)

    def start_all(self):
        self.manager.fps = self.fpsSpin.value()
        self.manager.loop = self.loopChk.isChecked()
        self.manager.set_gamestate_preview(self.preview_gs)
        self.manager.set_gamestate_program(self.program_gs)
        self.manager.start_all(ndi_out=self.ndiChk.isChecked())
        self._set_led(self.manager.any_running())
        self.statusBar().showMessage("Alle Kamera-Pipelines gestartet.", 3000)

    def stop_all(self):
        self.manager.stop_all()
        self._set_led(False)
        self.statusBar().showMessage("Alle gestoppt.", 3000)

    def _on_frames(self, cam_id, program, preview):
        tile = self.tiles.get(cam_id)
        if tile:
            tile.set_frame(program)
        if cam_id == self.focus_cam:
            self.program_mon.set_frame(program)
            self.preview_mon.set_frame(preview)
            if self._fs is not None:
                self._fs.set_frame(program)

    def _on_status(self, cam_id, st):
        tile = self.tiles.get(cam_id)
        if tile:
            tile.set_status(st)
        if cam_id == self.focus_cam:
            txt = f"{st.get('fps', 0):.0f}  fps"
            tr = st.get("track") or ""
            if "lost" in tr:
                txt += "  ⚠"
            elif "TRACK" in tr:
                txt += "  ◉"
            self.fps_pill.setText(txt)

    def closeEvent(self, ev):
        if self._fs is not None:
            self._fs.close()
        if getattr(self, "mview", None) is not None:
            self.mview.close()
        self.manager.stop_all()
        super().closeEvent(ev)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    QApplication.setFont(QFont("Segoe UI", 10))
    win = MainWindow(); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
