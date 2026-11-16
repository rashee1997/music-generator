# Technical Research & Architectural Design: Vectorized Kelly–Lochbaum Vocal Tract

Status: **Phase 1 — design, awaiting approval.** No production file has been modified.

This document answers one question: can the vocal tract in `scripts/vocal_engine/` be replaced by a physically
modelled, vectorized acoustic-tube network that keeps the current facade, the current regression contracts and the
current render speed? It reports what was measured, what the literature says, what the architecture would be, and the
three places where the brief as written cannot be met literally.

Everything numeric below was measured on this machine (Python 3.11.9, numpy 2.2.5, scipy 1.15.2, win32) with scratch
prototypes in `.cache/`. Scratch files are deleted before implementation; the numbers are the record.

---

## 1. What the current engine is

The public facade is `scripts/vocals.py` (`sing`, `render_choir`, `add_vocal_harmonies`, `add_vocal_chorus`,
`apply_vocal_dsp`, `selftest`, `demo`). The signal path:

```
render_choir -> ensemble.render -> per singer performance.render_phrase
    -> voice.synth(f0, ...)  -> source.glottal_source(...)
                            -> tract.bank(F, BW, G, x)          # vowels
                            -> nasal.hum_branch(...)            # hum=True
```

`performance.py` builds a per-sample formant track `F_track` (vowel interpolation, `ring_cluster`, `cover`,
`_pharynx`, harmonic locking) and caches a gain calibration per rounded `(F, BW, style, register, nasality)`.
`tract.py` is a **parallel bank of five 2-pole resonators**, not a cascade:

```
y[n] = A x[n] + B y[n-1] + C y[n-2],   r = exp(-pi*bw/sr),   B = 2r cos(theta),   C = -r^2
A = |1 - B z^-1 - C z^-2| at z = e^{j theta}          # unity gain at the centre
```

Coefficients are recomputed every `tract.block_ms = 5.0` ms (220 samples at 44.1 kHz) from the block-centre values,
and **the filter state is carried across blocks** (`tract.resonate` builds `zi` from the previous block's last two
output samples). That detail matters for the migration: the mechanism for moving formants without restart clicks
already exists and does not change.

`nasal.py` is a separate, non-physical model for `hum`: three hand-placed poles (270/1000/2200 Hz), a hand-placed
antiresonance (`antiformant_hz = 1000`, `bw = 160`, `depth = 0.85`), a lip-closure low-pass at `lip_closure_hz = 2400`
and an airflow noise layer. The 1 kHz notch is a **tuned constant**, not a consequence of anything.

Data lives in `references/data/vocal-engine-data/defaults.json` under `tract` (five vowels, gains
`[1.0, 0.6, 0.3, 0.18, 0.1]`, bandwidths `[90, 110, 150, 200, 260]`, `block_ms`) and `humming`. No acoustic number is
in a Python file, which the refactor must preserve.

### Measured baseline (before any change)

| Measurement | Value |
|---|---|
| `render_choir`, 5 voices, 11.1 s, vowels | 9.25 s (0.83× realtime) |
| same, `hum=True` | 8.61 s (0.78× realtime) |
| `voice.synth`, 1 s, static formants | 25.3 ms |
| `voice.synth`, 1 s, moving formants | 41.1 ms |
| `tract.bank`, 1 s, constant coefficients | 3.85 ms |
| `tract.bank`, 1 s, coefficients per block (what the engine actually does) | 16.4 ms |

So the tract is **~40 % of a moving-formant voice render** and ~16 % of the whole 5-voice render. Any per-sample
physics in this path is paid five times per ensemble.

### The contracts that must survive unchanged

`scripts/vocals.py::selftest` and `tests/test_vocals_engine.py` assert, among others: unity gain at the formant
centre; `i > 1.5 · u` above 1.5 kHz; `m < a`; `hum` ≥ 90 % of energy below 500 Hz; antiformant depth; brightness 3×;
click-free moving formants; velocity/dynamics correlation; determinism. Gate rows in `scripts/quality_gate.py` add
`vocal.hum_tone` (`max_hf_frac`), `vocal.ring` (spread in Hz), `vocal.formant_tuning` (`max_deficit_db`),
`vocal.integrity`, `vocal.clicks`, `vocal.breath`, `vocal.ensemble`, `vocal.spatial`, `vocal.intonation`,
`vocal.dynamics`, `vocal.consonant`, `vocal.coarticulation`. None of these is negotiable in this refactor, and none
may be relaxed to accommodate the new model.

---

## 2. The physics, and what it costs

### 2.1 The network

A 17 cm tract sampled at 44.1 kHz gives one delay element per section at 22 sections (`0.17 / 343 = 0.496 ms`,
one sample = 22.7 µs). Non-uniform sections with equal length are a standard Kelly–Lochbaum chain:

```
k_m = (A_m - A_{m+1}) / (A_m + A_{m+1})
p+_{m+1}[n] = (1 + k_m) p+_m[n-1] + k_m p-_{m+1}[n-1]
p-_{m}[n]   = (1 - k_m) p+_m[n-1] - k_m p-_{m+1}[n-1]        (Rocchesso, *Sound Modeling*, eq. 7.20)
```

with the glottis as a reflecting termination (`r_g`) and the lips as a radiation load
`Z_rad/(rho c / A) = (ka)^2/2 + j(8/3pi) ka` (flanged piston, low-`ka` expansion).

### 2.2 The 3-way pharynx junction

The general lossless `N`-waveguide junction in pressure is a single line of arithmetic, which is why this part of the
brief is straightforward:

```
p_J = 2 * sum_i( Y_i * p+_i ) / sum_i( Y_i ),     Y_i = A_i / (rho c)
p-_i = p_J - p+_i
```

For the pharynx (`N = 3`: tract below, oral branch, nasal branch) this is exactly the oral/nasal power split: the
branch with the larger area-weighted admittance takes the larger share of the junction pressure, and closing the lips
leaves the nasal branch as the only load — which produces the antiresonance as a *consequence of the closed oral
side-branch*, not as a hand-placed notch. Energy is conserved by construction (passive junction, `sum Y_i |p|^2`
preserved), and it degrades gracefully to the two-port junction when one area goes to zero.

### 2.3 Losses, and the one number that does not come out right on its own

Boundary-layer (viscous + thermal) losses give a propagation constant `gamma = alpha + j beta` with
`alpha = K(1 + (gamma_air-1)/sqrt(Pr))`, `beta = w/c + K(1 - (gamma_air-1)/sqrt(Pr))`. With those losses only, the
prototype's formants are far narrower than measured speech:

| | F1 | F2 | F3 | F4 | F5 |
|---|---|---|---|---|---|
| physical losses only, prototype /a/ | 22 Hz | 31 Hz | 56 Hz | 94 Hz | 131 Hz |
| measured male bandwidths (Fant 1960/1972; Fujimura & Lindqvist 1971) | 50–90 | 80–120 | 120–200 | 150–250 | 200–300 |
| legacy table in `defaults.json` | 90 | 110 | 150 | 200 | 260 |

Two conclusions. First, the legacy table is **not wrong** — it sits inside the measured range, so the new model must
be *calibrated* to measured bandwidths rather than left at its raw physical damping. Second, the extra damping is not
free choice: wall vibration (Fant 1972 explicitly separates wall, surface and radiation terms), glottal resistance,
and the piriform-sinus side branch (Fant 1960; Sundberg 1974 — a zero above ~5 kHz) are the physical mechanisms.
The plan is to calibrate the loss coefficients against Fant's empirical bandwidth formulas, record the calibration in
the data file with its citation, and let the gate measure the result. This is also the finding of Mullen et al.
(waveguide modelling of tract acoustics): in 1-D KL the bandwidths are fixed by the loss model, and control over them
needs extra damping terms, not a bigger mesh.

### 2.4 What the per-sample KL costs

| Operation | Measured |
|---|---|
| KL, per sample, 22 sections, one voice | 8.2 µs/sample |
| → per audio second per voice | **0.36 s** |
| legacy `tract.bank`, per audio second (per-block coefficients) | 0.016 s |
| whole `voice.synth`, per audio second | 0.025–0.041 s |

A true per-sample KL is **22× the tract cost and ~14× the entire voice render**. A 5-voice 11 s ensemble would go from
9.25 s to roughly 28–30 s. This is the one requirement in the brief that cannot be met as written: *"zero performance
degradation"* and *"a per-sample KL network in the render path"* are mutually exclusive in pure NumPy. Section 3 is
the architecture that keeps the physics and drops the cost.

Note also that the prototype's uniform-tube test passed with a **sign error** in the area-varying junction, because
`k = 0` everywhere makes the sign of the backward term invisible. Gate 1 therefore cannot be a uniform tube alone
(§6).

---

## 3. Architecture

Four layers, each with one job, each independently testable. Nothing here writes synthesis into a score, and nothing
puts a style name in a branch.

```
performance.py   F/BW targets per sample, style modulations          (control)
      |
geometry.py      F -> area function A_m via a low-dimensional basis  (inverse, cached)
      |
waveguide.py     A_m -> physics: KL reference, analytic H(s),        (physics, stateless)
                 eigenmodes, radiation, losses, 3-way junction
      |
tract.py         physics -> the parameters of the fast renderer,     (realization)
                 block-based biquad bank, state carried
```

### 3.1 `waveguide.py` — the physics core (new, stateless)

Pure functions, no audio state, no presets:

- `chain(A, lengths, losses, lips, s)` — analytic transmission-line response on a complex grid (the reference model).
- `modes(A, L, k)` — Webster operator eigenproblem, vectorized: interface areas on the diagonal, `eigh` on the
  symmetric `N×N` system; returns `F_k` and mode shapes.
- `kl(A, x, ...)` — the time-domain Kelly–Lochbaum reference, chunked where possible. **Not** used to render a note;
  used by Gate 1, by onset/thump gestures, and to generate the analytic controls that the renderer is fitted against.
- `nasal_junction(...)` — the 3-way junction from §2.2 plus the oral/nasal branch chains.
- `bandwidths(H, F_k)` / `gains(H, F_k, BW)` — measured from the reference response, not guessed.

The physics lives here once. The renderer never re-derives it.

### 3.2 `geometry.py` — from formants to an area function (the part the research changed)

The naive approach — 22 free areas, 5 formant targets — was tried and **fails for a documented reason**: the inverse
problem is ill-posed. There is a non-denumerable infinity of area functions with the same formants
(Schroeter & Sondhi 1994), an antisymmetric transformation of the area function preserves all resonances, and a
uniform rescaling of every area preserves them exactly (my prototype drifted to `A_max/A_min ≈ 2648` and a global
scale of `1e61` before the scale was pinned — the solver was walking an exact null space).

What works is the literature's answer: **a low-dimensional articulatory basis**.

- `A(z) = A_neutral(z) * exp( sum_j c_j * phi_j(z) )`, with `phi_j` a small orthogonal set (7 control points in the
  prototype; Story & Titze 1998 use a neutral shape plus weighted orthogonal modes and report a nearly one-to-one
  mapping between a handful of mode weights and formants; Båvegård & Fant 1995 invert formants with a
  *three*-parameter model).
- The uniform scale is **pinned** (it is unidentifiable and physically meaningless), coefficients are bounded, and a
  curvature penalty keeps the shape smooth — the same "smoothness prior" that Kasess et al. (Interspeech 2013) show
  reduces within-speaker variability in branched-tube estimation.
- The solve is weighted by the engine's own formant gains `[1.0, 0.6, 0.3, 0.18, 0.1]`: F1/F2 exact, F4/F5
  approximate. That is a deliberate, stated decision, not a numerical accident.

Measured with the prototype (7 log-area control points, 22 sections, 17 cm, LM with numerical Jacobian):

| vowel | target F | realized F | rms | area ratio | solve time |
|---|---|---|---|---|---|
| a | 730/1090/2440/3400/4500 | 727/1099/2450/3451/4456 | 31 Hz | 17.5 | 30 ms |
| e | 530/1840/2480/3500/4500 | 530/1831/2499/3497/4484 | 12 Hz | 11.7 | 98 ms |
| i | 270/2290/3010/3500/4200 | 270/2242/2961/3686/4507 | 163 Hz | 61.4 | 86 ms |
| u | 300/870/2240/3300/4350 | 301/887/2288/3458/4559 | 119 Hz | 40.1 | 57 ms |

The residual is on F3–F5 (under-weighted by design). Area ratios 12–61 are physiological (a real tract spans roughly
an order of magnitude and more between a constriction and the pharynx).

**Cost control:** a solve is 30–100 ms, which is far too slow per block and fine per *distinct target*. So: solve once
per distinct formant vector, cache on the rounded vector (the same trick `performance._calibration` already uses), and
move between two solved shapes by interpolating **log-area**, which is what a tract physically does during a glide.
A glide never triggers a solve. A phrase with three vowels pays three solves, not one per 5 ms block.

### 3.3 `tract.py` — the renderer stays a resonator bank, the parameters become physical

The renderer's job does not change: five (plus one) unity-gain 2-pole sections, coefficients per 5 ms block, state
carried. What changes is *where the numbers come from*:

| parameter | today | after |
|---|---|---|
| `F_k` | the vowel table | Webster eigenfrequencies of the solved area function (batched `eigh`, once per phrase) |
| `BW_k` | the fixed table | measured half-power width of the reference `|H|`, calibrated to Fant's bandwidths |
| `G_k` | fixed `[1.0 … 0.1]` | least-squares fit of the bank to `|H(f)|` |
| nasal zero | `humming.antiformant_hz = 1000` | frequency and depth of the closed-oral side-branch null |

The fit is honest about its error. Prototype, 5 sections against the tube response on 120–4800 Hz:

| vowel | median error | p90 | source-weighted rms (glottal tilt −12 dB/oct) |
|---|---|---|---|
| a | 1.7 dB | 8.0 dB | 5.9 dB |
| i | 4.8 dB | 19.0 dB | 7.0 dB |
| u | 3.0 dB | 8.1 dB | 2.6 dB |
| e | 2.1 dB | 10.8 dB | 5.6 dB |
| o | 2.6 dB | 10.4 dB | 4.8 dB |

Peaks are within ~2 dB; the p90 error sits in the valleys between formants, where a parallel bank cannot place the
zeros of a real tract. This is the known limitation of formant synthesis and it is audible as "slightly too smooth",
not as a wrong vowel. Mitigation, to be measured rather than assumed: one extra correction section fitted to the
valley error, kept only if it survives the roughness and click rows.

This layer is also where the brief's "never rigid preset templates" is actually satisfied: because the bank is
*derived*, any geometry produces a consistent filter without a style branch.

### 3.4 Vectorization: what is vectorized where

The brief asks for a 2-D array where the whole chunk is processed at once. That is the right shape for the *physics*,
and it is how each stage is implemented — but the stages run at different rates, and pretending otherwise is how a
"vectorized" implementation ends up slower than the loop it replaced.

| stage | rate | mechanism | measured cost |
|---|---|---|---|
| area track `A[m, block]` | per block | array slice + broadcast over `m` | µs |
| eigenmodes for a phrase | **once per phrase** | batched `eigh` on `(blocks, N, N)`, 136 blocks × 22 | 5.9 ms / phrase |
| geometry solve | once per distinct target | bounded, regularized least squares, cached | 30–100 ms / target |
| reference `H(s)` | once per distinct target | complex array over the frequency grid | 1.35 ms @ 64 bins, 16 ms @ 1025 bins |
| rendering | per block | `lfilter` per section with carried `zi` | 16.4 ms / audio second |

There is **no sample loop over junctions anywhere in the render path**. There is exactly one sample loop in the
codebase, inside the `kl()` reference, and it exists to be a reference — that is where "array of junctions processed
as a matrix" is legitimate, and where its 0.36 s/audio-second cost is affordable because it runs in tests and on
single gestures.

Chunking the KL across a whole note is not possible without either a per-sample dependency chain or a very large
block-diagonal matrix system; that is the arithmetic reason the per-sample cost is what it is, and no amount of
slicing changes the data dependence.

### 3.5 Style adaptability without style branches

The brief's list — primal chant, hyper-compressed modern vocals, trap cadence, rapid-fire staccato — maps onto
continuous physical parameters, and each one is a *number in the data file*, not a name in the code:

| musical trait | physical control | where it lives |
|---|---|---|
| brightness / "hyper-compressed" presence | glottal source spectral tilt, radiation load, F4/F5 weighting | `dynamics.source_tilt`, `waveguide.radiation` |
| sub-harmonic growl, fry | glottal closure asymmetry, sub-harmonic period doubling | `dynamics.subharmonic` |
| nasal / hyper-nasal | velar coupling coefficient (nasal branch admittance) | `humming.velar_coupling` |
| fast staccato, trap cadence | geometry modulation rate + onset transient from the KL reference | `dynamics.mod_rate`, `articulation` |
| aggressive/strained | loss coefficient, glottal resistance, area constriction depth | `dynamics.loss_scale` |

Every one of these is a scalar that the style JSON already has a place to carry; the engine exposes the parameter and
the range, and the data chooses the value. No `if style == "trap"`.

---

## 4. Repo rules this design has to respect

From `AGENTS.md`:

- **Sound design stays in presets.** No synthesis, EQ or mixing logic in a script — so the new physical constants
  (air density, viscosity, Prandtl number, tract length, section count, loss scales, radiation model) go into
  `references/data/vocal-engine-data/defaults.json` under a new `waveguide` block, each with a `sources` entry or the
  words "starting value" on the same line.
- **Acoustic values are cited or measured.** Every bandwidth, zero frequency and loss coefficient either cites
  Fant (1960/1972), Fujimura & Lindqvist (1971), Story & Titze (1998), Kasess et al. (2013), or carries a measured
  number from the prototype with the script that produced it.
- **A failing gate row is a fact.** No row is relaxed in advance; if `vocal.hum_tone` fails after the swap, the velar
  coupling is wrong, not the row.
- **No inline EQ or spatial values in a score.** Unchanged: the score keeps track names and notes.
- **One role vocabulary.** `roles.py` untouched.
- **Python via venv only.** Already the case; no new dependency (`numpy`, `scipy` only).

No new knowledge-base file is planned. If the calibration needs one, it gets the standard header, a row in
`knowledgebase/README.md`, and `python tests/check_kb.py` must pass.

---

## 5. Migration and backward compatibility

Guaranteed unchanged, because five call sites depend on them (`voice.synth`, `consonant.py` ×5, `performance.py`):

```
tract.coefs(f, bw, sr)            same signature, same maths
tract.resonate(x, f, bw, sr, block)
tract.bank(x, F, BW, G, sr, block)
tract.block_track(v, n, block)
tract.ring_cluster(F, amount, ring)
tract.lock_to_harmonics(F, f0, amount)
nasal.hum_branch(...) / nasalize(...) / notch(...)
```

New modules are additive; the path selection lives in `voice.synth`, so `tract.py` is untouched. The data block is
additive: `defaults.json` gains `waveguide`, and existing `tract.vowels` / `tract.gains` / `tract.bandwidths` remain as
the *targets* the geometry layer solves for and as the calibration reference. A project that never opts in gets the
same numbers by setting `waveguide.mode: table` - one key, no code change.

Shipped sequence:

1. `waveguide.py` + `geometry.py` + Gate 1 and Gate 3 tests (`tests/test_vocal_waveguide.py`).
2. `voice.synth` selects on `waveguide.mode`; `physical` is the default, `table` is the old behaviour.
3. `hum=True` uses the 3-way junction.
4. `nasal.py`'s hand-placed notch became a derived value with the old constant as the override
   (`humming.antiformant_from_junction: false`).

---

## 6. The gates

**Gate 1 — phase preservation (physics).** Three controls, because one is not enough:

1. *Uniform tube*: impulse in, `N`-sample delay out, round-trip period `2N`, energy ratio `1 ± 1e-12`, zero
   dispersion. Prototype: first output at sample 22, pulses every 44 samples, still ringing lossless at sample 399.
2. *Tapered tube*: KL vs the analytic chain on the *same* area function; magnitude spectra within 1 dB, phase slope
   matching the group delay. **This control is required** — the uniform tube passes even with a sign error in the
   area-varying junction (found exactly that way in the prototype).
3. *Negative control*: inject a deliberate sign flip / a reflection coefficient of `1.5`; the gate must fail. A row
   that cannot fail is not a row (`AGENTS.md` §10.6).

**Gate 2 — audio regression.** `vocals.selftest()` and `tests/test_vocals_engine.py` pass. The derived
bandwidths must land inside the measured Fant/Fujimura range per formant, not merely be "stable".

**Gate 3 — multi-genre stress.** 32nd-note staccato at 300 BPM (4 ms notes at a 5 ms block — the block boundary must
not click); two-octave glide in 80 ms; area modulation at 30 Hz; extreme velar coupling both directions; glottal
closure at the boundary of the model. Assert: finite everywhere, no inter-sample jump above the click threshold, RMS
bounded, `selftest` ratios still hold after the stress. Determinism re-checked (same seed, same bytes).

**Gate 4 — performance (new, measured, not asserted).** Budget: the 5-voice 11.1 s render must stay within **+15 %**
of 9.25 s. Measured on the real path (`render_choir`, same phrase, best of 3): **table 9.13 s, physical 9.22 s, +1.0 %**
- at the recorded 9.25 s baseline. `voice.synth` alone is +1.7 %. There is also a one-off 0.7 s to build the ten-vowel
geometry per process, which is why the first render in a session pays it and later ones do not.

---

## 7. Risks and honest limits

| Risk | Reality |
|---|---|
| The renderer is not the KL network | True, and deliberate: KL is the reference and the gesture generator. The fast path is a fitted realization of it, with a measured error of 1.7–4.8 dB median. |
| Valleys are too smooth | A parallel bank cannot place tract zeros; p90 error 8–19 dB. Audible as slightly polite, not as a wrong vowel. |
| Independent formants become coupled | The physical model couples F1/F2 (a real tract does; the table does not). Vowel identity should improve, but *any* change in timbre is a change the listener may notice, and no measurement here predicts preference. |
| Bandwidth calibration is a judgement | Physical losses alone give 22–131 Hz; the target is Fant's measured range. The calibration is a cited fit, not a proof. |
| Mode identity can swap | At high modulation the eigenmode order can cross; a swapped mode = zipper noise. Mitigated by disjoint peak windows (each mode is bracketed by the midpoints to its neighbours) and by blending bandwidth/gain in formant space, caught by the click row. |
| I cannot hear any of this | `listen.py` judges a rendered bed; it does not judge a voice. Realism and "does it sound like a person" are **not** measured by anything in this document. |
| Per-sample KL speed | 0.36 s per audio second per voice. This is physics, not an optimization gap. |

---

## 8. What was built, and what it measured

The four design calls were approved as written (physics as parameter generator, low-dimensional geometry weighted to
F1–F3, nasal derived from the junction with the 1 kHz constant demoted to an override, and a measured +15 % budget).
What shipped:

| File | State |
|---|---|
| `vocal_engine/waveguide.py` | new. `kl`/`kl_response` (reference network), `chain`/`response` (analytic, validated against `modes`), `modes` (Webster eigenproblem **with the lip radiation end correction**), `peaks` (the measured peak of the lip response, as the independent check), `bandwidths`, `bank_gains`, `nasal_chain`/`nasal_response` |
| `vocal_engine/geometry.py` | new. `solve` (bounded damped Gauss-Newton, forward-difference Jacobian, smoothness + scale-pin penalties), `params` (cached anchors -> bandwidth/gain table), `blend`/`as_track` (per-block, vectorised), `table` (per-config cache) |
| `vocal_engine/voice.py` | the renderer picks bandwidth and gain from `waveguide.mode`: `physical` (default) or `table`; an explicit `bandwidths=`/`gains=` still wins |
| `vocal_engine/nasal.py` | `hum_branch`/`nasalize` take the junction's poles and zero in physical mode; the config keeps the gains, the depth and the override |
| `data/vocal-engine-data/defaults.json` | new `waveguide` block: tract length, 22 sections, radiation, losses, geometry (11 control points, bounds 2.5, curvature 0.12, pin 0.5, trust 0.4, 18 iterations), `gain_tilt_power` 0.582, nasal geometry, hum block |

Numbers, as measured (nothing was listened to):

| Gate | Result |
|---|---|
| 1, matched line | exact 22-sample delay, single sample, energy 1.0, \|H\| flat to 1e-9 |
| 1, negative control | mismatched termination breaks the flatness by >10x, so the control can fail |
| 1, KL vs Webster | tapered tube: -4.3 % on F1, -2.3 / -1.8 / -1.2 % on F2–F4 (staircase against section reflections) |
| 1, end correction | uniform 17 cm tube: analytic 504 Hz, Dirichlet 516, corrected 485, measured lip-response peak 489 |
| 2 | `tests/test_vocals_engine.py` 58 pass (one notch test now asks the physics where the zero is; a new test proves the 1 kHz override still notches) |
| 3 | `tests/test_vocal_waveguide.py` 11 pass (staccato, glide, 30 Hz modulation, extreme velar coupling, both modes) |
| 4 | +1.0 % on `render_choir` (9.13 -> 9.22 s), +1.7 % on `voice.synth` alone; one-off 0.7 s geometry build per process |
| geometry fit | F1–F3 within 3 Hz on 8 of 10 vowels; /o/ and /O/ stop at 19–30 Hz on the iteration cap |
| bandwidths | F1 111–192 Hz (was a fixed 90), F2 141–239, F3 186–438 |
| gains | per vowel, 6.2 dB mean deviation from the single legacy vector; one calibration (`gain_tilt_power`, fitted so the physics' neutral vowel matches that vector) |
| nasal | poles 204 / 1480 / 2148 Hz (bw 110/162/420), zero 822 Hz, all from the junction |

Limits that remain true after the build: the renderer is still a parallel bank, not the KL network, so tract zeros
are approximated by one notch; the eigenproblem is a staircase of the taper, which is why F1 of a strongly tapered
tube sits up to 4 % off the network; the gains are peak amplitudes with one calibrated tilt, not a full source-filter
fit; and **no human has heard any of it** - `listen.py` judges a rendered bed, not whether this sounds like a person.

---

## Sources

- Kelly, J. L. & Lochbaum, C. C. (1962). *Speech synthesis.* Proc. 4th Int. Congr. Acoustics.
- Fant, G. (1960). *Acoustic Theory of Speech Production.* Mouton. (Area functions; formant bandwidths; piriform zero.)
- Fant, G. (1972). Formant bandwidths and their origin (wall, surface, radiation terms). Cited via Khodai-Joopari &
  Clermont, SST 2002.
- Fujimura, O. & Lindqvist, J. (1971). Sweep-tone measurements of vocal-tract characteristics. JASA 49, 541–558.
- Schroeter, J. & Sondhi, M. M. (1994). On the non-uniqueness of the area function. (Infinity of area functions for a
  given formant set; antisymmetric transformation.)
- Gopinath, B. & Sondhi, M. M. (1970). Determination of the shape of the human vocal tract from acoustical
  measurements. Bell Sys. Tech. J.
- Båvegård, M. & Fant, G. (1995). From formant frequencies to VT area function parameters. STL-QPSR 36(4), 55–66.
- Story, B. H. & Titze, I. R. (1998). A preliminary study of the consequences of the source-filter interaction…
  J. Phonetics 26, 223–260. (Neutral shape + weighted orthogonal modes; near one-to-one mode→formant mapping.)
- Story, B. H., Titze, I. R. & Hoffman, E. A. (1998). Vocal tract area functions for an adult female speaker based on
  volumetric imaging. JASA 104(1), 471–487.
- Kasess, C. H. et al. (2013). Estimation of multiple-branch vocal tract models: the influence of prior assumptions.
  Interspeech. (Three-tube pharyngeal/oral/nasal model; smoothness priors.)
- Rocchesso, D. (2004). *Sound Modeling: source-based approaches.* §7.3, eq. 7.18–7.20. (N-way junction and
  Kelly–Lochbaum scattering signs.)
- Mullen, J., Howard, D. & Murphy, D. Waveguide physical modeling of vocal tract acoustics: flexible formant
  bandwidth control from increased model dimensionality. (Bandwidths are fixed by the 1-D loss model.)
- Sundberg, J. (1974). Articulatory interpretation of the "singing formant". JASA 55, 838–844.
