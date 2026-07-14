// Minimaler VMix-Web-Controller-Client (HTTP-API, Standard-Port 8088).
// Doku: https://www.vmix.com/help/  ->  "Web Scripting / API"
// Beispiel-Aufruf:  http://<host>:8088/api/?Function=OverlayInput1In&Input=LINE-CAM1

export class VmixClient {
  constructor({ host = '127.0.0.1', port = 8088 } = {}) {
    this.base = `http://${host}:${port}/api/`;
  }

  async call(func, params = {}) {
    const url = new URL(this.base);
    url.searchParams.set('Function', func);
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));
    const res = await fetch(url, { method: 'GET' });
    if (!res.ok) throw new Error(`VMix ${func} -> HTTP ${res.status}`);
    return res.text();
  }

  // Kompletten Zustand als XML holen (Inputs, Overlays, Tally ...).
  async state() {
    const res = await fetch(this.base, { method: 'GET' });
    if (!res.ok) throw new Error(`VMix state -> HTTP ${res.status}`);
    return res.text();
  }

  // Convenience
  overlayIn(channel, input) {
    return this.call(`OverlayInput${channel}In`, { Input: input });
  }
  overlayOut(channel) {
    return this.call(`OverlayInput${channel}Out`);
  }
  cut(input) {
    return this.call('Cut', { Input: input });
  }

  // Text eines GT-Title-Feldes setzen (fuer Scorebug/Strafen in VMix statt im Feed).
  setText(input, selectedName, value) {
    return this.call('SetText', { Input: input, SelectedName: selectedName, Value: value });
  }

  // Bild eines GT-Title-Feldes setzen (z.B. Team-Logo im Scorebug).
  setImage(input, selectedName, value) {
    return this.call('SetImage', { Input: input, SelectedName: selectedName, Value: value });
  }

  // Kompletten Spielstand in einen GT-Title schreiben.
  async pushGameState(input, gs) {
    await this.setText(input, 'DownDistance', downDistanceText(gs));
    const pen = gs.penalty || {};
    await this.setText(input, 'Penalty', pen.active ? String(pen.text || '') : '');
  }
}

const ORD = { 1: '1st', 2: '2nd', 3: '3rd', 4: '4th' };
export function downDistanceText(gs) {
  if (!gs?.down) return '';
  const d = ORD[gs.down] || `${gs.down}th`;
  if (gs.goalToGo || gs.distance <= 0) return `${d} & Goal`;
  return `${d} & ${gs.distance}`;
}
