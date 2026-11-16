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
"""ADM BW64 (BS.2088 strict form + BS.2076): structural, routing and negative-control tests.

Synthetic signals and small temporary files only. Every property is asserted against the bytes and the
ADM in the file, never against a file name. No third-party BW64/ADM validator (libbw64/libadm) is available
in this environment, so these structural tests plus spatial_gate are the verification this repo can run --
the honest limit is stated in every failure message and in references/spatial/immersive-spatial.md.
"""
import os
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))

import spatial_gate
from spatial_engine import adm

SR = 44100
NS = {'e': 'urn:ebu:metadata-schema:ebuCore_2016'}


def _bus():
    return adm.AdmBus(SR, dict(enabled=True, height_by_role={'melody': 20.0, 'pad': 30.0},
                               max_elevation=60.0, pair=dict(width_deg_stereo=12.0, width_deg_bed=40.0)),
                      dict(title='t'))


def _write(tmp, bus, audio=None):
    audio = bus.result() if audio is None else audio
    adm.write(tmp, audio, SR, bus.xml(len(audio), SR), bus.chna())
    return audio


def _az(blk):
    return float(blk.find("e:position[@coordinate='azimuth']", NS).text)


def _el(blk):
    return float(blk.find("e:position[@coordinate='elevation']", NS).text)


def _dist(blk):
    return float(blk.find("e:position[@coordinate='distance']", NS).text)


class Container(unittest.TestCase):
    def test_report_fields(self):
        bus = _bus()
        bus.objects.append(('a', np.ones(100, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        rep = bus.report(100, SR)
        for key in ('renderer', 'container', 'sample_rate', 'bit_depth', 'channels', 'objects', 'bed',
                    'trajectory', 'loudness_method'):
            self.assertIn(key, rep)
        self.assertEqual(rep['container'], 'BW64 (ITU-R BS.2088, strict form)')
        self.assertEqual(rep['objects'], ['a'])
        self.assertEqual(rep['bed'], False)
    def _file(self, bus=None, audio=None):
        bus = bus or _bus()
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        _write(path, bus, audio)
        return path

    def test_bw64_structure(self):
        bus = _bus()
        bus.objects.append(('still', np.ones(4410, np.float32) * 0.1, 30.0, 10.0, 2.0, None, 'melody'))
        path = self._file(bus)
        raw = open(path, 'rb').read()
        self.assertEqual(raw[:4], b'BW64')
        self.assertEqual(struct.unpack('<I', raw[4:8])[0], 0xFFFFFFFF)
        self.assertEqual(raw[8:12], b'WAVE')
        self.assertEqual(raw[12:16], b'ds64')
        chunks = adm.read_chunks(path)
        self.assertEqual(list(chunks), ['ds64', 'fmt ', 'chna', 'axml', 'data'])
        dsz = struct.unpack('<QQQI', chunks['ds64'])
        self.assertEqual(dsz[0] + 8, len(raw))                       # bw64Size = file - 8
        self.assertEqual(dsz[1], 4410 * 1 * 3)                       # dataSize
        self.assertEqual(dsz[2], 0)
        self.assertEqual(dsz[3], 0)
        fmt = struct.unpack('<HHIIHH', chunks['fmt '])
        self.assertEqual(fmt, (1, 1, SR, SR * 3, 3, 24))
        self.assertEqual(len(chunks['chna']), 4 + 40 * 1)
        self.assertEqual(adm.validate_file(path), [])

    def test_riff_old_container_fails(self):
        """The regression this file exists to catch: the previous writer emitted a plain RIFF/WAVE with an
        axml and a chna chunk, and a .wav name let it pass as BW64. The gate must fail that structure."""
        fd, path = tempfile.mkstemp(suffix='_master_adm.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        bus = _bus()
        bus.objects.append(('a', np.ones(100, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        xml = bus.xml(100, SR)
        chna = bus.chna()
        # the old writer's layout: RIFF + fmt + chna + axml + data with 32-bit sizes
        fmt = struct.pack('<HHIIHH', 1, 1, SR, SR * 3, 3, 24)
        table = struct.pack('<HH', 1, len(chna)) + b''.join(
            struct.pack('<H12s14s11sx', i, u.encode(), t.encode(), p.encode()) for i, u, t, p in chna)
        data = struct.pack('<i', int(round(0.1 * 8388607)))[:3] * 100
        chunks = [(b'fmt ', fmt), (b'chna', table), (b'axml', xml), (b'data', data)]
        size = 4 + sum(8 + len(b) + len(b) % 2 for _, b in chunks)
        with open(path, 'wb') as f:
            f.write(b'RIFF' + struct.pack('<I', size) + b'WAVE')
            for tag, body in chunks:
                f.write(tag + struct.pack('<I', len(body)) + body + (b'\x00' if len(body) % 2 else b''))
        problems = adm.validate_file(path)
        self.assertTrue(any('not BW64' in p for p in problems), problems)
        out = []
        spatial_gate.output_rows(dict(output_targets=['stereo', 'adm_bw64'], tracks=[]), path, out)
        self.assertIn('FAIL', [r[0] for r in out if r[1] == 'adm.container'])

    def test_long_file_path_saturates_and_reads_back(self):
        """A data chunk too large for a 32-bit field gets 0xFFFFFFFF plus its true size in ds64 (BS.2088
        section 2.4). ``SATURATE_AT`` is lowered so this runs on a few kilobytes instead of 4 GiB."""
        bus = _bus()
        bus.objects.append(('a', np.ones(4000, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        audio = bus.result()
        old = adm.SATURATE_AT
        adm.SATURATE_AT = 64
        try:
            path = self._file(bus, audio)
        finally:
            adm.SATURATE_AT = old
        with open(path, 'rb') as fh:
            raw = fh.read()
        _magic, walk, _raw = adm._read_chunks_raw(path)
        data_size32 = [s for t, s, _o in walk if t == 'data']
        self.assertEqual(data_size32, [0xFFFFFFFF])
        chunks = adm.read_chunks(path)
        bw64_size, data_size, third, tlen = struct.unpack('<QQQI', chunks['ds64'][:28])
        self.assertEqual(data_size, audio.shape[0] * 3)        # true data size lives in ds64
        self.assertEqual(bw64_size + 8, len(raw))
        self.assertEqual(third, 0)
        # with SATURATE_AT lowered, the oversized non-data chunks are listed in the ds64 table too
        table = {}
        for i in range(tlen):
            tag = chunks['ds64'][28 + 12 * i:32 + 12 * i]
            table[tag] = struct.unpack('<Q', chunks['ds64'][32 + 12 * i:40 + 12 * i])[0]
        self.assertIn(b'axml', table)
        self.assertEqual(table[b'axml'], len(chunks['axml']))
        parsed = adm.parse(path)                               # the reader resolves it through ds64
        self.assertEqual((parsed['frames'], parsed['channels']), (audio.shape[0], 1))
        np.testing.assert_allclose(parsed['audio'][:, 0], audio[:, 0], atol=1.0 / 8388607.0 + 1e-7)
        self.assertEqual(adm.validate_file(path), [])

    def test_round_trip(self):
        bus = _bus()
        rng = np.random.default_rng(7)
        src = rng.standard_normal((SR // 2, 2)).astype(np.float32) * 0.05
        bus.objects.append(('a', src[:, 0], 10.0, 5.0, 1.5, None, 'melody'))
        bus.objects.append(('b', src[:, 1], -40.0, 0.0, 2.5, None, 'chord'))
        path = self._file(bus)
        audio = bus.result()
        parsed = adm.parse(path)
        self.assertEqual((parsed['sr'], parsed['channels'], parsed['frames']), (SR, 2, audio.shape[0]))
        np.testing.assert_allclose(parsed['audio'], audio, atol=1.0 / 8388607.0 + 1e-7)
        self.assertEqual(max(parsed['audio'].max(axis=0).tolist()), float(parsed['audio'].max()))


class FoldForStereoRows(unittest.TestCase):
    """An object file has no channels of its own until something renders it, so the stereo-shaped gate rows
    need a documented fold. These tests pin that fold to the bus's own reference fold."""

    def _file(self, bus):
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        audio = bus.result()
        adm.write(path, audio, SR, bus.xml(len(audio), SR), bus.chna())
        return path, audio

    def test_fold_matches_the_bus_reference_fold(self):
        bus = _bus()
        rng = np.random.default_rng(11)
        src = (rng.standard_normal((2000, 2)) * 0.05).astype(np.float32)
        bus.objects.append(('left', src[:, 0], -60.0, 0.0, 1.5, None, 'melody'))
        bus.objects.append(('right', src[:, 1], 60.0, 0.0, 1.5, None, 'chord'))
        bus.add_reverb((rng.standard_normal((2000, 2)) * 0.02).astype(np.float32))
        path, audio = self._file(bus)
        parsed = adm.parse(path)
        fold = adm.fold_to_stereo(parsed)
        ref = bus.stereo_fold(audio)
        self.assertEqual(fold.shape, (audio.shape[0], 2))
        np.testing.assert_allclose(fold, ref, atol=2e-7)

    def test_stereo_rows_measure_an_adm_master_instead_of_crashing(self):
        """An `adm_bw64` listed first is the certified master; libsndfile cannot open it, so the stereo rows
        must fold it (or fail with a row), never raise."""
        import quality_gate
        bus = _bus()
        # long enough for the loudness meter's block size, so the row measures rather than raising
        bus.objects.append(('a', np.ones(SR * 3, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        path, _audio = self._file(bus)
        dest = path.replace('.wav', '_master_adm.wav')
        os.replace(path, dest)
        self.addCleanup(lambda: os.path.exists(dest) and os.remove(dest))
        out = []
        quality_gate.audio_checks(dest, dict(tracks=[], output_targets=['adm_bw64', 'stereo']), out)
        names = [r[1] for r in out]
        self.assertIn('audio', names)                     # rows were measured through the fold
        self.assertNotIn('audio.read', names)             # and the file itself was readable
        self.assertTrue(any(r[0] == 'PASS' for r in out), out[:3])


class ObjectRouting(unittest.TestCase):
    def _file(self, bus):
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        audio = bus.result()
        adm.write(path, audio, SR, bus.xml(len(audio), SR), bus.chna())
        return path, audio

    def test_placed_stereo_becomes_two_objects(self):
        rng = np.random.default_rng(3)
        bus = _bus()
        lr = (rng.standard_normal((SR // 10, 2)) * 0.01).astype(np.float32)   # uncorrelated channels
        spec = dict(role='melody', spatial=dict(azimuth=30.0, elevation=10.0, distance=2.0))
        bus.add('stereo-track', lr, spec)
        names = [o[0] for o in bus.objects]
        self.assertEqual(names, ['stereo-track L', 'stereo-track R'])
        # left at azimuth minus the pair half-width (12 deg), right at plus (pair_half_width returns the
        # half-width directly, as used by the binaural router)
        self.assertAlmostEqual(bus.objects[0][2], 30.0 - 12.0, delta=1e-6)
        self.assertAlmostEqual(bus.objects[1][2], 30.0 + 12.0, delta=1e-6)
        # neither channel folded: each object holds its own channel (x the undone distance scalar of 2.0)
        np.testing.assert_allclose(bus.objects[0][1], lr[:, 0] * 2.0)

    def test_stereo_and_unpositioned_policies(self):
        bus = _bus()
        stereo = np.stack([np.ones(SR // 10, np.float32) * 0.1, np.ones(SR // 10, np.float32) * 0.2], axis=1)
        bus.add('flat', stereo, dict(role='melody', spatial=None))
        bus.add('out', stereo, dict(role='melody', spatial=dict(azimuth=99.0, binaural=False)))
        bus.add('one', np.ones(SR // 10, np.float32) * 0.1, dict(role='melody', spatial=None))
        bus.add('one-out', np.ones(SR // 10, np.float32) * 0.1,
                dict(role='melody', spatial=dict(azimuth=99.0, binaural=False)))
        pos = {o[0]: (o[2], o[3]) for o in bus.objects}
        self.assertEqual(pos['flat L'], (-30.0, 20.0))     # role height, split at +-30
        self.assertEqual(pos['flat R'], (30.0, 20.0))
        self.assertEqual(pos['out L'], (-30.0, 0.0))       # binaural false: out of the field, flat
        self.assertEqual(pos['one'], (0.0, 20.0))          # centred, role height
        self.assertEqual(pos['one-out'], (0.0, 0.0))
        self.assertEqual(bus.bed, None)
        self.assertEqual(bus.channel_count(), 2 + 2 + 1 + 1)
        # no bed channels and no bed object when the mix has no reverb return
        path, audio = self._file(bus)
        root = ET.fromstring(adm.parse(path)['axml'])
        self.assertEqual([o.get('audioObjectName') for o in root.findall('.//e:audioObject', NS)],
                         ['flat L', 'flat R', 'out L', 'out R', 'one', 'one-out'])

    def test_bed_only_with_reverb(self):
        bus = _bus()
        bus.objects.append(('a', np.ones(100, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        bus.add_reverb(np.ones((100, 2), np.float32) * 0.03)
        self.assertEqual(bus.channel_count(), 3)
        path, audio = self._file(bus)
        root = ET.fromstring(adm.parse(path)['axml'])
        self.assertEqual([o.get('audioObjectName') for o in root.findall('.//e:audioObject', NS)],
                         ['a', 'room return'])
        names = [r[1] for r in adm.parse(path)['chna']]
        self.assertEqual(names, ['ATU_00000001', 'ATU_00000002', 'ATU_00000003'])
        self.assertEqual(adm.validate_file(path), [])


class Metadata(unittest.TestCase):
    def _file(self, bus):
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        audio = bus.result()
        adm.write(path, audio, SR, bus.xml(len(audio), SR), bus.chna())
        return path

    def test_coordinate_convention(self):
        bus = _bus()
        bus.objects.append(('still', np.ones(4410, np.float32) * 0.1, 30.0, 10.0, 2.0, None, 'melody'))
        root = ET.fromstring(adm.parse(self._file(bus))['axml'])
        chan = root.findall('.//e:audioChannelFormat', NS)[0]
        blk = chan.findall('e:audioBlockFormat', NS)[0]
        self.assertAlmostEqual(_az(blk), -30.0)     # engine +30 (right) is ADM -30
        self.assertAlmostEqual(_el(blk), 10.0)      # elevation passes through
        self.assertAlmostEqual(_dist(blk), 2.0)     # metres written as the normalised distance

    def test_block_continuity_and_coverage(self):
        bus = _bus()
        p = np.zeros((SR // 64 + 2, 3), np.float32)
        p[:, 0] = np.linspace(-20, 50, len(p))      # 70 deg in 1 s: needs sub-0.1 s blocks
        p[:, 1] = 5.0
        p[:, 2] = 1.5
        bus.objects.append(('mover', np.ones(SR, np.float32) * 0.1, 0.0, 5.0, 1.5, p, 'melody'))
        rep = bus.report(SR, SR)
        self.assertLessEqual(rep['trajectory']['mover']['max_step_deg'], 2.5)
        root = ET.fromstring(adm.parse(self._file(bus))['axml'])
        blocks = root.findall('.//e:audioChannelFormat', NS)[0].findall('e:audioBlockFormat', NS)
        self.assertGreater(len(blocks), 5)
        prev_end = None
        for b in blocks:
            rt = adm._time_of(b.get('rtime'))
            dur = adm._time_of(b.get('duration'))
            self.assertGreater(dur, 0)
            self.assertAlmostEqual(rt, 0.0 if prev_end is None else prev_end, delta=2e-5)
            prev_end = rt + dur
        self.assertAlmostEqual(prev_end, 1.0, delta=2e-5)
        self.assertGreater(_az(blocks[0]), 10.0)    # first block near -20 engine -> +20 ADM
        self.assertLess(_az(blocks[-1]), -40.0)     # last block near +50 engine -> -50 ADM

    def test_chna_maps_every_channel(self):
        bus = _bus()
        for i in range(3):
            bus.objects.append((f'o{i}', np.ones(100, np.float32) * 0.1, 10 * i, 0.0, 1.5, None, 'melody'))
        parsed = adm.parse(self._file(bus))
        self.assertEqual(len(parsed['chna']), 3)
        self.assertEqual([r[0] for r in parsed['chna']], [1, 2, 3])
        objs = ET.fromstring(parsed['axml']).findall('.//e:audioObject', NS)
        refs = sorted(r.text.strip() for o in objs for r in o.findall('e:audioTrackUIDRef', NS))
        self.assertEqual(sorted(r[1] for r in parsed['chna']), refs)


class NegativeControls(unittest.TestCase):
    def _valid_file(self):
        bus = _bus()
        bus.objects.append(('a', np.ones(1000, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        fd, path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        audio = bus.result()
        adm.write(path, audio, SR, bus.xml(len(audio), SR), bus.chna())
        return path

    def test_malformed_bw64_structure(self):
        path = self._valid_file()
        raw = bytearray(open(path, 'rb').read())
        raw[12:16] = b'XXXX'   # ds64 renamed: no longer a BW64 file
        fd, bad = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(bad) and os.remove(bad))
        open(bad, 'wb').write(raw)
        self.assertTrue(adm.validate_file(bad))

    def test_bad_ids_and_references(self):
        root_id = None
        xml = adm.parse(self._valid_file())['axml']
        bad = xml.replace(b'AP_00031001', b'AP_00039999', 1)
        self.assertTrue(adm.validate_adm(bad, adm.parse(self._valid_file())['chna'],
                                        sr=SR, channels=1))

    def test_incorrect_channel_mapping(self):
        parsed = adm.parse(self._valid_file())
        problems = adm.validate_adm(parsed['axml'], parsed['chna'] + [(2, 'ATU_00000002',
                                        'AT_00031002_01', 'AP_00031002')], sr=SR, channels=1)
        self.assertTrue(any('chna has' in p for p in problems), problems)

    def test_missing_metadata(self):
        parsed = adm.parse(self._valid_file())
        self.assertTrue(adm.validate_adm(None, parsed['chna'], sr=SR, channels=1))

    def test_writer_refuses_non_finite_and_over_full_scale(self):
        bus = _bus()
        bus.objects.append(('a', np.ones(100, np.float32) * 0.1, 0.0, 0.0, 1.5, None, 'melody'))
        x = np.full((100, 1), np.nan, np.float32)
        with self.assertRaises(ValueError):
            adm.write('/tmp/_adm_nan.wav', x, SR, bus.xml(100, SR), bus.chna())
        y = np.full((100, 1), 1.5, np.float32)
        with self.assertRaises(ValueError):
            adm.write('/tmp/_adm_hot.wav', y, SR, bus.xml(100, SR), bus.chna())

    def test_invalid_trajectory_metadata(self):
        bus = _bus()
        p = np.full((100, 3), np.nan, np.float32)   # non-finite path
        bus.objects.append(('bad', np.ones(100, np.float32) * 0.1, 0.0, 0.0, 1.5, p, 'melody'))
        with self.assertRaises(ValueError):
            bus.xml(100, SR)
        bus2 = _bus()                               # elevation out of range
        bus2.objects.append(('bad2', np.ones(100, np.float32) * 0.1, 0.0, 200.0, 1.5, None, 'melody'))
        with self.assertRaises(ValueError):
            bus2.xml(100, SR)

    def test_gate_ceiling(self):
        # a file over the -3 dBTP ceiling must fail delivery.true_peak through the gate
        fd, hot = tempfile.mkstemp(suffix='_master_adm.wav')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(hot) and os.remove(hot))
        bus = _bus()
        t = np.arange(SR // 4) / SR
        bus.objects.append(('a', (0.99 * np.sin(2 * np.pi * 1000.0 * t)).astype(np.float32),
                            0.0, 0.0, 1.5, None, 'melody'))
        audio = bus.result()
        adm.write(hot, audio, SR, bus.xml(len(audio), SR), bus.chna())
        out = []
        spatial_gate.output_rows(dict(output_targets=['stereo', 'adm_bw64'], tracks=[]), hot, out)
        self.assertIn('FAIL', [r[0] for r in out if r[1] == 'delivery.true_peak'])

    def test_gate_finite_row(self):
        out = []
        spatial_gate.finite_row(np.array([[np.nan], [0.5]], np.float32), out, 'x.wav')
        self.assertEqual(out[0][0], 'FAIL')
        out = []
        spatial_gate.finite_row(np.zeros((10, 2), np.float32), out, 'x.wav')
        self.assertEqual(out[0][0], 'PASS')

    def test_gate_accepts_valid_adm(self):
        path = self._valid_file()
        dest = path.replace('.wav', '_master_adm.wav')
        os.rename(path, dest)
        self.addCleanup(lambda: os.path.exists(dest) and os.remove(dest))
        out = []
        spatial_gate.output_rows(dict(output_targets=['stereo', 'adm_bw64'], tracks=[]), dest, out)
        by_name = {}
        for lvl, name, detail in out:
            by_name.setdefault(name, []).append(lvl)
        self.assertNotIn('FAIL', [r for r in out if r[1] in ('adm.container', 'adm.channels', 'render.finite')])
        assert any(r[1] == 'adm.container' and r[0] == 'PASS' for r in out), out


if __name__ == '__main__':
    unittest.main()
