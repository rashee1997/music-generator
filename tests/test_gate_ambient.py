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

"""Quality-gate checks for natural ambience: roughness must score partials, not noise; ambient_bed must judge beds and event stems
for what they are, with a silent floor relative to the mix.  Run: python -m unittest tests.test_gate_ambient"""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import mixer  # noqa: E402
import naturalness_check as nc  # noqa: E402
import quality_gate as qg  # noqa: E402

SR = 44100


def stereo(x):
    return np.stack([x, x], 1).astype(np.float32)


def tones(freqs, secs=8, partials=4):
    t = np.arange(SR * secs) / SR
    return sum(np.sin(2 * np.pi * f * h * t) / h for f in freqs for h in range(1, partials + 1)) * 0.05


class RoughnessScoresPartialsNotNoise(unittest.TestCase):
    def test_noise_is_not_rough(self):
        rng = np.random.default_rng(2)
        noise = signal.sosfilt(signal.butter(2, [200, 5000], 'band', fs=SR, output='sos'), rng.standard_normal(SR * 10)) * 0.1
        rows, m = nc.cochlear_roughness_check(stereo(noise), sr=SR)
        self.assertNotIn('FAIL', [r[0] for r in rows])
        self.assertLess(m['mean_roughness'], 0.15)

    def test_a_semitone_cluster_is_still_rough(self):
        cluster, triad = tones([440.0, 466.16, 493.88]), tones([220.0, 329.63, 440.0])
        _, rough = nc.cochlear_roughness_check(stereo(cluster), sr=SR)
        _, calm = nc.cochlear_roughness_check(stereo(triad), sr=SR)
        self.assertGreater(rough['mean_roughness'], 3 * calm['mean_roughness'])

    def test_a_tonal_cluster_stays_rough_on_top_of_a_noise_bed(self):
        rng = np.random.default_rng(4)
        bed = signal.sosfilt(signal.butter(2, [200, 5000], 'band', fs=SR, output='sos'), rng.standard_normal(SR * 8)) * 0.05
        _, plain = nc.cochlear_roughness_check(stereo(tones([440.0, 466.16, 493.88])), sr=SR)
        _, mixed = nc.cochlear_roughness_check(stereo(tones([440.0, 466.16, 493.88]) + bed), sr=SR)
        self.assertGreater(mixed['mean_roughness'], 0.5 * plain['mean_roughness'])


class AmbientBedJudgesEachStemForWhatItIs(unittest.TestCase):
    N = 40 * SR

    def setUp(self):
        self.rng = np.random.default_rng(1)
        self.saved = mixer.STATE.get('processed')

    def tearDown(self):
        mixer.STATE['processed'] = self.saved

    def db(self, x, level):
        return stereo(x / (np.sqrt(np.mean(x ** 2)) + 1e-12) * 10 ** (level / 20))

    def rows(self, **stems):
        t = np.arange(self.N) / SR
        lead = self.db(np.sin(2 * np.pi * 440 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.3 * t)), -40)
        mixer.STATE['processed'] = dict(lead=lead, **stems)
        score = {'bpm': 60, 'tracks': [{'name': 'lead', 'role': 'melody', 'instrument': 'flute'}] +
                 [{'name': k, 'role': 'environment' if k == 'bed' else 'fx', 'instrument': f'env:{k}', 'full_length': True} for k in stems]}
        return qg.ambient_fusion_rows(score, None, sr=SR)

    def test_quiet_but_steady_bed_under_a_quiet_mix_passes(self):
        bed = self.db(self.rng.standard_normal(self.N), -62)          # 22 dB under the lead: a normal bed, below the old fixed -58 floor
        rows = self.rows(bed=bed)
        self.assertEqual([r[0] for r in rows if r[1] == 'ambient_bed'], ['PASS'])

    def test_a_real_hole_in_a_bed_still_fails(self):
        bed = self.db(self.rng.standard_normal(self.N), -62)
        bed[15 * SR:19 * SR] = 0.0
        rows = self.rows(bed=bed)
        self.assertIn('FAIL', [r[0] for r in rows if r[1] == 'ambient_bed'])

    def test_sparse_calls_are_judged_as_events(self):
        calls = np.zeros(self.N)
        for t0 in range(10, 38, 4):                                   # a call every 4 s, 0.3 s long, exact silence between
            calls[t0 * SR:t0 * SR + SR // 3] = self.rng.standard_normal(SR // 3)
        rows = [r for r in self.rows(calls=self.db(calls, -50)) if r[1] == 'ambient_bed']
        self.assertEqual([r[0] for r in rows], ['PASS'])
        self.assertIn('event stem', rows[0][2])

    def test_events_too_quiet_to_hear_fail(self):
        calls = np.zeros(self.N)
        for t0 in range(10, 38, 4):
            calls[t0 * SR:t0 * SR + SR // 3] = self.rng.standard_normal(SR // 3)
        rows = [r for r in self.rows(calls=self.db(calls, -90)) if r[1] == 'ambient_bed']
        self.assertEqual([r[0] for r in rows], ['FAIL'])


if __name__ == '__main__':
    unittest.main()
