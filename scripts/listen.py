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

#!/usr/bin/env python3
"""listen.py - hear a rendered piece and judge it against its direction sheet.

    python3 scripts/listen.py song.wav --direction direction.json            # full report (needs earshot)
    python3 scripts/listen.py song.wav --direction direction.json --no-ears  # measurements only
    python3 scripts/listen.py song.wav --direction direction.json --out report.json

Two layers, both reported:
  1. Measurements (always, no models): loudness, true peak, clipping, length, and the checker's
     dynamics / stereo / balance numbers (scripts/naturalness_check.py).
  2. Ears (optional): earshot (https://github.com/Leonxlnx/earshot) listens to the file with an
     audio-text model and an AudioSet tagger. It says what the piece sounds like, how well a feel
     word fits against the opposite words, which instruments it hears, the tempo, pulse clarity,
     and the key. It is a second opinion from a model, not a human ear: its mood labels are wrong
     about one time in five on test material, so treat a single FAIL as a question, not a verdict.

Each target in the direction sheet becomes one PASS / CHECK / FAIL line, with the numbers behind
it and the levers from references/workflow/music-direction.md that usually fix that kind of miss.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
import naturalness_check as nc  # noqa: E402

# What to change when a target misses. Keys match check names below.
LEVERS = {
    'feel': [
        'mode: major for bright/epic/hopeful, minor or dorian for sad/tense (mode is the strongest cue)',
        'tempo: move 10-20 BPM toward the feel (slower reads sad/calm, faster reads energetic)',
        'register: raise the melody 5-12 semitones for hope, drop the bass and melody for dread',
        'dynamics: a bigger arc (quiet start, loud peak) for epic; flatter dynamics for calm',
        'orchestration: add the instruments the feel needs (brass and taiko for epic, cello and piano for sad)',
    ],
    'avoid': [
        'remove the layer or harmony that reads as the unwanted feel (the earshot ranking names it)',
        'switch the mode if the unwanted word is the mode itself (minor reads sad, major reads happy)',
        'slow down or thin the texture if an energetic word leaked in',
    ],
    'instruments': [
        'the instrument is not in the score: add a track for it, or raise its gain by 3-6 dB',
        'the instrument is buried: move it up a register or reduce the layers around it',
    ],
    'pulse:steady': [
        'steady pulse wanted: add a drum or ostinato track with a clear grid (kick on the beat)',
        'a grid that is too loose: use humanize "tight" on the drums and keep the tempo map flat',
    ],
    'pulse:none': [
        'no pulse wanted: remove the drums and any bar-locked ostinato; let the phrases breathe',
    ],
    'tempo': [
        'tempo off: set bpm in compose / the score to the target range; check the score bpm, not the render',
        'tempo may read double or half: if the double or half is inside the range, the check passes',
    ],
    'mode': [
        'mode reads the other way: change the scale or the chord set (the mode is the largest cue)',
        'key estimates are weak on short or busy pieces: confirm by ear before changing a working score',
    ],
    'loudness': [
        'loudness off: change master.lufs in the score or the mix JSON; a very dynamic piece may not reach it',
    ],
    'true_peak': [
        'true peak hot: lower master.true_peak or the loudest stems\' gain_db',
    ],
    'clipping': [
        'clipping: lower the master input (-3 dB) and re-render; never fix clipping with a limiter alone',
    ],
    'length': [
        'length off: change duration_s or the bar count; compose fits bars to the requested duration',
    ],
    'hits': [
        'hit lands late or missing: put the hit on a beat (compose hit_points snap to half-beats), or move the cut',
        'hit too soft: raise the impact stem (+3 dB) and add a sub layer under it',
    ],
}


def ears():
    """Return earshot's api module, or None if it is not installed or its models won't load."""
    os.environ.setdefault('EARSHOT_HOME', os.path.join(os.path.expanduser('~'), '.cache', 'music-generator', 'earshot'))
    try:
        from earshot import api  # noqa: WPS433
        return api
    except Exception:
        return None


def status_rank(s):
    return {'PASS': 0, 'SKIP': 0, 'CHECK': 1, 'FAIL': 2}[s]


def check(name, status, detail, target=None):
    return dict(name=name, status=status, detail=detail, target=target)


def loudness_checks(r, sheet, out):
    lufs = r['lufs']
    target = sheet.get('loudness_lufs')
    if target is None:
        out.append(check('loudness', 'SKIP', f'{lufs:.1f} LUFS (no target in the direction sheet)'))
    else:
        d = abs(lufs - target)
        st = 'PASS' if d <= 1.5 else ('CHECK' if d <= 3 else 'FAIL')
        out.append(check('loudness', st, f'{lufs:.1f} LUFS, target {target:.1f} (within 1.5 dB passes)', target))
    peak_max = sheet.get('true_peak_max', -1.0)
    st = 'PASS' if r['true_peak'] <= peak_max else 'FAIL'
    out.append(check('true_peak', st, f'{r["true_peak"]:.1f} dBTP, ceiling {peak_max:.1f}', peak_max))
    st = 'PASS' if r['clipped'] == 0 else 'FAIL'
    out.append(check('clipping', st, f'{r["clipped"]} samples at full scale'))
    dur = sheet.get('duration_s')
    if dur:
        st = 'PASS' if abs(r['dur'] - dur) <= 1.0 else 'CHECK'
        out.append(check('length', st, f'{r["dur"]:.1f} s, target {dur:.1f} s', dur))


def feel_checks(api, path, sheet, out):
    """Forced choice: does each feel word beat the avoid words for this audio?"""
    feel = sheet.get('feel') or []
    avoid = sheet.get('avoid_feel') or []
    if not feel:
        return
    alts = [f'{a} music' for a in avoid] or ['calm background music', 'a happy upbeat song']
    for w in feel:
        res = api.match(path, f'{w} music', alts=alts)
        p = res.get('p_vs_alts') or 0.0
        z = res.get('z') or 0.0
        if p >= 0.5 and z >= 2.5:
            st = 'PASS'
        elif p >= 0.35:
            st = 'CHECK'
        else:
            st = 'FAIL'  # the opposite word wins the forced choice
        out.append(check(f'feel:{w}', st,
                         f'"{w} music" vs the alternatives: {p * 100:.0f}% of the forced choice, z {z:+.1f} '
                         f'(earshot verdict: {res.get("verdict")})', target=w))


def hint_rank(hints, word):
    """Position (0 = strongest) of the first hint whose text contains the word, or None."""
    word = word.lower()
    for i, h in enumerate(hints):
        if word in str(h.get('term', '')).lower():
            return i
    return None


def ears_checks(api, path, sheet, out, notes):
    desc = api.describe(path)
    hints = desc.get('music_hints') or []
    notes['top_readings'] = [f"{h['term']} (z {h['z']:+.1f})" for h in hints[:6]]
    notes['earshot_summary'] = desc.get('summary', '')

    feel_checks(api, path, sheet, out)

    for w in sheet.get('avoid_feel') or []:
        i = hint_rank(hints, w)
        if i is None or i >= 8:
            st, d = 'PASS', f'"{w}" is not among earshot\'s top readings'
        elif i < 3:
            st, d = 'FAIL', f'"{w}" is one of earshot\'s top three readings (position {i + 1})'
        else:
            st, d = 'CHECK', f'"{w}" appears in the top readings (position {i + 1})'
        out.append(check(f'avoid:{w}', st, d, target=w))

    for w in sheet.get('instruments') or []:
        i = hint_rank(hints, w)
        if i is not None and i < 10:
            out.append(check(f'instrument:{w}', 'PASS', f'earshot hears "{w}" (reading {i + 1})', target=w))
        else:
            out.append(check(f'instrument:{w}', 'CHECK',
                             f'earshot does not name "{w}" among its top readings (it may be buried or missing)',
                             target=w))

    m = api.measure(path, music=True)
    tl = api.timeline(path)
    mu = tl.get('music') or {}
    clarity = mu.get('pulse_clarity')
    tempo = m.get('tempo')
    notes['tempo_estimate'] = tempo
    notes['pulse_clarity'] = clarity

    want_pulse = sheet.get('pulse')
    if want_pulse and clarity is not None:
        if want_pulse == 'steady':
            st = 'PASS' if clarity >= 0.30 else ('CHECK' if clarity >= 0.15 else 'FAIL')
            d = f'pulse clarity {clarity:.2f} (clear from 0.30, weak below 0.15)'
        elif want_pulse == 'none':
            st = 'PASS' if clarity < 0.15 else 'CHECK'
            d = f'pulse clarity {clarity:.2f} (no pulse wanted; passes below 0.15)'
        else:
            st, d = 'SKIP', f'pulse "{want_pulse}" is not checked'
        out.append(check('pulse', st, d, target=want_pulse))

    want_tempo = sheet.get('tempo_bpm') or sheet.get('bpm')     # a range [lo, hi], or one exact tempo (a cue cut to picture)
    if isinstance(want_tempo, (int, float)):
        lo = hi = float(want_tempo)
    elif want_tempo:
        lo, hi = (float(v) for v in want_tempo)
    else:
        lo = hi = None
    if lo and tempo:
        ok = any(lo * f <= tempo <= hi * f for f in (1.0, 2.0, 0.5))
        st = 'PASS' if ok else 'FAIL'
        out.append(check('tempo', st, f'estimated {tempo:.0f} BPM, target {lo:.0f}-{hi:.0f} '
                                      f'(double or half counts)', target=f'{lo}-{hi}'))

    want_mode = sheet.get('mode')
    keys = m.get('key') or []
    if want_mode and keys:
        top = keys[0]['key']
        got = 'minor' if 'minor' in top else 'major'
        st = 'PASS' if got == want_mode else 'CHECK'
        out.append(check('mode', st, f'key estimate {top} (r {keys[0]["r"]:.2f}); mode wanted {want_mode}',
                         target=want_mode))

    hits = sheet.get('hits_at') or []
    if hits:
        onsets = np.asarray(m.get('onsets') or [])
        missed = []
        for t in hits:
            near = onsets[np.abs(onsets - t) <= 0.3] if len(onsets) else []
            if len(near) == 0:
                missed.append(t)
        st = 'PASS' if not missed else 'CHECK'
        d = 'every hit has an onset within 0.3 s' if not missed else \
            f'no onset within 0.3 s of {", ".join(f"{t:.1f}s" for t in missed)}'
        out.append(check('hits', st, d))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('wav')
    ap.add_argument('--direction', help='direction sheet JSON (templates/direction_sheet.json)')
    ap.add_argument('--no-ears', action='store_true', help='measurements only; skip earshot')
    ap.add_argument('--out', help='also write the full report as JSON')
    a = ap.parse_args()
    import cli_util
    cli_util.require_file(a.wav, 'audio file')
    cli_util.require_file(a.direction, 'direction sheet')

    sheet = {}
    if a.direction:
        with open(a.direction, encoding='utf-8') as f:
            sheet = json.load(f)

    r = nc.analyse(a.wav, bpm=None, target_lufs=sheet.get('loudness_lufs'))
    checks, notes = [], {}
    loudness_checks(r, sheet, checks)

    api = None if a.no_ears else ears()
    if a.no_ears:
        notes['ears'] = 'Ears off (--no-ears): measurements only; the feel, instrument, pulse, tempo and key checks were not run.'
    if api is None and not a.no_ears:
        notes['ears'] = ('earshot is not installed or its models did not load, so the feel, instrument, '
                         'pulse, tempo and key checks were skipped. Run scripts/setup_project.py --ears to install it.')
    elif api is not None:
        try:
            ears_checks(api, a.wav, sheet, checks, notes)
        except Exception as e:  # noqa: BLE001 - report, don't crash the loop
            notes['ears'] = f'earshot failed on this file: {e}'

    worst = max((c['status'] for c in checks), key=status_rank, default='PASS')
    print(f'listen: {os.path.basename(a.wav)} ({r["dur"]:.1f} s)'
          + (f' - purpose: {sheet["purpose"]}' if sheet.get('purpose') else ''))
    if notes.get('top_readings'):
        print('Earshot hears: ' + '; '.join(notes['top_readings']))
        print('(Readings are not exclusive; the forced choice against the opposite words is the sharper test.)')
    if notes.get('tempo_estimate') is not None:
        print(f'Tempo ~{notes["tempo_estimate"]:.0f} BPM, pulse clarity {notes.get("pulse_clarity") or 0:.2f}')
    print()
    for c in checks:
        print(f'  {c["status"]:<5} {c["name"]:<22} {c["detail"]}')
    print()
    if notes.get('ears'):
        print('Note: ' + notes['ears'])

    priority = ['feel', 'avoid', 'pulse', 'instruments', 'tempo', 'mode', 'hits', 'loudness', 'true_peak',
                'clipping', 'length']
    misses = [c for c in checks if c['status'] in ('CHECK', 'FAIL')]
    misses.sort(key=lambda c: (c['status'] != 'FAIL', priority.index(c['name'].split(':')[0])
                               if c['name'].split(':')[0] in priority else 99))
    shown = []
    for c in misses:
        base = c['name'].split(':')[0]
        keyed = LEVERS.get(f"{base}:{c.get('target')}", LEVERS.get(base, []))
        for lever in keyed[:2]:
            if lever not in shown:
                shown.append(lever)
    if shown:
        print('Levers to try, most important first (change one at a time, then listen again):')
        for lv in shown[:8]:
            print(f'  - {lv}')
    print()
    print(f'Overall: {worst}' + ('  (a FAIL is a question for you, not a verdict: listen before changing)'
                                 if worst == 'FAIL' else ''))

    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(dict(file=a.wav, sheet=sheet, checks=checks, notes=notes, overall=worst,
                           lufs=r['lufs'], true_peak=r['true_peak'], dur=r['dur']), f, indent=2, default=float)


if __name__ == '__main__':
    main()
