---
id: western
title: Western harmony, film and trailer conventions
domain: culture
status: unverified
sources: []
used_by: [AGENTS.md]
updated: 2026-11-04
---

> **Not verified.** These values are a starting point from practice, not a measurement.
> Cite a source before presenting one as established, and say "starting value" when a piece uses one.

# Western harmony, film and trailer conventions

## 1. Core Psychoacoustics: How the "Western Ear" Listens

Unlike Tamil (*Raga/Gamaka*), Arabic (*Maqam/Heterophony*), or African (*Polyrhythmic Timeline/Speech-Tone*) music, the Western ear is conditioned over 1,000 years around **Vertical Functional Harmony, Counterpoint, and 12-Tone Equal Temperament (12-TET)**:

| Perceptual Dimension | Non-Western Ear Conditioning | Western Ear Conditioning | Algorithmic / Python DSP Rule |
| :--- | :--- | :--- | :--- |
| **Pitch Grid** | Continuous microtonal curves (*Gamaka*), neutral 3rds (*Sikah*), or stretched heptatonics. | **12-TET Quantization ($2^{n/12}$):** Every semitone is exactly `100.0 cents`. Deviations $>15$ cents on chordal instruments sound "out of tune." | Keep chordal pads, pianos, and guitars strictly locked to $f = 440 \times 2^{(m-69)/12}$, using subtle detuning (`±4 to 8 cents`) only for stereo chorus width. |
| **Emotional Engine** | Modal tension against a static drone (*Sruti*) or rhythmic trance accumulation. | **Harmonic Tension & Resolution (Functional Harmony):** Emotion is driven by **Predominant $\rightarrow$ Dominant ($V^7$) $\rightarrow$ Tonic ($I$)** cadences and the resolution of the **Tritone** (`6 semitones`). | Build a Markov-chain or state-machine chord engine where chords move by descending 5ths ($vi \rightarrow ii \rightarrow V^7 \rightarrow I$) and leading tones (`scale degree 11`) resolve up by `+1` semitone to `12` (`Root`). |
| **Voice Leading** | Parallel octaves/unisons (heterophony) are prized for power. | **Independent Voice Leading & Contrary Motion:** Parallel 5ths and octaves between bass and melody weaken harmonic richness. Bass moves opposite to the melody. | When the melody ascends, step the bassline downward (Contrary Motion). Keep inner chord voices moving by the **shortest possible semitone distance** ($\le 2$ semitones) between chord changes. |
| **Dynamic Architecture** | Gradual rhythmic acceleration or continuous high-energy street festival density. | **Macro-Dynamic Contrast & "The Drop":** Dramatic shifts between quiet, sparse sections (*Piano / Verse*) and massive full-spectrum walls of sound (*Fortissimo / Chorus / Drop*). | Automate both ** spectral cutoff frequency** (`Lowpass 400Hz -> 18kHz`) and **voice count** across 8- or 16-bar boundaries. |

## 2. The Classical Evolution (Medieval & Renaissance $\rightarrow$ 20th Century)

### 2.1 Medieval & Renaissance (900–1600 AD) — *Modal Purity & Polyphony*
* **How the Ear Listens:** Floating, beatless, reverberant vocal/string spaces using **Gregorian Modes** (*Dorian, Phrygian, Lydian, Mixolydian*) and **Open Fifths ($1 : 1.5$ frequency ratio)** without 3rds.
* **Algorithmic Rules:**
  * **Organum & Drone:** Sustain bare `[0, 7, 12]` (Root, 5th, Octave) intervals with a long `3.5-second` cathedral convolution/Schroeder reverb tail.
  * **Imitative Counterpoint (Palestrina Style):** Voice 2 enters 2 bars after Voice 1 with the exact same melody transposed up a 5th (`+7 semitones`), moving mostly stepwise (`1–2 semitones`), following every large leap (`>4 semitones`) with stepwise motion in the opposite direction.

### 2.2 The Baroque era (1600–1750)
* **Cultural & Mathematical DNA:** The birth of **Equal Temperament** and **Counterpoint (Fugue & Canon)**. Music operates like an intricate mechanical clock.
* **How the Ear Listens:** Tracks **2 to 4 independent melodic lines simultaneously** (Soprano, Alto, Tenor, Bass) locked to a continuous chugging 8th- or 16th-note pulse (**Basso Continuo**).
* **Algorithmic Rules for Python:**
  1. **The circle-of-fifths sequence:** Cycle roots through `[0, 5, 11, 4, 9, 2, 7, 0]` (`i -> iv -> VII -> III -> VI -> ii° -> V7 -> i` in Harmonic Minor) while running continuous 16th-note arpeggios (`[Root, 3rd, 5th, 3rd]`).
  2. **The *Picardy Third* (*Tierce de Picardie*):** Run the entire piece in a dark Minor key (`[0, 2, 3, 5, 7, 8, 11]`), and on the **final held chord**, raise the minor 3rd (`3`) to a **Major 3rd (`4`)** for a blindingly radiant resolution!
  3. **Harpsichord DSP:** Plucked string (Karplus-Strong) with **zero velocity sensitivity** (fixed amplitude regardless of note force) + a sharp `2.5kHz` plectrum click on both note-on and note-off.

### 2.3 The Classical era (1750–1820)
* **How the Ear Listens:** Rejects dense Baroque polyphony in favor of **crystal-clear melody over accompaniment (*Homophony*)**, symmetry (`4-bar Question + 4-bar Answer`), and **Sonata Form** (Exposition $\rightarrow$ Development $\rightarrow$ Recapitulation).
* **The *Alberti Bass* (Algorithmic Left-Hand Accompaniment):**
  * Instead of block chords, arpeggiate every chord in 16th notes using the pattern: **`[Lowest, Highest, Middle, Highest]`** (e.g., `[0, 7, 4, 7]` in semitones).

### 2.4 The Romantic and late-Romantic era (1820–1910)
* **How the Ear Listens:** Yearns for **emotional extremes, tempo elasticity (*Rubato*), lush chromaticism, and massive orchestral color**. (the ancestor of **Hollywood film scores** and **Tamil film orchestral arrangements**).
* **Algorithmic Rules:**
  1. **Tempo *Rubato* (Elastic Time Curve):** Modulate the global clock/BPM using a slow sine wave ($\pm 8\%$ speed variation over 4 bars)—speeding up slightly as melody pitch rises (*Stringendo*) and slowing down at phrase peaks (*Ritardando*).
  2. **Chromatic Mediants (The "Epic Cinema" Chord Shift):** Move directly from a **C Minor** chord `[0, 3, 7]` to **Ab Major** `[8, 0, 3]` or **E Minor** `[4, 7, 11]` (roots a 3rd apart sharing 1 common tone). This instantly triggers awe, magic, or tragedy in the human brain.
  3. **Impressionism:** Use the **Whole-Tone Scale** `[0, 2, 4, 6, 8, 10]` (zero half-steps, floating/dreamlike) and parallel **Major 9th chords** `[0, 4, 7, 11, 14]`.

## 3. The African-American & 20th-Century Groove Revolution

Modern Western popular music was born when West African rhythmic and microtonal sensibilities collided with European harmonic instruments in the Americas:

### 3.1 The Blues & Gospel (The Soul of Modern Music)
* **The Psychoacoustic Secret — "The Blue Notes":**
  * Western pianos only have Minor 3rd (`300 cents`) and Major 3rd (`400 cents`). The Blues lives in the **crack between the keys** (`~330 to 365 cents`), along with the **flattened 5th (`600 cents`)** and **flattened 7th (`1000 cents`)**.
* **DSP Implementation:** On guitar, harmonica, or synth leads, never play the Major 3rd cleanly—start on the Minor 3rd (`3`) and **bend upward by `+40 to +80 cents`**.
* **The 12-Bar Blues Matrix (Bar-by-Bar Root Progression):**
  * `[I7, I7, I7, I7 | IV7, IV7, I7, I7 | V7, IV7, I7, V7]` (Every chord is a **Dominant 7th `[0, 4, 7, 10]`**, defying classical theory where only the V chord can be a Dominant 7th!).

### 3.2 Jazz (Swing, Bebop, Modal Jazz, Neo-Soul)
* **How the Jazz Ear Listens:** Listens for **Upper-Structure Chord Extensions** (`9ths, 11ths, 13ths, #9, b13`), **ii–V–I Voice Leading**, and **Swung 8th Notes**.
* **The Mathematical Swing Ratio:**
  * In straight 8th notes, a beat is split `50% / 50%` (`1.0 : 1.0`).
  * In **Medium Jazz Swing**, split the beat between **`60% / 40%` (`1.5 : 1.0`) and `66.6% / 33.3%` (`2.0 : 1.0` triplet feel)**, and **accent the off-beat (the second 8th note)** rather than the downbeat!
* **The "ii – V – I" Shell Voicing Algorithm:**
  * Drop the 5th of the chord and keep only the **Root, 3rd, 7th, and 9th** (Guide Tones):
    * **Dm9 (`ii`):** `Root=D [2], b3=F [5], b7=C [12], 9=E [16]`
    * **G13 (`V7`):** `Root=G [7], 7=F [5], 3=B [11], 13=E [16]` *(Notice only `F->F` stays and `C->B` moves by 1 semitone!)*
    * **CMaj9 (`I`):** `Root=C [0], 3=E [4], 7=B [11], 9=D [14]`

### 3.3 Funk, Soul & Disco (1960s–1970s — *James Brown, Parliament, Chic*)
* **The Rule of "The One":** Hit Beat `1` of every bar with maximum bass and kick weight, then make the remaining 15 sixteenth-notes a hyper-syncopated conversation between **ghost-note snare hits**, **16th-note muted "chuck" guitar scratches**, and **slap-bass octave pops**.
* **DSP — Clavinet & Slap Bass:**
  * Filter a sawtooth wave through an **Envelope Follower (Auto-Wah)**: the harder the note velocity, the higher a resonant bandpass filter sweeps (`300Hz -> 2.8kHz` over `60ms`).

### 3.4 Rock, Punk & Heavy Metal (1950s–Present)
* **Psychoacoustic Engine:** **Non-Linear Harmonic Distortion (Wave-Shaping)** and **Power Chords**.
* **Why Distortion Needs Power Chords (`[0, 7, 12]`):**
  * When you pass a full Major (`[0, 4, 7]`) or Minor (`[0, 3, 7]`) triad through heavy overdrive (`np.tanh(5.0 * x)`), **intermodulation distortion** creates difference tones ($f_2 - f_1$) that clash dissonantly with the 3rd!
  * Removing the 3rd leaves only the **Root, Fifth, and Octave (`[0, 7, 12]`)**, whose difference tones reinforce the fundamental sub-octave, creating a massive, clean wall of heavy guitar power.
* **Palm-Muting (*Djent / Metal Chug*):** Shorten the string decay to `45ms`, boost `110Hz–180Hz` by `+6dB` (cabinet resonance), and low-pass at `2.2kHz` on rhythmic 16th-note chugs, opening the filter to `6kHz` on accented open chords.

## 4. Modern Electronic, Hip-Hop & 21st-Century Pop (1980s–2026)

### 4.1 Hip-Hop: Boom-Bap, J-Dilla Quintuplet Swing, Trap & UK Drill
1. **90s Boom-Bap & Neo-Soul ("Drunken" J-Dilla Micro-Timing):**
   * Turn off grid quantization! Push the **Kick slightly late (`+8ms to +15ms`)** on occasional beats, pull the **Snare slightly early (`-10ms`) or late (`+12ms`)**, and space hi-hats using a **5-tuple (quintuplet) swing ratio (`58% / 42%`)**.
2. **Modern Trap (`135–160 BPM` Half-Time Feel):**
   * **Snare / Clap:** Hits on **Beat 3** of a 4/4 bar (giving a slow `70 BPM` half-time head-nod while hi-hats run at double-time `140 BPM`).
   * **Hi-Hat Rolls:** Rapidly subdivide single 8th-note steps into **32nd-note (`4x`), 64th-note (`8x`), and triplet (`3x` / `6x`) ratchets** with downward pitch steps (`0 -> -2 -> -4` semitones).
3. **UK / NY Drill (`140–144 BPM`):**
   * **The Drill Hi-Hat Pattern (16-step):** `[1, 0, 0, 1,  0, 0, 1, 0,  0, 1, 0, 0,  1, 0, 1, 0]` (`3 + 3 + 3 + 3 + 2 + 2` — identical to the tresillo/comparsa pulse!).
   * **Sliding 808 Bass:** Sub-bass sine/triangle wave (`45Hz–75Hz`) that jumps up **`+12` or `+19` semitones** at the end of a bar with a `60ms` portamento pitch-glide.

### 4.2 House, Techno, Trance & UK Garage / DnB
* **House & Techno (`122–135 BPM`):**
  * **Four-on-the-Floor Kick:** Steps `0, 4, 8, 12`.
  * **Off-Beat Open Hi-Hat:** Steps `2, 6, 10, 14` (`and` of every beat).
  * **Sidechain Compression (The "Pumping" Psychoacoustic Effect):** Every time the Kick triggers (`steps 0, 4, 8, 12`), duck the volume of all synths, bass, and reverb tails by `-12dB` using an envelope `1.0 - np.exp(-t / 0.090)` so the room appears to "breathe" in time with the kick!
* **Acid Techno (Roland TB-303 Engine):** Single sawtooth/square oscillator into a **18dB/24dB resonant lowpass ladder filter** (`Q = 8.0 to 15.0`) with an accent circuit that spikes both filter cutoff and resonance on accented 16th-note slides.
* **Drum & Bass / Jungle (`170–176 BPM`):**
  * **The *Amen / 2-Step* Break:** Kick on Step `0` and Step `10` (`1` and `and-of-3`); Snare on Step `4` and Step `12` (`2` and `4`), layered over a heavily distorted, LFO-modulated **Reese Bass** (two detuned sawtooth waves beating against each other at `45Hz–90Hz`).

### 4.3 Synthwave, cyberpunk and modern pop
* **80s Synthwave / Retrowave:**
  * **Gated Reverb Snare:** Feed a punchy snare into a dense room reverb (`400ms`), then apply a **hard noise gate** that chops the reverb tail completely off to `0.0` at `t = 220ms`.
  * **Arpeggiated Juno Bass:** Continuous 16th-note sawtooth bassline (`[0, 0, 12, 0, 0, 0, 12, 0]`) passed through a warm chorus effect (`0.8Hz` delay-line LFO).

## 5. Pure-Python DSP & Algorithmic Parameter Cheat Sheet

Drop these building blocks directly into your Python synthesis engine for instant Western harmonic, timbral, and rhythmic capabilities:

### 5.1 Supersaw stadium lead and pad
\`\`\`python
import numpy as np

def synth_supersaw(f0: float, duration_sec: float, sr: int = 44100) -> tuple[np.ndarray, np.ndarray]:
    """
    Synthesizes the iconic 7-oscillator Roland JP-8000 style Stereo SuperSaw.
    Returns (left_channel, right_channel) with wide stereo phase & detune spread.
    """
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # 7 classic detune offsets in cents
    detune_cents = np.array([-38.0, -22.0, -10.0, 0.0, +10.0, +22.0, +38.0])
    gains        = np.array([ 0.35,   0.55,   0.75, 1.0,  0.75,  0.55,  0.35])
    pans         = np.array([-0.9,   +0.7,   -0.4,  0.0, +0.4,  -0.7,  +0.9]) # Stereo spread

    left = np.zeros_like(t)
    right = np.zeros_like(t)

    for cents, gain, pan in zip(detune_cents, gains, pans):
        freq = f0 * (2.0 ** (cents / 1200.0))
        # Random initial phase prevents harsh laser-zap transient on attack!
        phase_offset = np.random.uniform(0, 1.0)
        saw = 2.0 * ((t * freq + phase_offset) % 1.0) - 1.0

        # Constant-power stereo panning
        angle = (pan + 1.0) * (np.pi / 4.0)
        left  += saw * gain * np.cos(angle)
        right += saw * gain * np.sin(angle)

    return left * 0.35, right * 0.35
\`\`\`

### 5.2 Sidechain "Pumping" Envelope Generator
\`\`\`python
def apply_sidechain_pump(signal: np.ndarray, kick_trigger_times: list[float], sr: int = 44100, release_sec: float = 0.14, depth: float = 0.85) -> np.ndarray:
    """
    Ducks the input audio signal every time a kick drum hits, creating the signature
    modern EDM / Pop / Hip-Hop rhythmic 'pumping' effect.
    """
    gain_env = np.ones(len(signal), dtype=np.float64)
    release_samples = int(release_sec * sr)
    recovery_curve = 1.0 - depth * np.exp(-np.linspace(0, 5.0, release_samples))

    for t_kick in kick_trigger_times:
        idx = int(t_kick * sr)
        end_idx = min(idx + release_samples, len(signal))
        seg_len = end_idx - idx
        if seg_len > 0:
            gain_env[idx:end_idx] = np.minimum(gain_env[idx:end_idx], recovery_curve[:seg_len])

    return signal * gain_env
\`\`\`

### 5.3 Western Harmonic Chord Voicing Dictionary (Semitone Offsets)
\`\`\`python
WESTERN_CHORD_VOICINGS = {
    # Classical & Pop Triads / 7ths
    "major_triad":      [0, 4, 7],
    "minor_triad":      [0, 3, 7],
    "dominant_7":       [0, 4, 7, 10],
    "diminished_7":     [0, 3, 6, 9],         # High-tension Baroque/Cinema suspense chord
    # Jazz / Neo-Soul / Lo-Fi Lush Voicings
    "maj9_lush":        [0, 4, 7, 11, 14],
    "min9_neosoul":     [0, 3, 7, 10, 14],
    "min11_amapiano":   [0, 3, 7, 10, 14, 17],
    "dom13_jazz":       [0, 4, 10, 14, 21],   # Root, 3rd, b7, 9th, 13th (No 5th)
    "hendrix_7sharp9":  [0, 4, 10, 15],       # Blues/Funk/Rock 'Purple Haze' chord
    # Rock / Metal / Cinematic
    "power_chord_5th":  [0, 7, 12],           # Safe for heavy tanh/clipping distortion!
    "cinematic_sus2": [-12, 0, 2, 7, 12],   # Wide cinematic brass/string stack
}
\`\`\`

### 5.4 Western Genre Drum & Groove Matrices (16-Step 4/4 Grids)
\`\`\`python
WESTERN_GROOVES_16 = {
    # 1. 90s BOOM-BAP / J-DILLA (Notice the 'drunken' micro_shift_ms on kick and snare!)
    "hiphop_boombap_16": {
        "kick":           [1, 0, 0, 0,  0, 0, 0, 1,  0, 0, 1, 0,  0, 0, 0, 0],
        "snare":          [0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0],
        "hihat":          [1, 0, 1, 0,  1, 0, 1, 0,  1, 0, 1, 0,  1, 0, 1, 1],
        "micro_shift_ms": [0, 0, +14,0, -9,0, +16,11,0, 0, +12,0, -8,0, +15,-12]
    },
    # 2. UK DRILL / NY DRILL (142 BPM — Tresillo Hi-Hats + Delayed Snare on Step 6 & 12!)
    "uk_drill_16": {
        "kick":           [1, 0, 0, 0,  0, 0, 0, 0,  0, 0, 0, 0,  0, 1, 0, 0],
        "snare_rim":      [0, 0, 0, 0,  0, 0, 1, 0,  0, 0, 0, 0,  1, 0, 0, 0], # Snare on beat 2.5 and 4!
        "drill_hihat":    [1, 0, 0, 1,  0, 0, 1, 0,  0, 1, 0, 0,  1, 0, 1, 0], # 3-3-3-3-2-2 bounce
        "808_slide_note": [0, 0, 0, 0,  0, 0, 0, 0,  0, 0, 0, 12, 0, 7, 12,15] # High octave 808 glides at bar end
    },
    # 3. JAMES BROWN FUNK ("The One" + Syncopated Ghost Snare)
    "funk_break_16": {
        "kick":           [1, 0, 1, 0,  0, 0, 0, 1,  0, 0, 1, 0,  0, 1, 0, 0],
        "snare_main":     [0, 0, 0, 0,  1, 0, 0, 0,  0, 0, 0, 0,  1, 0, 0, 0],
        "snare_ghost":    [0, 1, 0, 0,  0, 0, 0, 1,  0, 1, 0, 0,  0, 0, 0, 1], # Quiet 0.25 velocity hits
    }
}
\`\`\`

## 6. The Grand Unified Synthesis: How to Combine ALL FOUR Worlds in Python
*(Tamil $\times$ Arabic $\times$ African $\times$ Western)*

Assign each culture the frequency band and role it dominates:

| Frequency Band / Role | Best Cultural Engine | Why It Works Psychoacoustically |
| :--- | :--- | :--- |
| **Sub-Bass (`35Hz–110Hz`)** | **Western Trap/Drill Sliding 808** OR **South African Amapiano Log Drum** | Western & South African club genres engineered the cleanest, hardest-hitting sub-bass envelopes in music history. |
| **Low-Mid & High Percussion (`120Hz–8kHz`)** | **Tamil Kuthu (*Thavil, Parai, Urumi*)** $\times$ **West African 12/8 Bell** $\times$ **Gulf *Safqa* Claps** | Creates an interlocking 3D polyrhythmic street-festival groove that no standard Western 4/4 drum kit can match. |
| **Chordal Bed / Harmony (`200Hz–1.2kHz`)** | **Western Neo-Soul (`m9`/`m11`)** OR **Baroque/film strings** + **Sidechain Pump** | Gives the Western ear the lush vertical chord progressions and cinematic space it craves, while ducking out of the way of the drums. |
| **Lead Melody (`800Hz–4.5kHz`)** | **Tamil *Nadaswaram*** + **Arabic *Ney / Oud*** (with *Gamakas* & *Maqam* Quarter-Tones) + **SuperSaw Octave Layer** | The human ear locks onto the vocal-like microtonal pitch-bends of Tamil & Arabic leads, while a subtle Western SuperSaw layer gives it stadium-sized width. |
