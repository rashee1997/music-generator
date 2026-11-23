"""Immersive 3.1: the research-driven changes, each measured here rather than asserted in prose.

Every threshold is the starting value the change was made with, not a calibrated pass mark.
"""
import os
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import gate_profiles
import mix_schema
import presets
import render_targets
from spatial_engine import adm, config, hoa, nfc
from spatial_hrtf import binaural, io, sph

LAYOUTS = ('itu_bs2051_system_c', 'itu_bs2051_system_d', 'itu_bs2051_system_h',
           'itu_bs2051_system_i', 'itu_bs2051_system_j', 'itu_bs2051_system_b')


def _spread(speakers, order, kind='allrad2', points=400):
    az, el = hoa._sphere_points(points)
    y = sph.sh_matrix(order, np.radians(az), np.radians(90.0 - el), 'real')
    matrix = (hoa.allrad_matrix(speakers, order, points=points) if kind == 'allrad'
              else hoa.allrad2_matrix(speakers, order, points=points))
    power = np.sum((y @ matrix.T) ** 2, axis=1)
    db = 10.0 * np.log10(power / np.mean(power) + 1e-30)
    return float(db.max() - db.min())


class Annex3Weights(unittest.TestCase):
    """A1: BS.1770-5 Annex 3 gives the surrounds +1.5 dB, not the heights and not the +-135 deg rears."""

    def test_layouts_follow_the_annex3_rule(self):
        for name in LAYOUTS:
            for spk in config.speakers(name):
                if str(spk['name']).upper().startswith('LFE'):
                    continue
                az, el = float(spk['azimuth']), float(spk['elevation'])
                want = 1.5 if (60.0 <= abs(az) <= 120.0 and abs(el) < 30.0) else 0.0
                self.assertAlmostEqual(float(spk['loudness_weight_db']), want, places=6,
                                       msg=f'{name} {spk["name"]} at az {az} el {el}')

    def test_rears_and_heights_are_not_boosted(self):
        j = {s['name']: float(s['loudness_weight_db']) for s in config.speakers('itu_bs2051_system_j')}
        self.assertEqual(j.get('LFE1', 0.0), 0.0)
        for name, db in j.items():
            if name.startswith('U') or name.startswith('T'):
                self.assertEqual(db, 0.0, f'height {name} must not carry the surround boost')
            if name in ('Lsc', 'Rsc', 'Lrs', 'Rrs', 'Lb', 'Rb'):
                self.assertEqual(db, 0.0, f'rear {name} is outside the Annex 3 window')


class AllRoundDecoder(unittest.TestCase):
    """C: AllRAD2 is the default and is measurably more uniform than AllRAD on the same layouts."""

    def test_allrad2_is_default_in_the_preset(self):
        self.assertEqual(mix_schema.DEFAULTS['immersive']['decoder'], 'allrad2')

    def test_allrad2_spread_is_small_and_better_than_allrad(self):
        for name in LAYOUTS:
            spk = config.speakers(name)
            two = _spread(spk, 5, 'allrad2')
            one = _spread(spk, 5, 'allrad')
            self.assertLess(two, 1.5, f'{name}: AllRAD2 spread {two:.2f} dB')
            self.assertLess(two, one, f'{name}: AllRAD2 {two:.2f} dB is not better than AllRAD {one:.2f} dB')

    def test_a_source_is_decoded_to_the_side_it_was_placed_on(self):
        """Azimuth is clockwise from the front, as in the layout presets (FL is -30): both decoders must agree with the encoder.
        AllRAD2 built its harmonics with the azimuth un-negated, so it mirrored the whole field left to right."""
        spk = config.speakers('itu_bs2051_system_j')
        names = [s['name'] for s in spk]
        for kind, matrix in (('allrad', hoa.allrad_matrix), ('allrad2', hoa.allrad2_matrix)):
            d = matrix(spk, 5)
            for az, want in ((-30.0, 'FL'), (30.0, 'FR'), (-90.0, 'SL'), (90.0, 'SR'), (-135.0, 'BL'), (135.0, 'BR')):
                out = d @ hoa._hrtf().gains(5, az, 0.0)[0]
                self.assertEqual(names[int(np.argmax(np.abs(out)))], want, (kind, az))

    def test_speaker_decoder_follows_the_configured_kind(self):
        bus = hoa.HoaBus(48000, 5, 'speakers', dict(decoder='allrad2'), {},
                         speakers=config.speakers('itu_bs2051_system_j'))
        self.assertEqual(bus.speaker_matrix().shape, (len(config.speakers('itu_bs2051_system_j')), 36))
        bus.imm['decoder'] = 'allrad'
        self.assertEqual(bus.speaker_matrix().shape, (len(config.speakers('itu_bs2051_system_j')), 36))


class MagLS(unittest.TestCase):
    """B: the crossover defaults to min(N*600, 1500) Hz and the diffuse-field EQ is capped and applied."""

    def setUp(self):
        # the default is read outside a mix; a mix context left installed by an earlier test would override it
        import mix_context
        self._prev_ctx = mix_context.make_current(None)

    def tearDown(self):
        import mix_context
        mix_context.make_current(self._prev_ctx)

    def test_crossover_default_follows_order(self):
        self.assertEqual(binaural.f_trans(5), 1500.0)
        self.assertEqual(binaural.f_trans(2), 1200.0)

    def test_magls_is_configurable_and_stable(self):
        from spatial_hrtf import decoder
        hrirs = io.load_hrirs(48000, 'dummy')
        a = decoder.magls_bin(hrirs, 2, f_trans=800.0)
        b = decoder.magls_bin(hrirs, 2, f_trans=2000.0)
        self.assertEqual(a.shape, b.shape)
        self.assertTrue(np.isfinite(a).all() and np.isfinite(b).all())
        self.assertGreater(np.max(np.abs(a - b)), 1e-6, 'the crossover frequency did not change the filters')
        from spatial_hrtf import decoder as _dec
        self.assertNotEqual(binaural._magls_tag(_dec.__file__, 2, 800.0, True),
                            binaural._magls_tag(_dec.__file__, 2, 2000.0, True))

    def test_diffuse_field_eq_flattens_high_frequency_deviation_within_the_cap(self):
        from spatial_hrtf import decoder
        hrirs = io.load_hrirs(48000, 'dummy')
        dec = decoder.magls_bin(hrirs, 2, f_trans=1500.0)
        eq, metrics = binaural.diffuse_field_eq(dec, hrirs)
        self.assertEqual(eq.shape, dec.shape)
        self.assertTrue(np.isfinite(eq).all())
        self.assertLessEqual(metrics['ear0_after_db'], metrics['ear0_before_db'] + 1e-9)
        self.assertLessEqual(metrics['ear1_after_db'], metrics['ear1_before_db'] + 1e-9)
        gain = 20 * np.log10(np.abs(np.fft.rfft(eq, 1024)) /
                             (np.abs(np.fft.rfft(dec, 1024)) + 1e-12) + 1e-30)
        self.assertLessEqual(float(np.max(gain)), 6.0 + 0.5, 'the EQ exceeded its +-6 dB cap')


class NearFieldCompensation(unittest.TestCase):
    """NFC-HOA: boosts the near-field orders and stops at the configured cap."""

    def test_order_zero_is_unity_and_m_1_is_about_plus_six_db_at_low_frequency(self):
        g = nfc.order_gains(np.array([20.0]), 5, 0.5, 1.0, 30.0)
        self.assertAlmostEqual(float(abs(g[0, 0])), 1.0, places=6)
        self.assertAlmostEqual(20 * np.log10(abs(g[1, 0])), 6.02, delta=0.6)

    def test_boost_is_monotonic_with_distance_and_capped(self):
        near = nfc.boost_db(5, 0.25, 1.0, 60.0)
        mid = nfc.boost_db(5, 0.5, 1.0, 60.0)
        far = nfc.boost_db(5, 0.9, 1.0, 60.0)
        self.assertGreater(near, mid)
        self.assertGreater(mid, far)
        self.assertLessEqual(nfc.boost_db(5, 0.25, 1.0, 30.0), 30.0 + 1e-6)
        g = nfc.order_gains(np.array([20.0]), 5, 0.25, 1.0, 12.0)
        self.assertLessEqual(float(np.max(20 * np.log10(np.abs(g) + 1e-30))), 12.0 + 1e-6)

    def test_apply_returns_a_stable_signal_per_order(self):
        rng = np.random.default_rng(4)
        x = (0.1 * rng.standard_normal(2048)).astype(np.float32)
        out = nfc.apply(x, 3, 0.4, 48000, 1.0, 24.0)
        self.assertEqual(out.shape, (2048, 4))
        self.assertTrue(np.isfinite(out).all())
        self.assertGreater(float(np.std(out)), 0.0)


class AdmMetadata(unittest.TestCase):
    """A2: the ADM declares BS.2076-3 and carries a truthful loudnessMetadata block."""

    def _xml(self, loudness):
        bus = adm.AdmBus(48000, dict(enabled=True, height_by_role={'melody': 20.0}))
        bus.add('lead', np.ones(480, np.float32), dict(role='melody',
                                                       spatial=dict(az=10.0, el=0.0, dist=1.0)))
        return bus.xml(480, 48000, loudness)

    def test_version_and_loudness_metadata(self):
        import xml.etree.ElementTree as ET
        xml = self._xml(dict(integrated_lufs=-18.4, max_true_peak_dbtp=-1.1))
        root = ET.fromstring(xml)
        ns = {'e': adm._NS['e']}
        afx = root.find('.//e:audioFormatExtended', ns)
        self.assertEqual(afx.get('version'), 'ITU-R_BS.2076-3')
        lm = afx.find('.//e:loudnessMetadata', ns)
        self.assertIsNotNone(lm)
        self.assertAlmostEqual(float(lm.find('e:integratedLoudness', ns).text), -18.4, places=1)
        self.assertAlmostEqual(float(lm.find('e:maxTruePeak', ns).text), -1.1, places=1)
        self.assertIn('adm-stereo-fold', lm.find('e:renderer', ns).get('uri'))

    def test_validate_bodies_rejects_the_old_version(self):
        bus = adm.AdmBus(48000, dict(enabled=True, height_by_role={'melody': 20.0}))
        bus.add('lead', np.ones(480, np.float32), dict(role='melody',
                                                       spatial=dict(az=10.0, el=0.0, dist=1.0)))
        xml = bus.xml(480, 48000, dict(integrated_lufs=-20.0, max_true_peak_dbtp=-2.0))
        if isinstance(xml, bytes):
            xml = xml.decode('utf-8')
        xml = xml.replace('ITU-R_BS.2076-3', 'ITU-R_BS.2076-2')
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'a.wav')
            adm.write(path, np.zeros((480, 1), np.float32), 48000, xml.encode('utf-8'), bus.chna())
            problems = adm.validate_file(path)
        self.assertTrue(any('2076-2' in p for p in problems), problems)


class Targets(unittest.TestCase):
    """D and IAMF: public delivery figures, declared per target, and a loud failure without the encoder."""

    def test_atmos_music_declares_the_public_figures(self):
        tgt = presets.get('outputs', 'atmos_music')
        self.assertEqual(tgt['loudness']['ceiling_lufs'], -18.0)
        self.assertEqual(tgt['true_peak_dbtp'], -1.0)
        self.assertEqual(tgt['rate_hz'], 48000)
        self.assertEqual(tgt['subtype'], 'PCM_24')
        self.assertEqual(tgt['conform_max_ms'], 50.0)

    def test_iamf_target_and_missing_encoder_error(self):
        import spatial_engine.render as render
        self.assertEqual(presets.get('outputs', 'iamf')['renderer'], 'iamf')
        old = {k: os.environ.get(k) for k in ('IAMF_ENCODER', 'PATH')}
        try:
            os.environ.pop('IAMF_ENCODER', None)
            os.environ['PATH'] = ''
            self.assertIsNone(render.iamf_encoder())
            with self.assertRaises(ValueError) as ctx:
                render._iamf_encode('none.wav', os.path.join(tempfile.gettempdir(), 'x.iamf'),
                                    tempfile.gettempdir())
            self.assertIn('iamf-tools', str(ctx.exception))
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_new_gate_rows_exist_and_carry_their_limits(self):
        for row in ('delivery.loudness_ceiling', 'delivery.conform', 'iamf.container',
                    'imm.decode_uniformity'):
            self.assertIn(row, gate_profiles.ROWS)
        g = gate_profiles.resolve({})
        self.assertEqual(g.param('delivery.loudness_ceiling', 'max_lufs'), -18.0)
        self.assertEqual(g.param('delivery.conform', 'max_abs_ms'), 50.0)
        self.assertGreater(g.param('imm.decode_uniformity', 'max_spread_db'), 0.0)


if __name__ == '__main__':
    unittest.main()
