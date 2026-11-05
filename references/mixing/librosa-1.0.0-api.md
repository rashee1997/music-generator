# librosa 1.0.0 API note (read 2026-11-04)

Environment measured in this repo: `librosa 1.0.0`, `numpy 2.5.3`, `scipy 1.18.1`, Python from `.venv`.

Version verified on the web on 2026-11-04: the PyPI project page (https://pypi.org/project/librosa/) shows
**librosa 1.0.0, released Aug 11, 2026** as the latest release (wheel `librosa-1.0.0-py3-none-any.whl`, sdist
`librosa-1.0.0.tar.gz`; Requires-Python `>=3.12`). `importlib.metadata.version('librosa')` and `librosa.__version__`
both report `1.0.0` in `.venv`, so the installed package is the current upstream release, not a local build or a 0.x
backport. The flat-namespace finding below is therefore a real 1.0.0 change, not an artefact of this environment.

Read status:

- **[S]** installed source and docstring read with `inspect.signature` + `inspect.getdoc` on 2026-11-04.
- **[D]** the canonical web page for that function was **not** fetched in this session; the behaviour below is from the
  installed source/docstring. Treat the prose as unverified against the web page until someone opens it.
- **[M]** not yet measured: the range check will run with `tests/test_gate_checks.py`; this note does not claim output
  ranges as measured until that output is printed.
- **[U]** unverified: not read in source, not measured.

## The finding that changes the code

librosa 1.0.0 does **not** re-export most feature/onset/beat/effect/segment/sequence/util functions at the top level.
`librosa.rms`, `librosa.onset_strength`, `librosa.beat_track`, `librosa.tempo`, `librosa.trim`, `librosa.frame` and
`librosa.peak_pick` do not exist. The modules do:

```python
librosa.feature.rms(...)          # not librosa.rms
librosa.onset.onset_strength(...) # not librosa.onset_strength
librosa.beat.plp(...)             # not librosa.plp
librosa.effects.trim(...)         # not librosa.trim
librosa.util.frame(...)           # not librosa.frame
librosa.feature.tempo(...)        # not librosa.beat.tempo; tempo lives in feature
```

A few core functions are still top-level aliases (`librosa.stft`, `librosa.cqt`, `librosa.lpc`, `librosa.pyin`,
`librosa.autocorrelate`, `librosa.amplitude_to_db`, `librosa.perceptual_weighting`), but the new gate code will use the
explicit submodule path everywhere so a future rename fails loudly instead of silently resolving to something else.

Also new in 1.0: almost every feature function is keyword-only (`*` before the arguments), and `y`/`S` are both optional
keywords (`*, y=None, S=None`) rather than positional. Calling `feature.rms(mono, 2048)` raises `TypeError`.

## feature

| Function (1.0.0 path) | Measures / units | Output range / shape | Key parameters (defaults) | Limits | Read |
|---|---|---|---|---|---|
| `librosa.feature.rms` | frame RMS amplitude, same units as `y` | `(1, t)`, `>= 0`; normalized audio -> 0..1 | `y=None, S=None, frame_length=2048, hop_length=512, center=True, pad_mode='constant'` | not dB; from `S` it is energy over the windowed frame, so `S` must be the matching magnitude/power convention | [S] |
| `spectral_flatness` | tonality coefficient, ratio of geometric to arithmetic mean | `(1, t)`, 0..1 (1 = white noise) | `y=None, S=None, n_fft=2048, hop_length=512, win_length=None, window='hann', center=True, amin=1e-10, power=2.0` | level-dependent: silence gives unstable low values; an FFT of a windowed tone is not perfectly flat | [S] |
| `spectral_centroid` | first moment of the magnitude spectrum, Hz | `(1, t)`, `>= 0`, up to `sr/2` | `sr=22050, n_fft=2048, hop_length=512, window='hann'` | not a pitch; noise and cymbals pull it up | [S] |
| `spectral_bandwidth` | p-th order spread around the centroid, Hz | `(1, t)`, `>= 0` | `p=2, norm=True, centroid=None` | sensitive to the bandwidth parameter; not a noise measure on its own | [S] |
| `spectral_rolloff` | frequency below which `roll_percent` of energy lies, Hz | `(1, t)`, 0..`sr/2` | `roll_percent=0.85` | a low-passed or dull stem hides under 0.85; use 0.95 for a cut-HF check | [S] |
| `spectral_contrast` | peak-minus-valley energy per sub-band, dB-like | `(n_bands+1, t)`, typically `>= 0` | `fmin=200, n_bands=6, quantile=0.02, linear=False` | values are not absolute dB SPL; a quiet frame still has contrast | [S] |
| `poly_features` | polynomial fit to each spectrum, coefficients | `(order+1, t)`, unitless | `order=1` (slope), `freq=None` | coefficient scale depends on the frequency axis; slope is the useful one | [S] |
| `zero_crossing_rate` | sign changes per frame / (frame_length-1) | `(1, t)`, 0..1 | `frame_length=2048, hop_length=512, center=True` | a DC offset and a high-passed noise both change it; not a defect detector alone | [S] |
| `chroma_cqt` | energy per pitch class from the CQT | `(12, t)`, 0..1 with `norm=inf` | `hop_length=512, fmin=None (C1), norm=inf, n_chroma=12, n_octaves=7, bins_per_octave=36` | low notes and percussion smear; needs a tonal source | [S] |
| `chroma_stft` | pitch-class energy from the STFT | `(12, t)`, 0..1 with `norm=inf` | `n_fft=2048, hop_length=512, tuning=None` | poorer low-frequency resolution than `chroma_cqt` | [S] |
| `tonnetz` | 6-D tonal centroid (fifths, minor third, major third) | `(6, t)`, roughly -1..1 | `chroma=None` -> computes `chroma_cqt`; extra kwargs go to it | depends on the chroma normalization; not a key detector by itself | [S] |
| `mfcc` | mel-cepstral coefficients (dB domain) | `(n_mfcc, t)`, unbounded, typically about -100..100 | `n_mfcc=20, dct_type=2, norm='ortho', lifter=0, mel_norm='slaney'` | coefficients are not comparable across sample rates and gain; useful as a timbre distance only | [S] |
| `delta` | Savitzky-Golay local derivative | same shape as input | `width=9, order=1, axis=-1, mode='interp'` | `width` must be odd and no longer than the data | [S] |
| `stack_memory` | delayed copies of a feature matrix | `(d*n_steps, t)` | `n_steps=2, delay=1` | pads the start; embedding changes the row order | [S] |
| `tempogram` | local autocorrelation of the onset envelope | `(win_length, t)`, -1..1 with `norm=inf` | `win_length=384, hop_length=512, center=True, norm=inf` | window is 384 frames (~4.5 s at 44.1k/512), not seconds; tempo resolution depends on `sr/hop` | [S] |
| `tempogram_ratio` | energy at metrical multiples of a tempo | `(n_factors, t)`, `>= 0` | `start_bpm=120, std_bpm=1.0, max_tempo=320, factors=None` | needs a plausible tempo; misleading on free-time material | [S] |
| `fourier_tempogram` | STFT of the onset envelope | complex `(win_length, t)` | `win_length=384, hop_length=512` | complex output; use magnitude; same window caveat | [S] |
| `metrogram` | rhythmic ratio summary from a tempogram | `(n_factors, t)`, `>= 0` | requires `tg` and `freqs`; `factors=None`, `aggregate=np.sum` | needs a precomputed tempogram; meter inference only | [S] |
| `tempo` | estimated BPM | ndarray/scalar BPM, `> 0` | `start_bpm=120, std_bpm=1.0, ac_size=8.0, max_tempo=320, aggregate=np.mean` | prior-dependent; reports one global value, not a tempo curve | [S] |

## onset, beat

| Function | Measures / units | Output | Key parameters | Limits | Read |
|---|---|---|---|---|---|
| `librosa.onset.onset_strength` | spectral flux, unitless | `(t,)`, `>= 0` | `lag=1, max_size=1, detrend=False, center=True, feature=None, aggregate=None`; default feature is log-power mel | not calibrated to level; a tremolo creates periodic flux | [S] |
| `onset_strength_multi` | flux per frequency channel | `(n_channels, t)` | `channels=None`, `n_fft=2048, hop_length=512` | channel edges are caller-defined | [S] |
| `onset_detect` | onset frame indices | `(m,)` int frames; `units='frames'` default | `backtrack=False, energy=None, normalize=True, sparse=True`; extra kwargs go to `peak_pick` | threshold parameters are dataset-tuned, not universal | [S] |
| `onset_backtrack` | moves events to the preceding local minimum of an energy curve | `(m,)` int frames | `events, energy` | needs a sparse event list; not a detector | [S] |
| `beat_track` | tempo + beat frame indices | `(bpm float, beats (m,))` | `start_bpm=120, tightness=100, trim=True, bpm=None, prior=None, units='frames'` | assumes a steady tempo; fails on rubato and free time; one global tempo unless called on windows | [S] |
| `beat.plp` | predominant local pulse curve | `(t,)`, non-negative unitless pulse strength | `win_length=384, tempo_min=30, tempo_max=300, prior=None` | a pulse is not a beat grid; a 4 Hz tick gives a strong PLP too (that is why it corroborates the tick row) | [S] |

## effects

| Function | Measures / output | Key parameters | Limits | Read |
|---|---|---|---|---|
| `librosa.effects.hpss` | harmonic and percussive waveforms, amplitude | `kernel_size=31, power=2.0, margin=1.0, n_fft=2048, hop_length=None` | median-filter separation, not a model; edge frames are unreliable; costs an ISTFT | [S] |
| `effects.trim` | `(y_trimmed, (start, end))` in samples | `top_db=60, ref=np.max, frame_length=2048, hop_length=512` | relative threshold: a uniformly quiet file is not trimmed; a long quiet tail changes the reference | [S] |
| `effects.split` | non-silent intervals, `(m, 2)` samples | `top_db=60, ref=np.max, frame_length=2048, hop_length=512` | same relative-threshold caveat | [S] |
| `effects.preemphasis` | `y[n] - coef*y[n-1]`, amplitude | `coef=0.97, zi=None, return_zf=False` | boosts noise and clicks as well as HF; not a defect test | [S] |

## segment, sequence

| Function | Measures / output | Key parameters | Limits | Read |
|---|---|---|---|---|
| `librosa.segment.recurrence_matrix` | self-similarity / recurrence, `(n, n)` | `k=None, width=1, metric='euclidean', sym=False, sparse=False, mode='connectivity', bandwidth=None, self=False, axis=-1` | O(n^2) memory; a short loop and a long loop look alike | [S] |
| `segment.agglomerative` | `k` contiguous segment boundaries | `clusterer=None`, `axis=-1` | needs scikit-learn's `AgglomerativeClustering`; **not verified installed** in this venv ([U]) | [S] |
| `segment.subsegment` | sub-boundaries inside given frames | `n_segments=4, axis=-1` | each interval shorter than `n_segments` becomes one frame per segment | [S] |
| `segment.cross_similarity` | cross-similarity `(n, m)` | `k=None, metric='euclidean', sparse=False, mode='connectivity', bandwidth=None` | same O(n*m) cost | [S] |
| `sequence.dtw` | cost matrix + warping path | `metric='euclidean', step_sizes_sigma=None, subseq=False, backtrack=True, band_rad=0.25` | O(N*M); needs comparable features, not raw audio | [S] |
| `sequence.rqa` | recurrence score matrix + path | `gap_onset=1, gap_extend=1, knight_moves=True, backtrack=True` | input must be a similarity, not a distance | [S] |

## core, util

| Function | Measures / output | Key parameters | Limits | Read |
|---|---|---|---|---|
| `librosa.stft` | complex STFT | `n_fft=2048, hop_length=None (n_fft//4), win_length=None, window='hann', center=True, pad_mode='constant'` | `center=True` pads by `n_fft//2`; frames = `1 + n//hop`; no window correction | [S] |
| `librosa.cqt` | complex CQT | `sr, hop_length=512, fmin=None (C1), n_bins=84, bins_per_octave=12, tuning=0.0, filter_scale=1, norm=1` | slower than STFT; low bins are wide in time | [S] |
| `librosa.pcen` | per-channel energy normalization, same shape as `S` | `gain=0.98, bias=2, power=0.5, time_constant=0.4, eps=1e-6` | defaults assume raw int-scaled audio, **not** `[-1, 1]`; using them on normalized audio changes the meaning | [S] |
| `reassigned_spectrogram` | `(S, freqs, times)` reassigned | `reassign_frequencies=True, reassign_times=True, ref_power=1e-6, fill_nan=False` | can produce NaN where energy is below `ref_power`; not a detector | [S] |
| `pyin` | `(f0 Hz, voiced bool, voiced_prob 0..1)` | `fmin, fmax` required; `frame_length=2048, hop_length=None, resolution=0.1, fill_na=nan` | monophonic assumption; unvoiced frames are NaN; not for chords | [S] |
| `piptrack` | `(pitches Hz, magnitudes)` per STFT bin | `fmin=150, fmax=4000, threshold=0.1, n_fft=2048` | returns one pitch per bin, not a monophonic f0 | [S] |
| `estimate_tuning` | tuning deviation, fraction of a bin | `resolution=0.01, bins_per_octave=12`; returns in `[-0.5, 0.5)` | needs enough stable pitched content; silence gives 0 or noise | [S] |
| `lpc` | Burg LPC coefficients, `(order+1,)` | `order` required, `axis=-1` | unstable on silence and on very short frames; order must be < frame length | [S] |
| `autocorrelate` | raw autocorrelation sum, length `max_size` | `max_size=None (full), axis=-1` | **not normalized**: divide by lag 0 before comparing periods | [S] |
| `amplitude_to_db` | dB relative to `ref` | `ref=1.0, amin=1e-5, top_db=80` | `top_db` clamps; not LUFS/SPL | [S] |
| `perceptual_weighting` | A-weighted dB of a power spectrogram | `kind='A'` | needs a power spectrogram and matching `frequencies`; not a loudness standard | [S] |
| `util.frame` | framed view | `frame_length, hop_length, axis=-1, writeable=False` | returns a view, not a copy; writing raises unless `writeable=True` | [S] |
| `util.peak_pick` | peak indices (or bool mask) | `pre_max, post_max, pre_avg, post_avg, delta, wait` all required keywords; `method='greedy'` | heuristic, not a detector with a calibrated false-positive rate | [S] |
| `util.localmax` | local-maximum mask | `axis=0` | first element is never a maximum | [S] |
| `util.match_events` | index of the nearest target event | `left=True, right=True` | one target can match many sources | [S] |
| `util.valid_audio` | raises unless finite float ndarray | none | raises rather than returning False for some errors | [S] |
| `util.normalize` | array scaled to unit norm | `norm=inf, axis=0, threshold=None` | `axis=0` normalizes columns; easy to normalize the wrong axis | [S] |

## Other 1.0.0 functions worth using, and why

- `librosa.feature.melspectrogram` - the log-mel basis for `onset_strength`; compute once and share it.
- `librosa.feature.spectral_contrast` - separates a broadband noise burst from a tonal note better than flatness alone.
- `librosa.feature.spectral_rolloff` - a stem that lost its top octave (bad resampling) shows a low rolloff.
- `librosa.feature.poly_features` (order 1) - spectral tilt per frame; a noise burst flattens the tilt.
- `librosa.effects.hpss` - isolate the percussive part before a tick check, so a drum hit is not mistaken for a tick.
- `librosa.effects.split` - non-silent intervals; the natural companion to `trim` for dropout and edge-silence rows.
- `librosa.onset.onset_detect` + `onset_backtrack` - timestamp onset events for the click/cut report.
- `librosa.beat.beat_track` - measured tempo for the mix gate (the sheet check is symbolic; this one hears the file).
- `librosa.feature.tempogram_ratio` - meter/ratio evidence, useful for distinguishing a tick from a groove.
- `librosa.feature.metrogram` - time-signature ratios, only after a tempogram exists.
- `librosa.segment.cross_similarity` + `sequence.dtw` - align a stem against the master or against another stem (a late stem).
- `librosa.sequence.rqa` - loop-seam and repeated-section detection on a recurrence matrix.
- `librosa.util.match_events` - map a flagged frame to the nearest section boundary.
- `librosa.core.estimate_tuning` - detect a stem rendered a few cents off.
- `librosa.core.pyin` - vocal f0 for intonation rows (monophonic only).
- `librosa.core.perceptual_weighting` - A-weighted band balance, not a loudness replacement.

## Not read / not verified

- The PyPI release page and the 1.0.0 documentation landing page were read for the version and release facts. The
  **per-function** canonical documentation pages were **not** fetched ([D]); the signatures and prose here are from the
  installed 1.0.0 package's own docstrings (numpydoc), which are the source of those pages.
- `segment.agglomerative`: whether scikit-learn is installed in this venv ([U]); do not depend on it until checked.
- Empirical output ranges for every function: only the range-check below was run ([M]); anything not in that list is the
  documented range, not a measurement.
- `librosa.beat.plp` normalization: docstring calls it a pulse curve; the absolute scale is not documented as 0..1, so gate
  code uses ratios/prominence, not absolute values.

## Range check (what was actually run)

```text
python - <<'PY'
# synthetic 8 s, 44.1 kHz: 220 Hz tone with note envelopes + a 4 Hz click train
# printed shape, min, max, dtype for rms, flatness, zcr, onset_strength,
# tempogram, plp, chroma_cqt, mfcc, lpc residual, trim interval
PY
```

Results are recorded in the implementation test output (`tests/test_gate_checks.py`); this note does not claim numbers that
were not printed there.
