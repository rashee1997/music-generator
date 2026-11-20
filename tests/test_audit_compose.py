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

"""One test per defect found by the composition audit. Each fails on the code as it was and passes on the fix."""
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))

import compose
import fusion
import humanize as hz
import intent
import pattern_audit as pa
import theory


def _notes(n=12, p=60):
    return [dict(t=float(i), d=0.5, p=p + (i % 5), v=0.7) for i in range(n)]


class FusionRoles(unittest.TestCase):
    def _tracks(self, role):
        notes = [dict(t=float(i), d=0.5, p=60 + i % 3, v=0.7) for i in range(16)]
        return [dict(name='x', instrument='flute', role=role, notes=notes)]

    def test_lead_and_vocal_are_the_figure(self):
        for role in ('lead', 'vocal', 'melody'):
            tracks = self._tracks(role)
            out = fusion.shape_for_soul(tracks, dict(soul=dict(call_response=True), roles={'lead': ['flute']}), 4)
            self.assertTrue(any(t['name'] == 'answer' for t in out), role)

    def test_augmented_second_at_the_octave_wrap(self):
        # a synthetic 7-note scale whose only 3-semitone step is the closing one (10 -> 12 is 2; use 9 -> 12)
        theory.MODES['_synthetic_wrap'] = [0, 1, 2, 3, 4, 5, 9]
        try:
            self.assertTrue(fusion._has_aug_second('_synthetic_wrap'))
        finally:
            del theory.MODES['_synthetic_wrap']


class PatternAuditRoles(unittest.TestCase):
    def test_lead_and_vocal_tracks_are_melody_tracks(self):
        for role in ('lead', 'vocal'):
            tr = dict(name='m', role=role, notes=_notes(), instrument='flute')
            self.assertTrue(pa._is_melodic(tr), role)
            self.assertTrue(pa._is_figure(tr), role)
        self.assertFalse(pa._is_figure(dict(role='chord')))

    def test_vocal_track_is_audited_like_a_melody(self):
        score = dict(ts=[4, 4], key='C major', tracks=[
            dict(name='v', role='vocal', instrument='voice', notes=[dict(t=i * 0.5, d=0.4, p=60 + (i % 3), v=0.7) for i in range(40)]),
            dict(name='c', role='chord', instrument='piano', notes=[dict(t=4.0 * i, d=4, p=48, v=0.5) for i in range(5)])])
        self.assertTrue(pa.harmonic_resolution_feel(score) is not None)
        _info, flags = pa.audit(score)
        self.assertTrue(any(f.startswith('v:') and 'note length' in f for f in flags), flags)   # the melody rules reached the vocal

    def test_cognitive_metrics_say_what_failed(self):
        score = dict(ts=[4, 4], tracks=[dict(name='m', role='melody', notes=_notes(20))], key='C major')
        with mock.patch.object(pa, 'build_metric_tree', side_effect=RuntimeError('boom')):
            out = pa.cognitive_metrics(score)
        self.assertIn('witek_bsi', out['_errors'])
        self.assertIn('boom', out['_errors']['witek_bsi'])

    def test_cognitive_metrics_clean_run_has_no_errors(self):
        score = dict(ts=[4, 4], tracks=[dict(name='m', role='melody', notes=_notes(20))], key='C major')
        self.assertNotIn('_errors', pa.cognitive_metrics(score))


class HitTypes(unittest.TestCase):
    def _score(self):
        return dict(dynamics=[], tracks=[])

    def test_typo_raises(self):
        key = theory.Key('C', 'major')
        with self.assertRaises(ValueError):
            compose.add_hit_points(self._score(), [dict(t=4.0, type='impcat')], 120, 4, key, np.random.default_rng(1))

    def test_accepted_types_do_not_raise(self):
        key = theory.Key('C', 'major')
        for typ in ('impact', 'rise', 'silence', 'shift', 'drop'):
            compose.add_hit_points(self._score(), [dict(t=8.0, type=typ)], 120, 4, key, np.random.default_rng(1))

    def test_compose_rejects_a_typo_up_front(self):
        with self.assertRaises(ValueError):
            compose.compose(dict(emotion='calm', duration_s=20, seed=1, hit_points=[dict(t=5, type='impcat')]))


class VaryPhraseSpan(unittest.TestCase):
    def test_shifted_phrase_stays_inside_the_span(self):
        key = theory.Key('C', 'major')
        ch = [key.chord('I')] * 2
        span = (-3, 11)
        phrase = [dict(t=0.0, d=1.0, deg=11, p=key.pitch(11), v=0.6, strong=True),
                  dict(t=1.0, d=1.0, deg=-3, p=key.pitch(-3), v=0.6, strong=True),
                  dict(t=4.0, d=1.0, deg=11, p=key.pitch(11), v=0.6, strong=False)]
        rng = np.random.default_rng(0)
        free = theory.vary_phrase(rng, key, phrase, ch, 4, shift=1)
        self.assertTrue(any(n['deg'] > span[1] for n in free))          # the old behaviour leaves the span
        held = theory.vary_phrase(rng, key, phrase, ch, 4, shift=1, span=span)
        self.assertTrue(all(span[0] <= n['deg'] <= span[1] for n in held), [n['deg'] for n in held])
        held = theory.vary_phrase(rng, key, phrase, ch, 4, shift=-1, span=span)
        self.assertTrue(all(span[0] <= n['deg'] <= span[1] for n in held), [n['deg'] for n in held])


class RolelessHumanize(unittest.TestCase):
    def test_roleless_track_is_said(self):
        tm = hz.TempoMap(100, total_beats=8)
        buf = io.StringIO()
        with redirect_stderr(buf):
            hz.humanize_track(_notes(8), tm, 'natural', role=None, seed=1)
        self.assertIn('[WARN]', buf.getvalue())
        buf = io.StringIO()
        with redirect_stderr(buf):
            hz.humanize_track(_notes(8), tm, 'natural', role='chord', seed=1)
        self.assertEqual(buf.getvalue(), '')


class IntentFx(unittest.TestCase):
    def test_fx_track_is_not_a_pitched_part(self):
        score = dict(tracks=[dict(name='f', role='sfx', notes=[dict(t=0, d=1, p=60, v=.5)]),
                             dict(name='c', role='chord', notes=[dict(t=0, d=1, p=48, v=.5)])])
        names = {t['name'] for t, _n in intent._pitched(score)}
        self.assertEqual(names, {'c'})


class DeadCode(unittest.TestCase):
    def test_resolve_emotion_returns_two_values(self):
        self.assertEqual(len(compose.resolve_emotion(dict(emotion='calm'))), 2)
        self.assertEqual(compose.resolve_emotion(dict(emotion='zzzz'))[1], False)


if __name__ == '__main__':
    unittest.main()
