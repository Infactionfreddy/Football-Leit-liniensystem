# API

[← Zurück zur README](../README.md)

Der Node-Server (Standard `http://127.0.0.1:3000`) bietet eine REST-API und einen WebSocket. **Es gibt keine Authentifizierung.**

## REST-Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/config` | Aktuelle Config (oder Beispiel-Config beim Erststart) |
| PUT | `/api/config` | Gesamte Config speichern |
| PUT | `/api/cameras/:id/calibration` | Body `{imagePoints, worldPoints}`; 404 bei unbekannter Kamera |
| POST | `/api/preview` | Body `{imagePoints, worldPoints, yard, fieldWidth, widthYards?}` → `{H, corners}`; 400 bei Fehlern |
| GET | `/api/cameras/:id/state` | Heißer Kamera-State |
| PUT | `/api/cameras/:id/state` | State flach mergen (`enabled`, `yardPosition`, `colorBGR`, `showGraphics`, `showScorebug`) |
| GET | `/api/gamestate` | Geteilter Spielstand |
| PUT | `/api/gamestate` | Spielstand mergen (`penalty` separat); optional VMix-Push, wenn `overlays.vmixPush` aktiv; Body-Feld `vmix` kann `host`/`port` setzen |
| POST | `/api/gamestate/action` | Body `{action}`: `nextDown`, `firstDown`, `togglePenalty` |
| GET | `/api/workers` | `{running: [ids]}` |
| POST | `/api/cameras/:id/worker/start` | Body `{sink?, sourceOverride?}`; `sink` Standard `ndi` |
| POST | `/api/cameras/:id/worker/stop` | Beendet den Worker (SIGTERM) |
| POST | `/api/vmix/call` | Body `{host, port, func, params}`; 502 bei Fehler |
| GET | `/api/health` | `{ok, running}` |

Beispiel:

```bash
curl -X PUT http://127.0.0.1:3000/api/gamestate \
  -H 'content-type: application/json' \
  -d '{"down":3,"distance":7,"losYard":40,"firstDownYard":47}'
```

## WebSocket

Verbindung auf demselben Host/Port. Server → Client Nachrichten:

| `type` | Zusatzfelder |
|---|---|
| `config-updated` | – |
| `state-updated` | `camera`, `state` |
| `gamestate-updated` | `gamestate` |
| `worker-log` | `camera`, `stream` (`out`/`err`/`exit`), `line` |

## VMix-Client (`server/vmix.js`)

`VmixClient({host, port})` mit `call`, `state`, `overlayIn`, `overlayOut`, `cut`, `setText`, `setImage`, `pushGameState`. `pushGameState` schreibt `DownDistance` und `Penalty` in den angegebenen GT-Title.

## Python-Schnittstellen (Auszug)

| Funktion | Modul | Beschreibung |
|---|---|---|
| `compute_homography(world, image)` | `homography` | 3×3-Matrix Welt→Bild |
| `yard_line_quad`, `project_points` | `homography` | Linien-Geometrie projizieren |
| `field_mask(frame, lower, upper, k)` | `occlusion` | Rasen-Maske |
| `compose(frame, H, cfg, gamestate, ...)` | `render` | Komplettes Rendering |
| `render_field_graphics(...)` | `graphics` | Logos aufs Feld |
| `render_scorebug(...)` | `hud` | Scorebug/Strafen |
| `PitchTracker.update/reanchor` | `tracking` | Homographie-Tracking |
| `open_source`, `list_ndi_sources` | `io_sources` | Eingänge |
| `open_sink` | `io_sinks` | Ausgänge |
