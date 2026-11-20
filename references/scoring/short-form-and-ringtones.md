---
title: Short-form pieces and ringtones
summary: Hook, structure, phone-speaker translation, looping and delivery for a ringtone, alert or jingle.
tags: [ringtone, alert, jingle, hook, loop, short-form, phone, mobile, notification, catchy]
load_when:
  - the brief is a ringtone, an alert, a jingle or any piece meant to be recognised in seconds
  - a piece must loop and be heard on a phone speaker
---

# Short-form pieces and ringtones

A ringtone is heard many times, in noise, on a small speaker, by someone who did not choose the moment. It has four jobs,
in this order: be recognised in the first seconds, interrupt, survive repetition, and loop without a seam. The facts and
the starting values behind this file are in `knowledgebase/genre-and-feel/short-form-functional-music.md`; every number
here is a starting value from it, to be changed to the brief and said so.

## 1. Decide, then write the sheet

Run the craft pass first (`references/workflow/director-craft.md`). For a ringtone the sheet says:

| Field | Write |
|---|---|
| `medium` | `ringtone` |
| `purpose` | where it plays, how long it rings, and whether it loops |
| `piece_type`, `focus` | `melodic`, `melody`: the tune is the subject |
| `pulse` | `steady`: the listener must hear a beat in the first bar |
| `loudness_lufs`, `true_peak_max` | `-14`, `-1.0` as a start |
| `delivery.sample_rate` | the rate the engine renders at |
| `expression.theme` | the hook as a shape with its rhythm cell and its `variation_plan` |
| `avoid_sounds` | sharp 2-5 kHz peaks, a sustained sub-bass, a long reverb tail |

## 2. The hook

- It starts inside 3 s, usually on the first beat, played by the instrument with the clearest attack.
- Three to six notes, one leap among steps, a rhythm cell with a syncopation, inside an octave so a listener can hum it.
- It is stated in three moves: **state** it, **answer** it (the same shape landing on the tonic or the fifth), **vary** it
  (one change: the last interval, the rhythm, the register). Then it returns, always recognisable, never twice the same.
- It is not buried by a bed: during a statement, nothing else carries a line.

## 3. Structure of a 60 s loop

At 120 BPM in four-four a bar is 2 s, so thirty bars are one minute. One new thing arrives roughly every 8 s: a part, a
register, a colour, a rhythm. The plan below is a starting shape for the sheet's `sections`.

| Section | Bars | Job | Energy (0..1) |
|---|---|---|---|
| Hook | 1-4 | the motif alone on one plucked or struck instrument, then answered | 0.50 |
| Hook, joined | 5-8 | the motif again with the pulse and the bed entering | 0.60 |
| Passing | 9-16 | the tune passes to a second tradition's instrument; a counter-line and a new colour arrive | 0.65 |
| Lift | 17-22 | higher register, the fullest layers, a rhythmic fill into the peak | 0.80 |
| Breath | 23-24 | thin: the hook alone or with the bed, a deliberate gap before the return | 0.40 |
| Return | 25-28 | the hook at full strength with the best variation | 0.75 |
| Turnaround | 29-30 | the harmony leads into the first chord; the tail rings into bar one | 0.45 |

## 4. The phone speaker

Carry the tune and the pulse between roughly 300 Hz and 5 kHz. A bass part reaches a phone through its harmonics, so write
it high enough (or use an instrument rich in upper partials) and do not rely on the fundamental. Keep sub-bass out of the
mix, keep the image mono-compatible, keep the 2-5 kHz region smooth (that is where the ear is most sensitive and a
sharp transient is most tiring), and keep the dynamic range narrow: a quiet passage is lost in a noisy room.

## 5. The loop

Set `loop_seconds` in the score to the length of the piece: the engine folds the tail past the loop point back onto the
start with a crossfade, so there is no fade-out and no gap. Write the last bars so the harmony leads into the first chord,
and let the last notes ring into the tail. Judge it with `short_form_report.py --loop`: the step across the seam against
the steps inside the piece, and the level across it.

## 6. Judge and deliver

1. The gate: `pipeline.py` with 0 FAIL.
2. `scripts/helpers/short_form_report.py out/master.wav --score scores/<title>_score.json --loop`: the seam, the energy in
   the phone band, the onsets in the first seconds, how often the opening shape returns, and whether the density moves.
3. `scripts/helpers/arc_report.py` against the section energies in the sheet.
4. The director's second review (`director-craft.md` section 5). Say what was not heard.

Deliver the certified WAV. An MP3 for a phone is a manual step (`scripts/helpers/compress_mp3.py`) and is reported with its
bitrate.
