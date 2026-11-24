#!/usr/bin/env python3
"""humanize.py - the public surface of the humanize engine.

The engine itself lives in `scripts/humanize_engine/`, one module per concern:

    config.py       presets, role/expression profiles, tuning tables, the key schema and resolve()
    noise.py        smooth / 1/f^beta noise and the piece's one shared drift curve
    form.py         phrases, motor streams, metric weight, tonal charge, key parsing
    timemap.py      TempoMap and tempo_map_for: the one beats->seconds map of a score
    swing.py        the swing ratio a tempo implies, and where the off-beat lands
    ensemble.py     section expansion and the ensemble asynchrony field
    microtiming.py  the timing stage: two-scale 1/f error and per-limb motor error
    dynamics.py     the velocity stage: accent, phrase arch, contour, runs, chord voicing
    articulation.py gate, duration rules, legato overlap and the piano pedal
    coupling.py     cross-track phase correction (opt-in `score.coupling`)
    drums.py        kit runs, flams and pocket application
    pocket.py       a pushed/laid-back groove as data (timing AND velocity per limb)
    track.py        humanize_track: stage order and event assembly
    report.py       event_stats, coupling_report and the humanize report
    humanize_report.py (scripts/) runs the report on a score without rendering audio

This module re-exports every name from those modules, so `import humanize` and `humanize.foo(...)`
keep working for callers that predate the split. The engine never imports this facade.
"""
import sys

from humanize_engine import (articulation, config, coupling, drums, dynamics, ensemble, form, microtiming,
                             noise, pocket, report, swing, timemap, track)

_MODULES = (config, noise, form, timemap, swing, ensemble, drums, dynamics, microtiming, articulation,
            coupling, pocket, report, track)
_SKIP = {'annotations'}

for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if _name.startswith('__') or _name in _SKIP:
            continue
        globals()[_name] = _value

del _module, _name, _value

if __name__ == '__main__':
    tm = TempoMap(100, total_beats=16, rubato=0.03, ritard=0.35)
    notes = [dict(t=i * 0.5, d=0.45, p=60 + (i % 5) * 2, v=0.7, role='melody') for i in range(32)]
    ev = humanize_track(notes, tm, 'natural', role='melody', seed=1)
    print(humanize_report(ev))
    print([round(e['t'], 3) for e in ev[:8]])
