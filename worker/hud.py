"""Bildschirm-Overlays (nicht aufs Feld gewarpt): Scorebug mit Down & Distance,
Ballbesitz und Strafen-Banner. Wird in denselben Feed gebrannt.

Nutzt Pillow fuer sauberen (auch Umlaut-)Text; faellt sonst auf cv2.putText zurueck.
"""
from __future__ import annotations

import numpy as np
import cv2

try:
    from PIL import Image, ImageDraw, ImageFont
    _HAS_PIL = True
except ImportError:  # pragma: no cover
    _HAS_PIL = False

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_font_cache = {}


def _font(size):
    if not _HAS_PIL:
        return None
    if size in _font_cache:
        return _font_cache[size]
    f = None
    for p in _FONT_CANDIDATES:
        try:
            f = ImageFont.truetype(p, size)
            break
        except OSError:
            continue
    if f is None:
        f = ImageFont.load_default()
    _font_cache[size] = f
    return f


_ORD = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def down_distance_text(gs):
    """z.B. '1st & 10' oder '3rd & Goal'."""
    down = gs.get("down")
    dist = gs.get("distance")
    if not down:
        return ""
    d = _ORD.get(int(down), f"{down}th")
    if gs.get("goalToGo") or (isinstance(dist, (int, float)) and dist <= 0):
        return f"{d} & Goal"
    return f"{d} & {dist}"


def _rounded(draw, xy, r, fill):
    draw.rounded_rectangle(xy, radius=r, fill=fill)


def render_scorebug(frame_bgr, gamestate, teams, cfg):
    """Scorebug unten-links: Heim/Gast-Kuerzel + Down & Distance. Optional Strafen-Banner."""
    if not _HAS_PIL:
        return _render_scorebug_cv(frame_bgr, gamestate, teams)

    Hh, Ww = frame_bgr.shape[:2]
    overlay = Image.new("RGBA", (Ww, Hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    home = teams.get("home", {})
    away = teams.get("away", {})
    poss = gamestate.get("possession", "home")

    def bgr2rgb(c, default):
        c = c or default
        return (int(c[2]), int(c[1]), int(c[0]))

    home_col = bgr2rgb(home.get("colorBGR"), [80, 80, 80])
    away_col = bgr2rgb(away.get("colorBGR"), [120, 120, 120])

    x, y, h = 40, Hh - 90, 46
    fL, fS = _font(28), _font(18)

    def chip(px, w, color, text, active):
        _rounded(d, [px, y, px + w, y + h], 8, color + (235,))
        if active:
            d.rectangle([px, y, px + 6, y + h], fill=(255, 220, 0, 255))
        d.text((px + 16, y + 9), text, font=fL, fill=(255, 255, 255, 255))
        return px + w + 8

    nx = chip(x, 120, home_col, home.get("abbr", "HOME"), poss == "home")
    nx = chip(nx, 120, away_col, away.get("abbr", "AWAY"), poss == "away")

    dd = down_distance_text(gamestate)
    if dd:
        w = 150
        _rounded(d, [nx, y, nx + w, y + h], 8, (18, 18, 22, 235))
        d.text((nx + 16, y + 9), dd, font=fL, fill=(255, 220, 0, 255))

    # Strafen-Banner (mittig oben), nur wenn aktiv
    pen = gamestate.get("penalty") or {}
    if pen.get("active") and pen.get("text"):
        txt = "STRAFE — " + str(pen["text"])
        tw = d.textbbox((0, 0), txt, font=fS)[2] + 40
        bx = (Ww - tw) // 2
        _rounded(d, [bx, 30, bx + tw, 30 + 40], 8, (200, 30, 30, 235))
        d.text((bx + 20, 39), txt, font=fS, fill=(255, 255, 255, 255))

    base = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
    out = Image.alpha_composite(base, overlay).convert("RGB")
    return cv2.cvtColor(np.array(out), cv2.COLOR_RGB2BGR)


def _render_scorebug_cv(frame_bgr, gamestate, teams):
    """Fallback ohne Pillow (ASCII, schlichter)."""
    f = frame_bgr.copy()
    Hh = f.shape[0]
    dd = down_distance_text(gamestate)
    label = f"{teams.get('home',{}).get('abbr','HOME')} vs {teams.get('away',{}).get('abbr','AWAY')}  {dd}"
    cv2.rectangle(f, (30, Hh - 70), (30 + 9 * len(label) + 20, Hh - 30), (20, 20, 22), -1)
    cv2.putText(f, label, (44, Hh - 42), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
    pen = gamestate.get("penalty") or {}
    if pen.get("active") and pen.get("text"):
        cv2.putText(f, "STRAFE: " + str(pen["text"]), (44, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 60, 220), 2)
    return f
