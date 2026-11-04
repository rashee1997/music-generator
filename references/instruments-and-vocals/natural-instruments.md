---
title: Natural instrument sources
summary: Which sampled or modelled source to use for a given sound, and the range and playing limits of each.
tags: [instrument, range, articulation, soundfont, samples, realism]
load_when:
  - choosing a source for an instrument
  - writing notes outside a comfortable range
---

# Natural instrument sources: what to use for which sound

Real instruments have irregularities that a formula does not give for free: attack noise, body resonance, uneven
partials, and a slightly different sound on every note. The pipeline plays **recorded instrument samples** (a
General MIDI SoundFont) and adds performance on top. For sounds the bank does not have, it uses a cloned instrument
from the user's own recording. Choose the source from this table.

| Need | Best source | How |
|---|---|---|
| Piano, strings, winds, brass, guitar, bass, harp, mallets, choir, orchestral and pop drums | **SoundFont samples** (GeneralUser GS via `tinysoundfont`) | `"instrument": "cello"` (names: `python3 scripts/soundbank.py --list`) |
| Instrument the user can record (sitar, oud, a voice, a toy, a tabla loop) | **cloned** instrument | `clone_instrument.py analyze ...`, then `"instrument": "clone:path"` |
| Music-box, kalimba, glass or bell colours | GM presets: Music Box (10), Glockenspiel (9), Vibraphone (11), Marimba (12), Tubular bells (14) | `"instrument": "marimba"` etc. |
| Traditional timbres (sitar, bansuri, santoor, oud, qanun, ney, erhu, guzheng, pipa, koto, shamisen, kora, charango, bouzouki...) | a cloned instrument for the real sound; otherwise the **150+ named stand-ins** in `references/scoring/world-music.md` section 4 (`"instrument": "oud"` plays a nylon guitar with microtonal bends) | say the approximation in the reply |
| Tabla, dhol, darbuka, riq, taiko, surdo, tamborim, cuica, cajon, djembe, palmas | the 77 world drum names (`soundbank.py --list`), mapped to GM percussion keys | stylised, not recordings |
| Realistic singing with words | not possible here | say so; use choir or "oohs" as texture (GM 52/53) |
| Sound effects (whooshes, risers, UI clicks) | use the GM percussion and the hit points in `compose.py`; for a custom riser use `direct.add_line` with a reverse-feeling phrase | synthesis of effects is out of scope now |

## SoundFont route in detail

- `scripts/soundbank.py` finds `$MUSICGEN_SF2`, `assets/soundfonts/`, `~/.cache/music-generator`, or downloads
  **GeneralUser GS** (about 32 MB, free for music including commercial use; by S. Christian Collins). If the network
  is blocked it falls back to the small TimGM6mb bundled with `pretty_midi` (usable, noticeably duller). Tell the user
  which bank was used.
- Better banks the user may supply: MuseScore_General, FluidR3, Arachno, SGM-V2.01. Set `MUSICGEN_SF2=/path/file.sf2`.
- The synth is `tinysoundfont`. It plays velocity layers and loops, plus MIDI volume, expression, pan, sustain pedal
  and pitch bend. It has **no built-in reverb or chorus**; `mixer.py` adds a convolution reverb.
- Every sustained instrument (strings, winds, brass, voice, pads) gets **one MIDI channel per note**, so each note has
  its own vibrato, expression swell and small detune. Struck and plucked instruments (piano, harp, mallets, guitar)
  share a channel and use the sustain pedal.

### Which GM presets are strong, usable or weak (GeneralUser GS)
- **Strong**: Grand Piano (0), Nylon/Steel Guitar (24/25), Acoustic/Finger Bass (32/33), Cello (42), Violin (40),
  Slow/Fast Strings (49/48), Harp (46), Flute (73), Oboe (68), Clarinet (71), French Horns (60), Trombone (57),
  Marimba/Vibraphone (12/11), Timpani (47), Orchestral kit (128:48), Standard/Room/Jazz/Brush kits.
- **Usable**: Choir and Voice Oohs (52/53), Trumpet (56), the sax family, Celesta, Glockenspiel, Music Box, pipe organ,
  accordion, stylised kalimba, koto and sitar.
- **Synthy by nature** (GM synth leads 80-103, synth bass 38-39): fine for electronic genres. Avoid them when the
  brief says natural, organic or acoustic.
- Layer two instruments for realism: cello + viola for a fuller line; piano + soft strings for a pad; flute + a quiet
  clarinet an octave lower.

### Playable ranges (stay inside them; outside, samples sound stretched)
violin G3-E6 (55-100), viola C3-E5, cello C2-E5 (36-76), double bass E1-C4 (28-60), flute C4-C7 (60-96; weak low,
shrill above C7), oboe Bb3-G6, clarinet D3-C7, bassoon Bb1-Eb5, trumpet F#3-Bb5, horn B1-F5, trombone E2-Bb4, tuba
D1-F3, harp C1-G7, nylon/steel guitar E2-E5 (40-84), electric/acoustic bass E1-G3 (28-55). `compose.py` clamps the
lead to a safe range.

### Arrangement rules that make samples sound like a band
1. One clear lead; everything else under it (the mixer sets melody -3 dB, pads -11 dB).
2. Give each instrument its own register: bass 40-200 Hz, chords 200-1000 Hz, lead 500-4000 Hz, air above 6 kHz.
3. Voice chords with smooth motion (voice leading); avoid doubling the third in the bass.
4. Different pulse per layer (pad = whole bars, piano = 8ths, drums = 16ths) so layers interlock instead of stacking.
5. Not everything plays all the time. Enter and leave (the `min` intensity of a layer decides when it enters).

## Rendering quality (what the sampler adds or loses)

| Key (mix preset `render`) | Default | What it does |
|---|---|---|
| `oversample` | 2 | renders the SoundFont at that multiple of the rate and decimates with a polyphase filter. tinysoundfont resamples with linear interpolation, so a transposed note leaves images above its own band; measured on GeneralUser GS the share of energy above 15 kHz rose 11 dB from C4 to C7 on the flute and 19 dB on the violin at 1x |
| `mechanics` | on | the table `scripts/mechanics.py` reads: filter band, length and level for the noise a mechanism makes at note-on and note-off, per class (`bowed`, `wind`, `plucked`, `keys`, `drum`). A track picks its class with `mechanics_class` in the instrument preset |

Per note the renderer also adds an alternating stroke dip on bowed notes (a bow change is audible) and vibrato with
jitter and shimmer rather than a perfectly periodic LFO (healthy sustained phonation sits near 0.5 % jitter and 3-5 %
shimmer). Articulation is an instrument preset value: `{"overlap_ms": 30, "gate": 1.0, "release_ms": 180}`.

What none of this fixes: a single-layer GM patch cannot brighten with velocity the way a second recorded layer would,
there are no real release samples or legato transitions, and tinysoundfont exposes no sample offset, so a repeated note
still plays the same sample (varied only by detune, attack, stroke and mechanism noise). This makes a bank sound
*played*; it does not make it a sampled orchestra.

## Quality honesty

Sampled GM with humanization and a proper mix is a large step up from math synthesis. It is still a library sound.
Never claim it is indistinguishable from a real orchestra. Say what was done (real samples, humanized, mixed) and
what `listen.py` reported. Offer the upgrade paths: a better SoundFont, the user's own recordings cloned into
instruments, or the MIDI and stems for a person to finish in a DAW.

Sources: GeneralUser GS (mrbumpy409/GeneralUser-GS); TinySoundFont; General MIDI program list; Lemo-Opuscar
`core/audio/sampler.py` (velocity-layer picking, round-robin, grain-extended sustains, the reason for darker soft notes).

---
