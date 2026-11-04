"""Negative controls: healthy material must pass the rows added by the two-stage gate.

The positive controls live in `test_gate_checks.py`, `test_stem_gate.py` and `gate_defects.py`. This file is the other
half of the pair: a natural fade, a reverb tail, a drum pulse, a quiet but playing bed and an arc that follows the sheet
must not fail.
"""
import os
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)

import gate_checks as gc  # noqa: E402
import gate_fixture as fx  # noqa: E402
import quality_gate  # noqa: E402
import stem_gate  # noqa: E402
from gate_audio import Signal  # noqa: E402


def fade(x, seconds=2.0):
    y = np.array(x, copy=True)
    n = min(len(y), int(seconds * fx.SR))
    ramp = np.linspace(1.0, 0.0, n) ** 2
    y[-n:] = y[-n:] * (ramp[:, None] if y.ndim == 2 else ramp)
    return y


def sine_tail(x, seconds=3.0, amp=0.05):
    """A room tail after the last note: a decaying sine well under the programme."""
    y = np.array(fade(x, seconds=0.8), copy=True)
    n = min(len(y), int(seconds * fx.SR))
    t = np.arange(n) / fx.SR
    tail = amp * np.sin(2 * np.pi * 110 * t) * np.exp(-t * 2.5)
    y[-n:] = y[-n:] + (tail[:, None] if y.ndim == 2 else tail)
    return y


class NegativeControls(unittest.TestCase):
    def rows(self, mix):
        with tempfile.TemporaryDirectory() as td:
            wav = os.path.join(td, 'mix.wav')
            sf.write(wav, mix, fx.SR)
            rows, _ = quality_gate.run_gate(None, wav_path=wav, refresh=False, score=fx.score(), mode='draft')
        return {n: l for l, n, _ in rows}

    def test_a_natural_fade_passes_the_ending_row(self):
        self.assertNotEqual(self.rows(fade(fx.build_mix(fx.build_stems()))).get('end.abrupt'), 'FAIL')

    def test_a_reverb_tail_passes_the_ending_row(self):
        self.assertNotEqual(self.rows(sine_tail(fx.build_mix(fx.build_stems()))).get('end.abrupt'), 'FAIL')

    def test_a_clean_mix_passes_cut_and_dropout(self):
        levels = self.rows(fx.build_mix(fx.build_stems()))
        for row in ('cut.hard', 'dropout', 'master.dc', 'section.energy'):
            self.assertNotEqual(levels.get(row), 'FAIL', (row, levels))

    def test_a_rest_between_phrases_is_not_a_dropout(self):
        score = fx.score()
        for tr in score['tracks']:                      # delete the note that covered 1.5-2.5 s: a written rest
            if tr['name'] == 'lead':
                tr['notes'] = [n for n in tr['notes'] if n['t'] != 3]
        stems = fx.build_stems()
        stems['lead'] = stems['lead'].copy()
        stems['lead'][int(1.9 * fx.SR):int(2.1 * fx.SR)] = 0.0     # the audio is silent where the score rests
        rows, _ = stem_gate.run_stem_gate(score, stems, sr=fx.SR, workers=1)
        self.assertNotIn('stem.dropout', [n for l, n, _ in rows if l == 'FAIL'])

    def test_a_pulse_in_a_drum_stem_is_not_a_tick(self):
        stems = fx.build_stems()
        stems['drums'] = fx.add_tick(stems['drums'], at=2.0, amp=0.08)
        rows, _ = stem_gate.run_stem_gate(fx.score(), stems, sr=fx.SR, workers=1)
        self.assertNotIn('stem.tick', [n for l, n, _ in rows if l == 'FAIL'])

    def test_a_quiet_but_playing_bed_is_not_dead(self):
        stems = fx.build_stems()
        stems['pad'] = stems['pad'] * 0.02           # 34 dB down the pad but still audible
        rows, _ = stem_gate.run_stem_gate(fx.score(), stems, sr=fx.SR, workers=1)
        dead = [d for l, n, d in rows if n == 'stem.dead' and l == 'FAIL' and 'pad' in d]
        self.assertEqual(dead, [], dead)

    def test_a_one_sample_click_fails_but_a_steep_attack_passes(self):
        base = np.sin(2 * np.pi * 220 * np.arange(fx.SR) / fx.SR) * 0.3
        click = base.copy()
        click[int(0.5 * fx.SR)] += 0.3
        ramp = base.copy()
        i = int(0.5 * fx.SR)
        ramp[i:i + 3] += np.array([0.1, 0.2, 0.3])       # a 3-sample attack rise ...
        ramp[i + 3:i + 43] += 0.3 * np.linspace(0.9, 0.0, 40)      # ... and a natural decay, not an instant return
        self.assertEqual(gc.check_clicks(Signal(click, fx.SR)).get('mad_count'), 1)
        self.assertEqual(gc.check_clicks(Signal(ramp, fx.SR)).get('mad_count'), 0)

    def test_a_clean_pad_passes_the_edge_row(self):
        rows, _ = stem_gate.run_stem_gate(fx.score(), fx.build_stems(), sr=fx.SR, workers=1)
        self.assertNotIn('stem.edge', [n for l, n, _ in rows if l == 'FAIL'])

    def test_an_arc_that_follows_the_sheet_passes(self):
        sig = Signal(fx.build_mix(fx.build_stems()), fx.SR)
        res = gc.section_energy(sig, fx.score())
        self.assertNotEqual(res.get('level'), 'FAIL', res)


if __name__ == '__main__':
    unittest.main()
