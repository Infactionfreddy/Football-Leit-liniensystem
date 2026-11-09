# Entwicklung

[← Zurück zur README](../README.md)

## Lokale Umgebung

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r worker/requirements.txt -r app/requirements.txt
npm install
cp config/example.config.json config/config.json
npm run dev          # Server mit Auto-Reload
```

Die Engine ohne Hardware testen: Videodatei als Quelle, `--sink window` oder `--sink file`, optional `--loop`.

## Code-Struktur

- `server/` – ES-Module (`"type": "module"`); Routen in `index.js`, Dateizugriff in `config.js`.
- `web/` – statische Dateien ohne Build-Schritt.
- `worker/` – reine CV-Logik; `render.compose` ist die einzige Render-Quelle für CLI und App.
- `app/` – Qt: `EngineThread` je Kamera, `CameraManager` verteilt den globalen Spielstand, Styling in `theme.py` (QSS).
- Die App fügt `worker/` zum `sys.path` hinzu; Module dort verwenden daher flache Importe (`import homography`).

## Typische Änderungen

- Neues Overlay: in `worker/render.py` an der gewünschten Stelle der Reihenfolge einfügen (Logos → LOS → First-Down → Scorebug).
- Neuer Spielstandwert: `server/config.js` (Defaults), `web/` (Formular), `worker/hud.py`/`render.py`.
- Neuer Ausgang: Klasse in `worker/io_sinks.py` und in `open_sink` registrieren.
- Tracking-Verbesserung: `worker/tracking.py` (`reanchor`).

## Tests

Im Repository sind **keine automatisierten Tests** vorhanden. Empfehlung (Annahme/Vorschlag): `pytest` für `homography`, `occlusion`, `hud.down_distance_text` und `tracking` mit synthetischen Bildern; Node-Tests (`node --test`) für `server/homography.js` und `vmix.js`.

## Coding-Standards

Nicht festgelegt. Beobachtet: Python mit Type-Future-Import und Docstrings, Node mit ES-Modulen und kurzen Kommentaren. Kommentare und UI-Texte sind deutsch.

## Release-Ablauf

Nicht definiert (Version `0.1.0` in `package.json`). Vorschlag:

1. Version in `package.json` anheben.
2. Roadmap-Punkte abhaken.
3. Tag setzen (`git tag vX.Y.Z`) und Release auf GitHub erstellen.
4. Lizenzdatei ergänzen (in `package.json` steht MIT, eine LICENSE-Datei fehlt).
