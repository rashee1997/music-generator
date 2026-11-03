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

| Target | Integrated LUFS | True peak |
|---|---|---|
| YouTube / YouTube Shorts | -14 | -1.5 dBTP |
| TikTok / Instagram Reels | -14 | -1 dBTP (check on a phone speaker; push 2-4 kHz) |
| Spotify / streaming | -14 | -2 dBTP |
| Podcasts (Apple) | -16 | -1 dBTP |
| Film / cinematic underscore | -18 to -16 (leave dynamics) | -1.5 dBTP |
| Broadcast (EBU R128) | -23 | -1 dBTP |
| Music bed under speech (deliver stem) | about -20 to -18 | -2 dBTP |

Never exceed 0 dBFS; measure true peak with oversampling (mixer does). Keep the noise floor below -60 dB. Delivery
sample rate 44.1 kHz (music) or 48 kHz (video, matches picture), 24-bit WAV; export MP3 192-320 kbps only for sharing.
If the target LUFS cannot be reached without squashing a very dynamic piece, the master prints a note - a
natural 18-20 dB crest piece should simply be a little quieter, not crushed.

## 4. Music under voice-over (OpenMontage, W3C, BBC practice & Commercial Contract)

- **The Voice-Over First Contract:** In commercials, explainers, and corporate media, speech intelligibility is sacred. Consult [`knowledgebase/COMMERCIAL_CORPORATE_PROMO.md`](file:///D:/Vasima/.agents/skills/music-generator/knowledgebase/COMMERCIAL_CORPORATE_PROMO.md) for complete mathematical ducking curves and commercial persuasion psychoacoustics:
  - Apply a static -4 to -6 dB bell notch filter ($Q = 1.2$) centered at 1,800 Hz across all chordal/pad beds (pianos, electric guitars, synth pads).
  - Dynamically duck the music bed by -8 to -14 dB whenever vocal activity is detected (25 ms attack, 250–350 ms release).
- Voice: high-pass 80 Hz, cut ~500 Hz, boost 2-5 kHz, tame 6-8 kHz sibilance, compress 3:1 (1-5 ms attack, 10-20 ms release).
- Music peak 18-20 dB under the voice when speaking (W3C: 20 dB lower for accessibility; BBC: go a further 4 dB lower than looks right); duck 6-12 dB while speech is active (up to 22 for complex narration).
- Cut 2-4 kHz on the music bed. Use instrumental only. Avoid bright busy hi-hats under speech.
- Steady dynamics: no crescendos that rise over a sentence.
- Whoosh/SFX start 10-20 ms *before* the visual change, SFX 6+ dB under dialogue.
- Test on a phone speaker: if the voice disappears, cut more at 2-4 kHz on the bed and duck deeper.
Use `video-mixer/video_program_mix.py` - it does all of the above and prints how far under the voice the music sits (aim >= 15 dB).

## 5. Reverb, Space & Algorithmic Engines

For pure-Python algorithmic reverb synthesis models and topologies, see [`knowledgebase/COMMERCIAL_CORPORATE_PROMO.md`](file:///D:/Vasima/.agents/skills/music-generator/knowledgebase/COMMERCIAL_CORPORATE_PROMO.md) Section 6.0:
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

For mathematical derivations, weather physics (mist, monsoon, ocean surf, desert simoom, fire, thunder), and bio-acoustics (avian syrinx FM synthesis), see [`knowledgebase/PROCEDURAL_SFX_AMBIENCE.md`](file:///D:/Vasima/.agents/skills/music-generator/knowledgebase/PROCEDURAL_SFX_AMBIENCE.md). Enforce the **5 Laws of Zero-Overlap Blending**:
1. **Dynamic Spectral Notching:** 4th-order Butterworth high-pass at 140 Hz (sub-bass protection) + -8 to -14 dB notch on ambient beds at the lead instrument's instantaneous $f_0(t)$ and $2f_0(t)$.
2. **Temporal Call-and-Response Gating:** Discrete SFX (birds, drops, whistles) trigger with inverse-envelope probability $P \propto (1 - M_{env})^2$ during musical pauses.
3. **Key-Locked Harmonic Resonators ("Singing Ambience"):** Pass 25–40% of raw wind/rain/surf noise through a parallel bank of high-Q resonators ($Q = 25–45$) tuned to the song's root, 5th, and mode so nature naturally hums in key.
4. **3D Spherical Mid-Side & Haas Separation:** Mid channel attenuated -6 dB, Side boosted +3 dB with 7–13 ms Haas delay so ambience forms a 360° dome around the listener, leaving the center clear for drums, bass, and lead.
5. **Rhythmic Quantization of Micro-Foley:** Snap 75% of nature/foley transients to within $\pm 15\text{ ms}$ of the 16th/12th rhythmic grid.

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

Every setting is a key in a mix preset: `references/presets/mix/default.json` ships it, a project's
`presets/mix/<name>.json` deep-merges over it, and `scripts/mix_schema.py` holds the default value and the
rule for every key. `python scripts/presets.py validate` now checks a mix preset too: an unknown key, a
number out of range, a malformed EQ band, an unknown spectral profile or a bad mastering profile is
reported with its path.

`scripts/mix_context.py` resolves a piece's configuration once (`mix_context.resolve(score)`), so mixing
two pieces in one process cannot leak one into the other. The engine is single-threaded by design; it was
already, and still is.

| Section | Keys | Default |
|---|---|---|
| `gain_staging` | `strategy` (`legacy`/`adaptive`), `ref_lufs`, `ref_by_role`, `max_boost_db`, `max_cut_db`, `block_s`, `active_db`, `peak_headroom_db`, `crest_preserve_db`, `sparse_active_frac` | `legacy`: the old `min(ref - active_lufs, max_boost_db)`. `adaptive` adds a per-role reference, a cut limit, a peak-headroom cap and a crest guard, so a delicate layer, a percussion stem and a field recording keep their own dynamics |
| `dynamics` | `engine` (`pedalboard`/`dsp`), `knee_db`, `detector`, `stereo_link`, `lookahead_ms`, `makeup_db`, `parallel`, `multiband`, `dynamic_eq`, `transient`, `sidechain_hp_hz`, `sidechain_lp_hz` | `pedalboard`: the four-knob compressor. `dsp` reaches `scripts/dsp.py`: soft knee, RMS or peak detector, filtered sidechain, lookahead, parallel (NY) compression, multiband and dynamic EQ |
| `spectral` | `profiles`, `preserve_spectrum_roles`, `mid_bands`, `side_bands`, `max_auto_cut_db` | The role chain. A track with `"spectral_profile": "rain"` (or `wind`, `water`, `foliage`, `insect`, `voice`, `strings`, `flute`, `bed`) no longer shares the one universal environment chain. `"preserve_spectrum": true` bypasses the automatic chain for a physically modelled source |
| `space` | `auto_env_blend`, `drr`, `er`, `cache_ir`, `tail_guard_db` | The shared-room blend when ambience is present (`auto_env_blend.enabled`), the old early-reflection construction, and a cached IR |
| `sidechain` | `mode` (`legacy`/`explicit`/`off`), `band_hz`, `residual`, `threshold`, `attack_ms`, `release_ms`, `env_plateau` | `legacy`: a bed is ducked under the first drum track, band-limited, with the plateau lock. `explicit` ducks only what a track's `duck_by` asks for; `off` ducks nothing |
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
contract. Stage 6 is one call to `quality_gate.run_gate(..., score=<the score it just rendered>)`, so the
pipeline and `quality_gate.py <score>` produce the same rows and cannot drift apart.

**Export validation.** `mix_and_master` re-reads the file it wrote and checks sample rate, channels,
length, sample peak, oversampled true peak and full-scale samples, in `mixer.STATE['export']`. A problem
is printed; the render is not silently accepted.

**Benchmarks.** `python scripts/mix_bench.py` times a synthetic arrangement;
`python scripts/mix_bench.py --compare` prints the same stems mixed legacy and adaptive, with loudness,
crest, mono fold and correlation side by side. That is a measurement. It is not a listening test, and no
row in that table by itself proves the mix sounds better.

## 9. Spotify Pedalboard DSP Architecture & Broadcast Mastering

The mixing engine ([`scripts/mixer.py`](file:///D:/Vasima/.agents/skills/music-generator/scripts/mixer.py)) uses Spotify's **Pedalboard** C++ library (built on JUCE with GIL release) for SIMD-accelerated stem filtering, dynamics, and master limiting:

1. **ITU-R BS.1770 Broadcast Mastering via `pb.BrickwallLimiter`**:
   - Enforces a precise true-peak ceiling (e.g. `-1.5 dBTP`) using lookahead delay lines and exponential release envelopes without unwanted makeup gain or hard-clipping distortion.
   - Enables 4x oversampled sidechain analysis (`true_peak=True`) to detect and eliminate inter-sample peaks prior to DAC conversion.
2. **Gated Reverb via `pb.NoiseGate`**:
   - For 80s drums, snare bursts, and modern synthwave: chains `pb.Convolution` (or `pb.Reverb`) into `pb.NoiseGate(threshold_db=-32.0, release_ms=80.0)`, cleanly cutting reverb tails on rhythmic boundaries.
3. **Parallel Processing via `pb.Mix`**:
   - Combines dry stem transients with heavily compressed/saturated wet paths (New York drum compression: `pb.Compressor(threshold_db=-30, ratio=8.0, attack_ms=5)`) for punchy drums and fat bass without destroying dynamic range.
4. **Data Contract**:
   - Pedalboard processes NumPy float32 arrays in `(channels, samples)` shape (`[2, N]`). Scripts automatically handle transposition between Scipy/Soundfile format (`[N, 2]`) and Pedalboard format.

Sources: OpenMontage `skills/creative/sound-design.md` and `tools/audio/audio_mixer.py` (loudnorm/limiter, sidechain
ducking); Lemo `styles/*/demo/mix.py` (voice-over ducking -9.5 dB, brightness lift for dark scores); Mindlin & Goller (2001) / Laje et al. (2002) physical models of avian vocalization; standard
mixing EQ charts; ITU-R BS.1770 / EBU R128 loudness; platform loudness specs (YouTube, Spotify, Apple, TikTok); Spotify Pedalboard Audio Intelligence Lab.
