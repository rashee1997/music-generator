# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The processed-stem cache: a repeat render reuses the chain, a changed stem does not.

`docs/agent_prompt_mix_speed_and_channels.md` step 6 asks for the processed-stem cache and for a second output
format to reuse the first one's per-stem processing. Both come from one split in mixer.py: `process_chain` (gain
staging, EQ, dynamics, level, automation - the same for every deliverable) is cached, `_place` (width, pan, the
head filter, the bus hand-over - different per bus) is not.

The cache must be invisible when it works: a reused stem has to produce the same samples as a fresh one.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import mix_context                                            # noqa: E402
import mixer                                                  # noqa: E402

SR = 44100
SCORE = dict(bpm=120, ts=[4, 4], space='hall', mix_preset='default',
             tracks=[dict(name='lead', role='melody', instrument='flute'),
                     dict(name='bass', role='bass', instrument='cello'),
                     dict(name='pad', role='pad', instrument='slow_strings')])


def stems(seed=1, seconds=1.0):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    return {name: (0.1 * rng.standard_normal((n, 2))).astype(np.float32)
            for name in ('lead', 'bass', 'pad')}


def context():
    return mix_context.MixContext(mix_context.mix_for('default'), mixer.resolve_space('hall'),
                                  name='cache-test', space_name='hall', space_owned=False)


class ProcessedStemCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='mix_cache_')
        self.stems = stems()
        self.ctx = context()
        mixer.use_mix_cache(self.tmp)

    def tearDown(self):
        mixer.use_mix_cache(None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def mix(self, st=None, ctx=None):
        return mixer.mix_stems(SCORE, st if st is not None else self.stems, SR, ctx or self.ctx)

    def test_a_repeat_mix_reuses_every_stem_and_sounds_the_same(self):
        first = self.mix()
        self.assertEqual(mixer.STATE['cache']['hits'], 0, msg='the first mix has nothing to reuse')
        second = self.mix()
        self.assertEqual(mixer.STATE['cache']['hits'], len(self.stems))
        np.testing.assert_array_equal(second, first, err_msg='a reused stem is not the same audio')

    def test_only_the_changed_stem_is_processed_again(self):
        self.mix()
        changed = dict(self.stems)
        changed['bass'] = (changed['bass'] * 0.5).astype(np.float32)
        self.mix(changed)
        self.assertEqual(mixer.STATE['cache']['hits'], len(self.stems) - 1)
        before = self.mix(self.stems)
        self.assertNotEqual(float(np.abs(before).sum()), 0.0)

    def test_a_changed_mix_preset_invalidates_every_stem(self):
        self.mix()
        loud = dict(mix_context.mix_for('default'))
        loud['gain_staging'] = dict(loud['gain_staging'], target_lufs=float(loud['gain_staging'].get('target_lufs', -18.0)) - 3.0)
        ctx = mix_context.MixContext(loud, mixer.resolve_space('hall'), name='loud', space_name='hall',
                                     space_owned=False)
        self.mix(ctx=ctx)
        self.assertEqual(mixer.STATE['cache']['hits'], 0, msg='a different mix preset must re-process the stems')

    def test_a_different_bus_still_reuses_the_chain(self):
        # the second format is what the cache is for: placement differs per bus, the chain does not
        from spatial_engine import render
        self.mix()
        bus = render.LayoutBus('itu_bs2051_system_j', 'immersive_7_1_4', SR)
        out = mixer.mix_stems(SCORE, self.stems, SR, self.ctx, bus=bus)
        self.assertEqual(mixer.STATE['cache']['hits'], len(self.stems))
        self.assertEqual(out.shape[1], len(render.config.channel_names('itu_bs2051_system_j')))

    def test_no_cache_directory_is_a_normal_render(self):
        mixer.use_mix_cache(None)
        a = self.mix()
        b = self.mix()
        self.assertEqual(mixer.STATE['cache']['hits'], 0)
        np.testing.assert_array_equal(a, b)

    def test_a_corrupt_entry_is_a_miss_not_an_error(self):
        self.mix()
        for name in self.stems:
            for path in Path(self.tmp).rglob(f'{name}.npy'):
                path.write_bytes(b'not a numpy file')
        out = self.mix()
        self.assertEqual(mixer.STATE['cache']['hits'], 0)
        self.assertTrue(np.isfinite(out).all())


if __name__ == '__main__':
    unittest.main()
