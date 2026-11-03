# Vocal A/B: old engine vs new engine

Files are loudness-matched copies for listening. Numbers are measured from the files. They show faults and differences, not realism. Listen before believing any of it.

| scenario | engine | RMS dB | peak dB | DC | max step / std | dip at joins dB | note level range dB | corr(level, velocity) |
|---|---|---|---|---|---|---|---|---|
| 02_isolated_hum | old | -20.0 | -14.3 | 1.2e-05 | 0.17 | +nan | nan | +nan |
| 02_isolated_hum | new | -20.0 | -13.1 | 1.1e-05 | 0.10 | +nan | nan | +nan |
| 03_connected_hum_phrase | old | -20.0 | -13.3 | 7.2e-06 | 0.19 | -19.9 | 2.9 | +0.96 |
| 03_connected_hum_phrase | new | -20.0 | -13.0 | 1.3e-05 | 0.18 | +0.5 | 2.2 | +0.88 |
| 04_expressive_hum_phrase | old | -20.0 | -13.3 | 7.2e-06 | 0.19 | -19.9 | 2.9 | +0.96 |
| 04_expressive_hum_phrase | new | -20.0 | -12.5 | 1.3e-05 | 0.19 | +0.4 | 2.2 | +0.88 |
| 05_single_singer | old | -20.0 | -9.6 | 1.4e-05 | 0.60 | -20.0 | 3.5 | +0.95 |
| 05_single_singer | new | -20.0 | -10.9 | 1.5e-05 | 0.25 | +0.3 | 2.7 | +0.84 |
| 06_five_hum_ensemble | old | -20.1 | -8.7 | 9.8e-06 | 0.24 | -15.6 | 4.4 | +0.64 |
| 06_five_hum_ensemble | new | -20.1 | -8.0 | 1.4e-05 | 0.22 | -1.3 | 4.3 | +0.26 |
| 07_cinematic_layers | old | -20.1 | -6.7 | 8.4e-06 | 0.32 | -15.4 | 5.3 | +0.81 |
| 07_cinematic_layers | new | -20.1 | -6.3 | 1.4e-05 | 0.30 | -0.4 | 4.6 | +0.70 |

Joins are at 1.2, 2.4 and 3.2 s (the connected notes of the melody). A large negative dip means the voice drops out between notes. Velocities of the seven notes are 70, 76, 80, 88, 70, 78, 66.
