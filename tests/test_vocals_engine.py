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

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'scripts')]
import vocals  # noqa: E402

SR = 44100


class LegacyApi(unittest.TestCase):
    """Names and shapes other modules depend on must survive the upgrade."""

    def test_public_names(self):
        for n in ('sing', 'render_choir', 'add_vocal_harmonies', 'add_vocal_chorus',
                  'apply_vocal_dsp', 'VOCAL_STYLES', 'VOWELS', 'INSTRUMENTS'):
            self.assertTrue(hasattr(vocals, n), n)
        self.assertEqual(vocals.INSTRUMENTS, {'choir_formant', 'hum_formant', 'voice_formant',
                                              'throat_formant', 'chant_formant'})
        for s in ('tuvan_kargyraa', 'tuvan_sygyt', 'bulgarian_chant', 'nordic_kulning',
                  'qawwali_devotional', 'gregorian_monastic', 'african_polyphony', 'classical_choir'):
            self.assertIn(s, vocals.VOCAL_STYLES)

    def test_render_choir_shape_dtype(self):
        y = vocals.render_choir([dict(t=0.0, dur=0.5, p=60, v=90)], sr=SR, voices=2, seed=1)
        self.assertEqual(y.ndim, 2)
        self.assertEqual(y.shape[1], 2)
        self.assertEqual(y.dtype, np.float32)

    def test_empty_events(self):
        y = vocals.render_choir([], sr=SR)
        self.assertEqual(y.shape[1], 2)
        self.assertTrue(np.isfinite(y).all())

    def test_seed_reproducible(self):
        ev = [dict(t=0.0, dur=0.6, p=62, v=80)]
        a = vocals.render_choir(ev, sr=SR, voices=3, seed=5)
        b = vocals.render_choir(ev, sr=SR, voices=3, seed=5)
        c = vocals.render_choir(ev, sr=SR, voices=3, seed=6)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))


from scipy.signal import freqz  # noqa: E402
from vocal_engine import data, nasal, source, tract, voice  # noqa: E402


def _band(y, sr, lo, hi, skip=0.4):
    y = y[int(skip * sr):]
    s = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    fr = np.fft.rfftfreq(len(y), 1 / sr)
    return float(s[(fr >= lo) & (fr < hi)].sum()), float(s.sum())


def _syn(sr=SR, f0=150.0, dur=2.0, seed=1, cfg=None, **kw):
    cfg = cfg or data.defaults()
    y, _ = voice.synth(np.full(int(sr * dur), f0), sr, np.random.default_rng(seed), cfg, **kw)
    return y


class CoreSynthesis(unittest.TestCase):
    def test_resonator_unity_gain_at_centre_all_rates(self):
        for sr in (22050, 44100, 48000, 96000):
            for f, bw in ((250, 70), (730, 90), (2440, 150), (3300, 45)):
                A, B, C = tract.coefs(f, bw, sr)
                _, h = freqz([A], [1, -B, -C], worN=[2 * np.pi * f / sr])
                self.assertAlmostEqual(abs(h[0]), 1.0, places=6, msg=(sr, f, bw))

    def test_resonator_stable_and_finite_on_noise(self):
        x = np.random.default_rng(0).standard_normal(SR)
        for f, bw in ((20, 5), (100, 10), (20000, 5), (0.45 * SR, 1)):
            y = tract.resonate(x, f, bw, SR)
            self.assertTrue(np.isfinite(y).all() and np.abs(y).max() < 1e4)

    def test_phase_is_continuous_across_calls(self):
        f0 = np.linspace(120, 180, 2000)
        whole = source.cycles(f0, SR)
        a = source.cycles(f0[:1000], SR)
        b = source.cycles(f0[1000:], SR, phase0=a[-1])
        self.assertTrue(np.allclose(whole, np.concatenate([a, b])))

    def test_glottal_flow_bounded_and_closes(self):
        phi = np.linspace(0, 1, 1000, endpoint=False)
        for oq in (0.4, 0.6, 0.85):
            g = source.pulse(phi, oq, 2.0, 0.3)
            self.assertTrue(g.min() >= 0 and g.max() <= 1.0 + 1e-9)
            self.assertEqual(float(g[phi > oq + 1e-3].max()), 0.0)

    def test_vowel_formants_shape_spectrum(self):
        ya, yi = _syn(f0=100, formants=data.defaults()['tract']['vowels']['a']), _syn(f0=100, formants=data.defaults()['tract']['vowels']['i'])
        lo_a, tot_a = _band(ya, SR, 600, 900)
        lo_i, tot_i = _band(yi, SR, 600, 900)
        self.assertGreater(lo_a / tot_a, 3 * lo_i / tot_i)      # F1 730 vs 270
        yu = _syn(f0=100, formants=data.defaults()['tract']['vowels']['u'])
        hi_i, _ = _band(yi, SR, 1500, 4000)
        hi_u, tot_u = _band(yu, SR, 1500, 4000)
        self.assertGreater(hi_i / tot_i, 1.5 * hi_u / tot_u)     # F2 2290 (/i/) vs 870 (/u/)

    def test_register_changes_harmonic_balance(self):
        c = data.defaults()
        hi = {}
        for r in ('chest', 'falsetto'):
            y = _syn(cfg=c, register=r, formants=c['tract']['vowels']['a'])
            h, tot = _band(y, SR, 1500, 8000)
            hi[r] = h / tot
        self.assertGreater(hi['chest'], 2 * hi['falsetto'])

    def test_hum_is_dark_and_murmur_heavy(self):
        c = data.defaults()
        h = _syn(cfg=c, hum=True)
        a = _syn(cfg=c, formants=c['tract']['vowels']['a'])
        self.assertLess(_band(h, SR, 1500, 20000)[0] / _band(h, SR, 0, 20000)[0],
                        _band(a, SR, 1500, 20000)[0] / _band(a, SR, 0, 20000)[0])
        self.assertGreater(_band(h, SR, 0, 500)[0] / _band(h, SR, 0, 20000)[0], 0.9)

    def test_hum_antiformant_notch_removes_energy(self):
        c0, c1 = data.defaults(), data.defaults()
        c0['humming']['antiformant_depth'] = 0.0
        c0['humming']['oral_coupling'] = c1['humming']['oral_coupling'] = 0.0
        # f0 chosen so a harmonic sits on the notch (1000 Hz = 8 x 125)
        e0 = _band(_syn(cfg=c0, f0=125, hum=True, breathiness=0.0), SR, 900, 1100)[0]
        e1 = _band(_syn(cfg=c1, f0=125, hum=True, breathiness=0.0), SR, 900, 1100)[0]
        self.assertLess(e1, 0.25 * e0)

    def test_hum_brightness_and_lip_closure(self):
        dark, bright = data.defaults(), data.defaults()
        dark['humming']['brightness'], bright['humming']['brightness'] = 0.1, 0.9
        d = _band(_syn(cfg=dark, hum=True), SR, 800, 20000)
        b = _band(_syn(cfg=bright, hum=True), SR, 800, 20000)
        self.assertGreater(b[0] / b[1], 3 * d[0] / d[1])

    def test_nasalize_adds_low_pole_and_notch(self):
        c = data.defaults()
        plain = _syn(cfg=c, formants=c['tract']['vowels']['a'], breathiness=0.0)
        nas = _syn(cfg=c, formants=c['tract']['vowels']['a'], breathiness=0.0, nasality=1.0)
        self.assertNotAlmostEqual(float(np.abs(plain - nas).mean()), 0.0, places=3)
        self.assertTrue(np.isfinite(nas).all())

    def test_moving_formants_and_f0_are_finite_and_click_free(self):
        c = data.defaults()
        n = SR * 2
        f0 = 150 * 2 ** (np.linspace(0, 1, n) * 0.5)
        F = np.stack([np.linspace(730, 270, n), np.linspace(1090, 2290, n), np.full(n, 2440.0)])
        y, _ = voice.synth(f0, SR, np.random.default_rng(2), c, formants=F)
        self.assertTrue(np.isfinite(y).all())
        self.assertLess(np.abs(np.diff(y)).max(), 6 * y.std())

    def test_style_flags_run(self):
        c = data.defaults()
        for st in ({'subharmonic': True}, {'whistle_overtone': True}, {'harmonic_lock': True}):
            y = _syn(cfg=c, style=st, formants=(650, 1600, 2700))
            self.assertTrue(np.isfinite(y).all() and y.std() > 0)

    def test_same_seed_same_signal(self):
        self.assertTrue(np.array_equal(_syn(seed=3, hum=True), _syn(seed=3, hum=True)))
        self.assertFalse(np.array_equal(_syn(seed=3, hum=True), _syn(seed=4, hum=True)))


from vocal_engine import performance as pf  # noqa: E402


def _flat_cfg(**over):
    """No random pitch motion, so pitch assertions are tight."""
    c = data.defaults()
    c['vibrato']['depth_cents'] = 0.0
    c['performance'].update(drift_cents=0.0, jitter_cents=0.0, arch_cents=0.0, end_sag_cents=0.0)
    for k, v in over.items():
        c[k].update(v)
    return c


def _phrase(notes, cfg=None, hum=True, seed=1):
    return pf.render_phrase(notes, SR, np.random.default_rng(seed), cfg or data.defaults(), hum=hum)


def _cents(f):
    return 1200 * np.log2(f / 440.0) + 6900


MEL = [dict(t=0.0, dur=1.0, p=62, v=80), dict(t=1.0, dur=1.0, p=65, v=80), dict(t=2.0, dur=1.0, p=64, v=80)]


class PhraseEngine(unittest.TestCase):
    def test_pitch_reaches_note_targets(self):
        r = _phrase(MEL, _flat_cfg(performance=dict(overshoot_cents=0.0)))
        for e in MEL:
            c = _cents(r['f0'][int((e['t'] + 0.8 * e['dur']) * SR)])
            self.assertLess(abs(c - e['p'] * 100), 12, e)

    def test_connected_notes_glide_through_intermediate_pitches(self):
        r = _phrase(MEL, _flat_cfg(performance=dict(overshoot_cents=0.0)))
        seg = _cents(r['f0'][int(0.9 * SR):int(1.2 * SR)])
        mid = seg[(seg > 6200 + 60) & (seg < 6500 - 60)]
        self.assertGreater(len(mid), int(0.02 * SR))                  # a real portamento, not a jump
        self.assertTrue(np.all(np.diff(seg) > -0.5))                  # monotonic when overshoot is off

    def test_overshoot_then_settles(self):
        r = _phrase(MEL, _flat_cfg(performance=dict(overshoot_cents=15.0, overshoot_frac=0.3)))
        seg = _cents(r['f0'][int(1.0 * SR):int(1.6 * SR)])
        self.assertGreater(seg.max(), 6500 + 5)
        self.assertLess(abs(seg[-1] - 6500), 3)

    def test_joins_have_no_click(self):
        for hum in (True, False):
            r = _phrase(MEL, hum=hum)
            y = r['signal']
            self.assertTrue(np.isfinite(y).all())
            self.assertLess(np.abs(np.diff(y)).max(), 0.8 * y.std())
            for j in (1.0, 2.0):                                    # envelope has no step at the joins
                w = np.abs(y[int((j - 0.01) * SR):int((j + 0.01) * SR)])
                self.assertLess(w.max(), 3 * np.abs(y[int((j - 0.3) * SR):int((j - 0.1) * SR)]).max())

    def test_legato_keeps_voice_detached_breaks_it(self):
        leg = _phrase(MEL)
        det = _phrase([dict(e, art='detached') for e in MEL])
        j = int(1.0 * SR)
        self.assertGreater(leg['gate'][j - 2000:j + 2000].min(), 0.7)
        self.assertLess(det['gate'][j - 2500:j + 500].min(), 0.05)

    def test_velocity_sets_level_without_per_note_normalisation(self):
        soft = _phrase([dict(t=0, dur=2.0, p=60, v=40)])['signal']
        loud = _phrase([dict(t=0, dur=2.0, p=60, v=110)])['signal']
        ratio = np.sqrt(np.mean(loud ** 2) / np.mean(soft ** 2))
        self.assertGreater(ratio, 2.0)
        self.assertLess(ratio, 3.6)                                   # 110/40 = 2.75

    def test_same_velocity_gives_same_level_across_pitches(self):
        """Harmonics landing near a formant must not make some pitches 6 dB louder (singers even that out).
        Phrase dynamics are switched off here on purpose: this test measures pitch calibration, not expression."""
        for hum in (True, False):
            ev = [dict(t=i * 1.2, dur=1.2, p=p, v=90) for i, p in enumerate((60, 62, 65, 67, 64))]
            c0 = data.defaults()
            c0['phrasing']['amount'] = 0.0
            r = _phrase(ev, c0, hum=hum)
            rms = np.array(r['note_rms'])
            self.assertLess(20 * np.log10(rms.max() / rms.min()), 3.0, (hum, rms))
            c = data.defaults()
            c['phrasing']['amount'] = 0.0
            c['dynamics']['pitch_compensation'] = 0.0
            r0 = _phrase(ev, c, hum=hum)
            self.assertGreater(np.ptp(20 * np.log10(r0['note_rms'])), np.ptp(20 * np.log10(rms)))   # the switch does something

    def test_vibrato_develops_over_a_held_note(self):
        c = data.defaults()
        c['performance'].update(drift_cents=0.0, jitter_cents=0.0, arch_cents=0.0, end_sag_cents=0.0)
        c['vibrato'].update(depth_cents=30.0, delay_s=0.4, onset_s=0.8)
        r = _phrase([dict(t=0, dur=3.0, p=60, v=80)], c)
        cs = _cents(r['f0'])
        early, late = cs[int(0.05 * SR):int(0.3 * SR)].std(), cs[int(1.6 * SR):int(2.4 * SR)].std()
        self.assertLess(early, 0.2 * late)
        self.assertGreater(late, 10)

    def test_vibrato_phase_continues_across_notes(self):
        c = data.defaults()
        c['performance'].update(drift_cents=0.0, jitter_cents=0.0, arch_cents=0.0, end_sag_cents=0.0,
                                overshoot_cents=0.0)
        c['vibrato'].update(depth_cents=30.0, delay_s=0.0, onset_s=0.01, carry_floor=1.0)
        r = _phrase([dict(t=0, dur=2.0, p=60), dict(t=2.0, dur=2.0, p=60)], c)
        cs = _cents(r['f0']) - 6000
        self.assertLess(np.abs(cs[int(2.0 * SR) - 5] - cs[int(2.0 * SR) + 5]), 3.0)

    def test_steady_note_pitch_measured_from_audio(self):
        r = _phrase([dict(t=0, dur=2.0, p=55, v=90)], _flat_cfg())
        y = r['signal'][int(0.6 * SR):int(1.4 * SR)]
        ac = np.correlate(y, y, 'full')[len(y) - 1:]
        lo, hi = int(SR / 260), int(SR / 150)
        f = SR / (lo + int(np.argmax(ac[lo:hi])))
        self.assertLess(abs(1200 * np.log2(f / 196.0)), 25)           # G3 = 196 Hz

    def test_edge_cases_finite(self):
        for notes in ([dict(t=0, dur=0.004, p=60)],                                   # shorter than any ramp
                      [dict(t=0, dur=1.0, p=28), dict(t=0.5, dur=1.0, p=31)],          # overlap, very low
                      [dict(t=0, dur=1.0, p=96, v=127), dict(t=1.0, dur=0.3, p=100)],  # very high
                      [dict(t=0, dur=0.3, p=60, art='non_legato'), dict(t=0.3, dur=0.3, p=62, art='non_legato')]):
            for hum in (True, False):
                y = _phrase(notes, hum=hum)['signal']
                self.assertTrue(np.isfinite(y).all() and len(y) > 0)

    def test_phrase_is_deterministic(self):
        a, b = _phrase(MEL, seed=4)['signal'], _phrase(MEL, seed=4)['signal']
        self.assertTrue(np.array_equal(a, b))

    def test_split_lines_and_phrases(self):
        chord = [dict(t=0, dur=1, p=57), dict(t=0, dur=1, p=60), dict(t=0, dur=1, p=64), dict(t=1, dur=1, p=57)]
        lines = pf.split_lines(chord)
        self.assertEqual(sorted(len(l) for l in lines), [1, 1, 2])
        ph = pf.split_phrases([dict(t=0, dur=1, p=60), dict(t=1.1, dur=1, p=62), dict(t=3.0, dur=1, p=60)], data.defaults())
        self.assertEqual([len(p) for p in ph], [2, 1])


from vocal_engine import breath, expression, singer  # noqa: E402

LONG = [dict(t=0.0, dur=2.5, p=60, v=80), dict(t=2.5, dur=2.5, p=64, v=80)]


class Expression(unittest.TestCase):
    def test_all_profiles_load_and_touch_several_sections(self):
        names = expression.names()
        for n in ('gentle', 'reflective', 'melancholic', 'hopeful', 'ethereal', 'cinematic', 'devotional',
                  'powerful', 'intimate', 'mysterious'):
            self.assertIn(n, names)
            base = data.defaults()
            out = expression.apply(base, n)
            changed = {k for k in base if isinstance(base[k], dict) and out[k] != base[k]}
            self.assertGreaterEqual(len(changed), 3, (n, changed))         # not a single volume knob

    def test_intensity_blends_numbers(self):
        base = data.defaults()
        full, half, zero = (expression.apply(base, 'powerful', w) for w in (1.0, 0.5, 0.0))
        a0, a1 = base['articulation']['attack_ms'], full['articulation']['attack_ms']
        self.assertAlmostEqual(half['articulation']['attack_ms'], (a0 + a1) / 2)
        self.assertEqual(zero['articulation'], base['articulation'])
        self.assertEqual(expression.apply(base, ''), base)
        with self.assertRaises(KeyError):
            expression.apply(base, 'nope')

    def test_profiles_change_the_sound_in_more_than_level(self):
        res = {}
        for n in ('powerful', 'ethereal'):
            c = expression.apply(data.defaults(), n)
            r = _phrase([dict(t=0, dur=3.0, p=60, v=80)], c, hum=False, seed=2)
            cs = _cents(r['f0'])
            att = int(np.argmax(r['gate'] > 0.5)) / SR
            res[n] = dict(att=att, vib=cs[int(2.0 * SR):int(2.8 * SR)].std(), hf=_band(r['signal'], SR, 3000, 12000)[0]
                          / _band(r['signal'], SR, 0, 12000)[0])
        self.assertGreater(res['ethereal']['att'], 1.8 * res['powerful']['att'])
        self.assertGreater(res['powerful']['vib'], 1.5 * res['ethereal']['vib'])
        self.assertNotAlmostEqual(res['powerful']['hf'], res['ethereal']['hf'], places=4)


class Breathing(unittest.TestCase):
    def test_exhaustion_drops_level_and_adds_breath(self):
        c = data.defaults()
        c['breathing'].update(capacity_s=4.0, exhaust_start=0.5, pressure_drop_db=6.0, exhaust_breath=4.0)
        c['dynamics'].update(phrase_arc_db=0.0, flutter=0.0)
        r = _phrase([dict(t=0, dur=5.5, p=60, v=90)], c, hum=False)
        y = r['signal']
        early, late = y[int(0.8 * SR):int(1.4 * SR)], y[int(4.6 * SR):int(5.0 * SR)]
        self.assertLess(np.sqrt(np.mean(late ** 2)), 0.7 * np.sqrt(np.mean(early ** 2)))
        n = len(y)
        br = breath.aspiration_track(n, SR, 0.03, c['breathing'], [])
        self.assertGreater(br[int(5.0 * SR)], 2.5 * br[0])

    def test_aspirated_onset(self):
        n = SR
        br = breath.aspiration_track(n, SR, 0.02, data.defaults()['breathing'], [1000])
        self.assertGreater(br[1000], br[999] + 0.03)
        self.assertAlmostEqual(br[-1], 0.02, places=3)

    def test_inhale_is_banded_finite_and_scaled(self):
        B = data.defaults()['breathing']
        x = breath.inhale(SR, np.random.default_rng(0), B, 0.1)
        self.assertTrue(np.isfinite(x).all())
        self.assertAlmostEqual(float(np.sqrt(np.mean(x ** 2))) / (B['inhale_gain'] * 0.1), 1.0, delta=0.6)
        lo, tot = _band(x, SR, 0, 200, skip=0.0)[0], _band(x, SR, 0, 20000, skip=0.0)[0]
        self.assertLess(lo / tot, 0.05)

    def test_inhale_has_a_body_and_turbulent_air_not_a_flat_hiss(self):
        """A breath reads as air when its low body dominates and its level flutters. A single two-pole band of
        steady white noise (the first design) is what sounds like a sheet being scratched."""
        B = data.defaults()['breathing']
        x = breath.inhale(SR, np.random.default_rng(3), B, 0.1)
        body = _band(x, SR, 200, 900, skip=0.0)[0]      # the event is shorter than the default 0.4 s skip
        air = _band(x, SR, 2000, 6000, skip=0.0)[0]
        self.assertGreater(body, air, (body, air))
        frames = len(x) // 512
        rms = np.sqrt(np.mean(x[:frames * 512].reshape(frames, 512) ** 2, axis=1) + 1e-20)
        steady = rms[len(rms) // 4: -len(rms) // 4]
        self.assertGreater(float(np.std(steady) / (np.mean(steady) + 1e-12)), 0.02)   # flutter, not a constant level

    def test_breath_is_continuous_air_not_a_burst_in_silence(self):
        """The whole point of the airflow bed: a gap is air at a floor, not digital silence followed by a burst."""
        B = data.defaults()['breathing']
        spans = [(0.0, 1.2), (3.4, 4.6), (7.0, 8.2)]
        n = int(9.0 * SR)
        x = breath.bed(SR, np.random.default_rng(1), B, 0.1, spans, n)
        frames = n // 1024
        e = np.sqrt(np.mean(x[:frames * 1024].reshape(frames, 1024) ** 2, axis=1) + 1e-20)
        gap = e[int(1.3 * SR / 1024):int(3.3 * SR / 1024)]
        self.assertGreater(float(gap.min()), 1e-6)                      # never zero inside the gap
        self.assertGreater(float(gap.min()), float(e.max()) * 1e-3)     # air, well above the noise floor of nothing
        steps = np.abs(np.diff(20 * np.log10(e + 1e-12)))
        self.assertLess(float(steps.max()), 8.0, float(steps.max()))    # no 23 ms jump that reads as an object
        peak_gap = 20 * np.log10(float(gap.max()) + 1e-12)
        self.assertLess(peak_gap, -10.0)                                # a breath, not a note

    def test_plan_inhales_needs_room(self):
        B = data.defaults()['breathing']
        plan = breath.plan_inhales_detailed([(0.0, 3.0), (3.1, 5.0), (6.0, 8.0)], B)
        self.assertEqual(len(plan), 1)                       # no room at t=0, 0.1 s gap too short, 1 s gap ok
        self.assertAlmostEqual(plan[0]['end'], 6.0 - B['inhale_lead_ms'] * 1e-3)

    def test_release_puff_decays(self):
        B = data.defaults()['breathing']
        x = breath.release_puff(SR, np.random.default_rng(0), B, 0.1)
        h = len(x) // 2
        self.assertGreater(np.abs(x[:h]).mean(), 2 * np.abs(x[h:]).mean())

    def test_phrase_reports_times_for_the_ensemble(self):
        r = _phrase(MEL)
        self.assertAlmostEqual(r['t0'], 0.0)
        self.assertGreater(r['t1'], r['voiced_end'])


class Singers(unittest.TestCase):
    def test_deterministic_and_seed_dependent(self):
        c = data.defaults()
        a1, _ = singer.make_singer(c, 2, seed=5)
        a2, _ = singer.make_singer(c, 2, seed=5)
        b, _ = singer.make_singer(c, 2, seed=6)
        self.assertEqual(a1, a2)
        self.assertNotEqual(a1['vibrato']['rate_hz'], b['vibrato']['rate_hz'])

    def test_singers_differ_and_diversity_zero_collapses(self):
        c = data.defaults()
        rates = {singer.make_singer(c, i, 3)[0]['vibrato']['rate_hz'] for i in range(5)}
        self.assertEqual(len(rates), 5)
        same = {singer.make_singer(c, i, 3, diversity=0.0)[0]['vibrato']['rate_hz'] for i in range(5)}
        self.assertEqual(same, {c['vibrato']['rate_hz']})
        self.assertEqual(c, data.defaults())                 # input untouched

    def test_explicit_singer_overrides_win(self):
        c = data.defaults()
        c['ensemble']['singers'] = [{'vibrato': {'rate_hz': 4.0}}, {'source': {'register': 'chest'}}]
        self.assertEqual(singer.make_singer(c, 0, 1)[0]['vibrato']['rate_hz'], 4.0)
        self.assertEqual(singer.make_singer(c, 3, 1)[0]['source']['register'], 'chest')    # wraps

    def test_five_singers_do_not_sound_like_one_copied(self):
        c = data.defaults()
        sig = []
        for i in range(5):
            sc, _ = singer.make_singer(c, i, 11)
            sig.append(_phrase(MEL, sc, seed=100 + i)['signal'])
        L = min(len(s) for s in sig)
        M = np.corrcoef(np.stack([s[:L] for s in sig]))
        off = M[np.triu_indices(5, 1)]
        self.assertLess(np.abs(off).max(), 0.5)
        f0m = [np.mean(_phrase(MEL, singer.make_singer(c, i, 11)[0], seed=100 + i)['f0']) for i in range(5)]
        self.assertGreater(np.std(f0m), 0.1)                 # different tuning


from vocal_engine import ensemble  # noqa: E402

PH = [dict(t=0.0, dur=1.0, p=60, v=90), dict(t=1.0, dur=1.0, p=64, v=90), dict(t=3.5, dur=1.5, p=62, v=90)]


def _ens(events=PH, sr=SR, seed=1, voices=3, hum=True, stems=False, **ens):
    c = data.defaults()
    c['ensemble'].update(ens)
    return ensemble.render(events, sr, c, seed=seed, hum=hum, voices=voices, stems=stems)


class Ensemble(unittest.TestCase):
    def test_shape_levels_dc_and_finite_for_many_voice_counts(self):
        for v in (1, 2, 5, 16):
            y = _ens(voices=v)
            self.assertEqual(y.shape[1], 2)
            self.assertEqual(y.dtype, np.float32)
            self.assertTrue(np.isfinite(y).all())
            self.assertLessEqual(np.abs(y).max(), 1.0)
            self.assertGreater(np.abs(y).max(), 0.02)
            self.assertLess(np.abs(y.mean(0)).max(), 1e-3)

    def test_sample_rates_and_empty(self):
        for sr in (22050, 44100, 48000):
            y = _ens(sr=sr, voices=2)
            self.assertTrue(np.isfinite(y).all() and len(y) > 5 * sr)
        e = _ens(events=[], voices=3)
        self.assertEqual(e.shape[1], 2)
        self.assertEqual(float(np.abs(e).max()), 0.0)

    def test_seed_reproducible_and_changes(self):
        self.assertTrue(np.array_equal(_ens(seed=3), _ens(seed=3)))
        self.assertFalse(np.array_equal(_ens(seed=3), _ens(seed=4)))

    def test_stems_metadata_and_stereo_independence(self):
        y, info = _ens(voices=5, stems=True)
        self.assertEqual(len(info['stems']), 5)
        self.assertEqual(len(info['voices']), 5)
        self.assertEqual(len(info['breath_stems']), 5)
        az = [v['azimuth_deg'] for v in info['voices']]
        self.assertEqual(az, sorted(az))
        self.assertLess(az[0], 0)
        self.assertGreater(az[-1], 0)
        self.assertTrue(all(v['distance_m'] >= 0.3 for v in info['voices']))
        self.assertGreater(np.abs(y[:, 0] - y[:, 1]).mean(), 1e-3)
        M = np.corrcoef(np.stack(info['stems']))
        self.assertLess(np.abs(M[np.triu_indices(5, 1)]).max(), 0.6)        # not one voice copied

    def test_stems_sum_to_mix_before_pan_and_breath(self):
        y, info = _ens(voices=1, stems=True)
        mono = info['stems'][0] + info['breath_stems'][0]
        self.assertTrue(np.allclose(y[:, 0], y[:, 1], atol=1e-4))          # centre voice
        self.assertGreater(np.corrcoef(y[:, 0], mono)[0, 1], 0.99)

    def test_cohesion_controls_timing_and_pitch_spread(self):
        def spread(coh):
            _, info = _ens(voices=7, stems=True, cohesion=coh, timing_spread_ms=60.0, pitch_spread_cents=20.0)
            onsets = [int(np.argmax(np.abs(s) > 0.2 * np.abs(s).max())) / SR for s in info['stems']]
            return np.std(onsets), np.ptp([v['detune_cents'] for v in info['voices']])
        t_tight, p_tight = spread(1.0)
        t_loose, p_loose = spread(0.0)
        self.assertLess(p_tight, 1e-9)
        self.assertGreater(p_loose, 10)
        self.assertGreater(t_loose, t_tight)

    def test_chords_become_lines_and_hum_vowel_mix_renders(self):
        chord = [dict(t=0, dur=2, p=57), dict(t=0, dur=2, p=60), dict(t=0, dur=2, p=64),
                 dict(t=2, dur=2, p=62, vowel='a'), dict(t=4.2, dur=1, p=60, vowel='m')]
        y = _ens(events=chord, voices=2, hum=False)
        self.assertTrue(np.isfinite(y).all() and np.abs(y).max() > 0.02)

    def test_breath_stem_has_inhale_in_the_gap_not_at_zero(self):
        c = data.defaults()
        c['phrasing']['amount'] = 0.0            # isolate the inhale: the onset puff is a separate, later feature
        c['ensemble']['voices'] = 1
        _, info = ensemble.render(PH, SR, c, seed=1, hum=True, stems=True)
        b = info['breath_stems'][0]
        self.assertGreater(np.abs(b[int(2.8 * SR):int(3.5 * SR)]).max(), 0.0)    # gap before the third note
        # the bed is air, not an event: at t=0 it may only sit on the room floor, never at a breath's level
        self.assertLess(float(np.abs(b[:int(0.05 * SR)]).max()),
                        float(np.abs(b[int(2.8 * SR):int(3.5 * SR)]).max()) * 0.6)

    def test_breath_sits_well_under_the_voice_and_adds_no_clicks(self):
        """An inhale louder than the sung tone (the first default was) is the opposite of natural breath."""
        ev = [dict(t=0.0, dur=1.2, p=62, v=70), dict(t=1.2, dur=1.2, p=65, v=76), dict(t=3.5, dur=1.5, p=62, v=80)]
        y, info = _ens(events=ev, voices=1, stems=True)
        voice, br = info['stems'][0], info['breath_stems'][0]
        self.assertGreater(np.abs(br).max(), 0.0)
        self.assertLess(np.abs(br).max(), 0.35 * np.abs(voice).max())
        m = y.mean(axis=1)
        self.assertLess(np.abs(np.diff(m)).max(), 0.7 * m.std())

    def test_per_event_voices_override_and_expression(self):
        ev = [dict(t=0, dur=1, p=60, v=90, voices=1)]
        _, info = _ens(events=ev, voices=4, stems=True)
        loud = [float(np.abs(s).max()) for s in info['stems']]
        self.assertGreater(loud[0], 0.0)
        self.assertEqual(loud[1:], [0.0, 0.0, 0.0])
        a, b = _ens(), _ens(expression='cinematic')
        self.assertFalse(np.array_equal(a, b))

    def test_explicit_singers_in_config_are_used(self):
        _, info = _ens(voices=2, stems=True, singers=[{'source': {'register': 'chest'}}, {'source': {'register': 'falsetto'}}])
        self.assertEqual([v['identity'].get('explicit') for v in info['voices']], [0, 1])

    def test_soft_limiter_never_exceeds_one(self):
        x = np.linspace(-5, 5, 1001)
        y = ensemble.soft_limit(x)
        self.assertLessEqual(np.abs(y).max(), 1.0)
        self.assertTrue(np.allclose(y[np.abs(x) < 0.9], x[np.abs(x) < 0.9]))


if __name__ == '__main__':
    unittest.main()
