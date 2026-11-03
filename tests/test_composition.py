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
"""Tests for the composition plan, the role-aware humanizer, and the stability fixes.

    .venv/Scripts/python.exe -m unittest discover -s tests -v      (Windows; use .venv/bin/python elsewhere)

Deterministic fixtures only: no audio is rendered except in the widening test, which runs two processes with
different hash seeds and compares the output.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import plan as planmod          # noqa: E402
import compose                  # noqa: E402
import humanize as hz           # noqa: E402
import render_natural as rn     # noqa: E402

TRAILER_HITS = [{'t': 24, 'type': 'impact'}, {'t': 38, 'type': 'silence'}]
TRAILER_BRIEF = {'emotion': 'triumphant', 'genre': 'orchestral', 'duration_s': 45, 'bpm': 104, 'mode': 'major',
                 'arc': 'build', 'intensity': 0.8, 'hit_points': TRAILER_HITS, 'seed': 2}
FLAT_CFG = dict(timing_ms=0, drum_ms=0, lead_ms=0, drift_ms=0, vel_sigma=0, rubato=0, wander=0, strum_ms=0,
                ritard=0, accent=0)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = planmod.build_plan(20, bb=4, bpm=104, hits=TRAILER_HITS)

    def test_impact_starts_climax_and_silence_makes_hush_then_reveal(self):
        by = {s['name']: s for s in self.plan['sections']}
        self.assertEqual(by['climax']['start_bar'], 10)          # 24 s at 104 bpm = bar 10
        self.assertEqual(by['hush']['start_bar'], 16)            # 38 s = bar 16.4 -> 16
        self.assertEqual(by['reveal']['start_bar'], 17)
        self.assertEqual(by['hush']['dens'], 0.0)
        self.assertFalse(by['hush']['lead'])

    def test_sections_cover_every_bar_once(self):
        covered = [b for s in self.plan['sections'] for b in range(s['start_bar'], s['end_bar'])]
        self.assertEqual(covered, list(range(20)))

    def test_climax_is_loudest_and_densest_and_lead_goes_up(self):
        c = next(s for s in self.plan['sections'] if s['name'] == 'climax')
        self.assertEqual(c['dyn'], max(s['dyn'] for s in self.plan['sections']))
        self.assertEqual(c['dens'], max(s['dens'] for s in self.plan['sections']))
        self.assertEqual(c['reg'], 12)

    def test_trailer_plan_has_no_failure(self):
        self.assertFalse([m for lvl, m in planmod.check_plan(self.plan) if lvl == 'FAIL'])

    def test_no_hits_uses_template_and_still_validates(self):
        p = planmod.build_plan(24, bb=4, bpm=100, hits=[])
        names = [s['name'] for s in p['sections']]
        self.assertEqual(names[0], 'open')
        self.assertIn('climax', names)
        self.assertFalse([m for lvl, m in planmod.check_plan(p) if lvl == 'FAIL'])

    def test_lockstep_curves_are_reported(self):
        p = planmod.build_plan(24, bb=4, bpm=100, hits=[])
        for s in p['sections']:                         # force loudness and density to rise together
            s['dens'] = s['dyn']
        msgs = [m for lvl, m in planmod.check_plan(p)]
        self.assertTrue(any('lockstep' in m for m in msgs))

    def test_per_bar_arrays_match_sections(self):
        dyn, dens, lead, reg = planmod.per_bar(self.plan)
        self.assertEqual(len(dyn), 20)
        self.assertEqual(dens[16], 0.0)
        self.assertTrue(lead[12] and not lead[16])
        self.assertEqual(reg[12], 12)


class ComposeTests(unittest.TestCase):
    def test_compose_without_plan_is_deterministic_and_has_no_plan(self):
        a = compose.compose(dict(TRAILER_BRIEF))
        b = compose.compose(dict(TRAILER_BRIEF))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotIn('plan', a)

    def test_compose_with_plan_gates_lead_and_sets_fade(self):
        s = compose.compose(dict(TRAILER_BRIEF, plan=True, seed=3))
        self.assertIn('plan', s)
        self.assertGreater(s['master']['fade_out'], 0)
        lead = next(t for t in s['tracks'] if t['name'] == 'lead')
        silent = [n for n in lead['notes'] if 16 * 4 <= n['t'] < 17 * 4]   # the plan's hush bar
        self.assertEqual(silent, [])
        climax = [n['p'] for n in lead['notes'] if 10 * 4 <= n['t'] < 16 * 4]
        before = [n['p'] for n in lead['notes'] if 4 * 4 <= n['t'] < 8 * 4]
        self.assertGreater(np.mean(climax), np.mean(before) + 6)           # lifted register in the climax


class HumanizeTests(unittest.TestCase):
    def _track(self, role, pitches, n_phrase=8):
        notes = [dict(t=float(i), d=0.9, p=p, v=0.6) for i, p in enumerate(pitches[:n_phrase])]
        return notes

    def test_melody_swells_to_middle_but_pad_is_flat_when_pitch_is_constant(self):
        tm = hz.TempoMap(100, total_beats=20)
        mel = hz.humanize_track(self._track('melody', [60 + (i % 2) for i in range(8)]), tm, cfg=FLAT_CFG,
                                role='melody', seed=1)
        v = np.array([e['v'] for e in mel])
        self.assertGreater(v[3:5].mean(), v[[0, -1]].mean())               # arch: middle louder than the ends
        pad = hz.humanize_track(self._track('pad', [60] * 8), tm, cfg=FLAT_CFG, role='pad', seed=1)
        self.assertEqual(len({e['v'] for e in pad}), 1)                    # no arch on a bed

    def test_lead_leads_only_when_accompanied(self):
        tm = hz.TempoMap(100, total_beats=20)
        solo = [dict(t=float(i), d=0.9, p=64, v=0.6, acc=0.0) for i in range(4)]
        acc = [dict(n, acc=1.0) for n in solo]
        lead_cfg = dict(FLAT_CFG, lead_ms=20)
        t_solo = [e['t'] for e in hz.humanize_track(solo, tm, cfg=lead_cfg, role='melody', seed=1)]
        t_acc = [e['t'] for e in hz.humanize_track(acc, tm, cfg=lead_cfg, role='melody', seed=1)]
        self.assertTrue(all(abs(a - tm.sec(i)) < 1e-9 for a, i in zip(t_solo, range(4))))
        self.assertTrue(all(a <= tm.sec(i) for a, i in zip(t_acc, range(4))))      # beat 0 cannot go before 0
        self.assertTrue(all(a < tm.sec(i) for a, i in zip(t_acc[1:], range(1, 4))))

    def test_fast_run_is_shaped_in_groups_of_four(self):
        # eight 16ths at one flat velocity (the taan case): group starts stronger, the run swells and lets go
        tm = hz.TempoMap(100, total_beats=20)
        run = [dict(t=i * 0.25, d=0.25, p=62 + i, v=0.8) for i in range(8)]
        ev = hz.humanize_track(run, tm, cfg=FLAT_CFG, role='melody', seed=1)
        v = [e['v'] for e in sorted(ev, key=lambda e: e['beat'])]
        self.assertGreater(v[0], v[1])                 # group start over the next note
        self.assertGreater(v[4], v[5])                 # the second group starts stronger too
        self.assertGreater(v[3], v[0])                 # swells toward the middle of the run
        self.assertGreater(len(set(v)), 3)             # no longer one flat level

    def test_mark_accompanied_flags_notes_under_a_sounding_track(self):
        mel = dict(name='lead', role='melody', notes=[dict(t=0, d=1, p=60), dict(t=4, d=1, p=62)])
        pad = dict(name='pad', role='pad', notes=[dict(t=0, d=2, p=48)])
        out = rn._mark_accompanied(mel, [mel, pad])
        self.assertEqual([n['acc'] for n in out['notes']], [1.0, 0.0])


class AcousticAndMoodTests(unittest.TestCase):
    """The rules that stop a score sounding like a MIDI file, and the reading of the brief's mood words."""

    def test_acoustic_rules_flag_a_midi_style_score(self):
        import pattern_audit
        bad = dict(ts=[4, 4], room='hall', tracks=[
            dict(name='keys', instrument='piano', role='chord',
                 notes=[dict(t=b, d=1.0, p=p, v=0.6) for b in range(4) for p in (60, 64, 67)]),
            dict(name='gtr', instrument='acoustic_guitar', role='chord',
                 notes=[dict(t=i, d=0.2, p=52 + i % 5, v=0.6, art='staccato') for i in range(10)]),
            dict(name='drums', instrument='drums', role='drum',
                 notes=[dict(t=i * 0.5, d=0.5, p=p, v=0.5) for i in range(8) for p in ('snare', 'clap')]),
            dict(name='pad', instrument='strings', role='pad',
                 notes=[dict(t=b, d=2.0, p=p, v=0.5) for b in range(4) for p in (45, 48, 52)]),
        ])
        flags = {n for level, n, _ in pattern_audit.acoustic_checks(bad) if level == 'FAIL'}
        for want in ('chord_voicing_and_strum', 'choked_resonance', 'machine_gun_percussion', 'percussion_flam',
                     'low_interval_mud'):
            self.assertIn(want, flags)

    def test_composed_scores_pass_the_acoustic_rules(self):
        import pattern_audit
        for brief in ({'emotion': 'motivational'}, {'emotion': 'slow reverb mix'}):
            s = compose.compose(dict(brief, duration_s=45, seed=7))
            left = [r for r in pattern_audit.acoustic_checks(s) if r[0] == 'FAIL']
            self.assertEqual(left, [], brief)

    def test_strum_is_low_to_high_and_staggered(self):
        import theory
        ev = theory.tex_strum([48, 52, 55, 60], 4, vel=0.6, rng=np.random.default_rng(0))
        down = [n for n in ev if abs(n['t'] - 0.0) < 0.1]
        self.assertEqual([n['p'] for n in down], [48, 52, 55, 60])
        self.assertTrue(all(b['t'] > a['t'] for a, b in zip(down, down[1:])))    # rolled, not one sample
        self.assertTrue(all(n['d'] >= 0.6 and n['art'] == 'legato' for n in ev))

    def test_fill_crescendos_exponentially_and_does_not_phase_lock(self):
        import theory
        bar = theory.drum_bar('pop', 4, 0.7, np.random.default_rng(1), fill=True)
        roll = [n for n in bar if n['t'] >= 3.0]
        v = [n['v'] for n in roll]
        self.assertGreater(v[-1] - v[0], 0.25)
        self.assertLess(v[3], (v[0] + v[-1]) / 2)               # convex: a curve, not a linear ramp
        same = [dict(t=0.0, d=0.1, p='snare', v=0.6), dict(t=0.0, d=0.1, p='clap', v=0.6)]
        theory._flam_layered(same)
        self.assertNotEqual(same[0]['t'], same[1]['t'])

    def test_mood_words_pick_the_mood_tempo_and_room(self):
        mot = compose.compose({'emotion': 'motivational', 'duration_s': 45, 'seed': 7})
        self.assertEqual(mot['meta']['emotion'], 'hopeful')
        self.assertTrue(76 <= mot['bpm'] <= 98, mot['bpm'])
        adv = compose.compose({'emotion': 'adventure', 'duration_s': 45, 'seed': 7})
        self.assertEqual(adv['meta']['emotion'], 'adventure')
        self.assertTrue(84 <= adv['bpm'] <= 104, adv['bpm'])
        slow = compose.compose({'emotion': 'slow reverb mix', 'duration_s': 45, 'seed': 7})
        self.assertEqual(slow['meta']['emotion'], 'dreamy')
        self.assertEqual(slow['room'], 'large_hall')
        self.assertEqual(slow['mix']['reverb_return'], 1.5)
        self.assertLess(slow['bpm'], 80)
        self.assertTrue(slow['meta']['mood_notes'])              # says what it read, instead of guessing silently

    def test_a_mood_still_wins_over_a_fast_genre(self):
        s = compose.compose({'emotion': 'motivational', 'genre': 'corporate', 'duration_s': 45, 'seed': 7})
        self.assertEqual(s['meta']['emotion'], 'hopeful')
        self.assertLess(s['bpm'], 112)                           # corporate's own 112-126 used to erase the mood
        self.assertTrue(any('do not overlap' in n for n in s['meta']['mood_notes']))

    def test_a_fusion_no_longer_forces_joyful(self):
        s = compose.compose({'fusion': ['indian', 'west_african'], 'emotion': 'calm', 'duration_s': 45, 'seed': 7})
        self.assertEqual(s['meta']['emotion'], 'calm')
        neutral = compose.compose({'fusion': ['indian', 'west_african'], 'duration_s': 45, 'seed': 7})
        self.assertNotEqual(neutral['meta']['emotion'], 'joyful')

    def test_a_mood_still_wins_over_a_fast_fusion(self):
        # indian+west_african plans ~110 bpm; 'calm' (56-74) does not overlap it, same tiebreak as mood-vs-genre
        s = compose.compose({'fusion': ['indian', 'west_african'], 'emotion': 'calm', 'duration_s': 30, 'seed': 7})
        self.assertLess(s['bpm'], 95)
        self.assertTrue(any('do not overlap' in n for n in s['meta']['mood_notes']))


class MixerStabilityTests(unittest.TestCase):
    def test_stereo_widening_is_the_same_under_different_hash_seeds(self):
        code = (
            "import sys; sys.path.insert(0, %r); import numpy as np, mixer\n"
            "rng = np.random.default_rng(0)\n"
            "x = rng.standard_normal((44100, 2)).astype(np.float32) * 0.1\n"
            "score = {'tracks': [{'name': 'pad', 'role': 'pad', 'notes': []}]}\n"
            "y = mixer.mix_stems(score, {'pad': x}, sr=44100)\n"
            "print(float(np.round(np.abs(y).sum(), 6)))\n") % SCRIPTS
        outs = []
        for seed in ('1', '2'):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr[-800:])
            outs.append(r.stdout.strip().splitlines()[-1])
        self.assertEqual(outs[0], outs[1])


if __name__ == '__main__':
    unittest.main()
