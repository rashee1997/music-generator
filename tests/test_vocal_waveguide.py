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

"""Gates for the waveguide core.

Gate 1 is the physics: a scattering network must pass a matched line unchanged, must ring at the resonances the
Webster eigenproblem predicts, and the controls must be able to fail. Gate 3 is the render path under the conditions
that break a per-sample model: machine-gun staccato, a two-octave glide in 80 ms, a 30 Hz area modulation and an
extreme velar coupling.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'scripts')]
from vocal_engine import data, geometry, nasal, voice, waveguide  # noqa: E402

SR = 22050


def _cfg():
    return data.defaults()


class Gate1Physics(unittest.TestCase):
    """The scattering network and the eigenproblem must agree with the analytic tube, and fail when they should."""

    def test_matched_line_is_a_pure_delay(self):
        areas = np.full(22, 2.0e-4)
        x = np.zeros(128)
        x[0] = 1.0
        y = waveguide.kl(x, areas, r_glottis=0.0, r_lip=0.0)
        self.assertEqual(int(np.argmax(np.abs(y))), 22)          # one trip down and back
        self.assertAlmostEqual(float(np.abs(y).max()), 1.0, places=9)
        self.assertAlmostEqual(float(np.sum(y ** 2)), 1.0, places=9)

    def test_matched_line_has_flat_response(self):
        areas = np.full(22, 2.0e-4)
        _, mag = waveguide.kl_response(areas, r_glottis=0.0, r_lip=0.0)
        self.assertLess(float(np.abs(mag - 1.0).max()), 1e-9, 'an all-pass must have |H| = 1 everywhere')

    def test_the_flat_response_control_can_fail(self):
        """A mismatched termination must break the flatness the previous test asserts: the control is not vacuous."""
        areas = np.full(22, 2.0e-4)
        _, mag = waveguide.kl_response(areas, r_glottis=1.0, r_lip=-1.0)
        self.assertGreater(float(mag.max() / max(mag.min(), 1e-12)), 10.0)

    def test_open_lip_rings_at_odd_quarters(self):
        """Closed-open tube: resonances at (2n+1)c/4L, which for a 22-section delay line at 44.1 kHz is (2n+1)SR/88."""
        n = 22
        areas = np.full(n, 2.0e-4)
        _, mag = waveguide.kl_response(areas, r_glottis=1.0, r_lip=-1.0)
        f = np.fft.rfftfreq(2 * (len(mag) - 1), 1.0 / 44100.0)
        idx = np.nonzero((mag[1:-1] > mag[:-2]) & (mag[1:-1] > mag[2:]))[0] + 1
        measured = f[idx][:4]
        expect = 44100.0 * (2 * np.arange(4) + 1) / (4.0 * n)
        self.assertGreaterEqual(len(measured), 4, measured)
        for a, b in zip(measured, expect):
            self.assertLess(abs(a - b) / b, 0.02, (measured, expect))

    def test_kl_resonances_match_the_eigenproblem(self):
        """A tapered tube: the time-domain network and the Webster eigenproblem must find the same resonances.

        `lip=False` here on purpose: the network is terminated by a hard-open (p = 0) lip with no radiation load, and
        the eigenproblem's default end correction models exactly that load. Comparing the two without this is
        comparing two different tubes.
        """
        wv = _cfg()['waveguide']
        areas = np.linspace(1.6e-4, 0.35e-4, 22)
        _, mag = waveguide.kl_response(areas, n_fft=16384, r_glottis=0.95, r_lip=-0.9)
        f = np.fft.rfftfreq(2 * (len(mag) - 1), 1.0 / 44100.0)
        idx = np.nonzero((mag[1:-1] > mag[:-2]) & (mag[1:-1] > mag[2:]))[0] + 1
        kl_peaks = []
        for i in idx[:4]:                                # parabolic refinement: the 2.7 Hz bins are too coarse
            y0, y1, y2 = mag[i - 1], mag[i], mag[i + 1]
            d = y0 - 2.0 * y1 + y2
            kl_peaks.append(f[i] + (0.5 * (y0 - y2) / d if d else 0.0) * (f[1] - f[0]))
        # the delay line samples the tube at 22 sections, so its speed of sound is 44100 * 0.17 / 22 = 340.8 m/s
        modes = waveguide.modes(areas, float(wv['tract_length_m']), 4, lip=False)[0] * (44100.0 * 0.17 / 22.0 / 343.0)
        self.assertGreaterEqual(len(kl_peaks), 4, kl_peaks)
        # measured on this tube: -4.3 % on F1 (the strongly tapered end is most sensitive to staircase vs section
        # reflections), -2.3 / -1.8 / -1.2 % on F2-F4
        for a, b in zip(kl_peaks, modes):
            self.assertLess(abs(a - b) / b, 0.05, (kl_peaks, modes))
        self.assertLess(max(abs(a - b) / b for a, b in list(zip(kl_peaks, modes))[1:]), 0.03)

    def test_lip_end_correction_moves_the_mode_onto_the_response_peak(self):
        """The correction is the difference between an eigenfrequency and a formant: it must shrink that gap."""
        wv = _cfg()['waveguide']
        length = float(wv['tract_length_m'])
        areas = np.full(22, 2.0e-4)
        plain, _ = waveguide.modes(areas, length, 1, lip=False)
        corr, _ = waveguide.modes(areas, length, 1, lip=True)
        measured = waveguide.peaks(corr, areas, length, wv)[0]
        self.assertLess(corr[0], plain[0])                      # the mass load lengthens the tube
        self.assertLess(abs(corr[0] - measured), abs(plain[0] - measured), (plain, corr, measured))


class Gate3RenderPath(unittest.TestCase):
    """Conditions that break a per-sample model: the block-vectorised path must survive them cleanly."""

    def _syn(self, f0, formants=None, **kw):
        cfg = _cfg()
        n = len(f0)
        y, _ = voice.synth(f0, SR, np.random.default_rng(1), cfg, formants=formants, **kw)
        self.assertEqual(len(y), n)
        self.assertTrue(np.isfinite(y).all(), 'non-finite output')
        return y

    def _click_free(self, y, factor=8.0):
        self.assertLess(float(np.abs(np.diff(y)).max()), factor * float(y.std()) + 1e-9, 'discontinuity')

    def test_staccato_32nd_notes_at_300_bpm(self):
        # 32nd at 300 BPM = 25 ms per note, half of it silence: the tract is re-articulated faster than a 5 ms block
        step = 0.025
        n = int(SR * step)
        f0 = np.zeros(int(SR * 0.4))
        for i in range(8):
            s = int(i * n * 2)
            f0[s:s + n] = 62 * 2 ** ((i % 4) / 12.0)
        y = self._syn(f0)
        self.assertGreater(float(np.abs(y).max()), 0.0)
        self._click_free(y)

    def test_two_octave_glide_in_80ms(self):
        n = int(SR * 0.4)
        f0 = 110.0 * 2 ** (np.clip((np.arange(n) / SR - 0.1) / 0.08, 0.0, 1.0) * 2.0)
        y = self._syn(f0)
        self._click_free(y)

    def test_thirty_hz_area_modulation(self):
        """A vowel track moving 30 times a second is faster than the block rate: bandwidths must follow smoothly."""
        cfg = _cfg()
        wv = cfg['waveguide']
        n = int(SR * 0.5)
        t = np.arange(n) / SR
        vib = 0.18 * np.sin(2 * np.pi * 30.0 * t)
        F = np.stack([730 * (1 + vib), 1090 * (1 - vib), 2440 * np.ones(n)])
        tab = geometry.table(cfg, SR)
        bw, g = geometry.as_track(tab, F, max(16, int(cfg['tract']['block_ms'] * 1e-3 * SR)), n, None)
        self.assertEqual(bw.shape, F.shape)
        self.assertTrue(np.isfinite(bw).all() and np.isfinite(g).all())
        self.assertLess(float(np.abs(np.diff(bw, axis=1)).max()), 50.0, 'bandwidth jumped between samples')
        y = self._syn(110.0 * np.ones(n), formants=F)
        self._click_free(y)

    def test_extreme_velar_coupling(self):
        cfg = _cfg()
        src = np.sin(2 * np.pi * 220.0 * np.arange(SR // 2) / SR)
        h = dict(cfg['humming'])
        h['oral_coupling'] = 1.0
        h['antiformant_depth'] = 1.0
        y = nasal.hum_branch(src, SR, h, np.random.default_rng(0), wv=cfg['waveguide'])
        self.assertTrue(np.isfinite(y).all() and np.abs(y).max() > 0)
        z = nasal.nasalize(src, src, SR, 1.0, h, wv=cfg['waveguide'])
        self.assertTrue(np.isfinite(z).all())

    def test_physical_and_table_modes_both_render(self):
        cfg = _cfg()
        n = int(SR * 0.3)
        f0 = 146.0 * np.ones(n)
        a, _ = voice.synth(f0, SR, np.random.default_rng(3), cfg)
        cfg2 = _cfg()
        cfg2['waveguide']['mode'] = 'table'
        b, _ = voice.synth(f0, SR, np.random.default_rng(3), cfg2)
        self.assertTrue(np.isfinite(a).all() and np.isfinite(b).all())
        self.assertFalse(np.array_equal(a, b), 'the two modes must not be the same render')


if __name__ == '__main__':
    unittest.main()
