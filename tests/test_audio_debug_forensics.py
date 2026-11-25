"""The debug engine's signal-level evidence: who owns a click, whether the model can be believed, and bookkeeping."""
import json
import os
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import audio_debug                                  # noqa: E402
from audio_debug import catalog, forensics, history, zplace   # noqa: E402

SR = 44100


def _project(tmp, bed_gain=1.0, step=0.12):
    """Two stems: a noise bed (loud highs, the floor) and a 'perc' stem with one isolated HF step at 2.0 s."""
    rng = np.random.default_rng(3)
    n = SR * 4
    bed = (rng.standard_normal(n) * 0.01).astype(np.float32)
    perc = np.zeros(n, np.float32)
    k = int(2.0 * SR)
    perc[k:k + 3] = [step, -step, step]            # an isolated impulse: broadband, above the 6 kHz corner
    stems = {'bed': bed * bed_gain, 'perc': perc}
    os.makedirs(os.path.join(tmp, '.cache', 'mix', 'k1'))
    files = {}
    for nm, v in stems.items():
        p = os.path.join(tmp, '.cache', 'mix', 'k1', nm + '.npy')
        np.save(p, np.stack([v, v], 1))
        files[nm] = (p, SR)
    master = stems['bed'] + stems['perc']
    os.makedirs(os.path.join(tmp, 'out'))
    mp = os.path.join(tmp, 'out', 'master.wav')
    sf.write(mp, np.stack([master, master], 1), SR, subtype='FLOAT')
    score = {'tracks': [{'name': 'bed', 'instrument': 'env:rain', 'role': 'environment', 'notes': [{'t': 0, 'd': 8}]},
                        {'name': 'perc', 'instrument': 'Shaker One', 'role': 'percussion',
                         'notes': [{'t': 1.95, 'd': 0.2, 'p': 70, 'v': 0.5}]}]}
    return audio_debug.Case(tmp, score, [], {'inst_eq': {'shaker_one': [{'type': 'highshelf', 'f': 5500, 'gain': -3}]}},
                            {}, files, mp, {})


class Forensics(unittest.TestCase):
    def test_owner_is_the_stem_that_made_the_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = _project(tmp)
            mx = forensics.mixdown(c)
            self.assertGreater(mx.r2, 0.95)
            ev = forensics.explain_events(c, [2.0], mx)
            self.assertEqual(ev[0]['owners'][0]['stem'], 'perc')
            self.assertGreater(ev[0]['owners'][0]['share'], 0.7)

    def test_sham_replay_reproduces_the_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = _project(tmp)
            row = dict(row='clicks', raw={}, detail='')
            got = forensics.validate(c, row)
            self.assertTrue(got['ok'], got)
            self.assertGreater(got['gate'], 0)

    def test_cutting_the_owner_clears_but_cutting_the_bed_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = _project(tmp)
            mx = forensics.mixdown(c)
            base, _t = forensics.replay(c, {}, mx)
            self.assertGreater(base, 0)
            cut_owner, _t = forensics.replay(c, {'perc': 10 ** (-12 / 20)}, mx)
            self.assertLess(cut_owner, base)
            cut_bed, _t = forensics.replay(c, {'bed': 10 ** (-12 / 20)}, mx)
            self.assertGreaterEqual(cut_bed, base)          # the floor falls, the threshold falls with it

    def test_inst_eq_key_is_the_instrument_not_the_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = _project(tmp)
            self.assertEqual(catalog.inst_key(c, 'perc'), 'shaker_one')
            self.assertEqual(catalog.inst_key(c, 'bed'), 'env:rain')
            lv = {l.id: l for l in catalog.hf_levers(c)}
            self.assertEqual(lv['hf.perc'].current, -3.0)
            self.assertIn('inst_eq["env:rain"]', lv['hf.bed'].text)


class Bookkeeping(unittest.TestCase):
    def _case_with(self, tmp, row_value):
        c = _project(tmp)
        c.rows = [dict(row='clicks', level='FAIL' if row_value else 'PASS', value=row_value, threshold=0.0,
                       unit='events', stem=None, detail='', raw={})]
        return c

    def test_unchanged_stem_after_an_applied_move_is_unreachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._case_with(tmp, 2)
            fp = history.fingerprint(c, 'bed')
            os.makedirs(os.path.join(tmp, 'reports'))
            history.record(tmp, 'x', 'clicks', -3.0, 'proposed')       # noise; must be ignored
            entry = dict(stamp='s1', lever='hf.bed', row='clicks::-', delta=-3.0, outcome='proposed', baseline=0.0,
                         rows={'clicks::-': -2.0}, stem_hash=fp)
            with open(history.path(tmp), 'a') as fh:
                fh.write(json.dumps(entry) + '\n')
            lv = catalog.base.Lever('hf.bed', 'master', 'hf_shelf', -3.0, -15.0, 0.0, 0.5, 'dB', 't', stem='bed')
            done = history.settle(tmp, c, [lv], [])
            self.assertEqual([d['outcome'] for d in done], ['unreachable'])

    def test_improvement_is_better_not_no_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._case_with(tmp, 1)                                # 2 events before, 1 now
            os.makedirs(os.path.join(tmp, 'reports'))
            entry = dict(stamp='s2', lever='hf.perc', row='clicks::-', delta=-3.0, outcome='proposed', baseline=0.0,
                         rows={'clicks::-': -2.0}, stem_hash='different')
            with open(history.path(tmp), 'a') as fh:
                fh.write(json.dumps(entry) + '\n')
            lv = catalog.base.Lever('hf.perc', 'master', 'hf_shelf', -3.0, -15.0, 0.0, 0.5, 'dB', 't', stem='perc')
            done = history.settle(tmp, c, [lv], [])
            self.assertEqual([d['outcome'] for d in done], ['better'])

    def test_drift_blocks_settling(self):
        with tempfile.TemporaryDirectory() as tmp:
            c = self._case_with(tmp, 1)
            c.drift = ['presets/mix/x.json']
            self.assertEqual(history.settle(tmp, c, [], []), [])


class ZPlacement(unittest.TestCase):
    def _tab(self, az_b=3.0, role_b='counter'):
        parts = {'a': dict(az=0.0, el=0.0, role='counter', rendered=True),
                 'b': dict(az=az_b, el=0.0, role=role_b, rendered=True),
                 'c': dict(az=40.0, el=0.0, role='chord', rendered=True)}
        params = dict(overlap_min=0.5, min_sep=25.0, min_elev=15.0)

        def pair(x, y):
            daz = zplace._wrap(parts[x]['az'] - parts[y]['az'])
            return dict(a=x, b=y, overlap=0.8, sep=daz, daz=daz, delev=0.0, heights=True)
        pairs = [pair('a', 'b'), pair('a', 'c'), pair('b', 'c')]
        fights = [p for p in pairs if p['sep'] < 25 and p['delev'] < 15]
        return dict(params=params, parts=parts, pairs=pairs, fights=fights, unplaced=0)

    def test_solution_clears_every_pair_not_only_the_failing_one(self):
        tab = self._tab()
        sol = zplace.solve(tab)
        self.assertEqual(sol['status'], 'solved')
        az = {n: v['az'] for n, v in tab['parts'].items()}
        el = {n: v['el'] for n, v in tab['parts'].items()}
        for n, m in sol['moves'].items():
            az[n], el[n] = m['az'], m['el']
        self.assertEqual(zplace.verify(tab, az, el), [])

    def test_anchors_do_not_travel(self):
        tab = self._tab(role_b='bass')
        tab['parts']['a']['role'] = 'drum'
        sol = zplace.solve(tab)
        self.assertEqual(sol['status'], 'unsolvable')
        self.assertTrue(sol['anchors_blocked'])


if __name__ == '__main__':
    unittest.main()
