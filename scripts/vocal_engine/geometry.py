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

"""Cross-sectional area functions: the map from a formant target to a tube.

The inverse problem (formants -> area function) is ill-posed: there are infinitely many area functions with the same
resonances (Schroeter & Sondhi 1994), an antisymmetric transformation of the area function preserves all of them, and
a uniform rescale of every area preserves them exactly. Solving for 22 free areas therefore wanders a null space -
a first prototype did exactly that, drifting to A_max/A_min ~ 2600 and an absolute scale of 1e61.

The literature's answer, and this module's design, is a low-dimensional articulatory basis: a neutral area function
times exp() of a few control points (Story & Titze 1998 use a neutral shape plus weighted orthogonal modes and report
a near one-to-one mapping between a handful of weights and formants; Bavegard & Fant 1995 invert with three
parameters). Here: `control_points` log-area offsets, linear in z, the uniform scale pinned (it is unidentifiable),
the coefficients bounded, and a curvature penalty that keeps the shape smooth - the same smoothness prior Kasess et
al. (2013) use for branched-tube estimation.

The fit is weighted to F1-F3: vowel identity and the tract's character live there, F4/F5 are allowed to land
approximately. That is a stated decision, reported by the gate, not a numerical accident.
"""
import numpy as np

from . import waveguide as wg


def signature(wv):
    """Everything that changes the solved geometry, as a hashable tuple. Two configs with the same numbers share a
    cache entry; a piece that changes the tract length does not."""
    g = wv['geometry']
    return (float(wv['tract_length_m']), int(wv['sections']), int(g['control_points']),
            float(wv['losses']['k0_per_m']), float(wv['losses']['k1_s_per_m']),
            float(wv['radiation']['ka_max']), float(g['bounds']), float(g['curvature']),
            float(g['scale_pin']), tuple(float(x) for x in g['weights']),
            tuple(float(x) for x in g['neutral_cm2']), float(g['tolerance_hz']))


_WEIGHTS = {}


def control_weights(n, cp):
    """(cp, n) linear interpolation weights on the normalised tract length; each column sums to 1.

    A fixed basis, so it is built once per (n, cp) and returned read-only: the solver calls it in its inner loop.
    """
    key = (int(n), int(cp))
    w = _WEIGHTS.get(key)
    if w is None:
        z = np.linspace(0.0, 1.0, cp)
        zz = np.linspace(0.0, 1.0, n)
        w = np.zeros((cp, n))
        for j, t in enumerate(z):
            w[j] = np.clip(1.0 - np.abs(zz - t) / max(z[1] - z[0], 1e-9), 0.0, None)
        s = w.sum(axis=0)
        w = w / np.where(s > 0, s, 1.0)
        w.flags.writeable = False
        _WEIGHTS[key] = w
    return w


_A0 = {}


def _neutral(wv):
    """The neutral area function resampled onto the sections, in m^2. Cached per config signature."""
    key = signature(wv)
    a0 = _A0.get(key)
    if a0 is None:
        g = wv['geometry']
        n = int(wv['sections'])
        neutral = np.asarray(g['neutral_cm2'], dtype=float) * 1e-4
        z = np.linspace(0.0, 1.0, len(neutral))
        a0 = np.exp(np.interp(np.linspace(0.0, 1.0, n), z, np.log(neutral)))
        a0.flags.writeable = False
        _A0[key] = a0
    return a0


def areas(p, wv):
    """Area function in m^2 from the log-area offsets `p` (one per control point)."""
    w = control_weights(int(wv['sections']), int(wv['geometry']['control_points']))
    return _neutral(wv) * np.exp(w.T @ np.asarray(p, dtype=float))


def solve(target, wv, p0=None, weights=None):
    """Bounded, damped Gauss-Newton for the control points whose area function has `target` formants.

    Returns dict(areas, p, formants, error_hz, iterations, converged). One solve is 2-10 ms and is cached by the
    caller: the renderer never calls it per block.
    """
    g = wv['geometry']
    target = np.asarray(target, dtype=float)
    k = len(target)
    cp = int(g['control_points'])
    n = int(wv['sections'])
    length = float(wv['tract_length_m'])
    wts = np.ones(k) if weights is None else np.asarray(weights, dtype=float)
    wts = wts / wts.sum()
    bound = float(g['bounds'])
    curv = float(g['curvature'])
    pin = float(g['scale_pin'])
    tol = float(g['tolerance_hz'])
    W = control_weights(n, cp)

    p = np.zeros(cp) if p0 is None else np.clip(np.asarray(p0, dtype=float), -bound, bound)
    # second difference (smoothness) and the uniform-scale direction (unidentifiable, pinned)
    D = np.zeros((cp - 2, cp))
    for i in range(cp - 2):
        D[i, i], D[i, i + 1], D[i, i + 2] = 1.0, -2.0, 1.0
    S = np.ones(cp)
    S[0] = 0.0
    S = S / np.linalg.norm(S)

    def jacobian(pp, A0):
        """dF/dp by forward differences of the same eigensolve the residual uses.

        An analytic sensitivity (perturbation of the Webster operator) was tried first and kept disagreeing with the
        eigensolver's own operator at the lip boundary, which silently destroyed the descent direction. Differentiating
        the real function costs control_points eigensolves (about 1 ms) and cannot disagree with itself; a forward
        difference is used rather than a central one because the step is small next to the curvature and it halves the
        cost of the only expensive thing in the solve.
        """
        j = np.empty((cp, k))
        base = wg.modes(A0, length, k)[0]
        for i in range(cp):
            step = np.zeros(cp)
            step[i] = 1e-4
            j[i] = (wg.modes(areas(pp + step, wv), length, k)[0] - base) / 1e-4
        return j

    def eigen(pp):
        return wg.modes(areas(pp, wv), length, k)[0]

    trust = float(g['trust'])                    # per-iteration limit on any control point; keeps a step out of
    it = 0                                       # the null space instead of slamming into the bounds

    def fit(eff, pp):
        """Damped Gauss-Newton on the eigenvalue surrogate for one effective target. Returns (p, iterations)."""
        A = areas(pp, wv)
        F = eigen(pp)
        n_it = 0
        for n_it in range(1, int(g['max_iterations']) + 1):
            err = F - eff
            if np.max(np.abs(err)) <= tol:
                break
            J = jacobian(pp, A) * wts[None, :]
            # Normal equations. The penalties are scaled to the data (trace of J^T J), otherwise a Jacobian of order
            # 1e4 Hz per unit log-area makes a fixed 0.12 smoothness weight vanish and the step walks the null space.
            Jw = J * wts[None, :]                # (cp, k): weighted sensitivity of each target to each control point
            H = Jw @ J.T                         # (cp, cp)
            scale = float(np.trace(H)) / cp
            M = H + curv * scale * (D.T @ D) + pin ** 2 * scale * np.outer(S, S)
            rhs = -(Jw @ (err * wts))
            try:
                step = np.linalg.solve(M, rhs)
            except np.linalg.LinAlgError:
                break
            m = float(np.max(np.abs(step)))
            if m > trust:
                step = step * (trust / m)
            base = float(np.sum((err * wts) ** 2))
            gain = 1.0
            for _ in range(8):                   # line search: never accept a step that makes the fit worse
                cand = np.clip(pp + gain * step, -bound, bound)
                Fc = eigen(cand)
                if float(np.sum(((Fc - eff) * wts) ** 2)) < base:
                    pp, F, A = cand, Fc, areas(cand, wv)
                    break
                gain *= 0.5
            else:
                break
        return pp, n_it

    # `modes` already carries the lip radiation end correction, so the eigenfrequency and the peak of the lip response
    # are the same number; the peak is still measured once at the end and reported, because the correction is an
    # approximation of a tapered termination and the difference is a fact the caller should see.
    p, it = fit(target, p)
    A = areas(p, wv)
    formants = eigen(p)
    err = formants - target
    return dict(areas=A, p=p, formants=formants, error_hz=err, iterations=it,
                converged=float(np.max(np.abs(err))) <= tol,
                peaks=wg.peaks(formants, A, length, wv))


_CACHE = {}


def params(F0, wv, sr, bw_table=None):
    """Physical (bandwidth, gain) for a formant target, from the solved geometry.

    One solve per distinct vowel in the engine's table, cached. Any other target (a glide, a style modification, a
    formant scale) gets the bandwidths and gains of its neighbours in formant space, blended by distance: the poles
    stay exactly where the score asked for them, and the physics supplies how wide and how loud each mode is.
    Interpolating physical parameters - not areas - is deliberate: an eigensolve per 5 ms block would cost more than
    the whole render.
    """
    vowels = np.asarray(F0, dtype=float)
    if vowels.ndim == 1:
        vowels = vowels[None, :]
    key = (signature(wv), sr, vowels.shape[1], tuple(np.round(vowels, 3).ravel()))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    k = vowels.shape[1]
    length = float(wv['tract_length_m'])
    # 20 Hz spacing: a 54 Hz grid gives two samples across a 110 Hz bandwidth, and the -3 dB measurement inherits
    # that resolution even after the crossing interpolation.
    fgrid = np.linspace(60.0, min(5200.0, 0.45 * sr), 256)
    names, anchors, bws, gs = [], [], [], []
    prev = None
    for i, target in enumerate(vowels):
        sol = solve(target, wv, p0=prev)         # warm start: neighbouring vowels differ by a smooth step
        prev = sol['p']
        A = sol['areas']
        H = wg.response(fgrid, A, length, wv)
        # Measured peaks, not the eigenfrequencies: the eigenproblem is a staircase of the real taper, so on a strongly
        # tapered shape it can sit 10 % above the peak the response actually has (measured: 730 Hz asked, 730 Hz
        # eigen, 648 Hz peak on /a/). Bandwidth and gain are read where |H| peaks, the only place they mean anything.
        f0 = sol['peaks']
        bw = wg.bandwidths(fgrid, H, f0)
        h = np.abs(wg.response(f0, A, length, wv))
        gvec = wg.bank_gains(f0, h, float(wv['gain_tilt_power']))
        names.append(tuple(np.round(target, 1)))
        anchors.append(f0)
        bws.append(bw)
        gs.append(gvec)

    out = dict(anchors=np.array(anchors), bw=np.array(bws), g=np.array(gs),
               targets=np.array(vowels), length=length,
               residual=np.array([np.abs(a - t).max() for a, t in zip(anchors, vowels)]))
    _CACHE[key] = out
    return out


def blend(table, target, sigma_hz=None):
    """Bandwidths and gains for a formant target (k,) or (k, m): distance-weighted over the solved anchors.

    `target` columns may be many points at once - a whole phrase's formant track - and each is blended against the
    anchors solved from the vowel table. Interpolating (BW, G) rather than re-solving is deliberate: an eigensolve
    every 5 ms block would cost an order of magnitude more than the whole render.
    """
    t = np.asarray(target, dtype=float)
    single = t.ndim == 1
    if single:
        t = t[:, None]
    k = t.shape[0]
    a = table['targets'][:, :k]                      # a preset may declare fewer formants than the table has
    bw, g = table['bw'][:, :k], table['g'][:, :k]
    sigma = float(sigma_hz if sigma_hz is not None else 260.0)
    scale = np.maximum(a, 1.0)
    d = np.sqrt(np.mean(((t.T[:, None, :] - a[None, :, :]) / scale[None, :, :]) ** 2, axis=2)) * 1000.0
    w = np.exp(-(d / sigma) ** 2)
    bad = ~np.isfinite(w).all(axis=1) | (w.sum(axis=1) <= 0)
    if bad.any():                                    # fall back to the nearest anchor rather than to a default
        w[bad] = 0.0
        w[bad, np.argmin(np.where(np.isfinite(d), d, np.inf), axis=1)[bad]] = 1.0
    w = w / w.sum(axis=1, keepdims=True)
    bw = (w @ bw).T                                  # (k, m)
    g = (w @ g).T
    return (bw[:, 0], g[:, 0]) if single else (bw, g)


def as_track(table, F, block, n, block_track):
    """Bandwidth and gain tracks for a (possibly per-sample) formant track, shaped like `F`.

    `F` is (k,) or (k, n). The blend is evaluated at the block centres the renderer already uses for the formants
    and then interpolated to every sample, so a moving vowel does not step its bandwidth at block boundaries and the
    filter state in `tract.resonate` is never asked to take a jump.
    """
    F = np.asarray(F, dtype=float)
    if F.ndim == 1 or F.shape[1] == 1:              # static vowel (or a track that never moved)
        bw, g = blend(table, F.reshape(-1) if F.ndim == 1 else F[:, 0])
        return bw.reshape(-1, 1), g.reshape(-1, 1)
    if np.ptp(F, axis=1).max() < 1.0:               # a track that is constant to within 1 Hz is a static vowel
        bw, g = blend(table, F[:, 0])
        return bw.reshape(-1, 1), g.reshape(-1, 1)
    k, n = F.shape
    nb = int(np.ceil(n / block))
    centres = np.minimum(np.arange(nb) * block + block // 2, n - 1)
    bw, g = blend(table, F[:, centres])              # (k, nb)
    # Hold each block's value for the block, rather than interpolating a per-sample track: `tract.resonate` reads
    # the track at exactly these block centres, so the two are the same signal to the filter and the repeat is a
    # memcpy where the interpolation was a 5 x n Python-level pass (measured: 1.7 s of a 5-voice 11 s phrase).
    bw = np.repeat(bw, block, axis=1)[:, :n]
    g = np.repeat(g, block, axis=1)[:, :n]
    return bw, g


_TABLE = {}


def table(cfg, sr):
    """The solved (bandwidth, gain) table for a voice config's vowel table, cached per signature."""
    wv = cfg['waveguide']
    vowels = cfg['tract']['vowels']
    V = np.asarray([vowels[k] for k in vowels], dtype=float)
    key = (signature(wv), sr, tuple(np.round(V, 3).ravel()))
    tab = _TABLE.get(key)
    if tab is None:
        tab = params(V, wv, sr)
        _TABLE[key] = tab
    return tab


def split(areas, wv):
    """Pharynx / oral / nasal split of a tract at the velum, for the 3-way junction.

    The velum sits at `wv['nasal']['velum_fraction']` of the tract length; the nasal branch is a separate, shorter
    tube of `nasal_length_m` with `nasal_sections` sections. The nasal area is not fitted to a formant - it is the
    cavity's own area, which is why the zeros it produces are a consequence rather than a placement.
    """
    nz = wv['nasal']
    n = len(areas)
    cut = int(np.clip(round(float(nz['velum_fraction']) * n), 2, n - 2))
    length = float(wv['tract_length_m'])
    l_ph = length * cut / n
    l_or = length * (n - cut) / n
    a_na = np.full(int(nz['nasal_sections']), float(nz['nasal_area_cm2']) * 1e-4)
    a_na[0] = float(nz['velum_area_cm2']) * 1e-4
    return dict(a_ph=areas[:cut], l_ph=l_ph, a_or=areas[cut:], l_or=l_or,
                a_na=a_na, l_na=float(nz['nasal_length_m']))
