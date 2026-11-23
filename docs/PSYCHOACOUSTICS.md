# Psychoacoustics & Theoretical Foundations

This system is grounded in established auditory neuroscience and music perception research.

## Cognitive & Perceptual Laws Enforced

| Law | Implementation | Threshold/Rule | Reference |
|---|---|---|---|
| **Meyer's Gap-Fill & Melodic Contour Law** | `pattern_audit.py` | ≥ 45% conjunct step motion; leaps ≥ 5 semitones must resolve in opposite direction | Meyer (1956), Narmour (1990) |
| **Harmonic Resolution Gravity** | `pattern_audit.py`, `theory.py` | Chromatic non-scale tension notes must step to adjacent chord tones; exempts microtonal ornamentation ($c \neq 0$) | Huron (2001) |
| **Chew's 3D Spiral Array Tonal Tension** | `pattern_audit.py` | Helical line-of-fifths projection measuring Cloud Diameter, Cloud Momentum, Tensile Strain from tonic | Chew (2000, 2001) |
| **Witek-Vuust Syncopation Curve** | `pattern_audit.py` | Dynamic metric tree for any meter ($4/4, 3/4, 6/8, 5/4, 7/8, 12/8$). Bar Syncopation Index ($BSI$): $0.15 \le BSI \le 5.5$ | Witek et al. (2014) |
| **IDyOM-style information content** | `expectation.py`, rows in `pattern_audit.py` | Prediction by partial matching (escape C, order 3) over pitch interval, scale degree and inter-onset ratio; each note predicted before it is learned. Information content $I = -\log_2 P(e \mid context)$ and entropy $H = -\sum p_i \log_2 p_i$ per note. Row limits: `feel.entropy` and `expr.surprise_grounded` in `gate_profiles.ROWS` | Pearce & Wiggins (2004, 2006) |
| **Plomp-Levelt & Sethares Cochlear Sensory Roughness** | `naturalness_check.py` | 1.0s Hann-windowed basilar membrane critical-band analysis 80–6000 Hz. Detects overtone clashes and cadence resolution | Plomp & Levelt (1965), Sethares (1993) |
| **Moore-Glasberg ERB Binaural Masking** | `mixer.py`, `spatial.py`, scales in `auditory.py` | 8 Equivalent Rectangular Bandwidth filters ($250 - 4000\text{ Hz}$) with $+3.5\text{ dB}$ Binaural Masking Level Difference ($\Delta BMLD$) stereo panning bonus | Moore & Glasberg (1983, 1996) |
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

## Virtual ears (advisory rows)

Code: `scripts/ear_model/`, rows in `scripts/ear_rows.py`, scales in `scripts/auditory.py`, facts in
`knowledgebase/sound-design/virtual-ears.md`. A streaming model (5 s chunks, state carried) turns the master into a neural
activity pattern at 2240 Hz: middle-ear weighting (inverse absolute threshold), a serial cascade of asymmetric resonators at
ERB spacing (channel = stage input minus stage output), a block-rate compressive gain spread over neighbouring channels
(feed-forward, so one numpy pass; CARFAC proper feeds the level back into each stage), hair-cell rectification, saturation
and low-pass, and two-time-constant divisive adaptation. Rows: `ear.fatigue`, `ear.masking`, `ear.mod_roughness`,
`ear.pitch_salience`, `ear.iacc`. All are INFO or WARN: starting values calibrated on synthetic fixtures. Known limits: the hair
cell saturates, so modulation roughness under-reads loud material; pitch salience stops near 700 Hz; fatigue is a proxy.

## Three-front layout with two low-frequency channels

`lrc_lfe2` (L, R, C, LFE1, LFE2) is a project layout, not a BS.2051 system (`knowledgebase/sound-design/layout-3-2.md`). The
low-frequency pair is mono and in phase below `decorrelate_above_hz` (40 Hz) and decorrelated above it by a bounded
all-pass cascade (3 ms total group delay), so the two subs add under the corner and excite different room modes above it.
Fold chain: 3.2 -> 3.1 (the two LFEs summed with gain $1/\sqrt{2(1+\rho)}$, $\rho$ their correlation) -> BS.775 stereo.
Rows: `lfe.polarity` (FAIL for an inverted sub), `lfe.sum_coherence`, `lfe.fold_loss`, `lfe.modal_spread` (a model of a box
room, not the listener's room), `front.fold_phantom` (centre folded into L/R against a real centre through the measured head set).

## Spatial and room acoustics (Immersive 2.0)

Code: `scripts/spatial_engine/hoa.py`, `scripts/spatial_engine/trajectory.py`, `scripts/spatial_hrtf/room.py`,
`scripts/spatial_hrtf/binaural.py`, `scripts/airabs.py`. How to switch each on: `references/spatial/immersive-spatial.md`.

### The sound field
A source signal $s(t)$ at direction $(\theta, \phi)$ is written into the field as

$$
b_{nm}(t) = s(t)\, Y_n^m(\theta(t), \phi(t)), \qquad 0 \le n \le N,\ |m| \le n
$$

with real, orthonormal spherical harmonics in ACN order and $N = 5$ (36 channels). A moving source only changes the
gains $Y_n^m$ over time, so no filter is switched. AmbiX export rescales each order by $\sqrt{4\pi / (2n+1)}$ (SN3D).

### Headphones: magnitude least squares
The decoding filters $h_{nm}^{L,R}$ solve a least-squares fit to the measured head filters below the transition
frequency $f_t = 600\,N$ Hz and a magnitude-only fit above it, with the phase continued from the bin below
(Schörkhuber, Zaunschirm & Höldrich 2018; Hold, Meyer-Kahlen & Pulkki 2023). The ear signal is
$\sum_{nm} b_{nm} * h_{nm}$.

### Loudspeakers: all-round decoding
$J$ virtual loudspeakers on a near-uniform sphere sample the field; each is panned onto the real layout by VBAP:

$$
D = \frac{4\pi}{J}\, G^{\mathsf T}\, Y\, \mathrm{diag}(w_n)
$$

$G$ holds the VBAP gains of the virtual loudspeakers, $Y$ their harmonics and $w_n$ the max-$r_E$ order weights
(Zotter & Frank 2012). $D$ is scaled so a plane wave keeps unit power on average. VBAP itself picks, among the
loudspeaker triplets that hold a direction with non-negative gains, the one with the smallest gain sum: that is the
face of the layout the direction passes through.

### Air: ISO 9613-1
$$
\alpha(f) = 8.686 f^2 \left[ 1.84\times10^{-11} \frac{p_r}{p} \sqrt{\tfrac{T}{T_0}} + \left(\tfrac{T}{T_0}\right)^{-5/2}
\left( \frac{0.01275\, e^{-2239.1/T}}{f_{rO} + f^2/f_{rO}} + \frac{0.1068\, e^{-3352/T}}{f_{rN} + f^2/f_{rN}} \right) \right]
\ \text{dB/m}
$$

$f_{rO}$, $f_{rN}$ are the oxygen and nitrogen relaxation frequencies (functions of humidity, temperature, pressure).
A still source gets the linear-phase filter $10^{-\alpha(f)\,d/20}$; a moving one gets the same gain per STFT frame
with $d = d(t)$. Check values at 20 °C, 50 % RH: 4.7 dB/km at 1 kHz, 159 dB/km at 10 kHz.

### Early reflections: image sources
In a box, wall reflections are mirror images of the source (Allen & Berkley 1979). An image at path length $r_i$
arrives $(r_i - r_0)/c$ after the direct sound, from its own direction, at amplitude

$$
g_i(f) = \frac{1}{r_i} \prod_{\text{bounces}} \sqrt{1 - a_k(f)}
$$

$a_k$ is the energy absorption of each surface hit, so $\sqrt{1 - a_k}$ is its pressure reflection factor. For a moving
source each image has its own $r_i(t)$, which gives each reflection its own Doppler shift.

### Late field: Eyring and the mixing time
$$
T_{60}(f) = \frac{24 \ln 10}{c} \cdot \frac{V}{-S \ln(1 - \bar a(f)) + 4\, m(f)\, V}, \qquad
t_{mix} \approx 20\, \frac{V}{S} + 12\ \text{ms}
$$

$\bar a$ is the area-weighted mean absorption, $m = \alpha / 4.343$ the power attenuation of air per metre
(Eyring 1930; mixing-time predictor of Lindau, Kosanke & Weinzierl 2012).

### Near field: the distance variation function
A far-field head filter becomes the filter of a nearer source when multiplied by the ratio of two rigid-sphere
responses (Kan, Jin & van Schaik 2009), each from the series of Duda & Martens (1998):

$$
H(\rho, \mu, \theta) = -\frac{\rho}{\mu} e^{-i\mu\rho} \sum_{m=0}^{\infty} (2m+1)\, P_m(\cos\theta)\,
\frac{h_m(\mu\rho)}{h_m'(\mu)}, \qquad \mathrm{DVF} = \frac{|H(\rho_{near})|}{|H(\rho_{ref})|}
$$

$\mu = ka$ is the normalised frequency, $\rho = r/a$ the distance in head radii, $\theta$ the angle between the source
and the ear. Measured here at 25 cm, 90°: +4.2 dB at the near ear and −3.0 dB at the far ear at 100 Hz.

### Doppler
The direct sound is read at $t - \lambda\,(d(t) - d_{min})/c$ with $\lambda$ = `doppler_strength`; a reflection is read
later by its extra path $(r_i(t) - r_0(t))/c$. The read is a cubic spline through the samples.

### Room measures on the impulse response (ISO 3382-1)
With $h_L, h_R$ the two ear responses timed from the direct sound and filtered to one octave:

$$
\mathrm{IACC}_E = \max_{|\tau| \le 1\,\mathrm{ms}}
\frac{\left|\int_0^{80\,\mathrm{ms}} h_L(t)\, h_R(t+\tau)\, dt\right|}
{\sqrt{\int_0^{80\,\mathrm{ms}} h_L^2\, dt \int_0^{80\,\mathrm{ms}} h_R^2\, dt}}, \qquad
C_{80} = 10 \log_{10} \frac{\int_0^{80\,\mathrm{ms}} h^2\, dt}{\int_{80\,\mathrm{ms}}^{\infty} h^2\, dt}\ \text{dB}
$$

The gate reports $\mathrm{IACC}_{E3}$ (mean of the 500, 1000, 2000 Hz octaves) and $C_{80}$ averaged over 500 to
4000 Hz, both on an impulse rendered through the piece's own room (`hoa.probe_brir`). Occupied concert halls measure
$C_{80}$ of about $-5$ to $+5$ dB; the just-noticeable difference is about 1 dB.

### Mono fold-down loss per band
$$
\Delta(b) = 10 \log_{10} \frac{\tfrac12 \sum_{f \in b} (P_{LL} + P_{RR})}
{\tfrac14 \sum_{f \in b} (P_{LL} + P_{RR} + 2\,\mathrm{Re}\, P_{LR})}
$$

0 dB for a centred sound, 3 dB for two unrelated channels, unbounded when they cancel. Bands are one ERB wide,
$\mathrm{ERB\text{-}rate}(f) = 21.4 \log_{10}(0.00437 f + 1)$ (Glasberg & Moore 1990).

## Sources of sound (Immersive 2.0)

### Liljencrants-Fant glottal source
One period of the flow derivative, with $t_p$ the flow peak, $t_e$ the closure and $t_a$ the return time:

$$
E(t) = \begin{cases} E_0\, e^{\alpha t} \sin(\pi t / t_p) & 0 \le t \le t_e \\
-\dfrac{E_e}{\varepsilon t_a} \left[ e^{-\varepsilon (t - t_e)} - e^{-\varepsilon (T_0 - t_e)} \right] & t_e < t \le T_0 \end{cases}
$$

$\varepsilon$ solves $\varepsilon t_a = 1 - e^{-\varepsilon (T_0 - t_e)}$ and $\alpha$ makes the net flow zero. One shape
parameter sets the timing (Fant 1995):

$$
R_a = \frac{-1 + 4.8 R_d}{100}, \quad R_k = \frac{22.4 + 11.8 R_d}{100}, \quad
R_g = \frac{R_k (0.5 + 1.2 R_k)}{4\,(0.11 R_d - R_a (0.5 + 1.2 R_k))}
$$

with $t_p = T_0 / (2 R_g)$, $t_e = t_p (1 + R_k)$, $t_a = R_a T_0$, valid for $0.3 \le R_d \le 2.7$. Code:
`scripts/vocal_engine/source.py`.

### Vibrato as an Ornstein-Uhlenbeck process
Rate and depth each follow $dx = -\frac{x}{\tau}\,dt + \sigma \sqrt{2/\tau}\, dW$, discretised exactly as
$x_{k+1} = a x_k + \sigma \sqrt{1 - a^2}\, \xi_k$ with $a = e^{-\Delta t / \tau}$; the phase is the running sum of the
rate. Code: `scripts/render_natural.py`.

### Sympathetic strings
Each string is a two-pole resonator at $f_k$ with quality $Q$, ringing for $Q / (\pi f_k)$ seconds; the bank is
driven by the sum of the source stems. Code: `dsp.resonator_bank`, `mixer.sympathetic_bed`.

### Animal calls as source and filter
A call is a vibrating source and a tube (Taylor & Reby 2010). For a tube of length $L$ closed at the source:

$$
F_k = \frac{(2k - 1)\, c}{4 L}, \qquad \Delta F = \frac{c}{2L}
$$

so the spacing of the resonances gives the length of the vocal tract, and through it the size of the animal
(Fitch 1997). The source's irregularities are the nonlinear phenomena of Wilden et al. (1998): subharmonics (energy
at $f_0/2$ and its odd multiples), biphonation (two unrelated pitches), deterministic chaos and frequency jumps.
Across species the dominant frequency falls with body mass roughly as $M^{-0.4}$ (Fletcher 2004). In cold-blooded
callers the pulse rate rises linearly with temperature (Gerhardt & Doherty 1988). Code: `scripts/env_engine/calls.py`.

## References

- Allen, J. B., & Berkley, D. A. (1979). Image method for efficiently simulating small-room acoustics. *JASA*, 65, 943-950.
- Chew, E. (2000). Towards a mathematical model of tonality. PhD thesis, MIT.
- Duda, R. O., & Martens, W. L. (1998). Range dependence of the response of a spherical head model. *JASA*, 104, 3048-3058.
- Fant, G. (1995). The LF-model revisited. Transformations and frequency domain analysis. *STL-QPSR*, 36(2-3), 119-156.
- Fant, G., Liljencrants, J., & Lin, Q. (1985). A four-parameter model of glottal flow. *STL-QPSR*, 26(4), 1-13.
- Fitch, W. T. (1997). Vocal tract length and formant frequency dispersion correlate with body size in rhesus macaques. *JASA*, 102, 1213-1222.
- Fletcher, N. H. (2004). A simple frequency-scaling rule for animal communication. *JASA*, 115, 2334-2338.
- Gerhardt, H. C., & Doherty, J. A. (1988). Acoustic communication in the gray treefrog, Hyla versicolor. *J. Comp. Physiol. A*, 162, 261-278.
- Glasberg, B. R., & Moore, B. C. J. (1990). Derivation of auditory filter shapes from notched-noise data. *Hearing Research*, 47, 103-138.
- ISO 3382-1:2009. Acoustics: measurement of room acoustic parameters, part 1: performance spaces.
- ITU-R BS.2076-2 (2019). Audio Definition Model. ITU-R BS.2088-1 (2019). Long-form file format (BW64).
- Nachbar, C., Zotter, F., Deleflie, E., & Sontacchi, A. (2011). AmbiX: a suggested ambisonics format. Ambisonics Symposium.
- Eyring, C. F. (1930). Reverberation time in "dead" rooms. *JASA*, 1, 217-241.
- Hold, C., Meyer-Kahlen, N., & Pulkki, V. (2023). Magnitude-least-squares binaural ambisonic rendering with phase continuation. DAGA 2023.
- ISO 9613-1:1993. Acoustics: attenuation of sound during propagation outdoors, part 1.
- Kan, A., Jin, C., & van Schaik, A. (2009). A psychophysical evaluation of near-field head-related transfer functions synthesized using a distance variation function. *JASA*, 125, 2233-2242.
- Lindau, A., Kosanke, L., & Weinzierl, S. (2012). Perceptual evaluation of model- and signal-based predictors of the mixing time in binaural room impulse responses. *JAES*, 60, 887-898.
- Schörkhuber, C., Zaunschirm, M., & Höldrich, R. (2018). Binaural rendering of Ambisonic signals via magnitude least squares. DAGA 2018.
- Zotter, F., & Frank, M. (2012). All-round ambisonic panning and decoding. *JAES*, 60, 807-820.
- Huron, D. (2001). Tone and voice: A derivation of the rules of voice-leading from perceptual principles. *Music Perception*, 19(1), 1-64.
- Meyer, L. B. (1956). *Emotion and Meaning in Music*. University of Chicago Press.
- Moore, B. C. J., & Glasberg, B. R. (1983). Suggested formulae for calculating auditory-filter bandwidths and excitation patterns. *JASA*, 74, 750-753.
- Narmour, E. (1990). *The Analysis and Cognition of Basic Melodic Structures*. University of Chicago Press.
- Pearce, M. T., & Wiggins, G. A. (2006). Expectation in melody: The influence of context and learning. *Music Perception*, 23, 377-405.
- Plomp, R., & Levelt, W. J. M. (1965). Tonal consonance and critical bandwidth. *JASA*, 38, 548-560.
- Taylor, A. M., & Reby, D. (2010). The contribution of source-filter theory to mammal vocal communication research. *J. Zoology*, 280, 221-236.
- Wilden, I., Herzel, H., Peters, G., & Tembrock, G. (1998). Subharmonics, biphonation, and deterministic chaos in mammal vocalization. *Bioacoustics*, 9, 171-196.
- Sethares, W. A. (1993). Local consonance and the relationship between timbre and scale. *JASA*, 94, 1218-1228.
- Witek, M. A. G. et al. (2014). Syncopation, body-movement and pleasure in groove music. *PLoS ONE*, 9(4), e94446.
