---
title: Music direction, revision half
summary: Cue order, picture moments, adaptive music, revision levers, earshot and delivery.
tags: [direction, revision, hits, adaptive, delivery, levers]
load_when:
  - revising a cue that misses a target
  - building picture moments or adaptive music
---

# Music direction: revision half

This continues [`music-direction.md`](music-direction.md) after section 2.12.
## 3. Decide in the order listeners weigh cues

Mode is the strongest cue for happy and sad; tempo, register, dynamics, articulation and timbre follow, and the cues
add up, so one pointing the wrong way is not cancelled by the rest. Decide in that order and make them agree. For a
mixed feeling (bittersweet, anxious hope), take the main feeling's mode and tempo and borrow one cue from the other;
do not average.

Rows and thresholds for melodic contour, interval entropy, note lengths, breath gaps, voice leading, groove pocket
and ostinato repetition: see `references/mixing/quality-gate.md` §3e, and write to them instead of fixing failures
later.

## 4. Build the picture's moments (hits, risers, silence)

- **Hit:** a kick or taiko with its highs cut, layers stacked low to high (sub, boom, metal or orchestral percussion),
  each EQ'd separately, then distortion, EQ, compression and reverb; the transient lands on the frame.
- **Riser:** pitch or filter climbing over several bars, faster and louder, peaking on the cut.
- **Silence before the hit:** end the riser, leave a short gap, then hit; the gap makes the hit land harder.
- **Braam:** a long, loud, low brass note (C1-C2) stacked in octaves (C0, C1, C2), pitched down, distorted and
  reverbed, on cuts that mark a transition.
- **Sub drop:** a low layer under the hit, EQ'd separately, felt more than heard on a large system.

In a score these are a `rise` at `t`, a `silence`, and an `impact` on the exact beat; `compose.py` hit points do this.
For custom placement use `direct.add_line` (a stab or fanfare) or `direct.add_pulse` (the grid under it).

## 5. Adaptive music (games, interactive pieces)

A game hands timing to the player.

- **Vertical layering:** one base loop runs always; stems fade in or out on events, and a muted stem keeps looping in
  sync so it can return at any point.
- **Horizontal re-sequencing:** intro, loop and outro sections switch into one another, with fades to soften cuts.
- Combine them: loopable stacked stems that switch sections and add layers. Sync transitions to a bar or beat, set
  tempo and meter once, keep the first beat after a transition clean, and write loops of one to two minutes.

Direction: one key and one tempo for every state, three intensities with
`compose.py --intensity 0.3 / 0.6 / 0.95 --loop`, a sheet per state, and `listen.py` on each.

## 6. Revision levers: what to change when a target misses

Change one lever at a time, render, listen. Each row starts with the most likely cause.

| Target misses | First lever | Second lever | Code |
|---|---|---|---|
| It reads upbeat when the brief was not | check `meta.mood_notes`: if it says "no mood word recognised", name the feel. Then `energy` and `space` | add `slow`/`sparse` words, or lower `energy` one step | `compose --emotion`, `--energy`, `--space` |
| The mood is right but the room is wrong | `space`: `large_hall` for landscape or "reverb mix", `dry` for intimate | lower the reverb return (`mix.reverb_return`) instead of the room | score `room`, `mix` |
| `feel` loses to `avoid_feel` (forced choice under 35 %) | **mode**: major for epic, triumphant, hopeful; minor/dorian for sad, tense | tempo up 10-20 BPM for energy, down for calm | `compose.py --mode major --bpm 104` |
| Forced choice is close (35-50 %) | a bigger **loudness arc** (quiet start, loud peak) | add a **fanfare or a hook** on the reveal | `direct.set_arc`, `direct.add_line` |
| `avoid` word in top 3 readings | take out the layer or the harmony that reads as the wrong feel | slow the tempo or lower the register | `direct.remove_track`, `direct.set_gain` |
| `pulse` clarity under 0.15 but `steady` wanted | add a kick on every beat from the start | make the drums `tight`, keep the tempo map flat | `direct.add_pulse` |
| `pulse` high but `none` wanted | remove drums and bar-locked ostinatos | let the phrases rubato | `direct.remove_track` |
| `tempo` out of range (double/half counts as passing) | set the score tempo | check the score bpm, not a render estimate | `direct.tempo`, `compose --bpm` |
| `instruments` not named (e.g. taiko) | add a track for the instrument, or raise its gain 3-6 dB | move it up a register | `direct.add_line`, `direct.set_gain` |
| `mode` mismatch with a weak key (r under 0.6) | do not trust the key estimate; check the sound, then decide | change the mode only if the feel check also fails | `compose --mode` |
| `hits` missing onsets | put the hit on a beat (`hit_points` snap to half-beats) | add a sub layer under the hit (+3 dB on the impact) | `compose` hit points, `direct.add_line` |
| `loudness` off | `master.lufs` in the score | a very dynamic piece may not reach a target; accept it | score `master` |
| `true_peak` hot or `clipping` | lower the master input 2-3 dB | lower the loudest stem's `gain_db` | score `master`, `gain_db` |
| `length` off | `duration_s` / bar count | a ring-out adds 2-5 s; trim the file or accept and say so | `compose --duration` |
| An SFZ part reads as a sample player (same attack every note, flat sustain) | patch per articulation + `art` on the notes (2.9) | a written `dynamics` arc, then move an exposed sustained solo to the GM path | `sfz` block, score `dynamics` |

Gate rows, thresholds and levers: see `references/mixing/quality-gate.md`.

Two rules that stop revision from going round in circles:

1. **A second change to the same target that does not move it means the lever is wrong.** Try another lever from the
   same row, or the row below it.
2. **A FAIL on `feel` is a question, not a verdict.** earshot is a model: listen yourself, or tell the user what the
   numbers say and ask them to listen.

## 7. What earshot can and cannot hear

earshot listens with CLAP (text-audio similarity) and AST (AudioSet tags) plus measurements: a second opinion, not a
human ear.

**Use it for:** the forced choice (the wanted word must win more than half; `listen.py` reports FAIL when an opposite
wins), the ranked readings (genre, mood, instruments), pulse clarity, tempo, key, onsets and an A/B comparison.

**Its limits:** mood labels are wrong about one time in five; readings are not exclusive (a piece can read triumphant
and sad at once); tempo can read double or half, and with no pulse (clarity under 0.15) there is none to trust; key
estimates with r under 0.6 are weak; it cannot judge taste, melody, lyrics, cultural fit or whether a synth is real,
and an instrument it does not name is not proven absent.

## 8. Delivery

Deliver the master WAV and the MIDI, the filled direction sheet, the `listen.py` report in plain words (which targets
pass, which still check, what earshot heard), one or two named variations if the brief was open, and one line on what
was not checked (taste, the real instruments, how it sits in the final video). Situation recipes, each with a brief,
the direct calls and a sheet: `references/workflow/scene-recipes.md`.

Do not say "it sounds like an orchestra" or "it is natural". Say what the sheet asked for, what the report found, and
what is left.
