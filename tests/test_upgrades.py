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

"""Tests for the cultural-idiom, dynamic-epic, contour and mixing upgrades.
Run from the skill folder:  python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import compose                       # noqa: E402
import humanize as hz                # noqa: E402
import mixer                         # noqa: E402
import theory                        # noqa: E402
from theory import Key               # noqa: E402


class EpicIsDynamic(unittest.TestCase):
    def test_default_epic_has_anchor_bass_lead_pad_and_drums(self):
        s = compose.compose({'emotion': 'epic', 'duration_s': 30, 'seed': 3})
        names = {t['instrument'] for t in s['tracks']}
        self.assertIn('piano', names)                           # the anchor
        self.assertTrue({'contrabass', 'violin', 'choir_aahs'} & names)
        roles = {t['role'] for t in s['tracks']}
        self.assertTrue({'chord', 'bass', 'melody', 'pad', 'drum'} <= roles)

    def test_brief_instruments_replace_the_default_mix(self):
        s = compose.compose({'emotion': 'epic', 'duration_s': 30, 'seed': 3,
                             'instruments': ['sitar', 'tanpura', 'cello', 'shehnai']})
        names = [t['instrument'] for t in s['tracks']]
        self.assertIn('sitar', names)
        self.assertIn('cello', names)
        self.assertNotIn('french_horn', names)
        self.assertNotIn('piano', names)                         # the brief named no piano

    def test_culture_epic_keeps_western_orchestra_out(self):
        s = compose.compose({'emotion': 'epic', 'genre': 'bhangra', 'duration_s': 30, 'seed': 3})
        names = {t['instrument'] for t in s['tracks']}
        for banned in ('french_horn', 'horn', 'trumpet', 'fast_strings', 'timpani', 'orchestral'):
            self.assertNotIn(banned, names)

    def test_culture_epic_allows_orchestra_when_asked(self):
        s = compose.compose({'emotion': 'epic', 'genre': 'bhangra', 'duration_s': 30, 'seed': 3,
                             'instruments': ['french_horn', 'tabla_ge'], 'scene': 'orchestral hero'})
        self.assertIn('french_horn', [t['instrument'] for t in s['tracks']])


class CultureIdioms(unittest.TestCase):
    def test_indo_afro_table_has_no_charukeshi_or_hijaz(self):
        for scale in theory.CULTURE_SCALES['indo_afro']:
            self.assertNotIn(scale, ('raga_charukeshi', 'maqam_hijaz'))

    def test_kora_thumb_and_index_registers(self):
        notes = theory.kora_bar(2, 4, {2, 4, 6, 7, 9, 11, 0})
        thumb = [n['p'] for n in notes if n['p'] < 62]
        index = [n['p'] for n in notes if n['p'] >= 62]
        self.assertTrue(thumb and all(48 <= p <= 60 for p in thumb))
        self.assertTrue(index and all(64 <= p <= 79 for p in index))

    def test_gankogui_standard_pattern_has_seven_strokes(self):
        self.assertEqual(len(theory.bell_bar(6.0)), 7)

    def test_sitar_phrase_passes_through_gamaka_and_meend(self):
        notes = [dict(t=0, d=0.25, p=62, v=.8), dict(t=0.25, d=0.25, p=64, v=.8), dict(t=0.5, d=1.5, p=66, v=.8)]
        out = theory.idiom_notes('sitar', notes, tonic_pc=2)
        self.assertTrue(any('gl' in n for n in out))
        self.assertTrue(any(n.get('gs') == 0.22 for n in out if 'gl' in n))
        self.assertEqual(theory.idiom_notes('piano', notes, tonic_pc=2), notes)   # other instruments untouched

    def test_pickup_fill_lands_before_the_downbeat(self):
        fill = theory.pickup_fill('tabla', at_beat=16.0, beats=1.0)
        self.assertTrue(all(12.9 <= n['t'] < 16.0 for n in fill))


class ContourAndGrace(unittest.TestCase):
    def test_sixteenth_run_has_contoured_velocities(self):
        tm = hz.TempoMap(100, total_beats=8)
        run = [dict(t=i * 0.25, d=0.22, p=60 + (i % 8), v=0.7) for i in range(16)]
        ev = hz.humanize_track(run, tm, 'natural', role='melody', seed=1)
        vels = np.array([e['v'] for e in ev])
        self.assertGreater(vels.std(), 4.0)

    def test_grace_note_is_softer_and_early(self):
        tm = hz.TempoMap(100, total_beats=4)
        ev = hz.humanize_track([dict(t=1.0, d=0.08, p=62, v=0.8), dict(t=1.0, d=1.0, p=50, v=0.8)], tm, 'tight',
                               role='melody', seed=2)
        grace = [e for e in ev if e['p'] == 62][0]
        main = [e for e in ev if e['p'] == 50][0]
        self.assertLess(grace['v'], main['v'])


class MixerRules(unittest.TestCase):
    def test_instrument_eq_tables(self):
        self.assertEqual(len(mixer.inst_eq('piano')), 3)
        self.assertTrue(mixer.inst_eq('sitar'))
        self.assertTrue(mixer.inst_eq('cello'))
        self.assertEqual(mixer.inst_eq('synth_pad'), [])

    def test_role_board_applies_instrument_eq(self):
        self.assertGreater(len(mixer.role_board('bass', 'cello')), len(mixer.role_board('bass', 'synth_bass')))

    def test_eq_chain_does_not_clip(self):
        rng = np.random.default_rng(0)
        x = (rng.standard_normal((44100, 2)) * 0.3).astype(np.float32)
        for role, inst in (('bass', 'cello'), ('melody', 'sitar'), ('chord', 'piano'), ('melody', 'bansuri')):
            y = mixer.process_stem('t', x, mixer.default_spec(dict(role=role, instrument=inst)))
            self.assertTrue(np.isfinite(y).all())
            self.assertLess(float(np.abs(y).max()), 1.0, f'{role}/{inst} clips')

    def test_active_gain_ignores_silence(self):
        sr = 44100
        tone = np.zeros((sr * 4, 2), np.float32)
        tone[: sr] = 0.2 * np.sin(np.linspace(0, 300, sr))[:, None]     # one second of sound, three of silence
        self.assertGreater(mixer.active_lufs(tone, sr), mixer.lufs(tone, sr))


class ArabicIqaat(unittest.TestCase):
    def test_maqsum_has_dum_tek_and_ghost(self):
        rng = np.random.default_rng(0)
        notes = theory.iqaat_bar('maqsum', 4, 0.8, rng)
        dums = sorted(n['t'] for n in notes if n['p'] == 'dum')
        self.assertEqual(dums, [0.0, 2.0])
        self.assertTrue(any(abs(n['t'] - 3.75) < 1e-6 for n in notes))     # the 3.75 ghost

    def test_malfuf_is_three_plus_three_plus_two(self):
        notes = theory.iqaat_bar('malfuf', 4, 0.8, np.random.default_rng(0))
        self.assertEqual(sorted(round(n['t'], 2) for n in notes), [0.0, 0.75, 1.5])

    def test_no_latin_skank_in_iqaat(self):
        for name in theory.ARABIC_IQAAT:
            names = {n['p'] for n in theory.iqaat_bar(name, 4, 0.8, np.random.default_rng(0))}
            self.assertFalse(names & {'conga_open', 'conga_mute', 'bongo_high', 'guiro', 'cowbell'})
        with self.assertRaises(ValueError):
            theory.iqaat_bar('cumbia', 4, 0.8, np.random.default_rng(0))


if __name__ == '__main__':
    unittest.main()
