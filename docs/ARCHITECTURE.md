# Architektur

## Ziele & Randbedingungen

- Virtuelle First-Down-Line perspektivisch korrekt und **hinter** Spielern.
- Integration in eine bestehende **VMix + Blackmagic**-Produktion.
- Ein-/Ausgabe über **NDI** oder **DeckLink-Capture**.
- **Die 4 bestehenden externen NDI-Feeds dürfen nicht blockiert/verändert werden** → die
  Engine erzeugt jeweils einen _zusätzlichen_ Feed (`LINE-CAMx`).
- **Gemischte Kameras**: manche fest / mit Presets, manche frei geführt (PTZ).

## Zwei-Ebenen-Design (Control-Plane / Data-Plane)

Node.js ist ideal für Steuerung, aber **ungeeignet** für Echtzeit-Pixelverarbeitung bei
1080p50. Deshalb strikte Trennung:

### Front-Ends (austauschbar, gleiche Engine)
- **Desktop-App (`app/`, PySide6)** – eigenständige Anwendung für Windows/Linux/Mac im
  VMix-Stil: oben zwei Video-Monitore **PREVIEW | PROGRAM**, dazwischen **TAKE**, unten die
  Control-Menüs als Tabs (Spiel, Strafen, Logos, Quelle/Ausgang, Kalibrierung). Die Engine
  läuft als `QThread` (`app/engine.py`) und liefert die komponierten Frames **direkt** als
  QImage → keine Encoding-/Streaming-Latenz. Optionaler NDI-Programm-Ausgang aus der App.
  Preview/Program folgen dem Broadcast-Muster: Controls editieren den **Preview**-Zustand,
  **TAKE** kopiert ihn nach **Program** (und schreibt `gamestate.json`).
- **Web-Control (`server/` + `web/`)** – Browser-Oberfläche (siehe unten).

Beide Front-Ends nutzen dasselbe Render-Modul `worker/render.py` und dieselben Dateien
(`config/config.json`, `config/gamestate.json`) → identische Ausgabe, kein Auseinanderlaufen.

### Control-Plane — Node.js (`server/`)
- Express-HTTP + WebSocket.
- Serviert die Kalibrier-UI (`web/`).
- REST/WS für: Kalibrierpunkte speichern, Homographie-Preview, Linie an/aus, Yard-Position,
  Farbe, Presets pro Kamera.
- **VMix-API-Client** (`server/vmix.js`, HTTP Web-Controller Port 8088): Titel/Overlay/Input
  schalten, Tally lesen.
- **Prozess-Management**: startet/überwacht pro Kamera einen Python-Worker.
- Schreibt Laufzeit-Steuerung in `config/state.<camera>.json` (der Worker liest sie).

### Data-Plane — Python/OpenCV (`worker/`)
- `line_engine.py`: Hauptschleife Capture → Homographie → **Logos** → **LOS/First-Down-Linien**
  → Rasen-Maske/Compositing → **Scorebug** → Ausgabe.
- `homography.py`: Feld↔Bild-Abbildung (3×3), aus Kalibrierpunkten (`cv2.findHomography`).
- `occlusion.py`: HSV-Rasen-Maske + Morphologie → Grafik nur auf Feldpixeln.
- `graphics.py`: Team-Logos/Bilder perspektivisch aufs Feld warpen (`warpPerspective`),
  mit derselben Rasen-Maske → **hinter Spielern**.
- `hud.py`: Bildschirm-Scorebug (Down & Distance, Ballbesitz) + Strafen-Banner (Pillow).
- `io_sources.py` / `io_sinks.py`: Datei / Webcam / **NDI (cyndilib)** / **DeckLink**.

### Rendering-Reihenfolge (pro Frame)
1. Rasen-Maske einmal berechnen (geteilt von Logos + Linien).
2. **Team-Logos** aufs Feld (occludiert).
3. **Line of Scrimmage** (blau) + **First-Down-Line** (gelb) aus dem Game-State (occludiert).
4. **Scorebug + Strafen-Banner** als Bildschirm-Overlay obendrauf (nicht occludiert, gut lesbar).

### Game-State (Down & Distance, Strafen)
Ein **geteilter** Zustand `config/gamestate.json` (ein Spiel, alle Kameras) hält
`down`, `distance`, `losYard`, `firstDownYard`, `possession`, `penalty`. Er wird vom Worker
pro Poll gelesen und speist Linien **und** Scorebug. Über den Node-Server editierbar
(`/api/gamestate`, `/api/gamestate/action` für „Nächster Down"/„Neue Serie"). Optional werden
dieselben Werte per `SetText` an einen **VMix-GT-Title** gepusht (`overlays.vmixPush`), falls du
den Scorebug lieber nativ in VMix statt im Feed haben willst.

### Warum die Ebenen so kommunizieren
- **Config** (`config/config.json`): statisch, editiert über UI/Server. Feld, Kameras,
  Kalibrierpunkte, Quelle/Ziel.
- **State** (`config/state.<camera>.json`): heiß, pro Frame vom Worker gepollt (an/aus,
  Yard-Position, Farbe). Kein Socket-Zwang, robust, restart-fest.

## Die drei CV-Kernbausteine

### 1. Homographie (Perspektive)
3×3-Matrix H bildet **Feldkoordinaten** (Yards, Bodenebene) auf **Bildpixel** ab. Aus ≥4
Korrespondenzen (Yard-Marker, Hash-Marks, Ecken) berechnet. Eine Yard-Linie ist im Feld ein
Rechteck `(yard, 0)…(yard, breite)` mit Dicke `line.widthYards`; die 4 Weltecken werden
projiziert und als Polygon gefüllt → korrekte Perspektive automatisch (Homographien bilden
Geraden auf Geraden ab).

### 2. Okklusion (Linie hinter Spielern)
- `fieldMask` = HSV-Schwellwert auf Rasen-Grün (+ Morphologie gegen Rauschen).
- `lineMask` = gerasterte Yard-Linie.
- `drawMask = lineMask AND fieldMask` → gezeichnet wird nur, wo Linie **und** Rasen.
- Spieler/Trikots/Schiris sind nicht „grün" → Linie wird dort ausgespart.
- Weiche Kanten via leichtem Alpha-Blend gegen „Treppen".

### 3. Kamera-Tracking (fest vs. frei)
- **`mode: "fixed"`**: H ist konstant. Einmal pro Kamera/Preset kalibrieren. **Jetzt lauffähig.**
- **`mode: "tracked"`**: H muss pro Frame nachgeführt werden. Erweiterungspunkt in
  `homography.py::track_update()` — Optionen:
  - **Optisch**: Feature-Matching/Optical-Flow gegen ein Referenz-Keyframe (rein Software).
  - **Encoder**: Pan/Tilt/Zoom-Daten der Kamera → H aus Kameramodell (präziser, Hardware nötig).
  - Start: Preset-Erkennung (bei PTZ-Presets zurück auf die passende `fixed`-H schalten).

## Signal-/Netz-Topologie mit VMix

```
                         ┌───────────────── Produktions-LAN (NDI) ──────────────────┐
 Kamera 1 ─SDI─► DeckLink ──► line_engine (cam1) ──NDI──► "LINE-CAM1" ─┐
 Kamera 2 ─NDI──────────────► line_engine (cam2) ──NDI──► "LINE-CAM2" ─┤
   ...                                                                  ├─► VMix
 (4 externe NDI-Feeds) ───────────────────────────────────────────────►┘  (unangetastet)
                         └──────────────────────────────────────────────────────────┘
        Node.js Control-Server + Web-UI  ◄── steuert Worker & VMix-API (HTTP :8088)
```

**Okklusions-relevant:** Die Engine nimmt *ein* Kamerabild rein und gibt *Kamera+Linie fertig
komponiert* raus. In VMix wird `LINE-CAMx` **statt** der Rohkamera geschaltet. Das ist robuster
als ein Fill+Key-Overlay in VMix, weil ein reines Overlay nicht hinter Spielern liegen kann und
Genlock/Alignment bräuchte.

## Latenz & Genlock
- Voll-Composite in der Engine → 1 zusätzliche Verarbeitungsstufe (~1–3 Frames bei GPU/optimiert).
- Für sauberes Umschalten in VMix sollten alle Kameras genlockt sein (Blackmagic-Referenz).
- Python-Prototyp priorisiert Korrektheit; für Live-50p ggf. CUDA/`cv2.cuda`, GStreamer oder
  ein Shader-Pipeline-Rewrite der heißen Schleife.

## Sicherheits-/Betriebsnotizen
- Ein Worker-Prozess **pro Kamera** (Isolation; ein Absturz nimmt nicht die ganze Produktion mit).
- Der Control-Server bindet standardmäßig auf `127.0.0.1`. Für Zugriff vom Regie-Netz bewusst öffnen.
