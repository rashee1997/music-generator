---
title: Cloning an instrument from audio
summary: What to measure from a reference recording, in what order, and what the clone can and cannot promise.
tags: [clone, sample, timbre, spectrum, pitch, formant, reference audio]
load_when:
  - the brief asks to sound like a recording
  - a preset needs a measured character
---

# Cloning an instrument from a recording

Goal: the user has a sound (a sitar, a family oud, a recorder, a toy piano, their own humming, a pan lid)
and wants to play new melodies with it. Use `scripts/clone_instrument.py`.

## Choose the method

| You have | Method | Result |
|---|---|---|
| A recording with SEVERAL different notes, one at a time (scale, phrase, a few sustained notes), clean | `--mode sampler` | Most lifelike. Real samples, velocity layers from loud/soft takes, re-pitched <= ~4 semitones, long notes extended with phase-aligned grains. |
| ONE clean sustained or plucked note | `--mode harmonic` | Re-synthesises any pitch from the measured spectral envelope, inharmonicity (stiffness), noise colour, attack, decay and vibrato (the idea behind DDSP, done with classical DSP). Characterful, a bit "synthetic". |
| Arbitrary audio reference, multi-timbral recording, continuous slides, or polyphonic chords | 6-Stage Reverse-Engineering | Complete algorithmic deconstruction into pure code and Acoustic Fingerprint JSON (see below). |
| Wants a neural clone (more detail) | outside this sandbox | Name the options (below), offer to prepare the training audio and the score; the neural model needs a GPU. |

---

## The 6-Stage Reverse-Engineering Pipeline & Universal Acoustic Fingerprints

For mathematical derivations, YIN/pYIN equations, LPC formant filters, CQT salience matrices, and pure-Python code, consult the master knowledge base:
 [`knowledgebase/sound-design/audio-cloning.md`](../../knowledgebase/sound-design/audio-cloning.md).

When reverse-engineering an instrument or reference audio file without human ears, follow the **6-Stage Deconstruction Pipeline**:
1. **Continuous Microtonal Pitch Extraction:** Sub-sample accurate $f_0(t)$ tracking using pYIN, CMNDF, and parabolic peak interpolation; splits static notes from dynamic *Gamaka/Meend* bends.
2. **Spectral Modeling Synthesis (SMS):** Separates audio into a *Deterministic Layer* (harmonic peak tracking and phase alignment) and a *Stochastic Residual* (breath, bow friction, attack clicks), paired with *LPC Formant Poles* estimating body resonance.
3. **Polyphonic & Harmonic Extraction:** Constant-Q Transform (CQT) and pitch-salience matrices detect non-12-TET chord voicings and bass inversions.
4. **Groove & Micro-Timing Profiling:** Spectral flux Onset Detection Function (ODF) calculates the `micro_shift_ms` vector, swing asymmetry, and velocity dynamics.
5. **Spatial & Room Deconvolution:** Schroeder backward integration calculates the $T_{60}$ energy decay curve, direct-to-reverberant ratio (DRR), and stereo panning azimuth ($\theta$).
6. **Universal "Acoustic Fingerprint" JSON:** Outputs a standardized machine-readable recipe capturing the instrument's exact physical parameters for zero-loss reproduction.

---

## How to record (tell the user - this matters more than any algorithm)

1. Quiet room, microphone 10-30 cm from the instrument, no music/voice behind it, no reverb or effects (add reverb later).
2. 44.1 kHz or higher, WAV/FLAC, no clipping, peaks around -6 dB.
3. Play **single notes** with a gap between them, each held 1.5-3 s (plucked: let ring).
4. Cover the range: a note every 3-4 semitones (minor third) is ideal; every 5-6 is the limit. Include lowest and highest comfortable notes.
5. Two dynamics (soft and normal; three if possible). The tool assigns velocity layers from loudness.
6. Two takes of the same note are welcome (used as round-robin alternates).
7. For bowed/blown instruments also record 1-2 long notes (6 s) so sustains can be extended cleanly.

## Commands

```
python3 scripts/clone_instrument.py analyze rec.wav --name my_oud --mode sampler --out clones/
python3 scripts/clone_instrument.py play clones/my_oud --notes 48 52 55 60 --out demo.wav     # quick audition file
python3 scripts/clone_instrument.py sfz clones/my_oud                                         # .sfz for a DAW sampler
```
Then in a score: `{"name":"oud","instrument":"clone:clones/my_oud","role":"melody","notes":[...]}` - the cloned instrument goes through the same humanizer, mixer and master as every other track (but has no per-note vibrato; the vibrato of the original samples is what you get).

## What the sampler does (so you can debug it)

1. **YIN pitch tracking** (de Cheveigne & Kawahara 2002) over 2048-sample frames, 512 hop.
2. **Segmentation**: frames with confidence > 0.75 and within 45 dB of the loudest; note start boundaries are refined using **spectral-flux transient onset detection** (as in `naturalness_check.py`) with a 5 ms pre-roll to preserve the true physical attack of the pluck, strike, or bow scrape. Notes shorter than 0.15 s are dropped.
3. Each note is stored with its fractional MIDI pitch (so a slightly flat instrument stays in tune with itself), loudness and brightness; velocity layers are the loudness rank mapped to 0.35-0.95.
4. **Playing**: choose the zone with the smallest `|semitone distance| + 4 |velocity distance|`; round-robin among near ties; re-pitch with polyphase resampling; soft notes are low-passed (`fc = 18000 (v/0.8)^2.2`); notes longer than the sample are extended by cross-correlation-aligned grains from the stable tail with 100 ms raised-cosine crossfades; a quadratic release fade ends every note.
5. Honest limits: re-pitching shifts the formants (a re-pitched cello starts to sound like a different-size cello beyond ~4-5 semitones); the tool warns when your recording has gaps wider than ~8 semitones.

## What the harmonic clone does

Finds f0 (YIN), runs high-resolution 8,192-point FFT extraction (`extract_harmonic_partials`) to isolate the top 16 harmonic partials ($f_1 \dots f_{16}$) that rise $\ge 12\text{ dB}$ over the median noise floor, measures peak amplitudes of the first up to 60 partials, fits inharmonicity `B` from `f_n = n f0 sqrt(1 + B n^2)`, builds a smooth log-frequency spectral envelope (so timbre follows pitch like a real body would), estimates the noise floor between partials, the attack time, the decay rate (sustained if < 8 dB/s) and any vibrato (3.5-8.5 Hz). New notes: additive sines at the stretched partial frequencies + coloured noise, shaped by the attack/decay; louder notes are brighter.
Checked on a stand-in recording (a SoundFont cello treated as the user's recording) at notes that were NOT in it: sampler pitch error < 1 cent and spectral centroid within 2-17 % of the real thing; harmonic clone pitch error < 9 cents but spectral centroid off by 10-50 % - so expect the harmonic clone to be the rougher of the two. These are measurements, not listening tests. Real microphone recordings with room noise will do worse; always audition.

## Neural options (for the user's own GPU / later)

- **DDSP**: differentiable harmonic-plus-noise synthesiser + reverb driven by f0 and loudness; trains on a collection of recordings of one instrument; the best-known approach to "timbre transfer / instrument cloning".
- **Few-shot DDSP**: a pre-trained model adapted to a new instrument from about 16 s of audio.
- **TokenSynth**: zero-shot instrument cloning from about 5 s of reference audio using a codec language model.
- Sample-based commercial/open samplers (sforzando + the exported `.sfz`) are the practical bridge: use `clone_instrument.py sfz` and load into any DAW.
Do not promise these results here; offer to prepare the data.

---

## Separating a mix first

To clone from a full song, extract the stems with `scripts/extract_pipeline.py` (see `references/workflow/extraction.md`), then clone from the stem you want.

---

## Ethics / rights

Clone instruments the user owns or recorded themselves. Do not clone a sample library they only licensed for use as-is, and do not clone a specific real person's voice without consent. Say so briefly if a request looks like that.
