"""The six cinematic realism dimensions, each with a positive and a negative control on synthetic signals."""
import os
import sys
import unittest

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import realism_cinema as rc      # noqa: E402
import realism_report as rr      # noqa: E402

SR = 22050
RNG = np.random.default_rng(3)


def tone(f, s, a=0.3):
    t = np.arange(int(s * SR)) / SR
    return a * np.sin(2 * np.pi * f * t)


def lowpass(x, hz):
    return signal.sosfilt(signal.butter(10, hz / (SR / 2), 'low', output='sos'), x)


class Sub(unittest.TestCase):
    def test_sub_lost_between_stem_and_master_warns(self):
        stems = {'kick': tone(45, 4), 'lead': tone(800, 4)}
        master = tone(800, 4) + 0.01 * tone(45, 4)
        self.assertEqual(rc.sub_weight(master, stems, SR)['verdict'], 'WARN')

    def test_sub_kept_passes_and_no_carrier_passes(self):
        stems = {'kick': tone(45, 4), 'lead': tone(800, 4)}
        self.assertEqual(rc.sub_weight(stems['kick'] + 0.5 * stems['lead'], stems, SR)['verdict'], 'PASS')
        self.assertEqual(rc.sub_weight(tone(800, 4), {'lead': tone(800, 4)}, SR)['carriers'], 0)


class Air(unittest.TestCase):
    def test_rolled_off_master_warns_and_names_band_limited_parts(self):
        noise = RNG.normal(0, 0.1, 4 * SR)
        r = rc.air(lowpass(noise, 5000), {'horn': lowpass(noise, 4500)}, SR)
        self.assertEqual(r['verdict'], 'WARN')
        self.assertEqual(r['band_limited'], 1)

    def test_open_master_passes(self):
        self.assertEqual(rc.air(RNG.normal(0, 0.1, 4 * SR), {}, SR)['verdict'], 'PASS')


class Scale(unittest.TestCase):
    def sections(self, levels):
        sec, x, t = [], [], 0.0
        for i, a in enumerate(levels):
            sec.append(dict(name=f's{i}', start_s=t, end_s=t + 3.0))
            x.append(tone(300, 3.0, a))
            t += 3.0
        return np.concatenate(x), {'plan': {'sections': sec}}

    def test_flat_loudness_warns_wide_passes(self):
        m, sc = self.sections([0.30, 0.31, 0.29, 0.30])
        self.assertEqual(rc.dynamic_scale(m, SR, sc)['verdict'], 'WARN')
        m, sc = self.sections([0.03, 0.10, 0.5, 0.05])
        self.assertEqual(rc.dynamic_scale(m, SR, sc)['verdict'], 'PASS')


class Impact(unittest.TestCase):
    def hits(self, soft):
        x = np.zeros(6 * SR)
        for k in range(4):
            i = int((0.5 + 1.4 * k) * SR)
            n = int(0.4 * SR)
            t = np.arange(n) / SR
            body = np.sin(2 * np.pi * 55 * t) * np.exp(-t * 8)
            if soft:
                body *= np.minimum(1.0, t / 0.12)                                    # a 120 ms swell: no click
            else:
                body += 0.8 * RNG.normal(0, 1, n) * np.exp(-t * 90)                  # a beater click
            x[i:i + n] += 0.5 * body
        return x

    def score(self):
        return {'tracks': [dict(name='drum1', role='drum')]}

    def test_soft_attack_warns_clicky_passes(self):
        self.assertEqual(rc.impact_attack({'drum1': self.hits(True)}, SR, self.score())['verdict'], 'WARN')
        self.assertEqual(rc.impact_attack({'drum1': self.hits(False)}, SR, self.score())['verdict'], 'PASS')

    def test_no_struck_part_is_not_applicable(self):
        self.assertEqual(rc.impact_attack({'a': tone(200, 2)}, SR, {'tracks': [dict(name='a', role='lead')]})['verdict'], 'N/A')


class Foreground(unittest.TestCase):
    def test_buried_voice_warns_audible_passes(self):
        loud = tone(200, 6, 0.5)
        sc = {'foreground': ['tick']}
        self.assertEqual(rc.foreground({'pad': loud, 'tick': tone(3000, 6, 0.02)}, SR, sc)['verdict'], 'WARN')
        self.assertEqual(rc.foreground({'pad': loud, 'tick': tone(3000, 6, 0.4)}, SR, sc)['verdict'], 'PASS')
        self.assertEqual(rc.foreground({'pad': loud}, SR, {})['verdict'], 'N/A')


class Harmony(unittest.TestCase):
    def score(self, roots):
        tracks = [dict(name='bass', role='bass', notes=[dict(t=4.0 * i, d=4.0, p=r) for i, r in enumerate(roots)])]
        return {'ts': '4/4', 'plan': {'sections': [dict(name='a', start_bar=1, end_bar=len(roots), start_s=0.0, end_s=30.0)]}, 'tracks': tracks}

    def test_one_note_pedal_over_a_long_section_warns_a_move_passes(self):
        self.assertEqual(rc.harmonic_motion(self.score([36] * 8))['verdict'], 'WARN')
        self.assertEqual(rc.harmonic_motion(self.score([36, 36, 41, 43, 36, 41, 43, 36]))['verdict'], 'PASS')

    def test_ts_written_as_a_list_works_like_a_string(self):
        s = self.score([36] * 8)
        s['ts'] = [4, 4]
        self.assertEqual(rc.harmonic_motion(s)['verdict'], 'WARN')
        s['ts'] = '4/4'
        self.assertEqual(rc.harmonic_motion(s)['verdict'], 'WARN')

    def test_drum_names_and_ambience_do_not_break_it(self):
        s = self.score([36, 41, 43, 36, 41, 43, 36, 41])
        s['tracks'].append(dict(name='kit', role='drum', notes=[dict(t=0.0, d=0.5, p='tabla_ge')]))
        s['tracks'].append(dict(name='amb', role='environment', notes=[dict(t=0.0, d=30.0, p=60)]))
        self.assertEqual(rc.harmonic_motion(s)['verdict'], 'PASS')

    def test_a_declared_pedal_is_respected(self):
        s = self.score([36] * 8)
        s['plan']['sections'][0]['pedal'] = True
        self.assertEqual(rc.harmonic_motion(s)['verdict'], 'PASS')


class Wiring(unittest.TestCase):
    def test_analyse_reports_the_six_dimensions(self):
        r = rr.analyse(np.stack([tone(300, 4), tone(300, 4)], 1), SR, stems={'a': np.stack([tone(300, 4), tone(300, 4)], 1)}, score={'tracks': [dict(name='a')]})
        for k in ('13_sub_weight', '14_air', '15_dynamic_scale', '16_impact_attack', '17_foreground', '18_harmonic_motion'):
            self.assertIn(k, r)
        rows = rr.rows_from(r)
        self.assertTrue(all(lv in ('WARN', 'PASS') for lv, _, _ in rows))
        self.assertIn('realism.sub_weight', [n for _, n, _ in rows])


if __name__ == '__main__':
    unittest.main()
