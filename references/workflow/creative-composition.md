---
title: Creative composition
summary: Writing a piece by hand: form, motif development, harmony and the checks before rendering.
tags: [compose, motif, form, harmony, melody, development]
load_when:
  - writing a custom score
  - a motif has to develop rather than repeat
---

# Creative composition: write music, do not fill in templates

`compose.py` genres and moods are **scaffolds**. Each one repeats a one-bar pattern under a chord loop. Used alone they
give a competent, generic loop, and every piece comes out sounding like the last one (a march, a loop). A music
director does not stop there. Treat the preset as a rough sketch, then compose the piece that this request needs.

## 1. The rule

> Before the first note, state **the idea**: one sentence that makes this piece different from a generic piece in
> the same genre. Then write the notes yourself (custom score) or take the preset draft and change it until the idea
> is audible.

Ideas that work are specific and small: "the melody is a question that only gets answered at the very end",
"the beat starts as a heartbeat and gains a limb every 4 bars", "the tabla never plays the downbeat until the
last chorus", "a 7-beat cycle hidden under a 4/4 melody", "the bridge is the same tune played backwards".

## 2. Patterns that sound like a template (and what to do)

| Template habit | Why it sounds fake | Do this instead |
|---|---|---|
| Every bar of drums identical | No human plays a bar twice the same; the ear tires by bar 4 | A 2- or 4-bar drum phrase: the pattern, a variation, the pattern, a turnaround. Ghost notes. A dropout. A fill into each section |
| Kick on every beat, snare on every 2 and 4, hats straight | The march / oom-pah | Leave beats out. Put a kick on an off-beat. Move the snare late (lazy) or leave beat 4 empty. Change the hat pattern in the chorus |
| One chord per bar, a 4-chord loop for the whole piece | Predictable harmony | Change the chord rhythm: two chords in a bar, a chord held for 2 bars, a borrowed chord (bVI, iv in major), a pedal bass under moving chords, a suspension that resolves late |
| Chord figure identical every bar (the same arpeggio) | A music box | A figure that develops: add a note, drop the top, invert the voicing, move the arpeggio start by a beat each bar |
| Melody notes all on the beat, all the same length | The grid | Start phrases off the beat (pickup), tie across the bar line, one long note against a run, rests that are as important as the notes |
| Melody that steps up and down the scale | Exercise, not tune | A leap then a step back, a repeated note used as a hook, a rhythm that repeats while the pitches change |
| Same loudness throughout | Flat | A quiet start, a real peak, a breath before it. Dynamics move by 0.3 or more over the piece |
| Every layer starts together | No story | Enter one layer at a time; remove the drums for 4 bars; bring the bass in late |
| Phrases always 4 bars, always AABA | Square | 3-bar or 5-bar phrases, an extension, a bar of silence, a cut-off phrase |
| The ending is a ritard on the tonic every time | Cliche | End on the unexpected: an unfinished phrase, a drone alone, the first motif returning |

## 3. A method that produces something with identity

1. **Motif first.** Write 3 to 7 notes with a rhythm you could tap. The rhythm matters more than the pitches. Check that you could hum it.
2. **Develop, do not repeat.** Each return changes one thing: sequence it up a step, invert it, stretch the rhythm (augmentation),
   squeeze it (diminution), change the last note, put it in a new register or instrument, or take away its first note.
   See `theory.vary_phrase` for a ready version.
3. **Form with a surprise.** Intro, A, A', B (contrast), A'' (changed), outro is a base. Add one unexpected thing: the tune
   in the bass, a silent bar, a key lift, a double-time section.
4. **Rhythm with a displacement.** Keep one pattern but shift it by an eighth every 4 bars; or put a 3-against-4 cross-rhythm
   in one layer (`world.cycle_notes` writes odd cycles).
5. **Harmony with one non-obvious chord.** Pick the bar where the story turns and put the borrowed chord there.
6. **Texture arc.** Decide which layer enters or leaves at which bar before you write notes. List it: bar 1 pad only,
   bar 5 + bass, bar 9 + melody, bar 17 drums out, bar 21 everything.
7. **Imperfection by intent.** Rubato at phrase ends, a push before a hit, a note held slightly long. `humanize` does the
   small stuff; you decide the large stuff.
8. **Cross-tradition fusion done properly.** Take the rhythm cycle and scale from one tradition and the harmony or
   production of the other, keep one bass. Do not stack two full genre presets (two basses, two drum kits).
   Example: a Tamil film melody in Kharaharapriya over a half-time trap kit, thavil only on the turnarounds.
   The full method (one pulse, one drone, one bass, one lead at a time, register layout, in time versus in layers) and
   the country sub-styles are in `genre-fusion.md`.

## 4. Use the presets as raw material

- `compose.py --genre X --variation 0.7` for a first sketch; raise `variation` for looser, 0 for strict.
- Take the preset score, then `direct.py`: `remove_track` the drums and `add_line` your own; `copy_track` a layer to a new
  instrument; `set_arc` for a bigger build.
- Mutate a drum bar yourself: from `theory.groove_bar` / `world.GROOVES` copy the hits into a list, then edit them per bar.
- Mix presets only by taking pieces (the groove of one, the scale of another), not by stacking whole genres.

## 5. Check for copy-paste before rendering

```bash
python3 scripts/pattern_audit.py score.json            # flags: identical bars, no dynamics, grid-bound melody, flat velocity
```
Treat each flag as a question. A drone is meant to be flat; a minimalist ostinato is meant to repeat. Anything else that
is flagged should be changed, or you should be able to say why it stays. The same command also reports the six
acoustic rules (voicing/strum, choked plucks, machine-gun runs, phase-locked flams, low mud, dry tracks in a wet
score); see `SKILL.md`. Then render and listen (`listen.py`).

## 6. Writing the reply

State the idea, not just the settings: "The idea: the hook enters on the off-beat and the drums only play the downbeat in
the last chorus." Then list what the audit said, what you changed, and what you did not hear.

## 7. What these tools still cannot do

The renderer plays General MIDI samples. The templates are patterns, not understanding. The audit measures repetition
in notes, not whether a tune is good. A person has to listen to judge taste.

---
