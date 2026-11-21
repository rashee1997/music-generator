"""scripts/arrange.py: a declared arrangement becomes a score, and a mistake in the declaration is an error."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import arrange  # noqa: E402

BASE = dict(
    title='T', bpm=120, ts=[4, 4], key='C', mode='major', seed=1,
    score=dict(piece_type='melodic', space='r', mix_preset='m'),
    scale=dict(pcs=[0, 2, 4, 7, 9]),
    shapes=dict(up=[1, 1, 2]),
    voicings=dict(pad=dict(A=[48, 55], B=[50, 57])),
    lines=dict(tune=[[0, 1, 60, 80], [1, 1, 64, 80], [2, 2, 67, 80]]),
    patterns=dict(p=dict(variants=[[dict(t=0, d=1, p='@pad[0]', v=60)], [dict(t=0, d=1, p='@pad[1]', v=60)]]),
                  drum=dict(variants=[[dict(t=0, d=.2, p='kick', v=70), dict(t=2, d=.2, p='kick', v=70)]])),
    runs=dict(r=dict(n=4, step=.1, v0=50, v1=70, tail=1.0, first=60, shape='up', ceiling=100)),
    tracks=dict(lead=dict(role='melody', lean=0.1), pad=dict(role='pad'), kit=dict(role='drum')),
    sections=[dict(name='a', bars=[1, 2], energy=.5, chords=['A', 'B']), dict(name='b', bars=[3, 4], energy=.8, chords=['B'])],
    events=[dict(track='lead', do='line', ref='tune', bar=1, octave=12),
            dict(track='pad', do='pattern', ref='p', bars=[1, 4], scale=dict(a=1.0, b=2.0)),
            dict(track='kit', do='pattern', ref='drum', bars=[1, 4], every=[2, 0]),
            dict(track='lead', do='run', ref='r', bar=2, beat=3.0),
            dict(track='lead', do='note', bar=4, beat=0, d=1, p='@pad[1]', v=50)])


def spec():
    return copy.deepcopy(BASE)


class Arrange(unittest.TestCase):
    def test_expands_to_a_score(self):
        s = arrange.build(spec())
        self.assertEqual([t['name'] for t in s['tracks']], ['lead', 'pad', 'kit'])
        self.assertEqual(s['space'], 'r')
        self.assertEqual([x['name'] for x in s['plan']['sections']], ['a', 'b'])
        self.assertAlmostEqual(s['plan']['sections'][1]['start_s'], 4.0)       # bar 3 of 120 BPM 4/4 starts at 4 s

    def test_line_octave_and_lean(self):
        lead = next(t for t in arrange.build(spec())['tracks'] if t['name'] == 'lead')
        first = lead['notes'][0]
        self.assertEqual(first['p'], 72)
        self.assertAlmostEqual(first['t'], 0.1)                                  # the track's lean, in beats

    def test_voicing_follows_the_chord_of_the_bar(self):
        pad = next(t for t in arrange.build(spec())['tracks'] if t['name'] == 'pad')
        # bar 1 chord A, variant 0 -> A[0]=48; bar 2 chord B, variant 1 -> B[1]=57
        self.assertEqual([n['p'] for n in pad['notes']][:2], [48, 57])

    def test_scale_by_section_and_every(self):
        s = arrange.build(spec())
        pad = next(t for t in s['tracks'] if t['name'] == 'pad')
        self.assertEqual([n['v'] for n in pad['notes']], [60, 60, 120, 120])
        kit = next(t for t in s['tracks'] if t['name'] == 'kit')
        self.assertEqual(len({round(n['t'] // 4) for n in kit['notes']}), 2)    # bars 2 and 4 only

    def test_vary_by_bar_survives_a_skipped_bar(self):
        sp = spec()
        sp['events'] = [dict(track='pad', do='pattern', ref='p', bars=[1, 4], skip=[1], vary='bar')]
        pad = next(t for t in arrange.build(sp)['tracks'] if t['name'] == 'pad')
        # bar 2 -> variant 1 (B[1]=57), bar 3 -> variant 0 (B[0]=50), bar 4 -> variant 1 (57)
        self.assertEqual([n['p'] for n in pad['notes']], [57, 50, 57])

    def test_run_stays_in_the_scale(self):
        lead = next(t for t in arrange.build(spec())['tracks'] if t['name'] == 'lead')
        run = [n for n in lead['notes'] if 6.9 < n['t'] < 8.0]
        self.assertTrue(run and all(n['p'] % 12 in (0, 2, 4, 7, 9) for n in run))

    def test_same_seed_same_score(self):
        a, b = spec(), spec()
        a['patterns']['p']['jitter'] = b['patterns']['p']['jitter'] = dict(v=3)
        self.assertEqual(json.dumps(arrange.build(a)), json.dumps(arrange.build(b)))

    def test_unknown_key_is_an_error(self):
        s = spec()
        s['bogus'] = 1
        with self.assertRaises(arrange.ArrangementError):
            arrange.build(s)
        s = spec()
        s['events'][0]['colour'] = 'red'
        with self.assertRaises(arrange.ArrangementError):
            arrange.build(s)

    def test_mistakes_are_errors_not_defaults(self):
        for mutate in (lambda s: s['events'][0].update(track='nobody'),
                       lambda s: s['events'][0].update(ref='missing'),
                       lambda s: s['events'][1].update(bars=[1, 9]),
                       lambda s: s['events'][1].update(scale=dict(a=1.0)),
                       lambda s: s['sections'].append(dict(name='c', bars=[4, 5], chords=['A']))):
            s = spec()
            mutate(s)
            with self.assertRaises(arrange.ArrangementError):
                arrange.build(s)

    def test_a_chord_without_a_voicing_is_an_error(self):
        s = spec()
        s['sections'][0]['chords'] = ['A', 'Z']
        with self.assertRaises(arrange.ArrangementError):
            arrange.build(s)


class Shipped(unittest.TestCase):
    """Every shipped project that is declared as data: the committed score is exactly what the engine writes."""
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _check(self, project, stem, tracks):
        p = os.path.join(self.ROOT, 'projects', project, 'scores', stem + '_arrangement.json')
        with open(p, encoding='utf-8') as fh:
            s = arrange.build(json.load(fh))
        self.assertEqual(len(s['tracks']), tracks)
        with open(p.replace('_arrangement', '_score'), encoding='utf-8') as fh:
            self.assertEqual(json.load(fh), json.loads(json.dumps(s)))

    def test_the_alarm_arrangement_builds(self):
        self._check('alarm_dawn', 'dawn_alarm', 10)

    def test_the_ringtone_arrangement_builds(self):
        self._check('ringtone_confluence', 'confluence', 10)


if __name__ == '__main__':
    unittest.main()
