# Research & plan: Immersive 3.2, virtual ears, expression QA

Status: DESIGN ONLY. No pipeline code was changed. Date: 2026-11-23. Goal: everything on CPU (4 cores, no GPU); GPU optional.

Evidence labels used below: **[repo]** read in this repo; **[measured]** timed in this session; **[lit]** from literature or
package pages I could only skim via search (verify before citing in a KB file); **[start]** a starting value with no
source yet (AGENTS rule 16 requires this label on the same line as the number).

## 0. Findings that change the brief

1. **"Immersive 3.2" is not an open standard.** ITU-R BS.2051 has no 3-front + 2-LFE layout; the only two-LFE system is the
   22.2 family (LFE1/LFE2) [lit]. IAMF's layouts (mono, stereo, 5.1, 7.1 families, 3.1.2) have none either [lit]. So 3.2 is a
   **project-defined layout preset** (`layouts/` accepts project files [repo: `spatial_engine/config.py` docstring]) and it
   ships as discrete WAV and as ADM/BW64 DirectSpeakers, not as a named broadcast format. The report says so in the delivery
   note; it must not claim standard compliance.
2. **Dual LFE cannot be certified by a file-only pipeline for room-mode cancellation.** Whether two subs flatten a room needs
   the room and sub positions. What the pipeline *can* do: deliver a safe pair (polarity, phase alignment, mono-compatibility,
   fold-down) and give an advisory simulation using a virtual box room.
3. **The engine is single-LFE by construction** (see §1). Dual LFE is a code change, not only a preset.
4. **IDyOM-style information content already half exists** (`pattern_audit.melodic_information_entropy`: first-order Markov
   on pitch intervals, add-0.2 smoothing, in-piece only). The upgrade is a proper PPM model with several viewpoints, not a
   new concept.
5. **A CPU-only ear model is feasible.** A CAR-style cascade + hair-cell + adaptation surrogate ran 60 s of mono audio at
   22.05 kHz in ~0.9 s (32 ch) / ~1.1 s (64 ch) for the cascade, plus 3.1 / 5.5 s for hair-cell + adaptation [measured, §3.4].
   Zilany/Verhulst-class models are not CPU-practical for whole pieces; use them only as calibration references.

## 1. Codebase gap analysis [repo]

| Area | What exists | Gap for 3.2 / ears / expression |
|---|---|---|
| Layout data | `references/data/presets/layouts/*.json` (ITU B, C, D, H, I, J, `ambix_qa_36`, `stereo_bs775`); schema: `speakers[]`, one `lfe` block, `downmix`, `reverb`, `decorrelation`, `gate` | No 3-front layout. `lfe` is a single dict. |
| Layout code | `spatial_engine/config.py`: `lfe_speaker()` returns the **first** `lfe` speaker; `lfe_cfg()`; `problems()` requires an LFE and a downmix entry for every speaker (incl. LFE) | Needs `lfe_speakers()` (plural), per-LFE config, validation of ≥1 LFE |
| Panning | `spatial_engine/pan.py`: horizontal ring uses `_pair_gains` (equal-power between neighbours); 3-D uses VBAP triplets | A 3-speaker front arc works with `_pair_gains` as is. Rear/side energy has no speaker: the HOA decoder (`hoa.allrad2_matrix`) must fold it into the arc (decode_uniformity row will flag a front-only layout; it must be a declared exception, not a loosened row) |
| Bass | `spatial_engine/bass.py`: LR4 low-pass, `lfe_bus(sends, sr, cfg)` sums all low sends into ONE bus, `guard`, `release_fade`, `stopband_leak_db` | Needs `lfe_bus_pair`: split by per-track `lfe_pan` (-1..1) or by a stereo bass source, optional per-channel delay, polarity, band-split decorrelation above `decorr_hz` |
| Bus | `render.LayoutBus.result()`: `mix[self.lfe_speaker['name']] += low`; `skip=[lfe name]` for decorrelation | Single name hard-wired; loop over LFEs |
| Master | `spatial_engine/master.py`: `_dc_block` skips `name == 'LFE'` (string match); `fold_lufs` via BS.775 fold; `programme_lufs` method `bs1770_layout` | Match on the speaker's `lfe: true` flag, not a name. `loudness.layout_lufs` must exclude both LFEs (check `scripts/loudness.py`) |
| Fold | `downmix.fold()` iterates names, skips missing coefficient; LFE has none | Add 3.2 -> 3.1 stage (LFE1+LFE2 -> LFE) and a 3.1 layout preset so fold chain is data |
| Targets | `outputs/*.json` (`renderer: spatial`, `layout`, `lfe`, `loudness`, `limiter`, `gate`); `render_targets` validates `REQUIRED` keys | New `immersive_3_2.json`. `lfe` becomes list-or-dict (back-compat) |
| ADM | `spatial_engine/adm.py` (864 lines, BW64), `atmos_music.json` | DirectSpeakers pack for 3.2 with two LFE labels (BS.2051 names `LFE1`,`LFE2` [lit]) |
| Gate | `gate_profiles.ROWS` (id -> meaning, params `(default,min,max)`, `protected`, `no_skip`), `spatial_gate.fold_rows`, `channel_rows`, `channel_qa.py` per-bar conflicts, `imm.low_fold`, `imm.foldown`, `fold.mono`, `fold.timbre` | New rows (§4) registered in `ROWS`; `channel_qa` already handles N channels |
| Peripheral model | `naturalness_check.cochlear_roughness_check` (1 s Hann STFT, 10 loudest partials, Plomp-Levelt/Sethares, `level_aware`: Vassilakis + simultaneous-masking spread, ATH), `roughness_forecast.py`, `quality_gate.masking`/ERB-band `masking.excess`, `spatial_gate._erb_bands` | Static, frame-based; no compression, no adaptation, no temporal masking, no neural fatigue, no pitch salience |
| Ears (ML) | `listen.py` + `requirements-ears.txt` (earshot, transformers, torch **CPU wheel**, librosa) | Optional layer. Keep the new ear model OUT of this file: numpy/scipy only, so it runs in the main `.venv` |
| Expectation | `pattern_audit.melodic_information_entropy`, `spiral_tension_arc` (Chew helical array, 2*beats-per-bar windows), `witek_groove_curve`, `soul_check._tonic_pc` | No viewpoints, no LTM, no per-note IC/H time series exported, no entropy-weighted combination |
| Humanizer | `humanize.py`: `TempoMap` (phrase-arch rubato, wander, elastic breaths, ritard q=3), KTH rules (`melodic_charge_*`, `harmonic_charge_*`, `vel_dur=0.018`), `MOODS`, `humanize_report` | Tension couples to timing only via KTH charge (circle-of-fifths). No IC/H input. |
| Intent / direction | `intent.py`, `references/data/presets/intent/`, direction sheet `energy`, `feel`, `expression.cues` | No valence/arousal coordinates per word; no measured trajectory to compare to |
| Tests | `tests/test_immersive_31.py` pattern (parametrised over `LAYOUTS`), `test_hrtf`, `test_roughness_model`, fixtures in `tests/fixtures/roughness/` | Reuse pattern and the synthetic-fixture approach |
| Environment | No `.venv` in this container; system Python 3.13, numpy present, scipy/torch absent; repo pins numpy 2.5.3 / scipy 1.18.1 | Benchmarks here used scipy 1.18.1 in a scratch venv |

## 2. Immersive 3.2 specification (proposal)

### 2.1 Channel layout
Name: `lrc_lfe2` (layout) / `immersive_3_2` (target). File order: `L, R, C, LFE1, LFE2` (SMPTE-style 5.1 order with C third,
as in `immersive_5_1.json`'s `FL, FR, FC, LFE, ...`).

| Ch | Name | Azimuth (clockwise from front, repo convention) | Elev. | Role |
|---|---|---|---|---|
| 1 | L | -30 | 0 | main |
| 2 | R | +30 | 0 | main |
| 3 | C | 0 | 0 | main |
| 4 | LFE1 | 0 | 0 | `lfe: true`, `lfe_side: "left"` |
| 5 | LFE2 | 0 | 0 | `lfe: true`, `lfe_side: "right"` |

L/R at +-30 and C at 0 is BS.775 / BS.2051 front geometry [lit]. LFE azimuth is nominal; real sub placement is the room's.

### 2.2 Preset JSON additions (all numbers are data)
```jsonc
// layouts/lrc_lfe2.json  (additions marked)
{ "channels": 5, "speakers": [ ...L,R,C, {"name":"LFE1","lfe":true,"lfe_side":"left",...}, {"name":"LFE2","lfe":true,"lfe_side":"right",...} ],
  "lfe": {                                   // dict stays valid for 1 LFE; 3.2 adds:
    "channels": ["LFE1","LFE2"],
    "lowpass_hz": 80.0, "stopband_hz": 120.0, "guard_order": 4,   // same shape as itu_bs2051_system_b [repo]
    "mode": "stereo_bass",                   // "stereo_bass" | "dual_mono" | "modal_split"
    "decorrelate_above_hz": 40.0,            // [start] mono (identical, in phase) below, partially decorrelated above
    "decorrelation": {"kind": "allpass_cascade", "stages": 4, "max_group_delay_ms": 8.0},   // [start]
    "delay_ms": [0.0, 0.0],                  // per-LFE alignment; nonzero only from a measured room
    "polarity": [1, 1],
    "send_db": -10.0 },
  "downmix": { "L":[1,0], "R":[0,1], "C":[0.7071,0.7071] },       // BS.775: C -3 dB into both [lit]
  "fold_chain": ["lrc_lfe1", "stereo_bs775"],                     // new: data-driven 3.2 -> 3.1 -> 2.0
  "gate": {"stereo_correlation_min":0.15, "fold_band_max_db":6.0, "fold_floor_db":30.0} }  // copied from 5.1 target [repo]
```
Companion `layouts/lrc_lfe1.json` (L,R,C,LFE) is the 3.1 stage. Strictly the `lrc_lfe1` / fold chain is two presets, no code
constants.

### 2.3 Dual-LFE routing math
Let `s_k` be the LR4-low-passed (fc = `lowpass_hz`) send of track k, `g` = send gain, `p_k` in [-1,1] a track's `lfe_pan`
(default 0), `a_k = (1-p_k)/2`.

- **stereo_bass** (default): `LFE1 = g * sum_k sqrt(1-a_k') * s_k`, `LFE2 = g * sum_k sqrt(a_k') * s_k` with `a_k' = a_k`
  rescaled so `LFE1^2+LFE2^2` keeps power. Below `decorrelate_above_hz` both are identical (in phase, summed bass is
  coherent: +6 dB acoustic sum, no cancellation). Above it, LFE2 passes an all-pass cascade (flat magnitude, bounded
  group delay) so room-mode excitation differs between subs. All-pass phase scrambling of a sub only smears it, which is
  why the current code never decorrelates the LFE [repo `render.py` comment]; here it is limited to the 40-80 Hz band and
  capped, and it is gated by `lfe.sum_coherence`.
- **dual_mono**: same signal, no decorrelation (safe fallback; identical to 5.1 behaviour on two outputs).
- **modal_split**: LFE1/LFE2 get the signal through opposing-polarity-free delays chosen from a *measured* room only
  (`delay_ms`). Never defaulted. Listed for completeness.
- **Crossover**: LR4 (24 dB/oct, in phase at fc, -6 dB each) [repo `bass.py`, Linkwitz 1976]. Mains are high-passed with the
  complementary LR4 only for roles in `lfe.roles`; keep 80 Hz as the shipped value from 5.1 [repo]. A **slope/alignment
  check** is automatic: LR4 low+high must sum flat, tested in `tests/` (sum of LP and HP within 0.1 dB, 20 Hz..20 kHz).
- **Phase alignment of sub vs mains** is a room measurement (delay and polarity of the sub against L/R at the crossover).
  The file cannot know it, so `delay_ms` and `polarity` are inputs and the report lists them as "not verified for the room".

### 2.4 Fold-down and phantom stability
- 3.2 -> 3.1: `LFE = (LFE1 + LFE2) * k`, `k = 1/sqrt(2)` if the two are uncorrelated, `0.5` if identical (coherent; keeps
  level). Choose k from measured coherence over `lowpass_hz` and write it into the report [start].
- 3.1 -> 2.0: BS.775 `L' = L + 0.7071 C`, `R' = R + 0.7071 C`; LFEs dropped (as in `downmix.py` docstring) [repo, lit].
- Because the 3-channel front *is* the target, phantom-centre stability is the metric that matters: C carries dialogue/lead
  (`focus`), and the fold must not move it. Measured with the existing binaural HRTF path (`spatial_hrtf.binaural`): render
  C alone and L+R(-3 dB) alone through the same head set, compare ITD (below 1.5 kHz, cross-correlation lag) and ILD (above).
  A true centre has ITD 0 / ILD 0; a phantom centre from L+R at +-30 deg shows comb colouration (the repo's `imm.coloration`
  idea) - that difference is the fold's cost.

### 2.5 Virtual speaker QA metrics (extends `virtual-speaker-qa.md`)
All on CPU, all numpy/scipy, all reuse `hoa.allrad2_matrix` and the HRTF set already shipped:

| Metric | Formula | Note |
|---|---|---|
| `lfe.sum_coherence` | `rho = <LFE1,LFE2> / sqrt(<LFE1^2><LFE2^2>)` over 20..`lowpass_hz`, per 1/3 octave | want rho ~ +1 below `decorrelate_above_hz` |
| `lfe.fold_loss_db` | `10log10(P(LFE1+LFE2)/ (P(LFE1)+P(LFE2)))` per band | 0 dB uncorrelated: +3 dB; -inf if opposite polarity |
| `lfe.polarity` | sign of broadband cross-correlation peak at lag 0 +-1 ms | negative = a flipped sub |
| `lfe.stopband` | existing `bass.stopband_leak_db` per channel | already in repo |
| `lfe.modal_spread_db` (advisory) | std (dB) of summed response at N listener grid points in a virtual box room, 2 subs vs 1 sub; modes from `f = (c/2) sqrt((nx/Lx)^2+(ny/Ly)^2+(nz/Lz)^2)` [lit, Kuttruff]; room from the project's `space` preset geometry | needs no measurement but is only a model of a box; label "virtual room" |
| `front.phantom_itd_us`, `front.phantom_ild_db` | see 2.4 | needs HRTF set |
| `front.decode_uniformity` | existing `imm.decode_uniformity` (power spread over the sphere) | will be large for a front-only layout; declare `gate.decode_uniformity.max_spread_db` per layout with measured value, do not loosen globally |

Honest limit: the room measures above are a model. Delay/polarity of real subs stay user inputs.

## 3. Virtual ears and expression DSP

### 3.1 Candidate models

| Model | Licence | Python | CPU cost | Verdict |
|---|---|---|---|---|
| **CARFAC v2** (Lyon et al.) | Apache-2.0 [lit: verify LICENSE file; Apache-2.0 is AGPL-3 compatible] | NumPy + JAX port exists (arXiv 2404.17490, repo `python/np`) [lit, path unverified] | cascade of 2nd-order sections + AGC; ~64-96 ch real-time-capable in C++; NumPy port speed unmeasured | **Primary.** Vendor the NumPy port (like `scripts/spatial_hrtf` vendors spaudiopy, with LICENSE + NOTICE) or write a clean-room CAR cascade from the paper. JAX = optional GPU path |
| Zilany-Bruce-Carney 2014 | wrappers: `PyZBC2014` AGPL-3.0, `cochlea` GPL-3 [lit]; model is C/Cython | wrapper, needs compiler | per fibre, 100 kHz internal rate; slow for full pieces (not benchmarked) | **Calibration reference only**, 2-3 s probes, optional extra |
| Verhulst 2018 transmission line | licence not confirmed (search found nothing) | C/Python | ~1000 sections at high rate, slower than real time [lit, unverified] | Out of scope on CPU |
| Gammatone + Meddis IHC (Brian2Hears etc.) | varies | yes | cheap | Fallback if CARFAC port is not usable; I would write it from the papers instead of adding a dependency |
| Moore-Glasberg-Schlittenlacher loudness / Dau modulation | papers | none vetted | cheap | Reference for thresholds, implement from equations |

### 3.2 Pipeline `scripts/ear_model/` (numpy/scipy, no new requirement)
1. **Resample** to 22.05 kHz mono (or per ear for binaural; per-stem for masking). Calibrate: file LUFS placed at
   `calib_spl_db` exactly as `cochlear_roughness_check` does (reuse the number, no new constant).
2. **Middle ear**: 2nd-order band-pass, ~0.5-5 kHz emphasis [start: coefficients from a cited ear-canal/middle-ear curve; ISO 226 / ATH function already in the repo as `quality_gate._ath_db`, reuse it as the inverse].
3. **Cochlea (CAR)**: `N` stages from ~9 kHz down to 50 Hz at ERB spacing (`ERB-rate = 21.4 log10(0.00437 f + 1)` [repo `spatial_gate._erb_bands`, Glasberg-Moore 1990]). Each stage: pole-zero pair; the **AGC** feedback (fast-acting compression) changes pole damping with level, which is the active outer-hair-cell non-linearity. This is the only sequential, non-vectorisable part.
4. **Inner hair cell**: half-wave rectify + saturating non-linearity + 1st-order low-pass (~1-3 kHz, phase locking roll-off) [lit: Lyon]. CARFAC's own IHC (v2) also provides this.
5. **Auditory-nerve adaptation**: divisive adaptation with two time constants (fast ~10 ms, slow ~60 ms; surrogate in §3.4 used these [start]); an alternative is the three-store Westerman-Smith / Meddis synapse. Output: neural activity pattern **NAP(ch, t)** at ~2.2 kHz, plus `adapt(ch,t)` = fraction of the adaptation reservoir depleted.
6. **Summaries** (all derived from NAP):
   - **excitation / masking**: NAP energy per channel replaces the static ERB spread in `masking.excess` (compression and two-tone suppression come free from the AGC).
   - **fatigue**: `F(ch) = mean over a 2-5 s window of adapt(ch,t)`; sustained `F > F_hi` for `T` seconds in >= `m` channels, while the programme is *loudness-stable* (LUFS-S range < 2 LU), flags "dense saturated pad that LUFS cannot see".
   - **modulation roughness**: band-pass the NAP envelope 30-150 Hz per channel (peak ~70 Hz) [lit: Fastl-Zwicker, Daniel-Weber]; roughness proxy = summed modulation power x depth over channels. It is independent of the existing partial-pair model, so agreement/disagreement is informative.
   - **pitch salience / resolvability**: summary autocorrelation (SACF) of NAP (Meddis-Hewitt); salience = peak height at the dominant lag; **resolvability** = share of harmonic energy with harmonic number below ~8-10 [lit: Plack; Bernstein-Oxenham] in channels where the partial passes the AGC. Low salience under a dense bed = the figure is not heard as a pitch.
7. **Binaural option**: render the 3.2 file through the HRTF path (`spatial_hrtf.binaural`) to two ears, run steps 1-5 per ear, compute **IACC** from the two NAPs (not from the waveform) per ERB channel; LFE channels are low-passed and sent equally to both ears (nominal, no HRTF: below ~80 Hz interaural cues are negligible [lit]).

### 3.3 Expression pipeline `scripts/expectation.py`
- **Events**: per track note list (already in the score). Viewpoints: *cpint* (pitch interval), *cpintfref* (scale degree via `soul_check._tonic_pc`), *ioi ratio*, optional *chord root* from `theory.py`.
- **Model**: PPM-C with escape and blending, order bound 3-4 (Pearce & Wiggins 2004 / Pearce 2005 [lit]), STM = the piece only; LTM = optional pre-trained on a bundled public-domain corpus. **Licence check needed before bundling any corpus** (Essen / music21 corpus files carry their own terms [lit]); STM-only is the default and needs no data.
- **Outputs per note**: information content `IC = -log2 P(e|ctx)` and entropy `H = -sum_e P(e|ctx) log2 P(e|ctx)`; arrays `ic[n]`, `h[n]`, a per-bar roll-up, and a combination across viewpoints weighted by 1/H^b (as IDyOM does) [lit].
- **Tension coupling**: keep Chew's helical tension (`spiral_tension_arc`); add the cross-correlation of tension(bar) and mean IC(bar) as an INFO number. Do not merge them into one score.
- **Humanize coupling** (new keys, all in `humanize.TIMING`/preset, default 0 so nothing changes silently):
  `ic_agogic_ms` (lengthen the onset-to-next-onset of a note by `a * z(IC)` ms, capped), `ic_vel` (velocity bump), `h_breath_ms`
  (a short pause before a high-entropy position, using the existing `elastic.breaths`). Evidence that performers vary timing and dynamics with
  melodic uncertainty/surprise exists (Gingras et al. 2016 [lit, verify citation]); effect sizes are small, so the caps are
  small and the gate row is advisory.
- **Valence/arousal**: (a) *target*: a data file `intent/valence_arousal.json` giving each resolved intent word a
  (valence, arousal) pair on Russell's circumplex, each value labelled "starting value" with the source scale used [lit]. (b)
  *measured*: arousal from loudness, onset density, spectral centroid, tempo, modulation power; valence from mode/chroma
  major-minor correlation (already in `naturalness_check.chroma_analysis`), roughness, brightness. Fit per-axis weights by
  **ridge regression on a user-supplied annotated set** (DEAM and similar; licences need checking before the repo touches
  them, so fitting is a script run on the user's machine, weights land in a preset with provenance). Published audio-only valence
  prediction is much weaker than arousal [lit], so valence is WARN-only. (c) optional: earshot/CLAP (already in `requirements-ears.txt`) as a second opinion, CPU.

### 3.4 Complexity and measured runtime
Benchmark [measured, this container: 4 cores, scipy 1.18.1, numpy 2.5.5]. Surrogate = CAR-style cascade (no AGC feedback) +
half-wave/saturation/LP + two divisive adaptation stages, **not CARFAC itself**, 60 s mono, 22.05 kHz, float64, one pass:

| Channels | Cascade | IHC + adaptation | Peak array |
|---|---|---|---|
| 32 | 0.37 s | 3.11 s | 339 MB (whole file; chunk it) |
| 64 | 0.56 s | 5.50 s | 677 MB |

Reading: ~6 s per mono channel-minute for 64 ch, so a 4-minute stereo piece is ~50 s of ear model; a 5-channel 3.2 file analysed
per channel ~2 min; HRTF binaural (2 ears) ~50 s. The AGC feedback loop will cost more than the surrogate (sample-by-sample
state), probably the dominant term; I expect it to need numba-free vectorisation across channels per sample block or
a chunked C-ordered loop. **Unmeasured**: the real AGC cost. Milestone M3 must benchmark it before committing to row defaults.
Mitigations: decimate NAP to ~2.2 kHz right after IHC; process in 10 s chunks with state carry; analyse a 30 s excerpt around
each section boundary in draft mode; per-stem ear analysis only for the figure and the top-2 beds. Memory stays < 200 MB chunked.
GPU: the JAX CARFAC path could be enabled with `compute.py`'s device selection [repo, not inspected in depth]; not needed.
IDyOM-lite: O(notes x orders x viewpoints), milliseconds for a piece.

## 4. New gate rows (`ci_report.json`) - all registered in `gate_profiles.ROWS` with `(default, min, max)`

Rollout rule (matches `masking.excess` precedent [repo]): every ear/expression row ships **advisory (WARN/INFO)**; it becomes
FAIL only after calibration on fixtures shows it separates faulty from clean material. Thresholds below are **[start]**.
Protected/hard rows are untouched. A failing new row is fixed in the notes/presets, never by loosening (AGENTS §1).

| Row | Metric / formula | PASS / WARN / FAIL [start] | Remediation hint for the Step-7 loop |
|---|---|---|---|
| `lfe.sum_coherence` | rho of LFE1,LFE2 over 20-80 Hz | rho >= 0.9 / 0.5-0.9 / < 0.5 | set `lfe.mode: stereo_bass`, lower `decorrelate_above_hz` range, check `lfe_pan` of bass tracks |
| `lfe.polarity` | zero-lag xcorr sign | + / - / - and \|rho\|>0.5 FAIL | `lfe.polarity` entry, or fix an inverted bass preset |
| `lfe.fold_loss` | per-band loss of LFE1+LFE2 vs powers | <= 1.5 dB / <= 3 dB / > 3 dB | reduce decorrelation depth; narrow stereo bass |
| `lfe.modal_spread` (advisory) | std over listener grid, 2 subs vs 1 | improvement >= 1 dB / 0-1 dB / worse | change virtual room only if the project room is known; else report |
| `front.fold_phantom` | ITD error of fold vs true C (us), ILD error (dB) | ITD <= 100 / 100-200 / > 200 us; ILD <= 2 / 2-4 / > 4 dB | move content off L/R toward C or lower L/R inter-channel correlation |
| `ear.fatigue` | `F` per §3.2.6 | F < 0.6 / 0.6-0.8 for < 5 s / sustained > 5 s in >= 3 ch while LUFS-S range < 2 LU | thin the pad (fewer voices), add rests or motion, lower pad `gain_db`, high-pass the bed |
| `ear.masking` | NAP-domain excitation of figure minus beds per ERB channel | figure >= beds + 3 dB in >= 70 % of frames / 50-70 % / < 50 % | the existing masking remediation: lane EQ, `lead_carve`, bed level |
| `ear.mod_roughness` | NAP 30-150 Hz modulation power x depth | calibrated against `tests/fixtures/roughness/` (63 tones, 12 pairs [repo]) | same as `cochlear_roughness`: `roughness_forecast.py diagnose`, move the clashing partial |
| `ear.roughness_agree` | Spearman rho of per-frame `ear.mod_roughness` vs `cochlear_roughness` | rho >= 0.5 / 0.2-0.5 / < 0.2 (INFO only) | disagreement means one model is blind: report, do not act |
| `ear.pitch_salience` | SACF peak height of the figure frames / resolvable share | >= 0.4 / 0.25-0.4 / < 0.25 | figure is buried or unresolved: raise register, remove co-registered bed, change timbre |
| `ear.iacc` (binaural) | IACC from the two NAPs, per ERB channel, mean 500-2000 Hz | calibrate against `imm.iacc_early` [repo] | as `imm.envelopment` |
| `expr.ic_profile` | mean IC, mean H, per-bar arrays | INFO: H in 1.2-3.8 bits (existing corridor, `docs/PSYCHOACOUSTICS.md`) | the existing `melodic_information_entropy` remediation; supersedes its first-order estimate |
| `expr.surprise_grounded` | share of IC > 4.2 bits not followed by IC <= 2.2 within 2 notes | keep the existing numbers [repo] | resolve high-surprise leaps stepwise |
| `expr.agogic_coupling` | Spearman rho between per-note IC and rendered inter-onset lengthening, and with velocity | rho >= 0.15 / 0.05-0.15 / < 0.05 when `ic_agogic_ms > 0` | raise `ic_agogic_ms` cap or check humanize preset is not `tight` |
| `expr.tension_ic` | corr(Chew tension per bar, mean IC per bar) | INFO | none |
| `emotion.arc_arousal` | Spearman rho of measured arousal per section vs the sheet's `energy` order | >= 0.6 / 0.3-0.6 / < 0.3 | change density/velocity/tempo of the named section (not the target) |
| `emotion.arc_valence` | same for valence vs the intent word's coordinate | WARN-only | mode/register/consonance of the section |

`ear.fatigue`, `ear.masking`, `ear.pitch_salience` need to be listed in the profile tables (§6 of AGENTS.md): `ambient`/`drone`
profiles must either set the fatigue limit with a measurement or declare `skip` with a reason, because a held pad is their
subject. That is the "relax only with measured evidence" path.

## 5. Phased roadmap (each item one PR; each lists its tests under `tests/`)

| # | Milestone | Scope | Tests |
|---|---|---|---|
| M0 | KB + docs | `knowledgebase/sound-design/virtual-ears.md`, `.../layout-3-2.md`, `.../expectation-idyom.md` with header and README rows; `python tests/check_kb.py` passes; literature claims above verified and sourced | `check_kb.py` |
| M1 | Multi-LFE data model | `config.lfe_speakers()`, `lfe` list-or-dict, `problems()` updates, `master._dc_block` by `lfe` flag, `loudness.layout_lufs` excludes all LFEs; layouts `lrc_lfe1`, `lrc_lfe2`; back-compat for all 6 existing layouts | `test_multi_lfe.py`: every existing layout unchanged byte for byte; 3.2 validates; LFE-name independence |
| M2 | Dual-LFE routing | `bass.lfe_bus_pair`, `lfe_pan`, polarity, delay, band-limited all-pass decorrelation; `LayoutBus.result()` loops LFEs | `test_dual_lfe.py`: LR4 LP+HP flat sum, mono sum equals single-LFE path when `mode: dual_mono`, power conserved, stopband per channel |
| M3 | 3.2 target + folds | `outputs/immersive_3_2.json`, `fold_chain`, `downmix` stages, ADM DirectSpeakers with LFE1/LFE2, `render_targets` validation, `_default` unchanged | `test_immersive_3_2.py` (clone of `test_immersive_31.py` pattern), `test_adm_bw64.py` additions, fold identities |
| M4 | 3.2 QA rows | `lfe.*`, `front.fold_phantom`, virtual box-room modal sim; rows advisory in `gate_profiles.ROWS`; `docs/VIRTUAL-SPEAKER-QA.md` update | synthetic: flipped-polarity sub trips `lfe.polarity`; identical subs pass coherence; known-ITD source recovers ITD |
| M5 | Ear model core | `scripts/ear_model/` (middle ear, CAR cascade, IHC, adaptation, chunked state), benchmark script `tests/bench_ear.py`; decide vendored CARFAC-NumPy vs clean-room after measuring | impulse / tone / two-tone fixtures: tone-in-noise compressive slope, adaptation time constants, chunk-boundary continuity (chunked == unchunked within 1e-6), runtime budget test (skippable on slow CI) |
| M6 | Ear rows | `ear.fatigue`, `ear.masking`, `ear.mod_roughness`, `ear.pitch_salience`, `ear.iacc`; calibrate on `tests/fixtures/roughness/`; add fatigue fixtures (dense saturated pad vs same-LUFS sparse texture) | fixture ordering tests: fatigued pad ranks above sparse; clean fifth above semitone cluster; salience ordering |
| M7 | Expectation | `scripts/expectation.py` PPM-C, viewpoints, IC/H series; `expr.*` rows; refactor `melodic_information_entropy` to call it (same row id, same thresholds) | known-sequence tests (repeated motif has falling IC; random has high IC); cross-check vs a hand-computed PPM on a toy string |
| M8 | Humanize coupling | keys `ic_agogic_ms`, `ic_vel`, `h_breath_ms` (default 0), seeded determinism preserved, `humanize_report` adds the coupling statistic | `test_humanize_stats.py` additions: default preset renders identically to today; with keys on, rho(IC, lengthening) > 0 and within caps |
| M9 | Emotion arc | `intent/valence_arousal.json` (sourced), feature extractor, `emotion.*` rows (WARN-only valence), calibration script (user data), direction-sheet comparison in `listen.py` output | synthetic arousal ladder (tempo/density/level) is monotone; mode flip moves valence sign |
| M10 | Optional GPU / calibration | JAX CARFAC behind `compute.py`; ZBC probe-reference script (optional extra); promote calibrated rows from advisory to FAIL where evidence supports it | parity test CPU vs JAX within tolerance |

Order: M0-M4 (3.2) and M5-M6 (ears) are independent tracks; M7-M9 independent of both. Suggested first PR set: M0, M1, M5 in parallel.

## 6. Risks and what is not verified

- 3.2 is a project layout, not a standard; any "open standard" claim in a delivery note would be false.
- All library licence/path statements marked [lit] came from search snippets; confirm each LICENSE file before vendoring.
- The §3.4 timings are from a surrogate, not CARFAC with AGC. Real cost is unmeasured.
- Ear-model thresholds are starting values; fatigue in particular has no published pass mark for music. Advisory until calibrated.
- Valence from audio is unreliable; arousal is better. Do not gate on valence.
- Nothing was auditioned; no listening test supports any row. Taste, realism and room behaviour stay unmeasured (AGENTS §7.10).
- A front-only layout will trip existing `imm.decode_uniformity`/surround-energy expectations; each needs a measured, written per-layout declaration.

## Sources consulted (search only, not read in depth)
- CARFAC v2 in Matlab, NumPy, JAX: https://arxiv.org/html/2404.17490v1 ; https://github.com/google/carfac
- py2lispIDyOM (wrapper, MIT) https://pypi.org/project/py2lispidyom ; IDyOMpy paper code https://github.com/GuiMarion/codeForPaper-IDyOMpy-
- PyZBC2014 (AGPL-3.0) https://github.com/tomstoll/PyZBC2014 ; cochlea (GPL-3) https://github.com/mrkrd/cochlea
- Repo files read: AGENTS.md, docs/PSYCHOACOUSTICS.md, docs/roughness_model.md, spatial_engine/{config,bass,downmix,master,pan,render}.py, spatial_gate.py, render_targets.py, naturalness_check.py, pattern_audit.py, humanize.py, gate_profiles.py, layouts/outputs presets.
- NOT read in full: SKILL.md, quality_gate.py, listen.py, theory.py, compose.py, video-mixer/gate/, hoa.py, adm.py, loudness.py, compute.py.
