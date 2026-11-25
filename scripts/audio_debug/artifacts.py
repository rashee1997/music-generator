"""artifacts.py - one render's evidence, loaded once.

Everything the engine reasons about comes from files the render already wrote: the gate's own metrics
(`presets/gate/data/*.json`, each with `meta.metrics`), the score, the presets, and the processed stems the mixer
keeps in `<project>/.cache/mix/<key>/<stem>.npy`. Nothing is re-measured except per-event attribution, which needs
the stems; when they are absent the engine still runs and says which rows it could not attribute.
"""
from __future__ import annotations

import glob
import json
import os
import re

import numpy as np


def _read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


_NUM = re.compile(r'(-?\d+(?:\.\d+)?)\s*(dBTP|dBFS|dB|LUFS|LU|ms|FS|events|samples|%|s)(?![A-Za-z])')
_THR = re.compile(r'(limit|want|fail|warn|target|max|min)\s*(?:of\s*)?(-?\d+(?:\.\d+)?)')


_COUNT = re.compile(r'^\s*(\d+)\s+(?:click|clipped|impulse|event)')


def _parse_detail(text):
    """(value, threshold, unit, sense) out of a row's prose, for renders written before rows.json existed."""
    text = text or ''
    count = _COUNT.match(text.lower())
    if count:                          # "1 click event(s): ..." - the count is the value, the limit is zero events
        return dict(value=float(count.group(1)), threshold=0.0, unit='events', sense='max')
    m = _NUM.search(text)
    if not m:
        return {}
    value, unit = float(m.group(1)), m.group(2)
    hits = _THR.findall(text)
    if not hits:
        return dict(value=value, unit=unit, sense='max')
    word, thr = hits[-1]
    sense = 'min' if word in ('want', 'min') and unit in ('%', 'LU', 'LUFS', 'dB') else 'max'
    return dict(value=value, threshold=float(thr), unit=unit, sense=sense)


class Case:
    """The measurements, the declarations behind them, and the audio they were taken from."""

    def __init__(self, project, score, rows, mix, instruments, stems, master, sources, stale=False):
        self.project = project
        self.score = score or {}
        self.rows = rows                   # [{row, level, value, threshold, unit, stem, detail, raw}]
        self.mix = mix or {}
        self.instruments = instruments or {}
        self._stems = stems                # {name: (path, sr)} - arrays are loaded on demand
        self.master = master
        self.sources = sources             # which files this case was built from
        self.stale = bool(stale)           # the audio on disk is newer than the verdict that judged it
        self.drift = []                    # inputs edited after the master was written
        self._cache = {}

    # -- loading ---------------------------------------------------------------------------------
    @classmethod
    def load(cls, project, score_path=None):
        project = os.path.abspath(project)
        sources = {}
        score = None
        if score_path:
            score = _read(score_path)
            sources['score'] = os.path.abspath(score_path)
        else:
            # The piece's own score first: a project folder may also hold a scaffold or a second cue's score, and the
            # newest file is not necessarily the one this render used.
            base = os.path.basename(project.rstrip(os.sep))
            found = sorted(glob.glob(os.path.join(project, 'scores', '*_score.json')))
            own = [p for p in found if os.path.basename(p).startswith(base)]
            pick = own or found
            if pick:
                score = _read(pick[-1])
                sources['score'] = pick[-1]
        score = score or {}

        rows = []
        data_dir = os.path.join(project, 'presets', 'gate', 'data')
        for path in sorted(glob.glob(os.path.join(data_dir, '*.json'))):
            body = _read(path)
            if not isinstance(body, dict):
                continue
            for m in ((body.get('meta') or {}).get('metrics') or []):
                if not isinstance(m, dict) or not m.get('row'):
                    continue
                rows.append(dict(row=m['row'], level=m.get('level') or 'INFO', stem=m.get('stem'),
                                 value=m.get('value'), threshold=m.get('threshold'), unit=m.get('unit', ''),
                                 margin=m.get('margin'), detail=m.get('detail', ''), raw=m,
                                 source=os.path.basename(path)))
            sources.setdefault('gate_data', []).append(os.path.basename(path))

        # Rows the structured files did not carry (a render written before rows.json existed): the CI verdict still
        # states the numbers in its prose for most rows, so read them from there instead of showing an empty autopsy.
        # Such a row is marked parsed, not measured, and never overwrites a row that was written with its numbers.
        ci = _read(os.path.join(project, 'reports', 'ci_report.json')) or {}
        # Only when this render wrote no rows.json: the verdict file is the *previous* run's until the pipeline
        # finishes, so mixing its rows into a fresh render's rows would assemble two runs into one case.
        has_rows = os.path.isfile(os.path.join(data_dir, 'rows.json'))
        known = {r['row'] for r in rows}
        added = 0
        for entry in ([] if has_rows else (ci.get('ci_checks') or [])):
            name = entry.get('check')
            if not name or name in known:
                continue
            parsed = _parse_detail(entry.get('detail'))
            rows.append(dict(row=name, level=entry.get('level'), stem=None,
                             value=parsed.get('value'), threshold=parsed.get('threshold'),
                             unit=parsed.get('unit') or '', margin=None, detail=entry.get('detail') or '',
                             raw=dict(parsed=True, sense=parsed.get('sense')), source='ci_report'))
            added += 1
        if added:
            sources['gate_rows'] = f'reports/ci_report.json ({added} rows parsed from the verdict text)'

        mix_name = score.get('mix_preset') or 'default'
        mix = _read(os.path.join(project, 'presets', 'mix', mix_name + '.json')) or {}
        instruments = {}
        for path in glob.glob(os.path.join(project, 'presets', 'instruments', '*.json')):
            body = _read(path)
            if isinstance(body, dict):
                instruments[body.get('name') or os.path.basename(path)[:-5]] = body

        stems = {}
        for path in glob.glob(os.path.join(project, '.cache', 'mix', '*', '*.npy')):
            name = os.path.basename(path)[:-4]
            if name not in stems or os.path.getmtime(path) > os.path.getmtime(stems[name][0]):
                stems[name] = (path, 44100)
        if stems:
            sources['stems'] = f'{len(stems)} processed stems from .cache/mix'

        # The master the verdict names, not merely the newest file in out/: an interrupted render leaves a draft that
        # no gate ever judged, and measuring it would silently mix two renders in one report.
        master, stale = None, False
        declared = ((ci.get('deliverables') or {}).get('master_wav') if isinstance(ci, dict) else None)
        candidates = ([declared] if declared and os.path.isfile(declared) else
                      [os.path.join(project, 'out', n) for n in ('master.wav', '_draft_master.wav')])
        for p in candidates:
            if os.path.isfile(p):
                master = p
                sources['master'] = os.path.relpath(p, project)
                break
        # The gate data is written in the same run as the master it judged, so it is the file to compare against;
        # ci_report.json is written at the end of the run and would flag every fresh render as stale.
        marks = [os.path.join(project, 'presets', 'gate', 'data', n) for n in ('rows.json', 'stem_gate.json')]
        marks = [p for p in marks if os.path.isfile(p)]
        if master and marks:
            try:
                stale = os.path.getmtime(master) > max(os.path.getmtime(p) for p in marks) + 1.0
                sources['verdict'] = (ci or {}).get('timestamp') or 'unknown'
            except OSError:
                stale = False
        if stale:
            sources['warning'] = 'the audio is newer than the verdict: the pending render has not been judged'
        case = cls(project, score, rows, mix, instruments, stems, master, sources, stale=stale)
        case.drift = case._drift()
        if case.drift:
            sources['drift'] = ('the presets or score changed after this master was rendered: ' + ', '.join(case.drift[:4])
                                + ' - the autopsy describes the previous mix until you re-render')
        return case

    def _drift(self):
        """Files the render reads that are newer than the master it produced (the render has not seen them)."""
        if not self.master or not os.path.isfile(self.master):
            return []
        t0 = os.path.getmtime(self.master)
        newer = []
        pats = [os.path.join(self.project, 'presets', d, '*.json') for d in ('mix', 'instruments', 'vocals', 'spaces',
                                                                          'environments', 'sfx')]
        pats.append(os.path.join(self.project, 'scores', '*_score.json'))
        for pat in pats:
            for path in glob.glob(pat):
                try:
                    if os.path.getmtime(path) > t0 + 1.0:
                        newer.append(os.path.relpath(path, self.project))
                except OSError:
                    continue
        return sorted(newer)

    # -- access ----------------------------------------------------------------------------------
    def stem(self, name):
        """The processed stem as a float32 (n, 2) array, or None."""
        if name not in self._stems:
            return None
        if name not in self._cache:
            path, _sr = self._stems[name]
            try:
                a = np.load(path).astype(np.float32)
            except (OSError, ValueError):
                return None
            if a.ndim == 1:
                a = np.stack([a, a], 1)
            self._cache[name] = a
        return self._cache[name]

    def stem_names(self):
        return sorted(self._stems)

    def stem_paths(self, name):
        """Every cached copy of a processed stem, oldest first: one per distinct mix the project has rendered."""
        paths = glob.glob(os.path.join(self.project, '.cache', 'mix', '*', name + '.npy'))
        return sorted(paths, key=os.path.getmtime)

    def role(self, name):
        for tr in self.score.get('tracks', []):
            if tr.get('name') == name:
                return tr.get('role')
        return None

    def track(self, name):
        for tr in self.score.get('tracks', []):
            if tr.get('name') == name:
                return tr
        return None

    def failing(self):
        return [r for r in self.rows if r['level'] == 'FAIL']

    def warn(self):
        return [r for r in self.rows if r['level'] == 'WARN']

    def worst_first(self):
        from .margins import safety
        return sorted(self.rows, key=lambda r: safety(r)[0])

    def __repr__(self):
        return f'Case({os.path.basename(self.project)}, rows={len(self.rows)}, stems={len(self._stems)})'
