---
id: low-end-and-virtual-bass
title: Where a theatrical low end goes missing, and the virtual bass that lets headphones hear it
domain: sound-design
status: unverified
sources: [aes_virtual_bass_22055, patent_us9794688_virtual_bass_frequency_domain, ntu_virtual_bass_synthesis, dafx2020_virtual_bass, waves_maxxbass_manual, aes_bass_management_lfe_13021, wikipedia_bass_management, dolby_lfe_usage, tvtechnology_bass_management, designingsound_bass_management]
used_by: [scripts/mix_engine/mastering.py, scripts/preflight_lint.py, scripts/realism_cinema.py, references/data/master_targets.json, AGENTS.md]
updated: 2026-11-28
---

> **Not verified.** The pages behind the sources were not opened: each statement is what a search result said about its page.
> Every number the skill uses is a starting value until measured on a rendered master (`scripts/realism_report.py`, `sub_weight`).
> Nothing was found on how headphones or binaural renders reproduce 20-60 Hz.

# Where a theatrical low end goes missing

## 1. The failure that was measured (Highway Pursuit)

- The stems carried the bass: kick, taiko, timpani and basses held most of their power at 20-80 Hz. The master kept 22 dB less of
  that band than the stems summed, and its 20-40 Hz share was -55 dB.
- Cause: the project's mix preset set `mastering.highpass_hz` 105 with `highpass_order` 4, a 24 dB/octave high-pass. A fourth-order
  Butterworth-style cascade takes a note of fundamental f down by `10 * log10(1 + (fc / f) ** (2 * order))` dB: 6 dB at 105 Hz and 25 dB at
  55 Hz (an A1 on the tuba), and a bass written at 33 Hz is gone. The shipped default is 24 Hz, first order.
- How it spread: the figure was written into a Night Pursuit preset script, copied into Night Pursuit Cinematic, Palace Chase and
  Highway, and `rca.py` advised writing the part an octave up. `realism.sub_weight` should have said so and did not: it needed the
  master to be "thin" (under -34 dB) as well as 6 dB down, and a master at -32 dB passed with a 31 dB loss.
- Fixes: the sub row warns on the loss alone (`realism.sub_loss_max_db`); `preflight.master_highpass` fails a pitched bass or drone
  part that the master high-pass removes, before a render; `rca.py` points at the preset, not the notes.

## 2. Virtual bass (the missing fundamental)

- **Per search result:** a listener infers a low pitch from its upper harmonics when the fundamental is absent; virtual-bass systems
  use this to make small and flat-panel loudspeakers (and headphones, which cannot give the body vibration of a sub) read as having
  bass. The usual method passes the bass band through a nonlinear function, which makes harmonics, and mixes the result back; a phase
  vocoder or harmonic transposition is the alternative; a commercial example (MaxxBass) removes everything under a chosen point,
  creates harmonics above it and lets the two be mixed in any proportion. Research notes that good quality is still hard and that simple
  nonlinear methods smear transients.
- **In the engine (`mastering.virtual_bass`, off unless a mix preset enables it):**

      s = band-pass(x, source_hz = 30..90)
      h = band-pass(tanh(drive * s / peak(s)) + 0.35 * (s / peak(s)) ** 2, harmonics_hz = 80..240)
      x' = x + h * (short-time rms(s) / short-time rms(h)) * 10 ** (gain_db / 20)

  The harmonics are scaled to the level of the sub moment by moment, so they follow the bass and carry no level of their own (a
  quiet second gives quiet harmonics, `tests/test_master_lowend.py`). The sub itself is left alone (within 0.5 dB). Starting values:
  `drive` 4, `gain_db` -6.
- **A cue judged on headphones needs it more than one judged on a sub.** Say in the report that a free SoundFont's kick and timpani are
  samples, and that a virtual bass adds harmonics, not weight.

## 3. A theatrical tone

`mastering.tones.theatrical` is a broad low shelf (+3 dB at 70 Hz) and a gentle high shelf (+1 dB at 9 kHz), starting values chosen
for a chase cue; the master picks it with `master.tone`. It costs headroom (the converge loop and `crest_floor_db` say so).

## 4. How a cinema handles bass, and why home playback differs

- **Per search result:** bass management sends the low-frequency content of any channel to the loudspeakers able to play it; the LFE
  channel carries a +10 dB gain in the monitoring chain (an AES abstract); a cinema dub stage is mixed without home bass management;
  TV Technology warns that all of a cinema's bass can overwhelm a consumer. A stereo or binaural deliverable has no LFE channel, so
  its low end has to be in the main channels at a level that does not clip the limiter.

## 5. What is not known

How a binaural (HRTF) render treats 20-60 Hz (measured head data is band-limited), an equal-loudness correction for low
frequencies at headphone level, and a published level for a trailer's sub. Measure the master (`sub_weight`) instead of
assuming.

## Sources

- AES, virtual bass system (e-library 22055): https://www.aes.org/e-lib/download.cfm/22055.pdf?ID=22055
- US patent 9794688, addition of virtual bass in the frequency domain: https://patents.google.com/patent/US9794688
- NTU, virtual bass synthesis: https://www3.ntu.edu.sg/home/ewsgan/VBS.html
- DAFx 2020, virtual bass (Aalto): https://acris.aalto.fi/ws/portalfiles/portal/51973173/Eloi2020_Virtual_bass_DAFx2020.pdf
- Waves, MaxxBass manual: https://www.sweetwater.com/store/detail/MaxxBass--waves-maxxbass-plug-in
- AES e-library, bass management and the LFE gain: https://www.aes.org/e-lib/browse.cfm?elib=13021
- Wikipedia, bass management: https://www.wikipedia.org/wiki/Bass_management
- Dolby, LFE usage: https://professional.dolby.com/en-in/gaming/downloads/lfe-usage
- TV Technology, 5.1 bass management: https://tvtechnology.com/opinions/51-bass-management
- Designing Sound, bass management and your subwoofer: https://designingsound.org/2014/05/13/big-noise-go-boom-bass-management-and-your-subwoofer/
