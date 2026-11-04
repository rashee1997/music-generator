"""Synthetic measurement fixture for the gate tests.

This is test material, not a preset: short tones and envelopes used to prove that a detector fires on a known defect and
stays quiet on clean material. It is deliberately simple so the expected row is unambiguous.
"""
import numpy as np

SR = 44100
BPM = 120.0
DUR = 8.0

SECTIONS = [(0.0, 2.0, 0.30), (2.0, 4.0, 0.50), (4.0, 6.0, 0.90), (6.0, 8.0, 0.35)]


def _section_gain(n):
    g = np.ones(n, dtype=np.float64)
    for a, b, v in SECTIONS:
        g[int(a * SR):int(b * SR)] = v
    # a 30 ms ramp, not a step: an instantaneous gain jump is itself a click and a cut-like discontinuity
    k = max(1, int(0.03 * SR))
    g = np.convolve(g, np.ones(k) / k, mode='same')
    return g / max(1e-9, float(np.max(g)))


def _norm(x, peak=0.25):
    m = float(np.max(np.abs(x))) if np.size(x) else 0.0
    return x * (peak / m) if m > 1e-9 else x


def _note(freq, dur, amp=0.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = np.minimum(1.0, t / 0.01) * np.exp(-t * 3.0)
    env *= np.minimum(1.0, (dur - t) / 0.05)
    return amp * np.sin(2 * np.pi * freq * t) * np.clip(env, 0.0, 1.0)


def build_stems(dur=DUR):
    n = int(dur * SR)
    t = np.arange(n) / SR
    gain = _section_gain(n)
    # root, fifth, octave: the second is a fifth, not a third, so the stacked sines do not beat against each other and
    # the roughness row judges the fixture's own defects instead of the test chord
    pad = 0.05 * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 330 * t)
                  + np.sin(2 * np.pi * 440 * t))
    pad *= 0.9 + 0.1 * np.sin(2 * np.pi * 0.2 * t)
    bass = 0.12 * np.sin(2 * np.pi * 110 * t)
    lead = np.zeros(n)
    for k, f in enumerate([440.0, 493.88, 523.25, 587.33, 523.25, 493.88, 440.0]):
        start = int((0.5 + k) * SR)
        seg = _note(f, 1.0)
        lead[start:start + len(seg)] += seg[:max(0, min(len(seg), n - start))]
    drums = np.zeros(n)
    kick = _note(55.0, 0.18, 0.5)
    for k in range(int(dur / 0.5)):
        start = int(k * 0.5 * SR)
        drums[start:start + len(kick)] += kick[:max(0, min(len(kick), n - start))]
    out = {}
    for name, x in (('lead', lead), ('pad', pad), ('bass', bass), ('drums', drums)):
        out[name] = _norm(x * gain, 0.25 if name != 'drums' else 0.18)
    return out


def score(dur=DUR):
    bars = dur / 2.0
    return dict(
        title='gate fixture', bpm=BPM, ts=[4, 4], key='A', mode='minor',
        master={'lufs': -16.0, 'true_peak': -1.5},
        tracks=[
            dict(name='lead', instrument='flute', role='melody',
                 notes=[dict(t=1 + 2 * k, d=2, p=[69, 71, 72, 74, 72, 71, 69][k], v=0.8)
                        for k in range(7)]),
            dict(name='pad', instrument='slow_strings', role='chord',
                 notes=[dict(t=0, d=16, p=57, v=0.5)]),
            dict(name='bass', instrument='bass', role='bass',
                 notes=[dict(t=0, d=16, p=45, v=0.6)]),
            dict(name='drums', instrument='kit', role='drum',
                 notes=[dict(t=k, d=0.5, p='kick', v=0.7) for k in range(int(dur / 0.5))]),
        ],
        plan=dict(n_bars=int(bars), bb=4, bpm=BPM, sections=[
            dict(name=name, start_bar=i, end_bar=i + 1, dyn=dyn)
            for i, (name, dyn) in enumerate(zip(['open', 'develop', 'climax', 'release'],
                                                [0.30, 0.50, 0.90, 0.35]))
        ]),
    )


def build_mix(stems, dur=DUR):
    n = int(dur * SR)
    mix = sum(stems.values())
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.7
    t = np.arange(n) / SR
    mix *= np.minimum(1.0, t / 0.02)
    mix *= np.minimum(1.0, (dur - t) / 1.0) ** 2
    return np.stack([mix, mix], axis=1)


def add_click(x, at=3.0, amp=0.5):
    y = np.array(x, copy=True)
    i = int(at * SR)
    y[i] += amp
    return y


def add_dropout(x, at=3.0, ms=80.0):
    y = np.array(x, copy=True)
    a = int(at * SR)
    y[a:a + int(ms / 1000.0 * SR)] = 0.0
    return y


def add_cut(x, at=4.0, ms=500.0):
    y = np.array(x, copy=True)
    a = int(at * SR)
    y[a:a + int(ms / 1000.0 * SR)] = 0.0
    return y


def trim_head(x, remove_s=0.3):
    """A stem that starts `remove_s` late: its first note is where it always was, the sound is not."""
    y = np.array(x, copy=True)
    y[:max(1, int(remove_s * SR))] = 0.0
    return y


def truncate_end(x, remove_s=1.0):
    y = np.array(x, copy=True)
    return y[:max(1, len(y) - int(remove_s * SR))]


def add_dc(x, offset=0.02):
    return np.asarray(x) + offset


def clip_hard(x, gain=20.0):
    return np.clip(np.asarray(x) * gain, -1.0, 1.0)


def add_tick(x, at=2.0, period=0.25, amp=0.08, count=12):
    y = np.array(x, copy=True)
    burst = _note(1800.0, 0.005, amp)
    for k in range(count):
        a = int((at + k * period) * SR)
        if a >= len(y):
            break
        y[a:a + len(burst)] += burst[:max(0, min(len(burst), len(y) - a))]
    return y


def add_noise_burst(x, at=5.0, ms=120.0, amp=0.06, seed=7):
    y = np.array(x, copy=True)
    rng = np.random.default_rng(seed)
    a = int(at * SR)
    n = int(ms / 1000.0 * SR)
    y[a:a + n] += amp * rng.standard_normal(min(n, len(y) - a))
    return y
