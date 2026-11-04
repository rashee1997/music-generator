---
document_id: "TAMIL_CARNATIC_KUTHU_DSP_ONTOLOGY_V1"
target_consumers: ["AI_Music_Agents", "Python_DSP_Synthesizers", "Ethnomusicology_Engines"]
schema_version: "2026.10.1"
status: unverified
sources: []
---

> **Not verified.** These values are a starting point from practice, not a measurement.
> Cite a source before presenting one as established, and say "starting value" when a piece uses one.
# The Tamil Music Psychoacoustic & Algorithmic DSP Knowledge Base
**Target Application:** Pure-Code Audio Synthesis (Python / NumPy / SciPy), Algorithmic Composition, Humanization Matrices, and Cross-Cultural Fusion.

---

## Table of Contents (Machine-Parsable Index)
- [1.0 Core Psychoacoustics: How the "Tamil Ear" Listens vs. The "Western Ear"](#1-core-psychoacoustics-how-the-tamil-ear-listens-vs-the-western-ear)
- [2.0 Complete Taxonomy of Tamil Genres (Feel, Physics & DSP Rules)](#2-complete-taxonomy-of-tamil-genres-feel-physics--dsp-rules)
  - [2.1 Dappankoothu (Kuthu) & Gaana (Chennai Street Folk)](#21-dappankoothu-kuthu--gaana-chennai-street-folk)
  - [2.2 Carnatic Classical & Semi-Classical (Ragam-Tanam-Pallavi)](#22-carnatic-classical--semi-classical-ragam-tanam-pallavi)
  - [2.3 Gramiya Isai (Rural Village Folk / Oyilattam / Karagattam)](#23-gramiya-isai-rural-village-folk--oyilattam--karagattam)
  - [2.4 Tamil melodrama / pathos](#24-tamil-melodrama--pathos)
  - [2.5 Oppari (Ritual Lament / Dark Kuthu)](#25-oppari-ritual-lament--dark-kuthu)
- [3.0 Western & Global Fusion Blueprints (How to Blend Without Losing Tamil Identity)](#3-western--global-fusion-blueprints-how-to-blend-without-losing-tamil-identity)
  - [3.1 Arabic-Tamil Kuthu (The "Halamithi" / Middle-East Street Fusion)](#31-arabic-tamil-kuthu-the-halamithi--middle-east-street-fusion)
  - [3.2 Neo-classical / Baroque + Carnatic](#32-neo-classical--baroque--carnatic)
  - [3.3 Trap / Hip-Hop / Drill + Chennai Gaana (Santhosh Narayanan Style)](#33-trap--hip-hop--drill--chennai-gaana-paal-dabba--asal-kolaar--santhosh-narayanan-style)
  - [3.4 EDM / Mass-Kuthu / Synthwave (the film composer Blueprint)](#34-edm--mass-kuthu--synthwave-anirudh-ravichander-blueprint)
  - [3.5 Jazz / R&B / Lo-Fi + Carnatic (Pradeep Kumar Style)](#35-jazz--rb--lo-fi--carnatic-pradeep-kumar--sean-roldan--karthik-style)
- [4.0 Pure-Python Algorithmic Parameter Cheat Sheet](#4-pure-python-algorithmic-parameter-cheat-sheet)
  - [4.1 Scale Lookup Dictionary (Semitone Offsets from MIDI Root)](#41-scale-lookup-dictionary-semitone-offsets-from-midi-root)

---

## 1. Core Psychoacoustics: How the "Tamil Ear" Listens vs. The "Western Ear"

Before coding specific genres, an algorithm must understand the fundamental perceptual differences between Western and Tamil musical conditioning:

| Parameter | Western Ear Perception | Tamil / South Indian Ear Perception | Algorithmic / Python Implementation |
| :--- | :--- | :--- | :--- |
| **Pitch (Notes)** | **Discrete Steps:** A note is a static frequency ($f_0$) on a 12-TET grid. | **Continuous Curves (*Gamakas*):** A note exists in the *movement* between frequencies. Static notes sound "dead" or "toy-like." | Never trigger static frequencies on leads. Always apply pitch-envelopes (glides, oscillations, micro-bends) using spline interpolation. |
| **Harmony vs. Drone** | **Vertical (Chords):** Emotion comes from chord progressions (I–V–vi–IV). | **Horizontal (Raga against *Sruti*):** Emotion comes from how scale degrees rub against a constant root/fifth drone ($Sa - Pa$). | Keep a subtle, continuous harmonic drone ($f_0$ and $1.5 \times f_0$) at `-24dB` or anchor basslines heavily to the root and 5th rather than complex jazz voice-leading. |
| **Rhythm (Time)** | **Divisive & Metronomic:** 4/4 or 3/4 grid with backbeat accents (2 and 4). | **Additive & Cyclical (*Tala / Nadai*):** Grouped in pulses of 3 (*Tisra*), 4 (*Chatusra*), 5 (*Khanda*), or 7 (*Misra*), resolving on *Sam* (Beat 1). | Build rhythm generators using additive pulse arrays (e.g., `[3, 3, 2]` or `[3, 3, 3, 3]`) with heavy accent weights on index `0` and syncopated *Karvai* (rests/holds). |
| **Timbre Preference** | **Warm & Smooth:** Rounded sine/triangle leads, clean pianos, controlled mid-range. | **Nasal, Formant-Rich & Transient-Heavy:** High odd-harmonics (1kHz–3.5kHz) that mimic the human voice crying, celebrating, or calling out in an open street. | Use sawtooth/pulse waves passed through multi-peak Bandpass Formant Filters (`800Hz`, `1.8kHz`, `3.2kHz`) and asymmetric wave-shaping. |

---

## 2. Complete Taxonomy of Tamil Genres (Feel, Physics & DSP Rules)

### 2.1 Dappankoothu (Kuthu) & Gaana (Chennai Street Folk)
* **Cultural Origin:** Ancient Tamil *Parai* drum traditions + North Chennai working-class street poetry (*Gaana*), funerals (*oppari* celebration), and temple festivals (*Thiruvizha*).
* **How the Ear Listens:** The ear ignores delicate chord changes and locks onto **sub-bass chest impact (60–100Hz)** and **ear-splitting skin-slap transients (2.5kHz–5kHz)**. It listens for the "gallop."
* **Emotional Feel:** Primal, defiant, ecstatic, raw, communal, anti-elitist, kinetic (forces involuntary shoulder/foot movement).
* **Rhythmic DNA:**
  * **6/8 *Tisra Nadai* (135–160 BPM):** `1 - & - a - 2 - & - a` (`Dhum - ka - ta | Dhum - ka - ta`).
  * **Syncopated Kuthu Clave:** Accent on Beat `1`, the `and-of-2` (or subdivision 4 in a 6-grid), and a rapid roll on subdivision `5–6`.
* **Signature Timbres & Python Synthesis:**
  1. **Parai / Tappu (Frame Drum):** High-pitched calfskin hit with a bamboo stick (*Chindu*) and bass hand slap (*Adi*).
     * *DSP:* Combine a `280Hz` resonant membrane mode with a `3ms` white-noise burst filtered at `3.2kHz` for the stick crack.
  2. **Thavil (Barrel Drum):** Booming bass hand + metallic-sounding capped fingers (*Koodu*) on the treble side.
     * *DSP:* Sub-kick pitch-drop (`160Hz -> 62Hz` over `70ms`) + FM metallic transient (`fc=420Hz, fm=1120Hz`).
  3. **Urumi Melam (Friction/Hourglass Drum):** The signature weeping/howling pitch-sweep.
     * *DSP:* Sawtooth + filtered noise at `130Hz`, swept via sine-curve envelope `130Hz -> 290Hz -> 140Hz` over `450ms–600ms`.
  4. **Nadaswaram (Double-Reed Horn):** Piercing, nasal, celebratory horn.
     * *DSP:* Pulse wave (`duty=0.3`) + Formant filters at `950Hz` and `2400Hz` + `6.5Hz` pitch vibrato + `40ms` upward pitch-scoop on attack.

---

### 2.2 Carnatic Classical & Semi-Classical (*Ragam-Tanam-Pallavi*)
* **Cultural Origin:** Temple and royal court traditions of Tamil Nadu (*Thevaram*, Trinity of Carnatic Music).
* **How the Ear Listens:** Hyper-focused on **microtonal inflection (*Sruti*)** and **mathematical rhythmic resolution (*Korvai / Mora*)**. A single flat note breaks the illusion.
* **Emotional Feel:** Devotional (*Bhakti*), intellectually exhilarating, meditative, regal, deeply nostalgic.
* **Melodic DNA (Key Melakarta Scales in Semitones from Root `[0]`):**
  * **Mayamalavagowla** (Morning / Mystic / Folk crossover): `[0, 1, 4, 5, 7, 8, 11]` *(Double Harmonic Major)*
  * **Kalyani** (Auspicious / Grand / Euphoric): `[0, 2, 4, 6, 7, 9, 11]` *(Lydian)*
  * **Kharaharapriya** (Soulful / Grounded / Cinematic): `[0, 2, 3, 5, 7, 9, 10]` *(Dorian)*
  * **Shankarabharanam** (Bright / Heroic): `[0, 2, 4, 5, 7, 9, 11]` *(Major)*
  * **Charukesi** (Bittersweet / Romantic yearning): `[0, 2, 4, 5, 7, 8, 10]` *(Mixolydian b6)*
  * **Simhendramadhyamam** (Intense / Dramatic / Arabic-adjacent): `[0, 2, 3, 6, 7, 8, 11]` *(Hungarian Minor)*
* **Signature Timbres & Python Synthesis:**
  1. **Saraswati Veena:** Plucked string with heavy curved-fret deflection (*Kampita*) and brass-bridge buzz (*Jivari*).
     * *DSP:* Karplus-Strong string model + non-linear all-pass filter (simulating bridge grazing) + slow 3Hz pitch oscillation of $\pm 100$ cents.
  2. **Mridangam:** Tuned double-headed drum with a black iron-paste spot (*Soru/Karanai*) that produces harmonic overtones ($1 : 2 : 3 : 4$ instead of Bessel function disharmonics).
     * *DSP:* Sum of harmonic sine partials (`f0`, `2*f0`, `3*f0`) with independent exponential decay times (`Nam` = strong `2*f0`, `Chapu` = strong `3*f0`).

---

### 2.3 Gramiya Isai (Rural Village Folk / Oyilattam / Karagattam)
* **Cultural Origin:** Agrarian harvest songs, rain prayers, village deity (*Kula Deivam*) worship in Madurai, Theni, and Kongu regions.
* **How the Ear Listens:** Listens for **breath, wood, and open-air space**. It rejects overly compressed, synthetic EDM highs in favor of earthy mid-range warmth (`300Hz–1.5kHz`).
* **Emotional Feel:** Innocent, nostalgic, maternal, earthy, bittersweet, connected to soil and rain.
* **Rhythmic & Melodic DNA:**
  * Pentatonic scales: **Mohanam** `[0, 2, 4, 7, 9]` (Major Pentatonic) or **Suddha Saveri** `[0, 2, 5, 7, 9]` or **Madhyamavati** `[0, 2, 5, 7, 10]`.
  * Call-and-response phrasing between a solo voice/flute and a group chorus.
* **Signature Timbres:**
  * **Pullanguzhal (Bamboo Flute):** Breathy, warm, rich in 2nd-harmonic overblowing and slow finger slides.
  * **Udukkai & Pambai:** Talking-drum pitch bends + twin cylindrical drums (one brass, one wood).
  * **Salangai (Ankle Bells):** Clustered metallic jingles (`6kHz–12kHz`) slightly staggered by `5–15ms` per bell.

---

### 2.4 Tamil melodrama / pathos
* **Cultural origin:** the form the 1970s-1990s Tamil film song settled into.
* **How the Ear Listens:** Tracks **two independent melodies simultaneously** (e.g., a solo violin/flute playing a Carnatic Raga counter-melody against a Western Bach-style string quartet bassline).
* **Emotional Feel:** Heartbreak, longing (*Pirivu*), monsoon rain nostalgia, cinematic grandeur.
* **Algorithmic Rules:**
  * **Counterpoint fill:** During every rest in the main melody (`bar 2, beats 3–4`), trigger a fast 16th-note string/flute arpeggio run that bridges into the next chord.
  * **Bassline:** Melodic electric bass playing syncopated octave leaps (`Root -> 5th -> Octave`) rather than static roots.

---

### 2.5 Oppari (Ritual Lament / Dark Kuthu)
* **Cultural Origin:** Traditional funeral elegies sung by wailing performers, later transformed into cathartic dance tracks (e.g., *Santhosh Narayanan* style).
* **How the Ear Listens:** Sensitive to **falling pitch contours**, microtonal flat 3rds/6ths, and raw vocal-like tremors.
* **Emotional Feel:** Tragic yet liberating, dark, hypnotic, goosebump-inducing.
* **DSP Implementation:**
  * Use **Shubhapantuvarali** `[0, 1, 3, 6, 7, 8, 11]` (Todi / Gypsy Minor).
  * Apply a **downward pitch-droop** (`-40 cents`) at the end of every phrase along with amplitude tremolo (`8Hz`) to simulate crying/sobbing breath.

---

## 3. Western & Global Fusion Blueprints (How to Blend Without Losing Tamil Identity)

When fusing Tamil genres with Western/Global styles in code, **Rule #1** is: *Keep the micro-timing and melodic ornamentation Tamil, while letting the harmonic bed or frequency spectrum adopt the Western genre.*

### 3.1 Arabic-Tamil Kuthu (*The "Halamithi" / Middle-East Street Fusion*)
* **Why It Works:** Arabic **Maqam Hijaz** `[0, 1, 4, 5, 7, 8, 10]` and Tamil **Mayamalavagowla / Vakulabharanam** `[0, 1, 4, 5, 7, 8, 10/11]` share the exact same augmented-second interval (`1 -> 4` semitones, e.g., $Eb \rightarrow F\#$).
* **The Fusion Formula:**
  * **Intro:** Arabic **Oud / Qanun** plucked string + **Darbuka** (*Malfuf* `3 + 3 + 2` rhythm) + handclaps.
  * **Drop:** Transition from 4/4 Arabic *Malfuf* into **6/8 Tamil Dappankoothu** (*Parai + Thavil + Urumi*) while keeping an **Arabic Ney (breathy flute) or Mizmar** trading phrases with a **Tamil Nadaswaram**.
  * **Psychoacoustic Glue:** Layer Arabic **Riq (tambourine)** over Tamil **Salangai (ankle bells)** in the `8kHz–12kHz` band.

### 3.2 Neo-classical / Baroque + Carnatic
* **Why It Works:** Both Baroque music (Bach/Vivaldi) and Carnatic music are **contrapuntal and linear** rather than block-chordal.
* **The Fusion Formula:**
  * **Melody:** Pure Carnatic Raga (e.g., *Kalyani* or *Keeravani* `[0, 2, 3, 5, 7, 8, 11]`) with full *Gamaka* pitch-bends on Flute or Solo Violin.
  * **Harmony:** Western string section playing staccato 8th-note Triad inversions (`i - iv - V7 - i`) with a walking cello bassline.
  * **Critical Rule:** Never bend the Western chord strings—keep the chords 100% 12-TET quantized so the microtonal bends of the Tamil lead rub against the rigid grid for maximum emotional tension.

### 3.3 Trap / Hip-Hop / Drill + Chennai Gaana (*Paal Dabba / Asal Kolaar / Santhosh Narayanan Style*)
* **Why It Works:** UK Drill's **sliding 808s** and **triplet hi-hat flows** map directly onto the **Urumi drum pitch-slide** and **6/8 Gaana *Tisra* cadence**.
* **The Fusion Formula:**
  * **Low End (20Hz–120Hz):** Western distorted 808 sub-bass with **100ms portamento glides** mimicking the *Urumi Melam*.
  * **Mid-Range Percussion (200Hz–4kHz):** Replace the Trap snare on beat 3 with a **tight, high-tuned Parai slap** and syncopated **Thavil** ghost notes.
  * **Hi-Hats:** Replace standard 16th-note trap hi-hats with **6/8 triplet Salangai (bell) rolls**.

### 3.4 EDM / Mass-Kuthu / Synthwave (*the film composer Blueprint*)
* **Why It Works:** Modern Tamil "Mass" cinema themes rely on **stadium-sized EDM drops** fused with **traditional folk hooks**.
* **The Fusion Formula:**
  * **Lead Synth:** Layer a **SuperSaw / Brass synth** in octaves directly on top of a **Nadaswaram** sample/synth, both following the exact same pitch-bend automation curve.
  * **Rhythm:** Four-on-the-floor EDM kick (`128 BPM` or `140 BPM`) locked underneath a **double-time 6/8 Kuthu percussion loop** (creating a `4:3` polyrhythm).
  * **Pre-Drop Fakeout:** Cut all bass for 1 bar (`bar 8`), play a solo **Urumi sweep + Street Whistle**, then drop the sub-bass + brass hook on Beat 1.

### 3.5 Jazz / R&B / Lo-Fi + Carnatic (*Pradeep Kumar / Sean Roldan / Karthik Style*)
* **Why It Works:** Carnatic Ragas like **Kharaharapriya** (Dorian) and **Harikambhoji** (Mixolydian) naturally contain the `b3`, `b7`, and `9th` extensions used in Neo-Soul and Jazz.
* **The Fusion Formula:**
  * **Chords:** Fender Rhodes electric piano playing **Min9, Maj7#11, and Sus13** voicings with a gentle tremolo.
  * **Drums:** Laid-back boom-bap kick/snare (snare delayed by `+12ms` for drunken Dilla swing) layered with a soft **Kanjira** (South Indian lizard-skin frame drum with a pitch-drop when pressed).

---

## 4. Pure-Python Algorithmic Parameter Cheat Sheet

Use these exact mathematical constants and functions in your Python synthesis scripts (`NumPy` / `SciPy`) to dial in authentic Tamil feel:

### 4.1 Scale Lookup Dictionary (Semitone Offsets from MIDI Root)
```python
TAMIL_RAGAS = {
    "mayamalavagowla_kuthu": [0, 1, 4, 5, 7, 8, 11],     # Classic Kuthu / Temple / Mystic
    "vakulabharanam_arabic": [0, 1, 4, 5, 7, 8, 10],     # Arabic Hijaz + Tamil Fusion
    "simhendramadhyamam":    [0, 2, 3, 6, 7, 8, 11],     # Intense Mass Hero / Dark Arabic
    "shubhapantuvarali":     [0, 1, 3, 6, 7, 8, 11],     # Oppari / Pathos / Raw Emotion
    "keeravani_cinematic":   [0, 2, 3, 5, 7, 8, 11],     # Melodramatic minor
    "kharaharapriya_soul":   [0, 2, 3, 5, 7, 9, 10],     # Gaana / Folk-Soul / Dorian
    "mohanam_gramiya":       [0, 2, 4, 7, 9],            # Village Folk / Flute / Uplifting
    "kalyani_grand":         [0, 2, 4, 6, 7, 9, 11],     # Euphoric / Wedding / Festival
}

4.2 The Gamaka (Microtonal Pitch-Curve) Generator

Instead of generating a constant frequency array f = np.full(N, f_target), wrap
lead notes in one of three Tamil articulation envelopes:

1.  The Eduppu Scoop (Attack Slide): Start at f_target * (2 ** (-45 / 1200))
    (-45 cents) and reach f_target at t = 0.045s using 1 - np.exp(-t / 0.015).
2.  The Kampita Oscillation (Carnatic Shake): On scale degrees 1, 3, 6, or 11,
    modulate frequency between the current note and the next scale degree up at
    5.5 Hz to 7.0 Hz.
3.  The Oppari Release Droop: Over the final 60ms of a held note, drop pitch
    exponentially by -35 cents.

4.3 The Kuthu 12-Step (6/8 Tisra) Probability & Velocity Matrix

For a 12-subdivision bar (index 0 to 11, representing two groups of 6 sixteenths
in 6/8 time):

KUTHU_GRID_12 = {
    # Index:       0     1     2     3     4     5     6     7     8     9    10    11
    "thavil_bass":[1.0,  0.0,  0.0,  0.75, 0.0,  0.0,  0.85, 0.0,  0.4,  0.0,  0.0,  0.0],
    "parai_slap": [0.0,  0.0,  0.8,  0.0,  0.9,  0.4,  0.0,  0.0,  0.85, 0.0,  0.95, 0.7],
    "salangai":   [0.9,  0.4,  0.6,  0.8,  0.4,  0.6,  0.9,  0.4,  0.6,  0.8,  0.5,  0.7],
    "micro_shift":[0.0, +4.0, -3.0,  0.0, +5.0, -2.0,  0.0, +4.0, -3.0,  0.0, +3.0, -4.0] # in milliseconds
}

  - Notice the micro_shift array: In authentic Tamil Kuthu, subdivisions 1 and 4
    are pushed slightly late (+4ms), while subdivision 2 snaps slightly early
    (-3ms), creating the signature forward-leaning street groove.

4.4 Spatial & Ambient Street Engine ("Thiruvizha" Psychoacoustics)

To make pure code sound like a live Tamil festival rather than a sterile synth:

  - Frequency Masking Rule: Carve a -4dB dip at 1.2kHz–2.5kHz in all chord/pad
    instruments so the Nadaswaram / Ney / Parai stick crack owns the human ear's
    most sensitive Fletcher-Munson region (2kHz–4kHz).
  - Procedural Crowd/Street Bed: Generate pink noise (-32dB), pass through a
    slowly wandering bandpass filter (400Hz–1200Hz), and inject randomized
    high-Q sine chirps (2800Hz -> 3400Hz -> 2900Hz over 180ms) on bar
    transitions to simulate Kuthu finger-whistles (Visil).
