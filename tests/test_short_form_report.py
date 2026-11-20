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

"""short_form_report: each measurement fails on the input it is meant to catch and passes on one it is not."""
import sys
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts' / 'helpers'))
sys.path.insert(0, str(SK / 'scripts'))

import short_form_report as sf  # noqa: E402

SR = 22050


def tone(freq, sec, amp=0.4):
    t = np.arange(int(sec * SR)) / SR
    return amp * np.sin(2 * np.pi * freq * t)


class LoopSeam(unittest.TestCase):
    def test_a_whole_number_of_cycles_loops_without_a_step(self):
        x = tone(441.0, 2.0)                                  # 2 s of 441 Hz at 22050 Hz: 882 whole cycles
        self.assertLess(sf.loop_seam(x, SR)['step_ratio'], 1.0)

    def test_a_cut_mid_cycle_steps_at_the_seam(self):
        x = tone(441.0, 2.0)[:-11]                            # ends partway up the next cycle
        x = np.concatenate([np.full(1, 0.0), x + 0.3])        # and starts at a different value
        self.assertGreater(sf.loop_seam(x, SR)['step_ratio'], 1.0)

    def test_the_level_step_is_the_end_against_the_start(self):
        x = np.concatenate([tone(300.0, 1.0, 0.1), tone(300.0, 1.0, 0.4)])
        self.assertAlmostEqual(sf.loop_seam(x, SR)['level_step_db'], 20 * np.log10(4.0), delta=0.5)


class PhoneBand(unittest.TestCase):
    def test_energy_in_the_speaker_band_and_below_it(self):
        mid = sf.phone_band(tone(1000.0, 2.0), SR)
        self.assertGreater(mid['in_band'], 0.95)
        self.assertLess(mid['below_low'], 0.01)
        sub = sf.phone_band(tone(60.0, 2.0), SR)
        self.assertGreater(sub['below_low'], 0.9)
        self.assertLess(sub['in_band'], 0.05)


class Hook(unittest.TestCase):
    def test_attacks_in_the_first_seconds_are_counted(self):
        x = np.zeros(int(6 * SR))
        for t0 in (0.2, 0.9, 1.6):
            i = int(t0 * SR)
            x[i:i + int(0.3 * SR)] = tone(880.0, 0.3)
        h = sf.hook(x, SR, 3.0)
        self.assertEqual(h['onsets'], 3)

    def test_a_silent_start_has_no_hook(self):
        x = np.zeros(int(6 * SR))
        x[int(4 * SR):int(4.3 * SR)] = tone(880.0, 0.3)
        self.assertEqual(sf.hook(x, SR, 3.0)['onsets'], 0)


def score_of(*lines, ts=(4, 4)):
    return dict(ts=list(ts), tracks=[dict(name=f't{i}', role=r, notes=[dict(t=float(t), d=0.5, p=p, v=80) for t, p in ns])
                                     for i, (r, ns) in enumerate(lines)])


class Motif(unittest.TestCase):
    def test_the_opening_shape_is_counted_wherever_it_returns(self):
        shape = [0, 2, 4, 2, 7]                                 # up a step, up a step, down, up a leap
        melody = []
        for bar, root in enumerate((60, 62, 55, 60)):           # the same shape on four roots, a different tail between
            melody += [(bar * 4 + i * 0.5, root + s) for i, s in enumerate(shape)]
            melody += [(bar * 4 + 3.0, root + 11), (bar * 4 + 3.5, root - 12)]
        m = sf.motif_returns(score_of(('melody', melody)), 5)
        self.assertGreaterEqual(m['occurrences'], 4)
        self.assertGreaterEqual(m['exact'], 1)

    def test_a_line_that_never_repeats_scores_one(self):
        rng = np.random.default_rng(4)
        notes = [(i * 0.5, int(60 + rng.integers(-12, 13))) for i in range(40)]
        self.assertLessEqual(sf.motif_returns(score_of(('melody', notes)), 5)['occurrences'], 3)


class Density(unittest.TestCase):
    def test_a_flat_arrangement_has_no_spread_and_a_built_one_does(self):
        flat = [(i * 0.5, 60) for i in range(64)]                # eight notes a bar for eight bars
        self.assertLess(sf.density(score_of(('melody', flat)), 4)['cv'], 0.05)
        built = [(i * 2.0, 60) for i in range(8)] + [(16 + i * 0.25, 60) for i in range(64)]
        self.assertGreater(sf.density(score_of(('melody', built)), 4)['cv'], 0.3)


if __name__ == '__main__':
    unittest.main()
