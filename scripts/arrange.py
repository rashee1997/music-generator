"""Declarative arrangement -> score JSON.

A piece is DECLARED, not coded: this engine holds no key, tempo, scale, chord, phrase, pattern or level. Everything a piece
needs is a key in `scores/<title>_arrangement.json`; the engine expands it into `scores/<title>_score.json` (notes and
roles only: sound lives in presets/, intent in direction/).

    python scripts/arrange.py <project>/scores/<title>_arrangement.json [-o score.json]

Arrangement keys (all strictly validated: an unknown key is an error, never ignored):

  title bpm ts key mode seed            the piece. seed fixes the humanising jitter so a run is repeatable.
  score                                 keys copied to the score unchanged (space, mix_preset, piece_type, focus, intent,
                                        mix_intent, master, output_targets, rubato, ritard, wander, dynamics, ...).
  scale {pcs: [..]}                     the pitch classes the `run` and `shift` helpers walk (a pentatonic, a mode ...).
  shapes {name: [steps]}                scale-step sequences a `run` follows.
  voicings {set: {chord: [pitches]}}    named note sets per chord; a pattern pitch "@set[i]" reads index i of the chord
                                        sounding in that bar. chords are named per section (below).
  lines {name: [[beat, len, pitch, vel], ...]}   a tune, in beats from its own start.
  patterns {name: {variants: [[note, ...], ...], jitter: {v: n}}}   one bar of notes (beat t, d, p, v, extras). variant
                                        i is used for the i-th bar of the event (cycling), so a pattern never repeats
                                        a bar by accident.
  runs {name: {n, step, v0, v1, tail, first, shape, ceiling, d}}   a scale run that ends on a held note.
  tracks {name: {role, lean}}           lean: seconds-in-beats a player sits ahead (-) or behind (+) the grid.
  sections [{name, bars:[a,z], energy, chords:[..], chord_at:{bar: chord}}]   form; chords cycle over the bars.
  events [{track, do, ref, bar | bars, ...}]    do: line | pattern | run | note. Common keys: every [m,r] (only bars
                                        with bar % m == r), skip [bars], scale (a number or {section: number}; 0 = rest).
                                        vary "bar" picks a pattern variant by absolute bar number, so a skipped bar
                                        keeps the others' variants (default: by position in the event's bars).
                                        line: octave vel shift scoop{gl,gs,leap,rest} trill{d,above,min_len,vel}
                                        from to.  pattern: until take.  run: beat pitch shape n step v0 v1 tail ceiling.
                                        note: beat d p v + extras.
"""
import argparse
import json
import os
import random
import sys

TOP = {'title', 'bpm', 'ts', 'key', 'mode', 'seed', 'score', 'scale', 'shapes', 'voicings', 'lines', 'patterns', 'runs',
       'tracks', 'sections', 'events'}
EVENT_KEYS = {'track', 'do', 'ref', 'bar', 'bars', 'every', 'skip', 'scale', 'octave', 'vel', 'shift', 'scoop', 'trill',
              'from', 'to', 'until', 'take', 'beat', 'pitch', 'shape', 'n', 'step', 'v0', 'v1', 'tail', 'd', 'p', 'v',
              'extra', 'why', 'vary', 'ceiling'}


class ArrangementError(ValueError):
    pass


def _need(cond, msg):
    if not cond:
        raise ArrangementError(msg)


def _check_keys(d, allowed, where):
    extra = set(d) - allowed
    _need(not extra, '%s: unknown key(s) %s' % (where, sorted(extra)))


def _clamp_v(v):
    return int(max(1, min(127, round(v))))


class Arranger:
    def __init__(self, spec):
        _check_keys(spec, TOP, 'arrangement')
        for k in ('title', 'bpm', 'ts', 'key', 'mode', 'tracks', 'sections', 'events'):
            _need(k in spec, 'arrangement: missing "%s"' % k)
        self.spec = spec
        self.beats_per_bar = float(spec['ts'][0]) * 4.0 / float(spec['ts'][1])
        self.rng = random.Random(spec.get('seed', 0))
        self.pcs = tuple(spec.get('scale', {}).get('pcs', ()))
        self.shapes = spec.get('shapes', {})
        self.voicings = spec.get('voicings', {})
        self.lines = spec.get('lines', {})
        self.patterns = spec.get('patterns', {})
        self.runs = spec.get('runs', {})
        self.tracks = spec['tracks']
        self.notes = {name: [] for name in self.tracks}
        self.bar_section = {}
        self.bar_chord = {}
        for sec in spec['sections']:
            _check_keys(sec, {'name', 'bars', 'energy', 'chords', 'chord_at', 'dyn'}, 'section %s' % sec.get('name'))
            a, z = sec['bars']
            cycle = sec.get('chords') or []
            for i, bar in enumerate(range(a, z + 1)):
                _need(bar not in self.bar_section, 'section %s: bar %d is in two sections' % (sec['name'], bar))
                self.bar_section[bar] = sec['name']
                if cycle:
                    self.bar_chord[bar] = cycle[i % len(cycle)]
            for bar, name in (sec.get('chord_at') or {}).items():
                self.bar_chord[int(bar)] = name

    # ------------------------------------------------------------------------------------------------ helpers
    def t(self, bar, beat=0.0):
        return (bar - 1) * self.beats_per_bar + beat

    def shift(self, p, k):
        _need(self.pcs, 'scale.pcs is needed for run / trill')
        step = 1 if k >= 0 else -1
        for _ in range(abs(k)):
            p += step
            while p % 12 not in self.pcs:
                p += step
        return p

    def pitch(self, ref, bar):
        if not (isinstance(ref, str) and ref.startswith('@')):
            return ref
        name, _, idx = ref[1:].partition('[')
        chord = self.bar_chord.get(bar)
        _need(chord, 'bar %d has no chord for pitch %s' % (bar, ref))
        sets = self.voicings.get(name)
        _need(sets is not None, 'unknown voicing set "%s"' % name)
        _need(chord in sets, 'voicing set "%s" has no chord "%s" (bar %d)' % (name, chord, bar))
        return sets[chord][int(idx.rstrip(']'))]

    def level(self, ev, bar):
        s = ev.get('scale', 1.0)
        if isinstance(s, dict):
            sec = self.bar_section[bar]
            _need(sec in s or 'default' in s, 'event %s: no scale for section "%s"' % (ev.get('ref'), sec))
            s = s.get(sec, s.get('default'))
        return float(s)

    def bars_of(self, ev):
        if 'bar' in ev:
            bars = [ev['bar']]
        else:
            _need('bars' in ev, 'event %s needs bar or bars' % ev.get('ref'))
            bars = list(range(ev['bars'][0], ev['bars'][1] + 1))
        every, skip = ev.get('every'), set(ev.get('skip', ()))
        return [b for b in bars if b not in skip and (not every or b % every[0] == every[1])]

    def put(self, track, note, extra=None):
        n = dict(t=round(float(note['t']), 4), d=round(float(note['d']), 4), p=note['p'], v=_clamp_v(note['v']))
        for k, v in (extra or {}).items():
            n[k] = v
        self.notes[track].append(n)

    # ------------------------------------------------------------------------------------------------ event kinds
    def do_line(self, ev, bar):
        line = self.lines[ev['ref']]
        lo, hi = ev.get('from', 0.0), ev.get('to', 1e9)
        sc, oc, vel, sh = ev.get('scoop'), ev.get('octave', 0), ev.get('vel', 1.0) * self.level(ev, bar), ev.get('shift', 0.0)
        tr, prev, prev_end = ev.get('trill'), None, 0.0
        for (t, d, p, v) in line:
            if not (lo <= t < hi):
                continue
            a = self.t(bar, t - lo + sh)
            extra = {}
            if sc and (prev is None or p - prev >= sc['leap'] or t - prev_end >= sc['rest']):
                extra = dict(gl=sc['gl'], gs=sc['gs'])
            if tr and d >= tr['min_len']:
                hi_p = self.shift(p, tr.get('above', 1))
                td = tr['d']
                v1, v2 = tr['vel']
                self.put(ev['track'], dict(t=a, d=td, p=p + oc, v=v * vel))
                self.put(ev['track'], dict(t=a + td, d=td, p=hi_p + oc, v=v * vel * v1))
                self.put(ev['track'], dict(t=a + 2 * td, d=d - 2 * td, p=p + oc, v=v * vel * v2))
            else:
                self.put(ev['track'], dict(t=a, d=d, p=p + oc, v=v * vel), extra)
            prev, prev_end = p, t + d

    def do_pattern(self, ev, bar, index):
        pat = self.patterns[ev['ref']]
        variants = pat['variants']
        notes = variants[index % len(variants)]
        jit = pat.get('jitter', {}).get('v', 0)
        until, take = ev.get('until'), ev.get('take')
        lvl = self.level(ev, bar)
        for i, n in enumerate(notes):
            if take is not None and i >= take:
                break
            if until is not None and n['t'] >= until:
                continue
            extra = {k: v for k, v in n.items() if k not in ('t', 'd', 'p', 'v')}
            v = n['v'] * lvl + (self.rng.randint(-jit, jit) if jit else 0)
            self.put(ev['track'], dict(t=self.t(bar, n['t']), d=n['d'], p=self.pitch(n['p'], bar), v=v), extra)

    def do_run(self, ev, bar):
        r = dict(self.runs[ev['ref']])
        for k in ('n', 'step', 'v0', 'v1', 'tail', 'shape', 'ceiling'):
            if k in ev:
                r[k] = ev[k]
        p, shape = ev.get('pitch', r['first']), self.shapes[r['shape']]
        start = self.t(bar, ev.get('beat', 0.0))
        for i in range(r['n']):
            last = i == r['n'] - 1
            v = r['v0'] + (r['v1'] - r['v0']) * i / max(1, r['n'] - 1)
            self.put(ev['track'], dict(t=start + i * r['step'], d=r['tail'] if last else r['step'] * r.get('d', 1.6),
                                       p=p, v=v * self.level(ev, bar)))
            p = self.shift(p, shape[i % len(shape)])
            while p > r.get('ceiling', 127):
                p -= 12

    def do_note(self, ev, bar):
        self.put(ev['track'], dict(t=self.t(bar, ev['beat']), d=ev['d'], p=self.pitch(ev['p'], bar), v=ev['v'] * self.level(ev, bar)),
                 ev.get('extra'))

    # ------------------------------------------------------------------------------------------------ build
    def build(self):
        for ev in self.spec['events']:
            _check_keys(ev, EVENT_KEYS, 'event %s' % ev.get('ref', ev.get('track')))
            _need(ev['track'] in self.tracks, 'event: unknown track "%s"' % ev['track'])
            kind = ev['do']
            _need(kind in ('line', 'pattern', 'run', 'note'), 'event: unknown "do" %s' % kind)
            if kind != 'note':
                src = {'line': self.lines, 'pattern': self.patterns, 'run': self.runs}[kind]
                _need(ev.get('ref') in src, 'event: %s "%s" is not declared' % (kind, ev.get('ref')))
            for i, bar in enumerate(self.bars_of(ev)):
                _need(bar in self.bar_section, 'event %s: bar %d is outside every section' % (ev.get('ref'), bar))
                if self.level(ev, bar) == 0.0:
                    continue
                if kind == 'line':
                    self.do_line(ev, bar)
                elif kind == 'pattern':
                    self.do_pattern(ev, bar, bar - 1 if ev.get('vary') == 'bar' else i)
                elif kind == 'run':
                    self.do_run(ev, bar)
                else:
                    self.do_note(ev, bar)
        return self.score()

    def score(self):
        s = self.spec
        bar_s = self.beats_per_bar * 60.0 / float(s['bpm'])
        sections = []
        for sec in s['sections']:
            a, z = sec['bars']
            if 'energy' in sec:
                sections.append(dict(name=sec['name'], start_bar=a, end_bar=z, start_s=round((a - 1) * bar_s, 4),
                                     end_s=round(z * bar_s, 4), energy=sec['energy'], dyn=sec.get('dyn', sec['energy'])))
        tracks = []
        for name, cfg in self.tracks.items():
            _check_keys(cfg, {'role', 'lean', 'instrument'}, 'track %s' % name)
            lean = cfg.get('lean', 0.0)
            notes = [dict(n, t=round(n['t'] + lean, 4)) if n['t'] + lean >= 0 else n for n in self.notes[name]]
            if notes:
                tracks.append(dict(name=name, instrument=cfg.get('instrument', name), role=cfg['role'],
                                   notes=sorted(notes, key=lambda e: (e['t'], str(e['p'])))))
        out = dict(title=s['title'], bpm=float(s['bpm']), ts=s['ts'], key=s['key'], mode=s['mode'])
        out.update(s.get('score', {}))
        out['plan'] = dict(sections=sections)
        out['tracks'] = tracks
        return out


def build(spec):
    return Arranger(spec).build()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('arrangement')
    ap.add_argument('-o', '--out', help='score path (default: <title>_score.json next to the arrangement)')
    a = ap.parse_args(argv)
    with open(a.arrangement, encoding='utf-8') as fh:
        spec = json.load(fh)
    score = build(spec)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.arrangement)),
                                os.path.basename(a.arrangement).replace('_arrangement', '_score'))
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(score, fh, indent=1)
    print(out)
    for t in score['tracks']:
        print('  %-20s %-9s %4d notes' % (t['name'], t['role'], len(t['notes'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
