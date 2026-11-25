"""forensics.py - the signal-level evidence under an impulse row.

The first version of the engine attributed a click by the loudness of each stem's first difference at that instant,
priced a lever by a straight line, and gave up ("closed") when no declared EQ band existed. Measured on a real render
that was wrong three ways:

  * Owner. A loud stem is not the stem that made the step: the mixer scales each stem (an environment bed is lifted by
    ~16 dB, a drum is placed and ducked), so the unscaled stem says nothing about the master. The owner of a step is
    the stem whose *mixed* contribution to it is large, and that is a regression of the master on the processed stems,
    taken in the band the row itself reads.
  * Shape. A click row here is a robust statistic (a MAD z-score of the high-passed residual), so it is not monotone in
    any one stem's level: cutting the highs of the stem that makes the bed *lowers the noise floor the threshold is
    taken against*, and every other transient crosses it. A straight line through that row promises a fix that makes it
    worse. Only a replay through the gate's own checker can price such a move.
  * Reach. "No lever" was read from the bands a preset already had. A band that does not exist yet (a high shelf below
    the row's corner) is a legal preset edit, so it is a lever.

Everything here reads the files a render already wrote (the master, the processed stems the mixer cached, the score)
and calls the gate's own `check_clicks`; it renders nothing and writes nothing but the report. The model is
`master ~ sum_i g_i * stem_i` in the row's band; it is checked by its own R^2 and by how well it reproduces each
event's step, and both numbers are printed so an unreliable decomposition says so.
"""
from __future__ import annotations

import itertools

import numpy as np

# Fraction of an event's step a stem must own to be named, and to count as one of several coincident sources.
OWNER_SHARE = 0.20
SOLE_SHARE = 0.70
# A decomposition that reproduces an event's step within this ratio of the master's is trusted for that event.
FIT_RATIO = (0.6, 1.4)
# Gains (linear, applied to the row's band of one stem) a replay tries, in dB: -3, -6, -9, -12 starting values.
REPLAY_DB = (-3.0, -6.0, -9.0, -12.0)
# Stems a replay combines (the owners only: every extra stem multiplies the replays).
MAX_COMBINE = 4


def _gate():
    import gate_audio
    import gate_checks
    return gate_audio, gate_checks


def click_band(sr):
    """(order, corner) of the high-pass the click row reads, taken from the gate and never copied."""
    _a, gc = _gate()
    return int(gc.CLICK_ORDER), float(gc.HP_HZ)


class Mixdown:
    """The master as a weighted sum of the processed stems, in the click row's band."""

    def __init__(self, case, ridge=1e-6):
        import soundfile as sf
        from scipy.signal import butter, sosfiltfilt
        data, sr = sf.read(case.master, always_2d=True)
        self.sr = int(sr)
        self.master = data.mean(axis=1)
        n = len(self.master)
        order, corner = click_band(self.sr)
        sos = butter(order, corner, 'high', fs=self.sr, output='sos')
        self.names = [s for s in case.stem_names() if case.stem(s) is not None]
        self.hp = {}
        for name in self.names:
            v = case.stem(name).mean(axis=1).astype(np.float64)
            v = np.pad(v, (0, max(0, n - len(v))))[:n]          # a stem trimmed at its last note is silent after it
            self.hp[name] = sosfiltfilt(sos, v).astype(np.float32)
        self.hm = sosfiltfilt(sos, self.master)
        self.n = n
        self._fit(ridge)

    def _fit(self, ridge):
        """Per-stem gain by regularised least squares; the normal equations keep it to a 12x12 solve."""
        k = len(self.names)
        if not k:
            self.gain, self.r2 = {}, 0.0
            return
        gram = np.zeros((k, k))
        rhs = np.zeros(k)
        step = 1 << 19
        for a in range(0, self.n, step):
            blk = np.stack([self.hp[nm][a:a + step] for nm in self.names], 1).astype(np.float64)
            gram += blk.T @ blk
            rhs += blk.T @ self.hm[a:a + step]
        gram += ridge * np.trace(gram) / k * np.eye(k)
        co = np.linalg.solve(gram, rhs)
        self.gain = {nm: float(c) for nm, c in zip(self.names, co)}
        res = np.sum((self.hm - sum(self.gain[nm] * self.hp[nm] for nm in self.names)) ** 2)
        self.r2 = float(1.0 - res / max(float(np.sum(self.hm ** 2)), 1e-18))

    # -- one event ------------------------------------------------------------------------------
    def locate(self, t, reach_ms=3.0):
        """Sample index of the largest step of the row's residual near time t."""
        k = int(round(t * self.sr))
        r = int(reach_ms * self.sr / 1000.0)
        lo, hi = max(1, k - r), min(self.n - 2, k + r)
        d = np.diff(self.hm[lo - 1:hi + 1])
        return lo - 1 + int(np.argmax(np.abs(d)))

    def contributions(self, j):
        """{stem: signed step it adds at sample j -> j+1 after mixing}, and the master's own step."""
        out = {nm: float(self.gain[nm] * (self.hp[nm][j + 1] - self.hp[nm][j])) for nm in self.names}
        for key, arr in (getattr(self, 'layer_hp', None) or {}).items():
            stem = key.split('/', 1)[0]
            out[key] = float(arr[j + 1] - arr[j])          # a layer is part of its stem: it replaces that share below
        return out, float(self.hm[j + 1] - self.hm[j])

    def add_bed(self, case, stem):
        """Split an environment stem into its preset's layers, as contributions to the master's band.

        The layers are rendered again with the piece's own track seed (so the random draws are the render's), once whole
        and once with each layer muted by gain; the difference is that layer's signal, and the stem's band is regressed
        on them to carry it through the stem's own chain. Keys are `stem/layer`. Returns the layer names, or [] when the
        bed is not a layer preset (a biome, a scene) or cannot be rebuilt; the fit is stored in `self.bed_fit`.
        """
        got = layer_signals(case, stem, self.n, self.sr)
        if not got or stem not in self.hp:
            return []
        from scipy.signal import butter, sosfiltfilt
        order, corner = click_band(self.sr)
        sos = butter(order, corner, 'high', fs=self.sr, output='sos')
        names = list(got)
        cols = np.stack([sosfiltfilt(sos, got[k]).astype(np.float64) for k in names], 1)
        tgt = self.hp[stem].astype(np.float64)
        gram = cols.T @ cols
        gram += 1e-6 * np.trace(gram) / len(names) * np.eye(len(names))
        a = np.linalg.solve(gram, cols.T @ tgt)
        fit = cols @ a
        self.bed_fit = getattr(self, 'bed_fit', {})
        self.bed_fit[stem] = float(1.0 - np.sum((tgt - fit) ** 2) / max(float(np.sum(tgt ** 2)), 1e-18))
        self.layer_hp = getattr(self, 'layer_hp', {})
        for k, nm in enumerate(names):
            self.layer_hp[f'{stem}/{nm}'] = (self.gain[stem] * a[k] * cols[:, k]).astype(np.float32)
        return names

    def sigma(self):
        d = np.diff(self.hm)
        return float(1.4826 * np.median(np.abs(d - np.median(d))))


def mixdown(case):
    """The Mixdown for a case, built once (it is the expensive part and every event shares it)."""
    got = case._cache.get('forensics.mixdown')
    if got is None:
        got = Mixdown(case)
        case._cache['forensics.mixdown'] = got
    return got


# -- what a step is ---------------------------------------------------------------------------------------

def classify(shares, signs_with_master, raw_step_fs, local_peak_fs):
    """One word for how the event was made, from who contributed and how the raw waveform behaves."""
    owners = [s for s, v in shares.items() if v >= OWNER_SHARE]
    if raw_step_fs >= 0.5 or (local_peak_fs > 0 and raw_step_fs >= 0.5 * local_peak_fs and raw_step_fs >= 0.1):
        return 'discontinuity'
    top = max(shares.values(), default=0.0)
    if top >= SOLE_SHARE:
        return 'single source'
    aligned = [s for s in owners if signs_with_master.get(s, 0) > 0]
    if len(aligned) >= 2:
        return 'coincident transients'
    return 'mixed'


def nearest_notes(score, t, before_ms=250.0, after_ms=30.0, limit=3, only=None):
    """For each track, the written note whose onset is closest before the event: where in a note the step lands.

    `only` restricts it to the stems that own the event: the kit that happens to play 26 ms earlier did not make a step
    the environment bed made. A bed (one long note) has no onset to be near, so it is named as continuous.
    """
    out = []
    for tr in score.get('tracks', []):
        if only is not None and tr.get('name') not in only:
            continue
        if only is not None and len(tr.get('notes') or []) <= 2:
            out.append(dict(track=tr.get('name'), pitch=None, velocity=None, onset_s=None, after_onset_ms=0.0,
                            written_len=None, continuous=True))
            continue
        best = None
        for n in tr.get('notes') or []:
            if not isinstance(n, dict) or 't' not in n:
                continue
            dt = (t - float(n['t'])) * 1000.0
            if -after_ms <= dt <= before_ms and (best is None or abs(dt) < abs(best[0])):
                best = (dt, n)
        if best:
            dt, n = best
            out.append(dict(track=tr.get('name'), pitch=n.get('p'), velocity=n.get('v'), onset_s=round(float(n['t']), 4),
                            after_onset_ms=round(dt, 1), written_len=n.get('d')))
    out.sort(key=lambda x: abs(x['after_onset_ms']))
    return out[:limit]


def events(case, row):
    """The events a click row reported: times in seconds, from the verdict or from the gate's own checker."""
    times = list(((row.get('raw') or {}).get('worst_times_s') or []))
    if not times:
        import re
        times = [float(x) for x in re.findall(r'(\d+\.\d+)s', row.get('detail') or '')]
    if not times and case.master:
        try:
            ga, gc = _gate()
            res = gc.check_clicks(ga.load(case.master))
            times = [float(x) for x in res.get('times') or []]
        except Exception:
            times = []
    return sorted(set(round(float(t), 4) for t in times))[:12]


def _split_beds(case, mx, times):
    """Decompose into layers any environment stem that owns a share of an event (done once per bed)."""
    if getattr(mx, '_beds_done', None) is None:
        mx._beds_done = set()
    for t in times:
        j = mx.locate(t)
        contrib, step = mx.contributions(j)
        tot = sum(abs(v) for v in contrib.values()) or 1.0
        for stem, v in list(contrib.items()):
            if '/' in stem or stem in mx._beds_done or abs(v) / tot < OWNER_SHARE:
                continue
            tr = case.track(stem) or {}
            if str(tr.get('instrument') or '').startswith('env:'):
                mx._beds_done.add(stem)
                mx.add_bed(case, stem)


def explain_events(case, times, mx=None):
    """Forensic record per event: owner shares, type, the notes under it, and how far over the threshold it is."""
    mx = mx or mixdown(case)
    sigma = mx.sigma()
    _ga, gc = _gate()
    _split_beds(case, mx, times)
    thr = max(float(8.0 * sigma), float(0.02))
    out = []
    for t in times:
        j = mx.locate(t)
        contrib, step = mx.contributions(j)
        beds = {k.split('/', 1)[0] for k in contrib if '/' in k}
        for b in beds:
            contrib.pop(b, None)                      # the bed is reported through its layers, not twice
        mag = {s: abs(v) for s, v in contrib.items()}
        total = sum(mag.values()) or 1.0
        shares = {s: v / total for s, v in mag.items()}
        sgn = float(np.sign(step)) or 1.0
        aligned = {s: float(np.sign(v) * sgn) for s, v in contrib.items()}
        fit = sum(contrib.values())
        ratio = fit / step if abs(step) > 1e-12 else 0.0
        lo = max(0, j - 16)
        raw = float(np.max(np.abs(np.diff(mx.master[lo:j + 18])))) if j + 18 < mx.n else 0.0
        peak = float(np.max(np.abs(mx.master[max(0, j - 200):j + 200])))
        kind = classify(shares, aligned, raw, peak)
        owners = sorted(((s, shares[s]) for s in shares if shares[s] >= OWNER_SHARE), key=lambda x: -x[1])
        owner_names = {o_s.split('/', 1)[0] for o_s, _v in owners}
        notes = nearest_notes(case.score, j / mx.sr, only=owner_names)
        for n_ in notes:
            if n_.get('continuous'):
                n_['layers'] = [ly for ly in bed_layers(case, n_['track']) if ly['impulsive']]
        out.append(dict(
            t=round(j / mx.sr, 4), step=round(abs(step), 5), threshold=round(thr, 5),
            over_threshold_db=round(20 * np.log10(abs(step) / thr), 2) if thr > 0 and abs(step) > 0 else 0.0,
            z=round(abs(step) / sigma, 1) if sigma > 0 else None,
            kind=kind, trusted=bool(FIT_RATIO[0] <= ratio <= FIT_RATIO[1]), fit_ratio=round(float(ratio), 2),
            owners=[dict(stem=s, share=round(v, 3), signed=round(contrib[s], 5)) for s, v in owners],
            raw_step_fs=round(raw, 4), notes=notes))
    return out


# -- what a move would do: a replay through the gate's own checker ---------------------------------------

def replay(case, scales, mx=None):
    """Value and times the click row would read if the named stems' band were scaled (linear gain per stem).

    scales: {stem: linear gain on that stem's high-passed part}. The master's own band content is replaced by the
    modelled one and the gate's `check_clicks` runs on the result, so the robust threshold is re-taken against the new
    floor: this is what a straight line cannot do.
    """
    x = _modelled(case, scales, mx)
    mx = mx or mixdown(case)
    ga, gc = _gate()
    res = gc.check_clicks(ga.Signal(np.stack([x, x], 1), mx.sr))
    return int(res.get('value') or 0), [round(float(t), 3) for t in (res.get('times') or [])]


def margin_db(case, scales, mx=None, steps=(1.0, 2.0, 3.0)):
    """How many dB tighter the click threshold can be before the modelled mix fails (0 when it fails as it stands).

    The row is a MAD z-score and an absolute floor; both are tightened together by the same factor, so a mix that clears
    with 2 dB of margin has no event within 2 dB of the line. A candidate that clears with none is inside the model's
    own error and is the reason a fix that "worked" in replay fails by one event in the render.
    """
    mx = mx or mixdown(case)
    ga, gc = _gate()
    x = _modelled(case, scales, mx)
    sig = ga.Signal(np.stack([x, x], 1), mx.sr)
    got = 0.0
    for db in steps:
        k = 10 ** (db / 20.0)
        res = gc.check_clicks(sig, mad_z=8.0 / k, floor_fs=0.02 / k)
        if int(res.get('value') or 0) != 0:
            break
        got = db
    return got


def _modelled(case, scales, mx=None):
    mx = mx or mixdown(case)
    x = mx.master.copy()
    for nm, g in scales.items():
        if '/' in nm and nm in (getattr(mx, 'layer_hp', None) or {}):
            x -= (1.0 - g) * mx.layer_hp[nm].astype(np.float64)
        elif nm in mx.hp and abs(1.0 - g) > 1e-9:
            # The move is a high shelf, and a shelf is not a scaled copy of the band: near its corner it cuts less than
            # its nominal gain, so scaling the whole band by the nominal gain promised more than the mixer delivers
            # (a false proof, measured). The stem is run through the same Pedalboard filter the mixer uses.
            x += mx.gain[nm] * (shelf_hp(case, mx, nm, 20.0 * np.log10(max(g, 1e-6))).astype(np.float64)
                                - mx.hp[nm].astype(np.float64))
    return x


def shelf_hp(case, mx, stem, db):
    """The stem's click band after a real high shelf of `db` at the catalogue's corner (cached per stem and depth)."""
    cache = mx.__dict__.setdefault('_shelf', {})
    key = (stem, round(float(db), 2))
    if key not in cache:
        import pedalboard as pb
        from scipy.signal import butter, sosfiltfilt
        from .catalog import HF_SHELF_HZ
        v = case.stem(stem).mean(axis=1).astype(np.float32)
        v = np.pad(v, (0, max(0, mx.n - len(v))))[:mx.n]
        y = pb.Pedalboard([pb.HighShelfFilter(HF_SHELF_HZ, float(db), 0.7)])(v[None, :], mx.sr)[0]
        order, corner = click_band(mx.sr)
        cache[key] = sosfiltfilt(butter(order, corner, 'high', fs=mx.sr, output='sos'), y.astype(np.float64)).astype(np.float32)
    return cache[key]


# -- is the model fit to be believed? ---------------------------------------------------------------------

def validate(case, row, mx=None):
    """The sham test: replay with no change must give back the gate's own verdict, event for event.

    Before any counterfactual is trusted, the model is asked to reproduce what the gate already said. If it finds a
    different count or different events, its decomposition of this master is wrong in a way no candidate can be
    believed through (the click row is a robust statistic of the whole file). The per-event fit ratio (modelled step over
    the master's own) is reported with it. Returns dict(ok, sham, gate, missing, extra, fit).
    """
    mx = mx or mixdown(case)
    v, times = replay(case, {}, mx)
    gate = sorted(float(t) for t in (events(case, row) or []))
    near = lambda a, b: any(abs(a - c) < 0.01 for c in b)       # 10 ms: a located step vs the gate's reported time
    missing = [t for t in gate if not near(t, times)]
    extra = [t for t in times if not near(t, gate)]
    return dict(ok=not missing and not extra and v == len(gate), sham=v, gate=len(gate), missing=missing, extra=extra,
                r2=round(mx.r2, 3), resolution_db=resolution_db(mx))


def resolution_db(mx, top=3000, pct=90.0):
    """The model's own error on the master's largest band steps, in dB (90th percentile).

    Measured on this render: modelled step against the master's step for the 3000 largest, median 0.7 dB and 90th
    percentile 1.7 dB. A counterfactual that clears the row by less than this is inside the model's error: the backtest
    (undo a cut whose real effect is known) is wrong at exactly that scale. So a candidate is proved only when it clears
    with at least this much margin, and the figure is printed beside every candidate.
    """
    if 'res' in mx.__dict__:
        return mx.res
    d = np.diff(mx.hm)
    fit = np.zeros_like(d)
    for nm in mx.names:
        fit += mx.gain[nm] * np.diff(mx.hp[nm].astype(np.float64))
    idx = np.argsort(-np.abs(d))[:top]
    err = np.abs(20 * np.log10(np.clip(np.abs(fit[idx]), 1e-9, None) / np.clip(np.abs(d[idx]), 1e-9, None)))
    mx.res = round(float(np.percentile(err, pct)), 2) if err.size else 3.0
    return mx.res


def search(case, owners, base_value, mx=None, levels=REPLAY_DB, max_combine=MAX_COMBINE, budget=96):
    """Replays over the owners' band: every single move, then pairs, best first, each tagged with what it does.

    Returns a list of dicts {moves: {stem: dB}, value, times, delta, verdict} where verdict is 'clears', 'better',
    'no change' or 'worse'. 'worse' on a cut is the signature of a floor effect and is kept: it is the reason a
    lever must not be priced linearly.
    """
    mx = mx or mixdown(case)
    layers = getattr(mx, 'layer_hp', None) or {}
    owners = [s for s in owners if s in mx.hp or s in layers][:max_combine]
    out, done = [], 0

    def one(moves):
        nonlocal done
        done += 1
        v, t = replay(case, {s: 10 ** (db / 20.0) for s, db in moves.items()}, mx)
        verdict = ('clears' if v == 0 else 'better' if v < base_value else 'no change' if v == base_value else 'worse')
        mg = margin_db(case, {s: 10 ** (db / 20.0) for s, db in moves.items()}, mx) if v == 0 else None
        out.append(dict(moves=dict(moves), value=v, times=t[:6], delta=v - base_value, verdict=verdict, margin_db=mg))
        return v

    for s in owners:
        for db in levels:
            if done >= budget:
                return _rank(out)
            one({s: db})
    # pairs only among the owners, at matching depth: the grid is small on purpose
    for a, b in itertools.combinations(owners, 2):
        for da, db_ in itertools.product(levels[:3], levels[:3]):
            if done >= budget:
                return _rank(out)
            one({a: da, b: db_})
    return _rank(out)


def _rank(out):
    # fewest events first, then the widest margin from the line, then the smallest total cut
    return sorted(out, key=lambda r: (r['value'], -(r.get('margin_db') or 0.0), sum(abs(x) for x in r['moves'].values())))


def floor_effect(results):
    """True when cutting a stem's band made the row worse: the threshold moves with the floor, so the row is not a line."""
    return [r for r in results if r['verdict'] == 'worse' and len(r['moves']) == 1]


def monotone_slope(results, stem):
    """events per dB of cut for one stem, from the single-stem replays, or None when the response is not monotone."""
    pts = sorted(((db, r['value']) for r in results if list(r['moves']) == [stem] for db in r['moves'].values()),
                 reverse=True)
    if len(pts) < 2:
        return None
    vals = [v for _db, v in pts]
    if any(b > a for a, b in zip(vals, vals[1:])):
        return None
    span = pts[0][0] - pts[-1][0]
    return (vals[-1] - vals[0]) / span if span else None


def as_notes(events_, results, mx):
    """The report lines this module contributes, as plain strings."""
    lines = [f'decomposition: master ~ sum of gain x stem in the click band (R^2 {mx.r2:.2f}); gains '
             + ', '.join(f'{s} {mx.gain[s]:.2f}' for s in mx.names if abs(mx.gain[s]) > 0.05)]
    for e in events_:
        own = ', '.join(f"{o['stem']} {100 * o['share']:.0f}%" for o in e['owners']) or 'no stem owns it'
        note = e['notes'][0] if e['notes'] else None
        where = (f"; nearest onset {note['track']} p{note['pitch']} v{note['velocity']} {note['after_onset_ms']:+.0f} ms"
                 if note else '')
        lines.append(f"event {e['t']:.3f}s [{e['kind']}] {own}; step {e['step']:.4f} vs threshold {e['threshold']:.4f} "
                     f"({e['over_threshold_db']:+.1f} dB over){where}{'' if e['trusted'] else '  (fit unreliable)'}")
    return lines


IMPULSIVE_PRIMITIVES = ('impulse_cluster', 'click_train', 'fm_chirp_cluster', 'animal_call', 'drip', 'crackle')


def bed_layers(case, stem):
    """The layers of an environment stem's preset, flagging the ones that make isolated transients.

    A bed has no note to blame, so the autopsy used to stop at "continuous bed". The preset still says which layers are
    impulsive; naming them turns "the canopy" into "the `drips` layer (impulse_cluster, -19 dB)", which is a preset line
    to change. The stem is not re-rendered per layer, so this is a candidate list, not a measurement.
    """
    tr = case.track(stem) or {}
    inst = str(tr.get('instrument') or '')
    if not inst.startswith('env:'):
        return []
    import glob
    import json
    import os
    name = inst.split(':', 1)[1]
    for path in glob.glob(os.path.join(case.project, 'presets', 'environments', name + '.json')):
        try:
            with open(path, encoding='utf-8') as fh:
                body = json.load(fh)
        except (OSError, ValueError):
            continue
        out = []
        for ly in body.get('layers') or []:
            prim = str(ly.get('primitive') or '')
            out.append(dict(layer=ly.get('name'), primitive=prim, gain_db=ly.get('gain_db'),
                            impulsive=any(k in prim for k in IMPULSIVE_PRIMITIVES), rate=ly.get('event_rate')))
        return out
    return []


def layer_signals(case, stem, n, sr):
    """{layer: mono signal in master time} for an environment stem built from a layer preset, or {}.

    Muting a layer by gain leaves every random draw where it was (each primitive draws before the gain is applied), so
    `whole - muted` is exactly that layer's contribution to the render. The preset is the project's own.
    """
    tr = case.track(stem) or {}
    inst = str(tr.get('instrument') or '')
    if not inst.startswith('env:'):
        return {}
    key = f'bed.layers.{stem}'
    if key in case._cache:
        return case._cache[key]
    out = {}
    try:
        import copy
        import environment
        import humanize as hz
        import presets
        import render_natural as rn
        saved = list(presets.PROJECT_ROOTS)
        presets.reset_projects()
        presets.add_project(case.project)
        try:
            cfg = presets.find_environment(inst.split(':', 1)[1])
            if not cfg or cfg.get('schema') or not cfg.get('layers') or isinstance(cfg.get('scene'), dict):
                case._cache[key] = {}
                return {}
            sc = case.score
            tm = hz.tempo_map_for(sc, seed=sc.get('seed', 7))
            seed = rn._track_seed(stem, tr, tm, sc.get('humanize', 'natural'))
            dur = float(tm.sec(tm.total_beats))
            notes = tr.get('notes') or []
            t0, span = 0.0, dur
            if notes and not tr.get('full_length'):
                t0 = float(tm.sec(min(x['t'] for x in notes)))
                t1 = min(dur, float(tm.sec(max(x['t'] + x.get('d', 1.0) for x in notes))))
                span = max(1.0, t1 - t0) + 0.1
            whole = environment.render_environment_preset(copy.deepcopy(cfg), duration_s=span, sr=sr, seed=seed)
            for i, ly in enumerate(cfg['layers']):
                muted = copy.deepcopy(cfg)
                muted['layers'][i]['gain_db'] = -300.0
                part = whole - environment.render_environment_preset(muted, duration_s=span, sr=sr, seed=seed)
                mono = part.mean(axis=1) if part.ndim == 2 else part
                buf = np.zeros(n, np.float64)
                i0 = int(t0 * sr)
                seg = mono[:max(0, n - i0)]
                buf[i0:i0 + len(seg)] = seg
                out[str(ly.get('name') or f'layer{i}')] = buf
        finally:
            presets.PROJECT_ROOTS[:] = saved
    except Exception:
        out = {}
    case._cache[key] = out
    return out


# -- closing the loop in simulation ------------------------------------------------------------------------

TIGHTEN_DB = (0.0, 1.0, 2.0, 3.0)      # thresholds tried, as dB tighter than the gate's own (starting values)
CUT_STEP_DB = 3.0                      # one move is a 3 dB cut of one owner's band
CUT_LIMIT_DB = 12.0                    # no owner is cut deeper than this (a shelf that deep is a different sound)


def _profile(case, scales, mx):
    """(events at the gate's own threshold, +1 dB, +2 dB, +3 dB tighter) and the times at the tightest level."""
    ga, gc = _gate()
    x = _modelled(case, scales, mx)
    sig = ga.Signal(np.stack([x, x], 1), mx.sr)
    counts, tight = [], []
    for db in TIGHTEN_DB:
        k = 10 ** (db / 20.0)
        res = gc.check_clicks(sig, mad_z=8.0 / k, floor_fs=0.02 / k, run_lpc=False)
        counts.append(int(res.get('value') or 0))
        tight = [float(t) for t in (res.get('times') or [])]
    return tuple(counts), tight


def _owners_modelled(mx, scales, times):
    """Stems (or bed layers) that own the near-threshold events of the modelled mix, strongest first."""
    weight = {}
    layers = getattr(mx, 'layer_hp', None) or {}
    for t in times:
        j = mx.locate(t)
        contrib, _step = mx.contributions(j)
        beds = {k.split('/', 1)[0] for k in contrib if '/' in k}
        for b in beds:
            contrib.pop(b, None)
        scaled = {k: v * float(scales.get(k, 1.0)) for k, v in contrib.items()}
        tot = sum(abs(v) for v in scaled.values()) or 1.0
        for k, v in scaled.items():
            if abs(v) / tot >= OWNER_SHARE:
                weight[k] = weight.get(k, 0.0) + abs(v) / tot
    return [k for k, _w in sorted(weight.items(), key=lambda kv: -kv[1]) if k in mx.hp or k in layers]


def plan_clicks(case, mx=None, rounds=5):
    """Greedy cut plan, simulated end to end: owners of near-threshold events, one 3 dB cut at a time.

    Each round finds the events within 3 dB of the line (the failing ones and the ones that a cut will expose), tries a
    further 3 dB on each of their owners and keeps the cut that gives the lexicographically smallest profile
    (events at 0, 1, 2, 3 dB tighter), then explains what is left. It stops on a clean profile, when no cut improves it,
    or when every owner is at the cut limit. Returns dict(moves {stem or stem/layer: dB}, profile, history).
    """
    mx = mx or mixdown(case)
    cuts = {}                                     # stem or layer -> dB (negative)
    prof, near = _profile(case, {}, mx)
    path = [dict(moves={}, profile=prof)]
    start = prof
    for _ in range(rounds):
        if sum(prof) == 0:
            break
        _split_beds(case, mx, near)
        pool = [o for o in _owners_modelled(mx, {k: 10 ** (v / 20.0) for k, v in cuts.items()}, near)
                if cuts.get(o, 0.0) - CUT_STEP_DB >= -CUT_LIMIT_DB][:4]
        best = None
        for o in pool:
            trial = dict(cuts)
            trial[o] = trial.get(o, 0.0) - CUT_STEP_DB
            p, tn = _profile(case, {k: 10 ** (v / 20.0) for k, v in trial.items()}, mx)
            key = (p, sum(abs(v) for v in trial.values()))
            if best is None or key < best[0]:
                best = (key, trial, p, tn)
        if best is None or best[2] >= prof:
            break
        cuts, prof, near = best[1], best[2], best[3]
        path.append(dict(moves=dict(cuts), profile=prof))
    return dict(moves=cuts, profile=prof, start=start, path=path)
