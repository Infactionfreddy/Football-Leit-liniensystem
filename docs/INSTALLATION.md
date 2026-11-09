# Installation

[← Zurück zur README](../README.md)

## Voraussetzungen

| Komponente | Anforderung |
|---|---|
| Python | 3.x mit `venv` (genaue Mindestversion im Repo nicht festgelegt, Annahme: aktuelles 3.x, das PySide6 ≥ 6.6 unterstützt) |
| Node.js | ≥ 18 (`engines` in `package.json`; nutzt `fetch` und ES-Module) |
| Linux (Desktop-App) | `libegl1`, `libgl1`, `libxkbcommon0` |
| Optional NDI | `cyndilib` und NDI-Runtime (Annahme: separat vom NDI-SDK/Tools abhängig) |
| Optional DeckLink | Als Video-Device (`device:0`) oder per Blackmagic-Tools als NDI |

## Schritt für Schritt

1. Repository klonen und ins Verzeichnis wechseln.
2. Python-Umgebung anlegen:
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r worker/requirements.txt -r app/requirements.txt
   ```
3. Node-Abhängigkeiten installieren:
   ```bash
   npm install
   ```
4. Konfiguration anlegen:
   ```bash
   cp config/example.config.json config/config.json
   ```
5. Quelle bereitstellen, z. B. `recordings/cam1.mp4` (Pfad in der Kamera-Config anpassen).
6. Optional Linux-Bibliotheken: `sudo apt install libegl1 libgl1 libxkbcommon0`.
7. Optional NDI: `pip install cyndilib`.
8. Eigene Logos als PNG mit Alpha in `assets/` ablegen.

## Start

```bash
python app/main.py                # Desktop-App
npm start                         # Web-Control auf http://127.0.0.1:3000
npm run dev                       # Server mit --watch
python worker/line_engine.py --config config/config.json --camera cam1 --sink window
```

Vor dem ersten Rendern muss die Kamera kalibriert sein (mind. 4 Punkte), sonst bricht die CLI-Engine ab.

## Update

```bash
git pull
pip install -U -r worker/requirements.txt -r app/requirements.txt
npm install
```

Eigene `config/config.json` bleibt erhalten; neue Schlüssel ggf. aus `config/example.config.json` übernehmen.

## Deinstallation

- Laufende Prozesse beenden (Server, Worker, App).
- Verzeichnis samt `.venv` und `node_modules` löschen.
- Optional `cyndilib` und NDI-Runtime separat entfernen.
