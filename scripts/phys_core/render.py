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

#!/usr/bin/env python3
"""render.py - a scene becomes samples.

The renderer does four things and nothing else: it resolves each object to a modal identity (geometry + material), it
runs the interaction the timeline asks for, it schedules the result at its time (including the `then` edges that make a
break a sequence), and it propagates the sum to the listener. Every amplitude comes from a physical energy through
calibrate.amplitude, so intensity relationships survive; nothing is peak-normalized unless the scene asks for it.

Adding a new interaction means adding one function and one line in INTERACTIONS. It never means adding a sound name.
"""
import numpy as np

from . import calibrate, excite, fracture, gait, geometry, materials, propagate, resonate, vegetation

INTERACTIONS = ('impact', 'repeated_impact', 'friction', 'stick_slip', 'rolling', 'flow',
                'granular', 'creak', 'fracture', 'gait', 'foliage')
MAX_DEPTH = 6
# a grain, a leaf edge, a twig: small and stiff, so its contact modes are inharmonic and high. A short contact on a
# substrate is not what a listener hears; the small struck body is.
CONTACT_RATIOS = (1.0, 2.35, 4.10, 6.50, 9.20, 12.60)


def render_scene(scene, sr=44100, seed=1, seconds=None):
    """(mono float array, calibration report) for a scene."""
    sec = float(seconds if seconds is not None else scene.get('seconds', 1.0))
    n = max(1, int(round(sec * sr)))
    ctx = _context(scene, sr, sec, seed)
    out = np.zeros(n)
    for i, act in enumerate(scene.get('timeline') or []):
        out += _action(act, ctx, seed, i, n, 0)
    out = propagate.apply(out, sr, scene.get('propagation'))
    out, report = calibrate.apply(out, scene.get('calibration'), sr)
    return out, report


def _context(scene, sr, sec, seed):
    mats = {}
    for name, m in (scene.get('materials') or {}).items():
        mats[name] = materials.get(m, name=name)
    objs = scene.get('objects') or {}
    cal = scene.get('calibration') or {}
    return dict(sr=sr, sec=sec, seed=seed, materials=mats, objects=objs,
                ref_j=float(cal.get('reference_j', calibrate.REFERENCE_J)))


def _object(ctx, ref, act=None):
    """(f1, ratios, t60, material) for an object name, an inline object, or a sensible default."""
    obj = ctx['objects'].get(ref) if isinstance(ref, str) else (ref if isinstance(ref, dict) else None)
    obj = dict(obj or {})
    if act:
        for k in ('modes', 'material', 'geometry', 'strike'):
            if k in act and k not in obj:
                obj[k] = act[k]
    return geometry.resolve(obj, ctx['materials'])


def _place(out, sig, at_s, sr, gain=1.0):
    i = int(round(float(at_s) * sr))
    if i >= len(out) or i < 0 or not len(sig):
        return
    seg = np.asarray(sig, float)[: len(out) - i]
    out[i:i + len(seg)] += gain * seg


def _modal_hit(ctx, mat, f1, ratios, t60, tau, energy, rng, pitch=1.0):
    """One contact: a pulse of `tau` seconds into the object's modes, scaled by its energy."""
    sr = ctx['sr']
    exc = excite.impact_pulse(tau, sr)
    need = max(len(exc), int(min(8.0, t60 * 1.2) * sr))
    exc = np.pad(exc, (0, max(0, need - len(exc))))
    y = resonate.modal(exc, f1, ratios, t60, sr, damp_exp=mat['damp_exp'], pitch=pitch,
                       strike_spread=0.3, rng=rng)
    peak = float(np.abs(y).max())
    if peak < 1e-12:
        return np.zeros(1)
    return y / peak * calibrate.amplitude(energy, ctx['ref_j'])


def _contact_hz(act, default_hz, size, exp=0.5):
    """Contact corner for a small body, or the scene's own `contact_hz`."""
    return float(act.get('contact_hz', default_hz)) * float(np.clip(size, 0.15, 4.0)) ** (-exp)


def _grain_hit(ctx, mat, rng, act, size, velocity):
    """One grain contact, from the grain itself: its mass, its Hertz contact time, its momentum.

    A sand grain and a gravel stone differ because a grain is ~20x smaller: it is lighter (less energy per contact),
    softer against the surface (a longer contact time, so a duller click) and there are far more of them per step. That
    is the difference a listener hears, and it comes from `grain_size_m`, not from an EQ.
    """
    d = float(mat.get('grain_size_m', 0.005)) * float(size) ** 0.5
    d = float(np.clip(d, 5e-5, 0.06))
    m_grain = float(mat['density']) * (np.pi / 6.0) * d ** 3
    tau = excite.contact_time(float(mat['young_modulus_gpa']) * 1e9 * 0.1, m_grain, float(velocity))
    hz = float(act.get('contact_hz') or min(12000.0, 1.0 / (np.pi * max(tau, 1e-6))))
    energy = excite.impact_energy(m_grain, float(velocity))
    t60 = float(np.clip(0.02 * (d / 0.005) ** 0.3, 0.004, 0.12))
    return _modal_hit(ctx, mat, hz, CONTACT_RATIOS, t60, tau, energy, rng)


def _dur(act, ctx):
    return float(act.get('for', act.get('duration_s', 0.0)) or 0.0)


def _action(act, ctx, seed, index, n, depth):
    """One timeline entry (and its `then` children) as an n-length array."""
    out = np.zeros(n)
    if not isinstance(act, dict) or depth > MAX_DEPTH:
        return out
    rng = np.random.default_rng([int(seed) & 0xFFFFFFFF, int(index), int(depth)])
    at = float(act.get('at', 0.0))
    kind = act.get('interaction', 'impact')
    handler = INTERACTIONS_MAP.get(kind)
    if handler is not None:
        try:
            handler(act, ctx, rng, out, at, n, depth)
        except (ValueError, KeyError, ZeroDivisionError):
            raise
    for j, child in enumerate(act.get('then') or []):
        sub = dict(child)
        sub['at'] = at + float(sub.get('offset', sub.get('at', 0.0)))
        sub['interaction'] = sub.get('interaction', 'impact')
        out += _action(sub, ctx, seed, index * 100 + j + 1, n, depth + 1)
    return out


# ------------------------------------------------------------------ interactions
def _impact(act, ctx, rng, out, at, n, depth):
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    v = float(act.get('velocity_m_s', 1.0))
    mass = float(act.get('mass_kg', 0.5))
    stiff = float(act.get('stiffness_pa_m', mat['young_modulus_gpa'] * 1e9 * 0.05))
    tau = excite.contact_time(stiff, mass, v)
    energy = excite.impact_energy(mass, v) * float(act.get('efficiency', 0.25))
    y = _modal_hit(ctx, mat, f1, ratios, t60, tau, energy, rng)
    _place(out, y, at, ctx['sr'], float(act.get('gain', 1.0)))


def _repeated_impact(act, ctx, rng, out, at, n, depth):
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    e = float(act.get('restitution', mat['restitution']))
    v0 = float(act.get('velocity_m_s', 1.0))
    mass = float(act.get('mass_kg', 0.5))
    gap = float(act.get('gap_s', 0.3))
    count = int(act.get('count', 8))
    t = at
    for k in range(count):
        vk = v0 * (e ** k)
        energy = excite.impact_energy(mass, max(vk, 1e-3)) * float(act.get('efficiency', 0.25))
        y = _modal_hit(ctx, mat, f1, ratios, t60, excite.contact_time(1e7, mass, max(vk, 1e-3)), energy, rng)
        _place(out, y, t, ctx['sr'])
        t += gap * (e ** k) * (1.0 + 0.05 * rng.standard_normal())


def _friction(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or 0.5
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    speed = float(act.get('speed_m_s', 1.0))
    x = excite.scratch(dur, sr, rng, speed=speed, beta=float(act.get('beta', mat['roughness_beta'])))
    lo = max(40.0, f1 * float(act.get('band_low', 0.7)))
    hi = max(lo * 1.5, f1 * float(act.get('band_high', 3.0)))
    y = resonate.bandpass(x, lo, hi, sr)
    if materials.porous(mat):
        y = resonate.porous(y, materials.porous(mat), mat['thickness_m'], sr)
    peak = float(np.abs(y).max())
    if peak > 1e-12:
        y = y / peak * calibrate.amplitude(excite.impact_energy(0.3, speed), ctx['ref_j']) * 0.3
    _place(out, y, at, sr)


def _stick_slip(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or 0.4
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    x = excite.stick_slip(dur, sr, rng, f_slip=float(act.get('slip_hz', max(18.0, f1 * 0.25))),
                          depth=float(act.get('depth', 0.8)))
    y = resonate.modal(x, f1, ratios, t60, sr, damp_exp=mat['damp_exp'], rng=rng)
    peak = float(np.abs(y).max())
    if peak > 1e-12:
        y = y / peak * calibrate.amplitude(float(act.get('energy_j', 0.05)), ctx['ref_j']) * 0.5
    _place(out, y, at, sr)


def _rolling(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or 1.0
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    x = excite.rolling(dur, sr, rng, roughness=float(act.get('beta', mat['roughness_beta'])),
                       speed=float(act.get('speed_m_s', 1.0)))
    y = resonate.bandpass(x, f1 * 0.6, f1 * 4.0, sr)
    peak = float(np.abs(y).max())
    if peak > 1e-12:
        y = y / peak * calibrate.amplitude(float(act.get('energy_j', 0.2)), ctx['ref_j']) * 0.4
    _place(out, y, at, sr)


def _flow(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or ctx['sec']
    speed = act.get('speed_m_s', 4.0)
    speed = float(speed if not isinstance(speed, dict) else speed.get('value', 4.0))
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    x = excite.flow(dur, sr, rng, speed_m_s=speed, corner_hz=float(act.get('corner_hz', 0.12)),
                    intensity=float(act.get('intensity', 0.2)),
                    band=(float(act.get('band_low', 60.0)), float(act.get('band_high', 5000.0))))
    if materials.porous(mat):
        x = resonate.porous(x, materials.porous(mat), mat['thickness_m'], sr)
    sig = _fit(x, n, at, sr)
    out += sig * float(act.get('gain', 1.0))


def _granular(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or 0.6
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    rate = float(act.get('rate_hz', 80.0))
    vel = float(act.get('velocity_m_s', 1.0))
    times, sizes = excite.granular(dur, rng, rate=rate, restitution=mat['restitution'])
    for t, size in zip(times, sizes):
        _place(out, _grain_hit(ctx, mat, rng, act, size, vel), at + float(t), sr)


def _creak(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or 1.0
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    x = excite.stress(dur, sr, rng, strain=float(act.get('strain', 0.004)),
                      rate_per_s=float(act.get('rate_hz', 2.0)), creep=bool(act.get('creep', False)))
    y = resonate.modal(x, f1, ratios, t60, sr, damp_exp=mat['damp_exp'], rng=rng)
    peak = float(np.abs(y).max())
    if peak > 1e-12:
        y = y / peak * calibrate.amplitude(float(act.get('energy_j', 0.02)), ctx['ref_j']) * 0.6
    _place(out, y, at, sr)


def _fracture(act, ctx, rng, out, at, n, depth):
    """Stress released as a crack train, then the pieces, then settling. All of it is data in `act`."""
    sr = ctx['sr']
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    energy = float(act.get('energy_j') or 0.0)
    if energy <= 0:
        energy = fracture.released_energy(float(act.get('mass_kg', 0.5)), float(act.get('velocity_m_s', 2.0)))
    crack_pitch = float(act.get('crack_pitch', 2.2))
    for t, amp, tau in fracture.crack_train(mat, energy, rng, brittle=act.get('brittle')):
        y = _modal_hit(ctx, mat, f1, ratios, t60 * 0.5, tau, energy * amp * 0.5, rng, pitch=crack_pitch)
        _place(out, y, at + t, sr)
    if act.get('fragments', True):
        for size, delay in fracture.fragments(mat, energy, rng, count=act.get('piece_count'),
                                              brittle=act.get('brittle')):
            pitch = float(np.clip(float(size) ** -0.5, 0.5, 4.0))
            e = energy * 0.12 * float(size)
            y = _modal_hit(ctx, mat, f1, ratios, t60, excite.contact_time(1e7, 0.05 * size, 1.5), e, rng, pitch=pitch)
            _place(out, y, at + 0.15 + delay, sr)
    if act.get('settle', True):
        times, sizes = excite.granular(float(act.get('settle_s', 0.8)), rng, rate=float(act.get('settle_rate_hz', 25.0)))
        for t, size in zip(times, sizes):
            y = _modal_hit(ctx, mat, f1, ratios, t60 * 0.3, 0.001, energy * 0.02 * float(size), rng,
                           pitch=float(size) ** -0.5)
            _place(out, y, at + 0.4 + float(t), sr)


def _gait(act, ctx, rng, out, at, n, depth):
    """Walk or run: alternating contacts whose force follows a ground reaction curve, on a surface material."""
    sr = ctx['sr']
    dur = _dur(act, ctx) or 2.0
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('surface')), act)
    cadence = float(act.get('cadence_spm') or 112.0)
    mass = float(act.get('mass_kg') or 75.0)
    run = gait.is_running(cadence)
    # a granular or absorbent surface has no ringing mode to excite: the force goes into the grains. Trying to ring
    # it on its structural mode is what makes sand footfalls rumble instead of hiss.
    nonresonant = materials.is_granular(mat) or mat['family'] == 'absorbent'
    for step in gait.steps(dur, cadence, rng):
        env = gait.grf(int(step['contact_s'] * sr), sr, peak=mass * 9.81 * step['weight'],
                       style='run' if run else 'walk', heel=step['phase'] == 'heel')
        drive = np.abs(np.diff(env, prepend=env[0]))
        e = excite.impact_energy(mass * 0.06, step['velocity'])
        if nonresonant:
            y = resonate.bandpass(drive, 80.0, 1200.0, sr, order=2)
            peak = float(np.abs(y).max())
            if peak > 1e-12:
                y = y / peak * calibrate.amplitude(e, ctx['ref_j']) * 0.25
        else:
            y = resonate.modal(drive, f1, ratios, t60, sr, damp_exp=mat['damp_exp'], rng=rng)
            peak = float(np.abs(y).max())
            if peak > 1e-12:
                y = y / peak * calibrate.amplitude(e, ctx['ref_j'])
        _place(out, y, at + step['t'], sr)
        if materials.is_granular(mat):
            times, sizes = excite.granular(min(0.09, step['contact_s']), rng, rate=float(act.get('grain_rate_hz', 500.0)))
            for t, size in zip(times, sizes):
                gy = _grain_hit(ctx, mat, rng, act, size, step['velocity'])
                _place(out, gy, at + step['t'] + float(t), sr)


def _foliage(act, ctx, rng, out, at, n, depth):
    sr = ctx['sr']
    dur = _dur(act, ctx) or ctx['sec']
    f1, ratios, t60, mat = _object(ctx, act.get('target', act.get('object')), act)
    speed = float(act.get('speed_m_s', 3.0))
    gust = vegetation.gust_envelope(dur, sr, rng, float(act.get('corner_hz', 0.15)), float(act.get('intensity', 0.35)))
    times, amps, sizes = vegetation.leaf_events(dur, speed, float(act.get('leaf_count', 4000.0)), rng, gust)
    for t, amp, size in zip(times, amps, sizes):
        if t >= dur:
            continue
        y = _grain_hit(ctx, mat, rng, act, float(size) * 0.6, float(amp) * 1.2)
        _place(out, y, at + float(t), sr)


INTERACTIONS_MAP = {'impact': _impact, 'repeated_impact': _repeated_impact, 'friction': _friction,
                    'stick_slip': _stick_slip, 'rolling': _rolling, 'flow': _flow, 'granular': _granular,
                    'creak': _creak, 'fracture': _fracture, 'gait': _gait, 'foliage': _foliage}


def _fit(x, n, at, sr):
    """An n-length buffer already placed at `at` (for continuous interactions)."""
    out = np.zeros(n)
    _place(out, x, at, sr)
    return out
