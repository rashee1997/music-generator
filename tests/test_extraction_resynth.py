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

#!/usr/bin/env python3
"""test_extraction_resynth.py - MIDI clean-up and stems rebuilt from MIDI, measured against the known synthetic sources."""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'scripts')))
import test_extraction_drums as D  # noqa: E402
import test_extraction_separate as S  # noqa: E402
from extraction import config, drums, gate, midi_clean, resynth  # noqa: E402
from extraction.music_db import hz  # noqa: E402


def note(midi, a, b, strength=1.0):
    return {'midi': midi, 'start_s': a, 'end_s': b, 'strength': strength}


class TestMidiClean(unittest.TestCase):
    cfg = config.load()

    def test_a_monophonic_voice_never_has_two_notes_at_once(self):
        notes = [note(60, 0.0, 1.0, 1.0), note(61, 0.5, 1.5, 2.0), note(62, 0.55, 0.57, 3.0), note(90, 2.0, 3.0), note(60, 3.0, 4.0)]
        kept, st = midi_clean.clean_voice(notes, 1, (55, 70), self.cfg)
        self.assertEqual(midi_clean.overlap_violations(kept, 1), 0)
        self.assertEqual(st['short'], 1)                                   # the 20 ms flicker
        self.assertEqual(st['out_of_range'], 1)                            # the 90 is not for this instrument
        self.assertEqual(st['trimmed'], 1)                                 # the weaker held 60 is cut when the stronger 61 starts
        self.assertEqual([n['midi'] for n in kept], [60, 61, 60])
        self.assertAlmostEqual(kept[0]['end_s'], 0.5)

    def test_chords_survive_when_polyphony_allows(self):
        chord = [note(m, 0, 2, 1.0) for m in (48, 52, 55, 59)]
        kept, st = midi_clean.clean_voice(chord, 4, None, self.cfg)
        self.assertEqual(len(kept), 4)
        self.assertEqual(st['repaired_pct'], 0.0)

    def test_key_fit(self):
        modes = self.cfg['gate']['modes']
        cmaj = {'a': [note(m, 0, 1) for m in (60, 62, 64, 65, 67)]}
        self.assertEqual(midi_clean.key_fit_pct(cmaj, {'tonic': 'C', 'mode': 'major'}, modes), 100.0)
        self.assertEqual(midi_clean.key_fit_pct(cmaj, {'tonic': 'F#', 'mode': 'major'}, modes), 20.0)   # only the F (pitch class 5) lies in F# major
        self.assertIsNone(midi_clean.key_fit_pct(cmaj, None, modes))


class TestVoiceResynthesis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load()
        cls.stems, cls.mix, cls.vs, cls.left, cls.res = S.run_pipeline(cls.cfg)
        n = cls.mix.shape[1]
        cls.out = {}
        for k, v in cls.vs.items():
            notes, _ = midi_clean.clean_voice(cls.res['notes'][k], 1 if k != 'pad' else 4, v['range'], cls.cfg)
            cls.out[k] = resynth.render_voice(k, notes, v, {}, cls.res['amps'][k], cls.res['frame_t'], cls.res['voices'][k], n, S.SR, S.CENTS, cls.cfg, 5)

    def test_rebuilt_voices_match_the_true_sources(self):
        for k, (y, info) in self.out.items():
            corr, db = gate.fidelity(self.stems[k], y, S.SR, self.cfg)
            print(f'  {k}: log-mel correlation {corr:.2f}, level {db:+.1f} dB, gain {info["gain"]}, noise {info["noise_ratio"]}')
            self.assertGreater(corr, 0.8, k)
            self.assertLess(abs(db), 3.0, k)

    def test_pitch_is_the_notes_pitch(self):
        y, _ = self.out['bass']
        seg = y.mean(axis=0)[int(0.3 * S.SR):int(1.2 * S.SR)]
        sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / S.SR)
        self.assertAlmostEqual(float(f[np.argmax(sp)]), hz(40, S.CENTS), delta=1.5)

    def test_stereo_balance_follows_the_stem(self):
        y, _ = self.out['lead']
        got = 10 * np.log10(np.sum(y[1] ** 2) / np.sum(y[0] ** 2))
        true = 10 * np.log10(np.sum(self.stems['lead'][1] ** 2) / np.sum(self.stems['lead'][0] ** 2))
        self.assertAlmostEqual(got, true, delta=1.5)

    def test_silence_stays_silent(self):
        y, _ = self.out['lead']                                            # the lead plays nothing before 0.5 s
        self.assertLess(float(np.abs(y[:, :int(0.3 * S.SR)]).max()), 0.01 * float(np.abs(y).max()))

    def test_no_clicks_at_note_starts(self):
        import quality_gate as qg
        for k, (y, _) in self.out.items():
            self.assertEqual(len(qg.find_clicks(y.mean(axis=0))), 0, k)


class TestDrumResynthesis(unittest.TestCase):
    def test_pieces_are_rebuilt_at_the_measured_hits(self):
        cfg = config.load()
        parts = D.build()
        mono = sum(parts.values())
        perc = np.stack([mono, mono])
        db = [{'id': 'kick_main', 'kind': 'kick', 'centroid_hz': 140}, {'id': 'snare_main', 'kind': 'snare', 'centroid_hz': 1850},
              {'id': 'hat_closed', 'kind': 'hat_closed', 'centroid_hz': 6800}]
        res = drums.extract(perc, D.SR, db, cfg)
        out, shots = resynth.render_drums(res['pieces'], D.SR, perc.shape[1], cfg)
        self.assertEqual(sorted(out), sorted(res['pieces']))
        for pid, y in out.items():
            corr, dbl = gate.fidelity(res['pieces'][pid]['stem'], y, D.SR, cfg)
            print(f'  {pid}: log-mel correlation {corr:.2f}, level {dbl:+.1f} dB')
            self.assertGreater(corr, 0.6, pid)                  # the test hats are fresh noise bursts: only their colour and timing repeat
            self.assertLess(abs(dbl), 3.0, pid)
        self.assertLess(float(np.abs(shots['kick_main'][:, -50:]).max()), 1e-3)           # one-shot ends faded


class TestSamplerVoice(unittest.TestCase):
    """A sampler of real notes cut from the stem plays the cleaned MIDI; its level follows the song's own."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from extraction import export
        import clone_instrument as ci
        cls.tmp = tempfile.mkdtemp(prefix='test_resynth_')
        cls.cfg = config.load()
        cls.stems, cls.mix, cls.vs, cls.left, cls.res = S.run_pipeline(cls.cfg)
        n = cls.mix.shape[1]
        cls.out = {}
        for k, v in cls.vs.items():
            notes, _ = midi_clean.clean_voice(cls.res['notes'][k], 1 if k != 'pad' else 4, v['range'], cls.cfg)
            others = [a for j, a in cls.res['voices'].items() if j != k]
            meta = export.build_sampler(k, cls.res['voices'][k], notes, others, S.CENTS, S.SR, cls.tmp, cls.cfg, min_clean=0.6, quality='purity')
            inst = ci.SamplerInstrument(os.path.join(cls.tmp, k)) if meta else None
            cls.out[k] = (meta, resynth.render_voice(k, notes, v, {}, cls.res['amps'][k], cls.res['frame_t'], cls.res['voices'][k], n, S.SR, S.CENTS, cls.cfg, 5, inst))

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_sampler_was_used_and_matches_the_source(self):
        used = 0
        for k, (meta, (y, info)) in self.out.items():
            corr, db = gate.fidelity(self.stems[k], y, S.SR, self.cfg)
            print(f'  {k}: mode {info["mode"]}, {info["samples"]} samples, log-mel correlation {corr:.2f}, level {db:+.1f} dB')
            used += info['mode'].startswith('sampler')
            self.assertGreater(corr, 0.6, k)
            self.assertLess(abs(db), 4.0, k)
        self.assertGreaterEqual(used, 1, 'no voice had enough clean notes for a sampler')

    def test_silence_stays_silent_with_a_sampler(self):
        meta, (y, info) = self.out['lead']
        self.assertLess(float(np.abs(y[:, :int(0.3 * S.SR)]).max()), 0.02 * float(np.abs(y).max()))

    def test_a_voice_without_samples_falls_back_to_additive(self):
        k = 'bass'
        n = self.mix.shape[1]
        notes, _ = midi_clean.clean_voice(self.res['notes'][k], 1, self.vs[k]['range'], self.cfg)
        y, info = resynth.render_voice(k, notes, self.vs[k], {}, self.res['amps'][k], self.res['frame_t'], self.res['voices'][k], n, S.SR, S.CENTS, self.cfg, 5, None)
        self.assertEqual(info['mode'], 'additive')


class TestRoom(unittest.TestCase):
    def test_the_fitted_room_level_recovers_a_known_reverb(self):
        import mixer
        cfg = config.load()
        stems, mix, *_ = S.run_pipeline(cfg)
        dry = stems['bass'] + stems['lead']
        spec = (1.0, 12.0, 0.55, 0.3)
        wet_true = mixer.reverb_bus(dry.T.astype('float64'), spec, S.SR, seed=cfg['resynth']['reverb_seed']).T[:, :dry.shape[1]]
        heard = dry + 10 ** (-12 / 20.0) * wet_true
        wet, info = resynth.fit_room(dry.astype('float32'), heard.astype('float32'), S.SR, spec, [], cfg)
        self.assertEqual(info['gain_db'], -12)
        self.assertLess(info['error_pct'], info['error_without_room_pct'])
        off, info2 = resynth.fit_room(dry.astype('float32'), heard.astype('float32'), S.SR, (1.6, 12.0, 0.55, 0.3), [], cfg)   # wrong decay time: still helps
        self.assertLess(info2['error_pct'], info2['error_without_room_pct'])
        none, info3 = resynth.fit_room(dry.astype('float32'), dry.astype('float32'), S.SR, spec, [], cfg)                  # a dry recording gets no room
        self.assertEqual(info3['gain_db'], -99)
        self.assertEqual(float(np.abs(none).max()), 0.0)


if __name__ == '__main__':
    unittest.main()
