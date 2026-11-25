# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""arc_report.py: a loud-then-quiet signal reports its quiet stretch, a steady one reports none.

Run: python -m unittest tests.test_arc_report
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'helpers'))
import arc_report  # noqa: E402

SR = 44100


def _tone(seconds, amp):
    t = np.arange(int(seconds * SR)) / SR
    return amp * np.sin(2 * np.pi * 220.0 * t)


class ArcReport(unittest.TestCase):
    def _run(self, x, sections=None):
        with tempfile.TemporaryDirectory() as d:
            wav = os.path.join(d, 'a.wav')
            sf.write(wav, np.stack([x, x], 1), SR)
            score = None
            if sections:
                score = os.path.join(d, 's.json')
                json.dump({'plan': {'sections': sections}}, open(score, 'w'))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                out = arc_report.report(wav, score)
            return out, buf.getvalue()

    def test_a_quiet_middle_is_reported_as_a_gap(self):
        x = np.concatenate([_tone(10, 0.5), _tone(10, 0.005), _tone(10, 0.5)])
        out, text = self._run(x)
        self.assertEqual(len(out['gaps']), 1)
        self.assertIn('quiet stretches', text)

    def test_a_steady_signal_has_no_gap_and_full_pressure(self):
        out, text = self._run(_tone(20, 0.3))
        self.assertEqual(out['gaps'], [])
        self.assertGreater(out['share'], 0.95)

    def test_sections_come_from_the_score_and_a_louder_one_is_nearer_the_top(self):
        x = np.concatenate([_tone(10, 0.05), _tone(10, 0.5)])
        out, _ = self._run(x, [dict(name='soft', start_s=0, end_s=10), dict(name='loud', start_s=10, end_s=20)])
        names = [r[0] for r in out['sections']]
        self.assertEqual(names, ['soft', 'loud'])
        self.assertLess(out['sections'][0][3], out['sections'][1][3])


if __name__ == '__main__':
    unittest.main()
