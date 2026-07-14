#!/usr/bin/env python3
"""Football Leit-Liniensystem – Desktop-Control (Windows/Linux).

VMix-artiges Layout: oben PREVIEW | PROGRAM, unten alle Control-Menues
(Spiel, Strafen, Logos, Quelle/Ausgang, Kalibrierung, VMix). Live-Bild kommt
Low-Latency direkt aus der OpenCV-Pipeline (kein Streaming)."""
from __future__ import annotations

import os
import sys
import json
import copy

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QLineEdit, QTabWidget, QGroupBox, QTableWidget, QTableWidgetItem, QFileDialog,
    QHeaderView, QSizePolicy,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.join(ROOT, "worker"))

from engine import EngineThread  # noqa: E402
import homography as hg          # noqa: E402

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


class VideoPane(QLabel):
    """Monitor mit farbigem Rahmen (Program=rot, Preview=gruen). Klick liefert
    Bildkoordinaten (fuer Kalibrierung)."""
    clicked = Signal(float, float)

    def __init__(self, title, color):
        super().__init__()
        self.setMinimumSize(360, 202)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"background:#000; border:3px solid {color};")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._title = title
        self._img_w = self._img_h = 0
        self.setText(title)

    def set_frame(self, frame):
        self._img_h, self._img_w = frame.shape[:2]
        pix = QPixmap.fromImage(bgr_to_qimage(frame))
        self.setPixmap(pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _disp_geometry(self):
        if not self._img_w:
            return None
        lw, lh = self.width(), self.height()
        scale = min(lw / self._img_w, lh / self._img_h)
        dw, dh = self._img_w * scale, self._img_h * scale
        return (lw - dw) / 2, (lh - dh) / 2, scale

    def mousePressEvent(self, ev):
        g = self._disp_geometry()
        if g:
            ox, oy, s = g
            ix, iy = (ev.position().x() - ox) / s, (ev.position().y() - oy) / s
            if 0 <= ix <= self._img_w and 0 <= iy <= self._img_h:
                self.clicked.emit(ix, iy)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Football Leit-Liniensystem – Control")
        self.resize(1280, 860)

        self.config = load_json(CONFIG_PATH) or load_json(EXAMPLE_PATH, {})
        self.camera = (self.config.get("cameras") or [{}])[0]
        gs_default = self.config.get("gameState", {
            "possession": "home", "down": 1, "distance": 10, "goalToGo": False,
            "losYard": 45.0, "firstDownYard": 55.0, "quarter": 1, "clock": "15:00",
            "penalty": {"active": False, "text": "", "team": "home"},
        })
        self.program_gs = load_json(GAMESTATE_PATH, gs_default)
        self.preview_gs = copy.deepcopy(self.program_gs)
        self._calib_capture = False
        self._loading = False  # verhindert Clobbern von preview_gs beim Laden der Widgets

        self.engine = EngineThread(self)
        self.engine.framesReady.connect(self._on_frames)
        self.engine.status.connect(self._on_status)
        self.engine.error.connect(lambda m: self.statusBar().showMessage("Engine: " + m, 6000))

        self._build_ui()
        self._push_all_to_engine()

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- obere Haelfte: PREVIEW | TAKE | PROGRAM ----
        top = QHBoxLayout()
        self.preview_pane = VideoPane("PREVIEW", "#33cc55")
        self.program_pane = VideoPane("PROGRAM", "#e53935")
        self.preview_pane.clicked.connect(self._on_pane_click)

        center = QVBoxLayout()
        center.addStretch()
        self.take_btn = QPushButton("TAKE ▸")
        self.take_btn.setMinimumHeight(70)
        self.take_btn.setStyleSheet("background:#e53935;color:#fff;font-size:20px;font-weight:bold;border-radius:8px;")
        self.take_btn.clicked.connect(self.take)
        self.fps_lbl = QLabel("– fps")
        self.fps_lbl.setAlignment(Qt.AlignCenter)
        center.addWidget(QLabel("PREVIEW → PROGRAM", alignment=Qt.AlignCenter))
        center.addWidget(self.take_btn)
        center.addWidget(self.fps_lbl)
        center.addStretch()

        top.addWidget(self.preview_pane, 5)
        top.addLayout(center, 1)
        top.addWidget(self.program_pane, 5)
        root.addLayout(top, 3)

        # ---- untere Haelfte: Control-Tabs ----
        tabs = QTabWidget()
        tabs.addTab(self._tab_game(), "Spiel")
        tabs.addTab(self._tab_penalty(), "Strafen")
        tabs.addTab(self._tab_logos(), "Logos")
        tabs.addTab(self._tab_source(), "Quelle / Ausgang")
        tabs.addTab(self._tab_calib(), "Kalibrierung")
        root.addWidget(tabs, 2)

        self.statusBar().showMessage("Bereit. Quelle im Tab 'Quelle / Ausgang' waehlen und Start.")

    def _tab_game(self):
        w = QWidget()
        g = QGridLayout(w)
        self.possession = QComboBox(); self.possession.addItems(["home", "away"])
        self.down = QComboBox(); self.down.addItems(["1", "2", "3", "4"])
        self.distance = QSpinBox(); self.distance.setRange(0, 99)
        self.goalToGo = QCheckBox("Goal to Go")
        self.losYard = QDoubleSpinBox(); self.losYard.setRange(0, 120); self.losYard.setSingleStep(0.5)
        self.firstDownYard = QDoubleSpinBox(); self.firstDownYard.setRange(0, 120); self.firstDownYard.setSingleStep(0.5)
        self.quarter = QSpinBox(); self.quarter.setRange(1, 5)
        self.clock = QLineEdit()

        g.addWidget(QLabel("Ballbesitz"), 0, 0); g.addWidget(self.possession, 0, 1)
        g.addWidget(QLabel("Down"), 0, 2); g.addWidget(self.down, 0, 3)
        g.addWidget(QLabel("Distance"), 0, 4); g.addWidget(self.distance, 0, 5)
        g.addWidget(self.goalToGo, 0, 6)
        g.addWidget(QLabel("Line of Scrimmage (Yard)"), 1, 0); g.addWidget(self.losYard, 1, 1)
        g.addWidget(QLabel("First-Down (Yard)"), 1, 2); g.addWidget(self.firstDownYard, 1, 3)
        g.addWidget(QLabel("Quarter"), 1, 4); g.addWidget(self.quarter, 1, 5)
        g.addWidget(QLabel("Clock"), 1, 6); g.addWidget(self.clock, 1, 7)

        self.dd_lbl = QLabel(); self.dd_lbl.setStyleSheet("color:#ffdc00;font-size:18px;font-weight:bold;")
        next_down = QPushButton("Naechster Down ▸"); next_down.clicked.connect(self._next_down)
        new_series = QPushButton("Neue Serie (1st & 10)"); new_series.clicked.connect(self._new_series)
        g.addWidget(next_down, 2, 0, 1, 2)
        g.addWidget(new_series, 2, 2, 1, 2)
        g.addWidget(QLabel("Preview:"), 2, 4); g.addWidget(self.dd_lbl, 2, 5, 1, 3)

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
        w = QWidget()
        v = QVBoxLayout(w)
        row = QHBoxLayout()
        self.penActive = QCheckBox("Strafe aktiv (Flag)")
        self.penTeam = QComboBox(); self.penTeam.addItems(["home", "away"])
        row.addWidget(self.penActive); row.addWidget(QLabel("Team")); row.addWidget(self.penTeam); row.addStretch()
        v.addLayout(row)
        self.penText = QLineEdit(); self.penText.setPlaceholderText("z. B. Halten #75, 10 Yards")
        v.addWidget(self.penText)
        quick = QGridLayout()
        for i, p in enumerate(PENALTIES):
            b = QPushButton(p)
            b.clicked.connect(lambda _=False, t=p: (self.penText.setText(t), self.penActive.setChecked(True)))
            quick.addWidget(b, i // 2, i % 2)
        box = QGroupBox("Schnellauswahl"); box.setLayout(quick)
        v.addWidget(box); v.addStretch()

        self.penActive.stateChanged.connect(self._collect_preview)
        self.penTeam.currentIndexChanged.connect(self._collect_preview)
        self.penText.textChanged.connect(self._collect_preview)
        pen = self.preview_gs.get("penalty", {})
        self.penActive.setChecked(bool(pen.get("active")))
        self.penText.setText(pen.get("text", ""))
        return w

    def _tab_logos(self):
        w = QWidget()
        v = QVBoxLayout(w)
        flags = QHBoxLayout()
        self.showGraphics = QCheckBox("Logos anzeigen"); self.showGraphics.setChecked(True)
        self.showScorebug = QCheckBox("Scorebug anzeigen"); self.showScorebug.setChecked(True)
        self.showGraphics.stateChanged.connect(self._flags_changed)
        self.showScorebug.stateChanged.connect(self._flags_changed)
        flags.addWidget(self.showGraphics); flags.addWidget(self.showScorebug); flags.addStretch()
        v.addLayout(flags)

        self.logo_table = QTableWidget(0, 6)
        self.logo_table.setHorizontalHeaderLabels(["ID", "an", "X (Yard)", "Y (Yard)", "Groesse", "Rot°"])
        self.logo_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v.addWidget(self.logo_table)
        self._load_logo_table()
        self.logo_table.cellChanged.connect(self._logo_changed)
        v.addWidget(QLabel("Logos liegen in assets/ (PNG mit Alpha). Aenderungen werden sofort wirksam."))
        return w

    def _tab_source(self):
        w = QWidget()
        g = QGridLayout(w)
        src = self.camera.get("source", {})
        default_spec = src.get("path") or ("ndi://" + src.get("name", "") if src.get("type") == "ndi" else "device:0")
        self.sourceEdit = QLineEdit(default_spec or "recordings/cam1.mp4")
        browse = QPushButton("Datei…"); browse.clicked.connect(self._browse_source)
        self.loopChk = QCheckBox("Datei loopen"); self.loopChk.setChecked(True)
        self.fpsSpin = QDoubleSpinBox(); self.fpsSpin.setRange(1, 120); self.fpsSpin.setValue(50)

        g.addWidget(QLabel("Quelle (Datei / device:0 / ndi://Name)"), 0, 0)
        g.addWidget(self.sourceEdit, 0, 1, 1, 2); g.addWidget(browse, 0, 3)
        g.addWidget(self.loopChk, 1, 0); g.addWidget(QLabel("FPS"), 1, 1); g.addWidget(self.fpsSpin, 1, 2)

        self.startBtn = QPushButton("▶ Start"); self.startBtn.clicked.connect(self.start_engine)
        self.stopBtn = QPushButton("■ Stop"); self.stopBtn.clicked.connect(self.stop_engine)
        g.addWidget(self.startBtn, 2, 0); g.addWidget(self.stopBtn, 2, 1)

        out = QGroupBox("Programm-Ausgang (neuer NDI-Feed, blockiert bestehende nicht)")
        og = QGridLayout(out)
        self.ndiChk = QCheckBox("NDI-Ausgang aktiv")
        self.ndiName = QLineEdit(self.camera.get("output", {}).get("name", "LINE-PROGRAM"))
        self.ndiChk.stateChanged.connect(lambda: self.engine.set_ndi(self.ndiChk.isChecked(), self.ndiName.text()))
        og.addWidget(self.ndiChk, 0, 0); og.addWidget(QLabel("Name"), 0, 1); og.addWidget(self.ndiName, 0, 2)
        g.addWidget(out, 3, 0, 1, 4)
        g.setRowStretch(4, 1)
        return w

    def _tab_calib(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("Referenzpunkte: 'Aus Klick erfassen' aktivieren, dann in den PREVIEW-Monitor "
                           "klicken. Welt-Yards (X,Y) eintragen, dann Berechnen & Speichern."))
        row = QHBoxLayout()
        self.captureChk = QCheckBox("Aus Klick erfassen")
        self.captureChk.stateChanged.connect(lambda: setattr(self, "_calib_capture", self.captureChk.isChecked()))
        add = QPushButton("Zeile +"); add.clicked.connect(lambda: self._add_calib_row())
        rem = QPushButton("Zeile −"); rem.clicked.connect(lambda: self.calib_table.removeRow(self.calib_table.rowCount() - 1) if self.calib_table.rowCount() else None)
        row.addWidget(self.captureChk); row.addWidget(add); row.addWidget(rem); row.addStretch()
        v.addLayout(row)

        self.calib_table = QTableWidget(0, 4)
        self.calib_table.setHorizontalHeaderLabels(["Bild x", "Bild y", "Welt X (Yard)", "Welt Y (Yard)"])
        self.calib_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v.addWidget(self.calib_table)
        self._load_calib_table()

        calc = QPushButton("Homographie berechnen & speichern"); calc.clicked.connect(self._compute_calib)
        v.addWidget(calc)
        return w

    # ---------------- Datenfluss ----------------
    def _load_game_widgets(self, gs):
        gs = copy.deepcopy(gs)  # von preview_gs entkoppeln
        self._loading = True
        self.possession.setCurrentText(gs.get("possession", "home"))
        self.down.setCurrentText(str(gs.get("down", 1)))
        self.distance.setValue(int(gs.get("distance", 10)))
        self.goalToGo.setChecked(bool(gs.get("goalToGo")))
        self.losYard.setValue(float(gs.get("losYard", 45)))
        self.firstDownYard.setValue(float(gs.get("firstDownYard", 55)))
        self.quarter.setValue(int(gs.get("quarter", 1)))
        self.clock.setText(str(gs.get("clock", "15:00")))
        self._loading = False
        self._collect_preview()  # einmal sauber aus den geladenen Widgets

    def _collect_preview(self):
        if self._loading:
            return
        self.preview_gs.update({
            "possession": self.possession.currentText(),
            "down": int(self.down.currentText()),
            "distance": self.distance.value(),
            "goalToGo": self.goalToGo.isChecked(),
            "losYard": self.losYard.value(),
            "firstDownYard": self.firstDownYard.value(),
            "quarter": self.quarter.value(),
            "clock": self.clock.text(),
        })
        if hasattr(self, "penActive"):
            self.preview_gs["penalty"] = {
                "active": self.penActive.isChecked(),
                "team": self.penTeam.currentText(),
                "text": self.penText.text(),
            }
        self.engine.set_preview_state(self.preview_gs)
        self._update_dd()

    def _update_dd(self):
        ordm = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
        gs = self.preview_gs
        d = ordm.get(gs.get("down"), f"{gs.get('down')}th")
        txt = f"{d} & Goal" if gs.get("goalToGo") else f"{d} & {gs.get('distance')}"
        self.dd_lbl.setText(txt)

    def take(self):
        """PREVIEW → PROGRAM."""
        self.program_gs = copy.deepcopy(self.preview_gs)
        save_json(GAMESTATE_PATH, self.program_gs)
        self.engine.set_program_state(self.program_gs)
        self.statusBar().showMessage("TAKE – Program aktualisiert.", 3000)

    def _next_down(self):
        self.down.setCurrentText(str(min(4, int(self.down.currentText()) + 1)))

    def _new_series(self):
        self.losYard.setValue(self.firstDownYard.value())
        self.firstDownYard.setValue(self.firstDownYard.value() + 10)
        self.down.setCurrentText("1")
        self.distance.setValue(10)

    def _flags_changed(self):
        self.engine.set_flags(self.showGraphics.isChecked(), self.showScorebug.isChecked())

    # ---- Logos ----
    def _load_logo_table(self):
        items = self.config.get("fieldGraphics", [])
        self.logo_table.blockSignals(True)
        self.logo_table.setRowCount(len(items))
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
        self.engine.set_cfg(self.config)

    # ---- Quelle ----
    def _browse_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Video waehlen", ROOT, "Video (*.mp4 *.mov *.mkv);;Alle (*)")
        if path:
            self.sourceEdit.setText(path)

    # ---- Kalibrierung ----
    def _load_calib_table(self):
        cal = self.camera.get("calibration", {})
        ip, wp = cal.get("imagePoints", []), cal.get("worldPoints", [])
        self.calib_table.setRowCount(len(ip))
        for r in range(len(ip)):
            for c, val in enumerate([ip[r][0], ip[r][1], wp[r][0] if r < len(wp) else 0, wp[r][1] if r < len(wp) else 0]):
                self.calib_table.setItem(r, c, QTableWidgetItem(str(val)))

    def _add_calib_row(self, ix=0.0, iy=0.0):
        r = self.calib_table.rowCount()
        self.calib_table.insertRow(r)
        for c, val in enumerate([round(ix, 1), round(iy, 1), 0, 0]):
            self.calib_table.setItem(r, c, QTableWidgetItem(str(val)))

    def _on_pane_click(self, ix, iy):
        if self._calib_capture:
            self._add_calib_row(ix, iy)
            self.statusBar().showMessage(f"Punkt erfasst: {ix:.0f}, {iy:.0f} – Welt-Yards eintragen.", 4000)

    def _compute_calib(self):
        ip, wp = [], []
        for r in range(self.calib_table.rowCount()):
            try:
                ip.append([float(self.calib_table.item(r, 0).text()), float(self.calib_table.item(r, 1).text())])
                wp.append([float(self.calib_table.item(r, 2).text()), float(self.calib_table.item(r, 3).text())])
            except (ValueError, AttributeError):
                continue
        if len(ip) < 4:
            self.statusBar().showMessage("Mindestens 4 Punkte noetig.", 4000)
            return
        try:
            self.engine.set_calibration(wp, ip)
        except Exception as e:
            self.statusBar().showMessage(f"Homographie-Fehler: {e}", 5000)
            return
        self.camera["calibration"] = {"imagePoints": ip, "worldPoints": wp}
        save_json(CONFIG_PATH, self.config)
        self.statusBar().showMessage("Kalibrierung gespeichert & aktiv.", 4000)

    # ---- Engine ----
    def _push_all_to_engine(self):
        self.engine.set_cfg(self.config)
        self.engine.set_program_state(self.program_gs)
        self.engine.set_preview_state(self.preview_gs)
        cal = self.camera.get("calibration", {})
        if cal.get("imagePoints") and len(cal["imagePoints"]) >= 4:
            try:
                self.engine.set_calibration(cal["worldPoints"], cal["imagePoints"])
            except Exception:
                pass

    def start_engine(self):
        if self.engine.isRunning():
            return
        self.engine.configure(self.config, self.sourceEdit.text().strip(),
                              assets_root=ROOT, fps=self.fpsSpin.value(), loop=self.loopChk.isChecked())
        self._push_all_to_engine()
        self.engine.start()
        self.statusBar().showMessage("Engine laeuft.", 3000)

    def stop_engine(self):
        self.engine.stop()
        self.engine.wait(1500)
        self.statusBar().showMessage("Engine gestoppt.", 3000)

    def _on_frames(self, program, preview):
        self.program_pane.set_frame(program)
        self.preview_pane.set_frame(preview)

    def _on_status(self, st):
        self.fps_lbl.setText(f"{st.get('fps', 0):.0f} fps")

    def closeEvent(self, ev):
        self.engine.stop()
        self.engine.wait(1500)
        super().closeEvent(ev)


DARK_QSS = """
QWidget { background:#15181e; color:#e7e9ee; font-size:13px; }
QGroupBox { border:1px solid #2a2f3a; border-radius:6px; margin-top:8px; padding-top:8px; }
QGroupBox::title { subcontrol-origin: margin; left:10px; color:#9aa3b2; }
QTabWidget::pane { border:1px solid #2a2f3a; }
QTabBar::tab { background:#1c2029; padding:8px 16px; border:1px solid #2a2f3a; }
QTabBar::tab:selected { background:#2d7dff; color:#fff; }
QPushButton { background:#222833; border:1px solid #2a2f3a; border-radius:6px; padding:7px 12px; }
QPushButton:hover { border-color:#2d7dff; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget { background:#0c0e12; border:1px solid #2a2f3a; border-radius:5px; padding:4px; }
QHeaderView::section { background:#1c2029; border:1px solid #2a2f3a; padding:4px; }
"""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
