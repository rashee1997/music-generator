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

"""The quality gate adapts to the type of piece, and every adaptation is a gate preset (scripts/gate_profiles.py).
Run: python -m unittest tests.test_gate_profiles"""
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import gate_profiles as gpf  # noqa: E402
import mixer  # noqa: E402
import naturalness_check as nc  # noqa: E402
import pattern_audit  # noqa: E402
import presets  # noqa: E402
import quality_gate as qg  # noqa: E402

SR = 44100


def notes_loop(bars, period, bb=4):
    """`period` different bars repeated for `bars` bars (one 4-note bar each), velocities vary so only the loop is flagged."""
    out = []
    for b in range(bars):
        k = b % period
        for i in range(bb):
            out.append(dict(t=b * bb + i, d=0.9, p=48 + 3 * k + 2 * i, v=0.4 + 0.08 * ((i + k) % 4)))
    return out


def loop_score(**extra):
    s = dict(ts=[4, 4], bpm=100, dynamics=[[0, 0.5], [128, 0.5]],
             tracks=[dict(name='arp', role='arp', instrument='piano', notes=notes_loop(32, 4))])
    s.update(extra)
    return s


def kick_score(**extra):
    kicks = [dict(t=float(i), d=0.25, p='kick', v=0.8) for i in range(64)]
    s = dict(ts=[4, 4], bpm=124, dynamics=[[0, 0.3], [64, 0.9]], tracks=[dict(name='drums', role='drum', instrument='kit', notes=kicks)])
    s.update(extra)
    return s


def tone(db, secs=10, f=440.0):
    t = np.arange(SR * secs) / SR
    x = np.sin(2 * np.pi * f * t) * np.sqrt(2) * 10 ** (db / 20)
    return np.stack([x, x], 1).astype(np.float32)


class Base(unittest.TestCase):
    def setUp(self):
        self.roots = list(presets.PROJECT_ROOTS)
        presets.PROJECT_ROOTS.clear()
        self.saved = mixer.STATE.get('processed')
        mixer.STATE['processed'] = None
        self.tmp = []

    def tearDown(self):
        presets.PROJECT_ROOTS[:] = self.roots
        mixer.STATE['processed'] = self.saved
        for d in self.tmp:
            shutil.rmtree(d, ignore_errors=True)

    def project(self, **profiles):
        d = tempfile.mkdtemp()
        self.tmp.append(d)
        os.makedirs(os.path.join(d, 'presets', 'gate'))
        for name, body in profiles.items():
            json.dump(dict(body, name=name), open(os.path.join(d, 'presets', 'gate', name + '.json'), 'w'))
        presets.add_project(d)
        return d


class Shipped(Base):
    def test_shipped_profiles_are_valid(self):
        self.assertEqual(gpf.problems(), [])
        self.assertEqual(set(presets.load('gate')), {'melodic', 'tense', 'ambient', 'dance', 'cinematic', 'effects_only',
                                                     'video_cinematic'})

    def test_melodic_changes_nothing(self):
        p = gpf.resolve(loop_score())
        self.assertEqual((p.label, p.how), ('melodic', 'default'))
        self.assertEqual(p.param('pattern.flags_max', 'max'), 6)
        self.assertTrue(all(p.on(r) for r in gpf.ROWS))

    def test_every_relax_and_skip_has_a_reason(self):
        for name, prof in presets.load('gate').items():
            for rid, cfg in (prof.get('rows') or {}).items():
                if cfg.get('mode') in ('relax', 'skip'):
                    self.assertTrue(cfg.get('reason'), f'{name}/{rid}')


class Picking(Base):
    def test_keywords_still_infer_the_old_flags(self):
        for text, flag in (('dark', 'is_tense'), ('calm', 'is_ambient'), ('techno', 'is_dance')):
            self.assertTrue(pattern_audit.get_intent_profile(dict(emotion=text, tracks=[]))[flag], text)
        self.assertFalse(any(pattern_audit.get_intent_profile(dict(emotion='joyful', tracks=[])).values()))

    def test_free_pulse_and_drone_ratio_infer_ambient(self):
        self.assertIn('ambient', gpf.resolve(dict(pulse='free', tracks=[])).flags)
        drones = [dict(name=f'd{i}', role='drone', notes=[dict(t=0, d=4, p=40, v=.5)]) for i in range(3)]
        self.assertIn('ambient', gpf.resolve(dict(tracks=drones)).flags)

    def test_inferred_says_why(self):
        p = gpf.resolve(dict(emotion='dark suspense', tracks=[]))
        self.assertEqual((p.label, p.how), ('tense', 'inferred'))
        self.assertIn('dark', p.why)
        self.assertIn('inferred', p.notes()[0][2])

    def test_declared_beats_keywords(self):
        p = gpf.resolve(dict(emotion='dark', piece_type='melodic', tracks=[]))
        self.assertEqual((p.label, p.how, p.flags), ('melodic', 'declared', set()))

    def test_a_list_merges_in_order(self):
        p = gpf.resolve(dict(piece_type=['tense', 'dance'], tracks=[]))
        self.assertEqual(p.flags, {'tense', 'dance'})
        self.assertEqual(p.mode('pattern.four_on_floor'), 'skip')
        self.assertEqual(p.param('roughness', 'scale'), 1.6)

    def test_unknown_type_is_a_fail_row_with_the_list(self):
        p = gpf.resolve(dict(piece_type='polka', tracks=[]))
        fails = [r for r in p.notes() if r[0] == 'FAIL']
        self.assertEqual(len(fails), 1)
        self.assertIn('tense', fails[0][2])


class FalseFlags(Base):
    """The same score is flagged as melodic and not flagged once its type is declared."""

    def flags(self, score):
        return pattern_audit.audit(score)[1]

    def test_four_bar_loop_flagged_melodic_not_tense_or_ambient(self):
        self.assertTrue(any('loops every' in f for f in self.flags(loop_score())))
        for t in ('tense', 'ambient', 'dance', 'effects_only'):
            self.assertFalse(any('loops every' in f for f in self.flags(loop_score(piece_type=t))), t)

    def test_a_one_bar_loop_is_still_flagged_in_tense(self):
        s = loop_score(piece_type='tense')
        s['tracks'][0]['notes'] = notes_loop(32, 1)
        self.assertTrue(any('loops every' in f for f in self.flags(s)))

    def test_flat_dynamics_relaxed_only_where_declared(self):
        narrow = [[0, 0.5], [128, 0.58]]        # a steady drive: 0.08 of range on a mean of 0.54
        for t, flagged in ((None, True), ('tense', True), ('dance', False), ('ambient', False)):
            s = loop_score(dynamics=narrow)
            if t:
                s['piece_type'] = t
            self.assertEqual(any('dynamics:' in f for f in self.flags(s)), flagged, t)
        # relaxed is not switched off: a curve that does not move at all is still flagged in dance
        self.assertTrue(any('dynamics:' in f for f in self.flags(loop_score(piece_type='dance'))))

    def test_four_on_the_floor_flagged_unless_dance(self):
        self.assertTrue(any('four-on-the-floor' in f for f in self.flags(kick_score())))
        self.assertFalse(any('four-on-the-floor' in f for f in self.flags(kick_score(piece_type='dance'))))

    def test_flag_limit_follows_the_profile_but_an_explicit_score_key_wins(self):
        self.assertEqual(gpf.resolve(loop_score(piece_type='tense')).param('pattern.flags_max', 'max'), 8)
        rows = []
        qg.score_checks(loop_score(piece_type='tense', pattern_flags_max=1), rows)
        self.assertTrue(any(r[0] == 'FAIL' and r[1] == 'pattern' for r in rows))

    def test_relaxed_and_skipped_rows_are_listed_with_reasons(self):
        rows = []
        qg.score_checks(loop_score(piece_type='dance'), rows)
        text = ' | '.join(f'{r[1]}:{r[2]}' for r in rows)
        self.assertIn('piece_type:dance (declared)', text)
        self.assertIn('SKIP pattern.four_on_floor: a kick on every beat is the genre', text)
        self.assertIn('pattern.loop_short: max_period_bars=2', text)

    def test_feel_rows_skipped_for_effects_only_and_listed(self):
        s = dict(ts=[4, 4], piece_type='effects_only', tracks=[])
        self.assertEqual(pattern_audit.cognitive_feel_checks(s), [])
        rows = []
        qg.score_checks(dict(s, bpm=100), rows)
        self.assertTrue(any('SKIP feel.contour' in r[2] for r in rows))


class EveryRowCanBeAdapted(Base):
    """A row the report prints but no profile owns can never be relaxed or skipped by any type of music."""

    def test_rows_the_report_prints_have_a_profile_row(self):
        for rid in ('ambient_bed', 'modulation_flutter', 'note_collision', 'chord_voicing_and_strum',
                    'choked_resonance', 'machine_gun_percussion', 'percussion_flam', 'low_interval_mud'):
            self.assertIn(rid, gpf.ROWS, rid)

    def test_report_ids_map_to_their_profile_row(self):
        for reported, owned in (('cochlear_roughness', 'roughness'), ('kick_grid', 'kick.grid'),
                                ('harmonic_concordance', 'chroma.concordance'), ('spiral_tension_arc', 'feel.spiral')):
            self.assertEqual(gpf.canonical(reported), owned)
        p = gpf.resolve(dict(piece_type='tense', tracks=[]))
        self.assertEqual(p.param('cochlear_roughness', 'scale'), p.param('roughness', 'scale'))   # either id works
        self.assertIn('reported as cochlear_roughness', ' | '.join(d for _, _, d in p.notes()))

    def test_a_bed_or_flutter_row_cannot_be_switched_off(self):
        for rid in ('ambient_bed', 'modulation_flutter', 'roughness'):
            self.assertTrue(gpf.row_problems({rid: {'mode': 'skip', 'reason': 'x'}}, 'w'), rid)

    def test_the_ranges_stay_narrow_enough_to_hurt(self):
        self.assertLessEqual(gpf.ROWS['ambient_bed']['params']['pump_db'][2], 6.0)
        self.assertLessEqual(gpf.ROWS['modulation_flutter']['params']['warn'][2], 0.30)

    def test_ambient_bed_takes_its_limit_from_the_profile(self):
        import inspect
        src = inspect.getsource(qg.ambient_fusion_rows)
        self.assertIn("gp.param('ambient_bed', 'pump_db')", src)


class RoughnessIsDensityInvariant(unittest.TestCase):
    """The row must measure a clash, not the number of parts: the old sum over pairs failed 6 of 6 real masters."""

    def tone(self, f, nh=10, a=0.3, secs=4):
        t = np.arange(SR * secs) / SR
        return sum(a / k ** 1.1 * np.sin(2 * np.pi * f * k * t) for k in range(1, nh + 1))

    def counts(self, x):
        rows, _ = nc.cochlear_roughness_check(np.stack([x, x], 1).astype(np.float32), sr=SR)
        return [r[0] for r in rows]

    def test_consonant_voicings_pass_at_any_part_count(self):
        for freqs in ((261.6, 329.6, 392.0), (146.8, 185.0, 220.0, 293.7),
                      (73.4, 110, 146.8, 185, 220, 293.7, 370, 440)):
            x = sum(self.tone(f) for f in freqs)
            self.assertNotIn('FAIL', self.counts(x), freqs)

    def test_a_semitone_cluster_still_fails(self):
        self.assertIn('FAIL', self.counts(self.tone(262.0) + self.tone(277.0)))

    def test_a_clean_triad_is_not_made_rougher_by_more_parts(self):
        three = sum(self.tone(f) for f in (261.6, 329.6, 392.0))
        eight = sum(self.tone(f) for f in (73.4, 110, 146.8, 185, 220, 293.7, 370, 440))
        _, a = nc.cochlear_roughness_check(np.stack([three / np.abs(three).max(), three / np.abs(three).max()], 1), sr=SR)
        _, b = nc.cochlear_roughness_check(np.stack([eight / np.abs(eight).max(), eight / np.abs(eight).max()], 1), sr=SR)
        self.assertLess(b['mean_roughness'], 2.0 * a['mean_roughness'])


class RealDefectsStillFail(Base):
    def test_balance_layer_outlier_fails_and_even_layers_pass(self):
        score = dict(piece_type='effects_only', tracks=[dict(name=n, role='fx') for n in 'abc'])
        mixer.STATE['processed'] = {'a': tone(-30), 'b': tone(-31, f=900), 'c': tone(-6, f=2000)}
        self.assertEqual([r[0] for r in qg.balance_rows(score)], ['FAIL'])
        mixer.STATE['processed'] = {'a': tone(-30), 'b': tone(-31, f=900), 'c': tone(-33, f=2000)}
        self.assertEqual([r[0] for r in qg.balance_rows(score)], ['PASS'])

    def test_no_lead_melodic_stays_silent_as_before(self):
        mixer.STATE['processed'] = {'a': tone(-30), 'b': tone(-6, f=900)}
        score = dict(tracks=[dict(name='a', role='fx'), dict(name='b', role='fx')])
        self.assertEqual(qg.balance_rows(score), [])

    def test_lead_pieces_keep_the_lead_rule_in_every_profile(self):
        mixer.STATE['processed'] = {'lead': tone(-40), 'bass': tone(-27, f=60.0)}
        for t in ('melodic', 'tense', 'ambient', 'dance', 'cinematic'):
            score = dict(piece_type=t, tracks=[dict(name='lead', role='melody'), dict(name='bass', role='bass')])
            self.assertEqual([r[0] for r in qg.balance_rows(score)], ['FAIL'], t)

    def test_protected_rows_cannot_be_touched(self):
        for cfg in ({'mode': 'skip', 'reason': 'x'}, {'mode': 'relax', 'reason': 'x'}):
            for rid in ('loudness', 'true_peak', 'clipping', 'silence', 'clicks', 'channels'):
                self.assertTrue(gpf.row_problems({rid: cfg}, 'w'), rid)
        self.assertEqual(gpf.row_problems({'loudness': {'mode': 'apply'}}, 'w'), [])

    def test_kick_and_masking_and_chroma_skip_only_where_the_profile_says(self):
        self.assertEqual(qg.kick_grid_rows(dict(piece_type='ambient', tracks=[dict(name='d', role='drum')]), {'d': tone(-20)}), [])
        self.assertEqual(qg.chroma_concordance_rows(dict(piece_type='effects_only', tracks=[dict(name='e', role='environment')]),
                                                    None, {'e': tone(-20)}), [])
        self.assertEqual(qg.masking_rows({'m': tone(-20)}, dict(piece_type='effects_only', tracks=[dict(name='m', role='melody')])), [])


class ProjectProfiles(Base):
    def test_project_profile_extends_and_is_picked_up(self):
        self.project(horror={'character': 'horror cue: sparse, dissonant, unresolved', 'extends': 'tense', 'flags': ['tense'],
                             'detect': {'keywords': ['creepy']},
                             'rows': {'pattern.flags_max': {'mode': 'relax', 'max': 10, 'reason': 'very sparse'}}})
        self.assertEqual(gpf.problems(), [])
        p = gpf.resolve(dict(piece_type='horror', tracks=[]))
        self.assertEqual(p.param('pattern.flags_max', 'max'), 10)
        self.assertEqual(p.param('roughness', 'scale'), 1.6)             # inherited from tense
        self.assertEqual(gpf.resolve(dict(emotion='creepy', tracks=[])).label, 'horror')

    def test_a_project_may_not_shadow_a_shipped_profile(self):
        """Shadowing `tense` would retune every tense cue in the project at once: the quiet way to switch the gate off."""
        self.project(tense={'rows': {'pattern.flags_max': {'mode': 'relax', 'max': 9, 'reason': 'this project writes sparse cues'}}})
        self.assertIn('may not redefine', '\n'.join(gpf.problems()))

    def test_a_project_profile_extends_instead(self):
        self.project(sparse_cues={'character': 'sparse cues', 'extends': 'tense',
                                  'rows': {'pattern.flags_max': {'mode': 'relax', 'max': 9, 'reason': 'this project writes sparse cues'}}})
        self.assertEqual(gpf.problems(), [])
        self.assertEqual(gpf.resolve(dict(piece_type='sparse_cues', tracks=[])).param('pattern.flags_max', 'max'), 9)

    def test_bad_profiles_are_rejected_with_the_reason(self):
        cases = {
            'no_reason': {'character': 'c', 'rows': {'pattern.loop_short': {'mode': 'relax', 'max_period_bars': 2}}},
            'protected': {'character': 'c', 'rows': {'loudness': {'mode': 'skip', 'reason': 'loud is fine'}}},
            'unknown_row': {'character': 'c', 'rows': {'pattern.nope': {'mode': 'skip', 'reason': 'x'}}},
            'unknown_param': {'character': 'c', 'rows': {'pattern.flags_max': {'mode': 'relax', 'huge': 1, 'reason': 'x'}}},
            'off_switch': {'character': 'c', 'rows': {'pattern.flags_max': {'mode': 'relax', 'max': 500, 'reason': 'x'}}},
            'no_skip': {'character': 'c', 'rows': {'roughness': {'mode': 'skip', 'reason': 'x'}}},
            'no_character': {'rows': {}},
            'bad_extends': {'character': 'c', 'extends': 'missing'},
            'bad_flag': {'character': 'c', 'flags': ['jazzy']},
            'bad_trait': {'character': 'c', 'detect': {'traits': {'cool': 1}}},
        }
        self.project(**cases)
        probs = '\n'.join(gpf.problems())
        for key, needle in (('no_reason', 'no "reason"'), ('protected', 'protected row'), ('unknown_row', 'unknown row'),
                            ('unknown_param', 'no parameter "huge"'), ('off_switch', 'outside'), ('no_skip', 'cannot be skipped'),
                            ('no_character', 'missing "character"'), ('bad_extends', 'does not exist'),
                            ('bad_flag', 'not one of'), ('bad_trait', 'unknown trait')):
            self.assertIn(needle, probs, key)

    def test_extends_loop_is_caught(self):
        self.project(a={'character': 'c', 'extends': 'b'}, b={'character': 'c', 'extends': 'a'})
        self.assertIn('loops', '\n'.join(gpf.problems()))

    def test_score_override_needs_a_reason_and_is_applied(self):
        bad = gpf.resolve(dict(tracks=[], gate={'pattern.flags_max': {'mode': 'relax', 'max': 9}}))
        self.assertTrue(bad.errors)
        ok = gpf.resolve(dict(tracks=[], gate={'pattern.flags_max': {'mode': 'relax', 'max': 9, 'reason': 'single-take improvisation'}}))
        self.assertEqual((ok.errors, ok.param('pattern.flags_max', 'max')), ([], 9))

    def test_score_override_cannot_reach_a_protected_row(self):
        p = gpf.resolve(dict(tracks=[], gate={'loudness': {'mode': 'skip', 'reason': 'x'}}))
        self.assertTrue(p.errors)
        self.assertEqual(p.mode('loudness'), 'apply')

    def test_scaffold_from_a_shipped_profile_inherits_and_validates(self):
        d = tempfile.mkdtemp()
        self.tmp.append(d)
        path = presets.scaffold('gate', 'horror', d, 'tense')
        body = json.load(open(path))
        self.assertEqual((body['extends'], body['rows']), ('tense', {}))
        presets.add_project(d)
        body['character'] = 'a horror cue'
        json.dump(body, open(path, 'w'))
        self.assertEqual(gpf.problems(), [])

    def test_plain_scaffold_template_is_valid_once_its_character_is_written(self):
        d = tempfile.mkdtemp()
        self.tmp.append(d)
        path = presets.scaffold('gate', 'mine', d)
        body = json.load(open(path))
        body['character'] = 'my music'
        json.dump(body, open(path, 'w'))
        presets.add_project(d)
        self.assertEqual(gpf.problems(), [])


class ClimaxSeparationAndHarshness(Base):
    """`spatial.z_separation` and `spectral.equal_loudness`: profile rows, and each fires on a real defect and not on a fix."""

    def pair(self, az_a=0.0, el_a=0.0, az_b=0.0, el_b=0.0):
        score = dict(piece_type='melodic', tracks=[
            dict(name='strings', role='chord', spatial={'azimuth': az_a, 'elevation': el_a, 'binaural': True}),
            dict(name='brass', role='counter', spatial={'azimuth': az_b, 'elevation': el_b, 'binaural': True})])
        return score, {'strings': tone(-18, f=1200), 'brass': tone(-18, f=1800)}

    def test_both_rows_are_adaptable_profile_rows(self):
        for rid in ('spatial.z_separation', 'spectral.equal_loudness'):
            self.assertIn(rid, gpf.ROWS, rid)
            self.assertEqual(gpf.row_problems({rid: {'mode': 'relax', 'reason': 'a measured exception'}}, 'w'), [], rid)

    def test_colocated_midrange_pair_fails_and_separation_clears_it(self):
        rows = []
        qg.spatial_separation_rows(*self.pair(), out=rows)
        self.assertEqual([r[0] for r in rows], ['FAIL'], rows)
        for kw in ({'az_b': 40.0}, {'el_b': 30.0}):
            rows = []
            qg.spatial_separation_rows(*self.pair(**kw), out=rows)
            self.assertEqual([r[0] for r in rows], ['PASS'], (kw, rows))

    def test_a_staged_height_without_a_binaural_route_is_not_credited(self):
        score, stems = self.pair(el_b=30.0)
        for t in score['tracks']:
            t['spatial']['binaural'] = False
        rows = []
        qg.spatial_separation_rows(score, stems, out=rows)
        self.assertEqual(rows[0][0], 'FAIL')
        self.assertIn('no binaural route', rows[0][2])

    def test_equal_loudness_flags_a_3k5_spike_and_passes_a_dark_stem(self):
        score = dict(piece_type='melodic', tracks=[dict(name='lead', role='melody')])
        rows = []
        qg.equal_loudness_rows(score, {'lead': tone(-12, f=3500)}, out=rows)
        self.assertIn(rows[0][0], ('WARN', 'FAIL'), rows)
        self.assertIn('inst_eq', rows[0][2])
        rows = []
        qg.equal_loudness_rows(score, {'lead': tone(-12, f=300)}, out=rows)
        self.assertEqual([r[0] for r in rows], ['PASS'], rows)


class ProjectGate(Base):
    def test_project_gate_reports_profile_errors_and_unknown_type(self):
        import project_gate
        d = self.project(bad={'rows': {}})
        self.assertTrue(any('gate/bad' in p for p in project_gate.gate_problems(dict(tracks=[]), d)))
        self.assertTrue(any('polka' in p for p in project_gate.gate_problems(dict(tracks=[], piece_type='polka'), d)))

    def test_undeclared_type_is_a_warning_not_an_error(self):
        import project_gate
        from pathlib import Path
        d = self.project()
        warn = project_gate.warnings(Path(d), dict(emotion='dark', tracks=[]))
        self.assertTrue(any('no "piece_type"' in w and 'tense' in w for w in warn))
        self.assertFalse(any('no "piece_type"' in w for w in project_gate.warnings(Path(d), dict(piece_type='tense', tracks=[]))))


if __name__ == '__main__':
    unittest.main()
