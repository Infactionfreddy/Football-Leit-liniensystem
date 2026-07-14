# Roadmap

## Phase 0 — Scaffold (dieser Stand)
- [x] Zwei-Ebenen-Architektur (Node-Control + Python-Engine)
- [x] Config-/State-Schema
- [x] Homographie + Yard-Linie + Rasen-Okklusion (Offline auf Video-Datei)
- [x] Web-Kalibrier-UI (Punkte klicken, Preview)
- [x] VMix-API-Client (Grundfunktionen)
- [x] I/O-Abstraktion Datei/Webcam + NDI/DeckLink-Anbindung
- [x] Team-Logos aufs Feld (perspektivisch + Okklusion)
- [x] Game-State: Down & Distance, LOS (blau) + First-Down (gelb), Strafen-Banner, Scorebug
- [x] VMix-Push (SetText) für Scorebug/Strafen als Alternative zum Burn-in
- [x] Desktop-App (PySide6): Preview/Program-Monitore + Control-Menüs (VMix-artig), TAKE,
      Live-Kalibrierung per Klick, optionaler NDI-Programm-Ausgang
- [x] Gemeinsames Render-Modul für CLI + App (worker/render.py)
- [x] Professionelles VMix-artiges UI-Theme (app/theme.py): Tally-Header, Transition-Bar,
      Funktions-Bar, Vollbild-Programm-Ausgang, Tastatur-Shortcuts

## Phase 1 — Feste Kameras live
- [ ] NDI-Eingang real testen (cyndilib) mit einer Produktionskamera
- [ ] NDI-Ausgang `LINE-CAMx` in VMix einbinden, 4 Bestands-Feeds gegenprüfen
- [ ] Kalibrier-Workflow pro Preset (mehrere H pro Kamera speichern)
- [ ] Rasen-Maske pro Stadion/Licht kalibrierbar machen (HSV-Picker in UI)
- [ ] Genlock/Latenz messen

## Phase 2 — Robustheit & Bedienung
- [ ] Linie animieren (Ein-/Ausblenden), zweite Linie (Line of Scrimmage) in Blau
- [ ] Yard-Position per Tastatur/StreamDeck/VMix-Trigger setzen
- [ ] Tally-Auswertung: Linie nur auf der in VMix aktiven Kamera rendern
- [ ] Performance: `cv2.cuda`/GStreamer für 1080p50, Latenzbudget < 4 Frames

## Phase 3 — Freie Kameras / Programm-Feed (Tracking)
- [x] Bildbasiertes Tracking (ORB + RANSAC, `worker/tracking.py::PitchTracker`), Drift gemessen
- [ ] **Feldmodell-Reanchor** gegen Drift: Yard-/Seitenlinien pro Frame erkennen und absolut
      einpassen (`PitchTracker.reanchor`) — Kern für broadcast-robust
- [x] Mehrere Kamera-Eingaenge in der App umschaltbar + NDI-Quellen-Discovery + Tracking-Toggle
- [x] **Multi-Kamera gleichzeitig**: je Kamera eigene Pipeline/Tracker/NDI-Ausgang
      (`app/manager.py`), Multiview + Fokus, globaler Spielstand fuer alle Kameras
- [ ] Schnitt-Erkennung im Programm-Feed (Kamerawechsel) + Re-Init
- [ ] Optional PTZ-Encoder-Anbindung (Kameramodell → H)
- [ ] Tally-gesteuertes Umschalten pro-Kamera-Kalibrierung

## Phase 4 — Produktion
- [ ] Ausfallsicherheit (Worker-Watchdog, Bypass auf Rohfeed)
- [ ] Mehr-Kamera-Orchestrierung + zentrales Dashboard
- [ ] Aufzeichnungs-/Replay-Kompatibilität
