# Sound effects: how they are made in code, and when a small model is used

Used by `scripts/sfx.py`: 21 one-hit effect recipes with a shipped default preset each (`references/presets/sfx/`), plus 7 older ambience recipes
(rain, wind, ocean, fire, crickets, birdsong, electric_hum) kept only so old scores render (`python3 scripts/sfx.py list`), a `make` command,
and `timeline()`, which lays effects on a stereo bed to sit under music or a video.

`sfx.py` is the facade; `scripts/sfx_engine/oneshot.py` owns the dispatch (scene → model → spec → generator) and
`scripts/phys_core/` owns the physics. `make()` exists once, so the same preset returns the same bytes whichever entry
point a caller uses; the facade only keeps the older return contract (`'preset'` where the engine says `'model'`).

For advanced physical modeling of weather (mist, monsoon, ocean surf, desert wind, campfire, thunder shockwaves), bio-acoustics (avian syrinx dual-FM synthesis), and the **5 Zero-Overlap Blending Laws** (Key-Locked Harmonic Resonators, 3D Mid-Side geometry, and micro-foley quantization), consult:  
👉 [`knowledgebase/PROCEDURAL_SFX_AMBIENCE.md`](../knowledgebase/PROCEDURAL_SFX_AMBIENCE.md).

---

## 1. What the research says

- **Procedural audio is sound made at run time from parameters** (the GDC procedural-audio talk by Fournel: real-time
  synthesis with exposed controls; the Splice overview). A generator with a seed and named parameters is the same
  idea: the same call gives the same effect, and a parameter changes it (for example rain density or door speed).
- **Impacts are layers**: a low body for weight, a short noise transient for the attack, and a tail. The Crackdown
  impact work (Bernhard, Lloyd and colleagues, interactive impact synthesis from a recorded hit) and the sound-design
  practice from the search results both layer low to high. The `impact`, `boom`, `hit` and `explosion` generators use
  this order.
- **Whooshes and risers are filtered noise with a moving filter and a moving level.** The tutorials agree: a band-pass
  whose centre sweeps, with a swell that peaks near the end of the move. `whoosh` and `sword_swing` sweep a band-pass;
  `riser` rises in pitch and brightness; `downlifter` falls.
- **Textures are many small events.** Rain is a bed of filtered noise with random drops; fire is a rumble with
  random crackles; typewriter and water drip are event lists placed at random times. These use seeded random positions
  so the result is repeatable.
- **Tonal events are short.** UI blips, coins, clock ticks and drips are sine sweeps with fast envelopes.
- Sources were search results plus two fetched pages (the GDC slides and an overview). The GDC page returned
  its text, the others did not; this file says so where a claim rests on a snippet.

## 2. The generators

| Family | Names |
|---|---|
| Motion | whoosh, riser, downlifter, sword_swing |
| Impact | impact, boom, hit, explosion, gunshot, thunder, heartbeat |
| Ambience (older fixed recipes; in a project use an `env:` preset instead, section 6) | rain, wind, ocean, fire, crickets, birdsong, electric_hum |
| Foley and objects | footstep (wood or gravel), door_creak, glass_break, water_drip, typewriter, shutter |
| Interface and game | ui_blip, coin, laser, clock_tick |

Each returns a mono float array at 44.1 kHz, peak about 0.9. The self-test checks that every effect is finite, has the
right length, is not silent, and is the same for the same seed.

## 2b. One-hit effects are presets

`sfx:<name>` looks up `presets/sfx/<name>.json` in the project first, then the skill's neutral default. A preset has `character` (one real sentence),
and says what the sound is in one of four ways, newest first: `"scene"` (physical scene, section 2d), `"model"` (a voice stack,
section 2c), `"generator"` (+ `params`, the keys that recipe takes) or a `spec` of layers (`noise`, `glide`, `tone`, `click`; see the top of
`sfx.py`). It also carries `sources` (the research slugs it rests on). An unknown key is an error, never ignored. Start from a default:
`presets.py scaffold sfx impact_heavy --from impact --project <dir>`; `sfx.py make impact_heavy --project <dir>`.
The project gate requires `sources` only for presets the project owns; the shipped defaults are neutral and need none.

## 2c. The sound model: any sound as data

For a sound the recipes and the four layer kinds do not cover, write a `model` (`scripts/sound_model.py`; `python scripts/sound_model.py laws` lists every part).
A sound is a stack of voices, each `excite -> resonator -> events`:

| Part | Choices |
|---|---|
| excite | `impact` (1 - cos pulse, `tau` = contact time), `noise` (white, pink, brown, band, burst envelope), `friction` (fractal noise, `beta`, speed curve, stick-slip), `periodic` (pulse train, glide, jitter), `burst` |
| resonator | `modal` (damped sinusoids; laws string, tube_closed, bar, membrane, power, or your own ratios; `t60`, damping slope), `bandpass`, `formant`, `bubble` (Minnaert, f = 3.26 / r), `none` |
| events | `single`, `periodic`, `poisson`, `gamma`, `cluster`, `bounce` (restitution), `sequence`, `continuous` |
| vary | `size` (lognormal, exp, marshall_palmer), `pitch_exp`, `amp_exp`, `level_spread_db` |
| control | `gain_db`: curve, lfo, ou (random walk), env; `pitch`: curve (continuous periodic voices) |

Use it as a one-hit effect (`presets/sfx/<name>.json` with `"model"`) or as ambience (an environments layer `{"primitive": "model_layer", "voices": [...]}`).
Fifteen worked models are in `references/sound-models/` (door creak, glass break, bouncing ball, gravel footstep, clock tick, tin-roof rain, leaf rain,
wind in trees, ocean wave, fire crackle, frog chorus, crowd murmur, car pass, thunder, boiling water): starting values, not answers. Their formulas and where
each comes from: `knowledgebase/SFX_MODEL_FORMULAS.md`. Unknown keys, out-of-range values and models that would take too long to render are errors.

To match a real recording: `ambience_reference.py measure <wav> --slug <slug> --project <dir> [--modes N]` stores spectrum, bands, texture statistics
(reduced McDermott-Simoncelli set) and, for a struck object, its resonances. Write `"free": {"voices.0.resonator.f1": [min, max], ...}` in the model, then
`sound_fit.py fit <preset.json> <slug> --project <dir>` writes `<name>_fit.json` with the distance before and after. It never edits the original, and with
one recording it says it is a weak anchor.

## 2d. The physical scene: the route for anything new

`"scene"` is now the way to build a sound, and `generator`/`model`/`spec` are the older shapes that still render. A scene
describes the physics, not the effect:

| Part | What it holds |
|---|---|
| `materials` | density, stiffness, loss factor, thickness, toughness, flow resistivity, restitution, roughness, `grain_size_m`, family (brittle/fibrous/granular/membrane/absorbent/metal) |
| `objects` | one material + one geometry (bar, plate, tube, string, membrane, leaf) + `modes`; `f1_hz` overrides the estimate |
| `timeline` | interactions (`impact`, `repeated_impact`, `friction`, `stick_slip`, `rolling`, `flow`, `granular`, `creak`, `fracture`, `gait`, `foliage`) with a `then` edge for dependent stages |
| `calibration` | `normalize` (`energy` default, `none`, `peak`, `rms`) and `level_db` - a declared choice, never silent |
| `propagation` | one law: 1/r, ISO 9613-1 air, canopy loss, one ground reflection |

```bash
python scripts/physical.py template --out scene.json   # a worked branch break
python scripts/physical.py check site.json             # every problem, render nothing
python scripts/physical.py render site.json --out x.wav
python scripts/physical.py verify                      # 40 frozen renders: nothing moved
```

There is no name-to-sound table: an unknown interaction, material or key is an error that lists what is valid. Two
materials on one object are two different sounds (a glass knock rings and is bright, an oak one is dull and short),
and a grain size turns gravel into sand. Details: `references/physical-scene.md`. Formulas and their read-status:
`knowledgebase/SFX_MODEL_FORMULAS.md` sections 8-11.

## 3. Pure Procedural DSP & Acoustic Validity

All effects are generated deterministically via procedural synthesis and physical DSP (noise shaping, resonant bandpass filters, envelope modulation, and Pedalboard DSP). No black-box neural or AI generation models are used.

`acceptable()` verifies that an effect output is finite, has the correct duration, is not silent (RMS > -50 dBFS), does not clip beyond full scale, is not a bare steady tone (crest factor >= 2.5), and contains no isolated clicks or dropouts (`quality_gate.find_clicks`). Dense textured noise bursts are preserved.

## 4. What was checked, and what was not

- Checked: all 28 procedural generators (`sfx.py selftest`), the audio quality gate's rejection of a tone and acceptance of a hit, dynamic parameter specs, and a stereo timeline with multiple effects.
- Checked: Pedalboard analog Moog ladder filters, 8-bit lofi bitcrushing, and stereo delays.
- Not checked by ear: Listen to sound effects in context before delivery.

## 5. Pedalboard Analog Sweeps, Delays & Lo-Fi Degradation

Integrated in `scripts/sfx.py`:

1. **Analog Moog 24 dB/oct Resonant Filter Sweeps (`apply_ladder_filter`)**:
   - Uses `pb.LadderFilter(mode=LPF24, cutoff_hz=..., resonance=..., drive=...)` for warm, fat analog sweeps on whooshes, risers, and sci-fi lasers.
2. **Lo-Fi, Retro Gaming & Codec Degradation (`apply_lofi`)**:
   - `pb.Bitcrush(bit_depth=8)`: Downsamples resolution for vintage 8-bit / 12-bit arcade and sampler textures (MPC60 / SP-1200).
   - `pb.GSMFullRateCompressor()`: Authentic vintage cellular / walkie-talkie band-limiting and lossy compression.
   - `pb.MP3Compressor(vbr_quality=2.0)`: Early 2000s internet streaming and cyber MP3 artifact simulation.
3. **Stereo Tempo-Synced Delays (`apply_delay`)**:
   - Uses `pb.Delay(delay_seconds=..., feedback=..., mix=...)` for cavernous dub echoes and sci-fi UI repeats.

---

## How to create / use

Make an effect or ambience:
1. Named effect: `python scripts/sfx.py list`, then `python scripts/sfx.py make riser --seconds 3 --out out/riser.wav`.
2. A place (rain, canopy, river), only if the user asked for it: `python scripts/presets.py scaffold environments <name> --project <project>` (steps: `environments-as-presets.md`), edit its `layers`, use `"instrument": "env:<name>"`, `"role": "environment"` in the score.
3. Check by ear-proxies: the `Environmental Bed Stability` and masking rows in the Stage 6 scoreboard.

## 6. Ambience is a place, and a place is a preset

Rain on leaves, on a tin roof and on a pond are three sounds. `sfx.rain` is one fixed recipe (a band of noise with clicks, which can read as
frying oil), so ambience is made with `env:` presets: `rain_physical` (`rate_mm_h`, `surface` water|solid|leaf, `bubble_prob`), `resonant_gust`,
`cricket_chorus`, `bird_chorus`, and the rest. The old names `rain`, `water_drip`, `birdsong` in an environments layer still render and the gate
prints a warning that names the primitive to write instead. `sfx:rain` and the other six ambience names are an error in a project.
The numbers in a primitive are tuned by ear unless a preset cites a real recording, so the research phase finds one
(`research-step.md`, Step 0.2b) and `scripts/ambience_reference.py` compares the render with what was measured (a WARN row, not a FAIL).

## How to make realistic ambience (rain, wind, insects, birds, distance, width)

1. `python scripts/presets.py scaffold environments <name> --project <dir>`; edit `<dir>/presets/environments/<name>.json`.
2. Put the weather once at the top: `"atmosphere": {"temp_c": 20, "rh": 50}` (real ISO 9613-1 air absorption by each layer's `spatial.distance`).
3. Pick physical primitives: `rain_physical` (`rate_mm_h`, `surface`), `resonant_gust` + `"turbulence": true`, `cricket_chorus` (`temp_c`), `bird_chorus` (`species`, `dawn_s`).
4. Add `"decorrelate": 1.0` to wash-type layers (rain, wind, insects) so they surround the listener; leave it off single close sounds.
5. In the score, give the `env:<name>` track `spatial: {"distance": ..., "temp_c": ..., "rh": ...}` to use the same filter in the mixer. Set distance in the preset or the mixer, not both.
6. Check: `python -m unittest tests.test_ambience_realism`, then the CI gate. Listening is still needed.

Formulas and sources: `knowledgebase/PROCEDURAL_SFX_AMBIENCE.md`.
