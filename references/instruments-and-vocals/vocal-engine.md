---
title: Vocal performance engine
summary: Every knob of the singing voice: formants, breathing, vibrato, expression, and the gate rows that judge it.
tags: [vocal, formant, vowel, breath, vibrato, choir, singer, expression]
load_when:
  - a piece has a sung or hummed part
  - a vocal gate row fails
---

# Vocal performance engine: how it works and how to configure it

Code: `scripts/vocals.py` (public facade) and `scripts/vocal_engine/`. Data: `references/data/vocal-engine-data/`.
Short version for a project: `references/instruments-and-vocals/vocals-and-choirs.md`. Everything here is synthesised from maths: no samples, no
recordings, no models, no network. Whether it sounds human has **not** been listened to (see section 11).

## 2. Files

| Part | File | Job |
|---|---|---|
| Facade | `scripts/vocals.py` | `render_choir`, `sing`, `add_vocal_harmonies`, `add_vocal_chorus`, `apply_vocal_dsp`, `selftest`, `demo`, `hum` |
| Config | `vocal_engine/config.py` | defaults, migration of old keys, range clamping, validation |
| Source | `vocal_engine/source.py` | glottal flow pulse (open quotient, speed quotient, closure), tilt, shimmer, aspiration, subharmonic, whistle |
| Tract | `vocal_engine/tract.py` | resonators with exact unity gain at the centre, moving formants, `harmonic_lock` |
| Hum | `vocal_engine/nasal.py` | nasal poles, anti-formant, oral coupling, lip-closure low-pass, nasal airflow, `nasalize` |
| Voice | `vocal_engine/voice.py` | f0 track to signal (no envelope, no normalisation) |
| Phrase | `vocal_engine/performance.py` | pitch curve, portamento, overshoot, vibrato, articulation, dynamics, phrase contours, micro-timing |
| Context | `vocal_engine/context.py` | tempo, phrase position, direction, register, energy, expression, role: the input to the phrasing choices |
| Breath | `vocal_engine/breath.py` | aspiration, exhaustion, inhale and release events |
| Expression | `vocal_engine/expression.py` | profiles from `references/data/vocal-engine-data/expression/*.json` |
| Singer | `vocal_engine/singer.py` | per-singer identity from `singer_variation` |
| Ensemble | `vocal_engine/ensemble.py` | independent singers, cohesion, stems, report, soft limiter |
| Data | `references/data/vocal-engine-data/{defaults,styles}.json`, `expression/*.json`, `vocal.schema.json` | every number |

## 3. Signal path

```
events -> split into monophonic lines (chords become lines) -> for each singer (own identity) -> for each line
  -> split into phrases (long gap, or hum<->vowel change)
  -> pitch curve (cents): note targets + portamento + anticipation + overshoot/settle + drift + jitter + arch + end sag + vibrato
  -> glottal source (continuous phase) -> tract (vowel) or nasal hum -> x calibration x level x phrase arc x flutter x gate x pressure
  -> + inhale / release (breath stem) -> pan -> sum -> DC block -> soft limiter -> (N,2) float32
```

- **Source.** Flow pulse rises (raised cosine) for the first part of the open phase, then closes. `closure` 0 = abrupt (more high
  harmonics, chest/pressed), 1 = smooth (fewer, falsetto/breathy). The radiated source is the flow derivative. Tilt is a
  one-pole low-pass that follows level (`dynamics.timbre_follow`: louder = brighter). Per-cycle shimmer, aspiration noise
  modulated by the flow, optional Kargyraa subharmonic and Sygyt whistle.
- **Tract.** Parallel two-pole resonators, each with gain exactly 1 at its centre (the old code's normalisation was
  evaluated at the wrong point). Formants can move inside a phrase (vowel changes blend over `performance.vowel_blend_ms`).
- **Loudness.** One calibration constant per timbre **and pitch** (`dynamics.pitch_compensation` 1 = a singer evens out the
  level between pitches; 0 = raw resonance). It is not a per-note normaliser: velocity, phrase arc and dynamics sit on top.
  Without it, a harmonic landing near a formant made some pitches 6 dB louder (found by the gate test, fixed).

## 4. Humming (the priority feature)

A note whose vowel is `m`, or any note when `hum: true`, goes through `nasal.hum_branch` instead of the vowel tract:

| Part | Config (`humming.*`) | Default |
|---|---|---|
| Nasal murmur poles | `nasal_poles` [{hz, bw, gain}] | 270 Hz (bw 70), 1000 (180, 0.25), 2200 (300, 0.10) |
| Oral anti-formant | `antiformant_hz`, `antiformant_bw`, `antiformant_depth` | 1000 Hz, 160, 0.85 |
| Oral cavity coupling | `oral_coupling`, `oral_formants`, `oral_bandwidths` | 0.25, 300/870/2240 |
| Lip closure low-pass | `lip_closure_hz` (moved by `brightness`) | 2400 Hz |
| Nasal brightness | `brightness` 0..1 (0.5 neutral) | 0.5 |
| Murmur level | `murmur_gain` | 1.0 |
| Nasal airflow | `airflow`, `airflow_hz` | 0.02, 900 Hz (2-pole low-pass, flow-modulated) |
| Hum register | `register` | `hum` (Oq 0.65, soft closure, tilt 2200 Hz) |
| Vibrato / breath when `hum` | `vibrato_cents`, `breathiness` | 18 cents, 0.01 |
| Nasality on open vowels | `nasality_vowels` 0..1 | 0 |

Tests check the spectrum: the hum is darker than "a", more than 90% of its energy is below 500 Hz, removing the anti-formant
puts back at least 4x the energy at 1 kHz, brightness moves the energy above 800 Hz at least 3x. These prove the structure
works as designed. They do not prove it sounds like a person humming.

## 5. Phrase performance (`performance.*`, `vibrato.*`, `articulation.*`)

- **Connected vs detached.** Notes closer than `connect_gap_s` (0.10 s) are joined: pitch glides over `portamento_ms`, starting
  `anticipation_ms` early, overshooting by a fraction (`overshoot_frac`, up to `overshoot_cents`) and settling over
  `settle_ms`. A note's `art` (`legato` | `non_legato` | `detached`/`staccato`) or `articulation.mode` chooses how.
- **Vibrato.** One continuous phase per phrase; depth develops after `delay_s` over `onset_s`; rate and depth wander
  (`rate_var`, `depth_var`); a join keeps `carry_floor` of the depth.
- **Intonation.** Slow drift, micro jitter, a small arch (sharper mid-phrase) and a sag at the phrase end. All scale with
  `pitch_stability` (a singer trait).
- **Articulation vs dynamics.** The gate (attack, release, dips at joins, phrase-end tail) and the level curve (velocity, arc,
  flutter) are separate. Legacy per-note keys still work: `attack`, `release` (seconds), `vib_*`, `breath`, `gl`, `c`
  (cents; it was divided by 100 twice before, now fixed), `formants`, `vowel`, `style`, `formant_scale`, `voices`.
- A note shorter than a ramp, overlapping notes, and extreme registers (E1 to E7) are handled and tested.

## 5b. Context-aware phrasing (`phrasing.*`)

A phrase is not one shape with one dynamic. `phrasing` makes the phrase respond to the music around it. Every term
is blended by `phrasing.amount` (0 = the previous phrase exactly, 1 = shipped defaults), so an old render can be
reproduced byte for byte with one key.

| Part | Key | Default | What it does |
|---|---|---|---|
| Blend | `amount` | 1.0 | 0 = static arc, no accents, no micro-timing, no articulation glide, time-locked inhales |
| Tempo | `tempo_bpm`, `beats_per_bar`, `tempo_reference_bpm` | 0, 4, 96 | `render_natural` fills tempo from the score's TempoMap; 0 = unknown (metric accents are skipped, never guessed) |
| Contours | `contours` | swell, fall, rise, hairpin, late_swell, settle | Named level shapes `[[position 0..1, level], ...]`, chosen by weight |
| Context choice | `expression_bias`, `role_profiles` | 10 expression profiles, 6 roles | Weight multipliers for the contour, and multipliers on `amount`, `depth`, `timing`, `vibrato` |
| Depth | `contour_depth` | 1.0 | Scales the contour *around its mean*, so the phrase's mean level never moves |
| Accents | `accent.*` | 1.6 dB, 240 ms | A short level bump on a group onset: bar line > beat > off-grid, plus 0.7 dB on long notes, plus 0.6 dB note-to-note variation; the curve's mean is removed |
| Micro-timing | `timing.*` | 8 ms sigma, 14 ms bend, 10 ms metric lag | Phrase bend (arrives, holds, closes), per-note jitter, strong beats slightly late, short notes a touch early; clamped to 45 % of the gap, first note anchored |
| Pitch | `pitch.*` | 3.5, 4, 0.7, 7 cents | Stress on accented notes, a lean with the melodic direction, arch scaled down, terminal fall on the last phrase only |
| Vibrato | `vibrato.*` | short 0.55, long 1.2, asymmetry 0.12 | Depth follows note length; delay and onset shorten on short notes; a second-harmonic term removes the clean-LFO timbre; rate scales with tempo |
| Articulation | `formants.*` | glide 0.05, settle 130 ms | Formants start toward the previous vowel (toward neutral on a phrase's first note) and settle; very long notes drift slightly |

Order of choices: defaults < expression profile < preset's explicit `phrasing` block. Later wins, as everywhere else
in `config.resolve`. Unknown contours, unknown profile keys and non-positive weights are reported by `config.check`
(so `presets.py validate` and the project gate see them); they are never silently replaced.

Measured A/B (`tests/vocal_expression_report.py`, 7-note line, same seeds, `amount` 0 vs 1):

| Metric | Before | After |
|---|---|---|
| Contour correlation, first vs last phrase | 1.000 | 0.080 |
| Micro-timing std / max | 0 / 0 ms | 12.3 / 35.1 ms |
| Accent depth | 0 dB | 2.26 dB |
| Vibrato on a 0.35 s note (peak-to-peak) | 2.3 cents | 11.6 cents |
| Vibrato on a 0.6 s note (peak-to-peak) | 9.5 cents | 19.1 cents |
| Formant movement at a note onset | 0 Hz | 16.5 Hz |
| Choir inhale spread (identical singer timing) | 0 ms | 16.3 ms |
| Pitch error vs the score (median inside a note) | 4.1 cents | 4.8 cents |
| Solo stem RMS | −27.46 dBFS | −27.79 dBFS |

## 6. Breathing (`breathing.*`)

**The breath is a continuous airflow, not an event.** `breath.bed()` builds one envelope for the whole line:
`inhale_floor_db` (-44) of air in every gap, an inhalation that fills `inhale_gap_frac` (0.45) of the gap and peaks
`inhale_lead_ms` before the next phrase, a `inhale_crossfade_ms` (60) tail that passes *under* the voice's attack,
and a release after each phrase that grows over 120 ms before decaying. The envelope is smoothed over 30 ms and never
reaches zero, so a gap is air rather than digital silence with a burst in it — the failure mode that reads as a
footstep, and the first version's measured gap profile was -240 dB (silence) for 2 s and then 0.28 s at -48 dB. Length
and level follow the gap (`inhale_min_s`/`inhale_max_s`, `inhale_peak_db`, -6 dB per doubling of the breath), because
singers shorten the inspiration as the phrase comes faster. Every singer shares that phase
(offset at most 12 ms), so a section breathes together instead of producing N unrelated events.

The noise itself is shaped air: `inhale_body_hz` (520) is the low chest part, the air band (`inhale_band_hz`) sits
above it held down by `inhale_tilt_db` (-11 dB) because real inhalation spectra fall with weak peaks below 3 kHz
and `turbulence_hz`/`turbulence_depth` (10.5 Hz, 0.4) flutter the level. Measured on the
inhale alone: the old flat band had a centroid of 2211 Hz with as much energy above 2 kHz as below; the shaped breath
sits at 719 Hz and puts the air band 17 dB down. A preset overrides any of those keys.

Three separate gains. **Aspiration** (inside the voiced signal): an aspirated onset (`aspirate_gain`, `aspirate_attack_ms`)
and a rise as the breath runs out. **Inhalation**: band noise (`inhale_band_hz`) of `inhale_ms`, ending `inhale_lead_ms`
before a phrase, only when the gap is at least `inhale_min_gap_s` and there is room (never before time 0). **Release**: an
exhale puff after the phrase. **Exhaustion**: past `capacity_s * exhaust_start` the pressure falls by up to
`pressure_drop_db` and breathiness rises to `exhaust_breath` times. Inhale and release go to the **breath stem**, about 20 dB
under the voice by default (`inhale_gain` 0.08 of `ref_rms`; it was 0.5 and louder than the voice, fixed after a measured step).

Breaths are **per singer**, not per ensemble. `plan_inhales_detailed` decides *whether* a phrase gets a breath;
the ensemble decides *when* (`inhale_timing_jitter_ms` 18), *how long* (`inhale_duration_var`) and *through which
end* (`inhale_character_var`: −1 nasal and slow, +1 mouth and quick). A phrase that lasted
`catch_breath_after_s` gets a quicker, brighter catch breath. A phrase with no room for an inhale gets an
`onset_puff` — the air that escapes before the first voiced note — and the release after a long phrase carries
`release_scale_by_phrase` more air than after a short one. With `phrasing.amount` 0 the plan is applied exactly
as before (one character, no jitter).

## 7. Expression (`expression`, `expression_intensity`)

`gentle reflective melancholic hopeful ethereal cinematic devotional powerful intimate mysterious` are JSON files in
`references/data/vocal-engine-data/expression/` (a project adds or overrides one with `<project>/presets/vocals/expression/<name>.json`, found
automatically once the project is added; or give an inline object). Each moves several sections: attack and release, vibrato depth/rate/delay, portamento, overshoot, phrase
arc, level scale, register, breathiness, breathing, scoop, tail. `expression_intensity` blends every number between the current
value (0) and the profile (1), and can exceed 1. **Order:** defaults, then the profile, then the preset's explicit values, so a
preset that says `attack: 0.5` keeps its attack under any profile. The profiles are design choices, not measurements.

## 8. Singers and the ensemble (`ensemble.*`, `singer_variation`)

Each singer gets a deterministic identity from `seed` and index, by perturbing `singer_variation` entries (formant scale,
breathiness, vibrato rate/depth/delay, tuning, pitch stability, portamento, hum brightness and anti-formant, attack, release,
level, timbre follow, breath capacity). Edit that table to change who the singers are. `diversity` 0 makes identical singers.
`ensemble.singers` is a list of explicit per-singer override objects (wraps around). **`cohesion`**: 1 = tight (no timing or
pitch spread, less identity variation), 0 = loose (up to `timing_spread_ms` and `pitch_spread_cents`). Typical: tight 0.9,
default 0.4, loose 0.1. Every singer renders every line (as before), so chords are sung by all.

## 9. Interface for the spatial engine (source only, nothing spatial is computed here)

`render_choir(..., return_stems=True)` returns `(mix, info)`:

- `info['stems']`: one dry mono `float32` array per singer (before pan and breath)
- `info['breath_stems']`: one breath-only array per singer
- `info['voices'][i]`: `index`, `pan`, `azimuth_deg`, `distance_m`, `detune_cents`, `timing_bias_ms`, `group`, `identity`
- `info['report']`: the numbers the quality gate reads (section 10)

`render_natural` currently takes the stereo mix only. To place singers individually, feed `info['stems'][i]` to
`spatial.spatialize_stem(audio, azimuth_deg, elevation_deg, distance_m, ...)` or register each singer as its own track. The
spatial routes that fold stereo to mono (`mixer.py`, for a preset with a `spatial` block) remove the width of the mix; the stems
avoid that.

## 10. Quality gate rows (`gate_profiles.py rows`)

`quality_gate.vocal_rows` reads `render_natural.REPORT[track]['vocal']` (copied from `vocals.LAST`) and the raw stem.

| Row | Checks | Default |
|---|---|---|
| `vocal.integrity` (protected) | finite, DC offset, limiter hit | DC at most 0.005 |
| `vocal.clicks` | single-sample jumps in the stem (`find_clicks`) | 0 |
| `vocal.breath` | longest phrase against breath capacity (the old "choir breath gaps not enforced") | factor 1.0 |
| `vocal.ensemble` | 3+ voices that are one voice copied (max stem correlation) | below 0.6 |
| `vocal.intonation` | pitch against the score, vibrato excluded | mean 60 cents |
| `vocal.dynamics` | note level follows velocity (no per-note normalisation) | correlation at least 0.5 |
| `vocal.hum_tone` | a hum stays dark | at most 2% above 1.5 kHz |
| `vocal.ring` | the singer's formant is an F3-F5 cluster (measured spread of the produced pole track) | at most 400 Hz |
| `vocal.formant_tuning` | level at f0 against the F1 band on notes whose f0 is above F1 | deficit at most 6 dB |
| `vocal.consonant` | consonant centroid inside its declared band, stop VOT inside tolerance | VOT ±30 %, centroid inside |
| `vocal.coarticulation` | the formant track moves toward the next vowel before the note boundary | at least 20 ms early |
| `vocal.perturbation` | local period jitter measured on the signal (not smooth flutter) | 0.3-2 % |
| `vocal.passaggio` | register parameters stay continuous across the break | step at most 0.01 |
| `vocal.vibrato` | amplitude modulation present and correlated with the f0 modulation | r at least 0.5, depth at least 0.2 dB |
| `vocal.identity` | two singers' tracts differ (length × pharynx scale) | at least 2 % |

Every number above is a starting value, measured on the engine's own output and never on the config that asked for it.

`project_gate` also checks vocal presets and a track's `vocal` block: unknown style, register, vowel or expression, numbers out of
range, and a placeholder `character`. Relaxing a row needs a reason, in a gate profile or the score's `gate` block; `vocal.integrity`
cannot be relaxed. A PASS means the measurable faults are absent, not that the voice is good.

`report` also carries the measured technique numbers (`ring_spread_hz`, `tuning_deficit_db`, `coart_lead_ms`, `jitter_pct`,
`passaggio_step`, `vib_am_db`, `vib_am_corr`, `consonants`, `identity_pct`) so the rows above judge the signal, not the preset.

`vib_am_db`/`vib_am_corr` are read from the realised glottal cycles, one note at a time, only where the vibrato is
developed and outside rests/creak, and only in the band around that note's own modulation peak; an ensemble reports the
phrase where the coupling is fully developed. They are never read off the `vibrato` config.

`report['phrasing']` (contours used, timing std/max, accent depth, inhale spread, tempo) is **informational**.
No gate row judges it: these numbers say what the phrase did, not whether it was good.

## 11. Limits (read before promising anything)

- **Not listened to.** All checks are objective. Realism, emotion and phrasing are unjudged. Run `listen.py` and use your ears.
- Numbers are literature-informed starting points, not from the knowledge base, not tuned by ear (`defaults.json` lists the sources).
- **Syllables, not words.** `consonants` adds the missing syllable layer (stops, fricatives, nasals, liquids, a trill), but
  there is no lexicon, no language and no text setting. A sung text still needs a recording or a speech model, which this
  skill forbids.
- The singer's formant, formant tuning, vowel cover, creak and the consonant recipes are literature-informed starting
  values (Klatt 1980, Sundberg 1975/1987, Peterson & Barney 1952, Ladefoged & Johnson). They are unmeasured as a *whole
  voice*; `listen.py` is the only judge of whether the result reads as a person.
- Anti-formants are approximated by one notch: a nasal consonant is a murmur with one null, not a full nasal tract model.
- A hum-to-vowel change inside one phrase starts a new phrase (no crossfade between the two models).
- A first phrase at time 0 has no room for an inhale.
- Styles are synthesis profiles, not claims of authentic reproduction of any tradition.
- Ensemble level follows velocity less tightly than a single voice (timing spread smears note windows).
- The contour set, weight multipliers and expression/role bias tables are design choices, not measurements. The
  A/B proves they change timing, level, vibrato extent, formant movement and breath timing; it does not prove they
  sound better.
- Metric accents need the score's tempo. A render that never passes tempo (a bare `vocals.render_choir` call) uses
  phrase structure only.
- The phrase's mean level is preserved by construction (±0.35 dB measured), but a contour that is loud early and
  quiet late can still read differently against a bed than the old symmetric arch.
- Pedalboard (`add_vocal_*`, `apply_vocal_dsp`) is imported on use and needs the skill venv.

## 12. Compatibility and migration

Old flat keys, the old nested preset keys (`formant_profile`, `articulation.attack_ms/vib_*/tremolo_*`) and the style identifiers
all still work (`config.resolve`). Differences a user can hear versus the old engine: no per-note peak normalisation; notes
connect instead of dropping out; `c` now works in cents; chorus default mix 0.25 (was 0.4); `qawwali_devotional` now gets its
saturation; `harmonic_lock`, `bandwidths` and style registers now act. The three shipped vocal presets were converted to the new
schema (they had no effect before). `tests/legacy_vocals.py` keeps the old code for A/B and benchmarks.
