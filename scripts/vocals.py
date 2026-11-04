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
"""vocals.py - sung, chanting and humming voices by source-filter synthesis (no samples, no models).

Public facade over scripts/vocal_engine/. The old names still work; the engine behind them is now phrase based:
  render_choir(events, ...)     -> (N,2) float32. Each singer is an independent performer; a phrase is one
                                   continuous pitch curve with portamento, vibrato that never restarts, breath,
                                   expression, true nasal humming for vowel 'm' / hum=True.
  render_choir(..., return_stems=True) -> (mix, info): dry per-singer stems, breath stems, positions, distances, report
  sing(midi, dur, ...)          -> one note through the same engine (legacy, peak-normalised like before)
  add_vocal_harmonies / add_vocal_chorus / apply_vocal_dsp  -> pedalboard polish, numbers from the `dsp` config

Configuration (all optional, all JSON): see references/instruments-and-vocals/vocal-engine.md and references/data/vocal-engine-data/vocal.schema.json.
Legacy flat keys (voices, attack, vib_cents, ...) and the old nested preset keys keep working.

Styles (tuvan_kargyraa, tuvan_sygyt, bulgarian_chant, nordic_kulning, qawwali_devotional, gregorian_monastic,
african_polyphony, classical_choir) are configurable synthesis profiles in references/data/vocal-engine-data/styles.json,
not claims of authentic reproduction.

    python3 scripts/vocals.py selftest | demo [out.wav] | hum [out.wav]
"""
import argparse
import os
import sys
import warnings

import numpy as np
from scipy.signal import lfilter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from vocal_engine import config as _config, data as _data, ensemble as _ensemble, performance as _perf, tract as _tract  # noqa: E402
from vocal_engine.utils import smooth_noise as _smooth_noise_fast  # noqa: E402

INSTRUMENTS = {'choir_formant', 'hum_formant', 'voice_formant', 'throat_formant', 'chant_formant'}
_DEF = _data.defaults()
VOWELS = {k: tuple(v) for k, v in _DEF['tract']['vowels'].items()}
VOCAL_STYLES = _data.styles()
BANDWIDTH = tuple(_DEF['tract']['bandwidths'])
TRACT_GAIN = tuple(_DEF['tract']['gains'])
def _smooth_noise(rng, n, sr, rate_hz=6.0):
    return _smooth_noise_fast(rng, n, sr, rate_hz)


def _resonator(x, f, bw, sr):
    """Two-pole resonator with unity gain at its centre frequency (the old normalisation was evaluated wrongly)."""
    return _tract.resonate(x, f, bw, sr)


def sing(midi, dur, sr, rng, vowel='a', vib_cents=28.0, vib_hz=5.3, vib_delay=0.35, glide_cents=0.0,
         attack=0.18, release=0.22, breath=0.03, formant_scale=1.0, gain=1.0, formants=None,
         style=None, bandwidths=None):
    """One note through the phrase engine, peak-normalised to `gain` (the legacy contract). For performances use
    render_choir: nothing there is normalised per note."""
    cfg, _ = _config.resolve(dict(vib_cents=vib_cents, vib_hz=vib_hz, vib_delay=vib_delay, breath=breath,
                                  attack=attack, release=release, formant_scale=formant_scale, bandwidths=bandwidths))
    cfg['performance'].update(arch_cents=0.0, end_sag_cents=0.0)
    ev = dict(t=0.0, dur=dur, p=midi, v=100, gl=glide_cents, vowel=vowel)
    if formants:
        ev['formants'] = list(formants)
    st = VOCAL_STYLES.get(style, {})
    r = _perf.render_phrase([ev], sr, rng, cfg, hum=(vowel == 'm'), style=st)
    out = r['signal'][:int(round(dur * sr))]
    return gain * out / (np.abs(out).max() + 1e-9)


def render_choir(events, sr=44100, voices=5, spread_cents=9.0, pan_width=0.45, vowel='a', seed=1, formant_scale=1.0,
                 hum=False, config=None, return_stems=False):
    """Multi-singer vocal stem, (N,2) float32 (or (mix, info) with return_stems=True).
    events: dicts t, dur (seconds), p (MIDI), v (1-127) and optional c (cents), gl (glide cents), vowel, style,
    formants, art (legato|non_legato|detached), voices, plus any per-note vib_*/attack/release/breath override.
    config: legacy flat keys and/or the new sections (see module doc)."""
    cfg, warn = _config.resolve(config, voices=voices, spread_cents=spread_cents, pan_width=pan_width,
                                vowel=None if (hum and vowel == 'a') else vowel, formant_scale=formant_scale, hum=hum)
    for w in warn:
        warnings.warn(f'vocals: {w}', stacklevel=2)
    res = _ensemble.render(events, sr, cfg, seed=seed, hum=bool(cfg.get('hum')), stems=True)
    out, info = res
    info['report']['warnings'] = warn
    return (out, info) if return_stems else out


# ---------------------------------------------------------------- DSP polish (pedalboard, imported on use)
def _stereo_in(audio):
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=0).astype(np.float32)
    return np.ascontiguousarray(audio.T.astype(np.float32))


def _stereo_out(y, like, keep_shape):
    y = np.nan_to_num(y.T.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    y = np.stack([_ensemble.dc_block(y[:, 0]), _ensemble.dc_block(y[:, 1])], axis=1)
    y = _ensemble.soft_limit(y).astype(np.float32)
    return y.mean(axis=1) if (keep_shape and like.ndim == 1) else y


def add_vocal_harmonies(audio, semitones=None, mix=None, sr=44100, dsp=None, keep_shape=False):
    """Backing harmonies via pitch shift. audio (samples,2) or (samples,). Returns (samples,2) unless keep_shape."""
    import pedalboard as pb
    d = _data.deep_merge(_DEF['dsp'], dsp or {})
    semitones = d['harmonies']['semitones'] if semitones is None else semitones
    mix = d['harmonies']['mix'] if mix is None else mix
    x = _stereo_in(audio)
    harm = np.zeros_like(x)
    for semi in semitones:
        harm += pb.Pedalboard([pb.PitchShift(semitones=semi)])(x, sr) / max(1, len(semitones))
    return _stereo_out((1.0 - mix) * x + mix * harm, audio, keep_shape)


def add_vocal_chorus(audio, rate_hz=None, depth=None, mix=None, sr=44100, dsp=None, keep_shape=False):
    """Light ensemble widening. Defaults are gentler than before (mix 0.25) so single voices stay recognisable."""
    import pedalboard as pb
    c = _data.deep_merge(_DEF['dsp'], dsp or {})['chorus']
    x = _stereo_in(audio)
    y = pb.Pedalboard([pb.Chorus(rate_hz=c['rate_hz'] if rate_hz is None else rate_hz,
                                 depth=c['depth'] if depth is None else depth, mix=c['mix'] if mix is None else mix)])(x, sr)
    return _stereo_out(y, audio, keep_shape)


def apply_vocal_dsp(audio, sr=44100, style=None, dsp=None, keep_shape=False):
    """Highpass, presence and air EQ, gentle compression, optional style saturation. `dsp` overrides the defaults;
    dsp.intensity (0..1) scales every gain/ratio toward neutral. Saturation: dsp.saturation_db, else the style's
    dsp_saturation_db (qawwali_devotional); the old names qawwali_sufi / arabic_desert_vocal / bulgarian_chant still get 1.5 dB."""
    import pedalboard as pb
    d = _data.deep_merge(_DEF['dsp'], dsp or {})
    k = float(np.clip(d['intensity'], 0.0, 1.0))
    sat = d['saturation_db']
    if not sat:
        sat = VOCAL_STYLES.get(style, {}).get('dsp_saturation_db', 1.5 if style in ('qawwali_sufi', 'arabic_desert_vocal', 'bulgarian_chant') else 0.0)
    c = d['compressor']
    chain = [pb.HighpassFilter(cutoff_frequency_hz=d['highpass_hz']),
             pb.PeakFilter(cutoff_frequency_hz=d['presence']['hz'], gain_db=d['presence']['gain_db'] * k, q=d['presence']['q']),
             pb.HighShelfFilter(cutoff_frequency_hz=d['air']['hz'], gain_db=d['air']['gain_db'] * k, q=d['air']['q']),
             pb.Compressor(threshold_db=c['threshold_db'], ratio=1.0 + (c['ratio'] - 1.0) * k, attack_ms=c['attack_ms'],
                           release_ms=c['release_ms'])]
    if sat:
        chain.append(pb.Distortion(drive_db=float(sat) * k))
    return _stereo_out(pb.Pedalboard(chain)(_stereo_in(audio), sr), audio, keep_shape)


def _envelope_energy_above(x, sr, f):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    fr = np.fft.rfftfreq(len(x), 1 / sr)
    return spec[fr > f].sum() / (spec.sum() + 1e-12)


def selftest():
    sr = 44100
    rng = np.random.default_rng(3)
    x = {v: sing(57, 1.5, sr, rng, vowel=v, breath=0.0, vib_cents=0.0) for v in 'aiuom'}
    hi = {v: _envelope_energy_above(x[v][int(0.4 * sr):int(1.2 * sr)], sr, 1500) for v in x}
    assert hi['i'] > 1.5 * hi['u'], hi
    assert hi['m'] < hi['a'], hi
    print('ok: energy above 1.5 kHz (fraction): ' + ', '.join(f'{v}={hi[v]:.1e}' for v in 'aiuom') + '; i > 1.5 u and m < a')
    for st, p in (('tuvan_kargyraa', 45), ('nordic_kulning', 72), ('bulgarian_chant', 55), ('tuvan_sygyt', 60)):
        y = sing(p, 1.5, sr, rng, style=st)
        assert len(y) > 0 and np.isfinite(y).all()
    print('ok: world vocal styles synthesize cleanly (harmonic_lock, subharmonic, whistle all reach the source)')
    ev = [dict(t=0.0, dur=2.0, p=60, v=90), dict(t=0.5, dur=2.0, p=64, v=90)]
    st, _rep = render_choir(ev, sr=sr, voices=5, seed=4, return_stems=True)
    assert st.shape[1] == 2 and np.isfinite(st).all() and np.abs(st).max() <= 1.0
    assert np.abs(st[:, 0] - st[:, 1]).mean() > 1e-3 and np.abs(st).max() > 0.02
    print('ok: 5-voice choir: finite, stereo spread, audible; report', {k: _rep['report'][k] for k in ('voices', 'phrases', 'peak')})
    assert add_vocal_harmonies(st, sr=sr).shape == st.shape
    assert add_vocal_chorus(st, sr=sr).shape == st.shape
    d = apply_vocal_dsp(st, sr=sr, style='qawwali_devotional')
    assert d.shape == st.shape and np.isfinite(d).all() and np.abs(d).max() <= 1.0
    print('ok: pedalboard harmonies, chorus and vocal dsp chain verified')
    print('selftest passed')


def demo(path, hum=False):
    import soundfile as sf
    chords = [(0.0, [57, 60, 64]), (3.0, [53, 57, 60]), (6.0, [55, 59, 62]), (9.0, [57, 60, 64])]
    if hum:
        mel = [(0.0, 1.2, 62), (1.2, 1.2, 65), (2.4, 0.8, 64), (3.2, 1.6, 62), (5.2, 1.0, 60), (6.2, 1.0, 62), (7.2, 2.4, 57)]
        ev = [dict(t=t, dur=d, p=p, v=80) for t, d, p in mel]
        st = render_choir(ev, sr=44100, voices=5, seed=9, hum=True, config=dict(expression='melancholic'))
    else:
        ev = [dict(t=t, dur=2.8, p=p, v=85, gl=-80 if i == 0 else 0) for t, ps in chords for i, p in enumerate(ps)]
        ev += [dict(t=t, dur=2.8, p=p - 12, v=60, vowel='m') for t, ps in chords for p in ps[:1]]
        st = render_choir(ev, sr=44100, voices=5, seed=9)
    sf.write(path, st / (np.abs(st).max() + 1e-9) * 0.7, 44100)
    print('wrote', path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', nargs='?', choices=['selftest', 'demo', 'hum'])
    ap.add_argument('out', nargs='?', default='choir_demo.wav')
    ap.add_argument('--selftest', action='store_true', help='same as the "selftest" command')
    a = ap.parse_args()
    if a.selftest:
        a.cmd = 'selftest'
    if not a.cmd:
        ap.error('give a command: selftest, demo, hum')
    selftest() if a.cmd == 'selftest' else demo(a.out, hum=(a.cmd == 'hum'))


if __name__ == '__main__':
    main()
