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

"""Natural-vocal phases 1-7: five formants and the ring, formant tuning,
consonants, coarticulation and diphthongs, per-cycle jitter / passaggio / creak, vibrato amplitude coupling,
identity through tract length, and the gate rows that measure all of it.

Nothing here is a listening test: every assertion is a number measured on the produced signal or its tracks.
"""
import os
import sys
import unittest
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'scripts')]
import quality_gate as qg  # noqa: E402
import vocals  # noqa: E402
from vocal_engine import config, consonant, data, ensemble, performance as pf, tract, voice  # noqa: E402

SR = 44100


def cfg(**over):
    """Quiet defaults: no vibrato, no random pitch motion, flat level, so a measurement is about one feature."""
    c = data.defaults()
    c['vibrato'].update(depth_cents=0.0, amplitude_db=0.0, phase_walk=0.0, rate_var=0.0, depth_var=0.0)
    c['performance'].update(drift_cents=0.0, jitter_cents=0.0, arch_cents=0.0, end_sag_cents=0.0, overshoot_cents=0.0)
    c['dynamics'].update(flutter=0.0, phrase_arc_db=0.0)
    c['phrasing']['amount'] = 0.0
    for k, v in over.items():
        c[k].update(v)
    return c


def phrase(notes, c=None, hum=False, seed=1, style=None):
    return pf.render_phrase(notes, SR, np.random.default_rng(seed), c or cfg(), hum=hum, style=style or {})


def band(y, sr, lo, hi):
    s = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2
    fr = np.fft.rfftfreq(len(y), 1 / sr)
    return float(s[(fr >= lo) & (fr < hi)].sum())


MEL = [dict(t=0.0, dur=1.0, p=60, v=90, vowel='a'), dict(t=1.0, dur=1.0, p=62, v=90, vowel='a')]


class FiveFormants(unittest.TestCase):
    def test_five_by_default_three_when_declared(self):
        c = cfg()
        self.assertEqual(len(pf._formants({'vowel': 'a'}, c, {})), 5)
        F3 = pf._formants({'formants': [730, 1090, 2440]}, c, {})
        self.assertEqual(len(F3), 3)                     # a 3-formant preset still renders 3 poles
        self.assertAlmostEqual(float(F3[0]), 730.0)

    def test_f4_f5_are_distinct_and_ordered(self):
        for name, F in cfg()['tract']['vowels'].items():
            F = np.asarray(F, dtype=float)
            self.assertEqual(len(F), 5, name)
            self.assertTrue(np.all(np.diff(F) > 0), (name, F))

    def test_vowel_identity_survives_the_bigger_bank(self):
        yi = phrase([dict(t=0, dur=1.2, p=45, v=90, vowel='i')])['signal']
        yu = phrase([dict(t=0, dur=1.2, p=45, v=90, vowel='u')])['signal']
        seg = slice(int(0.4 * SR), int(1.0 * SR))
        self.assertGreater(band(yi[seg], SR, 1500, 4000) / band(yi[seg], SR, 0, 4000),
                           1.5 * band(yu[seg], SR, 1500, 4000) / band(yu[seg], SR, 0, 4000))


class SingersFormant(unittest.TestCase):
    def test_ring_clusters_f3_f5_and_raises_the_ring_band(self):
        spreads, ratios = [], []
        for amount in (0.0, 1.0):
            c = cfg(technique=dict(singer_formant=amount))
            F = pf._formants({'vowel': 'a'}, c, {})
            spreads.append(float(F[4] - F[2]))
            y = phrase([dict(t=0, dur=1.5, p=57, v=90)], c)['signal'][int(0.5 * SR):int(1.2 * SR)]
            ratios.append(band(y, SR, 2800, 3200) / max(band(y, SR, 700, 800), 1e-30))
        self.assertGreater(spreads[0], 1500)
        self.assertLess(spreads[1], 450)                  # F3-F5 converge toward 2.8-3.2 kHz
        self.assertGreater(ratios[1], 1.3 * ratios[0])    # and the ring band is louder for it

    def test_ring_is_not_a_boost_pole(self):
        """A clustering moves the poles; it must not add energy somewhere the tract has no pole."""
        c = cfg(technique=dict(singer_formant=1.0))
        F = pf._formants({'vowel': 'a'}, c, {})
        self.assertLessEqual(len(F), 5)

    def test_ring_keeps_high_vowel_brighter_than_back_vowel(self):
        c = cfg(technique=dict(singer_formant=1.0))
        yi = phrase([dict(t=0, dur=1.2, p=45, v=90, vowel='i')], c)['signal']
        yu = phrase([dict(t=0, dur=1.2, p=45, v=90, vowel='u')], c)['signal']
        seg = slice(int(0.4 * SR), int(1.0 * SR))
        self.assertGreater(band(yi[seg], SR, 1800, 2600), 1.2 * band(yu[seg], SR, 1800, 2600))

    def test_zero_ring_changes_nothing(self):
        a = phrase(MEL, cfg(technique=dict(singer_formant=0.0)))['signal']
        b = phrase(MEL, cfg())['signal']
        self.assertTrue(np.array_equal(a, b))


class FormantTuning(unittest.TestCase):
    def test_tuning_raises_the_fundamental_on_a_high_note(self):
        got = {}
        for amount in (0.0, 1.0):
            c = cfg(technique=dict(formant_tuning=amount))
            r = phrase([dict(t=0, dur=1.5, p=84, v=90, vowel='i')], c)
            seg = r['signal'][int(0.5 * SR):int(1.2 * SR)]
            f0 = 440.0 * 2 ** ((84 - 69) / 12)
            got[amount] = (band(seg, SR, f0 * 0.97, f0 * 1.03), r['technique'].get('tuning_deficit_db'))
        self.assertGreater(got[1.0][0], 1.5 * got[0.0][0])
        self.assertLessEqual(got[1.0][1], 2.0)          # tuned: the f0 harmonic sits on F1 now

    def test_low_notes_are_untouched_by_tuning(self):
        a = phrase([dict(t=0, dur=1.0, p=45, v=90)], cfg(technique=dict(formant_tuning=1.0)))['signal']
        b = phrase([dict(t=0, dur=1.0, p=45, v=90)], cfg(technique=dict(formant_tuning=0.0)))['signal']
        self.assertTrue(np.array_equal(a, b))

    def test_tuning_does_not_make_the_level_follow_the_pitch(self):
        """The calibration must be measured through the tract that is sung through. Measuring the untuned F1 and then
        synthesising the tuned one made `note_rms` swing 7 dB between neighbouring pitches, so the level stopped
        following velocity and the gate read the resulting level/pitch correlation as a broken dynamic."""
        c = cfg(technique=dict(formant_tuning=1.0))
        db = []
        for p in (74, 76, 77, 79, 81):
            r = phrase([dict(t=0, dur=1.2, p=p, v=80)], c)
            db.append(20 * np.log10(r['note_rms'][0]))
        self.assertLess(np.ptp(db), 2.0)


class Coarticulation(unittest.TestCase):
    def test_formant_moves_before_the_note_boundary(self):
        r = phrase([dict(t=0.0, dur=1.0, p=60, v=90, vowel='a'),
                    dict(t=1.0, dur=1.0, p=60, v=90, vowel='i')])
        self.assertIsNotNone(r['technique'].get('coart_lead_ms'))
        self.assertGreaterEqual(r['technique']['coart_lead_ms'], 20.0)
        F2 = r['formants'][1]
        j = int(1.0 * SR)
        self.assertGreater(F2[j - int(0.02 * SR)] - F2[int(0.9 * SR)], 60.0)   # F2 already rising at -20 ms

    def test_diphthong_glides_inside_the_note(self):
        a = phrase([dict(t=0, dur=1.2, p=60, v=90, vowel=['o', 'a'])])
        b = phrase([dict(t=0, dur=1.2, p=60, v=90, vowel='o')])
        F1a, F1b = a['formants'][0], b['formants'][0]
        self.assertGreater(F1a[int(0.8 * SR)] - F1a[int(0.05 * SR)], 60.0)     # /o/ 570 -> /a/ 730
        self.assertLess(np.ptp(F1b[int(0.05 * SR):int(1.1 * SR)]), 1.0)        # no diphthong, no glide

    def test_diphthong_does_not_change_a_plain_vowel(self):
        c = cfg()
        plain = phrase(MEL, c)['signal']
        explicit = phrase([dict(e, vowel_to=None) for e in MEL], c)['signal']
        self.assertTrue(np.array_equal(plain, explicit))


class SourceRealism(unittest.TestCase):
    def test_period_jitter_is_cycle_level_and_measurable(self):
        got = {}
        for pct in (0.0, 0.6):
            r = phrase([dict(t=0, dur=1.5, p=60, v=90)], cfg(source=dict(jitter_period_pct=pct)))
            got[pct] = r['technique'].get('jitter_pct')
        self.assertIsNotNone(got[0.6])
        self.assertTrue(got[0.0] is None or got[0.0] < 0.15, got[0.0])     # nothing reported when jitter is off
        self.assertGreater(got[0.6], max(0.2, 2.0 * (got[0.0] or 0.0)))
        self.assertLess(got[0.6], 2.0)

    def test_jitter_is_not_the_smooth_7hz_wobble(self):
        c = cfg(source=dict(jitter_period_pct=0.6), performance=dict(jitter_cents=0.0))
        r = phrase([dict(t=0, dur=1.5, p=60, v=90)], c)
        cents = 1200 * np.log2(r['f0'] / 440.0) + 6900
        self.assertLess(np.std(cents[int(0.4 * SR):int(1.2 * SR)]), 1.0)        # the pitch curve stays steady
        self.assertGreater(r['technique']['jitter_pct'], 0.2)                   # the cycles do not

    def test_passaggio_blends_instead_of_switching(self):
        c = cfg()
        notes = [dict(t=i * 0.4, dur=0.45, p=p, v=80) for i, p in enumerate(range(57, 65))]
        r = phrase(notes, c)
        oq = voice.register_track(c, 'modal', r['f0'])['open_quotient']
        self.assertGreater(float(np.max(oq)), 0.65)                             # it reaches head voice
        self.assertLess(r['technique']['passaggio_step'], 0.01)                 # and never jumps there
        self.assertTrue(np.all(np.diff(oq) >= -1e-9))

    def test_creak_adds_a_subharmonic_at_the_phrase_end(self):
        def low_ratio(r):
            y = r['signal']
            a, b = r['s'][-1], r['e'][-1]
            seg = y[max(0, b - int(0.08 * SR)):b]
            lo = band(seg, SR, 40, 63)                       # f0/2 at A2 (110 Hz): the period-doubled cycle
            return lo / max(band(seg, SR, 98, 122), 1e-30)

        c0 = cfg(technique=dict(creak=0.0))
        c1 = cfg(technique=dict(creak=1.0))
        r0 = phrase([dict(t=0, dur=1.2, p=45, v=90)], c0)
        r1 = phrase([dict(t=0, dur=1.2, p=45, v=90)], c1)
        self.assertGreater(low_ratio(r1), 1.2 * low_ratio(r0))


class VibratoCoupling(unittest.TestCase):
    def _render(self, amplitude_db):
        c = cfg(technique=dict(creak=0.0))
        c['vibrato'].update(depth_cents=25.0, rate_hz=5.3, delay_s=0.1, onset_s=0.2, amplitude_db=amplitude_db)
        return phrase([dict(t=0, dur=2.5, p=60, v=90)], c)

    def test_amplitude_modulates_with_the_pitch(self):
        r = self._render(2.0)
        self.assertIn('vib_am_corr', r['technique'])
        self.assertGreater(r['technique']['vib_am_corr'], 0.5)
        self.assertGreater(r['technique']['vib_am_db'], 1.0)

    def test_no_modulation_when_disabled(self):
        r = self._render(0.0)
        self.assertNotIn('vib_am_corr', r['technique'])


class Consonants(unittest.TestCase):
    def test_every_recipe_renders_finite_and_banded(self):
        cn = data.defaults()['consonants']
        rng = np.random.default_rng(0)
        for code, row in cn['inventory'].items():
            y, meta = consonant.render(code, cn, SR, rng, f0=180.0, vowel=[730, 1090, 2440, 3400, 4500])
            self.assertGreater(len(y), 0, code)
            self.assertTrue(np.isfinite(y).all(), code)
            self.assertLess(float(np.abs(np.diff(y)).max()), 8 * float(np.abs(y).max()) + 1e-9, code)
            if row['type'] == 'fricative':
                c = meta['measured']['centroid_hz']
                self.assertGreaterEqual(c, 0.5 * row['band'][0], code)
                self.assertLessEqual(c, 2.0 * row['band'][1], code)

    def test_unknown_code_is_silent_and_reported(self):
        cn = data.defaults()['consonants']
        y, meta = consonant.render('zzz', cn, SR, np.random.default_rng(0))
        self.assertEqual(len(y), 0)
        self.assertIn('error', meta)

    def test_onset_is_placed_before_the_voiced_onset_at_the_declared_vot(self):
        c = cfg(consonants=dict(auto=True, onsets=['t']))
        r = phrase([dict(t=0, dur=1.2, p=60, v=90)], c)
        self.assertEqual(len(r['consonants']), 1)
        self.assertLess(r['t0'], 0.0)                     # the phrase buffer grew backwards for the consonant
        cons = r['consonants'][0]
        self.assertLessEqual(abs(cons['dur_ms'] - cons['vot_ms']) / cons['vot_ms'], 0.3)
        self.assertGreater(float(np.abs(r['signal'][:int(0.03 * SR)]).max()), 0.0)

    def test_no_consonant_key_means_no_consonant(self):
        c = cfg(consonants=dict(auto=False))
        r = phrase([dict(t=0, dur=1.0, p=60, v=90)], c)
        self.assertEqual(r['consonants'], [])
        self.assertEqual(r['t0'], 0.0)

    def test_auto_is_deterministic(self):
        c = cfg(consonants=dict(auto=True, onsets=['s', 't']))
        a = phrase(MEL, c)['signal']
        b = phrase(MEL, c)['signal']
        self.assertTrue(np.array_equal(a, b))


class Identity(unittest.TestCase):
    def test_two_singers_have_measurably_different_tracts(self):
        c = data.defaults()
        c['ensemble'].update(voices=4, diversity=1.0)
        _, info = ensemble.render([dict(t=0, dur=1.0, p=60, v=90)], SR, c, seed=3, hum=False, stems=True)
        self.assertIsNotNone(info['report']['identity_pct'])
        self.assertGreater(info['report']['identity_pct'], 2.0)

    def test_diversity_zero_collapses_the_tracts(self):
        c = data.defaults()
        c['ensemble'].update(voices=3, diversity=0.0)
        _, info = ensemble.render([dict(t=0, dur=1.0, p=60, v=90)], SR, c, seed=3, hum=False, stems=True)
        self.assertAlmostEqual(info['report']['identity_pct'], 0.0, places=3)


class ConfigLayer(unittest.TestCase):
    def test_new_sections_merge_without_warnings(self):
        c, w = config.resolve({'technique': {'singer_formant': 0.8, 'creak': 0.2},
                               'consonants': {'auto': True, 'onsets': ['s', 't']}})
        self.assertEqual(w, [])
        self.assertAlmostEqual(c['technique']['singer_formant'], 0.8)
        self.assertTrue(c['consonants']['auto'])

    def test_bad_values_are_clamped_or_reported(self):
        c, _ = config.resolve({'technique': {'singer_formant': 9}, 'tract': {'pharynx_scale': 5}})
        self.assertEqual(c['technique']['singer_formant'], 1.0)
        self.assertLessEqual(c['tract']['pharynx_scale'], 1.15)
        _, w = config.resolve({'consonants': {'onsets': ['zzz']}})
        self.assertTrue(any('zzz' in x for x in w))
        _, w2 = config.resolve({'tract': {'cover_map': {'a': 'nope'}}})
        self.assertTrue(any('nope' in x for x in w2))


class GateRows(unittest.TestCase):
    SCORE = {'tracks': [{'name': 'v', 'instrument': 'choir_formant'}]}

    def _rows(self, **over):
        base = dict(voices=4, phrases=2, joins=2, longest_phrase_s=2.0, capacity_s=7.0, over_capacity=0,
                    inhales=1, no_room_phrases=0, mean_abs_dev_cents=5.0, max_abs_dev_cents=10.0,
                    dyn_corr=0.9, max_corr=0.2, hum_hf_frac=None, finite=True, dc=1e-6,
                    peak_pre_limit=0.4, peak=0.4, ring_spread_hz=300.0, ring_amount=1.0,
                    tuning_deficit_db=2.0, coart_lead_ms=40.0, jitter_pct=0.6, passaggio_step=0.001,
                    vib_am_db=1.0, vib_am_corr=0.9, identity_pct=5.0,
                    consonants=dict(n=2, centroid_ok=True, centroid_bad=0, codes=['s', 't'],
                                    declared_vot_ms=70.0, measured_vot_ms=72.0))
        base.update(over)
        stems = {'v': np.zeros((SR, 2), np.float32)}
        return qg.vocal_rows(self.SCORE, stems, report={'v': {'vocal': base}})

    def test_every_new_row_passes_on_a_good_report(self):
        rs = self._rows()
        self.assertNotIn('FAIL', [r[0] for r in rs], rs)
        for word in ('cluster', 'f0 sits', 'consonant', 'before the boundary', 'jitter', 'open-quotient',
                     'amplitude modulation', 'tract length'):
            self.assertTrue(any(word in d for _, _, d in rs), word)

    def test_every_new_row_can_fail(self):
        rs = self._rows(ring_spread_hz=900.0, tuning_deficit_db=20.0, coart_lead_ms=2.0, jitter_pct=5.0,
                        passaggio_step=0.2, vib_am_corr=0.1, identity_pct=0.1,
                        consonants=dict(n=1, centroid_ok=False, centroid_bad=1, codes=['s'],
                                        declared_vot_ms=70.0, measured_vot_ms=20.0))
        self.assertGreaterEqual(len([r for r in rs if r[0] == 'FAIL']), 8, rs)

    def test_rows_skip_when_the_engine_did_not_use_the_feature(self):
        rs = self._rows(ring_spread_hz=None, tuning_deficit_db=None, coart_lead_ms=None,
                        passaggio_step=None, vib_am_corr=None, consonants=None)
        self.assertNotIn('FAIL', [r[0] for r in rs], rs)
        self.assertFalse(any('cluster' in d for _, _, d in rs))


class EndToEnd(unittest.TestCase):
    def test_a_full_technique_render_reports_and_passes_the_gate(self):
        ev = [dict(t=0.0, dur=2.2, p=60, v=80, vowel='a'), dict(t=2.2, dur=2.2, p=64, v=95, vowel='i'),
              dict(t=5.0, dur=2.2, p=62, v=70, vowel='a')]   # long enough for a vibrato to develop
        cfgd = {'technique': {'singer_formant': 0.7, 'cover': 0.4, 'creak': 0.3},
                'consonants': {'auto': True, 'onsets': ['s', 't', 'm']},
                'ensemble': {'voices': 3}}
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            y, info = vocals.render_choir(ev, sr=SR, voices=3, seed=2, config=cfgd, return_stems=True)
        rep = info['report']
        for key in ('ring_spread_hz', 'ring_amount', 'coart_lead_ms', 'jitter_pct', 'consonants', 'identity_pct'):
            self.assertIn(key, rep, key)
        self.assertTrue(rep['consonants']['centroid_ok'], rep['consonants'])
        self.assertIsNotNone(rep['consonants']['measured_vot_ms'])
        rs = qg.vocal_rows({'tracks': [{'name': 'v', 'instrument': 'choir_formant'}]}, {'v': y},
                           report={'v': {'vocal': rep}})
        self.assertNotIn('FAIL', [r[0] for r in rs], rs)


class TradCtr(unittest.TestCase):
    def test_ring_helper_is_a_no_op_below_five_formants(self):
        F = tract.ring_cluster(np.array([730.0, 1090.0, 2440.0]), 1.0, data.defaults()['tract']['ring'])
        self.assertTrue(np.allclose(F, [730.0, 1090.0, 2440.0]))


if __name__ == '__main__':
    unittest.main()
