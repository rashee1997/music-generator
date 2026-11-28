# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The orch.* rows: each one fires on a defect and stays quiet on the thing it must not catch.

A row that cannot fail is not a row, so every check has a positive and a negative control.

Run: python -m unittest tests.test_orch_rows
"""
import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import gate_profiles  # noqa: E402
import orch_rows  # noqa: E402
import pattern_audit  # noqa: E402

NO_PRESETS = lambda kind, name: None          # noqa: E731  (an instrument with no preset: identified by name alone)


def score(*tracks, **extra):
    return dict(ts=[4, 4], bpm=120, tracks=list(tracks), **extra)


def track(name, instrument, notes, role='melody', **extra):
    return dict(name=name, instrument=instrument, role=role, notes=notes, **extra)


def line(pitches, start=0.0, step=1.0, d=0.9):
    return [dict(t=start + i * step, d=d, p=p, v=0.7) for i, p in enumerate(pitches)]


def rows(sc, name=None):
    out = orch_rows.checks(sc, exact=NO_PRESETS)
    return [r for r in out if name is None or r[1] == name]


def levels(sc, name):
    return {r[0] for r in rows(sc, name)}


class RangesTable(unittest.TestCase):
    def test_the_shipped_table_is_valid(self):
        self.assertEqual(orch_rows.problems(orch_rows.table(project_roots=[])), [])

    def test_a_broken_table_is_reported(self):
        tab = copy.deepcopy(orch_rows.table(project_roots=[]))
        tab['instruments']['flute']['lo'] = 100
        tab['instruments']['oboe']['voices'] = 0
        tab['aliases']['ghost'] = 'no_such_instrument'
        bad = ' | '.join(orch_rows.problems(tab))
        self.assertIn('flute', bad)
        self.assertIn('oboe', bad)
        self.assertIn('ghost', bad)

    def test_every_instrument_states_that_its_numbers_are_starting_values(self):
        tab = orch_rows.table(project_roots=[])
        self.assertEqual(tab['status'], 'starting value')
        self.assertIn('starting value', tab['provenance'])

    def test_a_project_table_overrides_one_instrument_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'orchestra'))
            with open(os.path.join(d, 'orchestra', 'ranges.json'), 'w', encoding='utf-8') as fh:
                json.dump({'instruments': {'flute': {'lo': 40}}}, fh)
            tab = orch_rows.table(project_roots=[d])
        self.assertEqual(tab['instruments']['flute']['lo'], 40)
        self.assertEqual(tab['instruments']['flute']['hi'], 96)
        self.assertIn('oboe', tab['instruments'])


class Identification(unittest.TestCase):
    def setUp(self):
        self.tab = orch_rows.table(project_roots=[])

    def key(self, name):
        return orch_rows.instrument_key(name, self.tab)

    def test_names_aliases_and_plurals(self):
        self.assertEqual(self.key('violin'), 'violin')
        self.assertEqual(self.key('french_horn'), 'horn')
        self.assertEqual(self.key('Violins'), 'violin')
        self.assertEqual(self.key('green_horns'), 'horn')
        self.assertEqual(self.key('mayan_violins_tremolo'), 'violin')
        self.assertEqual(self.key('string_ensemble'), 'strings')

    def test_a_modifier_means_a_different_instrument_so_nothing_is_guessed(self):
        for name in ('bass_clarinet', 'alto_flute', 'bass_trombone', 'contra_bassoon'):
            self.assertIsNone(self.key(name), name)

    def test_unknown_and_prefixed_names_are_not_identified(self):
        self.assertIsNone(self.key('kalimba_hook'))
        t = track('x', 'sfx:impact', line([60]))
        self.assertIsNone(orch_rows.identify(t, self.tab, NO_PRESETS))
        t = track('x', 'env:forest', line([60]))
        self.assertIsNone(orch_rows.identify(t, self.tab, NO_PRESETS))

    def test_the_preset_decides_before_the_name(self):
        t = track('lead', 'my_patch', line([70]))
        self.assertEqual(orch_rows.identify(t, self.tab, lambda kind, name: {'gm': 'oboe'}), 'oboe')

    def test_the_track_name_is_the_last_resort(self):
        t = track('cellos_low', 'my_patch', line([40]))
        self.assertEqual(orch_rows.identify(t, self.tab, NO_PRESETS), 'cello')


class Range(unittest.TestCase):
    def test_inside_the_range_passes(self):
        sc = score(track('f', 'flute', line([60, 72, 96])))
        self.assertEqual(levels(sc, 'orch.range'), {'PASS'})

    def test_a_double_bass_may_use_its_low_c_extension_but_not_go_further(self):
        self.assertEqual(levels(score(track('b', 'double_bass', line([24, 36]), role='bass')), 'orch.range'), {'PASS'})
        self.assertEqual(levels(score(track('b', 'double_bass', line([21, 36]), role='bass')), 'orch.range'), {'WARN'})
        self.assertEqual(levels(score(track('b', 'double_bass', line([10, 36]), role='bass')), 'orch.range'), {'FAIL'})

    def test_a_little_outside_warns_and_far_outside_fails(self):
        self.assertEqual(levels(score(track('f', 'flute', line([58, 72]))), 'orch.range'), {'WARN'})
        self.assertEqual(levels(score(track('f', 'flute', line([40, 72]))), 'orch.range'), {'FAIL'})
        self.assertEqual(levels(score(track('f', 'flute', line([72, 120]))), 'orch.range'), {'FAIL'})

    def test_the_detail_names_the_track_the_note_and_the_way_out(self):
        detail = rows(score(track('lead', 'flute', line([40, 72]))), 'orch.range')[0][2]
        self.assertIn('"lead"', detail)
        self.assertIn('down to 40', detail)
        self.assertIn('extended_range', detail)

    def test_extended_range_on_the_track_is_the_composers_decision(self):
        sc = score(track('f', 'flute', line([40, 72]), extended_range=True))
        self.assertEqual(rows(sc, 'orch.range'), [])

    def test_an_unknown_instrument_and_a_drum_are_not_judged(self):
        sc = score(track('k', 'kalimba', line([20])), track('d', 'drums', [dict(t=0, d=1, p='kick', v=0.8)], role='drum'))
        self.assertEqual(rows(sc, 'orch.range'), [])

    def test_the_failing_margin_is_a_profile_parameter(self):
        sc = score(track('f', 'flute', line([54, 72])), gate={'orch.range': {'mode': 'relax', 'reason': 'test', 'fail_over_semitones': 3}})
        self.assertEqual(levels(sc, 'orch.range'), {'FAIL'})


class VoiceLeading(unittest.TestCase):
    TOP = [72, 74, 76, 77, 79, 81, 83, 84]

    def pair(self, upper, lower):
        return score(track('a', 'violin', line(upper)), track('b', 'cello', line(lower), role='counter'))

    def test_parallel_fifths_are_flagged(self):
        sc = self.pair(self.TOP, [p - 7 for p in self.TOP])
        r = rows(sc, 'orch.voice_leading')
        self.assertEqual({x[0] for x in r}, {'WARN'})
        self.assertIn('parallel fifth', r[0][2])

    def test_contrary_motion_in_fifths_is_not(self):
        lower = [65, 62, 60, 58, 57, 55, 53, 52]          # moves opposite to the top line
        sc = self.pair(self.TOP, lower)
        self.assertNotIn('WARN', levels(sc, 'orch.voice_leading'))

    def test_a_whole_line_doubled_at_the_octave_is_orchestration_not_an_error(self):
        sc = self.pair(self.TOP, [p - 12 for p in self.TOP])
        self.assertEqual(levels(sc, 'orch.voice_leading'), {'PASS'})

    def test_octaves_are_not_a_fault_unless_the_profile_asks(self):
        lower = [p - 12 for p in self.TOP[:4]] + [66, 64, 62, 60]      # doubled for three moves, then contrary: 3 octaves in 7 moves
        sc = self.pair(self.TOP, lower)
        self.assertEqual(levels(sc, 'orch.voice_leading'), {'PASS'})
        asked = dict(sc, gate={'orch.voice_leading': {'mode': 'relax', 'reason': 'strict counterpoint exercise', 'include_octaves': True}})
        r = rows(asked, 'orch.voice_leading')
        self.assertEqual({x[0] for x in r}, {'WARN'})
        self.assertIn('parallel octave', r[0][2])

    def test_thirds_and_sixths_are_not_flagged(self):
        sc = self.pair(self.TOP, [p - 4 if i % 2 else p - 3 for i, p in enumerate(self.TOP)])
        self.assertEqual(levels(sc, 'orch.voice_leading'), {'PASS'})

    def test_a_chord_track_is_not_a_line_so_it_is_not_paired(self):
        chords = [dict(t=i, d=0.9, p=p, v=0.7) for i in range(8) for p in (48, 55, 60)]
        sc = score(track('a', 'violin', line(self.TOP)), track('pad', 'strings', chords, role='chord'))
        self.assertEqual(rows(sc, 'orch.voice_leading'), [])

    def test_too_few_shared_moves_are_not_judged(self):
        sc = self.pair(self.TOP[:3], [p - 7 for p in self.TOP[:3]])
        self.assertEqual(rows(sc, 'orch.voice_leading'), [])


class Playable(unittest.TestCase):
    def test_a_chord_on_a_solo_wind_is_flagged_and_on_a_section_is_not(self):
        chord = [dict(t=i * 2, d=1.5, p=p, v=0.7) for i in range(4) for p in (62, 66, 69)]
        self.assertIn('WARN', levels(score(track('f', 'flute', chord)), 'orch.playable'))
        self.assertNotIn('WARN', levels(score(track('strings', 'strings', chord, role='chord')), 'orch.playable'))

    def test_a_solo_violin_may_play_a_double_stop(self):
        stops = [dict(t=i * 2, d=1.5, p=p, v=0.7) for i in range(4) for p in (64, 71)]
        self.assertNotIn('WARN', levels(score(track('v', 'violin', stops)), 'orch.playable'))

    def test_a_run_faster_than_the_tongue_is_flagged(self):
        fast = line([72 + i % 3 for i in range(16)], step=0.125, d=0.1)          # 16 notes/s at 120 bpm
        self.assertIn('notes/s', ' '.join(r[2] for r in rows(score(track('f', 'flute', fast)), 'orch.playable')))
        ok = line([72 + i % 3 for i in range(16)], step=0.5, d=0.4)              # 4 notes/s
        self.assertNotIn('WARN', levels(score(track('f', 'flute', ok)), 'orch.playable'))

    def test_a_string_tremolo_is_a_bow_technique_not_a_note_rate(self):
        trem = [dict(t=i * 0.125, d=0.1, p=60 + i % 3, v=0.6, art='tremolo') for i in range(24)]
        plain = [dict(n, art='sustain') for n in trem]
        self.assertNotIn('WARN', levels(score(track('v', 'violin', trem)), 'orch.playable'))
        self.assertIn('WARN', levels(score(track('v', 'violin', plain)), 'orch.playable'))

    def test_a_harp_may_play_fast_where_a_tuba_may_not(self):
        fast = line([48 + i % 5 for i in range(16)], step=0.25, d=0.2)            # 8 notes/s
        self.assertIn('WARN', levels(score(track('t', 'tuba', fast, role='bass')), 'orch.playable'))
        self.assertNotIn('WARN', levels(score(track('h', 'harp', fast)), 'orch.playable'))

    def test_a_brass_phrase_without_a_breath_is_flagged_and_a_gap_clears_it(self):
        held = line([55, 57, 59, 60] * 8, step=1.0, d=1.0)                       # 32 beats = 16 s, never a gap
        self.assertIn('without a breath', ' '.join(r[2] for r in rows(score(track('t', 'trombone', held)), 'orch.playable')))
        breathing = [dict(n, d=0.6) for n in held]          # 0.4 beat = 0.2 s of air at 120 bpm: over the 0.15 s breath
        self.assertNotIn('WARN', levels(score(track('t', 'trombone', breathing)), 'orch.playable'))

    def test_a_section_may_stagger_its_breaths(self):
        held = line([55, 57, 59, 60] * 8, step=1.0, d=1.0)
        self.assertNotIn('WARN', levels(score(track('trombones', 'trombone', held)), 'orch.playable'))

    def test_strings_have_no_breath_limit(self):
        held = line([55, 57, 59, 60] * 8, step=1.0, d=1.0)
        self.assertNotIn('WARN', levels(score(track('v', 'violin', held)), 'orch.playable'))

    def test_the_scale_parameters_tighten_the_row(self):
        ok = line([72 + i % 3 for i in range(8)], step=0.25, d=0.2)              # 8 notes/s: inside the flute's 10
        self.assertNotIn('WARN', levels(score(track('f', 'flute', ok)), 'orch.playable'))
        tight = score(track('f', 'flute', ok), gate={'orch.playable': {'mode': 'relax', 'reason': 'test', 'rate_scale': 0.5}})
        self.assertIn('WARN', levels(tight, 'orch.playable'))


class Voices(unittest.TestCase):
    """_max_voices replaced a pairwise count with a heap sweep: it must agree with the definition and stay fast."""

    @staticmethod
    def brute(notes):
        best = 0
        for n in notes:
            t = float(n['t'])
            best = max(best, sum(1 for m in notes if float(m['t']) <= t + 1e-9 and float(m['t']) + float(m.get('d', 1.0)) - t > orch_rows.OVERLAP_BEATS))
        return best

    def test_it_agrees_with_the_definition_on_random_notes(self):
        import random
        rng = random.Random(7)
        for _ in range(40):
            notes = [dict(t=round(rng.uniform(0, 20), 2), d=round(rng.uniform(0.05, 3.0), 2), p=60) for _ in range(rng.randint(1, 60))]
            self.assertEqual(orch_rows._max_voices(notes), self.brute(notes), notes)

    def test_a_tie_or_a_tiny_overlap_is_not_two_voices(self):
        self.assertEqual(orch_rows._max_voices([dict(t=0, d=1.0, p=60), dict(t=1.0, d=1.0, p=62)]), 1)
        self.assertEqual(orch_rows._max_voices([dict(t=0, d=1.05, p=60), dict(t=1.0, d=1.0, p=62)]), 1)
        self.assertEqual(orch_rows._max_voices([dict(t=0, d=1.5, p=60), dict(t=1.0, d=1.0, p=62)]), 2)

    def test_a_long_score_is_judged_in_well_under_a_second(self):
        import time
        notes = [dict(t=i * 0.5, d=0.45, p=60 + i % 12, v=0.7) for i in range(20000)]
        t0 = time.perf_counter()
        orch_rows._max_voices(notes)
        self.assertLess(time.perf_counter() - t0, 1.0)


class Legato(unittest.TestCase):
    def test_a_gap_between_legato_notes_is_flagged_and_a_join_is_not(self):
        gappy = [dict(t=i, d=0.5, p=60 + i, v=0.7, art='legato') for i in range(4)]
        joined = [dict(t=i, d=1.05, p=60 + i, v=0.7, art='legato') for i in range(4)]
        self.assertEqual(levels(score(track('v', 'violin', gappy)), 'orch.legato'), {'WARN'})
        self.assertEqual(levels(score(track('v', 'violin', joined)), 'orch.legato'), {'PASS'})

    def test_a_rest_between_phrases_is_not_a_slur(self):
        notes = [dict(t=0, d=1.0, p=60, v=0.7, art='legato'), dict(t=8, d=1.0, p=62, v=0.7, art='legato')]
        self.assertEqual(levels(score(track('v', 'violin', notes)), 'orch.legato'), {'PASS'})

    def test_notes_without_the_marking_are_not_judged(self):
        gappy = [dict(t=i, d=0.3, p=60 + i, v=0.7) for i in range(4)]
        self.assertEqual(rows(score(track('v', 'violin', gappy)), 'orch.legato'), [])


class Wiring(unittest.TestCase):
    def test_every_orch_row_is_a_profile_row_with_a_coverage_entry(self):
        import lint_coverage
        for rid in ('orch.range', 'orch.voice_leading', 'orch.playable', 'orch.legato'):
            self.assertIn(rid, gate_profiles.ROWS)
            self.assertIn(rid, lint_coverage.COVERAGE)

    def test_a_profile_can_skip_a_row_with_a_reason_and_it_does_not_run(self):
        sc = score(track('f', 'flute', line([20, 72])), gate={'orch.range': {'mode': 'skip', 'reason': 'a piece for a broken flute'}})
        self.assertEqual(rows(sc, 'orch.range'), [])

    def test_the_rows_reach_stage_two_through_acoustic_checks(self):
        sc = score(track('f', 'flute', line([20, 72])))
        names = {r[1] for r in pattern_audit.acoustic_checks(sc)}
        self.assertIn('orch.range', names)

    def test_a_score_with_no_orchestral_track_gets_no_orch_row(self):
        sc = score(track('s', 'synth_bass', line([36, 40]), role='bass'))
        self.assertEqual(rows(sc), [])

    def test_the_command_line_reports_and_exits_nonzero_on_a_fail(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 's.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(score(track('f', 'flute', line([20, 72]))), fh)
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'orch_rows.py'), path], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('[FAIL] orch.range', r.stdout)


if __name__ == '__main__':
    unittest.main()
