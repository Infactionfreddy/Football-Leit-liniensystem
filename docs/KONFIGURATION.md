# Konfiguration

[← Zurück zur README](../README.md)

## Umgebungsvariablen (Node-Server)

| Variable | Standard | Beschreibung |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind-Adresse; für Zugriff aus dem Regie-Netz bewusst ändern |
| `PORT` | `3000` | HTTP-/WebSocket-Port |
| `PYTHON_BIN` | `python3` | Interpreter für Worker-Prozesse |

## Dateien

| Datei | Zweck |
|---|---|
| `config/config.json` | Statische Konfiguration (wird beim Erststart aus `example.config.json` abgeleitet, falls nicht vorhanden) |
| `config/state.<kamera>.json` | Heißer Zustand je Kamera (vom Worker gepollt) |
| `config/gamestate.json` | Geteilter Spielstand für alle Kameras |

## Schlüssel in `config.json` (aus dem Code abgeleitet)

Vollständige Defaults siehe `config/example.config.json`; hier die vom Code gelesenen Schlüssel.

| Schlüssel | Typ | Bedeutung / Default im Code |
|---|---|---|
| `field.width` | Zahl | Feldbreite in Yards, 53.3 |
| `line.yardPosition` | Zahl | Start-Yardposition der First-Down-Linie |
| `line.widthYards` | Zahl | Linienbreite, 0.35 |
| `line.colorBGR` | [B,G,R] | Farbe der First-Down-Linie, [0,220,255] |
| `line.softnessPx` | Zahl | Weichzeichnung der Kanten, 2 |
| `occlusion.fieldHsvLower` | [H,S,V] | untere Rasen-Schwelle, [33,40,40] |
| `occlusion.fieldHsvUpper` | [H,S,V] | obere Rasen-Schwelle, [90,255,255] |
| `occlusion.morphKernel` | Zahl | Morphologie-Kernel, 5 |
| `overlays.firstDownLine.enabled` | Bool | gelbe Linie an/aus, `true` |
| `overlays.lineOfScrimmage.enabled` / `.colorBGR` | Bool / [B,G,R] | blaue Linie, Farbe [255,90,0] |
| `overlays.scorebug.enabled` | Bool | Scorebug an/aus, `true` |
| `overlays.vmixPush.enabled` / `.titleInput` | Bool / String | Push an VMix-GT-Title |
| `teams.home` / `teams.away` | Objekt | `abbr`, `colorBGR` für den Scorebug |
| `gameState` | Objekt | Startwerte des Spielstands |
| `fieldGraphics[]` | Liste | Logos: `id`, `type` (`logo`), `image`, `enabled`, `centerYard`, `widthYards`, `heightYards`, `rotationDeg`, `opacity`, `occlude` |
| `cameras[]` | Liste | `id`, `name`, `mode` (`fixed`/`tracked`), `source` (`type`, `path`/`name`), `output.name`, `calibration` (`imagePoints`, `worldPoints`) |

## Game-State

| Feld | Bedeutung |
|---|---|
| `possession` | `home` / `away` |
| `down`, `distance`, `goalToGo` | Down & Distance |
| `losYard`, `firstDownYard` | Position der blauen/gelben Linie |
| `quarter`, `clock` | Anzeige (Web-UI) |
| `penalty` | `active`, `team`, `text` |

## Kamera-State (`state.<cam>.json`)

`enabled`, `yardPosition`, `colorBGR`, `showGraphics`, `showScorebug`.

## Quellen-Angaben

| Spezifikation | Bedeutung |
|---|---|
| `recordings/cam1.mp4` | Videodatei |
| `device:0` | Capture-Device (USB/DeckLink) |
| `ndi://<Name>` | NDI-Quelle (Teilstring-Match, groß/klein egal) |

## CLI-Optionen `worker/line_engine.py`

| Option | Standard | Beschreibung |
|---|---|---|
| `--config` | (Pflicht) | Pfad zur config.json |
| `--camera` | (Pflicht) | Kamera-ID |
| `--sink` | `window` | `window`, `file`, `ndi` |
| `--source-override` | – | Quelle überschreiben |
| `--out` | `out/line.mp4` | Zieldatei bei `file` |
| `--loop` | aus | Datei in Schleife |
| `--max-frames` | 0 | Stopp nach N Frames |
| `--state-poll` | 5 | State alle N Frames lesen |

## Hooks/Filter

Es gibt keine Plugin-Hooks. Einziger Erweiterungspunkt: `PitchTracker.reanchor(H_model)` für Feldmodell-Verankerung.
