"""Professionelles, VMix-artiges Dark-Theme (Qt Stylesheet + Farb-Palette)."""

# Farbpalette (Broadcast-Dark).
C = {
    "bg":        "#141619",
    "panel":     "#1b1e24",
    "panel2":    "#22262e",
    "elev":      "#282d37",
    "border":    "#31363f",
    "border2":   "#3c424d",
    "text":      "#e9ecf1",
    "muted":     "#8b93a1",
    "faint":     "#5c6472",
    "accent":    "#2f80ed",
    "preview":   "#20a83a",
    "previewHi": "#2ecc5a",
    "program":   "#e0322f",
    "programHi": "#ff4a47",
    "gold":      "#ffcc00",
}

QSS = f"""
* {{ outline: 0; }}
QMainWindow, QWidget {{ background: {C['bg']}; color: {C['text']};
    font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif; font-size: 13px; }}

/* ---- Toolbar / Kopf ---- */
#TopBar {{ background: {C['panel']}; border-bottom: 1px solid {C['border']}; }}
#AppTitle {{ font-size: 15px; font-weight: 700; color: {C['text']}; }}
#AppTitle #dot {{ color: {C['gold']}; }}
#Clock {{ color: {C['muted']}; }}

/* ---- Monitore ---- */
#Monitor {{ background: {C['panel']}; border: 1px solid {C['border']}; }}
#MonHeaderPreview {{ background: {C['preview']}; color: #06210c; font-weight: 800;
    letter-spacing: 1px; padding: 5px 10px; }}
#MonHeaderProgram {{ background: {C['program']}; color: #2a0605; font-weight: 800;
    letter-spacing: 1px; padding: 5px 10px; }}
#MonSub {{ color: #ffffff; font-weight: 600; }}
#MonPane {{ background: #000; }}
#TallyPreview {{ background: {C['previewHi']}; }}
#TallyProgram {{ background: {C['programHi']}; }}

/* ---- Transition-Leiste ---- */
#XBar {{ background: {C['panel']}; border: 1px solid {C['border']}; }}
#XLabel {{ color: {C['muted']}; font-size: 11px; letter-spacing: 1px; }}
#TakeBtn {{ background: {C['program']}; color: #fff; font-size: 20px; font-weight: 800;
    letter-spacing: 1px; border: none; border-radius: 6px; padding: 14px 0; }}
#TakeBtn:hover {{ background: {C['programHi']}; }}
#TakeBtn:pressed {{ background: #b81f1d; }}
#CutBtn {{ background: {C['elev']}; color: {C['text']}; font-weight: 700; border: 1px solid {C['border2']};
    border-radius: 5px; padding: 9px 0; }}
#CutBtn:hover {{ border-color: {C['accent']}; }}
#FpsPill {{ background: {C['panel2']}; color: {C['muted']}; border: 1px solid {C['border']};
    border-radius: 10px; padding: 2px 10px; }}

/* ---- Funktions-Bar ---- */
#FuncBar {{ background: {C['panel']}; border: 1px solid {C['border']}; }}
#FuncBar QPushButton {{ background: {C['elev']}; border: 1px solid {C['border2']}; border-radius: 5px;
    padding: 8px 14px; font-weight: 600; }}
#FuncBar QPushButton:hover {{ border-color: {C['accent']}; background: {C['panel2']}; }}
#FuncBar QPushButton:checked {{ background: {C['accent']}; border-color: {C['accent']}; color: #fff; }}
#FuncBar QPushButton#FlagBtn:checked {{ background: {C['gold']}; border-color: {C['gold']}; color: #241f00; }}

/* ---- Tabs ---- */
QTabWidget::pane {{ background: {C['panel']}; border: 1px solid {C['border']}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: {C['panel']}; color: {C['muted']}; padding: 9px 20px;
    border: 1px solid {C['border']}; border-bottom: none; margin-right: 2px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {C['panel2']}; color: {C['text']}; border-top: 2px solid {C['accent']}; }}
QTabBar::tab:hover:!selected {{ color: {C['text']}; }}

/* ---- Gruppen / Labels ---- */
QGroupBox {{ background: {C['panel2']}; border: 1px solid {C['border']}; border-radius: 6px;
    margin-top: 14px; padding: 12px 10px 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {C['muted']};
    font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#SectionHint {{ color: {C['faint']}; font-size: 12px; }}
QLabel#DDPreview {{ color: {C['gold']}; font-size: 20px; font-weight: 800; letter-spacing: 1px; }}
QLabel#FieldLabel {{ color: {C['muted']}; font-size: 11px; letter-spacing: .5px; }}

/* ---- Eingaben ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {C['bg']}; color: {C['text']};
    border: 1px solid {C['border2']}; border-radius: 5px; padding: 6px 8px; min-height: 18px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C['accent']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background: {C['panel2']}; border: 1px solid {C['border2']};
    selection-background-color: {C['accent']}; }}

QPushButton {{ background: {C['elev']}; color: {C['text']}; border: 1px solid {C['border2']};
    border-radius: 5px; padding: 8px 14px; }}
QPushButton:hover {{ border-color: {C['accent']}; }}
QPushButton:pressed {{ background: {C['panel2']}; }}
QPushButton#Primary {{ background: {C['accent']}; border-color: {C['accent']}; color: #fff; font-weight: 700; }}
QPushButton#Primary:hover {{ background: #4a90f2; }}
QPushButton#Danger {{ background: {C['panel2']}; border-color: {C['border2']}; }}
QPushButton#Danger:hover {{ border-color: {C['program']}; color: {C['programHi']}; }}

QCheckBox {{ color: {C['text']}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['border2']};
    border-radius: 4px; background: {C['bg']}; }}
QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}

/* ---- Tabellen ---- */
QTableWidget {{ background: {C['bg']}; border: 1px solid {C['border']}; gridline-color: {C['border']};
    selection-background-color: {C['accent']}; }}
QHeaderView::section {{ background: {C['panel']}; color: {C['muted']}; border: none;
    border-right: 1px solid {C['border']}; border-bottom: 1px solid {C['border']}; padding: 6px; font-weight: 600; }}
QTableWidget QLineEdit {{ border-radius: 0; }}

/* ---- Statusbar / Scrollbars ---- */
QStatusBar {{ background: {C['panel']}; color: {C['muted']}; border-top: 1px solid {C['border']}; }}
QScrollBar:vertical {{ background: {C['bg']}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['border2']}; border-radius: 6px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C['faint']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""
