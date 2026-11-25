# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""The engine's data: presets, role profiles, expression profiles, tuning tables and their schema.

Every number the humanizer starts from lives in this module and nowhere else. A preset, a score's
`humanize` block or a track's overrides name keys here; an unknown key is an error, not a silent no-op.
"""
import roles as rolelib


PRESETS = {
    # timing_ms = short-scale (<8 beats) per-note jitter sigma; lead_ms = how early the melody sits;
    # drift_ms = long-scale (>=8 beats) shared ensemble wander; short_share = how much of the short-scale timing
    # variance is 1/f rather than white motor error. Sogorski, Geisel & Priesemann (2018) measured two power-law
    # regimes in >100 jazz and rock/pop recordings: a short process below ~8 beats that is much larger in jazz, and a
    # long process above ~8 beats (the shared tempo drift) that is similar across genres. So `timing_ms` is the
    # short, genre-dependent part and `drift_ms` the long, shared one - they are not interchangeable.
    'tight':   dict(timing_ms=3,  drum_ms=2,  lead_ms=8,  drift_ms=3,  vel_sigma=3, rubato=0.00, wander=0.000, strum_ms=4,  ritard=0.20, accent=0.6, short_share=0.15),
    'natural': dict(timing_ms=7,  drum_ms=5,  lead_ms=20, drift_ms=9,  vel_sigma=5, rubato=0.025, wander=0.006, strum_ms=10, ritard=0.35, accent=1.0, short_share=0.22),
    'loose':   dict(timing_ms=12, drum_ms=9,  lead_ms=25, drift_ms=15, vel_sigma=7, rubato=0.04, wander=0.010, strum_ms=16, ritard=0.40, accent=1.2, short_share=0.30),
    'rubato':  dict(timing_ms=9,  drum_ms=6,  lead_ms=28, drift_ms=12, vel_sigma=6, rubato=0.07, wander=0.015, strum_ms=22, ritard=0.50, accent=0.8, short_share=0.30),
    'punchy':  dict(timing_ms=4,  drum_ms=2,  lead_ms=10, drift_ms=4,  vel_sigma=4, rubato=0.01, wander=0.002, strum_ms=6,  ritard=0.20, accent=1.3, upbeat=True, short_share=0.15),
    'bouncy':  dict(timing_ms=5,  drum_ms=3,  lead_ms=12, drift_ms=5,  vel_sigma=5, rubato=0.01, wander=0.003, strum_ms=8,  ritard=0.20, accent=1.4, upbeat=True, short_share=0.18),
}


TIMING = dict(note_lag1=0.5, drift_corr_beats=6.0, vel_dur=0.018, tune_drift_cents=1.2, just_ratio=0.45,
              push_tempo_power=0.4, subdiv_push_ms=1.2,
              fractal_beta=0.85, short_scale_beats=8.0, short_share=0.22, vel_time_couple=0.35,
              duration_contrast=0.06, double_duration=0.10, faster_uphill_ms=2.0, punctuation_ms=12.0,
              repetition_gap_ms=14.0, high_sharp_cents=1.5, vel_lead_ms=6.0, phrase_tempo_vel=2.0,
              melodic_charge_vel=2.0, melodic_charge_dur=0.015, harmonic_charge_vel=1.5, harmonic_charge_dur=0.010,
              ic_agogic_ms=0.0, ic_vel=0.0, h_breath_ms=0.0,
              # tempo-relative short-scale spread and the swing on-beat delay; both 0 = old behaviour
              timing_beat_frac=0.0, timing_cap_ms=40.0, swing_downbeat_ms=0.0)


ELASTIC_KEYS = ('amount', 'corr_beats', 'breaths', 'breath_s')


JUST = {1: 11.7, 2: 3.9, 3: 15.6, 4: -13.7, 5: -2.0, 6: -9.8, 7: 2.0, 8: 13.7, 9: -15.6, 10: 17.6, 11: -11.7}


ROLE = {
    'melody':  dict(off=-1.0, vel=+8,  gate=1.00, legato=True),    # offset multiplier of lead_ms (negative = early)
    'lead':    dict(off=-1.0, vel=+8,  gate=1.00, legato=True),    # the same figure under its prominence name
    'vocal':   dict(off=-0.9, vel=+7,  gate=1.03, legato=True),    # a sung line sits slightly ahead and holds longer
    'counter': dict(off=-0.4, vel=+2,  gate=1.00, legato=True),
    'chord':   dict(off=+0.2, vel=-6,  gate=0.95, legato=False),
    'pad':     dict(off=+0.3, vel=-10, gate=1.02, legato=True),
    'texture': dict(off=+0.3, vel=-10, gate=1.03, legato=True),    # a grain bed is shaped like a pad, not like an effect
    'drone':   dict(off=+0.3, vel=-10, gate=1.05, legato=True),    # holds through, never re-attacks on the grid
    'bass':    dict(off=0.0,  vel=-1,  gate=0.90, legato=False),
    'arp':     dict(off=+0.1, vel=-4,  gate=0.85, legato=False),
    'ostinato': dict(off=+0.1, vel=-3, gate=0.94, legato=False),   # repeated cell, but each repeat is played
    'drum':    dict(off=0.0,  vel=0,   gate=1.00, legato=False),
    'fx':      dict(off=0.0,  vel=0,   gate=1.00, legato=False),
    'environment': dict(off=0.0, vel=0, gate=1.00, legato=False),
}


FIG = rolelib.LEAD


MOODS = {
    'tender': dict(vel=-6.0, gate=+0.04, accent=0.85, duration_contrast=0.70, strum=1.35, rubato=1.25),
    'bright': dict(vel=+5.0, gate=-0.02, accent=1.15, duration_contrast=1.30, strum=0.75, rubato=0.85),
    'solemn': dict(vel=-3.0, gate=+0.02, accent=1.05, duration_contrast=0.85, strum=1.15, rubato=0.70),
    'urgent': dict(vel=+4.0, gate=-0.06, accent=1.25, duration_contrast=1.50, strum=0.50, rubato=0.35),
}


DRUM_PUSH = {36: -3.0, 35: -3.0, 38: +5.0, 40: +5.0, 37: +3.0, 39: +4.0, 42: +1.0, 44: +1.0, 46: +2.0,
             51: +2.0, 59: +2.0, 49: 0.0, 57: 0.0}


DRUM_LIMB = {35: 'kick', 36: 'kick', 37: 'stick', 38: 'snare', 39: 'clap', 40: 'snare', 41: 'tom_low',
             43: 'tom_low', 45: 'tom_mid', 47: 'tom_mid', 48: 'tom_high', 50: 'tom_high',
             42: 'hat', 44: 'hat', 46: 'hat', 51: 'ride', 53: 'ride', 59: 'ride', 49: 'crash', 52: 'crash',
             55: 'crash', 57: 'crash'}


VEL_LEAD_WORDS = ('piano', 'celesta', 'harpsichord', 'clav', 'marimba', 'vibra', 'xylophone', 'glocken', 'kalimba',
                  'guitar', 'lute', 'harp', 'sitar', 'santoor', 'kora', 'banjo', 'mandolin', 'dulcimer', 'cimbalom')


CIRCLE = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: 7, 8: 8, 3: 9, 10: 10, 5: 11}


NOTE_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


SWING_BUR_SLOW, SWING_BUR_FAST = 3.5, 1.0


SWING_BPM_SLOW, SWING_BPM_FAST = 60.0, 280.0


SWING_FLOOR_S = 0.095


SWING_FIG_DEPTH = 0.6


CHORD_ROLES = ('chord', 'pad', 'bass', 'arp', 'texture')


# Every key a preset, a score's `humanize` block or a track override may set. A key outside this set is an
# error: a typo must not become a silent no-op (the reason `pocket` or `timing_beat_frac` could otherwise be
# written and do nothing).
HUMANIZE_KEYS = frozenset([*TIMING, *PRESETS['natural'], 'mood', 'vel_bias', 'gate_bias', 'upbeat', 'upbeats',
                           'pocket'])


def resolve(cfg):
    """A preset name or a dict -> the full starting values of one track.

    A dict may name a base preset (`{"preset": "loose", "timing_ms": 9}`): the base is applied first and the
    explicit keys override it. Before this the `preset` key was merged in as an inert value, so 92 instrument
    presets in the example projects asked for `tight` or `loose` and silently played `natural`.
    """
    c = dict(PRESETS['natural'])
    c.update(TIMING)
    if cfg is None:
        return c
    if isinstance(cfg, str):
        if cfg not in PRESETS:
            raise ValueError(f"humanize: unknown preset {cfg!r}; known: {', '.join(sorted(PRESETS))}")
        c.update(PRESETS[cfg])
        return c
    if not isinstance(cfg, dict):
        raise TypeError(f"humanize: expected a preset name or an object, got {type(cfg).__name__}")
    base = cfg.get('preset')
    if base is not None:
        if base not in PRESETS:
            raise ValueError(f"humanize.preset: unknown preset {base!r}; known: {', '.join(sorted(PRESETS))}")
        c.update(PRESETS[base])
    unknown = sorted(k for k in cfg if k != 'preset' and k not in HUMANIZE_KEYS)
    if unknown:
        raise ValueError(f"humanize: unknown key(s) {', '.join(unknown)}; known: {', '.join(sorted(HUMANIZE_KEYS))}")
    c.update({k: v for k, v in cfg.items() if k != 'preset'})
    return c
