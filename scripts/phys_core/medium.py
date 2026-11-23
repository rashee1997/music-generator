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
"""medium.py - the one object that says what sound travels through.

Before this module the speed of sound was a literal in six modules, and absorption had three owners (environment.py,
phys_core/propagate.py, spatial_engine/hoa.py). A medium is data:

    {"model": "iso9613", "state": {"temperature_k": 292.15, "pressure_pa": 89900, "rh_percent": 96}}      Earth air
    {"model": "ideal_gas", "gas": {...}, "state": {...}, "relaxations": [{"f_hz": ..., "mu_max": ...}]}    any gas
    {"model": "liquid", "c_m_s": 1400, "rho_kg_m3": 450}                                                   a sea

Bulk state (ideal gas):          c = sqrt(gamma R T / M),   rho = p M / (R T),   Z = rho c
Absorption, any gas, Np/m:       alpha(f) = a_cl f^2 + sum_i (2 mu_i / c) (f^2 / f_r,i) / (1 + (f / f_r,i)^2)
    mu_i is the peak absorption per wavelength of relaxation process i (at f = f_r,i). ISO 9613-1 is exactly this form
    with two processes (O2 and N2) whose f_r and mu follow from temperature, humidity and pressure (`iso_terms`), so
    Earth air is one instance of the general law and its numbers are reproduced to rounding (tests/test_medium.py).
Classical term (viscosity and heat conduction):  a_cl = (2 pi)^2 / (2 rho c^3) * eta * (4/3 + (gamma - 1) / Pr)
Interface between two media:     T = 4 Z1 Z2 / (Z1 + Z2)^2   (energy transmission)

`active()` is the medium the renderers read when nothing says otherwise; it defaults to the Earth reference
(c = 343.0 m/s at 20 C, the speed the repo has always used), so a project that declares no medium renders as before.
`playback` constants (the head model of a binaural decoder, a loudspeaker room's modes) are NOT read from here: they
describe where the finished programme is heard, not where it was recorded.

Every number a preset gives is checked against SCHEMA (unknown keys and out-of-range values are errors, never clamped).
"""
import contextlib
import math

import numpy as np

R_GAS = 8.314462618                 # J/(mol K), CODATA 2018
EARTH_C = 343.0                     # m/s at 293.15 K: the reference speed every module used before there was a medium
T_REF = 293.15
MODELS = ('ideal_gas', 'iso9613', 'liquid')
PROFILES = ('log', 'power')
BASES = ('power', 'pressure')
TAPS = 1025                         # odd, so the centre tap is an exact integer delay (as airabs.py)

# path -> (default, low, high, unit, what it does)
SCHEMA = {
    'gas.molar_mass_kg_mol': (0.02897, 0.002, 0.5, 'kg/mol', 'mean molar mass of the gas'),
    'gas.gamma': (1.40, 1.0, 1.7, '-', 'ratio of specific heats'),
    'gas.viscosity_pa_s': (None, 1e-7, 1e-3, 'Pa s', 'dynamic viscosity; with prandtl it gives the classical absorption and Reynolds numbers'),
    'gas.prandtl': (None, 0.3, 2.0, '-', 'Prandtl number'),
    'state.temperature_k': (T_REF, 1.0, 2000.0, 'K', 'air or liquid temperature'),
    'state.pressure_pa': (101325.0, 1.0, 1e9, 'Pa', 'ambient pressure (a depth in a liquid raises it)'),
    'state.rh_percent': (50.0, 0.0, 100.0, '%', 'relative humidity; the iso9613 model only'),
    'c_m_s': ('auto', 1.0, 20000.0, 'm/s', 'speed of sound; a number overrides the model'),
    'rho_kg_m3': ('auto', 1e-4, 30000.0, 'kg/m3', 'density; a number overrides the model'),
    'c_measured_m_s': (None, 1.0, 20000.0, 'm/s', 'a measurement the declared state must agree with (env.medium_consistency)'),
    'classical': ('auto', 0.0, 1e-6, 'Np/m/Hz^2', 'absorption growing as f squared; auto = from viscosity, Prandtl and gamma'),
}
KEYS = ('name', 'model', 'gas', 'state', 'c_m_s', 'rho_kg_m3', 'c_measured_m_s', 'classical', 'relaxations', 'flow',
        'boundary', 'level_ref', 'sources', 'note')
GAS_KEYS = ('molar_mass_kg_mol', 'gamma', 'viscosity_pa_s', 'prandtl', 'composition')
STATE_KEYS = ('temperature_k', 'pressure_pa', 'rh_percent')
RELAX_KEYS = ('f_hz', 'mu_max', 'sources', 'name')
FLOW_KEYS = ('u_ref_m_s', 'z_ref_m', 'profile', 'gust_corner_hz', 'power_exponent')
BOUNDARY_KEYS = ('canopy', 'ground')
CANOPY_KEYS = ('excess_db_per_m', 'sources')
GROUND_KEYS = ('material', 'height_m')
LEVEL_KEYS = ('basis', 'p_ref_pa')


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _check(path, v, out):
    spec = SCHEMA[path]
    if not _num(v):
        out.append(f'{path}: needs a number ({spec[3]}), got {v!r}')
    elif not spec[1] <= v <= spec[2]:
        out.append(f'{path}={v}: outside {spec[1]} to {spec[2]} {spec[3]}')


def problems(cfg, where='medium'):
    """Every problem of a medium preset (a dict), as plain sentences. Empty means it can be built."""
    if not isinstance(cfg, dict):
        return [f'{where}: a medium is an object (see phys_core/medium.py)']
    out = []
    for k in cfg:
        if k not in KEYS:
            out.append(f'{where}: unknown key "{k}" (known: {", ".join(KEYS)})')
    model = cfg.get('model', 'ideal_gas')
    if model not in MODELS:
        out.append(f'{where}.model "{model}": use one of {", ".join(MODELS)}')
        return out
    gas, state = cfg.get('gas') or {}, cfg.get('state') or {}
    for blk, name, keys in ((gas, 'gas', GAS_KEYS), (state, 'state', STATE_KEYS)):
        if not isinstance(blk, dict):
            out.append(f'{where}.{name}: an object')
            continue
        for k, v in blk.items():
            if k not in keys:
                out.append(f'{where}.{name}: unknown key "{k}" (known: {", ".join(keys)})')
            elif k != 'composition' and f'{name}.{k}' in SCHEMA:
                _check(f'{name}.{k}', v, out)
    for k in ('c_m_s', 'rho_kg_m3', 'classical'):
        v = cfg.get(k, 'auto')
        if v != 'auto':
            _check(k, v, out)
    if cfg.get('c_measured_m_s') is not None:
        _check('c_measured_m_s', cfg['c_measured_m_s'], out)
    if model == 'liquid':
        for k in ('c_m_s', 'rho_kg_m3'):
            if cfg.get(k, 'auto') == 'auto':
                out.append(f'{where}.{k}: a liquid has no ideal-gas default; give a number')
    if model == 'iso9613' and cfg.get('relaxations'):
        out.append(f'{where}.relaxations: the iso9613 model computes its own; use ideal_gas to list your own')
    if model == 'ideal_gas' and cfg.get('classical', 'auto') == 'auto':
        if gas.get('viscosity_pa_s') is None or gas.get('prandtl') is None:
            out.append(f'{where}.classical "auto" needs gas.viscosity_pa_s and gas.prandtl; give both, or give classical a number '
                       f'(0 for none): there is no silent default')
    rel = cfg.get('relaxations', [])
    if not isinstance(rel, list):
        out.append(f'{where}.relaxations: a list of {{"f_hz", "mu_max"}}')
        rel = []
    for i, r in enumerate(rel):
        if not isinstance(r, dict):
            out.append(f'{where}.relaxations[{i}]: an object {{"f_hz", "mu_max"}}')
            continue
        for k in r:
            if k not in RELAX_KEYS:
                out.append(f'{where}.relaxations[{i}]: unknown key "{k}" (known: {", ".join(RELAX_KEYS)})')
        if not _num(r.get('f_hz')) or not 1.0 <= r['f_hz'] <= 1e7:
            out.append(f'{where}.relaxations[{i}].f_hz: a number from 1 to 1e7 Hz')
        if not _num(r.get('mu_max')) or not 0.0 <= r['mu_max'] <= 1.0:
            out.append(f'{where}.relaxations[{i}].mu_max: a number from 0 to 1 (absorption per wavelength at the peak)')
    flow = cfg.get('flow')
    if flow is not None:
        if not isinstance(flow, dict):
            out.append(f'{where}.flow: an object')
        else:
            out += [f'{where}.flow: unknown key "{k}" (known: {", ".join(FLOW_KEYS)})' for k in flow if k not in FLOW_KEYS]
            if flow.get('profile', 'power') not in PROFILES:
                out.append(f'{where}.flow.profile: one of {", ".join(PROFILES)}')
    bd = cfg.get('boundary')
    if bd is not None:
        if not isinstance(bd, dict):
            out.append(f'{where}.boundary: an object')
        else:
            out += [f'{where}.boundary: unknown key "{k}" (known: {", ".join(BOUNDARY_KEYS)})' for k in bd if k not in BOUNDARY_KEYS]
            can = bd.get('canopy')
            if can is not None:
                if not isinstance(can, dict):
                    out.append(f'{where}.boundary.canopy: an object')
                else:
                    out += [f'{where}.boundary.canopy: unknown key "{k}" (known: {", ".join(CANOPY_KEYS)})' for k in can if k not in CANOPY_KEYS]
                    tab = can.get('excess_db_per_m')
                    ok = (isinstance(tab, list) and len(tab) >= 2 and all(isinstance(p, (list, tuple)) and len(p) == 2
                                                                         and _num(p[0]) and _num(p[1]) and p[0] > 0 and p[1] >= 0 for p in tab)
                          and all(tab[i][0] < tab[i + 1][0] for i in range(len(tab) - 1)))
                    if not ok:
                        out.append(f'{where}.boundary.canopy.excess_db_per_m: [[f_hz, dB per metre], ...] with rising f_hz, at least two points, dB >= 0')
            gr = bd.get('ground')
            if gr is not None and (not isinstance(gr, dict) or any(k not in GROUND_KEYS for k in gr)):
                out.append(f'{where}.boundary.ground: an object with {", ".join(GROUND_KEYS)}')
    lv = cfg.get('level_ref')
    if lv is not None:
        if not isinstance(lv, dict) or any(k not in LEVEL_KEYS for k in lv):
            out.append(f'{where}.level_ref: an object with {", ".join(LEVEL_KEYS)}')
        elif lv.get('basis', 'power') not in BASES:
            out.append(f'{where}.level_ref.basis: one of {", ".join(BASES)}')
    return out


def iso_terms(temperature_k=T_REF, rh_percent=50.0, pressure_kpa=101.325, c=EARTH_C):
    """ISO 9613-1 written as the general law: (classical Np/m/Hz^2, [(f_r Hz, mu), ...] for O2 then N2).

    The standard's two terms are A (f^2 / f_r) / (1 + (f / f_r)^2), so mu = A c / 2 for the speed `c` the caller uses."""
    T, T0, T01, pr = float(temperature_k), T_REF, 273.16, 101.325
    pp = float(pressure_kpa) / pr
    C = -6.8346 * (T01 / T) ** 1.261 + 4.6151
    h = float(rh_percent) * 10.0 ** C / pp
    fr_o = pp * (24.0 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    fr_n = pp * (T / T0) ** -0.5 * (9.0 + 280.0 * h * math.exp(-4.170 * ((T / T0) ** (-1.0 / 3.0) - 1.0)))
    a_o = (T / T0) ** -2.5 * 0.01275 * math.exp(-2239.1 / T)
    a_n = (T / T0) ** -2.5 * 0.1068 * math.exp(-3352.0 / T)
    cl = 1.84e-11 / pp * (T / T0) ** 0.5
    return cl, [(fr_o, a_o * c / 2.0), (fr_n, a_n * c / 2.0)]


class Medium:
    """One acoustic medium. Build it from a preset dict; `Medium()` is Earth air at 20 C, 50 % RH, 101.325 kPa."""

    def __init__(self, cfg=None):
        cfg = dict(cfg or {'model': 'iso9613'})
        bad = problems(cfg)
        if bad:
            raise ValueError('medium: ' + '; '.join(bad))
        self.cfg = cfg
        self.name = str(cfg.get('name', cfg.get('model', 'ideal_gas')))
        self.model = cfg.get('model', 'ideal_gas')
        gas, st = cfg.get('gas') or {}, cfg.get('state') or {}
        self.molar_mass = float(gas.get('molar_mass_kg_mol', SCHEMA['gas.molar_mass_kg_mol'][0]))
        self.gamma = float(gas.get('gamma', SCHEMA['gas.gamma'][0]))
        self.viscosity = gas.get('viscosity_pa_s')
        self.prandtl = gas.get('prandtl')
        self.temperature_k = float(st.get('temperature_k', T_REF))
        self.pressure_pa = float(st.get('pressure_pa', 101325.0))
        self.rh = float(st.get('rh_percent', 50.0))
        c = cfg.get('c_m_s', 'auto')
        if c != 'auto':
            self.c = float(c)
        elif self.model == 'iso9613':
            self.c = EARTH_C * math.sqrt(self.temperature_k / T_REF)      # 343.0 at 20 C: the repo's reference speed
        else:
            self.c = math.sqrt(self.gamma * R_GAS * self.temperature_k / self.molar_mass)
        rho = cfg.get('rho_kg_m3', 'auto')
        self.rho = float(rho) if rho != 'auto' else self.pressure_pa * self.molar_mass / (R_GAS * self.temperature_k)
        self.c_measured = cfg.get('c_measured_m_s')
        self.relaxations = [(float(r['f_hz']), float(r['mu_max'])) for r in cfg.get('relaxations', [])]
        cl = cfg.get('classical', 'auto')
        if self.model == 'iso9613':
            self.classical, self.relaxations = iso_terms(self.temperature_k, self.rh, self.pressure_pa / 1000.0, self.c)
        elif cl != 'auto':
            self.classical = float(cl)
        elif self.model == 'ideal_gas':
            self.classical = ((2.0 * math.pi) ** 2 / (2.0 * self.rho * self.c ** 3) * float(self.viscosity)
                              * (4.0 / 3.0 + (self.gamma - 1.0) / float(self.prandtl)))
        else:
            self.classical = 0.0
        self.flow = dict(cfg.get('flow') or {})
        self.canopy = (cfg.get('boundary') or {}).get('canopy')
        self.ground = (cfg.get('boundary') or {}).get('ground')
        self.level_ref = dict(dict(basis='power', p_ref_pa=2e-5), **(cfg.get('level_ref') or {}))

    # ---- bulk -----------------------------------------------------------------------------------------------
    @property
    def z(self):
        """Characteristic impedance rho c, rayl."""
        return self.rho * self.c

    @property
    def temp_c(self):
        return self.temperature_k - 273.15

    def wavelength(self, f_hz):
        return self.c / np.maximum(np.asarray(f_hz, dtype=float), 1e-9)

    def doppler_scale(self, v_m_s):
        """v / c: the factor every Doppler shift in the renderers scales with."""
        return float(v_m_s) / self.c

    # ---- absorption -----------------------------------------------------------------------------------------
    def alpha_np_per_m(self, f):
        """Pure-tone absorption, Np/m (classical term plus every relaxation process)."""
        f = np.asarray(f, dtype=np.float64)
        a = self.classical * f * f
        for fr, mu in self.relaxations:
            a = a + (2.0 * mu / self.c) * (f * f / fr) / (1.0 + (f / fr) ** 2)
        return a

    def alpha_db_per_m(self, f):
        """Pure-tone absorption, dB/m. Earth air goes through airabs (the ISO routine) so it is unchanged."""
        if self.model == 'iso9613':
            import airabs
            return airabs.iso_alpha_db_per_m(f, self.temp_c, self.rh, self.pressure_pa / 1000.0)
        return 8.685889638 * self.alpha_np_per_m(f)

    def absorb(self, x, distance_m, sr=44100):
        """Filter x ((N,) or (N, C)) for distance_m of this medium: gain 10^(-alpha r / 20), linear phase, no spreading.
        Earth air is delegated to airabs.apply, so its output is bit-identical to the old path."""
        x = np.asarray(x, dtype=np.float32)
        if distance_m <= 0:
            return x
        if self.model == 'iso9613':
            import airabs
            return airabs.iso_apply(x, distance_m, temp_c=self.temp_c, rh=self.rh, pressure_kpa=self.pressure_pa / 1000.0, sr=sr)
        from scipy import signal
        freqs = np.linspace(0.0, sr / 2.0, TAPS // 2 + 1)
        gain = 10.0 ** (-self.alpha_db_per_m(freqs) * float(distance_m) / 20.0)
        n = TAPS - 1
        ir = np.roll(np.fft.irfft(gain, n=n), n // 2)
        ir = (np.append(ir, 0.0) * signal.windows.blackman(TAPS)).astype(np.float32)
        out = signal.fftconvolve(x, ir if x.ndim == 1 else ir[:, None], mode='full', axes=0)
        start = TAPS // 2
        return out[start:start + len(x)].astype(np.float32)

    # ---- boundaries and flow --------------------------------------------------------------------------------
    def canopy_excess_db(self, f_hz, distance_m):
        """Extra loss through vegetation, dB, from the preset's measured table (0 when it has none)."""
        if not self.canopy:
            return np.zeros_like(np.asarray(f_hz, dtype=float))
        tab = np.asarray(self.canopy['excess_db_per_m'], dtype=float)
        f = np.maximum(np.asarray(f_hz, dtype=float), 1e-9)
        per_m = np.interp(np.log(f), np.log(tab[:, 0]), tab[:, 1])
        return per_m * max(0.0, float(distance_m))

    def wind_speed(self, height_m):
        """Mean wind speed at a height from the flow profile (0 when the medium declares none)."""
        fl = self.flow
        if not fl or 'u_ref_m_s' not in fl:
            return 0.0
        zr, u = float(fl.get('z_ref_m', 10.0)), float(fl['u_ref_m_s'])
        z = max(float(height_m), 0.05)
        if fl.get('profile', 'power') == 'log':
            z0 = 0.03
            return u * math.log(z / z0) / math.log(zr / z0)
        return u * (z / zr) ** float(fl.get('power_exponent', 0.14))

    # ---- interfaces and checks ------------------------------------------------------------------------------
    def transmission_db(self, other):
        """Energy transmission into another medium, dB: 10 log10(4 Z1 Z2 / (Z1 + Z2)^2). Symmetric."""
        z1, z2 = self.z, other.z
        return 10.0 * math.log10(4.0 * z1 * z2 / (z1 + z2) ** 2)

    def consistency(self):
        """{'c': relative error against c_measured_m_s or None} for env.medium_consistency."""
        err = None if self.c_measured is None else abs(self.c - float(self.c_measured)) / float(self.c_measured)
        return dict(c_declared=self.c, c_measured=self.c_measured, err_c=err)

    def reynolds(self, u_m_s, d_m):
        """rho U d / eta, needs gas.viscosity_pa_s."""
        if self.viscosity is None:
            raise ValueError(f'medium "{self.name}": a Reynolds number needs gas.viscosity_pa_s')
        return self.rho * float(u_m_s) * float(d_m) / float(self.viscosity)

    def describe(self):
        return (f'{self.name}: model {self.model}, c {self.c:.1f} m/s, rho {self.rho:.4g} kg/m3, Z {self.z:.1f} rayl, '
                f'{len(self.relaxations)} relaxation(s)')


# ---- the active medium ------------------------------------------------------------------------------------------
_STACK = []


def earth():
    """Earth air at 20 C, 50 % RH, 101.325 kPa (the default)."""
    return Medium({'model': 'iso9613', 'name': 'earth_air'})


def active():
    """The medium renderers read when nothing else says: the innermost `use(...)`, else Earth air."""
    return _STACK[-1] if _STACK else _EARTH


@contextlib.contextmanager
def use(m):
    """Make `m` (a Medium or a preset dict) the active medium inside the block."""
    m = m if isinstance(m, Medium) else Medium(m)
    _STACK.append(m)
    try:
        yield m
    finally:
        _STACK.pop()


def from_score(score):
    """The medium a score declares (`score["medium"]`), else Earth air."""
    cfg = (score or {}).get('medium')
    return Medium(cfg) if cfg else earth()


def speed_of_sound():
    """c of the active medium: the one place a renderer asks for it."""
    return active().c


_EARTH = earth()
