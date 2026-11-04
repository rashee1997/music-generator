# Mixer and video path: audit and enhancement plan

Audited 2026-11-03. **Read only: no code was changed for this audit.** Every number below was either
measured on this machine during the audit or read from the code at the cited line; nothing was listened
to and no mix was re-rendered.

Scope: `scripts/mixer.py`, `scripts/dsp.py`, `scripts/mix_schema.py`, `scripts/mix_diagnostics.py`,
`scripts/pipeline.py` (stages 5-6), `scripts/quality_gate.py` (balance/loudness rows), the whole of
`video-mixer/` and `scripts/video_score.py`, plus `references/presets/video/default.json`.

## 1. What is already sound

| Area | Evidence |
|---|---|
| Mix decisions are preset values, not code | `mix_schema.DEFAULTS` holds every knob; `validate()` rejects an unknown key or an out-of-range value; `role_chains` and `spectral_profiles` are JSON |
| Diagnostics only report | `mix_diagnostics.analyse()` returns rows and never edits the mix; the gate downgrades a diagnostic FAIL to WARN by contract |
| One Welch PSD per stem | `dsp.band_powers` replaced 1,848 per-pair PSDs with 24; `analyse()` went 46 min -> **103 s** with bit-identical numbers |
| Mux never re-encodes video | `video_mux.mux` uses `-c:v copy` and then proves it by comparing codec, size, pixel format and frame count |
| Cut sync only judges cut-derived hits | `video_gate.cut_sync_rows` keeps `kind: motion` hits out of the cut measurement |
| One gate implementation | `quality_gate.run_gate` is called by both `pipeline.py` and `quality_gate.py` |

## 2. Measured bottlenecks

Measured with `numpy 2`/`scipy` in the skill venv, 200,000 samples at 44.1 kHz, then scaled to a 195 s
program (8.6 M samples).

| # | Where | Measurement | Fix |
|---|---|---|---|
| 1 | `video_program_mix.speech_mask` - box filter via `np.convolve(active, np.ones(hold)/hold)`, `hold = speech_hold_s(0.35) x 44100 = 15,435` taps | **33.6 s per 200k samples -> about 1,440 s (24 min) for a 195 s program.** This one line is the video path's stall. | `scipy.ndimage.uniform_filter1d(x, k)` measured **<0.01 s** for the same work; the result is the same moving average |
| 2 | `speech_mask`, `duck_curve` smoothing | 1,323 taps (0.03 s) = 0.08 s per 200k -> ~3 s per program | same one-line swap |
| 3 | `master_chain` loudness convergence | up to 6 limiter passes plus 6 full K-weighted measurements, each over the whole master | estimate static gain from the pre-limiter loudness, then 1-2 verification passes (the 0.75 damped step rarely needs more than 3) |
| 4 | `dsp.true_peak_db` | 4x `resample_poly` in float64 over the whole buffer: **519 MB** transient for a 184 s stereo master; the Amazon run's working set was 3.4 GB | block it (10 s blocks with at least 3x filter-length overlap): same value, flat memory |
| 5 | `mix_stems` | 24 stems x 196 s stereo float32 = 830 MB per copy; processed + dry + send + return is the 3.4 GB that was resident | accumulate then free each stem, or process in 30 s blocks with a tail overlap for the reverb |

## 3. Audio findings

**A1 - the true-peak trim breaks the loudness just reached.** `mixer.master_chain` measures `tp` after
the limiter and, if it is over the ceiling, scales the whole master by `10**((ceiling-tp)/20)`. That
moves the delivered LUFS away from the target (the code recomputes `reached` and sets
`limited_by_ceiling`, but the target is missed). Lower the limiter ceiling and re-limit, or apply the
trim before the final loudness iteration.

**A2 - `multiband_compressor` and `dynamic_eq` do not reconstruct flat.** `dsp.multiband_compressor`
sums independent 2nd-order Butterworth bands (`out += part`); `dsp.dynamic_eq` builds `rest = y - band`
from a non-complementary band-pass. The docstring admits the phase point, but the consequence is a
level ripple at every crossover and, in `dynamic_eq`, a partial notch where the band was extracted.
An LR4 crossover sums flat and stays phase-aligned (Rane Note 160, and the linear-vs-minimum-phase
literature in section 6).

**A3 - `active_lufs` measures LUFS per 0.4 s window.** `mixer.active_lufs` calls `lufs()` once per
active window of every stem, i.e. thousands of 0.4 s K-weightings. K-weighting is LTI: filter the stem
once, then take block energies. Same number, one filter pass instead of roughly 500.
(Identified from the code pattern; not yet timed.)

**A4 - balance is judged in RMS, mixing is decided in LUFS.** `quality_gate._active_db` is plain RMS,
while gain staging uses `active_lufs`. A 2 kHz-heavy stem and a bass-heavy stem at equal RMS are not
equally loud, so `balance` can pass a mix that is audibly wrong. Either use a K-weighted level there
too, or state the limitation in the row text (the docstring already says "plain RMS").

**A5 - the reverb IR is energy-normalised, not level-calibrated.** `make_ir` divides by the IR's own
RMS, so the wet level depends on tail length and room rather than on a target direct-to-reverberant
ratio. The `space.drr` block exists but is `enabled: false`; calibrating against it would make room
changes reproducible.

**A6 - an EQ band with `order` bypasses the preset chain.** `process_stem` sends `order` hp/lp bands to
`dsp.slope_filter` before the Pedalboard chain runs, while peak bands go through Pedalboard. Two filter
implementations in one chain, with different phase response, applied outside the order the preset lists.
Acceptable if intended; it should be stated in the preset schema.

## 4. Video findings

**V1 - the dialogue-gated loudness mode is a label, not a measurement.** `references/presets/video/default.json`
declares `"loudness_mode": "dialogue_gated"` for `broadcast` and `cinema`, and `video_gate.master_row`
prints it. A grep of `scripts/` and `video-mixer/` finds **no implementation** - only the literals in
`scripts/presets.py`. The voice is normalised by full-file `mx.lufs(v, sr)` in
`video_program_mix.build`, and the program is mastered by full-program loudness. Broadcast and Netflix
targets are dialogue-anchored (section 6), so the delivered number is not the one the report names.
Fix: reuse the existing `speech_mask` and gate the meter to speech-active frames; report both
full-program and dialogue-gated numbers.

**V2 - `frame_metrics` buffers the whole rawvideo stream.** `video_probe._run(..., binary=True)` is
`subprocess.run(stdout=PIPE)`. At 12 fps, 320x180 RGB24 that is 172.8 kB per frame, so a one-hour clip
is **7.5 GB** in RAM. The docstring says the pipe is streamed; the code is not. Switch to `Popen` plus
`readinto` and process one frame at a time.

**V3 - two full decodes per probe.** One pass for `scdet`, another for `rawvideo`. A single ffmpeg
invocation with two outputs, or reusing the read frames for a luma-difference score, halves probe time
on long clips.

**V4 - resampling after limiting.** `video_program_mix.master()` limits at 44.1 kHz and then
`resample_poly` to 48 kHz. Inter-sample peaks can appear after the resample and nothing re-checks them;
`video_gate.master_row` measures the file again, so it surfaces as a FAIL rather than as a limiter
action.

**V5 - `-shortest` can truncate silently.** `video_mux.mux` passes `-shortest` when the preset asks for
it, and `video_gate.duration_row` measures `program.wav`, not the muxed audio stream. If the music ends
before the picture, the delivered file is short and no row names it.

**V6 - the frame-count proof is skipped when the container omits `nb_frames`.** `mux()` only compares
frames `if src['frames'] and dst['frames']`. MKV and WebM commonly report 0. Use
`-count_frames -show_entries stream=nb_read_frames` in `_video_identity`.

**V7 - `spectral_duck`'s band split is not a crossover.** `band(music, 250, 3800)` is a 4th-order
Butterworth band-pass and `rest = music - banded`. Where the two gain curves differ (`g` against
`g**(1+extra)`), the duck depth varies with frequency in a way that is not the intended curve, because
`rest` still holds band-edge energy. An LR4 hi/lo split makes the depth exact per band.

**V8 - `cut_candidates` misses dissolves and fades by design.** `video_probe` documents this, and the
shot-detection benchmark literature confirms it. If cues must hit dissolves, add a second detector
(histogram or edge based, or a dissolve-aware algorithm) and merge the two lists.

## 5. Prioritised roadmap

| Phase | Change | Expected gain | Risk |
|---|---|---|---|
| 1 | `uniform_filter1d` in `speech_mask` / `duck_curve` | about 24 min -> under 1 s on a 3-minute program | none, same output |
| 1 | Chunked `true_peak_db` | about 500 MB less peak per call | none (verify the value is identical) |
| 1 | Speech-gated dialogue meter and an honest `loudness_mode` | correct broadcast and Netflix numbers | low |
| 2 | Stream the rawvideo probe with `Popen` | flat memory on long clips | low |
| 2 | Re-limit instead of a global trim; re-check true peak after the 48 kHz resample | the loudness target is actually met | low |
| 3 | LR4 crossovers in `multiband_compressor`, `dynamic_eq`, `spectral_duck` | removes the ripple and the notch | medium, changes audio |
| 3 | One K-weighting per stem in `active_lufs`; K-weighted `balance` | speed and consistent loudness | low |
| 4 | Stream `mix_stems` in blocks; DRR-calibrated IR | memory, repeatable space | medium, changes audio |
| 4 | Second dissolve detector; `-count_frames` proof | picture accuracy | medium |

Each phase must be verified with `quality_gate.py --selftest`, `tests/test_gate_ambient.py`, the
pipeline on a short cue, and a before/after measurement of the exact number it targets. A change that
alters audio (phase 3-4) also needs a listen; the audits here cannot hear.

## 6. References

Loudness and delivery
- ITU-R BS.1770-5, K-weighting, gating and true peak (Annex 2, 4x oversampling):
  <https://www.forasoft.com/learn/audio-for-video/articles-audio/loudness-normalization-ebu-r128-bs1770-atsc-a85>,
  <https://github.com/basilica-audio/Apotheosis/blob/main/docs/research-notes.md>
- EBU R 128, programme loudness -23 LUFS, true peak -1 dBTP, +/-0.5 LU: <https://tech.ebu.ch/docs/r/r128.pdf>
- Netflix branded sound mix, -27 LKFS dialogue-gated +/-2 LU, -2 dBTP:
  <https://studiopartner.netflix.net/studio/branded-sound-mix-spec-and-best-practices>
- ATSC A/85, dialogue as the anchor element, long-form -24 LKFS +/-2, -2 dBTP
  (already cited in `references/presets/video/default.json`)
- Streaming targets and when to use -2 dBTP: <https://mazufa.com/loudness-reference/>
- pyloudnorm accuracy and speed against ffmpeg and libebur128:
  <https://csteinmetz1.github.io/pyloudnorm-eval/paper/pyloudnorm_preprint.pdf>
- ffmpeg `loudnorm` two-pass method:
  <https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3>

DSP
- Rane Note 160, Linkwitz-Riley crossovers (flat sum, phase alignment):
  <https://www.ranecommercial.com/legacy/note160.html>
- Linear against minimum phase at crossovers, and what each smears:
  <https://matlefflerschulman.com/mastering-articles/minimum-phase-linear-phase-eq-mastering>
- Fast convolution, partitioned and overlap-add for long impulse responses:
  <https://thewolfsound.com/fast-convolution-fft-based-overlap-add-overlap-save-partitioned/>,
  <https://ccrma.stanford.edu/~jos/sasp/Convolving_Long_Signals.html>

Video
- Muxing without re-encoding: <https://www.mux.com/articles/merge-audio-and-video-files-with-ffmpeg>
- `scdet` thresholds and its blind spot on fades and dissolves:
  <https://ffmpeg-cookbook.com/en/articles/scene-detect/>
- Shot-boundary benchmark, ffmpeg against Shotdetect and PySceneDetect:
  <https://github.com/albanie/shot-detection-benchmarks>
- Dissolve and fade detection (Campisi and Neri):
  <https://www.semanticscholar.org/paper/Automatic-dissolve-and-fade-detection-for-video-Campisi-Neri/c98504e4bcb07e0bfcad3db20b2c3b4c4dcfe99b>
- ITU-R BS.775-4, multichannel downmix, if a surround deliverable is ever added:
  <https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.775-4-202212-I!!PDF-E.pdf>

## 7. Limits of this audit

- Everything is read from the code, and measured only where a number is given. **Nothing was listened
  to**; a mix that measures well can still be wrong, and only `listen.py` or a person can say otherwise.
- The convolution numbers were measured on this machine at 200k samples and scaled by 43 to a 195 s
  program at 44.1 kHz. The `active_lufs` estimate is inference from the code pattern, not a stopwatch.
- `scripts/spatial_hrtf/` (about 7.5k lines) was not audited beyond its call site in `mixer._place`;
  its per-stem cost is unmeasured.
- Platform loudness specs change. The sources above were current when this was written; re-check them
  before a delivery and update the preset's `sources` list with the date checked.
- The video rows are standard summaries to verify against the receiving platform's current spec; they
  are not a substitute for a QC pass on the delivered file.
