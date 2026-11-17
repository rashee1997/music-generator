# Engine audit and the plan for Immersive 3.0

Status: proposal, nothing in the engine has been changed. Written 2026-11-17 from a read of the code, a
profile of the render path and web research.

## 1. What this is based on, and what it is not

| Checked | How |
|---|---|
| Hardcoded numbers | An AST count of every numeric literal in `scripts/` and `video-mixer/` (vendored spaudiopy files excluded, trivial values such as 0, 1, 2, 1000 excluded), then a read of the mixer, mastering, spatial, SFX and environment code |
| Bottlenecks | `cProfile` on synthetic stems in a 4-core cloud container, Python 3.13, the pinned numpy / scipy / pedalboard versions |
| Library use | Every `pb.*` call site, and a count of which vendored spaudiopy functions are called from engine code |
| Outside practice | Web search (sources in section 9) |

Not checked, and the plan says so where it matters:

- **Nothing was listened to.** `listen.py` did not run. Every claim about naturalness is a design argument, not a result.
- **The binaural decode was not profiled.** The head data host (`depositonce.tu-berlin.de`) is blocked in this session.
- **The SoundFont render, the SFZ path and the quality gate were not profiled** (no SoundFont, no librosa installed here).
- **No GPU was available**, so every GPU speed-up below is an expectation to be measured.
- `spaudiopy.readthedocs.io` and `spotify.github.io` were blocked. Library capabilities were read from the installed
  pedalboard 0.9.26 and the vendored `scripts/spatial_hrtf` source instead.

## 2. Findings in one page

1. **The mix is not the slow part.** Mix plus master ran at about 0.10x real time (5.9 s for 60 s of six stems). A third of
   that is loudness metering, not audio processing.
2. **Most hardcoded numbers are data tables written in Python**, not stray constants: `world.py` (2002 literals),
   `compose.py` (911), `theory.py` (613), `mix_schema.py` (247). They are overridable only where a preset key exists.
3. **The mastering chain is the least configurable part of the mixer.** Tone shelves, the glue compressor, the high-pass
   and the convergence loop are literals in `mixer.py:1061-1091`. A mix preset can choose `warm` but cannot say what warm is.
4. **The sample rate is a constant.** `44100` appears on 101 lines and as 149 function defaults. A 48 kHz delivery is a
   resample of a 44.1 kHz master (`spatial_engine/render.py:357`), not a 48 kHz render.
5. **Pedalboard is used as an EQ, a compressor and a convolver.** 18 of its 31 plugin classes are used. `Reverb`, `Phaser`,
   `Clipping`, `IIRFilter`, `Mix`, `Chain`, `Resample`, `time_stretch` and VST3 hosting are unused.
6. **About 6 of roughly 90 vendored spaudiopy functions are called.** Unused: `allrad2`, `epad`, `vbip`, `sh_rotation_matrix`,
   `rotate_sh`, `binaural_coloration_compensation`, `hrirs_ctf`, `sdm_post_equalization`, `energy_decay`, the fractional-octave
   filter bank.
7. **There is no mono deliverable and no 5.1.** Targets are stereo, binaural, 7.1, 7.1.2, 7.1.4, AmbiX and ADM. Mono
   compatibility is a gate row on the stereo master, and an immersive master is exempt from it
   (`quality_gate.py:448`: a source at 60 degrees loses 698-803 Hz when the two ears are summed).
8. **The multichannel master has no limiter and does not use BS.1770 channel weights.** `spatial_engine/master.py` sets
   one scalar gain from the loudness of the stereo fold. The layouts carry `loudness_weight_db`, and no Python reads it.
9. **The direction sheet's mix intent is not executed.** `mix_intent.leave_free_hz` and `mix_intent.must_hear` are not read
   by the mixer. They are words for `listen.py`, not instructions to the mix.
10. **No GPU path exists.** torch is installed only for `listen.py`, from the CPU wheel index.

## 3. Bottlenecks, measured

All timings: 4 cores, synthetic input. RTF is compute seconds per second of audio.

| Path | Result | Where the time goes |
|---|---|---|
| Stereo mix + master, 6 stems, 60 s | 5.9 s, RTF 0.10 | `lufs()` called 844 times, 1.77 s. `_short_term` (`mixer.py:1025`) re-runs K-weighting on every 3 s window. `true_peak_db` 0.95 s for two calls. `widen` 0.85 s. Building pedalboard objects 0.79 s |
| Ambisonic bus to AmbiX, order 5, 4 sources, 30 s | 2.7 s, RTF 0.09 | `hoa.encode` 1.12 s. `airabs.apply` 1.67 s over 21 calls, one FFT convolution per reflection |
| Vocal choir, 11 s phrase | 1 voice 0.70 s, 5 voices 3.2 s, 16 voices 9.5 s (RTF 0.85) | Linear in voices, rendered one after another. 47,314 `lfilter` calls for five voices (a filter call per frame). `numpy.correlate` 1.08 s of 2.77 s |
| Environment preset, 30 s | `amazon_rainforest` 5.2 s; `savanna_dusk` 0.47 s; `wetland_night` 0.87 s | A tenfold spread between presets. The slow layer was not isolated |
| `import spatial_hrtf.binaural` | 1.05 s | `decoder.py` imports `plot.py`, which imports matplotlib (0.35 s). The mix cannot run without matplotlib installed |
| SFX one-shots, 3 s | under 0.1 s each | Not a bottleneck |

Structural limits behind those numbers:

- **Stems are mixed in a serial loop** (`mixer.py:1402`). Pedalboard releases the GIL, so threads would help, but
  `process_stem` writes into the module-global `STATE` dict, so it is not safe to run in parallel today.
- **Only SFZ tracks render in parallel** (`render_natural.py:990`). SoundFont tracks appear to render one after another.
- **The ambisonic field is held whole**: 36 float32 channels, 1.9 GB for five minutes at order 5, spilling to a temp file
  above 768 MB (`hoa.py:35`). Cost grows with sources times reflections.
- **Every deliverable re-mixes from stems.** Seven targets is seven passes through `mix_stems`.

## 4. Hardcoded values to move into JSON

Ranked by how much flexibility each one costs. "Table" means a data table in Python; "inline" means a literal inside logic.

| Where | What | Kind | Proposed home |
|---|---|---|---|
| `mixer.py:1061-1069` | Master high-pass 24 Hz, the three tone curves, glue compressor -18 dB / 1.6:1 / 40 / 250 ms | inline | `mastering.tones.<name>` and `mastering.glue` in the mix preset |
| `mixer.py:1082-1091`, `1115` | Six iterations, 0.3 LU tolerance, 0.75 step, "8 dB of crest is music" | inline | `mastering.converge`, `mastering.min_crest_db` |
| `mixer.py:317-329`, `370`, `388-392` | Ten built-in rooms; four decay bands; 12 early taps at 0.9 x 0.82^k between 6 and 85 ms | table + inline | Rooms already exist as space presets: delete the table. Bands and taps into the space preset |
| `mixer.py:950-1002` | Reverb send per role (0.08 to 0.30), default 0.18, fallback level -8 dB | inline | `space.send_by_role` in the mix preset |
| `mixer.py:1373`, `1434-1439` | Auto-blend floors; duck release 1600 / 180 ms, attack 25 / 8 ms, smoothing 0.35 s, look-ahead 10 ms | inline | `sidechain.defaults_by_role`, `space.auto_env_blend.floors` |
| `mixer.py:529-531`, `847-850` | Duck band and roles; distance law (1.5 m, 0.40, 3200 Hz, 0.18) | inline | Already half in presets; remove the Python fallbacks |
| `mix_schema.py:40-123`, `129-308` | Role chains, spectral profiles, every default | table | `references/data/presets/mix/_defaults.json`, loaded and validated by `mix_schema.py` |
| `sfx.py:143-366` | 30 generators, 233 literals, no parameters beyond `density` and `surface` | inline | Retire: re-express each as a `sound-models/*.json` model (15 already exist) |
| `environment.py:90-585` | 308 literals, 68 function defaults | defaults | Defaults into `presets/environments/_primitives.json` so a project can retune a primitive, not only a layer |
| `spatial.py:58-133` | Head radius, speed of sound, the built-in acoustic spaces | table | Space presets and a `physics.json` |
| `spatial_engine/hoa.py:34-38`, `92` | 343 m/s, 30 degree stereo pair, 1200 virtual speakers, block sizes | inline | `immersive.decoder` in the mix preset |
| `spatial_engine/master.py:42`, `81-87` | 24 Hz DC block, six trims, 0.05 dB step | inline | The output target preset |
| `spatial_engine/decorrelate.py` | Seeds, coefficient range 0.2 to 0.95 | inline | The layout's `decorrelate` block |
| `dsp.py:31` and defaults | Control rate 400 Hz; click-repair thresholds | inline | `render.control_rate_hz`; the gate profile |
| All modules | `SR = 44100` | constant | One `render.sample_rate` read through the mix context |
| `world.py`, `compose.py`, `theory.py` | Instrument maps, genre recipes, scales | table | `references/data/` JSON, with the loaders keeping today's names |

Rule 16 of `AGENTS.md` applies to every moved number: it carries its source or the words "starting value". Most of the
inline mixer numbers have no citation today, so the move also surfaces which ones are unsourced.

## 5. Immersive 3.0

### 5.1 The idea: one scene, many renders

Immersive 2.0 mixes the piece once per deliverable and treats stereo as the certified master with the others beside it.
3.0 makes the **scene** the master:

```
stems -> per-stem processing (EQ, dynamics, sends)        once
      -> SCENE: objects (signal + position over time)      once, cached on disk
                + room (early reflections, late field)
                + beds (LFE send, sympathetic bed)
      -> renderer per target                               cheap, parallel
           mono | stereo | binaural | 5.1 | 5.1.2 | 5.1.4 | 7.1 | 7.1.2 | 7.1.4 | 9.1.6 | AmbiX | ADM | IAMF
      -> master per target (loudness, limiter, ceiling)
      -> one gate, with cross-target rows
```

This is the seam `mix_stems(..., bus=)` already has. The change is that the bus input is rendered once and stored, and
every target is a decode of it.

### 5.2 Every channel count, including mono

"No degradation in mono" cannot mean summing a binaural file. Interaural time differences are what make a binaural image,
and summing two ears turns them into comb filters; the repo has already measured this. No filter design removes that
without giving up part of the image. So mono is **rendered, not folded**:

| Target | How it is made | Why it does not degrade |
|---|---|---|
| `mono` (new) | Sources summed at their mixed level with no head filter and no time difference. Room: the late field decoded to one channel with its energy held equal to the stereo render | Nothing to cancel: there is only one path per source |
| `stereo` | Amplitude panning from the scene (no delays between channels). Width from decorrelators built as mid/side pairs, as `mixer.widen` already does, so L+R returns the dry mid | Its mono sum equals the mono render by construction |
| `binaural` | Unchanged route (MagLS), plus an optional `mono_safe` mode that reduces time differences below a preset frequency | The trade against externalisation is measured and reported, never assumed |
| 5.1, 5.1.2, 5.1.4, 9.1.6 (new), 7.1.x | Layout presets only; the decoder is already layout-driven | BS.775 fold coefficients are in each layout |
| `iamf` (new) | The ADM file handed to the open `iamf-tools` encoder, as an optional external tool like `sfizz_render` | Open, royalty-free; reported as "not built" when the tool is absent |

New gate rows, each with a positive and a negative control:

- `fold.mono_null`: the stereo master summed to mono against the mono render, per auditory band. Protected, like `loudness`.
- `fold.chain`: each layout folded down one step (7.1.4 to 5.1 to stereo to mono) loses no more than a preset amount per band.
- `fold.timbre`: long-term spectrum of every target against the stereo master, so no format is the dull one.
- `imm.loudness_weights`: the multichannel loudness is computed with the layout's own `loudness_weight_db`.

The limits are starting values until measured on the three sample projects.

### 5.3 The spatial engine

| Change | Uses | Purpose |
|---|---|---|
| AllRAD2 and EPAD decoders, chosen per layout | `decoder.allrad2`, `decoder.epad` (vendored, unused) | Even loudness on small layouts such as 5.1, where plain AllRAD thins out between speakers |
| Binaural diffuse-field equalisation and colouration compensation | `process.hrirs_ctf`, `sph.binaural_coloration_compensation` | Removes the head set's own tone from the headphone render |
| Field rotation | `sph.sh_rotation_matrix`, `rotate_sh` | A scene can turn (camera pan, head-tracked preview) without re-rendering sources |
| Late reverb as a feedback delay network with velvet-noise diffusion, per-band decay from the room's materials | new, `spatial_engine/fdn.py`; numbers in the space preset | Replaces filtered noise shaped by an exponential (`mixer.make_ir`). Decay per band follows the room, echo density builds the way a room's does, and the tail is produced directly in the field |
| Source directivity and extent | new preset keys on instruments | A violin does not radiate like a point; extent replaces the fixed pair angle |
| Linked multichannel true-peak limiter | new, `spatial_engine/master.py` | The one-gain master cannot reach a loudness target on dynamic material |
| BS.1770 loudness with channel weights | the layout presets' existing field | The measure a delivery spec means |
| Native sample rate | `render.sample_rate` | A 48 kHz deliverable rendered at 48 kHz |

### 5.4 Delivery profiles as presets

`presets/outputs/` gains loudness and ceiling per profile, each line with its source. The Atmos-style music profile is
-18 LKFS integrated and -1 dBTP; the engine's multichannel default today is -14 with a -3 dBTP ceiling. An ADM file from
this engine stays what the current preset says it is: an open-standard file, not a vendor master.

## 6. The mix: natural and dynamic

Each item is a preset section first, code second, and off by default so an older piece mixes as before.

1. **Spectral unmasking in place of fixed carving.** Per band and per frame, cut a bed only where it actually masks the
   focus, by an amount bounded in the preset. Replaces the static `carve_db` and the fixed 250-3800 Hz duck band.
2. **`mix_intent` becomes executable.** `leave_free_hz` and `sits_under` resolve to the unmasking targets; `must_hear`
   entries become gate rows measured at their timestamps.
3. **Section-aware automation.** The sheet's `sections[].energy` drives rides on sends, width and bed level between
   sections, with the curve shapes in the mix preset. This is what makes a mix move with the piece.
4. **Dynamics.** Program-dependent release and an RMS/peak blend in `dsp.compressor`; multiband and dynamic EQ are already
   written and stay opt-in.
5. **Depth as one decision.** Distance sets direct level, air absorption, early-reflection pattern and send together from
   the space preset, instead of four separate fallbacks in `_place`.
6. **Mastering as data.** A chain list in the mix preset (`eq`, `multiband`, `saturate`, `width`, `limit`), with the
   limiter oversampling and release in the preset. A VST3 slot through pedalboard for a user who owns a mastering plugin;
   never required, never shipped.
7. **Pedalboard used for what it is good at.** `Mix` and `Chain` for parallel paths, `Clipping` ahead of the limiter,
   `time_stretch` for fitting a cue to picture, `Resample` quality set per target, chunked processing with `reset=False`
   so long pieces do not need whole-file buffers.

## 7. Vocals, SFX and ambience

**Vocals.** The engine already has a glottal source, a tract and a waveguide with its numbers in `defaults.json`.
The gaps are structural: voices render serially, and filtering is per frame.
- Batch voices as one array through the tract (the same change gives the GPU path).
- Replace per-frame `lfilter` with a time-varying lattice run over whole phrases.
- Add coarticulation between syllables and consonant-vowel transitions as data in the expression profiles.
- Report what was sent. A sung text is still vowels and a syllable inventory, not a language; say so.

**SFX: any sound, as data.** Two generators exist side by side: 30 fixed Python recipes in `sfx.py` and the `sound_model` /
`phys_core` engines that already describe a sound as exciter, resonator and events.
- Retire the fixed recipes into model JSON, so there is one path.
- Add the missing exciters and resonators as general primitives (waveguide tube and string, plate, cavity, turbulence
  jet, combustion), never one generator per sound name (rule 16).
- Make `sound_fit.py` the standard way in: a reference recording fits a model's parameters, and the preset records the
  recording, its licence and the fit error.
- "Any SFX" then means any sound the primitives can express. A sound they cannot is reported as a gap, not approximated.

**Ambience.** Beds become scene objects with extent rather than stereo files placed in a field: a rain bed surrounds, a
bird is a point with a position, a call moves. Add time-of-day and weather curves on layers, and require the two sources
and the measurement that Phase 3.4 already asks for. Still only when the brief asks for ambience.

**Direction.** The sheet gains fields that the engine reads rather than fields that describe:

| New or changed field | Read by |
|---|---|
| `sections[].mix` (send, width, bed level, focus per section) | section automation |
| `mix_intent.leave_free_hz`, `sits_under`, `must_hear[].at_s` | unmasking, new gate rows |
| `delivery.targets[]` with profile, sample rate, bit depth per target | the scene renderers |
| `immersive.mono_policy` (`render` or `fold`) and `fold_priority` | the mono target, `fold.*` rows |
| `situation` (medium, playback system, listening level, programme around it) | resolves to a delivery profile and mix defaults through `presets/intent/` |

`situation` is how "proper situation-based" direction is made checkable: a trailer in a cinema, a podcast bed on a phone
and a game loop on headphones resolve to different profiles, and an unknown word is an error, as intent words are today.
`music-direction.md` and `directing-space.md` get a section each; `AGENTS.md` Phase 4.3 and 4.7 list the new fields.

## 8. CPU first, GPU when present

**One module, `scripts/compute.py`.** It picks a backend once: CUDA, then Apple MPS, then CuPy, then NumPy. Overrides:
`render.compute.device` in the mix preset and `MUSICGEN_DEVICE` in the environment, both accepting `auto`, `cpu`, `cuda`,
`mps`. The choice and the device name are written into the render report.

| Work | CPU plan | GPU candidate |
|---|---|---|
| Loudness metering | K-weight once, reuse block energies (removes most of the 1.77 s) | no |
| Stem processing | Move `STATE` into the mix context, then a thread pool | no (pedalboard is CPU) |
| Convolution: reverb, air absorption, binaural decode | `scipy.fft` with `workers`, partitioned for long tails, air absorption batched per source instead of per reflection | yes |
| Ambisonic encode and decode | Blocked matrix products, already vectorised | yes |
| Modal banks, vocal tract, choir | Batched arrays | yes |
| IIR filters, limiter, SoundFont, SFZ | unchanged | no |
| Deliverables | Scene cached once, targets rendered in a process pool | per target |

Rules for the GPU path:
- It is optional. `requirements.txt` stays CPU-only; a GPU install is `setup_project.py --gpu`.
- A GPU render is not bit-identical to a CPU one. The stem cache key includes the device, the gate certifies whichever
  render was made, and a test bounds the difference between the two.
- A failure on the GPU (out of memory, missing kernel) falls back to CPU with a line in the report, never silently.
- No speed-up is claimed until `mix_bench.py` has measured it on a real GPU.

## 9. Order of work

Each phase ends with the existing test suite green, new rows proven able to fail, and the three sample projects
re-rendered and compared against their current masters.

| Phase | Content | Risk |
|---|---|---|
| 0. Baseline | `mix_bench.py` extended to time every stage; record today's numbers and null-test files for the three samples | none |
| 1. Free speed | Metering reuse, lazy matplotlib import, `STATE` into the context, threaded stems, batched air absorption | low: output must null against phase 0 |
| 2. Numbers to JSON | Section 4, top to bottom; defaults keep today's values, so output must still null | low, large diff |
| 3. Sample rate | `render.sample_rate` end to end | medium: every module's `SR` |
| 4. Scene and targets | Scene cache, `mono`, 5.1 family, 9.1.6, `fold.*` rows, weighted loudness, multichannel limiter | medium |
| 5. Spatial quality | AllRAD2 / EPAD, binaural equalisation, FDN late field, directivity, rotation | high: changes the sound, so each is opt-in per preset |
| 6. Mix | Unmasking, executable `mix_intent`, section automation, mastering chain | high: opt-in |
| 7. Voices, SFX, ambience | Section 7 | medium |
| 8. Compute backend | `compute.py`, GPU kernels, parity test | medium; needs a GPU machine |
| 9. Direction and docs | Template, guides, `AGENTS.md`, knowledge base rows with sources | low |

Phases 1 to 3 change no sound and can be verified by null test. Phases 5 to 7 change the sound and cannot be verified
by numbers alone: they need `listen.py` and a person.

## 10. Decisions needed before phase 4

1. **Mono policy default.** Rendered mono (recommended) or the BS.775 fold. Rendered is cleaner; the fold is what a
   device that sums a stereo file will actually play, so the gate checks both either way.
2. **Master rate.** Render at 48 kHz by default (recommended, it is the delivery rate for picture and for object
   formats) or keep 44.1 kHz and let targets ask.
3. **GPU dependency.** torch (recommended: already used by `listen.py`, covers CUDA and MPS) or CuPy (lighter, CUDA only).
4. **`sfx.py` recipes.** Retire them (recommended) or keep them as legacy names that resolve to models.

## Sources

- Dolby Atmos music delivery playbook: https://dolby.com/siteassets/dolby-institute/dolby-atmos-music-accelerator/dolby-atmos-music-delivery-playbook-1.pdf
- Apple video and audio asset guide: https://help.apple.com/itc/videoaudioassetguide/en.lproj/itcf946aaace.html
- ITU-R BS.1770-5: https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf
- ITU-R BS.2127-1 (ADM renderer): https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.2127-1-202311-I!!PDF-C.pdf
- AOMedia Open Audio Renderer spec (layout names): https://aomedia.org/specifications/oar/1.0.0/
- Eclipsa Audio announcement: https://opensource.googleblog.com/2025/01/introducing-eclipsa-audio-immersive-audio-for-everyone.html
- iamf-tools encoder interface: https://android.googlesource.com/platform/external/iamf_tools/+/refs/heads/android17-release/docs/iamf_encoder_interface.md
- Binaural filters for monophonic compatibility (patent): https://uspto.report/patent/grant/8515104
- Diffuse signal processing for mono compatibility (AES Europe 2025): https://aeseurope2025.sched.com/event/222dv/diffuse-signal-processing-disp-as-a-method-of-decorelating-a-stereo-mix-to-increase-mono-compatibility
- Velvet-noise feedback delay networks (DAFx 2020): https://acris.aalto.fi/ws/portalfiles/portal/52251303/DAFx2020_paper_23.pdf
- Differentiable artificial reverberation: https://arxiv.org/pdf/2105.13940v2
- Differentiable FDN for colorless reverberation: https://cris.fau.de/publications/313574952
- Partitioned convolution (DAFx 2020): https://dafx2020.mdw.ac.at/Proceedings/papers/DAFx2020_paper_1.pdf
- torchaudio FFTConvolve: https://docs.pytorch.org/audio/master/generated/torchaudio.transforms.FFTConvolve.html
- State of the art in sound texture synthesis: https://dafx.de/paper-archive/details/61SplddyWP6RcOOx0SEdAw
- 6KSFx procedural SFX dataset: https://arxiv.org/html/2501.17198v1
- Neural audio synthesis for sound effects, a scope review: https://vbn.aau.dk/ws/files/818061358/Neural_Audio_Synthesis_for_Sound_Effects_A_Scope_Review.pdf
- spaudiopy: https://www.github.com/chris-hld/spaudiopy
- pedalboard: https://github.com/sarvex/pedalboard (mirror; the official docs host was unreachable from this session)

The web figures above come from search summaries of these pages, not from a full read of each document. Any number
taken into a preset must be re-read from the primary source first.
