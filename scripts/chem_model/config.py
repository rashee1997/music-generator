# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""chem_model.config - the chem presets, and the validation that keeps every number traceable.

Three data files, no numbers in Python:

    chem/model.json    the reaction kinetics, the elicitor weights, the dimension anchors, the levers
    chem/moods.json    valence/arousal -> the chemical signature a mood asks for (every mood the intent vocabulary has)
    chem/genres.json   genre -> the constraints its connection has to meet (every genre compose.py ships)

The rules are the repository's (AGENTS.md sections 1 and 7.16): a number carries a source or the words "starting
value", an unknown key is an error and never silently ignored, and nothing here is a measurement - the layer is an
inferred state (proxy), see docs/NEUROCHEMICAL-AFFECT-PLAN.md.
"""
import presets

POOLS = ('DA_ant', 'DA_con', 'NE', 'CORT', 'OXT', 'END', 'PSNS')
DIMENSIONS = ('reward_build', 'reward_arrival', 'stress_load', 'affiliation', 'motor_drive', 'recovery', 'arc_variety')
ELICITORS = ('build', 'proximity', 'tension', 'uncertainty', 'surprise', 'ungrounded', 'roughness', 'fatigue',
             'density', 'low_end', 'vocal', 'legato', 'consonance', 'silence', 'arrival', 'recovery', 'slow_tempo',
             'pulse')
MEASURES = ('stress', 'variety', 'recovery', 'build', 'arrival')


class ChemPresetError(ValueError):
    """A chem preset is missing a block, has an unknown key, or a number outside its own range."""


def _obj(v, where):
    if not isinstance(v, dict):
        raise ChemPresetError(f'{where} must be an object, not {type(v).__name__}')
    return v


def _keys(d, allowed, where):
    extra = sorted(set(d) - set(allowed) - {'_source', 'name'})
    if extra:
        raise ChemPresetError(f'{where} has unknown key(s) {extra}; known: {sorted(allowed)}')


def _num(d, key, where, lo=None, hi=None):
    v = d.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ChemPresetError(f'{where}.{key} must be a number, not {v!r}')
    if lo is not None and v < lo or hi is not None and v > hi:
        raise ChemPresetError(f'{where}.{key} = {v} is outside {lo}..{hi}')
    return float(v)


def _text(d, key, where, required=True):
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        if required:
            raise ChemPresetError(f'{where} needs a non-empty "{key}" (what this number means, or why it is a '
                                  f'starting value)')
        return ''
    return v


def _rate(d, pool, where):
    """k, tau_rec_s, k_des are per second (tau > 0); the first-order loss must be slower than the recovery."""
    k = _num(d, 'k', where, 0.0, 5.0)
    tau = _num(d, 'tau_rec_s', where, 0.5, 3600.0)
    _num(d, 'k_des', where, 0.0, 5.0)
    _num(d, 'vmax', where, 0.01, 10.0)
    _num(d, 'km', where, 0.01, 5.0)
    if k <= 0.0:
        raise ChemPresetError(f'{where}.k must be above 0, or the pool never clears')
    if tau * k > 3600.0:
        raise ChemPresetError(f'{where}: tau_rec_s {tau} with k {k} would take over an hour to recover; a piece '
                              f'cannot reach it')
    return k, tau


def model():
    p = presets.get('chem', 'model')
    _keys(p, ('character', 'provenance', 'step_s', 'pools', 'weights', 'elicitors', 'anchors', 'levers',
              'confidence', 'measures'), 'chem/model')
    _text(p, 'character', 'chem/model')
    _text(p, 'provenance', 'chem/model')
    _num(p, 'step_s', 'chem/model', 0.05, 1.0)
    pools = _obj(p.get('pools'), 'chem/model.pools')
    if set(pools) != set(POOLS):
        raise ChemPresetError(f'chem/model.pools must hold exactly {list(POOLS)}; the rows read them by name. '
                              f'Got {sorted(pools)}')
    for name, cfg in pools.items():
        where = f'chem/model.pools.{name}'
        _obj(cfg, where)
        _keys(cfg, ('tier', 'reads_as', 'k', 'tau_rec_s', 'k_des', 'vmax', 'km', 'why'), where)
        if cfg.get('tier') not in ('A', 'B', 'C'):
            raise ChemPresetError(f'{where}.tier must be A, B or C')
        _text(cfg, 'reads_as', where)
        _text(cfg, 'why', where)
        _rate(cfg, name, where)
    weights = _obj(p.get('weights'), 'chem/model.weights')
    if set(weights) != set(POOLS):
        raise ChemPresetError(f'chem/model.weights must have one entry per pool {list(POOLS)}')
    for name, w in weights.items():
        _obj(w, f'chem/model.weights.{name}')
        for f, v in w.items():
            if f not in ELICITORS:
                raise ChemPresetError(f'chem/model.weights.{name} names the unknown elicitor "{f}"; '
                                      f'known: {list(ELICITORS)}')
            _num(w, f, f'chem/model.weights.{name}', -5.0, 5.0)
    elic = _obj(p.get('elicitors'), 'chem/model.elicitors')
    for name, cfg in elic.items():
        if name not in ELICITORS:
            raise ChemPresetError(f'chem/model.elicitors names the unknown elicitor "{name}"; known: {list(ELICITORS)}')
        _obj(cfg, f'chem/model.elicitors.{name}')
        _text(cfg, 'why', f'chem/model.elicitors.{name}')
    anchors = _obj(p.get('anchors'), 'chem/model.anchors')
    for d in DIMENSIONS:
        _num(anchors, d, 'chem/model.anchors', 0.05, 5.0)
    levers = _obj(p.get('levers'), 'chem/model.levers')
    for d in DIMENSIONS:
        _text(levers, d, 'chem/model.levers')
    conf = _obj(p.get('confidence'), 'chem/model.confidence')
    for t in ('A', 'B', 'C'):
        _text(conf, t, 'chem/model.confidence')
    meas = _obj(p.get('measures'), 'chem/model.measures')
    if set(meas) != set(MEASURES):
        raise ChemPresetError(f'chem/model.measures must hold exactly {list(MEASURES)}')
    for name, cfg in meas.items():
        _obj(cfg, f'chem/model.measures.{name}')
        _text(cfg, 'why', f'chem/model.measures.{name}')
        for k, v in cfg.items():
            if k == 'why' or isinstance(v, str):
                continue
            _num(cfg, k, f'chem/model.measures.{name}')
    return p


def moods():
    p = presets.get('chem', 'moods')
    _keys(p, ('character', 'provenance', 'base', 'dimensions', 'axes', 'overrides', 'max_words', 'why',
              'excess_weight', 'excess_why'), 'chem/moods')
    _text(p, 'character', 'chem/moods')
    _text(p, 'provenance', 'chem/moods')
    _num(p, 'base', 'chem/moods', 0.0, 1.0)
    _num(p, 'max_words', 'chem/moods', 1, 8)
    _num(p, 'excess_weight', 'chem/moods', 0.0, 1.0)
    _text(p, 'excess_why', 'chem/moods')
    dims = p.get('dimensions')
    if list(dims or []) != list(DIMENSIONS):
        raise ChemPresetError(f'chem/moods.dimensions must be exactly {list(DIMENSIONS)} in that order')
    axes = _obj(p.get('axes'), 'chem/moods.axes')
    if set(axes) != {'arousal', 'valence'}:
        raise ChemPresetError('chem/moods.axes must hold exactly "valence" and "arousal" (the intent preset\'s two axes)')
    for axis, cfg in axes.items():
        where = f'chem/moods.axes.{axis}'
        _obj(cfg, where)
        _keys(cfg, ('shift', 'why'), where)
        _text(cfg, 'why', where)
        for d, v in _obj(cfg.get('shift'), f'{where}.shift').items():
            if d not in DIMENSIONS:
                raise ChemPresetError(f'{where}.shift names the unknown dimension "{d}"; known: {list(DIMENSIONS)}')
            _num(cfg['shift'], d, f'{where}.shift', -1.0, 1.0)
    import intent
    known = set(intent.vocabulary()['emotions'])
    for word, cfg in _obj(p.get('overrides'), 'chem/moods.overrides').items():
        where = f'chem/moods.overrides.{word}'
        if word not in known:
            raise ChemPresetError(f'{where}: "{word}" is not an emotion in the intent vocabulary; known: {sorted(known)}')
        _obj(cfg, where)
        _text(cfg, 'why', where)
        for d, v in cfg.items():
            if d == 'why':
                continue
            if d not in DIMENSIONS:
                raise ChemPresetError(f'{where} names the unknown dimension "{d}"; known: {list(DIMENSIONS)}')
            _num(cfg, d, where, 0.0, 1.0)
    return p


def genres():
    p = presets.get('chem', 'genres')
    _keys(p, ('character', 'provenance', 'tolerance', 'families', 'genres', 'aliases'), 'chem/genres')
    _text(p, 'character', 'chem/genres')
    _text(p, 'provenance', 'chem/genres')
    _num(p, 'tolerance', 'chem/genres', 0.0, 0.5)
    fams = _obj(p.get('families'), 'chem/genres.families')
    if 'default' not in fams:
        raise ChemPresetError('chem/genres.families needs a "default" family (a genre with no profile)')
    for fam, cfg in fams.items():
        where = f'chem/genres.families.{fam}'
        _obj(cfg, where)
        _text(cfg, 'why', where, required=fam != 'default')
        for d, lim in cfg.items():
            if d == 'why':
                continue
            if d not in DIMENSIONS:
                raise ChemPresetError(f'{where} names the unknown dimension "{d}"; known: {list(DIMENSIONS)}')
            _obj(lim, f'{where}.{d}')
            _keys(lim, ('min', 'max'), f'{where}.{d}')
            for k in lim:
                _num(lim, k, f'{where}.{d}', 0.0, 1.0)
    for g, fam in _obj(p.get('genres'), 'chem/genres.genres').items():
        if fam not in fams:
            raise ChemPresetError(f'chem/genres.genres.{g} names the unknown family "{fam}"; known: {sorted(fams)}')
    for a, g in _obj(p.get('aliases'), 'chem/genres.aliases').items():
        if g not in fams:
            raise ChemPresetError(f'chem/genres.aliases.{a} names the unknown family "{g}"')
    return p


def problems():
    """Every problem in the three presets, as text. Empty = good (presets.validate calls this)."""
    out = []
    for name, fn in (('model', model), ('moods', moods), ('genres', genres)):
        try:
            fn()
        except ChemPresetError as exc:
            out.append(f'chem/{name}: {exc}')
        except KeyError as exc:
            out.append(f'chem/{name}: missing file or key ({exc})')
    return out
