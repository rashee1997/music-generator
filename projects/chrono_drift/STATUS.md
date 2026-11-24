# Project Status: Chrono Drift

Rebuilt from scratch on 2026-11-24 (`projects/chrono_drift` deleted first; nothing carried over from the earlier cue).

## Flow (SKILL.md)

- [x] 1. Project scaffolded
- [x] 2. Research: `reports/research_black_hole_gravity_time_dilation_tension_cinematic.md`, KB ids cited plus five web sources
      (Chandra Perseus sonification, NASA on tidal forces and time dilation, NASA data sonifications, Sabine's RT60 equation)
- [x] 3. Direction sheet: `direction/direction_chrono_drift.json`, every field filled, `immersive` and `expression` included
- [x] 4. Nine instrument presets, one space preset, one mix preset; every preset carries `sources`
- [x] 5. Score: `scores/chrono_drift_score.json`, 76 bars of 4/4 at 152 BPM = 120.0 s
- [x] 6. `pipeline.py ... --targets stereo,immersive_3_2` → `out/master_v01.wav`, `midi/`, `stems/`, `reports/ci_report.json`
- [x] 7. Revised one lever at a time until the stereo master certified (15 renders; see "What changed" below)
- [ ] 8. `listen.py` did **not** run. The ears are not part of this delivery.

## Delivered

| item | value |
|---|---|
| master | `out/master_v04.wav` (= `out/master.wav`), version 4, 44.1 kHz, 24-bit, stereo, 127.34 s (120.0 s cue + 7.3 s room tail) |
| loudness | −16.38 LUFS integrated, −1.50 dBTP true peak, crest 17.7 dB |
| verdict | **STEREO CERTIFIED**; the 3.2 immersive format failed its own rows and was not delivered |
| score | D phrygian, 152 BPM, 4/4, 9 tracks, no SFX, no ambience |

## The piece

- **Form**: accretion 0–15.8 s (pedal, piano fragment) → tidal 15.8–41.1 (cello sixteenths enter, pad widens, timpani quarter pulse)
  → crush 41.1–72.6 (low brass, choir, chromatic violin climb) → dilation 72.6–94.7 (hard cut; harp and choir, the figure at half
  length) → horizon 94.7–113.7 (everything returns, crest at 110.5 s) → last light 113.7–120.0 (one piano D over the field).
- **Carriers of pressure** (KB `cinematic-hybrid-scoring` §1): a pulse that never stops (bowed sixteenths on chord tones), low brass
  and sub weight at the turns, constant percussion (one timp, four strokes per bar, never a kit), and a rising device (the violin
  climbs a semitone every two beats through the crush).
- **The figure**: D–F–E–Eb–D–C–D. Stated as a four-note fragment at 5.5 s, whole at 22 s, in octaves at 44 s, at double length in
  the dilation, and reduced to one D at 115 s. The Eb is the phrygian colour and it never resolves upward.
- **SF2 naturalness**: every sampled instrument carries a `velocity_timbre` block (four velocity bands with a low-pass per band),
  because TinySoundFont applies no velocity-to-filter modulator and one sample per key — level alone would make the soft statements
  read as the loud ones turned down.
- **No SFX**: no `sfx:` track, no whoosh, no riser, no impact sample. The crush is a chord; the cut at 72.6 s is silence plus the room.

## What changed while certifying (one lever at a time)

| gate row | measurement | change in the piece |
|---|---|---|
| `stem.dropout` / `stem.dead` | sub pedal had a 685 ms hole and one dead section | one pedal note per two bars, no gap |
| `machine_gun_percussion` | timpani roll flat at 9 hits | exponential crescendo plus alternating accents |
| `harmonic_resolution_feel` | octave-doubled figure leaped 12 semitones; later the D→A fourth under the bII | doubling dropped; the figure steps down to C |
| `master.dc` | 0.00368 FS "drift" | pedal moved out of the sub-sonic band, 40 Hz master high-pass (the row itself was also fixed, below) |
| `tempo.audio` | 99.4 BPM measured on a 152 BPM master | timpani became a quarter-note pulse (the row itself was also fixed, below) |
| `cochlear_roughness` | 0.128 at 10.5 s: piano D4 against Eb4 in one critical band, plus the pedal's 294 Hz partial | the opening fragment speaks an octave higher; pedal low-passed at 180 Hz |
| `spiral_tension_arc` | momentum 2.13 at bar 8 | the accretion's bass became a true pedal point on D; the horizon keeps Bb through the C |
| `stem.tick` | harp at 0.54 on a 197 ms grid | the harp figure is syncopated and enters only at the dilation |
| `channel.bars` | sub pedal one-bar polarity flip | the overlapping pedal note per bar was removed |
| `stem.edge` | 510 ms trailing silence | the last pedal note is held past the end of the score |

## Gate fixes made after this cue (general, not project-specific)

Everything below was a measurement that decided a row wrongly; no threshold moved (`tests/test_gate_no_loosening.py`
still passes, and the regenerated snapshot adds two parameters and changes no number).

1. **`channel_qa` polarity** judged a bar against its neighbours with a fixed ±64-sample lag search. At 44.1 kHz that is
   1.45 ms, the half-period of 345 Hz, so a bar of anything lower could not be aligned: a clean, never-inverted 220 Hz
   tone read **−0.96** against its own next bar and was reported as a polarity inversion, while the same code at 8 kHz
   (where the unit test runs) read +0.96. The search now follows the sample rate and is capped at a quarter bar, polarity
   is judged on the band above 500 Hz where inversion is not just a delay, and a pair is skipped when both signs reach the
   peak (an inverted copy and a half-period-delayed copy are the same waveform).
2. **`channel_qa` level floors**: the only guard was an absolute −60 dBFS, so a 7.1 LFE sitting at −60 dBFS produced 29
   of 33 reported faults at levels between −48 and −111 dBFS while the programme ran at −25. Jump and dropout now need the
   channel to be part of the programme, the low-frequency channel is never judged for polarity, and a balance swing must
   move the image further than the bar's own total (a part entering mid-bar is not a pan fault).
3. **`imm.surround_ratio` and `imm.height_arc` summed channel means over groups of different sizes**: four surrounds
   against three fronts read **+1.25 dB** at an identical per-speaker level, and seven beds against two heights **+5.44 dB**.
   Both now use the group mean, the same correction `channel_qa._energy` already documented. The windows and ceilings are
   unchanged.
4. **`check_dc` on files shorter than four seconds** was decided by its own decimating filter's start-up (8e-3 of "drift"
   on a clean 2 s control): the guard is now proportional on a short file.
5. **`check_tempo`**: the onset count that decides whether a tempo can be judged was peak-relative, so a cue that runs from
   a quiet opening to a loud climax counted only its climax attacks (37 frames in 127 s, a quarter-note pulse throughout)
   and declined to judge it. It now counts with the adaptive detector. The four-quarter drift was the spread of quarters that
   had locked onto half or double the beat (75.8 BPM of "drift" on a render that does not drift); each quarter is snapped to
   the nearest metrical relative first.

Effect measured on this project's delivered 7.1 file: `channel.bars` went from **33 conflicts to 0** over 80 bars, and
`imm.surround_ratio` now reports the true per-speaker figure (+0.3 dB instead of +1.5 dB).

## Engine fixes made for this cue (general, not project-specific)

1. **`gate_checks.check_dc`** measured "DC drift" as the spread of 1-second block means. A block mean is a boxcar decimation, and
   a low programme tone leaks about A/(πf) into every block: a clean 73 Hz pedal read as 2.2e-3 FS of offset. The drift is now
   measured on the sub-2 Hz component (decimate to ~400 Hz, 4th-order low-pass at 2 Hz, one second dropped at each edge for the
   filter's own start), so an offset still fails and a low note does not. On this master the row went from 0.00282 FS to 0.00001.
2. **`gate_checks.check_tempo`** deferred to `librosa.beat.beat_track`, which returns **0.0 BPM on a perfect 152 BPM click track**
   (librosa 1.0.1) and 99.4 BPM on a 152 BPM master whose onset envelope autocorrelates at exactly 152.0 (2:3 of 152 is 101.3, which
   is what it locked to). The row now reads the mean-removed onset-envelope autocorrelation peak inside a 50–220 BPM window, with
   parabolic lag refinement, and skips a signal with no attacks instead of inventing a tempo. This master measures 151.7 BPM.
3. **Tests**: `tests/test_gate_dc_tempo.py`, six cases (152/90/120 BPM clicks, wrong tempo fails, no-pulse skipped, clean low tone
   passes, a real offset fails, a slow offset drift fails). All six pass.

## Not done / limits

- **Immersive: objects delivered, 7.1 loudspeakers still failing one real row.** "3.3" was clarified as ADM object-based
  spatial audio in eight channels, which here is two formats: `adm_bw64` (one object per placed track, ITU-R BS.2076 metadata in
  a BW64 container) and `immersive_7_1` (ITU-R BS.2051 System H, eight discrete channels). The ADM file **passed every row**
  (11 tracks: 9 objects + a stereo reverb bed, captured before the last send trims). The 7.1 file now passes `channel.bars` and
  every other row except `imm.surround_ratio`, which reads **+0.3 dB** against a −9..−2 dB window: the surrounds in this mix sit
  level with the front stage, so about 2.3 dB of real trim is still owed in the space or the sends. It was withheld rather than
  delivered uncertified.
- **The low-frequency channel is effectively empty in the 7.1 file** (−60 dBFS RMS): the pedal lives at 73 Hz and above while the
  LFE low-passes at 80 Hz with a −10 dB send. That is a mix decision still to make, not a gate row, and it is why the per-bar row
  used to light up on it.
- **`listen.py` did not run.** Nothing here has been judged by the ears, only measured.
- The last nine renders were `--max-attempts 1` single passes after a specific measured change, not automatic retries.
- `reports/ci_report.json` for the certified stereo pass is the record; earlier attempts are in `/tmp/render*.log`, which is not versioned.

## Director's second review

- **Could be flat in the middle**: the crush runs 31 s. Measured: the section energies are accretion 0.22, tidal 0.50, crush 0.95,
  dilation 0.55, horizon 0.92, last light 0.15, and `section.energy` correlates 0.66 with the sheet (WARN, threshold 0.7). Density
  moves with them (one part → seven → three → seven → one).
- **Could be two competing leads**: the violin climbs across the crush while the piano states the figure. Measured: `spatial
  z_separation` passes with the brass/violin pair 171° apart, and the violin is 6 dB under the piano.
- **One thing a producer would change first**: the dilation holds the same harp figure for 22 s at one velocity band; a real player
  would vary the roll. That is the weakest stretch of the piece.
- **Not heard, not measured**: whether the room at 6.5 s reads as vast or as a reverb effect; whether the 3.2 LFE problem is
  audible or only a measurement of a low channel doing what a low channel does.

## Self-check

| box | answer |
|---|---|
| `pipeline.py` ended with 0 FAIL on the delivered format | **yes** for stereo (STEREO CERTIFIED); **no** for the requested immersive format |
| `listen.py` ran | **no** — ears did not run |
| every WARN listed with its cause | yes, the ones that remain: `section.energy` 0.66, `preflight.roughness_partials` (advisory forecast) |
| thresholds loosened or rows skipped | no |
| research cited | yes (KB ids + 5 URLs) |
