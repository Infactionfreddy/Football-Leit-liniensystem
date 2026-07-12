// Kalibrier-UI: Standbild laden, Referenzpunkte klicken, Homographie-Vorschau,
// Kalibrierung speichern, Linie live steuern.

const $ = (id) => document.getElementById(id);
const cv = $('cv');
const ctx = cv.getContext('2d');

let img = null;              // geladenes Standbild
let scale = 1;              // Anzeige- zu Bild-Skalierung
let points = [];           // { ix, iy, wx, wy } in Bild-Pixeln + Weltkoordinaten
let previewCorners = null; // Yard-Linien-Ecken aus /api/preview
let config = null;

// ---- WebSocket-Status ----
function connectWs() {
  const ws = new WebSocket(`ws://${location.host}`);
  ws.onopen = () => { $('conn').textContent = 'verbunden'; $('conn').classList.add('ok'); };
  ws.onclose = () => { $('conn').textContent = 'getrennt'; $('conn').classList.remove('ok'); setTimeout(connectWs, 1500); };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.type === 'worker-log') log(`[${m.camera}/${m.stream}] ${m.line.trim()}`);
  };
}

function log(line) {
  const el = $('log');
  el.textContent += line + '\n';
  el.scrollTop = el.scrollHeight;
}

function msg(text, kind = '') {
  const el = $('msg');
  el.textContent = text;
  el.className = 'hint ' + kind;
}

// ---- Config laden ----
async function loadConfig() {
  config = await (await fetch('/api/config')).json();
  const sel = $('camera');
  sel.innerHTML = '';
  for (const cam of config.cameras) {
    const o = document.createElement('option');
    o.value = cam.id; o.textContent = `${cam.name} (${cam.id}, ${cam.mode})`;
    sel.appendChild(o);
  }
  if (config.field?.width) $('fieldW').value = config.field.width;
  if (config.line?.widthYards) $('lineW').value = config.line.widthYards;
  if (config.line?.yardPosition != null) { $('yard').value = config.line.yardPosition; $('liveYard').value = config.line.yardPosition; }
  loadCameraCalibration();
}

function currentCamera() {
  return config.cameras.find((c) => c.id === $('camera').value);
}

function loadCameraCalibration() {
  points = [];
  const cam = currentCamera();
  const cal = cam?.calibration;
  if (cal?.imagePoints?.length) {
    for (let i = 0; i < cal.imagePoints.length; i++) {
      points.push({
        ix: cal.imagePoints[i][0], iy: cal.imagePoints[i][1],
        wx: cal.worldPoints[i][0], wy: cal.worldPoints[i][1],
      });
    }
  }
  renderPoints();
  draw();
}

// ---- Standbild ----
$('frame').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  img = new Image();
  img.onload = () => {
    scale = cv.width / img.width;
    cv.height = Math.round(img.height * scale);
    draw();
  };
  img.src = url;
});

// ---- Punkte setzen ----
cv.addEventListener('click', (e) => {
  const rect = cv.getBoundingClientRect();
  const dispX = (e.clientX - rect.left) * (cv.width / rect.width);
  const dispY = (e.clientY - rect.top) * (cv.height / rect.height);
  // In Bild-Pixel (Originalaufloesung) zuruecktransformieren.
  points.push({ ix: dispX / scale, iy: dispY / scale, wx: 0, wy: 0 });
  renderPoints();
  draw();
});

$('undo').onclick = () => { points.pop(); renderPoints(); draw(); };
$('clear').onclick = () => { points = []; previewCorners = null; renderPoints(); draw(); };

function renderPoints() {
  const tb = $('points').querySelector('tbody');
  tb.innerHTML = '';
  points.forEach((p, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i + 1}</td><td>${p.ix.toFixed(0)}, ${p.iy.toFixed(0)}</td>` +
      `<td><input type="number" step="0.5" value="${p.wx}" data-i="${i}" data-k="wx"></td>` +
      `<td><input type="number" step="0.5" value="${p.wy}" data-i="${i}" data-k="wy"></td>`;
    tb.appendChild(tr);
  });
  tb.querySelectorAll('input').forEach((inp) => {
    inp.onchange = () => { points[+inp.dataset.i][inp.dataset.k] = parseFloat(inp.value); };
  });
}

// ---- Zeichnen ----
function draw() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (img) ctx.drawImage(img, 0, 0, cv.width, cv.height);
  else { ctx.fillStyle = '#111'; ctx.fillRect(0, 0, cv.width, cv.height); ctx.fillStyle = '#555'; ctx.fillText('Standbild laden…', 20, 30); }

  // Referenzpunkte
  points.forEach((p, i) => {
    const x = p.ix * scale, y = p.iy * scale;
    ctx.fillStyle = '#2d7dff';
    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.fillText(String(i + 1), x + 7, y - 7);
  });

  // Yard-Linien-Vorschau (Ecken kommen in Bild-Pixeln vom Server)
  if (previewCorners) {
    ctx.beginPath();
    previewCorners.forEach(([px, py], i) => {
      const x = px * scale, y = py * scale;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,220,0,0.75)';
    ctx.fill();
  }
}

// ---- Preview / Speichern ----
$('preview').onclick = async () => {
  if (points.length < 4) return msg('Mindestens 4 Punkte nötig.', 'err');
  const body = {
    imagePoints: points.map((p) => [p.ix, p.iy]),
    worldPoints: points.map((p) => [p.wx, p.wy]),
    yard: parseFloat($('yard').value),
    fieldWidth: parseFloat($('fieldW').value),
    widthYards: parseFloat($('lineW').value),
  };
  const res = await fetch('/api/preview', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok) { previewCorners = null; draw(); return msg(data.error, 'err'); }
  previewCorners = data.corners;
  draw();
  msg('Homographie berechnet – gelbes Band = projizierte Yard-Linie.', 'ok');
};

$('save').onclick = async () => {
  const cam = currentCamera();
  const body = { imagePoints: points.map((p) => [p.ix, p.iy]), worldPoints: points.map((p) => [p.wx, p.wy]) };
  const res = await fetch(`/api/cameras/${cam.id}/calibration`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  msg(res.ok ? 'Kalibrierung gespeichert.' : 'Speichern fehlgeschlagen.', res.ok ? 'ok' : 'err');
};

// ---- Live-Steuerung ----
async function pushState() {
  const cam = currentCamera();
  await fetch(`/api/cameras/${cam.id}/state`, {
    method: 'PUT', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ enabled: $('enabled').checked, yardPosition: parseFloat($('liveYard').value) }),
  });
}
$('enabled').onchange = pushState;
$('liveYard').onchange = pushState;

$('startW').onclick = async () => {
  const cam = currentCamera();
  const r = await (await fetch(`/api/cameras/${cam.id}/worker/start`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ sink: 'ndi' }),
  })).json();
  log(`start ${cam.id}: ${JSON.stringify(r)}`);
};
$('stopW').onclick = async () => {
  const cam = currentCamera();
  const r = await (await fetch(`/api/cameras/${cam.id}/worker/stop`, { method: 'POST' })).json();
  log(`stop ${cam.id}: ${JSON.stringify(r)}`);
};

$('camera').onchange = loadCameraCalibration;

connectWs();
loadConfig();
