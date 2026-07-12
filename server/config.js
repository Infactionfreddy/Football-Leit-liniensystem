// Laden/Speichern der Config und des heissen Laufzeit-States.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const CONFIG_DIR = join(ROOT, 'config');
export const CONFIG_PATH = join(CONFIG_DIR, 'config.json');
export const EXAMPLE_PATH = join(CONFIG_DIR, 'example.config.json');

export async function loadConfig() {
  try {
    return JSON.parse(await readFile(CONFIG_PATH, 'utf8'));
  } catch (err) {
    if (err.code === 'ENOENT') {
      // Erststart: Beispiel als Basis nehmen (nicht ueberschreiben).
      return JSON.parse(await readFile(EXAMPLE_PATH, 'utf8'));
    }
    throw err;
  }
}

export async function saveConfig(config) {
  await mkdir(CONFIG_DIR, { recursive: true });
  await writeFile(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf8');
}

export function statePath(cameraId) {
  return join(CONFIG_DIR, `state.${cameraId}.json`);
}

// Der heisse State wird pro Frame vom Python-Worker gepollt.
export async function saveState(cameraId, state) {
  await mkdir(CONFIG_DIR, { recursive: true });
  await writeFile(statePath(cameraId), JSON.stringify(state, null, 2), 'utf8');
}

export async function loadState(cameraId, config) {
  try {
    return JSON.parse(await readFile(statePath(cameraId), 'utf8'));
  } catch {
    // Default aus der Config ableiten.
    return {
      enabled: true,
      yardPosition: config?.line?.yardPosition ?? 45.0,
      colorBGR: config?.line?.colorBGR ?? [0, 220, 255],
    };
  }
}

export function findCamera(config, cameraId) {
  return (config.cameras || []).find((c) => c.id === cameraId);
}

// Geteilter Spielstand (Down & Distance, Strafen, LOS/First-Down) fuer alle Kameras.
export const GAMESTATE_PATH = join(CONFIG_DIR, 'gamestate.json');

export async function loadGameState(config) {
  try {
    return JSON.parse(await readFile(GAMESTATE_PATH, 'utf8'));
  } catch {
    return config?.gameState ?? {
      possession: 'home', down: 1, distance: 10, goalToGo: false,
      losYard: 45.0, firstDownYard: 55.0, quarter: 1, clock: '15:00',
      penalty: { active: false, text: '', team: 'home' },
    };
  }
}

export async function saveGameState(gs) {
  await mkdir(CONFIG_DIR, { recursive: true });
  await writeFile(GAMESTATE_PATH, JSON.stringify(gs, null, 2), 'utf8');
}
