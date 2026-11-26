# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""A drum part of a few hundred hits keeps sounding to its last hit.

The per-pitch drum path once sent no note-off to the synth, so every hit kept its voice and a long kick part went silent after about
250 hits, with no error. This renders 420 kicks (one every half second) of an orchestral kit and checks that the last 45 s are as loud as the first 40 s.

Run: python -m unittest tests.test_drum_voices
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import render_natural as rn  # noqa: E402


class DrumVoices(unittest.TestCase):
    def test_a_long_kick_part_does_not_run_out_of_voices(self):
        notes = [dict(t=1.0 * i, d=0.25, p=36, v=0.8) for i in range(420)]          # 210 s at 120 bpm, a hit every beat (0.5 s)
        score = dict(bpm=120, ts=[4, 4], seed=3, humanize='tight', tempo_points=[[0, 120], [210, 120]], rubato=0.0, wander=0.0, ritard=0.0,
                     tracks=[dict(name='kick', instrument='orchestral', role='drum', notes=notes)])
        stems, _tm = rn.build_stems(score, None, 3, verbose=False)
        x = stems['kick']
        x = x.mean(axis=1) if x.ndim == 2 else x
        sr = rn.SR
        first = float(np.sqrt(np.mean(x[10 * sr:50 * sr] ** 2)))
        last = float(np.sqrt(np.mean(x[160 * sr:205 * sr] ** 2)))
        self.assertGreater(first, 1e-3)
        self.assertGreater(last, 0.3 * first, 'the last quarter of a long kick part is silent: the synth ran out of voices')


if __name__ == '__main__':
    unittest.main()
