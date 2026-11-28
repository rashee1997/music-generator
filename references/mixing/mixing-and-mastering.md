---
title: Mixing and mastering
summary: The whole mix and master path: bus structure, dynamics, space, loudness targets and the embedded checks.
tags: [mix, master, loudness, lufs, true peak, limiter, reverb, depth]
load_when:
  - building or auditing a mix preset
  - loudness or true peak fails
---

# Mixing and mastering

`scripts/mixer.py` does this for you (render_natural.py calls it). Read this page to decide settings, to
fix what `naturalness_check.py` flags, and to mix any stems the user already has
(`python3 scripts/mixer.py stems_dir/ --mix mix.json --out final.wav`).

## 0. Where an effect or ambience sits (preset-driven)

An `sfx:<name>` or `env:<name>` track takes its mix settings from its own preset (`gain_db`, `reverb`, `spatial` with azimuth and distance, `eq`, `hp`, `lp`, `comp`, `duck_by`, `width`, `role`), the same way an instrument does; a key written on the score track overrides the preset, and a shipped default with no mix keys falls back to the role defaults (`fx`, `environment`). Ambience (`env:`) gets the environment treatment in the mixer: level, ducking under the lead, band carving and the ambient gate rows. A one-hit effect is an `fx` stem. So a rain made with a `model_layer`, a creak made with a `model`, and a recorded-and-fitted preset all sit in the mix through the same preset keys.

## 1. Order of operations (what a mix engineer does)

1. **Gain staging** - every stem to the same reference loudness (-24 LUFS), then a role level: melody -3, counter -6, chord -8, pad -11, bass -6, arp -9, drums -7 (dB). Fix balance with these first, EQ second.
2. **Subtractive EQ** - high-pass what does not need lows; cut mud (250-500 Hz); carve 2-4 kHz on accompaniment so the lead/voice is clear; only then add a little presence/air.
3. **Compression** - 2:1 to 4:1, slow-ish attack (15-25 ms) so the pluck/attack survives, release 100-300 ms; 2-4 dB gain reduction is plenty. Bass 3:1, drums 3:1.
4. **Low end** - mono below ~120 Hz; no pad/chord notes below MIDI 48 (C3) unless intended; one instrument owns the sub.
5. **Pan and width** - constant-power pan with orchestral seating (violins left, cello right, bass centre-right); widen pads with a mono-safe decorrelator, never with a delay that cancels in mono.
6. **Space** - one shared reverb bus (convolution with a synthesised impulse response). Return high-passed ~150 Hz and low-passed ~7.5 kHz so the tail adds depth, not mud or hiss.
7. **Ducking** - kick/voice triggers dips on bass/pads/music bed.
8. **Master** - gentle glue (1.6:1, 40 ms attack), tone tilt, limiter, loudness to target, true-peak safe.

## 2. EQ cheat sheet (frequency slots)

| Band | Hz | Do |
|---|---|---|
| Sub | < 60 | only kick/bass; high-pass everything else |
| Bass | 60-250 | bass body, kick thump; keep tidy |
| Mud | 250-500 | the usual problem: cut 2-4 dB on pads/chords/piano (we use -2 to -3 dB around 300-350 Hz) |
| Low-mid / body | 500-1000 | warmth of strings, winds, vocals; cut a little if "boxy" |
| Mids / presence | 1-4 k | where the lead lives and speech intelligibility sits; add +1-2 dB to the lead, cut 2-3 dB from accompaniment (and 3 dB from a music bed under speech) |
| Presence / bite | 4-7 k | attack of strings/guitar/hi-hats; too much = harsh |
| Air | 8-16 k | shimmer: gentle shelf +1-2 dB on lead/overall; low-pass pads ~9 kHz to stay dark |

Per instrument starting points (cut / boost): piano cut 300-400 / boost 3-5 k air; acoustic guitar cut 200-300 / boost 5-10 k sparkle; strings cut 250-400 / boost 3-6 k bow detail; flute cut < 250 (high-pass 250) / boost 3-5 k breath; kick boost 60-80 + 3-5 k click, cut 300-400; snare body 150-250, crack 3-5 k; bass body 60-100, definition 700-1000.

## 3. Loudness and delivery

| Target | Integrated LUFS | True peak | Source |
|---|---|---|---|
| Broadcast, EBU R 128 | -23 | -1 dBTP | EBU R 128 v5 (2023), +-0.2 LU in QC |
| Television, ATSC A/85 | -24 LKFS | -2 dBTP | ATSC A/85:2026-07, +-2 dB |
| Streaming music, AES TD1008 | -16 | -1 dBTP | AES TD1008 (2021); -14 for an album's loudest track |
| Spotify (platform policy, not a standard) | -14, normalised both ways | -1 dBTP; -2 dBTP when hotter than -14 LUFS | Spotify loudness documentation |
| Film / cinematic underscore | -18 to -16 (leave dynamics) | -1.5 dBTP | starting values |
| Music bed under speech (deliver stem) | about -20 to -18 | -2 dBTP | starting values |
| Podcast | -16 | -1 dBTP | starting values |

Apple Music and YouTube publish no music loudness target. The figures commonly quoted for them (-16 and -14) are
third-party measurements, not specifications, so they are not listed as rules. A mix preset can declare which
document it implements with `mastering.standard`; the gate then checks the declared numbers against it. Figures,
tolerances, versions and URLs are in [`delivery-standards.md`](delivery-standards.md).

Never exceed 0 dBFS; measure true peak with oversampling (mixer does). Keep the noise floor below -60 dB. Delivery
sample rate 44.1 kHz (music) or 48 kHz (video, matches picture), 24-bit WAV; export MP3 192-320 kbps only for sharing.
If the target LUFS cannot be reached without squashing a very dynamic piece, the master prints a note - a
natural 18-20 dB crest piece should be a little quieter, not crushed.

## 4. Music under voice-over (OpenMontage, W3C, BBC practice & Commercial Contract)

- **The Voice-Over First Contract:** the contract, its ducking depths and the persuasion rules live in
  [`knowledgebase/genre-and-feel/commercial-promo.md`](../../knowledgebase/genre-and-feel/commercial-promo.md); this section only says how to apply it.
- Voice: high-pass 80 Hz, cut ~500 Hz, boost 2-5 kHz, tame 6-8 kHz sibilance, compress 3:1 (1-5 ms attack, 10-20 ms release).
- Music peak 18-20 dB under the voice when speaking (W3C: 20 dB lower for accessibility; BBC: go a further 4 dB lower than looks right); duck 6-12 dB while speech is active (up to 22 for complex narration).
- Cut 2-4 kHz on the music bed. Use instrumental only. Avoid bright busy hi-hats under speech.
- Steady dynamics: no crescendos that rise over a sentence.
- Whoosh/SFX start 10-20 ms *before* the visual change, SFX 6+ dB under dialogue.
- Test on a phone speaker: if the voice disappears, cut more at 2-4 kHz on the bed and duck deeper.
Use `video-mixer/video_program_mix.py` - it does all of the above and prints how far under the voice the music sits (aim >= 15 dB).

## 5. Reverb, Space & Algorithmic Engines

For pure-Python algorithmic reverb synthesis models and topologies, see [`knowledgebase/genre-and-feel/commercial-promo.md`](../../knowledgebase/genre-and-feel/commercial-promo.md) Section 6.0:
- **Schroeder/Moorer Comb & All-Pass Networks:** Dense natural room diffusion.
- **The Shimmer Reverb Engine:** Granular octave-up pitch-shifted feedback loop ($+12\text{ semitones}$) for ethereal, celestial swells.
- **80s Phil Collins Gated Reverb:** High-energy non-linear cutoff at 220 ms.
- **Infinite Dune / Cathedral Reverb:** Formant-preserving multi-tap golden-ratio delay matrix (230ms, 372ms, 602ms, 974ms) bandpassed strictly to 350 Hz – 2.6 kHz.

| Room | RT60 | Use |
|---|---|---|
| studio / room_warm | 0.5-0.9 s | lo-fi, folk, close and intimate |
| chamber | 1.2 s | acoustic, chamber music |
| plate | 1.8 s | bright pop vocal-style sheen |
| hall | 2.3 s | piano, strings, default natural |
| large_hall | 3.2 s | cinematic |
| cathedral / cave | 5-6.5 s | ambient, dread; use with slow music |

Send levels: lead 0.2, pads 0.3, piano 0.18, drums 0.08, bass 0 (bass and kick stay dry). Longer reverb = slower tempo and
fewer notes, or it smears.

A send pre-delay keeps a part clear of its own tail. `space.predelay_ms_by_role` delays only the send, never the dry
path; 20-80 ms is the practitioner range for a vocal (iZotope, guidance rather than a measured optimum), and the
~30 ms precedence/Haas boundary is the perceptual reason it is audible (AES Convention Paper 10264, 2019).

**Space is a brief decision, not an afterthought.** `room` sets the impulse response; `mix.reverb_return` sets how
much wet signal returns (1.0 is neutral, 1.5 for a "reverb mix", 0.6 dry). `compose.py` sets both from the brief:
`space: large_hall`, or the words `reverb / wet / spacious / distant`, give a 3.2 s hall with a 1.5 return; `dry /
close / intimate` give the dry room. If a slow piece still smears, shorten the room before adding notes, and if a
"reverb mix" still sounds dry, raise the return before changing the room. A reverb tail over 4 s needs a tempo under
about 80 BPM and sparse layers; that is exactly why "slow reverb mix" reads as `dreamy` at 64 BPM and not as a fast
piece with a long tail.

## 6. Fix table (checker message -> action)

| naturalness_check says | Do this |
|---|---|
| clipped / true peak hot | lower `master.true_peak`, reduce loud stems' `gain_db`, avoid stacking many loud layers |
| loudness far from target | check `master.lufs`; a very dynamic piece may not reach it - accept |
| dynamics barely change | add/steepen the `dynamics` arc; layers with `min` thresholds; reduce compression |
| crest < 9 dB | the master is squashing: lower the LUFS target a little, remove stem compressors (`"chain":"none"` for one stem) |
| mud 250-500 Hz | `"eq":[{"type":"peak","f":320,"gain":-3,"q":1}]` on chords/pad/piano; high-pass pads higher |
| bright / harsh top | `"lp": 9000` on the offender; lower synth/lead level; avoid raw GM synth leads |
| too much sub | `"hp": 40` on non-bass stems; keep bass above MIDI 33 (A1) for small speakers |
| low end wide / mono loss | `"mono_below": 140` on the stem; reduce `"widen"` |
| stereo essentially mono | pan layers differently; raise `"widen"` on pads (0.4-0.7); use a bigger room |
| timing too grid-like | `humanize: "natural"` or `"loose"`; add `rubato` |
| timbre static | add vibrato/expression, layer a second instrument, vary articulation, change texture between sections |

## 7. Stem delivery

If the user will mix elsewhere: `render_natural.py score.json --stems-only --stems-dir stems/` writes one WAV per
track (pre-mix, normalised only by the instrument), and `compose.export_midi(score, "song.mid")` writes the MIDI.
Deliver: master WAV, instrumental/underscore version, stems, MIDI.

## 8. Ambient & Nature Fusion (The 5 Zero-Overlap Blending Laws)

The five zero-overlap laws, the weather and bio-acoustic models belong to
[`knowledgebase/sound-design/sfx-ambience.md`](../../knowledgebase/sound-design/sfx-ambience.md); this section only says how to
place the result in the mix.

1. **The Shared Acoustic Space Rule (Eliminating the Dry vs Wet Perception Gap)**:
   - *Why it sounds artificial:* If the instruments (guitar, flute, drums) sound like bone-dry studio recordings while nature sounds have wide outdoor reverberance, the brain immediately detects two separate unrelated audio files playing at the same time.
   - *The Solution:* Musical instruments and environmental soundscapes must inhabit the EXACT same shared acoustic space (`room` convolution / IR impulse response). When environmental tracks are present, acoustic guitars, flutes, strings, and percussion must send a cohesive portion (0.14–0.28) to the shared room reverb bus (`hall`, `large_hall`, `forest_canopy`). The environmental tracks themselves must also route a moderate send (0.18–0.24) to the shared bus so both music and nature blend into a single physical world.
2. **Dynamic Volume Staging & Macro-Automation**:
   - Nature sounds must act as a subtle background texture (-12 dB to -16 dB relative to lead instruments), never competing as lead elements.
   - *Intro/Outro Swelling:* Nature sounds should swell naturally (+3 to +4 dB) during musical intros (00:00–00:05) and outro decays, and duck automatically into the background as the rhythmic arrangement and drums kick in.
3. **Frequency Niche Allocation (Anti-Hiss & Unmasking)**:
   - *Water & Rain:* High-pass filter at 280–320 Hz to eliminate low-frequency mud and avoid clashing with kick/bass. Gentle low-pass shelf roll-off at 6.8–7.5 kHz to eliminate the constant white-noise hiss wall that blinds hi-hats, shakers, and guitar pick transients.
   - *Mid-Range Lead Scoop:* Ambient beds must scoop 1.5–3.5 kHz (around `LEAD_BAND_HZ`) by 3–5 dB, leaving an open acoustic pocket for the lead flute, solo strings, or vocals.
4. **Avian Syrinx Physical Modeling (Authentic Biological Calls)**:
   - *Why sines sound synthetic:* Simple FM sinusoidal sweeps sound like 8-bit video game beeps. Real birdsong is produced by syringeal labia oscillating in a non-linear limit cycle (Mindlin-Goller dynamics) coupled with dual bronchus biphonation (micro-detuned beating between two independent labial sources), dynamic tracheal/beak acoustic cavity formant tracking, and aerodynamic aspiration breath noise at onset.
5. **Dynamic Sidechain Ducking**:
   - Environmental beds must automatically duck by 2.5–4.5 dB whenever the rhythm section (kick, snare, cajón) or lead melody sounds, allowing the musical groove to breathe naturally without fighting a static noise wall.
6. **Mid-Side Staging**:
   - Keep the phantom center clear and grounded for kick, snare, bass, and lead flute. Distribute ambient beds across the stereo periphery ($W = 1.2\text{--}1.4$), wrapping the listener in an immersive 3D natural envelopment.

## 8b. What the engine can do now, and what is off by default

Every setting is a key in a mix preset: `references/data/presets/mix/default.json` ships it, a project's
`presets/mix/<name>.json` deep-merges over it, and `scripts/mix_schema.py` holds the default value and the
rule for every key. `python scripts/presets.py validate` now checks a mix preset too: an unknown key, a
number out of range, a malformed EQ band, an unknown spectral profile or a bad mastering profile is
reported with its path.

`scripts/mix_context.py` resolves a piece's configuration once (`mix_context.resolve(score)`), so mixing
two pieces in one process cannot leak one into the other. The context is per thread, and `render.mix_workers`
processes several stems at once with the same samples as one after another.

| Section | Keys | Default |
|---|---|---|
| `gain_staging` | `strategy` (`legacy`/`adaptive`), `ref_lufs`, `ref_by_role`, `max_boost_db`, `max_cut_db`, `block_s`, `active_db`, `peak_headroom_db`, `crest_preserve_db`, `sparse_active_frac` | `legacy`: the old `min(ref - active_lufs, max_boost_db)`. `adaptive` adds a per-role reference, a cut limit, a peak-headroom cap and a crest guard, so a delicate layer, a percussion stem and a field recording keep their own dynamics |
| `dynamics` | `engine` (`pedalboard`/`dsp`), `knee_db`, `detector`, `stereo_link`, `lookahead_ms`, `makeup_db`, `parallel`, `multiband`, `dynamic_eq`, `transient`, `sidechain_hp_hz`, `sidechain_lp_hz` | `pedalboard`: the four-knob compressor (thr, ratio, attack, release). Every other key here is **inert** under it: the mixer prints a `[WARN] mix.dynamics.<key> ... has no effect` line when a preset sets one (`mix_schema.inert_dynamics`), so set `engine` to `dsp` or drop the key. `dsp` reaches `scripts/dsp.py`: soft knee, RMS or peak detector, filtered sidechain, lookahead, parallel (NY) compression, multiband and dynamic EQ |
| `spectral` | `profiles`, `preserve_spectrum_roles`, `mid_bands`, `side_bands`, `max_auto_cut_db` | The role chain. A track with `"spectral_profile": "rain"` (or `wind`, `water`, `foliage`, `insect`, `voice`, `strings`, `flute`, `bed`) no longer shares the one universal environment chain. `"preserve_spectrum": true` bypasses the automatic chain for a physically modelled source |
| `space` | `auto_env_blend`, `drr`, `er`, `cache_ir`, `tail_guard_db` | The shared-room blend when ambience is present (`auto_env_blend.enabled`), the old early-reflection construction, and a cached IR |
| `sidechain` | `mode` (`legacy`/`explicit`/`off`), `band_hz`, `residual`, `threshold`, `attack_ms`, `release_ms`, `env_plateau` | `legacy`: a bed is ducked under the first drum track, band-limited, with the plateau lock. `explicit` ducks only what a track's `duck_by` asks for; `off` ducks nothing |
| `lead_carve` | `enabled`, `source`, `bands_hz`, `ratio`, `threshold_db`, `attack_ms`, `release_ms`, `roles`, `skip_ducked` | Off. When on, each listed bed's band is a **dynamic** EQ keyed by the band-passed lead, so the bed keeps its body in the rests and yields only where the two collide. `carve_db` (the fixed dip `carve_for_lead` takes from the score) still applies and is the floor this adds to; a role already moved by its own `duck_by` is skipped, so nothing is ducked twice. Use it when the static carve is audible as a permanently dull bed |
| `automation` | `curve` (`linear`/`cosine`/`exponential`), `phrase_boundaries` | linear, the fades this engine always used |
| `mastering` | `profile`, `profiles`, `lra_target_lu`, `crest_floor_db`, `validate_export`, `report` | `default` (-14 LUFS, -1.5 dBTP). A score's own `master` block still wins over the profile |
| `role_chains` | one entry per role: `eq` bands and `comp` | The starting chains this engine shipped with, now editable from JSON instead of living in code. `scaffold mix` and `setup_project.py` write all of them out (every role, plus `spectral.profiles` for rain, water, wind, foliage, insect, voice, strings, flute and the legacy `bed`), so a project starts from a complete, visible, editable set rather than from names it has to guess |

A track may also carry `"dynamics": {...}` (its own knee, detector, multiband, dynamic EQ, transient
shape), `"spectral_profile"`, `"preserve_spectrum"`, `"ref_lufs"`, `"pan_law": "energy"` and
`"sidechain": {...}`. All of them are optional: a preset that sets none of them renders exactly as it did
before these keys existed.

**Diagnostics.** `scripts/mix_diagnostics.py` measures the mix that was played (post-EQ, post-pan) and
reports `FAIL` / `WARN` / `INFO` rows for loudness imbalance, spectral overlap, low-end congestion,
transient masking, phase and mono fold-down, over-compression, reverb buildup, mud, harshness,
intelligibility, true peak, clipping, headroom and LRA. It never changes the mix. Run it with
`python scripts/mixer.py stems/ --mix mix.json --out out.wav --diagnose`, or from code with
`mix_and_master(..., diagnose=True)` and `mixer.STATE['diagnostics']`. The rows are measurements with the
stems and the bands named; a `WARN` is a question, not a verdict.

The pipeline runs them on every render: stage 5 calls `mix_and_master(..., diagnose=True)` and stage 6 appends
them to `reports/ci_report.json` as `mix:<row>`. There a diagnostic `FAIL` is printed as `WARN`, because the
gate's own rows (true peak, clipping, silence) own the blocking verdicts and the diagnostics are advisory by
contract. Stage 6 is one call to `quality_gate.run_gate(..., score=<the score it rendered>)`, so the
pipeline and `quality_gate.py <score>` produce the same rows and cannot drift apart.

**Sympathetic resonance** (`sympathetic_resonance`, off by default). Strings that are never played but ring with
the music: sitar taraf, sarangi, a piano with the pedal down. A bank of resonators is tuned once for the piece and fed
by the mixed stems of `sources` (track names or roles; empty means everything except drums and places).

| Key | Meaning |
|---|---|
| `tuning` | `"score_scale"`: the `strings` most-used pitch classes of the source tracks, placed upward from `low_hz`. Or a list of Hz |
| `partials` | each string also rings at this many harmonics |
| `q` | a string at f rings for q / (pi f) seconds |
| `level_db` | the bed against the level of what excites it |
| `width` | stereo widening of the bed, 0 to 1 |
| `spatial` | where the bed sits on the ambisonic bus; empty leaves it unplaced |

The tuning does not follow the chords: real sympathetic strings are tuned to the scale and left alone.

**Brightness that follows level** (`dynamic_tilt` on a track or an instrument preset). A SoundFont stem always gets
it; an SFZ stem gets it when the block is present, for a library with a single velocity layer:
`{"low_hz": 1500, "span_hz": 2600, "floor": 0.55, "curve": 1.2}`. The corner is `low_hz` plus `span_hz` times the mean
velocity; `floor` is how much of the full band a silent moment keeps. An unknown key is an error.

**The theatrical stage** (`theatrical`, off by default) is the programme-side realism decision: a dynamic dip in
180-420 Hz while that band is loud (`low_mid`), a capped 9 kHz lift that scales with the mastered programme level
(`air`), and a shared-send dip that lasts only through an attack (`detail`). It is stereo-only; a discrete
multichannel master keeps its own stage. It is not a substitute for the piece's own dynamics: the coupling of
timbre to loudness, section scatter and bar-scale breathing are decided on the track and in the score. Rules:
`references/mixing/theatrical-realism.md`; facts: `knowledgebase/sound-design/theatrical-realism.md`.

**Numbers that live in the mix preset, not in the mixer.**

| Section | Keys | What they are |
|---|---|---|
| `mastering` | `highpass_hz`, `tones` (name -> EQ bands), `glue` (`threshold_db`, `ratio`, `attack_ms`, `release_ms`), `converge` (`max_iterations`, `tolerance_lu`, `step`, `report_miss_lu`), `fallback_limiter`, `min_crest_db` | the master chain itself. A master block or a profile picks a tone by name; a project adds its own tone by listing its bands. A tone that is not listed masters neutral and says so on stderr |
| `space` | `send_by_role`, `ir` (`bands`, `length_factor`, `length_pad_s`, `onset_s`), `er` (`taps`, `first_gain`, `tap_decay`, `window_s`), `return` (`highpass_hz`, `lowpass_hz`), `auto_env_blend.floors` | the room send each role starts with, the synthesised tail and its early reflections, the band the reverb returns in. `send_by_role.default` is every role; a role listed beside it gets its own send, and a track's `reverb` still wins |
| `sidechain` | `band_roles`, `default_duck_db`, `legacy_env_duck_db`, `lookahead_ms`, `timing` (`default`, `environment`), `plateau_percentile`, `plateau_fade_max_s`, `plateau_fade_frac` | which roles duck only in the lead's band, and the follower times when neither the track nor the per-role maps name one |
| `lead_carve` | `from_intent` | with `enabled`, take the source from the score's `mix_intent.hero` and the band from `mix_intent.leave_free_hz`; `mixer.STATE['mix_intent_used']` records what was taken |
| `render` | `compute` (`device`, `workers`), `mix_workers`, `mix_worker_mb_per_second` | where the array work runs and how many stems are processed at once. `mix_workers: "auto"` is one per core, then **capped by free memory**: `mix_worker_mb_per_second` (starting value 2.0) is the measured working set of one stem per second of audio, so a 16 GB machine fits about a dozen 3-minute stems at once rather than one per core. The cap only lowers the count and prints when it does; `docs/mix_memory_profile.md` has the measurements (`references/spatial/immersive-spatial.md`, section 2e) |

A project scaffolded with `presets.py scaffold mix` lists a starting `send_by_role` (a dry bass, a wet pad). The schema
default lists only `default`, so a piece with no such table sends every role alike.

**Export validation.** `mix_and_master` re-reads the file it wrote and checks sample rate, channels,
length, sample peak, oversampled true peak and full-scale samples, in `mixer.STATE['export']`. A problem
is printed; the render is not silently accepted.

**Benchmarks.** `python scripts/mix_bench.py` times a synthetic arrangement;
`python scripts/mix_bench.py --compare` prints the same stems mixed legacy and adaptive, with loudness,
crest, mono fold and correlation side by side. That is a measurement. It is not a listening test, and no
row in that table by itself proves the mix sounds better.

**The processed-stem cache.** `<project>/.cache/mix/` keeps each stem's chain output — gain staging, EQ, dynamics,
level, automation, fades — keyed on that stem's bytes, its resolved spec, the whole mix preset, the sample rate,
the compute device and the engine's own code hash (every module of `mix_engine/` is hashed). Two things follow from one split in the engine: a retry
after a one-note fix re-processes only the stems that changed, and a second output format reuses the first one's
chain, because `process_chain` is independent of the bus while `_place` (width, pan, the head filter, the bus
hand-over) is not. Placement therefore always runs per mix. Delete the folder to force a rebuild;
`mixer.use_mix_cache(None)` turns it off, and the run's hit count is in `reports/ci_report.json` under
`gate.cache`. A cached stem is the same float32 samples a fresh one would be — that is what
`tests/test_mix_cache.py` asserts, including across two different buses.

**The 3-D mix.** `python scripts/helpers/bench_mix.py` times `HoaBus.field()` — the ambisonic mix a piece on
`immersive.engine: "hoa_bus"` runs — and prints the reflections, the encoder and the late field as shares of it,
from a space preset's own room (`--space`, `--seconds`, `--sources`, `--profile`). `docs/mix_profile_palace.md` is
the same measurement on a real 180 s render: 64 % of the run was the mix, and 715 s of that was the reflection
loop. Change that loop only with this bench before and after, and with `tests/test_immersive_v2.py` green: it
pins every tap's delay, level and spectrum against the per-tap loop the faster path replaced.

## 9. Spotify Pedalboard DSP Architecture & Broadcast Mastering

The mixing engine ([`scripts/mixer.py`](../../scripts/mixer.py)) uses Spotify's **Pedalboard** library for stem filtering, dynamics and master limiting:

1. **ITU-R BS.1770 Broadcast Mastering via `pb.BrickwallLimiter`**:
   - Enforces a precise true-peak ceiling (e.g. `-1.5 dBTP`) using lookahead delay lines and exponential release envelopes without unwanted makeup gain or hard-clipping distortion.
   - Enables 4x oversampled sidechain analysis (`true_peak=True`) to detect and eliminate inter-sample peaks prior to DAC conversion.
2. **Gated Reverb via `pb.NoiseGate`**:
   - For 80s drums, snare bursts, and modern synthwave: chains `pb.Convolution` (or `pb.Reverb`) into `pb.NoiseGate(threshold_db=-32.0, release_ms=80.0)`, cleanly cutting reverb tails on rhythmic boundaries.
3. **Parallel Processing via `pb.Mix`**:
   - Combines dry stem transients with heavily compressed/saturated wet paths (New York drum compression: `pb.Compressor(threshold_db=-30, ratio=8.0, attack_ms=5)`) for punchy drums and fat bass without destroying dynamic range.
4. **Data Contract**:
   - Pedalboard processes NumPy float32 arrays in `(channels, samples)` shape (`[2, N]`). Scripts automatically handle transposition between Scipy/Soundfile format (`[N, 2]`) and Pedalboard format.


### 8c. Where the EQ comes from, and how many times it runs (traced in `mix_engine/chains.py`)
- A stem gets **one** spectral chain: its `spectral_profile` if it names one, else its role chain (`mixer.spectral_chain`). They never run together.
- An environment preset's own `blending` (high-pass and the vocal-pocket notch, applied in `environment.py`) runs **before** that, inside the environment render. So an ambience stem can hold two notches near 2.2-2.4 kHz: keep the blending notch or the chain's, or move one by a third of an octave.
- A `spectral_profile` belongs to the **stem**, and an environment preset's layers are summed into one stem. A bright layer (insects above 7.2 kHz) therefore shares the stem's chain; give the preset a profile that keeps that band, or set `preserve_spectrum` on the track.
- A project mix preset lists only what differs from the schema. `mix_schema.redundant_chains(mix)` names role chains and profiles that repeat the shipped values; such copies stop following later tuning of the defaults. The scaffold writes every key on purpose (so each is visible); trim the ones you did not change before you rely on a default.

## Section levels (`mastering.section_levels`)

`{"range_db": 10.0, "ramp_s": 1.5}` applies a gain curve from the plan's section `energy` before the limiter loop: range_db between energy 0 and 1, centred
on the duration-weighted mean, ramped at the edges. The loudness target still lands (the converge loop re-levels), so the loud sections stand above the
quiet ones without a louder cue. Off by default. It collides with nothing protected, but check `master.dc`, `dropout` and `fold.timbre` after turning it on.


## 11. The master's low end (high-pass, theatrical tone, virtual bass)

- `mastering.highpass_hz` is the master high-pass and `highpass_order` the number of cascaded first-order stages (6 dB/octave each). The shipped
  default is 24 Hz, order 1. A high-pass at 105 Hz, order 4 (written into one preset script and copied from project to project) removed the
  whole sub and bass of a chase cue: the stems held 22 dB more of 20-80 Hz than the master. `preflight.master_highpass` fails a pitched bass or
  drone part the high-pass takes down by 6 dB or more on 30 % of its notes, and warns above 45 Hz; both numbers are in `constants.json`.
- `mastering.tones.theatrical` is a low shelf (+3 dB at 70 Hz) and a high shelf (+1 dB at 9 kHz); a master picks it with `master.tone`.
- `mastering.virtual_bass` adds harmonics of the 30-90 Hz band at 80-240 Hz, scaled to the sub's own level, so bass is heard on headphones
  and small speakers. It is off unless the preset enables it. Equations and sources: `knowledgebase/sound-design/low-end-and-virtual-bass.md`.

## 12. Where the mixer's numbers live

The shipped defaults are `references/data/mix_defaults.json` (gain staging, dynamics, spectral profiles, space, sidechain, the master chain,
role chains; each section has a provenance line, the loudness profiles are `references/data/master_targets.json`). `scripts/mix_schema.py`
keeps the ranges, the enums and `validate()`. A piece's mix is the project's own preset (`presets.py scaffold mix <name> --project <dir>`): it
lists only what the piece changes, a key it leaves out is the default, and `project_gate` requires the preset to be the project's, not the
shipped one, and described. `presets.py show mix default` prints every key with its shipped value; `scaffold mix --full` writes them all out.

## 13. Mixing techniques as effects (parallel compression, de-essing, gates, saturation, width, delays, resonators)

The mix preset has two effect chains next to the EQ and dynamics. They use the fx engine (`references/sound-design/fx-engine.md`), so every number
has a range and a sentence in `references/data/presets/fx/effects.json` and an unknown effect, key or out-of-range value is a `mix_schema.validate`
problem naming it.

- `"fx": {"*": chain, "@drum": chain, "qf_snare": chain}` in the mix preset: a chain run on a stem after its EQ and dynamics and after the instrument
  preset's own `fx`. `*` is every stem, `@<role>` a role, anything else an instrument name (or one of its base names). All that match run, in that order.
- `"mastering": {"fx": [ ... ]}`: a chain on the summed master, after the tone curve, the glue compressor and the width, before the rest dip, the
  virtual bass and the limiter. Empty by default, so an older master is unchanged.

The effects: `saturator` (tube, tape, soft_clip, hard_clip, fold, diode), `de_esser`, `gate`, `parallel_comp`, `upward_comp`, `band_width`, `tilt_eq`,
`freq_shift`, `resonator_bank`, `ping_delay`; eleven shipped chain presets (`mix_vocal_air`, `mix_new_york_drums`, `mix_tape_glue`,
`mix_mono_low_wide_top`, `mix_ducked_echo`, `mix_key_air`, `mix_tight_gate`, `mix_lift_tails`, `mix_inharmonic_pad`, `mix_fold_grit`, `mix_pulse_dark`)
are starting points to name in a chain. Which to use for which problem:

| Problem | Technique | Not |
|---|---|---|
| A sampled drum is thin and the hits are fine | `parallel_comp` at `mix` 0.3-0.5, `hp_hz` 120-200 | a compressor on the whole part (it flattens the hits) |
| A sparse part's tails and quiet notes disappear | `upward_comp`, `max_gain_db` 6-12 | raising the part's `gain_db` (the peaks go too) |
| A voice or a bright sample is harsh at 4-8 kHz | `de_esser`, then `tilt_eq` or a shelf | an EQ notch over the whole part |
| The room between notes (sample hiss, a reverb tail, a ring) fills the gaps | `gate` with a hold, `sidechain_hp_hz` 80+ | a fade (it takes the notes too) |
| A bed or pad is flat | `saturator` tape or tube at `mix` 0.3-0.6, `freq_shift` 2-4 Hz with `spread` 1, a `resonator_bank` on the key | an EQ boost |
| The low end is wide and fights the mono fold | `band_width` `mono_below_hz` 120-200, `width` 1.2-1.5 above | narrowing the whole part |
| An echo that must not cover the part | `ping_delay` with `duck_db` 8-12 | a send at a fixed level |

Rules: a technique can move a stem's level (the gain staging ran before it), so read the balance and loudness rows after adding one and lower the
effect's `mix` instead of loosening a row; only add one a measured row or a written intent asks for. Research and sources:
`knowledgebase/sound-design/mixing-techniques.md`. Tests: `tests/test_mixfx.py`. Nothing here has been listened to.

