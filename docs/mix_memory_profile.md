# Mix and render memory profile: where the gigabytes go, and the plan

Measured on the branch `ccr-3a0c8741-kv7qx8` (commit `26da79b` plus the changes in this document), on a
2-core / 3 GB Linux container, Python 3.12.3, numpy 2.5.5, scipy 1.18.1, pedalboard 0.9.26. A consumer
laptop with 8-16 GB behaves the same way with proportionally larger buffers: the numbers below are the
engine's own working set, not a property of this machine. The real-project re-render in section 8 was
measured later on an 8-core / 16 GB machine, and says so there.

Reproduce any row with `python3 scripts/helpers/bench_memory.py <case>` (new file, `lufs` / `mix` /
`validate`). The CPU side is in `docs/mix_profile_palace.md`; this file is the memory side, plus the plan
that follows from both.

---

## 1. Results, before → after this change set

Peak RSS of the whole process, so every row includes the interpreter and the numpy/scipy/pedalboard
imports (about 200 MB on this machine; the bench prints the idle baseline it started from).

| Case | Audio in play | Before | After | Change |
|---|---|---|---|---|
| `active_lufs`, one 120 s stereo stem | 42.3 MB | 267 MB | 224 MB | −43 MB (−16 %) |
| `mix_stems`, 8 stems × 20 s, 2 workers | 56.4 MB | 337 MB | 331 MB | −6 MB |
| `mix_stems`, 8 stems × 20 s, 8 workers | 56.4 MB | 474 MB | 392 MB | −82 MB (−17 %) |
| `mix_stems`, 6 stems × 90 s, 6 workers | 190.5 MB | 997 MB | 748 MB | −249 MB (−25 %) |
| `mix_stems`, 12 stems × 120 s, 4 workers | 254.4 MB | — | 1 428 MB | new stress case |
| `mix_stems` + `master_chain`, one 180 s stem | 63.5 MB | 1 418 MB (9.62 s) | 766 MB (7.00 s) | **−652 MB (−46 %), −27 % time** |
| `_validate_export`, 60 s PCM_24 | 21.2 MB | 507 MB (0.64 s) | 238 MB (0.38 s) | −269 MB (−53 %), −41 % time |

The master stage was the single largest spike in a one-piece render: a 63.5 MB master took the process
from 741 MB to 1 418 MB. One `dsp.true_peak_db` call added 676 MB of that on its own.

---

## 2. Where the memory actually goes

### 2.1 The audio itself is multiplied

One second of one stem, stereo float32, is **0.353 MB**. A 180 s piece with 31 stems is therefore
1.98 GB *per copy of the whole piece*, and the pipeline keeps several alive at once:

| Copy | Where | 31 stems × 180 s |
|---|---|---|
| dry stems | `pipeline.stage4` returns them; alive until the last format is rendered | 1.98 GB |
| placed stems | `mixer.STATE['processed']` (`mixer.py:1534`), alive until stage 6 finishes | 1.98 GB |
| sum bus + room send | `dry` and `send` in `mix_stems`, plus the reverb return and the mix buffer | 2-3 × 63.7 MB |
| ambisonic field | `hoa._alloc` at order 5 = 36 channels | 1.15 GB (memmap past 768 MB) |
| worker partial fields | one `(n, K)` per mix worker (`hoa._place_all`) | up to workers × 1.15 GB |
| gate views | `gate_audio.Signal` casts the deliverable to float64 and keeps a mono copy | 2-3 × master |

That is already ~5 GB for a 3-minute piece before any per-stem temporary. The reported 13-14 GB peak on
the 7.1.2 mix is the sum of these copies plus one worker's worth of transients per core.

### 2.2 Per-stem transients were the multiplier

Every stage made a full-length copy of the stem it was working on, and several were alive together:

* `mixer.active_lufs` (`mixer.py:562`) stacked every 0.5 s window into one array and then squared a
  float64 copy of it: about **six stem-length buffers** per worker.
* Pedalboard calls copy into channel-major layout (`np.ascontiguousarray(x.T)`) and back
  (`mixer._run`), two full copies per board.
* `width_ms` and `pan_stereo` each allocated their result, so placement held three generations at once.
* `process_chain`/`process_stem` ended with `x.astype(np.float32)`, which copies even when the dtype is
  already float32.
* `dsp.true_peak_db` cast to float64, oversampled ×4 **in float64**, then took a full-length `abs`:
  eleven times the master for one measurement.
* `_validate_export` read the written file as float64 and took a full-length `abs` again.
* `gate_audio.Signal` (`gate_audio.py:54`) keeps the float64 deliverable plus a float64 mono mean.

### 2.3 The worker count ignored memory

`render.mix_workers: "auto"` meant "one stem per core". On a 16 GB machine with 21 stems that is 21
concurrent chain working sets, which is what took the 7.1.2 mix to 13-14 GB. The ambisonic bus already
had a fit (`hoa.workers_that_fit`); the mix did not.

---

## 3. What was changed

| Change | Where | Why it is safe |
|---|---|---|
| Loudness staging summed per window in float64 instead of stacking the stem and squaring a float64 copy | `mixer.active_lufs`, `mixer.py:562` | Same windows, same float64 accumulation; 6 stem buffers → one 0.5 s window. Selection is `flatnonzero` of the same comparison |
| `render.mix_worker_mb_per_second` (new preset key, default 2.0) and `mixer._workers_that_fit` | `mix_schema.py` (`render`), `mixer.py:884` | The count is capped by `resources.available_gb()` less `resources.HEADROOM_GB`; it never raises the requested count, and prints when it lowers it |
| Placement worked in place (`_width_inplace`, `_pan_inplace`, `x *= 1/r`, `x /= distance`), chain output returned with `np.asarray` | `mixer.py:967` | Bit-identical to the previous arithmetic (checked: `max|Δ| = 0` for widths 0.3/1.4 and pans −1…+1) |
| Processed-stem cache written **before** placement | `mixer.mix_stems._work`, `mixer.py:1534` | The cache must hold the dry chain output; `_place` now may work in place. This was a latent ordering bug |
| Reverb tail added into the existing bus instead of a third full-length buffer | `mixer.mix_stems` | Same samples, one less `(n, 2)` allocation |
| `true_peak_db` per channel, float32, blockwise maximum | `dsp.true_peak_db`, `dsp.py:188` | Agrees with the whole-buffer float64 measurement to 2e-7 dB on a 4 s fixture; PCM_24 is the delivered precision |
| `correlation`, `mono_fold_db` summed in float64 from float32 without full float64 copies | `dsp.py:61`, `dsp.py:94` | Verified against `np.corrcoef` and the old RMS formula: Δ ≤ 1e-12 |
| `_validate_export` reads float32 and takes peak/clipping blockwise | `mixer.py:1801` | Same peak, same clipping count; 4 file-length copies → one file plus a block |
| Ambisonic bypass bus and decoded columns in float32 instead of float64 | `hoa.py:602`, `hoa.py:622` | The field and the decode filters are float32 already; one 63 MB copy per harmonic removed |
| Reflection tap response no longer copied per tap | `hoa.tap_signals`, `hoa.py:163` | One multiply instead of copy+divide, per tap (60 MB per tap on a 3 min source) |
| Partial ambisonic fields freed as they are summed; their temp files removed | `hoa._place_all`, `hoa.py:408` | Peak was workers × field; the Windows temp-file path used to be discarded and leaked |
| The gate's per-file registry is capped at 2 files and is now an LRU | `gate_audio.py` (`_REGISTRY`, `load`) | A film or a multi-format run loaded every deliverable into a dict that never evicted: a float64 copy plus its caches per file. Evicting is safe, a live reference keeps its object |
| `naturalness_check.load` uses the gate's own array; `quality_gate`'s immersive block uses `gate_audio.load` instead of a second `sf.read` | `naturalness_check.py`, `quality_gate.py` | One master is read, cast and kept once per run. Verified: `nc.load(p)[0]` and `gate_audio.load(p).audio[:, :2]` share memory |
| A band-ducked bed is rewritten in place (two curves, no output allocation) | `mixer.mix_stems`, `mixer.py:1701` | Algebraically the same expression (`mid*d + (x-mid)*d**r == x*r + mid*(d-r)`); measured difference 6e-8 max, 5e-9 rms |
| The reflection tap loop reuses two spectrum scratch buffers and an in-place inverse FFT | `hoa.tap_signals`, `hoa.py:163` | Same arithmetic in the same order (verified through `test_immersive_v2`), three full spectra per tap no longer allocated and freed |
| The ambisonic field is never held whole: every source writes row blocks into a `_FieldSink`, which decodes each block before the next is written (binaural: overlap-save, one transform per block for both ears and every harmonic) | `hoa._FieldSink`, `hoa.encode`, `hoa.encode_many`, `hoa.HoaBus.field`, `hoa.HoaBus.result` | Decoding is linear, so decoding each contribution and adding the results is the same arithmetic as decoding the sum; the gate rows come out byte-identical (section 8) |
| A worker decodes into its own `(n, out_channels)` output instead of holding an `(n, K)` partial field | `hoa.HoaBus._place_all`, `hoa.HoaBus.workers_that_fit` | The partial field is summed into the output anyway; a decoded output is 2 channels, not 25-36 |
| Stems render in parallel: a pool of sampler slots (`_borrow_synth`) plus a thread per track, instead of one Synth and a serial loop | `render_natural.build_stems`, `render_natural._borrow_synth` | Every track has its own seed and its own reset sampler slot, so the bytes do not depend on the order: the parallel and the serial runs of the same piece produce **identical stems** (section 8.2) |
| `resources.stem_workers` / `STEM_WORKER_GB` (new number) / `MUSICGEN_STEM_WORKERS` | `resources.py`, `render_natural._stem_workers` | The count is cores capped by free memory minus the headroom, never by the piece; it is reused by the post-pass |
| The stem post-pass rewrites each stem **in place** as it is processed (`stems.pop`) instead of building a second dict | `render_natural.build_stems` | Same functions in the same order per stem; it removes one whole extra copy of the piece (1.15 GB peak on `palace_chase`) |
| The breath's two long smoothing kernels run overlap-add instead of direct convolution | `vocal_engine/breath.py:_conv_same` | `oaconvolve` centres `same` exactly where `np.convolve` does; the smoothed control signal agrees to 1.5e-13 (float64 rounding). Only a track with turbulence moves, by 1 float32 ULP (section 8.2) |
| `scripts/helpers/bench_memory.py` | new | Peak-RSS bench for these three cases, so a claim can be re-measured |

Verified: `python3 -m unittest tests.test_mix tests.test_mix_engine tests.test_mix_cache tests.test_mix_context
tests.test_gate_checks tests.test_gate_audio_cache tests.test_gate_band_memo tests.test_immersive_v2
tests.test_immersive_v3 tests.test_hoa_absorption_cache tests.test_lint_coverage` → 173 tests, OK (14 skips,
all of them HRTF/SFZ assets that are not installed in this container).
No gate threshold was changed; `mix_worker_mb_per_second` is a new number in the preset schema with a
starting value (2.0 MB per second of audio per worker) derived from the 180 s measurement above.

---

## 4. Bugs found

Fixed:

1. **The processed-stem cache could be written after placement** (`mix_stems._work`). With in-place
   placement the cached "dry chain" stem would have contained pan and width, so a second deliverable
   would reuse a placed stem and place it again. The write now happens before `_place`.
2. **`hoa._place_all` leaked one temp file per worker on Windows**: `_alloc` returns the path it made,
   and the path was thrown away, so a render past `IN_RAM_BYTES` never deleted its `.hoa` files.
3. **`hoa.result()` copied every harmonic of the field to float64** (`np.asarray(bus[:, c], float)`) to
   convolve it with float32 filters — 36 copies of 63 MB for a 3-minute piece, for no precision.
4. **`true_peak_db` allocated ~11× the master** (float64 cast + ×4 oversampled float64 + full `abs`).
5. **`_validate_export` allocated 4× the delivered file** (float64 read + full `abs`).
6. **`quality_gate.immersive_rows` called `gate_audio.load` without importing the module** (the P1 edit
   replaced a second `sf.read` with the gate's registry and left the name unbound). Found by the first palace
   run of this change set: stage 6 died with `NameError` after the mix had finished.
6. **`active_lufs` allocated ~6× the stem**, once per worker.
7. **`mix_workers: auto` ignored memory** — the documented cause of the 13-14 GB peak.
8. `mix_stems` allocated a third full-length bus to add the reverb tail into.
9. **Stage 4's post-pass kept two copies of the whole piece**: `build_stems` rebuilt `stems` into a *new* dict while the old one was still alive, so `_dc_block`/`repair_clicks`/`_align_onset`/`trim_digital_lead` ran with 2 x 1.6 GiB of stems resident. It now pops each stem, processes it and puts it back.
10. **Stage 4 rendered 31 independent tracks on one sampler, in a loop.** The shared `Synth` was also the lock that made the loop serial: one `sgenerate` at a time for the whole piece, and a formant vocal line (46 s) had every other track waiting behind it.
11. **A failed sampled track stranded its sampler slot, so stage 4 hung instead of reporting the error**
    (`Voice` / `render_track` / `build_stems`). The slot was returned at the end of a successful `render()` and by
    `Voice.__del__`, but a track that raised after `_borrow_synth` (a bad `vibrato.model`, an out-of-range note) kept
    its `Voice` alive through the failing future's traceback, so `__del__` did not run; every track still queued then
    blocked in `_borrow_synth` and the stage never returned the rendering error. The borrow is now a `_Slot` lease that
    `render_track` gives back in a `finally` (idempotent, so the render's own release and `__del__` stay safe), and the
    parallel loop cancels its queued futures when one track fails so the error comes back immediately. Regression test
    `tests/test_humanize_stats.py::RenderPathTests.test_a_track_that_fails_after_taking_a_sampler_slot_returns_it`:
    it fails when `_return_slot` is stubbed out, and a 4-track `build_stems` run (2 workers, one bad `vibrato.model`)
    raises in 0.9 s leaving 0 of 2 slots held (8 vCPU / 16 GB, one run).

Also fixed in the second pass: the gate registry is bounded (it grew without limit across formats and
cues), the master is read and kept once per run instead of three times, a band-ducked bed no longer
builds four full-length curves, and the tap loop no longer allocates three spectra per tap.

Deliberate, not a bug: `gate_audio.Signal` keeps the deliverable in float64 and keeps a float64 mono
mean. The gate's thresholds were calibrated on float64 measurements and a float32 conversion would move
values by ~1e-7 relative — inside every tolerance, but it is a measurement change and needs its own
before/after row-by-row run (P6), not a drive-by edit.

Still open, each in the plan below:

* `reverb_bus` pads the send by the whole IR length and then filters the padded buffer, so the send
  exists twice plus the return. It is bounded (3 × master, once per mix) and not the peak any more.
* The processed stem set, the block-wise chains and the ambisonic field: P2, P3, P4.
* `docs/mix_profile_palace.md` was stale (its "where to cut" items 1 and 2 are implemented in
  `hoa.tap_signals` / `encode_many`); a status line now says so.

---

## 5. CPU: what the profile says, and what is left

From `docs/mix_profile_palace.md` (180.7 s, 31 stems, 21 in the field, order 5, 4-core machine,
1 416.9 s total):

| Stage | Time | Share |
|---|---|---|
| 4 stem render | 155.4 s | 11.0 % |
| 4b stem gate | 47.6 s | 3.4 % |
| **5 mix and master** | **906.9 s** | **64.0 %** |
| 6 quality gate | 289.9 s | 20.5 % |
| 7 packaging | 11.9 s | 0.8 % |

Inside stage 5: `HoaBus.field` 760 s, `_reflections` 715 s, `encode` 265 s (self 131 s), `_late` 59 s,
`apply_lead_carve` 28.5 s, **all loudness metering 10.3 s (1 %)**. Inside stage 6, repeated `sosfilt` in
`band_db` (71 s) and `_band_frames` (30 s) filter the same stems over and over.

So the ranking is unambiguous:

1. **The reflection/encode loop** in the ambisonic bus (≈ half of the whole render).
2. **The gate re-filtering the same audio for different rows** (≈ 100 s).
3. The binaural decode at the end of `HoaBus.result()`: 36 harmonics × 2 ears = 72 overlap-add
   convolutions over the full length.
4. Everything else (lead carve, ducking curves, metering) is small.

What is left to do there, in the order the numbers support, is in the plan below. Anything that changes
the arithmetic must keep the gate rows within 0.01 LU and 0.1 dB (AGENTS.md section 7, rule 17b).

---

## 6. How the rest of the world does this, and what fits a consumer CPU

Researched against the engines that solve the same problem, with the constraint that this skill must run
on a laptop with no GPU and no build step beyond pip.

**Partitioned convolution is the standard answer for long impulse responses.** Torger and Farina's
real-time partitioned overlap-save (the BruteFIR/VST line, 2001) trades latency for cost: the IR is cut
into partitions, one FFT of the input block serves every partition, and each partition costs a complex
multiply plus an inverse FFT, so a long room is `O(log N)` per sample instead of one huge transform
(https://www.angelofarina.it/Public/Papers/164-Mohonk2001.PDF). Battenberg's and Wefers' measurements on
conventional operating systems come to the same conclusion, and non-uniform partitioning (small early
partitions, large late ones) is what modern convolution reverbs and the 2025 MCFX work use to keep both
latency and CPU down (https://ericbattenberg.com/pdf/partconvDAFx2011.pdf). This is exactly the shape of
`hoa._reflections`: many taps of one source, all convolved with short absorption/air responses into one
field. Block processing also fixes the memory: a block of the field is `R × K × 4` bytes (65 536 × 36 × 4
= 9 MB) instead of 1.15 GB.

**What the ambisonic engines do.**
* **libspatialaudio** (VideoLAN, the engine behind VLC's spatial audio) encodes, rotates and decodes HOA
  up to 3rd order, uses AllRAD (virtual loudspeakers panned by VBAP) for irregular layouts and interpolates
  encoder gains to avoid zipper noise on moving sources; it renders objects and ADM/IAMF
  (https://github.com/videolan/libspatialaudio, https://jbkempf.com/blog/2025/libspatialaudio-0.4/). It is
  the best reference for the architecture, but its 3rd-order ceiling makes it unusable as a drop-in for
  this engine's order 5, and it is C++ with a build step.
* **ReTiSAR** (Chalmers) shows that the Python stack is viable for exactly this order of work: pure Python
  with **pyFFTW plus FFTW wisdom** renders binaural HOA up to 8th order in real time on a laptop
  (https://research.chalmers.se/publication/509494/file/509494_Fulltext.pdf). That is the strongest
  argument for an optional FFTW backend rather than a rewrite.
* **Ambitools** (Mainz) reaches the same conclusion from the other side: it recommends **jconvolver** for
  the FIR-heavy part because a FAUST multichannel convolution implementation was too expensive
  (http://www.ifc18.uni-mainz.de/papers/lecomte.pdf).

**FFT backends.** `pyFFTW` is reported at roughly 1.6× on 1024×1024 complex64 transforms and 2–5× on 1-D
transforms against numpy/scipy, and about 10× on an FFT-dominated workload once real transforms, threading
and `FFTW_MEASURE` are used (https://github.com/sacbow/fft-comparison,
https://blog.hpc.qmul.ac.uk/pyfftw, https://slpr.sakura.ne.jp/sikinote/docs/programming/python/fft/).
`scipy.fft` already exposes `workers=`, but it only splits **independent 1-D transforms across a
multi-dimensional array**, not one long transform, so it helps a batched tap transform and not a
single-spectrum call (https://docs.scipy.org/doc/scipy/tutorial/fft.html). `scipy.fft.set_backend` lets a
project swap in `pyfftw`/`mkl_fft` without touching call sites — the clean seam, and `scripts/compute.py`
already owns the "where does the FFT run" decision.

**What is not worth it here.** A GPU path does not help: the field alone is larger than most consumer GPU
memories, and `compute.py` already documents that a GPU render is only a different arithmetic, not a
different sound. `librosa`/`spaudiopy`/`sound_field_analysis-py` are references, not speedups. A Rust/C++
extension would be fastest but adds a build step to a skill whose install story is `pip`.

**Verdict for consumer hardware:** keep numpy/scipy as the correctness path, add an optional FFTW backend
behind `compute.py`, and make the mix and the field **stream in blocks** so peak memory stops depending on
the number of stems or the length of the piece. That is the same conclusion the real-time engines reached
for a different reason (latency instead of RAM).

---

## 7. The plan

Each phase is independently certifiable: gate rows byte-identical in id and level, values within 0.01 LU
and 0.1 dB, `tests/` green, and a before/after number from `bench_memory.py` or the pipeline's `[TIME]`
report. No threshold is loosened; no row is skipped.

### P1 - done in this change set
Per-stem staging, master measurement buffers, worker fit, in-place placement, float32 field pieces, temp
file leak, cache ordering. Peak: −46 % on the master stage, −53 % on export validation, −16 % on staging.

### P1b - done in this change set: stem rendering (stage 4)
Three changes, none of them acoustic: stems render in parallel (a sampler slot per worker, thread per track), the
post-pass runs in the same pool and rewrites each stem in place, and the breath's 30-60 ms smoothing kernels use
overlap-add instead of direct convolution. *Measured* on `projects/palace_chase` (31 stems, 186 s, cold stem cache):
**177.1 s → 92.4 s** at 8 workers (144.6 s at one worker, which isolates the filter change: -32.5 s), peak RSS
3 819 MB serial → 2 659 MB serial, 5 667 MB at 8 workers. 30 of 31 stems are byte-identical; the one that moves
(`chant`, the only track with breath turbulence) moves by one float32 ULP and every stem-gate row is unchanged.
Section 8.2 has the table.

### P2 - the processed set on disk instead of in RAM (next, biggest structural win)
`mix_stems` returns a dict of arrays and `STATE['processed']` keeps it for the gate. At 31 stems that is
2 GB for the copy alone. Store the placed stems in a `(stems, n, 2)` memmap under `<project>/.cache/mix/`
(the same place the chain cache lives), hand the gate memory-mapped views, and let the OS page them.
*Expected*: −1.98 GB at 31 stems, −0 on a small piece. *Risk*: low; the arrays are written once and read
sequentially. *Acceptance*: same gate values, `test_mix_cache` green, bench `mix --stems 12 --seconds 120`
below 1 GB.

### P3 - block-wise stem chains
Process each stem in blocks of `2^16` samples: Pedalboard plugin objects are stateful and chunkable, so
one board per stem is built once and fed blocks; `mono_below` (zero-phase `sosfiltfilt`) and the widen
all-pass need either a linear-phase rewrite with `lfilter` state or a block overlap, and the 1/r and
pan/width laws are per-sample and trivially block-local. *Expected*: the per-stem transient (currently
~5 stem copies) becomes ~1 block regardless of piece length, and the memory-fitted worker count rises
because each worker is cheaper. *Risk*: medium — zero-phase filters must keep their phase behaviour.
*Acceptance*: bit-identical to the block-free path within 1e-6 on a fixture, gate rows unchanged.

### P4 - done: the ambisonic field is streamed, not allocated
`HoaBus.field()` no longer builds an `(n, K)` array. Every source writes row blocks into a `_FieldSink`, and
the sink decodes each block before the next one is written, so the field exists as one 9 MB block per worker
and nothing else. No reflection delay line or late convolver had to become state: the tap signals, the late
tails and the direct sound are still synthesised whole-length by the code that already did it (`tap_signals`
already shares one transform across all taps of a surface, which was the 715 s of the original profile), and
only the place they are written into changed. *Measured*: stage 5 of `projects/palace_chase` 282.1 s → 215.2 s,
peak 9 094 MB → 8 536 MB, every gate row (including `imm_*`) byte-identical. Section 8 has the table and why
the peak moved so much less than the field's size.

### P5 - done with P4: one binaural decode pass per block
`result()` used to run 72 overlap-add convolutions (36 harmonics × 2 ears) over the whole piece. The sink now
transforms each field block once and multiplies it by the `(2, K)` decoder spectra, so the decode is two inverse
transforms per block and one multiply. *Measured*: inside the P4 numbers above; `tests/test_immersive_v3` and
the `imm_*` rows agree to their printed precision with the old path.

### P6 - one decode for the gate (partly done)
Done: one read and one kept copy of the master per run (the gate registry, shared with
`naturalness_check`), and the registry is bounded. Left: `gate_audio.Signal` still keeps the delivered
file in float64 plus a float64 mono mean; per-stem band-filtered signals are still recomputed across
`band_db` / `_band_frames` / the tier-2 rows (profile: 101 s). *Expected*: the gate's working set from
~3 × master to ~1 × master, and ~100 s off stage 6. *Risk*: medium — float64→float32 must not move a row
across a threshold; run the gate fixtures before/after. *Acceptance*: `tests/test_gate_*` green, no row
changes level.

### P7 - optional FFTW backend
`compute.py` gets a third backend: `pyfftw` when it is installed and `render.compute.fft_backend` (or
`MUSICGEN_FFT_BACKEND`) asks for it, otherwise scipy. Use `scipy.fft.set_backend` so no call site changes,
and keep `cache_tag()` including the backend so a cached stem is never served across backends. *Expected*:
1.5-5× on the transform-bound parts (the tap loop, the decode); no change on I/O. *Risk*: low, it is a
dependency decision (wheel available for all three platforms; `requirements.txt` gets it as optional).
*Acceptance*: same samples within float32 rounding, `bench_mix.py` before/after.

### P8 - pipeline-level hygiene
Render only the requested formats (already true since the `--only` work), publish each extra format before
the next one starts (already true), and add `resources.release_memory()` between the gate and the next
format (currently only inside the extra-format loop). Small, cheap, no acoustic effect.

### P9 - only if the profile still says so
A numba or Cython kernel for the per-tap loop, or a small native extension for `tap_signals`. The
partitioned-convolution work in P4 should shrink this need to nothing; do not start here.

---

## 8. The real project, re-rendered and re-profiled

`projects/palace_chase` (31 stems, 184.9 s master, order-5 `palace_room`, 21 sources in the field) driven
through `pipeline` stages 1-6 on this change set. Machine: 8 vCPU, 16 GB RAM, no swap, Python 3.12.3,
numpy 2.5.3, scipy 1.18.1 (`docs/mix_profile_palace.md` was recorded on 4 cores, so the two CPU columns
are not a controlled A/B; the per-function shares are).

Stages driven directly, because the project gate (stage 0) still blocks a certified run on this box: the
research note and `reports/` are absent, the `sso` SFZ set is incomplete, and there is no Linux
`sfizz_render`. SFZ stems were mapped to the nearest GM programs for this run. Memory and time of stages
5-6 do not depend on that mapping (same stems, same lengths, same field); timbre does, so no listening
claim is made.

| Stage | Wall | Peak RSS (whole process) |
|---|---|---|
| 1 ingest | 0.0 s | 113 MB |
| 2 preflight lint | 1.5 s | 117 MB |
| 3 humanize | 0.0 s | 117 MB |
| 4 stems (all 31 from the on-disk cache) | 47.9 s | 3 884 MB |
| **5 mix and master** | **236.2 s** | **9 143 MB** |
| 6 quality gate | 22.4 s | 9 143 MB |
| total | 309.4 s | 9 143 MB (`ru_maxrss`); a 0.25 s tree sampler saw 8 650 MB |

Stage 4 here is a cache read of 1.60 GiB of stems, not a render: the previous rendered figure was 155.4 s.
Stage 5 reads those 1.60 GiB dry stems and ends at 9.1 GB. (This project is order 4, `k = 25`, so its field
is 0.82 GB, not the 1.15 GB of the order-5 arithmetic above; section 8.1 shows what the field actually
contributed to that peak.) P2 (placed set on disk) and P3 (block chains) are the rows left that would move it.

### 8.1 P4, measured on the same project

Both rows are full stage 1-6 runs of the same score on the same 8-core / 16 GB box, through the same `/tmp`
harness (stages driven directly, SFZ tracks on the nearest GM program, stereo master only):

| | Before (P1 code) | After (P4) |
|---|---|---|
| stage 4 (stems) | 70.8 s, cache | 214.3 s, re-rendered (the stem cache key includes the code) |
| **stage 5 (mix and master)** | **282.1 s** | **215.2 s** |
| stage 6 (gate) | 209.7 s | 181.3 s (not attributed: the gate reads one file and its rows are identical) |
| peak RSS | 9 094 MB | 8 536 MB |
| gate rows | 68 rows, 2 FAIL, 28 WARN | 68 rows, 2 FAIL, 28 WARN, **every row identical in status and value** |
| of which `imm_*` | 14 PASS + 1 WARN | the same, to the printed precision |

The two runs did not use the same number of workers: the memory fit allowed 4 before and 8 after, because a
worker no longer carries a partial field. Pinning `render.mix_workers` to 4 for a second after-run gave
**210.3 s and 8 229 MB**: on this piece the extra workers cost 5 s and 0.3 GB, because the stage is
memory-bandwidth bound long before it is core bound.

The peak moved far less than the field's 0.82 GB, and the RSS trace says why. A field past `IN_RAM_BYTES`
(768 MB) was already a `np.memmap` on a file that is unlinked immediately, so the kernel wrote its pages back
and could evict them: it was never 0.82 GB of resident memory, and neither were the workers' partial fields.
Streaming removed 0.5-0.9 GB of resident pages, not four gigabytes. The 8.2 GB that is left is the stem
staging (1.6 GiB dry + 1.6 GiB placed), each worker's tap signals (`SIGNAL_BUDGET`, 256 MB) and its
transients - P2 and then P3, which is what the trace supports and what the plan already said.

Stage 5 under `cProfile`, compared with the same function in `docs/mix_profile_palace.md`:

| Function | 4 cores, before (s) | 8 cores, this change set (s) |
|---|---|---|
| `HoaBus.field` | 760 | 147.7 |
| `_reflections` | 715 | 107.2 |
| `_place_all` | - | 102.4 (of which the worker pool `_run` 91.4) |
| `encode` + `encode_many` | 265 | 28.0 + 26.0 |
| `_late` | 59 | 41.6 |
| `mix_diagnostics.analyse` | - | 40.1 |
| `mixer.lufs` | (all metering 10.3) | 26.9 |
| **stage 5 total** | **906.9** | **236.2** (239.8 under the profiler) |

The reflection/encode loop is still the largest single block (63 % of stage 5, `_reflections` alone 45 %),
which is why P4/P5 in the plan target it and nothing else is worth touching first. The gate stage fell
from 289.9 s to 22.4 s with the shared, bounded `gate_audio` registry; what is left in it is mostly the
band rows still re-filtering the same stems (P6).

Gate result for this run: 56 rows, **1 FAIL**, 15 WARN. The FAIL is `dropout` (a 35 ms hole at
-72.4 dBFS), a property of the piece and of the GM substitution for the SFZ parts, not of this change set;
it was not fixed because the task was the profile. The WARNs are note collisions on `basses`,
`harmonic_resolution_feel` on `horns`, `witek_groove_curve`, `pattern` on bass drum and snare, wide low
end, one `cochlear_roughness` frame, and the mix-diagnostic imbalance/overlap rows. Nothing was
auditioned: no `listen.py` run.

---

### 8.2 Stem rendering (stage 4), before → after

Same machine, same score, same GM substitution as 8.1, `build_stems` driven directly with a **cold** stem cache (a
per-run cache directory, so no row is a cache read) and the full-length stems written out for comparison. The
baseline is the pre-change code at one worker.

| | Before | After, 1 worker | After, 8 workers |
|---|---|---|---|
| `build_stems` wall | **177.1 s** | 144.6 s | **92.4 s** |
| peak RSS | 3 819 MB | 2 659 MB | 5 667 MB |
| render phase (sum of per-track wall) | 136.9 s | 105.7 s | 433 s of thread-wall across 8 threads (contended; the phase itself is ~55 s) |
| post-pass (dc / clicks / onset / trim) | 32.6 s | 30.9 s | - |
| longest track (`chant`, formant voices) | 46.2 s | 28.6 s | - |
| `whisper` | 10.5 s | 5.3 s | - |

Where the time went, and what each change bought:

* **One sampler, one lock.** All 25 sampled tracks were rendered in a serial loop, and `_borrow_synth` held a single
  `Synth`'s lock for the whole of each track, so the sampler was the serialisation. 8 sampler slots + a thread per
  track: 1.57x on 8 cores over the after-serial row. It is not 8x because a third of this stage is Python-level work
  that holds the GIL (the event loop in `Voice.render`, the vocal engine's per-note code); the thread pool overlaps
  the sampler's C work with that bookkeeping, not the bookkeeping with itself.
* **The breath envelope was 18.6 s of one track.** `_turbulence` and `airflow_env` smoothed a 3-minute line with a
  30-60 ms Hann kernel by direct convolution: 2e10 multiply-adds, 3.4 s for one call, 15 calls. Overlap-add does the
  same filter in 0.23 s. `chant` 46.2 s → 28.6 s and `whisper` 10.5 s → 5.3 s.
* **The post-pass held a second copy of the piece.** `stems.pop` per stem: 3 819 MB → 2 659 MB at one worker, with a
  slightly *lower* post-pass time (fewer allocations to fault in).
* **Memory fit.** `STEM_WORKER_GB = 0.5` (measured: +3.0 GB from 1 to 8 workers, i.e. 0.43 GB per extra worker on this
  piece). The count is `cores` capped by `available_gb() - HEADROOM_GB`, so an 8 GB laptop gets fewer workers instead
  of an out-of-memory.

Output check (the reason this is a speed change, not a sound change):

* **30 of 31 stems byte-identical** (sha256 of the float32 samples). `chant` differs by max |Δ| = 1.49e-8 at a peak of
  0.475 (about -150 dBFS relative to peak, one float32 ULP, 0.06 % of samples): that is the overlap-add rounding in
  its breath envelope, and it is the only track with `turbulence_depth > 0`.
* **The parallel and the serial run produce byte-identical stems**, so the pool does not reorder any arithmetic.
* **Stage-4b stem gate, 249 rows, run on both stem sets**: identical statuses and identical detail text (242 PASS,
  3 FAIL, 4 INFO before and after). The 3 FAILs are the pre-existing GM-substitution rows of this project, not
  something this change introduced. The gate itself got faster (41.6 s → 36.0 s, both on 6 threads, because two
  tracks are cheaper).

## 9. Not checked

* Nothing was listened to: no `listen.py` run, no audition. This is a memory and timing audit.
* The full `unittest discover` suite was not run (2 cores, ~95 test modules, and several need the SFZ
  engine and HRTF data). The mix, cache, context, immersive and absorption-cache modules were run: 97
  tests, OK.
* `projects/palace_chase` was re-rendered through stages 1-6 (section 8), but not end to end: stage 0's
  project gate blocks a certified run (no research note, no `reports/`, incomplete `sso`), the SFZ parts
  ran on GM substitutes because there is no Linux `sfizz_render`, and only the stereo master was made, not
  the 7.1.2 deliverable. The 13-14 GB figure for the 7.1.2 mix is the project's own earlier record, not
  something measured here.
* GPU paths (`compute.py` torch backend) were not exercised: no GPU in this container.
* The gain numbers are peak RSS of a process that also imports numpy/scipy/pedalboard (~200 MB floor),
  so compare rows with rows, not with an "engine-only" figure.
* The P4 before/after in section 8.1 is one full run per code version. Stage-5 timing is single-run on a
  shared 8-core box: expect a few percent of drift, and the two runs used different worker counts (the
  4-worker after-run is reported separately for that reason). No `fold.*` row exists in either run, because
  only the stereo master was rendered.
* Nothing was listened to. The streamed decode is checked by the gate rows and the unit tests, not by ear.
* The stage-4 numbers in 8.2 are one run per configuration on a shared 8-core box, with `build_stems` driven directly.
  Stage 4 inside the full pipeline also writes the `stems/` deliverable and runs stage 4b, so its wall time is not
  92.4 s; the stage-4b rows and their timing are reported separately and were identical.
* The mix and the mix gate were **not** re-run after 8.2: only one stem moved, by one float32 ULP, and the stem gate
  that measures the stems themselves reports the same rows. Nothing was auditioned.
* The parallel stem pool scales to 1.57x on 8 cores, not 8x (GIL-bound Python in the event loop). A process pool would
  scale further but has to ship 31 full-length stems back through a pipe; that is not done here.
