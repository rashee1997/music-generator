"""base.py - the vocabulary every domain module shares.

A Lever is one admissible change: a preset or score value, its current setting, the range it may move in and the
granularity the format can express. Nothing here knows about a particular piece; a lever is built from whatever the
presets and score actually declare.

An Analysis is what one domain contributes to the system: the rows it examined, the levers it offers, first-order
coefficients `(row_key, lever_id) -> d value / d lever`, and notes about what it could not measure.
"""
from __future__ import annotations

import functools
import math

import numpy as np
from scipy.signal import welch


class Lever:
    __slots__ = ('id', 'domain', 'stem', 'kind', 'current', 'lo', 'hi', 'step', 'unit', 'text', 'burns')

    def __init__(self, id, domain, kind, current, lo, hi, step, unit, text, stem=None, burns=()):
        self.id = id
        self.domain = domain
        self.kind = kind
        self.current = float(current)
        self.lo = float(lo)
        self.hi = float(hi)
        self.step = abs(float(step)) or 0.01
        self.unit = unit
        self.text = text
        self.stem = stem
        self.burns = tuple(burns)          # row prefixes this lever has already been tried against

    def snap(self, delta):
        """Round a requested move to the format's granularity, staying inside the bounds."""
        target = self.current + float(delta)
        target = max(self.lo, min(self.hi, target))
        steps = round((target - self.current) / self.step)
        return round(self.current + steps * self.step, 6) - self.current

    def as_dict(self):
        return dict(id=self.id, domain=self.domain, kind=self.kind, stem=self.stem, current=self.current,
                    lo=self.lo, hi=self.hi, step=self.step, unit=self.unit, text=self.text)


class Analysis:
    def __init__(self, rows=(), levers=(), coefficients=None, notes=(), measured=(), first_order=True):
        self.rows = list(rows)
        self.levers = list(levers)
        self.coefficients = dict(coefficients or {})
        self.notes = list(notes)
        self.measured = list(measured)
        self.first_order = bool(first_order)

    def merge(self, other):
        self.rows.extend(other.rows)
        self.levers.extend(other.levers)
        self.coefficients.update(other.coefficients)
        self.notes.extend(other.notes)
        self.measured.extend(other.measured)
        self.first_order = self.first_order and other.first_order
        return self


# -- shared measurement helpers -------------------------------------------------------------------------------

@functools.lru_cache(maxsize=64)
def _psd_cached(key, path, sr):
    a = np.load(path).astype(np.float32)
    mono = a.mean(axis=1) if a.ndim == 2 else a
    return welch(mono.astype(np.float64), fs=sr, nperseg=4096)


def psd(case, stem):
    """Welch PSD of one processed stem, cached per stem for the life of the Case."""
    if stem not in case._stems:
        return None
    path, sr = case._stems[stem]
    return _psd_cached((stem, path), path, sr)


def band_energy(f, p, lo, hi):
    m = (f >= lo) & (f < hi)
    return float(np.sum(p[m]))


def energy_share(f, p, band, eq_band):
    """Fraction of a row's band energy that an EQ band actually covers."""
    total = band_energy(f, p, *band)
    if total <= 0:
        return 0.0
    lo = max(band[0], eq_band[0])
    hi = min(band[1], eq_band[1])
    if hi <= lo:
        return 0.0
    return float(band_energy(f, p, lo, hi) / total)


def eq_band(kind, f0, q=1.0):
    """(lo, hi) a first-order band shape covers, in octaves: a bell's bandwidth is about 1/Q octaves."""
    q = max(0.1, float(q or 1.0))
    f0 = max(1.0, float(f0))
    b = 1.0 / q
    return f0 * 2 ** (-b / 2.0), f0 * 2 ** (b / 2.0)


def shelf_band(kind, f0):
    """A shelf or low-pass moves everything above (or below) its corner."""
    f0 = max(1.0, float(f0))
    if kind in ('lp', 'lowpass'):
        return 20.0, f0
    if kind in ('hp', 'highpass'):
        return f0, 20000.0
    if kind == 'highshelf':
        return f0, 20000.0
    if kind == 'lowshelf':
        return 20.0, f0
    return f0 * 0.5, f0 * 2.0


def hf_share(case, stem, above_hz=6000.0):
    """Share of a stem's energy above a frequency: the quantity a click row reacts to."""
    got = psd(case, stem)
    if got is None:
        return None
    f, p = got
    total = float(np.sum(p))
    if total <= 0:
        return 0.0
    return float(np.sum(p[f >= above_hz]) / total)


def energy_at(case, stem, t, sr=44100, win=0.004, above_hz=6000.0):
    """High-passed amplitude of one stem at around time t (event attribution for an impulse)."""
    a = case.stem(stem)
    if a is None:
        return 0.0
    i = int(round(float(t) * sr))
    lo = max(0, i - int(win * sr))
    hi = min(len(a), i + int(win * sr))
    if hi <= lo:
        return 0.0
    seg = a[lo:hi].mean(axis=1).astype(np.float64)
    if above_hz > 0 and len(seg) > 8:
        d = np.diff(seg)                       # a crude high-pass: impulses live in the first difference
        return float(np.max(np.abs(d))) if d.size else 0.0
    return float(np.max(np.abs(seg)))


def rms_at(case, stem, t, sr=44100, win=0.02):
    a = case.stem(stem)
    if a is None:
        return 0.0
    i = int(round(float(t) * sr))
    seg = a[max(0, i):min(len(a), i + int(win * sr))].astype(np.float64)
    if not seg.size:
        return 0.0
    return float(np.sqrt(np.mean(seg ** 2)))


def db(x, floor=-200.0):
    return max(floor, 20.0 * math.log10(max(float(x), 1e-12)))


def audible(rows):
    """Rows worth acting on: the failing ones, else the warned ones."""
    fail = [r for r in rows if r.get('level') == 'FAIL']
    return fail or [r for r in rows if r.get('level') == 'WARN']
