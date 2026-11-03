"""room.py - a room as data: shoebox geometry, surface materials, image-source reflections and the late field's shape.

Nothing is decided here. A space preset says how big the room is, where the listener stands, which materials the six
surfaces are made of, how many reflections to keep and how the late tail is spread; this module turns that into taps
(delay, direction, one absorption filter each) that `binaural.reflections` renders through the measured head filters.

    geom = presets.find_space('concert_hall')['geometry']
    taps = room.taps(geom, azimuth_deg=-30, elevation_deg=10, distance_m=4.0)

Image-source method (Allen & Berkley 1979): every wall reflects the source into an image; the listener hears the image
through the wall's absorption, arriving from that image's direction. We keep the `max_taps` strongest images and stop
below `min_level_db` re the direct sound, because a dense uncountable tail is what the late field is for.

What is not modelled: diffusion from surface roughness (a specular image cannot scatter), diffraction around the
listener's own body, and coupling through open doors. `scattering` in the preset is recorded and used by the late
field's direction spread, not by the taps.
"""
import os
import sys

import numpy as np
from scipy import signal

C = 343.0
BANDS_HZ = (125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
SR = 44100


def material_table(name=None):
    """The material library: presets/materials/<name>.json (skill, then project). Raises on an unknown set."""
    here = os.path.dirname(os.path.abspath(__file__))
    scripts = os.path.dirname(here)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import presets
    table = presets.load('materials')
    key = str(name or 'room_materials').lower().strip().replace(' ', '_')
    if key not in table:
        raise KeyError(f'no materials preset "{key}". Known: {sorted(table)}. '
                       f'Add one in presets/materials/{key}.json')
    return table[key]


def coefficients(materials_doc, surface):
    """The octave absorption coefficients of a named surface, in the table's band order."""
    surfaces = {k.lower(): v for k, v in (materials_doc.get('surfaces') or {}).items()}
    name = str(surface or '').lower()
    if name not in surfaces:
        raise KeyError(f'material "{surface}" is not in the materials preset; known: {sorted(surfaces)}')
    coeff = [float(x) for x in surfaces[name]]
    if len(coeff) != len(materials_doc.get('bands_hz') or BANDS_HZ):
        raise ValueError(f'material "{surface}" needs one coefficient per band')
    return np.array(coeff, float)


def absorption_fir(coeffs, bands=BANDS_HZ, sr=SR, taps=129):
    """A linear-phase FIR whose magnitude is the *amplitude* reflection coefficient sqrt(1 - absorption) at each
    octave centre, interpolated in log frequency. Applied once per bounce, so two bounces give (1-a) power, which is
    what Sabine's absorption area means."""
    refl = np.sqrt(np.clip(1.0 - np.asarray(coeffs, float), 0.0, 1.0))
    nyq = sr / 2.0
    freqs = np.concatenate([[0.0], np.asarray(bands, float) / nyq, [1.0]])
    gains = np.concatenate([[refl[0]], refl, [refl[-1]]])
    freqs = np.clip(freqs, 0.0, 1.0)
    return signal.firwin2(taps, freqs, gains, window='hann')


def _images(n, size, source):
    """Image coordinate along one axis and how many bounces it took, for image index n (Allen & Berkley)."""
    return n * size + (source if n % 2 == 0 else size - source), abs(n)


def taps(geom, azimuth_deg=0.0, elevation_deg=0.0, distance_m=2.0, sr=SR):
    """[(delay_ms, azimuth, elevation, distance_m, coefficients)] for a shoebox room.

    `geom`: width_m, depth_m, height_m (the box is 0..W, 0..D, 0..H), listener {x,y,z} inside it, materials
    {floor, ceiling, walls}, material_set (a presets/materials name), max_order, max_taps, min_level_db.
    The source sits at the track's own azimuth/elevation/distance from the listener, so a score keeps talking about
    where a part is, while the room decides when its reflections arrive.
    """
    if not geom:
        return []
    w = float(geom.get('width_m', 10.0))
    d = float(geom.get('depth_m', 12.0))
    h = float(geom.get('height_m', 5.0))
    lis = geom.get('listener') or {}
    lx, ly, lz = float(lis.get('x', w / 2.0)), float(lis.get('y', 0.3 * d)), float(lis.get('z', 1.5))
    az, el = np.radians(float(azimuth_deg)), np.radians(float(elevation_deg))
    dist = max(0.2, float(distance_m))
    sx = lx + dist * np.cos(el) * np.sin(az)
    sy = ly + dist * np.cos(el) * np.cos(az)
    sz = np.clip(lz + dist * np.sin(el), 0.05, h - 0.05)
    sx = float(np.clip(sx, 0.05, w - 0.05))
    sy = float(np.clip(sy, 0.05, d - 0.05))

    table = material_table(geom.get('material_set'))
    bands = table.get('bands_hz') or list(BANDS_HZ)
    mats = geom.get('materials') or {}
    a_floor = coefficients(table, mats.get('floor', 'wood'))
    a_ceil = coefficients(table, mats.get('ceiling', 'plaster'))
    a_wall = coefficients(table, mats.get('walls', 'plaster'))

    order = max(0, int(geom.get('max_order', 2)))
    direct = np.sqrt((sx - lx) ** 2 + (sy - ly) ** 2 + (sz - lz) ** 2)
    out = []
    for i in range(-order, order + 1):
        ix, nx = _images(i, w, sx)
        for j in range(-order, order + 1):
            iy, ny = _images(j, d, sy)
            for k in range(-order, order + 1):
                if i == 0 and j == 0 and k == 0:
                    continue
                iz, nz = _images(k, h, sz)
                path = np.sqrt((ix - lx) ** 2 + (iy - ly) ** 2 + (iz - lz) ** 2)
                if path <= direct + 1e-6:
                    continue
                coeff = np.ones(len(bands))
                # two side walls, front+rear wall, then floor OR ceiling (k's sign says which)
                coeff *= np.power(np.sqrt(np.clip(1 - a_wall, 0, 1)), nx)
                coeff *= np.power(np.sqrt(np.clip(1 - a_wall, 0, 1)), ny)
                coeff *= np.power(np.sqrt(np.clip(1 - (a_ceil if k > 0 else a_floor), 0, 1)), nz)
                level = float(np.sqrt(np.mean(coeff ** 2))) * direct / path
                out.append(dict(delay_ms=(path - direct) / C * 1000.0, distance_m=float(path),
                                azimuth=float(np.degrees(np.arctan2(ix - lx, iy - ly))),
                                elevation=float(np.degrees(np.arcsin(np.clip((iz - lz) / path, -1, 1)))),
                                coeffs=coeff, level=level))
    if not out:
        return []
    floor_db = float(geom.get('min_level_db', -30.0))
    out.sort(key=lambda t: t['level'], reverse=True)
    kept = [t for t in out if 20 * np.log10(max(t['level'], 1e-9)) >= floor_db]
    return kept[:max(1, int(geom.get('max_taps', 8)))]


def late_ir(cfg, sr=SR):
    """The late field's impulse response: one decorrelated noise tail, exponentially decaying per octave band, with the
    high bands dying `hf_decay` times faster (air and surface absorption both act that way). Seeded, so a render is
    repeatable.

    cfg: rt60_s, hf_decay, bands_hz, seed, rise_s (the tail builds for one mean free path instead of starting at full
    level, which is what a room does).
    """
    rt60 = max(0.05, float(cfg.get('rt60_s', 1.6)))
    hf = float(np.clip(cfg.get('hf_decay', 0.55), 0.05, 1.5))
    bands = cfg.get('bands_hz') or list(BANDS_HZ)
    n = int(min(12.0, rt60 * 1.6) * sr)
    rng = np.random.default_rng(int(cfg.get('seed', 7)))
    noise = rng.standard_normal(n)
    t = np.arange(n) / sr

    def band(sig, lo, hi):
        sos = signal.butter(2, [max(20.0, lo), min(sr * 0.45, hi)], 'band', fs=sr, output='sos')
        return signal.sosfilt(sos, sig)

    edges = [0.0] + list(bands) + [sr / 2.0]
    ir = np.zeros(n)
    for b in range(len(bands)):
        lo, hi = max(20.0, edges[b]), min(sr * 0.45, edges[b + 1])
        if hi - lo < 20.0:
            continue
        decay = rt60 * (hf ** min(3, b / 2.0))          # lows ring longest
        env = np.exp(-6.9078 * t / max(0.05, decay))
        ir += band(noise, lo, hi) * env
    rise = max(0.0, float(cfg.get('rise_s', 0.0)))
    if rise > 0:
        ir *= np.clip(t / rise, 0.0, 1.0) ** 0.5
    ir /= np.sqrt(np.mean(ir ** 2)) + 1e-12
    return ir.astype(np.float32)


def directions(cfg):
    """Where the late field arrives from: an explicit list, or `count` directions spread over `spread_deg` around the
    source's side, plus the rear and above. The listener's own direction is never used: a tail from the source's exact
    location is the classic in-head failure."""
    fixed = cfg.get('directions_deg')
    if fixed:
        return [(float(a), float(e)) for a, e in fixed]
    count = max(2, int(cfg.get('count', 6)))
    spread = float(cfg.get('spread_deg', 60.0))
    base = float(cfg.get('bias_azimuth_deg', 0.0))
    out = []
    for i in range(count):
        frac = (i / max(1, count - 1)) - 0.5
        az = base + frac * 2.0 * spread
        el = 20.0 if i % 3 == 1 else (-15.0 if i % 3 == 2 else 0.0)
        out.append((float(np.clip(az, -179.0, 179.0)), el))
    return out
