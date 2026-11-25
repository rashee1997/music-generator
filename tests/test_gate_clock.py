# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The gate counts beats on the tempo map the renderer plays, and a gate module cannot read the flat bpm without saying why.

Run: python -m unittest tests.test_gate_clock
"""
import os
import re
import sys
import unittest

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import gate_checks  # noqa: E402
import gate_clock  # noqa: E402
import pattern_audit  # noqa: E402

STILL = {'humanize': 'tight', 'rubato': 0.0, 'wander': 0.0, 'ritard': 0.0}                  # a tempo map with no rubato, so beats are exact
SLOW = dict(STILL, bpm=120, ts=[4, 4], seed=1, tempo_points=[[0, 60], [100, 60]])      # plays at 60 BPM; the flat bpm says 120


class Clock(unittest.TestCase):
    def test_a_score_with_a_tempo_map_is_counted_on_the_map(self):
        self.assertAlmostEqual(float(gate_clock.seconds_fn(SLOW)(8.0)), 8.0, places=2)           # 8 beats at 60 BPM, not 4 s

    def test_a_score_without_a_map_is_counted_at_its_bpm(self):
        self.assertAlmostEqual(float(gate_clock.seconds_fn({'bpm': 120})(8.0)), 4.0)

    def test_arrays_are_converted_together(self):
        out = gate_clock.seconds_fn({'bpm': 60})(np.array([0.0, 1.0, 2.0]))
        self.assertEqual([round(float(v), 3) for v in out], [0.0, 1.0, 2.0])

    def test_the_beat_grid_follows_a_tempo_that_changes(self):
        score = dict(STILL, bpm=90, seed=1, tempo_points=[[0, 60], [8, 120], [100, 120]])
        g = gate_clock.beat_grid_seconds(score, 12.0)
        gaps = np.diff(g)
        self.assertGreater(gaps[0], gaps[12])                  # the beats close up as the tempo rises
        self.assertAlmostEqual(float(gaps[-1]), 0.5, places=1)


class Consumers(unittest.TestCase):
    def test_sections_given_in_bars_land_where_the_map_plays_them(self):
        score = dict(SLOW, plan={'sections': [{'name': 'a', 'start_bar': 1, 'end_bar': 2}, {'name': 'b', 'start_bar': 2, 'end_bar': 3}]})
        secs = gate_checks.section_bounds(score, 100.0)
        self.assertAlmostEqual(secs[1]['start_s'], 8.0, places=1)           # 8 beats (start_bar 2 x 4) at 60 BPM is 8 s; the flat 120 BPM said 4 s

    def test_the_collision_message_names_the_time_on_the_map(self):
        score = dict(SLOW, tracks=[{'name': 'x', 'notes': [{'t': 8.0, 'd': 1.0, 'p': 60}, {'t': 8.0, 'd': 1.0, 'p': 60}]}])
        rows = pattern_audit.note_collision(score)
        self.assertIn('8.00 s', rows[0][2])


class NoFlatBpmWithoutAReason(unittest.TestCase):
    """The lint of the lints: every read of the flat `bpm` in a gate module carries `flat-bpm-ok: <why>` on its line."""
    MODULES = ('quality_gate.py', 'stem_gate.py', 'gate_checks.py', 'gate_audio.py', 'pattern_audit.py', 'mix_diagnostics.py',
               'spatial_gate.py', 'project_gate.py', 'preflight_lint.py')
    PATTERN = re.compile(r"""get\(\s*['"]bpm['"]|\[\s*['"]bpm['"]\s*\]""")

    def test_every_flat_bpm_read_says_why(self):
        bad = []
        for name in self.MODULES:
            path = os.path.join(ROOT, 'scripts', name)
            if not os.path.isfile(path):
                continue
            for i, line in enumerate(open(path, encoding='utf-8'), 1):
                if self.PATTERN.search(line) and 'flat-bpm-ok' not in line:
                    bad.append(f'{name}:{i}: {line.strip()[:90]}')
        self.assertEqual(bad, [], 'a gate module reads the flat bpm; use gate_clock.seconds_fn, or add "# flat-bpm-ok: <why>"')

    def test_the_audit_can_fail(self):
        self.assertTrue(self.PATTERN.search("    bd = 60.0 / float(score.get('bpm', 90.0))"))


if __name__ == '__main__':
    unittest.main()
