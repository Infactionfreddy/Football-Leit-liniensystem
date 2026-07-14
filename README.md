# Football Leit-Liniensystem

Virtuelle **First-Down-Line** („gelbe Linie") für American-Football-Produktionen mit
**VMix** und **Blackmagic**, gesteuert über einen **Node.js-Server** und gerendert mit
einer **Python/OpenCV**-Engine. Ein-/Ausgabe wahlweise über **NDI** oder **Capture-Karte
(DeckLink)** – ohne die vorhandenen NDI-Feeds zu blockieren (die Engine erzeugt einen
_zusätzlichen_ Feed).

> Status: Scaffold / Proof-of-Concept. Der Offline-Pfad (Video-Datei rein → Linie mit
> Perspektive + Okklusion → Video/Fenster raus) läuft ohne Spezial-Hardware. Der Live-Pfad
> (NDI/DeckLink) ist verdrahtet und dokumentiert.

## Zwei Bedien-Oberflächen (gleiche Engine)

1. **Desktop-App** (`app/`, PySide6) – professioneller, VMix-artiger Produktions-Look:
   Kopfleiste mit Engine-Status + Uhr, **PREVIEW | TAKE/CUT | PROGRAM** mit Tally-Headern,
   Funktions-Bar (Neue Serie / Down / Flag / Logos / Scorebug) und Control-Tabs (Spiel,
   Strafen, Logos, Quelle/Ausgang, Kalibrierung). **Vollbild-Programm-Ausgang** auf einem
   zweiten Monitor (F11), Tastatur-Shortcuts (Enter/Leertaste = TAKE). Live-Bild kommt
   Low-Latency direkt aus der OpenCV-Pipeline. **Windows/Linux/Mac.** Styling in `app/theme.py`.
2. **Web-Control** (`server/` + `web/`) – Browser-UI zum Kalibrieren und Fernsteuern.

Beide lesen/schreiben **dieselben** Dateien (`config/config.json`, `config/gamestate.json`)
und rendern über dasselbe Modul (`worker/render.py`) – kein Auseinanderlaufen.

## Architektur in einem Satz

**Node.js = Steuerung** (Web-UI, Kalibrierung, Presets, VMix-API, Prozess-Management),
**Python/OpenCV = Bildverarbeitung** (Homographie, Rasen-Maske/Okklusion, Compositing, NDI-I/O).

Signalfluss:

```
Kamera ──SDI──> DeckLink ─┐
    oder ──NDI────────────┤
                          ▼
             Linien-Engine (worker/line_engine.py)
        [Homographie → Yard-Linie → Rasen-Maske → Compositing]
                          ▼
          NEUER NDI-Output "LINE-CAMx"  (zusätzlicher Feed)
                          ▼
                        VMix   ← die 4 bestehenden NDI-Feeds bleiben unangetastet
```

Details: siehe [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) und [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Eingänge & Ausgang (Signalkette)

- **Mehrere Kamera-Eingänge**, in der App umschaltbar (Tab *Quelle / Ausgang → Aktive Kamera*):
  Datei, USB/DeckLink-Device (`device:0`) oder **NDI** (mit *NDI-Quellen suchen*).
- **Kamera-Tracking** pro Kamera zuschaltbar (frei geführte Kamera **oder** Programm-Feed):
  bildbasierte Homographie-Nachführung (`worker/tracking.py`).
- **Programm-Ausgang an VMix**: neuer NDI-Feed `LINE-CAMx` (blockiert bestehende NDI-Feeds
  nicht). **SDI-Ausgang** folgt über DeckLink/AJA (native SDK-Schicht).

## Funktionsumfang

- **First-Down-Line** (gelb) + **Line of Scrimmage** (blau) – perspektivisch, hinter Spielern.
- **Team-Logos auf dem Rasen** – PNG mit Alpha, aufs Feld gewarpt, ebenfalls hinter Spielern
  (`worker/graphics.py`, Config `fieldGraphics[]`).
- **Nächste Spielzüge (Down & Distance)** + **Strafen** – Game-State-Modell, das die Feldlinien
  speist und einen **Scorebug/Strafen-Banner** rendert (`worker/hud.py`); dieselben Werte lassen
  sich optional per **VMix-API (SetText)** an einen GT-Title pushen.
- Alles **live steuerbar** über die Web-UI (Down ▸, Neue Serie, Strafe ein/aus, Logo-Position).

## Warum die Linie *hinter* den Spielern liegt

Die Linie wird **nur auf rasenfarbene Pixel** gemalt (HSV-Farb-Keying). Steht ein Spieler
auf der Linie, ist sein Pixel nicht „grün" → dort wird nichts gezeichnet → die Linie wirkt,
als läge sie unter ihm. Siehe `worker/occlusion.py`.

## Schnellstart · Desktop-App (Preview/Program, VMix-artig)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r worker/requirements.txt -r app/requirements.txt
# Linux zusaetzlich einmalig: sudo apt install libegl1 libgl1 libxkbcommon0

cp config/example.config.json config/config.json   # dann recordings/cam1.mp4 ablegen
python app/main.py
#  -> Tab "Quelle / Ausgang": Quelle setzen + Start
#  -> Tab "Kalibrierung": Punkte im PREVIEW klicken, Yards eintragen, berechnen
#  -> Tab "Spiel"/"Strafen": Down/Distance/Strafe im PREVIEW setzen, dann TAKE
#  -> Tab "Quelle / Ausgang": NDI-Ausgang "LINE-PROGRAM" fuer VMix aktivieren
```

## Schnellstart (Offline-PoC, ohne Hardware)

```bash
# 1) Python-Engine
cd worker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Config anlegen
cd ..
cp config/example.config.json config/config.json
#   -> recordings/cam1.mp4 hinterlegen (deine Kamera-Aufnahme)

# 3) Control-Server + Kalibrier-UI
npm install
npm start
#   -> http://localhost:3000  (Feldpunkte klicken, Yard-Linie setzen, kalibrieren)

# 4) Engine auf einer Kamera starten (Fenster-Ausgabe zum Testen)
python worker/line_engine.py --config config/config.json --camera cam1 --sink window
```

## Live-Betrieb (NDI)

```bash
pip install cyndilib          # NDI für Python
# Quelle = NDI-Feed, Ziel = neuer NDI-Sender "LINE-CAM1"
python worker/line_engine.py --config config/config.json --camera cam1 \
       --source-override "ndi://KAMERA-PC (Cam 1)" --sink ndi
```
In VMix den neuen NDI-Sender `LINE-CAM1` als Input hinzufügen – deine vier bestehenden
NDI-Feeds bleiben unberührt.

## Verzeichnisse

| Pfad | Inhalt |
|------|--------|
| `app/` | Desktop-App (PySide6): Preview/Program-Monitore + Control-Menüs, VMix-artig |
| `server/` | Node.js Control-Plane (Express + WebSocket, VMix-Client, Homographie-Preview, Game-State) |
| `web/` | Kalibrier- & Spielstand-UI (Browser-Canvas) |
| `worker/` | Python/OpenCV Data-Plane: `render` (gemeinsam) · `homography` · `occlusion` · `graphics` (Logos) · `hud` (Scorebug) · I/O/NDI |
| `config/` | Feldmodell, Teams, `fieldGraphics`, `gameState`, Kameras, Kalibrierpunkte, Laufzeit-State |
| `assets/` | Team-Logos (PNG mit Alpha) – eigene ablegen |
| `docs/` | Architektur & Roadmap |
