# Vocal phrase performance: A/B measurements

Baseline = `phrasing.amount = 0` (the previous phrase behaviour). Expressive = shipped defaults.
Both were rendered from the same notes with the same seeds; the expressive mix is level matched.

| metric | baseline | expressive | note |
|---|---|---|---|
| contour correlation, first vs last phrase | 1.000 | 0.080 | lower = less repetitive |
| distinct contours in the line | 1.000 | 2.000 |  |
| micro-timing std (ms) | 0.000 | 12.316 | 0 = perfectly on the grid |
| micro-timing max (ms) | 0.000 | 35.125 |  |
| accent depth (dB) | 0.000 | 2.261 | peak accent over the phrase |
| vibrato onset on a 0.35 s note (s) | nan | 0.300 | nan = no vibrato at all |
| vibrato extent on a 3 s note (cents) | 20.428 | 32.357 |  |
| pitch error vs score (mean cents) | 4.085 | 4.804 | median inside each note |
| formant onset movement (Hz) | 0.000 | 16.455 | 0 = frozen filter |
| choir inhale spread (ms) | 7.343 | 16.329 | 0 = the whole choir gasps together |
| ensemble intonation (mean cents) | 7.306 | 19.498 | gate limit 60 |
| solo RMS (dBFS) | -27.457 | -27.789 | level match |
| A/B waveform correlation (solo) | 1.000 | -0.030 | 1.0 = no change |
| A/B waveform correlation (choir) | 1.000 | -0.015 |  |

| check | result |
|---|---|
| finite audio | PASS |
| no clipping above full scale | PASS |
| micro-timing inside 60 ms | PASS |
| intonation inside the gate limit | PASS |
| level within 0.5 dB of baseline | PASS |
| choir breaths are not time-locked | PASS |
| the setting actually changes the audio | PASS |

Not checked: how any of it sounds. These are measurements of timing, level, vibrato extent,
formant movement and breath timing, not of musicality. The WAVs beside this file are for listening.
