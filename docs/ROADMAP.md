# Roadmap

## Phase 0 — Scaffold (dieser Stand)
- [x] Zwei-Ebenen-Architektur (Node-Control + Python-Engine)
- [x] Config-/State-Schema
- [x] Homographie + Yard-Linie + Rasen-Okklusion (Offline auf Video-Datei)
- [x] Web-Kalibrier-UI (Punkte klicken, Preview)
- [x] VMix-API-Client (Grundfunktionen)
- [x] I/O-Abstraktion Datei/Webcam + NDI/DeckLink-Anbindung

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

## Phase 3 — Freie Kameras (Tracking)
- [ ] Optisches Tracking (Feature-Matching gegen Keyframe) in `homography.track_update()`
- [ ] Optional PTZ-Encoder-Anbindung (Kameramodell → H)
- [ ] Preset-Erkennung als Fallback

## Phase 4 — Produktion
- [ ] Ausfallsicherheit (Worker-Watchdog, Bypass auf Rohfeed)
- [ ] Mehr-Kamera-Orchestrierung + zentrales Dashboard
- [ ] Aufzeichnungs-/Replay-Kompatibilität
