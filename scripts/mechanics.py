# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""mechanics.py - the small noises a player and an instrument make that a sample library does not contain.

A recording of a real player is never silent between notes: a bow touches the string, a key bottoms out, the breath
starts before the tone, a damper drops on the piano. A sampled GM patch gives none of that, and the digital silence
between notes is one of the strongest "this is a library" cues.

This module adds noise bursts at the note's onset and offset, filtered into the band where that mechanism lives, from a
table in the mix preset (`render.mechanics`): nothing about a particular instrument is decided in code.

    import mechanics
    y = mechanics.add(x, track, events, sr=44100, seed=7)

The table: {enabled, default_class, classes: {<class>: {onset: {...}, offset: {...}}}} and each of onset/offset is
{gain_db, lo_hz, hi_hz, ms, shape}. A track or instrument preset selects its class with `mechanics_class`.
"""
import numpy as np
from scipy import signal


def _table():
    """The mechanics table: the mix preset's `render.mechanics` over the schema defaults for the render section."""
    import mix_schema
    import presets
    try:
        mx = mix_schema.with_defaults(presets.mix())
    except Exception:
        mx = mix_schema.with_defaults({})
    return ((mx.get('render') or {}).get('mechanics') or {})


def _class_for(track, cfg):
    """The class a track's instrument belongs to, from the preset's `class_by_instrument` table (prefix match)."""
    inst = str(track.get('instrument') or track.get('preset') or '').lower()
    if ':' in inst:
        inst = inst.split(':', 1)[0]
    for key, cls in (cfg.get('class_by_instrument') or {}).items():
        if inst.startswith(key):
            return cls
    return None


def _burst(rng, sr, spec, level=1.0):
    """One short filtered noise burst with a Hann envelope, or None when the spec is switched off."""
    ms = float(spec.get('ms', 0.0))
    gain_db = float(spec.get('gain_db', -96.0))
    if ms <= 0 or gain_db <= -95.0:
        return None
    n = max(2, int(ms / 1000.0 * sr))
    lo, hi = float(spec.get('lo_hz', 200.0)), float(spec.get('hi_hz', 6000.0))
    lo = max(20.0, min(lo, sr * 0.45))
    hi = max(lo * 1.05, min(hi, sr * 0.45))
    sos = signal.butter(2, [lo, hi], 'band', fs=sr, output='sos')
    noise = signal.sosfilt(sos, rng.standard_normal(n))
    shape = str(spec.get('shape', 'hann'))
    env = np.hanning(n) if shape == 'hann' else np.exp(-np.linspace(0.0, 4.0, n))
    return (noise * env * 10 ** (gain_db / 20.0) * float(level)).astype(np.float32)


def add(x, track, events, sr=44100, seed=0):
    """Add the mechanism noise of this instrument to a rendered stem. Returns a new array (never in place)."""
    cfg = _table()
    if not cfg.get('enabled', True) or not events:
        return x
    classes = cfg.get('classes') or {}
    name = str(track.get('mechanics_class') or _class_for(track, cfg) or cfg.get('default_class') or 'keys')
    spec = classes.get(name)
    if not spec:
        return x
    level = float(cfg.get('level_db', 0.0)) / 20.0
    level = 10.0 ** level
    rng = np.random.default_rng(int(seed) + 104729)
    out = np.array(x, dtype=np.float32, copy=True)
    if out.ndim == 1:
        out = out[:, None]
    n = len(out)
    for e in events:
        vel = float(e.get('v', 90)) / 127.0
        # humanized events carry 'd' (beats) or 'dur' (seconds); accept both so an offset never lands on the onset
        dur = float(e.get('dur', e.get('d', 0.0)) or 0.0)
        for key, at in (('onset', float(e['t'])), ('offset', float(e['t']) + dur)):
            spec_k = spec.get(key) or {}
            i0 = max(0, int(at * sr))
            if i0 >= n or _burst(rng, sr, spec_k, 0.0) is None:
                continue
            gain = level * (0.35 + 0.65 * vel)
            for c in range(out.shape[1]):    # independent per channel: the mechanism is not one mono source
                seg = _burst(rng, sr, spec_k, gain)[:max(0, n - i0)]
                if len(seg):
                    out[i0:i0 + len(seg), c] += seg
    return out
