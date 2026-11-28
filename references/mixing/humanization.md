---
title: Humanization
summary: Where to add timing, velocity and articulation variation, and where not to.
tags: [humanize, timing, velocity, swing, rubato, grid, performance]
load_when:
  - a render sounds mechanical
  - a dance or techno grid must stay tight
---

# Humanization: why machines sound robotic and what to change

A score where every note starts exactly on the grid, with the same loudness and the same length, sounds
mechanical even with real recorded samples. Human performances deviate in **structured** ways. `scripts/humanize.py` (the facade over
`scripts/humanize_engine/`) applies the following automatically (preset `natural` by default). Use this page to tune it or to hand-write
nuance in custom scripts.

## 1. The deviations that matter (with numbers)

| Aspect | What real players do | What humanize.py does |
|---|---|---|
| Melody vs accompaniment | The melody voice sounds ~10-30 ms **before** the other voices and is played louder ("melody lead", Goebl 2001; the velocity advantage is the cause, not a choice) | melody offset = -lead_ms (20 ms natural), melody velocity +8, chords -6, pads -10 |
| Timing error | Not white noise: long-range (1/f^beta) correlations in both intervals and amplitudes, plus note-to-note errors that are **anti-correlated** along one limb (a late note is followed by an early one). Drummers: inter-beat-interval SD roughly 9-15 ms in good playing | spectral 1/f^beta short-scale error plus per-limb `e[i] - 0.5 e[i-1]` (sigma 7 ms), and a shared 1/f drift (9 ms) |
| Tempo | Breathes on the real phrases: speed-up into a phrase's middle, slowing at its end, and a final ritardando that follows a stopping runner's braking curve | `TempoMap`: arch on the figure's phrase spans (+-2.5 %), 1/f wander (0.6 %), final ritardando 35 % over the last 6 beats with q = 3 |
| Dynamics | Downbeats stronger; phrases swell to a peak and relax; higher notes slightly louder in a rising line; last note of a phrase softer | metric accent, phrase arch (+-3.5), pitch-contour term, phrase-end relax |
| Chords | Never struck at one instant: guitar strum 20-80 ms, piano roll 5-20 ms, harp roll 20-40 ms | strum spread 10 ms (up/down alternating) |
| Articulation | Legato notes overlap the next one by tens of ms; staccato = ~50 % length; every note length varies a few % | overlap 35 ms on legato roles, +-4 % duration jitter, `"art":"staccato"` honoured |
| Vibrato (voice, strings, winds) | 5-6.5 Hz, ~20-50 cents peak-to-peak range for strings, starts after ~200-300 ms and grows, differs on every note | per-note pitch-bend LFO, delayed onset, random rate/depth/phase |
| Note shape | A bowed/blown note is not a flat rectangle: it blooms, then fades | per-note CC11 expression curves (`bow`, `breath`) |
| Pedal / sustain | Piano: pedal changes with each harmony, lifted just before the new chord | `auto_pedal`: lift 40 ms before each chord change |
| Drums | Kick tight/early, snare a touch late, hats loose; ghost notes (very soft) between backbeats; a fill every 4-8 bars; the same hit is never twice identical | piece-specific push (kick -3 ms, snare +5 ms), velocity jitter, `drum_bar` ghost notes + fills |
| Swing | Off-beat 8ths late: 0.5 = straight, ~0.58 light, ~0.66 triplet feel. The ratio falls as the tempo rises (BUR ~3.5:1 slow, 2:1 medium-fast, 1:1 near 280 bpm), a soloist swings less than the ride cymbal, and the short side of a pair has a physical floor near 95 ms | `score["swing"]`, or `"swing": "auto"` for the tempo-derived ratio; `apply_swing(..., bpm=, role=)` |
| Tuning | Not exactly equal-tempered every note; ensembles are a few cents apart | random +-3 cents per note on per-note channels, `detune_cents` per track (the renderer applies it) |
| Tempo-relative spread | Microtiming is a fraction of the beat (0.026 beats in funk, 0.068 in swing), not a fixed number of ms | `timing_beat_frac` (default 0: the old absolute `timing_ms`); capped by `timing_cap_ms`, drums stay under 10 ms |
| Vertical spread between parts | An ensemble is 20-50 ms apart; the bass is the reference, treble parts sit behind it, and the melody leads at downbeats more than elsewhere | `score.asynchrony` -> one stable signed offset per named part (`ensemble.asynchrony_field`), capped at 35 ms |
| Pushed / laid-back | A pocket is timing AND dynamics: a laid-back snare is later and louder, a pushed hi-hat is earlier and louder | `pocket` on a drum track -> `references/data/presets/humanize/<name>.json`, per limb ms + velocity delta |
| Swing shape | Measured swing delays the on-beat note too, and a soloist's ratio curve is not a scaled drummer's | `swing_downbeat_ms` (0-20 ms, default 0) on top of the off-beat shift |

KTH performance rules (Friberg, Bresin & Sundberg 2006): "high loud", "phrase arch", "final ritard",
"duration contrast", "double duration", "faster uphill", "punctuation", "repetition articulation", "high sharp" and
"leap articulation" are all in the model now, each with its own `TIMING` weight (section 1b, 1d). They act on the
notes, not on the score: switch a rule off by setting its weight to 0.

## 1b. The timing model's own keys (all overridable)

`humanize.TIMING` holds the values the model starts from; a preset, a score or a per-track `humanize` dict overrides any
of them. They exist because the old model had one behaviour for every piece.

| Key | Default | What it does |
|---|---|---|
| `note_lag1` | 0.5 | how much each note is pulled back toward the previous one. This is the term that gives a real player's negative lag-1 timing correlation; the measured value at 0.5 is about -0.4 on the motor term alone |
| `drift_corr_beats` | 6 | how slowly the wander moves (in notes) |
| `vel_dur` | 0.018 | a louder note is a little longer, a softer one shorter (duration moves by ~1.8 % per 64 velocity) |
| `tune_drift_cents` | 1.2 | a phrase drifts in intonation together instead of every note being independently detuned |
| `just_ratio` | 0.45 | chord tones bend toward just intonation (major third ~-13.7 cents, fifth ~+2); 0 = 12-TET |
| `push_tempo_power` | 0.4 | scales the fixed drum push with tempo (96 bpm is the reference) |
| `subdiv_push_ms` | 1.2 | extra hat push when the part is written in 16ths or faster |
| `fractal_beta` | 0.85 | slope of the 1/f^beta timing, drift and velocity wander (measured band 0.5-1.0) |
| `short_scale_beats` | 8 | the crossover between the short process and the shared long one (Sogorski et al. 2018: ~8 beats) |
| `short_share` | 0.22 | share of the short-scale timing variance that is 1/f rather than white motor error; per preset (0.15 tight .. 0.30 loose) |
| `vel_time_couple` | 0.35 | on drums, how much velocity wander follows the microtiming (Rasanen et al. 2015) |
| `duration_contrast` | 0.06 | shorten short notes / lengthen long ones (KTH) |
| `double_duration` | 0.10 | soften a written 2:1 pair by ~10 % each way |
| `faster_uphill_ms` | 2.0 | an ascending step leans forward, up to 2 ms (0.35 ms per semitone) |
| `punctuation_ms` | 12 | micro-phrase comma: lengthen the turn's last note, delay the next gesture |
| `repetition_gap_ms` | 14 | air before a repeated identical pitch, taken off the held note's end (no onset move) |
| `high_sharp_cents` | 1.5 | high register sits slightly sharp (per octave above C4), figure roles only |
| `vel_lead_ms` | 6 | a harder stroke arrives sooner: the loud note of a chord leads it (Goebl 2005) |
| `phrase_tempo_vel` | 2 | phrase dynamics track the phrase rubato (Todd 1992) |
| `melodic_charge_vel` / `_dur` | 2.0 / 0.015 | velocity and length grow with a figure note's circle-of-fifths distance from the sounding root |
| `harmonic_charge_vel` / `_dur` | 1.5 / 0.010 | the same for a chord root's distance from the tonic |

**The drift is shared, not per track.** `tempo_map_for()` attaches one `shared_drift` curve to the tempo map, and every
track of the piece reads it. Before this each track drew its own drift, so two players of one section wandered apart by
tens of milliseconds. `humanize_track(..., drift=(beats, values))` overrides it by hand.

**Articulation is an instrument property.** `humanize_track(..., articulation={'overlap_ms': 30, 'gate': 1.0})`, set by
the instrument preset, replaces the role's fixed 35 ms overlap (a bowed line overlaps more than a plucked one).

**Velocity and duration move together**: a score that writes one flat velocity still gets level variation, but it is no
longer level alone.

## 1c. The role decides the phrasing (`humanize.ROLE`)

A role is a function, and every function is played differently. `humanize.py` reads the canonical role from
`scripts/roles.py`; a role it does not know raises rather than falling back to a comp, which is how a drone used to be
phrased like a chord.

| Role | Offset of `lead_ms` | Velocity | Gate | Why |
|---|---|---|---|---|
| `melody`, `lead` | -1.0 (early) | +8 | 1.00 | the figure leads the accompaniment (Goebl 2001) |
| `vocal` | -0.9 | +7 | 1.03 | a sung line sits slightly ahead and holds longer |
| `counter` | -0.4 | +2 | 1.00 | answers the lead, does not lead |
| `chord` | +0.2 | -6 | 0.95 | comps behind the beat, shorter than written |
| `pad` | +0.3 | -10 | 1.02 | sustains, never re-attacks on the grid |
| `texture` | +0.3 | -10 | 1.03 | a grain bed is shaped like a pad, not like an effect |
| `drone` | +0.3 | -10 | 1.05 | holds through the harmony change |
| `bass`, `drum` | 0.0 | -1 / 0 | 0.90 / 1.00 | the rhythm section stays on the grid |
| `ostinato` | +0.1 | -3 | 0.94 | the cell repeats, but every repeat is played |
| `arp` | +0.1 | -4 | 0.85 | even and short |

A `groove` or `texture` piece has no figure, so nothing gets the melody lead; the piece is phrased by its cell and its
surface. The mix's `level_by_role` and `widen_by_role` follow the same roles, so phrasing and level cannot disagree
about what a part is.

## 1d. The newer parts of the model

- **Two scales, one exponent.** Timing error is generated as 1/f^beta noise in the frequency domain, split at
  `short_scale_beats` (8): the short band (`timing_ms`, per player, larger in jazz/loose) and the long band
  (`drift_ms`, shared by the whole section). The old Gaussian-smoothed white noise had one correlation length
  and no scale-free regime, which is what listeners rate as less human than 1/f.
- **One motor stream per limb/finger.** The lag-1 correction now runs inside each stream: one limb on a kit
  (kick {35,36}, snare {37,38,40}, hats/ride {42,44,46,51,53,59}, ...) and one pitch on a keyboard. A simultaneous
  kick and hi-hat are two limbs; two notes of one chord are two fingers. Correlating the flat sorted list made the
  hi-hat's error depend on the kick's and note 2 of a chord on note 1, which is not motor behaviour.
- **The close is kinematics, not a parabola.** `ritard_q` (default 3) sets v(x) = [1 + (w^q - 1)x]^(1/q) with
  w = 1 - ritard: constant braking power, the curve that fits measured final ritardandi and the best-rated
  decelerations (Friberg & Sundberg 1999). `ritard_q: 2` gives constant braking force.
- **Swing has a tempo.** `swing: "auto"` derives the beat-upbeat ratio from the tempo, the figure roles swing at
  60 % of the accompaniment's depth, and no swung pair is allowed a short side under 95 ms, so fast passages
  straighten themselves instead of asking for an unplayable note.
- **The phrase is one structure.** `tempo_map_for(score)` reads the figure's real phrase spans and puts the rubato
  arches on them; `humanize_track` reads the same spans for its velocity arches and its phrase-end relax, and its
  velocity follows the local tempo factor (`phrase_tempo_vel`). A fixed 16-beat rubato over a 5-beat phrase swelled
  where the line did not.
- **The humanizer can hear the harmony.** `tempo_map_for` also carries the tonic and the sounding chord roots (the
  lowest note of each chord/pad/bass cluster). A figure note's distance from the root on the circle of fifths, and a
  root's distance from the tonic, raise velocity and length a little (KTH melodic/harmonic charge).
- **Moods are a separate axis.** `MOODS` (`tender`, `bright`, `solemn`, `urgent`) scale level, gate, accent,
  duration contrast, strum and rubato on top of any groove preset (GERM: Juslin, Friberg & Bresin 2001). Set
  `"mood"` on the score, or pass `mood=` to `humanize_track`; an unknown name raises.
- **A declared limit: the coupling is first-order and score-level.** Each part is corrected once, toward one
  anchor, from the onsets it shares with it; there is no iterative re-estimation after the correction, no
  part-to-part network (a string section correcting toward the cello while the cello follows the bass), and
  ensemble expansion's per-player jitter is not in the estimate (the curve is per written onset, and the render
  applies it to every player). Breath and hand-span constraints are still not modelled: a phrase a player cannot
  play is not shortened by the engine.

## 1e. Tempo-relative spread, ensemble field, pockets, swing shape

- **`timing_beat_frac`** (default 0): the short-scale sigma becomes a fraction of the beat, floored at
  `timing_ms` and capped by `timing_cap_ms` (40 ms; drums 10 ms). Measured microtiming is 0.026 beats in funk
  and 0.068 in swing (Frontiers in Psychology 2016), so a ballad and a dance should not share a fixed ms value.
- **`score.asynchrony`** `{amount_ms}` (absent = off): `tempo_map_for()` attaches one stable signed offset per
  named part, from instrument family (bass and drums reference; strings, winds, brass, voices behind) and the
  seed; the renderer passes each track's name and `humanize_track(..., part=)` adds it. Capped at 35 ms a side.
  Measured spread: 20-50 ms between players, 30-50 ms between sections (Rasch; Tahvanainen et al. 2015), bass
  leading by ~22 ms and treble lagging (TISMIR 2026). Weights are starting values; the sign is measured.
- **`pocket`** (drum tracks): replaces the fixed per-piece push with a per-limb table of signed ms and a
  velocity delta (`references/data/presets/humanize/<name>.json`, validated by `presets.py`). The direction is
  measured (laid-back strokes later and louder, pushed ones earlier and more intense; Music Perception 2024;
  JNMR 2017 found a 2-26 ms hi-hat lead); magnitudes are starting values.
- **`swing_downbeat_ms`** (default 0, clipped +/-20 ms): delays the notes on a beat, because measured swing is
  a long-short pair with a late on-beat note too (Communications Physics 2022).
- **`score.coupling`** (absent = off): `{mode: "phase", gain: 0.6, anchor: "auto", window_beats: 2, cap_ms: 25}`.
  A pre-pass humanizes every part without audio, measures each one's asynchrony against the anchor (drums, then
  bass) at the onsets they share, and gives each part a bounded, smoothed correction curve that
  `humanize_track` adds to its onsets. The pre-pass takes the render's own arguments (swing unit, strum
  direction, instrument, articulation), so the curve is estimated from the performance that plays, and its
  result is cached by score, seed, renderer and resolved presets, so a fully cached rebuild does not
  re-humanize every track to rediscover the same curves. An `anchor` naming a track that did not render is an
  error, not a fallback. This is the measured first-order linear correction (J. R. Soc. Interface
  2014; the coordination structure listeners hear, PLOS One 2025), not a new offset: the stable vertical field
  of section 1f supplies the spread, this removes part of it. `gain` is a starting value at the 0.6 the
  first-order model predicts for minimal asynchrony variance; `cap_ms` bounds what one player can be moved.

## 2. Presets (in `humanize.PRESETS`)

| Preset | timing_ms | lead_ms | drift_ms | vel_sigma | rubato | Feel |
|---|---|---|---|---|---|---|
| tight | 3 | 8 | 3 | 3 | 0 | pop/electronic, near the grid but not dead |
| natural | 7 | 20 | 9 | 5 | 2.5 % | default: a good studio player |
| loose | 12 | 25 | 15 | 7 | 4 % | folk, jazz, lo-fi, live band |
| rubato | 9 | 28 | 12 | 6 | 7 % | solo piano, film ballads, ambient |
| punchy | 4 | 10 | 4 | 4 | 1 % | pop, rock, funk: the offbeat gets the accent, the grid stays tight |
| bouncy | 5 | 12 | 5 | 5 | 1 % | dance, funk, light swing: lift on the upbeats without leaving the grid |

`punchy` and `bouncy` are the two presets whose accent lands on the offbeat (`upbeat=True` in `PRESETS`), which is why
they read as a groove rather than a sloppier `natural`.

### 2a. The phrase arch has a size, and it follows the written level

`vel_arch` (tight 5, natural 7, loose 11, rubato 10, punchy 6, bouncy 8, in MIDI velocity units) is how far a phrase
swells to its middle. It is multiplied by `clip(v_in.mean() / 90, 0.45, 1.35)` for every phrase, so a phrase the score
wrote at *pp* arches less than one at *ff*. One fixed +-7 on every phrase of every piece made a written *pp* and a
written *ff* arch by the same amount, which is a mannerism rather than a performance.

**Every velocity-shaping term shares that scale.** The run shaping in `dynamics.shape_velocity`, the KTH melodic and
harmonic charge and the expectation coupling in `track.humanize_track` are all multiplied by the same
`gain = clip(mean / 90, 0.45, 1.35) x vel_arch / 7`. A term left at a fixed value while the arch grows is a detail the
arch cancels: the group-start accent of a run stopped reading as the loudest note of its group, and
`event_stats()['coupling']['ic_vel_rho']` fell from 0.55 to 0.47 when only the arch was raised.

Pass a dict to override any key: `"humanize": {"timing_ms": 5, "lead_ms": 30, "strum_ms": 18}`.
Per-track: `"humanize": "loose"` inside a track overrides the score setting.

### 2b. What the score can set

The tempo and expression keys below are read by `tempo_map_for()` (and so by the renderer and the gate clock) or by
`humanize_track()` (directly, or through the renderer). They live in the score, next to `bpm` and `humanize`; a
per-track `humanize` dict overrides the track's preset, never these score-level keys.

| Score key | What it sets |
|---|---|
| `humanize` | preset name (or dict) per score, and `"humanize"` inside a track overrides it for that track |
| `swing` | offbeat placement: 0.5 straight, 0.58 light, 0.66 triplet feel; `"auto"` takes the ratio from the tempo |
| `rubato`, `wander` | phrase-arch amplitude, and the slow shared tempo wander |
| `ritard`, `ritard_beats`, `ritard_q` | the final ritardando: depth, length, and the braking law (3 = constant braking power) |
| `phrase_beats` | the rubato period used only when the figure has no phrase spans to follow |
| `tempo_points` | explicit tempo map, `[[beat, bpm], ...]`, linear between points |
| `fermata` | held beats, `[(beat, extra_seconds), ...]` |
| `elastic` | long-range breathing: `{amount, corr_beats, breaths, breath_s}` (section 3e) |
| `asynchrony` | `{amount_ms}`: the vertical spread between named parts (section 1f); 0 or absent = no field |
| `mood` | `tender`, `bright`, `solemn` or `urgent`: an expression profile on top of the preset (section 1d) |
| `key` | the tonic, used by the figure's tonal charge (a wrong key changes phrasing, not notes) |

## 3. Instrument-specific advice

- **Piano**: let the pedal ring through a chord, lift at changes; melody 8-10 velocity above the accompaniment; roll big chords.
- **Strings (bowed)**: one channel per note (automatic); `expression: "bow"`; vibrato on long notes only; keep ensemble pads long and legato; avoid repeated identical bow starts.
- **Winds/brass**: `expression: "breath"`; leave 1/4-1/2 beat rests where a player must breathe (phrase ends); no playing above the comfortable range (see `natural-instruments.md`).
- **Guitar**: strum with `strum_ms` 15-25; alternate down/up; palm-muted low strings; avoid chords above the 12th fret region.
- **Bass**: slightly behind or exactly on the kick; notes 85-95 % long, not wall-to-wall; octave jumps sparingly.
- **Drums**: lower hat velocity on off-beats, accent backbeats, ghost snares at 20-40 velocity, a different fill each time, crash only at section starts. The kit has 3-4 snare/kick variants: alternate them (`snare`/`snare2`, `kick`/`kick2`) for round-robin feel.
- **Voice / choir pads**: slow attacks (CC11 curve), no hard repeated notes, long legato with vibrato 5 Hz.

## 3b. Checking the model, not trusting it

`python scripts/humanize_report.py <score.json>` prints the tempo-adjusted deviation, lag-1 correlation,
velocity/duration coupling, DNVR/DNODR, estimated swing ratio and the ensemble spread, without rendering audio.
It is advisory: it reports, it never edits the piece, and it is not a gate row.

`tests/test_humanize_stats.py` and `tests/test_humanize_engine.py` assert the claims instead of the code: two tracks of a piece share one drift; the motor
term is negative at lag 1; louder notes are longer; a major third sits about 14 cents flat under `just_ratio: 1`; an
instrument articulation overrides the role overlap; the drum push grows at a slower tempo. Run it before changing a
number here.

A measured caveat worth knowing: the *motor* term is negative at lag 1 (about -0.4), but the *total* deviation's
lag-1 is whatever the slow wander and the 1/f short band make it - with a large `drift_ms` it can be positive. That is
realistic for tempo drift; it means "neighbouring notes are anti-correlated" describes the motor term, not the sum.

## 3c. Vibrato that wanders (`vibrato.model: "ou"`)

The default vibrato is one sine per note with a random rate, depth and phase. With `"model": "ou"` on a track's or an
instrument preset's `vibrato` block, rate and depth each follow a seeded Ornstein-Uhlenbeck track around their mean:
`rate_sigma` (0.06, a fraction of the rate), `depth_sigma` (0.15) and `tau_s` (0.35, how long a deviation lasts). The
phase is the running sum of the rate, so it never jumps. Each track starts at zero deviation: a note begins regular
and drifts as it is held. `delay_ms`, glides, `jitter_cents` and `shimmer` work as before. Chord and pad roles still
get no vibrato.

The noises of the instrument itself (bow, key, breath, damper at each onset and release) are `render.mechanics` in
the mix preset; a preset picks its class with `mechanics_class`.

## 3d. A section is several players (`ensemble`)

One track is one player. A sampled string or brass section is therefore one very good player multiplied, not a
room of them. A track can declare players:

```json
"ensemble": {"players": 4, "spread_cents": 5, "spread_ms": 10, "vel_spread": 3}
```

The renderer expands each written note into `players` copies before humanisation. Each player draws one fixed
offset for the whole piece (intonation, timing, level) and a small per-note jitter, so the section is stable and
not a chorus. Measured scatter in real small sections is 2-13 cents and 20-50 ms (ISMA 2019; Rasch), so these
are at the tight end on purpose: copies of one sample correlate more than independent players. Pitched section
parts only; a drum, effect or environment part raises, and a solo declares nothing. 2-8 players; above that the
answer is a multisampled section, not eight copies.

## 3e. Macro phrase breathing (`elastic`)

Per-note humanisation does not make a bar breathe. The score can ask for long-range elasticity and a collective
breath:

```json
"elastic": {"amount": 0.04, "corr_beats": 12, "breaths": [16, 48], "breath_s": 0.08}
```

`amount` is the peak deviation (about +/-4 %), centred so the average tempo is unchanged; `corr_beats` is how many
beats a deviation lasts (about two bars); each beat in `breaths` adds `breath_s` seconds for every player at once,
which is what a conductor's preparatory breath does. It sits on top of the per-phrase rubato and the final
ritardando. Keep it off a dance or trailer pulse: the pulse is the pulse. Ensemble tempo excursion measured 7-10 %
over a performance (ISPS), so 4 % is the inside of the expressive range, not the outside.

## 4. What humanization cannot fix

- Wrong notes, clashing voicings, notes outside the instrument's range, bad register balance. Fix the score.
- Sample quality: GM soundfonts are good, not concert-grade. The upgrade path is a bigger SoundFont or a user-provided instrument (see `natural-instruments.md`, `instrument-cloning.md`).
- Over-humanizing: sloppy timing on a pad is fine, sloppy kick/bass lock sounds like an amateur. Keep rhythm section tight (3-6 ms), melody and chords looser.

## 5. Manual hooks in a custom script

```python
import humanize as hz
tm = hz.TempoMap(72, total_beats=64, rubato=0.03, ritard=0.4, fermata=[(32, 1.2)])   # hold beat 32 for +1.2 s
events = hz.humanize_track(notes, tm, 'natural', role='melody', seed=3)             # seconds, MIDI velocity
print(hz.event_stats(events, tm))                                                   # timing/velocity spread
print(hz.humanize_metrics({'lead': events}, tm))                                    # the report's numbers
```
Note fields you can set by hand: `"art": "staccato"|"legato"`, `"v"` (0..1), `"d"` (beats). Role names: melody counter chord pad bass arp drum fx.
`humanize_track` also takes `mood=`, `swing='auto'`, `key=` and `chord_roots=` when a caller has them outside a score.

## 6. The six acoustic laws

Humanizing is not enough on its own: `scripts/pattern_audit.py` also checks the score's construction, because no
amount of timing jitter rescues a block chord on one sample, a choked plucked note, a flat machine-gun run or a dry
track in a wet hall. The six rules and their numbers are in `SKILL.md` ("Six acoustic laws") and
`custom-scripts.md` section 3a. One of them is about dynamics here: a track's velocity spread is judged against its
own mean (sd at least 5 %), so a quiet shaker and a loud snare are held to the same standard.


---

## Anticipation and bar breath (opt-in)

`anticipate_ms` leans an off-beat note that sits within 0.76 beat before the next bar line or the middle of the bar a few ms early (0.6-1.4 x the
value, drawn from the track's generator); `bar_breath_ms` lets the last note of a bar go early and delays the first note of the next bar by 35 % of it,
and the legato rule does not close that gap. Both default to 0 and draw nothing then, so an existing track plays exactly as before. Starting values:
anticipate 20-40 ms, breath 60-120 ms. Roles: figure roles, counter, arp, chord, ostinato.
