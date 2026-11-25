# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""preflight_levels: each row warns on the fault it names and passes on the repaired score.

Run: python -m unittest tests.test_preflight_levels
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'helpers'))
import preflight_levels as pl  # noqa: E402


def level(rows, name):
    return [r[0] for r in rows if r[1] == name]


def note(t, d, p=60, v=0.8):
    return dict(t=t, d=d, p=p, v=v)


SECTIONS = [dict(name='quiet', start_bar=1, end_bar=4, energy=0.2), dict(name='mid', start_bar=5, end_bar=8, energy=0.6),
            dict(name='loud', start_bar=9, end_bar=12, energy=1.0)]


class StemLevel(unittest.TestCase):
    def score(self, v_quiet, curve_quiet):
        notes = [note(0, 2, v=v_quiet), note(8, 2, v=v_quiet), note(16, 2, v=0.9), note(24, 2, v=0.9), note(32, 2, v=0.9), note(40, 2, v=0.9)]
        return {'ts': [4, 4], 'plan': dict(sections=SECTIONS), 'dynamics': [[0, curve_quiet], [15.9, curve_quiet], [16, 1.0], [48, 1.0]],
                'tracks': [dict(name='horns', role='chord', instrument='x', notes=notes)]}

    def test_quiet_notes_on_a_quiet_curve_warn(self):
        self.assertEqual(level(pl.stem_level_rows(self.score(0.4, 0.3)), 'preflight.stem_level'), ['WARN'])

    def test_quiet_notes_on_a_loud_curve_pass(self):
        self.assertEqual(level(pl.stem_level_rows(self.score(0.4, 1.0)), 'preflight.stem_level'), ['PASS'])

    def test_a_quiet_curve_with_the_usual_velocity_passes(self):
        self.assertEqual(level(pl.stem_level_rows(self.score(0.9, 0.3)), 'preflight.stem_level'), ['PASS'])


class Arc(unittest.TestCase):
    def score(self, reverse=False):
        counts = [1, 3, 6]
        if reverse:
            counts = counts[::-1]
        tracks = []
        for i in range(6):
            notes = []
            for sec, n in zip(SECTIONS, counts):
                if i < n:
                    a = (sec['start_bar'] - 1) * 4
                    notes += [note(a + 4 * k, 4.0, v=0.8) for k in range(4)]
            tracks.append(dict(name=f'p{i}', role='chord', instrument='x', notes=notes))
        return {'ts': [4, 4], 'plan': dict(sections=SECTIONS), 'dynamics': [[0, 1.0], [48, 1.0]], 'tracks': tracks}

    def test_more_parts_in_the_louder_sections_passes(self):
        self.assertEqual(level(pl.arc_rows(self.score()), 'preflight.arc'), ['PASS'])

    def test_the_busiest_section_declared_the_quietest_warns(self):
        self.assertEqual(level(pl.arc_rows(self.score(reverse=True)), 'preflight.arc'), ['WARN'])

    def test_two_sections_are_not_ranked(self):
        s = self.score()
        s['plan'] = dict(sections=SECTIONS[:2])
        self.assertEqual(level(pl.arc_rows(s), 'preflight.arc'), ['INFO'])


class Tempo(unittest.TestCase):
    def test_a_wide_map_warns(self):
        self.assertEqual(level(pl.tempo_rows({'tempo_points': [[0, 72], [100, 158]]}), 'preflight.tempo'), ['WARN'])

    def test_a_wide_map_with_a_recorded_skip_passes(self):
        s = {'tempo_points': [[0, 72], [100, 158]], 'gate': {'tempo.audio': {'mode': 'skip', 'reason': 'measured twice'}}}
        self.assertEqual(level(pl.tempo_rows(s), 'preflight.tempo'), ['PASS'])

    def test_a_narrow_map_passes(self):
        self.assertEqual(level(pl.tempo_rows({'tempo_points': [[0, 100], [100, 108]]}), 'preflight.tempo'), ['PASS'])

    def test_one_tempo_passes(self):
        self.assertEqual(level(pl.tempo_rows({'bpm': 120}), 'preflight.tempo'), ['PASS'])


class Roughness(unittest.TestCase):
    def score(self, p_b, d=4.0, name_b='choir'):
        return {'tracks': [dict(name='violins', role='pad', instrument='x', notes=[note(0, d, 69)]), dict(name=name_b, role='pad', instrument='y', notes=[note(0, d, p_b)])]}

    def test_a_second_between_instruments_warns(self):
        self.assertEqual(level(pl.roughness_rows(self.score(70)), 'preflight.roughness'), ['WARN'])
        self.assertEqual(level(pl.roughness_rows(self.score(71)), 'preflight.roughness'), ['WARN'])

    def test_a_third_passes(self):
        self.assertEqual(level(pl.roughness_rows(self.score(72)), 'preflight.roughness'), ['PASS'])

    def test_a_short_clash_passes(self):
        self.assertEqual(level(pl.roughness_rows(self.score(70, d=1.0)), 'preflight.roughness'), ['PASS'])

    def test_one_family_clashing_with_itself_passes(self):
        self.assertEqual(level(pl.roughness_rows(self.score(70, name_b='violins_sustain')), 'preflight.roughness'), ['PASS'])


if __name__ == '__main__':
    unittest.main()
