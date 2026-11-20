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

"""Measure what a short functional piece (a ringtone, an alert, a jingle) needs and a green gate does not say.

    python scripts/helpers/short_form_report.py out/master.wav --score scores/<title>_score.json [--loop]

What it prints
    - loop seam: the sample step where the end meets the start, against the 99.9th percentile of the steps inside the
      piece (so the limit comes from the piece itself), and the level step across the seam
    - phone band: the share of the energy between `--band-lo` and `--band-hi` Hz, and the share below `--low-hz`
      (the part a phone speaker does not reproduce)
    - hook: the onsets in the first `--hook-s` seconds, and how loud those seconds are against the whole piece
    - motif: how often the opening motif's shape returns in the figure-family tracks (from the score)
    - density: notes per bar in windows of `--window-bars` bars, so a flat arrangement shows as a flat line

It measures and flags. It does not hear: it says nothing about taste, whether the tune is catchy, or whether the
blend of instruments is pleasant. The defaults are starting values from knowledgebase/genre-and-feel/short-form-functional-music.md,
not calibrated limits: change them to the brief.
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import roles  # noqa: E402


def loop_seam(x, sr, level_ms=100.0):
    """The step where the last sample meets the first, and the level step across the seam.

    `step_ratio` is the larger channel's |x[0] - x[-1]| over the 99.9th percentile of the sample steps inside the piece:
    near or below 1 the seam is no louder a jump than the music makes by itself. `level_step_db` is the RMS of the last
    `level_ms` against the first `level_ms`."""
    x = np.asarray(x, dtype=np.float64)
    x = x if x.ndim > 1 else x[:, None]
    n = max(1, int(level_ms * 1e-3 * sr))
    worst = 0.0
    for c in range(x.shape[1]):
        steps = np.abs(np.diff(x[:, c]))
        ref = float(np.percentile(steps, 99.9)) if len(steps) else 0.0
        worst = max(worst, abs(float(x[0, c] - x[-1, c])) / max(ref, 1e-9))
    head = float(np.sqrt(np.mean(x[:n] ** 2)))
    tail = float(np.sqrt(np.mean(x[-n:] ** 2)))
    return dict(step_ratio=worst, level_step_db=20.0 * np.log10(max(tail, 1e-9) / max(head, 1e-9)))


def phone_band(x, sr, band=(300.0, 5000.0), low_hz=200.0):
    """Share of the energy inside `band` and below `low_hz` (Welch power spectrum of the mono sum)."""
    from scipy.signal import welch
    m = np.asarray(x, dtype=np.float64)
    m = m.mean(axis=1) if m.ndim > 1 else m
    f, p = welch(m, fs=sr, nperseg=min(len(m), 8192))
    total = float(np.sum(p)) + 1e-30
    return dict(in_band=float(np.sum(p[(f >= band[0]) & (f <= band[1])]) / total),
                below_low=float(np.sum(p[f < low_hz]) / total))


def hook(x, sr, first_s=3.0, hop_ms=10.0):
    """Onsets in the first `first_s` seconds and their loudness against the whole piece.

    An onset is a local peak of the positive energy flux (frame energy in dB, hop `hop_ms`) that rises more than 6 dB
    above the frame before it: a note attack, not a swell."""
    m = np.asarray(x, dtype=np.float64)
    m = m.mean(axis=1) if m.ndim > 1 else m
    hop = max(1, int(hop_ms * 1e-3 * sr))
    k = len(m) // hop
    e = 10.0 * np.log10(np.mean(m[:k * hop].reshape(k, hop) ** 2, axis=1) + 1e-12)
    flux = np.diff(e, prepend=e[0])
    cut = int(first_s * 1000.0 / hop_ms)
    onsets = [i for i in range(1, min(cut, k - 1)) if flux[i] > 6.0 and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]]
    first = float(np.sqrt(np.mean(m[:int(first_s * sr)] ** 2)))
    whole = float(np.sqrt(np.mean(m ** 2)))
    return dict(onsets=len(onsets), first_vs_whole_db=20.0 * np.log10(max(first, 1e-9) / max(whole, 1e-9)))


def _figure_tracks(score):
    out = []
    for t in score.get('tracks', []):
        try:
            fam = roles.family(roles.canonical(t.get('role') or ''))
        except Exception:
            continue
        if fam in ('figure', 'melody', 'lead', 'vocal'):
            out.append(t)
    return out


def _shape(notes):
    """Direction and size class of each step: ('u'|'d'|'r', 's' for 0-2 semitones or 'l' for a leap). A repeated
    note is 'r'. The shape survives transposition by a scale step, which an exact interval list does not."""
    out = []
    for a, b in zip(notes[:-1], notes[1:]):
        d = int(b['p']) - int(a['p'])
        out.append('r' if d == 0 else ('u' if d > 0 else 'd') + ('s' if abs(d) <= 2 else 'l'))
    return tuple(out)


def motif_returns(score, n_notes=5):
    """How many times the shape of the opening `n_notes` notes of the lead line occurs in the figure tracks.

    Returns dict(motif_notes, occurrences, exact, tracks): `occurrences` counts every window with the same shape
    (the first one included); `exact` those with the same intervals as well."""
    figs = _figure_tracks(score)
    if not figs:
        return dict(motif_notes=0, occurrences=0, exact=0, tracks=[])
    lead = sorted(figs[0]['notes'], key=lambda e: e['t'])
    if len(lead) < n_notes:
        return dict(motif_notes=len(lead), occurrences=0, exact=0, tracks=[figs[0].get('name')])
    want = _shape(lead[:n_notes])
    want_iv = tuple(int(b['p']) - int(a['p']) for a, b in zip(lead[:n_notes - 1], lead[1:n_notes]))
    occ = exact = 0
    for t in figs:
        ns = sorted(t['notes'], key=lambda e: e['t'])
        for i in range(len(ns) - n_notes + 1):
            w = ns[i:i + n_notes]
            if _shape(w) == want:
                occ += 1
                exact += int(tuple(int(b['p']) - int(a['p']) for a, b in zip(w[:-1], w[1:])) == want_iv)
    return dict(motif_notes=n_notes, occurrences=occ, exact=exact, tracks=[t.get('name') for t in figs])


def density(score, window_bars=4):
    """Note onsets per bar, in windows of `window_bars` bars, over every track. A flat list is a flat arrangement."""
    ts = score.get('ts') or [4, 4]
    bar_beats = float(ts[0]) * 4.0 / float(ts[1])
    last = max((e['t'] + e.get('d', 0) for t in score.get('tracks', []) for e in t.get('notes', [])), default=0.0)
    n_bars = max(1, int(np.ceil(last / bar_beats)))
    per_bar = np.zeros(n_bars)
    for t in score.get('tracks', []):
        for e in t.get('notes', []):
            per_bar[min(n_bars - 1, int(e['t'] // bar_beats))] += 1
    wins = [float(per_bar[i:i + window_bars].mean()) for i in range(0, n_bars, window_bars)]
    mean = float(np.mean(wins)) if wins else 0.0
    return dict(per_window=wins, cv=float(np.std(wins) / mean) if mean > 0 else 0.0)


def report(wav, score_path=None, loop=False, band=(300.0, 5000.0), low_hz=200.0, hook_s=3.0, window_bars=4,
           seam_max=1.0, seam_level_db=3.0, band_min=0.85, low_max=0.05, hook_onsets_min=2, motif_min=3, density_cv_min=0.15):
    import soundfile as sf
    x, sr = sf.read(wav)
    flags = []
    print(f'{os.path.basename(wav)}: {len(x) / float(sr):.2f} s, {sr} Hz, {x.shape[1] if x.ndim > 1 else 1} ch')
    if loop:
        s = loop_seam(x, sr)
        print(f'loop seam      step {s["step_ratio"]:.2f} x the 99.9th-percentile step; level across the seam {s["level_step_db"]:+.1f} dB')
        if s['step_ratio'] > seam_max:
            flags.append(f'loop seam steps {s["step_ratio"]:.1f}x the largest step the music makes: a click on every repeat')
        if abs(s['level_step_db']) > seam_level_db:
            flags.append(f'the end is {s["level_step_db"]:+.1f} dB from the start: the repeat jumps in level')
    b = phone_band(x, sr, band, low_hz)
    print(f'phone band     {100 * b["in_band"]:.0f}% of the energy in {band[0]:.0f}-{band[1]:.0f} Hz, {100 * b["below_low"]:.1f}% below {low_hz:.0f} Hz')
    if b['in_band'] < band_min:
        flags.append(f'only {100 * b["in_band"]:.0f}% of the energy is in {band[0]:.0f}-{band[1]:.0f} Hz: a phone speaker will thin it')
    if b['below_low'] > low_max:
        flags.append(f'{100 * b["below_low"]:.1f}% of the energy is below {low_hz:.0f} Hz, where a phone speaker gives nothing back')
    h = hook(x, sr, hook_s)
    print(f'hook           {h["onsets"]} onset(s) in the first {hook_s:g} s, those seconds {h["first_vs_whole_db"]:+.1f} dB against the whole')
    if h['onsets'] < hook_onsets_min:
        flags.append(f'{h["onsets"]} onset(s) in the first {hook_s:g} s: the hook has not started')
    if score_path:
        score = json.load(open(score_path, encoding='utf-8'))
        m = motif_returns(score)
        print(f'motif          the opening {m["motif_notes"]}-note shape occurs {m["occurrences"]} time(s) ({m["exact"]} with the same intervals)')
        if m['occurrences'] < motif_min:
            flags.append(f'the opening motif returns {m["occurrences"]} time(s): a tune a listener can learn needs to come back at least {motif_min}')
        d = density(score, window_bars)
        print('density        notes per bar by ' + f'{window_bars}-bar window: ' + ' '.join(f'{v:.1f}' for v in d['per_window']) + f'  (spread {d["cv"]:.2f})')
        if d['cv'] < density_cv_min:
            flags.append(f'note density barely moves (spread {d["cv"]:.2f}): the arrangement is one texture from start to end')
    for f in flags:
        print('FLAG', f)
    if not flags:
        print('no flags. This measures the notes and the file; it does not say the tune is catchy or the blend pleasant.')
    return flags


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('wav')
    ap.add_argument('--score')
    ap.add_argument('--loop', action='store_true', help='judge the end meeting the start')
    ap.add_argument('--band-lo', type=float, default=300.0)
    ap.add_argument('--band-hi', type=float, default=5000.0)
    ap.add_argument('--low-hz', type=float, default=200.0)
    ap.add_argument('--hook-s', type=float, default=3.0)
    ap.add_argument('--window-bars', type=int, default=4)
    a = ap.parse_args()
    report(a.wav, a.score, a.loop, (a.band_lo, a.band_hi), a.low_hz, a.hook_s, a.window_bars)


if __name__ == '__main__':
    main()
