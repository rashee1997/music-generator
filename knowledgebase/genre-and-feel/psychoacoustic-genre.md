---
id: psychoacoustic-genre
title: Genre and mood archetypes: tempo, intervals, timbre and space
domain: genre
status: unverified
sources: []
used_by: [AGENTS.md, references/scoring/genres-and-moods.md]
updated: 2026-11-04
---

> **Not verified.** These values are a starting point from practice, not a measurement.
> Cite a source before presenting one as established, and say "starting value" when a piece uses one.

# The Master Psychoacoustic Genre, Sub-Feel & Algorithmic Music Ontology
**Purpose:** Prevent AI music generators from defaulting to generic "upbeat 4/4 block-chord" templates. Every genre and emotional sub-archetype possesses a unique **psychoacoustic contract** with the human ear—defined by **Interval Leap Geometry, Micro-Timing Gravity, Spectral Centroid Trajectory, Harmonic Voice-Leading, and Spatial Reverb Physics**.

---

## Table of Contents (Machine-Parsable Index)
- [1.0 Core Agent Directive: Breaking the "Upbeat Trap"](#10-core-agent-directive-breaking-the-upbeat-trap)
- [2.0 The "Adventurous" Ontology (5 Distinct Sub-Archetypes)](#20-the-adventurous-ontology-5-distinct-sub-archetypes)
  - [2.1 ARCHETYPE: Adventurous_Forest_Mystic (Woodland / Elven / Folklore)](#21-archetype-adventurous_forest_mystic-woodland--elven--folklore)
  - [2.2 ARCHETYPE: Adventurous_Cinematic_Frontier (Wide-Screen Horizon / Discovery)](#22-archetype-adventurous_cinematic_frontier-wide-screen-horizon--discovery)
  - [2.3 ARCHETYPE: Adventurous_HighSeas_Swashbuckler (Maritime / Pirate / Kinetic)](#23-archetype-adventurous_highseas_swashbuckler-maritime--pirate--kinetic)
  - [2.4 ARCHETYPE: Adventurous_Ancient_Desert_Ruin (Archaeological / Mirage / Dune)](#24-archetype-adventurous_ancient_desert_ruin-archaeological--mirage--dune)
  - [2.5 ARCHETYPE: Adventurous_Cosmic_Odyssey (Sci-Fi / Zero-Gravity / Interstellar)](#25-archetype-adventurous_cosmic_odyssey-sci-fi--zero-gravity--interstellar)
- [3.0 The "Epic" Ontology (4 Distinct Sub-Archetypes)](#30-the-epic-ontology-4-distinct-sub-archetypes)
  - [3.1 ARCHETYPE: Epic_Colossal_Hybrid_Trailer (Braaam / Titan / Modern Cinema)](#31-archetype-epic_colossal_hybrid_trailer-braaam--titan--modern-cinema)
  - [3.2 ARCHETYPE: Epic_Mythic_Choral_Tragedy (Soulsborne / Gothic / Apocalyptic)](#32-archetype-epic_mythic_choral_tragedy-soulsborne--gothic--apocalyptic)
  - [3.3 ARCHETYPE: Epic_Triumphant_Ascension (Coronation / Victory / Stadium Mass)](#33-archetype-epic_triumphant_ascension-coronation--victory--stadium-mass)
  - [3.4 ARCHETYPE: Epic_Tribal_War_March (Primal / Phalanx / Earth-Shaking)](#34-archetype-epic_tribal_war_march-primal--phalanx--earth-shaking)
- [4.0 The "Electronic" Ontology (5 Distinct Sub-Archetypes)](#40-the-electronic-ontology-5-distinct-sub-archetypes)
  - [4.1 ARCHETYPE: Electronic_Hypnotic_Warehouse (Berlin Minimal / Rolling Techno)](#41-archetype-electronic_hypnotic_warehouse-berlin-minimal--rolling-techno)
  - [4.2 ARCHETYPE: Electronic_Euphoric_Festival (Progressive / Melodic / SuperSaw)](#42-archetype-electronic_euphoric_festival-progressive--melodic--supersaw)
  - [4.3 ARCHETYPE: Electronic_Cyberpunk_Midtempo (Dystopian / Gritty / Industrial)](#43-archetype-electronic_cyberpunk_midtempo-dystopian--gritty--industrial)
  - [4.4 ARCHETYPE: Electronic_Organic_Deep_Sunset (Melodic House / Desert / Afro-Deep)](#44-archetype-electronic_organic_deep_sunset-melodic-house--desert--afro-deep)
  - [4.5 ARCHETYPE: Electronic_Neuro_Kinetic_Bass (Drum & Bass / Halftime / Glitch)](#45-archetype-electronic_neuro_kinetic_bass-drum--bass--halftime--glitch)
- [5.0 The "Pop" Ontology (4 Distinct Sub-Archetypes)](#50-the-pop-ontology-4-distinct-sub-archetypes)
  - [5.1 ARCHETYPE: Pop_MaxMartin_Pocket_Drive (Crisp / Syncopated / Radio-Tight)](#51-archetype-pop_maxmartin_pocket_drive-crisp--syncopated--radio-tight)
  - [5.2 ARCHETYPE: Pop_Dreamy_Nostalgic_Synth (Midnight / 80s Retro / Bittersweet)](#52-archetype-pop_dreamy_nostalgic_synth-midnight--80s-retro--bittersweet)
  - [5.3 ARCHETYPE: Pop_Bedroom_Intimate_Whisper (ASMR / Lo-Fi / Billie-Style)](#53-archetype-pop_bedroom_intimate_whisper-asmr--lo-fi--billie-style)
  - [5.4 ARCHETYPE: Pop_Sunshine_Funk_NuDisco (Strut / Slap-Bass / Uplifting)](#54-archetype-pop_sunshine_funk_nudisco-strut--slap-bass--uplifting)
- [6.0 The "Celtic" Ontology (4 Distinct Sub-Archetypes)](#60-the-celtic-ontology-4-distinct-sub-archetypes)
  - [6.1 ARCHETYPE: Celtic_Tavern_Reel_Frenzy (Foot-Stomping / Fiddle / Joyful)](#61-archetype-celtic_tavern_reel_frenzy-foot-stomping--fiddle--joyful)
  - [6.2 ARCHETYPE: Celtic_Misty_Highland_Lament (Ancient / Cliffside / Keening)](#62-archetype-celtic_misty_highland_lament-ancient--cliffside--keening)
  - [6.3 ARCHETYPE: Celtic_Fae_Woodland_SlipJig (Enchanted / 9-8 Meter / Harp)](#63-archetype-celtic_fae_woodland_slipjig-enchanted--9-8-meter--harp)
  - [6.4 ARCHETYPE: Celtic_Highland_Battle_Charge (Bagpipe Drone / War Drums / Fierce)](#64-archetype-celtic_highland_battle_charge-bagpipe-drone--war-drums--fierce)
- [7.0 Agent Decision Matrix & Python Parameter Schema](#70-agent-decision-matrix--python-parameter-schema)

---

## 1.0 Core Agent Directive: Breaking the "Upbeat Trap"

When an AI agent is prompted for *"energetic"*, *"adventurous"*, *"upbeat"*, or *"epic"*, naive algorithms default to the same broken formula: `128 BPM + 4/4 Kick-Snare + I-V-vi-IV Major Chords + Stepwise 8th-Note Melody`.

**Psychoacoustic Reality:** The human brain does **not** classify emotion by BPM alone. It classifies musical feel across **5 Orthogonal Axes**:
1. **Melodic Interval Geometry:** Stepwise motion (`+1/+2` semitones) feels *narrative/intimate*; Perfect 4th/5th leaps (`+5/+7` semitones) feel *heroic/horizon-expanding*; Minor 6th leaps (`+8` semitones) feel *yearning/tragic*; Octave leaps (`+12`) feel *soaring/ecstatic*.
2. **Harmonic Motion Type:** Diatonic root movement (`I -> IV -> V`) feels *predictable/pop*; **Chromatic Mediants** (`i -> bVI`, `I -> bIII`, `I -> bVII`) bypass rational logic and trigger *wonder, magic, and cinematic scale*.
3. **Rhythmic Gravity (Where the Weight Sits):** Front-heavy (`Beat 1` stomp) feels *marching/grounded*; Back-heavy (`Beats 2 & 4`) feels *dancing/urban*; Compound (`6/8, 9/8, 12/8` triplet roll) feels *galloping/seafaring/folklore*; Beatless/Pulse-Arpeggio feels *floating/forest/cosmic*.
4. **Spectral Centroid & Transient Sharpness:** Soft `40ms` attacks with `1.2kHz` centroid feel *ancient/misty/warm*; `2ms` transients with `4.5kHz` presence feel *modern/aggressive/urgent*.
5. **Spatial Acoustic Envelope:** Short dry room (`120ms` ER) feels *inside the listener's head*; Pre-delayed `60ms` + `3.5s` hall feels *wide-screen cinema*; High-passed shimmer tail (`+12 semitone pitch-shifted reverb`) feels *magical/ethereal*.

---

## 2.0 The "Adventurous" Ontology (5 Distinct Sub-Archetypes)

> **CRITICAL RULE:** "Adventurous" is **NOT** "Upbeat Pop". Adventure requires **curiosity, spatial vastness, modal color (Lydian `#4` or Mixolydian `b7`), and forward momentum without claustrophobic four-on-the-floor club kicks**.

---

### 2.1 ARCHETYPE: `Adventurous_Forest_Mystic` (Woodland / Elven / Folklore)
* **How the Ear Listens:** The ear listens for **pointillistic, plucked wooden/metallic droplets** (*Celesta, Harp, Pizzicato Strings, Dulcimer*) dancing around a breathy solo wind instrument (*Alto Flute, Oboe, Ocarina*). Heavy sub-bass (`<70Hz`) ruins this feel—the low end must be warm, woody, and airy (`90Hz–200Hz` upright bass pizzicato or low harp).
* **How the Body Feels:** Light-footed curiosity, dappled sunlight through leaves, wonder, safety mixed with ancient mystery.
* **Musical Mathematics:**
  * **Meter & Tempo:** `3/4`, `6/8`, or `5/4` at `96 – 112 BPM` (Waltz-like or uneven stepping stride).
  * **Scale:** **Dorian with occasional Lydian modulation** (`[0, 2, 3, 5, 7, 9, 10]` shifting to `[0, 2, 4, 6, 7, 9, 11]`).
  * **Chord Engine:** `i(add9)` $\rightarrow$ `IV7` (The *Dorian Bright IV* chord!) $\rightarrow$ `bVII` $\rightarrow$ `i`.
  * **Melodic Rule:** Arpeggiated 5ths and 9ths (`[0 -> 7 -> 14 -> 10 -> 7]`) with crisp grace-note flicks; leave **30% rest space** between phrases so forest echoes can ring out.
  * **Percussion:** Zero kick/snare kit! Use **shakers, finger cymbals, light frame-drum (*Bodhrán/Duff*) rim taps, and pizzicato cello**.

---

### 2.2 ARCHETYPE: `Adventurous_Cinematic_Frontier` (Wide-Screen Horizon / Discovery)
* **How the Ear Listens:** The ear tracks a **Dual-Speed Engine**: fast, bustling 16th-note string/woodwind *ostinatos* in the mid-range (`400Hz–2kHz`) paired with a **slow, majestic, half-note French Horn melody** (`200Hz–800Hz`) that leaps upward by Perfect 5ths (`0 -> 7`) and Major 6ths (`0 -> 9`).
* **How the Body Feels:** Chest expanding, cresting a mountain ridge to see a vast unknown valley, wind in the face, heroic optimism.
* **Musical Mathematics:**
  * **Meter & Tempo:** `4/4` (with `12/8` triplet string ostinatos) at `116 – 126 BPM`.
  * **Scale:** **Mixolydian** (`[0, 2, 4, 5, 7, 9, 10]`) or **Lydian** (`[0, 2, 4, 6, 7, 9, 11]`).
  * **Chord Engine (The John Williams / Howard Shore Frontier Shift):** `I` $\rightarrow$ `bVII` $\rightarrow$ `IV` $\rightarrow$ `I` (e.g., `C Major -> Bb Major -> F Major -> C Major`) or `I -> II7 (#4) -> IV -> I`.
  * **Melodic Rule:** Start on a pickup beat (`Beat 4`), leap **`0 -> 7` (Perfect 5th)** on `Beat 1`, hold for 2.5 beats, then soar up to `12` (Octave) or `14` (9th).
  * **Percussion:** Orchestral **Timpani** tuned to `Root` and `5th` + rolling orchestral snare on transitions + bright crash cymbals on 8-bar peaks.

---

### 2.3 ARCHETYPE: `Adventurous_HighSeas_Swashbuckler` (Maritime / Pirate / Kinetic)
* **How the Ear Listens:** Locked 100% into a **heavy, lurching `6/8` or `12/8` compound gallop** (mimicking the pitch and roll of a wooden ship deck on ocean waves). The ear craves **aggressive, dry bowed string staccatos (*Spiccato* Cello/Violin)**, accordion/hurdy-gurdy drones, and brass fanfare stabs.
* **How the Body Feels:** Adrenaline, swagger, physical momentum, swinging from ropes, reckless danger.
* **Musical Mathematics:**
  * **Meter & Tempo:** `6/8` or `12/8` at `132 – 148 BPM` (Compound pulse: **`ONE - and - a - TWO - and - a`** with heavy accents on `1`, `3`, `4`, `6` of the 6-grid: `[1.0, 0.0, 0.75, 0.95, 0.0, 0.70]`).
  * **Scale:** **Harmonic Minor** `[0, 2, 3, 5, 7, 8, 11]` alternating with **Aeolian/Natural Minor** `[0, 2, 3, 5, 7, 8, 10]`.
  * **Chord Engine:** `i` $\rightarrow$ `bVII` $\rightarrow$ `bVI` $\rightarrow$ `V7` (The classic *Andalusian/Pirate* cadence: `Dm -> C -> Bb -> A7`).
  * **Melodic Rule:** Rapid triplet runs (`[0, 2, 3, 2, 0, -1, 0]`) punctuated by heavy staccato unison hits on Beat 1 and Beat 4 (in 6/8).

---

### 2.4 ARCHETYPE: `Adventurous_Ancient_Desert_Ruin` (Archaeological / Mirage / Dune)
* **How the Ear Listens:** Listens for **microtonal/augmented-second tension**, dry skin/wood percussion (*Darbuka, Frame Drum, Shaker*), plucked fretless strings (*Oud, Bouzouki*), and **heat-shimmer drones** (`Root + 5th` sustaining continuously while the melody explores above).
* **How the Body Feels:** Heat haze, ancient secrets buried under sand, cautious footsteps, sacred awe.
* **Musical Mathematics:**
  * **Meter & Tempo:** `4/4` (*Malfuf* `3+3+2` pulse) or `7/8` (`2+2+3`) at `95 – 110 BPM`.
  * **Scale:** **Phrygian Dominant (*Hijaz*)** `[0, 1, 4, 5, 7, 8, 10]` or **Double Harmonic (*Mayamalavagowla*)** `[0, 1, 4, 5, 7, 8, 11]`.
  * **Chord Engine:** Static pedal bass on `0` (`Root`) while upper voices shift slowly between `[0, 4, 7]` (`I`) and `[1, 5, 8]` (`bII`).

---

### 2.5 ARCHETYPE: `Adventurous_Cosmic_Odyssey` (Sci-Fi / Zero-Gravity / Interstellar)
* **How the Ear Listens:** Rejects earthy drums! The ear locks onto a **hypnotic, mathematical minimalist film-score arpeggio** (Pipe Organ, Analog Prophet/Moog Synth, Glass Marimba) while massive sub-bass pedals (`35Hz–55Hz`) and shimmering high strings swell in and out like gravitational waves.
* **How the Body Feels:** Weightlessness, insignificance before the cosmos, time dilation, transcendent awe.
* **Musical Mathematics:**
  * **Meter & Tempo:** `3/4` or `12/8` polymeter at `108 – 120 BPM`.
  * **Scale:** **Aeolian / Lydian** bi-modal ambiguity.
  * **Chord Engine (Chromatic Mediant / Interstellar Engine):** `VI Maj7` $\rightarrow$ `v7` $\rightarrow$ `i9` $\rightarrow$ `VII6` (or `Am -> F -> C -> G` with a constant high `E` `[4]` and `B` `[11]` pedal tone ringing inside every single chord!).

---

## 3.0 The "Epic" Ontology (4 Distinct Sub-Archetypes)

> **CRITICAL RULE:** "Epic" is defined by **Apparent Acoustic Mass (Sub-50Hz weight + >8kHz air)** and **Macro-Dynamic Patience**. If everything is fast and loud, nothing feels big. Big things move **slowly** with massive inertia.

---

### 3.1 ARCHETYPE: `Epic_Colossal_Hybrid_Trailer` (Braaam / Titan / Modern Cinema)
* **How the Ear Listens:** Listens for **Extreme Frequency Polarization**—an earth-shattering low-brass/synth **BRAAAM** (`38Hz–180Hz` sawtooth stack with waveshaping distortion) answered by razor-sharp **Metallic Anvil/Taiko Impacts** (`2.5kHz–8kHz`) and a relentless **16th-note Staccato String Ostinato** that climbs 1 semitone higher every 4 bars!
* **How the Body Feels:** Visceral chest compression, goosebumps, impending collision of titans.
* **Musical Mathematics:**
  * **Tempo:** `90 – 110 BPM` (Heavy, deliberate march; subdivided into 16th-note string motors).
  * **Chord Engine:** **Minor Chromatic Mediant**: `i` (`C minor`) $\rightarrow$ `bvi` (`Ab minor`! Notice *minor*, not major—this creates dark, colossal sci-fi/trailer dread!).
  * **Structural Rule — The "Pre-Climax Vacuum":** At Bar 15.5, **cut all audio to -80dB silence for 2 beats** (leaving only a sub-bass reverse-suck sweep), then slam Beat 1 of Bar 17 with maximum amplitude.

---

### 3.2 ARCHETYPE: `Epic_Mythic_Choral_Tragedy` (Soulsborne / Gothic / Apocalyptic)
* **How the Ear Listens:** No synth basses or modern club drums! Dominated by **Operatic Choir Formants (`Aa / Oh / Ee`)**, **Pipe Organ**, **Solo Cello/Violin weeping in the high register**, and ** frantic, irregular orchestral timpani/snare rolls**.
* **How the Body Feels:** Tragic grandeur, fighting a fallen god in a ruined cathedral, sorrow mixed with terror.
* **Musical Mathematics:**
  * **Meter & Tempo:** `3/4` (Dark Waltz) or `4/4` at `125 – 145 BPM`.
  * **Scale:** **Harmonic Minor** `[0, 2, 3, 5, 7, 8, 11]` + **Neapolitan Flat-2 (`bII` = `1`)**.
  * **Chord Engine:** `i` $\rightarrow$ `bII` (Neapolitan Major!) $\rightarrow$ `V7(b9)` $\rightarrow$ `i` (e.g., `Dm -> Eb Major -> A7(b9) -> Dm`).

---

### 3.3 ARCHETYPE: `Epic_Triumphant_Ascension` (Coronation / Victory / Stadium Mass)
* **How the Ear Listens:** Tracks an **unstoppable ascending bassline** (`0 -> 2 -> 4 -> 5 -> 7 -> 9`) while brass horns and high strings play soaring **suspended-4th (`sus4 -> Major 3rd`) resolutions**.
* **How the Body Feels:** Tears of joy, overcoming impossible odds, stadium-sized euphoria.
* **Musical Mathematics:**
  * **Chord Engine (The "Hero's Ascent"):** `vi` $\rightarrow$ `IV` $\rightarrow$ `I(add9)/3rd` $\rightarrow$ `V(sus4 -> 3)`.

---

### 3.4 ARCHETYPE: `Epic_Tribal_War_March` (Primal / Phalanx / Earth-Shaking)
* **How the Ear Listens:** Zero lush chords! Pure **Unison / Octave / Open-Fifth (`[0, 7, 12]`)** low brass, war horns (*Nadaswaram, Conch, Carnyx, Didgeridoo*), throat-singing/warrior chants, and **stacked multi-cultural war drums (*Taiko + Thavil + Urumi + Frame Drums*)**.
* **How the Body Feels:** Primal rage, fearless unity, adrenaline surge.

---

## 4.0 The "Electronic" Ontology (5 Distinct Sub-Archetypes)

> **CRITICAL RULE:** "Electronic" is not a single genre—it is a set of distinct **Groove-to-Spectrum Contracts**. A Berlin Techno listener will reject a bright EDM SuperSaw melody; a Progressive House listener will feel bored by a static 1-note techno loop.

| Sub-Archetype | BPM & Meter | Bass & Kick Physics | Melodic & Harmonic Density | Signature Psychoacoustic Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **4.1 `Electronic_Hypnotic_Warehouse`** *(Berlin Minimal / Techno)* | `132–142 BPM` (`4/4`) | **Rumble Kick** (`52Hz` dry kick + sidechained distorted reverb tail). No melodic bassline! | **Zero Chords!** 1- or 2-note polymetric (`3/16` or `5/16` loop length against `16/16` bar) FM/Acid synth sequence in Phrygian `[0, 1, 7]`. | Slowly sweeping a resonant lowpass filter (`300Hz -> 3.5kHz`) over 32 bars while keeping the groove locked in concrete. |
| **4.2 `Electronic_Euphoric_Festival`** *(Prog House / Melodic Trance)* | `126–130 BPM` (`4/4`) | Tight, short `65Hz` kick + rolling 16th-note sawtooth bass ducked `85%` by sidechain pump. | **7-Voice Stereo SuperSaw Chords** (`vi -> IV -> I -> V` or `i -> bVI -> bIII -> bVII`) + soaring octave-doubled lead hook. | White-noise risers + snare acceleration (`8th -> 16th -> 32nd`) exploding into a wide stereo chord drop. |
| **4.3 `Electronic_Cyberpunk_Midtempo`** *(Dystopian / Gesaffelstein / Rezz)* | `95–105 BPM` (`4/4`) | Heavy, dry punchy kick + **Heavily Wave-Folded / Bit-Crushed Sawtooth Bass** (`45Hz` sub + `1.5kHz` nasty metallic buzz) playing syncopated `16th-note` triplet stabs. | Dark **Locrian / Phrygian** `[0, 1, 3, 6]` single-note brassy siren leads. No happy major chords! | Sudden `16th-note` digital silence gates (chopping all audio to `0.0` between bass stabs for mechanical aggression). |
| **4.4 `Electronic_Organic_Deep_Sunset`** *(Anjunadeep / Tulum / Afro-Melodic)* | `118–122 BPM` (`4/4` with `12/8` percussion) | Warm, rounded `58Hz` sine kick (soft attack!) + deep, smooth Moog sub-bass playing sustained `m9` root notes. | Lush, low-passed **Minor 9th (`[0, 3, 7, 10, 14]`)** warm Juno pads + plucked wooden marimba/kalimba/oud arpeggios with long tape delay. | Panned organic shakers, woodblocks, breathy vocal `"Oooo"` pads, and vinyl/rain/desert-wind ambience. |
| **4.5 `Electronic_Neuro_Kinetic_Bass`** *(Drum & Bass / Liquid / Neurofunk)* | `172–176 BPM` (`4/4` Two-Step Break) | Kick on Step `0` & `10`; Snare on Step `4` & `12` (`200Hz` fundamental pop) + **Reese Bass** (detuned phasing sawtooths with moving notch filters). | Either ultra-lush Jazz/Soul Rhodes `m11` chords (*Liquid DnB*) OR dark sci-fi pitch-gliding bass growls (*Neurofunk*). | High-speed `174 BPM` breakbeat energy contrasted against slow, floating half-time chord pads (`87 BPM` harmonic feel). |

---

## 5.0 The "Pop" Ontology (4 Distinct Sub-Archetypes)

> **CRITICAL RULE:** Modern Pop is **Vocal-Centric & Pocket-Driven**. The instruments must leave a carved spectral pocket at `1kHz–3.5kHz` and rely on **syncopated bass-to-kick interplay** rather than cluttered wall-of-sound arrangements.

| Sub-Archetype | BPM & Groove Pocket | Harmonic Palette | Arrangement & Timbral Signature |
| :--- | :--- | :--- | :--- |
| **5.1 `Pop_MaxMartin_Pocket_Drive`** *(Dua Lipa / Weeknd / Radio Pop)* | `114–122 BPM`. Tight `4/4` kick + **Syncopated Pluck/Slap Bass** hitting `Steps 0, 3, 6, 10, 14` with crisp `16th-note` mute gaps! | **Dorian (`i7 - IV7`)** or **Minor Pop (`i - bVI - bVII - v`)**—never cheesy nursery-rhyme Major! | **Pre-Chorus Subtraction:** Strip out the kick drum for 4 bars before the chorus, then drop a massive stereo bass + tight clap on Beat 1 of the Chorus. |
| **5.2 `Pop_Dreamy_Nostalgic_Synth`** *(Midnight 80s / Dream-Pop / Indie)* | `100–110 BPM`. Straight 8th-note driving bassline (`[1,1,1,1,1,1,1,1]`) + 80s Gated Reverb Snare on `2` & `4`. | **Lydian / Major 7th & Add9 Voicings** (`IVMaj7 -> V6 -> I(add9) -> vi7`). | Chorus-drenched Juno-106 pads (`0.6Hz` stereo pitch wobble), shimmering electric guitar arpeggios, bittersweet nostalgia. |
| **5.3 `Pop_Bedroom_Intimate_Whisper`** *(Billie Eilish / Finneas / Alt-Pop)* | `75–95 BPM` (or `120 BPM` minimal). **Bone-dry, close-mic acoustics** (zero hall reverb!). | Dark Minor + **Resolved/Unresolved Diminished/Harmonic Minor `V7` chord** (`i -> iv -> V7 -> i`). | Deep, clean sub-bass (`45Hz` pure sine) + finger snaps / rim clicks + whispered vocal hum (`200ms` away from the ear) with high breath noise. |
| **5.4 `Pop_Sunshine_Funk_NuDisco`** *(Bruno Mars / Daft Punk / Parcels)* | `110–118 BPM`. Heavy `16th-note` swing (`57%`) with a loud kick+bass hit on **Beat 1 ("The One")** and ghost-snare syncopation. | **Jazz-Funk Extended Chords:** `ii9` $\rightarrow$ `V13` $\rightarrow$ `IMaj9` $\rightarrow$ `VI7(#9)`. | Clean Nile Rodgers-style 16th-note Stratocaster guitar chucks (`1.5kHz–3.5kHz`) + envelope-filtered synth/slap bass + tight brass section stabs. |

---

## 6.0 The "Celtic" Ontology (4 Distinct Sub-Archetypes)

> **CRITICAL RULE:** "Celtic" has 4 completely different emotional worlds—do not play a fast Tavern Reel when the prompt asks for a Misty Highland Lament or an Enchanted Fae Forest!

| Sub-Archetype | Meter & Tempo | Scale & Ornamentation | Core Instrument Physics & Feel |
| :--- | :--- | :--- | :--- |
| **6.1 `Celtic_Tavern_Reel_Frenzy`** *(Pub Session / Dance)* | `4/4` Reel (`116 BPM` continuous 8th-notes) OR `6/8` Double Jig (`126 BPM` with `38%-28%-34%` lilt). | **D Dorian** `[0, 2, 3, 5, 7, 9, 10]` or **G Mixolydian** `[0, 2, 4, 5, 7, 9, 10]`. Zero vibrato—use **5-part Long Rolls & Cuts**! | **Fiddle + Tin Whistle + Accordion** playing in tight heterophonic unison, backed by a driving **Bodhrán** tipper roll and acoustic guitar `DADGAD` strumming. |
| **6.2 `Celtic_Misty_Highland_Lament`** *(Slow Air / Sean-nós / Cliffside)* | **Beatless / Free Rubato** or slow `3/4` at `62 BPM`. | **Pentatonic Gap Scale** `[0, 2, 4, 7, 9]` or **Aeolian** `[0, 2, 3, 5, 7, 8, 10]`. Slow `4.5Hz` weeping vibrato + `60ms` upward pitch scoops. | Solo **Uilleann Pipes** or **Low Whistle** + **Celtic *Caoineadh* (Keening Vocal Hum)** over a single low `DADGAD` guitar/drone chord `[0, 7, 12, 14]` with 4-second cliffside reverb. |
| **6.3 `Celtic_Fae_Woodland_SlipJig`** *(Enchanted / Elven / Mythic)* | **`9/8` Slip Jig** (`3 + 3 + 3` leaping triplet meter at `120 BPM`). | **Lydian** `[0, 2, 4, 6, 7, 9, 11]` or **Dorian** `[0, 2, 3, 5, 7, 9, 10]`. | **Celtic Lever Harp (*Cláirseach*)** playing cascading 9/8 arpeggios + breathy **Wooden Flute** + soft finger-cymbal/bell sparkles. |
| **6.4 `Celtic_Highland_Battle_Charge`** *(Scottish Clan / Braveheart / Fierce)* | `4/4` or `6/8` War March (`118–132 BPM`). | **A Mixolydian (Highland Bagpipe Scale)** rocking between **A Major `[0, 4, 7]`** and **G Major `[-2, 2, 5]`** (The *Double-Tonic Shift*!). | **Great Highland Bagpipe** (piercing nasal chanter + 3 roaring bass/tenor drones) + **Scottish *Scotch Snap* (`16th-Dotted-8th`)** snare corps + booming war drums. |

---

## 7.0 Agent Decision Matrix & Python Parameter Schema

An AI Agent or Python script can directly load and execute this dictionary to configure its **Scale, Rhythm Grid, Chord Progression, Melodic Leap Profile, and Spectral/Spatial DSP** for any requested genre + sub-feel:

\`\`\`python
# MASTER AI-AGENT GENRE & SUB-FEEL CONFIGURATION SCHEMA
GENRE_FEEL_ENGINE_DB = {
    # ================= ADVENTUROUS SUB-ARCHETYPES =================
    "adventurous_forest_mystic": {
        "bpm": 104,
        "meter_steps": 12, # 6/8 or 3/4 compound feel
        "scale_semitones": [0, 2, 3, 5, 7, 9, 10], # Dorian (with #4=6 & Maj3=4 borrowed on IV chord!)
        "chord_progression": [[0, 3, 7, 14], [5, 9, 12, 16], [10, 14, 17, 21], [0, 3, 7, 14]], # i9 -> IV -> bVII -> i9
        "melody_leap_weights": {1: 0.25, 2: 0.30, 5: 0.20, 7: 0.20, 12: 0.05}, # Favors open 4ths/5ths & steps
        "rest_probability": 0.32, # High breathing space for forest echoes
        "kick_weight": 0.15,      # No heavy club kick! Light woody frame-drum pulse
        "reverb_decay_sec": 2.8,
        "lead_timbre": "wooden_flute_plus_celesta_harp",
    },
    "adventurous_cinematic_frontier": {
        "bpm": 122,
        "meter_steps": 12, # 4/4 with 12/8 triplet string ostinato
        "scale_semitones": [0, 2, 4, 5, 7, 9, 10], # Mixolydian heroic horizon scale
        "chord_progression": [[0, 4, 7, 12], [10, 14, 17, 22], [5, 9, 12, 17], [0, 4, 7, 12]], # I -> bVII -> IV -> I
        "melody_leap_weights": {2: 0.25, 5: 0.25, 7: 0.35, 9: 0.10, 12: 0.05}, # Strong Perfect-5th (7) heroic leaps!
        "rest_probability": 0.18,
        "kick_weight": 0.65,      # Orchestral Timpani on Root & 5th
        "reverb_decay_sec": 3.4,
        "lead_timbre": "french_horn_octet_plus_spiccato_strings",
    },
    "adventurous_highseas_swashbuckler": {
        "bpm": 140,
        "meter_steps": 12, # 6/8 Pirate Gallop: [1, 0, 1, 1, 0, 1 | 1, 0, 1, 1, 0, 1]
        "rhythm_accent_grid": [1.0, 0.0, 0.75, 0.95, 0.0, 0.70, 0.95, 0.0, 0.75, 0.90, 0.0, 0.80],
        "scale_semitones": [0, 2, 3, 5, 7, 8, 11], # Harmonic Minor
        "chord_progression": [[0, 3, 7], [10, 14, 17], [8, 12, 15], [7, 11, 14]], # i -> bVII -> bVI -> V7
        "melody_leap_weights": {1: 0.35, 2: 0.35, 3: 0.15, 7: 0.15}, # Fast scalar triplet runs
        "rest_probability": 0.10,
        "kick_weight": 0.85,
        "reverb_decay_sec": 1.4,  # Tighter, punchy wooden ship-deck room acoustics
        "lead_timbre": "aggressive_spiccato_cello_violin_plus_accordion",
    },

    # ================= EPIC SUB-ARCHETYPES =================
    "epic_colossal_hybrid_trailer": {
        "bpm": 98,
        "meter_steps": 16,
        "scale_semitones": [0, 2, 3, 5, 7, 8, 11],
        "chord_progression": [[-12, 0, 3, 7], [-4, 8, 11, 15], [-12, 0, 3, 7], [-5, 7, 11, 14]], # i -> bvi (Dark Minor Mediant!)
        "melody_leap_weights": {1: 0.40, 3: 0.25, 7: 0.25, 12: 0.10},
        "rest_probability": 0.25, # Massive pauses between BRAAAM impacts
        "kick_weight": 1.00,      # Sub-45Hz seismic drop + Taiko/Anvil crack
        "reverb_decay_sec": 4.2,
        "lead_timbre": "distorted_low_brass_braaam_plus_staccato_strings",
    },
    "epic_mythic_choral_tragedy": {
        "bpm": 132,
        "meter_steps": 12, # 3/4 Dark Cathedral Waltz
        "scale_semitones": [0, 1, 3, 5, 7, 8, 11], # Neapolitan Harmonic Minor (includes b2=1 AND Maj7=11!)
        "chord_progression": [[0, 3, 7], [1, 5, 8], [7, 11, 14, 15], [0, 3, 7]], # i -> bII (Neapolitan!) -> V7(b9) -> i
        "melody_leap_weights": {1: 0.35, 2: 0.20, 6: 0.15, 8: 0.20, 12: 0.10}, # Tragic Minor-6th (8) & Tritone (6) leaps
        "rest_probability": 0.15,
        "kick_weight": 0.80,
        "reverb_decay_sec": 4.8,  # Huge Gothic cathedral reverb
        "lead_timbre": "operatic_formant_choir_plus_pipe_organ_and_solo_cello",
    },

    # ================= ELECTRONIC SUB-ARCHETYPES =================
    "electronic_hypnotic_warehouse": {
        "bpm": 136,
        "meter_steps": 16,
        "scale_semitones": [0, 1, 5, 7, 8], # Dark Phrygian/Minimal subset
        "chord_progression": [[0, 7]],      # Static single-root drone/rumble! Zero pop chord changes!
        "polymetric_loop_steps": 6,         # 6-step synth pattern looping over 16-step kick grid (Polyrhythm!)
        "kick_weight": 1.00,                # Berlin Rumble Kick
        "reverb_decay_sec": 2.2,
        "lead_timbre": "resonant_fm_acid_sequence_with_slow_filter_sweep",
    },
    "electronic_organic_deep_sunset": {
        "bpm": 120,
        "meter_steps": 16,
        "scale_semitones": [0, 2, 3, 5, 7, 9, 10], # Dorian Deep House
        "chord_progression": [[0, 3, 7, 10, 14], [5, 9, 12, 16, 19], [3, 7, 10, 14, 17], [10, 14, 17, 21]], # m9 -> IVmaj9
        "melody_leap_weights": {2: 0.30, 3: 0.30, 5: 0.25, 7: 0.15},
        "rest_probability": 0.35,
        "kick_weight": 0.70, # Warm, soft-attack 58Hz sine kick
        "reverb_decay_sec": 3.6,
        "lead_timbre": "plucked_marimba_oud_plus_arabic_oooo_vocal_pad",
    },

    # ================= POP SUB-ARCHETYPES =================
    "pop_maxmartin_pocket_drive": {
        "bpm": 118,
        "meter_steps": 16,
        "bass_syncopation_grid": [1, 0, 0, 1,  0, 0, 1, 0,  0, 0, 1, 0,  0, 1, 1, 0], # Tight muted funk-pop bass
        "scale_semitones": [0, 2, 3, 5, 7, 9, 10],
        "chord_progression": [[0, 3, 7, 10], [3, 7, 10, 14], [5, 9, 12, 16], [7, 10, 14, 17]],
        "melody_leap_weights": {1: 0.30, 2: 0.40, 3: 0.20, 5: 0.10}, # Catchy, repetitive hook intervals
        "rest_probability": 0.22,
        "kick_weight": 0.85,
        "reverb_decay_sec": 0.9, # Ultra-clean, dry, punchy radio mix!
        "lead_timbre": "crisp_vocal_formant_synth_plus_funk_guitar_chucks",
    },

    # ================= CELTIC SUB-ARCHETYPES =================
    "celtic_fae_woodland_slipjig": {
        "bpm": 120,
        "meter_steps": 9, # 9/8 Slip Jig (3 + 3 + 3)!
        "rhythm_accent_grid": [1.0, 0.3, 0.6,  0.85, 0.3, 0.6,  0.90, 0.4, 0.7],
        "scale_semitones": [0, 2, 4, 6, 7, 9, 11], # Lydian Enchanted Mode
        "chord_progression": [[0, 4, 7, 11], [2, 6, 9, 13], [0, 4, 7, 14], [7, 11, 14, 18]],
        "melody_leap_weights": {2: 0.35, 4: 0.25, 5: 0.20, 7: 0.20},
        "rest_probability": 0.15,
        "kick_weight": 0.20, # Soft Bodhran finger pulse only
        "reverb_decay_sec": 2.9,
        "lead_timbre": "celtic_lever_harp_plus_wooden_flute_with_rolls",
    }
}
\`\`\`

---

## 8.0 How Your AI Agent Should Route Prompts Using This Ontology

When a user prompts your Python music agent:
1. **Parse the Primary Genre + Secondary Environment/Feel Modifier:**
   * *Example Prompt:* `"Create an adventurous track in a magical forest"` $\rightarrow$ Do **NOT** load `128 BPM 4/4 drums`. Route to `adventurous_forest_mystic` (`6/8` or `3/4`, Dorian/Lydian `IV` chord, `kick_weight=0.15`, Harp/Celesta/Flute).
   * *Example Prompt:* `"Create an adventurous pirate battle"` $\rightarrow$ Route to `adventurous_highseas_swashbuckler` (`140 BPM 6/8` gallop, Harmonic Minor `i -> bVII -> bVI -> V7`, Spiccato Cello/Violin).
   * *Example Prompt:* `"Create an electronic track for a dark club"` $\rightarrow$ Route to `electronic_hypnotic_warehouse` (`136 BPM`, Berlin Rumble Kick, 6-step over 16-step polymetric loop, zero pop chord changes).
2. **Enforce the 5 Orthogonal Axes:**
   * Apply the archetype's exact `meter_steps`, `chord_progression`, `melody_leap_weights`, `rest_probability`, and `reverb_decay_sec` before generating a single sample of audio.