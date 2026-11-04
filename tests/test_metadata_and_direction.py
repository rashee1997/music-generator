"""Metadata inside the delivered file, and the gate reading the direction sheet.

Covers: RIFF tags written into the WAV (samples untouched), the description from the direction sheet, the
sidecar for the versioned master, a tagging failure reported instead of swallowed, and the new direction rows
(wrong sample rate, wrong tempo, a key mismatch as FAIL in certify mode and WARN in draft, a missing sheet as FAIL in
certify mode and INFO in draft) plus stage 0's piece_type/gate_reason.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))

import quality_gate as qg  # noqa: E402
import project_gate  # noqa: E402
from helpers import ingest_metadata as im  # noqa: E402

SR = 44100


def write_wav(path, sr=SR, seconds=1.0, channels=2):
    t = np.arange(int(sr * seconds)) / sr
    x = 0.2 * np.sin(2 * np.pi * 220 * t)
    data = np.stack([x] * channels, 1) if channels > 1 else x
    sf.write(str(path), data, sr, subtype='PCM_16')
    return Path(path)


def rows_of(rows, name):
    return [r for r in rows if r[1] == name]


class TagsInsideTheWav(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)
        self.proj = self.dir / 'proj'
        (self.proj / 'direction').mkdir(parents=True)
        self.wav = write_wav(self.dir / 'master.wav')

    def tearDown(self):
        self.td.cleanup()

    def test_tags_are_written_into_the_wav_and_samples_are_untouched(self):
        before, sr_before = sf.read(str(self.wav))
        im.ingest(self.wav, overrides={'title': 'Cue', 'artist': 'Me', 'album': 'Album', 'date': '2026',
                                       'comment': 'fact', 'copyright': '(c) Me', 'license': 'CC-BY',
                                       'genre': 'Cinematic', 'tracknumber': '3'}, tag_audio=True)
        after, sr_after = sf.read(str(self.wav))
        self.assertEqual(sr_before, sr_after)
        np.testing.assert_array_equal(before, after)          # not one sample changed
        tags = im.read_wav_tags(self.wav)
        self.assertEqual(tags['title'], 'Cue')
        self.assertEqual(tags['artist'], 'Me')
        self.assertEqual(tags['license'], 'CC-BY')
        self.assertEqual(tags['tracknumber'], '3')

    def test_the_description_comes_from_the_direction_sheet(self):
        (self.proj / 'direction' / 'direction_x.json').write_text(json.dumps({
            'purpose': 'a slow adagio over the valley at dawn',
            'story': 'Mist, then a ridge, then the sun.'}), encoding='utf-8')
        im.ingest(self.wav, project_dir=self.proj, tag_audio=True)
        tags = im.read_wav_tags(self.wav)
        self.assertIn('adagio over the valley', tags['description'])
        self.assertIn('Mist, then a ridge', tags['description'])

    def test_without_a_sheet_the_factual_comment_stays(self):
        im.ingest(self.wav, score={'key': 'D', 'mode': 'minor', 'bpm': 84}, project_dir=self.proj, tag_audio=True)
        tags = im.read_wav_tags(self.wav)
        self.assertNotIn('description', tags)
        self.assertIn('D minor', tags['comment'])
        self.assertIn('84 BPM', tags['comment'])

    def test_a_tagging_failure_is_returned_not_swallowed(self):
        bad = self.dir / 'bad.wav'
        bad.write_bytes(b'not a riff file at all')
        result = im.ingest(bad, overrides={'title': 'x'}, tag_audio=True)
        self.assertTrue(result['tag_error'])
        self.assertTrue(Path(result['sidecar']).is_file())

    def test_the_versioned_master_gets_its_own_sidecar(self):
        proj = self.proj
        out = proj / 'out'
        out.mkdir()
        versioned = write_wav(out / 'master_v02.wav')
        result = im.ingest(versioned, project_dir=proj, extra={'version': 2})
        self.assertTrue((out / 'master_v02.json').is_file())
        self.assertEqual(json.loads(Path(result['sidecar']).read_text(encoding='utf-8'))['version'], 2)


class MetadataGateReadsTheFile(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.proj = Path(self.td.name) / 'p'
        (self.proj / 'out').mkdir(parents=True)
        self.wav = write_wav(self.proj / 'out' / 'master.wav')

    def tearDown(self):
        self.td.cleanup()

    def test_an_untagged_wav_is_a_warn_with_the_fix_command(self):
        (self.proj / 'out' / 'master.json').write_text(json.dumps({'metadata': {'title': 'T'}}), encoding='utf-8')
        rows = []
        qg.metadata_rows({'title': 'T'}, rows, project_dir=str(self.proj))
        meta = [r for r in rows if r[1] == 'meta']
        self.assertTrue(any(r[0] == 'WARN' and 'carries no tags' in r[2] for r in meta), meta)
        self.assertTrue(any('ingest_metadata.py' in r[2] for r in meta), meta)

    def test_tags_in_the_file_that_match_the_sidecar_pass(self):
        im.ingest(self.wav, overrides={'title': 'T'})
        rows = []
        qg.metadata_rows({'title': 'T'}, rows, project_dir=str(self.proj))
        self.assertTrue(any(r[0] == 'PASS' and 'inside the master' in r[2] for r in rows), rows)

    def test_a_mismatched_tag_warns(self):
        im.ingest(self.wav, overrides={'title': 'T'})
        sidecar = self.proj / 'out' / 'master.json'
        data = json.loads(sidecar.read_text(encoding='utf-8'))
        data['metadata']['title'] = 'Other'
        sidecar.write_text(json.dumps(data), encoding='utf-8')
        rows = []
        qg.metadata_rows({'title': 'T'}, rows, project_dir=str(self.proj))
        self.assertTrue(any(r[0] == 'WARN' and 'in-file title' in r[2] for r in rows), rows)


class DirectionRows(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.proj = Path(self.td.name) / 'p'
        (self.proj / 'direction').mkdir(parents=True)
        self.wav = write_wav(Path(self.td.name) / 'master.wav', sr=44100)
        self.sheet(dict(delivery={'sample_rate': 44100, 'bit_depth': 16, 'channels': 2},
                        duration_s=1.0, tempo_bpm=[80, 90], key='D', mode='minor'))

    def tearDown(self):
        self.td.cleanup()

    def sheet(self, data):
        (self.proj / 'direction' / 'direction_x.json').write_text(json.dumps(data), encoding='utf-8')

    def rows(self, score, mode='full'):
        out = []
        qg.direction_rows(score, out, project_dir=str(self.proj), wav_path=str(self.wav), mode=mode)
        return out

    def test_a_delivered_rate_that_breaks_the_sheet_fails(self):
        self.sheet(dict(delivery={'sample_rate': 48000, 'bit_depth': 16}, duration_s=1.0))
        rows = self.rows({'bpm': 85, 'key': 'D', 'mode': 'minor'})
        fail = rows_of(rows, 'delivery.sample_rate')
        self.assertEqual(fail[0][0], 'FAIL', fail)
        self.assertIn('48000', fail[0][2])

    def test_a_wrong_bit_depth_fails(self):
        self.sheet(dict(delivery={'sample_rate': 44100, 'bit_depth': 24}, duration_s=1.0))
        rows = self.rows({'bpm': 85})
        self.assertEqual(rows_of(rows, 'delivery.bit_depth')[0][0], 'FAIL')

    def test_a_tempo_outside_the_sheet_fails(self):
        rows = self.rows({'bpm': 120, 'key': 'D', 'mode': 'minor'})
        fail = rows_of(rows, 'tempo.bpm')
        self.assertEqual(fail[0][0], 'FAIL', fail)
        self.assertIn('120', fail[0][2])

    def test_a_tempo_inside_the_sheet_passes(self):
        rows = self.rows({'bpm': 84, 'key': 'D', 'mode': 'minor'})
        self.assertEqual(rows_of(rows, 'tempo.bpm')[0][0], 'PASS')

    def test_a_key_mismatch_fails_in_certify_mode_and_warns_in_draft(self):
        rows = self.rows({'bpm': 84, 'key': 'E', 'mode': 'minor'})
        key = rows_of(rows, 'key.mode')
        self.assertEqual(key[0][0], 'FAIL', key)
        draft = self.rows({'bpm': 84, 'key': 'E', 'mode': 'minor'}, mode='draft')
        self.assertEqual(rows_of(draft, 'key.mode')[0][0], 'WARN', draft)

    def test_no_sheet_fails_in_certify_mode_and_is_info_in_draft(self):
        (self.proj / 'direction' / 'direction_x.json').unlink()
        draft = self.rows({'bpm': 84}, mode='draft')
        self.assertTrue(all(r[0] == 'INFO' for r in draft), draft)
        self.assertIn('no direction', draft[0][2])
        full = self.rows({'bpm': 84})
        self.assertEqual(rows_of(full, 'delivery.direction')[0][0], 'FAIL', full)


class StageZeroNeedsAReason(unittest.TestCase):
    def test_a_sheet_without_gate_reason_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td)
            (proj / 'direction').mkdir()
            base = json.loads(Path(__file__).resolve().parent.parent.joinpath(
                'templates', 'direction_sheet.json').read_text(encoding='utf-8'))
            base['gate_reason'] = ''
            (proj / 'direction' / 'direction_x.json').write_text(json.dumps(base).replace('TODO', 'filled'), encoding='utf-8')
            problems = project_gate.direction_problems(proj)
            self.assertTrue(any('gate_reason' in p for p in problems), problems)
            base['gate_reason'] = 'a film cue builds with the picture, so the cinematic profile fits'
            (proj / 'direction' / 'direction_x.json').write_text(json.dumps(base).replace('TODO', 'filled'), encoding='utf-8')
            self.assertEqual(project_gate.direction_problems(proj), [])


if __name__ == '__main__':
    unittest.main()
