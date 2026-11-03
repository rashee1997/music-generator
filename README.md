# music-generator

A programmatic, research-backed music composition, multi-engine rendering, and psychoacoustic CI/CD verification engine.

---

## 1. The Core Problem with Code-Generated Music

When LLMs or algorithmic scripts generate music (MIDI or raw audio), they suffer from specific perceptual defects because **text models cannot hear what they write**:

1. **Mechanical Rigidity vs. Random Chaos:**
   - Naive code locks notes to exact grid ticks with static velocities (sounding like a 1990s MIDI file).
   - If prompted to "humanize" or "vary", LLMs scatter notes unpredictably, generating zig-zag melodies, unrecovered leaps, and rhythmic incoherence that technically pass simple rules while sounding unmusical.
2. **Harmonic Mud & Voicing Violations:**
   - Chord voices clustered below middle C violate the **Low-Interval Limit (Huron 2001)**, muddying the 100–300 Hz region.
   - Closed-position major 7ths voice roots and 7ths adjacent in the same register (e.g. B3 and C4), creating grating minor-2nd interference.
3. **Cochlear Sensory Roughness:**
   - Multi-instrument arrangements stack overtones that collide within **1/4 of an auditory critical bandwidth**, causing rapid basilar membrane beating (roughness) that tires human ears.
4. **Spectral Masking & Missing Separation:**
   - Pads, rhythm guitars, and bass swallow vocal/lead melodies in the 250–500 Hz region without frequency pocket carving or binaural unmasking.
5. **Static Harmony & Broken Tension:**
   - Progressions either stagnate indefinitely or "teleport" between unrelated keys without voice leading, failing to resolve tension at cadences.

---

## 2. What This Skill Solves & How

This engine establishes an automated **7-Stage CI/CD Pipeline** that constrains music generation within the corridor of **human auditory neuroscience and psychoacoustics**:

```
[Brief / Prompt / Score]
        │
   Stage 1: Composition, Voice-Leading & Culture Fusion (compose.py, theory.py, world.py)
        │
   Stage 2: Acoustic & Cognitive Preflight Linter (pattern_audit.py: 10 Cognitive Laws)
        │
   Stage 3: Humanization & Phrase Respiration (humanize.py: shared tempo drift, motor error, rubato, E(t))
        │
   Stage 4: Multi-Engine Stem Rendering (tinysoundfont with oversampling and mechanism noise, vocals.py, environment.py, spatial.py)
        │
   Stage 5: High-Precision Mixing & Mastering (mixer.py: gain staging, EQ, dynamics, shared space, limiter;
            strategies and diagnostics driven by the piece's mix preset)
        │
   Stage 6: Automated CI Quality Suite (quality_gate.py, naturalness_check.py, music21)
        │
   Stage 7: Certified Release Packaging (WAV, MIDI, stems/, ci_report.json)
```

### Key Modules & Capabilities

- **Meyer's Gap-Fill & Melodic Contour Law:** Enforces $\ge 45\%$ conjunct step motion; large leaps ($\ge 5$ semitones) must resolve in the opposite direction.
- **Harmonic Resolution Gravity:** Chromatic non-scale tension notes must step into adjacent chord tones; exempts genuine microtonal ornamentation ($c \ne 0$).
- **Chew's 3D Spiral Array Tonal Tension:** Helical line-of-fifths projection measuring Cloud Diameter (chord spread), Cloud Momentum (voice-leading speed), and Tensile Strain (distance from tonic).
- **Witek-Vuust Syncopation Curve:** Dynamic metric tree across any meter ($4/4, 3/4, 6/8, 5/4, 7/8, 12/8$) measuring Bar Syncopation Index ($BSI$). Prevents robotic marches ($BSI < 0.15$) and metric collapse ($BSI > 5.5$).
- **IDyOM Information Entropy:** Shannon entropy ($H$) and Markov surprise ($I = -\log_2 P$) ensuring optimal human cognitive interest ($1.2 \le H \le 3.8$ bits).
- **Plomp-Levelt & Sethares Cochlear Sensory Roughness:** 1.0s Hann-windowed basilar membrane critical-band analysis across 80–6000 Hz, detecting overtone clashes and outro cadence resolution.
- **Moore-Glasberg ERB Binaural Masking:** 8 equivalent rectangular bandwidth filters ($250 - 4000\text{ Hz}$) with $+3.5\text{ dB}$ Binaural Masking Level Difference ($\Delta BMLD$) stereo panning bonus.
- **Environmental Bed Stability:** Enforces dropout-free ambient soundscapes ($>-58\text{ dBFS}$) and flags gain pumping ($|\Delta\text{RMS}| \le 3.8\text{ dB}$).
- **Naturalness by measurement, not by wish:** the humanizer separates the tempo drift a section shares from each player's own motor error (measured lag-1 −0.58), scales drum push with tempo, and couples velocity to duration; the renderer oversamples the sampler (its linear interpolation leaves audible images when a note is transposed) and adds the noise a mechanism makes at note-on and note-off, per instrument class.
- **Spatial staging:** per-stem azimuth pan, distance filter/level/reverb send, width and a shared room in `mixer.py`; `spatial.py` holds ITD/HRTF-style tools that are not in the default mix. Measured-HRTF binaural and an immersive mode (height per role, headphone fold-down checks) are opt-in per mix preset.
- **Preset-driven, never hardcoded:** sound, space, mix strategy, gate profile and every spatial number live in JSON presets (`presets.py scaffold`); scripts only write notes.

---

## 3. Auditing Existing Music (`--check-only`)

You can audit pre-existing tracks, stems, and scores without re-rendering or altering audio:

```powershell
# Direct check on an existing master WAV
python scripts/pipeline.py path/to/master.wav --check-only

# Or specify project stems, presets, and score explicitly
python scripts/pipeline.py --check-only \
  --wav path/to/master.wav \
  --score path/to/score.json \
  --presets-dir path/to/presets \
  --stems-dir path/to/stems
```

**Auto-Discovery Features:**
- Automatically adopts instrument/environmental presets from adjacent `presets/` folders.
- Automatically loads pre-rendered stems from adjacent `stems/` folders for masking and grid checks.
- Generates a full scoreboard and outputs an actionable `ci_report.json` in `reports/`.

---

## 4. Structure

```
music-generator/
├── scripts/           # Core engine (pipeline, compose, mix, render, quality gates, extraction)
├── scripts/extraction/# Pure-DSP song decomposition/reconstruction
├── scripts/vocal_engine/# Formant vocal synthesis
├── scripts/spatial_hrtf/# Vendored spaudiopy + measured HRTF support
├── video-mixer/       # Video scoring, dialogue ducking, program mix & mux
├── references/        # Psychoacoustic specs, direction guides, quality criteria
├── knowledgebase/     # Domain research (world music, DSP, SFX, adaptive music)
├── templates/         # Scaffolds and analyzers
├── tests/             # Selftests and regression suites
├── requirements.txt   # Core dependencies
└── SKILL.md           # Agent instructions
```

---

## 5. Taking a Song Apart (`extract_pipeline.py`)

Pure-DSP, CPU-only, guided by a listening model's `music_db`. Scope: instruments (and humming), drums, space and ambience (no sung vocals).
Finds the notes, repairs them as MIDI, then rebuilds each stem from that MIDI (a sampler of the song's own cleanest notes where there
are enough, additive synthesis otherwise), adds drums, ambience, effects and a fitted room, and gates the rebuilt mix against the
original with checks borrowed from the main quality gate. Own environment (`requirements-extraction.txt`, no neural models).
Full guide: `references/extraction.md`.

```powershell
python scripts/extract_pipeline.py setup --new-project <project_dir> --song path/to/song.mp3
python scripts/extract_pipeline.py check-db <project_dir>
python scripts/extract_pipeline.py run <project_dir>
```

---

## 6. Highlights

- **Pure Vectorized Math (<50ms execution):** All cognitive, acoustic, and psychoacoustic checks run on NumPy/SciPy without neural weights, heavy models, or external servers.
- **Zero Hallucination / Self-Healing Feedback:** Every gate failure outputs exact timestamps, offending tracks, measured metrics, and plain-English musical prescriptions so an LLM composer can self-correct the score JSON.
- **Microtonal & Cultural Integrity:** Supports continuous microtonal pitch space ($p_{\text{cont}} = p + c / 100$), Maqamat quartertones, Indian shruti, and Gamelan slendro/pelog tunings without snapping to 12-TET.
- **Gate profiles:** the CI battery is chosen from the music (melodic, cinematic, ambient, dance, tense, effects only) or a piece's own profile, and every relaxed row is reported with its measured reason.
- **Non-Destructive Project Audits:** Quickly inspects existing master WAVs against project stems and presets in seconds.

---

## 7. Quickstart

### Run Selftests
```powershell
# Verify quality gates & psychoacoustic calculations
python scripts/quality_gate.py --selftest

# Verify complete 7-stage CI/CD pipeline
python scripts/pipeline.py --selftest
```

### Generate Music from Prompt
```powershell
# real music: python scripts/pipeline.py <project>/scores/<title>_score.json --project <project>   (see SKILL.md)
python scripts/pipeline.py "meditative ambient in D dorian, 60s" --test --out final.wav   # smoke test only
```

### Quality Audit Existing Production
```powershell
python scripts/pipeline.py path/to/master.wav --check-only
```

## 8. Credits

- `scripts/spatial_hrtf/` contains a vendored copy of [spaudiopy](https://github.com/chris-hld/spaudiopy) by Chris Hold (MIT License, kept in `scripts/spatial_hrtf/LICENSE`) with the small changes listed in `scripts/spatial_hrtf/README.md`.
- Head-Related Transfer Function data is from the **FABIAN HRTF Database**, TU Berlin, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ([DOI: 10.14279/depositonce-5718.5](https://doi.org/10.14279/depositonce-5718.5)), downloaded via `setup_project.py` and not bundled in this repository.
- SoundFont synthesis utilizes [tinysoundfont](https://github.com/schellingb/tinysoundfont) by Bernhard Schelling (MIT License) with the [GeneralUser GS SoundFont](https://schristiancollins.com/generaluser.php) by S. Christian Collins.

---

## 9. Third-Party Libraries, Attributions & Key Equations

All dependencies are used in accordance with their respective open-source licenses.

### Core Scientific Computing
| Library | License | Repository & Docs | Purpose & Key Mathematical Operations |
|---|---|---|---|
| [NumPy](https://numpy.org/) | BSD-3-Clause | [GitHub](https://github.com/numpy/numpy) | Vectorized numerical computation, linear algebra, FFT operations for spectral analysis, windowing functions |
| [SciPy](https://scipy.org/) | BSD-3-Clause | [GitHub](https://github.com/scipy/scipy) | Digital signal processing (`scipy.signal`), IIR/FIR filter design, Welch PSD, polyphase decimation (`resample_poly`) |

### Audio I/O & Processing
| Library | License | Repository & Docs | Purpose & Key Algorithms Used |
|---|---|---|---|
| [soundfile](https://python-soundfile.readthedocs.io/) | BSD-3-Clause | [GitHub](https://github.com/bastibe/python-soundfile) | C-level audio file I/O via libsndfile; bit-depth preservation (32-bit float streaming) |
| [Pedalboard](https://spotify.github.io/pedalboard/) | GPL-3.0 | [GitHub](https://github.com/spotify/pedalboard) | Spotify DSP engine: true-peak brickwall limiting, dynamic compression, stereo spatialization |
| [pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) | MIT | [GitHub](https://github.com/csteinmetz1/pyloudnorm) | EBU R128 & ITU-R BS.1770-4 loudness measurement with K-weighting pre-filter |

### MIDI & Music Theory
| Library | License | Repository & Docs | Purpose & Key Algorithms Used |
|---|---|---|---|
| [pretty_midi](https://craffel.github.io/pretty-midi/) | MIT | [GitHub](https://github.com/craffel/pretty-midi) | MIDI 1.0 container parsing, timing quantization, note array extraction |
| [mido](https://mido.readthedocs.io/) | MIT | [GitHub](https://github.com/mido/mido) | Real-time and file-based MIDI stream serialization |
| [music21](https://web.mit.edu/music21/) | BSD-3-Clause / LGPL | [GitHub](https://github.com/cuthbertLab/music21) | Computational musicology, Roman numeral voice-leading analysis, tonal pitch class matrices |

### Audio Analysis & Machine Learning Tools
| Library | License | Repository & Docs | Purpose & Key Algorithms Used |
|---|---|---|---|
| [librosa](https://librosa.org/) | ISC | [GitHub](https://github.com/librosa/librosa) | Short-Time Fourier Transform (STFT), constant-Q transform (CQT), 12-bin chroma profiling, onset envelope detection |
| [matplotlib](https://matplotlib.org/) | PSF | [GitHub](https://github.com/matplotlib/matplotlib) | Offline diagnostic plotting of spectral masking curves, roughness surfaces, and rhythm trees |

### Spatial Audio & Utilities
| Library | License | Repository & Docs | Purpose & Key Algorithms Used |
|---|---|---|---|
| [h5py](https://www.h5py.org/) | BSD-3-Clause | [GitHub](https://github.com/h5py/h5py) | HDF5 binary access for multidimensional SOFA / FABIAN HRTF impulse response grids |
| [requests](https://requests.readthedocs.io/) | Apache-2.0 | [GitHub](https://github.com/psf/requests) | Secure HTTPS asset acquisition for soundbanks and acoustic impulse responses |
| [resampy](https://github.com/bmcfee/resampy) | ISC | [GitHub](https://github.com/bmcfee/resampy) | High-order bandlimited sinc interpolation for sample-rate conversion |

---

### Psychoacoustic & Music Theory Foundations

This engine implements formal computational models from peer-reviewed acoustic and cognitive literature:

| Model | Canonical Citation & Link | Purpose & Defining Mathematical Formulation |
|---|---|---|
| **Low-Interval Limit (LIL)** | Huron, D. (2001). [Tone and Voice: A Derivation of the Rules of Voice-Leading from Perceptual Principles](https://doi.org/10.1525/mp.2001.19.1.1). *Music Perception*, 19(1), 1–64. | Enforces register-dependent frequency minimums to prevent basilar membrane critical-band roughness in the low register ($f < 250\text{ Hz}$). |
| **Krumhansl-Schmuckler Key Profiles** | Krumhansl, C. L. (1990). [*Cognitive Foundations of Musical Pitch*](https://global.oup.com/academic/product/cognitive-foundations-of-musical-pitch-9780195148367). Oxford University Press. | Tonal hierarchy correlation measuring pitch-class distributions against perceptual probe-tone ratings: $r = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sqrt{\sum (x_i - \bar{x})^2 \sum (y_i - \bar{y})^2}}$. |
| **Chew's Spiral Array** | Chew, E. (2000). [*Towards a Mathematical Model of Tonality*](https://dspace.mit.edu/handle/1721.1/9139). Doctoral dissertation, MIT. | Maps pitch classes into a 3D helical space where line-of-fifths intervals are contiguous: $\mathbf{p}(k) = \left[ r \sin\left(\frac{k\pi}{2}\right), r \cos\left(\frac{k\pi}{2}\right), k \cdot h \right]^T$. Measures Tensile Strain and Cloud Momentum. |
| **Plomp-Levelt Sensory Consonance** | Plomp, R., & Levelt, W. J. M. (1965). [Tonal Consonance and Critical Bandwidth](https://doi.org/10.1121/1.1909741). *JASA*, 38(4), 548–560. | Predicts dissonance between partials $f_1, f_2$ as a function of critical bandwidth ($CB$): $d(f_1, f_2) = e^{-a s \Delta f} - e^{-b s \Delta f}$, peaking when frequency separation is $\approx 25\%$ of the critical band. |
| **Sethares Dissonance Curves** | Sethares, W. A. (1998 / 2005). [*Tuning, Timbre, Spectrum, Scale*](https://doi.org/10.1007/978-1-84628-113-6). Springer-Verlag. | Generalizes sensory dissonance to arbitrary non-harmonic spectra and microtonal temperaments by integrating all pairwise partial clashes across complex tones. |
| **Witek-Vuust Syncopation Curve** | Witek, M. A. G. et al. (2014). [Syncopation, Body-Movement and Pleasure in Groove Music](https://doi.org/10.1371/journal.pone.0094446). *PLOS ONE*, 9(4), e94446. | Enforces an inverted U-shaped groove index across metric levels using the Bar Syncopation Index ($BSI$): $0.15 \le BSI \le 5.5$. |
| **Moore-Glasberg ERB Auditory Filters** | Moore, B. C. J., & Glasberg, B. R. (1983). [Suggested formulae for calculating auditory-filter bandwidths and excitation patterns](https://doi.org/10.1121/1.389861). *JASA*, 74(3), 750–753. | Calculates Equivalent Rectangular Bandwidth for auditory masking pockets: $\text{ERB}(f) = 24.7 \cdot (4.37 \cdot f / 1000 + 1)\text{ Hz}$. |
| **Meyer's Gap-Fill Principle** | Meyer, L. B. (1956). [*Emotion and Meaning in Music*](https://press.uchicago.edu/ucp/books/book/chicago/E/bo5479468.html). University of Chicago Press. | Expectation rule mandating that wide melodic disjunct leaps ($\ge 5$ semitones) resolve conjunctly in the opposite direction ($\ge 45\%$ step motion). |
| **IDyOM Information Dynamics** | Pearce, M. T. (2005). [*The Construction and Evaluation of Statistical Models of Melodic Predictability*](https://qmro.qmul.ac.uk/xmlui/handle/123456789/1376). PhD Thesis, City University London. | Variable-order Markov Shannon entropy ($1.2 \le H \le 3.8\text{ bits}$) and information surprise ($I = -\log_2 P$) ensuring compositions balance predictability with cognitive interest. |
| **ITU-R BS.1770-4 / EBU R128** | International Telecommunication Union (2015). [ITU-R BS.1770-4](https://www.itu.int/rec/R-REC-BS.1770-4-201510-I/en). | Standardized loudness gating: $L_K = -0.691 + 10 \log_{10} \sum_{i} G_i \cdot z_i$ after pre-filtering through high-pass and high-frequency shelf curves (RLB/K-weighting). |