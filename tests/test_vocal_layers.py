"""Choir layers: sections that enter with the dynamics. Short renders at a low rate."""
import json
import os
import sys
import unittest
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import vocals                       # noqa: E402
from vocal_engine import layers     # noqa: E402

PRESET = os.path.join(HERE, '..', 'references', 'data', 'presets', 'vocals', 'vocal_choir_cinematic.json')
SR = 16000


def load():
    with open(PRESET, encoding='utf-8') as fh:
        return json.load(fh)


def chord(v, t=0.0):
    return [dict(t=t, dur=1.6, p=p, v=v) for p in (57, 64, 69)]


def sections(**kw):
    return {'ensemble': {'layers': [dict(name='a', voices=2, **kw), dict(name='b', voices=2, vel=[90, 127], select='lowest', shift=-12)]}}


class Specs(unittest.TestCase):
    def test_unknown_key_and_bad_values_are_errors(self):
        for bad in ({'bogus': 1}, {'select': 'top'}, {'vel': [100, 20]}, {'vel': [0, 10]}):
            with self.assertRaises(ValueError, msg=bad):
                layers.specs({'ensemble': {'layers': [dict(name='x', **bad)]}})
        with self.assertRaises(ValueError):
            layers.specs({'ensemble': {'layers': [dict(name='x'), dict(name='x')]}})

    def test_selection_band_and_shift(self):
        sp = layers.specs(sections())
        high = layers.select_events(chord(60) + chord(120, t=2.0), dict(sp[1], select='highest', shift=0))
        self.assertEqual([e['p'] for e in high], [69])                       # only the loud chord, its top note
        low = layers.select_events(chord(120), sp[1])
        self.assertEqual([e['p'] for e in low], [57 - 12])
        mid = layers.select_events(chord(60), dict(sp[0], select='middle'))
        self.assertEqual([e['p'] for e in mid], [64])

    def test_input_is_not_mutated(self):
        ev = chord(100)
        before = json.dumps(ev)
        layers.select_events(ev, layers.specs(sections(shift=7))[0])
        self.assertEqual(json.dumps(ev), before)


class Rendering(unittest.TestCase):
    def render(self, cfg, v):
        return vocals.render_choir(chord(v), sr=SR, config=cfg, return_stems=True)

    def test_the_choir_grows_with_the_dynamics(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            cfg = load()
            _, soft = self.render(cfg, 30)
            _, loud = self.render(cfg, 120)
        self.assertGreater(loud['report']['voices'], soft['report']['voices'])
        self.assertIn('tutti_forte', {v['group'] for v in loud['voices']})
        self.assertNotIn('tutti_forte', {v['group'] for v in soft['voices']})

    def test_a_layered_choir_has_a_wider_dynamic_range_than_a_flat_one(self):
        cfg = load()
        flat = dict(voices=12, vowel='o', expression='cinematic')

        def span(c):
            r = [float(np.sqrt(np.mean(self.render(c, v)[0] ** 2))) for v in (30, 120)]
            return 20 * np.log10(r[1] / r[0])
        self.assertGreater(span(cfg), span(flat) + 3.0)

    def test_sections_are_different_singers(self):
        cfg = load()
        _, info = self.render(cfg, 120)
        groups = {}
        for v in info['voices']:
            groups.setdefault(v['group'], []).append(v['detune_cents'])
        self.assertGreaterEqual(len(groups), 4)
        flat = [x for g in groups.values() for x in g]
        self.assertGreater(len(set(round(x, 3) for x in flat)), len(flat) - 2)

    def test_no_section_singing_is_an_error(self):
        with self.assertRaises(ValueError):
            vocals.render_choir(chord(10), sr=SR, config={'ensemble': {'layers': [dict(name='x', voices=2, vel=[100, 127])]}})

    def test_without_layers_the_render_is_unchanged(self):
        a = vocals.render_choir(chord(90), sr=SR, voices=3, seed=4)
        b = vocals.render_choir(chord(90), sr=SR, voices=3, seed=4, config={'ensemble': {'layers': []}})
        self.assertTrue(np.array_equal(a, b))


if __name__ == '__main__':
    unittest.main()


class Limit(unittest.TestCase):
    def test_the_sum_of_sections_never_exceeds_full_scale_and_peak_trim_caps_it(self):
        cfg = load()
        loud = [dict(t=0.0, dur=1.5, p=p, v=125) for p in (57, 64, 69, 76)]
        out = vocals.render_choir(loud, sr=SR, config=cfg)
        self.assertLessEqual(float(np.abs(out).max()), 1.0)
        capped = vocals.render_choir(loud, sr=SR, config=dict(cfg, peak_trim=0.5))
        self.assertLess(float(np.abs(capped).max()), float(np.abs(out).max()) + 1e-6)
