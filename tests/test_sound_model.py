# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""sound_model.py against the physics it claims: each part is run on a signal whose answer is known."""
import glob
import json
import sys
import time
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
import environment as env
import sfx
import sound_model as sm

SR = 44100


def one(voice, seconds=2.0, seed=1):
    return sm.render(dict(seconds=seconds, voices=[voice]), SR, seed)


def peak_freqs(x, n, lo=50):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / SR)
    out = []
    s = spec.copy()
    s[f < lo] = 0
    for _ in range(n):
        i = int(np.argmax(s))
        out.append(float(f[i]))
        s[max(0, i - 40):i + 40] = 0
    return sorted(out)


class Laws(unittest.TestCase):
    def test_modal_bank_peaks_sit_at_the_mode_ratios(self):
        x = one(dict(excite=dict(kind='impact', tau=0.0001), resonator=dict(kind='modal', law='bar', f1=400.0, n=4, t60=1.0, damp_exp=0.0),
                     events=dict(kind='single')), 1.5)
        got = peak_freqs(x, 4)
        for want, g in zip([400 * r for r in (1, 2.757, 5.404, 8.933)], got):
            self.assertLess(abs(g - want) / want, 0.02, (want, got))

    def test_mode_laws_match_their_tables(self):
        self.assertEqual(list(sm.mode_ratios(dict(law='string', n=4))), [1, 2, 3, 4])
        self.assertEqual(list(sm.mode_ratios(dict(law='tube_closed', n=3))), [1, 3, 5])
        self.assertAlmostEqual(float(sm.mode_ratios(dict(law='membrane', n=6))[1]), 1.594)
        self.assertAlmostEqual(float(sm.mode_ratios(dict(law='power', n=3, exponent=2.0))[2]), 9.0)

    def test_t60_is_the_time_to_minus_60_db(self):
        t60 = 0.5
        x = one(dict(excite=dict(kind='impact', tau=0.0001), resonator=dict(kind='modal', law='string', f1=1000.0, n=1, t60=t60),
                     events=dict(kind='single')), 1.0)
        env_db = 20 * np.log10(np.maximum(np.abs(__import__('scipy.signal', fromlist=['hilbert']).hilbert(x)), 1e-12))
        a, b = int(0.05 * SR), int(0.4 * SR)
        slope = np.polyfit(np.arange(a, b) / SR, env_db[a:b], 1)[0]            # dB per second
        self.assertLess(abs(-60.0 / slope - t60) / t60, 0.15, -60.0 / slope)

    def test_a_harder_contact_is_brighter(self):
        def centroid(tau):
            x = one(dict(excite=dict(kind='impact', tau=tau), resonator=dict(kind='modal', law='string', f1=500.0, n=20, t60=0.3),
                         events=dict(kind='single')), 0.6)
            s = np.abs(np.fft.rfft(x)) ** 2
            f = np.fft.rfftfreq(len(x), 1 / SR)
            return (f * s).sum() / s.sum()
        self.assertGreater(centroid(0.0002), centroid(0.004) * 1.15)

    def test_bounce_gaps_shrink_by_the_restitution(self):
        t, lv = sm.event_times(dict(kind='bounce', at=0.0, gap=0.5, restitution=0.7, n=6), 5.0, np.random.default_rng(0))
        gaps = np.diff(t)
        self.assertTrue(np.allclose(gaps[1:] / gaps[:-1], 0.7))
        self.assertTrue(np.allclose(lv[1:] / lv[:-1], 0.7))

    def test_poisson_rate_and_gap_statistics(self):
        t, _ = sm.event_times(dict(kind='poisson', rate=50.0), 200.0, np.random.default_rng(3))
        self.assertLess(abs(len(t) / 200.0 - 50.0) / 50.0, 0.05)
        g = np.diff(t)
        self.assertLess(abs(g.std() / g.mean() - 1.0), 0.1)                       # exponential gaps: coefficient of variation 1

    def test_gamma_shape_makes_events_more_regular(self):
        t, _ = sm.event_times(dict(kind='gamma', rate=20.0, shape=8.0), 200.0, np.random.default_rng(3))
        g = np.diff(t)
        self.assertLess(g.std() / g.mean(), 0.45)

    def test_periodic_count(self):
        t, _ = sm.event_times(dict(kind='periodic', period=0.25, jitter=0.0, start=0.0), 10.0, np.random.default_rng(0))
        self.assertEqual(len(t), 40)

    def test_bubble_follows_minnaert(self):
        for r_mm in (1.0, 2.0, 4.0):
            x = one(dict(excite=dict(kind='impact', tau=0.0002), resonator=dict(kind='bubble', radius_mm=r_mm, t60=0.3, rise=0.0),
                         events=dict(kind='single')), 0.5)
            want = 3.26 / (r_mm * 1e-3)
            got = peak_freqs(x, 1)[0]
            self.assertLess(abs(got - want) / want, 0.03, (r_mm, got, want))

    def test_friction_spectrum_slope_follows_beta(self):
        rng = np.random.default_rng(5)
        for beta in (-1.0, -2.0):
            ex = sm._d(dict(kind='friction', beta=beta), sm.EXCITE) | {'kind': 'friction'}
            x = sm.excitation(ex, 20.0, SR, rng)
            ps = np.abs(np.fft.rfft(x)) ** 2
            f = np.fft.rfftfreq(len(x), 1 / SR)
            sel = (f > 100) & (f < 5000)
            slope = np.polyfit(np.log(f[sel]), np.log(ps[sel] + 1e-30), 1)[0]
            self.assertLess(abs(slope - beta), 0.25, (beta, slope))

    def test_noise_colors_have_their_slopes(self):
        rng = np.random.default_rng(7)
        for color, want in (('white', 0.0), ('pink', -1.0), ('brown', -2.0)):
            x = sm._colored_noise(rng, SR * 20, color)
            ps = np.abs(np.fft.rfft(x)) ** 2
            f = np.fft.rfftfreq(len(x), 1 / SR)
            sel = (f > 50) & (f < 8000)
            self.assertLess(abs(np.polyfit(np.log(f[sel]), np.log(ps[sel]), 1)[0] - want), 0.2, color)

    def test_marshall_palmer_sizes_are_exponential_and_mean_one(self):
        s = sm.sample_sizes(dict(size=dict(dist='marshall_palmer', rate_mm_h=10)), 20000, np.random.default_rng(1))
        self.assertAlmostEqual(float(s.mean()), 1.0, places=6)
        self.assertGreater(float(s.std()), 0.6)                                    # broad, like an exponential
        self.assertGreater(float((s < 0.5).mean()), 0.25)                          # many small drops

    def test_ou_control_has_the_requested_spread(self):
        db = sm.control_db([dict(kind='ou', sigma_db=4.0, tau_s=1.0)], SR * 600, SR, np.random.default_rng(2))
        self.assertLess(abs(db.std() - 4.0) / 4.0, 0.2)

    def test_doppler_pitch_falls_across_the_pass(self):
        v = dict(excite=dict(kind='periodic', f0=100.0, harmonics=1), resonator=dict(kind='none'), events=dict(kind='continuous'),
                 control=dict(pitch=[dict(kind='curve', points=[[0, 1.2], [2, 0.8]])]))
        x = one(v, 2.0)
        a, b = peak_freqs(x[:SR // 2], 1)[0], peak_freqs(x[-SR // 2:], 1)[0]
        self.assertGreater(a, b * 1.3)


class Pulsed(unittest.TestCase):
    def test_am_gates_a_periodic_source_into_a_pulse_train(self):
        v = dict(excite=dict(kind='periodic', f0=300.0, harmonics=8, am_hz=30.0, am_depth=1.0), resonator=dict(kind='none'), events=dict(kind='continuous'))
        x = one(v, 4.0)
        env_ = np.abs(x[:len(x) // 441 * 441]).reshape(-1, 441).mean(axis=1)
        env_ = env_ - env_.mean()
        spec = np.abs(np.fft.rfft(env_)) ** 2
        f = np.fft.rfftfreq(len(env_), 0.01)
        sel = (f > 10) & (f < 45)
        self.assertLess(abs(float(f[sel][np.argmax(spec[sel])]) - 30.0), 1.0)
        plain = one(dict(v, excite=dict(kind='periodic', f0=300.0, harmonics=8)), 4.0)
        pe = np.abs(plain[:len(plain) // 441 * 441]).reshape(-1, 441).mean(axis=1)
        self.assertGreater(env_.std() / (env_ + pe.mean()).mean(), 3 * (pe.std() / pe.mean()))      # far more modulation than the plain tone

    def test_noise_mix_breaks_up_a_pure_harmonic_tone(self):
        base = dict(excite=dict(kind='periodic', f0=200.0, harmonics=10), resonator=dict(kind='none'), events=dict(kind='continuous'))
        rough = dict(base, excite=dict(kind='periodic', f0=200.0, harmonics=10, noise_mix=0.5))

        def valley_share(v):                                  # power halfway between harmonics, relative to the power on the harmonics
            x = one(v, 2.0)
            sp = np.abs(np.fft.rfft(x)) ** 2
            f = np.fft.rfftfreq(len(x), 1 / SR)
            on = sum(sp[np.argmin(abs(f - 200.0 * k))] for k in range(1, 9))
            off = sum(sp[np.argmin(abs(f - 200.0 * (k + 0.5)))] for k in range(1, 9))
            return float(off / on)
        self.assertGreater(valley_share(rough), 20 * valley_share(base))
        self.assertTrue(sm.problems(dict(voices=[dict(excite=dict(kind='periodic', noise_mix=2.0), events=dict(kind='continuous'))])))


class Rules(unittest.TestCase):
    def test_same_seed_same_samples_different_seed_differs(self):
        m = json.load(open(next(iter(glob.glob(str(HERE.parent / 'references' / 'sound-models' / 'tin_roof_rain.json')))), encoding='utf-8'))['model']
        a, b, c = sm.render(m, SR, 4), sm.render(m, SR, 4), sm.render(m, SR, 5)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))

    def test_unknown_and_out_of_range_keys_are_errors(self):
        bad = dict(voices=[dict(excite=dict(kind='impact', tau=5.0, colour=1), resonator=dict(kind='modal', n=1000), events=dict(kind='poisson', rate=-1))])
        text = ' '.join(sm.problems(bad))
        for needle in ('colour', 'tau=5.0', 'n=1000', 'rate=-1'):
            self.assertIn(needle, text)
        with self.assertRaises(ValueError):
            sm.render(bad, SR, 1)

    def test_missing_parts_are_reported(self):
        self.assertTrue(sm.problems(dict(voices=[dict(resonator=dict(kind='none'))])))
        self.assertTrue(sm.problems(dict(voices=[dict(excite=dict(kind='friction'), events=dict(kind='poisson'))])))
        self.assertTrue(sm.problems(dict(voices=[dict(excite=dict(kind='impact'), resonator=dict(kind='modal', law='free'))])))

    def test_work_guard_refuses_a_runaway_model(self):
        v = dict(excite=dict(kind='impact', tau=0.001), resonator=dict(kind='modal', n=96, t60=8.0), events=dict(kind='poisson', rate=4000.0))
        m = dict(seconds=600.0, voices=[v] * 4)
        self.assertTrue(any('estimated work' in p for p in sm.problems(m)))

    def test_a_normal_render_is_fast_enough(self):
        m = json.load(open(HERE.parent / 'references' / 'sound-models' / 'tin_roof_rain.json', encoding='utf-8'))['model']
        t = time.time()
        sm.render(m, SR, 1)
        self.assertLess(time.time() - t, 5.0)


class CoverageSet(unittest.TestCase):
    FILES = sorted(glob.glob(str(HERE.parent / 'references' / 'sound-models' / '*.json')))

    def test_there_are_fifteen_and_all_are_valid(self):
        self.assertEqual(len(self.FILES), 15)
        for f in self.FILES:
            d = json.load(open(f, encoding='utf-8'))
            self.assertEqual(sm.problems(d['model']), [], d['name'])
            self.assertTrue(d.get('note'), d['name'])

    def test_each_renders_finite_loud_enough_and_repeatably(self):
        for f in self.FILES:
            d = json.load(open(f, encoding='utf-8'))
            a = sm.render(d['model'], SR, 2)
            self.assertTrue(np.isfinite(a).all(), d['name'])
            self.assertGreater(20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-12), -60, d['name'])
            self.assertTrue(np.array_equal(a, sm.render(d['model'], SR, 2)), d['name'])

    def test_physical_targets_of_the_set(self):
        load = lambda n: json.load(open(HERE.parent / 'references' / 'sound-models' / f'{n}.json', encoding='utf-8'))['model']
        # bouncing ball: onsets shrink by 0.7
        ev = load('bouncing_ball')['voices'][0]['events']
        t, _ = sm.event_times(dict(sm._d(ev, sm.EVENTS), kind='bounce'), 3.5, np.random.default_rng(0))
        self.assertAlmostEqual(float(np.diff(t)[2] / np.diff(t)[1]), 0.7, places=6)
        # clock: one tick and one tock per second
        x = sm.render(load('clock_tick'), SR, 1)
        env_ = np.abs(x[:len(x) // 441 * 441]).reshape(-1, 441).max(axis=1)           # 10 ms blocks, so a ringing tick counts once
        hits = np.flatnonzero((env_ > 0.3 * env_.max()) & (np.r_[0, env_[:-1]] <= 0.3 * env_.max()))
        self.assertTrue(7 <= len(hits) <= 9, len(hits))
        # car pass: loudest near 4 s, pitch lower after the pass
        c = sm.render(load('car_pass'), SR, 1)
        blocks = np.sqrt(np.mean(c[:len(c) // SR * SR].reshape(-1, SR) ** 2, axis=1))
        self.assertIn(int(np.argmax(blocks)), (3, 4))
        # boiling water: bubble tones sit in the Minnaert range for 1 to 6 mm radius (540 to 3300 Hz)
        w = sm.render(dict(load('boiling_water'), voices=load('boiling_water')['voices'][:1]), SR, 1)
        spec = np.abs(np.fft.rfft(w)) ** 2
        f = np.fft.rfftfreq(len(w), 1 / SR)
        self.assertGreater(spec[(f > 500) & (f < 4000)].sum() / spec.sum(), 0.8)
        # thunder: energy is mostly below 300 Hz after the crack
        th = sm.render(load('thunder'), SR, 1)[SR:]
        s = np.abs(np.fft.rfft(th)) ** 2
        ff = np.fft.rfftfreq(len(th), 1 / SR)
        self.assertGreater(s[ff < 300].sum() / s.sum(), 0.9)


class WiredIn(unittest.TestCase):
    def test_sfx_make_renders_a_model_preset(self):
        import presets
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / 'presets' / 'sfx').mkdir(parents=True)
            model = json.load(open(HERE.parent / 'references' / 'sound-models' / 'glass_break.json', encoding='utf-8'))['model']
            (Path(td) / 'presets' / 'sfx' / 'glass_x.json').write_text(json.dumps(dict(name='glass_x', character='x', model=model)), encoding='utf-8')
            presets.PROJECT_ROOTS.clear()
            presets.add_project(td)
            try:
                a, src, _ = sfx.make('glass_x', 1.6, SR, 3)
                b, _, _ = sfx.make('glass_x', 1.6, SR, 3)
                self.assertEqual(src, 'preset')
                self.assertTrue(np.array_equal(a, b))
                self.assertLessEqual(float(np.abs(a).max()), 0.9001)
                (Path(td) / 'presets' / 'sfx' / 'bad.json').write_text(
                    json.dumps(dict(name='bad', character='x', model=dict(voices=[dict(excite=dict(kind='impact', colour=1))]))), encoding='utf-8')
                with self.assertRaises(ValueError):
                    sfx.make('bad', 1.0, SR, 1)
            finally:
                presets.PROJECT_ROOTS.clear()

    def test_environment_model_layer_renders_and_validates(self):
        voices = json.load(open(HERE.parent / 'references' / 'sound-models' / 'leaf_rain.json', encoding='utf-8'))['model']['voices']
        cfg = {'layers': [dict(primitive='model_layer', kind='bed', gain_db=-18, voices=voices)]}
        self.assertEqual(env.preset_problems(cfg), [])
        a = env.render_environment_preset(cfg, duration_s=3, seed=4)
        b = env.render_environment_preset(cfg, duration_s=3, seed=4)
        self.assertTrue(np.isfinite(a).all() and np.array_equal(a, b))
        self.assertGreater(float(np.abs(a).max()), 0.001)
        bad = {'layers': [dict(primitive='model_layer', voices=[dict(excite=dict(kind='impact', tau=9))])]}
        self.assertTrue(env.preset_problems(bad))


class Fit(unittest.TestCase):
    def test_fit_recovers_a_known_pitch_and_never_edits_the_original(self):
        import tempfile
        import ambience_reference as ar
        import sound_fit
        import soundfile as sf

        def model(f1, t60):
            return dict(seconds=4.0, voices=[dict(excite=dict(kind='impact', tau=0.0004), resonator=dict(kind='modal', law='power', f1=f1, n=6, t60=t60, exponent=1.4),
                                                  events=dict(kind='poisson', rate=120.0), vary=dict(size=dict(dist='lognormal', sigma=0.1), pitch_exp=1.0, amp_exp=1.0))])
        truth = sm.render(model(2400.0, 0.06), SR, 9)
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / 'real.wav'
            sf.write(str(wav), (truth / np.abs(truth).max() * 0.5).astype(np.float32), SR)
            ar.measure_file(str(wav), 'plate', td)
            refs = ar.load_refs(td, 'plate')
            start = model(900.0, 0.06)
            start['free'] = {'voices.0.resonator.f1': [300.0, 6000.0]}
            before = json.dumps(start, sort_keys=True)
            fitted, rep = sound_fit.fit(start, refs, start['free'], seed=1, sweeps=4, seconds=4.0, texture=False)
            self.assertEqual(json.dumps(start, sort_keys=True), before)                     # the input model is untouched
            self.assertTrue(rep['improved'] and rep['distance_after'] < rep['distance_before'])
            f_new = sm.get_path(fitted, 'voices.0.resonator.f1')
            self.assertLess(abs(f_new - 2400.0), abs(900.0 - 2400.0) * 0.5, f_new)          # moved at least half way toward the truth
            self.assertTrue(rep['weak_anchor'])                                             # one recording is called a weak anchor
            again, rep2 = sound_fit.fit(start, refs, start['free'], seed=1, sweeps=4, seconds=4.0, texture=False)
            self.assertEqual(sm.get_path(again, 'voices.0.resonator.f1'), f_new)           # same inputs, same answer

    def test_free_parameters_are_validated(self):
        m = dict(seconds=1.0, voices=[dict(excite=dict(kind='impact'), resonator=dict(kind='modal', f1=500.0))],
                 free={'voices.0.resonator.f1': [100.0, 400.0], 'voices.0.resonator.nope': [1.0, 2.0], 'voices.0.excite.kind': [1.0, 2.0]})
        text = ' '.join(sm.problems(m))
        self.assertIn('outside its range', text)
        self.assertIn('no such parameter', text)
        self.assertIn('not a number', text)

    def test_texture_statistics_tell_a_sparse_texture_from_a_steady_one(self):
        import ambience_reference as ar
        rng = np.random.default_rng(1)
        steady = rng.standard_normal(SR * 4)
        sparse = np.zeros(SR * 4)
        sparse[rng.integers(0, SR * 4, 60)] = 1.0
        sparse = np.convolve(sparse, np.exp(-np.arange(400) / 40.0) * rng.standard_normal(400), 'same')
        a, b = ar.texture_stats(steady, SR), ar.texture_stats(sparse, SR)
        self.assertGreater(np.mean(b['kurtosis']), np.mean(a['kurtosis']) * 1.5)
        self.assertEqual(ar.texture_distance(a, a)['total'], 0.0)
        self.assertGreater(ar.texture_distance(a, b)['total'], 0.1)

    def test_modal_fit_finds_the_frequencies_and_decay_of_a_struck_object(self):
        import ambience_reference as ar
        x = sm.render(dict(seconds=1.5, voices=[dict(excite=dict(kind='impact', tau=0.0002),
                      resonator=dict(kind='modal', law='bar', f1=500.0, n=3, t60=0.5, damp_exp=0.0), events=dict(kind='single'))]), SR, 1)
        modes = ar.modal_fit(x, SR, 3)
        want = [500.0, 500 * 2.757, 500 * 5.404]
        for m, w in zip(modes, want):
            self.assertLess(abs(m['f_hz'] - w) / w, 0.03, modes)
        self.assertLess(abs(modes[0]['t60_s'] - 0.5) / 0.5, 0.3, modes)


if __name__ == '__main__':
    unittest.main()
