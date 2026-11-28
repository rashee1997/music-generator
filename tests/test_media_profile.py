"""Game and film scene score profiles are valid data, their knowledge files exist, and the gate constants are overridable."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import gate_constants  # noqa: E402
import intent  # noqa: E402
import media_profile  # noqa: E402


class Profiles(unittest.TestCase):
    def test_both_profiles_are_valid(self):
        self.assertEqual(media_profile.problems(), [])

    def test_a_state_carries_families_and_the_mixing_block(self):
        st = media_profile.state('game', 'combat')
        self.assertIn('struck_membrane', st['families_prefer'])
        self.assertIn('duck_under_dialogue_db', st['mixing'])
        sc = media_profile.state('film', 'dialogue_underscore')
        self.assertNotIn('blown_brass', sc['families_prefer'])
        self.assertIn('blown_brass', sc['families_avoid'])

    def test_unknown_state_names_the_known_ones(self):
        with self.assertRaises(KeyError) as e:
            media_profile.state('game', 'nope')
        self.assertIn('combat', str(e.exception))

    def test_every_rule_has_a_source_and_every_register_resolves(self):
        for kind in ('game', 'film'):
            doc = media_profile.load(kind)
            for r in doc['dos'] + doc['donts']:
                self.assertTrue(r['source'])
            for reg in doc['registers'].values():
                self.assertIsNotNone(intent.register_loudness([reg]))

    def test_platform_loudness_follows_the_cited_bands(self):
        self.assertEqual(intent.register_loudness(['game_console']), -24.0)
        self.assertEqual(intent.register_loudness(['game_mobile']), -18.0)
        self.assertEqual(intent.register_loudness(['game_vr']), -17.0)

    def test_a_validator_catches_an_unknown_family(self):
        doc = media_profile.load('game')
        doc['states']['combat']['families_prefer'].append('theremin')
        orig = media_profile.load
        try:
            media_profile.load = lambda kind: doc if kind == 'game' else orig(kind)
            self.assertTrue([p for p in media_profile.problems() if 'theremin' in p])
        finally:
            media_profile.load = orig


class Scaffold(unittest.TestCase):
    def test_media_flag_seeds_the_register_and_the_loudness(self):
        with tempfile.TemporaryDirectory() as d:
            proj = os.path.join(d, 'p')
            subprocess.run([sys.executable, os.path.join(SCRIPTS, 'setup_project.py'), '--new-project', proj, '--title', 'G',
                            '--media', 'game', '--platform', 'mobile'], check=True, capture_output=True)
            sheet = json.load(open(os.path.join(proj, 'direction', 'direction_sheet.json')))
            self.assertEqual(sheet['intent']['registers'], ['game_mobile'])
            self.assertEqual(sheet['loudness_lufs'], -18.0)


class Constants(unittest.TestCase):
    def test_shipped_values_and_unknown_names(self):
        self.assertEqual(gate_constants.get('masking.window_s'), 4.0)
        with self.assertRaises(KeyError):
            gate_constants.get('no.such.constant')

    def test_a_project_overrides_by_name(self):
        import presets
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'presets', 'gate'))
            with open(os.path.join(d, 'presets', 'gate', 'constants.json'), 'w') as f:
                json.dump({'masking.window_s': 6.0}, f)
            gate_constants._CACHE.clear()
            presets.add_project(d)
            try:
                self.assertEqual(gate_constants.get('masking.window_s'), 6.0)
            finally:
                presets.PROJECT_ROOTS[:] = [r for r in presets.PROJECT_ROOTS if not str(r).startswith(d)]
                gate_constants._CACHE.clear()
        self.assertEqual(gate_constants.get('masking.window_s'), 4.0)

    def test_every_constant_has_a_source(self):
        for name in gate_constants.names():
            self.assertTrue(gate_constants._shipped()[name]['source'], name)


if __name__ == '__main__':
    unittest.main()
