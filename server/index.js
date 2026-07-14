// Control-Plane: Express + WebSocket. Serviert die Kalibrier-UI, verwaltet Config/State,
// steuert die Python-Worker und bietet VMix-Anbindung.
import express from 'express';
import { WebSocketServer } from 'ws';
import { createServer } from 'node:http';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { loadConfig, saveConfig, saveState, loadState, findCamera,
  loadGameState, saveGameState } from './config.js';
import { computeHomography, projectYardLine } from './homography.js';
import { VmixClient } from './vmix.js';
import { startWorker, stopWorker, listRunning } from './workers.js';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const HOST = process.env.HOST || '127.0.0.1';
const PORT = Number(process.env.PORT || 3000);

const app = express();
app.use(express.json({ limit: '2mb' }));
app.use(express.static(join(ROOT, 'web')));

const clients = new Set();
function broadcast(msg) {
  const data = JSON.stringify(msg);
  for (const ws of clients) if (ws.readyState === 1) ws.send(data);
}

// ---- Config ----
app.get('/api/config', async (_req, res) => {
  res.json(await loadConfig());
});

app.put('/api/config', async (req, res) => {
  await saveConfig(req.body);
  broadcast({ type: 'config-updated' });
  res.json({ ok: true });
});

// Kalibrierpunkte einer Kamera speichern.
app.put('/api/cameras/:id/calibration', async (req, res) => {
  const config = await loadConfig();
  const cam = findCamera(config, req.params.id);
  if (!cam) return res.status(404).json({ error: 'camera not found' });
  cam.calibration = { imagePoints: req.body.imagePoints, worldPoints: req.body.worldPoints };
  await saveConfig(config);
  broadcast({ type: 'config-updated' });
  res.json({ ok: true });
});

// Homographie-Preview: Bild-Eckpunkte der Yard-Linie zurueckgeben.
app.post('/api/preview', async (req, res) => {
  try {
    const { imagePoints, worldPoints, yard, fieldWidth, widthYards } = req.body;
    const H = computeHomography(worldPoints, imagePoints);
    const corners = projectYardLine(H, yard, fieldWidth, widthYards ?? 0.35);
    res.json({ H, corners });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// ---- Heisser Linien-State (an/aus, Yard, Farbe) ----
app.get('/api/cameras/:id/state', async (req, res) => {
  const config = await loadConfig();
  res.json(await loadState(req.params.id, config));
});

app.put('/api/cameras/:id/state', async (req, res) => {
  const config = await loadConfig();
  const cur = await loadState(req.params.id, config);
  const next = { ...cur, ...req.body };
  await saveState(req.params.id, next);
  broadcast({ type: 'state-updated', camera: req.params.id, state: next });
  res.json(next);
});

// ---- Geteilter Spielstand (Down & Distance, Strafen, LOS/First-Down) ----
app.get('/api/gamestate', async (_req, res) => {
  const config = await loadConfig();
  res.json(await loadGameState(config));
});

app.put('/api/gamestate', async (req, res) => {
  const config = await loadConfig();
  const cur = await loadGameState(config);
  // Flach mergen, penalty-Objekt separat mergen.
  const next = { ...cur, ...req.body };
  if (req.body.penalty) next.penalty = { ...(cur.penalty || {}), ...req.body.penalty };
  await saveGameState(next);
  broadcast({ type: 'gamestate-updated', gamestate: next });

  // Optional: dieselben Werte an einen VMix-GT-Title pushen.
  const push = config?.overlays?.vmixPush;
  if (push?.enabled && push.titleInput) {
    try {
      await new VmixClient(req.body.vmix || {}).pushGameState(push.titleInput, next);
    } catch (err) {
      console.warn('VMix-Push fehlgeschlagen:', err.message);
    }
  }
  res.json(next);
});

// Convenience: Down erhoehen / neue Serie / Strafe umschalten.
app.post('/api/gamestate/action', async (req, res) => {
  const config = await loadConfig();
  const gs = await loadGameState(config);
  const { action } = req.body || {};
  if (action === 'nextDown') gs.down = Math.min(4, (gs.down || 1) + 1);
  else if (action === 'firstDown') { gs.down = 1; gs.distance = 10; gs.losYard = gs.firstDownYard; gs.firstDownYard = gs.firstDownYard + 10; }
  else if (action === 'togglePenalty') gs.penalty = { ...(gs.penalty || {}), active: !gs.penalty?.active };
  await saveGameState(gs);
  broadcast({ type: 'gamestate-updated', gamestate: gs });
  res.json(gs);
});

// ---- Worker-Steuerung ----
app.get('/api/workers', (_req, res) => res.json({ running: listRunning() }));

app.post('/api/cameras/:id/worker/start', (req, res) => {
  const r = startWorker(req.params.id, req.body || {}, (cam, stream, line) =>
    broadcast({ type: 'worker-log', camera: cam, stream, line }));
  res.json(r);
});

app.post('/api/cameras/:id/worker/stop', (req, res) => {
  res.json(stopWorker(req.params.id));
});

// ---- VMix ----
app.post('/api/vmix/call', async (req, res) => {
  try {
    const { host, port, func, params } = req.body;
    const vmix = new VmixClient({ host, port });
    res.json({ ok: true, result: await vmix.call(func, params) });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

app.get('/api/health', (_req, res) =>
  res.json({ ok: true, running: listRunning() }));

const server = createServer(app);
const wss = new WebSocketServer({ server });
wss.on('connection', (ws) => {
  clients.add(ws);
  ws.on('close', () => clients.delete(ws));
});

server.listen(PORT, HOST, () => {
  console.log(`Control-Server: http://${HOST}:${PORT}`);
  console.log(`Aktive Worker: ${listRunning().join(', ') || '(keine)'}`);
});

export { app, server };
