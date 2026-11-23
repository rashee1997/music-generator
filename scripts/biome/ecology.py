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

"""ecology.py - who may call when: niches, rules, a density budget, and the pockets the score leaves open.

    Occupancy        a time x band grid of what the score occupies (notes, their harmonics, drums), built from the score
    section_times    section names and hit times of a score / direction sheet, in seconds
    niche overlap    Schoener's D on band shares (1 = the same band, 0 = disjoint), after Krause's niche hypothesis:
                     D_vw = 1 - 1/2 sum_b |p_v(b) - p_w(b)|
    Planner          decides every bout of every animal in time order, BEFORE it is rendered, so a freeze is an absence of
                     events (plus a short fade of a call already sounding), not a duck laid on top afterwards

A candidate bout is refused (and retried later) when: its animal is frozen by a rule; its activity curve says it is not the
time of day; an animal whose niche overlaps (D above the preset's limit) is calling; the score occupies its band over
the whole call (a `foreground` call looks for a pocket, a `bed` call is only kept out of dense passages); or the density
budget of calls per second is full. After `max_tries` a foreground call is dropped, except with probability `p_force`.

Numbers that are not from a source are labelled starting values in their doc (ecology_schema.NUMBERS).
"""
import heapq
import math

import numpy as np

import roles as roles_mod

F_LO, F_HI, N_BANDS = 60.0, 9000.0, 24
FRAME_S = 0.5
FIGURE = ('melody', 'lead', 'vocal', 'counter')
ROLE_WEIGHT = {'melody': 1.0, 'lead': 1.0, 'vocal': 1.0, 'counter': 0.8, 'bass': 0.7, 'chord': 0.6, 'arp': 0.6, 'ostinato': 0.6,
               'pad': 0.45, 'drone': 0.45, 'texture': 0.45, 'drum': 0.8}
SKIP_ROLES = ('environment', 'fx')


# ------------------------------------------------------------------------------------------------ the score's side
def _tempo(score):
    try:
        import humanize
        tm = humanize.tempo_map_for(score, seed=score.get('seed', 1))
        return lambda beats: float(tm.sec(float(beats)))
    except Exception:
        spb = 60.0 / float((score or {}).get('bpm', 100.0))
        return lambda beats: float(beats) * spb


def _beats_per_bar(score):
    ts = (score or {}).get('ts') or (score or {}).get('meter') or [4, 4]
    if isinstance(ts, str) and '/' in ts:
        ts = ts.split('/')
    try:
        return float(ts[0]) * 4.0 / float(ts[1])
    except Exception:
        return 4.0


def section_times(score=None, direction=None):
    """({section name: [(start_s, end_s), ...]}, [hit times s]) from a score's plan and a direction sheet's sections and hits."""
    out, hits = {}, []
    sec = _tempo(score or {})
    bpb = _beats_per_bar(score)
    for s in ((score or {}).get('plan') or {}).get('sections') or []:
        if 'start_bar' in s:
            out.setdefault(str(s['name']), []).append((sec(s['start_bar'] * bpb), sec(s.get('end_bar', s['start_bar']) * bpb)))
    for h in ((score or {}).get('plan') or {}).get('hits') or []:
        t = h.get('t') if isinstance(h, dict) else h
        if isinstance(t, (int, float)):
            hits.append(float(t))
    for s in (direction or {}).get('sections') or []:
        if 'start_s' in s:
            out.setdefault(str(s['name']), []).append((float(s['start_s']), float(s.get('end_s', s['start_s']))))
    for h in (direction or {}).get('hits') or []:
        if isinstance(h, dict) and isinstance(h.get('t'), (int, float)):
            hits.append(float(h['t']))
    return out, sorted(set(hits))


class Occupancy:
    """What the score occupies: [frame, band] in 0..1, plus the share a protected (figure) role holds."""

    def __init__(self, duration_s, frame_s=FRAME_S, n_bands=N_BANDS, f_lo=F_LO, f_hi=F_HI):
        self.frame_s = float(frame_s)
        self.edges = np.geomspace(f_lo, f_hi, n_bands + 1)
        self.n = max(1, int(math.ceil(float(duration_s) / self.frame_s)) + 1)
        self.grid = np.zeros((self.n, n_bands))
        self.protect = np.zeros((self.n, n_bands))

    def band_of(self, f):
        return int(np.clip(np.searchsorted(self.edges, f) - 1, 0, len(self.edges) - 2))

    def add(self, t0, t1, bands_weights, protected=False):
        a = max(0, int(t0 / self.frame_s))
        b = min(self.n, max(a + 1, int(math.ceil(t1 / self.frame_s))))
        for band, w in bands_weights.items():
            self.grid[a:b, band] += w
            if protected:
                self.protect[a:b, band] += w

    @classmethod
    def from_score(cls, score, direction=None, protect_roles=FIGURE, margin_db=3.0, duration_s=None):
        sec = _tempo(score)
        tracks = (score or {}).get('tracks') or []
        end = 0.0
        for tr in tracks:
            for n in tr.get('notes') or []:
                end = max(end, sec(float(n['t']) + float(n.get('d', 1.0))))
        occ = cls(duration_s or end or 1.0)
        spread = 2 if margin_db >= 6.0 else (1 if margin_db >= 3.0 else 0)
        vmax = max([float(n.get('v', 1.0)) for tr in tracks for n in tr.get('notes') or []] or [1.0])
        scale = 127.0 if vmax > 1.5 else 1.0
        prot = {roles_mod.canonical(r, default=r) for r in protect_roles}
        for tr in tracks:
            raw = str(tr.get('role') or 'chord')
            role = roles_mod.canonical(raw, default='chord')
            if role in SKIP_ROLES or str(tr.get('instrument', '')).startswith('env:'):
                continue
            w_role = ROLE_WEIGHT.get(role, 0.5)
            for n in tr.get('notes') or []:
                t0, t1 = sec(float(n['t'])), sec(float(n['t']) + float(n.get('d', 1.0)))
                v = float(n.get('v', 0.7 * scale)) / scale
                w = w_role * (0.4 + 0.6 * min(max(v, 0.0), 1.0))
                if role == 'drum':
                    occ.add(t0, max(t1, t0 + 0.1), {b: w * 0.5 for b in range(len(occ.edges) - 1)})
                    continue
                f0 = 440.0 * 2.0 ** ((float(n.get('p', 60)) - 69.0) / 12.0)
                bw = {}
                for h in range(1, 9):
                    if f0 * h > 5000.0 or f0 * h > F_HI:
                        break
                    b = occ.band_of(f0 * h)
                    for db in range(-spread if role in prot else 0, (spread if role in prot else 0) + 1):
                        if 0 <= b + db < len(occ.edges) - 1:
                            bw[b + db] = bw.get(b + db, 0.0) + w / h ** 0.7 * (1.0 if db == 0 else 0.5)
                occ.add(t0, t1, bw, protected=role in prot)
        occ.grid = np.clip(occ.grid, 0.0, 1.0)
        occ.protect = np.clip(occ.protect, 0.0, 1.0)
        return occ

    def level(self, t0, t1, lo_hz, hi_hz, protected_only=False):
        """The highest occupancy over the frames and bands a call would use (0 outside the piece)."""
        a = int(max(t0, 0.0) / self.frame_s)
        b = int(math.ceil(max(t1, t0 + 1e-6) / self.frame_s))
        if a >= self.n:
            return 0.0
        b0, b1 = self.band_of(lo_hz), self.band_of(hi_hz)
        g = self.protect if protected_only else self.grid
        return float(g[a:min(b, self.n), b0:b1 + 1].max())


# ------------------------------------------------------------------------------------------------ niches
def third_octave_edges(lo=50.0, hi=12500.0):
    n = int(round(3 * math.log2(hi / lo)))
    return lo * 2.0 ** (np.arange(n + 1) / 3.0)


def band_shares(lo_hz, hi_hz, edges=None):
    """Share of an animal's energy in each third-octave band, taken as uniform over [lo_hz, hi_hz] on a log axis."""
    e = third_octave_edges() if edges is None else np.asarray(edges, dtype=float)
    a, b = np.log(e[:-1]), np.log(e[1:])
    x0, x1 = math.log(lo_hz), math.log(hi_hz)
    over = np.clip(np.minimum(b, x1) - np.maximum(a, x0), 0.0, None)
    return over / max(over.sum(), 1e-12)


def spectrum_shares(x, sr, edges=None):
    """Share of a signal's energy in each third-octave band (the measured counterpart of band_shares)."""
    e = third_octave_edges() if edges is None else np.asarray(edges, dtype=float)
    s = np.abs(np.fft.rfft(np.asarray(x, dtype=np.float64))) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    out = np.array([s[(f >= lo) & (f < hi)].sum() for lo, hi in zip(e[:-1], e[1:])])
    return out / max(out.sum(), 1e-30)


def schoener(p, q):
    """Schoener's D: 1 for the same distribution, 0 for disjoint ones."""
    return float(1.0 - 0.5 * np.abs(np.asarray(p) - np.asarray(q)).sum())


def activity(niche, controls, t):
    """0..1 'is it the time of day' of an animal at time(s) t (1 when it declares none)."""
    a = (niche or {}).get('active')
    if not a:
        return np.ones(np.shape(t)) if np.ndim(t) else 1.0
    return np.clip(controls.value(a, t), 0.0, 1.0)


def collisions(fauna_cfgs, controls=None, horizon_s=600.0, edges=None):
    """[(a, b, D, co_activity)] for every pair of animals that declares a niche band."""
    rows = []
    cfgs = [f for f in fauna_cfgs if (f.get('niche') or {}).get('band_hz')]
    t = np.linspace(0.0, horizon_s, 400)
    for i, f in enumerate(cfgs):
        for g in cfgs[i + 1:]:
            d = schoener(band_shares(*f['niche']['band_hz'], edges), band_shares(*g['niche']['band_hz'], edges))
            if controls is not None:
                af, ag = np.asarray(activity(f['niche'], controls, t)), np.asarray(activity(g['niche'], controls, t))
                co = float(np.minimum(af, ag).mean() / max(min(af.mean(), ag.mean()), 1e-9))
            else:
                co = 1.0
            rows.append((f['name'], g['name'], d, min(co, 1.0)))
    return rows


# ------------------------------------------------------------------------------------------------ the planner
def _pair(v, default=(0.0, 0.0)):
    if v is None:
        return default
    return (float(v[0]), float(v[1])) if isinstance(v, (list, tuple)) else (float(v), float(v))


class Planner:
    """Decides, in time order, when every individual of every animal calls. `start_of(name, individual, k)` is what the
    animals read; `plan_until(t)` extends the plan (the engine calls it ahead of each chunk)."""

    def __init__(self, faunas, ecology, controls, occupancy=None, sections=None, hits=None, t0_s=0.0, foreground=()):
        self.fauna = {f.name: f for f in faunas}
        self.eco = dict(ecology or {})
        self.controls, self.occ, self.t0 = controls, occupancy, float(t0_s)
        sc = self.eco.get('score') or {}
        self.pocket_thr = float(sc.get('pocket_threshold', 0.35))
        self.bed_thr = float(sc.get('bed_threshold', 0.8))
        self.p_force = float(sc.get('p_force', 0.05))
        self.max_tries = int(sc.get('max_tries', 8))
        db = self.eco.get('density_budget') or {}
        self.budget = float(db['events_per_s_max']) if db.get('events_per_s_max') else None
        self.window_s = 10.0
        ni = self.eco.get('niches') or {}
        self.min_sep = _parse_limit(ni.get('min_separation', 'D<=0.4')) if ni.get('auto') else None
        self.foreground = {f.name for f in faunas if f.cfg.get('salience', 'bed') == 'foreground'}
        self.keys = [(f.name, i) for f in faunas for i in range(f.n_ind)]
        self.rng = {k: f_ctx.rng(f'{k[0]}/i{k[1]}/plan') for k in self.keys for f_ctx in [self.fauna[k[0]].ctx]}
        self.plan = {k: [] for k in self.keys}
        self.accepted = []                       # (start, end, name, ind) in time order
        self.windows = {n: [] for n in self.fauna}
        self.dropped = []                        # (name, ind, t): calls given up
        self.tries = {k: 0 for k in self.keys}
        self.heap, self._seq = [], 0
        self.planned_to = 0.0
        self.conflicts = set()
        if self.min_sep is not None:
            cl = collisions([f.cfg for f in faunas], controls)
            self.conflicts = {frozenset((a, b)) for a, b, d, _ in cl if d > self.min_sep}
        self.rules = self._rules(sections or {}, hits or [])
        for k in self.keys:
            f = self.fauna[k[0]]
            first = f.first_s if (f.first_s is not None and k[1] == 0) else self.rng[k].uniform(0.1, 1.0) * f.mean_gap
            self._push(float(first), k, 'regular')
        for t, rule in self._score_triggers:
            self._effects(rule, t, 0.0, None)

    # -- rules
    def _rules(self, sections, hits):
        out, self._score_triggers = [], []
        for i, r in enumerate(self.eco.get('rules') or []):
            on, do = r['on'], r['do']
            for n in list(do.get('freeze', [])) + ([do['answer']] if do.get('answer') else []):
                if n not in self.fauna:
                    raise ValueError(f'ecology.rules[{i}]: "{n}" is not an animal of this biome ({", ".join(sorted(self.fauna))})')
            if 'fauna' in on and on['fauna'] not in self.fauna:
                raise ValueError(f'ecology.rules[{i}].on.fauna "{on["fauna"]}" is not an animal of this biome')
            if 'score' in on:
                name = on['score']
                if name == 'hit':
                    times = list(hits)
                elif name in sections:
                    times = [a for a, _ in sections[name]]
                else:
                    raise ValueError(f'ecology.rules[{i}].on.score "{name}": no such section or hit in the score '
                                     f'(sections: {", ".join(sorted(sections)) or "none; pass the score or the direction sheet"})')
                for t in times:
                    self._score_triggers.append((t - self.t0, r))
            out.append(r)
        return out

    def _effects(self, rule, t, dur, ind):
        do = rule['do']
        rng = self.fauna[next(iter(self.fauna))].ctx.rng(f'rule/{self.rules.index(rule)}/{round(t, 3)}')
        lo, hi = _pair(do.get('for_s'), (5.0, 5.0))
        until = t + float(rng.uniform(lo, hi))
        fade, ramp = float(do.get('fade_ms', 200.0)) / 1000.0, float(do.get('ramp_s', 0.0))
        for n in do.get('freeze', []):
            self.windows[n].append((t, until, fade, ramp))
            self.fauna[n].add_silence(t, until, fade, ramp)
        if do.get('answer'):
            if float(rng.random()) <= float(do.get('p', 1.0)):
                a, b = _pair(do.get('after_ms'), (300.0, 900.0))
                self._push(t + dur + float(rng.uniform(a, b)) / 1000.0, (do['answer'], 0), 'answer')

    # -- the queue
    def _push(self, t, key, kind):
        self._seq += 1
        heapq.heappush(self.heap, (float(t), self._seq, key, kind))

    def start_of(self, name, ind, k):
        p = self.plan[(name, ind)]
        return p[k][0] if k < len(p) else None

    def _frozen_until(self, name, t):
        end = None
        for a, b, _, ramp in self.windows[name]:
            if a <= t < b:
                end = max(end or 0.0, b)
        return end

    def _overlapping(self, t0, t1):
        return [a for a in self.accepted[-40:] if a[0] < t1 and a[1] > t0]

    def plan_until(self, T):
        T = float(T)
        while self.heap and self.heap[0][0] < T:
            t, _, key, kind = heapq.heappop(self.heap)
            self._decide(t, key, kind)
        self.planned_to = max(self.planned_to, T)

    def _decide(self, t, key, kind):
        name, ind = key
        f, rng = self.fauna[name], self.rng[key]
        k = len(self.plan[key])
        dur = f.call_duration(ind, k)
        retry = None
        fz = self._frozen_until(name, t)
        if fz is not None:
            retry = fz + float(rng.uniform(0.0, max(f.mean_gap * 0.2, 0.5)))
        elif kind == 'regular' and float(rng.random()) > float(activity(f.cfg.get('niche'), self.controls, t)):
            retry = t + float(rng.uniform(0.5, 1.5)) * max(f.mean_gap * 0.2, 1.0)
        if retry is None and self.conflicts:
            for a, b, other, _ in self._overlapping(t, t + dur):
                if frozenset((name, other)) in self.conflicts and other != name:
                    retry = b + 0.2
                    break
        if retry is None and self.occ is not None and (f.cfg.get('niche') or {}).get('band_hz'):
            lo, hi = f.cfg['niche']['band_hz']
            lvl = self.occ.level(t + self.t0, t + self.t0 + dur, lo, hi)
            thr = self.pocket_thr if name in self.foreground else self.bed_thr
            if lvl > thr:
                self.tries[key] += 1
                if self.tries[key] > self.max_tries:
                    self.tries[key] = 0
                    if float(rng.random()) > self.p_force:
                        self.dropped.append((name, ind, t))
                        self._push(t + max(dur + 0.2, f.mean_gap * float(rng.uniform(0.7, 1.3))), key, 'regular')
                        return
                else:
                    retry = t + float(rng.uniform(1.0, 3.0))
        if retry is None and self.budget:
            recent = sum(1 for a in self.accepted[-200:] if t - self.window_s < a[0] <= t)
            if (recent + 1) / self.window_s > self.budget:
                retry = t + 1.0
        if retry is not None:
            if kind == 'answer':
                return                                     # an answer that cannot be given now is not given late
            self._push(retry, key, kind)
            return
        self.tries[key] = 0
        self.plan[key].append((t, dur))
        self.accepted.append((t, t + dur, name, ind))
        self.accepted.sort()
        for r in self.rules:
            if r['on'].get('fauna') == name:
                self._effects(r, t, dur, ind)
        if kind == 'regular':
            self._push(t + max(dur + 0.2, f.mean_gap * float(rng.uniform(0.7, 1.3))), key, 'regular')

    def report(self):
        return dict(bouts={f'{n}/{i}': list(v) for (n, i), v in self.plan.items()}, windows={n: list(w) for n, w in self.windows.items()},
                    dropped=list(self.dropped), conflicts=sorted(sorted(c) for c in self.conflicts), planned_to=self.planned_to)


def _parse_limit(s):
    """'D<=0.4' -> 0.4"""
    return float(str(s).replace(' ', '').split('<=')[-1])
