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

"""adm.py - the mix as an object-based file: ADM metadata (ITU-R BS.2076) in a BW64 / WAV container (BS.2088).

Every placed track is one mono object with its position over time; a track the piece keeps out of the 3-D field
is two objects at +-30 degrees; the shared reverb return is a stereo bed (the common definition 0+2+0). A renderer
on the playback side (the EBU ADM Renderer, a DAW's object panner) places the objects on whatever loudspeakers are
there, which is the point of the format.

The file is written here, without the EBU `ear` library: its release pins numpy below 2 and would downgrade the
whole environment. It is an open-standard ADM file, not a Dolby Atmos master file.

    bus = AdmBus(sr, imm, score); mixer.mix_stems(score, stems, sr, ctx, bus=bus)
    audio = bus.result(); write(path, audio, sr, bus.xml(len(audio), sr), bus.chna())
"""
import struct
import xml.etree.ElementTree as ET

import numpy as np

from . import trajectory

STEREO_DEG = 30.0
BLOCK_S = 0.1                          # how often a moving object's position is written
BED = (('FrontLeft', 'AT_00010001_01'), ('FrontRight', 'AT_00010002_01'))
BED_PACK = 'AP_00010002'
RIFF_LIMIT = 0xFFFFFFFF


def _time(seconds):
    s = round(max(0.0, float(seconds)), 5)
    return f'{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:08.5f}'


class AdmBus:
    """A mixer bus that keeps every track apart and remembers where it is: add(name, signal, spec),
    add_reverb(signal), result()."""
    places_tracks = True               # the mixer leaves placing to this bus, as it does for the ambisonic bus

    def __init__(self, sr=44100, imm=None, score=None):
        self.sr, self.imm, self.score = int(sr), imm or {}, score or {}
        self.objects, self.bed = [], None      # objects: (name, mono signal, azimuth, elevation, path or None)

    def add(self, name, y, spec):
        import mixer
        y = np.asarray(y, np.float32)
        if not y.size:
            return
        y = y if y.ndim == 2 else y[:, None]
        spec = dict(spec or {})
        sp = spec.get('spatial')
        if not sp or sp.get('binaural') is False:
            if y.shape[1] == 1:
                self.objects.append((name, y[:, 0], 0.0, 0.0, None))
            else:
                for ch, az, tag in ((0, -STEREO_DEG, 'L'), (1, STEREO_DEG, 'R')):
                    self.objects.append((f'{name} {tag}', y[:, ch], az, 0.0, None))
            return
        az, el, dist = mixer.place_of(spec, self.imm)
        traj = sp.get('trajectory')
        p = trajectory.path(traj, az, el, dist, len(y), self.sr, self.score)
        if p is not None and trajectory.is_anchor(traj, spec.get('role')):
            p = trajectory.anchor(p, az, el, dist, float(self.imm.get('anchor_max_span_deg', 6.0)))
        self.objects.append((name, y.mean(axis=1), az, el, p))

    def add_reverb(self, ret):
        if ret is not None and len(ret):
            ret = np.asarray(ret, np.float32)
            self.bed = ret if ret.ndim == 2 else np.repeat(ret[:, None], 2, axis=1)

    def result(self):
        """(n, objects + 2): one channel per object, then the bed's left and right."""
        n = max([len(o[1]) for o in self.objects] + [len(self.bed) if self.bed is not None else 0])
        out = np.zeros((n, len(self.objects) + 2), np.float32)
        for i, o in enumerate(self.objects):
            out[:len(o[1]), i] = o[1]
        if self.bed is not None:
            out[:len(self.bed), -2:] = self.bed[:, :2]
        return out

    def stereo_fold(self, audio):
        """A plain two-speaker fold of the objects (constant-power pan by azimuth) plus the bed: what the loudness
        of the file is measured on, since an object file has no loudness until something renders it."""
        out = np.array(audio[:, -2:], dtype=np.float64)
        for i, (_, _, az, _, p) in enumerate(self.objects):
            a = float(np.mean(p[:, 0])) if p is not None else az
            th = (np.clip(((a + 180.0) % 360.0 - 180.0) / 90.0, -1.0, 1.0) + 1.0) * np.pi / 4.0
            out[:, 0] += audio[:, i] * np.cos(th)
            out[:, 1] += audio[:, i] * np.sin(th)
        return out.astype(np.float32)

    def chna(self):
        """[(track number from 1, track UID, track format, pack format)] for the chna chunk."""
        rows = [(i + 1, f'ATU_{i + 1:08X}', f'AT_{0x00031001 + i:08X}_01', f'AP_{0x00031001 + i:08X}')
                for i in range(len(self.objects))]
        k = len(self.objects)
        return rows + [(k + 1 + j, f'ATU_{k + 1 + j:08X}', BED[j][1], BED_PACK) for j in (0, 1)]

    def xml(self, n, sr=None):
        """The axml chunk. This engine's azimuth grows to the right; ADM's grows to the left, so it is negated."""
        sr = int(sr or self.sr)
        dur = _time(n / float(sr))
        root = ET.Element('ebuCoreMain', {'xmlns': 'urn:ebu:metadata-schema:ebuCore_2016', 'xml:lang': 'en'})
        afx = ET.SubElement(ET.SubElement(ET.SubElement(root, 'coreMetadata'), 'format'), 'audioFormatExtended',
                            version='ITU-R_BS.2076-2')
        title = str(self.score.get('title') or 'programme')
        prog = ET.SubElement(afx, 'audioProgramme', audioProgrammeID='APR_1001', audioProgrammeName=title,
                             start=_time(0), end=dur)
        ET.SubElement(prog, 'audioContentIDRef').text = 'ACO_1001'
        content = ET.SubElement(afx, 'audioContent', audioContentID='ACO_1001', audioContentName=title)
        chna = self.chna()
        for i, (name, _, az, el, p) in enumerate(self.objects):
            hexid = f'{0x00031001 + i:08X}'
            oid = f'AO_{0x1001 + i:04X}'
            ET.SubElement(content, 'audioObjectIDRef').text = oid
            obj = ET.SubElement(afx, 'audioObject', audioObjectID=oid, audioObjectName=str(name),
                                start=_time(0), duration=dur)
            ET.SubElement(obj, 'audioPackFormatIDRef').text = 'AP_' + hexid
            ET.SubElement(obj, 'audioTrackUIDRef').text = chna[i][1]
            pack = ET.SubElement(afx, 'audioPackFormat', audioPackFormatID='AP_' + hexid,
                                 audioPackFormatName=str(name), typeLabel='0003', typeDefinition='Objects')
            ET.SubElement(pack, 'audioChannelFormatIDRef').text = 'AC_' + hexid
            chan = ET.SubElement(afx, 'audioChannelFormat', audioChannelFormatID='AC_' + hexid,
                                 audioChannelFormatName=str(name), typeLabel='0003', typeDefinition='Objects')
            if p is None:
                blocks = [(None, None, az, el)]
            else:                                          # a block glides to its position over its own length
                stride = max(1, int(round(BLOCK_S * sr / trajectory.HOP)))
                idx = list(range(0, len(p), stride))
                t = [k * trajectory.HOP / float(sr) for k in idx]
                end = n / float(sr)
                # times are written to 1e-5 s: round the block edges first, so that each block's start plus its
                # length is exactly the next block's start (the EBU renderer rejects a file where they differ)
                t = [round(min(v, end), 5) for v in t]
                keep = [k for k in range(1, len(idx)) if t[k] > t[k - 1]]
                t[keep[-1]] = round(end, 5)                # the last block runs to the end of the object
                blocks = [(t[k - 1], t[k] - t[k - 1], p[idx[k], 0], p[idx[k], 1]) for k in keep]
            for b, (rt, d, a, e) in enumerate(blocks):
                attrs = {'audioBlockFormatID': f'AB_{hexid}_{b + 1:08X}'}
                if rt is not None:
                    attrs.update(rtime=_time(rt), duration=_time(d))
                blk = ET.SubElement(chan, 'audioBlockFormat', attrs)
                a = -(((float(a) + 180.0) % 360.0) - 180.0)
                for coord, val in (('azimuth', a), ('elevation', float(np.clip(e, -90.0, 90.0))), ('distance', 1.0)):
                    ET.SubElement(blk, 'position', coordinate=coord).text = f'{val:.3f}'
            stream = ET.SubElement(afx, 'audioStreamFormat', audioStreamFormatID='AS_' + hexid,
                                   audioStreamFormatName='PCM_' + str(name), formatLabel='0001', formatDefinition='PCM')
            ET.SubElement(stream, 'audioChannelFormatIDRef').text = 'AC_' + hexid
            ET.SubElement(stream, 'audioTrackFormatIDRef').text = f'AT_{hexid}_01'
            track = ET.SubElement(afx, 'audioTrackFormat', audioTrackFormatID=f'AT_{hexid}_01',
                                  audioTrackFormatName='PCM_' + str(name), formatLabel='0001', formatDefinition='PCM')
            ET.SubElement(track, 'audioStreamFormatIDRef').text = 'AS_' + hexid
        bed_id = f'AO_{0x1001 + len(self.objects):04X}'
        ET.SubElement(content, 'audioObjectIDRef').text = bed_id
        bed = ET.SubElement(afx, 'audioObject', audioObjectID=bed_id, audioObjectName='room return',
                            start=_time(0), duration=dur)
        ET.SubElement(bed, 'audioPackFormatIDRef').text = BED_PACK       # a common definition: not declared here
        for row in chna[-2:]:
            ET.SubElement(bed, 'audioTrackUIDRef').text = row[1]
        for _, uid, track_format, pack_format in chna:
            u = ET.SubElement(afx, 'audioTrackUID', UID=uid, sampleRate=str(sr), bitDepth='24')
            ET.SubElement(u, 'audioTrackFormatIDRef').text = track_format
            ET.SubElement(u, 'audioPackFormatIDRef').text = pack_format
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8')


def write(path, audio, sr, xml, chna):
    """A 24-bit WAV with the two ADM chunks: `chna` ties each track to its ADM ids, `axml` carries the metadata."""
    audio = np.asarray(audio, np.float32)
    channels = audio.shape[1]
    pcm = np.round(np.clip(audio, -1.0, 1.0) * 8388607.0).astype('<i4')
    data = pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    fmt = struct.pack('<HHIIHH', 1, channels, int(sr), int(sr) * channels * 3, channels * 3, 24)
    table = struct.pack('<HH', channels, len(chna)) + b''.join(
        struct.pack('<H12s14s11sx', idx, uid.encode(), tf.encode(), pf.encode()) for idx, uid, tf, pf in chna)
    chunks = [(b'fmt ', fmt), (b'chna', table), (b'axml', xml), (b'data', data)]
    size = 4 + sum(8 + len(body) + len(body) % 2 for _, body in chunks)
    if size > RIFF_LIMIT:
        # shortcut: plain RIFF only (4 GiB); write the BW64 `ds64` chunk when a piece is ever that long
        raise ValueError(f'the ADM file would be {size / 2 ** 30:.1f} GiB; a RIFF file holds 4 GiB')
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', size) + b'WAVE')
        for tag, body in chunks:
            f.write(tag + struct.pack('<I', len(body)) + body + (b'\x00' if len(body) % 2 else b''))
    return path


def read_chunks(path):
    """{chunk id: bytes} of a RIFF/WAVE file (for checking what write() made)."""
    with open(path, 'rb') as f:
        raw = f.read()
    out, pos = {}, 12
    while pos + 8 <= len(raw):
        tag, size = raw[pos:pos + 4], struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        out[tag.decode('ascii')] = raw[pos + 8:pos + 8 + size]
        pos += 8 + size + size % 2
    return out
