# Copyright (C) 2026 rasheed <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""The gate measures each stem's band once, and the packaging stage reuses the gate's analysis.

`docs/agent_prompt_mix_speed_and_channels.md` step 5: share the per-stem band-filtered signals between
`band_db`, `_band_frames` and the tier-2 rows, and stop stage 7 re-running `nc.analyse` /
`cochlear_roughness_check` on audio the gate has just measured.

Both are memoisation, so the tests are about identity: the *same* array asked twice costs one measurement, a
different array is measured again, and the reused number is the number a fresh call would give.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import dsp                                                    # noqa: E402
import naturalness_check as nc                                # noqa: E402
import pipeline                                                # noqa: E402
import quality_gate as qg                                     # noqa: E402

SR = 44100


def noise(seconds=1.5, seed=3):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    return np.stack([0.1 * rng.standard_normal(n), 0.1 * rng.standard_normal(n)], axis=1).astype(np.float32)


class BandMemo(unittest.TestCase):
    def test_two_band_questions_cost_one_measurement(self):
        x = noise()
        calls = {'n': 0}
        real = dsp.band_power

        def counting(*a, **k):
            calls['n'] += 1
            return real(*a, **k)

        dsp.band_power = counting
        try:
            first = dsp.band_db(x, SR, 500.0, 4000.0)
            second = dsp.band_db(x, SR, 500.0, 4000.0)
        finally:
            dsp.band_power = real
        self.assertEqual(calls['n'], 1)
        self.assertEqual(first, second)

    def test_a_different_array_is_measured_again(self):
        x = noise()
        first = dsp.band_db(x, SR, 500.0, 4000.0)
        y = noise(seed=9)
        self.assertNotEqual(first, dsp.band_db(y, SR, 500.0, 4000.0))
        # the same bytes in a new array: a fresh measurement, and the same answer
        self.assertAlmostEqual(first, dsp.band_db(x.copy(), SR, 500.0, 4000.0), places=6)

    def test_band_frames_are_computed_once_per_stem(self):
        from scipy import signal as scipy_signal
        x = noise(seconds=5.0)
        calls = {'n': 0}
        real = scipy_signal.sosfilt

        def counting(*a, **k):
            calls['n'] += 1
            return real(*a, **k)

        scipy_signal.sosfilt = counting
        try:
            a = qg._band_frames(x, SR)
            b = qg._band_frames(x, SR)
        finally:
            scipy_signal.sosfilt = real
        self.assertEqual(calls['n'], 1)
        np.testing.assert_array_equal(a, b)


class PackagingReusesTheGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='packaging_')
        self.path = os.path.join(self.tmp, 'master.wav')
        sf.write(self.path, noise(1.5), SR, subtype='PCM_24')
        self.score = dict(title='reuse', bpm=120, key='D', ts=[4, 4], output_targets=['stereo'],
                          tracks=[dict(name='lead', role='melody', instrument='flute',
                                       notes=[dict(t=0, d=4, p=62)])],
                          master=dict(lufs=-14.0, true_peak=-1.5))

    def test_the_master_is_analysed_once_for_the_whole_run(self):
        pipe = pipeline.MusicPipeline(verbose=False)
        calls = {'n': 0}
        real = nc.analyse

        def counting(*a, **k):
            calls['n'] += 1
            return real(*a, **k)

        nc.analyse = counting
        try:
            pipe.stage6_ci_quality_suite(self.score, None, self.path, mode='draft')
            rows = pipe.stage6_ci_quality_suite.__self__          # keep the object alive for the reader
            self.assertIs(rows, pipe)
            report = pipe.stage7_package_release(self.score, self.path, [], 0, 0)
        finally:
            nc.analyse = real
        self.assertEqual(calls['n'], 1, msg='the packaging stage measured the master a second time')
        self.assertIsNotNone(report['measurements']['integrated_lufs'])


if __name__ == '__main__':
    unittest.main()
