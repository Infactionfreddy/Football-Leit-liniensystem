// Leichte Homographie fuer die BROWSER-PREVIEW (Feld -> Bild).
// Die massgebliche Berechnung passiert in Python (cv2.findHomography);
// hier reicht ein direkter DLT-Loeser fuer die Live-Vorschau der Yard-Linie.

// Loest A x = b (n x n) via Gauss-Elimination mit Teilpivotisierung.
function solveLinear(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col++) {
    let piv = col;
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(M[r][col]) > Math.abs(M[piv][col])) piv = r;
    }
    if (Math.abs(M[piv][col]) < 1e-12) throw new Error('Singulaere Matrix (Punkte kollinear?)');
    [M[col], M[piv]] = [M[piv], M[col]];
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const f = M[r][col] / M[col][col];
      for (let c = col; c <= n; c++) M[r][c] -= f * M[col][c];
    }
  }
  return M.map((row, i) => row[n] / row[i]);
}

// Homographie H (3x3, h33=1), die Weltpunkte (Yards) auf Bildpunkte (Pixel) abbildet.
// worldPoints/imagePoints: Arrays von [x,y], mind. 4 Korrespondenzen.
export function computeHomography(worldPoints, imagePoints) {
  if (worldPoints.length < 4 || worldPoints.length !== imagePoints.length) {
    throw new Error('Mindestens 4 gleich viele Welt-/Bildpunkte noetig');
  }
  // Normalgleichungen A^T A x = A^T b (erlaubt >4 Punkte, Least Squares).
  const rows = [];
  const rhs = [];
  for (let i = 0; i < worldPoints.length; i++) {
    const [wx, wy] = worldPoints[i];
    const [ix, iy] = imagePoints[i];
    rows.push([wx, wy, 1, 0, 0, 0, -wx * ix, -wy * ix]);
    rhs.push(ix);
    rows.push([0, 0, 0, wx, wy, 1, -wx * iy, -wy * iy]);
    rhs.push(iy);
  }
  const ncol = 8;
  const AtA = Array.from({ length: ncol }, () => new Array(ncol).fill(0));
  const Atb = new Array(ncol).fill(0);
  for (let r = 0; r < rows.length; r++) {
    for (let i = 0; i < ncol; i++) {
      Atb[i] += rows[r][i] * rhs[r];
      for (let j = 0; j < ncol; j++) AtA[i][j] += rows[r][i] * rows[r][j];
    }
  }
  const h = solveLinear(AtA, Atb);
  return [
    [h[0], h[1], h[2]],
    [h[3], h[4], h[5]],
    [h[6], h[7], 1],
  ];
}

// Projiziert einen Weltpunkt (Yards) auf Bildpixel.
export function project(H, wx, wy) {
  const d = H[2][0] * wx + H[2][1] * wy + H[2][2];
  return [
    (H[0][0] * wx + H[0][1] * wy + H[0][2]) / d,
    (H[1][0] * wx + H[1][1] * wy + H[1][2]) / d,
  ];
}

// Eckpunkte des Yard-Linien-Rechtecks im Bild (fuer die Preview).
export function projectYardLine(H, yard, fieldWidth, widthYards) {
  const half = widthYards / 2;
  return [
    project(H, yard - half, 0),
    project(H, yard + half, 0),
    project(H, yard + half, fieldWidth),
    project(H, yard - half, fieldWidth),
  ];
}
