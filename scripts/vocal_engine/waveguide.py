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

"""Acoustic tube physics for the vocal tract. Pure numpy, no audio state, no presets.

A vocal tract is a chain of cylindrical sections. Two models live here:

* `chain` / `nasal_chain` - the analytic (frequency domain) response of a lossy, non-uniform tube, evaluated on a
  complex grid. This is the *reference*: it is what every number the renderer uses is measured from.
* `kl` - the time-domain Kelly-Lochbaum network, sample by sample. It is a reference and a gesture generator, never
  the render path: it costs ~0.36 s of CPU per audio second per voice (measured), against 0.016 s for the resonator
  bank. `tests/test_vocal_waveguide.py` uses it to prove the scattering network is phase-preserving.

The scattering junction is the standard lossless one. For two sections with areas A1, A2 and
k = (A1 - A2) / (A1 + A2):

    p1- = (1 - k) p2+ + k p1+
    p2- = (1 + k) p1+ - k p2+

and for N waveguides meeting at a junction (the pharynx, where the tract splits into oral and nasal branches) with
admittance Y_i = A_i / (rho c):

    p_J = 2 sum_i(Y_i p_i+) / sum_i(Y_i),      p_i- = p_J - p_i+

Sign convention follows Rocchesso, *Sound Modeling* eq. 7.18-7.20. Note that a *uniform* tube is blind to the sign of
the backward term (k = 0), so the sign is proved by a tapered tube, not by a uniform one - see the gate tests.
"""
import numpy as np

# Physical constants of air at 20 C. The speed of sound and the density are properties of the medium, not of a piece;
# every acoustic number derived from them (formants, bandwidths, impedances) is a measurement against these.
C_AIR = 343.0
RHO_AIR = 1.2
MU_AIR = 1.8e-5
PR_AIR = 0.71
GAMMA_AIR = 1.4
LIP_LENGTH = 8.0 / (3.0 * np.pi)      # flanged-piston radiation end correction, in lip radii (Morse & Ingard;
                                      # Petersen & Fant 1994 for the speech case). 0.849 r.


def _w(s):
    """Angular frequency continued off the real axis. s = j*w on the real axis; a small +j keeps sqrt() on the causal
    branch so a complex evaluation never returns the conjugate pole."""
    s = np.asarray(s, dtype=complex)
    w = -1j * s
    return np.where(np.real(w) > 1e-6, w + 1e-12j, 1e-6 + 1e-12j)


def gamma(s, radius, wv):
    """Propagation constant of a lossy narrow tube (boundary layer + optional calibrated damping).

    alpha: viscous and thermal boundary-layer losses, from the Stokes layer thickness sqrt(2 mu / (rho w)).
    beta:  the lossless wavenumber w/c plus the small boundary-layer dispersion.
    The calibrated term (k0, k1) stands for wall vibration and the losses a one-dimensional model cannot express;
    it is what brings formant bandwidths up to measured values (Fant 1972 separates wall, surface and radiation
    losses; the raw boundary layer alone gives 22-131 Hz where speech shows 50-300 Hz).
    """
    w = _w(s)
    k = np.sqrt(w * MU_AIR / RHO_AIR / 2.0) / (radius * C_AIR)
    alpha = k * (1.0 + (GAMMA_AIR - 1.0) / np.sqrt(PR_AIR))
    beta = w / C_AIR + k * (1.0 - (GAMMA_AIR - 1.0) / np.sqrt(PR_AIR))
    alpha = alpha + float(wv['losses']['k0_per_m']) + float(wv['losses']['k1_s_per_m']) * w
    return alpha + 1j * beta


def radiation(s, area, wv):
    """Radiation load at the lips, normalised by the section's characteristic impedance: (ka)^2/2 + j(8/3pi)ka.
    Low-ka expansion of a flanged piston; the clip keeps the parasitic real part from exceeding the tube's own
    impedance at the top of the band."""
    w = _w(s)
    ka = w * np.sqrt(area / np.pi) / C_AIR
    ka = np.minimum(ka, float(wv['radiation']['ka_max']))
    return 0.5 * ka ** 2 + 1j * (8.0 / (3 * np.pi)) * ka


def _load(s, area, wv, closed=False):
    """Normalised termination: radiation (open) or a hard wall (closed)."""
    z0 = RHO_AIR * C_AIR / area
    if closed:
        return np.full(np.shape(s), z0 * 1e9, dtype=complex)
    return z0 * radiation(s, area, wv)


def _section(s, area, length, z_out, wv):
    """One conical/cylindrical section: transfer factor and the impedance seen looking into it."""
    z0 = RHO_AIR * C_AIR / area
    gl = gamma(s, np.sqrt(area / np.pi), wv) * length
    gl = np.where(np.real(gl) > 40.0, 40.0 + 1j * np.imag(gl), gl)      # cosh/sinh overflow guard
    ch, sh = np.cosh(gl), np.sinh(gl)
    th = sh / ch
    t = ch + (z0 / z_out) * sh
    z_in = z0 * (z_out + z0 * th) / (z0 + z_out * th)
    return t, z_in


def chain(s, areas, length, wv, closed=False):
    """Pressure at the lips per unit volume velocity at the glottis, for a single tube of `areas` (m^2).

    `s` is complex angular frequency (use `1j*2*pi*f` for the real axis). Returns the complex transfer function.
    """
    s = np.atleast_1d(np.asarray(s, dtype=complex))
    n = len(areas)
    l = length / n
    z = _load(s, areas[-1], wv, closed=closed)
    t = np.ones(s.shape, dtype=complex)
    for j in range(n - 1, -1, -1):
        f, z = _section(s, areas[j], l, z, wv)
        t = t * f
    return z / t


def response(f, areas, length, wv, closed=False):
    """`chain` on the real frequency axis."""
    return chain(1j * 2 * np.pi * np.asarray(f, dtype=float), areas, length, wv, closed=closed)


def nasal_chain(s, a_ph, l_ph, a_or, l_or, a_na, l_na, wv, oral_closed=True):
    """The 3-way pharynx junction: tract below, oral branch, nasal branch.

    The two upper branches are parallel loads at the velum, so the junction is an impedance split and the nasal branch
    carries its own transmission. The antiresonance is not placed: a closed oral branch of length l has an input
    impedance that goes to zero at c/(4l), which is the /m/ zero. Returns pressure at the nostrils per unit flow at
    the glottis.
    """
    s = np.atleast_1d(np.asarray(s, dtype=complex))
    # oral branch, velum -> lips, closed at the lips
    z_or = _load(s, a_or[-1], wv, closed=oral_closed)
    lo = l_or / len(a_or)
    for j in range(len(a_or) - 1, -1, -1):
        _, z_or = _section(s, a_or[j], lo, z_or, wv)
    # nasal branch, velum -> nostrils, open
    z_na = _load(s, a_na[-1], wv)
    ln = l_na / len(a_na)
    t_na = np.ones(s.shape, dtype=complex)
    z_in_na = z_na
    for j in range(len(a_na) - 1, -1, -1):
        f, z_in_na = _section(s, a_na[j], ln, z_in_na, wv)
        t_na = t_na * f
    # junction: the two upper branches in parallel, then down the pharynx
    z_j = 1.0 / (1.0 / z_or + 1.0 / z_in_na)
    t_ph = np.ones(s.shape, dtype=complex)
    lp = l_ph / len(a_ph)
    for j in range(len(a_ph) - 1, -1, -1):
        f, z_j = _section(s, a_ph[j], lp, z_j, wv)
        t_ph = t_ph * f
    # pressure at the nostrils = junction pressure / nasal transmission; junction pressure = z_j / (t_ph*t_na)
    return z_j / (t_ph * t_na)


def nasal_response(f, a_ph, l_ph, a_or, l_or, a_na, l_na, wv, oral_closed=True):
    return nasal_chain(1j * 2 * np.pi * np.asarray(f, dtype=float), a_ph, l_ph, a_or, l_or, a_na, l_na, wv,
                       oral_closed=oral_closed)


def modes(areas, length, k, c=C_AIR, lip=True):
    """Webster eigenproblem for a hard-walled tube: Neumann at the glottis, Dirichlet at the lips.

    Returns (F_hz[k], p[n, k]); p is the pressure eigenvector, zero at the lip. The eigenfrequencies are the
    resonances the area function actually has, which is what makes them a measurement rather than a target.

    `lip` adds the radiation end correction: the lip load's reactance is (8/3pi)ka, i.e. the mass of a tube length
    (8/3pi)r, so the Dirichlet node sits at L + (8/3pi)r rather than at L. Measured on a uniform 17 cm tube of
    2 cm^2: analytic 504 Hz, uncorrected Dirichlet 516 Hz, corrected 485 Hz, peak of the lip response 489 Hz. The
    correction is what makes the eigenfrequency the same number as the formant. Pass lip=False to compare against a
    network with a hard-open (p = 0) lip such as `kl`, which has no radiation load at all.
    """
    n = len(areas)
    if lip:
        length = length + LIP_LENGTH * np.sqrt(areas[-1] / np.pi)
    dx = length / n
    iface = 0.5 * (areas[1:] + areas[:-1])
    nn = n - 1                                   # the lip node is fixed at p = 0 (Dirichlet), so it is not an
    K = np.zeros((nn, nn))                       # unknown: building it as a penalty double-counts the last stiffness
    idx = np.arange(nn - 1)
    K[idx + 1, idx + 1] += iface[:-1]
    K[idx, idx] += iface[:-1]
    K[idx + 1, idx] -= iface[:-1]
    K[idx, idx + 1] -= iface[:-1]
    K[nn - 1, nn - 1] += iface[-1]
    m = areas[:-1] * dx * dx
    s = 1.0 / np.sqrt(m)
    w, v = np.linalg.eigh(K * np.outer(s, s))
    k = min(k, nn)
    # v is the eigenvector of the symmetrised system; the generalised eigenvector is p = S v with S = diag(1/sqrt(M)),
    # so this p satisfies p^T K p = lambda and p^T M p = 1 exactly. The Jacobian reads the same p (padded at the lip).
    p = np.zeros((n, k))
    p[:-1, :] = v[:, :k] * s[:, None]
    return np.sqrt(np.maximum(w[:k], 1e-12)) * c / (2 * np.pi), p



def peaks(f_pred, areas, length, wv, span=0.12, points=61, closed=False):
    """Measured formant frequencies: the local maximum of the lip response near each predicted frequency.

    This is the independent check on `modes`, not the value the renderer uses: `modes` states the resonance from the
    eigenproblem (with the lip end correction), this measures the peak of the analytic response. They are the same
    number when the model is right, and reporting both keeps the agreement a measurement rather than a claim.

    The search windows are disjoint by construction - each is bounded by the midpoints to its neighbours - because an
    overlap lets two modes latch onto one strong peak and report it twice (measured: 2039 Hz for both F2 and F3 of
    /e/).
    """
    f_pred = np.asarray(f_pred, dtype=float)
    k = len(f_pred)
    lo, hi = _peak_windows(f_pred, span)
    g = np.linspace(0.0, 1.0, points)[None, :]
    f = lo[:, None] + g * (hi - lo)[:, None]
    mag = np.abs(response(f.ravel(), areas, length, wv, closed=closed)).reshape(k, points)
    i = np.argmax(mag, axis=1)
    df = (hi - lo) / (points - 1)
    out = f[np.arange(k), i].copy()
    for m in range(k):
        j = i[m]
        if 0 < j < points - 1:
            y0, y1, y2 = mag[m, j - 1], mag[m, j], mag[m, j + 1]
            d = y0 - 2.0 * y1 + y2
            if abs(d) > 1e-30:
                out[m] = out[m] + 0.5 * (y0 - y2) / d * df[m]
    return out


def _peak_windows(f_pred, span):
    """(lo, hi) search window per mode, each bounded by the midpoints to its neighbours so no two overlap. A window
    narrower than 40 Hz is kept at the neighbour midpoint rather than widened into the next one."""
    k = len(f_pred)
    mid = np.empty(k + 1)
    if k == 1:                                       # one mode: the neighbour gap is unknown, so bound it by 45 %
        mid[0], mid[-1] = f_pred[0] * 0.55, f_pred[0] * 1.45
    else:
        mid[1:-1] = 0.5 * (f_pred[1:] + f_pred[:-1])
        mid[0] = f_pred[0] - 0.45 * (mid[1] - f_pred[0])
        mid[-1] = f_pred[-1] + 0.45 * (f_pred[-1] - mid[k - 1])
    lo = np.maximum(np.maximum(f_pred * (1.0 - span), mid[:-1]), 20.0)
    hi = np.minimum(np.maximum(f_pred * (1.0 + span), lo + 40.0), mid[1:])
    return lo, hi


def bandwidths(f, H, F0, floor_hz=6.0):
    """-3 dB width of each peak of |H| around its mode frequency, read off the measured response.

    This is a measurement of the physics, not a table: whatever the losses do is what the renderer gets.
    """
    f = np.asarray(f, dtype=float)
    mag = np.abs(H)
    out = np.empty(len(F0))
    for i, f0 in enumerate(F0):
        near = np.abs(f - f0) < 0.35 * f0 + 80.0
        if not near.any():
            out[i] = floor_hz
            continue
        idx = np.nonzero(near)[0]
        pk = idx[int(np.argmax(mag[idx]))]
        half = mag[pk] / np.sqrt(2.0)
        lo = pk
        while lo > 0 and mag[lo] > half:
            lo -= 1
        hi = pk
        while hi < len(mag) - 1 and mag[hi] > half:
            hi += 1
        out[i] = max(_cross(f, mag, hi, half) - _cross(f, mag, lo, half), floor_hz)
    return out


def _cross(f, mag, j, level):
    """Frequency at which |H| crosses `level`, interpolated between sample j and its neighbour above the level.

    Without this the width is quantised to the grid step: on a 54 Hz grid the raw bin difference reported 162/216/270
    Hz for crossings that are really 150/203/259 Hz, and the renderer's filters would inherit that staircase.
    """
    if j <= 0:
        return f[0]
    if j >= len(mag) - 1:
        return f[-1]
    a = j - 1 if mag[j - 1] >= level else j + 1
    if mag[a] == mag[j]:
        return f[j]
    t = (level - mag[j]) / (mag[a] - mag[j])
    return f[j] + float(np.clip(t, 0.0, 1.0)) * (f[a] - f[j])


def bank_gains(F0, h, tilt_power, floor=0.02):
    """Amplitude of each mode in the engine's parallel resonator bank, from the measured response.

    A unity-peak resonator contributes its peak height, so the physical amplitude of mode i is |H| at that peak. That
    alone is not enough: the parallel bank has no source tilt in it, the source does, and the table these gains
    replace (`tract.gains`) is the balance every melodic preset was voiced against. So the measured amplitude is
    tilted by (F_i/F_1)^-`tilt_power`, with `tilt_power` calibrated once across every vowel in the table against
    those legacy gains (a least-squares fit in log amplitude). Per-vowel variation then comes from the measurement
    and only the overall tilt is a calibration.

    Returns gains in [floor, 1], normalised to the loudest mode.
    """
    h = np.maximum(np.asarray(h, dtype=float), 1e-12)
    F0 = np.maximum(np.asarray(F0, dtype=float), 20.0)
    g = (h / h.max()) * (F0 / F0[0]) ** (-float(tilt_power))
    g = np.maximum(g / g.max(), floor)
    return g



def kl(x, areas, r_glottis=1.0, r_lip=-1.0):
    """Time-domain Kelly-Lochbaum network. Reference only - one Python iteration per sample.

    `x` is the glottal excitation (volume velocity), `areas` the section areas. Returns the pressure radiated at the
    lips. With a uniform area, r_glottis = 0 and r_lip = 0 this is an exact delay of len(areas) samples with unit
    magnitude at every frequency: the all-pass / no-dispersion control in the gate.
    """
    x = np.asarray(x, dtype=float)
    a = np.asarray(areas, dtype=float)
    n = len(a)
    k = (a[:-1] - a[1:]) / (a[:-1] + a[1:])
    f = np.zeros(n)
    b = np.zeros(n)
    y = np.empty(len(x))
    fwd = 1.0 + k
    bwd = 1.0 - k
    for i in range(len(x)):
        fn = np.empty(n)
        bn = np.empty(n)
        # forward wave into section m+1, backward wave out of section m (Rocchesso 7.20)
        fn[1:] = fwd * f[:-1] - k * b[1:]
        bn[:-1] = k * f[:-1] + bwd * b[1:]
        fn[0] = x[i] + r_glottis * b[0]
        bn[-1] = r_lip * f[-1]
        y[i] = (1.0 - r_lip) * f[-1]
        f, b = fn, bn
    return y


def kl_response(areas, n_fft=4096, **kw):
    """Impulse response and magnitude response of the network (for the gate)."""
    x = np.zeros(n_fft)
    x[0] = 1.0
    h = kl(x, areas, **kw)
    return h, np.abs(np.fft.rfft(h))
