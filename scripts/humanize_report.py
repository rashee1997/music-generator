#!/usr/bin/env python3
"""humanize_report.py - measure what the humanizer did to a score, without rendering audio.

    python scripts/humanize_report.py <score.json> [--json]

Reports, per part and for the ensemble: the tempo-adjusted timing deviation (sDelta in beats), the
lag-1 timing correlation, the velocity/duration correlation, unique velocity levels, the DNVR and DNODR
expressive-performance ratios, an estimated swing ratio, and the vertical asynchrony between parts.

Advisory only: it reports, it never edits a score, a preset or a mix.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import humanize as hz          # noqa: E402
import presets                 # noqa: E402


def _articulation(track):
    inst = str(track.get('instrument') or '')
    try:
        cfg = presets.find_instrument(inst) or presets.find_vocal(inst)
    except Exception:
        cfg = None
    return track.get('articulation') or (cfg or {}).get('articulation')


def events_of(score, tm):
    """Humanize every played track; returns {name: events} (environment/effect parts are silent here)."""
    out = {}
    cfg = score.get('humanize', 'natural')
    ts = score.get('ts', [4, 4])
    swing = score.get('swing', 0.5)
    for i, tr in enumerate(score.get('tracks', []) or []):
        role = str(tr.get('role') or '')
        inst = str(tr.get('instrument') or '')
        if role in ('environment', 'fx') or inst.startswith(('env:', 'sfx:')):
            continue
        name = tr.get('name', f'track{i}')
        notes = [dict(n, p=int(round(float(n['p'])))) for n in tr.get('notes', []) if 'p' in n]
        try:
            ev = hz.humanize_track(notes, tm, tr.get('humanize', cfg), role=role or 'chord', seed=score.get('seed', 1),
                                   ts=tuple(ts), swing=swing, articulation=_articulation(tr), instrument=inst,
                                   part=name)
        except Exception as ex:                     # a part the score wrote badly must not hide the others
            print(f'[WARN] {name}: {type(ex).__name__}: {ex}', file=sys.stderr)
            continue
        out[name] = ev
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('score')
    ap.add_argument('--json', action='store_true', help='machine-readable output')
    args = ap.parse_args(argv)
    with open(args.score, encoding='utf-8') as fh:
        score = json.load(fh)
    tm = hz.tempo_map_for(score, seed=score.get('seed', 1))
    metrics = hz.humanize_metrics(events_of(score, tm), tm)
    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
        return 0
    print(f'humanize report: {args.score}')
    print(f'  {"part":24s} {"notes":>5s} {"sdt(beat)":>9s} {"lag1":>6s} {"vel/dur":>7s} {"DNVR":>6s} {"DNODR":>6s} {"BUR":>5s}')
    for name, m in metrics['parts'].items():
        def f(v):
            return '-' if v is None else (f'{v:.3f}' if isinstance(v, float) else str(v))
        print(f'  {name[:24]:24s} {m.get("notes", 0):5d} {f(m.get("timing_beat_sd")):>9s} {f(m.get("timing_lag1")):>6s} '
              f'{f(m.get("vel_dur_r")):>7s} {f(m.get("dnvr")):>6s} {f(m.get("dnodr")):>6s} {f(m.get("swing_bur")):>5s}')
    ens = metrics['ensemble']
    print(f'  ensemble: {ens["parts"]} part(s), asynchrony SD {ens["asynchrony_sd_ms"]} ms, '
          f'mean |spread| {ens["asynchrony_mean_abs_ms"]} ms')
    print('  sdt = tempo-adjusted timing deviation; advisory only, not a gate row.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
