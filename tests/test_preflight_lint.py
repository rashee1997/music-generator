# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""preflight_lint: each row fails on the fault it names and passes on the repaired score.

Run: python -m unittest tests.test_preflight_lint
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import preflight_lint as pl  # noqa: E402


def lookup_for(table):
    return lambda kind, name: table.get(f'{kind}:{name}')


def level(rows, name):
    return [r[0] for r in rows if r[1] == name]


def note(t, d, p=60):
    return dict(t=t, d=d, p=p, v=0.8)


class Range(unittest.TestCase):
    table = {'instrument:horns': {'sfz': {'library': 'x', 'patch': 'Horn'}}}

    def rows(self, pitches):
        score = {'bpm': 120, 'tracks': [dict(name='horns', instrument='horns', role='melody', notes=[note(i, 1, p) for i, p in enumerate(pitches)])]}
        return pl.range_rows(score, lookup_for(self.table), lambda b, p: (35, 77), None)

    def test_a_note_above_the_patch_fails(self):
        r = self.rows([60, 79, 81])
        self.assertEqual(level(r, 'preflight.range'), ['FAIL'])
        self.assertIn('79', r[0][2])

    def test_notes_inside_the_patch_pass(self):
        self.assertEqual(level(self.rows([40, 60, 77]), 'preflight.range'), ['PASS'])

    def test_an_unreadable_patch_is_info_not_a_pass(self):
        score = {'bpm': 120, 'tracks': [dict(name='horns', instrument='horns', role='melody', notes=[note(0, 1)])]}
        r = pl.range_rows(score, lookup_for(self.table), lambda b, p: None, None)
        self.assertEqual(level(r, 'preflight.range'), ['INFO'])


class SfzRange(unittest.TestCase):
    def test_range_comes_from_the_file_and_its_includes(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, 'inc.sfz'), 'w').write('<region>\nlokey=40 hikey=50\n<region>\nlokey=c4 hikey=a#4\n')
            open(os.path.join(d, 'patch.sfz'), 'w').write('<group>\n#include "inc.sfz"\n<region>\nsw_lokey=0 sw_hikey=5 key=30\n')
            self.assertEqual(pl.sfz_range(os.path.join(d, 'patch.sfz')), (30, 70))

    def test_a_missing_file_is_none(self):
        self.assertIsNone(pl.sfz_range('/no/such/file.sfz'))


class SfxLength(unittest.TestCase):
    table = {'sfx:step': {'seconds': 1.0}}

    def rows(self, d, gap):
        score = {'bpm': 120, 'tracks': [dict(name='steps', instrument='sfx:step', role='fx', notes=[note(0, d), note(gap, d)])]}
        return pl.sfx_length_rows(score, lookup_for(self.table))

    def test_an_event_shorter_than_its_sound_fails(self):
        self.assertEqual(level(self.rows(d=0.8, gap=4.0), 'preflight.sfx_length'), ['FAIL'])       # 0.4 s of a 1 s sound

    def test_the_next_onset_cutting_the_ring_fails(self):
        self.assertEqual(level(self.rows(d=4.0, gap=1.0), 'preflight.sfx_length'), ['FAIL'])       # 0.5 s to the next event

    def test_room_for_the_whole_sound_passes(self):
        self.assertEqual(level(self.rows(d=3.0, gap=4.0), 'preflight.sfx_length'), ['PASS'])


class SectionEdge(unittest.TestCase):
    sections = [dict(name='a', start_bar=1, end_bar=2, energy=0.5), dict(name='b', start_bar=3, end_bar=4, energy=0.5)]

    def rows(self, events):
        score = {'bpm': 120, 'ts': [4, 4], 'plan': dict(sections=self.sections),
                 'tracks': [dict(name='snap', instrument='sfx:snap', role='fx', notes=[note(t, d) for t, d in events])]}
        return pl.section_edge_rows(score)

    def test_a_sparse_sound_that_runs_into_a_section_with_no_event_of_its_own_warns(self):
        self.assertEqual(level(self.rows([(7.0, 3.0)]), 'preflight.section_edge'), ['WARN'])

    def test_a_sound_that_ends_before_the_line_passes(self):
        self.assertEqual(level(self.rows([(6.0, 1.5)]), 'preflight.section_edge'), ['PASS'])

    def test_a_long_bed_may_cross_the_lines(self):
        self.assertEqual(level(self.rows([(0.0, 30.0)]), 'preflight.section_edge'), ['PASS'])


class Unison(unittest.TestCase):
    def rows(self, p_b, d=4.0, a='violins', b='choir'):
        score = {'tracks': [dict(name=a, role='pad', instrument='x', notes=[note(0, d, 74)]), dict(name=b, role='pad', instrument='y', notes=[note(0, d, p_b)])]}
        return pl.unison_rows(score)

    def test_two_instruments_on_one_pitch_warn(self):
        self.assertEqual(level(self.rows(74), 'preflight.unison'), ['WARN'])

    def test_a_third_apart_passes(self):
        self.assertEqual(level(self.rows(78), 'preflight.unison'), ['PASS'])

    def test_short_notes_pass(self):
        self.assertEqual(level(self.rows(74, d=1.0), 'preflight.unison'), ['PASS'])

    def test_two_parts_of_one_family_pass(self):
        self.assertEqual(level(self.rows(74, a='violins_tremolo', b='violins_sustain'), 'preflight.unison'), ['PASS'])


class FigureLevel(unittest.TestCase):
    sections = [dict(name='quiet', start_bar=1, end_bar=4, energy=0.2), dict(name='loud', start_bar=5, end_bar=8, energy=1.0)]

    def rows(self, role, start):
        score = {'bpm': 120, 'ts': [4, 4], 'plan': dict(sections=self.sections),
                 'tracks': [dict(name='flute', role=role, instrument='x', notes=[note(start + 2 * i, 2.0) for i in range(4)])]}
        return pl.figure_level_rows(score)

    def test_a_melody_that_plays_only_the_quiet_sections_warns(self):
        self.assertEqual(level(self.rows('melody', 0.0), 'preflight.figure_level'), ['WARN'])

    def test_the_same_part_as_a_counter_passes(self):
        self.assertEqual(level(self.rows('counter', 0.0), 'preflight.figure_level'), ['PASS'])

    def test_a_melody_in_the_loud_section_passes(self):
        self.assertEqual(level(self.rows('melody', 16.0), 'preflight.figure_level'), ['PASS'])


class Placement(unittest.TestCase):
    def rows(self, az_fx, el_fx=0.0):
        score = {'bpm': 120, 'tracks': [dict(name='cello', role='ostinato', instrument='cello', notes=[note(0, 8)]),
                                        dict(name='step', role='fx', instrument='sfx:step', notes=[note(0, 8)],
                                             spatial=dict(azimuth=az_fx, elevation=el_fx, distance=1.0))]}
        return pl.placement_rows(score, lookup_for({'instrument:cello': {'spatial': dict(azimuth=-26.0, elevation=0.0)}}))

    def test_a_sound_beside_a_part_at_the_same_height_warns(self):
        self.assertEqual(level(self.rows(-20.0), 'preflight.placement'), ['WARN'])

    def test_a_sound_wide_of_the_part_passes(self):
        self.assertEqual(level(self.rows(-90.0), 'preflight.placement'), ['PASS'])

    def test_a_sound_above_the_part_passes(self):
        self.assertEqual(level(self.rows(-20.0, el_fx=20.0), 'preflight.placement'), ['PASS'])


class Clock(unittest.TestCase):
    """The plan must be built on the renderer's own tempo map."""

    def score(self, start_s):
        return {'ts': [4, 4], 'bpm': 120, 'tempo_points': [[0, 120], [8, 60], [16, 120]], 'rubato': 0.0, 'wander': 0.0, 'ritard': 0.0,
                'tracks': [{'name': 'a', 'notes': [{'t': 0.0, 'd': 100.0, 'p': 60, 'v': 0.5}]}],
                'plan': {'sections': [{'name': 'late', 'start_bar': 5, 'end_bar': 8, 'start_s': start_s}]}}

    def test_a_plan_on_the_renderers_map_passes(self):
        import humanize as hz
        s = self.score(0.0)
        s['plan']['sections'][0]['start_s'] = float(hz.tempo_map_for(s).sec(16.0))
        self.assertEqual(level(pl.clock_rows(s), 'preflight.clock'), ['PASS'])

    def test_a_plan_on_another_clock_fails(self):
        self.assertEqual(level(pl.clock_rows(self.score(8.0)), 'preflight.clock'), ['FAIL'])

    def test_a_score_with_no_map_is_not_judged(self):
        s = self.score(8.0)
        s.pop('tempo_points')
        self.assertEqual(pl.clock_rows(s), [])


class FullChecks(unittest.TestCase):
    def test_the_command_line_set_includes_the_intent_rows(self):
        s = {'ts': [4, 4], 'bpm': 100, 'intent': {'emotions': ['tense'], 'avoid': ['four_on_floor']},
             'tracks': [{'name': 'kick', 'role': 'drum', 'instrument': 'standard',
                         'notes': [{'t': float(i), 'd': 0.5, 'p': 36, 'v': 0.6} for i in range(32)]}]}
        names = [r[1] for r in pl.full_checks(s, None, probe=False)]
        self.assertIn('intent.avoid', names)


if __name__ == '__main__':
    unittest.main()


class InstEq(unittest.TestCase):
    """An inst_eq entry that names no instrument of the score is silent at render time, so preflight says so."""

    def test_a_key_by_track_name_is_flagged_and_a_key_by_instrument_passes(self):
        from unittest import mock
        score = dict(mix_preset='m', tracks=[dict(name='snare', instrument='pursuit_snare', notes=[dict(t=0, d=1, p=38)])])
        with mock.patch('presets.load', return_value={'m': {'inst_eq': {'snare': [{'type': 'peak'}]}}}):
            rows = pl.inst_eq_rows(score)
        self.assertEqual(rows[0][0], 'WARN')
        self.assertIn('snare', rows[0][2])
        with mock.patch('presets.load', return_value={'m': {'inst_eq': {'pursuit_snare': [{'type': 'peak'}]}}}):
            self.assertEqual(pl.inst_eq_rows(score)[0][0], 'PASS')
        with mock.patch('presets.load', return_value={'m': {}}):
            self.assertEqual(pl.inst_eq_rows(score), [])


class ChoirLayers(unittest.TestCase):
    """preflight.choir_layers: one block of identical singers is the same choir at every dynamic."""
    def rows(self, tracks, presets_map):
        import preflight_lint as pl

        def lookup(kind, name):
            return presets_map.get(name)
        return pl.choir_layer_rows({'tracks': tracks}, lookup)

    def test_a_flat_synthesised_choir_alone_warns(self):
        r = self.rows([dict(name='choir', instrument='x_choir', role='pad', notes=[{'t': 0, 'd': 1, 'p': 60}], vocal={'ensemble': {'voices': 8}})], {})
        self.assertEqual(r[0][:2], ('WARN', 'preflight.choir_layers'))

    def test_layers_or_a_second_voice_part_pass(self):
        r = self.rows([dict(name='choir', instrument='x_choir', role='pad', notes=[{'t': 0, 'd': 1, 'p': 60}], vocal={'ensemble': {'voices': 8, 'layers': [{'name': 'a'}]}})], {})
        self.assertEqual(r[0][0], 'PASS')
        r = self.rows([dict(name='a', instrument='x', role='pad', notes=[{'t': 0, 'd': 1, 'p': 60}], vocal={'ensemble': {'voices': 6}}),
                       dict(name='b', instrument='y', role='pad', notes=[{'t': 0, 'd': 1, 'p': 60}], vocal={'ensemble': {'voices': 6}})], {})
        self.assertEqual(r[0][0], 'PASS')

    def test_one_sampled_choir_warns_and_no_voice_is_silent(self):
        r = self.rows([dict(name='c', instrument='choir', role='pad', notes=[{'t': 0, 'd': 1, 'p': 60}])], {'choir': {'instrument': 'choir'}})
        self.assertEqual(r[0][0], 'WARN')
        self.assertEqual(self.rows([dict(name='v', instrument='violin', role='melody', notes=[{'t': 0, 'd': 1, 'p': 60}])], {'violin': {'instrument': 'violin'}}), [])
