# Neurochemical affect plan — a chemistry layer beside the virtual ears

Status: **IMPLEMENTED (M1-M6).** Date: 2026-11-24. This document is the design; section 10 lists what was built,
where it lives, and the four places the code differs from the plan below. The plan text is left as written so the
design and what shipped can be compared.

Goal: the gate should judge not only whether a piece is *clean* (the existing rows) and whether its
periphery is *driven sanely* (`ear.*`), but whether its arc contains the events that make a listener
**want** the next moment, **feel** the arrival, and **come down** afterwards — so that a render that
passes every technical row can still be told "this does not connect yet, and here is the bar that
says so".

This is the plan for that layer. It is deliberately conservative: the layer is called
**chemical-reaction analysis** because it integrates release/clearance/adaptation kinetics, not
because it measures a molecule. Nothing here may print "dopamine released".

Evidence labels, as elsewhere in this repo:

- **[repo]** read in this repository;
- **[lit]** read in the cited paper/abstract during this session;
- **[lit, abstract only]** the claim is from the abstract or a search excerpt, not the full methods;
- **[start]** a starting value or modelling choice of this skill, not a measurement.

---

## 0. Findings that change the brief

1. **There is no audio-only measurement of neurochemistry.** Every human result below is PET/fMRI,
   a pharmacological challenge, or a peripheral assay (saliva/plasma). A render can only supply
   *elicitors*, and the layer must say "proxy" in every row. This is the same honesty rule the
   virtual ears already follow (`knowledgebase/sound-design/virtual-ears.md`: "fatigue is a proxy").
2. **The strongest, most replicated link is expectation → reward, not "sad chord → sad listener".**
   Dopaminergic anticipation/consummation, reward-prediction error and the uncertainty×surprise
   interaction are the parts with causal evidence [lit]. Mode/tempo→mood is a cue table, not
   chemistry. The layer must therefore be built on the expectancy model the repo already has
   (`scripts/expectation.py`), not on a bigger emotion-word table.
3. **Chills are predictable only barely better than chance.** The largest model (1,806 chills in
   1,019 pieces, 402 listeners) reaches **AUC ≈ 0.56–0.60** with acoustic + IDyOM features
   [lit, de Fleurian et al. 2024]. A row built on that must never FAIL a piece, and its threshold
   must be justified against a *held-out track* split — otherwise it encodes the training set.
4. **Stress/relaxation effects are real but small and context-dependent.** The big meta-analysis
   finds d ≈ 0.38 physiological, 0.35 hormonal, 0.46 heart rate across 104 RCTs [lit, de Witte et
   al. 2019]; a later meta-analysis of *stress recovery* finds g = 0.15, CI [−0.21, 0.52], i.e. not
   distinguishable from silence [lit, 2022]. Slow-tempo listening raised salivary oxytocin and HRV
   in one within-subject study [lit, Ooishi 2017]; choral singing *lowered* salivary oxytocin in
   another [lit, 2017]. So "bonding" is a low-confidence construct and cannot be a gate row that
   anyone fixes notes to satisfy.
5. **Individual differences dominate.** 5–10 % of people have specific musical anhedonia — normal
   reward responses to money, no pleasure from music [lit, Mas-Herrero 2014; Belfi 2020 review].
   Familiarity, preference and listening context outweigh any acoustic feature we can compute.
   The layer can only be about *ingredients*, never about a guaranteed reaction.
6. **The repo already has most of the machinery**: expectancy (IC/H), Chew tension, Witek groove,
   a major/minor valence proxy, an arousal arc, and a neural-activity-pattern ear model. The new
   layer is an integrator, not a new signal chain.
7. **The gate is where this belongs, but only as WARN/INFO.** `ear.*` rows are advisory because
   their numbers are synthetic-fixture starting values [repo]. Chemistry is weaker evidence than
   cochlear mechanics, so `chem.*` must start advisory and stay WARN-only even after calibration.

---

## 1. Evidence, with its real strength

| Construct | What was actually measured | Result | Confidence for a gate row |
|---|---|---|---|
| **Dopaminergic reward — anticipation** | [¹¹C]raclopride PET + fMRI; dorsal striatum (caudate) before chills | Dopamine release during anticipation of the peak; caudate BOLD scales with number of chills [lit, Salimpoor et al. 2011; NCBI Bookshelf summary] | **Moderate.** Causal-ish, but n small and music self-selected |
| **Dopaminergic reward — consummation** | Same, ventral striatum (NAcc) during the chill | Release at the peak; NAcc activity predicts willingness to pay [lit, Salimpoor 2011/2013] | **Moderate** |
| **Dopamine is causal, not incidental** | Levodopa vs risperidone vs placebo, real-time pleasure + EDA | Bidirectional modulation of musical pleasure and motivational bids [lit, Ferreri et al. 2019 PNAS] | **Moderate–strong** for the mechanism; not a feature recipe |
| **Reward prediction error** | fMRI + RL model, consonant/dissonant outcomes | NAc tracks musical RPE [lit, Gold et al. 2019 PNAS]; a published critique notes sensory vs reward prediction are conflated [lit, PNAS letter 2019] | **Low–moderate.** Use as "expectation violation", not as a dopamine meter |
| **Uncertainty × surprise** | Chord-progression fMRI + liking | Liking peaks at high-surprise/low-uncertainty *or* low-surprise/high-uncertainty [lit, Cheung et al. 2019 Current Biology] | **Moderate.** Maps directly onto the repo's `ic`/`h` |
| **Chills (frisson)** | PET; HR, EMG, respiration during self-selected chills | Ventral striatum, midbrain, amygdala, OFC, vmPFC; autonomic changes accompany chills [lit, Blood & Zatorre 2001, n=10] | **Moderate** for the phenomenon, **weak** for prediction |
| **Chill prediction from audio** | 1,806 onsets / 1,019 tracks; 16 acoustic + IDyOM features; SVM/GMM-HMM | AUC 0.56–0.60; F1 ≈ 0.07–0.08; best model only marginally over chance [lit, de Fleurian et al. 2024] | **Weak.** A row here is a nudge, not a verdict |
| **Chills corpus bias** | 988 chill tracks vs matched controls | Chill tracks are sadder, slower, less intense, more instrumental; logistic R² ≈ 0.006 [lit, de Fleurian & Pearce 2021] | **Weak**; warns against a "chills = epic" rule |
| **Tension / expectation** | ITPRA framework (imagination, tension, prediction, reaction, appraisal) | Five response systems on different time scales; tension is pre-outcome, appraisal post-outcome [lit, Huron 2006/2020] | **Strong as a framework**, not as numbers |
| **Stress / cortisol** | 104 RCTs, 9,617 participants | d = 0.38 physiological, 0.545 psychological, 0.349 hormones, 0.456 HR [lit, de Witte et al. 2019] | **Moderate** for intervention effect; **weak** for a single track |
| **Stress recovery** | 14 experimental studies, N=706 | g = 0.15, 95 % CI [−0.21, 0.52], p = .37 vs silence/control [lit, 2022 PLOS ONE] | **Weak**: no reliable recovery effect from listening alone |
| **Oxytocin — listening** | Saliva, within-subject, slow vs fast tempo (n≈23–25) | Slow tempo ↑ oxytocin, ↓ HR, ↑ HF-HRV; oxytocin change correlated with HR (r = −0.47) but *not* with valence/arousal [lit, Ooishi et al. 2017] | **Low** |
| **Oxytocin — singing/clinical** | 40 cardiac-surgery patients, RCT | Music ↑ plasma oxytocin and relaxation vs bed rest [lit, Nilsson 2009] | **Low–moderate**, clinical context, not a mix decision |
| **Oxytocin — group singing** | Saliva, choir vs solo | Salivary oxytocin *decreased* after both; peripheral assays disagree across studies [lit, 2017] | **Low**; do not build a row on it |
| **Endorphins / social bonding** | Pain threshold as proxy; singing, dance, synchrony | Synchrony and exertion independently raise pain threshold and bonding [lit, Tarr/Dunbar 2015]; group singing raises pain threshold [lit, Pearce et al. 2016] | **Low–moderate**; exertion/synchrony, not "happy chords" |
| **Groove** | Syncopation (BSI) and body movement | Inverted-U: medium syncopation most pleasurable/moving [lit, Witek et al. 2014] | **Moderate**, and already implemented as `feel.witek` |
| **Individual differences** | BMRQ + SCR/HR, 3 groups of 10 | Specific musical anhedonia: no autonomic response to music, normal to money; prevalence 5–10 % [lit, Mas-Herrero 2014; Belfi 2020] | **Strong constraint**: no guarantee is possible |

**What this licenses:** a layer that scores *elicitor density and ordering* — does the piece build
uncertainty, then resolve it at a marked arrival, then recover? — and reports it as an inferred
state with a confidence tier.

**What it forbids:** rows named after a molecule, rows that FAIL, rows that claim a listener's
feeling, and "more chills" as an optimisation target (that produces riser-impact cliché).

---

## 2. What the repo already has

| Area | Exists | Used by this plan |
|---|---|---|
| Expectancy | `scripts/expectation.py`: PPM-C over pitch interval, scale degree, IOI; per-note IC and H; `note_z`, `by_bar`, `ungrounded_share` [repo] | **Primary driver** of anticipation, tension and arrival surprise |
| Tension | `pattern_audit.spiral_tension_arc` (Chew helical tension per 2-bar window), `tension_ic_row` [repo] | Stress-load and arrival-contrast inputs |
| Groove | `pattern_audit.witek_groove_curve` (BSI, sweet-spot window), `groove_pocket_lock`, `kinematic_effort_feel` [repo] | Motor/endorphin proxy |
| Affect | `scripts/affect.py`: per-section LUFS, onset rate, centroid, major/minor mode score, clash; `emotion.arc_arousal`, `emotion.arc_valence` [repo] | Arousal/valence axis and section slicing — reuse, do not duplicate |
| Virtual ears | `scripts/ear_model/` + `scripts/ear_rows.py`: NAP, fatigue, roughness, masking share, pitch salience, IACC [repo] | Peripheral gating of the chemical inputs (roughness→stress, masking→disconnection, fatigue→flatness) |
| Direction | Direction sheet with `sections`, `hits_at`, `energy`, `expression.cues` [repo] | Ground truth for "where the arrival was promised" |
| Gate | `gate_profiles.ROWS` registry, `(default,min,max)`, `on/param/mode`, advisory precedent [repo] | New rows and their defaults |
| Reports | `arc_report.py`, `expression_report.py`, `realism_report.py` pattern [repo] | `chem_report.py` mirrors them |

**Gap:** no cross-feature integrator, no time constants, no notion of anticipation vs consummation,
no recovery, and no row that asks whether the piece's *ordering* of events can produce a reward
cycle. `emotion.arc_*` asks "is the section as active as the sheet says"; it does not ask "does the
piece earn its peak".

---

## 3. The model: reaction kinetics, not a mood classifier

### 3.1 State

Seven pools, each a scalar state per time step. Two time scales per pool: a **phasic** pool `P`
(released, cleared) and an **availability** state `A` (receptor/vesicle depletion and recovery).
This is the smallest structure that can express "the build creates drive", "the drop spends it",
"the next drop is weaker because the pool is depleted", and "the ending recovers".

| Pool | Reads as | Evidence tier | Boundary |
|---|---|---|---|
| `DA_ant` | dopaminergic **anticipation** drive (wanting the next event) | B | caudate/anticipation [lit] |
| `DA_con` | dopaminergic **consummation** (the arrival lands) | B | NAcc/peak [lit] |
| `NE` | noradrenergic arousal / alertness | B | inferred from arousal + surprise, not assayed |
| `CORT` | stress load (HPA, slow) | C | slow, context-heavy; never a "this track stresses people" claim |
| `OXT` | affiliative/social warmth | C | peripheral assays disagree; low weight |
| `END` | effort/endorphin (exertion + synchrony) | C | pain-threshold proxy only [lit] |
| `PSNS` | parasympathetic recovery / come-down | C | HRV proxy from slow tempo + low flux [lit] |

Tier A is reserved for a row that has held-out predictive validity; nothing starts there.

### 3.2 Kinetics

For each pool `i` at time `t`:

```
dP_i/dt = R_i(t) * A_i(t)  -  Vmax_i * P_i / (Km_i + P_i)  -  k_i * P_i
dA_i/dt = (1 - A_i) / tau_rec_i  -  k_des_i * P_i * A_i
R_i(t)  = sum_j  w_ij * u_j(t)
```

- `u_j(t)` are the normalized elicitor signals of §3.3, each in 0..1.
- The Michaelis–Menten term is saturation: a very loud/dense passage cannot release unbounded
  "reward"; this is what stops the layer rewarding maximal intensity.
- `k_des` is adaptation: a repeated arrival releases less. This is the formal reason a piece with
  six identical drops reads as flat, and it is the anti-cliché mechanism.
- `Vmax`, `Km`, `k`, `tau_rec`, `k_des`, and every `w_ij` live in
  `references/data/presets/chem/model.json` with `provenance` on each block. All are **[start]**.

Time constants (model choices, not measurements) **[start]**:

| Pool | `k` (1/s) | `tau_rec` (s) | `k_des` |
|---|---|---|---|
| `DA_ant` | 0.15 | 8 | 0.6 |
| `DA_con` | 0.25 | 12 | 0.8 |
| `NE` | 0.08 | 20 | 0.2 |
| `CORT` | 0.002 | 600 | 0.02 |
| `OXT` | 0.004 | 300 | 0.05 |
| `END` | 0.01 | 120 | 0.1 |
| `PSNS` | 0.05 | 60 | 0.1 |

Integration: explicit Euler at 4 Hz over the master's duration (cheap; the pools are slow relative
to the step). Report the step and a convergence check against 8 Hz in the tests.

### 3.3 Elicitors (`u_j`) and where they come from

| Elicitor | Definition | Source | Cost |
|---|---|---|---|
| `build` | normalized positive slope of short-term loudness + onset rate + centroid over a 4–12 s window | `affect.section_features` on 1 s hops | cheap |
| `proximity` | 1 − normalized time to the next declared arrival (`hits_at` / section peak) | direction sheet + section map | free |
| `tension` | Chew spiral strain, normalized per piece | `pattern_audit.spiral_tension_arc` | free (score) |
| `uncertainty` | mean melodic `H` per bar, normalized | `expectation.Expectation` | ms (score) |
| `surprise` | mean melodic `IC` per bar, normalized; `ungrounded_share` subtracted | `expectation` | ms |
| `roughness` | NAP 30–150 Hz modulation index | `ear_model` summary | ~6 s/min mono |
| `fatigue` | NAP adaptation depth | `ear_model` summary | shared with roughness |
| `masking` | 1 − figure's neural share | `ear_model` + stems | shared |
| `pulse` | pulse clarity (already in `listen.py`) × 1/|BSI − sweet spot| | `listen`/`pattern_audit` | cheap |
| `vocal` | share of frames with a `vocal` role or voice-like preset | score + stems | free |
| `legato` | share of figure notes with `art: legato` / long gate | score | free |
| `consonance` | 1 − (clash + roughness) | `affect` + ears | shared |
| `low_end` | 20–80 Hz share relative to the piece's own median | audio | cheap |
| `silence` | rest/silence share in the window | score/audio | free |
| `arrival` | composite jump at a boundary: ΔLUFS (3 s), Δcentroid, spectral flux, Δlow-end, vocal entry | audio + sheet | cheap |
| `recovery` | fall in onset rate + centroid + mode brightening + consonant resolution after the last peak | `affect` per section | cheap |

Normalization is per piece (percentile rank) except `proximity`, `silence` and `arrival`, which are
absolute. Per-piece normalization is what keeps the layer from rewarding loudness; the trade-off is
that it cannot compare two pieces, only order events inside one. State that in the report.

### 3.4 Coupling (what raises which pool)

| Pool | Positive | Negative / saturating |
|---|---|---|
| `DA_ant` | `build`, `proximity`, `tension`, `uncertainty` | `silence` late in the build (a hole is not a build) |
| `DA_con` | `arrival`, `surprise` (grounded), `low_end`, `vocal` entry | `fatigue`, repeated `arrival` within `tau_rec` |
| `NE` | `surprise`, `roughness`, `onset rate`, `low_end` | `legato`, `silence` |
| `CORT` | `tension` unresolved, `roughness`, `masking`, `ungrounded_share`, sustained `NE` | `consonance`, `recovery`, `silence` |
| `OXT` | `legato`, `vocal`, `consonance`, slow tempo, stable `pulse` | `roughness`, `surprise` spikes |
| `END` | `pulse` in the Witek window, `low_end`, `onset rate`, duration of the peak | `silence`, tempo outside the groove range |
| `PSNS` | `recovery`, `consonance`, `legato`, falling `NE` | `tension`, `arrival` |

Weights default to 1.0 per named input and are then scaled by the preset; a missing input drops its
term and the row says so (never silently zero). This mirrors the ear model's "not measured" rows.

---

## 4. Gate rows

Registered in `gate_profiles.ROWS` with `(default, min, max)`, called from `quality_gate.py` after
`affect.rows` (line ~1796) and `ear_rows.rows` (line ~2055), so the ear summary can be passed in
rather than recomputed. **All are INFO or WARN. None can FAIL, be protected, or be skipped silently.**

| Row | Question it asks | Reads | Default (WARN above/below) | Remediation lever |
|---|---|---|---|---|
| `chem.reward_build` | Does the piece earn its arrival, or just get louder? | `DA_ant` ramp, correlation with `proximity`, lead time | `min_lead_s` 4.0; `min_rho` 0.6; `min_peak` 0.45 **[start]** | lengthen the build, withhold the tonic, raise tension before the hit, move the arrival later |
| `chem.reward_arrival` | Is there a real consummation event, and is it the loudest reward moment? | `DA_con` peak, `arrival` composite, offset to declared hit | `min_peak` 0.5; `max_offset_s` 2.0; `min_contrast_db` 3.0 **[start]** | put an actual change at the hit (timbre, low end, voice, register), not a volume nudge; stop burying the peak in the bed |
| `chem.stress_load` | Is tension carried and then resolved, or just accumulated? | `CORT` AUC, unresolved share, post-peak return | `max_auc` 0.35 per minute; `max_unresolved_s` 8.0; `min_resolve_frac` 0.6 **[start]** | resolve the dominant, thin the cluster, add a breath, move roughness out of the figure's band |
| `chem.affiliation` | Is there anything voice-like to bond with? | `OXT` mean in stable sections, legato/vocal share | `min_mean` 0.45; `min_legato` 0.5 when a figure exists **[start]** | give the lead a singable contour and legato, add a voice/hum, slow the harmonic rhythm, warm 150–400 Hz |
| `chem.motor_drive` | Does the body have something to lock to? | `END` mean, BSI window, pulse clarity | `bsi` in 0.4–4.8; `min_pulse` 0.4; `min_mean` 0.4 **[start]** | syncopate the cell into the window, make the kick/bass one owner, raise pulse clarity, keep the peak long enough |
| `chem.recovery` | Does the piece come down, or stop? | `PSNS` rise, `CORT`/`NE` fall over the final 20 % | `min_drop_frac` 0.35; `max_final_cort` 0.4 **[start]** | write a resolution section: slower, consonant, lower density, a real final cadence or a deliberate cliff (declare it) |
| `chem.arc_variety` | Is the piece a single chemical state? | number of pools that move ≥ 2× their own noise; flat share; arrivals per minute | `min_states` 3 of 6; `max_flat_share` 0.6; `max_arrivals_per_min` 1.0 **[start]** | change the state between sections; remove duplicate drops; give the middle a different chemistry from the chorus |

Detail text must include the **confidence tier** and the input list that was actually measured, e.g.:

```
WARN chem.reward_arrival: peak 0.31 at 62.0 s, 6.5 s after the declared hit; arrival contrast 1.2 dB.
      Inputs: arrival, surprise, low_end, vocal. Tier C (inferred, not assayed).
      No second arrival within 20 s, so depletion is not the cause.
```

### 4.1 Promotion rule

A row may move from `INFO` to `WARN` only when:

1. it separates positive from negative controls on **held-out tracks** (oChiM: AUC ≥ 0.62; DEAM
   arousal: Spearman ρ ≥ 0.5), and
2. a shuffled-label run is at chance (AUC 0.45–0.55), and
3. the reason names the dataset, split and measurement in the profile JSON, exactly as
   `ambient.json` names its fixture measurement for `ear.fatigue`.

No `chem.*` row ever becomes `FAIL`. The evidence does not support failing a piece, and the
individual-difference literature says the same piece can be inert for 5–10 % of listeners.

---

## 5. Making the music connect: the direction loop

The rows are useless if they only report. The layer must feed the existing director loop.

1. **Before the score (Phase 4.8/4.9).** Add an optional `expression.chem` block to the direction
   sheet: `{"build_s": 12, "arrival_s": 34, "stress_peak_s": 40, "recovery_s": 55,
   "avoid": ["flat_peak", "second_drop_without_new_information"]}`. Optional at first: absent means
   the rows report, and `direction.expression` already has a WARN precedent for a half-written sheet.
2. **Craft pass.** `references/workflow/director-craft.md` gains a seventh answer: *what does the
   listener want at each boundary, and what do they get?* Written before notes, reviewed in 9.4e.
3. **After the render (9.4b).** `scripts/helpers/chem_report.py` prints the seven pool traces, the
   arrival table against `hits_at`, and the flat stretches — the same shape as `arc_report.py`.
4. **Revision.** A failing row's remediation names a lever that exists (build length, arrival
   contrast, resolution, legato, BSI, duplicate drop). One lever per revision, per the existing
   rule.
5. **`listen.py`.** Print the chem arc next to pulse clarity, so the ears and the inferred state
   are read together. The ear can contradict the model; when it does, the report says so.

**Anti-cliché guard.** `chem.arc_variety` and the `k_des` term exist because "maximise chills"
degenerates into riser–impact–riser. A piece that adds a second identical arrival within `tau_rec`
gets *less* `DA_con`, and `max_arrivals_per_min` caps the density. The layer must never be used as
a reward function for a generator.

---

## 6. Calibration and acceptance

| Stage | Data | What it can establish | What it cannot |
|---|---|---|---|
| **C0 synthetic fixtures** | 8 × 24 s cues, each differs in one dimension (build length, arrival contrast, resolution, vocal/legato, groove BSI, duplicate drop) | ordering: the build cue outranks the flat cue on `DA_ant`; the resolved cue outranks the unresolved on `chem.recovery`; the duplicate-drop cue is penalised | anything about listeners |
| **C1 chills** | oChiM features + onsets (1,019 tracks, 1,806 onsets) [lit]; licence to verify before download | held-out **track** AUC for `chem.reward_arrival`; feature importances | causality; the dataset is self-selected Western-leaning music |
| **C2 affect** | DEAM (1,802 tracks, 2 Hz valence/arousal) [lit] | whether the `NE`/arousal composite tracks annotated arousal (expect ρ ≈ 0.5); valence will be weak | valence, taste |
| **C3 listening pilot** | ≥ 12 listeners, 6 cues, 5-point "moved / want to hear again" + free text | direction of effect, not significance; report as a pilot with N | a general claim about listeners |

Negative controls are mandatory: shuffled labels, time-reversed audio, and a flat 60 s pad. A row
that cannot fail its negative control is not a row (same rule as `video_score.py --selftest`).

Acceptance for the whole layer, stated as a limitation rather than a promise: *the gate can say a
render contains the elicitors and their ordering; it cannot say a given listener will feel
anything.*

---

## 7. Phased roadmap

| # | Milestone | Scope | Tests |
|---|---|---|---|
| **M0** | KB + docs | `knowledgebase/sound-design/neurochemical-affect.md` (header, evidence tiers, every number labelled); row in `knowledgebase/README.md`; this doc in `docs/README.md`; `python tests/check_kb.py` | `check_kb.py` |
| **M1** | Feature bus | `scripts/chem_model/features.py`: one function per `u_j`, all reused from `affect`/`expectation`/`ear_model`/`pattern_audit`; returns a `(time, feature)` matrix plus a `measured` mask | each feature monotone on a synthetic cue; missing input → `measured=False`, not 0 |
| **M2** | Kinetics | `scripts/chem_model/pools.py`: the ODE, preset loader, `provenance` required; 4 Hz Euler with an 8 Hz convergence check | mass-balance: no pool negative; zero input decays to 0; step response peaks then decays; duplicate arrivals give a smaller second peak |
| **M3** | Preset | `references/data/presets/chem/model.json` with every constant labelled `[start]` and a reason; `chem.py` facade | unknown key raises; a missing block raises; defaults documented |
| **M4** | Rows | `scripts/chem_rows.py` + `gate_profiles.ROWS` entries; wire after `ear_rows`; pass the ear summary; `lint_coverage.py` | positive/negative controls per row; every row is INFO/WARN only; detail names measured inputs |
| **M5** | Report | `scripts/helpers/chem_report.py`, same CLI shape as `arc_report.py` | report on the fixture set; flat cue vs build cue ordering |
| **M6** | Direction | optional `expression.chem` in the sheet template + `director-craft.md` seventh answer | sheet validates; absent block is a WARN, not a crash; section names must match the score |
| **M7** | Calibration | oChiM/DEAM scripts (download on the user's machine, never bundled); held-out split; weights land in the preset with provenance | shuffled-label control at chance; held-out AUC/ρ reported; a row is promoted only if it passes §4.1 |
| **M8** | Listening pilot | 6 cues, ≥ 12 listeners, sheet + analysis script | report N, direction, and that it is not significance |

M1–M5 are useful without M7 (advisory rows, honest INFO). M7 is what would let any row WARN.

---

## 8. Risks and limits

- **Reverse inference.** Region → transmitter → feeling is the classic fallacy. The layer is an
  *elicitor* model, not a measurement; every row says so.
- **Peripheral assays are noisy.** Salivary oxytocin is assay-sensitive and studies disagree on
  direction [lit: Ooishi +, choir −]. Cortisol is confounded by time of day and context. That is
  why `OXT` and `CORT` are tier C.
- **Effect sizes are small.** d ≈ 0.35–0.45 for stress outcomes; g = 0.15 n.s. for recovery. Do not
  sell a track as therapy.
- **Chills prediction is near chance** (AUC ≈ 0.60). A `chem.reward_arrival` WARN is a hint, not a
  finding.
- **Dataset bias.** oChiM/DEAM are Western, self-selected, mostly popular music. A Carnatic or
  maqam piece may read low for reasons that are cultural, not compositional. The report must name
  the calibration corpus and refuse to generalise.
- **Loudness confound.** Features must be read from stems or pre-master where possible; a limiter
  changes short-term loudness and would fake an arrival.
- **Per-piece normalization** means the layer cannot say "this piece is more emotional than that
  one"; it orders events within a piece.
- **Nothing here is auditioned.** No listening test supports a row until M8. Taste, realism and
  whether the piece actually moves someone remain unmeasured.
- **The name.** "Chemical reaction analysis" is the user's phrase; in the code and reports it must
  always be "inferred neurochemical state (proxy)".

---

## 9. Sources

Read during this session unless marked *(abstract only)*.

- Blood, A. J., & Zatorre, R. J. (2001). Intensely pleasurable responses to music correlate with
  activity in brain regions implicated in reward and emotion. *PNAS* 98(20), 11818–11823.
  https://www.pnas.org/doi/10.1073/pnas.191355898
- Salimpoor, V. N., Benovoy, M., Larcher, K., Dagher, A., & Zatorre, R. J. (2011). Anatomically
  distinct dopamine release during anticipation and experience of peak emotion to music.
  *Nature Neuroscience* 14, 257–262. (Summary read in NCBI Bookshelf NBK92781.)
- Ferreri, L., Mas-Herrero, E., Zatorre, R. J., Ripollés, P., Gomez-Andres, A., Alicart, H., …
  Rodriguez-Fornells, A. (2019). Dopamine modulates the reward experiences elicited by music.
  *PNAS* 116(9), 3793–3798. https://www.pnas.org/doi/10.1073/pnas.1811878116
- Gold, B. P., Mas-Herrero, E., Zeighami, Y., Benovoy, M., Dagher, A., & Zatorre, R. J. (2019).
  Musical reward prediction errors engage the nucleus accumbens and motivate learning. *PNAS*
  116(9), 3310–3315. https://www.pnas.org/doi/10.1073/pnas.1809855116 — with the published
  critique: https://www.pnas.org/doi/10.1073/pnas.1913244116
- Mas-Herrero, E., Dagher, A., Farrés-Franch, M., & Zatorre, R. J. (2021). Unraveling the temporal
  dynamics of reward signals in music-induced pleasure with TMS. *J. Neurosci.* 41(17), 3889–3899.
- Cheung, V. K. M., Harrison, P. M. C., Meyer, L., Pearce, M. T., Haynes, J.-D., & Koelsch, S.
  (2019). Uncertainty and surprise jointly predict musical pleasure and amygdala, hippocampus, and
  auditory cortex activity. *Current Biology* 29(23), 4084–4092.
- de Fleurian, R., Clemente, A., Benetos, E., & Pearce, M. T. (2024). Expectation elicits
  music-evoked chills. *bioRxiv* 2024.10.02.616280.
  https://www.biorxiv.org/content/10.1101/2024.10.02.616280v1 (supplementary Table 1 read)
- de Fleurian, R., & Pearce, M. T. (2021). The relationship between valence and chills in music: a
  corpus analysis. *i-Perception* 12(4). https://doi.org/10.1177/2059204320915654 *(abstract only)*
- Huron, D. (2006). *Sweet Anticipation: Music and the Psychology of Expectation*. MIT Press.
  ITPRA summary read in Huron (2020), *J. Consciousness Studies* 27(3–4), 185–202.
- de Witte, M., Spruit, A., van Hooren, S., Moonen, X., & Stams, G.-J. (2020). Effects of music
  interventions on stress-related outcomes: a systematic review and two meta-analyses. *Health
  Psychology Review* 14(2), 294–324. https://doi.org/10.1080/17437199.2019.1627897
- Music listening and stress recovery in healthy individuals: a systematic review with
  meta-analysis (2022). *PLOS ONE* 17(6), e0270031.
  https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0270031
- Ooishi, Y., Mukai, H., Watanabe, K., Kawato, S., & Kashino, M. (2017). Increase in salivary
  oxytocin and decrease in salivary cortisol after listening to relaxing slow-tempo and exciting
  fast-tempo music. *PLOS ONE* 12(12), e0189075.
- Nilsson, U. (2009). Soothing music can increase oxytocin levels during bed rest after open-heart
  surgery: a randomised control trial. *Journal of Clinical Nursing* 18(15), 2153–2161.
  *(abstract only)*
- Choir versus solo singing: effects on mood, and salivary oxytocin and cortisol concentrations
  (2017). *Frontiers in Human Neuroscience* 11, 430. *(abstract only)*
- Tarr, B., Launay, J., Cohen, E., & Dunbar, R. (2015). Synchrony and exertion during dance
  independently raise pain threshold and encourage social bonding. *Biology Letters* 11(10),
  20150767.
- Pearce, E., Launay, J., & Dunbar, R. I. M. (2016). Group music performance causes elevated pain
  thresholds and social bonding in small and large groups of singers. *Evolution and Human
  Behavior* 37(2), 152–158. *(abstract only)*
- Witek, M. A. G., Clarke, E. F., Wallentin, M., Kringelbach, M. L., & Vuust, P. (2014).
  Syncopation, body-movement and pleasure in groove music. *PLOS ONE* 9(4), e94446.
- Mas-Herrero, E., Zatorre, R. J., Rodriguez-Fornells, A., & Marco-Pallarés, J. (2014).
  Dissociation between musical and monetary reward responses in specific musical anhedonia.
  *Current Biology* 24(6), 699–704. *(abstract only)*
- Belfi, A. M., & Loui, P. (2020). Musical anhedonia and rewards of music listening: current
  advances and a proposed model. *Annals of the New York Academy of Sciences* 1464(1), 99–114.
  *(abstract only, prevalence 5–10 %)*
- DEAM: Aljanaki, A., Yang, Y.-H., & Soleymani, M. (2017). Developing a benchmark for emotional
  analysis of music. *PLOS ONE* 12(3), e0173392. https://cvml.unige.ch/databases/DEAM
- oChiM dataset: de Fleurian, R., & Pearce, M. T. (2021). OSF, doi:10.17605/osf.io/x59fm
  (licence to verify before any download).

Repo files read for this plan: `AGENTS.md`, `SKILL.md`, `docs/PSYCHOACOUSTICS.md`,
`docs/THEATRICAL-REALISM-PLAN.md`, `scripts/affect.py`, `scripts/expectation.py`,
`scripts/ear_rows.py`, `scripts/ear_model/summary.py`, `scripts/gate_profiles.py`
(`ROWS`, `emotion.*`, `ear.*`), `scripts/pattern_audit.py` (function list, `witek_groove_curve`),
`scripts/quality_gate.py` (row call sites), `scripts/listen.py` (pulse clarity),
`knowledgebase/sound-design/virtual-ears.md`, `knowledgebase/sound-design/valence-arousal.md`,
`knowledgebase/README.md`, `references/scoring/emotion-and-scoring.md`,
`references/data/presets/gate/melodic.json`, `reports/research_immersive_3_2_virtual_ears.md`.
Not read in full: `quality_gate.py`, `intent.py`, `presets.py`, the renderer, `video-mixer/`.

---

## 10. What was built (M1-M6), and where it differs from the design

### 10.1 Files

| Path | Holds |
|---|---|
| `scripts/chem_model/config.py` | loads and validates the three presets; an unknown key or a number without a `why` is an error, never a default |
| `scripts/chem_model/features.py` | the elicitor bus: one function per input, all re-read from `affect`, `expectation`, `pattern_audit` and `ear_model`; a missing input is a zero array plus `measured[name] = False` |
| `scripts/chem_model/pools.py` | the ODE (`dP/dt`, `dA/dt`), explicit Euler at the preset step, `substeps` for the 8 Hz convergence check |
| `scripts/chem_model/measures.py` | the numbers each row prints, and the 0..1 signature the mood and genre rows compare |
| `scripts/chem_model/targets.py` | mood and genre resolution (any emotion in the intent vocabulary, any genre `compose.py` ships) |
| `scripts/chem_model/__init__.py` | one `evaluate(score, path, sheet, summary, gp)` call for the whole layer |
| `scripts/chem_rows.py` | the ten rows, INFO/WARN only |
| `scripts/helpers/chem_report.py` | the trace report, same shape as `arc_report.py` |
| `references/data/presets/chem/model.json` | seven pools, their kinetics, the elicitor→pool weights, the elicitor definitions, the dimension anchors, the levers, the confidence tiers |
| `references/data/presets/chem/moods.json` | valence/arousal axis shifts plus a per-mood override where two axes fail |
| `references/data/presets/chem/genres.json` | eleven genre families and the mapping of all 121 shipped genres (plus aliases) onto them |
| `tests/test_chem_gate.py` | 27 controls: kinetics, feature bus, ordering, every row positively and negatively |

### 10.2 How it runs

`quality_gate.py` computes the virtual ear's mono summary once (`ear_rows.summary_for`) and passes it to both
`ear_rows.rows` and `chem_rows.rows`, so the NAP runs once per gate pass. The chem rows read the master, the score,
and the project's direction sheet (`_direction_sheet`); they run with the other tier-2 rows, in `mode != 'draft'`.
A project preset under `<project>/presets/chem/` overrides any shipped value (the normal preset layering), and a gate
profile may skip a chem row for a type of music whose brief is different, with the measurement that says so.

### 10.3 The rows, as implemented

| Row | Parameters (default, range) |
|---|---|
| `chem.model` | none: reports the pools, tiers and that nothing can FAIL; WARN when a preset does not validate |
| `chem.reward_build` | `min_lead_s` 4.0 (1-20), `min_rho` 0.4 (0-0.95), `min_peak` 0.45 (0.1-0.9) |
| `chem.reward_arrival` | `min_peak` 0.5 (0.1-0.9), `max_offset_s` 2.0 (0.5-8), `min_contrast_db` 3.0 (0.5-9) |
| `chem.stress_load` | `max_mean_load` 0.35 (0.05-1.0), `max_unresolved_s` 8.0 (2-30), `min_resolve_frac` 0.6 (0.2-1.0) |
| `chem.affiliation` | `min_mean` 0.45 (0.1-0.9), `min_legato` 0.5 (0.1-0.95) |
| `chem.motor_drive` | `bsi_lo` 0.4 (0-2), `bsi_hi` 4.8 (2-8), `min_pulse` 0.4 (0.1-0.9), `min_mean` 0.4 (0.1-0.9) |
| `chem.recovery` | `min_drop_frac` 0.35 (0.05-0.9), `max_final_cort` 0.4 (0.1-0.9) |
| `chem.arc_variety` | `min_states` 3 (1-7), `max_flat_share` 0.6 (0.2-1.0), `max_arrivals_per_min` 1.0 (0.2-4) |
| `chem.mood_connection` | `max_distance` 0.25 (0.05-0.6) |
| `chem.genre_connection` | none: the family constraint and its tolerance are in `chem/genres.json` |

Every detail names the tier and the inputs it actually measured. `tense` (a profile that declares a piece ending on
its peak) turns the stress and recovery WARN into INFO with that reason said in the row: a declared cliff is a brief,
not a fault, and nothing is relaxed.

### 10.4 "Any mood, any genre" without a hand-written table

- **Mood.** The sheet's `intent.emotions` (and `score.meta.emotion`) resolve through `intent.resolve_word` to the
  intent vocabulary, then the mood's own valence/arousal coordinates move seven dimension targets by two axis shifts
  in `chem/moods.json`. A per-mood override fixes the cases two axes cannot express (grief's affiliation, scary's
  absence of comfort, calm's absence of drive). All 24 emotions are covered by construction and tested.
- **Genre.** All 121 genres `compose.py` ships map to one of eleven families. A family holds only the constraints that
  family is defined by, so a constraint the style does not care about never warns a good piece in it.
- **Signature.** Each dimension is `measured / anchor`, clipped to 0..1: "0.7" means about 70 % of the level the row's
  own starting bar calls high. It is not a physiological quantity and it is not comparable between pieces.

### 10.5 Where the code deliberately differs from sections 3-4

1. **`build` is a climb, not a slope.** A 4-12 s slope dies exactly at the hit, because the slow window catches up with
   the fast one, so anticipation decayed where it should peak. `build` is now the climb out of the running 12 s floor.
2. **`density` is absolute, not per piece.** A per-piece normalisation gave a static pad the same density as a drum
   pattern, and made the motor pool blind. It is now onsets per second against 4/s.
3. **`stress_load` reads the mean load, not an AUC per minute.** An integral per minute of a 0..1 pool is just its mean
   times 60; the parameter is `max_mean_load`, and the unresolved-time and resolve-share legs are unchanged.
4. **The pools are clipped at `vmax`.** With `k = 0.004` a pool with three positive inputs integrates past 1 and the
   0..1 row thresholds stop meaning anything. The pool is reported on its own 0..1 scale.
5. **`arc_variety` counts a *state*, not movement.** A pool that only ramps out of zero is the model warming up; it
   counts when it rises and comes back down, measured after a 10 s warm-up, and arrivals per minute use a 60 s window
   so a 30 s cue is not judged by a rate.
6. **No event, no build.** Below a measured change of 0.2 at the hit there is nothing to earn, and `chem.reward_build`
   says that instead of reporting a lead time against a non-event.
7. **The mood distance is asymmetric.** Falling short of a mood target counts fully, exceeding it counts
   `excess_weight` (0.5 in `chem/moods.json`): the row asks whether the piece *has* what the mood needs, so a cue with
   more build than the mood asks for must not be scored as wrong as one with none. `chem.mood_connection` is the one
   row that could otherwise warn every ambitious piece.

### 10.6 Verification and what it is not

`tests/test_chem_gate.py` (27 tests) covers: the presets validate and reject an unknown key or a missing `why`; all 24
emotions and all 121 genres resolve; zero input decays to zero, no pool goes negative or past its ceiling, a step
peaks then decays, a repeat inside the recovery constant releases less, and the 4 Hz step agrees with an 8 Hz one
within 0.05; the feature bus measures the written elicitors from a score alone and says so when audio or a mood is
missing; a build piece outranks a flat one, a resolved ending outranks a cliff, a repeat is spent; every row is
registered, lint-covered and returns INFO/WARN only, with the flat piece warning the build, the cliff warning recovery
and the double drop warning arrival density. The threshold snapshot (`tests/fixtures/gate/thresholds.json`) was
regenerated and the diff is **additions only**: no existing default moved.

**Not done, and not claimed:** no corpus calibration (M7) and no listening test (M8). The numbers are starting values;
`chem.reward_arrival`'s nearest published predictor reaches AUC 0.56-0.60, and 5-10 % of listeners are music-anhedonic,
so no row here can say a listener will feel anything. The mode/valence readings the model consumes are themselves a
weak measure. Nothing was auditioned.
