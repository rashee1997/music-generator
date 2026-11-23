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

"""generators.py - the weather and micro-physics of a place, as stateful, chunk-exact generators.

    turbulence            vortex shedding (Aeolian tones) from obstacles in a gusting flow, plus a broadband residual
    particulate_impacts   drops, hail, grains or dust landing on a solid (modal ring) or a liquid (pulse + Minnaert bubble)
    modal_field           a resonant medium (ice, dune, hull, crystal) driven by events or by a continuous source

Every generator returns PRESSURE IN PASCALS at the reference distance (1 m), from the medium's own density and speed of
sound, so a drizzle and a downpour, or the same wind on Earth and on Titan, differ by physics and not by a normalisation.
`process(n)` can be called with any chunk sizes: the randomness is drawn in fixed blocks of 0.1 s and the filter state,
oscillator phases and event tails are carried, so the samples do not depend on how they were asked for.

The numbers a preset gives are checked by biome.schema; the constants here that are not from a source are labelled [start].
"""
import math

import numpy as np
from scipy import signal

from biome import physics
from phys_core import excite, geometry, materials as mat_mod, resonate

TAIL_S = 0.12                         # the longest event ring kept (s); longer rings are cut by their own envelope
RAMP_S = 0.0025                       # a real impact builds over a couple of milliseconds, so no ring starts with a step
GUST_RATE_HZ = 100.0


def db_to_lin(db):
    return 10.0 ** (float(db) / 20.0)


def unit_energy(w, sr):
    """Scale a waveform so that integral of w^2 dt = 1 (the convention of physics.pressure_scale_from_energy)."""
    e = float(np.sum(np.asarray(w, dtype=np.float64) ** 2)) / sr
    return w / math.sqrt(e) if e > 0 else w


class GustSeries:
    """Unit-variance turbulence series at 100 Hz whose spectrum falls as f^(-5/3) above `corner_hz` (von Karman / Kaimal).

    A bank of first-order sections with half-octave corners; for a target slope of -5/3 the variance of the section with
    corner f_j goes as f_j^(-2/3). Streams, unlike the FFT form in phys_core.excite.gust_series, which needs the whole
    series at once."""

    def __init__(self, corner_hz, rng, rate=GUST_RATE_HZ):
        self.rate = float(rate)
        top = min(0.2 * self.rate, 20.0)
        n = max(2, int(math.ceil(2.0 * math.log2(max(top / max(corner_hz, 1e-3), 2.0)))) + 1)
        f = float(corner_hz) * 2.0 ** (0.5 * np.arange(n))
        self.a = np.exp(-2.0 * math.pi * f / self.rate)
        v = f ** (-2.0 / 3.0)
        self.w = np.sqrt(v / v.sum())
        self.rng = rng
        self.x = rng.standard_normal(n)                  # start in the stationary state

    def next(self, m):
        out = np.empty(int(m))
        sd = np.sqrt(1.0 - self.a ** 2)
        noise = self.rng.standard_normal((int(m), len(self.a)))
        for i in range(int(m)):
            self.x = self.a * self.x + sd * noise[i]
            out[i] = float(np.dot(self.w, self.x))
        return out


class EventBank:
    """Waveform classes (each `tail` samples, unit energy) and their spectra at the size of one block's convolution."""

    def __init__(self, waves, block, tail):
        from scipy.fft import next_fast_len
        self.n = int(next_fast_len(block + tail, real=True))
        self.waves = waves
        self.spec = [np.fft.rfft(w, self.n) for w in waves]


class Generator:
    """Base: fixed 0.1 s blocks, event tails carried, output in Pa."""
    kind = ''

    def __init__(self, cfg, ctx):
        self.cfg, self.ctx = cfg, ctx
        self.name = str(cfg['name'])
        self.rng = ctx.rng(self.name)
        self.sr, self.B = ctx.sr, ctx.block
        self.med = ctx.medium
        self.index = 0
        self._out = np.zeros(0, np.float64)
        self.tail_len = int(TAIL_S * self.sr)
        self._carry = np.zeros(self.tail_len)

    def _ref(self, key, default=None):
        v = self.cfg.get(key, default)
        return v

    def process(self, n):
        n = int(n)
        while len(self._out) < n:
            blk = self._block()
            self.index += 1
            self._out = np.concatenate([self._out, blk])
        out, self._out = self._out[:n], self._out[n:]
        return out.astype(np.float32)

    def render(self, seconds):
        return self.process(int(round(float(seconds) * self.sr)))

    def _train(self, bank, pos, cls, amp):
        """Render a block of events: `pos` sample positions in the block, `cls` the waveform class of each, `amp` its pressure scale.

        One impulse train per class is transformed once and multiplied by that class's stored spectrum, so the cost does not
        grow with the number of events (a downpour has tens of thousands a second). The ring that runs past the block is
        carried into the next one."""
        B = self.B
        acc = None
        for c in np.unique(cls):
            m = cls == c
            imp = np.bincount(pos[m], weights=amp[m], minlength=B)[:B]
            spec = np.fft.rfft(imp, bank.n) * bank.spec[int(c)]
            acc = spec if acc is None else acc + spec
        y = np.fft.irfft(acc, bank.n)[:B + self.tail_len] if acc is not None else np.zeros(B + self.tail_len)
        if len(y) < B + self.tail_len:
            y = np.pad(y, (0, B + self.tail_len - len(y)))
        y[:self.tail_len] += self._carry
        self._carry = y[B:B + self.tail_len].copy()
        return y[:B]

    def expected_rms_pa(self, t_s=0.0):
        """The rms pressure at 1 m the physics predicts at time t_s (None when there is no closed form)."""
        return None

    def _block(self):
        raise NotImplementedError


# ------------------------------------------------------------------------------------------------ turbulence
class Turbulence(Generator):
    kind = 'turbulence'

    def __init__(self, cfg, ctx):
        super().__init__(cfg, ctx)
        ob, fl = cfg['obstacles'], cfg['flow']
        self.area = float(ob['frontal_area_m2'])
        K = int(ob.get('oscillators', 24))
        dd = ob['d_m']
        if dd.get('dist', 'fixed') == 'fixed':
            self.d = np.full(K, float(dd['value']))
        else:                                              # lognormal: stratified quantiles, so no random draw shapes the spectrum
            from statistics import NormalDist
            q = np.array([NormalDist().inv_cdf((k + 0.5) / K) for k in range(K)])
            self.d = float(dd['median']) * np.exp(float(dd['sigma']) * q)
        w = self.d / self.d.sum()                          # a thicker obstacle presents more frontal area
        self.share = w
        self.u_ref = fl['u_m_s']
        self.intensity = float(fl.get('intensity', 0.2))
        self.k_dipole = float(cfg.get('k_dipole', 1e-3))
        self.law = (cfg.get('strouhal') or {}).get('law', 'auto')
        bb = cfg.get('broadband') or {}
        self.bb_share = float(np.clip(bb.get('share', 0.3), 0.0, 1.0))
        band = bb.get('band_hz', [100.0, 5000.0])
        self.sos = signal.butter(2, [float(band[0]), min(float(band[1]), 0.45 * self.sr)], btype='bandpass', fs=self.sr, output='sos')
        _, h = signal.sosfreqz(self.sos, worN=8192)
        self.bb_gain = 1.0 / math.sqrt(float(np.mean(np.abs(h) ** 2)))     # unit-variance white noise in -> unit rms out
        self.zi = signal.sosfilt_zi(self.sos) * 0.0
        self.jit = float(cfg.get('tone_jitter', 0.02))
        self.jit_state = np.zeros(K)
        self.phase = self.rng.uniform(0.0, 2.0 * math.pi, K)
        self.gust = GustSeries(float(fl.get('gust_corner_hz', 0.1)), self.rng)
        self.prev_u = None
        self.prev_f = None
        self.med.reynolds(1.0, 1.0)                        # raises now, with its message, when the medium has no viscosity
        self.n_ctl = 10
        self.ctl_len = self.B // self.n_ctl

    def expected_rms_pa(self, t_s=0.0):
        u = float(self.ctx.controls.value(self.u_ref, float(t_s)))
        w = physics.dipole_power(self.k_dipole, self.med.rho, u, self.area, self.med.c)
        return physics.pressure_rms_from_power(self.med.z, w) * math.sqrt(1.0 + 15.0 * self.intensity ** 2)     # E[(1 + i z)^6]

    def _block(self):
        B, sr, n = self.B, self.sr, self.n_ctl
        t_ctl = self.index * B / sr + (np.arange(n) + 1) * (B / sr) / n
        z = self.gust.next(n)
        u_mean = np.asarray(self.ctx.controls.value(self.u_ref, t_ctl), dtype=float)
        u = np.maximum(u_mean * (1.0 + self.intensity * np.clip(z, -3.0, 3.0)), 0.0)
        if self.prev_u is None:
            self.prev_u = u[0]
        K = len(self.d)
        U = np.concatenate([[self.prev_u], u])
        re = self.med.rho * np.outer(U, self.d) / float(self.med.viscosity)
        st = np.vectorize(lambda r: physics.strouhal(r, self.law))(re)
        self.jit_state = 0.8 * self.jit_state + 0.2 * self.rng.standard_normal(K)
        f = st * U[:, None] / self.d[None, :] * (1.0 + self.jit * self.jit_state)[None, :]
        alive = (f > 1.0) & (f < 0.45 * sr)
        W = np.array([physics.dipole_power(self.k_dipole, self.med.rho, uu, self.area, self.med.c) for uu in U])
        p_rms = np.array([physics.pressure_rms_from_power(self.med.z, w) for w in W])
        amp = np.sqrt(2.0 * (1.0 - self.bb_share) * self.share)[None, :] * p_rms[:, None] * alive
        xs = np.concatenate([[0], (np.arange(n) + 1) * self.ctl_len]).astype(float)
        idx = np.arange(B, dtype=float)
        out = np.zeros(B)
        for k in range(K):
            fk = np.interp(idx, xs, f[:, k] * alive[:, k])
            ph = self.phase[k] + 2.0 * math.pi * np.cumsum(fk) / sr
            out += np.interp(idx, xs, amp[:, k]) * np.sin(ph)
            self.phase[k] = ph[-1] % (2.0 * math.pi)
        noise, self.zi = signal.sosfilt(self.sos, self.rng.standard_normal(B), zi=self.zi)
        out += noise * self.bb_gain * math.sqrt(self.bb_share) * np.interp(idx, xs, p_rms)
        self.prev_u = u[-1]
        return out


# ------------------------------------------------------------------------------------------------ particulate impacts
class Particulate(Generator):
    kind = 'particulate_impacts'
    N_BINS = 8

    def __init__(self, cfg, ctx):
        super().__init__(cfg, ctx)
        pop, sf = cfg['population'], cfg['surface']
        self.pop = pop
        self.rate_ref = pop['rate_mm_h']
        self.d_mm = pop.get('d_mm', [0.5, 6.0])
        self.rho_p = float(pop.get('rho_particle', 998.0))
        self.cd = float(pop.get('cd', 1.0))
        self.lam = pop.get('lambda_per_mm')
        self.eff = float(pop.get('efficiency', 1e-8))
        self.area = float(sf['area_m2'])
        self.liquid = sf.get('kind', 'solid') == 'liquid'
        self.K = int(sf.get('patches', 1))
        self.rho_l = float(sf.get('rho_kg_m3', self.rho_p))
        bb = cfg.get('bubbles') or {}
        self.bub_tab = np.asarray(bb.get('p_by_size', []), dtype=float).reshape(-1, 2)
        self.bub_ratio = float(bb.get('radius_ratio', 0.2))
        self.bub_share = float(bb.get('energy_share', 0.5))
        self.bub_t60 = float(bb.get('t60_s', 0.01))
        self._pop_cache = {}
        lib_rng = ctx.rng(self.name + '/library')
        self.bin_d = np.linspace(self.d_mm[0], self.d_mm[1], self.N_BINS) * 1e-3
        self.lib = self._library(sf, lib_rng)
        flat = [w for row in self.lib for w in row]
        if self.liquid and len(self.bub_tab):
            flat += self._bubble_library()
        self.bank = EventBank(flat, self.B, self.tail_len)

    # -- the drops that arrive
    def population(self, rate):
        key = round(float(rate), 1)
        if key not in self._pop_cache:
            self._pop_cache[key] = physics.drop_population(max(key, 0.0), self.d_mm, self.ctx.g, self.rho_p, self.med.rho,
                                                           self.cd, self.lam)
        return self._pop_cache[key]

    # -- one waveform per (patch, size bin): unit energy
    def _contact_s(self, d, v, stiffness):
        m = self.rho_p * math.pi * d ** 3 / 6.0
        if self.liquid:
            return float(np.clip(d / max(v, 1e-3), 1e-4, 0.05))           # the time a drop takes to enter its own diameter [derived scaling]
        return excite.contact_time(stiffness, m, v)

    def _library(self, sf, rng):
        sr, lib = self.sr, []
        n_len = self.tail_len
        t = np.arange(n_len) / sr
        ramp = np.ones(n_len)
        att = max(2, int(RAMP_S * sr))
        ramp[:att] = 0.5 - 0.5 * np.cos(np.pi * np.arange(att) / att)
        if not self.liquid:
            obj = {'material': sf.get('material', 'oak'), 'geometry': dict(sf.get('geometry') or {'shape': 'plate', 'width_m': 0.05,
                                                                                                     'thickness_m': 0.0005}),
                   'modes': int(sf.get('modes', 6))}
            f1, ratios, t60, mat = geometry.resolve(obj, self.ctx.materials)
            stiff = (4.0 / 3.0) * mat['young_modulus_gpa'] * 1e9 * math.sqrt(0.5 * float(np.mean(self.bin_d)))
        for _ in range(self.K):
            row = []
            scale = float(np.exp(rng.normal(0.0, 0.15)))                 # patches of one surface differ in size, so in pitch
            for d in self.bin_d:
                v = physics.terminal_velocity(self.ctx.g, d, self.rho_p, self.med.rho, self.cd)
                tau = self._contact_s(d, v, stiff if not self.liquid else 0.0)
                if self.liquid:
                    k = max(2, int(tau * sr))
                    pulse = np.zeros(n_len)
                    x = np.arange(min(k, n_len)) / max(k, 1)
                    pulse[:len(x)] = 1.0 - np.cos(2.0 * math.pi * x)       # the force pulse; the radiated pressure follows its slope
                    w = np.gradient(pulse) * sr
                else:
                    f = f1 * scale * ratios
                    keep = f < 0.45 * sr
                    f, r = f[keep], np.asarray(ratios)[keep]
                    decay = 6.907755 / mat_mod.mode_t60(t60, r, mat.get('damp_exp'))
                    cut = 1.0 / np.sqrt(1.0 + (math.pi * f * tau) ** 2)    # a longer contact excites fewer high modes
                    a = cut / np.maximum(r, 1e-9)
                    ph = rng.uniform(0.0, 2.0 * math.pi, len(f))
                    w = np.zeros(n_len)
                    for fn, dn, an, pn in zip(f, decay, a, ph):
                        w += an * np.exp(-dn * t) * np.sin(2.0 * math.pi * fn * t + 0.3 * pn)
                w = unit_energy(w * ramp, sr)
                row.append(w)
            lib.append(row)
        return lib

    def _bubble_wave(self, r):
        f = physics.minnaert_hz(r, self.med.gamma, self.med.pressure_pa, self.rho_l)
        if f >= 0.45 * self.sr:
            return None
        t = np.arange(self.tail_len) / self.sr
        dec = 6.907755 / self.bub_t60
        w = np.exp(-dec * t) * np.sin(2.0 * math.pi * f * (t + 0.05 * dec * t * t))
        k = max(2, int(RAMP_S * self.sr))
        w[:k] *= np.linspace(0.0, 1.0, k)
        return unit_energy(w, self.sr)

    def _bubble_library(self):
        """Bubble classes on a log grid of radii (a bubble's pitch is set by its radius, so by the class)."""
        self.bub_r = np.geomspace(0.6 * self.bub_ratio * self.d_mm[0] * 1e-3 / 2.0, 1.6 * self.bub_ratio * self.d_mm[1] * 1e-3 / 2.0, 24)
        waves = [self._bubble_wave(r) for r in self.bub_r]
        self.bub_ok = np.array([w is not None for w in waves])
        return [w if w is not None else np.zeros(self.tail_len) for w in waves]

    def p_bubble(self, d_mm):
        if not len(self.bub_tab):
            return np.zeros(np.shape(d_mm))
        return np.interp(d_mm, self.bub_tab[:, 0], self.bub_tab[:, 1])

    def expected_rms_pa(self, t_s=0.0):
        """Uncorrelated events: p_rms^2 = (events per second) x Z x (mean radiated energy) / 4 pi."""
        rate = float(self.ctx.controls.value(self.rate_ref, float(t_s)))
        d, pdf, v, per_m2_s = self.population(rate)
        e_a = self.eff * 0.5 * (self.rho_p * math.pi * d ** 3 / 6.0) * v ** 2
        mean_e = float((pdf * e_a).sum())
        return math.sqrt(per_m2_s * self.area * self.med.z * mean_e / (4.0 * math.pi))

    def _block(self):
        B, sr, K, nb = self.B, self.sr, self.K, self.N_BINS
        t_mid = (self.index + 0.5) * B / sr
        rate = float(self.ctx.controls.value(self.rate_ref, t_mid))
        d, pdf, v, per_m2_s = self.population(rate)
        n_ev = int(self.rng.poisson(per_m2_s * self.area * B / sr))
        pos = self.rng.integers(0, B, n_ev)
        size = self.rng.choice(len(d), size=n_ev, p=pdf)
        patch = self.rng.integers(0, K, n_ev)
        coin = self.rng.random(n_ev)
        spread = self.rng.standard_normal(n_ev)
        if not n_ev:
            return self._train(self.bank, np.zeros(0, int), np.zeros(0, int), np.zeros(0))
        dj, vj = d[size], v[size]
        e_a = self.eff * 0.5 * (self.rho_p * math.pi * dj ** 3 / 6.0) * vj ** 2
        with_bub = self.liquid and len(self.bub_tab) > 0
        share = self.bub_share if with_bub else 0.0
        b = np.abs(self.bin_d[None, :] - dj[:, None]).argmin(axis=1)
        z = self.med.z
        pos_all, cls_all, amp_all = [pos], [patch * nb + b], [np.sqrt(z * e_a * (1.0 - share) / (4.0 * math.pi))]
        if with_bub:
            has = coin < self.p_bubble(dj * 1e3)
            r = self.bub_ratio * dj / 2.0 * np.exp(0.2 * spread)
            bi = np.clip(np.abs(np.log(r[:, None]) - np.log(self.bub_r)[None, :]).argmin(axis=1), 0, len(self.bub_r) - 1)
            has &= self.bub_ok[bi]
            pos_all.append(pos[has])
            cls_all.append(K * nb + bi[has])
            amp_all.append(np.sqrt(z * e_a[has] * self.bub_share / (4.0 * math.pi)))
        return self._train(self.bank, np.concatenate(pos_all), np.concatenate(cls_all), np.concatenate(amp_all))


# ------------------------------------------------------------------------------------------------ modal field
class ModalField(Generator):
    kind = 'modal_field'

    def __init__(self, cfg, ctx):
        super().__init__(cfg, ctx)
        md, ex = cfg['modes'], cfg['excitation']
        self.ex = ex
        self.kindx = ex['kind']
        f, t60, gain = self._modes(md)
        keep = f < 0.45 * self.sr
        self.f, self.t60, self.gain = f[keep], t60[keep], gain[keep]
        if not len(self.f):
            raise ValueError(f'modal_field "{self.name}": every mode is above the Nyquist frequency')
        if self.kindx == 'continuous':
            self.level = ex['level_pa']
            self.q = float(ex.get('q', 30.0))
            self.sosl, self.zil, self.norm = [], [], []
            for fm in self.f:
                b, a = signal.iirpeak(fm, self.q, fs=self.sr)
                s = signal.tf2sos(b, a)
                _, h = signal.sosfreqz(s, worN=8192)
                self.sosl.append(s)
                self.zil.append(signal.sosfilt_zi(s) * 0.0)
                self.norm.append(math.sqrt(float(np.mean(np.abs(h) ** 2))))
            var = float(np.sum((self.gain * np.array(self.norm)) ** 2))
            self.cont_gain = 1.0 / math.sqrt(var)
        else:
            lib_rng = ctx.rng(self.name + '/library')
            self.wave = self._ring(lib_rng)
            self.bank = EventBank([self.wave], self.B, self.tail_len)
            self.rate = ex['rate_hz']
            self.energy = float(ex.get('energy_j', 1e-9))
            self.sigma = float(ex.get('sigma', 0.3 if self.kindx == 'poisson' else 0.5))
            self.shape = float(ex.get('burst_shape', 0.5))

    def _modes(self, md):
        if 'list' in md:
            arr = np.asarray(md['list'], dtype=float).reshape(-1, 3)
            return arr[:, 0], arr[:, 1], 10.0 ** (arr[:, 2] / 20.0)
        if md.get('law') == 'grain_vibration':
            f = physics.dune_hz(self.ctx.g, float(md['grain_size_m']), float(md.get('k', 0.4)))
            q = float(md.get('q', 30.0))
            return np.array([f]), np.array([6.907755 * q / (math.pi * f)]), np.array([1.0])
        obj = {'material': md['material'], 'geometry': dict(md['geometry']), 'modes': int(md.get('modes', 8))}
        f1, ratios, t60, mat = geometry.resolve(obj, self.ctx.materials)
        r = np.asarray(ratios, dtype=float)
        a = 1.0 / np.maximum(r, 1e-9)
        return f1 * r, mat_mod.mode_t60(t60, r, mat.get('damp_exp')), a / a.max()

    def _ring(self, rng):
        t = np.arange(self.tail_len) / self.sr
        w = np.zeros(self.tail_len)
        for fn, t60, g in zip(self.f, self.t60, self.gain):
            w += g * np.exp(-6.907755 / max(t60, 1e-4) * t) * np.sin(2.0 * math.pi * fn * t + rng.uniform(0, 0.5))
        ramp = np.ones(self.tail_len)
        att = max(2, int(RAMP_S * self.sr))
        ramp[:att] = 0.5 - 0.5 * np.cos(np.pi * np.arange(att) / att)
        return unit_energy(w * ramp, self.sr)

    def expected_rms_pa(self, t_s=0.0):
        if self.kindx == 'continuous':
            return float(self.ctx.controls.value(self.level, float(t_s)))
        rate = float(self.ctx.controls.value(self.rate, float(t_s)))
        return math.sqrt(rate * self.med.z * self.energy * math.exp(self.sigma ** 2) / (4.0 * math.pi))

    def _block(self):
        B, sr = self.B, self.sr
        if self.kindx == 'continuous':
            x = self.rng.standard_normal(B)
            out = np.zeros(B)
            for i, s in enumerate(self.sosl):
                y, self.zil[i] = signal.sosfilt(s, x, zi=self.zil[i])
                out += self.gain[i] * y
            t = (self.index + np.array([0.0, 1.0])) * B / sr
            lv = np.asarray(self.ctx.controls.value(self.level, t), dtype=float)
            return out * self.cont_gain * np.interp(np.arange(B), [0, B], np.atleast_1d(lv) if lv.size == 2 else [float(lv)] * 2)
        t_mid = (self.index + 0.5) * B / sr
        lam = float(self.ctx.controls.value(self.rate, t_mid)) * B / sr
        if self.kindx == 'stress':                       # bursts: the count per block is gamma-mixed Poisson (overdispersed)
            lam = float(self.rng.gamma(self.shape, lam / self.shape)) if lam > 0 else 0.0
        n_ev = int(self.rng.poisson(lam))
        pos = self.rng.integers(0, B, n_ev)
        amp = np.exp(self.sigma * self.rng.standard_normal(n_ev) - 0.5 * self.sigma ** 2)
        scale = np.sqrt(self.med.z * self.energy * amp ** 2 / (4.0 * math.pi))
        return self._train(self.bank, pos, np.zeros(n_ev, int), scale)


KINDS = {'turbulence': Turbulence, 'particulate_impacts': Particulate, 'modal_field': ModalField}


def build(cfg, ctx):
    """The generator a preset block describes. Raises on an unknown kind (it would render as silence)."""
    kind = cfg.get('kind')
    if kind not in KINDS:
        raise ValueError(f'generator "{cfg.get("name")}": unknown kind "{kind}" (known: {", ".join(sorted(KINDS))})')
    return KINDS[kind](cfg, ctx)
