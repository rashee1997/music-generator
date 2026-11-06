# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""The reel: certified cues placed in reel time, one program, one verdict."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'video-mixer'))

from deliver import reel            # noqa: E402

SR = 48000


def cue_wav(path, seconds, amp=0.2):
    t = np.arange(int(SR * seconds)) / SR
    y = (amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, np.repeat(y[:, None], 2, axis=1), SR, subtype='PCM_24')
    return path


class ReelBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.film = Path(self.tmp.name)
        (self.film / 'spotting').mkdir()
        (self.film / 'deliver').mkdir()
        (self.film / 'cues' / 'A').mkdir(parents=True)
        (self.film / 'cues' / 'B').mkdir(parents=True)
        cue_wav(self.film / 'cues' / 'A' / 'master.wav', 2.0, 0.2)
        cue_wav(self.film / 'cues' / 'B' / 'master.wav', 1.0, 0.1)

    def tearDown(self):
        self.tmp.cleanup()

    def sheet(self, cues):
        data = {'cues': cues}
        (self.film / 'spotting' / 'cuesheet.json').write_text(json.dumps(data), encoding='utf-8')
        return data


class TestPlacements(ReelBase):
    def test_placements_are_sorted_and_sized(self):
        data = self.sheet([
            dict(id='B', reel=1, in_s=3.0, duration_s=1.0, master='cues/B/master.wav'),
            dict(id='A', reel=1, in_s=0.0, duration_s=2.0, master='cues/A/master.wav'),
        ])
        places = reel.planned_placements(data, 1)
        self.assertEqual([p['id'] for p in places], ['A', 'B'])
        self.assertAlmostEqual(places[0]['end_s'], 2.0)
        self.assertAlmostEqual(places[1]['start_s'], 3.0)

    def test_out_s_gives_the_length_when_duration_is_missing(self):
        data = self.sheet([dict(id='A', in_s=1.0, out_s=4.0, master='cues/A/master.wav')])
        self.assertAlmostEqual(reel.planned_placements(data)[0]['length_s'], 3.0)

    def test_a_cue_without_a_length_is_an_error(self):
        data = self.sheet([dict(id='A', in_s=1.0, master='cues/A/master.wav')])
        with self.assertRaises(ValueError):
            reel.planned_placements(data)

    def test_another_reel_is_skipped(self):
        data = self.sheet([dict(id='A', reel=1, in_s=0.0, duration_s=2.0, master='cues/A/master.wav'),
                           dict(id='B', reel=2, in_s=0.0, duration_s=1.0, master='cues/B/master.wav')])
        self.assertEqual([p['id'] for p in reel.planned_placements(data, 1)], ['A'])


class TestAssembly(ReelBase):
    def test_cues_land_at_their_own_start(self):
        data = self.sheet([dict(id='A', reel=1, in_s=0.0, duration_s=2.0, master='cues/A/master.wav'),
                           dict(id='B', reel=1, in_s=3.0, duration_s=1.0, master='cues/B/master.wav')])
        audio, rep = reel.assemble(data, str(self.film), 5.0, {'sample_rate': SR})
        self.assertEqual(len(audio), 5 * SR)
        self.assertGreater(float(np.abs(audio[int(0.5 * SR):int(1.5 * SR)]).max()), 0.05)
        self.assertLess(float(np.abs(audio[int(2.2 * SR):int(2.8 * SR)]).max()), 1e-4)
        self.assertGreater(float(np.abs(audio[int(3.2 * SR):int(3.8 * SR)]).max()), 0.01)
        self.assertEqual(rep['placed'], 2)
        self.assertEqual(rep['overlaps'], [])

    def test_a_cue_is_trimmed_to_its_own_length(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=0.5, master='cues/A/master.wav')])
        audio, rep = reel.assemble(data, str(self.film), 3.0, {'sample_rate': SR})
        self.assertLess(float(np.abs(audio[int(0.7 * SR):int(2.0 * SR)]).max()), 1e-4)
        self.assertEqual(rep['cues'][0]['samples'], int(0.5 * SR))

    def test_overlap_is_reported_not_hidden(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=2.0, master='cues/A/master.wav'),
                           dict(id='B', in_s=1.5, duration_s=1.0, master='cues/B/master.wav')])
        _, rep = reel.assemble(data, str(self.film), 4.0, {'sample_rate': SR})
        self.assertEqual(len(rep['overlaps']), 1)
        rows = {n: lvl for lvl, n, _ in reel.reel_rows(rep)}
        self.assertEqual(rows['reel.overlap'], 'FAIL')

    def test_a_silent_cue_keeps_its_gap(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=2.0, master='cues/A/master.wav', silence=True)])
        audio, rep = reel.assemble(data, str(self.film), 3.0, {'sample_rate': SR})
        self.assertEqual(rep['placed'], 0)
        self.assertLess(float(np.abs(audio).max()), 1e-6)
        self.assertTrue(rep['cues'][0]['silence'])

    def test_a_missing_master_fails_the_reel(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=2.0, master='cues/A/nope.wav')])
        _, rep = reel.assemble(data, str(self.film), 3.0, {'sample_rate': SR})
        rows = {n: lvl for lvl, n, _ in reel.reel_rows(rep)}
        self.assertEqual(rows['reel.placement'], 'FAIL')
        self.assertEqual(reel.reel_verdict([], reel.reel_rows(rep))['status'], 'FAILED')

    def test_a_cue_past_the_reel_end_fails(self):
        data = self.sheet([dict(id='A', in_s=9.0, duration_s=2.0, master='cues/A/master.wav')])
        _, rep = reel.assemble(data, str(self.film), 10.0, {'sample_rate': SR})
        rows = {n: lvl for lvl, n, _ in reel.reel_rows(rep)}
        self.assertEqual(rows['reel.length'], 'FAIL')


class TestVerdict(unittest.TestCase):
    def test_a_failing_cue_fails_the_reel(self):
        cues = [{'title': 'M01', 'status': 'PASSED', 'ci_summary': {'fail': 0}},
                {'title': 'M02', 'status': 'FAILED', 'ci_summary': {'fail': 2}}]
        ver = reel.reel_verdict(cues, [('PASS', 'reel.overlap', 'none')])
        self.assertEqual(ver['status'], 'FAILED')
        self.assertEqual(ver['cue_fails'], 2)
        self.assertEqual(ver['uncertified_cues'], ['M02'])

    def test_a_clean_reel_passes(self):
        cues = [{'title': 'M01', 'status': 'PASSED', 'ci_summary': {'fail': 0}}]
        ver = reel.reel_verdict(cues, [('PASS', 'reel.overlap', 'none')])
        self.assertEqual(ver['status'], 'PASSED')

    def test_reel_rows_need_a_verdict(self):
        rows = [('PASS', 'reel.placement', '1 of 1 cues placed')]
        self.assertEqual(reel.reel_verdict([], rows)['status'], 'PASSED')


class TestWrite(ReelBase):
    def test_the_program_and_report_are_written(self):
        data = self.sheet([dict(id='A', in_s=0.0, duration_s=2.0, master='cues/A/master.wav')])
        audio, rep = reel.assemble(data, str(self.film), 3.0, {'sample_rate': SR})
        rows = reel.reel_rows(rep)
        wav, saved = reel.write_reel(str(self.film), 1, audio, rep, reel.reel_verdict([], rows))
        self.assertTrue(os.path.exists(wav))
        self.assertEqual(saved['reel'], 1)
        on_disk = json.loads((self.film / 'deliver' / 'reel_1_report.json').read_text(encoding='utf-8'))
        self.assertEqual(on_disk['placement']['placed'], 1)


if __name__ == '__main__':
    unittest.main()
