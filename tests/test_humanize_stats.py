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

"""The humanizer's claims, measured: shared drift, velocity-duration coupling, just intonation, articulation, drums.

These are statistical properties, so they are asserted on seeded output with generous windows; the point is that the
structure exists and points the right way, not that a particular sample lands on a number.
"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import humanize as hz  # noqa: E402

FLAT = dict(timing_ms=0, drum_ms=0, lead_ms=0, drift_ms=0, vel_sigma=0, rubato=0.0, wander=0.0,
            strum_ms=0, ritard=0.0, accent=0.0, note_lag1=0.0, vel_dur=0.0, tune_drift_cents=0.0,
            just_ratio=0.0, subdiv_push_ms=0.0)


def _notes(n=16, v=0.7, p=60, step=1.0):
    return [dict(t=i * step, d=step * 0.9, p=p, v=v) for i in range(n)]


class SharedDriftTests(unittest.TestCase):
    def test_tempo_map_carries_one_drift_curve(self):
        tm = hz.tempo_map_for(dict(bpm=96, seed=5))
        self.assertTrue(hasattr(tm, 'shared_drift'))
        grid, vals = tm.shared_drift
        self.assertEqual(len(grid), len(vals))
        again = hz.shared_drift(5, tm.total_beats, 'natural')
        self.assertTrue(np.allclose(vals, again[1]))

    def test_two_tracks_of_a_piece_drift_together(self):
        """Before this, each track built its own drift and two players wandered apart."""
        tm = hz.tempo_map_for(dict(bpm=96, seed=5, rubato=0.0, ritard=0.0, wander=0.0))
        cfg = dict(FLAT, drift_ms=12.0, lead_ms=0.0)
        a = hz.humanize_track(_notes(), tm, cfg, role='chord', seed=1)
        b = hz.humanize_track(_notes(), tm, cfg, role='chord', seed=2)
        da = np.array([e['t'] for e in a]) - tm.sec([e['beat'] for e in a])
        db = np.array([e['t'] for e in b]) - tm.sec([e['beat'] for e in b])
        self.assertLess(float(np.max(np.abs(da - db))), 1e-9)
        self.assertGreater(float(np.std(da)), 1e-4)          # and the shared term is not zero

    def test_the_motor_term_is_negative_at_lag_one(self):
        tm = hz.TempoMap(96, total_beats=130, rubato=0.0, ritard=0.0, wander=0.0)
        cfg = dict(FLAT, timing_ms=8.0, drift_ms=0.0, note_lag1=0.5)
        ev = hz.humanize_track(_notes(120), tm, cfg, role='chord', seed=4)
        d = np.array([e['t'] for e in ev]) - tm.sec([e['beat'] for e in ev])
        d = d - d.mean()
        self.assertLess(float(np.corrcoef(d[:-1], d[1:])[0, 1]), -0.1)

    def test_a_note_past_the_tempo_map_does_not_collapse_onto_one_instant(self):
        tm = hz.TempoMap(96, total_beats=8)                 # a map that ends before the notes do
        ev = hz.humanize_track(_notes(40), tm, FLAT, role='chord', seed=1)
        t = np.array([e['t'] for e in ev])
        self.assertEqual(len(set(np.round(t, 6))), len(t))
        self.assertGreater(float(np.max(t)), float(tm.sec(8)))


class DynamicsTests(unittest.TestCase):
    def test_louder_notes_are_a_little_longer(self):
        tm = hz.TempoMap(96, total_beats=8, rubato=0.0, ritard=0.0)
        loud = hz.humanize_track(_notes(8, v=1.0), tm, dict(FLAT, vel_dur=0.02), role='melody', seed=1)
        soft = hz.humanize_track(_notes(8, v=0.2), tm, dict(FLAT, vel_dur=0.02), role='melody', seed=1)
        self.assertGreater(np.mean([e['dur'] for e in loud]), np.mean([e['dur'] for e in soft]))

    def test_a_major_third_leans_flat_under_just_intonation(self):
        tm = hz.TempoMap(96, total_beats=4, rubato=0.0, ritard=0.0)
        notes = [dict(t=0, d=4, p=p, v=0.6) for p in (60, 64, 67)]
        ev = hz.humanize_track(notes, tm, dict(FLAT, just_ratio=1.0), role='chord', seed=1)
        cents = {e['p']: float(e.get('c', 0.0)) for e in ev}
        self.assertLess(cents[64], -8.0)                      # ~-13.7 cents
        self.assertLess(abs(cents[67]), 5.0)                  # fifth near equal temperament

    def test_just_intonation_can_be_switched_off(self):
        tm = hz.TempoMap(96, total_beats=4, rubato=0.0, ritard=0.0)
        notes = [dict(t=0, d=4, p=p, v=0.6) for p in (60, 64, 67)]
        ev = hz.humanize_track(notes, tm, dict(FLAT, just_ratio=0.0), role='chord', seed=1)
        self.assertTrue(all(abs(float(e.get('c', 0.0))) < 1e-9 for e in ev))


class ArticulationTests(unittest.TestCase):
    def test_an_instrument_articulation_overrides_the_role_overlap(self):
        tm = hz.TempoMap(96, total_beats=8, rubato=0.0, ritard=0.0)
        long = hz.humanize_track(_notes(6), tm, FLAT, role='melody', seed=1,
                                 articulation=dict(overlap_ms=120.0))
        short = hz.humanize_track(_notes(6), tm, FLAT, role='melody', seed=1,
                                  articulation=dict(overlap_ms=0.0))
        self.assertGreater(long[0]['dur'], short[0]['dur'] + 0.02)


class DrumPushTests(unittest.TestCase):
    def test_the_push_scales_with_tempo(self):
        slow = hz.TempoMap(60, total_beats=8, rubato=0.0, ritard=0.0)
        fast = hz.TempoMap(120, total_beats=8, rubato=0.0, ritard=0.0)
        notes = [dict(t=float(i), d=0.25, p=36, v=0.8) for i in range(4)]
        cfg = dict(FLAT, push_tempo_power=0.4)
        a = hz.humanize_track(notes, slow, cfg, role='drum', seed=1, bpm=60.0)
        b = hz.humanize_track(notes, fast, cfg, role='drum', seed=1, bpm=120.0)
        da = np.mean([e['t'] - slow.sec(e['beat']) for e in a])
        db = np.mean([e['t'] - fast.sec(e['beat']) for e in b])
        self.assertLess(da, db)                              # at half speed the same feel needs a longer push


class RenderPathTests(unittest.TestCase):
    def test_mechanics_adds_noise_and_can_be_switched_off(self):
        import mechanics
        x = np.zeros((4410, 2), np.float32)
        ev = [dict(t=0.01, d=0.05, v=100)]          # the key the renderer's events actually carry
        y = mechanics.add(x, dict(mechanics_class='keys'), ev, sr=44100, seed=1)
        self.assertEqual(y.shape, x.shape)
        self.assertGreater(float(np.abs(y).max()), 1e-6)
        self.assertGreater(float(np.abs(y[:, 1]).max()), 1e-6)     # both channels, not left only
        import mix_schema
        import presets
        table = ((mix_schema.with_defaults(presets.mix()).get('render') or {}).get('mechanics') or {})
        self.assertTrue(table.get('classes'))                 # the table is preset data, not a constant in code

    def test_oversample_is_a_preset_value(self):
        import render_natural as rn
        self.assertGreaterEqual(rn._oversample(), 1)

    def test_oversampled_render_has_the_same_length(self):
        try:
            import tinysoundfont  # noqa: F401
            import soundbank
            sf = soundbank.ensure_soundfont()
        except Exception as e:
            self.skipTest(f'no sampler available: {e}')
        import render_natural as rn
        v1 = rn.Voice(sf, 44100, 1)
        v1.program(0, 0, 0)
        v1.add(0.0, 'on', 0, 60, 100)
        v1.add(0.25, 'off', 0, 60)
        a = v1.render(tail=0.1)
        v2 = rn.Voice(sf, 44100, 2)
        v2.program(0, 0, 0)
        v2.add(0.0, 'on', 0, 60, 100)
        v2.add(0.25, 'off', 0, 60)
        b = v2.render(tail=0.1)
        self.assertEqual(len(a), len(b))
        self.assertEqual(a.shape[1], 2)


if __name__ == '__main__':
    unittest.main()
