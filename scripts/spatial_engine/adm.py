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

"""adm.py - the mix as an object-based file: ADM metadata (ITU-R BS.2076) in a BW64 container (BS.2088).

Every placed track becomes one or two mono objects with its position over time: a mono placed track is one
object, a stereo placed track is two objects (left at azimuth minus half the pair width, right at azimuth plus
half the pair width), so neither channel is folded away. A track the piece keeps out of the 3-D field
(``binaural: false``) is two objects at +-30 degrees; a track with no ``spatial`` block at all follows the
mixer's stereo placement outcome and is split the same way, or is one centred object when mono. The shared
reverb return, when the mix has one, is a stereo bed (the common definition 0+2+0); when the mix has no
reverb return there are no bed channels at all. A renderer on the playback side (the EBU ADM Renderer, a DAW's
object panner) places the objects on whatever loudspeakers are there, which is the point of the format.

Coordinate conventions (BS.2076): azimuth is measured from straight ahead, positive to the *left*; elevation
is positive *up*; distance is normalised, with 1.0 the default sphere radius. This engine measures azimuth
positive to the *right*, so ADM azimuth is the negated engine azimuth (wrapped to [-180, 180)); elevation
passes through unchanged. Engine distance is in metres and is written as the ADM distance directly (1.0
corresponds to a 1 m default sphere radius; relative distances are preserved, the absolute scaling is the
renderer's). See ``references/spatial/immersive-spatial.md`` for the full conversion table.

The container is strict BW64 (BS.2088-2 section 2 and 3): the file starts with ``BW64`` + 0xFFFFFFFF +
``WAVE``, the first chunk is ``ds64`` carrying the 64-bit file size and data size, then ``fmt ``, ``chna``,
``axml`` and ``data`` -- always, even for files far below 4 GiB, so a BW64 file is recognisable by structure
alone, never by its ``.wav`` name. Audio is streamed to disk in bounded blocks; a file whose data exceeds
the 4 GiB limit is written with the saturated 32-bit fields the spec requires, never by downgrading to RIFF.
Clipping is never used to force compliance: a non-finite sample or a sample over full scale is an error.

The file is written here, without the EBU ``ear``/``libbw64``/``libadm`` libraries: their releases pin numpy
below 2 and would downgrade the whole environment. This is an open-standard ADM file, not a Dolby Atmos
master file, and it has not been through any vendor's certification. Verification is this module's own
structural check (``validate_file``) plus byte-level tests; no third-party BW64/ADM validator was run (none
is available in this environment -- see ``tests/test_adm_bw64.py``).

    bus = AdmBus(sr, imm, score); mixer.mix_stems(score, stems, sr, ctx, bus=bus)
    audio = bus.result(); write(path, audio, sr, bus.xml(len(audio), sr), bus.chna())
"""
import struct
import xml.etree.ElementTree as ET

import numpy as np

from . import trajectory

STEREO_DEG = 30.0
MAX_BLOCK_S = 0.1                      # a moving object's position is written at least this often
MIN_BLOCK_S = 0.005                    # ... and at most this often (bounds the block count)
MAX_STEP_DEG = 2.0                     # the largest angular step one block may carry (BS.2076 dynamic metadata)
MAX_BLOCKS = 5000                      # a longer stride is used instead of more blocks
BITS = 24
BED = (('FrontLeft', 'AT_00010001_01'), ('FrontRight', 'AT_00010002_01'))
BED_PACK = 'AP_00010002'
DW = struct.Struct('<I')
U32MAX = 0xFFFFFFFF
# A chunk whose bytes reach this size gets the saturated 0xFFFFFFFF 32-bit field and its true size in ds64.
# It is a module constant (not a literal in the writer) so a test can lower it and exercise the long-file
# path end to end on a small file, instead of trusting arithmetic that was never written to disk.
SATURATE_AT = U32MAX


def _time(seconds):
    s = round(max(0.0, float(seconds)), 5)
    return f'{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:08.5f}'


def _time_of(text):
    """ADM timecode ``hh:mm:ss.fffff`` -> seconds (the only form the writer emits)."""
    if not isinstance(text, str):
        raise ValueError(f'not an ADM timecode: {text!r}')
    parts = text.strip().split(':')
    if len(parts) != 3 or '.' not in parts[2]:
        raise ValueError(f'not an ADM timecode (hh:mm:ss.fffff): {text!r}')
    try:
        h, m = int(parts[0]), int(parts[1])
        s = float(parts[2])
    except ValueError:
        raise ValueError(f'not an ADM timecode (hh:mm:ss.fffff): {text!r}')
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
        raise ValueError(f'ADM timecode out of range: {text!r}')
    return h * 3600 + m * 60 + s


def _wrap180(v):
    """Engine azimuth (any range, e.g. 0..360 for a full turn) -> [-180, 180)."""
    return float(((float(v) + 180.0) % 360.0) - 180.0)


def _adm_position(engine_az, engine_el, engine_dist, name='object'):
    """Engine (az, el, dist) -> ADM (azimuth, elevation, distance), validated.

    Azimuth is negated (engine +right, ADM +left); elevation passes through; distance in metres is written
    as the normalised ADM distance directly. Anything non-finite or out of range is an error, never a clip.
    """
    az, el, d = float(engine_az), float(engine_el), float(engine_dist)
    if not np.isfinite(az) or not np.isfinite(el) or not np.isfinite(d):
        raise ValueError(f'object "{name}" has a non-finite position ({az}, {el}, {d})')
    if not -90.0 <= el <= 90.0:
        raise ValueError(f'object "{name}" elevation {el} is outside -90..90 degrees')
    if d < 0.0:
        raise ValueError(f'object "{name}" distance {d} is negative')
    return -_wrap180(az), el, d


class AdmBus:
    """A mixer bus that keeps every track apart and remembers where it is: add(name, signal, spec),
    add_reverb(signal), result().

    Objects are stored in *engine* coordinates (azimuth positive right) as (name, mono signal, azimuth,
    elevation, distance, path-or-None, role); the ADM sign conversion happens in ``xml()``. Only the tracks
    the caller hands over appear -- nothing is summed into a stereo master first.
    """

    places_tracks = True               # the mixer leaves placing to this bus, as it does for the ambisonic bus

    def __init__(self, sr=44100, imm=None, score=None):
        self.sr, self.imm, self.score = int(sr), imm or {}, score or {}
        self.objects, self.bed = [], None      # objects: (name, mono, az, el, dist, path|None, role)

    def add(self, name, y, spec):
        import mixer
        y = np.asarray(y, np.float32)
        if not y.size:
            return
        y = y if y.ndim == 2 else y[:, None]
        spec = dict(spec or {})
        sp = spec.get('spatial')
        role = str(spec.get('role') or '')
        if not sp or sp.get('binaural') is False:
            # Kept out of the 3-D field (or never placed): the stereo outcome is preserved as two mono
            # objects, a mono track as one centred object. Height follows the role (place_of), flattened
            # to 0 for an explicit binaural: false, per the "out of the field" reading of that flag.
            _az, _el, dist = mixer.place_of(spec, self.imm)
            el = 0.0 if sp is not None else _el
            if y.shape[1] == 1:
                self.objects.append((name, y[:, 0], 0.0, el, dist, None, role))
            else:
                for ch, az, tag in ((0, -STEREO_DEG, 'L'), (1, STEREO_DEG, 'R')):
                    self.objects.append((f'{name} {tag}', y[:, ch], az, el, dist, None, role))
            return
        az, el, dist = mixer.place_of(spec, self.imm)
        # mixer._place hands a placed track over to a places_tracks bus as (x / max(dist, 1.0)), with every
        # pan/width law bypassed. Undo that single division so the level is not applied twice (once here,
        # once by the renderer from the ADM distance); azimuth/elevation/distance live in the metadata.
        y = y * np.float32(max(dist, 1.0))
        traj = sp.get('trajectory')
        p = trajectory.path(traj, az, el, dist, len(y), self.sr, self.score)
        if p is not None and trajectory.is_anchor(traj, role):
            p = trajectory.anchor(p, az, el, dist, float(self.imm.get('anchor_max_span_deg', 6.0)))
        hw = mixer.pair_half_width(y, sp, self.imm) if y.shape[1] == 2 else 0.0
        if hw and hw > 0.0:
            # A stereo placed track: each channel keeps its own object, mirrored about the track centre.
            for ch, off, tag in ((0, -hw, 'L'), (1, hw, 'R')):
                q = None if p is None else p.copy()
                if q is not None:
                    q[:, 0] = q[:, 0] + off
                self.objects.append((f'{name} {tag}', y[:, ch], az + off, el, dist, q, role))
        else:
            # A mono placed track (or dual-mono stereo): one object; the mean of dual-mono is the signal.
            mono = y[:, 0] if y.shape[1] == 1 else y.mean(axis=1)
            self.objects.append((name, mono, az, el, dist, p, role))

    def add_reverb(self, ret):
        if ret is not None and len(ret):
            ret = np.asarray(ret, np.float32)
            self.bed = ret if ret.ndim == 2 else np.repeat(ret[:, None], 2, axis=1)
            if self.bed.shape[1] < 2:
                raise ValueError('the reverb return must have two channels to be a stereo bed')

    def channel_count(self):
        return len(self.objects) + (2 if self.bed is not None else 0)

    def result(self):
        """(n, objects [+ 2 bed channels]): one channel per object, then the bed's left and right (bed only
        when the mix has a reverb return)."""
        n = max([len(o[1]) for o in self.objects] + [len(self.bed) if self.bed is not None else 0] + [0])
        extra = 2 if self.bed is not None else 0
        out = np.zeros((n, len(self.objects) + extra), np.float32)
        for i, o in enumerate(self.objects):
            out[:len(o[1]), i] = o[1]
        if self.bed is not None:
            out[:len(self.bed), len(self.objects):] = self.bed[:, :2]
        return out

    def stereo_fold(self, audio):
        """A plain two-speaker fold of the objects (constant-power pan by azimuth) plus the bed: what the
        loudness of the file is measured on, since an object file has no loudness until something renders
        it. This fold is this engine's internal levelling reference, not a standard-required measurement --
        see the delivery docs."""
        n_obj = len(self.objects)
        out = np.zeros((len(audio), 2), np.float64)
        if self.bed is not None:
            out[:] += audio[:, n_obj:n_obj + 2]
        for i, (_, _, az, _el, _d, p, _role) in enumerate(self.objects):
            a = float(np.mean(p[:, 0])) if p is not None else float(az)
            th = (np.clip(((a + 180.0) % 360.0 - 180.0) / 90.0, -1.0, 1.0) + 1.0) * np.pi / 4.0
            out[:, 0] += audio[:, i] * np.cos(th)
            out[:, 1] += audio[:, i] * np.sin(th)
        return out.astype(np.float32)

    def chna(self):
        """[(track number from 1, track UID, track format, pack format)] for the chna chunk, in data-chunk
        order: one row per object channel, then the two bed tracks when a bed is present."""
        rows = [(i + 1, f'ATU_{i + 1:08X}', f'AT_{0x00031001 + i:08X}_01', f'AP_{0x00031001 + i:08X}')
                for i in range(len(self.objects))]
        k = len(self.objects)
        if self.bed is not None:
            rows = rows + [(k + 1 + j, f'ATU_{k + 1 + j:08X}', BED[j][1], BED_PACK) for j in (0, 1)]
        return rows

    def report(self, n_samples=None, sr=None):
        """What was actually exported, for the delivery report: renderer, container, layout counts,
        trajectory resolution and the measurement methods. Nothing here is a guess -- every field is either
        measured from the bus or names the code that measured it."""
        sr = int(sr or self.sr)
        n = int(n_samples) if n_samples is not None else max([len(o[1]) for o in self.objects] + [0])
        blocks = {}
        for o in self.objects:
            try:
                b = _blocks(o[5], n, sr, name=o[0]) if o[5] is not None else [(0.0, n / float(sr), o[2], o[3], o[4])]
            except ValueError:
                blocks[o[0]] = 'invalid'
                continue
            step = 0.0
            for a, bb in zip(b, b[1:]):
                step = max(step, abs(float(bb[2] - a[2])))
            blocks[o[0]] = dict(blocks=len(b), max_step_deg=round(step, 3))
        return dict(renderer='adm', container='BW64 (ITU-R BS.2088, strict form)',
                    sample_rate=sr, bit_depth=BITS, channels=self.channel_count(),
                    objects=[o[0] for o in self.objects], bed=self.bed is not None,
                    trajectory=blocks,
                    loudness_method='BS.1770 loudness of a constant-power stereo fold of the objects '
                                    '(engine-internal levelling reference; an object file has no loudness)')
    
    def xml(self, n, sr=None):
        """The axml chunk: ADM (BS.2076) in the canonical element order (programme, content, objects, packs,
        channel formats, stream formats, track formats, track UIDs)."""
        sr = int(sr or self.sr)
        if not self.objects and self.bed is None:
            raise ValueError('an ADM file needs at least one object or a bed; the bus is empty')
        for o in self.objects:
            _adm_position(o[2], o[3], o[4], name=o[0])   # fail before writing a millisecond of audio
        dur = _time(n / float(sr))
        root = ET.Element('ebuCoreMain', {'xmlns': 'urn:ebu:metadata-schema:ebuCore_2016', 'xml:lang': 'en'})
        afx = ET.SubElement(ET.SubElement(ET.SubElement(root, 'coreMetadata'), 'format'), 'audioFormatExtended',
                            version='ITU-R_BS.2076-2')
        title = str(self.score.get('title') or 'programme')
        chna = self.chna()
        # programme + content (content references every object, bed included)
        prog = ET.SubElement(afx, 'audioProgramme', audioProgrammeID='APR_1001', audioProgrammeName=title,
                             start=_time(0), end=dur)
        ET.SubElement(prog, 'audioContentIDRef').text = 'ACO_1001'
        content = ET.SubElement(afx, 'audioContent', audioContentID='ACO_1001', audioContentName=title)
        for i in range(len(self.objects)):
            ET.SubElement(content, 'audioObjectIDRef').text = f'AO_{0x1001 + i:04X}'
        if self.bed is not None:
            ET.SubElement(content, 'audioObjectIDRef').text = f'AO_{0x1001 + len(self.objects):04X}'
        # objects
        for i, o in enumerate(self.objects):
            oid = f'AO_{0x1001 + i:04X}'
            obj = ET.SubElement(afx, 'audioObject', audioObjectID=oid, audioObjectName=str(o[0]),
                                start=_time(0), duration=dur)
            hexid = f'{0x00031001 + i:08X}'
            ET.SubElement(obj, 'audioPackFormatIDRef').text = 'AP_' + hexid
            ET.SubElement(obj, 'audioTrackUIDRef').text = chna[i][1]
        # pack + channel formats (channel formats carry the position blocks)
        for i, o in enumerate(self.objects):
            hexid = f'{0x00031001 + i:08X}'
            pack = ET.SubElement(afx, 'audioPackFormat', audioPackFormatID='AP_' + hexid,
                                 audioPackFormatName=str(o[0]), typeLabel='0003', typeDefinition='Objects')
            ET.SubElement(pack, 'audioChannelFormatIDRef').text = 'AC_' + hexid
            chan = ET.SubElement(afx, 'audioChannelFormat', audioChannelFormatID='AC_' + hexid,
                                 audioChannelFormatName=str(o[0]), typeLabel='0003', typeDefinition='Objects')
            blocks = _blocks(o[5], n, sr, name=o[0]) if o[5] is not None else [(0.0, n / float(sr), o[2], o[3], o[4])]
            for b, (rt, d, a, e, dist) in enumerate(blocks):
                adm_az, adm_el, adm_d = _adm_position(a, e, dist, name=o[0])
                blk = ET.SubElement(chan, 'audioBlockFormat', audioBlockFormatID=f'AB_{hexid}_{b + 1:08X}',
                                    rtime=_time(rt), duration=_time(d))
                for coord, val in (('azimuth', adm_az), ('elevation', adm_el), ('distance', adm_d)):
                    ET.SubElement(blk, 'position', coordinate=coord).text = f'{val:.3f}'
        # stream + track formats
        for i, o in enumerate(self.objects):
            hexid = f'{0x00031001 + i:08X}'
            stream = ET.SubElement(afx, 'audioStreamFormat', audioStreamFormatID='AS_' + hexid,
                                   audioStreamFormatName='PCM_' + str(o[0]), formatLabel='0001',
                                   formatDefinition='PCM')
            ET.SubElement(stream, 'audioChannelFormatIDRef').text = 'AC_' + hexid
            ET.SubElement(stream, 'audioTrackFormatIDRef').text = f'AT_{hexid}_01'
            track = ET.SubElement(afx, 'audioTrackFormat', audioTrackFormatID=f'AT_{hexid}_01',
                                  audioTrackFormatName='PCM_' + str(o[0]), formatLabel='0001',
                                  formatDefinition='PCM')
            ET.SubElement(track, 'audioStreamFormatIDRef').text = 'AS_' + hexid
        # bed object: its pack is the 0+2+0 common definition (BS.2094), referenced, not redefined
        if self.bed is not None:
            bed_id = f'AO_{0x1001 + len(self.objects):04X}'
            bed = ET.SubElement(afx, 'audioObject', audioObjectID=bed_id, audioObjectName='room return',
                                start=_time(0), duration=dur)
            ET.SubElement(bed, 'audioPackFormatIDRef').text = BED_PACK
            for row in chna[-2:]:
                ET.SubElement(bed, 'audioTrackUIDRef').text = row[1]
        # track UIDs tie every chna row to the audio tracks in the file
        for _, uid, track_format, pack_format in chna:
            u = ET.SubElement(afx, 'audioTrackUID', UID=uid, sampleRate=str(sr), bitDepth=str(BITS))
            ET.SubElement(u, 'audioTrackFormatIDRef').text = track_format
            ET.SubElement(u, 'audioPackFormatIDRef').text = pack_format
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='utf-8')


def _blocks(path, n, sr, name='object'):
    """[(rtime_s, duration_s, az, el, dist)] for one moving object, contiguous to the file end.

    The stride adapts to the trajectory's fastest angular speed so one block never jumps more than
    MAX_STEP_DEG (and never more than MAX_BLOCK_S); the position written for a block is the path position
    at the block's end, so a renderer that interpolates between blocks reproduces the authored path. Edges
    are rounded to the ADM 1e-5 s grid and then deduped, so blocks tile [0, duration] exactly.
    """
    end = n / float(sr)
    if end <= 0:
        raise ValueError(f'object "{name}" has no samples to describe (n={n})')
    if path is None or len(path) < 2:
        raise ValueError(f'object "{name}" needs a trajectory path of at least two control points')
    if not np.isfinite(path).all():
        raise ValueError(f'object "{name}" has non-finite trajectory values')
    speed = trajectory.speed_deg_per_s(path, sr)
    interval = min(MAX_BLOCK_S, 0.9 * MAX_STEP_DEG / max(speed, 1e-6))
    interval = max(interval, MIN_BLOCK_S)
    nblocks = max(1, int(np.ceil(end / interval)))
    nblocks = min(nblocks, MAX_BLOCKS)
    edges = [round(min(float(v), end), 5) for v in np.linspace(0.0, end, nblocks + 1)]
    dedup = [edges[0]]
    for v in edges[1:]:
        if v > dedup[-1]:
            dedup.append(v)
    dedup[0], dedup[-1] = 0.0, round(end, 5)
    if len(dedup) < 2:
        raise ValueError(f'object "{name}" is too short for ADM timecodes (duration {end} s)')
    out = []
    for j in range(len(dedup) - 1):
        t_end = dedup[j + 1]
        k = min(len(path) - 1, int(round(t_end * sr / trajectory.HOP)))
        out.append((dedup[j], dedup[j + 1] - dedup[j], float(path[k, 0]), float(path[k, 1]), float(path[k, 2])))
    return out


# ---------------------------------------------------------------------------------------------
# BW64 container (ITU-R BS.2088-2): strict form, streamed
# ---------------------------------------------------------------------------------------------

def _chna_body(chna):
    if not chna:
        raise ValueError('an ADM file needs at least one chna row')
    ids = []
    for idx, uid, tf, pf in chna:
        ids.append(struct.pack('<H12s14s11sB', int(idx), uid.encode('ascii'), tf.encode('ascii'),
                               pf.encode('ascii'), 0))
    n = len(ids)
    return struct.pack('<HH', n, n) + b''.join(ids)


def _fmt_body(channels, sr):
    return struct.pack('<HHIIHH', 1, channels, int(sr), int(sr) * channels * 3, channels * 3, BITS)


def _pcm24_block(block):
    """float32 (frames, channels) -> 24-bit LE interleaved bytes, no clipping (|x| <= 1 already checked)."""
    pcm = np.ascontiguousarray(np.round(np.asarray(block, dtype=np.float64) * 8388607.0).astype('<i4'))   # a transposed view is not viewable as bytes
    return pcm.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()


def write(path, audio, sr, xml, chna):
    """Write a strict BW64 file: ``BW64`` header, ``ds64``, ``fmt ``, ``chna``, ``axml``, ``data``.

    The PCM is 24-bit. Audio is streamed in bounded blocks, so a data chunk past the 4 GiB limit is
    supported (the 32-bit fields are then saturated exactly as BS.2088 requires). A non-finite sample or
    a sample over full scale raises -- the writer never clips and never downgrades to RIFF.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[0] < 1 or audio.shape[1] < 1:
        raise ValueError(f'ADM audio must be (frames, channels) with at least 1 frame and 1 channel, '
                         f'got shape {audio.shape}')
    if not np.isfinite(audio).all():
        raise ValueError('ADM audio contains NaN or infinite samples; nothing was written')
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:
        raise ValueError(f'ADM audio peaks at {peak:.6f} (> 1.0 full scale); refusing to clip it -- '
                         f'lower the programme gain instead')
    channels, frames = audio.shape[1], audio.shape[0]
    if channels > 65535:
        raise ValueError(f'{channels} channels exceed the chna WORD track count')
    if not xml or not xml.startswith(b'<?xml'):
        xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + (xml or b'')
    chna_body = _chna_body(chna)
    if len(chna) != channels:
        raise ValueError(f'chna has {len(chna)} rows but the audio has {channels} channels; '
                         f'every channel must map to exactly one ADM track')
    fmt_body = _fmt_body(channels, sr)
    data_bytes = int(frames) * channels * 3
    # 64-bit addressing for any non-data chunk over 4 GiB goes in the ds64 table (BS.2088-2 pp. 10-11);
    # data uses the dedicated dataSize field instead, so it is not in the table.
    table = [(t, len(b)) for t, b in ((b'fmt ', fmt_body), (b'chna', chna_body), (b'axml', xml))
             if len(b) >= SATURATE_AT]
    ds64_len = 28 + 12 * len(table)
    total = 12 + (8 + ds64_len + ds64_len % 2) + (8 + len(fmt_body)) + (8 + len(chna_body)) + \
        (8 + len(xml) + len(xml) % 2) + (8 + data_bytes + data_bytes % 2)
    bw64_size = total - 8                                    # the WAVE+chunks size (RIFF ckSize definition)
    ds64_body = struct.pack('<QQQI', bw64_size, data_bytes, 0, len(table)) + b''.join(
        struct.pack('<4sQ', tag, ln) for tag, ln in table)   # dummies are zero when writing (BS.2088)
    chunks = [(b'ds64', ds64_body), (b'fmt ', fmt_body), (b'chna', chna_body), (b'axml', xml)]
    data_field = data_bytes if data_bytes < SATURATE_AT else U32MAX

    def _field(body):
        return len(body) if len(body) < SATURATE_AT else U32MAX

    with open(path, 'wb') as f:
        f.write(b'BW64' + DW.pack(U32MAX) + b'WAVE')
        for tag, body in chunks:
            f.write(tag + DW.pack(_field(body)) + body + (b'\x00' if len(body) % 2 else b''))
        f.write(b'data' + DW.pack(data_field))
        n_write, block = 1 << 20, 8192 * channels
        for start in range(0, frames, block):
            f.write(_pcm24_block(audio[start:start + block]))
        if data_bytes % 2:
            f.write(b'\x00')
    return path


def fold_to_stereo(parsed):
    """A two-channel fold of a parsed ADM file: the object channels panned by their first block's azimuth with
    constant power, plus any bed channel pair added straight in. It answers the same question ``AdmBus.stereo_fold``
    answers for a bus that has not been written yet, and is what lets the stereo-shaped gate rows describe an
    object file (which has no channels of its own until something renders it).

    The fold is the engine's internal reference, not a standard-required measurement: a renderer on the receiving
    side decides what a listener hears. Raises ValueError when the metadata cannot give each channel a position.
    """
    audio, chna = np.asarray(parsed['audio'], np.float32), parsed['chna'] or []
    if len(chna) != audio.shape[1]:
        raise ValueError(f'{len(chna)} chna rows for {audio.shape[1]} channels: cannot fold without a mapping')
    root = ET.fromstring(parsed['axml']) if parsed.get('axml') else None
    if root is None:
        raise ValueError('no axml: an object channel has no position to fold by')
    azimuth_of = {}
    for chan in root.findall('.//e:audioChannelFormat', _NS):
        cid = (chan.get('audioChannelFormatID') or '')
        blk = chan.find('e:audioBlockFormat', _NS)
        pos = blk.find("e:position[@coordinate='azimuth']", _NS) if blk is not None else None
        if pos is not None and (pos.text or '').strip():
            azimuth_of[cid] = float(pos.text)
    track_to_channel = {}
    for tr in root.findall('.//e:audioTrackFormat', _NS):
        tid = tr.get('audioTrackFormatID') or ''
        st = tr.find('e:audioStreamFormatIDRef', _NS)
        stream = (st.text or '').strip() if st is not None else ''
        for sm in root.findall('.//e:audioStreamFormat', _NS):
            if (sm.get('audioStreamFormatID') or '') != stream:
                continue
            ref = sm.find('e:audioChannelFormatIDRef', _NS)
            if ref is not None and (ref.text or '').strip():
                track_to_channel[tid] = (ref.text or '').strip()
    out = np.zeros((audio.shape[0], 2), np.float64)
    for i, (_idx, _uid, track_format, pack_format) in enumerate(chna):
        if pack_format == BED_PACK:            # a bed channel pair is already a stereo feed
            out[:, 0 if _idx % 2 else 1] += audio[:, i]
            continue
        cid = track_to_channel.get(track_format)
        if cid not in azimuth_of:
            raise ValueError(f'channel {i + 1} ({track_format}) has no object azimuth; cannot fold it')
        # ADM azimuth (+left) back to the engine's constant-power pan (+right)
        th = (np.clip(-azimuth_of[cid] / 90.0, -1.0, 1.0) + 1.0) * np.pi / 4.0
        out[:, 0] += audio[:, i] * np.cos(th)
        out[:, 1] += audio[:, i] * np.sin(th)
    return out.astype(np.float32)


def _read_chunks_raw(path):
    """Raw chunk walk of a RIFF / RF64 / BW64 file: (magic, {tag: (size32, offset, span)}, file length).

    Returns the declared 32-bit size and the payload offset of every chunk; 64-bit resolution (ds64) is
    applied by the caller. This is the only file access -- no audio is decoded here.
    """
    with open(path, 'rb') as f:
        raw = f.read()
    if len(raw) < 12:
        raise ValueError(f'{path}: file is only {len(raw)} bytes; not a WAVE file')
    magic = raw[:4].decode('ascii', 'replace')
    if magic not in ('RIFF', 'RF64', 'BW64') or raw[8:12] != b'WAVE':
        raise ValueError(f'{path}: first bytes are {magic!r} + {raw[8:12]!r}, not RIFF/RF64/BW64 + WAVE')
    chunks, pos, table, data_size = [], 12, {}, None
    while pos + 8 <= len(raw):
        tag = raw[pos:pos + 4].decode('ascii', 'replace')
        size32 = DW.unpack(raw[pos + 4:pos + 8])[0]
        if size32 == U32MAX:           # saturated: the true size lives in ds64 (BW64/RF64)
            size = data_size if tag == 'data' else table.get(tag)
            if size is None:
                size = len(raw) - (pos + 8)   # no ds64 entry: the chunk runs to the file end (data)
        else:
            size = size32
        chunks.append((tag, size32, pos + 8))
        if tag == 'ds64':
            try:
                _bw, data_size, _third, tlen = struct.unpack('<QQQI', raw[pos + 8:pos + 36])
                for i in range(tlen):
                    eoff = pos + 8 + 28 + 12 * i
                    table[raw[eoff:eoff + 4].decode('ascii', 'replace')] = \
                        struct.unpack('<Q', raw[eoff + 4:eoff + 12])[0]
            except struct.error:
                pass
        pos = pos + 8 + size + size % 2
        if size == len(raw) - (chunks[-1][2]):
            break                    # the chunk ran to the file end
    return magic, chunks, raw


def parse(path):
    """Read a BW64 (or legacy RIFF/RF64) file for verification: container facts, chna rows, axml bytes and
    the decoded 24-bit audio as float32 (frames, channels).

    Raises ValueError with an actionable message on malformed structure. Use ``validate_file`` for a
    problem list, and ``read_chunks`` for the raw chunk map.
    """
    magic, chunks, raw = _read_chunks_raw(path)
    by_tag = {}
    for tag, size32, off in chunks:
        by_tag.setdefault(tag, []).append((size32, off))
    if 'fmt ' not in by_tag:
        raise ValueError(f'{path}: no fmt chunk')
    fmt32, fmt_off = by_tag['fmt '][0]
    if fmt32 < 16 or fmt_off + 16 > len(raw):
        raise ValueError(f'{path}: fmt chunk is {fmt32} bytes, need 16')
    tag, channels, sr, byte_rate, block_align, bits = struct.unpack('<HHIIHH', raw[fmt_off:fmt_off + 16])
    if tag != 1:
        raise ValueError(f'{path}: fmt format tag is {tag:#06x}, only WAVE_FORMAT_PCM (0x0001) is supported')
    if bits != BITS:
        raise ValueError(f'{path}: fmt bits per sample is {bits}, only 24-bit PCM is supported')
    if 'data' not in by_tag:
        raise ValueError(f'{path}: no data chunk')
    ds64 = None
    if 'ds64' in by_tag:
        dsz, doff = by_tag['ds64'][0]
        if dsz < 28 or doff + 28 > len(raw):
            raise ValueError(f'{path}: ds64 chunk is {dsz} bytes, need at least 28')
        bw64_size, data_size, third, tlen = struct.unpack('<QQQI', raw[doff:doff + 28])
        table = {}
        for i in range(tlen):
            eoff = doff + 28 + 12 * i
            if eoff + 12 > len(raw):
                raise ValueError(f'{path}: ds64 table entry {i} runs past the file end')
            k = raw[eoff:eoff + 4].decode('ascii', 'replace')
            table[k] = struct.unpack('<Q', raw[eoff + 4:eoff + 12])[0]
        ds64 = dict(bw64_size=bw64_size, data_size=data_size, third=third, table=table)
    data32, data_off = by_tag['data'][0]
    data_bytes = ds64['data_size'] if ds64 else data32
    if data_bytes < 0 or data_off + data_bytes > len(raw):
        raise ValueError(f'{path}: data chunk declares {data_bytes} bytes but the file holds '
                         f'{max(0, len(raw) - data_off)}')
    if channels < 1 or block_align != channels * 3 or byte_rate != sr * channels * 3:
        raise ValueError(f'{path}: fmt disagrees with 24-bit PCM ({channels} ch, {sr} Hz: '
                         f'byteRate {byte_rate}, blockAlign {block_align})')
    if data_bytes % block_align:
        raise ValueError(f'{path}: data size {data_bytes} is not a whole number of '
                         f'{block_align}-byte frames')
    frames = data_bytes // block_align
    chna, axml = None, None
    if 'chna' in by_tag:
        sz, off = by_tag['chna'][0]
        ln = sz if sz != U32MAX else (ds64['table'].get('chna') if ds64 else sz)
        if ln is None or ln < 4 or off + ln > len(raw) or (ln - 4) % 40:
            raise ValueError(f'{path}: chna chunk size {ln} is not 4 + 40*N')
        ntr, nuid = struct.unpack('<HH', raw[off:off + 4])
        chna = []
        for i in range((ln - 4) // 40):
            tidx, uid, tref, pref, _pad = struct.unpack('<H12s14s11sB', raw[off + 4 + 40 * i:off + 44 + 40 * i])
            chna.append((tidx, uid.decode('ascii', 'replace'), tref.decode('ascii', 'replace'),
                         pref.decode('ascii', 'replace')))
        chna_count = (ntr, nuid)
    else:
        chna_count = None
    if 'axml' in by_tag:
        sz, off = by_tag['axml'][0]
        ln = sz if sz != U32MAX else (ds64['table'].get('axml') if ds64 else sz)
        if ln is None or off + ln > len(raw):
            raise ValueError(f'{path}: axml chunk size {ln} does not fit the file')
        axml = bytes(raw[off:off + ln])
    # 24-bit little-endian decode
    nb = np.frombuffer(raw, dtype=np.uint8, count=data_bytes, offset=data_off).reshape(-1, 3).astype(np.int32)
    vals = (nb[:, 0] | (nb[:, 1] << 8) | (nb[:, 2] << 16))
    vals = np.where(nb[:, 2] >= 128, vals - (1 << 24), vals)
    audio = (vals / 8388607.0).reshape(frames, channels).astype(np.float32)
    return dict(magic=magic, sr=sr, channels=channels, frames=frames, audio=audio, ds64=ds64,
                fmt=dict(tag=tag, byte_rate=byte_rate, block_align=block_align, bits=bits),
                chna=chna, chna_count=chna_count, axml=axml,
                chunks=[t for t, _, _ in chunks])


def read_chunks(path):
    """{chunk id: bytes} of a BW64/RIFF file (for checking what write() made): the declared payload of
    every chunk, including ``ds64`` for a BW64 file."""
    parsed = parse(path)
    chunks, raw = _read_chunks_raw(path)[1:]
    ds = parsed['ds64']
    by_tag = {}
    for tag, size32, off in chunks:
        ln = size32
        if size32 == U32MAX:
            ln = ds['data_size'] if tag == 'data' and ds else \
                 ds['table'].get(tag) if ds else len(raw) - off
        by_tag[tag] = bytes(raw[off:off + ln])
    return by_tag


# ---------------------------------------------------------------------------------------------
# Validation: structure + ADM integrity, so a gate row can fail the file, not just its name
# ---------------------------------------------------------------------------------------------

_NS = {'e': 'urn:ebu:metadata-schema:ebuCore_2016'}


def _is_common_def(id_value):
    """A BS.2094 common definition: the last four hex digits are 0x0FFF or below (BS.2094)."""
    for prefix in ('AP_', 'AC_', 'AT_', 'AS_'):
        if id_value and id_value.startswith(prefix):
            return (int(id_value[len(prefix):], 16) & 0xFFFF) <= 0x0FFF
    return False


def validate_adm(xml_bytes, chna, sr=None, channels=None):
    """ADM integrity problems for (axml, chna): well-formed XML, unique IDs, every reference resolved
    (defined locally or a BS.2094 common definition), and every chna row mapping to a real track UID.
    Returns a list of problem strings (empty = valid)."""
    problems = []
    if chna is not None and channels is not None and len(chna) != channels:
        problems.append(f'chna has {len(chna)} rows but fmt has {channels} channels')
    if xml_bytes is None:
        if chna:
            problems.append('no axml chunk: the ADM metadata is missing')
        return problems
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        return [f'axml is not well-formed XML ({e})']
    if root.tag != f"{{{_NS['e']}}}ebuCoreMain":
        problems.append(f'axml root is {root.tag!r}, expected ebuCoreMain')
        return problems
    defined, seen = {}, {}
    for el in root.iter():
        id_attr = next((v for k, v in el.attrib.items() if k.endswith('ID') or k in ('UID',)), None)
        if id_attr is None:
            continue
        if id_attr in seen:
            problems.append(f'ID {id_attr} is defined twice ({seen[id_attr]} and {el.tag.split("}")[-1]})')
        else:
            seen[id_attr] = el.tag.split('}')[-1]
            defined.setdefault(el.tag.split('}')[-1], set()).add(id_attr)
    for ref_tag, kind in (('audioPackFormatIDRef', 'audioPackFormat'), ('audioChannelFormatIDRef', 'audioChannelFormat'),
                          ('audioStreamFormatIDRef', 'audioStreamFormat'), ('audioTrackFormatIDRef', 'audioTrackFormat'),
                          ('audioTrackUIDRef', 'audioTrackUID'), ('audioObjectIDRef', 'audioObject'),
                          ('audioContentIDRef', 'audioContent')):
        for el in root.findall(f'.//e:{ref_tag}', _NS):
            v = (el.text or '').strip()
            if v == 'ATU_00000000':      # the virtual empty track: refers to no file track
                continue
            if v not in (defined.get(kind) or set()) and not (kind != 'audioTrackUID' and _is_common_def(v)):
                problems.append(f'{ref_tag} {v!r} does not resolve (not defined in axml, not a common definition)')
    uids = defined.get('audioTrackUID') or set()
    if chna:
        for idx, uid, tf, pf in chna:
            if uid not in uids:
                problems.append(f'chna track {idx} UID {uid} has no audioTrackUID in axml')
            u = root.find(f".//e:audioTrackUID[@UID='{uid}']", _NS)
            if u is not None:
                tfr = (u.findtext('e:audioTrackFormatIDRef', default='', namespaces=_NS) or '').strip()
                pfr = (u.findtext('e:audioPackFormatIDRef', default='', namespaces=_NS) or '').strip()
                if tfr != tf:
                    problems.append(f'chna track {idx} trackFormat {tf} disagrees with audioTrackUID ({tfr})')
                if pfr != pf:
                    problems.append(f'chna track {idx} packFormat {pf} disagrees with audioTrackUID ({pfr})')
        mapped = [u for _, u, _, _ in chna]
        for u in sorted(uids):
            if u not in mapped:
                problems.append(f'audioTrackUID {u} is defined but no chna row maps it to a track')
    if sr is not None:
        for u in root.findall('.//e:audioTrackUID', _NS):
            if u.get('sampleRate') not in (None, str(int(sr))):
                problems.append(f"audioTrackUID {u.get('UID')} sampleRate {u.get('sampleRate')} disagrees with fmt ({sr})")
    # blocks: first at 0, contiguous, positive durations, positions in range
    for chan in root.findall('.//e:audioChannelFormat', _NS):
        blocks = chan.findall('e:audioBlockFormat', _NS)
        cid = chan.get('audioChannelFormatID')
        if cid in seen and not blocks:
            problems.append(f'channel format {cid} has no audioBlockFormat')
        end_prev = None
        for b in blocks:
            try:
                rt = _time_of(b.get('rtime')) if b.get('rtime') else 0.0
                d = _time_of(b.get('duration')) if b.get('duration') else None
            except ValueError as e:
                problems.append(f'{cid} block {b.get("audioBlockFormatID")}: {e}')
                continue
            if end_prev is None and abs(rt) > 1e-5:
                problems.append(f'{cid} first block starts at {rt}, not 0')
            if end_prev is not None and abs(rt - end_prev) > 2e-5:
                problems.append(f'{cid} blocks are not contiguous: gap/overlap at {rt:.5f} '
                                f'(previous ends {end_prev:.5f})')
            if d is None or d <= 0:
                problems.append(f'{cid} block {b.get("audioBlockFormatID")} has no positive duration')
                continue
            end_prev = rt + d
            for coord, lo, hi in (('azimuth', -180.0, 180.0), ('elevation', -90.0, 90.0)):
                p = b.find(f"e:position[@coordinate='{coord}']", _NS)
                if p is None:
                    problems.append(f'{cid} block {b.get("audioBlockFormatID")} has no position {coord}')
                    continue
                try:
                    v = float((p.text or '').strip())
                except ValueError:
                    problems.append(f'{cid} position {coord} is not a number: {p.text!r}')
                    continue
                if not np.isfinite(v) or not lo <= v <= hi:
                    problems.append(f'{cid} position {coord}={v} is outside {lo}..{hi}')
            p = b.find("e:position[@coordinate='distance']", _NS)
            if p is not None:
                try:
                    v = float((p.text or '').strip())
                except ValueError:
                    v = float('nan')
                if not np.isfinite(v) or v < 0:
                    problems.append(f'{cid} position distance={p.text!r} is invalid')
    return problems


def validate_file(path, expect_sr=None):
    """Every structural problem with the file at ``path`` (empty list = a valid BW64 ADM deliverable).

    Checks the BW64 container itself (magic, ds64, fmt/chna/axml/data agreement) and the ADM integrity
    (``validate_adm``). Loudness, true peak and finite samples are measured by the gate on the parsed
    audio. A plain RIFF file, however good its audio, fails here: its container is not BW64.
    """
    problems = []
    try:
        magic, chunks, raw = _read_chunks_raw(path)
    except ValueError as e:
        return [str(e)]
    if magic == 'BW64':
        if raw[4:8] != DW.pack(U32MAX):
            problems.append('BW64 outer size field is not the saturated 0xFFFFFFFF')
    elif magic == 'RF64':
        problems.append('container is RF64 (EBU Tech 3306 v1), not the strict BW64 (BS.2088) form')
    else:
        problems.append('container is plain RIFF/WAVE, not BW64: there is no ds64 chunk and the 32-bit '
                        'sizes cap the file at 4 GiB')
        for tag, _size32, _off in chunks:
            if tag not in ('fmt ', 'chna', 'axml', 'data'):
                problems.append(f'chunk {tag!r} is not part of a minimal BW64 file')
        return problems + _validate_bodies(path, expect_sr)
    order = [t for t, _, _ in chunks]
    if order[:1] != ['ds64']:
        problems.append(f'the first chunk is {order[:1]!r}, not ds64 (it must follow the BW64 header)')
    for want in ('fmt ', 'chna', 'axml', 'data'):
        if want not in order:
            problems.append(f'missing {want} chunk')
    if 'data' in order and 'ds64' in order and order.index('ds64') > order.index('data'):
        problems.append('ds64 must precede data')
    if 'fmt ' in order and 'data' in order and order.index('fmt ') > order.index('data'):
        problems.append('fmt must precede data')
    problems += _validate_bodies(path, expect_sr)
    return problems


def _validate_bodies(path, expect_sr=None):
    problems = []
    try:
        parsed = parse(path)
    except ValueError as e:
        return [str(e)]
    magic, chunks, raw = _read_chunks_raw(path)
    if parsed['ds64'] is not None:
        if parsed['ds64']['bw64_size'] + 8 != len(raw):
            problems.append(f"ds64 bw64Size promises {parsed['ds64']['bw64_size']} bytes but the file "
                            f'is {len(raw)} bytes')
        if parsed['ds64']['third'] != 0:
            problems.append(f"ds64 dummy field is {parsed['ds64']['third']}, it shall be zero when writing")
    else:
        problems.append('no ds64 chunk: the 64-bit sizes are missing')
    if parsed['fmt']['tag'] != 1:
        problems.append('fmt format tag is not PCM')
    axml = parsed['axml']
    if axml is None:
        problems.append('no axml chunk: the ADM metadata is missing')
    chna = parsed['chna']
    if chna is None:
        problems.append('no chna chunk: no track-to-ADM mapping')
    else:
        ntr, nuid = parsed['chna_count']
        if nuid != len(chna):
            problems.append(f'chna numUIDs {nuid} disagrees with {len(chna)} rows')
        idxs = sorted(r[0] for r in chna)
        if idxs != list(range(1, len(chna) + 1)):
            problems.append(f'chna track indices {idxs} are not 1..{len(chna)} (each channel must map once)')
        uids = [r[1] for r in chna]
        if len(set(uids)) != len(uids):
            problems.append('chna UIDs are not unique')
        for idx, uid, tf, pf in chna:
            if not uid.startswith('ATU_') or len(uid) != 12:
                problems.append(f'chna track {idx} UID {uid!r} is not ATU_ + 8 hex')
            if not tf.startswith('AT_') or len(tf) != 14:
                problems.append(f'chna track {idx} trackFormat {tf!r} is not AT_ + 8 hex + _ + 2 hex')
            if not pf.startswith('AP_') or len(pf) != 11:
                problems.append(f'chna track {idx} packFormat {pf!r} is not AP_ + 8 hex')
    if axml is not None:
        # NOTE 2 of BS.2088-2 section 2.1 permits axml after data, so chunk placement is not judged here;
        # the writer emits it before data, where ADM readers expect to find it without seeking past the audio.
        problems += validate_adm(axml, chna or [], sr=parsed['sr'], channels=parsed['channels'])
    if expect_sr is not None and parsed['sr'] != expect_sr:
        problems.append(f"fmt sample rate {parsed['sr']} is not the expected {expect_sr}")
    return problems
