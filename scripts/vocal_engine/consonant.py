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

"""Consonants: the syllable layer the phrase engine was missing.

Every consonant is a *physical recipe*, not a sound name. A row in `consonants.inventory` says what the articulators
do and the renderer follows it:

  stop       closure (near silence) -> burst (short noise around the place of articulation) -> voice-onset time
             (aspiration between the release and the voicing; Ladefoged & Johnson, 30-90 ms per place)
  fricative  band-limited noise with a tilt; `tract_shape: true` filters it through the following vowel's formants,
             which is what /h/ is (aspiration shaped by the tract, not a hiss)
  nasal      a buzz through two nasal poles with an oral anti-formant (the anti-formant is the /m/ - /n/ - /ng/ cue)
  liquid     a buzz through the liquid's own formants
  trill      a buzz through formants, amplitude-modulated at `rate_hz`

A new consonant is therefore a JSON row, never new Python (AGENTS.md: sounds are data). The renderer only knows the
five recipe types. Everything numeric comes from the row; nothing here is a musical decision.
"""
import numpy as np
from scipy.signal import butter, sosfilt

from . import nasal as nasal_mod
from . import tract
from .utils import rms


def _bp(x, sr, lo, hi, order=2):
    hi = min(max(hi, lo * 1.05), 0.45 * sr)
    sos = butter(order, [max(20.0, lo), hi], btype='band', fs=sr, output='sos')
    return sosfilt(sos, x)


def _lp(x, sr, f, order=2):
    sos = butter(order, min(max(f, 30.0), 0.45 * sr), btype='low', fs=sr, output='sos')
    return sosfilt(sos, x)


def _env(n, attack_ms, release_ms, sr):
    """Raised-cosine in and out: a consonant may not start or end with a step (that is a click)."""
    x = np.ones(n)
    a = min(int(max(attack_ms, 1.0) * 1e-3 * sr), n // 2)
    r = min(int(max(release_ms, 1.0) * 1e-3 * sr), n // 2)
    if a > 1:
        x[:a] = 0.5 * (1.0 - np.cos(np.pi * np.arange(a) / a))
    if r > 1:
        x[-r:] = np.minimum(x[-r:], 0.5 * (1.0 + np.cos(np.pi * np.arange(r) / r)))
    return np.clip(x, 0.0, 1.0)


def _buzz(n, sr, f0, harmonics=24):
    """A cheap periodic excitation for the voiced consonants (they are short; no glottal model needed)."""
    f0 = float(max(f0, 30.0))
    t = np.arange(n) / sr
    k = np.arange(1, max(2, int(min(harmonics, 0.45 * sr / f0))) + 1)
    ph = 2 * np.pi * f0 * np.outer(t, k)
    y = np.sum(np.sin(ph) / k[None, :], axis=1)
    return y / (rms(y) + 1e-12)


def _resonate(x, formants, bandwidths, sr):
    k = min(len(formants), len(bandwidths))
    gains = [1.0, 0.6, 0.3, 0.18, 0.1][:k]
    return tract.bank(x, list(formants[:k]), list(bandwidths[:k]), gains, sr)


def _stop(row, sr, rng, f0, vowel):
    nc = max(int(float(row.get('closure_ms', 40.0)) * 1e-3 * sr), 8)
    nb = max(int(float(row.get('burst_ms', 6.0)) * 1e-3 * sr), 6)
    vot = max(float(row.get('vot_ms', 60.0)), 5.0)
    nv = max(int((vot - float(row.get('burst_ms', 6.0))) * 1e-3 * sr), 8)
    band = row['band']
    # closure: the vocal tract is shut. Not digital zero (a hole reads as a dropout), a quiet room floor.
    floor = 10.0 ** (float(row.get('closure_floor_db', -55.0)) / 20.0)
    closure = _lp(rng.standard_normal(nc), sr, 120.0) * floor
    # burst: broadband release coloured by the place of articulation, decaying in a few ms
    burst = _bp(rng.standard_normal(nb), sr, band[0], band[1])
    burst = burst * np.exp(-np.arange(nb) / max(0.35 * nb, 1.0))
    burst = burst / (rms(burst) + 1e-12)
    # voice-onset time: aspiration between the release and the voicing, falling into the note
    asp = _bp(rng.standard_normal(nv), sr, 220.0, min(band[1] * 1.1, 0.45 * sr))
    asp = asp * np.exp(-np.arange(nv) / max(0.55 * nv, 1.0)) * _env(nv, 2.0, 8.0, sr)
    asp = 0.35 * asp / (rms(asp) + 1e-12)
    voiced = np.zeros(nb + nv)
    if row.get('voiced'):
        voiced = 0.35 * _resonate(_buzz(nb + nv, sr, f0), vowel or [500.0, 1500.0, 2500.0],
                                  [90.0, 120.0, 200.0], sr)
        voiced = voiced / (rms(voiced) + 1e-12) * 0.6
    tail = np.concatenate([burst, asp]) + voiced
    return np.concatenate([closure, tail]), dict(vot_ms=vot)


def _fricative(row, sr, rng, f0, vowel):
    n = max(int(float(row.get('dur_ms', 110.0)) * 1e-3 * sr), 8)
    w = rng.standard_normal(n)
    band = row['band']
    if row.get('tract_shape') and vowel is not None:
        y = _resonate(w, list(vowel), [400.0] * len(vowel), sr)     # /h/: the tract shapes the air
    else:
        y = _bp(w, sr, band[0], band[1])
        tilt = float(row.get('tilt_db', 0.0))
        if tilt:
            y = y + 10.0 ** (tilt / 20.0) * _lp(y, sr, band[0])
    y = y * _env(n, 15.0, 25.0, sr)
    return y / (rms(y) + 1e-12), dict(vot_ms=None)


def _nasal(row, sr, rng, f0, vowel):
    n = max(int(float(row.get('dur_ms', 70.0)) * 1e-3 * sr), 8)
    poles = list(row.get('poles', [250.0, 1000.0]))
    bw = [70.0, 180.0, 300.0][:len(poles)]
    gains = [1.0, 0.25, 0.1][:len(poles)]
    y = tract.bank(_buzz(n, sr, f0), poles, bw, gains, sr)
    y = nasal_mod.notch(y, float(row.get('antiformant_hz', 1000.0)), float(row.get('antiformant_bw', 160.0)), 0.85, sr)
    y = y * _env(n, 8.0, 18.0, sr)
    return y / (rms(y) + 1e-12), dict(vot_ms=None)


def _liquid(row, sr, rng, f0, vowel):
    n = max(int(float(row.get('dur_ms', 60.0)) * 1e-3 * sr), 8)
    y = _resonate(_buzz(n, sr, f0), list(row.get('formants', [360.0, 1300.0, 2700.0])),
                  list(row.get('bandwidths', [90.0, 120.0, 200.0])), sr)
    y = y * _env(n, 8.0, 18.0, sr)
    return y / (rms(y) + 1e-12), dict(vot_ms=None)


def _trill(row, sr, rng, f0, vowel):
    n = max(int(float(row.get('dur_ms', 70.0)) * 1e-3 * sr), 8)
    y = _resonate(_buzz(n, sr, f0), list(row.get('formants', [420.0, 1300.0, 1700.0])),
                  list(row.get('bandwidths', [90.0, 120.0, 160.0])), sr)
    rate = max(float(row.get('rate_hz', 28.0)), 1.0)
    am = 0.15 + 0.85 * np.maximum(0.0, np.sin(2 * np.pi * rate * np.arange(n) / sr))
    y = y * am * _env(n, 6.0, 15.0, sr)
    return y / (rms(y) + 1e-12), dict(vot_ms=None)


_KINDS = {'stop': _stop, 'fricative': _fricative, 'nasal': _nasal, 'liquid': _liquid, 'trill': _trill}


def recipe(cn, code):
    """The inventory row for a code (None when the code is not in this inventory)."""
    return (cn.get('inventory') or {}).get(str(code))


def length_s(cn, code):
    """How much time the recipe needs before the voiced onset, in seconds."""
    row = recipe(cn, code)
    if not row:
        return 0.0
    if row.get('type') == 'stop':
        return (float(row.get('closure_ms', 40.0)) + max(float(row.get('vot_ms', 60.0)),
                                                         float(row.get('burst_ms', 6.0)))) * 1e-3
    return float(row.get('dur_ms', 100.0)) * 1e-3


def measure(seg, sr):
    """Measured properties of the rendered segment: where its energy actually sits and how long it lasts.

    The centroid is taken on the loudest 20 ms window, which for a stop is the burst and not the aspiration
    (averaging the two would drag the centroid below the place of articulation and make the gate meaningless).
    """
    seg = np.asarray(seg, dtype=float)
    a = np.abs(seg)
    peak = float(a.max()) if len(a) else 0.0
    if peak <= 0:
        return dict(centroid_hz=0.0, dur_ms=0.0, vot_ms=0.0)
    idx = np.where(a > 0.1 * peak)[0]
    dur_ms = (int(idx[-1]) - int(idx[0]) + 1) / sr * 1e3
    w = max(64, int(0.02 * sr))
    if len(seg) > w:
        energy = np.convolve(seg * seg, np.ones(w) / w, mode='valid')
        start = int(np.argmax(energy))
    else:
        start = 0
    win = seg[start:start + w] * np.hanning(min(w, len(seg) - start) if len(seg) - start >= 8 else 8)
    spec = np.abs(np.fft.rfft(win))
    fr = np.fft.rfftfreq(len(win), 1 / sr)
    centroid = float((spec * fr).sum() / (spec.sum() + 1e-20)) if len(win) else 0.0
    return dict(centroid_hz=centroid, dur_ms=dur_ms, vot_ms=dur_ms)


def render(code, cn, sr, rng, f0=150.0, vowel=None):
    """code -> (signal, meta). meta carries the recipe's declared band/VOT and the measured values."""
    row = recipe(cn, code)
    if not row:
        return np.zeros(0), dict(code=str(code), error='not in inventory')
    kind = _KINDS.get(str(row.get('type')))
    if kind is None:
        return np.zeros(0), dict(code=str(code), error=f'unknown recipe type {row.get("type")!r}')
    y, extra = kind(row, sr, rng, f0, vowel)
    m = measure(y, sr)
    return y, dict(code=str(code), type=row.get('type'), band=row.get('band'),
                   vot_ms=extra.get('vot_ms'), measured=m)
