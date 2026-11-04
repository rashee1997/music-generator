---
document_id: "PAN_ARAB_MAQAM_IQAAT_DSP_ONTOLOGY_V1"
target_consumers: ["AI_Music_Agents", "Python_DSP_Synthesizers", "Microtonal_Engines"]
schema_version: "2026.10.1"
---

# The Pan-Arab Music Psychoacoustic & Algorithmic DSP Knowledge Base
**Target Application:** Pure-Code Audio Synthesis (Python / NumPy / SciPy), Microtonal *Maqam* Modeling, Regional *Iqa'at* (Rhythmic Cycles), and Global/Indian/Western Fusions.

---

## Table of Contents (Machine-Parsable Index)
- [1.0 Core Psychoacoustics: How the "Arab Ear" Listens (Tarab & Saltanah)](#1-core-psychoacoustics-how-the-arab-ear-listens-tarab--saltanah)
- [2.0 The Mathematical Architecture of Maqamat (Scales & Quarter-Tones)](#2-the-mathematical-architecture-of-maqamat-scales--quarter-tones)
- [3.0 Complete Regional Breakdown: The 6 Musical Worlds of the Arab World](#3-complete-regional-breakdown-the-6-musical-worlds-of-the-arab-world)
  - [3.1 The Arabian Gulf - Khaleeji](#31-the-arabian-gulf---khaleeji)
  - [3.2 Egypt - Masri (Tarab, Baladi, Shaabi & Mahraganat)](#32-egypt---masri-tarab-baladi-shaabi--mahraganat)
  - [3.3 The Levant - Shami (Lebanon, Syria, Palestine, Jordan)](#33-the-levant---shami-lebanon-syria-palestine-jordan)
  - [3.4 Iraq - Mesopotamian / Rafidain (Maqam Iraqi & Chobi)](#34-iraq---mesopotamian--rafidain-maqam-iraqi--chobi)
  - [3.5 North Africa - Al-Maghreb (Morocco, Algeria, Tunisia, Libya)](#35-north-africa---al-maghreb-morocco-algeria-tunisia-libya)
  - [3.6 Sudan & Yemen - The Southern Crossroads](#36-sudan--yemen---the-southern-crossroads)
- [4.0 Core Arabic Instruments: Physics & Pure-Python DSP Modeling](#4-core-arabic-instruments-physics--pure-python-dsp-modeling)
  - [4.1 Oud (Fretless Pear-Shaped Lute)](#41-oud---fretless-pear-shaped-lute)
  - [4.2 Qanun (78-String Trapezoidal Zither)](#42-qanun---78-string-trapezoidal-zither)
  - [4.3 Ney (End-Blown Reed Flute)](#43-ney---end-blown-reed-flute)
  - [4.4 Darbuka / Tabla (Goblet Drum)](#44-darbuka--tabla---goblet-drum)
  - [4.5 Riq (Virtuosic Classical Tambourine)](#45-riq---virtuosic-classical-tambourine)
- [5.0 Pure-Python Algorithmic Parameter Cheat Sheet](#5-pure-python-algorithmic-parameter-cheat-sheet)
  - [5.1 Microtonal Maqam Frequency Calculator](#51-microtonal-maqam-frequency-calculator-supports-quarter-tones)
  - [5.2 Regional Iqa'at (Rhythmic Matrices)](#52-regional-iqaat-rhythmic-matrices---16-step--12-step-grids)
- [6.0 Cross-Cultural Fusion Matrix: How to Fuse Regional Arabic with Tamil & Western Styles](#6-cross-cultural-fusion-matrix-how-to-fuse-regional-arabic-with-tamil--western-styles)

---

## 1. Core Psychoacoustics: How the "Arab Ear" Listens (*Tarab* & *Saltanah*)

In Arabic music, the ultimate psychoacoustic goal is **Tarab (طرب)**—a state of musical ecstasy, emotional enchantment, and time-suspension—achieved when the performer (or algorithm) reaches **Saltanah (سلطنة)** (complete modal immersion).

| Perceptual Dimension | Western Ear Conditioning | Arab Ear Conditioning | Algorithmic / Python DSP Rule |
| :--- | :--- | :--- | :--- |
| **Intonation (Pitch Space)** | **12-TET Grid:** Divides the octave into 12 equal 100-cent steps. Quarter-tones sound "out of tune." | **Microtonal *Maqam* Space:** Uses **Neutral Intervals** (approx. 145–165 cents, often called "quarter-tones" or *Sikah*). | Never quantize *Sikah* (`E-half-flat`, `B-half-flat`) to 12-TET. Use exact cent offsets (e.g., `+150 cents` or `-35 to -50 cents` from 12-TET) and adjust dynamically based on ascending vs. descending motion. |
| **Structural Unit** | **The Scale (Octave):** 7 notes repeating identically every octave. | **The *Jins* (Tetrachord/Pentachord):** A *Maqam* is built by stacking two 3-, 4-, or 5-note mini-scales (*Ajnas*, singular *Jins*) with distinct emotional flavors. | Generate melodies inside a 4-note **Lower *Jins* (Root to 4th)** for 70% of the phrase before modulating to the **Upper *Jins* (4th/5th to Octave)**. |
| **Harmony vs. Heterophony** | **Polyphony/Chords:** Multiple instruments play different chord notes simultaneously. | **Heterophony:** Multiple instruments (e.g., *Oud*, *Qanun*, *Ney*, *Violin*) play the **same melody simultaneously**, each adding its own idiomatic ornaments, trills, and micro-delays. | Layer 2–3 lead synths on the *same* melody line, but offset their timing by `±12ms` and give each a different ornamentation algorithm (e.g., tremolo on Qanun, pitch-slide on Violin). |
| **Rhythmic Polarity** | **Kick vs. Snare:** Low vs. mid-range backbeat. | ***Doum* (دم) vs. *Tak* (تك):** Deep, resonant center-skin chest thump (*Doum*) vs. razor-sharp, metallic rim slap (*Tak*) and muted finger roll (*Ka*). | Separate percussion strictly into `65Hz–110Hz` resonant *Doum* and `2.8kHz–6kHz` transient *Tak* with zero muddy `400Hz` overlap. |

---

## 2. The Mathematical Architecture of *Maqamat* (Scales & Quarter-Tones)

Unlike a static 24-TET grid (where every quarter-tone is rigidly 50 cents), real Arabic intonation varies by **region**!
* **Egyptian (Cairo) Intonation:** The neutral third (*Sikah*) sits slightly higher (`~355 to 360 cents` from the root, or `-40 to -45 cents` below a major 3rd).
* **Levantine (Syria/Lebanon) & Iraqi Intonation:** The neutral third sits lower and more melancholic (`~335 to 345 cents` from the root, or `-55 to -65 cents` below a major 3rd).

### Core *Maqam* Cent-Offset Dictionary (Relative to Root = `0.0` Semitones)
*(Note: `0.5` = 50 cents / 1 quarter-tone; `1.0` = 100 cents / 1 semitone)*

| Maqam Name | Semitone / Microtone Array (Ascending) | Emotional Feel (*Ta'thir*) | Regional Stronghold |
| :--- | :--- | :--- | :--- |
| **Rast (راست)** | `[0.0, 2.0, 3.55, 5.0, 7.0, 9.0, 10.55, 12.0]` *(Descends with `10.0`)* | Proud, regal, foundational, masculine, balanced. | Pan-Arab (Egypt, Levant, Gulf, Iraq) |
| **Bayati (بياتي)** | `[0.0, 1.5, 3.0, 5.0, 7.0, 8.0, 10.0, 12.0]` | Warm, earthy, folkloric, intimate, maternal, celebratory. | Most popular Maqam in Arabic Pop, Dabke & Khaleeji |
| **Hijaz (حجاز)** | `[0.0, 1.0, 4.0, 5.0, 7.0, 8.0, 10.0, 12.0]` *(or `11.0` in Hijaz Kar)* | Desert mystique, spiritual, dramatic, ancient, hypnotic. | Pan-Arab + Direct bridge to Tamil *Mayamalavagowla* |
| **Saba (صبا)** | `[0.0, 1.5, 3.0, 4.0, 7.0, 8.0, 10.0, 11.0]` *(Diminished 4th at `4.0`!)* | Deep sorrow, heartbreak, spiritual weeping, tragic yearning. | Egypt, Iraq (*Maqam Saba*), Levant |
| **Sikah (سيكاه)** | `[0.0, 1.45, 3.45, 5.0, 6.45, 8.45, 10.0, 12.0]` *(Starts on a quarter-tone!)* | Ecstatic, floating, mystical, Sufi trance. | Egypt, Syria, Iraq (*Huzam* variant) |
| **Nahawand (نهاوند)** | `[0.0, 2.0, 3.0, 5.0, 7.0, 8.0, 11.0, 12.0]` | Cinematic, romantic, dramatic, Western-compatible (Harmonic/Natural Minor). | Beirut/Cairo Pop, Orchestral Tarab |
| **Kurd (كرد)** | `[0.0, 1.0, 3.0, 5.0, 7.0, 8.0, 10.0, 12.0]` | Smooth, modern, nostalgic, romantic, Spanish/Andalusian vibe. | Modern Arabic Pop (Amr Diab style), Maghreb |
| **Nikriz (نكريز)** | `[0.0, 2.0, 3.0, 6.0, 7.0, 9.0, 10.0, 12.0]` | Playful, storytelling, theatrical, mischievous. | Egypt, Levant *(Similar to Tamil Simhendramadhyamam)* |

---

## 3. Complete Regional Breakdown: The 6 Musical Worlds of the Arab World

Arabic music is **not a monolith**. A listener from Doha, Riyadh, Cairo, Beirut, Baghdad, or Marrakech hears rhythm, swing, and timbre in completely different ways.

---

### 3.1 The Arabian Gulf — *Khaleeji* (الخليجي)
* **Countries:** Qatar, Saudi Arabia, UAE, Kuwait, Bahrain, Oman.
* **Cultural DNA:** Bedouin desert poetry (*Nabati*) + Pearl-diving sea shanties (*Fijiri / Bahri*) + Historic trade links across the Indian Ocean and East Africa (*Sawt* and *Lewa*).
* **How the Khaleeji Ear Listens:**
  * It does **not** listen to a straight 4/4 beat. It listens for a **rolling, polyrhythmic 6/8 or 12/8 compound swing** driven by interlocking group handclaps (*Safqa*) and deep frame drums (*Tar*).
  * The ear craves **warm, low-mid skin resonance** (heated frame drums) and **syncopated bass drops** on the *and-of-2*.
* **Signature Khaleeji Rhythms (*Iqa'at*):**
  1. **Rumpla / Khaleeji (رمبلا / خليجي) [4/4 with heavy swing or 12/8]:**
     * Pattern: `Doum (1) — — Doum (and-of-2) — — | Tak (4) — — —` (`1 . . 4 . . 7 .` on an 8-grid, with a deep sub-bass hit on `1` and `4`).
  2. **Samri (سامري) [6/8 or 3/4]:** Hypnotic, slow-to-medium desert swaying groove (`Doum - Tak - Tak | Doum - Doum - Tak`).
  3. **Ardah (عرضة) [6/8 Folkloric Sword Dance]:** Heavy, stately stacked drums (*Takhmer* + *Tathlith*) with proud call-and-response male chants.
  4. **Bandari / Lewa (بندري / ليوا) [Fast 6/8]:** High-energy coastal Gulf groove with polyrhythmic triplets, bagpipe/double-reed (*Habban* or *Surnay*), and African-Gulf percussion.
* **Signature Timbres & DSP:**
  * **Mirwas (مرواس):** Small, high-pitched double-sided Gulf hand drum. *DSP:* Crisp `450Hz` membrane pop + `5ms` sharp transient.
  * **Tar (طار):** Large frame drums tuned by holding them over a fire prior to performance. *DSP:* Deep `85Hz–110Hz` warm sine-triangle thump with long `250ms` decay.
  * **Safqa (صفقة - Interlocking Claps):** 3 to 5 layers of handclaps panned wide (`-45°` to `+45°`), bandpass filtered between `900Hz–2.8kHz`, with `8–18ms` human timing scatter.
  * **Khaleeji Oud:** Tuned lower (`C - F - A - D - G - C` or `F - A - D - G - C`), played with heavy thumb-strokes and percussive finger taps (*Risha*) on the wooden soundboard.

---

### 3.2 Egypt — *Masri* (المصري: *Tarab*, *Baladi*, *Shaabi* & *Mahraganat*)
* **Cultural DNA:** Nile Valley agrarian folk (*Sa'idi* from Upper Egypt), Cairo Golden-Age Orchestral *Tarab* (Umm Kulthum, Abdel Halim Hafez), and raw working-class Cairo street celebrations (*Shaabi* and electronic *Mahraganat*).
* **How the Egyptian Ear Listens:**
  * Obsessed with **Groove Pocket (*Dala'* - playfulness/swagger)**. Even orchestral strings play with a heavy, laid-back rhythmic bounce behind the beat.
  * Loves **call-and-response (*Luhma*)** between a solo instrument (Accordion, Nay, or Saxophone/Mizmar) and a massive unison violin section (*Firqa*).
* **Signature Egyptian Rhythms:**
  1. **Maqsum (مقسوم) [4/4]:** `Doum - Tak - (rest) - Tak - | Doum - (rest) - Tak - (rest)` (`D T . T D . T .`).
  2. **Baladi (بلدي - "Of the Country") [4/4]:** Starts with a famous double-Doum chest thump: `Doum - Doum - (rest) - Tak - | Doum - (rest) - Tak - (rest)`.
  3. **Sa'idi (صعيدي - Upper Egypt Stick Dance) [4/4]:** Double-Doum in the middle: `Doum - Tak - (rest) - Doum - | Doum - (rest) - Tak - (rest)`.
  4. **Malfuf (ملفوف) [2/4 Fast Entrance/Street Beat]:** `Doum - . - . - Tak - . - Tak - .` (`3 + 3 + 2` Euclidean pulse).
* **Sub-Genre Spotlight — *Shaabi* & *Mahraganat* (Electro-Chaabi):**
  * **The Egyptian Equivalent of Tamil Kuthu/Gaana!** Born in working-class Cairo weddings.
  * Uses **130–145 BPM** compressed electronic *Darbuka* loops, distorted *Malfuf/Baladi* kicks, microtonal **Quarter-Tone Keyboard Lead** (Korg Pa-series style *Mizmar* synth), and heavily Auto-Tuned rapid-fire vocal chants.

---

### 3.3 The Levant — *Shami* (الشامي: Lebanon, Syria, Palestine, Jordan)
* **Cultural DNA:** Mountain village line-dancing (**Dabke - دبكة**), Aleppo classical *Muwashahat* (Andalusian-Syrian poetic courts), and Beirut cosmopolitan synth-pop.
* **How the Levantine Ear Listens:**
  * Listens for **stomp-and-leap kinetic energy** (the foot-stomp on Beat 1 of Dabke) paired with **soaring, improvisational vocal/horn intros (*Mawwal*)**.
* **Signature Levantine Rhythms:**
  1. **Dabke / Dal'ouna (دبكة) [4/4 or 2/4]:** Driven by a booming **Tabl (Davul)** bass drum hit with a heavy wooden club on Beat 1, and a thin switch stick (*ss-tak*) on the off-beats.
  2. **Ayoub / Zar (أيوب) [2/4]:** Fast, driving, trance-inducing `Doum - . - . - Tak - | Doum - . - Tak - .`.
* **Signature Timbres & DSP:**
  * **Mijwiz (مجوز) & Arghul (يرغول):** Double-pipe single-reed bamboo clarinets played with circular breathing.
    * *DSP:* Two detuned pulse waves (`f0` and `f0 + 4 cents` for natural chorus beating, or `f0` + continuous drone pipe at root) passed through a sharp `1.4kHz` nasal formant filter with rapid `16th-note` finger-trill pitch modulation.
  * **Buzuq (بزق):** Long-necked fretted lute with bright, metallic double-courses of strings.

---

### 3.4 Iraq — *Mesopotamian / Rafidain* (العراقي: *Maqam Iraqi* & *Chobi*)
* **Cultural DNA:** Ancient Baghdad court music (*Al-Maqam Al-Iraqi*) and high-energy rural/tribal line-dancing (**Chobi - الجوبي**).
* **How the Iraqi Ear Listens:**
  * Deeply tuned to **sorrowful, raw, emotional vulnerability (*Huzn*)** juxtaposed against **earth-shaking, syncopated tribal bounce (*Chobi*)**.
* **Signature Iraqi Rhythms:**
  1. **wahda / Chobi (إيقاع الجوبي / الهجع) [4/4 with heavy dotted-triplet bounce]:**
     * The most infectious groove in modern Middle Eastern pop! It features a **double-snare/Khashaba crack right before Beat 1 and on the *and-of-2***.
  2. **Jurjina (جورجينا) [10/8]:** Complex `3 + 2 + 2 + 3` asymmetrical groove (`Doum - . - . - Tak - . - | Tak - . - Doum - . - Tak`).
* **Signature Timbres:**
  * **Khashaba (خشبة):** Narrow hourglass wooden hand-drum with a super high-pitched, gunshot-like rim crack (`3.5kHz`).
  * **Santur (سنطور):** Hammered dulcimer (72–100 metallic strings hit with wooden mallets) creating shimmering cascades of microtonal tremolos.
  * **Joza (جوزة):** Four-stringed spike fiddle made from a coconut shell, sounding remarkably like a weeping human voice.

---

### 3.5 North Africa — *Al-Maghreb* (المغرب العربي: Morocco, Algeria, Tunisia, Libya)
* **Cultural DNA:** Amazigh (Berber) polyrhythms + Andalusian *Nuba* classical music + Sub-Saharan *Gnawa* spiritual trance + Algerian *Raï*.
* **How the Maghrebi Ear Listens:**
  * Totally different from the East (*Mashriq*)! Uses **fewer quarter-tones** (often favors pure 12-TET diatonic/pentatonic or Phrygian/Hijaz modes) and focuses intensely on **hypnotic, accelerating 6/8 and 12/8 polyrhythms** (`3 against 2`).
* **Signature Maghrebi Styles & Rhythms:**
  1. **Moroccan Chaabi & Gnawa (6/8 / 12/8):** Starts at `95 BPM` and accelerates (*Derdeba*) up to `160+ BPM` in a single track!
  2. **Algerian Raï (راي) [4/4 or 6/8]:** Rebellious, funky synth-pop/folk mixing **Gasba** (reed flute), **Guellal** (clay drum), accordion/synth brass, and syncopated basslines.
* **Signature Timbres:**
  * **Guembri / Sintir (كمبري):** 3-stringed camel-skin bass lute played by *Gnawa* masters. *DSP:* Deep, woody, fretless upright-bass pluck (`70Hz–250Hz`) with a percussive finger-tap on the skin head.
  * **Qraqeb (قراقب):** Heavy iron castanets playing relentless `6/8` triplet metallic clanks (`2kHz–9kHz`).

---

### 3.6 Sudan & Yemen — *The Southern Crossroads*
* **Sudan:** Uses **5-note Anhemitonic Pentatonic scales** `[0, 2, 4, 7, 9]` (zero quarter-tones!) combined with swinging **6/8 *Tum-Tum* and *Daluka* clay-drum rhythms**, lush jazz-style saxophone/brass harmonies, and accordion.
* **Yemen (*Sana'ani*, *Hadrami*, *Adani*):** The ancestral homeland of many Gulf rhythms! Features the **Qanbus** (carved wooden skin-bellied lute), rhythmic copper tray percussion (**Sahn Nuhasi** held on the thumbs), and complex `7/8` (*Daasa*) and `11/8` cycles.

---

## 4. Core Arabic Instruments: Physics & Pure-Python DSP Modeling

To synthesize an authentic Arabic ensemble (*Takht*) in Python without external sample libraries, model these 5 core acoustic behaviors:

### 4.1 Oud (عود - Fretless Pear-Shaped Lute)
* **Acoustic Physics:** 5 double-courses of nylon/wound strings + 1 single bass string, plucked with a flexible plectrum (*Risha*), no frets, low string tension, large resonant cavity (`110Hz` and `220Hz` body modes).
* **Python DSP Recipe:**
  1. Generate **two Karplus-Strong delay lines per note** detuned by `+1.8 cents` and `-1.8 cents` (simulating the paired string course).
  2. Trigger the second string `4 milliseconds` after the first to simulate the *Risha* sweeping across the pair!
  3. Pass through a 2-pole resonant body filter at `115Hz` (`+4dB`) and `240Hz` (`+3dB`).
  4. Apply **Fretless *Glissando***: Slide between consecutive notes using a continuous frequency array rather than re-triggering the pluck on every note (simulating left-hand finger slides on the fretless neck).

### 4.2 Qanun (قانون - 78-String Trapezoidal Zither)
* **Acoustic Physics:** Triple-string courses stretched over a bridge resting on **fish-skin/parchment membranes (*Raqq*)**, plucked with tortoise-shell/horn plectra on the index fingers, with brass microtonal levers (*Mandal*).
* **Python DSP Recipe:**
  1. Combine **3 Karplus-Strong strings per pitch** (`-2.5 cents`, `0 cents`, `+2.5 cents`).
  2. **The *Rasha* (Signature Tremolo):** Rapidly re-trigger alternating left/right plucks every `35ms–50ms` (`20Hz–28Hz` roll) with randomized velocity (`0.6 to 1.0`).
  3. High-pass above `300Hz` and add a bright skin-bridge resonance peak at `2.8kHz`.

### 4.3 Ney (ناي - End-Blown Reed Flute)
* **Acoustic Physics:** Open hollow reed cylinder; player blows obliquely across the rim. Produces strong **breath turbulence + 1st and 2nd overblown octave harmonics**.
* **Python DSP Recipe:**
  1. Mix a fundamental sine wave (`f0`), second harmonic (`2*f0` at `0.4` gain), and third harmonic (`3*f0` at `0.25` gain).
  2. Multiply by **Bandpass-Filtered Pink Noise** (`center = f0 * 1.5, Q = 4.0`) at `25%` wet mix so the breath noise tracks the pitch!
  3. **Attack Overblow:** In the first `35ms` of a loud note, briefly spike the `2*f0` harmonic and pitch (`+20 cents`) before settling into the fundamental.

### 4.4 Darbuka / Tabla (دربكة / طبلة - Goblet Drum)
* **Acoustic Physics:** Aluminum or clay goblet body with a tight plastic or fish-skin head.
* **Python DSP Recipe:**
  * ***Doum* (Center Bass Hit):** Sine + Triangle wave sweeping from `185Hz -> 92Hz` over `45ms`, with a resonant tail decaying over `190ms` at `92Hz`.
  * ***Tak* (Rim Slap):** Inharmonic metallic membrane modes (`f1 = 420Hz`, `f2 = 1.59 * f1`, `f3 = 2.14 * f1`, `f4 = 2.65 * f1`) + a `4ms` burst of `4.5kHz` bandpass noise, decaying in `40ms`.
  * ***Ka* (Left-Hand Rim Tap):** Same as *Tak*, pitched `+80Hz` higher and `-6dB` quieter for rapid `16th/32nd-note` ornaments (*Farkha*).

### 4.5 Riq (رق - Virtuosic Classical Tambourine)
* **Acoustic Physics:** Frame drum with 5 double-pairs of thick brass cymbals (*Sagat*).
* **Python DSP Recipe:** High-passed FM metallic clusters (`4.5kHz`, `7.2kHz`, `11.4kHz`) with two modes: *Open Jingle* (`120ms` decay) and *Cash/Muted Shake* (`18ms` tight decay).

---

## 5. Pure-Python Algorithmic Parameter Cheat Sheet

Use these exact data structures in your Python script to switch between regional Arabic grooves and *Maqamat*:

### 5.1 Microtonal *Maqam* Frequency Calculator (Supports Quarter-Tones!)
\`\`\`python
import numpy as np

# Semitone offsets from Root (Decimals = Quarter-Tone / Microtonal inflections!)
ARABIC_MAQAMAT = {
    "rast_cairo":      [0.0, 2.0, 3.55, 5.0, 7.0, 9.0, 10.55, 12.0],
    "rast_levant":     [0.0, 2.0, 3.40, 5.0, 7.0, 9.0, 10.40, 12.0],
    "bayati_folk":     [0.0, 1.50, 3.0, 5.0, 7.0, 8.0, 10.0,  12.0],
    "hijaz_desert":    [0.0, 1.0,  4.0, 5.0, 7.0, 8.0, 10.0,  12.0],
    "hijaz_kar":       [0.0, 1.0,  4.0, 5.0, 7.0, 8.0, 11.0,  12.0],
    "saba_tragic":     [0.0, 1.50, 3.0, 4.0, 7.0, 8.0, 10.0,  11.0],
    "sikah_trance":    [0.0, 1.55, 3.55, 5.0, 6.55, 8.55, 10.0, 12.0],
    "nahawand_pop":    [0.0, 2.0,  3.0, 5.0, 7.0, 8.0, 11.0,  12.0],
    "kurd_maghreb":    [0.0, 1.0,  3.0, 5.0, 7.0, 8.0, 10.0,  12.0],
}

def maqam_degree_to_hz(root_midi: float, maqam_name: str, degree_idx: int) -> float:
    """Converts a Maqam scale degree index into exact microtonal Hz."""
    scale = ARABIC_MAQAMAT[maqam_name]
    octave = degree_idx // (len(scale) - 1)
    step = degree_idx % (len(scale) - 1)
    exact_midi = root_midi + (octave * 12.0) + scale[step]
    return 440.0 * (2.0 ** ((exact_midi - 69.0) / 12.0))
\`\`\`

### 5.2 Regional *Iqa'at* (Rhythmic Matrices — 16-Step & 12-Step Grids)
\`\`\`python
# Legend: 'D' = Doum (Low 90Hz), 'T' = Tak (Sharp 3.5kHz), 'k' = Ka (Soft Rim), 'S' = Safqa (Clap), '.' = Rest
REGIONAL_IQAAT = {
    # 1. EGYPTIAN BALADI (16-step 4/4: Double-Doum intro with syncopated bounce)
    "egypt_baladi_16": {
        "darbuka": ["D", ".", "D", ".", ".", "k", "T", ".", "D", ".", ".", "k", "T", ".", "k", "k"],
        "riq":     ["T", "k", "T", "k", "T", "k", "T", "k", "T", "k", "T", "k", "T", "k", "T", "k"],
        "swing_ms":[0.0, +3,  0.0, +4,  0.0, -2,  0.0, +4,  0.0, +3,  0.0, -2,  0.0, +4,  -2,  +3]
    },
    # 2. GULF KHALEEJI RUMPLA (16-step 4/4: Heavy Doum on 1 and 'and-of-2' + Interlocking Claps)
    "gulf_khaleeji_16": {
        "tar_bass":["D", ".", ".", "k", ".", ".", "D", ".", ".", ".", "T", ".", "D", ".", ".", "."],
        "safqa":   ["S", ".", ".", "S", ".", ".", "S", ".", "S", ".", "S", ".", ".", "S", ".", "S"],
        "swing_ms":[0.0, +6,  -3, +8,   0.0, +5,  -4, +6,   0.0, +6,  0.0, +5,  -3, +7,   0.0, +5]
    },
    # 3. LEVANTINE DABKE (16-step 4/4: Heavy Tabl stomp on 1 + fast off-beat stick cracks)
    "levant_dabke_16": {
        "tabl":    ["D", ".", "T", "k", "D", ".", "T", ".", "D", ".", "T", "k", "T", ".", "T", "k"],
        "swing_ms":[0.0,  0,  -2,  +2,  0.0,  0,  -2,  0,   0.0,  0,  -2,  +2,  0.0,  0,  -2,  +2]
    },
    # 4. IRAQI CHOBI (12-step 12/8 Triplet Grid: High-energy tribal bounce)
    "iraq_chobi_12": {
        "khashaba":["D", ".", "k", "D", "T", ".", "D", ".", "k", "T", ".", "T"],
        "swing_ms":[0.0, +4,  -3,  0.0, -2,  +4,  0.0, +3,  -3,  0.0, +4,  -4]
    },
    # 5. MOROCCAN CHAABI / GNAWA (12-step 6/8 Compound Groove)
    "maghreb_chaabi_12": {
        "bendir":  ["D", ".", "T", "D", ".", "T", "D", "D", "T", ".", "T", "k"],
        "qraqeb":  ["T", "k", "T", "T", "k", "T", "T", "k", "T", "T", "k", "T"]
    }
}
\`\`\`

---

## 6. Cross-Cultural Fusion Matrix: How to Fuse Regional Arabic with Tamil & Western Styles

Since your engine specializes in cross-cultural algorithmic synthesis, here are the **4 Ultimate Fusion Pairings**:

1. **Gulf *Khaleeji Samri/Bandari* (6/8) $\times$ Tamil *Dappankoothu* (6/8):**
   * **Why it's explosive:** Both Gulf *Bandari/Samri* and Tamil *Kuthu* operate on a galloping **6/8 (12-step) compound meter** and share historical Indian Ocean maritime roots!
   * **DSP Implementation:** Layer Gulf **Interlocking Handclaps (*Safqa*) + *Mirwas*** on the left/right channels (`±40°`) while the Tamil ***Parai* + *Thavil* + *Urumi*** hold down the center. Use *Maqam Bayati* (with the quarter-tone 2nd!) on a *Nadaswaram* lead.
2. **Egyptian *Mahraganat / Shaabi* $\times$ Chennai *Gaana*:**
   * **Why it's explosive:** Both are raw, high-tempo (`138 BPM`) street celebration genres.
   * **DSP Implementation:** Alternate 8 bars of Egyptian **Malfuf (`3 + 3 + 2`)** with 8 bars of Tamil **Gaana (`6/8`)**. Use a microtonal **Arabic Mizmar** trading 2-bar call-and-response riffs with a **Tamil Parai + Street Whistle**.
3. **Iraqi *Chobi* $\times$ Western Trap / Drill:**
   * **Why it's explosive:** The syncopated double-snare of Iraqi *Chobi* locks effortlessly into UK Drill 808 glides and triplet hi-hats.
   * **DSP Implementation:** Map a sliding **808 sub-bass** to *Maqam Saba* or *Hijaz*, and layer an Iraqi **Santur** (hammered dulcimer) playing dark 16th-note arpeggios in the high frequencies.
4. **Levantine *Dabke* $\times$ Anirudh-Style Mass Stadium Brass:**
   * **Why it's explosive:** Levantine *Dabke* has the heaviest Beat-1 foot-stomp in Arabic music, and its double-reed **Mijwiz** sounds like a cousin of the Tamil **Nadaswaram**.
   * **DSP Implementation:** Harmonize a Levantine *Mijwiz* trill in octaves with a heavy distorted **Sub-Drop + Brass Synth** on Beat 1, followed by a fast *Darbuka + Thavil* percussion battle.
