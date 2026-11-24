# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. See <https://www.gnu.org/licenses/>.

"""Beats to seconds: the one tempo map of a score, with its phrase arch, wander, elasticity and close."""
import numpy as np

from .config import ELASTIC_KEYS, MOODS, PRESETS, TIMING
from .ensemble import asynchrony_field
from .form import key_tonic, score_chord_roots, score_phrase_spans
from .noise import _fractal_noise, shared_drift


class TempoMap:
    """beats -> seconds, with tempo points, phrase-arch rubato, slow wander and a final ritardando.

    TempoMap(100) is a plain constant tempo. TempoMap(100, points=[[0,100],[32,84]]) ramps linearly.
    rubato: amplitude of the phrase arch (0.03 = +-3 % tempo). ritard: fraction slowed at the very end.
    ritard_q: the deceleration law of the close. q=3 (constant braking power) is the curve that fits measured final
    ritardandi and the highest-rated decelerations in listening tests (Friberg & Sundberg 1999); q=2 is the constant
    braking force. The old 1-ritard*x**2 was a parabola with no measurable support.
    phrase_spans: [(start_beat, end_beat)] - the figure's real phrases. When given, the rubato arch is placed on those
    and a rest carries no swell, instead of assuming a 16-beat period.
    elastic: long-range tempo deviation (0.04 = +-4 % over `elastic_corr_beats`), zero-mean so the average tempo
    is unchanged. breaths: beats where the whole ensemble takes a short collective breath (`breath_s` seconds).
    """

    def __init__(self, bpm, total_beats=64, points=None, rubato=0.0, phrase_beats=16, wander=0.0,
                 ritard=0.0, ritard_beats=6, fermata=None, seed=1, elastic=0.0,
                 elastic_corr_beats=12.0, breaths=None, breath_s=0.06, ritard_q=3.0, phrase_spans=None,
                 fractal_beta=None):
        rng = np.random.default_rng(seed)
        step = 1.0 / 48.0
        T = total_beats + 16
        g = np.arange(0, T, step)
        beta = float(TIMING['fractal_beta'] if fractal_beta is None else fractal_beta)
        if points:
            pts = sorted(points)
            base = np.interp(g, [p[0] for p in pts], [p[1] for p in pts])
        else:
            base = np.full_like(g, float(bpm))
        f = np.ones_like(g)
        if rubato:
            if phrase_spans:
                arch = np.ones_like(g)
                for s0, s1 in phrase_spans:
                    m = (g >= s0) & (g < s1)
                    if not m.any() or s1 <= s0:
                        continue
                    x = (g[m] - s0) / (s1 - s0)
                    arch[m] = 1 + rubato * (np.sin(np.pi * x) - 2 / np.pi)
                f *= arch
            else:
                x = (g % phrase_beats) / phrase_beats
                f *= 1 + rubato * (np.sin(np.pi * x) - 2 / np.pi)
        if wander:
            f *= 1 + wander * _fractal_noise(rng, len(g), beta=beta, fc=step / 8.0)
        if elastic:
            # phrase-scale elasticity, not a per-note wobble: a correlation length of several bars, and an
            # exactly zero-mean curve so the piece does not get slower or faster on average, only more or less urgent
            e = _fractal_noise(rng, len(g), beta=beta, fc=step / max(2.0, float(elastic_corr_beats)))
            body = g <= float(total_beats)             # centre on the piece, not on the padded map
            f *= 1 + float(elastic) * (e - float(e[body].mean() if body.any() else e.mean()))
        if ritard:
            a = total_beats - ritard_beats
            x = np.clip((g - a) / ritard_beats, 0, 1)
            q = float(ritard_q) if ritard_q and float(ritard_q) > 0.0 else 3.0
            w = max(0.05, 1.0 - float(ritard))
            f *= (1.0 + (w ** q - 1.0) * x) ** (1.0 / q)
        self.factor = f.copy()                    # the tempo multiplier alone, for local_tempo()/phrase coupling
        spb = 60.0 / (base * f)
        secs = np.concatenate([[0], np.cumsum(spb[:-1] * step)])
        if fermata:                               # [(beat, extra_seconds), ...] - hold a note/chord longer
            for b, extra in fermata:
                secs += np.where(g > b, extra, 0.0)
        if breaths:                               # a held breath before a harmonic turn, shared by every player
            for b in breaths:
                secs += np.where(g > float(b), float(breath_s), 0.0)
        self.g, self.secs, self.base_bpm, self.total_beats = g, secs, base, total_beats

    def sec(self, beats):
        b = np.asarray(beats, dtype=float)
        out = np.interp(b, self.g, self.secs)
        # np.interp clamps past the end of the map. A note beyond it then landed on the same second as every other
        # note out there, collapsing the end of a piece onto one instant (measured: 49 events at 20.60 s). Continue
        # at the last mapped tempo instead.
        if np.any(b > self.g[-1]) and len(self.g) > 2:
            slope = (self.secs[-1] - self.secs[-2]) / (self.g[-1] - self.g[-2])
            out = np.where(b > self.g[-1], self.secs[-1] + (b - self.g[-1]) * slope, out)
        return out

    def beat(self, seconds):
        return np.interp(np.asarray(seconds, dtype=float), self.secs, self.g)

    def local_tempo(self, beats):
        """The tempo multiplier at a beat (1.0 = the written tempo): rubato, wander, elasticity and the final ritard."""
        return np.interp(np.asarray(beats, dtype=float), self.g, self.factor, left=1.0, right=1.0)

    @property
    def length(self):
        return float(self.sec(self.total_beats))


def tempo_map_for(score, seed=None, pad_beats=1):
    """The one TempoMap of a score. The renderer and the pipeline both call this, so the reported duration,
    the ritardando position and the rendered audio cannot disagree (they were built independently with
    different rubato, ritard and total length).

    It also carries the piece's phrase spans, tonic and sounding chord roots, so a track's humanization can place its
    arches on the real phrases and hear the harmony under its own line.
    """
    tracks = score.get('tracks', []) or []
    total = max([float(n['t']) + float(n.get('d', 0.0)) for t in tracks for n in t.get('notes', [])] or [16.0])
    cfg = score.get('humanize', 'natural')
    preset = PRESETS.get(cfg if isinstance(cfg, str) else 'natural', PRESETS['natural'])
    rub = score.get('rubato', preset.get('rubato', 0.02))
    wander = score.get('wander', 0.0 if cfg == 'tight' else 0.004)
    elastic = score.get('elastic') or {}
    if not isinstance(elastic, dict):
        raise ValueError(f"score.elastic must be an object {{{', '.join(ELASTIC_KEYS)}}}, got {type(elastic).__name__}")
    unknown = sorted(set(elastic) - set(ELASTIC_KEYS))
    if unknown:
        raise ValueError(f"score.elastic: unknown key(s) {', '.join(unknown)}; known: {', '.join(ELASTIC_KEYS)}")
    el_amount = float(elastic.get('amount', 0.0))
    el_corr = float(elastic.get('corr_beats', 12.0))
    el_breaths = [float(b) for b in (elastic.get('breaths') or [])]
    el_breath_s = float(elastic.get('breath_s', 0.06))
    if el_amount < 0.0 or el_amount > 0.25:
        raise ValueError('score.elastic.amount: expected 0..0.25 (a quarter of the tempo is not elasticity)')
    if el_breath_s < 0.0 or el_breath_s > 2.0:
        raise ValueError('score.elastic.breath_s: expected 0..2 seconds')
    mood = score.get('mood')
    mood = str(mood).lower() if mood is not None else None
    if mood in MOODS:                       # an expression profile scales the rubato (GERM: urgency is less rubato)
        rub = float(rub) * float(MOODS[mood].get('rubato', 1.0))
    elif mood is not None:
        # an unknown word is an error, never a silent wash: a typo in a four-name vocabulary is a mistake, not a mood
        raise ValueError(f"score.mood: unknown expression {mood!r}; known: {', '.join(sorted(MOODS))}")
    seed = seed if seed is not None else score.get('seed', 1)
    tm = TempoMap(score.get('bpm', 90), total_beats=total + pad_beats, points=score.get('tempo_points'),
                  rubato=rub, wander=wander, ritard=score.get('ritard', 0.3),
                  elastic=el_amount, elastic_corr_beats=el_corr, breaths=el_breaths, breath_s=el_breath_s,
                  ritard_beats=score.get('ritard_beats', 6), phrase_beats=score.get('phrase_beats', 16),
                  ritard_q=score.get('ritard_q', 3.0), phrase_spans=score_phrase_spans(tracks),
                  fermata=score.get('fermata'), seed=seed)
    # one shared wander for the whole piece: every track of a section drifts together instead of apart
    tm.shared_drift = shared_drift(seed if seed is not None else score.get('seed', 1), tm.total_beats, cfg)
    tm.key = key_tonic(score.get('key'))
    tm.chord_roots = score_chord_roots(tracks)
    tm.mood = mood
    # one vertical spread for the whole piece: a named part reads its own stable offset
    tm.asynchrony, tm.asynchrony_sig = asynchrony_field(score, seed if seed is not None else score.get('seed', 1))
    return tm
