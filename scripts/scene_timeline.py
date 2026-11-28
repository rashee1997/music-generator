# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
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
"""scene_timeline.py - the piece's own timeline, read from the direction sheet a profile points at.

The scene is not a new file format: it is the sheet Phase 4 already writes (`templates/direction_sheet.json`). Its
`sections` carry `start_s`, `end_s` and `role` (`place`, `establish`, `build`, `peak`, `transition`, `button`, and the
`release` / `rupture` this plan adds); its `hits` carry `t`, `kind`, `sync` and an optional `silence_after_s`; its
`video.dialogue.windows` or `mix_intent.sits_under` can name where a voice sits. This module turns that into the time
windows a gate row asks about, and nothing else:

    tl = scene_timeline.load(score)            # None when no profile declares a scene block
    tl.role_at(31.2)                           # 'peak'
    tl.windows('peak')                         # [(28.0, 44.0)]
    tl.waived('roughness')                     # [(28.0, 44.0)]: a role that waives this row's ceiling
    tl.is_rest(33.0)                           # a declared silence, so a dropout row must not judge it
    tl.beat_to_s(64.0)                         # score beats -> sheet seconds

Every number it needs (the default hit window, the tolerance) comes from `references/data/presets/gate/data/scene_roles.json`;
a missing sheet is not an error - it is a profile that promised a scene and a project that has not written one, and the
rows say so instead of passing quietly.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

CONTRACT_PATH = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate', 'data', 'scene_roles.json')
_CONTRACT = {}


def contract(path=CONTRACT_PATH):
    """The role/key contract (roles, allowed keys, ranges, macro and dialogue defaults)."""
    key = os.path.abspath(path)
    if key not in _CONTRACT:
        with open(path, encoding='utf-8') as f:
            _CONTRACT[key] = json.load(f)
    return _CONTRACT[key]


def _project_dir(score, project_dir=None):
    if project_dir:
        return os.path.abspath(project_dir)
    try:
        import presets
        roots = list(getattr(presets, 'PROJECT_ROOTS', []) or [])
        if roots:
            return os.path.dirname(os.path.abspath(roots[-1]))
    except Exception:
        pass
    return None


def _sheet_path(scene, project_dir):
    """The sheet a scene block names, or the project's first direction sheet with sections."""
    named = ((scene.get('timeline') or {}).get('sheet') or '').strip()
    if named:
        if os.path.isabs(named):
            return named
        if project_dir:
            return os.path.join(project_dir, named)
        return None
    if not project_dir:
        return None
    d = os.path.join(project_dir, 'direction')
    if not os.path.isdir(d):
        return None
    for name in sorted(os.listdir(d)):
        if not name.endswith('.json'):
            continue
        try:
            with open(os.path.join(d, name), encoding='utf-8') as f:
                sheet = json.load(f)
        except (OSError, ValueError):
            continue
        if sheet.get('sections'):
            return os.path.join(d, name)
    return None


def _tempo_points(score):
    """[(beat, bpm)] sorted, from the score's own tempo map; empty for a flat tempo."""
    pts = []
    for row in score.get('tempo_points') or []:
        try:
            pts.append((float(row[0]), float(row[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return sorted(pts)


class Timeline:
    """One piece's scene windows. `active` is False when the profile declares a scene block but no sheet was found."""

    def __init__(self, scene, sheet=None, source=None, contract_doc=None):
        self.scene = dict(scene or {})
        self.doc = contract_doc or contract()
        self.sheet = sheet or {}
        self.source = source
        self.spans = []
        for i, s in enumerate(self.sheet.get('sections') or []):
            try:
                a, b = float(s['start_s']), float(s['end_s'])
            except (KeyError, TypeError, ValueError):
                continue
            role = str(s.get('role') or 'establish').strip().lower()
            self.spans.append(dict(name=str(s.get('name') or f'section {i + 1}'), role=role,
                                   start_s=min(a, b), end_s=max(a, b), energy=s.get('energy')))
        self.spans.sort(key=lambda s: s['start_s'])
        self.hits = []
        for h in self.sheet.get('hits') or []:
            try:
                t = float(h['t'])
            except (KeyError, TypeError, ValueError):
                continue
            self.hits.append(dict(t=t, kind=str(h.get('kind') or 'musical'), sync=str(h.get('sync') or 'soft'),
                                  silence_after_s=h.get('silence_after_s')))
        self._tempo = [(float(p[0]), float(p[1])) for p in (self.scene.get('_score_tempo') or [])]
        self._bpm = float(self.scene.get('_score_bpm') or 0.0)
        self.rests = []
        tol = float((self.scene.get('timeline') or {}).get('tolerance_s',
                                                           self.doc['timeline']['tolerance_s']['default']))
        self.tolerance_s = tol
        for h in self.hits:
            if h.get('silence_after_s'):
                try:
                    dur = float(h['silence_after_s'])
                except (TypeError, ValueError):
                    continue
                if dur > 0:
                    self.rests.append((h['t'], h['t'] + dur))
        for row in self.sheet.get('silence_windows') or self.sheet.get('silences') or []:
            try:
                self.rests.append((float(row[0]), float(row[1])))
            except (TypeError, ValueError, IndexError):
                continue
        for s in self.sheet.get('sections') or []:
            text = f"{s.get('music', '')} {s.get('action', '')}".lower()
            if 'silence' in text or 'nothing sounds' in text or 'no music' in text:
                try:
                    self.rests.append((float(s['start_s']), float(s['end_s'])))
                except (KeyError, TypeError, ValueError):
                    continue
        self.dialogue_windows = []

    # ---- time ---------------------------------------------------------------
    def beat_to_s(self, beat):
        """Score beat -> sheet seconds, through the score's tempo map when it has one."""
        beat = float(beat)
        pts = self._tempo
        if not pts:
            bpm = self._bpm or 120.0
            return beat * 60.0 / bpm
        if beat <= pts[0][0]:
            return beat * 60.0 / pts[0][1]
        secs = pts[0][0] * 60.0 / pts[0][1]
        for (b0, v0), (b1, v1) in zip(pts, pts[1:]):
            if beat <= b1:
                return secs + (beat - b0) * 60.0 / v0
            secs += (b1 - b0) * 60.0 / v0
        b_last, v_last = pts[-1]
        return secs + (beat - b_last) * 60.0 / v_last

    def s_to_beat(self, t_s):
        """Sheet seconds -> score beat (the inverse of `beat_to_s`, for a windowed score measurement)."""
        t_s = float(t_s)
        pts = self._tempo
        if not pts:
            bpm = self._bpm or 120.0
            return t_s * bpm / 60.0
        secs, beat = 0.0, pts[0][0]
        if t_s <= 0:
            return beat - (-t_s) * pts[0][1] / 60.0
        for (b0, v0), (b1, v1) in zip(pts, pts[1:]):
            span = (b1 - b0) * 60.0 / v0
            if t_s <= secs + span:
                return b0 + (t_s - secs) * v0 / 60.0
            secs += span
            beat = b1
        return beat + (t_s - secs) * pts[-1][1] / 60.0

    # ---- queries ------------------------------------------------------------
    @property
    def active(self):
        return bool(self.spans and self.scene)

    def role_at(self, t_s):
        t = float(t_s)
        for s in self.spans:
            if s['start_s'] - self.tolerance_s <= t < s['end_s'] + self.tolerance_s:
                return s['role']
        return None

    def span_at(self, t_s):
        t = float(t_s)
        for s in self.spans:
            if s['start_s'] - self.tolerance_s <= t < s['end_s'] + self.tolerance_s:
                return s
        return None

    def windows(self, role=None):
        return [(s['start_s'], s['end_s']) for s in self.spans if role is None or s['role'] == role]

    def roles(self):
        out = []
        for s in self.spans:
            if s['role'] not in out:
                out.append(s['role'])
        return out

    def role_cfg(self, role):
        return (self.scene.get('roles') or {}).get(role) or {}

    def waived(self, row, role=None):
        """Windows whose role waives this row's whole-piece ceiling (`waive_ceiling` names gate rows)."""
        out = []
        for s in self.spans:
            if role is not None and s['role'] != role:
                continue
            if row in (self.role_cfg(s['role']).get('waive_ceiling') or []):
                out.append((s['start_s'], s['end_s']))
        return out

    def in_windows(self, t_s, windows):
        t = float(t_s)
        return any(a - self.tolerance_s <= t <= b + self.tolerance_s for a, b in windows)

    def is_rest(self, t_s):
        """A declared rest: a `silence_after_s` hit, a `silence_windows` entry, or a section whose own words say so."""
        return self.in_windows(t_s, self.rests)

    def hits_for(self, role=None, window_ms=None):
        """[(t, kind, sync, window_s)] for the hits that sit inside a window of `role`."""
        out = []
        for h in self.hits:
            r = role_at(h['t'])
            if role is not None and r != role:
                continue
            cfg = self.role_cfg(r) if r else {}
            w_ms = window_ms or cfg.get('hit_window_ms') or self.doc.get('default_hit_window_ms', 250)
            out.append((h['t'], h['kind'], h['sync'], float(w_ms) / 1000.0))
        return out


def load(score, gp=None, project_dir=None):
    """The timeline a profile's `scene` block points at, or None when the profile declares none.

    `gp` is the resolved profile (pass it when the caller already has one). A declared block with no sheet returns a
    Timeline whose `active` is False: the rows that need it then report "no direction sheet" instead of judging.
    """
    import gate_profiles
    profile = gp or gate_profiles.resolve(score)
    scene = getattr(profile, 'scene', None) or {}
    if not scene:
        return None
    proj = _project_dir(score, project_dir)
    path = _sheet_path(scene, proj)
    sheet = {}
    if path and os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                sheet = json.load(f)
        except (OSError, ValueError):
            sheet = {}
    scene = dict(scene)
    scene['_score_tempo'] = _tempo_points(score)
    scene['_score_bpm'] = score.get('bpm')
    tl = Timeline(scene, sheet=sheet, source=path)
    # dialogue windows: the profile's own list, else the picture's speech windows. `mix_intent.sits_under` names the
    # parts that must stay intelligible, not times, so it can never become a window by itself.
    dlg = scene.get('dialogue') or {}
    wins = dlg.get('windows')
    if not wins:
        video = sheet.get('video') or {}
        wins = ((video.get('dialogue') or {}).get('windows') if isinstance(video, dict) else None)
    for row in wins or []:
        try:
            tl.dialogue_windows.append((float(row[0]), float(row[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return tl


def rests_of(score, gp=None, project_dir=None):
    """The rests the project's direction sheet declares, as [(start_s, end_s)], with or without a `scene` block.

    A rest is a fact of the sheet (a hit's `silence_after_s`, a `silence_windows` entry, a section whose own words say
    silence), not a scene-judging choice, so the rows that must not mistake a rest for a defect (`dropout`,
    `stem.dead`) read it here and do not need the profile to declare scenes. No sheet means no rests, never a guess.
    """
    import gate_profiles
    profile = gp or gate_profiles.resolve(score)
    scene = dict(getattr(profile, 'scene', None) or {})
    path = _sheet_path(scene, _project_dir(score, project_dir))
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            sheet = json.load(f)
    except (OSError, ValueError):
        return []
    scene['_score_tempo'] = _tempo_points(score)
    scene['_score_bpm'] = score.get('bpm')
    return list(Timeline(scene, sheet=sheet, source=path).rests)


def describe(tl):
    """One line for a report: the sheet it read and the roles it found."""
    if tl is None:
        return 'no scene block in this profile (the scene rows did not run)'
    if not tl.active:
        return (f'scene declared but no direction sheet with sections was found '
                f'(looked for {tl.source or "direction/*.json"}): the scene rows did not run')
    return (f'scene from {os.path.basename(tl.source or "")}: '
            + ', '.join(f'{s["role"]} {s["start_s"]:g}-{s["end_s"]:g}s' for s in tl.spans))
