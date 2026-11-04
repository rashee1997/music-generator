# Hums and choirs in code: how they are made, and how they blend with music

Used by `scripts/vocals.py` and the `scripts/vocal_engine/` package. Full technical reference, every setting, and the limits:
**`references/instruments-and-vocals/vocal-engine.md`**. This file is the working guide for a project.

A score routes to the engine by the instrument names `choir_formant`, `hum_formant`, `voice_formant`, `throat_formant` and
`chant_formant` (built in, no preset needed), or by the name of a `presets/vocals/<name>.json` preset (`render_natural.py`,
before the SoundFont lookup). A track can carry `voices`, `vowel` (a e i o u m), `formant_scale`, `style`, `expression`, and its
own `vocal` block (any key or section of the vocal config). Notes take `c` (cents off 12-TET), `gl` (glide-in cents), `art`
(`legato` | `non_legato` | `detached`), and optionally `vowel`, `style`, `formants`, `voices`.

## 1. What makes a synthetic voice sound like a voice

- **Source-filter model.** A voice is a source (the vocal folds, a periodic pulse train with a falling spectrum) shaped
  by the vocal tract, which adds resonances called formants. The ear identifies vowels from the formants, and the
  pitch from the source. CCRMA's vocal-model comparison: FM voices are cheap but hard to make convincing; formant
  synthesis is the practical choice. Aalto's thesis: three formants give intelligible speech, five give high quality;
  each formant is a two-pole resonator; cascade and parallel layouts are both used.
- **Klatt-style formant synthesis** is the reference design (Praat's KlattGrid implements it). Singing uses the same tract
  with the pitch of the note. The engine's source is a parametric glottal flow pulse (Rosenberg / LF family); values are
  literature-informed starting points listed in `references/data/vocal-engine-data/defaults.json`, not read from the knowledge base.
- **Human imperfection.** A sung note is never a steady tone: pitch jitter (a few cents, slow), amplitude shimmer
  (a few percent), vibrato that starts late and widens, breath at the onset, a glide into the note. The engine now builds these
  across a whole phrase, with one continuous pitch curve, so notes connect instead of restarting.
- **A real choir is many people.** Several singers slightly out of tune with each other, different vibrato phases and
  breathing, spread across the stereo field. Each singer here has their own identity (formant scale, vibrato, tuning, pitch
  stability, breath capacity, attack and release) derived from the seed, their own timing and their own pitch curve.
- **Mix treatment** (production sources): high-pass a choir at 100-150 Hz, cut 200-400 Hz mud, glue the stacked voices
  with light compression. A choir stem goes through the same mixer as any other.

## 2. Vowel formants used

Adult averages in the Peterson and Barney style; check them against a published table before a scientific claim. They live in `references/data/vocal-engine-data/defaults.json` (`tract.vowels`):

| Vowel | F1 Hz | F2 Hz | F3 Hz | Use |
|---|---|---|---|---|
| a | 730 | 1090 | 2440 | open choir "aah" |
| e | 530 | 1840 | 2480 | |
| i | 270 | 2290 | 3010 | bright, high F2 (the "singer's" brightness sits near 2-3 kHz) |
| o | 570 | 840 | 2410 | |
| u | 300 | 870 | 2240 | dark |
| m | 250 | 1000 | 2100 | selects the **hum model** (closed mouth, nasal), not three ordinary resonators |

Bandwidths 90, 110 and 150 Hz; each resonator has exactly unit gain at its own formant. The self-test checks the ordering: "i"
has at least 1.5 times the energy above 1.5 kHz of "u", and the hum is darker than "a".

## 3. Blending voices with a music bed

- A hum is a pad, not a melody: long notes, low velocity, `vowel: m` or `hum: true`, one octave below the chord tones.
- A choir in the chorus should lift an octave (or add a fifth above) to be heard over the band. Keep it out of the
  bass register: the cello and the choir fight below about 250 Hz.
- Vowel changes by phrase (a on the long notes, e or i on the short ones) make the words feel sung rather than held. A change
  between a hum and a vowel starts a new phrase (no crossfade between the two models).
- **Breath gaps.** Singers take a breath in rests of 0.3 s or more (an inhale in the breath stem). A phrase longer than the
  singers' breath capacity (`breathing.capacity_s`, default 7 s) raises the gate's `vocal.breath` WARN: add a rest or raise the
  capacity. A phrase starting at time 0 has no room for an inhale.- Words are not synthesised. A choir here sings vowels and hums only. Real lyrics need a sung recording or a speech model, which is outside this skill.

## 3b. Phrase performance (the `phrasing` block)

A phrase is not one shape and one dynamic. The engine shapes each phrase from the music around it: the score's tempo
(metric accents), where the phrase sits in the line (a first phrase opens, a last phrase closes), its melodic
direction, the register, the expression profile and the track's `role` in the arrangement (a pad emotes less than a
lead). What it adds, all scaled by `phrasing.amount`:

- **A chosen contour** (swell, fall, rise, hairpin, late swell, settle) instead of one arc on every phrase, with a
  short level accent on group onsets and a little note-to-note variation. The contour is rescaled so the phrase's
  mean level does not move: the stem stays where it sat in the mix.
- **Micro-timing**: a gentle bend inside the phrase, strong beats a hair late, short notes a touch early, small
  jitter, and a clamp at 45 % of the gap so notes never reorder. The phrase still starts where the score says.
- **Pitch life**: stress on accented notes, a lean that follows the melodic direction, and a terminal fall on the
  last phrase only.
- **Note-length-aware vibrato**: less on short notes (and an earlier onset, so a 0.35 s note is not plain), more on
  long ones, with a slight asymmetry that keeps it from sounding like a clean LFO. Rate follows tempo.
- **Formant articulation**: the vowel starts a little toward the previous one (toward neutral on a phrase's first
  note) and settles; a very long held note drifts slightly instead of freezing the filter.
- **Breaths per singer**: each singer places their own inhale (±18 ms), with their own length and nasal/mouth
  character; a catch breath after a long phrase; air before an unaccompanied first note; a bigger release after a
  long phrase.

Use it in a preset (every key is optional, defaults in `references/data/vocal-engine-data/defaults.json`):

```json
{"character": "...", "phrasing": {"amount": 1.0, "role": "melody",
  "expression": "melancholic", "accent": {"gain_db": 1.8}, "timing": {"sigma_ms": 10.0}}}
```

The expression comes from the preset's top-level `expression`; `role` is filled from the score track's `role` when
`render_natural` renders it. `phrasing.amount: 0` is exactly the previous phrase behaviour (one arc, no accents, no
micro-timing, no articulation glide, time-locked inhales) and is the switch to use for a byte-faithful old render.

## 4. What was checked, and what was not

- Checked (objective, phrase performance): contour correlation between phrases, micro-timing distribution and ordering, accent depth, vibrato extent by note length, formant movement at an onset, per-singer inhale spread, pitch error against the score, stem level. `tests/vocal_expression_report.py` prints them and writes `tests/artifacts/vocals/expr/` (WAVs, `REPORT.md`, `measurements.json`).
- Checked (objective): spectral shape of the vowels and the hum; resonator gain and stability at 22.05, 44.1, 48 and 96 kHz;
  pitch reaches its targets, connected notes glide, vibrato develops and keeps its phase across notes; no clicks at joins; level
  follows velocity and does not depend on the pitch; 1, 2, 5 and 16 voices; reproducible by seed; singers are not copies of
  one another; the old selftest. The gate's `vocal.*` rows run these measurements on a real render.
- Not checked: **how it sounds.** No listening test has been run (`listen.py` has not run on a vocal render). The gate cannot
  judge whether a voice is convincing, warm or moving. Say so when delivering.

## 5. Pedalboard harmonies, chorus and polish (`add_vocal_harmonies`, `add_vocal_chorus`, `apply_vocal_dsp`)

All three read their numbers from the `dsp` section (`references/data/vocal-engine-data/defaults.json`), imported on use:
- **Harmonies:** `pb.PitchShift` copies at `dsp.harmonies.semitones` (default -12 and +7), mix 0.35.
- **Chorus:** `pb.Chorus` rate 1 Hz, depth 0.25, **mix 0.25** (was 0.4: less smear, so single voices stay recognisable).
- **Polish:** high-pass 80 Hz, +1.8 dB presence at 3.2 kHz, +1.5 dB air at 10 kHz, 2.2:1 compression, and saturation from
  `dsp.saturation_db` or the style (`qawwali_devotional` has 1.5 dB; the old names `qawwali_sufi`, `arabic_desert_vocal` and
  `bulgarian_chant` still do). `dsp.intensity` 0..1 scales every gain and ratio. Output is DC-blocked, finite and soft-limited.
- Mono input still returns `(N, 2)` (as before); pass `keep_shape=True` for the input's shape.

---
