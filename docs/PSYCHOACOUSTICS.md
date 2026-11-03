# Psychoacoustics & Theoretical Foundations

This system is grounded in established auditory neuroscience and music perception research.

## Cognitive & Perceptual Laws Enforced

| Law | Implementation | Threshold/Rule | Reference |
|---|---|---|---|
| **Meyer's Gap-Fill & Melodic Contour Law** | `pattern_audit.py` | ≥ 45% conjunct step motion; leaps ≥ 5 semitones must resolve in opposite direction | Meyer (1956), Narmour (1990) |
| **Harmonic Resolution Gravity** | `pattern_audit.py`, `theory.py` | Chromatic non-scale tension notes must step to adjacent chord tones; exempts microtonal ornamentation ($c \neq 0$) | Huron (2001) |
| **Chew's 3D Spiral Array Tonal Tension** | `pattern_audit.py` | Helical line-of-fifths projection measuring Cloud Diameter, Cloud Momentum, Tensile Strain from tonic | Chew (2000, 2001) |
| **Witek-Vuust Syncopation Curve** | `pattern_audit.py` | Dynamic metric tree for any meter ($4/4, 3/4, 6/8, 5/4, 7/8, 12/8$). Bar Syncopation Index ($BSI$): $0.15 \le BSI \le 5.5$ | Witek et al. (2014) |
| **IDyOM Information Entropy** | `pattern_audit.py` | Shannon entropy $H = -\sum p_i \log_2 p_i$ and Markov surprise $I = -\log_2 P$. Optimal interest: $1.2 \le H \le 3.8$ bits | Pearce & Wiggins (2006) |
| **Plomp-Levelt & Sethares Cochlear Sensory Roughness** | `naturalness_check.py` | 1.0s Hann-windowed basilar membrane critical-band analysis 80–6000 Hz. Detects overtone clashes and cadence resolution | Plomp & Levelt (1965), Sethares (1993) |
| **Moore-Glasberg ERB Binaural Masking** | `mixer.py`, `spatial.py` | 8 Equivalent Rectangular Bandwidth filters ($250 - 4000\text{ Hz}$) with $+3.5\text{ dB}$ Binaural Masking Level Difference ($\Delta BMLD$) stereo panning bonus | Moore & Glasberg (1983, 1996) |
| **Environmental Bed Stability** | `quality_gate.py` | Dropout-free ambient beds ($>-58\text{ dBFS}$), gain pumping limit ($|\Delta\text{RMS}| \le 3.8\text{ dB}$) | - |

## Key Equations

### Shannon Entropy (IDyOM)
$$
H = -\sum_{i} p_i \log_2 p_i
$$

### Markov Surprise
$$
I(e) = -\log_2 P(e \mid context)
$$

### Bar Syncopation Index (BSI)
Computed via dynamic metric tree weighting across metrical positions per meter.

### Binaural Masking Level Difference
$$
\Delta BMLD \approx +3.5\text{ dB}
$$
Applied as stereo panning bonus in the $250-4000\text{ Hz}$ ERB range.

### Critical Band Roughness
Analyzed via critical band decomposition with beating detection in adjacent frequency components.

## References

- Chew, E. (2000). Towards a mathematical model of tonality. PhD thesis, MIT.
- Huron, D. (2001). Tone and voice: A derivation of the rules of voice-leading from perceptual principles. *Music Perception*, 19(1), 1-64.
- Meyer, L. B. (1956). *Emotion and Meaning in Music*. University of Chicago Press.
- Moore, B. C. J., & Glasberg, B. R. (1983). Suggested formulae for calculating auditory-filter bandwidths and excitation patterns. *JASA*, 74, 750-753.
- Narmour, E. (1990). *The Analysis and Cognition of Basic Melodic Structures*. University of Chicago Press.
- Pearce, M. T., & Wiggins, G. A. (2006). Expectation in melody: The influence of context and learning. *Music Perception*, 23, 377-405.
- Plomp, R., & Levelt, W. J. M. (1965). Tonal consonance and critical bandwidth. *JASA*, 38, 548-560.
- Sethares, W. A. (1993). Local consonance and the relationship between timbre and scale. *JASA*, 94, 1218-1228.
- Witek, M. A. G. et al. (2014). Syncopation, body-movement and pleasure in groove music. *PLoS ONE*, 9(4), e94446.
