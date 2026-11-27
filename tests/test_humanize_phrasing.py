"""Opt-in anticipation and bar breathing in the humanize engine."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import humanize as hz   # noqa: E402


def line():
    notes = []
    for bar in range(4):
        for k, (off, d) in enumerate([(0.0, 1.0), (1.0, 0.5), (1.5, 0.5), (2.0, 1.0), (3.0, 0.5), (3.5, 0.5)]):
            notes.append(dict(t=bar * 4 + off, d=d, p=60 + k, v=0.8))
    return notes


def run(cfg, role='melody'):
    return hz.humanize_track(line(), hz.tempo_map_for({'bpm': 120, 'ts': [4, 4], 'tracks': []}, seed=5), cfg, role=role, seed=5, ts=(4, 4), bpm=120.0)


class Phrasing(unittest.TestCase):
    def test_default_is_unchanged_and_unknown_keys_still_fail(self):
        a = run({'preset': 'natural'})
        b = run({'preset': 'natural', 'anticipate_ms': 0.0, 'bar_breath_ms': 0.0})
        self.assertEqual([e['t'] for e in a], [e['t'] for e in b])
        with self.assertRaises(ValueError):
            run({'anticipate': 20})

    def test_anticipation_moves_offbeat_notes_before_a_strong_beat_earlier(self):
        base, ant = run({'preset': 'tight'}), run({'preset': 'tight', 'anticipate_ms': 40.0})
        shift = [(e['t'] - f['t']) * 1000 for e, f in zip(base, ant)]
        for i, x in enumerate(shift):
            if i % 6 in (2, 5):                    # the eighth before the middle of the bar, and the eighth before the bar line
                self.assertGreater(x, 10.0, i)
            else:
                self.assertLess(abs(x), 1.0, i)

    def test_bar_breath_opens_a_gap_at_the_bar_line(self):
        base, br = run({'preset': 'tight'}), run({'preset': 'tight', 'bar_breath_ms': 120.0})

        def gap(ev, i):
            return ev[i + 1]['t'] - (ev[i]['t'] + ev[i]['dur'])
        for i in range(len(base) - 1):
            if i % 6 == 5:
                self.assertGreater(gap(br, i), gap(base, i) + 0.02, i)          # the bar breathes
            elif i % 6 in (0, 1):
                self.assertAlmostEqual(gap(br, i), gap(base, i), places=6)       # nothing else moves


if __name__ == '__main__':
    unittest.main()
