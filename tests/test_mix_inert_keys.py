"""A preset key the chosen engine never reads must be reported, and a copy of the shipped chains must be listed."""
import copy
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import mix_schema
import mixer


class InertDynamics(unittest.TestCase):
    def test_defaults_report_nothing(self):
        self.assertEqual(mix_schema.inert_dynamics({}), [])
        self.assertEqual(mix_schema.inert_dynamics({'dynamics': dict(mix_schema.DEFAULTS['dynamics'])}), [])

    def test_a_knee_under_the_pedalboard_engine_is_reported(self):
        got = mix_schema.inert_dynamics({'dynamics': {'knee_db': 6.0, 'lookahead_ms': 5.0}})
        self.assertEqual(sorted(k for k, _ in got), ['knee_db', 'lookahead_ms'])

    def test_the_dsp_engine_reads_them(self):
        self.assertEqual(mix_schema.inert_dynamics({'dynamics': {'engine': 'dsp', 'knee_db': 6.0}}), [])

    def test_the_four_compressor_knobs_are_not_dynamics_keys(self):
        self.assertEqual(mix_schema.inert_dynamics({'dynamics': {'engine': 'pedalboard'}}), [])

    def test_the_mixer_says_so_when_a_preset_is_installed(self):
        mix = mix_schema.with_defaults({'dynamics': {'knee_db': 6.0}})
        buf = io.StringIO()
        with redirect_stdout(buf):
            mixer._install(copy.deepcopy(mix))
        self.assertIn('mix.dynamics.knee_db', buf.getvalue())
        self.assertIn('engine', buf.getvalue())

    def test_a_clean_preset_prints_nothing(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            mixer._install(mix_schema.with_defaults({}))
        self.assertEqual(buf.getvalue(), '')


class RedundantChains(unittest.TestCase):
    def test_a_full_copy_is_listed_and_a_change_is_not(self):
        full = {'role_chains': copy.deepcopy(mix_schema.ROLE_CHAINS)}
        self.assertEqual(len(mix_schema.redundant_chains(full)), len(mix_schema.ROLE_CHAINS))
        changed = copy.deepcopy(full)
        changed['role_chains']['bass'] = {'eq': [{'type': 'hp', 'f': 99}]}
        self.assertNotIn('role_chains.bass', mix_schema.redundant_chains(changed))
        self.assertEqual(mix_schema.redundant_chains({}), [])


if __name__ == '__main__':
    unittest.main()
