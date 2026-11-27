#!/usr/bin/env python3
"""soundbank_build.py - assemble one multi-velocity-layer SoundFont 2 from licensed sample sets.

The shipped General MIDI banks have one sample layer per instrument (measured: soundbank_audit.py), so loud and soft
differ only in level. This builds a bank whose programs have real velocity zones from sample files you hold the
licence for (VSCO 2 CE and VCSL are CC0, the Iowa MIS page says "no restrictions"; see docs/REALISM-ENHANCEMENT-PLAN.md).

    python scripts/soundbank_build.py <spec.json> -o assets/soundfonts/cinematic_default.sf2

spec.json
    { "name": "cinematic_default",
      "sources": [{"id": "vsco2_ce", "licence": "CC0 1.0", "url": "...", "licence_read": true}],
      "programs": [{"bank": 0, "program": 42, "name": "Cello",
                    "zones": [{"wav": "path.wav", "source": "vsco2_ce", "root": 48, "keys": [36, 52],
                               "vel": [1, 64], "loop": [start, end] | null}]}] }

A source with no licence, or with `licence_read` false, is refused: an unlicensed sample is all rights reserved. Samples are
16-bit mono WAV at one rate each. Nothing here reads a part name; the programs come from the spec.
"""
import json
import os
import struct
import sys
import wave

import numpy as np


class BuildError(ValueError):
    pass


def _chunk(tag, data):
    return tag + struct.pack('<I', len(data)) + data + (b'\0' if len(data) & 1 else b'')


def _list(kind, *chunks):
    body = kind + b''.join(chunks)
    return b'LIST' + struct.pack('<I', len(body)) + body


def _name(s, n=20):
    return s.encode('latin1', 'replace')[:n - 1].ljust(n, b'\0')


def read_wav(path):
    with wave.open(path, 'rb') as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise BuildError(f'{path}: samples must be 16-bit mono WAV')
        return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2'), w.getframerate()


def check_sources(spec):
    ids = {}
    for src in spec.get('sources', []):
        if not src.get('licence') or not src.get('licence_read'):
            raise BuildError(f'source "{src.get("id", "?")}" has no read licence: an unlicensed sample is all rights reserved')
        ids[src['id']] = src
    for prog in spec['programs']:
        for z in prog['zones']:
            if z.get('source') not in ids:
                raise BuildError(f'program "{prog["name"]}" uses source "{z.get("source")}", which the spec does not declare')
    return ids


def build(spec, base_dir='.'):
    """The bytes of the SoundFont for a spec."""
    check_sources(spec)
    smpl, shdr = bytearray(), []
    sample_index = {}
    for prog in spec['programs']:
        for z in prog['zones']:
            wav = os.path.join(base_dir, z['wav'])
            if wav in sample_index:
                continue
            data, rate = read_wav(wav)
            start = len(smpl) // 2
            smpl += data.tobytes() + bytes(2 * 46)             # 46 zero points after every sample (SF2 2.04 rule)
            loop = z.get('loop') or [0, 0]
            shdr.append(struct.pack('<20sIIIIIBbHH', _name(os.path.splitext(os.path.basename(wav))[0]), start, start + len(data),
                                    start + int(loop[0]), start + int(loop[1]), rate, int(z['root']), 0, 0, 1))
            sample_index[wav] = len(shdr) - 1
    shdr.append(struct.pack('<20sIIIIIBbHH', _name('EOS'), 0, 0, 0, 0, 0, 0, 0, 0, 0))

    phdr, pbag, pgen, inst, ibag, igen = [], [], [], [], [], []
    for prog in spec['programs']:
        inst.append(struct.pack('<20sH', _name(prog['name']), len(ibag)))
        for z in prog['zones']:
            ibag.append(struct.pack('<HH', len(igen), 0))
            igen.append(struct.pack('<Hbb', 43, int(z['keys'][0]), int(z['keys'][1])))
            igen.append(struct.pack('<Hbb', 44, int(z['vel'][0]), int(z['vel'][1])))
            if z.get('loop'):
                igen.append(struct.pack('<Hh', 54, 1))          # sampleModes: loop continuously
            igen.append(struct.pack('<Hh', 58, int(z['root'])))
            igen.append(struct.pack('<HH', 53, sample_index[os.path.join(base_dir, z['wav'])]))
        phdr.append(struct.pack('<20sHHHIII', _name(prog['name']), int(prog['program']), int(prog['bank']), len(pbag), 0, 0, 0))
        pbag.append(struct.pack('<HH', len(pgen), 0))
        pgen.append(struct.pack('<HH', 41, len(inst) - 1))
    phdr.append(struct.pack('<20sHHHIII', _name('EOP'), 0, 0, len(pbag), 0, 0, 0))
    pbag.append(struct.pack('<HH', len(pgen), 0))
    pgen.append(struct.pack('<HH', 0, 0))
    inst.append(struct.pack('<20sH', _name('EOI'), len(ibag)))
    ibag.append(struct.pack('<HH', len(igen), 0))
    igen.append(struct.pack('<HH', 0, 0))
    pmod = struct.pack('<HHhHH', 0, 0, 0, 0, 0)
    imod = struct.pack('<HHhHH', 0, 0, 0, 0, 0)
    info = _list(b'INFO', _chunk(b'ifil', struct.pack('<HH', 2, 1)), _chunk(b'isng', b'EMU8000\0'),
                 _chunk(b'INAM', spec.get('name', 'built').encode('latin1', 'replace') + b'\0'),
                 _chunk(b'ICOP', ('; '.join(f"{s['id']} {s['licence']}" for s in spec.get('sources', []))).encode('latin1', 'replace') + b'\0'))
    sdta = _list(b'sdta', _chunk(b'smpl', bytes(smpl)))
    pdta = _list(b'pdta', _chunk(b'phdr', b''.join(phdr)), _chunk(b'pbag', b''.join(pbag)), _chunk(b'pmod', pmod),
                 _chunk(b'pgen', b''.join(pgen)), _chunk(b'inst', b''.join(inst)), _chunk(b'ibag', b''.join(ibag)),
                 _chunk(b'imod', imod), _chunk(b'igen', b''.join(igen)), _chunk(b'shdr', b''.join(shdr)))
    body = b'sfbk' + info + sdta + pdta
    return b'RIFF' + struct.pack('<I', len(body)) + body


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('spec')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args(argv)
    with open(a.spec, encoding='utf-8') as fh:
        spec = json.load(fh)
    data = build(spec, os.path.dirname(os.path.abspath(a.spec)))
    with open(a.out, 'wb') as fh:
        fh.write(data)
    print(f'wrote {a.out} ({len(data) / 1e6:.1f} MB, {len(spec["programs"])} programs)')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except BuildError as exc:
        sys.stderr.write(f'soundbank_build: {exc}\n')
        sys.exit(2)
