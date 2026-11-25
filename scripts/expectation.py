# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""expectation.py - melodic expectation as information content and entropy (IDyOM-style, numpy only).

For each note of a line the model predicts the next event from the notes before it and reports

    IC  = -log2 P(e | context)                  how surprising the note was
    H   = -sum_e P(e | context) log2 P(e | context)   how uncertain the listener was before it

Prediction is by partial matching, escape method C, with exclusion, over contexts of up to `order` previous symbols
(Cleary & Witten 1984; Pearce & Wiggins 2004). Three viewpoints are modelled apart:

    cpint   the pitch interval from the previous note, -12..+12 semitones
    degree  the pitch class relative to the tonic, 0..11
    ioi     the inter-onset ratio to the previous interval, round(2 log2 r), -4..+4

A viewpoint has a short-term model (learned online from the piece itself: every note is predicted BEFORE it is learned)
and, if the caller trains one, a long-term model from a corpus. The two distributions of a viewpoint, and then the
information contents of the two pitch viewpoints (cpint, degree), are mixed with weights 1 / H^b (IDyOM's entropy
weighting; b = 1 here). The rhythm viewpoint is reported apart (`ic_rhythm`): mixed in, a constant rhythm has
entropy near zero, takes nearly all the weight and hides the pitch surprise. IDyOM mixes the
viewpoints' distributions over one basic attribute; mixing their information contents instead is cheaper and does not
need a common alphabet, at the cost of not being IDyOM's number. No corpus ships with this module: the long-term model
is empty unless the caller trains it, and a corpus has its own licence to check first.

Everything is deterministic and works on the score's note list: no audio, no randomness.
"""
from collections import Counter

import numpy as np

ORDER = 3                  # the longest context, in symbols (starting value)
BIAS = 1.0                 # the exponent b of the 1 / H^b weights (IDyOM's default)
ALPHABETS = {'cpint': tuple(range(-12, 13)), 'degree': tuple(range(12)), 'ioi': tuple(range(-4, 5))}
PITCH = ('cpint', 'degree')        # the viewpoints whose information contents make up a note's pitch surprise
SIMULTANEOUS_BEATS = 1.0 / 64.0     # notes closer than this are one event; the highest is the line


class PPM:
    """One viewpoint's predictor: counts of every context up to `order` symbols long."""

    def __init__(self, alphabet, order=ORDER):
        self.alphabet = tuple(alphabet)
        self.index = {s: i for i, s in enumerate(self.alphabet)}
        self.order = int(order)
        self.counts = {}

    def learn(self, history, symbol):
        for k in range(min(self.order, len(history)) + 1):
            ctx = tuple(history[len(history) - k:]) if k else ()
            self.counts.setdefault(ctx, Counter())[symbol] += 1

    def train(self, sequence):
        seq = list(sequence)
        for i, s in enumerate(seq):
            self.learn(seq[:i], s)

    def distribution(self, history):
        """P(symbol | history) over the alphabet: PPM-C blending with exclusion, uniform over the unseen at the end."""
        a = len(self.alphabet)
        p = np.zeros(a)
        seen = np.zeros(a, dtype=bool)
        left = 1.0
        for k in range(min(self.order, len(history)), -1, -1):
            c = self.counts.get(tuple(history[len(history) - k:]) if k else ())
            if not c:
                continue
            items = [(self.index[s], n) for s, n in c.items() if not seen[self.index[s]]]
            if not items:
                continue
            total = float(sum(n for _, n in items))
            types = float(len(items))
            denom = total + types                 # method C: the escape count is the number of distinct symbols
            for i, n in items:
                p[i] += left * n / denom
                seen[i] = True
            left *= types / denom
        rest = ~seen
        if rest.any():
            p[rest] += left / rest.sum()
        else:
            p += left / a
        return p


def entropy(p):
    q = p[p > 0]
    return float(-(q * np.log2(q)).sum())


def _mix(dists, b=BIAS):
    """Entropy-weighted mixture of distributions over one alphabet: weights 1 / H^b (a point mass gets the most)."""
    w = np.array([1.0 / max(entropy(d), 1e-3) ** b for d in dists])
    return sum(wi * d for wi, d in zip(w / w.sum(), dists))


def line_of(notes):
    """(onsets in beats, pitches) of the melodic line: one event per onset (the highest simultaneous note), in time order."""
    ns = sorted((n for n in notes if isinstance(n.get('p'), (int, float))), key=lambda n: (n['t'], -n['p']))
    t, p = [], []
    for n in ns:
        if t and n['t'] - t[-1] < SIMULTANEOUS_BEATS:
            continue
        t.append(float(n['t']))
        p.append(float(n['p']) + float(n.get('c', 0.0) or 0.0) / 100.0)
    return np.asarray(t), np.asarray(p)


def viewpoints(onsets, pitches, tonic_pc):
    """{name: [symbol or None per note]}: None where the viewpoint needs notes that do not exist yet."""
    n = len(pitches)
    iv = [None] + [int(np.clip(round(pitches[i] - pitches[i - 1]), -12, 12)) for i in range(1, n)]
    deg = [int(round(p - tonic_pc)) % 12 for p in pitches]
    ioi = [None, None]
    for i in range(2, n):
        a, b = onsets[i] - onsets[i - 1], onsets[i - 1] - onsets[i - 2]
        ioi.append(int(np.clip(round(2.0 * np.log2(max(a, 1e-6) / max(b, 1e-6))), -4, 4)))
    return {'cpint': iv, 'degree': deg, 'ioi': ioi[:n]}


class Expectation:
    """The model: a short-term PPM per viewpoint (new for every line) and optional long-term ones."""

    def __init__(self, order=ORDER, bias=BIAS, long_term=None):
        self.order, self.bias = int(order), float(bias)
        self.ltm = long_term or {}                 # {viewpoint: PPM}, trained by the caller; empty by default

    def train(self, notes, tonic_pc):
        """Teach the long-term model one line (call it for each line of a corpus)."""
        t, p = line_of(notes)
        for name, seq in viewpoints(t, p, tonic_pc).items():
            ppm = self.ltm.setdefault(name, PPM(ALPHABETS[name], self.order))
            hist = []
            for s in seq:
                if s is not None:
                    ppm.learn(hist, s)
                    hist.append(s)

    def analyse(self, notes, tonic_pc):
        """IC and H per note of the line: dict(onsets, ic, h, viewpoints={name: dict(ic, h)}); arrays of length n."""
        t, p = line_of(notes)
        n = len(p)
        seqs = viewpoints(t, p, tonic_pc)
        ic = {k: np.full(n, np.nan) for k in seqs}
        hh = {k: np.full(n, np.nan) for k in seqs}
        for name, seq in seqs.items():
            stm = PPM(ALPHABETS[name], self.order)
            hist = []
            for i, s in enumerate(seq):
                if s is None:
                    continue
                dists = [stm.distribution(hist)]
                if name in self.ltm:
                    dists.append(self.ltm[name].distribution(hist))
                d = dists[0] if len(dists) == 1 else _mix(dists, self.bias)
                ic[name][i] = -np.log2(max(d[stm.index[s]], 1e-12))
                hh[name][i] = entropy(d)
                stm.learn(hist, s)               # the note is learned only after it was predicted
                hist.append(s)
        out = {}
        for label, names in (('', PITCH), ('_rhythm', ('ioi',))):
            oi, oh = np.full(n, np.nan), np.full(n, np.nan)
            for i in range(n):
                have = [k for k in names if not np.isnan(ic[k][i])]
                if not have:
                    continue
                w = np.array([1.0 / max(hh[k][i], 1e-3) ** self.bias for k in have])
                w = w / w.sum()
                oi[i] = float(sum(wi * ic[k][i] for wi, k in zip(w, have)))
                oh[i] = float(sum(wi * hh[k][i] for wi, k in zip(w, have)))
            out['ic' + label], out['h' + label] = oi, oh
        return dict(onsets=t, pitches=p, viewpoints={k: dict(ic=ic[k], h=hh[k]) for k in seqs}, **out)


def note_z(notes, tonic_pc, clip=2.0):
    """(z of IC, z of H) per note of `notes`, each over the line: zero mean, unit spread, clipped to +-`clip`; 0 for a note
    the model has no value for (the first, or a chord tone under the line's top note) and for a line with no spread.
    This is what the humanizer scales: a note's place in the line's surprise, not an absolute number of bits."""
    a = Expectation().analyse(notes, tonic_pc)
    out = []
    for key in ('ic', 'h'):
        v = a[key]
        ok = ~np.isnan(v)
        z = np.zeros(len(v))
        if ok.sum() > 2 and float(np.std(v[ok])) > 1e-6:
            z[ok] = np.clip((v[ok] - np.mean(v[ok])) / np.std(v[ok]), -clip, clip)
        out.append(z)
    onsets = a['onsets']
    res = []
    for z in out:
        per = np.zeros(len(notes))
        if len(onsets):
            for j, nt in enumerate(notes):
                k = int(np.clip(np.searchsorted(onsets, float(nt['t']) - SIMULTANEOUS_BEATS), 0, len(onsets) - 1))
                if abs(onsets[k] - float(nt['t'])) < SIMULTANEOUS_BEATS:
                    per[j] = z[k]
        res.append(per)
    return res[0], res[1]


def by_bar(onsets, values, beats_per_bar):
    """Mean of `values` (NaN ignored) per bar: array of length ceil(last onset / bar), NaN for a bar with no note."""
    if not len(onsets):
        return np.zeros(0)
    bars = (np.asarray(onsets) // float(beats_per_bar)).astype(int)
    out = np.full(bars.max() + 1, np.nan)
    for b in range(len(out)):
        v = np.asarray(values)[bars == b]
        v = v[~np.isnan(v)]
        if len(v):
            out[b] = float(v.mean())
    return out


def ungrounded_share(ic, high_bits=4.2, settle_bits=2.2):
    """Share of events whose surprise is above `high_bits` and not followed by one at or under `settle_bits`
    (the repo's rule: a high-surprise note must be followed by a predictable one). NaN events are skipped."""
    v = np.asarray(ic, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return 0.0
    bad = sum(1 for i in range(len(v)) if v[i] > high_bits and not (i + 1 < len(v) and v[i + 1] <= settle_bits))
    return bad / float(len(v))
