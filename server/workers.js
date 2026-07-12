// Startet/ueberwacht pro Kamera einen Python-Linien-Worker.
import { spawn } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const ENGINE = join(ROOT, 'worker', 'line_engine.py');

const running = new Map(); // cameraId -> child process

function pythonBin() {
  return process.env.PYTHON_BIN || 'python3';
}

export function isRunning(cameraId) {
  return running.has(cameraId);
}

export function listRunning() {
  return [...running.keys()];
}

export function startWorker(cameraId, { sink = 'ndi', sourceOverride } = {}, onLog = () => {}) {
  if (running.has(cameraId)) return { ok: false, reason: 'already-running' };

  const args = [ENGINE, '--config', join(ROOT, 'config', 'config.json'),
    '--camera', cameraId, '--sink', sink];
  if (sourceOverride) args.push('--source-override', sourceOverride);

  const child = spawn(pythonBin(), args, { cwd: ROOT });
  running.set(cameraId, child);

  child.stdout.on('data', (d) => onLog(cameraId, 'out', d.toString()));
  child.stderr.on('data', (d) => onLog(cameraId, 'err', d.toString()));
  child.on('exit', (code) => {
    running.delete(cameraId);
    onLog(cameraId, 'exit', `Worker beendet (code ${code})`);
  });
  return { ok: true };
}

export function stopWorker(cameraId) {
  const child = running.get(cameraId);
  if (!child) return { ok: false, reason: 'not-running' };
  child.kill('SIGTERM');
  return { ok: true };
}
