"""The mixer's defaults are data, a project's mix is its own preset, and nothing is forced to be restated.

`references/data/mix_defaults.json` holds every shipped default (with provenance); `mix_schema.DEFAULTS` is loaded from it.
`project_gate.mix_preset_problems` requires the piece's mix preset to be the project's own and described, and nothing else:
a key a preset leaves out is the default.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import mix_schema  # noqa: E402
import presets  # noqa: E402
import project_gate  # noqa: E402


class DefaultsAreData(unittest.TestCase):
    def doc(self):
        with open(mix_schema.MIX_DEFAULTS_PATH, encoding='utf-8') as f:
            return json.load(f)

    def test_the_schema_is_loaded_from_the_file(self):
        d = self.doc()
        for k, v in d.items():
            if k.startswith('_') or k == 'mastering':
                continue
            self.assertEqual(mix_schema.DEFAULTS[k], v, k)
        self.assertEqual(mix_schema.ROLE_CHAINS, d['role_chains'])
        self.assertEqual(mix_schema.SPECTRAL_PROFILES, d['spectral']['profiles'])

    def test_every_section_has_a_provenance_line(self):
        d = self.doc()
        sections = [k for k in d if not k.startswith('_')]
        self.assertEqual(sorted(set(sections) - set(d['_provenance'])), [])
        self.assertTrue(all(str(v).strip() for v in d['_provenance'].values()))

    def test_the_loudness_profiles_stay_in_master_targets(self):
        self.assertNotIn('profiles', self.doc()['mastering'])
        self.assertIn('default', mix_schema.DEFAULTS['mastering']['profiles'])

    def test_the_master_highpass_default_is_the_long_standing_one(self):
        m = mix_schema.DEFAULTS['mastering']
        self.assertEqual((m['highpass_hz'], m['highpass_order']), (24.0, 1))

    def test_a_preset_that_lists_nothing_gets_every_default(self):
        merged = mix_schema.with_defaults({'name': 'x', 'character': 'a'})
        self.assertEqual(merged['mastering']['highpass_hz'], 24.0)
        self.assertEqual(merged['role_chains'], mix_schema.ROLE_CHAINS)

    def test_a_preset_overrides_one_key_and_keeps_the_rest(self):
        merged = mix_schema.with_defaults({'mastering': {'highpass_hz': 30.0}})
        self.assertEqual(merged['mastering']['highpass_hz'], 30.0)
        self.assertEqual(merged['mastering']['highpass_order'], 1)


class Scaffold(unittest.TestCase):
    def run_scaffold(self, extra=()):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, os.path.join(SCRIPTS, 'presets.py'), 'scaffold', 'mix', 'm', '--project', d, *extra],
                           check=True, capture_output=True)
            return json.load(open(os.path.join(d, 'presets', 'mix', 'm.json')))

    def test_the_default_scaffold_lists_only_what_a_project_decides(self):
        body = self.run_scaffold()
        self.assertTrue(set(body).isdisjoint(mix_schema.DEFAULTS), sorted(set(body) & set(mix_schema.DEFAULTS)))
        self.assertIn('character', body)

    def test_full_writes_the_sections_out(self):
        body = self.run_scaffold(['--full'])
        self.assertIn('role_chains', body)
        self.assertIn('gain_staging', body)


class Gate(unittest.TestCase):
    def project(self, files):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'presets', 'mix'))
        for name, body in files.items():
            with open(os.path.join(d, 'presets', 'mix', name + '.json'), 'w') as f:
                json.dump(body, f)
        return d

    def cleanup(self, d):
        presets.PROJECT_ROOTS[:] = [r for r in presets.PROJECT_ROOTS if not str(r).startswith(d)]
        presets._CACHE.clear() if hasattr(presets, '_CACHE') and hasattr(presets._CACHE, 'clear') else None

    def problems(self, files, score):
        d = self.project(files)
        try:
            return project_gate.mix_preset_problems(score, d)
        finally:
            self.cleanup(d)

    def test_the_shipped_default_is_not_a_projects_mix(self):
        r = self.problems({}, {'mix_preset': 'default'})
        self.assertTrue(r and 'shipped default' in r[0], r)

    def test_a_score_with_no_mix_preset_is_judged_as_default(self):
        r = self.problems({}, {})
        self.assertTrue(r and 'shipped default' in r[0], r)

    def test_a_missing_preset_is_named(self):
        r = self.problems({}, {'mix_preset': 'nope_mix'})
        self.assertTrue(r and 'has no preset' in r[0], r)

    def test_a_placeholder_character_is_refused(self):
        r = self.problems({'p_mix': {'name': 'p_mix', 'character': 'ONE SENTENCE: what this music is'}}, {'mix_preset': 'p_mix'})
        self.assertTrue(r and 'character' in r[0], r)

    def test_a_preset_that_states_only_name_and_character_is_enough(self):
        r = self.problems({'p_mix': {'name': 'p_mix', 'character': 'a close dry chase: the pulse and the low end carry it'}}, {'mix_preset': 'p_mix'})
        self.assertEqual(r, [])


if __name__ == '__main__':
    unittest.main()
