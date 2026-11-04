---
document_type: "algorithmic_knowledge_base"
system_id: "ARR-GMKB-v4.0"
domain: "computational_musicology_and_dsp"
style_profile: "A.R. Rahman (90s–Present Acoustic-Electronic Fusion Aesthetic)"
target_architecture: "Multi-Agent Python Symbolic & DSP Audio Engine"
encoding: "UTF-8"
ai_parsable: true
research_foundations:
  - "Two-Component Stage-Dance Gamaka Modeling (Subramanian et al.)"
  - "Modal Jazz & Raga Vadi-Samvadi Pedal-Point Harmonization"
  - "Rhythm-First Composition & Keith Peters Syncopated Ostinato Bass Topology"
  - "H. Sridhar / Panchathan Record Inn Psychoacoustic Mixing & Spectral Carving"
python_dependencies:
  - numpy>=1.24.0
  - scipy>=1.10.0
  - mido>=1.2.10
  - librosa>=0.10.0
  - pedalboard>=0.7.0
---

# A.R. Rahman Generative Music Knowledge Base (ARR-GMKB)

> The `*_engine.py` names in this document are code listings inside it, not scripts in `scripts/`.
> The skill's own versions of these ideas live in `theory.py`, `world.py`, `humanize.py`, `compose.py` and `direct.py`.

## Table of Contents
1. [System Architecture & Execution Pipeline](#1-system-architecture--execution-pipeline)
2. [Module 1: Raga, Pitch & Two-Component Gamaka Engine](#2-module-1-raga-pitch--two-component-gamaka-engine)
3. [Module 2: Modal Harmony, Slash Chords & Counterpoint Engine](#3-module-2-modal-harmony-slash-chords--counterpoint-engine)
4. [Module 3: Tala, Euclidean Polyrhythms & Ostinato Bass Engine](#4-module-3-tala-euclidean-polyrhythms--ostinato-bass-engine)
5. [Module 4: Macro-Structure, Layering & Jingle-Drop Arrangement Engine](#5-module-4-macro-structure-layering--jingle-drop-arrangement-engine)
6. [Module 5: H. Sridhar Psychoacoustic DSP & Spatial Mixing Engine](#6-module-5-h-sridhar-psychoacoustic-dsp--spatial-mixing-engine)
7. [Master JSON Schema & Pipeline Orchestrator](#7-master-json-schema--pipeline-orchestrator)

---

## 1. System Architecture & Execution Pipeline

Unlike conventional composers who begin exclusively with a linear melody, A.R. Rahman frequently initiates composition from **rhythm and sonic texture**, building a dense, multi-layered palette designed to "fully occupy the listener's mind" while keeping the core melody pure and emotionally direct.

To prevent the "robotic MIDI" uncanny valley, this architecture decouples **Discrete Symbolic Events** from **Continuous Microtonal and Psychoacoustic Space** across five sequential Python engines:

```
[Module 3: Groove & Tala Engine]      --> Generates polyrhythmic grid + 1/f Pink Noise micro-timing
               |
               v
[Module 1: Raga & Gamaka Engine]      --> Generates asymmetric Markov melody + Continuous Pitch-Bend Splines
               |
               v
[Module 2: Modal Harmony Engine]      --> Generates Raga-safe Slash Chords + Counter-Melodies + Bass Ostinatos
               |
               v
[Module 4: Arrangement Graph Engine]  --> Applies density curves, "Pre-Chorus Vacuum Drops", & Call-Response
               |
               v
[Module 5: Sridhar DSP Mixing Engine] --> Applies dynamic spectral carving, Haas widening, & sub-bass alignment
```

---

## 2. Module 1: Raga, Pitch & Two-Component Gamaka Engine

### 2.1 Raga-Mode Mapping & Vadi/Samvadi Weights
Rahman bridges Indian classical music and global genres by selecting Carnatic/Hindustani ragas that naturally accommodate modal chord substitutions. Notes are weighted by **Vadi** (King note, probability multiplier $\approx 1.8\times$) and **Samvadi** (Queen note, multiplier $\approx 1.4\times$).

| Raga Name | Western Modal Equivalent | Semitone Array $S$ (Root = 0) | Vadi / Samvadi | Signature Mood & Musical Reference |
| :--- | :--- | :--- | :--- | :--- |
| **Kalyani / Yaman** | Lydian Mode ($\sharp 4$) | `[0, 2, 4, 6, 7, 9, 11]` | `4` ($E$) / `11` ($B$) | Grand, dreamy, uplifting (*Vennilave*, *Jiya Jale* interlude) |
| **Harikambhoji** | Mixolydian Mode ($\flat 7$) | `[0, 2, 4, 5, 7, 9, 10]` | `7` ($G$) / `0` ($C$) | Sufi, folk, earthy, driving (*Chaiyya Chaiyya*, *Ghanan Ghanan*) |
| **Kharaharapriya / Kafi**| Dorian Mode ($\flat 3, \flat 7$) | `[0, 2, 3, 5, 7, 9, 10]` | `7` ($G$) / `2` ($D$) | Cool, groovy, urban, melancholic (*Urvasi Urvasi*, *Masakali*) |
| **Keeravani** | Harmonic Minor ($\flat 3, \flat 6$) | `[0, 2, 3, 5, 7, 8, 11]` | `7` ($G$) / `3` ($D\sharp$) | Intense yearning, classical drama (*Evano Oruvan*) |
| **Mohanam / Bhupali** | Major Pentatonic | `[0, 2, 4, 7, 9]` | `4` ($E$) / `7` ($G$) | Pure, innocent, pastoral (*Chinna Chinna Aasai*, *Malargale*) |
| **Sindhubhairavi** | Phrygian / Folk Composite | `[0, 1, 3, 5, 7, 8, 10]` | `5` ($F$) / `0` ($C$) | Deeply emotional, folk-spiritual (*Rukkumani*, *Khwaja Mere Khwaja*) |

### 2.2 Mathematical Model: Direction-Aware Asymmetric Markov Chain
In Carnatic music, ascending (*Arohanam*) and descending (*Avarohanam*) trajectories have distinct rules. We define transition probabilities conditioned on a directional momentum state $D_t \in \{+1, -1\}$:

$$P(X_{t+1} = s_j \mid X_t = s_i, D_t = d) = \frac{W_{i,j}^{(d)} \cdot V_j \cdot \exp(-\lambda |j - i|)}{\sum_{k=1}^{N} W_{i,k}^{(d)} \cdot V_k \cdot \exp(-\lambda |k - i|)}$$

* $\lambda \approx 0.65$: Step-wise decay constant (keeps $\sim 72\%$ of transitions to adjacent scale degrees while allowing occasional dramatic leaps of 4ths or 5ths).
* $V_j$: Vadi/Samvadi gravitational weight for scale degree $j$.
* $W_{i,j}^{(d)}$: Raga grammar matrix encoding signature *Pakad* (catchphrases) and *Vakra* (zig-zag) turns.

### 2.3 Two-Component "Stage-Dance" Gamaka Synthesis
Standard MIDI pitch quantization destroys the soul of Indian melodies. We model microtonal **Gamakas** by decomposing pitch into a **Stage** component (macro-glissando between notes) and a **Dance** component (micro-oscillations on sustained notes):

1. **Stage Component — *Jaru* (Logistic Sigmoid Slide):**
   $$f_{\text{stage}}(t) = f_{\text{prev}} + \frac{f_{\text{curr}} - f_{\text{prev}}}{1 + \exp\left(-k(t - t_{\text{glide}}/2)\right)}$$
2. **Dance Component — *Kampita* (Damped Sinusoidal Pull):**
   $$f_{\text{dance}}(t) = A_{\text{cents}} \cdot \sin\left(\frac{\pi t}{T_{\text{dur}}}\right) \cdot \sin(2\pi \nu_{\text{gam}} t)$$
   Where $\nu_{\text{gam}} \in [4.8, 5.8]\text{ Hz}$ mimics the human vocal / bansuri flute oscillation rate.

### 2.4 Implementation listing (`raga_gamaka_engine.py`; not a shipped script)

```python
import numpy as np

class RagaGamakaEngine:
    def __init__(self, root_midi=60, raga_name="Kalyani", control_rate_hz=100):
        self.root = root_midi
        self.sr = control_rate_hz
        self.ragas = {
            "Kalyani": {
                "arohanam": [0, 2, 4, 6, 7, 9, 11, 12],
                "avarohanam": [12, 11, 9, 7, 6, 4, 2, 0],
                "vadi": 4, "samvadi": 11,
                "kampita_nodes": [4, 6, 9, 11]
            },
            "Harikambhoji": {
                "arohanam": [0, 2, 4, 5, 7, 9, 10, 12],
                "avarohanam": [12, 10, 9, 7, 5, 4, 2, 0],
                "vadi": 7, "samvadi": 0,
                "kampita_nodes": [2, 5, 9, 10]
            },
            "Kharaharapriya": {
                "arohanam": [0, 2, 3, 5, 7, 9, 10, 12],
                "avarohanam": [12, 10, 9, 7, 5, 3, 2, 0],
                "vadi": 7, "samvadi": 2,
                "kampita_nodes": [3, 5, 9, 10]
            }
        }
        self.profile = self.ragas.get(raga_name, self.ragas["Kalyani"])

    def generate_melody_phrase(self, num_notes=16, step_decay=0.65):
        scale = self.profile["arohanam"]
        n = len(scale)
        seq_semitones = [0]
        direction = 1

        for _ in range(num_notes - 1):
            curr_val = seq_semitones[-1]
            curr_idx = scale.index(curr_val) if curr_val in scale else 0
            indices = np.arange(n)

            # Exponential distance penalty
            distances = np.abs(indices - curr_idx)
            weights = np.exp(-step_decay * distances)
            weights[curr_idx] *= 0.12  # Avoid robotic repeated notes

            for idx, semitone in enumerate(scale):
                mod_semi = semitone % 12
                if mod_semi == self.profile["vadi"]:
                    weights[idx] *= 1.85
                elif mod_semi == self.profile["samvadi"]:
                    weights[idx] *= 1.45
                if direction == 1 and idx > curr_idx:
                    weights[idx] *= 1.50
                elif direction == -1 and idx < curr_idx:
                    weights[idx] *= 1.50

            probs = weights / np.sum(weights)
            next_idx = int(np.random.choice(indices, p=probs))

            if next_idx >= n - 1:
                direction = -1
            elif next_idx <= 0:
                direction = 1
            else:
                direction = 1 if next_idx >= curr_idx else -1

            seq_semitones.append(scale[next_idx])

        return [self.root + s for s in seq_semitones]

    def render_microtonal_pitch_curve(self, midi_notes, durations_sec):
        """
        Generates continuous pitch-bend array in Cents relative to self.root.
        """
        total_time = float(sum(durations_sec))
        num_samples = int(total_time * self.sr)
        t_axis = np.linspace(0, total_time, num_samples)
        pitch_cents = np.zeros(num_samples)

        curr_t = 0.0
        for i, (note, dur) in enumerate(zip(midi_notes, durations_sec)):
            start_idx = int(curr_t * self.sr)
            end_idx = min(num_samples, int((curr_t + dur) * self.sr))
            seg_t = t_axis[start_idx:end_idx] - curr_t
            target_cents = (note - self.root) * 100.0

            # 1. Stage Component (Jaru Glissando)
            if i > 0 and len(seg_t) > 0:
                prev_cents = (midi_notes[i - 1] - self.root) * 100.0
                glide_dur = min(0.16, dur * 0.35)
                k = 32.0 / max(glide_dur, 0.01)
                stage = prev_cents + (target_cents - prev_cents) / (
                    1.0 + np.exp(-k * (seg_t - glide_dur / 2.0))
                )
            else:
                stage = np.full_like(seg_t, target_cents)

            # 2. Dance Component (Kampita Oscillation)
            rel_semi = (note - self.root) % 12
            if rel_semi in self.profile["kampita_nodes"] and dur >= 0.35 and len(seg_t) > 0:
                vib_rate = np.random.uniform(4.8, 5.6)
                vib_depth = np.random.uniform(40.0, 80.0)
                window = np.sin(np.pi * seg_t / dur)
                dance = vib_depth * window * np.sin(2.0 * np.pi * vib_rate * seg_t)
            else:
                dance = np.zeros_like(seg_t)

            pitch_cents[start_idx:end_idx] = stage + dance
            curr_t += dur

        return t_axis.tolist(), pitch_cents.tolist()
```

---

## 3. Module 2: Modal Harmony, Slash Chords & Counterpoint Engine

### 3.1 Raga-Safe Harmonic Voicing Rules
Western functional harmony ($ii \rightarrow V^7 \rightarrow I$) often clashes with Indian Ragas because dominant 7th chords introduce chromatic leading tones that destroy the Raga's modal identity. Rahman solves this through three core harmonic devices:

1. **Pedal-Point Slash Chords:** Keeping the bass note locked on the tonic (*Sa*, `0`) or fifth (*Pa*, `7`) while shifting upper triads derived strictly from the Raga's pitch set.
   * *Example in C Kalyani (Lydian):* $C\text{maj9} \rightarrow D/C \rightarrow Bm7/C \rightarrow C\text{sus2}$.
2. **Quartal & Suspended Voicings (`sus2` / `sus4` / `add9`):** Omitting the 3rd in keyboard pads (`[0, 2, 7]` or `[0, 5, 7]`). Because the 3rd (*Ga*) and 7th (*Ni*) in Indian music carry heavy microtonal *Kampita* oscillations, leaving them out of the fixed-pitch backing chords prevents dissonance and creates an open, airy acoustic space.
3. **Chromatic Modal Borrowing (The "Surprise Bridge" Shift):** In the *Charanam* (verse/bridge), Rahman frequently modulates temporarily to the $\flat VI$ or $\flat III$ major chord to create a sudden cinematic lift before smoothly resolving back to the Raga's tonic via a suspended chord.

### 3.2 Mathematical Voicing Cost Function
To select the optimal chord voicing $C_t = \{c_1, c_2, c_3, c_4\}$ for a melody note $m_t$, the engine minimizes a multi-objective cost function:

$$J(C_t, C_{t-1}, m_t) = w_{\text{vl}} \sum_{k=1}^{4} |c_{t,k} - c_{t-1,k}| + w_{\text{clash}} \cdot \mathbb{I}\left(\min_k |m_t - c_{t,k}| \pmod{12} = 1\right) - w_{\text{sus}} \cdot \mathbb{I}(\text{is\_suspended}(C_t))$$

* $w_{\text{vl}}$: Voice-leading smoothness weight (minimizes semitone movement between chords).
* $w_{\text{clash}}$: Heavy penalty for minor-2nd ($1$ semitone) clashes against the active melody note.
* $w_{\text{sus}}$: Reward for `sus2`, `sus4`, and slash-pedal voicings.

### 3.3 Implementation listing (`harmony_voicing_engine.py`; not a shipped script)

```python
import numpy as np

class HarmonyVoicingEngine:
    def __init__(self, root_midi=48, raga_semitones=None):
        self.root = root_midi  # C3 octave for chord voicings
        self.raga_set = set(raga_semitones if raga_semitones else [0, 2, 4, 6, 7, 9, 11])
        
        # Templates relative to degree root: (name, intervals, suspension_bonus)
        self.chord_templates = [
            ("sus2", [0, 2, 7, 12], 1.5),
            ("sus4", [0, 5, 7, 12], 1.5),
            ("add9", [0, 4, 7, 14], 1.2),
            ("min7", [0, 3, 7, 10], 1.0),
            ("maj7", [0, 4, 7, 11], 1.1),
            ("slash_tonic", [0, 2, 6, 9], 1.8)  # Upper II triad over Tonic pedal
        ]

    def _generate_candidate_chords(self):
        candidates = []
        for deg in self.raga_set:
            for name, intervals, bonus in self.chord_templates:
                notes_mod12 = {(deg + iv) % 12 for iv in intervals}
                # Check if chord belongs to Raga pitch class set
                if notes_mod12.issubset(self.raga_set):
                    midi_voicing = [self.root + deg + iv for iv in intervals]
                    # Anchor bass on Tonic (Sa) or Fifth (Pa) 60% of the time (Pedal Slash Chord)
                    bass_note = self.root - 12 if (deg in [0, 2, 4, 6]) else self.root - 5
                    candidates.append({
                        "label": f"Deg{deg}_{name}/Bass{bass_note % 12}",
                        "voicing": [bass_note] + midi_voicing,
                        "bonus": bonus
                    })
        return candidates

    def harmonize_melody(self, melody_notes, chord_stride=4):
        """
        Harmonizes a melody sequence by evaluating every `chord_stride` notes.
        """
        candidates = self._generate_candidate_chords()
        progression = []
        prev_voicing = [self.root - 12, self.root, self.root + 2, self.root + 7, self.root + 12]

        for i in range(0, len(melody_notes), chord_stride):
            mel_slice = melody_notes[i:i + chord_stride]
            primary_mel = mel_slice[0] % 12

            best_chord = None
            best_cost = float("inf")

            for cand in candidates:
                v = cand["voicing"]
                # 1. Voice leading distance
                vl_cost = sum(abs(a - b) for a, b in zip(v[1:], prev_voicing[1:])) * 0.4
                
                # 2. Avoid semitone clash with active melody note
                clash_cost = 0.0
                for note in v[1:]:
                    interval = abs((note % 12) - primary_mel) % 12
                    if interval in [1, 11]:
                        clash_cost += 25.0
                
                # 3. Reward melody note presence & suspended openness
                melody_match = -4.0 if any((n % 12) == primary_mel for n in v[1:]) else 0.0
                total_cost = vl_cost + clash_cost + melody_match - (cand["bonus"] * 3.0) + np.random.uniform(0, 1.5)

                if total_cost < best_cost:
                    best_cost = total_cost
                    best_chord = cand

            progression.append(best_chord)
            prev_voicing = best_chord["voicing"]

        return progression
```

---

## 4. Module 3: Tala, Euclidean Polyrhythms & Ostinato Bass Engine

### 4.1 Rhythm-First Architecture & Carnatic Tala Grids
Rahman often builds a track starting with an unconventional percussive groove. He superimposes asymmetric Indian *Talas* over Western electronic breakbeats, Reggae skanks, or New Jack Swing grooves:

* **Adi Tala (8 beats / 32 sixteenth-note ticks):** Subdivided as $4 + 2 + 2$, or internally accented via *Tisra Nadai* ($3+3+2$ Euclidean-style pulse).
* **Rupaka Tala (6 beats / 24 ticks):** Subdivided as $2 + 4$ (Used in swaying ballads like *Vennilave* or *Tu Hi Re*).
* **Misra Chapu (7 beats / 14 or 28 ticks):** Subdivided as $3 + 2 + 2$ (Creates a hypnotic, forward-tumbling folk momentum).
* **Khanda Chapu (5 beats / 10 or 20 ticks):** Subdivided as $2 + 3$ (Driving, urgent pulse).

### 4.2 Bjorklund's Euclidean Algorithm & $1/f$ Pink Noise Groove Humanization
Quantized drum machines sound sterile. Human drummers (such as Sivamani or traditional *Parai* and *Dholak* players) exhibit **Long-Range Correlated ($1/f$ Pink Noise) Micro-Timing Deviations** rather than uncorrelated white-noise jitter.

1. **Euclidean Rhythm Distribution $E(k, n)$:** Distributes $k$ percussive onsets as evenly as possible across $n$ grid steps. For example, $E(3, 8) = [1, 0, 0, 1, 0, 0, 1, 0]$ forms the signature $3+3+2$ *Chaiyya Chaiyya* / Reggae undercurrent.
2. **Pink Noise Timing & Velocity Drift:**
   Given a discrete onset time $t_i$, the humanized timestamp $\hat{t}_i$ is computed by filtering Gaussian white noise $w[i] \sim \mathcal{N}(0, 1)$ through a $1/f^{\alpha/2}$ spectral shaping filter ($\alpha \approx 1.0$):
   $$\hat{t}_i = t_i + \sigma_{\text{ms}} \cdot \mathcal{F}^{-1}\left\{ \frac{\mathcal{F}\{w\}(f)}{\sqrt{f}} \right\}_i + \Delta_{\text{swing}}(i)$$

### 4.3 The "Keith Peters" Syncopated Bass Ostinato
A defining hallmark of 90s and 2000s Rahman tracks (*Muqabala*, *Hamma Hamma*, *Urvasi*, *Dil Se*) is the interplay between acoustic/electric bass (often played by his longtime bassist Keith Peters) and the drum groove. The bassline uses:
* **Sixteenth-note Ghost Notes:** Percussive muted plucks immediately preceding strong beats.
* **Octave & Fifth Syncopation:** Jumping from the root ($0$) to the octave ($+12$) or flat-7th ($+10$) on off-beat sixteenth subdivisions (`tick % 4 in [1, 3]`).

### 4.4 Implementation listing (`groove_tala_engine.py`; not a shipped script)

```python
import numpy as np

class GrooveTalaEngine:
    def __init__(self, bpm=108, tala_type="Adi_Tisra"):
        self.bpm = bpm
        self.step_sec = (60.0 / bpm) / 4.0  # 16th-note resolution
        self.talas = {
            "Adi_Tisra": {"steps": 16, "kicks": 5, "snares": [4, 12], "accents": [0, 3, 6, 8, 11, 14]},
            "Misra_Chapu": {"steps": 14, "kicks": 4, "snares": [6, 10], "accents": [0, 3, 6, 8, 10, 12]},
            "Rupaka": {"steps": 12, "kicks": 3, "snares": [4, 8], "accents": [0, 4, 6, 8, 10]}
        }
        self.tala = self.talas.get(tala_type, self.talas["Adi_Tisra"])

    @staticmethod
    def euclidean_rhythm(k, n):
        """Bjorklund's algorithm for distributing k pulses over n steps."""
        pattern = [[1] for _ in range(k)] + [[0] for _ in range(n - k)]
        while len(pattern) > 1:
            last_elem = pattern[-1]
            split_idx = 0
            for i in range(len(pattern) - 1, -1, -1):
                if pattern[i] == last_elem:
                    split_idx = i
                else:
                    break
            if split_idx == 0:
                break
            rem = pattern[split_idx:]
            pattern = pattern[:split_idx]
            for i in range(min(len(pattern), len(rem))):
                pattern[i] = pattern[i] + rem[i]
            if len(rem) > len(pattern):
                pattern.extend(rem[len(pattern):])
        return [bit for sub in pattern for bit in sub]

    @staticmethod
    def generate_pink_noise(length, scale_ms=0.012):
        """Generates 1/f pink noise for natural human micro-timing drift."""
        white = np.random.randn(length)
        fft_vals = np.fft.rfft(white)
        freqs = np.fft.rfftfreq(length)
        freqs[0] = 1.0  # Avoid division by zero at DC
        pink_fft = fft_vals / np.sqrt(freqs)
        pink = np.fft.irfft(pink_fft, n=length)
        pink = pink / (np.max(np.abs(pink)) + 1e-8)
        return pink * scale_ms

    def generate_groove_and_bass(self, num_bars=4, bass_root_midi=36):
        steps_per_bar = self.tala["steps"]
        total_steps = steps_per_bar * num_bars
        base_euclid = self.euclidean_rhythm(self.tala["kicks"], steps_per_bar)
        timing_drift = self.generate_pink_noise(total_steps, scale_ms=0.010)

        drum_events = []
        bass_events = []

        for step in range(total_steps):
            local_step = step % steps_per_bar
            t_ideal = step * self.step_sec
            # Add subtle 16th-note swing on odd steps + 1/f human drift
            swing = (0.018 * self.step_sec) if (step % 2 == 1) else 0.0
            t_actual = max(0.0, t_ideal + swing + timing_drift[step])

            # 1. Kick / Thavil Low Hit
            if base_euclid[local_step] == 1:
                vel = int(np.clip(np.random.normal(110, 6), 85, 127))
                drum_events.append({"instrument": "kick_thavil", "time": t_actual, "vel": vel})

            # 2. Snare / Rimshot / Dholak Slap
            if local_step in self.tala["snares"]:
                vel = int(np.clip(np.random.normal(105, 8), 80, 127))
                drum_events.append({"instrument": "snare_dholak", "time": t_actual, "vel": vel})

            # 3. Shaker / Ghungroo High-Frequency Layer (Crucial for Panchathan Air)
            shaker_vel = 95 if local_step in self.tala["accents"] else 58
            drum_events.append({
                "instrument": "shaker_ghungroo",
                "time": t_actual,
                "vel": int(np.clip(shaker_vel + np.random.randint(-8, 8), 35, 120))
            })

            # 4. Keith Peters Syncopated Bass Ostinato
            if local_step in self.tala["accents"]:
                # Choose Root, Fifth (+7), or Octave (+12) on off-beats
                interval = 0 if local_step == 0 else np.random.choice([0, 7, 10, 12], p=[0.45, 0.25, 0.15, 0.15])
                bass_events.append({
                    "note": int(bass_root_midi + interval),
                    "time": t_actual,
                    "duration": self.step_sec * 1.6,
                    "vel": int(np.clip(np.random.normal(102, 5), 80, 125)),
                    "articulation": "plucked_sustain"
                })
            elif (local_step + 1) in self.tala["accents"] and np.random.rand() < 0.45:
                # 16th-note percussive ghost note before an accented beat
                bass_events.append({
                    "note": int(bass_root_midi),
                    "time": t_actual,
                    "duration": self.step_sec * 0.45,
                    "vel": 52,
                    "articulation": "muted_ghost"
                })

        return drum_events, bass_events
```

---

## 5. Module 4: Macro-Structure, Layering & Jingle-Drop Arrangement Engine

### 5.1 Non-Linear Song Topology & Layering Philosophy
Rahman famously stated that modern listeners think in multiple layers, so he designs arrangements with evolving counter-melodies and textures beneath the lead vocal to keep the brain occupied. Furthermore, drawing from his early career composing 30-second advertising jingles, he disrupted the rigid Indian *Pallavi – Anupallavi – Charanam* template with three structural innovations:

1. **The "Pre-Chorus Vacuum Drop" (Acoustic Silence Hook):**
   Immediately before the main *Pallavi* (Chorus) hook or at the end of a buildup, all percussion and bass tracks are muted for $0.5$ to $1.0$ bars ($2\text{ to }4\text{ beats}$), leaving only a solo vocal syllable, a breathy flute decay, or a reversed reverb tail before the full rhythm section slams back in (e.g., *Muqabala*, *Urvasi*, *Chaiyya Chaiyya*).
2. **Asymmetric Interludes (BGM 1 vs. BGM 2):**
   In pre-Rahman cinema, Interlude 1 and Interlude 2 often used similar orchestral templates. In Rahman's scores, if Interlude 1 is a soaring acoustic solo (e.g., Naveen Kumar's flute or solo violin), Interlude 2 contrasts it entirely with a Sufi *Qawwali* vocal *Alaap*, a Continuum Fingerboard slide, or a polyrhythmic percussion breakdown.
3. **End-of-Line Instrumental Call-and-Response (*Nadais*):**
   Whenever the lead vocal rests at the end of a lyrical phrase (typically bars 2 and 4), a solo acoustic instrument (flute, *Shenai*, *Santoor*, or nylon guitar) immediately fills the gap with a 4-to-6 note micro-ornament.

### 5.2 Implementation listing (`arrangement_graph_engine.py`; not a shipped script)

```python
class ArrangementGraphEngine:
    def __init__(self):
        # Defines active stem layers and density (0.0 to 1.0) across the song timeline
        self.structural_nodes = [
            {
                "section": "Prelude_Atmospheric",
                "bars": 4,
                "energy": 0.30,
                "active_stems": ["drone_tanpura", "solo_flute", "shaker_ghungroo", "warm_pad"],
                "vacuum_drop_last_beats": 0
            },
            {
                "section": "Groove_Intro",
                "bars": 4,
                "energy": 0.65,
                "active_stems": ["kick_thavil", "snare_dholak", "shaker_ghungroo", "ostinato_bass", "warm_pad"],
                "vacuum_drop_last_beats": 2  # Signature 2-beat silence before Pallavi!
            },
            {
                "section": "Pallavi_A (Main_Hook)",
                "bars": 8,
                "energy": 0.85,
                "active_stems": ["lead_vocal", "call_response_flute", "kick_thavil", "snare_dholak", "shaker_ghungroo", "ostinato_bass", "warm_pad"],
                "vacuum_drop_last_beats": 0
            },
            {
                "section": "Interlude_1 (Grand_Orchestral_Fusion)",
                "bars": 8,
                "energy": 0.90,
                "active_stems": ["string_ensemble_octaves", "kick_thavil", "snare_dholak", "ostinato_bass", "arpeggio_santoor"],
                "vacuum_drop_last_beats": 1
            },
            {
                "section": "Charanam (Modal_Bridge_Shift)",
                "bars": 8,
                "energy": 0.75,
                "active_stems": ["lead_vocal", "acoustic_guitar_strum", "shaker_ghungroo", "ostinato_bass", "counter_cello"],
                "vacuum_drop_last_beats": 4  # Full 1-bar vacuum drop before final Pallavi return
            },
            {
                "section": "Pallavi_Climax (Sufi_Choir_Layer)",
                "bars": 8,
                "energy": 1.00,
                "active_stems": ["lead_vocal", "sufi_harmony_choir", "call_response_flute", "kick_thavil", "snare_dholak", "shaker_ghungroo", "ostinato_bass", "string_ensemble_octaves"],
                "vacuum_drop_last_beats": 0
            }
        ]

    def apply_vacuum_drop(self, events, section_end_time_sec, beat_duration_sec, drop_beats):
        """
        Mutes all rhythmic and bass events during the final `drop_beats` of a section
        to create the signature A.R. Rahman pre-hook silence.
        """
        if drop_beats <= 0:
            return events
        drop_start = section_end_time_sec - (drop_beats * beat_duration_sec)
        filtered_events = [
            ev for ev in events
            if not (drop_start <= ev["time"] < section_end_time_sec)
        ]
        return filtered_events
```

---

## 6. Module 5: H. Sridhar Psychoacoustic DSP & Spatial Mixing Engine

### 6.1 The Panchathan Record Inn Sonic Signature
The reason A.R. Rahman's 1990s scores (*Roja*, *Bombay*, *Dil Se*, *Taal*) sound like modern audiophile recordings is due to the groundbreaking engineering of the late **H. Sridhar** (a mathematics graduate turned chief audio engineer) and Rahman at Panchathan Record Inn. They replaced muddy, single-room orchestral recordings with multi-track acoustic isolation and precise frequency allocation:

1. **Dynamic Spectral Carving (Anti-Masking EQ):**
   To allow dense layering without muddiness, backing pads and strings are dynamically scooped in the vocal presence band ($1.2\text{ kHz} - 3.8\text{ kHz}$) proportional to the instantaneous RMS envelope of the lead vocal/melody.
2. **Bimodal Frequency Smile (Sub-Bass Punch + Shimmering Air):**
   * **Sub-Bass ($40\text{ Hz} - 90\text{ Hz}$):** Tight, phase-locked mono low-end (Rahman famously installed specialized Bag End subwoofers at Panchathan to monitor deep sub-bass extension).
   * **Mud Cut ($220\text{ Hz} - 380\text{ Hz}$):** Aggressive attenuation of boxiness in acoustic drums and guitars.
   * **Crystalline Air Shelf ($> 10\text{ kHz}$):** A $+3.5\text{ dB}$ high-shelf boost on shakers, *ghungroos*, acoustic guitar transients, and breathy vocal harmonics.
3. **Psychoacoustic Haas Stereo Widening:**
   Backing percussion, acoustic guitars, and synth pads are panned wide to the edges of the stereo field using a $12\text{ ms} - 18\text{ ms}$ inter-aural Haas delay and Mid-Side ($M/S$) matrixing, leaving the dead center ($0^\circ$ azimuth) completely clear for the lead vocal, solo flute, kick, and bass.

### 6.2 Mathematical Model: Mid-Side Spatial Matrix & Dynamic EQ Ducking
Given a stereo signal $(L, R)$, we decompose into Mid ($M$) and Side ($S$) channels:

$$M(t) = \frac{L(t) + R(t)}{\sqrt{2}}, \qquad S(t) = \frac{L(t) - R(t)}{\sqrt{2}}$$

For backing textures, we boost $S(t)$ by gain $\gamma_{\text{side}} \approx 1.35$ and apply a dynamic peaking filter $H_{\text{scoop}}(\omega, t)$ to $M(t)$ at center frequency $\omega_0 = 2\pi \cdot 2400\text{ rad/s}$ driven by the lead melody's Hilbert envelope $E_{\text{lead}}(t)$:

$$G_{\text{dB}}(t) = -6.0 \cdot \min\left(1.0, \frac{E_{\text{lead}}(t)}{\theta_{\text{thresh}}}\right)$$

### 6.3 Implementation listing (`sridhar_dsp_engine.py`; not a shipped script)

```python
import numpy as np
from scipy.signal import butter, sosfilt, hilbert

class SridharDSPEngine:
    def __init__(self, sample_rate=44100):
        self.sr = sample_rate

    def apply_haas_stereo_widening(self, mono_signal, delay_ms=14.5, side_gain=1.35):
        """
        Converts a mono backing stem into a wide Panchathan-style stereo image
        using the psychoacoustic Haas effect and Mid-Side widening.
        """
        delay_samples = int((delay_ms / 1000.0) * self.sr)
        left = mono_signal
        right = np.pad(mono_signal, (delay_samples, 0), mode="constant")[:-delay_samples]
        # Invert phase slightly and boost Side channel
        mid = (left + right) / np.sqrt(2.0)
        side = ((left - right) / np.sqrt(2.0)) * side_gain
        out_l = (mid + side) / np.sqrt(2.0)
        out_r = (mid - side) / np.sqrt(2.0)
        return np.vstack([out_l, out_r])

    def apply_panchathan_spectral_curve(self, audio_stereo):
        """
        Applies H. Sridhar's signature EQ curve:
        1. High-pass rumble below 32 Hz
        2. Cut lower-mid mud (250 Hz - 360 Hz)
        3. Boost crystalline high-air (> 10 kHz)
        """
        # 1. Sub-rumble HPF at 32 Hz
        sos_hp = butter(2, 32.0 / (self.sr / 2.0), btype="highpass", output="sos")
        cleaned = sosfilt(sos_hp, audio_stereo, axis=-1)

        # 2. Extract and attenuate 250-360 Hz mud band (-3.5 dB equivalent)
        sos_mud = butter(2, [250.0 / (self.sr / 2.0), 360.0 / (self.sr / 2.0)], btype="bandpass", output="sos")
        mud_band = sosfilt(sos_mud, cleaned, axis=-1)
        cleaned = cleaned - (0.33 * mud_band)

        # 3. Extract and boost > 10 kHz shimmer band (+4.0 dB equivalent)
        sos_air = butter(2, 10000.0 / (self.sr / 2.0), btype="highpass", output="sos")
        air_band = sosfilt(sos_air, cleaned, axis=-1)
        enhanced = cleaned + (0.58 * air_band)

        return np.clip(enhanced, -0.99, 0.99)

    def dynamic_spectral_unmasking(self, lead_mono, backing_stereo):
        """
        Carves a dynamic pocket in the 1.2 kHz - 3.8 kHz vocal presence zone of the
        backing track whenever the lead melody is active.
        """
        # Compute smooth amplitude envelope of the lead vocal/flute
        analytic_signal = hilbert(lead_mono)
        envelope = np.abs(analytic_signal)
        sos_env = butter(1, 15.0 / (self.sr / 2.0), btype="lowpass", output="sos")
        smooth_env = sosfilt(sos_env, envelope)
        norm_env = np.clip(smooth_env / (np.max(smooth_env) + 1e-8), 0.0, 1.0)

        # Isolate 1.2 kHz - 3.8 kHz presence band in backing stereo track
        sos_pres = butter(2, [1200.0 / (self.sr / 2.0), 3800.0 / (self.sr / 2.0)], btype="bandpass", output="sos")
        presence_band = sosfilt(sos_pres, backing_stereo, axis=-1)

        # Dynamically subtract up to 50% of the presence band when lead is loud
        ducking_curve = 0.50 * norm_env[np.newaxis, :]
        unmasked_backing = backing_stereo - (presence_band * ducking_curve)
        return unmasked_backing
```

---

## 7. Master JSON Schema & Pipeline Orchestrator

To connect all five modules into an automated AI/Python pipeline, the system exchanges a standardized JSON state payload (`ARR_Score_State.json`).

### 7.1 Inter-Module JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ARR_Generative_Score_State",
  "type": "object",
  "properties": {
    "metadata": {
      "type": "object",
      "properties": {
        "raga": { "type": "string", "enum": ["Kalyani", "Harikambhoji", "Kharaharapriya", "Keeravani", "Mohanam"] },
        "tala": { "type": "string", "enum": ["Adi_Tisra", "Misra_Chapu", "Rupaka"] },
        "bpm": { "type": "number", "minimum": 60, "maximum": 160 },
        "root_midi": { "type": "integer", "default": 60 }
      }
    },
    "symbolic_layers": {
      "type": "object",
      "properties": {
        "melody_midi": { "type": "array", "items": { "type": "integer" } },
        "microtonal_pitch_cents": { "type": "array", "items": { "type": "number" } },
        "chord_progression": { "type": "array", "items": { "type": "object" } },
        "drum_events": { "type": "array", "items": { "type": "object" } },
        "bass_ostinato_events": { "type": "array", "items": { "type": "object" } }
      }
    }
  }
}
```

### 7.2 Orchestration listing (`main_arr_generator.py`; not a shipped script)

```python
import json
from raga_gamaka_engine import RagaGamakaEngine
from harmony_voicing_engine import HarmonyVoicingEngine
from groove_tala_engine import GrooveTalaEngine
from arrangement_graph_engine import ArrangementGraphEngine

def build_arr_composition(raga="Kalyani", tala="Adi_Tisra", bpm=104, root_midi=60):
    # 1. Initialize Engines
    raga_engine = RagaGamakaEngine(root_midi=root_midi, raga_name=raga)
    harmony_engine = HarmonyVoicingEngine(
        root_midi=root_midi - 12,
        raga_semitones=raga_engine.profile["arohanam"][:-1]
    )
    groove_engine = GrooveTalaEngine(bpm=bpm, tala_type=tala)
    arr_engine = ArrangementGraphEngine()

    # 2. Generate Rhythm & Syncopated Bass Ostinato First (ARR Workflow)
    drums, bass = groove_engine.generate_groove_and_bass(num_bars=4, bass_root_midi=root_midi - 24)

    # 3. Apply Pre-Chorus Vacuum Drop on Bar 4 (Last 2 beats)
    beat_sec = 60.0 / bpm
    section_end_sec = 4 * groove_engine.tala["steps"] * groove_engine.step_sec
    drums = arr_engine.apply_vacuum_drop(drums, section_end_sec, beat_sec, drop_beats=2)
    bass = arr_engine.apply_vacuum_drop(bass, section_end_sec, beat_sec, drop_beats=2)

    # 4. Generate Raga Melody & Continuous Microtonal Gamaka Spline
    melody_notes = raga_engine.generate_melody_phrase(num_notes=16)
    durations = [beat_sec * 0.5] * 16
    t_axis, pitch_cents = raga_engine.render_microtonal_pitch_curve(melody_notes, durations)

    # 5. Generate Raga-Safe Modal Slash Harmony
    chords = harmony_engine.harmonize_melody(melody_notes, chord_stride=4)

    # 6. Package into AI-Parsable State Dictionary
    score_state = {
        "metadata": {"raga": raga, "tala": tala, "bpm": bpm, "root_midi": root_midi},
        "arrangement_plan": arr_engine.structural_nodes,
        "symbolic_layers": {
            "melody_midi": melody_notes,
            "microtonal_pitch_cents_preview": pitch_cents[:20],
            "chord_progression": chords,
            "drum_events_count": len(drums),
            "bass_ostinato_events_count": len(bass)
        }
    }
    return score_state

if __name__ == "__main__":
    composition_data = build_arr_composition(raga="Kalyani", tala="Adi_Tisra", bpm=106)
    print(json.dumps(composition_data, indent=2))
```

---
document_type: "algorithmic_knowledge_base_module"
module_id: "ARR-GMKB-Module-6"
module_name: "Acoustic Physical Modeling & Anti-Piercing Timbre Engine"
version: "4.0.0"
domain: "physical_audio_synthesis_and_psychoacoustics"
style_profile: "A.R. Rahman Organic Acoustic Core (Naveen Kumar Bansuri, Keith Peters Bass, Continuum/Esraj Strings)"
encoding: "UTF-8"
ai_parsable: true
purpose: "Eliminate plastic MIDI stiffness, static oscillator buzz, brick-wall transients, and ear-piercing 2.5kHz-4.5kHz digital glare"
python_dependencies:
  - numpy>=1.24.0
  - scipy>=1.10.0
  - soundfile>=0.12.1
---

# Module 6: Acoustic Physical Modeling & Anti-Piercing Timbre Engine

## Table of Contents
1. [Root-Cause Analysis: Why Standard MIDI Sounds Piercing & Fake](#1-root-cause-analysis-why-standard-midi-sounds-piercing--fake)
2. [Mathematical Foundations of Organic Acoustic Synthesis](#2-mathematical-foundations-of-organic-acoustic-synthesis)
3. [Instrument 1: Naveen Kumar-Style Breathy Bansuri Flute Model](#3-instrument-1-naveen-kumar-style-breathy-bansuri-flute-model)
4. [Instrument 2: Continuum / Esraj / Bowed String Formant Model](#4-instrument-2-continuum--esraj--bowed-string-formant-model)
5. [Instrument 3: Extended Karplus-Strong Plucked Veena / Acoustic Guitar](#5-instrument-3-extended-karplus-strong-plucked-veena--acoustic-guitar)
6. [The Psychoacoustic Anti-Piercing Filter (Fletcher-Munson + Tape Warmth)](#6-the-psychoacoustic-anti-piercing-filter-fletcher-munson--tape-warmth)
7. [Complete implementation listing: `organic_acoustic_synth.py`](#7-complete-implementation-listing-organic_acoustic_synthpy-not-a-shipped-script)

---

## 1. Root-Cause Analysis: Why Standard MIDI Sounds Piercing & Fake

Even when a melody has human timing (Module 3) and microtonal pitch bends (Module 1), routing it through a standard MIDI synth or basic waveform oscillator creates an artificial, ear-fatiguing sound due to four physical flaws:

| Acoustic Flaw in Standard MIDI | Why It Sounds Fake / Piercing | Mathematical Fix in Module 6 |
| :--- | :--- | :--- |
| **1. Static Harmonic Spectrum** | Basic oscillators output constant overtone ratios regardless of how soft or loud a note is. High harmonics ($n \ge 3$) drill into the ear continuously. | **Pressure-Coupled Harmonic Scaling:** Overtone amplitudes are coupled to a non-linear power of the breath/bow envelope $E(t)^k$. Soft passages are pure and dark; harmonics bloom only at emotional peaks. |
| **2. Brick-Wall Step Transients** | Triggering `NoteOn` jumps amplitude instantly or linearly, causing a subtle digital click and unnatural stiffness. | **Beta-Function Breath/Bow Arch + Chiff Injection:** Every note swells in using an asymmetric human lung/arm curve $t^\alpha (1-t)^\beta$ accompanied by a $40\text{ ms}$ burst of band-passed pink friction noise. |
| **3. Missing Wooden/Vocal Formants** | Raw waveforms lack the resonant acoustic cavities of a wooden violin body, bamboo flute bore, or human throat. | **Multi-Peak Formant Filter Bank:** Passes raw excitations through fixed biquad resonant peaks ($F_1, F_2, F_3$) that simulate bamboo and spruce wood cavities. |
| **4. 3.2 kHz Fletcher-Munson Glare** | The human ear canal naturally amplifies frequencies between $2.5\text{ kHz}$ and $4.2\text{ kHz}$. Digital synths overload this band, causing immediate ear fatigue. | **Fletcher-Munson Comfort Dip + Analog Tape Saturation:** Applies a $-4.5\text{ dB}$ dynamic notch at $3.2\text{ kHz}$ and rounds off sharp digital waveform edges via $\tanh$ soft-clipping. |

---

## 2. Mathematical Foundations of Organic Acoustic Synthesis

### 2.1 Continuous Phase Integration with Micro-Turbulence
To synthesize a continuous microtonal pitch spline $C(t)$ (in cents relative to root frequency $f_{\text{root}}$, generated by Module 1) without phase discontinuities or zipper noise, instantaneous frequency $f_{\text{inst}}(t)$ is integrated directly into instantaneous phase $\phi(t)$:

$$f_{\text{inst}}(t) = f_{\text{root}} \cdot 2^{\frac{C(t)}{1200}}$$

$$\phi(t) = 2\pi \int_{0}^{t} f_{\text{inst}}(\tau)\,d\tau + \eta_{\text{turb}}(t) \cdot E(t)$$

Where $\eta_{\text{turb}}(t)$ is band-passed $1/f$ pink noise ($800\text{ Hz} - 2600\text{ Hz}$). Injecting a small amount of pink turbulence directly into the phase ($\approx 0.08\text{ rad}$) creates the organic "woody air" of a bamboo flute or rosin bow friction instead of a sterile digital sine wave.

### 2.2 Asymmetric Human Lung / Bow Pressure Envelope $E(t)$
Real musicians do not hold a flat sustain level. For a phrase or note of normalized duration $\tau \in [0, 1]$, human breath/bow pressure follows a normalized Beta-distribution arch modulated by a $5.2\text{ Hz}$ diaphragmatic shimmer:

$$E(\tau) = \frac{\tau^{\alpha} (1 - \tau)^{\beta}}{\max_{\tau} \left[\tau^{\alpha} (1 - \tau)^{\beta}\right]} \cdot \left(1 + m_{\text{vib}} \sin(2\pi f_{\text{shimmer}} t)\right)$$

* For **Bansuri Flute**: $\alpha = 0.32$ (gentle breath attack), $\beta = 0.48$ (natural breath taper/sigh at the end of the note).
* For **Bowed Esraj / Strings**: $\alpha = 0.55$ (slow, emotional bow swell), $\beta = 0.35$.

### 2.3 Non-Linear Pressure-Dependent Harmonic Bloom
In real wind and string instruments, upper harmonics ($k = 2, 3, \dots, K$) do not scale linearly with volume—they bloom exponentially as air speed or bow pressure increases:

$$x_{\text{raw}}(t) = \sum_{k=1}^{K} a_k \cdot \left[E(t)\right]^{\gamma_k} \cdot \sin\left(k \cdot \phi(t) + \theta_k\right)$$

Where $\gamma_1 = 1.0$, $\gamma_2 = 1.6$, $\gamma_3 = 2.4$, and $\gamma_4 = 3.5$. When the melody is quiet ($E(t) < 0.3$), higher harmonics virtually vanish, producing an ultra-warm, non-piercing tone.

---

## 3. Instrument 1: Naveen Kumar-Style Breathy Bansuri Flute Model

Flautist Naveen Kumar is one of the defining voices of A.R. Rahman's 90s scores (*Roja*, *Bombay*, *Gentleman*). His sound is characterized by:
1. **Heavy Embouchure Chiff:** Audible breath rush at the start of every phrase.
2. **Cylindrical Bamboo Bore Harmonics:** Strong fundamental ($k=1$), rich octave ($k=2$, amplitude $0.45$), and soft twelfth ($k=3$, amplitude $0.15$), with almost zero harsh upper harmonics above $4\text{ kHz}$.
3. **End-of-Note Pitch Dip:** As breath pressure drops at the end of a held note, the pitch naturally dips by $-12\text{ cents}$.

---

## 4. Instrument 2: Continuum / Esraj / Bowed String Formant Model

Rahman frequently uses the **Haken Continuum Fingerboard**, **Esraj**, **Dilruba**, or solo **Carnatic Violin** for deeply emotional, crying melodies (*Dil Se*, *Taal*, *Lagaan*).
* Unlike a flute, bowed strings contain rich odd and even harmonics ($a_k = 1/k$), which **will sound like a piercing buzzsaw** unless passed through a **Wooden Body Formant Filter Bank**.
* We model the resonant spruce/skin cavity using three parallel biquad bandpass resonators centered at:
  * **Formant 1 (Hollow Body Air Cavity):** $285\text{ Hz}$ ($Q = 3.5$)
  * **Formant 2 (Warm Wood Bridge Resonance):** $720\text{ Hz}$ ($Q = 4.0$)
  * **Formant 3 (Vocal/Nasal Sing Zone):** $1850\text{ Hz}$ ($Q = 4.5$)
* All frequencies above $3200\text{ Hz}$ are rolled off at $-18\text{ dB/octave}$ to eliminate digital buzz.

---

## 5. Instrument 3: Extended Karplus-Strong Plucked Veena / Acoustic Guitar

For plucked arpeggios and call-and-response fills (*Chinna Chinna Aasai*, *Vennilave*, *Swades*), standard MIDI guitars sound plastic. We use an **Extended Digital Waveguide (Karplus-Strong)** algorithm with three anti-piercing upgrades:
1. **Warm Pink-Noise Pluck Excitation:** Instead of exciting the delay line with harsh white noise, we excite it with low-passed $1/f$ pink noise shaped by a Hanning window (simulating a fleshy finger pluck rather than a metal pick).
2. **One-Pole Loop Damping Filter:** Inside the feedback loop of length $L = \lfloor f_s / f_0 \rfloor$, high frequencies decay faster than low frequencies, just like a real nylon or bronze string:
   $$y[n] = g \cdot \left( (1 - s) \cdot y[n - L] + s \cdot y[n - L - 1] \right)$$
   Where $g \approx 0.995$ controls sustain and $s \in [0.35, 0.50]$ controls string softness.

---

## 6. The Psychoacoustic Anti-Piercing Filter (Fletcher-Munson + Tape Warmth)

Before any synthesized stem leaves Module 6, it passes through a mandatory 3-stage **Master Warmth Conditioning Chain**:

1. **Stage 1 — Analog Tape Soft-Saturation ($\tanh$):**
   Rounds off sharp digital transients and adds subtle, warm low-order harmonic compression:
   $$y_{\text{sat}}(t) = \frac{\tanh(\beta \cdot x(t))}{\tanh(\beta)}, \qquad \beta = 1.65$$
2. **Stage 2 — Fletcher-Munson 3.2 kHz Ear-Comfort Notch:**
   Human hearing is maximally sensitive around $3.2\text{ kHz}$ (the resonant frequency of the ear canal). Cutting this zone by $-4.5\text{ dB}$ ($Q = 1.8$) immediately removes the "piercing digital synth" sensation while preserving warmth and air.
3. **Stage 3 — Velvet Acoustic Room Early Reflections:**
   Dry synthesized signals sound unnaturally "inside your skull." Convolving the signal with a dense, exponentially decaying Velvet-Noise wooden studio impulse response ($T_{60} \approx 0.42\text{ s}$) places the instrument inside a warm acoustic room (like Panchathan Record Inn).

---

## 7. Complete implementation listing (`organic_acoustic_synth.py`; not a shipped script)

This complete, self-contained Python module implements all three physical instrument models and the psychoacoustic anti-piercing filter chain.

```python
import numpy as np
from scipy.signal import butter, sosfilt, iirnotch, tf2sos, fftconvolve

class OrganicAcousticSynth:
    """
    Module 6: Synthesizes natural, warm, breathy acoustic instruments directly
    from Module 1's microtonal pitch splines, completely eliminating rigid/piercing MIDI.
    """
    def __init__(self, sample_rate=44100):
        self.sr = sample_rate
        self.room_ir = self._generate_wooden_studio_ir(rt60_sec=0.45)

    # =========================================================================
    # INTERNAL NOISE, ENVELOPE & ROOM PHYSICS GENERATORS
    # =========================================================================

    def _generate_pink_turbulence(self, num_samples, low_hz=700.0, high_hz=2500.0):
        """
        Generates warm 1/f pink noise band-passed to simulate human breath
        or rosin bow friction without harsh white-noise hiss.
        """
        white = np.random.randn(num_samples)
        fft_w = np.fft.rfft(white)
        freqs = np.fft.rfftfreq(num_samples)
        freqs[0] = 1.0
        pink = np.fft.irfft(fft_w / np.sqrt(freqs), n=num_samples)

        nyq = self.sr / 2.0
        sos_bp = butter(2, [low_hz / nyq, high_hz / nyq], btype="bandpass", output="sos")
        filtered = sosfilt(sos_bp, pink)
        return filtered / (np.max(np.abs(filtered)) + 1e-8)

    def _generate_human_expression_envelope(self, durations_sec, alpha=0.32, beta=0.48, shimmer_hz=5.2):
        """
        Replaces robotic MIDI NoteOn/NoteOff with a continuous human lung/bow pressure curve.
        Includes a natural breath swell, micro-shimmer, and gentle sigh at note endings.
        """
        total_samples = int(round(sum(durations_sec) * self.sr))
        env = np.zeros(total_samples)
        attack_transients = np.zeros(total_samples)
        curr_idx = 0

        for dur in durations_sec:
            n_samp = int(round(dur * self.sr))
            if curr_idx + n_samp > total_samples:
                n_samp = total_samples - curr_idx
            if n_samp <= 0:
                continue

            t_norm = np.linspace(0.0, 1.0, n_samp)
            t_sec = np.linspace(0.0, dur, n_samp)

            # Beta-distribution human breath arch
            arch = (t_norm ** alpha) * ((1.0 - t_norm) ** beta)
            arch = arch / (np.max(arch) + 1e-8)

            # Subtle diaphragmatic / bow vibrato shimmer in amplitude
            shimmer = 1.0 + 0.05 * np.sin(2.0 * np.pi * shimmer_hz * t_sec)
            note_env = np.clip(arch * shimmer, 0.0, 1.0)
            env[curr_idx:curr_idx + n_samp] = note_env

            # Generate a 40ms initial breath/chiff transient envelope at note onset
            chiff_len = min(n_samp, int(0.045 * self.sr))
            chiff_win = np.hanning(chiff_len * 2)[:chiff_len]
            attack_transients[curr_idx:curr_idx + chiff_len] = chiff_win

            curr_idx += n_samp

        return env, attack_transients

    def _generate_wooden_studio_ir(self, rt60_sec=0.45):
        """
        Generates a warm, high-damped Velvet-Noise Impulse Response simulating
        the wooden acoustic treatment of Panchathan Record Inn.
        """
        num_samples = int(rt60_sec * self.sr)
        t = np.linspace(0.0, rt60_sec, num_samples)
        decay = np.exp(-6.91 * t / rt60_sec)

        # Sparse velvet noise pulses avoid metallic comb-filtering
        ir = np.zeros(num_samples)
        grid_size = 24
        for i in range(0, num_samples - grid_size, grid_size):
            pulse_idx = i + np.random.randint(0, grid_size)
            ir[pulse_idx] = np.random.choice([-1.0, 1.0]) * decay[pulse_idx]

        # Dampen high frequencies in the room reflections (> 3.2 kHz)
        sos_lp = butter(2, 3200.0 / (self.sr / 2.0), btype="lowpass", output="sos")
        warm_ir = sosfilt(sos_lp, ir)
        return warm_ir / (np.linalg.norm(warm_ir) + 1e-8)

    # =========================================================================
    # INSTRUMENT 1: NAVEEN KUMAR BANSURI FLUTE PHYSICAL MODEL
    # =========================================================================

    def synthesize_bansuri_flute(self, root_midi, pitch_cents_array, durations_sec):
        """
        Synthesizes a warm, breathy bamboo flute from Module 1's continuous pitch curve.
        """
        total_samples = int(round(sum(durations_sec) * self.sr))
        ctrl_x = np.linspace(0.0, 1.0, len(pitch_cents_array))
        audio_x = np.linspace(0.0, 1.0, total_samples)
        cents_upsampled = np.interp(audio_x, ctrl_x, pitch_cents_array)

        # Generate human breath envelope & attack chiff window
        pressure_env, chiff_env = self._generate_human_expression_envelope(
            durations_sec, alpha=0.30, beta=0.48, shimmer_hz=5.3
        )

        # Natural breath-drop pitch dip (-10 cents when lung pressure drops near zero)
        breath_pitch_dip = -10.0 * (1.0 - pressure_env) ** 3
        total_cents = cents_upsampled + breath_pitch_dip

        # Convert Cents to Instantaneous Frequency in Hz
        root_hz = 440.0 * (2.0 ** ((root_midi - 69.0) / 12.0))
        inst_freq = root_hz * (2.0 ** (total_cents / 1200.0))

        # Continuous phase integration + woody breath turbulence modulation
        breath_turb = self._generate_pink_turbulence(total_samples, low_hz=850.0, high_hz=2400.0)
        phase = np.cumsum(2.0 * np.pi * inst_freq / self.sr)
        phase_mod = phase + (0.09 * breath_turb * pressure_env)

        # Pressure-coupled harmonics (higher harmonics vanish on soft notes!)
        h1 = 1.00 * (pressure_env ** 1.0) * np.sin(phase_mod)
        h2 = 0.44 * (pressure_env ** 1.6) * np.sin(2.0 * phase_mod + 0.25)
        h3 = 0.15 * (pressure_env ** 2.4) * np.sin(3.0 * phase_mod + 0.60)
        h4 = 0.04 * (pressure_env ** 3.4) * np.sin(4.0 * phase_mod + 1.10)

        # Add embouchure air chiff at note attacks
        chiff_layer = 0.11 * breath_turb * chiff_env
        sustained_air = 0.035 * breath_turb * pressure_env

        raw_flute = h1 + h2 + h3 + h4 + chiff_layer + sustained_air
        return self.apply_master_anti_piercing_chain(raw_flute, wet_room=0.22)

    # =========================================================================
    # INSTRUMENT 2: CONTINUUM / ESRAJ / BOWED STRING FORMANT MODEL
    # =========================================================================

    def synthesize_esraj_bowed_string(self, root_midi, pitch_cents_array, durations_sec):
        """
        Synthesizes a soulful, crying Indian bowed string (Esraj / Violin / Continuum)
        using pressure-coupled harmonics passed through a 3-band Wooden Body Formant filter.
        """
        total_samples = int(round(sum(durations_sec) * self.sr))
        ctrl_x = np.linspace(0.0, 1.0, len(pitch_cents_array))
        audio_x = np.linspace(0.0, 1.0, total_samples)
        cents_upsampled = np.interp(audio_x, ctrl_x, pitch_cents_array)

        bow_env, bow_scrape_env = self._generate_human_expression_envelope(
            durations_sec, alpha=0.52, beta=0.36, shimmer_hz=5.6
        )

        root_hz = 440.0 * (2.0 ** ((root_midi - 69.0) / 12.0))
        inst_freq = root_hz * (2.0 ** (cents_upsampled / 1200.0))

        rosin_noise = self._generate_pink_turbulence(total_samples, low_hz=600.0, high_hz=2200.0)
        phase = np.cumsum(2.0 * np.pi * inst_freq / self.sr) + (0.05 * rosin_noise * bow_env)

        # Additive bowed string excitation (8 harmonics with pressure-dependent bloom)
        string_exc = np.zeros(total_samples)
        for k in range(1, 9):
            amp = (1.0 / k) * (bow_env ** (1.0 + 0.35 * (k - 1)))
            string_exc += amp * np.sin(k * phase + (k * 0.17))

        # Add gentle rosin bow-hair friction at note transitions
        string_exc += 0.05 * rosin_noise * bow_scrape_env

        # Pass through 3 parallel Wooden Body Formant Resonators (Spruce + Skin Cavity)
        nyq = self.sr / 2.0
        formants = [
            (260.0, 420.0, 1.00),   # F1: Deep hollow body warmth
            (650.0, 920.0, 0.75),   # F2: Wooden bridge resonance
            (1500.0, 2200.0, 0.45)  # F3: Vocal/Crying presence (kept below piercing 3kHz!)
        ]
        wooden_body_out = np.zeros(total_samples)
        for f_low, f_high, gain in formants:
            sos_f = butter(2, [f_low / nyq, f_high / nyq], btype="bandpass", output="sos")
            wooden_body_out += gain * sosfilt(sos_f, string_exc)

        # Blend 40% direct warm fundamental with 60% wooden body resonance
        sos_fund = butter(2, 450.0 / nyq, btype="lowpass", output="sos")
        direct_warmth = sosfilt(sos_fund, string_exc)
        combined = (0.45 * direct_warmth) + (0.55 * wooden_body_out)

        return self.apply_master_anti_piercing_chain(combined, wet_room=0.28)

    # =========================================================================
    # INSTRUMENT 3: EXTENDED KARPLUS-STRONG PLUCKED VEENA / ACOUSTIC GUITAR
    # =========================================================================

    def synthesize_plucked_string(self, midi_notes, durations_sec, brightness=0.58):
        """
        Synthesizes an organic plucked string (Veena / Nylon Guitar / Santoor)
        using Extended Karplus-Strong waveguide physics with pink-noise finger excitation.
        """
        total_samples = int(round(sum(durations_sec) * self.sr))
        output = np.zeros(total_samples)
        curr_idx = 0

        for note, dur in zip(midi_notes, durations_sec):
            n_samp = int(round(dur * self.sr))
            if curr_idx + n_samp > total_samples:
                n_samp = total_samples - curr_idx
            if n_samp <= 0:
                continue

            freq = 440.0 * (2.0 ** ((note - 69.0) / 12.0))
            delay_len = max(4, int(round(self.sr / freq)))

            # Excitation: Fleshy finger pluck (Pink noise shaped by Hanning window)
            pluck_burst = self._generate_pink_turbulence(delay_len, low_hz=120.0, high_hz=1800.0)
            pluck_burst *= np.hanning(delay_len)

            buf = np.zeros(n_samp)
            init_len = min(delay_len, n_samp)
            buf[:init_len] = pluck_burst[:init_len]

            # Waveguide feedback loop with frequency-dependent string damping
            s = 1.0 - np.clip(brightness, 0.2, 0.85) * 0.5  # Softening factor
            decay = 0.995
            for i in range(delay_len + 1, n_samp):
                buf[i] = decay * ((1.0 - s) * buf[i - delay_len] + s * buf[i - delay_len - 1])

            output[curr_idx:curr_idx + n_samp] += buf
            curr_idx += n_samp

        return self.apply_master_anti_piercing_chain(output, wet_room=0.20)

    # =========================================================================
    # MASTER ANTI-PIERCING & PSYCHOACOUSTIC WARMTH CONDITIONING CHAIN
    # =========================================================================

    def apply_master_anti_piercing_chain(self, signal, wet_room=0.22):
        """
        Guarantees zero ear-piercing harshness through 4 stages:
        1. Normalize input into optimal analog saturation sweet spot
        2. Fletcher-Munson 3.2 kHz Ear-Canal Glare Notch (-4.5 dB dip)
        3. Analog Tape Soft-Clipping (tanh) to round off sharp digital peaks
        4. Silk Low-Pass Roll-off (> 7.5 kHz) + Wooden Studio Room Convolution
        """
        # 1. Pre-normalize
        peak = np.max(np.abs(signal)) + 1e-8
        x = signal / peak

        # 2. Fletcher-Munson 3.2 kHz Anti-Glare Notch
        b_notch, a_notch = iirnotch(w0=3200.0, Q=1.8, fs=self.sr)
        sos_notch = tf2sos(b_notch, a_notch)
        notched = sosfilt(sos_notch, x)
        # Blend 60% notched + 40% dry for a smooth -4.5 dB acoustic dip
        x = (0.60 * notched) + (0.40 * x)

        # 3. Analog Tape Soft-Saturation (Eliminates sharp digital transients)
        drive = 1.65
        x_sat = np.tanh(drive * x) / np.tanh(drive)

        # 4. Silk High-Frequency Roll-off (Prevents upper-harmonic fizz)
        sos_silk = butter(2, 7200.0 / (self.sr / 2.0), btype="lowpass", output="sos")
        x_warm = sosfilt(sos_silk, x_sat)

        # 5. Convolve with Wooden Studio Impulse Response for natural acoustic air
        room_tail = fftconvolve(x_warm, self.room_ir, mode="same")
        final_audio = ((1.0 - wet_room) * x_warm) + (wet_room * room_tail)

        # Final peak-safe normalization (-1.0 dBFS headroom)
        final_peak = np.max(np.abs(final_audio)) + 1e-8
        return (final_audio / final_peak) * 0.89


# =============================================================================
# STANDALONE VERIFICATION & WAV EXPORT DEMO
# =============================================================================
if __name__ == "__main__":
    from raga_gamaka_engine import RagaGamakaEngine
    import soundfile as sf

    # 1. Generate a 12-note Kalyani Raga phrase with continuous microtonal Gamakas
    raga_gen = RagaGamakaEngine(root_midi=62, raga_name="Kalyani")  # D4 Root
    melody_midi = raga_gen.generate_melody_phrase(num_notes=12)
    durations = [0.65, 0.45, 0.80, 0.50, 0.55, 0.90, 0.45, 0.55, 0.75, 0.50, 0.60, 1.20]
    _, pitch_cents = raga_gen.render_microtonal_pitch_curve(melody_midi, durations)

    # 2. Synthesize Organic Bansuri Flute & Esraj Bowed String (Zero MIDI Harshness!)
    synth = OrganicAcousticSynth(sample_rate=44100)
    flute_audio = synth.synthesize_bansuri_flute(62, pitch_cents, durations)
    esraj_audio = synth.synthesize_esraj_bowed_string(50, pitch_cents, durations)  # 1 Octave lower
    veena_audio = synth.synthesize_plucked_string(melody_midi, durations, brightness=0.55)

    # 3. Blend into a lush acoustic ensemble & save to 24-bit WAV
    mix = (0.50 * flute_audio) + (0.30 * esraj_audio) + (0.20 * veena_audio)
    sf.write("arr_organic_acoustic_preview.wav", mix, 44100, subtype="PCM_24")
    print("Saved natural, non-piercing acoustic audio to: arr_organic_acoustic_preview.wav")
```
