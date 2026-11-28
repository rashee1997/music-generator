---
# Not verified: read as search-result text only (see the note under the header)
id: soundfont-velocity-and-realism
title: SoundFont velocity, brightness and orchestral realism
domain: sound-design
status: partly-sourced
sources: [https://sfzformat.com/opcodes/xfin_hivel, https://sfzformat.com/opcodes/fil_veltrack, https://sfzformat.com/opcodes/seq_length, https://forum.renoise.com/t/crossfading-between-velocity-layers/57284, https://homepage.univie.ac.at/christoph.reuter/unterwegs/Timbre2018_siddiq_reuter_czedik_knauf.pdf, https://en.wikipedia.org/wiki/Spectral_centroid, https://www.polyphone.io/en/forum/help/872-velocity-to-cutoff, http://www.synthfont.com/modulators.html, https://www.polyphone.io/o/en/forum/support-bug-reports/401-v2-1-issues-with-default-velocity-to-fc-mod, https://www.un4seen.com/forum/?topic=19546.0, https://www.github.com/FluidSynth/fluidsynth/wiki/SoundFont3Format, https://simplesoundbank.com/guides/best-free-soundfonts/, https://flypaper.soundfly.com/produce/4-techniques-realistic-orchestral-strings/, https://www.sonarworks.com/blog/learn/how-to-bring-your-string-mock-ups-to-life, https://www.pro-tools-expert.com/production-expert-1/how-to-improve-realism-in-orchestral-mock-ups]
used_by: [AGENTS.md, references/instruments-and-vocals/soundfont-realism.md, scripts/render_natural.py]
updated: 2026-11-21
---

> **Not verified.** The pages above were not opened in the session that wrote this file; each line is what a search
> result said about its page, and several pages are forum posts, vendor posts or tutorials. A number is `per search
> result` (a source states it) or `starting value` (a working figure, not calibrated). Cite a primary source (the
> SoundFont 2.04 specification) before presenting any of them as established.

# SoundFont velocity, brightness and orchestral realism

## 1. How a SoundFont is meant to make a soft note darker

| Finding | Basis |
|---|---|
| SF2 defines a default modulator that lowers the filter cutoff for soft notes; its default amount is -2400 cents, and makers override it with larger negative values (-3600, -4800, -6000) | per search result (Polyphone forum, SynthFont) |
| One forum user describes velocity 0 multiplying the cutoff by 0.132 and a velocity near 18 leaving it unchanged | per search result (one forum post; not checked against the specification) |
| The original definition had a secondary switch source that SoundFont 2.04 removed, so players differ; one maker disables the default modulator in every instrument and adds a custom one | per search result (Polyphone forum) |
| A list of the modulators BASSMIDI and Virtual MIDI Synth implement exists; it says nothing about TinySoundFont | per search result (un4seen forum) |
| Early SF2 fonts faked brightness with velocity-switched layers whose low layers cut more treble; they sound out of calibration on other engines | per search result (Polyphone forum) |
| A sample recorded at one velocity needs the cutoff modulator; velocity splits with different cutoffs are unnecessary when the engine applies it | per search result (SynthFont) |

Measured in this repository (not a search result): TinySoundFont maps velocity to gain only. On GeneralUser GS, velocity
127 to 60 is -6.5 dB with the spectral centroid unchanged (see the comment on `dsp.enhance_sf2_dynamics`). So the
modulator is not applied here, and a soft note differs from a hard one in level only.

## 2. What the SF3 format is

| Finding | Basis |
|---|---|
| SF3 is an unofficial extension of SF2, made for MuseScore, that stores samples as Ogg Vorbis; a flag bit in the sample header marks it | per search result (FluidSynth wiki, Polyphone) |
| It is much smaller (a 148 MB Fluid soundfont became 20 MB) and lossy, so unsuited to archiving; there is no formal specification | per search result |
| MuseScore General is MIT-licensed, 206 MB as SF2 and 38 MB as SF3; it is a general-MIDI bank, not an orchestral library | per search result (simpleSoundbank) |
| The `tinysoundfont` package listing says it loads SF2, SF3 and SFO files | per search result (PyPI listing; not loaded in this repository) |

## 3. Orchestral realism, from library documentation and tutorials

| Finding | Basis |
|---|---|
| Velocity shapes how a note begins; CC1 and CC11 shape its evolution. CC11 is usually volume and CC1 usually crossfades dynamic layers | per search result (Soundfly, Sonarworks; the mapping depends on the library) |
| Each part on its own MIDI channel lets each player have its own controller moves | per search result |
| Combine articulations (legato for a line, staccato for rhythm); add timing humanisation | per search result |
| Reverb is treated as the most important effect; convolution reverb is preferred for an orchestral space; reverb narrows the dynamic range of a dry patch | per search result (Production Expert) |
| No free SF2 with confirmed round robins was found; a community SF2 conversion of Sonatina Symphonic Orchestra exists but the original is SFZ | per search result (simpleSoundbank) |

## 4. Working figures for this repository

None of these comes from a source. Change them to the instrument and say so.

| Quantity | Starting value | Why it is a starting value |
|---|---|---|
| `velocity_timbre.points` for a bowed or blown part | [[25, 1800], [60, 3200], [100, 6500], [127, 9500]] Hz | follows the direction in section 1 (soft is darker) and the 2.1 kHz to 4.1 kHz corner range the existing `dynamic_tilt` comment gives; not calibrated |
| `velocity_timbre.points` for a struck or plucked part | [[25, 2500], [60, 4500], [127, 9500]] Hz | plucked and struck sounds keep more top end at low velocity; a working figure |
| `velocity_timbre.bands` | 4 | each band is one render of the track; four steps are small enough that no note jumps audibly between neighbours, an unmeasured judgement |
| Layering a short attack over a sustained patch | one track of `pizzicato` or `timpani` under `strings`, or `staccato` horn under a pad | the technique in AGENTS.md section 4b item 6; no measurement |

## 5. What the engine does with them

`velocity_timbre` on a track or an instrument preset plays the notes in `bands` groups by written velocity and low-passes
each group at the cutoff the `points` give for that group's mean velocity. It is the missing modulator, per note, from
numbers in the preset. It is not a real second sample layer: the attack character and the harmonic series of the sample
stay the same, only the top end moves.

## 5. How an SFZ library makes velocity real, and what this repository copies (read as search-result text only)

| SFZ mechanism | What a search result said | What `velocity_timbre` does with it |
|---|---|---|
| velocity zones (`lovel`/`hivel`) | each region plays inside a velocity range; `xfin_*`/`xfout_*` fade a layer in or out across a range so layers blend (sfzformat.com; Apple Logic sampler guide for the crossfade idea) | `zones` (2-16): a note's layer depends on its own velocity only, never on how the rest of the part is written |
| dense layers need no crossfade | a Renoise forum user: with many layers the samples are similar enough for the step not to be abrupt (one opinion) | 12 zones step the cutoff by about two semitones over velocity 25-127; no crossfade is built |
| velocity to cutoff (`fil_veltrack`) | the cutoff changes with note velocity, in cents, -9600 to 9600 (sfzformat.com) | `points`: [velocity, low-pass Hz], log-frequency interpolation |
| velocity to attack (`ampeg_vel2attack`) | attack time = ampeg_attack + ampeg_vel2attack x velocity / 127 (a community reference page, not the sfzformat.com page) | `attack_ms`: [velocity, onset ramp ms]; the renderer's onset fade, longer for a soft note |
| round robin (`seq_length`, `seq_position`) | the player counts per region and wraps at seq_length; one region per sample (sfzformat.com, KVR forum) | not copied: a GM bank has one sample per key; per-note random detune and timing are the only variation (`per_note_channels`) |
| release samples (`trigger=release`) | piano release samples should consider how long the note was held (a forum post) | not copied |

Why softer is darker (physical basis, per search result): a 2018 Timbre-conference study of five nonpercussive instruments at pp, mf and ff
found sounds ordered by dynamic level in almost every case and a correlation of 0.62 between dynamic level and spectral centroid; a patent
citing Askenfelt and Jansson reports the spectral cut-off frequency of a piano string rising with hammer velocity; Strong and Clark (cited in a
1966 paper) put the attack transient first for identifying nonpercussive tones. The cutoff and attack numbers in a preset stay `starting value`
until a SoundFont is measured; the engine does not read them from a source.

Velocity scale: a score writes velocity as 0-1 or as 1-127. Before this section the preset's 0-127 points were read against a 0-1 velocity as
velocity 1, which put every note of such a part on the darkest cutoff. A part whose largest velocity is 1.0 or less is now read as 0-1.
