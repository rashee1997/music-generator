#!/usr/bin/env python3
"""soundbank_audit.py - measure a SoundFont bank, family by family, so a default is chosen by numbers and not by name.

For every instrument family (references/data/presets/families/families.json) it plays that family's audit programs
through the same synth the renderer uses and reports

  layers          velocity zones behind the program (sf2_read), median over the family
  centroid_ratio  spectral centroid of the same held note at velocity 120 over velocity 40 (a one-layer bank sits at 1.0)
  air_db          share of 8-16 kHz power in the loud note, in dB (a band-limited sample set shows here)
  sustain_ok      the held note is still sounding 1 s in (a program that dies at once cannot play a sustained part)

and writes assets/soundfonts/audit/<bank>.json. `choose(family, installed)` then walks references/data/presets/banks/default.json
and returns the first bank that is installed and meets the thresholds for the family, else the fallback.

    python scripts/soundbank_audit.py <bank key | path.sf2> [--families bowed,blown_brass] [--json]
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import families as fam_mod                      # noqa: E402
import sf2_read                                 # noqa: E402

AUDIT_DIR = os.path.join(HERE, '..', 'assets', 'soundfonts', 'audit')
POLICY = os.path.join(HERE, '..', 'references', 'data', 'presets', 'banks', 'default.json')
SR = 44100
NOTE = 60                  # starting value: middle C, inside the range of every audit program
HOLD_S, TAIL_S = 1.6, 0.2
SOFT, LOUD = 40, 120       # starting values: a piano and a forte-fortissimo MIDI velocity


def policy():
    with open(POLICY, encoding='utf-8') as fh:
        return json.load(fh)


def centroid_and_air(x, sr=SR):
    """(spectral centroid in Hz, 8-16 kHz share in dB) of a mono signal."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < 2048 or not np.any(x):
        return 0.0, -200.0
    n = 1 << int(np.floor(np.log2(len(x))))
    sp = np.abs(np.fft.rfft(x[:n] * np.hanning(n))) ** 2
    f = np.fft.rfftfreq(n, 1.0 / sr)
    tot = float(sp.sum()) + 1e-30
    return float((f * sp).sum() / tot), float(10 * np.log10(sp[(f >= 8000) & (f < 16000)].sum() / tot + 1e-30))


def _play(path, program, velocity, bank=0):
    import tinysoundfont
    s = tinysoundfont.Synth(samplerate=SR, gain=0)
    sfid = s.sfload(path)
    s.program_select(0, sfid, bank, program)
    s.noteon(0, NOTE, velocity)
    a = np.frombuffer(bytes(s.generate(int(HOLD_S * SR))), dtype=np.float32).reshape(-1, 2).mean(1)
    s.noteoff(0, NOTE)
    return a


def audit_program(path, program, bank=0):
    soft, loud = _play(path, program, SOFT, bank), _play(path, program, LOUD, bank)
    c_s, _ = centroid_and_air(soft[int(0.05 * SR):int(0.8 * SR)])
    c_l, air = centroid_and_air(loud[int(0.05 * SR):int(0.8 * SR)])
    tail = loud[int(1.2 * SR):int(1.5 * SR)]
    body = loud[int(0.1 * SR):int(0.4 * SR)]
    sustain = bool(len(tail) and np.sqrt(np.mean(tail ** 2)) > 0.05 * (np.sqrt(np.mean(body ** 2)) + 1e-12))
    return dict(program=program, centroid_ratio=round(c_l / c_s, 3) if c_s > 0 else 0.0, air_db=round(air, 1), sustain_ok=sustain)


def audit(path, only=None):
    """The audit document of one bank file: per family, per program, and the family medians."""
    layers = sf2_read.read(path)
    out = {}
    for fam, entry in fam_mod.table()['families'].items():
        if only and fam not in only:
            continue
        rows = []
        for prog in entry['audit_programs']:
            info = layers.get((0, prog))
            if info is None:
                continue
            r = audit_program(path, prog)
            r.update(name=info['name'], layers=info['layers'])
            rows.append(r)
        if rows:
            out[fam] = dict(programs=rows,
                            layers=float(np.median([r['layers'] for r in rows])),
                            centroid_ratio=float(np.median([r['centroid_ratio'] for r in rows])),
                            air_db=float(np.median([r['air_db'] for r in rows])),
                            sustained=float(np.mean([r['sustain_ok'] for r in rows])))
    return dict(bank=os.path.basename(path), families=out)


def meets(entry, thresholds):
    """(ok, reasons it failed) for one family entry of an audit document."""
    why = []
    if entry['layers'] < thresholds['min_layers']:
        why.append(f"{entry['layers']:g} velocity layers (< {thresholds['min_layers']})")
    if entry['centroid_ratio'] < thresholds['min_centroid_ratio']:
        why.append(f"centroid ratio {entry['centroid_ratio']:.2f} (< {thresholds['min_centroid_ratio']})")
    if entry['air_db'] < thresholds['min_air_db']:
        why.append(f"8-16 kHz share {entry['air_db']:.0f} dB (< {thresholds['min_air_db']})")
    return (not why), why


def load(key, directory=None):
    p = os.path.join(directory or AUDIT_DIR, f'{key}.json')
    try:
        with open(p, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def choose(family, installed, pol=None, directory=None):
    """(bank key, why). `installed` is a set of bank keys on this machine. The first listed bank that is installed, audited
    and meets the thresholds wins; the fallback otherwise. A family with no list gets the fallback."""
    pol = pol or policy()
    order = pol['order'].get(family) or []
    notes = []
    for key in order:
        if key == pol['fallback']:
            return key, '; '.join(notes + ['fallback reached'])
        if key not in installed:
            notes.append(f'{key}: not installed')
            continue
        doc = load(key, directory)
        entry = (doc or {}).get('families', {}).get(family)
        if entry is None:
            notes.append(f'{key}: not audited for {family}')
            continue
        ok, why = meets(entry, pol['thresholds'])
        if ok:
            return key, f'{key} meets the thresholds for {family}'
        notes.append(f'{key}: ' + ', '.join(why))
    return pol['fallback'], '; '.join(notes) or 'no list for this family'


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('bank', help='a bank key of assets/soundfonts/MANIFEST.json or a .sf2 path')
    ap.add_argument('--families', default=None)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    import soundbank as sb
    path = a.bank if a.bank.lower().endswith(('.sf2',)) else sb.bank_path(a.bank)
    key = os.path.splitext(os.path.basename(path))[0] if a.bank.endswith('.sf2') else a.bank
    doc = audit(path, only=a.families.split(',') if a.families else None)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(os.path.join(AUDIT_DIR, f'{key}.json'), 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, indent=2)
        fh.write('\n')
    if a.json:
        print(json.dumps(doc, indent=2))
        return 0
    th = policy()['thresholds']
    print(f'{key}: {path}')
    for fam, e in doc['families'].items():
        ok, why = meets(e, th)
        print(f"  {fam:16s} layers {e['layers']:4.1f}  centroid x{e['centroid_ratio']:.2f}  8-16k {e['air_db']:6.1f} dB  "
              f"sustain {e['sustained']:.0%}  -> {'OK' if ok else 'below: ' + '; '.join(why)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
