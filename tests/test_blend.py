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

"""Smooth-blend features that work for any music: per-track fades in the mixer and the role-based balance check in the gate.
Run: python -m unittest tests.test_blend"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import mixer  # noqa: E402
import quality_gate as qg  # noqa: E402

SR = 44100


def tone(db, secs=20, f=440.0):
    t = np.arange(SR * secs) / SR
    x = np.sin(2 * np.pi * f * t) * np.sqrt(2) * 10 ** (db / 20)
    return np.stack([x, x], 1).astype(np.float32)


class Fades(unittest.TestCase):
    def test_fade_keys_reach_the_spec(self):
        spec = mixer.default_spec({'name': 'b', 'role': 'pad', 'instrument': 'warm_pad', 'fade_in_s': 3, 'fade_out_s': 4})
        self.assertEqual((spec['fade_in_s'], spec['fade_out_s']), (3, 4))

    def test_fades_ramp_the_ends_and_leave_the_middle(self):
        spec = mixer.default_spec({'name': 'b', 'role': 'pad', 'instrument': 'warm_pad', 'reverb': 0.0})
        spec.update(fade_in_s=3.0, fade_out_s=3.0)
        y = mixer.process_stem('b', tone(-20, 12), spec, SR)
        rms = lambda a, b: float(np.sqrt(np.mean(y[int(a * SR):int(b * SR)] ** 2)))
        self.assertLess(rms(0.0, 0.2), 0.05 * rms(5, 7))
        self.assertLess(rms(11.8, 12.0), 0.05 * rms(5, 7))


class Balance(unittest.TestCase):
    def setUp(self):
        self.saved = mixer.STATE.get('processed')

    def tearDown(self):
        mixer.STATE['processed'] = self.saved

    def rows(self, bass_db):
        mixer.STATE['processed'] = {'lead': tone(-40), 'bass': tone(bass_db, f=60.0)}
        score = {'tracks': [{'name': 'lead', 'role': 'melody'}, {'name': 'bass', 'role': 'bass'}]}
        return [r[0] for r in qg.balance_rows(score)]

    def test_bass_inside_its_allowance_passes(self):
        self.assertEqual(self.rows(-36), ['PASS'])

    def test_bass_far_above_the_lead_fails(self):
        self.assertEqual(self.rows(-27), ['FAIL'])

    def test_bass_a_little_over_warns(self):
        self.assertEqual(self.rows(-29.5), ['WARN'])


class MixPreset(unittest.TestCase):
    def test_no_preset_fails_and_a_copy_of_default_fails(self):
        self.assertEqual([r[0] for r in _rows({})], ['FAIL'])
        self.assertEqual([r[0] for r in _rows({'mix_preset': 'default'})], ['FAIL'])

    def test_use_mix_changes_levels_and_default_restores(self):
        import presets
        presets.add_project(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tmp_mixproj'))
        base = dict(mixer.use_mix('default')['level_by_role'])
        self.assertEqual(mixer._level_by_role()['bass'], base['bass'])
        mixer.use_mix(None)


def _rows(score):
    import presets
    if not presets.PROJECT_ROOTS:          # the row only applies in project mode; make that explicit
        presets.add_project(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tmp_mixproj'))
    out = []
    qg.mix_preset_row(score, out)
    return out


if __name__ == '__main__':
    unittest.main()
