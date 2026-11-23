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

"""calls.py - any animal's call written as data: the `animal_call` environment primitive.

A call is a source and a filter (Fant 1960; for other mammals Taylor & Reby 2010): something vibrates (vocal folds,
a syrinx, a frog's larynx) and a tube colours it. Nothing here knows a species. A preset says:

  elements   the sounds the animal makes, each a pitch contour with a duration and a source quality
  sequence   the order they come in, with repeat ranges: the song or the call
  tract_cm   the length of the tube after the source; its resonances are (2k - 1) c / (4 L) (Fitch 1997)
  bouts_per_min, individuals   how often, and how many animals

Source qualities are the nonlinear phenomena of real voices (Wilden, Herzel, Peters & Tembrock 1998):
`subharmonic` (period doubling), `biphonation` (a second, independent pitch), `noise` (irregular, chaotic vibration)
and `jump` (a sudden register break). `pulse_hz` chops the sound into pulses, which is how frogs, purrs, growls and
rattles are built; pulse rates follow temperature through `rate_per_c` (cold-blooded callers).

    python scripts/environment.py --call owl_hoot --seconds 12 --out owl.wav
"""
import inspect

import numpy as np
from scipy import signal
from scipy.interpolate import PchipInterpolator

SR = 44100
ELEMENT_KEYS = {'f0_hz', 'ms', 'harmonics', 'rolloff', 'noise', 'subharmonic', 'biphonation', 'jump', 'pulse_hz',
                'pulse_duty', 'vibrato_hz', 'vibrato_cents', 'attack', 'release', 'level_db'}
PRESET_ONLY = {'name', 'kind', 'character', 'sources', 'note', 'notes', '_source'}   # what a call preset says about itself
DEFAULT_ELEMENTS = {'note': dict(f0_hz=[[0.0, 900.0], [0.4, 1250.0], [1.0, 820.0]], ms=[180.0, 260.0], harmonics=4)}


def tube_formants(length_cm, sr=SR, count=5, c=None):
    """Resonances of a tube closed at the source and open at the mouth: (2k - 1) c / (4 L), c of the active medium."""
    if c is None:
        from phys_core import medium
        c = medium.speed_of_sound()
    if not length_cm or float(length_cm) <= 0:
        return []
    out = [(2 * k - 1) * float(c) / (4.0 * float(length_cm) / 100.0) for k in range(1, int(count) + 1)]
    return [f for f in out if f < 0.45 * sr]


def _pair(v):
    return (float(v[0]), float(v[1])) if isinstance(v, (list, tuple)) else (float(v), float(v))


def _contour(f0, m):
    """Hz per sample from a number or [[position 0..1, Hz], ...]; smooth and without overshoot, on a log scale."""
    if not isinstance(f0, (list, tuple)):
        return np.full(m, float(f0))
    pts = sorted((float(p), float(h)) for p, h in f0)
    if len(pts) == 1:
        return np.full(m, pts[0][1])
    pos, hz = np.array([p for p, _ in pts]), np.array([h for _, h in pts])
    x = np.clip(np.linspace(0.0, 1.0, m), pos[0], pos[-1])
    return np.exp(PchipInterpolator(pos, np.log(hz))(x))


def element(spec, sr, rng, scale=1.0, rate=1.0):
    """One sound of a call. `scale` is this animal's own pitch (a bigger one is lower), `rate` its pulse-rate factor."""
    lo, hi = _pair(spec.get('ms', 200.0))
    m = max(32, int(rng.uniform(lo, hi) / 1000.0 * sr))
    x = np.arange(m) / m
    t = np.arange(m) / float(sr)
    f0 = _contour(spec['f0_hz'], m) * float(scale)
    if spec.get('jump'):                                   # a register break: the pitch steps, it does not glide
        at, ratio = spec['jump']
        f0 = np.where(x >= float(at), f0 * float(ratio), f0)
    if spec.get('vibrato_hz'):
        f0 = f0 * 2.0 ** (float(spec.get('vibrato_cents', 30.0)) / 1200.0 * np.sin(2 * np.pi * float(spec['vibrato_hz']) * t))
    z = float(np.clip(spec.get('noise', 0.0), 0.0, 1.0))
    if z > 0:                                              # irregular vibration: the period itself wanders
        wander = signal.sosfilt(signal.butter(1, min(0.4 * sr, 0.5 * float(np.mean(f0))), fs=sr, output='sos'),
                                rng.standard_normal(m))
        f0 = f0 * np.maximum(1.0 + 0.6 * z * wander / (np.abs(wander).max() + 1e-12), 0.2)
    f0 = np.minimum(f0, 0.45 * sr)
    phase = 2 * np.pi * np.cumsum(f0) / sr
    roll = float(spec.get('rolloff', 1.2))
    top = max(1, min(int(spec.get('harmonics', 6)), int(0.45 * sr / float(f0.max()))))
    src = sum(np.sin(h * phase) / h ** roll for h in range(1, top + 1))
    sub = float(spec.get('subharmonic', 0.0))
    if sub > 0:                                            # period doubling: energy halfway between the harmonics
        src = src + sub * sum(np.sin(0.5 * h * phase) / (0.5 * h) ** roll for h in range(1, 2 * top, 2)) / 2.0 ** roll
    ratio = float(spec.get('biphonation', 0.0))
    if ratio > 0:                                          # a second source at an unrelated pitch
        src = src + 0.7 * sum(np.sin(h * ratio * phase) / h ** roll
                              for h in range(1, top + 1) if h * ratio * float(f0.max()) < 0.45 * sr)
    if z > 0:
        hiss = rng.standard_normal(m)
        src = (1.0 - z) * src + z * hiss * (np.sqrt(np.mean(src ** 2)) / (np.sqrt(np.mean(hiss ** 2)) + 1e-12))
    if spec.get('pulse_hz'):
        duty = float(np.clip(spec.get('pulse_duty', 0.5), 0.05, 1.0))
        frac = (float(spec['pulse_hz']) * float(rate) * t) % 1.0
        src = src * np.where(frac < duty, 0.5 - 0.5 * np.cos(2 * np.pi * frac / duty), 0.0)
    att, rel = max(float(spec.get('attack', 0.15)), 1e-3), max(float(spec.get('release', 0.3)), 1e-3)
    env = np.sin(0.5 * np.pi * np.clip(x / att, 0, 1)) ** 2 * np.sin(0.5 * np.pi * np.clip((1.0 - x) / rel, 0, 1)) ** 2
    return src * env * 10.0 ** (float(spec.get('level_db', 0.0)) / 20.0)


def one_call(elements, sequence, gap_ms, sr, rng, scale=1.0, rate=1.0, formants=(), formant_q=6.0, formant_mix=0.7):
    """One whole call or song phrase of one animal: its elements in order, then the tube."""
    parts = []
    glo, ghi = _pair(gap_ms)
    for item in sequence:
        name, lo, hi = (item, 1, 1) if isinstance(item, str) else (item[0], int(item[1]), int(item[-1]))
        for _ in range(int(rng.integers(lo, hi + 1))):
            parts.append(element(elements[name], sr, rng, scale, rate))
            parts.append(np.zeros(int(rng.uniform(glo, ghi) / 1000.0 * sr)))
    y = np.concatenate(parts[:-1]) if parts else np.zeros(0)
    if len(y) and formants:
        wet = np.zeros(len(y))
        for f in formants:
            if 20.0 < f * scale < 0.45 * sr:               # a smaller animal has a shorter tube as well
                b, a = signal.iirpeak(f * scale, float(formant_q), fs=sr)
                wet += signal.lfilter(b, a, y)
        y = (1.0 - float(formant_mix)) * y + float(formant_mix) * wet
    peak = float(np.abs(y).max()) if len(y) else 0.0
    return y / peak if peak > 0 else y


def problems(layer):
    """What is wrong with an animal_call layer or call preset (a dict): [] when it can be rendered."""
    out = []
    cfg = dict(layer)
    if cfg.get('call'):
        import presets
        known = presets.load('calls')
        if cfg['call'] not in known:
            return [f'call "{cfg["call"]}" is not a calls preset. Known: {", ".join(sorted(known)) or "none"}']
        cfg = dict({k: v for k, v in known[cfg['call']].items() if k not in PRESET_ONLY}, **layer)
    elements = cfg.get('elements') or DEFAULT_ELEMENTS
    if not isinstance(elements, dict) or not elements:
        return ['elements must be an object of named sounds, each with f0_hz']
    for name, e in elements.items():
        if not isinstance(e, dict) or 'f0_hz' not in e:
            out.append(f'element "{name}" needs f0_hz (a number, or [[position, Hz], ...])')
            continue
        bad = sorted(k for k in e if k not in ELEMENT_KEYS)
        if bad:
            out.append(f'element "{name}": key(s) {bad} are never read. Valid: {", ".join(sorted(ELEMENT_KEYS))}')
    for item in cfg.get('sequence') or []:
        name = item if isinstance(item, str) else (item[0] if item else None)
        if name not in elements:
            out.append(f'sequence names "{name}", which is not an element ({", ".join(sorted(elements))})')
    return out


def resolve(call, layer_keys):
    """The parameters of an animal_call layer that names a `calls` preset: the preset's, then the layer's own."""
    import presets
    preset = {k: v for k, v in presets.get('calls', call).items() if k not in PRESET_ONLY}
    valid = [p for p in inspect.signature(synth_animal_call).parameters if p not in ('sec', 'sr', 'rng', 'call')]
    unknown = sorted(k for k in preset if k not in valid)
    if unknown:
        raise ValueError(f'calls preset "{call}": key(s) {unknown} are never read. Valid: {", ".join(sorted(valid))}')
    return dict(preset, **{k: v for k, v in layer_keys.items() if k != 'call'})


def synth_animal_call(sec, sr=SR, rng=None, call=None, elements=None, sequence=None, gap_ms=(60.0, 140.0),
                      bouts_per_min=4.0, first_s=None, individuals=1, individual_spread=0.06, tract_cm=0.0,
                      formants_hz=(), formant_q=6.0, formant_mix=0.7, temp_c=20.0, temp_ref_c=20.0, rate_per_c=0.0):
    """Any animal call as data: named elements (pitch contour + source quality), a sequence, a tube, a number of callers.

    call names a `calls` preset; any key written beside it replaces the preset's. elements: {name: {f0_hz, ms,
    harmonics, rolloff, noise, subharmonic, biphonation, jump, pulse_hz, pulse_duty, vibrato_hz, vibrato_cents,
    attack, release, level_db}}. sequence: ["a", ["b", 2, 4]] plays a, then b two to four times (default: every
    element once). tract_cm gives the tube's resonances; formants_hz lists them instead. individuals each get their
    own pitch (individual_spread, a fraction) and their own timing. Pulse rates and the call rate change by
    rate_per_c per degree away from temp_ref_c. The peak of the whole layer is 0.5, so gain_db is relative to that.
    The environment renderer merges a layer over its preset exactly (resolve); called from Python with `call`, an
    argument left at its default takes the preset's value, so use resolve() to force a default back.
    """
    kw = dict(elements=elements, sequence=sequence, gap_ms=gap_ms, bouts_per_min=bouts_per_min, first_s=first_s,
              individuals=individuals, individual_spread=individual_spread, tract_cm=tract_cm, formants_hz=formants_hz,
              formant_q=formant_q, formant_mix=formant_mix, temp_c=temp_c, temp_ref_c=temp_ref_c, rate_per_c=rate_per_c)
    if call:
        sig = inspect.signature(synth_animal_call).parameters
        for k, v in resolve(call, {}).items():
            if kw[k] is None or kw[k] == sig[k].default:
                kw[k] = v
    bad = problems(dict(elements=kw['elements'], sequence=kw['sequence']))
    if bad:
        raise ValueError('animal_call: ' + '; '.join(bad))
    rng = rng or np.random.default_rng(1307)
    els = kw['elements'] or DEFAULT_ELEMENTS
    seq = kw['sequence'] or list(els)
    rate = max(0.1, 1.0 + float(kw['rate_per_c']) * (float(kw['temp_c']) - float(kw['temp_ref_c'])))
    formants = [float(f) for f in kw['formants_hz']] or tube_formants(kw['tract_cm'], sr)
    n = int(sec * sr)
    out = np.zeros(n, dtype=np.float64)
    mean_gap = 60.0 / max(0.05, float(kw['bouts_per_min']) * rate)
    count = max(1, int(kw['individuals']))
    for who in range(count):
        scale = float(np.exp(rng.normal(0.0, float(kw['individual_spread'])))) if count > 1 else 1.0
        level = 10.0 ** (-rng.uniform(0.0, 9.0) / 20.0) if count > 1 else 1.0     # some are further away
        t = float(kw['first_s']) if kw['first_s'] is not None and who == 0 else float(rng.uniform(0.1, 1.0) * mean_gap)
        while t < sec - 0.05:
            y = one_call(els, seq, kw['gap_ms'], sr, rng, scale, rate, formants, kw['formant_q'], kw['formant_mix'])
            i0 = int(t * sr)
            seg = y[:max(0, n - i0)]
            out[i0:i0 + len(seg)] += seg * level
            t += max(len(y) / sr + 0.2, mean_gap * float(rng.uniform(0.7, 1.3)))
    peak = float(np.abs(out).max())
    return (out * 0.5 / peak).astype(np.float32) if peak > 0 else out.astype(np.float32)
