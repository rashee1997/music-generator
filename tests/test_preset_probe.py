# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""preset_probe: a sound with a fault fails its own row; the repaired sound passes.

Run: python -m unittest tests.test_preset_probe
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import preset_probe as pp  # noqa: E402

SR = 44100


def good(seconds=1.0, peak=0.5):
    t = np.arange(int(seconds * SR)) / SR
    return peak * np.sin(2 * np.pi * 200 * t) * np.exp(-6 * t) * np.minimum(1.0, t * 400)       # starts at zero, decays to nothing


def levels(rows):
    return {r[1]: r[0] for r in rows}


class OneSound(unittest.TestCase):
    def test_a_clean_sound_passes(self):
        self.assertEqual(levels(pp.probe_sound('step', good())), {'probe.sound': 'PASS'})

    def test_a_silent_sound_fails(self):
        self.assertEqual(levels(pp.probe_sound('brush', good(peak=1e-5)))['probe.silent'], 'FAIL')

    def test_a_clipping_sound_fails(self):
        x = np.clip(good(peak=3.0), -1.0, 1.0)
        self.assertEqual(levels(pp.probe_sound('crack', x))['probe.clip'], 'FAIL')

    def test_the_event_velocity_scales_the_check(self):
        x = good(peak=1.4)
        self.assertEqual(levels(pp.probe_sound('crack', np.clip(x, -1, 1), velocity=1.0))['probe.clip'], 'FAIL')
        self.assertNotIn('probe.clip', levels(pp.probe_sound('crack', x, velocity=0.5)))

    def test_a_sound_that_starts_on_a_step_fails(self):
        x = good() + 0.2
        x[0] = 0.2
        self.assertEqual(levels(pp.probe_sound('thump', x))['probe.start'], 'FAIL')

    def test_a_sound_cut_at_full_level_warns(self):
        t = np.arange(SR) / SR
        x = 0.5 * np.sin(2 * np.pi * 200 * t) * np.minimum(1.0, t * 400)
        self.assertEqual(levels(pp.probe_sound('hum', x))['probe.tail'], 'WARN')

    def test_a_sound_with_a_mean_warns(self):
        x = good() * 0.2 + 0.01 * np.minimum(1.0, np.arange(SR) / 400.0)
        self.assertEqual(levels(pp.probe_sound('rumble', x))['probe.dc'], 'WARN')


    def test_a_mean_already_handled_by_the_track_filter_is_not_reported(self):
        x = good() * 0.2 + 0.01 * np.minimum(1.0, np.arange(SR) / 400.0)
        self.assertNotIn('probe.dc', levels(pp.probe_sound('rumble', x, dc_filtered=True)))


class Score(unittest.TestCase):
    def rows(self, render):
        score = {'tracks': [dict(name='steps', instrument='sfx:step', role='fx', notes=[dict(t=0, d=1, p=60, v=0.6), dict(t=2, d=1, p=60, v=0.9)]),
                            dict(name='violins', instrument='violins', role='pad', notes=[dict(t=0, d=1, p=60, v=0.6)])]}
        return pp.probe_rows(score, lambda n: {'seconds': 1.0}, render)

    def test_each_effect_is_probed_once_at_its_loudest_velocity(self):
        seen = []

        def render(name, seconds, sr, seed, **kw):
            seen.append((name, seconds))
            return good()
        rows = self.rows(render)
        self.assertEqual(seen, [('step', 1.0)])
        self.assertEqual(levels(rows), {'probe.sound': 'PASS'})

    def test_a_render_that_raises_is_reported_not_raised(self):
        def render(name, seconds, sr, seed, **kw):
            raise RuntimeError('no engine')
        self.assertEqual(self.rows(render)[0][0], 'INFO')

    def test_a_track_with_a_dc_filter_silences_the_dc_row(self):
        def render(name, seconds, sr, seed, **kw):
            return good() * 0.2 + 0.01 * np.minimum(1.0, np.arange(SR) / 400.0)
        score = {'tracks': [dict(name='door', instrument='sfx:door', role='fx', dc_hp_hz=90.0, notes=[dict(t=0, d=1, p=60, v=0.8)])]}
        self.assertNotIn('probe.dc', levels(pp.probe_rows(score, lambda n: {'seconds': 1.0}, render)))
        score['tracks'][0].pop('dc_hp_hz')
        self.assertEqual(levels(pp.probe_rows(score, lambda n: {'seconds': 1.0}, render))['probe.dc'], 'WARN')

    def test_a_real_shipped_effect_renders_and_is_judged(self):
        score = {'tracks': [dict(name='hb', instrument='sfx:heartbeat', role='fx', notes=[dict(t=0, d=2, p=60, v=0.8)])]}
        rows = pp.probe_rows(score, lambda n: {'seconds': 2.0})
        self.assertTrue(rows and all(r[1].startswith('probe.') for r in rows), rows)


if __name__ == '__main__':
    unittest.main()
