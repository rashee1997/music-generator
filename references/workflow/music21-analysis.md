# Dynamic Music Analysis with music21

`music21` is an expansive, object-oriented toolkit for computational musicology, music theory, and symbolic musical intelligence developed at MIT. It is not a static validator or rigid rule-checker; it is a full musical computing environment.

## 1. Core Rule: Dynamic, Custom Analysis Per Composition

> **POLICY** (the pipeline always runs the default template; a piece-specific script is recommended, not required): 
> Never use a predefined, rigid, or generic one-size-fits-all analysis script. 
> Every composition must have an **authored, dynamic analysis script customized specifically for that piece's musical universe, cultural lineage, instrumentation, and emotional purpose.**

When analyzing a piece with `music21`, first inspect the piece's specific targets:
* What is its emotional purpose (e.g. Epic Adventure vs Reflective Solitude)?
* What is its tuning and modal system (e.g. D Major Pentatonic, Mixolydian, Maqam Hijaz, Raga Bhairav)?
* What is its rhythmic engine (e.g. 12/8 Mandé Soli polyrhythmic cross-rhythm, 4/4 syncopated stride, 7/8 Balkan dance)?
* What are the interacting voices (e.g. Fula flute call answering Balafon, Kora polyphonic arpeggios, Dunun/Tama percussion dialogues)?

Then dynamically author the piece's custom analysis script to interrogate those specific dimensions using the appropriate `music21` modules.

---

## 2. The Vast Analytical Arsenal of music21

### A. Tonality, Modality & Modal Affect
* `score.analyze('key')`: Krumhansl-Schmuckler, Temperley-Kostka-Payne (`key.temperley`), and folk-weighted tonal determination.
* `analysis.windowed.WindowedAnalysis`: Evaluates how tonal center and key confidence move across bars, detecting unwanted modal drift or flagging modulation points.
* `scale.MajorScale`, `scale.DorianScale`, `scale.WeightedHexatonicScale`: Concrete scale membership verification and non-scale accidental isolation.
* Pitch Class Vectors (`n.pitch.pitchClass`): Quantitative modal distribution. E.g., discovering whether a cue has collapsed into sorrowful minor thirds (F natural) or lifted into triumphant major thirds (F#) and expansive major sixths (B).

### B. Vertical Harmony, Chords & Harmonic Rhythm
* `score.chordify()`: Flattens multi-track polyphony into time-aligned vertical chords.
* `c.quality`, `c.commonName`: Detects major, minor, augmented, diminished, half-diminished, suspended, and open fifth sonorities.
* `roman.romanNumeralFromChord(c, key)`: Formal functional harmonic analysis (Tonic, Subdominant, Dominant, secondary dominants, modal interchanges).
* Harmonic Rhythm: Rate of chord change per bar, ensuring harmonic momentum supports the dynamic arc.

### C. Melodic Contour, Intervals & Affective Semiotics
* `interval.Interval(noteA, noteB)`: Exact semitone, directed interval, and generic interval between successive melodic notes.
* Directional Vector: Percentage of rising intervals vs falling intervals.
  * *Heroic/Adventurous:* Dominated by rising 4ths, 5ths, and octaves with bright major leaps.
  * *Melancholic/Reflective:* Dominated by descending minor thirds, falling scalar sighs, and low-tessitura step motion.
* Melodic Ambitus (`part.flatten().pitches`): Range from lowest to highest pitch per instrument, confirming natural performance boundaries.
* Melodic Contour Classification: Arch, inverted arch, ascending ramp, undulating wave.

### D. Meter, Rhythm & Polyrhythmic Cross-Pulses
* `analysis.metrical`: Computes hierarchical metrical weights across measures.
* Metric Syncopation (`analysis.discrete.Syncopation`): Quantitative syncopation index.
* Compound & Cross-Rhythm Analysis:
  * Distinguishes 12/8 compound warrior cadences (e.g. Mandé *Soli*) from flat 4/4 grid drumming.
  * Analyzes hemiolas (3 against 2) and triplet cross-rhythms between polyphonic layers.

### E. Voice Leading & Counterpoint
* `m21.voiceLeading.VoiceLeadingQuartet`: Analyzes motion between any two voices across consecutive verticalities (parallel, similar, contrary, oblique motion).
* Voice Crossing & Register Separation: Validates that lead instruments (e.g. Fula flute, Balafon) never collide with or cross into low-end accompaniment foundations.

### F. Symbolic Feature Extraction
* `music21.features.native` & `music21.features.jSymbolic`:
  * Melodic pitch variety and entropy
  * Duration entropy and rhythmic variety
  * Vertical interval prevalence
  * Rhythmic transition matrices

---

## 3. How to Author the Custom Analysis Script

Whenever a composition is created or revised:
1. Export the composition to MIDI (`.mid`).
2. Write a customized analysis script: `analyze_<piece_name>.py` tailored specifically to that composition.
3. Import `music21 as m21` and load the score with `m21.converter.parse(midi_path)`.
4. Run targeted interrogations matching the creative brief:
   * **Tonality check:** Confirm the mode (e.g. D Major/Mixolydian) matches the intended emotional affect (adventure, wonder, heroism).
   * **Harmonic quality breakdown:** Ensure major/triumphant sonorities dominate when uplifting/adventurous feel is requested.
   * **Melodic contour vector:** Measure the rising vs falling transition ratio of the lead voice.
   * **Ambitus & Voice Leading:** Verify natural acoustic ranges and clean register separation.
   * **Rhythmic drive & metric weight:** Validate syncopation and groove consistency.
5. Print an intelligible, empirical report and use the findings to drive exact musical revisions.

---

## How to create / use

Stage 6 runs a music21 analysis for every project. Default: `templates/analyze_music21_template.py` (key, bass register, voice separation, contour, harmonic rhythm).
To tailor it to the piece (recommended when the culture or mode is unusual):
1. `cp templates/analyze_music21_template.py <project>/scripts/analyze_music21.py`.
2. Keep `analyze(score, out_wav=None, out_midi=None, reports_dir=None)` returning rows `(level, name, detail)` with level PASS | WARN | FAIL.
3. A crash in your script is reported as a FAIL row (never silently skipped). Run `pipeline.py ... --project <project>` and read the `music21_*` rows.
(The policy line above about a mandatory custom script is relaxed: the default template always runs; a custom one is optional.)
