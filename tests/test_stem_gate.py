"""Stem gate and mix gate defect injection: each known defect must reach its own row.

The table printed by `test_report` is the evidence: baseline, injected defect, rows that fired. A miss is a real gap in
the gate, not a reason to relax the test.
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

import gate_fixture as fx
import stem_gate


def _rows(rows, level='FAIL'):
    return [n for l, n, _ in rows if l == level]


def _stem_case(name, mutate):
    stems = fx.build_stems()
    stems[name] = mutate(stems[name])
    rows, meta = stem_gate.run_stem_gate(fx.score(), stems, sr=fx.SR, workers=1)
    return rows, meta, _rows(rows)


class StemGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean_rows, cls.clean_meta = stem_gate.run_stem_gate(fx.score(), fx.build_stems(), sr=fx.SR, workers=1)

    def test_baseline_has_no_fail(self):
        self.assertEqual(self.clean_meta['fails'], 0, _rows(self.clean_rows, 'FAIL'))
        self.assertGreater(len(self.clean_rows), 10)
        for m in self.clean_meta['metrics']:
            for key in ('row', 'stage', 'level', 'value', 'threshold', 'margin', 'unit'):
                self.assertIn(key, m)

    def test_click_fires_on_the_pad(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.add_click(x, at=3.0, amp=0.5))
        self.assertIn('stem.clicks', fails, fails)

    def test_dropout_fires(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.add_dropout(x, at=3.0, ms=80))
        self.assertIn('stem.dropout', fails, fails)

    def test_cut_fires(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.add_cut(x, at=4.0, ms=500))
        self.assertIn('stem.cut', fails, fails)

    def test_stem_edge_fires_when_a_stem_starts_late(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.trim_head(x, 0.3))
        self.assertIn('stem.edge', fails, fails)

    def test_clean_stems_pass_the_edge_row(self):
        self.assertIn('stem.edge', [n for l, n, _ in self.clean_rows if l in ('PASS', 'INFO')])
        self.assertNotIn('stem.edge', _rows(self.clean_rows, 'FAIL'))

    def test_truncated_stem_fires(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.truncate_end(x, remove_s=1.0))
        self.assertIn('stem.end', fails, fails)

    def test_dc_fires(self):
        rows, meta, fails = _stem_case('bass', lambda x: fx.add_dc(x, offset=0.02))
        self.assertIn('stem.dc', fails, fails)

    def test_clipping_fires(self):
        rows, meta, fails = _stem_case('lead', lambda x: fx.clip_hard(x, gain=20.0))
        self.assertIn('stem.clipping', fails, fails)

    def test_noise_burst_fires_flatness(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.add_noise_burst(x, at=5.0))
        self.assertIn('stem.flatness', fails, fails)

    def test_tick_train_fires(self):
        rows, meta, fails = _stem_case('pad', lambda x: fx.add_tick(x, at=2.0))
        self.assertIn('stem.tick', fails, fails)

    def test_dead_stem_fires(self):
        rows, meta, fails = _stem_case('lead', lambda x: np.zeros_like(x))
        self.assertIn('stem.dead', fails, fails)

    def test_report(self):
        cases = [
            ('baseline', lambda s: s, None),
            ('click', lambda s: dict(s, pad=fx.add_click(s['pad'])), 'stem.clicks'),
            ('dropout', lambda s: dict(s, pad=fx.add_dropout(s['pad'])), 'stem.dropout'),
            ('cut', lambda s: dict(s, pad=fx.add_cut(s['pad'])), 'stem.cut'),
            ('truncate', lambda s: dict(s, pad=fx.truncate_end(s['pad'])), 'stem.end'),
            ('dc', lambda s: dict(s, bass=fx.add_dc(s['bass'])), 'stem.dc'),
            ('clip', lambda s: dict(s, lead=fx.clip_hard(s['lead'])), 'stem.clipping'),
            ('noise', lambda s: dict(s, pad=fx.add_noise_burst(s['pad'])), 'stem.flatness'),
            ('tick', lambda s: dict(s, pad=fx.add_tick(s['pad'])), 'stem.tick'),
            ('dead', lambda s: dict(s, lead=np.zeros_like(s['lead'])), 'stem.dead'),
        ]
        lines = ['case,expected,caught,fired']
        missed = []
        for name, mutate, expected in cases:
            stems = mutate(fx.build_stems())
            rows, meta = stem_gate.run_stem_gate(fx.score(), stems, sr=fx.SR, workers=1)
            fails = _rows(rows)
            ok = expected is None and not fails or expected in fails
            lines.append(f'{name},{expected or "none"},{ok},{";".join(sorted(fails))}')
            if not ok:
                missed.append(name)
        print('\n' + '\n'.join(lines))
        self.assertEqual(missed, [], f'gate missed: {missed}\n' + '\n'.join(lines))


class ProfileAdoptionTest(unittest.TestCase):
    """The stem gate runs the piece's own gate profile: a preset decides apply/relax/skip, with its reason."""

    def scored(self, overlay):
        s = fx.score()
        s['gate'] = overlay
        return s

    def noisy_pad(self):
        stems = fx.build_stems()
        stems['pad'] = fx.add_noise_burst(stems['pad'])
        return stems

    def test_a_skipped_row_reports_skip_and_does_not_fail(self):
        score = self.scored({'stem.flatness': {'mode': 'skip', 'reason': 'measured: the pad is deliberately noise'}})
        rows, meta = stem_gate.run_stem_gate(score, self.noisy_pad(), sr=fx.SR, workers=1)
        fails = _rows(rows)
        self.assertNotIn('stem.flatness', fails, fails)
        self.assertTrue([d for l, n, d in rows if n == 'stem.flatness' and 'SKIPPED' in d], rows)
        self.assertEqual(meta['profile'], 'melodic')

    def test_a_relaxed_parameter_is_the_one_used(self):
        score = self.scored({'stem.flatness': {'mode': 'relax', 'threshold': 0.35,
                                               'reason': 'measured: a noise-based pad reaches 0.19'}})
        rows, meta = stem_gate.run_stem_gate(score, self.noisy_pad(), sr=fx.SR, workers=1)
        self.assertNotIn('stem.flatness', _rows(rows), rows)

    def test_an_unknown_piece_type_fails_instead_of_being_ignored(self):
        score = fx.score()
        score['piece_type'] = 'not-a-profile'
        rows, meta = stem_gate.run_stem_gate(score, fx.build_stems(), sr=fx.SR, workers=1)
        self.assertIn('piece_type', _rows(rows), rows)


class MixGateTest(unittest.TestCase):
    """The same defects, injected into the summed mix, must reach the unsuffixed master rows."""

    @classmethod
    def setUpClass(cls):
        import quality_gate as qg
        cls.qg = qg
        cls.tmp = tempfile.mkdtemp(prefix='gate_mix_')

    def run_mix(self, mix):
        wav = os.path.join(self.tmp, 'mix.wav')
        sf.write(wav, mix, fx.SR)
        rows, _ = self.qg.run_gate(None, wav_path=wav, refresh=False, score=fx.score(), mode='draft')
        return rows

    @staticmethod
    def _level(rows, name):
        return next((l for l, n, _ in rows if n == name), None)

    def test_clean_mix_passes_the_new_rows(self):
        rows = self.run_mix(fx.build_mix(fx.build_stems()))
        for name in ('dropout', 'cut.hard', 'end.abrupt', 'master.dc', 'section.energy'):
            self.assertNotEqual(self._level(rows, name), 'FAIL', (name, rows))

    def test_mix_click_fails(self):
        mix = fx.add_click(fx.build_mix(fx.build_stems()), at=3.0, amp=0.5)
        self.assertEqual(self._level(self.run_mix(mix), 'clicks'), 'FAIL')

    def test_mix_dropout_fails(self):
        mix = fx.add_dropout(fx.build_mix(fx.build_stems()), at=3.0, ms=80)
        self.assertEqual(self._level(self.run_mix(mix), 'dropout'), 'FAIL')

    def test_mix_dc_fails(self):
        mix = fx.add_dc(fx.build_mix(fx.build_stems()), offset=0.01)
        self.assertEqual(self._level(self.run_mix(mix), 'master.dc'), 'FAIL')

    def test_mix_truncation_fails(self):
        mix = fx.truncate_end(fx.build_mix(fx.build_stems()), remove_s=1.0)
        self.assertEqual(self._level(self.run_mix(mix), 'end.abrupt'), 'FAIL')

    def test_mix_clipping_fails(self):
        mix = fx.clip_hard(fx.build_mix(fx.build_stems()), gain=4.0)
        self.assertEqual(self._level(self.run_mix(mix), 'clipping'), 'FAIL')


if __name__ == '__main__':
    unittest.main()
