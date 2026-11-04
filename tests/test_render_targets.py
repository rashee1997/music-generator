# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Deliverables come from the score and the presets: only what was asked for, never a silent downgrade."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import presets
import render_targets


class Targets(unittest.TestCase):
    def tearDown(self):
        presets.reset_projects()
        presets.STRICT = False

    def test_manifest_is_valid(self):
        self.assertEqual(render_targets.manifest_problems(), [])
        self.assertEqual(presets.validate(), [])

    def test_named_targets_exist(self):
        self.assertEqual(render_targets.names(),
                         ['stereo', 'binaural', 'immersive_7_1', 'immersive_7_1_4'])
        self.assertEqual(render_targets.default(), ['stereo'])

    def test_no_output_key_builds_the_default(self):
        r = render_targets.resolve(dict(title='t'))
        self.assertEqual(r['selected'], ['stereo'])
        self.assertEqual(r['problems'], [])
        self.assertEqual(r['skipped'], [])

    def test_single_name_and_legacy_key(self):
        self.assertEqual(render_targets.resolve(dict(output_targets='stereo'))['selected'], ['stereo'])
        self.assertEqual(render_targets.resolve(dict(outputs='stereo'))['selected'], ['stereo'])

    def test_list_keeps_order_and_deduplicates(self):
        r = render_targets.resolve(dict(output_targets=['stereo', 'stereo']))
        self.assertEqual(r['selected'], ['stereo'])
        self.assertEqual(r['problems'], [])

    def test_filename_comes_from_the_preset(self):
        self.assertEqual(render_targets.filename('stereo'), 'master.wav')
        self.assertEqual(render_targets.channels('stereo'), 2)
        self.assertEqual(render_targets.true_peak('stereo'), -1.5)

    def test_all_builds_what_it_can_and_lists_the_rest(self):
        r = render_targets.resolve(dict(output_targets='all'))
        self.assertEqual(r['selected'], ['stereo'])
        self.assertEqual(sorted(s['target'] for s in r['skipped']),
                         ['binaural', 'immersive_7_1', 'immersive_7_1_4'])
        self.assertEqual(r['problems'], [])

    def test_alias_is_understood_but_blocks_when_unbuildable(self):
        r = render_targets.resolve(dict(output_targets='7.1'))
        self.assertEqual(r['selected'], [])
        self.assertTrue(any('immersive_7_1' in p for p in r['problems']))

    def test_unknown_name_blocks(self):
        r = render_targets.resolve(dict(output_targets='octaphonic'))
        self.assertEqual(r['selected'], [])
        self.assertTrue(any('not a target' in p for p in r['problems']))

    def test_malformed_values_block(self):
        for bad in ([], 7, ['stereo', 3]):
            r = render_targets.resolve(dict(output_targets=bad))
            self.assertTrue(r['problems'], msg=f'{bad!r} should be a problem')
            self.assertEqual(r['selected'], [])

    def test_score_is_not_mutated(self):
        score = dict(output_targets=['stereo', 'all'])
        before = copy.deepcopy(score)
        render_targets.resolve(score)
        self.assertEqual(score, before)

    def test_project_can_add_a_target_without_code(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / 'presets' / 'outputs'
            d.mkdir(parents=True)
            (d / 'immersive_7_1_2.json').write_text(json.dumps(dict(
                name='immersive_7_1_2', character='a project format', order=5, channels=10,
                channel_order=['FL', 'FR', 'FC', 'LFE', 'BL', 'BR', 'SL', 'SR', 'TFL', 'TFR'],
                file='master_7_1_2.wav', renderer='mix_master', true_peak_dbtp=-3.0,
                layout=None, sources=[])), encoding='utf-8')
            presets.reset_projects()
            presets.add_project(td)
            self.assertIn('immersive_7_1_2', render_targets.names())
            r = render_targets.resolve(dict(output_targets='immersive_7_1_2'))
            self.assertEqual(r['selected'], ['immersive_7_1_2'])
            self.assertEqual(render_targets.filename('immersive_7_1_2'), 'master_7_1_2.wav')
            self.assertEqual(render_targets.manifest_problems(), [])

    def test_project_gate_blocks_a_format_the_engine_cannot_build(self):
        import project_gate
        problems = project_gate.output_problems(dict(output_targets='immersive_7_1_4'))
        self.assertTrue(problems)
        self.assertEqual(project_gate.output_problems(dict(output_targets='stereo')), [])


if __name__ == '__main__':
    unittest.main()
