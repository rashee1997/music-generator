"""A SoundFont's one sample layer plays a hard note as a louder soft note. These tests pin the per-note laws that fix that:
brightness follows the written velocity (fc = f0 * h(v), with harmonic enrichment from a velocity-driven saturator), the level
gap between soft and loud notes survives, and a soft note rises more slowly than a hard one."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import dsp  # noqa: E402
import families  # noqa: E402
import family_dsp as fd  # noqa: E402

SR = 44100


def two_note_stem(f0=220.0, vels=(0.3, 0.95)):
    """One quiet and one loud pure-ish note one second apart: the amplitude follows the velocity as a sample bank does."""
    x = np.zeros(SR * (len(vels) + 1), dtype=np.float32)
    ev = []
    for i, v in enumerate(vels):
        tt = np.arange(int(0.8 * SR)) / SR
        seg = (0.05 + 0.45 * v ** 2) * np.sin(2 * np.pi * f0 * tt) * np.minimum(1, tt * 40) * np.minimum(1, (0.8 - tt) * 40)
        x[i * SR:i * SR + len(seg)] += seg
        ev.append(dict(t=float(i), dur=0.8, p=57, v=v))
    return np.stack([x, x], 1), ev


def centroid(y, t0):
    seg = y[int((t0 + 0.05) * SR):int((t0 + 0.7) * SR)].mean(axis=1)
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 16384)) ** 2
    f = np.fft.rfftfreq(16384, 1.0 / SR)
    return float(np.sum(f * sp) / np.sum(sp))


def level_db(y, t0):
    seg = y[int((t0 + 0.1) * SR):int((t0 + 0.7) * SR)]
    return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)


class Law(unittest.TestCase):
    def test_the_cutoff_rises_with_velocity_and_with_pitch_and_is_clipped(self):
        a = fd.cutoff_for(0.2, 57, 3, 22)
        b = fd.cutoff_for(0.9, 57, 3, 22)
        self.assertLess(a, b)
        self.assertLess(fd.cutoff_for(0.5, 45, 3, 22), fd.cutoff_for(0.5, 69, 3, 22))     # harmonics, not a fixed frequency
        self.assertEqual(fd.cutoff_for(1.0, 120, 3, 22, fc_max=9000.0), 9000.0)
        self.assertEqual(fd.cutoff_for(0.0, 20, 3, 22, fc_min=500.0), 500.0)

    def test_velocity_is_read_on_either_scale(self):
        self.assertAlmostEqual(fd._unit_velocity(127), 1.0)
        self.assertAlmostEqual(fd._unit_velocity(0.5), 0.5)

    def test_a_chord_is_one_cutoff_at_its_lowest_note(self):
        g = fd._note_groups([dict(t=0.0, dur=1, p=60, v=100), dict(t=0.01, dur=1, p=67, v=60), dict(t=1.0, dur=1, p=60, v=30)])
        self.assertEqual(len(g), 2)
        self.assertEqual(g[0][3], 60.0)


class Render(unittest.TestCase):
    def test_a_loud_note_is_brighter_than_a_soft_one_after_the_law_and_not_before(self):
        y, ev = two_note_stem()
        z = fd.velocity_brightness(y, SR, ev, 3, 24, 1.0, 0.0, 500.0, 12000.0, 10.0)
        before = centroid(y, 1.0) / centroid(y, 0.0)
        after = centroid(z, 1.0) / centroid(z, 0.0)
        self.assertLess(before, 1.05)                  # a sine at two levels has one timbre
        self.assertGreater(after, 1.3)

    def test_the_loud_over_soft_level_gap_survives(self):
        y, ev = two_note_stem()
        z = fd.velocity_brightness(y, SR, ev, 3, 24, 1.0, 0.0, 500.0, 12000.0, 10.0)
        gap_in = level_db(y, 1.0) - level_db(y, 0.0)
        gap_out = level_db(z, 1.0) - level_db(z, 0.0)
        self.assertGreater(gap_in, 10.0)
        self.assertLess(abs(gap_out - gap_in), 2.5, f'the saturator flattened the dynamics: {gap_in:.1f} dB -> {gap_out:.1f} dB')

    def test_no_events_means_no_change(self):
        y, _ = two_note_stem()
        self.assertTrue(np.array_equal(fd.apply(y, {'family': 'bowed'}, {}, SR, 0, events=None), fd.apply(y, {'family': 'bowed'}, {}, SR, 0, events=None)))
        z = fd.apply(y, {'family': 'synth'}, {}, SR, 0, events=two_note_stem()[1])
        self.assertTrue(np.allclose(z, y))             # a family without the blocks is untouched

    def test_the_jitter_is_deterministic_by_seed_and_differs_between_seeds(self):
        y, ev = two_note_stem()
        a = fd.velocity_brightness(y, SR, ev, 3, 24, 1.0, 0.3, seed=1)
        b = fd.velocity_brightness(y, SR, ev, 3, 24, 1.0, 0.3, seed=1)
        c = fd.velocity_brightness(y, SR, ev, 3, 24, 1.0, 0.3, seed=2)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))

    def test_a_soft_note_rises_more_slowly_than_a_hard_one(self):
        x = np.zeros((SR * 2, 2), dtype=np.float32)
        for i in (0, 1):
            x[i * SR + 100:i * SR + SR - 100] = 0.3
        ev = [dict(t=100 / SR, dur=0.9, p=60, v=0.2), dict(t=1 + 100 / SR, dur=0.9, p=60, v=0.95)]
        z = fd.velocity_attack(x, SR, ev, 45.0, 3.0, 1.5)

        def rise_ms(a, t0):
            seg = np.abs(a[int(t0 * SR):int((t0 + 0.2) * SR), 0])
            hi = seg.max()
            return (np.argmax(seg >= 0.9 * hi) - np.argmax(seg >= 0.1 * hi)) / SR * 1000.0
        self.assertGreater(rise_ms(z, 100 / SR), 4.0 * rise_ms(z, 1 + 100 / SR) + 1.0)

    def test_soften_onsets_still_takes_one_length_and_checks_a_list(self):
        x = np.ones((SR, 2), dtype=np.float32) * 0.2
        dsp.soften_onsets(x, SR, times=[0.1], ms=5.0)
        with self.assertRaises(ValueError):
            dsp.soften_onsets(x, SR, times=[0.1, 0.2], ms=[5.0])


class Data(unittest.TestCase):
    def test_every_family_block_is_complete_and_inside_its_range(self):
        for name, fam in families.table()['families'].items():
            t = fam.get('velocity_brightness')
            if t:
                self.assertLess(t['h_lo'], t['h_hi'], name)
                self.assertLess(t['fc_min'], t['fc_max'], name)
                self.assertTrue(0.0 <= t['jitter_oct'] <= 0.5, name)
                self.assertTrue(0.0 <= t['drive_k'] <= 20.0, name)
            a = fam.get('velocity_attack')
            if a:
                self.assertLess(a['ms_hard'], a['ms_soft'], name)

    def test_a_track_can_switch_a_block_off(self):
        eff = families.effective({'family': 'bowed'}, {'velocity_brightness': None})
        self.assertNotIn('velocity_brightness', eff)


class EndToEnd(unittest.TestCase):
    def test_a_rendered_cello_line_gets_brighter_with_velocity(self):
        import pretty_midi
        import render_natural as rn
        import realism_report as rr
        tim = os.path.join(os.path.dirname(pretty_midi.__file__), 'TimGM6mb.sf2')
        rng = np.random.default_rng(5)
        notes = [dict(t=float(i), d=0.8, p=int(48 + rng.integers(0, 12)), v=float(np.round(rng.uniform(0.28, 0.98), 2))) for i in range(32)]

        def run(extra):
            sc = {'bpm': 60, 'ts': [4, 4], 'tracks': [dict(name='m', instrument='cello', role='melody', family='bowed', notes=notes,
                                                         humanize={'preset': 'tight'}, **extra)]}
            stems, _ = rn.build_stems(sc, tim, seed=3, verbose=False)
            return rr.velocity_response(stems, sc)['value']
        on, off = run({}), run({'velocity_brightness': None, 'velocity_attack': None})
        self.assertGreater(on, off + 0.3)
        self.assertGreaterEqual(on, 0.30)


if __name__ == '__main__':
    unittest.main()
