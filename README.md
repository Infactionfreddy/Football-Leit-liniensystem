# Football Leit-Liniensystem

Virtuelle **First-Down-Line** („gelbe Linie") für American-Football-Produktionen mit
**VMix** und **Blackmagic**, gesteuert über einen **Node.js-Server** und gerendert mit
einer **Python/OpenCV**-Engine. Ein-/Ausgabe wahlweise über **NDI** oder **Capture-Karte
(DeckLink)** – ohne die vorhandenen NDI-Feeds zu blockieren (die Engine erzeugt einen
_zusätzlichen_ Feed).

> Status: Scaffold / Proof-of-Concept. Der Offline-Pfad (Video-Datei rein → Linie mit
> Perspektive + Okklusion → Video/Fenster raus) läuft ohne Spezial-Hardware. Der Live-Pfad
> (NDI/DeckLink) ist verdrahtet und dokumentiert.

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
| `server/` | Node.js Control-Plane (Express + WebSocket, VMix-Client, Homographie-Preview, Game-State) |
| `web/` | Kalibrier- & Spielstand-UI (Browser-Canvas) |
| `worker/` | Python/OpenCV Data-Plane: `homography` · `occlusion` · `graphics` (Logos) · `hud` (Scorebug) · I/O/NDI |
| `config/` | Feldmodell, Teams, `fieldGraphics`, `gameState`, Kameras, Kalibrierpunkte, Laufzeit-State |
| `assets/` | Team-Logos (PNG mit Alpha) – eigene ablegen |
| `docs/` | Architektur & Roadmap |
