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

"""Declaring what a piece is: the vocabulary, the derivation, and the two rows that read them.
Run: python -m unittest tests.test_intent"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import compose  # noqa: E402
import intent  # noqa: E402
import quality_gate as qg  # noqa: E402


def kick(every=1.0, n=16, role='drum'):
    return dict(name='kit', role=role, instrument='kit',
                notes=[dict(t=i * every, d=0.25, p='kick', v=0.8) for i in range(n)])


def kit(n=16):
    """Snare and hats: a drum-kit groove, not a single boom."""
    notes = []
    for i in range(n):
        notes.append(dict(t=i, d=0.2, p='hat_closed', v=0.5))
        if i % 2:
            notes.append(dict(t=i, d=0.2, p='snare', v=0.7))
    return dict(name='kit', role='drum', instrument='kit', notes=notes)


def line(role='melody', n=8, p=60):
    return dict(name=role, role=role, instrument='piano',
                notes=[dict(t=i, d=0.9, p=p + i, v=0.5) for i in range(n)])


class Vocabulary(unittest.TestCase):
    def test_the_shipped_data_is_consistent(self):
        self.assertEqual(intent.problems(), [])

    def test_every_emotion_compose_can_play_has_a_concept(self):
        self.assertEqual(set(compose.EMOTIONS) - set(intent.vocabulary()['emotions']), set())

    def test_a_plain_sentence_resolves_to_concepts(self):
        self.assertEqual(intent.resolve('heartbroken'), [('emotions', 'grief')])
        self.assertEqual(intent.resolve('barely there'), [('emotions', 'dreamy')])
        self.assertEqual(intent.resolve('documentary'), [('registers', 'documentary')])

    def test_an_unknown_word_is_an_error_with_near_misses(self):
        with self.assertRaises(intent.IntentError) as ctx:
            intent.resolve('grif')
        self.assertIn('grief', str(ctx.exception))

    def test_a_word_may_mean_one_thing_per_kind_but_not_two(self):
        self.assertEqual(set(intent.resolve('funeral')), {('emotions', 'grief'), ('scenes', 'farewell')})

    def test_a_word_in_the_wrong_field_says_what_it_is(self):
        with self.assertRaises(intent.IntentError) as ctx:
            intent.normalise_block({'registers': ['grief']})
        self.assertIn('not a register', str(ctx.exception))

    def test_avoid_accepts_a_gesture_itself_or_a_word_that_forbids_one(self):
        self.assertEqual(intent.normalise_block({'avoid': ['drums']})['avoid'], ['drum_kit'])
        self.assertEqual(intent.normalise_block({'avoid': ['four_on_the_floor']})['avoid'], ['four_on_floor'])
        calm = intent.normalise_block({'emotions': ['calm']})['avoid']
        self.assertIn('four_on_floor', calm)
        self.assertNotIn('drum_kit', calm)      # a kit is not anti-calm; a driving groove is

    def test_every_gesture_with_a_measurement_is_listed_as_avoidable(self):
        self.assertEqual(set(intent.MEASURE) - set(intent.GESTURES), set())


class Detectors(unittest.TestCase):
    def hits(self, score, avoid):
        return intent.gesture_hits(score, avoid)

    def test_four_on_the_floor_fires_on_a_kick_on_every_beat(self):
        hits, unmeasured = self.hits(dict(bpm=120, ts=[4, 4], tracks=[kick()]), ['four_on_floor'])
        self.assertEqual([g for g, _ in hits], ['four_on_floor'])
        self.assertEqual(unmeasured, [])

    def test_four_on_the_floor_does_not_fire_on_a_backbeat(self):
        notes = [dict(t=i, d=0.25, p='kick' if i % 4 == 0 else 'snare', v=0.8) for i in range(16)]
        hits, _ = self.hits(dict(bpm=120, ts=[4, 4], tracks=[dict(name='kit', role='drum', notes=notes)]),
                            ['four_on_floor'])
        self.assertEqual(hits, [])

    def test_a_kit_groove_and_a_single_boom_are_different_gestures(self):
        hits, _ = self.hits(dict(bpm=120, ts=[4, 4], tracks=[kit()]), ['drum_kit'])
        self.assertEqual([g for g, _ in hits], ['drum_kit'])
        one = dict(name='boom', role='drum', notes=[dict(t=0, d=2, p='kick', v=0.9)])
        self.assertEqual(self.hits(dict(bpm=120, ts=[4, 4], tracks=[one]), ['drum_kit'])[0], [])

    def test_a_thin_piece_is_measured_as_thin(self):
        hits, _ = self.hits(dict(bpm=120, ts=[4, 4], tracks=[line()]), ['thin_texture_throughout'])
        self.assertEqual([g for g, _ in hits], ['thin_texture_throughout'])

    def test_an_unmeasurable_gesture_is_reported_not_passed(self):
        hits, unmeasured = self.hits(dict(bpm=120, ts=[4, 4], tracks=[line()]), ['compressed_crest'])
        self.assertEqual((hits, unmeasured), ([], ['compressed_crest']))


class Derivation(unittest.TestCase):
    def test_a_scene_gives_the_focus_and_the_peak_intensity(self):
        brief, resolved = compose.apply_intent(dict(intent={'scenes': ['farewell'], 'emotions': ['grief']}))
        self.assertEqual(brief['emotion'], 'grief')
        self.assertEqual(brief['focus'], 'drone')
        scene = intent.vocabulary()['scenes']['farewell']
        self.assertEqual(brief['intensity'], scene['energy_arc'][1])

    def test_what_the_brief_already_says_wins(self):
        brief, _ = compose.apply_intent(dict(emotion='joyful', focus='melody', intensity=0.9,
                                            intent={'emotions': ['grief'], 'scenes': ['farewell']}))
        self.assertEqual((brief['emotion'], brief['focus'], brief['intensity']), ('joyful', 'melody', 0.9))

    def test_a_composed_piece_carries_the_declaration_onto_the_score(self):
        score = compose.compose(dict(genre='ambient', duration_s=12, seed=3,
                                     intent={'scenes': ['farewell'], 'emotions': ['grief']}))
        self.assertEqual(score['intent']['emotions'], ['grief'])
        self.assertTrue(score['meta']['intent_notes'])
        self.assertEqual([r[0] for r in qg.intent_rows(score) if r[1] == 'intent.vocabulary'], ['PASS'])

    def test_no_block_means_no_derivation(self):
        brief = dict(emotion='calm')
        self.assertIs(compose.apply_intent(brief)[1], None)


class Rows(unittest.TestCase):
    def test_a_declaration_is_passed_only_after_it_resolves(self):
        rows = qg.intent_rows(dict(piece_type='melodic', tracks=[line()],
                                   intent={'emotions': ['grief'], 'registers': ['cinematic']}))
        self.assertEqual([r[0] for r in rows if r[1] == 'intent.vocabulary'], ['PASS'])

    def test_a_word_that_does_not_resolve_fails(self):
        rows = qg.intent_rows(dict(piece_type='melodic', tracks=[line()], intent={'emotions': ['numinous']}))
        self.assertEqual([r[0] for r in rows if r[1] == 'intent.vocabulary'], ['FAIL'])

    def test_a_forbidden_gesture_in_the_notes_fails(self):
        score = dict(piece_type='groove', bpm=120, ts=[4, 4], tracks=[kick(), line('bass', 16, 40)],
                     intent={'emotions': ['calm']})
        rows = qg.intent_rows(score)
        self.assertIn(('FAIL', 'intent.avoid'), [(r[0], r[1]) for r in rows])

    def test_a_clean_piece_passes_the_avoidance_it_promised(self):
        score = dict(piece_type='groove', bpm=120, ts=[4, 4], tracks=[kit(), line('bass', 16, 40)],
                     intent={'emotions': ['calm']})
        rows = qg.intent_rows(score)
        self.assertEqual([r[0] for r in rows if r[1] == 'intent.avoid'], ['PASS'])

    def test_a_piece_with_no_block_says_so_and_is_not_a_failure(self):
        rows = qg.intent_rows(dict(piece_type='melodic', tracks=[line()]))
        self.assertEqual([r[0] for r in rows if r[1] == 'intent.vocabulary'], ['INFO'])


if __name__ == '__main__':
    unittest.main()
