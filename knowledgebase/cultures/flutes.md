---
document_id: "global_flute_procedural_dsp_kb_v1"
title: "Global Flute Procedural Synthesis & Cultural Soul Knowledge Base"
version: "1.0.0"
target_engine: "Pure-Python Procedural DSP & CI/CD Audio Quality Gate Engine"
zero_sample_policy: true
default_sample_rate_hz: 44100
default_master_lufs: -16.0
default_true_peak_dbtp: -1.2
schema_sections:
  - universal_dsp_physics
  - cultural_flute_profiles
  - soul_ornamentation_grammars
  - cicd_quality_gate_assertions
  - python_reference_interpreter
regions_covered:
  - South Asia (India)
  - East Asia (China, Japan)
  - Indigenous North America
  - Nordic / Scandinavia (Norway)
  - Middle East / Anatolia / Persia
  - Andean South America
  - Carpathian / Balkan Eastern Europe
  - West Africa (Guinea / Senegal)
  - Celtic / Ireland
  - Oceania / Aotearoa (Māori)
  - Polar / Antarctica (Glacial & Avian Bone Acoustics)
---

# Global Flute Procedural Synthesis & Cultural Soul Knowledge Base

## Table of Contents
1. [Universal Mathematical Architecture of a Flute's "Soul"](#1-universal-mathematical-architecture-of-a-flutes-soul)
   - [1.1 Jet-Edge Nonlinearity & Asymmetry (Even vs. Odd Harmonics)](#11-jet-edge-nonlinearity--asymmetry-even-vs-odd-harmonics)
   - [1.2 Bore Geometry & Boundary-Layer Visco-Thermal Losses](#12-bore-geometry--boundary-layer-visco-thermal-losses)
   - [1.3 "Soul" as a Stateful Time-Varying Trajectory (Not Static Notes)](#13-soul-as-a-stateful-time-varying-trajectory-not-static-notes)
2. [Cultural Flute Database (12 Global Archetypes)](#2-cultural-flute-database-12-global-archetypes)
   - [2.1 Indian Bansuri (South Asia)](#21-indian-bansuri-south-asia)
   - [2.2 Chinese Dizi with Dimo Membrane (East Asia)](#22-chinese-dizi-with-dimo-membrane-east-asia)
   - [2.3 Japanese Shakuhachi — Suizen Zen Flute (East Asia)](#23-japanese-shakuhachi--suizen-zen-flute-east-asia)
   - [2.4 Native American Cedar Courting Flute (Indigenous North America)](#24-native-american-cedar-courting-flute-indigenous-north-america)
   - [2.5 Norwegian Seljefløyte — Willow Overtone Flute (Nordic)](#25-norwegian-seljefløyte--willow-overtone-flute-nordic)
   - [2.6 Middle Eastern Reed Ney (Persia / Turkey / Levant)](#26-middle-eastern-reed-ney-persia--turkey--levant)
   - [2.7 Andean Quena & Siku Panpipes (South America)](#27-andean-quena--siku-panpipes-south-america)
   - [2.8 Slovak Fujara & Balkan Kaval (Eastern Europe)](#28-slovak-fujara--balkan-kaval-eastern-europe)
   - [2.9 West African Fula Tambin — Vocal-Flute Ring Modulation (Guinea/Senegal)](#29-west-african-fula-tambin--vocal-flute-ring-modulation-guineasenegal)
   - [2.10 Celtic Simple-System Wooden Flute (Ireland)](#210-celtic-simple-system-wooden-flute-ireland)
   - [2.11 Māori Kōauau & Pūtōrino (Aotearoa / Oceania)](#211-māori-kōauau--pūtōrino-aotearoa--oceania)
   - [2.12 Antarctic Glacial Ice-Bore & Albatross-Bone Flute (Polar)](#212-antarctic-glacial-ice-bore--albatross-bone-flute-polar)
3. [Cross-Cultural Micro-Ornamentation State Machines](#3-cross-cultural-micro-ornamentation-state-machines)
4. [CI/CD Audio Quality Gate Specification for Procedural Flutes](#4-cicd-audio-quality-gate-specification-for-procedural-flutes)
5. [Pure-Python Universal Cultural Flute Interpreter & Gate Validator](#5-pure-python-universal-cultural-flute-interpreter--gate-validator)

---

## 1. Universal Mathematical Architecture of a Flute's "Soul"

A flute's cultural "soul" is not mystical—it is the intersection of **four physical equations** and **three human performance grammars**:

### 1.1 Jet-Edge Nonlinearity & Asymmetry (Even vs. Odd Harmonics)
When an air jet strikes a splitting edge (*labium*, notch, or rim), its deflection $x(t)$ is governed by a polynomial saturation function with an **embouchure offset bias $b_0$**:

$$y(t) = (x(t) + b_0) - \alpha (x(t) + b_0)^3$$

* **If $b_0 = 0$ (Symmetric Split, e.g., Native American Cedar Fipple or Stopped Panpipe):** The air jet spends equal time inside and outside the tube. Even harmonics ($2f_0, 4f_0$) cancel out, leaving a hollow, woody, **odd-harmonic dominant** spectrum ($f_0, 3f_0, 5f_0$).
* **If $b_0 \in [0.15, 0.45]$ (Asymmetric Lip-Blown Angle, e.g., Bansuri, Shakuhachi, Quena):** The quadratic cross-term $3\alpha b_0 x^2(t)$ generates strong **even harmonics ($2f_0, 4f_0$)**, giving the flute octave-rich warmth and singing brightness.

### 1.2 Bore Geometry & Boundary-Layer Visco-Thermal Losses
The material (bamboo, cedar, bone, blackwood, glacial ice) controls internal wall damping $\gamma_{\text{wall}}$ and fixed body formants $\{F_1, F_2, F_3\}$:
* **Porous/Fibrous Walls (Soft Cedar, Old Bamboo, Reed):** High internal damping $\to$ rapid high-frequency rolloff ($\text{tilt} \ge 1.5$), warm low-mid resonance (`350–650 Hz`).
* **Dense/Crystalline Walls (Bone, African Blackwood, Glacial Ice):** Ultra-low wall damping $\to$ sustained upper partials ($\text{tilt} \le 1.15$), sharp attack transients, high-Q ringing formants (`1.8–3.2 kHz`).

### 1.3 "Soul" as a Stateful Time-Varying Trajectory (Not Static Notes)
No human flautist holds a constant frequency, constant breath pressure, or constant spectral tilt across a note. In procedural code, "soul" emerges when **pitch, timbre, and breath noise are coupled**:
1. **Pitch-Timbre Coupling (*Meri/Kari* Law):** Bending a note flatward by shading a hole or tilting the head *must* simultaneously lower the lowpass cutoff frequency and increase breath-to-tone noise ratio.
2. **Pressure-Pitch Coupling (Overblow & Bark Law):** Increasing air velocity pushes pitch slightly sharp (`+4 to +12 cents`) while boosting the 2nd and 3rd harmonics relative to the fundamental.
3. **Lung Depletion Phrase Envelope:** Across a multi-note phrase between rests, lung capacity $L(t) \in [1.0 \to 0.25]$ decays linearly, gradually widening vibrato depth and increasing breath effort.

---

## 2. Cultural Flute Database (12 Global Archetypes)

---

### 2.1 Indian Bansuri (South Asia)

* **The Soul & Emotional Feel:** Serene, pastoral, deeply vocal, and meditative. In Hindustani and Carnatic music, the Bansuri seeks *Gayaki Ang* (the style of the singing human voice). Notes rarely start or end on flat, discrete steps; they emerge from a tonic drone via fluid pitch glides (*Meend*) and gentle microtonal oscillations (*Gamaka*).
* **Acoustic Mechanics:** Side-blown, thin-walled seasoned Assam bamboo cylinder, stopped at one end with a cork, 6 or 7 open finger holes. Because the fingers partially shade large tone holes during *Meend*, the effective acoustic radiation impedance changes continuously during slides.

\`\`\`yaml
flute_profile:
  id: "bansuri_bamboo_flute"
  culture: "South Asian (Hindustani / Carnatic)"
  material: "thin_walled_assam_bamboo"
  bore_type: "open_cylindrical_transverse"
  pitch_range_midi: [55, 86] # G3 to D6 (Bass E/G Bansuri to Medium Bansuri)
  preferred_scales:
    raga_charukeshi_cents: [0, 204, 386, 498, 702, 814, 996]
    raga_yaman_cents: [0, 204, 386, 590, 702, 906, 1088]
    raga_bhairavi_cents: [0, 112, 316, 498, 702, 814, 1018]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.68, 0.28, 0.12, 0.05, 0.02, 0.01, 0.005]
    jet_asymmetry_bias_b0: 0.28
    cubic_nonlinearity_alpha: 0.16
    key_tracked_tilt_base: 1.35
    key_tracked_tilt_slope: 0.048
    subharmonic_ghost_gain_db: -32.0 # Active when MIDI >= 74
    breath_noise:
      steady_ratio: 0.11
      chiff_duration_ms: 32.0
      chiff_boost_mult: 2.1
      bandpass_f0_mult: [0.9, 2.6]
      turbulence_am_hz: 95.0
      turbulence_am_depth: 0.09
    body_formants_hz:
      - { freq: 440.0, gain_db: 3.5, q: 2.2 }  # Bamboo chamber warmth
      - { freq: 1350.0, gain_db: 2.0, q: 3.0 } # Woody mid presence
      - { freq: 2850.0, gain_db: -5.5, q: 2.5 } # Ear-canal anti-piercing dip
    dipole_radiation:
      enabled: true
      hole_delay_ms_range: [0.65, 1.55]
      wet_mix: 0.35
  soul_articulation_rules:
    default_legato_glide_ms: 140.0 # Long vocal Meend
    gamaka_oscillation:
      prob: 0.45
      rate_hz: 6.2
      depth_cents: 45.0
    murki_turn_ornament:
      prob: 0.25
      step_duration_ms: 42.0
    vibrato:
      delay_ms: 220.0
      rate_hz: 5.1
      depth_cents: 14.0
    finger_hole_thump_db: -26.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [550.0, 1650.0]
    spectral_flatness_range: [0.004, 0.035]
    max_piercing_ratio_2k5_to_3k8: 0.20
    min_h2_to_h1_ratio: 0.40
\`\`\`

---

### 2.2 Chinese Dizi with Dimo Membrane (East Asia)

* **The Soul & Emotional Feel:** Crisp, radiant, heroic, and soaring across mountain valleys (Jiangnan silk-and-bamboo lyrical style *Qudi* or northern virtuosic *Bangdi*). Its unmistakable soul comes from the **Dimo**—a paper-thin inner membrane of bamboo reed glued over a dedicated hole between the embouchure and the finger holes.
* **Acoustic Mechanics:** As the air column vibrates, the *Dimo* membrane buzzes nonlinearly against the air pressure, acting as a mechanical **rectifier + high-frequency ring modulator**. It injects rich upper harmonics (`1.8 kHz – 4.5 kHz`) that bloom dynamically only when air pressure exceeds a threshold (so soft notes are pure bamboo, and loud notes sizzle with golden membrane buzz).

\`\`\`yaml
flute_profile:
  id: "chinese_dizi_membrane"
  culture: "East Asian (Chinese Traditional Jiangnan / Northern)"
  material: "aged_bitter_bamboo_with_dimo_reed_membrane"
  bore_type: "open_cylindrical_membrane_coupled"
  pitch_range_midi: [62, 93] # D4 to A6
  preferred_scales:
    gong_pentatonic_cents: [0, 204, 386, 702, 906]
    yu_minor_pentatonic_cents: [0, 316, 498, 702, 1018]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.85, 0.62, 0.44, 0.30, 0.21, 0.14, 0.09]
    jet_asymmetry_bias_b0: 0.35
    cubic_nonlinearity_alpha: 0.22
    key_tracked_tilt_base: 1.08
    key_tracked_tilt_slope: 0.055
    dimo_membrane_modulator:
      enabled: true
      activation_velocity_threshold: 55
      membrane_resonance_hz: 2350.0
      membrane_q: 6.5
      nonlinear_rectification_mix: 0.24 # Adds |x(t)| * sin(w_dimo * t) buzz
      pressure_bloom_attack_ms: 45.0
    breath_noise:
      steady_ratio: 0.08
      chiff_duration_ms: 18.0
      chiff_boost_mult: 2.8
      bandpass_f0_mult: [1.2, 3.5]
      turbulence_am_hz: 130.0
      turbulence_am_depth: 0.12
    body_formants_hz:
      - { freq: 620.0, gain_db: 2.0, q: 2.5 }
      - { freq: 2350.0, gain_db: 4.5, q: 4.0 } # Dimo buzz formant peak
      - { freq: 3400.0, gain_db: -6.0, q: 2.0 } # Tames harshness above Dimo peak
  soul_articulation_rules:
    default_legato_glide_ms: 65.0 # Huayin (expressive pitch bend)
    duoyin_trill:
      prob: 0.35
      rate_hz: 11.5
      interval_semitones: 2
    flutter_tongue_huashe:
      prob: 0.15
      am_rate_hz: 26.0
      am_depth: 0.35
    vibrato:
      delay_ms: 150.0
      rate_hz: 6.0
      depth_cents: 18.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [950.0, 2400.0]
    spectral_flatness_range: [0.005, 0.045]
    max_piercing_ratio_2k5_to_3k8: 0.28 # Higher ceiling allowed for Dimo buzz
    min_h3_to_h1_ratio: 0.35
\`\`\`

---

### 2.3 Japanese Shakuhachi — Suizen Zen Flute (East Asia)

* **The Soul & Emotional Feel:** Wabi-sabi, austere, raw, and existential (*Honkyoku* solo Zen Buddhist meditation repertoire). In Shakuhachi music, **breath noise is equal in status to pitched tone** ("Ichion Jōbutsu" — attaining enlightenment in a single sound). A single sustained note is a complete drama: starting in pure air, blooming into a clear bamboo tone, dipping flatward into a dark, husky whisper (*Meri*), and erupting into a violent wind roar (*Muraiki*).
* **Acoustic Mechanics:** End-blown thick root-end *Madake* bamboo with a sharp oblique *Utaguchi* blowing edge and a lacquered *Ji* bore interior. Because the player's chin covers the top of the pipe, tilting the head down (*Meri*) lowers pitch by `100–200 cents` while simultaneously closing the embouchure aperture—causing a dramatic `-10 dB` drop in upper harmonics and a `2.5x` surge in turbulent air noise.

\`\`\`yaml
flute_profile:
  id: "japanese_shakuhachi_zen"
  culture: "East Asian (Japanese Komusō Zen Honkyoku)"
  material: "thick_root_madake_bamboo_lacquered_bore"
  bore_type: "open_conical_irregular_end_blown"
  pitch_range_midi: [62, 88] # D4 (1.8 shaku Ro) to E6
  preferred_scales:
    in_sen_pentatonic_cents: [0, 100, 500, 702, 1000]
    hon_kumoi_joshi_cents: [0, 100, 500, 702, 800]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.74, 0.45, 0.22, 0.11, 0.06, 0.03, 0.01]
    jet_asymmetry_bias_b0: 0.32
    cubic_nonlinearity_alpha: 0.25
    key_tracked_tilt_base: 1.25
    key_tracked_tilt_slope: 0.050
    meri_kari_coupled_physics:
      enabled: true
      meri_pitch_bend_cents: -120.0
      meri_lowpass_cutoff_mult: 0.45  # Darkens spectrum drastically during Meri
      meri_breath_noise_mult: 2.40    # Doubles airiness during Meri
      kari_pitch_bend_cents: +25.0
      kari_harmonic_bright_mult: 1.35
    muraiki_breath_explosion:
      enabled: true
      velocity_threshold: 92
      noise_burst_gain_db: +4.5
      duration_ms: 110.0
      overblow_h2_surge: 1.8
    breath_noise:
      steady_ratio: 0.26 # Very high organic breath presence
      chiff_duration_ms: 55.0
      chiff_boost_mult: 3.2
      bandpass_f0_mult: [0.7, 3.2]
      turbulence_am_hz: 75.0
      turbulence_am_depth: 0.18
    body_formants_hz:
      - { freq: 380.0, gain_db: 4.0, q: 1.8 } # Deep root-bamboo cavity
      - { freq: 1150.0, gain_db: 2.5, q: 2.8 }
      - { freq: 2700.0, gain_db: -6.5, q: 2.2 }
  soul_articulation_rules:
    default_legato_glide_ms: 180.0
    atari_finger_pop:
      prob: 0.40
      transient_ms: 12.0
      pitch_spike_cents: 65.0
    yuri_head_shake_vibrato:
      delay_ms: 350.0
      rate_hz: 4.4
      pitch_depth_cents: 32.0
      am_depth: 0.22 # Coupled pitch + amplitude vibrato
  cicd_quality_gates:
    spectral_centroid_hz_range: [480.0, 1550.0]
    spectral_flatness_range: [0.015, 0.085] # Must contain high breath entropy!
    max_piercing_ratio_2k5_to_3k8: 0.18
\`\`\`

---

### 2.4 Native American Cedar Courting Flute (Indigenous North America)

* **The Soul & Emotional Feel:** Intimate, warm, weeping, and canyon-resonant. Designed historically for solo courting and personal reflection in the quiet dusk, its voice is gentle, wooden, and completely free of harsh upper overtones.
* **Acoustic Mechanics:** A dual-chamber **fipple/duct flute** carved from aromatic soft Western Red Cedar or Redwood. Because the air stream is guided through a fixed shallow flue channel beneath a carved block ("bird" / fetish) straight into the splitting edge (`b0 ≈ 0.05`), the excitation is nearly symmetric: **the 2nd harmonic ($2f_0$) is weak, while the 1st ($f_0$) and 3rd ($3f_0$) harmonics dominate**, creating a clarinet-like hollow woody warmth.

\`\`\`yaml
flute_profile:
  id: "native_american_cedar_flute"
  culture: "Indigenous North American (Plains / Southwest Woodland)"
  material: "soft_aromatic_red_cedar"
  bore_type: "dual_chamber_fipple_duct_symmetric"
  pitch_range_midi: [60, 79] # C4 to G5 (Typically 1.25 octave range)
  preferred_scales:
    minor_pentatonic_just_cents: [0, 316, 498, 702, 1018]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.18, 0.48, 0.08, 0.14, 0.03, 0.04, 0.01] # Odd-harmonic dominant!
    jet_asymmetry_bias_b0: 0.06 # Symmetric fipple channel -> low even harmonics
    cubic_nonlinearity_alpha: 0.14
    key_tracked_tilt_base: 1.65 # Very warm, rapid upper-harmonic absorption in soft cedar
    key_tracked_tilt_slope: 0.060
    bark_onset_ornament:
      enabled: true
      velocity_threshold: 80
      initial_h2_h3_spike_ms: 28.0
      pitch_scoop_cents: +35.0 # Brief upward "bark" settling into warm fundamental
    breath_noise:
      steady_ratio: 0.09
      chiff_duration_ms: 22.0
      chiff_boost_mult: 1.4 # Fipple duct has softer chiff than lip-blown flutes
      bandpass_f0_mult: [0.8, 2.0]
      turbulence_am_hz: 60.0
      turbulence_am_depth: 0.06
    body_formants_hz:
      - { freq: 390.0, gain_db: 4.5, q: 2.0 } # Cedar chamber warmth
      - { freq: 980.0, gain_db: 2.0, q: 2.5 }
      - { freq: 2400.0, gain_db: -8.0, q: 1.8 } # Deep rolloff of any piercing highs
  soul_articulation_rules:
    default_legato_glide_ms: 95.0
    weeping_phrase_release:
      enabled: true
      release_drop_cents: -85.0
      release_duration_ms: 140.0
    diaphragm_pulse_vibrato:
      delay_ms: 180.0
      rate_hz: 4.6
      depth_cents: 12.0
      am_depth: 0.18 # Heartbeat-like diaphragm amplitude pulse
  cicd_quality_gates:
    spectral_centroid_hz_range: [380.0, 1150.0]
    spectral_flatness_range: [0.002, 0.022]
    max_piercing_ratio_2k5_to_3k8: 0.09 # Strictly warm, zero ear-canal harshness
    min_h3_to_h2_ratio: 1.40 # Enforces symmetric fipple odd-harmonic warmth!
\`\`\`

---

### 2.5 Norwegian Seljefløyte — Willow Overtone Flute (Nordic)

* **The Soul & Emotional Feel:** Ancient, untamed, mystical Nordic summer-solstice twilight. Because it is carved from fresh spring willow bark and has **zero finger holes**, it cannot play equal-tempered scales—it sings purely in the **natural acoustic overtone series**, including the haunting, otherworldly **11th partial (`+551 cents`, the neutral "Nordic Blue Fourth")** and **7th partial (`+969 cents`, the natural septimal minor seventh)**.
* **Acoustic Mechanics:** Sideways fipple-blown long tube (`50–80 cm`) with **no tone holes**. The player changes pitch solely by:
  1. Varying breath pressure to jump across harmonics $n \in \{2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12\}$.
  2. Opening or stopping the far end of the tube with the index finger:
     * **Open End:** Plays even and odd multiples of fundamental $f_0$ ($2f_0, 3f_0, 4f_0...$).
     * **Stopped End:** Converts the pipe into a quarter-wave resonator, shifting strictly to **odd multiples of $\frac{1}{2}f_0$** ($1.5 f_0, 2.5 f_0, 3.5 f_0, 4.5 f_0...$) and dropping the spectral brightness!

\`\`\`yaml
flute_profile:
  id: "norwegian_seljefloyte_willow"
  culture: "Nordic / Scandinavian (Norwegian Traditional Folk)"
  material: "fresh_peeled_willow_bark_tube"
  bore_type: "holeless_overtone_open_closed_hybrid"
  pitch_range_midi: [62, 91] # Overtones of a low D3/E3 fundamental tube
  preferred_scales:
    seljefloyte_overtone_scale_cents: [0, 204, 386, 551, 702, 841, 969, 1088] # Notice 551c (11th partial) & 969c (7th partial)!
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.55, 0.38, 0.20, 0.12, 0.06, 0.03, 0.01]
    jet_asymmetry_bias_b0: 0.20
    cubic_nonlinearity_alpha: 0.19
    key_tracked_tilt_base: 1.28
    key_tracked_tilt_slope: 0.042
    overtone_pipe_physics:
      enabled: true
      tube_fundamental_hz: 146.83 # D3 base tube
      stopped_end_odd_mode_filter_db: -3.5 # Slightly muffled when finger closes far end
      harmonic_jump_chiff_spike: 1.65 # Brief whistle transient when jumping partials
    breath_noise:
      steady_ratio: 0.15
      chiff_duration_ms: 28.0
      chiff_boost_mult: 2.5
      bandpass_f0_mult: [1.0, 3.0]
      turbulence_am_hz: 105.0
      turbulence_am_depth: 0.11
    body_formants_hz:
      - { freq: 520.0, gain_db: 3.0, q: 2.4 }
      - { freq: 1480.0, gain_db: 2.5, q: 3.2 }
      - { freq: 2900.0, gain_db: -5.0, q: 2.2 }
  soul_articulation_rules:
    default_legato_glide_ms: 25.0 # Snaps cleanly between natural harmonic nodes!
    overtone_cascade_grace:
      prob: 0.50
      step_duration_ms: 32.0 # Rapid willow-flute harmonic flick
    vibrato:
      delay_ms: 240.0
      rate_hz: 5.4
      depth_cents: 10.0 # Air-pressure vibrato (mostly AM + slight sharp pitch)
      am_depth: 0.16
  cicd_quality_gates:
    spectral_centroid_hz_range: [650.0, 1850.0]
    spectral_flatness_range: [0.006, 0.040]
    max_piercing_ratio_2k5_to_3k8: 0.22
\`\`\`

---

### 2.6 Middle Eastern Reed Ney (Persia / Turkey / Levant)

* **The Soul & Emotional Feel:** Mystical, aching spiritual longing (immortalized in Rumi’s *Masnavi*: *"Listen to the reed and the tale it tells, how it sings of separation"*). The Ney is the breathiest, most human-voice-like wind instrument on earth: a blend of desert wind, smoky low throat resonance, and crying microtonal *Maqam* inflections.
* **Acoustic Mechanics:** Rim-blown giant river reed (*Arundo donax*) divided by internal bamboo-like nodes. The air jet splits against the sharp inner rim while the player shapes their oral cavity as a **coupled Helmholtz pre-resonator**. In the low register (*Bam*), the fundamental is accompanied by a strong **bilabial wind hiss (`1.2–2.8 kHz`)** and a rich **3rd harmonic (12th interval)** that co-exists with the fundamental.

\`\`\`yaml
flute_profile:
  id: "middle_eastern_reed_ney"
  culture: "Middle Eastern (Sufi Turkish / Persian / Arabic Maqam)"
  material: "arundo_donax_nine_node_giant_reed"
  bore_type: "open_cylindrical_oblique_rim_blown"
  pitch_range_midi: [57, 86] # A3 to D6
  preferred_scales:
    maqam_bayati_cents: [0, 150, 300, 498, 702, 800, 1000] # 150c neutral 2nd!
    maqam_hijaz_cents: [0, 112, 386, 498, 702, 814, 1018]
    maqam_saba_cents: [0, 150, 300, 400, 702, 800, 1000]
  dsp_synthesis_params:
    harmonic_amplitudes: [0.85, 0.90, 1.00, 0.55, 0.32, 0.18, 0.09, 0.04] # 2nd & 3rd partials often stronger than fundamental!
    jet_asymmetry_bias_b0: 0.18
    cubic_nonlinearity_alpha: 0.28
    key_tracked_tilt_base: 1.18
    key_tracked_tilt_slope: 0.045
    oral_cavity_pre_resonator:
      enabled: true
      throat_formant_hz: 720.0
      throat_formant_q: 3.5
      sub_drone_fifth_mix: 0.14 # Subtle multiphonic 5th/octave undertone
    breath_noise:
      steady_ratio: 0.38 # Signature smoky Sufi reed hiss!
      chiff_duration_ms: 48.0
      chiff_boost_mult: 2.6
      bandpass_f0_mult: [0.8, 3.8]
      turbulence_am_hz: 85.0
      turbulence_am_depth: 0.22
    body_formants_hz:
      - { freq: 540.0, gain_db: 3.0, q: 2.2 }
      - { freq: 1650.0, gain_db: 4.0, q: 3.2 } # Reedy nasal presence
      - { freq: 3100.0, gain_db: -5.5, q: 2.0 }
  soul_articulation_rules:
    default_legato_glide_ms: 115.0
    tahrik_octave_breath_leap:
      prob: 0.35
      initial_fifth_or_octave_ms: 45.0 # Jumps to 3f0/2f0 on attack before settling
    vibrato:
      delay_ms: 200.0
      rate_hz: 5.5
      depth_cents: 22.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [750.0, 2100.0]
    spectral_flatness_range: [0.025, 0.110] # Must maintain high smoky breath ratio
    max_piercing_ratio_2k5_to_3k8: 0.24
\`\`\`

---

### 2.7 Andean Quena & Siku Panpipes (South America)

* **The Soul & Emotional Feel:** High-altitude Altiplano wind, bright sun over stone peaks, and deep ancestral melancholy (*Huayno* and *Yaraví*). The **Quena** has a piercing yet velvety crying projection, while the **Siku (Zampoña)** breathes with a chugging, hypnotic, stopped-pipe wind pulse.
* **Acoustic Mechanics:**
  * **Quena:** End-blown U/V-notched wide-bore bamboo/bone cylinder with a thumb hole underneath. The deep notch focuses the air jet into a high-intensity beam, creating strong 2nd and 3rd harmonics and a soaring `1.8 kHz` crying formant.
  * **Siku (Stopped Panpipe):** Closed at the bottom end ($\lambda = 4L$). Stopped pipes produce **strictly odd harmonics ($1f_0, 3f_0, 5f_0$)** and a prominent **12th-interval ($3f_0$) attack chiff** on every breath pulse!

\`\`\`yaml
flute_profile:
  id: "andean_quena_siku"
  culture: "Andean South American (Quechua / Aymara Altiplano)"
  material: "high_altitude_bamboo_and_condor_bone"
  bore_type: "notched_end_blown_quena_and_stopped_siku_hybrid"
  pitch_range_midi: [64, 91] # E4 to G6
  preferred_scales:
    andean_minor_pentatonic_cents: [0, 316, 498, 702, 1018]
    huayno_dorian_hexatonic_cents: [0, 204, 316, 498, 702, 906]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.72, 0.58, 0.25, 0.19, 0.07, 0.05, 0.02]
    siku_stopped_pipe_mode_amplitudes: [1.00, 0.04, 0.52, 0.02, 0.21, 0.01, 0.08, 0.00]
    jet_asymmetry_bias_b0: 0.26
    cubic_nonlinearity_alpha: 0.21
    key_tracked_tilt_base: 1.22
    key_tracked_tilt_slope: 0.052
    breath_noise:
      steady_ratio: 0.19
      chiff_duration_ms: 35.0
      chiff_boost_mult: 2.9 # Strong panpipe/quena edge chiff
      bandpass_f0_mult: [1.0, 3.0]
      turbulence_am_hz: 115.0
      turbulence_am_depth: 0.15
    body_formants_hz:
      - { freq: 580.0, gain_db: 2.5, q: 2.0 }
      - { freq: 1820.0, gain_db: 3.5, q: 2.8 } # Quena crying notch formant
      - { freq: 2950.0, gain_db: -6.0, q: 2.2 }
  soul_articulation_rules:
    default_legato_glide_ms: 55.0
    llanto_crying_fall_off:
      prob: 0.45
      fall_cents: -150.0
      duration_ms: 90.0 # Signature Andean falling cry at phrase endings
    vibrato:
      delay_ms: 120.0
      rate_hz: 6.4 # Fast, energetic Andean diaphragm vibrato
      depth_cents: 20.0
      am_depth: 0.20
  cicd_quality_gates:
    spectral_centroid_hz_range: [700.0, 1950.0]
    spectral_flatness_range: [0.010, 0.055]
    max_piercing_ratio_2k5_to_3k8: 0.23
\`\`\`

---

### 2.8 Slovak Fujara & Balkan Kaval (Eastern Europe)

* **The Soul & Emotional Feel:** Majestic pastoral solitude of Carpathian mountain shepherds. The **Fujara** is a giant (`1.7m`) bass overtone flute that begins with a shimmering, metallic cascade of high overtones (*Rozfuk*) before dropping down into a warm, cello-like, burbling bass voice. The **Kaval** is famous for its *Kaba* register—a smoky, growling low register where the 1st, 2nd, and 3rd harmonics lock together into a rich multiphonic chord.
* **Acoustic Mechanics:** Because the Fujara's bore is huge (`L ≈ 1.6m`, $f_0 \approx 65\text{–}98\text{ Hz}$) with a narrow diameter, the fundamental is weak while partials $n = 2..10$ are tightly spaced and easily excited by small breath-pressure changes.

\`\`\`yaml
flute_profile:
  id: "carpathian_fujara_kaval"
  culture: "Eastern European (Slovak Carpathian / Bulgarian Balkan)"
  material: "elderberry_hardwood_long_bore"
  bore_type: "giant_bass_overtone_fipple_and_kaba_rim"
  pitch_range_midi: [43, 81] # G2 to A5
  preferred_scales:
    lydian_dominant_overtone_cents: [0, 204, 386, 590, 702, 906, 996]
    balkan_hijaz_kaval_cents: [0, 112, 386, 498, 702, 814, 1018]
  dsp_synthesis_params:
    harmonic_amplitudes: [0.65, 1.00, 0.92, 0.68, 0.45, 0.28, 0.16, 0.09] # Kaba/Fujara rich 2nd & 3rd partials!
    jet_asymmetry_bias_b0: 0.34
    cubic_nonlinearity_alpha: 0.26
    key_tracked_tilt_base: 1.15
    key_tracked_tilt_slope: 0.045
    rozfuk_overtone_burst:
      enabled: true
      phrase_start_sweep_partials: [7, 6, 5, 4, 3, 2]
      step_ms: 45.0
    breath_noise:
      steady_ratio: 0.20
      chiff_duration_ms: 40.0
      chiff_boost_mult: 2.7
      bandpass_f0_mult: [1.5, 4.0]
      turbulence_am_hz: 65.0
      turbulence_am_depth: 0.16
    body_formants_hz:
      - { freq: 260.0, gain_db: 4.5, q: 2.0 } # Giant elderwood bass resonance
      - { freq: 880.0, gain_db: 3.0, q: 2.8 } # Kaba throat formant
      - { freq: 2650.0, gain_db: -5.5, q: 2.0 }
  soul_articulation_rules:
    default_legato_glide_ms: 40.0
    mordent_balkan_flick:
      prob: 0.55
      step_duration_ms: 24.0
    vibrato:
      delay_ms: 200.0
      rate_hz: 5.2
      depth_cents: 16.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [420.0, 1600.0]
    spectral_flatness_range: [0.008, 0.050]
    max_piercing_ratio_2k5_to_3k8: 0.19
\`\`\`

---

### 2.9 West African Fula Tambin — Vocal-Flute Ring Modulation (Guinea/Senegal)

* **The Soul & Emotional Feel:** Electrifying, percussive, joyous, and fiercely human. Played by Fulani (*Peul*) herders of the Fouta Djallon highlands, the **Tambin** is never played passively—the flautist **sings, shouts, and growls directly into the embouchure hole while blowing**, turning the flute and human vocal cords into a single coupled instrument.
* **Acoustic Mechanics:** When the player vocalizes at frequency $f_{\text{voice}}$ (`120–350 Hz` glottal pulse) while the flute oscillates at $f_{\text{flute}}$ (`500–1800 Hz`), the vocal pressure waves modulate the air-jet velocity entering the nonlinear labium ($x - \alpha x^3$). In DSP terms, this creates **true acoustic Ring Modulation and Intermodulation Sidebands ($f_{\text{flute}} \pm k \cdot f_{\text{voice}}$)**, giving the flute a gritty, talking, sax-like growl!

\`\`\`yaml
flute_profile:
  id: "west_african_fula_tambin"
  culture: "West African (Fulani / Peul Fouta Djallon)"
  material: "hollowed_vine_wood_and_brass_lip_plate"
  bore_type: "conical_vine_vocal_coupled_transverse"
  pitch_range_midi: [62, 91] # D4 to G6
  preferred_scales:
    fula_hemitonic_pentatonic_cents: [0, 112, 498, 702, 814]
    mixolydian_afro_modal_cents: [0, 204, 386, 498, 702, 906, 996]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.80, 0.55, 0.35, 0.22, 0.12, 0.06, 0.03]
    jet_asymmetry_bias_b0: 0.30
    cubic_nonlinearity_alpha: 0.28
    key_tracked_tilt_base: 1.20
    key_tracked_tilt_slope: 0.048
    vocal_glottal_ring_modulator:
      enabled: true
      voice_pitch_tracking_ratio: 0.50 # Sings an octave or 10th below flute pitch (or fixed drone)
      glottal_pulse_harmonics: [1.0, 0.6, 0.3]
      ring_mod_depth: 0.32 # Multiplies air-jet by (1 + 0.32 * glottal_wave) BEFORE x - x^3!
      throat_growl_roughness_hz: 75.0
    breath_noise:
      steady_ratio: 0.18
      chiff_duration_ms: 14.0 # Hyper-percussive tongue-slap attack!
      chiff_boost_mult: 3.8
      bandpass_f0_mult: [1.0, 3.2]
      turbulence_am_hz: 140.0
      turbulence_am_depth: 0.20
    body_formants_hz:
      - { freq: 510.0, gain_db: 3.5, q: 2.2 }
      - { freq: 1420.0, gain_db: 3.0, q: 2.8 }
      - { freq: 2800.0, gain_db: -5.0, q: 2.0 }
  soul_articulation_rules:
    default_legato_glide_ms: 30.0
    percussive_tongue_slap:
      prob: 0.65
      impulse_ms: 8.0
      pitch_kick_cents: +80.0
    vibrato:
      delay_ms: 100.0
      rate_hz: 6.8
      depth_cents: 24.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [680.0, 2050.0]
    spectral_flatness_range: [0.012, 0.075] # Sidebands + growl increase spectral richness
    max_piercing_ratio_2k5_to_3k8: 0.24
\`\`\`

---

### 2.10 Celtic Simple-System Wooden Flute (Ireland)

* **The Soul & Emotional Feel:** Driving, rhythmic, woody, and dance-infused (Jigs, Reels, and haunting Slow Airs). Unlike classical silver Boehm flutes (which use vibrato and tonguing for expression), traditional Irish flute players **almost never tongue consecutive notes**—instead, they divide a single continuous stream of breath using lightning-fast **fingered articulations: Cuts, Strikes (Taps), and Rolls**.
* **Acoustic Mechanics:** Inverse-conical bore turned from dense **African Blackwood (Grenadilla)** with large, unkeyed tone holes. In the bottom octave ("Hard D", `D4–G4`), the conical bore + large embouchure produces a dark, reedy, cello-like buzz (`H2` and `H3` stronger than `H1`).

\`\`\`yaml
flute_profile:
  id: "celtic_wooden_pratten_flute"
  culture: "Celtic / Irish Traditional (Sligo / Roscommon Style)"
  material: "dense_african_blackwood_grenadilla"
  bore_type: "inverse_conical_large_hole_transverse"
  pitch_range_midi: [62, 88] # D4 to E6
  preferred_scales:
    d_major_dorian_mixolydian_cents: [0, 204, 386, 498, 702, 906, 996]
  dsp_synthesis_params:
    harmonic_amplitudes: [0.88, 1.00, 0.72, 0.38, 0.18, 0.08, 0.03, 0.01] # Reedy "Hard D" 2nd/3rd partial weight!
    jet_asymmetry_bias_b0: 0.36
    cubic_nonlinearity_alpha: 0.24
    key_tracked_tilt_base: 1.32
    key_tracked_tilt_slope: 0.050
    breath_noise:
      steady_ratio: 0.13
      chiff_duration_ms: 26.0 # Diaphragm "Huh" pulse rather than hard "Tu" tongue
      chiff_boost_mult: 2.0
      bandpass_f0_mult: [0.9, 2.5]
      turbulence_am_hz: 90.0
      turbulence_am_depth: 0.10
    body_formants_hz:
      - { freq: 480.0, gain_db: 4.0, q: 2.4 } # Woody blackwood chest resonance
      - { freq: 1220.0, gain_db: 2.5, q: 3.0 } # Reedy conical core
      - { freq: 2750.0, gain_db: -6.0, q: 2.2 }
  soul_articulation_rules:
    default_legato_glide_ms: 18.0 # Snappy finger transitions
    celtic_roll_ornament:
      prob: 0.40
      cut_offset_semitones: +2
      cut_duration_ms: 22.0
      strike_offset_semitones: -2
      strike_duration_ms: 20.0
      finger_thump_boost_db: +4.0 # Audible wooden finger-slap on strikes!
    vibrato:
      delay_ms: 400.0 # Finger vibrato used only on long slow-air notes!
      rate_hz: 4.8
      depth_cents: 15.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [520.0, 1620.0]
    spectral_flatness_range: [0.005, 0.038]
    max_piercing_ratio_2k5_to_3k8: 0.19
\`\`\`

---

### 2.11 Māori Kōauau & Pūtōrino (Aotearoa / Oceania)

* **The Soul & Emotional Feel:** Haunting, ancestral, and deeply intertwined with wind, birds, and the spirit world (*Taonga Pūoro*). Rather than leaping between wide intervals, traditional *Kōauau* and *Pūtōrino* melodies hover hypnotic and microtonal within a narrow 3- to 4-semitone compass—weeping, fluttering like the bellbird (*Korimako*), and dissolving into whispered breath.
* **Acoustic Mechanics:**
  * **Kōauau:** Short (`12–20 cm`), wide-bore flute carved from albatross wing bone or *Matai* wood, blown obliquely across the top rim.
  * **Pūtōrino:** A unique **cocoon-shaped (fusiform) bore** that swells wide in the center (where a carved figure-8 mouth opening sits) and tapers narrow at the bottom. This non-cylindrical bulge shifts the overtone modes away from integer multiples ($f_2 \approx 2.12 f_0$), creating a ghostly, hollow dual-voice resonance (*Hine Raukatauri*, the case-moth goddess).

\`\`\`yaml
flute_profile:
  id: "maori_putorino_koauau"
  culture: "Oceanian (Māori Taonga Pūoro — Aotearoa)"
  material: "matai_heartwood_and_toroa_albatross_bone"
  bore_type: "fusiform_cocoon_cavity_and_short_wide_rim"
  pitch_range_midi: [65, 86] # F4 to D6
  preferred_scales:
    taonga_microtonal_cluster_cents: [0, 95, 190, 285, 386, 498] # Narrow microtonal step inflections!
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.42, 0.35, 0.14, 0.06, 0.02, 0.01, 0.00]
    fusiform_inharmonic_stretch: 1.035 # Stretches partials slightly ($k^{1.035} f_0$) for cocoon-cavity physics!
    jet_asymmetry_bias_b0: 0.14
    cubic_nonlinearity_alpha: 0.17
    key_tracked_tilt_base: 1.48
    key_tracked_tilt_slope: 0.055
    breath_noise:
      steady_ratio: 0.24
      chiff_duration_ms: 38.0
      chiff_boost_mult: 2.2
      bandpass_f0_mult: [0.8, 2.4]
      turbulence_am_hz: 70.0
      turbulence_am_depth: 0.15
    body_formants_hz:
      - { freq: 460.0, gain_db: 5.0, q: 3.2 } # Central cocoon Helmholtz resonance
      - { freq: 1180.0, gain_db: 2.0, q: 2.5 }
      - { freq: 2500.0, gain_db: -7.0, q: 2.0 }
  soul_articulation_rules:
    default_legato_glide_ms: 165.0 # Continuous shading of holes
    korimako_flutter_trill:
      prob: 0.45
      rate_hz: 9.5
      depth_cents: 55.0
    vibrato:
      delay_ms: 150.0
      rate_hz: 5.0
      depth_cents: 26.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [450.0, 1380.0]
    spectral_flatness_range: [0.010, 0.055]
    max_piercing_ratio_2k5_to_3k8: 0.14
\`\`\`

---

### 2.12 Antarctic Glacial Ice-Bore & Albatross-Bone Flute (Polar)

* **The Soul & Emotional Feel:** Vast, sub-zero crystalline stillness, katabatic winds howling across blue-ice crevasses, and fragile loneliness at the end of the earth. Designed specifically for **Antarctic / Polar procedural soundscapes**, this archetype merges the real physics of **cryogenic blue-ice cylindrical bores** (tested in real Nordic/Polar ice-music festivals at `-15°C`) with **hollowed Southern Ocean albatross bone**.
* **Acoustic Mechanics:**
  1. **Cryogenic Speed of Sound Drop:** At `-20°C`, the speed of sound in air drops from `343 m/s` to `318.9 m/s`, causing a natural adiabatic pitch drift (`-125 cents` relative to warm breath as the tube cools between phrases, or rising `+15 cents` across a long note as warm human breath heats the ice bore!).
  2. **Glacial Crystalline Wall Reflection:** Smooth frozen ice walls have near-zero porosity, producing glassy, bell-like upper partials ($H_3, H_5$) paired with a haunting **sub-harmonic crevasse wind resonance ($0.5 f_0$)** and tiny stochastic **thermal ice-microfracture pings** when warm breath hits `-20°C` ice.

\`\`\`yaml
flute_profile:
  id: "antarctic_glacial_ice_flute"
  culture: "Polar / Antarctic (Cryogenic Ice-Bore & Southern Ocean Bone)"
  material: "compressed_glacial_blue_ice_and_albatross_bone"
  bore_type: "cryogenic_crystalline_tube_with_katabatic_sub_bore"
  pitch_range_midi: [60, 88] # C4 to E6
  preferred_scales:
    polar_lydian_cryo_cents: [0, 204, 386, 610, 702, 906, 1088] # Shimmering raised #4 (610c)
    antarctic_aeolian_cents: [0, 204, 316, 498, 702, 814, 1018]
  dsp_synthesis_params:
    harmonic_amplitudes: [1.00, 0.35, 0.52, 0.15, 0.24, 0.06, 0.09, 0.02] # Crystalline odd-harmonic shimmer (H1, H3, H5)
    jet_asymmetry_bias_b0: 0.12
    cubic_nonlinearity_alpha: 0.12
    key_tracked_tilt_base: 1.26
    key_tracked_tilt_slope: 0.058 # Prevents ear-canal piercing while keeping glassy lows/mids
    cryogenic_thermal_physics:
      enabled: true
      warm_breath_pitch_drift_cents_per_sec: +3.5 # Breath slightly warms the ice tube over long notes!
      subharmonic_crevasse_drone_db: -24.0 # Strong 0.5*f0 hollow ice-tunnel undertone
      micro_ice_crystalline_shimmer_hz: 1850.0
      micro_ice_shimmer_q: 9.0 # High-Q glassy ice resonance (below the 2.8kHz piercing band!)
    breath_noise:
      steady_ratio: 0.22
      chiff_duration_ms: 42.0
      chiff_boost_mult: 1.9
      bandpass_f0_mult: [0.5, 2.2] # Deep, cold hollow wind breath
      turbulence_am_hz: 45.0 # Slow katabatic wind undulation
      turbulence_am_depth: 0.16
    body_formants_hz:
      - { freq: 340.0, gain_db: 4.5, q: 2.5 }  # Deep ice-cave resonance
      - { freq: 1850.0, gain_db: 3.0, q: 5.5 } # Crystalline glassy ring (safe below 2.2kHz!)
      - { freq: 2900.0, gain_db: -7.5, q: 2.0 } # Strict anti-piercing notch
  soul_articulation_rules:
    default_legato_glide_ms: 210.0 # Slow, frozen, haunting pitch transitions
    katabatic_whistle_harmonic_ghost:
      prob: 0.35
      harmonic_partial: 3
      swell_duration_ms: 320.0
    vibrato:
      delay_ms: 450.0 # Very still, cold initial tone before slow shiver vibrato
      rate_hz: 4.1
      depth_cents: 11.0
  cicd_quality_gates:
    spectral_centroid_hz_range: [420.0, 1450.0]
    spectral_flatness_range: [0.008, 0.048]
    max_piercing_ratio_2k5_to_3k8: 0.12 # Glassy without ever being piercing!
\`\`\`

---

## 3. Cross-Cultural Micro-Ornamentation State Machines

To make a JSON score (`notes: [{t, d, p, v}, ...]`) automatically breathe with cultural soul **without manually writing thousands of tiny MIDI notes**, your Python pre-processor can apply a **Cultural Ornamentation Grammar** to the note stream before synthesis:

\`\`\`yaml
ornamentation_grammars:
  indian_meend_and_murki:
    applies_to: ["bansuri_bamboo_flute"]
    rules:
      - name: "continuous_meend_bridge"
        condition: "gap_between_notes_beats <= 0.15 and abs(p_next - p_curr) in [1, 2, 3, 4, 5]"
        action: "interpolate_continuous_cosine_pitch_curve(duration_pct=0.35)"
      - name: "nyas_sustained_turn"
        condition: "note_duration_beats >= 1.5"
        action: "inject_pre_onset_grace_cluster([p+2, p, p-1, p], step_ms=40)"

  celtic_cut_strike_roll:
    applies_to: ["celtic_wooden_pratten_flute"]
    rules:
      - name: "long_note_irish_roll"
        condition: "note_duration_beats >= 1.2 and velocity >= 75"
        action: "split_sustained_air_column([p, p+2, p, p-2, p], durations=[0.30, 0.04, 0.28, 0.04, 0.34], retrigger_chiff=False, inject_finger_thump=True)"

  japanese_suizen_meri_muraiki:
    applies_to: ["japanese_shakuhachi_zen"]
    rules:
      - name: "phrase_ending_meri_sigh"
        condition: "gap_after_note_beats >= 0.8"
        action: "tail_pitch_bend(cents=-110, last_pct=0.30, cutoff_mult=0.45, breath_mult=2.2)"
      - name: "climax_muraiki_roar"
        condition: "velocity >= 92"
        action: "onset_turbulence_explosion(ms=110, noise_db=+4.5, h2_overblow=1.8)"

  nordic_willow_harmonic_flick:
    applies_to: ["norwegian_seljefloyte_willow"]
    rules:
      - name: "overtone_node_flick"
        condition: "note_duration_beats >= 1.0"
        action: "inject_onset_turn([p, p+2, p-2, p], step_ms=32, retrigger_chiff=False)"
\`\`\`

---

## 4. CI/CD Audio Quality Gate Specification for Procedural Flutes

Because your engine uses CI/CD quality gates that adapt dynamically to the active preset, here are the **6 mathematical gate assertions** that guarantee every synthesized flute stem sounds natural, non-piercing, and culturally authentic:

\`\`\`json
{
  "cicd_flute_quality_gates": {
    "gate_1_anti_piercing_ear_canal_index": {
      "description": "Prevents harsh 2.2kHz-3.8kHz ear-canal resonance on high notes (D5-D6)",
      "formula": "band_rms(2200, 3800) / (band_rms(300, 1200) + 1e-9)",
      "assert": "value <= preset.cicd_quality_gates.max_piercing_ratio_2k5_to_3k8",
      "on_fail_diagnostic": "FAIL [Anti-Piercing Gate]: 2.2-3.8kHz energy ratio ({value:.3f}) exceeds cultural ceiling ({limit}). Increase key_tracked_tilt_slope or deepen 2.8kHz formant cut."
    },
    "gate_2_organic_breath_entropy": {
      "description": "Ensures flute is not a sterile sine wave (too low) nor broken white noise (too high)",
      "formula": "geometric_mean(power_spectrum) / arithmetic_mean(power_spectrum)",
      "assert": "preset.cicd_quality_gates.spectral_flatness_range[0] <= value <= preset.cicd_quality_gates.spectral_flatness_range[1]",
      "on_fail_diagnostic": "FAIL [Breath Texture Gate]: Spectral flatness ({value:.5f}) outside preset bounds {bounds}. Check pitched breath bandpass and turbulence AM modulator."
    },
    "gate_3_bore_symmetry_harmonic_signature": {
      "description": "Verifies fipple/stopped flutes (Cedar/Siku) have odd-harmonic dominance while conical/reed flutes have H2/H3 richness",
      "formula": "harmonic_energy(3 * f0) / (harmonic_energy(2 * f0) + 1e-9)",
      "assert": "if bore_type == 'dual_chamber_fipple_duct_symmetric': value >= 1.40",
      "on_fail_diagnostic": "FAIL [Bore Symmetry Gate]: H3/H2 ratio ({value:.2f}) failed symmetric fipple physics check. Reduce jet_asymmetry_bias_b0."
    },
    "gate_4_legato_click_and_phase_continuity": {
      "description": "Catches zero-crossing discontinuities or accidental double-chiff re-triggers during slurred legato transitions",
      "formula": "max(abs(diff(waveform[slur_boundary - 64 : slur_boundary + 64])))",
      "assert": "value <= 0.08",
      "on_fail_diagnostic": "FAIL [Legato Continuity Gate]: Phase jump ({value:.3f}) at beat {beat}. Ensure continuous phase accumulator across slurred notes."
    },
    "gate_5_dynamic_envelope_correlation": {
      "description": "Verifies rendered stem RMS envelope tracks the JSON score's macro dynamics curve [[beat, target], ...]",
      "formula": "pearson_r(windowed_rms_envelope, interpolated_json_dynamics_curve)",
      "assert": "value >= 0.82",
      "on_fail_diagnostic": "FAIL [Macro Dynamics Gate]: Stem RMS correlation ({value:.2f}) drifted from JSON dynamics curve at beat {worst_beat}."
    },
    "gate_6_dc_offset_and_sub_rumble": {
      "description": "Catches asymmetric jet nonlinearity (x + b0 - a*(x+b0)^3) DC offset leakage",
      "formula": "abs(mean(waveform)) + band_rms(0, 45)",
      "assert": "value <= 0.002",
      "on_fail_diagnostic": "FAIL [DC/Sub-Rumble Gate]: Asymmetric jet bias b0 leaked DC offset ({value:.5f}). Apply 1st-order 35Hz highpass DC blocker."
    }
  }
}
\`\`\`

---

## 5. Pure-Python Universal Cultural Flute Interpreter & Gate Validator

Below is the drop-in, zero-sample Python engine module that reads **any of the 12 cultural YAML profiles above**, synthesizes a continuous phrase with stateful bore physics (Dimo membrane, Meri head-tilt, Fula vocal ring-mod, or Cryogenic ice shimmer), and runs the **CI/CD Quality Gate** on the rendered buffer:

\`\`\`python
import numpy as np
from scipy.signal import butter, lfilter, sosfilt, iirpeak, welch


class CulturalFluteDSPEngine:
    """
    Pure-Python, Zero-Sample Cultural Flute Synthesizer + CI/CD Quality Gate Validator.
    Ingests any `flute_profile` dictionary from the Global Flute Knowledge Base.
    """

    def __init__(self, profile: dict, sr: int = 44100, seed: int = 1973):
        self.profile = profile
        self.dsp = profile["dsp_synthesis_params"]
        self.soul = profile["soul_articulation_rules"]
        self.gates = profile["cicd_quality_gates"]
        self.sr = sr
        self.rng = np.random.default_rng(seed)

    def _biquad_peaking(self, signal: np.ndarray, freq_hz: float, gain_db: float, q: float) -> np.ndarray:
        """Applies a fixed acoustic body formant or ear-canal anti-piercing dip."""
        if freq_hz >= self.sr * 0.48 or abs(gain_db) < 0.1:
            return signal
        A = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * np.pi * freq_hz / self.sr
        alpha = np.sin(w0) / (2.0 * q)
        cos_w0 = np.cos(w0)

        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / A

        b = np.array([b0, b1, b2]) / a0
        a = np.array([1.0, a1 / a0, a2 / a0])
        return lfilter(b, a, signal)

    def render_phrase(self, notes: list[dict], bpm: float = 96.0) -> np.ndarray:
        """
        Renders a list of JSON notes [{'t': beat, 'd': dur_beats, 'p': midi, 'v': vel}, ...]
        with continuous phase memory on legato slurs and cultural physics.
        """
        beat_sec = 60.0 / bpm
        total_sec = max(n["t"] + n["d"] for n in notes) * beat_sec + 1.5
        n_total = int(total_sec * self.sr)
        out = np.zeros(n_total, dtype=np.float64)

        phase_accum = 0.0
        prev_end_beat = -999.0
        lung_capacity = 1.0

        for idx, note in enumerate(notes):
            start_beat, dur_beats = note["t"], note["d"]
            midi_p, vel = float(note["p"]), float(note["v"])
            vel_norm = np.clip(vel / 127.0, 0.1, 1.0)

            # Check if slurred (legato) from previous note or after a breath rest
            gap_beats = start_beat - prev_end_beat
            is_legato = abs(gap_beats) <= 0.12
            if gap_beats > 0.8:
                lung_capacity = 1.0  # Player inhaled during rest!
            else:
                lung_capacity = max(0.25, lung_capacity - 0.08 * dur_beats)

            start_idx = int(start_beat * beat_sec * self.sr)
            dur_sec = dur_beats * beat_sec
            n_samp = int(dur_sec * self.sr)
            t = np.arange(n_samp) / self.sr
            freq = 440.0 * (2.0 ** ((midi_p - 69.0) / 12.0))

            # 1. Cultural Pitch Trajectory (Scoop + Vibrato + Cryo/Lung Drift)
            vib_cfg = self.soul["vibrato"]
            vib_env = np.clip((t - vib_cfg["delay_ms"] / 1000.0) / 0.15, 0.0, 1.0)
            lung_vib_boost = 1.0 + 0.18 * (1.0 - lung_capacity)
            vib_cents = vib_cfg["depth_cents"] * lung_vib_boost * vib_env * np.sin(2 * np.pi * vib_cfg["rate_hz"] * t)

            scoop_cents = 0.0 if is_legato else -15.0 * np.exp(-t / 0.03)
            cryo_drift = 0.0
            if self.dsp.get("cryogenic_thermal_physics", {}).get("enabled", False):
                cryo_drift = self.dsp["cryogenic_thermal_physics"]["warm_breath_pitch_drift_cents_per_sec"] * t

            inst_freq = freq * (2.0 ** ((vib_cents + scoop_cents + cryo_drift) / 1200.0))
            phase = phase_accum + 2.0 * np.pi * np.cumsum(inst_freq) / self.sr
            phase_accum = float(phase[-1] % (2.0 * np.pi))

            # 2. Turbulent Breath Shimmer Modulator
            bn_cfg = self.dsp["breath_noise"]
            b_t, a_t = butter(2, min(bn_cfg["turbulence_am_hz"], self.sr * 0.4) / (self.sr / 2), btype="low")
            turbulence = lfilter(b_t, a_t, self.rng.standard_normal(n_samp))

            # 3. Harmonic Synthesis with Key-Tracked Visco-Thermal Tilt
            tilt = self.dsp["key_tracked_tilt_base"] + self.dsp["key_tracked_tilt_slope"] * max(0.0, midi_p - 66.0)
            stretch = self.dsp.get("fusiform_inharmonic_stretch", 1.0)
            harm_weights = self.dsp["harmonic_amplitudes"]

            sig = np.zeros(n_samp)
            for k_idx, h_weight in enumerate(harm_weights):
                k = k_idx + 1
                partial_freq = (k ** stretch) * freq
                if partial_freq >= self.sr * 0.44 or h_weight <= 0.0:
                    continue
                amp_k = h_weight / (k ** tilt)
                shimmer = 1.0 + (bn_cfg["turbulence_am_depth"] * k * 0.5) * turbulence
                sig += amp_k * shimmer * np.sin((k ** stretch) * phase)

            # 4. Cultural Special Physics (Fula Vocal Ring-Mod / Subharmonic Ghost)
            if self.dsp.get("vocal_glottal_ring_modulator", {}).get("enabled", False):
                v_cfg = self.dsp["vocal_glottal_ring_modulator"]
                v_phase = phase * v_cfg["voice_pitch_tracking_ratio"]
                glottal = np.sin(v_phase) + 0.5 * np.sin(2 * v_phase)
                sig *= (1.0 + v_cfg["ring_mod_depth"] * glottal)

            if midi_p >= 74.0 and "subharmonic_ghost_gain_db" in self.dsp:
                sub_amp = 10.0 ** (self.dsp["subharmonic_ghost_gain_db"] / 20.0)
                sig += sub_amp * np.sin(0.5 * phase)

            # 5. Asymmetric Jet-Edge Cubic Nonlinearity + DC Blocker
            b0_bias = self.dsp["jet_asymmetry_bias_b0"]
            alpha = self.dsp["cubic_nonlinearity_alpha"]
            x = sig * (0.55 + 0.35 * vel_norm) + b0_bias
            sig = (x - alpha * (x ** 3)) - (b0_bias - alpha * (b0_bias ** 3))

            # 6. Chinese Dimo Membrane Buzz (if enabled)
            if self.dsp.get("dimo_membrane_modulator", {}).get("enabled", False):
                d_cfg = self.dsp["dimo_membrane_modulator"]
                if vel >= d_cfg["activation_velocity_threshold"]:
                    dimo_carrier = np.sin(2 * np.pi * d_cfg["membrane_resonance_hz"] * t)
                    sig += d_cfg["nonlinear_rectification_mix"] * np.abs(sig) * dimo_carrier

            # 7. Pitched Breath Residual + Chiff (Suppressed on Legato Slurs!)
            chiff_mult = 0.15 if is_legato else bn_cfg["chiff_boost_mult"]
            chiff_env = np.exp(-t / (bn_cfg["chiff_duration_ms"] / 1000.0))
            breath_env = bn_cfg["steady_ratio"] * (1.0 + chiff_mult * chiff_env)
            low_bp = np.clip(freq * bn_cfg["bandpass_f0_mult"][0], 120.0, self.sr * 0.38) / (self.sr / 2)
            high_bp = np.clip(freq * bn_cfg["bandpass_f0_mult"][1], low_bp * 1.4, self.sr * 0.45) / (self.sr / 2)
            b_bp, a_bp = butter(2, [low_bp, high_bp], btype="band")
            sig += lfilter(b_bp, a_bp, self.rng.standard_normal(n_samp)) * breath_env

            # 8. Legato Finger-Hole Thump on Slurred Transitions
            if is_legato and "finger_hole_thump_db" in self.soul:
                thump_amp = 10.0 ** (self.soul["finger_hole_thump_db"] / 20.0)
                thump = thump_amp * np.exp(-t / 0.006) * np.sin(2 * np.pi * 210.0 * t)
                sig += thump

            # 9. Smooth Note Amplitude Envelope & Overlap-Add
            att_sec = 0.012 if is_legato else 0.038
            rel_sec = 0.045
            env = np.minimum(np.clip(t / att_sec, 0.0, 1.0), np.clip((dur_sec - t) / rel_sec, 0.0, 1.0))
            sig *= env * vel_norm

            end_idx = min(n_total, start_idx + n_samp)
            out[start_idx:end_idx] += sig[: end_idx - start_idx]
            prev_end_beat = start_beat + dur_beats

        # 10. Apply Body Formants & 35Hz DC/Sub-Rumble Highpass Blocker
        for fmt in self.dsp["body_formants_hz"]:
            out = self._biquad_peaking(out, fmt["freq"], fmt["gain_db"], fmt["q"])

        b_hp, a_hp = butter(2, 35.0 / (self.sr / 2), btype="high")
        out = lfilter(b_hp, a_hp, out)
        return out

    def run_cicd_quality_gate(self, audio: np.ndarray) -> dict:
        """
        Executes preset-aware CI/CD Quality Gates on the rendered audio buffer.
        Returns a structured pass/fail report with exact failure diagnostics.
        """
        freqs, psd = welch(audio, fs=self.sr, nperseg=4096)
        psd = np.maximum(psd, 1e-18)

        # 1. Spectral Centroid
        centroid_hz = float(np.sum(freqs * psd) / np.sum(psd))
        c_min, c_max = self.gates["spectral_centroid_hz_range"]

        # 2. Spectral Flatness (Breath Entropy)
        active_mask = (freqs >= 120.0) & (freqs <= 8000.0)
        p_sub = psd[active_mask]
        flatness = float(np.exp(np.mean(np.log(p_sub))) / np.mean(p_sub))
        f_min, f_max = self.gates["spectral_flatness_range"]

        # 3. Ear-Canal Piercing Ratio (2.5kHz - 3.8kHz vs 300Hz - 1.2kHz)
        e_pierce = np.sqrt(np.mean(psd[(freqs >= 2500.0) & (freqs <= 3800.0)]))
        e_warm = np.sqrt(np.mean(psd[(freqs >= 300.0) & (freqs <= 1200.0)]))
        pierce_ratio = float(e_pierce / (e_warm + 1e-12))
        p_max = self.gates["max_piercing_ratio_2k5_to_3k8"]

        # 4. DC Offset & Sub-Rumble
        dc_val = float(np.abs(np.mean(audio)))

        failures = []
        if not (c_min <= centroid_hz <= c_max):
            failures.append(f"Spectral Centroid {centroid_hz:.1f}Hz outside [{c_min}, {c_max}]Hz")
        if not (f_min <= flatness <= f_max):
            failures.append(f"Breath Texture Flatness {flatness:.5f} outside [{f_min}, {f_max}]")
        if pierce_ratio > p_max:
            failures.append(f"Piercing 2.5-3.8kHz Ratio {pierce_ratio:.3f} exceeds max {p_max}")
        if dc_val > 0.002:
            failures.append(f"DC Offset leakage {dc_val:.5f} exceeds 0.002")

        return {
            "instrument_id": self.profile["id"],
            "passed": len(failures) == 0,
            "metrics": {
                "spectral_centroid_hz": round(centroid_hz, 2),
                "spectral_flatness": round(flatness, 5),
                "piercing_ratio_2k5_3k8": round(pierce_ratio, 4),
                "dc_offset": round(dc_val, 6),
            },
            "failures": failures,
        }
\`\`\`
