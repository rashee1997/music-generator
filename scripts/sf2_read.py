"""sf2_read.py - read the structure of a SoundFont 2 file (presets, instruments, zones) without loading its samples.

A pure-Python RIFF reader for the `pdta` lists. It answers one question the audit needs: how many velocity layers does
a preset have (the distinct `velRange` generator values, generator 44, in the instrument zones behind it). It does not
read sample data and does not judge sound. A SoundFont can also give velocity-dependent brightness through modulators;
zero zones therefore means "no sample switching", never "no response" (soundbank_audit.py measures the response).
"""
import struct

GEN_INSTRUMENT, GEN_VEL_RANGE, GEN_KEY_RANGE, GEN_SAMPLE_ID = 41, 44, 43, 53


def _chunks(buf, start, end):
    o = start
    while o + 8 <= end:
        tag = buf[o:o + 4]
        size = struct.unpack('<I', buf[o + 4:o + 8])[0]
        if tag == b'LIST':
            yield buf[o + 8:o + 12], o + 12, o + 8 + size
        else:
            yield tag, o + 8, o + 8 + size
        o += 8 + size + (size & 1)


def _records(blob, fmt):
    n = struct.calcsize(fmt)
    return [struct.unpack(fmt, blob[i:i + n]) for i in range(0, len(blob) - n + 1, n)]


def read(path):
    """{(bank, program): {'name', 'layers', 'zones', 'keys'}} for every preset of the file.

    layers: distinct velocity ranges behind the preset (0 when no zone restricts velocity);
    zones: instrument zones that carry a sample; keys: (lowest, highest) key any zone covers."""
    with open(path, 'rb') as fh:
        buf = fh.read()
    if buf[:4] != b'RIFF' or buf[8:12] != b'sfbk':
        raise ValueError(f'{path} is not a SoundFont 2 file')
    p = {}
    for tag, a, e in _chunks(buf, 12, len(buf)):
        if tag == b'pdta':
            for t, aa, ee in _chunks(buf, a, e):
                p[t] = buf[aa:ee]
    for need in (b'phdr', b'pbag', b'pgen', b'inst', b'ibag', b'igen'):
        if need not in p:
            raise ValueError(f'{path} has no {need.decode()} list (an .sf3 or a damaged file?)')
    ph, pb, pg = _records(p[b'phdr'], '<20sHHHIII'), _records(p[b'pbag'], '<HH'), _records(p[b'pgen'], '<Hh')
    ins, ib, ig = _records(p[b'inst'], '<20sH'), _records(p[b'ibag'], '<HH'), _records(p[b'igen'], '<Hh')

    def instrument(k):
        vel, keys, zones = set(), [128, -1], 0
        for z in range(ins[k][1], ins[k + 1][1]):
            has_sample, zv, zk = False, None, None
            for g in range(ib[z][0], ib[z + 1][0]):
                op, amt = ig[g]
                if op == GEN_SAMPLE_ID:
                    has_sample = True
                elif op == GEN_VEL_RANGE:
                    zv = (amt & 255, (amt >> 8) & 255)
                elif op == GEN_KEY_RANGE:
                    zk = (amt & 255, (amt >> 8) & 255)
            if not has_sample:
                continue
            zones += 1
            if zv is not None and zv != (0, 127):
                vel.add(zv)
            if zk is not None:
                keys[0], keys[1] = min(keys[0], zk[0]), max(keys[1], zk[1])
        return vel, keys, zones

    out = {}
    for i in range(len(ph) - 1):
        name = ph[i][0].split(b'\0')[0].decode('latin1').strip()
        vel, keys, zones = set(), [128, -1], 0
        for z in range(ph[i][3], ph[i + 1][3]):
            for g in range(pb[z][0], pb[z + 1][0]):
                if pg[g][0] == GEN_INSTRUMENT:
                    v, k, n = instrument(pg[g][1])
                    vel |= v
                    keys = [min(keys[0], k[0]), max(keys[1], k[1])]
                    zones += n
        out[(ph[i][2], ph[i][1])] = dict(name=name, layers=len(vel), zones=zones,
                                          keys=None if keys[1] < 0 else tuple(keys))
    return out
