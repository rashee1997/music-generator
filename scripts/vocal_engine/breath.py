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

"""Breathing and phrase physiology.

The breath a singer takes is not an event dropped into a gap: it is a continuous airflow that never stops.
`bed()` builds that airflow across a whole line - a low room floor, a slow rise through each gap, a rounded
peak just before the next phrase, and a crossfade that passes under the voice's attack - and multiplies one
shaped noise signal by it. Because the envelope never reaches zero, a gap is air, not digital silence, which
is what made the old discrete bursts read as footsteps or paper being scratched.

Timing and level follow the gap (Salomoni et al. 2016: singers shorten the inspiration and raise peak airflow
as the phrase comes faster; a long rest gets a slow, quiet breath). Real inhalation noise has a falling
spectrum with weak peaks below 3 kHz (Werner et al., JSLHR 2023), so `inhale_tilt_db` holds the air band under
the body instead of leaving flat hiss.

The older event functions (`inhale`, `onset_puff`, `release_puff`, `plan_inhales_detailed`) stay for
compatibility and for a caller that wants one isolated event; the ensemble no longer uses them.

Phrase exhaustion: past `capacity_s * exhaust_start` the pressure falls and breathiness rises (`aspiration_track`).
"""
import numpy as np
from scipy.signal import butter, sosfilt


def _exhaustion(n, sr, B):
    t = np.arange(n) / sr
    start = B['capacity_s'] * B['exhaust_start']
    return np.clip((t - start) / max(B['capacity_s'] - start, 1e-3), 0.0, 1.5)


def pressure_curve(n, sr, B):
    """Amplitude multiplier: 1 until exhaustion starts, then falls by pressure_drop_db."""
    return 10.0 ** (-B['pressure_drop_db'] * _exhaustion(n, sr, B) ** 2 / 20.0)


def aspiration_track(n, sr, base, B, onsets, weights=None):
    """Per-sample breathiness: base, rising with exhaustion, plus an aspirated puff at each onset (sample indices).
    `weights` (optional, one per onset) scales each puff: an accented note starts with a little more air."""
    br = base * (1.0 + (B['exhaust_breath'] - 1.0) * _exhaustion(n, sr, B) ** 2) * np.ones(n)
    tau = max(B['aspirate_attack_ms'] * 1e-3, 1e-3)
    for j, o in enumerate(onsets):
        o = int(o)
        m = min(n - o, int(6 * tau * sr))
        w = 1.0 if weights is None else max(0.0, float(weights[j]))
        if m > 0:
            br[o:o + m] += B['aspirate_gain'] * w * np.exp(-np.arange(m) / sr / tau)
    return br


def _bp(x, sr, lo, hi, order=2):
    sos = butter(order, [max(20.0, lo), min(hi, 0.45 * sr)], btype='band', fs=sr, output='sos')
    return sosfilt(sos, x)


def _lp(x, sr, f, order=2):
    sos = butter(order, min(max(f, 30.0), 0.45 * sr), btype='low', fs=sr, output='sos')
    return sosfilt(sos, x)


def _smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _turbulence(n, sr, rng, B):
    """The air is not steady: a flutter around `turbulence_hz` plus a slow, smoothed wander.
    Returns a multiplier around 1.0."""
    depth = float(B['turbulence_depth'])
    if depth <= 0.0:
        return np.ones(n)
    t = np.arange(n) / sr
    ph = 2 * np.pi * float(B['turbulence_hz']) * t + 0.9 * np.sin(2 * np.pi * 0.6 * t)
    flutter = np.sin(ph)
    hann = np.hanning(max(3, int(0.06 * sr)))
    wander = np.convolve(rng.standard_normal(n), hann, mode='same')
    wander = wander / (np.max(np.abs(wander)) + 1e-12)
    return np.clip(1.0 + depth * (0.65 * flutter + 0.35 * wander), 0.0, 2.0)


def _breath_noise(rng, n, sr, B, lo, hi, body_hz, tilt_db):
    """Shaped breath noise: a low body band, the air band above it held down by `tilt_db`, and turbulence.
    Normalised to unit RMS so the gains in `breathing` keep their meaning."""
    w = rng.standard_normal(n)
    body = _bp(w, sr, 0.45 * body_hz, 1.7 * body_hz)
    air = _bp(w, sr, lo, hi) if hi > lo * 1.1 else _bp(w, sr, 0.8 * lo, 1.2 * lo)
    air = _lp(air, sr, hi)                      # one more pole: takes the sizzle off the top edge
    y = body + 10.0 ** (float(tilt_db) / 20.0) * air
    y = y * _turbulence(n, sr, rng, B)
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-12)


# ---------------------------------------------------------------- continuous airflow

def airflow_env(n, sr, B, spans, jitter=None):
    """The airflow envelope across a whole line, in linear amplitude relative to a phrase's RMS.

    `spans` are the sung (t0, voiced_end) pairs in seconds. Every gap gets an inhalation that rises through
    most of the gap and peaks `inhale_lead_ms` before the next phrase, then crossfades under the voice's
    attack (`inhale_crossfade_ms`); every phrase gets a decaying release. Between those, the envelope sits on
    `inhale_floor_db` - air, not silence. Level and length follow the gap, so a long rest is a slow quiet
    breath and a catch breath is short and firmer.

    `jitter` is one `(shift_s, duration_scale)` per gap, moving that inhalation inside its own gap and
    scaling its length. It is per gap on purpose: shifting the whole envelope would move the releases too,
    and a singer's breath is not the same person's reaction time as their exhale."""
    floor = 10.0 ** (float(B['inhale_floor_db']) / 20.0)
    env = np.full(n, floor, dtype=float)
    t = np.arange(n) / sr
    peak_db = float(B['inhale_peak_db'])
    rel_db = float(B['release_peak_db'])
    lead = float(B['inhale_lead_ms']) * 1e-3
    fade = max(0.02, float(B['inhale_crossfade_ms']) * 1e-3)
    jitter = jitter or []
    for i, (_t0, t1) in enumerate(spans):
        # release: the air keeps leaving after the note stops
        if rel_db > B['inhale_floor_db']:
            a = int(max(0, t1) * sr)
            if a < n:
                m = n - a
                # an exhale does not switch on: it grows out of the airflow already there, then decays
                tt = np.arange(m) / sr
                shape = _smooth(np.clip(tt / 0.12, 0, 1)) * np.exp(-np.clip(tt - 0.12, 0.0, None) / 0.25)
                env[a:] = np.maximum(env[a:], 10.0 ** (rel_db / 20.0) * shape)
        if i + 1 >= len(spans):
            continue
        gap_start, gap_end = t1, spans[i + 1][0]
        gap = gap_end - gap_start
        if gap < float(B['inhale_min_s']) * 0.6:
            continue
        shift, dscale = jitter[i] if i < len(jitter) else (0.0, 1.0)
        dur = float(np.clip(B['inhale_gap_frac'] * gap * float(dscale), B['inhale_min_s'], B['inhale_max_s']))
        end = min(gap_end - 0.4 * lead, gap_end - lead + float(np.clip(shift, -0.5 * gap, 0.5 * gap)))
        start = max(gap_start + 0.02, end - dur)
        end = max(start + 0.08, end)
        if end - start < 0.08:
            continue
        m = int((end - start) * sr)
        if m < 8:
            continue
        x = np.linspace(0.0, 1.0, m)
        shape = _smooth(np.clip(x / 0.78, 0, 1)) ** 1.15
        shape *= 1.0 - 0.35 * _smooth(np.clip((x - 0.78) / 0.22, 0, 1))
        # a longer breath is a quieter one (the same air over more time)
        level = 10.0 ** ((peak_db - 8.0 * np.log2(max(1.0, dur / max(B['inhale_min_s'], 1e-3)))) / 20.0)
        a = int(start * sr)
        seg = level * shape
        env[a:a + len(seg)] = np.maximum(env[a:a + len(seg)], seg[:max(0, n - a)])
        # crossfade: the tail does not stop at the note, it passes under the attack
        c = int(fade * sr)
        b = a + len(seg)
        if c > 4 and b < n:
            tail = level * 0.45 * np.exp(-np.arange(c) / (0.45 * c))
            env[b:b + c] = np.maximum(env[b:b + c], tail[:max(0, n - b)])
    # the envelope is a control signal: smooth it over 30 ms so no seam (a release starting, a crossfade
    # ending) can step the level and be heard as an object. Then hold the floor, so the bed never goes to zero.
    w = np.hanning(max(3, int(0.03 * sr)))
    env = np.convolve(env, w / w.sum(), mode='same')
    return np.maximum(env, floor)


def bed(sr, rng, B, ref_rms, spans, n, character=0.0, jitter=None):
    """Continuous breath signal for one line: one shaped noise, multiplied by `airflow_env`.
    `ref_rms` is the singer's reference RMS, so the level keys stay relative to the voice."""
    if n <= 0 or not spans:
        return np.zeros(max(n, 0))
    env = airflow_env(n, sr, B, spans, jitter=jitter)
    lo, hi = B['inhale_band_hz']
    shift = 1.0 + 0.18 * float(np.clip(character, -1.0, 1.0))
    noise = _breath_noise(rng, n, sr, B, lo * shift, hi * shift,
                          body_hz=float(B['inhale_body_hz']), tilt_db=float(B['inhale_tilt_db']))
    return noise * env * ref_rms * float(B['inhale_gain'])


# ---------------------------------------------------------------- single events (compatibility)

def _inhale_env(n):
    """Slower rise than a gate, then a rounded fall: an inspiratory ramp, not a burst with a cut at the end."""
    x = np.linspace(0.0, 1.0, n)
    rise = np.clip(x / 0.55, 0.0, 1.0) ** 1.6
    fall = np.clip((1.0 - x) / 0.18, 0.0, 1.0) ** 1.3
    return rise * fall


def inhale(sr, rng, B, ref_rms, dur_s=None, level_scale=1.0, character=0.0):
    """One isolated inhalation event (legacy path; the ensemble uses `bed`)."""
    c = float(np.clip(character, -1.0, 1.0))
    d = (dur_s if dur_s is not None else B['inhale_ms'] * 1e-3) * (1.0 + 0.18 * c)
    n = max(int(d * sr), 8)
    lo, hi = B['inhale_band_hz']
    shift = 1.0 + 0.18 * c
    x = _breath_noise(rng, n, sr, B, lo * shift, hi * shift,
                      body_hz=float(B['inhale_body_hz']) * (1.0 - 0.1 * c),
                      tilt_db=float(B['inhale_tilt_db']) + 2.0 * c)
    return x * _inhale_env(n) * B['inhale_gain'] * ref_rms * level_scale


def onset_puff(sr, rng, B, ref_rms, dur_s=None, level_scale=1.0, character=0.0):
    """The air that escapes just before a phrase's first voiced note when there was no room to inhale.
    Kept for compatibility; `bed` places no discrete event."""
    c = float(np.clip(character, -1.0, 1.0))
    n = max(int((dur_s if dur_s is not None else B['onset_puff_ms'] * 1e-3) * sr), 8)
    x = np.linspace(0.0, 1.0, n)
    env = np.sin(0.5 * np.pi * np.clip(x / 0.7, 0, 1)) ** 2 * np.clip((1 - x) / 0.25, 0, 1)
    d = _breath_noise(rng, n, sr, B, 300.0 * (1 + 0.2 * c), 2600.0 * (1 + 0.25 * c),
                      body_hz=float(B['inhale_body_hz']) * 2.0,
                      tilt_db=float(B['inhale_tilt_db']) + 6.0)
    return d * env * B['onset_puff_gain'] * ref_rms * level_scale


def release_puff(sr, rng, B, ref_rms, level_scale=1.0, dur_s=None, character=0.0):
    """Exhale after a phrase (legacy path)."""
    c = float(np.clip(character, -1.0, 1.0))
    n = max(int((dur_s if dur_s is not None else B['release_breath_ms'] * 1e-3) * sr), 8)
    env = np.exp(-np.arange(n) / (0.35 * n)) * np.sin(0.5 * np.pi * np.clip(np.arange(n) / (0.05 * n + 1), 0, 1))
    d = _breath_noise(rng, n, sr, B, 200.0 * (1 - 0.15 * c), 2600.0 * (1 + 0.1 * c),
                      body_hz=float(B['inhale_body_hz']),
                      tilt_db=float(B['inhale_tilt_db']) - 2.0)
    return d * env * B['release_breath_gain'] * ref_rms * level_scale


def plan_inhales_detailed(phrases, B):
    """phrases: list of (t_start, t_end) sorted. One entry per phrase that has room:
    dict(index, end, dur, phrase_start, catch)."""
    out, prev_end = [], None
    quick = float(B.get('catch_breath_after_s', 1e9))
    for i, (t0, t1) in enumerate(phrases):
        room = (t0 - prev_end) if prev_end is not None else t0
        lead = B['inhale_lead_ms'] * 1e-3
        dur = min(B['inhale_ms'] * 1e-3, room - lead - 0.02)
        if (prev_end is None or room >= B['inhale_min_gap_s']) and dur >= 0.12:
            out.append(dict(index=i, end=t0 - lead, dur=dur, phrase_start=t0, catch=(t1 - t0) >= quick))
        prev_end = t1
    return out
