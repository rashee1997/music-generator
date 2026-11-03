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

#!/usr/bin/env python3
"""test_extraction_residual.py - an instrument the music_db did not declare is found in the residual and given its own stem."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
try:                                                     # from tests/, or as `unittest tests.test_extraction_residual`
    import test_extraction_separate as T  # noqa: E402
except ModuleNotFoundError:
    from tests import test_extraction_separate as T  # noqa: E402
from extraction import config, notes, residual, separate, spectrum, voices  # noqa: E402


class TestResidual(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load()
        stems, mix = T.build()
        cls.stems, cls.mix = stems, mix
        pri = {'voices': [{'id': k, 'midi_lo': lo, 'midi_hi': hi, 'spans': [], 'timbre': None}
                          for k, (lo, hi) in T.RANGES.items() if k != 'pad']}          # the pad is not declared
        spec = spectrum.semitone_spectrum(mix.mean(0), T.SR, T.CENTS, cls.cfg)
        found, _ = notes.find_notes(spec, pri, cls.cfg)
        vs, _ = voices.assign(found, spec, pri, cls.cfg)
        cls.found_first_pass = [k for k in vs if k.startswith('unknown_')]
        vs = {k: v for k, v in vs.items() if v['declared']}                      # make the first pass miss the pad entirely
        cls.first = separate.separate(mix, T.SR, vs, spec, T.CENTS, cls.cfg)
        cls.res, cls.vs, cls.log = residual.rounds(mix, T.SR, vs, spec, T.CENTS, cls.cfg, separate.separate, first=cls.first)

    def test_undeclared_notes_are_clustered_into_a_voice_on_the_first_pass(self):
        self.assertEqual(self.found_first_pass, ['unknown_1'])

    def test_a_missed_voice_is_added_by_a_round_and_unexplained_energy_falls(self):
        self.assertTrue([k for k in self.vs if k.startswith('unknown_')])
        self.assertLess(self.log[-1]['unexplained_pct'], self.log[0]['unexplained_pct'])
        self.assertLessEqual(len([k for k in self.vs if k.startswith('unknown_')]), 2)

    def test_the_new_stem_is_the_missing_instrument(self):
        s = max(T.sdr(self.stems['pad'], a) for k, a in self.res['voices'].items() if k.startswith('unknown_'))
        print(f'  undeclared pad recovered: SDR {s:.1f} dB; unexplained {[r["unexplained_pct"] for r in self.log]}%')
        self.assertGreater(s, 5.0)

    def test_declared_voices_do_not_get_worse(self):
        for k in ('bass', 'lead'):
            before = T.sdr(self.stems[k], self.first['voices'][k])
            after = T.sdr(self.stems[k], self.res['voices'][k])
            self.assertGreater(after, before - 3.5, k)


if __name__ == '__main__':
    unittest.main()
