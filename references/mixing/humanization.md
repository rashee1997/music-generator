# Humanization: why machines sound robotic and what to change

A score where every note starts exactly on the grid, with the same loudness and the same length, sounds
mechanical even with real recorded samples. Human performances deviate in **structured** ways. `scripts/humanize.py`
applies the following automatically (preset `natural` by default). Use this page to tune it or to hand-write
nuance in custom scripts.

## 1. The deviations that matter (with numbers)

| Aspect | What real players do | What humanize.py does |
|---|---|---|
| Melody vs accompaniment | The melody voice sounds ~10-30 ms **before** the other voices and is played louder ("melody lead", Goebl 2001; the velocity advantage is the cause, not a choice) | melody offset = -lead_ms (20 ms natural), melody velocity +8, chords -6, pads -10 |
| Timing error | Not white noise. A slow drift (1/f-like) plus note-to-note errors that are **anti-correlated** (a late note is followed by an early one). Drummers: inter-beat-interval SD roughly 9-15 ms in good playing | per-note error `e[i] - 0.5 e[i-1]` (sigma 7 ms) + smooth drift (9 ms) |
| Tempo | Breathes: slight speed-up into the middle of a phrase, slowing at the end, big final ritardando | `TempoMap`: phrase arch (+-2.5 %), slow wander (0.6 %), final ritardando (35 %, last 6 beats) |
| Dynamics | Downbeats stronger; phrases swell to a peak and relax; higher notes slightly louder in a rising line; last note of a phrase softer | metric accent, phrase arch (+-3.5), pitch-contour term, phrase-end relax |
| Chords | Never struck at one instant: guitar strum 20-80 ms, piano roll 5-20 ms, harp roll 20-40 ms | strum spread 10 ms (up/down alternating) |
| Articulation | Legato notes overlap the next one by tens of ms; staccato = ~50 % length; every note length varies a few % | overlap 35 ms on legato roles, +-4 % duration jitter, `"art":"staccato"` honoured |
| Vibrato (voice, strings, winds) | 5-6.5 Hz, ~20-50 cents peak-to-peak range for strings, starts after ~200-300 ms and grows, differs on every note | per-note pitch-bend LFO, delayed onset, random rate/depth/phase |
| Note shape | A bowed/blown note is not a flat rectangle: it blooms, then fades | per-note CC11 expression curves (`bow`, `breath`) |
| Pedal / sustain | Piano: pedal changes with each harmony, lifted just before the new chord | `auto_pedal`: lift 40 ms before each chord change |
| Drums | Kick tight/early, snare a touch late, hats loose; ghost notes (very soft) between backbeats; a fill every 4-8 bars; the same hit is never twice identical | piece-specific push (kick -3 ms, snare +5 ms), velocity jitter, `drum_bar` ghost notes + fills |
| Swing | Off-beat 8ths late: 0.5 = straight, ~0.58 light, ~0.66 triplet feel, jazz tempo-dependent | `score["swing"]` |
| Tuning | Not exactly equal-tempered every note; ensembles are a few cents apart | random +-3 cents per note on per-note channels, `detune_cents` per track |

KTH performance rules (Friberg, Bresin & Sundberg) add more expressive rules - "high loud", "phrase arch",
"final ritard", "duration contrast", "punctuation" (tiny gap after a phrase), "leap articulation".
The humanizer implements the first three plus the legato/phrase-end behaviour. You can add the rest by hand
in custom scripts (shorten notes before big leaps, add 30-80 ms gaps at phrase ends).

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

**The drift is shared, not per track.** `tempo_map_for()` attaches one `shared_drift` curve to the tempo map, and every
track of the piece reads it. Before this each track drew its own drift, so two players of one section wandered apart by
tens of milliseconds. `humanize_track(..., drift=(beats, values))` overrides it by hand.

**Articulation is an instrument property.** `humanize_track(..., articulation={'overlap_ms': 30, 'gate': 1.0})`, set by
the instrument preset, replaces the role's fixed 35 ms overlap (a bowed line overlaps more than a plucked one).

**Velocity and duration move together**: a score that writes one flat velocity still gets level variation, but it is no
longer level alone.

## 2. Presets (in `humanize.PRESETS`)

| Preset | timing_ms | lead_ms | drift_ms | vel_sigma | rubato | Feel |
|---|---|---|---|---|---|---|
| tight | 3 | 8 | 3 | 3 | 0 | pop/electronic, near the grid but not dead |
| natural | 7 | 20 | 9 | 5 | 2.5 % | default: a good studio player |
| loose | 12 | 25 | 15 | 7 | 4 % | folk, jazz, lo-fi, live band |
| rubato | 9 | 28 | 12 | 6 | 7 % | solo piano, film ballads, ambient |

Pass a dict to override any key: `"humanize": {"timing_ms": 5, "lead_ms": 30, "strum_ms": 18}`.
Per-track: `"humanize": "loose"` inside a track overrides the score setting.

## 3. Instrument-specific advice

- **Piano**: let the pedal ring through a chord, lift at changes; melody 8-10 velocity above the accompaniment; roll big chords.
- **Strings (bowed)**: one channel per note (automatic); `expression: "bow"`; vibrato on long notes only; keep ensemble pads long and legato; avoid repeated identical bow starts.
- **Winds/brass**: `expression: "breath"`; leave 1/4-1/2 beat rests where a player must breathe (phrase ends); no playing above the comfortable range (see `natural-instruments.md`).
- **Guitar**: strum with `strum_ms` 15-25; alternate down/up; palm-muted low strings; avoid chords above the 12th fret region.
- **Bass**: slightly behind or exactly on the kick; notes 85-95 % long, not wall-to-wall; octave jumps sparingly.
- **Drums**: lower hat velocity on off-beats, accent backbeats, ghost snares at 20-40 velocity, a different fill each time, crash only at section starts. The kit has 3-4 snare/kick variants: alternate them (`snare`/`snare2`, `kick`/`kick2`) for round-robin feel.
- **Voice / choir pads**: slow attacks (CC11 curve), no hard repeated notes, long legato with vibrato 5 Hz.

## 3b. Checking the model, not trusting it

`tests/test_humanize_stats.py` asserts the claims instead of the code: two tracks of a piece share one drift; the motor
term is negative at lag 1; louder notes are longer; a major third sits about 14 cents flat under `just_ratio: 1`; an
instrument articulation overrides the role overlap; the drum push grows at a slower tempo. Run it before changing a
number here.

A measured caveat worth knowing: with the default drift and motor amplitudes, the *total* deviation's lag-1 is positive
(~+0.6) because the slow wander dominates. That is realistic for tempo drift, but it means the module's old claim that
neighbouring notes are anti-correlated describes the motor term, not the sum.

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
```
Note fields you can set by hand: `"art": "staccato"|"legato"`, `"v"` (0..1), `"d"` (beats). Role names: melody counter chord pad bass arp drum fx.

## 6. The six acoustic laws

Humanizing is not enough on its own: `scripts/pattern_audit.py` also checks the score's construction, because no
amount of timing jitter rescues a block chord on one sample, a choked plucked note, a flat machine-gun run or a dry
track in a wet hall. The six rules and their numbers are in `SKILL.md` ("Six acoustic laws") and
`custom-scripts.md` section 3a. One of them is about dynamics here: a track's velocity spread is judged against its
own mean (sd at least 5 %), so a quiet shaker and a loud snare are held to the same standard.

Sources: Goebl (2001) melody lead in piano performance; Friberg/Bresin/Sundberg KTH rule system; microtiming
studies (drummer IBI, 1/f drift, anti-correlation); vibrato studies (5-6 Hz, 50-84 cents in singing); piano
pedaling practice.

---

## How to create / use

Tune or write it:
1. Whole piece: `"humanize": "natural"` (tight | natural | loose | rubato | a dict, see `humanize.PRESETS`) in the score; per track: `"humanize": {...}` or a preset's `humanize` block.
2. Phrase breath and arch come from `humanize.py` automatically; per-track `swing`, `detune_cents`, `strum` override.
3. Check: `python scripts/pattern_audit.py scores/<title>_score.json` (flat dynamics, machine-gun hits) and the `witek_groove_curve` / `groove_pocket_lock` rows in the pipeline.
