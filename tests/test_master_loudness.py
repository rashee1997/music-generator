"""The master's loudness is data and follows the piece's register, not a figure compiled into three modules.

`references/data/master_targets.json` holds the shipped default and the named profiles; `intent.register_loudness` turns a
piece's declared registers into a target; `mastering._master_cfg` uses it only when the piece stated no loudness and chose no
profile. The old behaviour (-14.0 as the fallback in code) is gone.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import intent  # noqa: E402
import mix_schema  # noqa: E402
from mix_engine import mastering  # noqa: E402


class RegisterLoudness(unittest.TestCase):
    def test_the_middle_of_the_overlap(self):
        self.assertEqual(intent.register_loudness(['cinematic']), -16.0)
        self.assertEqual(intent.register_loudness(['cinematic', 'hybrid']), -16.0)      # [-18,-14] with [-20,-14]
        self.assertEqual(intent.register_loudness(['natural']), -14.5)

    def test_registers_that_do_not_overlap_or_say_nothing_give_no_target(self):
        self.assertIsNone(intent.register_loudness([]))
        from unittest import mock
        fake = {'registers': {'loud': {'lufs': [-12.0, -10.0]}, 'quiet': {'lufs': [-24.0, -20.0]}}}
        with mock.patch.object(intent, 'vocabulary', return_value=fake), \
                mock.patch.object(intent, 'resolve_word', side_effect=lambda w: [('registers', w)]):
            self.assertIsNone(intent.register_loudness(['loud', 'quiet']))
            self.assertEqual(intent.register_loudness(['loud']), -11.0)


class MasterCfg(unittest.TestCase):
    def cfg(self, m):
        return mastering._master_cfg(m, mastering._mix())

    def test_the_default_is_the_data_file_and_not_minus_14(self):
        d = mix_schema.master_targets()['default']
        self.assertEqual(self.cfg({})['lufs'], d['lufs'])
        self.assertEqual(d['lufs'], -16.0)

    def test_a_register_levels_an_unprofiled_master(self):
        c = self.cfg({'_registers': ['natural']})
        self.assertEqual(c['lufs'], -14.5)
        self.assertIn('register', c['_lufs_source'])

    def test_a_stated_loudness_wins_over_the_register(self):
        self.assertEqual(self.cfg({'_registers': ['natural'], 'lufs': -18.0})['lufs'], -18.0)

    def test_a_chosen_profile_wins_over_the_register(self):
        c = self.cfg({'_registers': ['natural'], 'profile': 'broadcast'})
        self.assertEqual(c['lufs'], mix_schema.master_targets()['profiles']['broadcast']['lufs'])

    def test_the_named_profiles_are_the_data_files(self):
        profiles = mix_schema.DEFAULTS['mastering']['profiles']
        self.assertEqual(set(profiles), {'default', *mix_schema.master_targets()['profiles']})


class NothingCompiledIn(unittest.TestCase):
    def test_no_module_falls_back_to_a_literal_loudness(self):
        for mod in ('mix_schema.py', 'mix_engine/mastering.py', 'quality_gate.py', 'spatial_gate.py', 'gate_report.py'):
            with open(os.path.join(HERE, '..', 'scripts', mod), encoding='utf-8') as f:
                src = f.read()
            self.assertIsNone(re.search(r"lufs['\"]?\s*,\s*-14", src), f'{mod} still carries a literal -14 loudness fallback')


if __name__ == '__main__':
    unittest.main()
