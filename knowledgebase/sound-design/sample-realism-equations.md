---
id: sample-realism-equations
title: Why a SoundFont part sounds like MIDI, and the per-note laws that fix part of it
domain: sound-design
status: unverified
sources: [gilbert_myers_brass_spectral_enrichment_ioa, campbell_brass_timbre_ioa, fletcher_sanders_1966_violin_vibrato, ccrma_violin_vibrato_project, prame_1994_singer_vibrato, wing_quartet_asynchrony_pmc3928944, string_trio_asynchrony_frontiers_2014, knutsa_onset_transient_times, guettler_bowed_attack, dannenberg_2006_midi_velocity, flat_io_velocity_curve, soundonsound_sample_realism, ask_audio_midi_orchestras]
used_by: [scripts/family_dsp.py, references/data/presets/families/families.json, scripts/realism_report.py, AGENTS.md]
updated: 2026-11-28
---

> **Not verified.** The pages behind the sources were not opened: each figure is what a search result said about its page, and
> every number the skill uses from it is a starting value until measured on an audited bank (`scripts/soundbank_audit.py`) or a
> rendered stem (`scripts/realism_report.py`, `velocity_response`).

# Why a SoundFont part sounds like MIDI

A GM SoundFont has one sample layer per instrument and plays velocity as plain gain, so a pp note and an ff note have the same
spectrum, the same attack and the same shape; only the level differs (measured on GeneralUser-GS: velocity 127 to 60 is -6.5 dB
with the spectral centroid unchanged at x1.000, `dsp.enhance_sf2_dynamics`). Real instruments change timbre with level and
every take differs. Practitioner guidance says the same: velocity layers, crossfades, round robins, legato transitions and
expression data are what libraries add (Sound On Sound, Ask.Audio, Splice). The skill cannot add recorded layers; it adds the
laws below to the rendered stem, from the written velocity of each note.

## 1. Brightness follows level (implemented: `velocity_brightness`)

- **Fact (per search result):** the share of high-frequency energy rises with playing level in all brass instruments (Gilbert and
  Myers, Institute of Acoustics); the spectral centroid is strongly correlated with perceived brightness and rises with the
  energy-arousal of a tone. No explicit centroid-versus-level equation was found.
- **Law used (starting value):** the cutoff of a note is the h-th harmonic of its own fundamental, h following velocity, so a
  low note and a high note get the same relative brightness:

      f0(p)  = 440 * 2 ** ((p - 69) / 12)
      h(v)   = h_lo * (h_hi / h_lo) ** (v ** gamma),      v = velocity / 127
      fc     = clip(f0 * h(v) * 2 ** N(0, jitter_oct), fc_min, fc_max)

- **Why a filter alone fails:** a sample that holds no overtones cannot be brightened by filtering (a GM horn's attack centroid
  measured 334 Hz). A hard note therefore first goes through a saturator driven by velocity,
  `y' = tanh(D(v) y / s) s / D(v)` with `D(v) = 1 + drive_k v ** gamma`, which generates the harmonics a louder note really has.
- **The level is restored.** A saturator compresses its loudest peaks hardest; unrestored it turned a 14 dB loud-over-soft gap
  into -2.4 dB. The saturated copy is scaled back, moment by moment, to the dry stem's short-time level (40 ms), so only the timbre
  moves (13.4 dB left in the same test). `tests/test_velocity_brightness.py` pins both.
- **Jitter** `jitter_oct` (starting value 0.10 octave): two takes of one note differ in brightness, as a round-robin set does.
- **Measured effect** (`realism.velocity_response`, brightness of a note's attack against its written velocity once pitch is
  removed, floor 0.30, the literature's loudness figure 0.62): cello -0.12 to 0.77, violin 0.03 to 0.48, flute 0.08 to 0.75,
  horn -0.16 to 0.41, piano 0.17 to 0.35 on a 32-note line with random velocities on GeneralUser-GS.

## 2. A soft note rises slower (implemented: `velocity_attack`)

- **Per search result:** transient durations of 50-90 ms are generally perceived as musically acceptable (Knutsa onset-transient
  times); bow acceleration allowed for a clean start scales with bow pressure, so a quieter start is a slower one; lower pitches
  take longer to build; the build-up of one simulated A3 was about 18 ms (not general). No pp-versus-ff table in ms was found.
- **Law used (starting value):** `ramp_ms(v) = ms_hard + (ms_soft - ms_hard) * (1 - v) ** power`, with `ms_soft` 45 (bowed), 30
  (reed), 20 (brass), 40 (voice), `ms_hard` 3-4, `power` 1.5. A sample's own attack cannot be made faster, only slower, so the rise is
  an added raised-cosine ramp (`dsp.soften_onsets` with one length per onset) and an onset over a still-sounding note is left alone.
- **Not done:** the pitch dependence (a low note builds slower). No figure to scale it by was found.

## 3. Vibrato (already in the engine: `bloom`, `mechanics`)

- **Per search result:** a typical violin vibrato is about 6 Hz with about 30 cents extent, ranging 10-60 cents (Fletcher and
  Sanders 1966; CCRMA); singers sit at 5.5-6.7 Hz with about +-60 cents, violinists in the same recordings used the same rate and a
  smaller extent, and the rate rises by a couple of Hz over the last cycles of a long note (Prame 1994); wind and bowed vibrato is
  under half a semitone either side. The existing bloom (vibrato depth ramping up after the onset) follows the delayed-vibrato
  practice; the end-of-note rate rise is not modelled.

## 4. Ensemble timing (a lever, not a default)

- **Per search result:** between-player onset asynchrony has an SD of tens of milliseconds: a string trio 49 ms at about 79 bpm, a
  wind trio 32 ms, two string quartets 24 and 28 ms at 157 bpm, falling with tempo (Wing and colleagues; Frontiers in Psychology
  2014). Listeners without training hear the difference in the variability and judge how "together" a performance sounds.
- **In the engine:** `ensemble_expand` defaults to `spread_ms` 10 (a peak offset, about 6 ms SD), two to five times tighter than
  those measurements. That is a likely part of a "too tight, too clean" section. It is left at its default, because changing it
  changes every render (AGENTS.md section 11, rule 5); a score or preset states `ensemble.spread_ms` 20-35 for a string section as a
  starting value and the section rows say whether it is too loose.

## 5. Velocity to level (context)

- No standard curve exists. Csound's `ampmidid` uses a squared curve (Dannenberg, "The Interpretation of MIDI Velocity", ICMC 2006);
  a forum figure `L(dB) = 40 log10(V / 127)` is the same law (amplitude proportional to the square of velocity) and is unconfirmed.
  A linear map gave 9.5 dB between velocity 5 and 15 and 0.8 dB between 100 and 110 (Flat.io). A GM SoundFont's own curve is whatever
  the bank holds; measure it with `soundbank_audit.py` and do not assume.

## 6. What is not fixed by this

Legato transitions between notes (a sampled legato layer), recorded round-robins, real room-and-bow noise per note and a real
multi-layer bank. A free SoundFont cannot sound like a recorded orchestra; say so in the report. The measure above is a starting
point: it says brightness follows velocity, not that the result sounds human.

## Sources

- Gilbert and Myers, spectral enrichment of brass (Institute of Acoustics): https://www.ioa.org.uk/system/files/proceedings/15._m_campbell.pdf
- Stevenson and Campbell, non-linear propagation and the timbre of brass: https://www.ioa.org.uk/system/files/proceedings/s_stevenson_dm_campbell_effects_of_non-linear_propagation_on_timbre_of_brass_instruments.pdf
- CCRMA, violin vibrato project (Fletcher and Sanders 1966 figures): https://ccrma.stanford.edu/~pdelac/151/project.html
- Prame, vibrato extent and rate of singers (via the search summary of the MCG vibrato paper): https://mcg.uva.nl/mcg-2023/papers/dhat-2/dhat-2.pdf
- Wing et al., optimal feedback correction in string quartet synchronization: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3928944/
- Frontiers in Psychology 2014, onset asynchrony in ensembles: https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2014.01115/full
- Knutsa, onset-transient times: https://knutsacoustics.com/files/Onset-transient-times-Rev.2.pdf
- Guettler, bowed-string attacks: https://viennatalk.mdw.ac.at/papers/Pap_01_20_Guettler.pdf
- Csound ampmidid (Dannenberg 2006): https://csound.com/manual/opcodes/ampmidid/
- Flat.io, music dynamics playback update: https://blog.flat.io/music-dynamics-playback-update/
- Sound On Sound, how virtual instruments work: https://www.soundonsound.com/techniques/how-virtual-instruments-work
- Ask.Audio, how to make MIDI orchestras sound more realistic: https://ask.audio/articles/how-to-make-midi-orchestras-sound-more-realistic
