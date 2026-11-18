# Mix profile: the palace render (n5, cProfile, 4-core machine)

Piece: 180.7 s, 31 stems (21 placed in the 3-D field), mix preset on the ambisonic bus (order 5, 36 harmonics), stereo deliverable (binaural decode).
Total 1416.9 s. `cProfile` adds some overhead, so read the shares, not the seconds.

## Stages

| Stage | Time | Share |
|---|---|---|
| 4 stem render | 155.4 s | 11.0 % |
| 4b stem gate | 47.6 s | 3.4 % |
| **5 mix and master** | **906.9 s** | **64.0 %** |
| 6 quality gate | 289.9 s | 20.5 % |
| 7 packaging | 11.9 s | 0.8 % |

## Inside stage 5 (cumulative seconds)

| Function | Calls | Cum |
|---|---|---|
| `hoa.HoaBus.field` (the 3-D mix) | 1 real + 1 probe | 760 |
| `hoa._place_all` (every source, threaded) | 1 | 699 |
| `hoa._reflections` (room reflections per source) | 301 | 715 |
| `hoa.encode` (add a signal to the 36-column field) | 3125 | 265 (self 131) |
| `hoa._late` (late reverb field) | 7 | 59 |
| `mixer.apply_lead_carve` | 1 | 28.5 |
| `mixer.lufs` (all loudness metering) | 3224 | **10.3** |

Everything outside the HOA bus in stage 5 is about 100 s. Loudness metering is 1 % of the render.

## What the reflection loop does

For every source, every room state (the space preset plus one per scene) and every image-source tap of the room geometry, `hoa._reflections` builds
a delayed full-length copy of the source, runs an absorption FIR over it with `lfilter`, runs the air filter (`airabs.apply`, one `fftconvolve` of the
whole span with a Blackman IR), then `encode` adds it to the field with 36 gains. Measured: about 365 000 forward FFTs and 9 800 inverse FFTs, 330 s of FFT time,
130 s inside `encode`, 107 s in `numpy.correlate` (the direct convolutions).

## Where to cut, in order of expected gain (none implemented yet)

1. **One forward FFT per source, one inverse FFT per tap.** Take the rfft of the source span once; for each tap multiply by the delay phase, the absorption response,
   the air response and 1/distance, then one irfft. That replaces the `lfilter` + `fftconvolve` pair (3 transforms) per tap with 1, and pad the span by the longest delay so nothing wraps.
2. **Fold taps into harmonics before the time domain.** Taps that share a room state and a source can be summed per harmonic in the frequency domain
   (36 weights per tap) so `encode` runs once per source instead of once per tap (131 s self time now).
3. **Merge the absorption FIR and the air IR into one filter per tap** if step 1 is not used.
4. **Skip the quiet tail.** Reflections that fall below the room's own floor (level under the late field) need no tap; the preset already carries the thresholds.
5. Stage 6: `sosfilt` in `band_db` (71 s) and `_band_frames` (30 s) filter the same stems repeatedly; share per-stem band signals.

## Checks any change must pass

Same gate rows and values (within 0.01 LU, 0.1 dB true peak), `tests.test_hoa*`, and a before/after timing of stage 5 on this project.

## Not checked

Nothing here was listened to. The profile covers one render on one 4-core machine; a machine with more cores will thread `_place_all` further.
