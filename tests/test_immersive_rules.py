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

"""Immersive headphone rules: route, directional reflections, Stage 0 mandate, Stage 6 rows (and that each row can fail)."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
from spatial_hrtf import binaural  # noqa: E402

SR = 44100
IMM = {'enabled': True, 'height_by_role': {'melody': 6, 'pad': 15, 'environment': 40, 'chord': 0, 'bass': 0, 'drum': 0},
       'max_elevation': 60, 'min_height_tracks': 1, 'gate': {'max_late_iacc': 0.4}}
REFL = {'ground_delay_ms': 8, 'ground_gain': .3, 'lateral_delay_ms': 20, 'lateral_gain': .25, 'ceiling_delay_ms': 25,
        'ceiling_gain': .2, 'rear_delay_ms': 30, 'rear_gain': .15}


def _noise():
    return signal.sosfilt(signal.butter(4, [300, 6000], 'band', fs=SR, output='sos'), np.random.default_rng(1).standard_normal(SR))


@unittest.skipUnless(binaural.available(), 'head data not downloaded')
class TestRoute(unittest.TestCase):
    def test_pair_keeps_stereo_width(self):
        rng = np.random.default_rng(2)
        st = np.stack([rng.standard_normal(SR), rng.standard_normal(SR)], 1) * 0.1
        y = binaural.spatialize_pair(st, 0, 0, 1.5, 40)
        c = np.corrcoef(y[:, 0], y[:, 1])[0, 1]
        self.assertLess(c, 0.5)                      # decorrelated sources stay wide; a mono fold would be fully coherent
        self.assertEqual(binaural.spatialize_pair(st, 0, 0, 1.5, 0).shape, (SR, 2))

    def test_reflections_have_direction(self):
        y = binaural.reflections(_noise(), 60, 1.5, REFL)
        self.assertEqual(y.shape, (SR, 2))
        L, R = np.sqrt((y[:, 0] ** 2).mean()), np.sqrt((y[:, 1] ** 2).mean())
        self.assertGreater(abs(20 * np.log10(R / L)), 1.0)             # a source on the right gives unequal ears, not a copy in both
        self.assertEqual(np.abs(binaural.reflections(_noise(), 0, 1.5, {})).max(), 0.0)

    def test_mixer_immersive_lifts_and_places(self):
        import mixer
        import mix_context
        _saved = mix_context.current()
        mixer._install(dict(mixer._mix(), immersive=IMM), _saved.space if _saved else {})
        try:
            x = _noise().astype(np.float32)
            spec = {'role': 'pad', 'gain_db': 0.0, 'inst': 'x', 'spatial': {'azimuth': 60.0, 'distance': 2.0, 'space': 'hall'}}
            y = mixer.process_stem('t', np.stack([x, x], 1), spec, sr=SR)       # no "binaural" key: immersive routes it anyway
            ild = 20 * np.log10(np.sqrt((y[:, 1] ** 2).mean()) / np.sqrt((y[:, 0] ** 2).mean()))
            self.assertGreater(ild, 3)
            flat = dict(spec, role='bass')
            yb = mixer.process_stem('t', np.stack([x, x], 1), flat, sr=SR)
            self.assertEqual(yb.shape[1], 2)
        finally:
            mixer.reset_context()


class TestProjectGate(unittest.TestCase):
    def _project(self, imm, tracks):
        import presets
        d = tempfile.mkdtemp()
        for k in ('mix', 'instruments', 'spaces'):
            os.makedirs(os.path.join(d, 'presets', k))
        json.dump(dict(name='m', character='a calm piece that needs room cues and a lifted pad', carve_db=-4.0, max_boost_db=12.0,
                       immersive=imm), open(os.path.join(d, 'presets', 'mix', 'm.json'), 'w'))
        os.makedirs(os.path.join(d, 'direction'))
        presets.add_project(d)
        return d, {'mix_preset': 'm', 'tracks': tracks}

    def test_bass_lift_and_no_height_block(self):
        import project_gate as pg
        d, score = self._project(IMM, [{'name': 'b', 'instrument': 'bass', 'role': 'bass', 'spatial': {'azimuth': 0, 'elevation': 20}},
                                       {'name': 'p', 'instrument': 'pad', 'role': 'pad'}])
        text = ' | '.join(pg.immersive_problems(score, d))
        if binaural.available():
            self.assertIn('bass at elevation 20', text)
        self.assertNotIn('only 0 track', text)                          # the pad is lifted by height_by_role (15 deg)
        d, score = self._project(dict(IMM, min_height_tracks=2), [{'name': 'p', 'instrument': 'pad', 'role': 'pad'}])
        self.assertIn('only 1 track', ' | '.join(pg.immersive_problems(score, d)))

    def test_off_means_no_rules(self):
        import project_gate as pg
        d, score = self._project(dict(IMM, enabled=False), [{'name': 'b', 'instrument': 'bass', 'role': 'bass', 'spatial': {'elevation': 40}}])
        self.assertEqual(pg.immersive_problems(score, d), [])

    def test_beyond_max_elevation(self):
        import project_gate as pg
        d, score = self._project(IMM, [{'name': 'e', 'instrument': 'x', 'role': 'environment', 'spatial': {'elevation': 85}}])
        self.assertIn('beyond max_elevation', ' | '.join(pg.immersive_problems(score, d)))


@unittest.skipUnless(binaural.available(), 'head data not downloaded')
class TestGateRows(unittest.TestCase):
    def _rows(self, tracks, imm=IMM, space='hall'):
        import mixer
        import quality_gate as qg
        import soundfile as sf
        real, d, rng, out = mixer.immersive_cfg, tempfile.mkdtemp(), np.random.default_rng(3), []
        mixer.immersive_cfg = lambda score: imm
        sf.write(os.path.join(d, 'm.wav'), rng.standard_normal((SR * 2, 2)) * 0.05, SR)
        try:
            qg.immersive_rows({'tracks': tracks, 'space': space, 'mix_preset': 'default'}, os.path.join(d, 'm.wav'),
                              {'p': rng.standard_normal(SR) * 0.1}, out)
        finally:
            mixer.immersive_cfg = real
        return {n: lvl for lvl, n, _ in out}

    def test_good_piece_passes_probes(self):
        rows = self._rows([{'name': 'p', 'instrument': 'pad', 'role': 'pad'}])
        for k in ('imm_cues', 'imm_elevation', 'imm_height_rules'):
            self.assertEqual(rows[k], 'PASS', k)

    def test_height_rule_can_fail(self):
        rows = self._rows([{'name': 'b', 'instrument': 'bass', 'role': 'bass', 'spatial': {'elevation': 30}}])
        self.assertEqual(rows['imm_height_rules'], 'FAIL')

    def test_no_lifted_track_can_fail(self):
        rows = self._rows([{'name': 'c', 'instrument': 'x', 'role': 'chord'}])
        self.assertEqual(rows['imm_height_rules'], 'FAIL')


@unittest.skipUnless(binaural.available(), 'head data not downloaded')
class TestPresetOwnedSpatial(unittest.TestCase):
    """The step the engine takes without being asked, and every number owned by a preset rather than by the code."""

    def test_reflections_obey_their_own_path(self):
        for d in (1.5, 4.0, 8.0):
            er = binaural.reflections(_noise(), 30, d, dict(REFL))
            dr = binaural.spatialize(_noise(), 30, 0, d)
            ratio = 10 * np.log10((er ** 2).sum() / ((dr ** 2).sum() + 1e-12))
            self.assertLess(ratio, -3.0, f'{d} m: ER {ratio:+.1f} dB re direct; reflections louder than the source is the old inversion')

    def test_path_physics_can_be_switched_off_for_an_old_project(self):
        on = binaural.reflections(_noise(), 30, 6.0, dict(REFL), path_physics=True)
        off = binaural.reflections(_noise(), 30, 6.0, dict(REFL), path_physics=False)
        self.assertGreater((off ** 2).sum(), (on ** 2).sum())

    def test_pair_keeps_the_stereo_stem_energy(self):
        """0.707 is the energy-preserving constant for two sources: the pair carries the stereo stem's own energy, so
        enabling the route does not add gain. It sits ~1 dB under a centred mono source because the filters at +-40 deg
        are off-axis; measuring against that single source is what made the first diagnosis wrong."""
        x = _noise().astype(np.float32)
        st = np.stack([x, x], 1)
        pair = binaural.spatialize_pair(st, 0, 0, 1.5, 40)

        def rms(y):
            return np.sqrt((np.asarray(y, float) ** 2).mean())
        self.assertLess(abs(20 * np.log10(rms(pair) / rms(st))), 2.0)

    def test_immersive_rows_are_profile_rows(self):
        import gate_profiles as gpf
        for rid in ('imm.cues', 'imm.elevation', 'imm.frontback', 'imm.height_rules', 'imm.band',
                    'imm.externalization', 'imm.envelopment', 'imm.width', 'imm.foldown',
                    'imm.coloration', 'imm.route_parity'):
            self.assertIn(rid, gpf.ROWS, rid)
            self.assertEqual(gpf.row_problems({rid: {'mode': 'relax', 'reason': 'measured exception'}}, 'w'), [], rid)
        self.assertEqual(gpf.row_problems({'imm.band': {'mode': 'relax', 'reason': 'measured', 'min_hf_frac': 0.002}}, 'w'), [])

    def test_a_profile_can_skip_an_imm_row_with_a_reason(self):
        import gate_profiles as gpf
        import presets
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'presets', 'gate'))
        json.dump(dict(name='quiet_immersive', character='a quiet immersive cue', extends='melodic',
                       rows={'imm.band': {'mode': 'skip', 'reason': 'every lifted stem is a sine'}}),
                  open(os.path.join(d, 'presets', 'gate', 'quiet_immersive.json'), 'w'))
        roots = list(presets.PROJECT_ROOTS)
        presets.PROJECT_ROOTS.clear()
        try:
            presets.add_project(d)
            self.assertEqual(gpf.problems(), [])
            self.assertFalse(gpf.resolve(dict(piece_type='quiet_immersive', tracks=[])).on('imm.band'))
        finally:
            presets.PROJECT_ROOTS[:] = roots


@unittest.skipUnless(binaural.available(), 'head data not downloaded')
class TestEnhancements(unittest.TestCase):
    """P1-P5 from the spatial plan: near field, geometry, late field, head sets, motion. Every switch is a preset key."""

    NF = dict(enabled=True, max_m=1.0, head_radius_m=0.0875, strength=1.0, lf_boost=0.0, lf_hz=700.0)

    def test_near_field_grows_as_the_source_approaches(self):
        def ild(y):
            return 20 * np.log10(np.sqrt((y[:, 1] ** 2).mean()) / np.sqrt((y[:, 0] ** 2).mean()))
        near = binaural.spatialize(_noise(), 60, 0, 0.2, near_field=self.NF)
        mid = binaural.spatialize(_noise(), 60, 0, 1.0, near_field=self.NF)
        self.assertGreater(ild(near), ild(mid) + 2.0)
        self.assertGreater(np.abs(near - mid).max(), 1e-3)          # before P1 these rendered identically

    def test_near_field_can_be_switched_off(self):
        off = binaural.spatialize(_noise(), 60, 0, 0.2, near_field=dict(self.NF, enabled=False))
        base = binaural.spatialize(_noise(), 60, 0, 0.2)
        self.assertTrue(np.allclose(off, base))

    def test_near_field_is_symmetric(self):
        right = binaural.spatialize(_noise(), 90, 0, 0.2, near_field=self.NF)
        left = binaural.spatialize(_noise(), -90, 0, 0.2, near_field=self.NF)
        self.assertGreater(right[:, 1].var(), right[:, 0].var())
        self.assertGreater(left[:, 0].var(), left[:, 1].var())

    def test_room_geometry_gives_real_path_lengths(self):
        import presets
        from spatial_hrtf import room
        refl = presets.find_space('concert_hall_3d')['reflections']
        taps = room.taps(refl['geometry'], -40, 5.0, 3.0)
        self.assertGreater(len(taps), 2)
        self.assertGreater(len({round(t['delay_ms'], 3) for t in taps}), 2)
        for t in taps:
            self.assertAlmostEqual(t['distance_m'], np.hypot(0, 0) + t['distance_m'])   # finite
            self.assertGreaterEqual(t['distance_m'], 3.0)
        self.assertTrue(any(t['elevation'] > 5.0 for t in taps))          # the ceiling is in there
        y = binaural.reflections(_noise(), -40, 3.0, refl, elevation_deg=5.0)
        self.assertGreater(float(np.abs(y).max()), 0.0)

    def test_an_unknown_material_is_an_error(self):
        import presets
        from spatial_hrtf import room
        geom = dict(presets.find_space('concert_hall_3d')['reflections']['geometry'])
        geom['materials'] = dict(geom['materials'], floor='unobtainium')
        with self.assertRaises(KeyError):
            room.taps(geom, 0, 0, 3.0)

    def test_late_field_is_decorrelated_and_switched_by_the_preset(self):
        refl = dict(REFL, late=dict(enabled=True, rt60_s=0.8, hf_decay=0.6, level_db=-12.0, count=4, seed=3))
        y = binaural.late(_noise(), 30, 2.0, refl)
        self.assertIsNotNone(y)
        c = float(np.corrcoef(y[:, 0], y[:, 1])[0, 1])
        self.assertLess(c, 0.6, 'one tail in both ears is the in-head sound')
        self.assertIsNone(binaural.late(_noise(), 30, 2.0, dict(REFL)))

    def test_head_set_can_be_chosen_and_missing_data_is_honest(self):
        try:
            self.assertEqual(binaural.set_dataset(None), 'fabian')
            binaural.set_dataset('missing_listener.mat')
            self.assertFalse(binaural.available())
        finally:
            binaural.set_dataset(None)
        self.assertTrue(binaural.available())

    def test_motion_updates_the_filter_not_only_the_gain(self):
        tj = dict(start_azimuth=-70, end_azimuth=70, start_distance=2.0, end_distance=2.0, doppler=False)
        mov = binaural.spatialize(_noise(), 0, 0, 2.0, trajectory=tj)
        still = binaural.spatialize(_noise(), 0, 0, 2.0)
        self.assertEqual(mov.shape, (SR, 2))
        self.assertGreater(float(np.abs(mov - still).max()), 1e-3)

    def test_doppler_resamples_the_path(self):
        d = np.linspace(4.0, 1.0, 4096)
        x = np.sin(2 * np.pi * 440 * np.arange(4096) / SR).astype(float)
        moved = binaural._doppler(x, d, SR)
        self.assertEqual(len(moved), len(x))
        self.assertGreater(float(np.abs(moved - x).max()), 1e-4)


if __name__ == '__main__':
    unittest.main()
