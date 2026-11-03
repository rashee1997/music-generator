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

"""The behaviour evaluation: it must catch the faults the audit named, and must not invent them on a healthy sound."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import sfx_eval as ev

SR = 44100


def _rows(x, kinds=(), interp='spot'):
    return ev.problems_for(ev.metrics(x, SR), kinds)


def _faults(x, kinds=()):
    return [msg for s, _, msg in _rows(x, kinds) if s == 'WARN']


class CatchesTheAuditFaults(unittest.TestCase):
    def test_a_whistle_inside_a_noise_event(self):
        rng = np.random.default_rng(1)
        t = np.arange(SR * 2) / SR
        x = 0.2 * rng.standard_normal(len(t)) + 0.25 * np.sin(2 * np.pi * 3200 * t)
        self.assertTrue(any('tonal component' in m for m in _faults(x, ['flow'])))

    def test_a_cycle_wearing_a_texture(self):
        t = np.arange(SR * 2) / SR
        x = np.random.default_rng(2).standard_normal(len(t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t))
        self.assertTrue(any('repeats every' in m for m in _faults(x)))

    def test_identical_transients(self):
        x = np.zeros(SR * 2)
        for i in range(int(0.1 * SR), SR * 2 - 1000, int(0.2 * SR)):
            x[i:i + 400] = np.random.default_rng(3).standard_normal(400) * 0.4
        self.assertTrue(any('same size' in m for m in _faults(x, ['granular'])))

    def test_a_hiss_wall(self):
        from scipy.signal import butter, sosfilt
        x = sosfilt(butter(4, [8000, 16000], btype='band', fs=SR, output='sos'),
                    np.random.default_rng(4).standard_normal(SR))
        self.assertTrue(any('hiss wall' in m for m in _faults(x, ['flow'])))

    def test_a_heavy_contact_with_no_weight(self):
        from scipy.signal import butter, sosfilt
        x = sosfilt(butter(4, [2000, 6000], btype='band', fs=SR, output='sos'),
                    np.random.default_rng(5).standard_normal(SR))
        self.assertTrue(any('structural weight' in m for m in _faults(x, ['impact'])))

    def test_dc_and_peak_normalization(self):
        t = np.arange(SR) / SR
        x = 0.05 + 0.05 * np.sin(2 * np.pi * 200 * t)
        self.assertTrue(any('DC offset' in m for m in _faults(x)))
        flat = 0.9 * np.tanh(6 * np.sin(2 * np.pi * 90 * t))
        flat = flat * (0.9 / np.abs(flat).max())
        self.assertTrue(any('peak-normalized' in m for m in _faults(flat, ['impact'])))


class LeavesHealthySoundsAlone(unittest.TestCase):
    def test_a_varied_granular_texture_passes(self):
        rng = np.random.default_rng(6)
        x = np.zeros(SR * 2)
        for _ in range(60):
            i = int(rng.uniform(0, SR * 2 - 2000))
            d = 600
            amp = rng.uniform(0.05, 0.5)
            t = np.arange(d) / SR
            x[i:i + d] += amp * np.exp(-t / 0.004) * np.sin(2 * np.pi * rng.uniform(700, 4000) * t)
        self.assertEqual([m for m in _faults(x, ['granular'])], [])

    def test_a_silent_buffer_does_not_raise(self):
        m = ev.metrics(np.zeros(100), SR)
        self.assertEqual(m['peak'], 0.0)
        self.assertIsInstance(ev.problems_for(m), list)


class GateWiring(unittest.TestCase):
    def test_rows_are_warn_or_pass_only(self):
        import sfx_eval
        rng = np.random.default_rng(7)
        stems = {'rain': rng.standard_normal((SR, 2)) * 0.1,
                 'hit': np.tanh(6 * rng.standard_normal(SR)) * 0.3}
        score = {'tracks': [{'name': 'rain', 'instrument': 'env:anything'},
                            {'name': 'hit', 'instrument': 'sfx:impact'}]}
        rows = sfx_eval.gate_rows(score, stems)
        self.assertTrue(rows)
        self.assertEqual({s for s, _, _ in rows} - {'WARN', 'PASS'}, set())

    def test_a_piece_without_sfx_or_env_tracks_adds_nothing(self):
        import sfx_eval
        self.assertEqual(sfx_eval.gate_rows({'tracks': [{'name': 'piano', 'instrument': 'piano'}]}, {'piano': None}), [])

    def test_the_gate_calls_it(self):
        src = open(os.path.join(HERE, '..', 'scripts', 'quality_gate.py'), encoding='utf-8').read()
        self.assertIn('sfx_eval.gate_rows', src)


if __name__ == '__main__':
    unittest.main()
