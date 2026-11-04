# Scene recipes: direction sheet, build, edits, listen

Each recipe gives the direction (what the piece must do), a starting brief for `scripts/compose.py`, the edits a
director would make with `scripts/direct.py`, and the sheet to listen against. Copy the sheet to a file, fill in
the seconds for your picture, and run:

```bash
python3 scripts/compose.py --brief brief.json --out score.json
python3 -c "import json,sys; sys.path.insert(0,'scripts'); import direct; s=json.load(open('score.json')); ...; json.dump(s, open('score2.json','w'))"
python3 scripts/render_natural.py score2.json --out cue.wav
python3 scripts/listen.py cue.wav --direction sheet.json
```

**Status.** The trailer recipe (section 1) was built and listened to end to end in this session. The others are
starting points written from the research in `music-direction.md`; run them through `listen.py` before you deliver
and treat the first render as a draft. Recipes 11-14 (motivational, adventure, slow reverb, fusion under a mood) were
run through `compose.py` and `quality_gate.score_checks` in this pass: 0 FAIL on the score, but they have not been
listened to with earshot.

---

## 1. Trailer or product reveal (tested)

**Direction.** Quiet start, a hard hit at 24 s, silence at 38 s, then a reveal with a brass fanfare. Feel: epic
and triumphant. Major mode. A steady pulse under the whole cue, so it drives. Not sad, not calm.

**Brief** (`brief.json`):
```json
{"emotion":"triumphant","genre":"orchestral","duration_s":45,"bpm":104,"mode":"major","arc":"build",
 "intensity":0.8,"hit_points":[{"t":24,"type":"impact"},{"t":38,"type":"silence"}],"seed":2}
```

**Edits** (`direct.py`), with beats = seconds x bpm / 60:
```python
import json, sys; sys.path.insert(0, 'scripts'); import direct
s = json.load(open('score.json'))
direct.add_pulse(s, start=0, gain_db=-6, dyn=[[0, .45], [20, .7], [24, 1.0], [40, .8]])   # kick every beat
direct.add_line(s, 'fanfare', 'trumpet', at_beat=66,                                       # 66 beats = 38 s
                phrase=[(0,.5,70),(.5,.5,74),(1,.5,77),(1.5,.5,74),(2,1.5,70),(3.5,.5,74),(4,2.0,77)],
                gain_db=-3, reverb=0.2, pan=0.15, dyn=[[0,.6],[66,1.0]])
json.dump(s, open('score2.json','w'))
```

**Sheet.** `templates/direction_sheet.json` (feel epic + triumphant, avoid sad + calm, instruments taiko + brass +
strings, pulse steady, 96-112 BPM, major, -16 LUFS, hits at 24 and 38).

**What happened (this session, three steps).**

| Version | Feel: epic | Feel: triumphant | Pulse | Result |
|---|---|---|---|---|
| Earlier epic render, before this rework (minor-leaning preset) | sad wins the forced choice | sad wins | none | FAIL: the old epic preset is aeolian/dorian, so it reads sad |
| `triumphant` preset, major, 104 BPM, seeds 1-3 | 32-42 % | 18-36 % | 0.04-0.05 | FAIL: no steady grid; brass and strings heard |
| + kick on every beat (`add_pulse`) | 65 % | 33 % | 0.49 | FAIL on triumphant only |
| + brass fanfare on the reveal (`add_line`) | 63 % | 45 % | 0.53 | no FAIL; CHECK: triumphant close, no taiko track in the score, +4.5 s over |

The same last version rebuilt from `direct.py` alone gave epic 55 %, triumphant 46 %, pulse 0.51, and no FAIL. Its
remaining CHECKs are honest: the score has no taiko track at all (the drums are an orchestral kit: kick and floor tom),
so earshot had nothing to name; the render runs about 5 s over the 45 s target because of the ring-out; "triumphant"
is close to the sad reading; and the key estimate fell to F minor at r 0.49, which is too weak to act on. Next
levers, in order: add a taiko track (GM "taiko") on the hits, a higher melody in the last 8 bars, and trim the tail.

**Since then.** `epic` is now the major heroic preset by default, and `dark_epic` is the minor one. A mood's own
percussion (taiko, march, heartbeat, half-time) now enters at intensity 0.35, so a 45 s build gets its drums; the
earlier render had none. Research and the genre tables are in `genres-and-moods.md`.

## 2. Sad voice-over underscore (documentary, memoir, explainer with feeling)

**Direction.** Minor or dorian, 56-70 BPM, a solo piano or piano and cello, long notes, wide quiet dynamics, no
drums. The music sits 18-20 dB under the voice, so it must be steady and simple. Hits: none.

**Brief:** `{"emotion":"melancholy","genre":"piano","duration_s":60,"bpm":62,"mode":"minor","arc":"fall",
"intensity":0.35,"voiceover":true,"seed":3}`

**Edits:** usually none. Lower the cello `gain_db` if the piano is too loud under speech.

**Sheet:** `feel: ["sad","melancholic"]`, `avoid_feel: ["happy","triumphant"]`, `instruments: ["piano","cello"]`,
`pulse: "none"`, `tempo_bpm: [56, 70]`, `mode: "minor"`, `loudness_lufs: -20`, `true_peak_max: -2`.

**Mix under the voice:** `python3 video-mixer/video_program_mix.py --voice narration.wav --music cue.wav --out final.wav`
and check the report (the music should sit at least 15 dB under the speech). If the cue has to follow picture,
`python3 scripts/video_score.py --video source.mp4 --project <dir>` does the whole job.

## 3. Calm explainer, focus or product demo (lo-fi, soft)

**Direction.** Major or pentatonic, 84-96 BPM, soft piano and a brushed kit, even dynamics, nothing that competes
with speech. A steady, unobtrusive pulse. Not energetic.

**Brief:** `{"emotion":"focused","genre":"lofi","duration_s":60,"bpm":90,"mode":"major","arc":"steady",
"intensity":0.4,"voiceover":true,"seed":5}`

**Edits:** `direct.add_pulse(s, gain_db=-12, humanize='natural', floor_tom_on_beat3=False, accent=0.5, soft=0.35)`
for a brush-like grid under the piano.

**Sheet:** `feel: ["calm","focused"]`, `avoid_feel: ["energetic","angry"]`, `instruments: ["piano"]`,
`pulse: "steady"`, `tempo_bpm: [84, 96]`, `mode: "major"`, `loudness_lufs: -18`.

## 4. Tense thriller or suspense cue

**Direction.** Minor or phrygian with a tritone or a flat second, 70-100 BPM or no pulse at all, low drone, tremolo
strings, sparse high notes, a rise then silence then an impact. Unpredictable accents.

**Brief:** `{"emotion":"tense","genre":"dark","duration_s":30,"bpm":84,"mode":"minor","arc":"tension_release",
"intensity":0.7,"hit_points":[{"t":20,"type":"rise"},{"t":22,"type":"silence"},{"t":23,"type":"impact"}],"seed":4}`

**Edits:** `direct.set_gain(s, 'strings', -4)`; add a low drone with `direct.add_line(s, 'drone', 'contrabass', at_beat=0,
phrase=[(0, 30*84/60, 36)], gain_db=-6)` for the held low note. (`add_line` makes each note at velocity 0.9; for a drone that is
loud, so lower `gain_db` as needed.)

**Sheet:** `feel: ["tense","suspenseful"]`, `avoid_feel: ["calm","happy"]`, `instruments: ["strings"]`,
`pulse: "none"`, `tempo_bpm: [70, 100]`, `mode: "minor"`, `hits_at: [23.0]`.

## 5. Joyful or hopeful end card (sting, 8-15 s)

**Direction.** Major, 112-124 BPM, bright kit, a strong tonic at the end that rings out. Hopeful, not cheesy.

**Brief:** `{"emotion":"joyful","genre":"pop","duration_s":12,"bpm":118,"mode":"major","arc":"build",
"intensity":0.8,"hit_points":[{"t":11,"type":"impact"}],"seed":6}`

**Sheet:** `feel: ["joyful","uplifting"]`, `avoid_feel: ["sad","tense"]`, `pulse: "steady"`, `tempo_bpm: [110, 126]`,
`mode: "major"`, `duration_s: 12`, `hits_at: [11.0]`.

## 6. Adaptive game loop (three intensity states)

**Direction.** One key, one tempo, identical loop length, three states. Calm = pad and piano. Medium = adds bass and
a soft kit. High = adds brass or strings and a fuller kit. Each state must read as its own feel and must sit in
time with the others so they crossfade.

**Build:** three briefs differing only in intensity, same seed and bpm, `"loop": true`:
```bash
for i in 0.3 0.6 0.95; do python3 scripts/compose.py --emotion hopeful --genre orchestral --bpm 100 --mode major \
  --intensity $i --loop --duration 60 --seed 9 --out state_$i.json --render state_$i.wav; done
```

**Sheets:** `state_0.3` feel calm, `pulse: "none"`; `state_0.6` feel hopeful, `pulse: "loose"`; `state_0.95` feel
triumphant, `pulse: "steady"`. Run `listen.py` on each. Check that the calm state does not read tense, and that
the high state does not read sad.

**Crossfade:** fade out one state and fade in the next at a bar line (see `music-direction.md` section 5).

## 7. Jingle or logo sting (3-6 s)

**Direction.** A short, memorable figure in a major key, a single strong final chord that rings out, no loop.

**Brief:** `{"emotion":"triumphant","genre":"orchestral","duration_s":5,"bpm":120,"mode":"major","arc":"build",
"hit_points":[{"t":4,"type":"impact"}],"seed":7}`

**Edits:** `direct.add_line(s, 'logo', 'trumpet', at_beat=0, phrase=[(0,.5,72),(.5,.5,76),(1,.5,79),(2,2.0,84)])`.
(Beats: at 120 BPM a beat is 0.5 s, so this phrase runs about 3 s.)

**Sheet:** `feel: ["triumphant","memorable"]`, `pulse: "none"`, `duration_s: 5`, `hits_at: [4.0]`.

## 8. Calm, sleep, meditation

**Direction.** 55-65 BPM or no pulse, pads and a soft piano or harp, no drums, very slow dynamics, long rests.
Loop optional.

**Brief:** `{"emotion":"calm","genre":"ambient","duration_s":120,"bpm":60,"mode":"major","arc":"sparse",
"intensity":0.2,"loop":true,"seed":8}`

**Sheet:** `feel: ["calm","peaceful"]`, `avoid_feel: ["tense","energetic"]`, `pulse: "none"`, `tempo_bpm: [52, 66]`,
`loudness_lufs: -20`.

## 9. Playful, children's, quirky

**Direction.** Major or mixolydian, 100-124 BPM, staccato, pizzicato, marimba, woodblock, a few chromatic passing
notes. Stops and starts.

**Brief:** `{"emotion":"playful","genre":"pop","duration_s":40,"bpm":112,"mode":"major","arc":"wave","seed":10}`

**Sheet:** `feel: ["playful","bouncy"]`, `avoid_feel: ["sad","calm"]`, `instruments: ["marimba","pizzicato"]`,
`pulse: "steady"`, `tempo_bpm: [104, 122]`.

## 10. Traditional and devotional idioms (raga, maqam, folk)

**Direction.** The tradition decides the scale, the ornaments and the instruments. Use the tradition's own scale
and the closest instrument, and say plainly what is an approximation.

**Start from `references/world-music.md`.** It has 69 scales (35 with real microtones), 167 world instrument names,
90 drum names, 67 grooves, 37 rhythm cycles and 79 ready genres for India, the Arabic world, Turkey, Persia, Greece,
China, Japan, Korea (K-pop, trot), Indonesia, Rio and Brazil, Latin America, the Caribbean, Africa, the Andes, Europe
and the Americas. Brief: `{"genre": "tarab", "mode": "maqam_sikah", "key": "D", "duration_s": 60}`.

**What the tools can and cannot do.**
- Instruments are stand-ins: the SoundFont has 128 sounds, so an oud is a nylon guitar, an erhu a violin with wide
  vibrato and slides. They are stylised, not authentic. Name that in the reply.
- A recording the user owns can be cloned (`scripts/clone_instrument.py`), and that is the honest route to a real
  sitar, oud or santoor timbre. A SoundFont with the real instrument also works (`MUSICGEN_SF2`).
- Quarter-tones and just-intonation intervals are real: each note carries a cents offset that the renderer plays as a
  pitch bend (measured: -48 to -50 cents for a quarter-flat note). Slides into notes are `gl`.
- earshot has no vocabulary for raga or maqam authenticity. It can tell you the instrument and the feel, not whether
  the ornaments are correct. Ask the user, or someone who knows the tradition, to judge that by ear.

**Sheet:** the same as any other, plus `notes: "raga <name> / maqam <name>; instrument approximated with <GM name>;
authenticity not checked by earshot"`.

## 11. Motivational film, launch or brand film

**Direction.** Confident, not triumphant and not a shout. Major, 76-98 BPM, a theme that steps upward, a
layer-by-layer build, energy around 0.65. Avoid: epic/war (taiko, brass fanfare), sad, and "generic corporate 120".

**Brief:** `{"emotion":"motivational","genre":"cinematic","duration_s":45,"seed":7,"arc":"build"}`
`motivational` resolves to `hopeful`. Add `"genre":"corporate"` for a corporate film: the mood then wins the tempo
2:1 (102 BPM in this pass, not corporate's 126) and the note says so.

**Sheet:** `feel: ["motivational","uplifting"]`, `avoid_feel: ["epic","sad"]`, `energy: 0.65`,
`tempo_bpm: [76, 98]`, `mode: "major"`. Edits: usually none; if it reads cute, lower the keyboard sparkle and raise
the low strings 2 dB.

**Verified in this pass:** `compose.py` + `quality_gate.score_checks` at 45 s: 0 FAIL, 85 BPM, 29 notes/bar.
Not yet listened to with earshot.

## 12. Adventure, travel or quest (a journey, not a battle)

**Direction.** Major or lydian, 84-104 BPM, open fifths, a half-time pulse, strings + horn + flute, space around the
notes. It opens outward instead of attacking. Avoid: taiko, war drums, 120+ BPM, minor.

**Brief:** `{"emotion":"adventure","genre":"orchestral","duration_s":60,"seed":7,"space":"large_hall","arc":"build"}`
`adventure` is its own preset (not `epic`), so it does not inherit the trailer recipe.

**Sheet:** `feel: ["adventurous","wonder"]`, `avoid_feel: ["epic","tense"]`, `instruments: ["strings","horn","flute"]`,
`energy: 0.6`, `space: "large_hall"`, `tempo_bpm: [84, 104]`, `mode: "major"`.

**Verified in this pass:** 45 s, 0 FAIL, 85 BPM, half-time kit. Not yet listened to with earshot.

## 13. Slow, reflective, reverb-washed ("slow reverb mix")

**Direction.** The words are the arrangement: `slow` takes the tempo to 0.86 and the energy down 0.15, `reverb`
gives a `large_hall` and a reverb return of 1.5. The mood defaults to `dreamy` when no mood word is present.
Few notes, long tails, nothing busy. Avoid: a drum groove that pushes, staccato beds.

**Brief:** `{"emotion":"slow reverb mix","duration_s":60,"seed":7}` -> `dreamy`, 64 BPM, `large_hall`,
`mix.reverb_return 1.5`, about 9 notes/bar.

**Sheet:** `feel: ["dreamy","reflective"]`, `avoid_feel: ["energetic","happy"]`, `energy: 0.35`,
`space: "large_hall"`, `tempo_bpm: [58, 76]`, `pulse: "none"` or `"loose"`. If it is still busy, add `"sparse": true`
or `--energy 0.3`; if it smears, use `hall` instead of `large_hall` and shorten the tails.

**Verified in this pass:** 45 s, 0 FAIL, 9.2 notes/bar, room `large_hall`.

## 14. Fusion under a mood ("any fusion, but not upbeat")

**Direction.** The cultures still decide the scale, meter, instruments and patterns. The mood decides tempo and
energy, so a slow or reflective fusion is not forced to 108-130 BPM.

**Brief:** `{"fusion":["indian","west_african"],"emotion":"slow reflective","duration_s":45,"seed":7}` gave
`melancholy` at 67 BPM. Without a mood word the same fusion is `focused` at 88 BPM and `meta.mood_notes` says the
mood was not named. A culture style can be added with `"style": "<name>"` (the style must exist in
`references/styles/`; `compose.main` loads them from the brief).

**Sheet:** the usual fields, plus `feel` from the mood, `tempo_bpm` from the fusion plan (+-7 BPM), and a `notes`
line naming the cultures. Check `fusion.plan` warnings: a non-overlapping tempo or a scale not shared by every
culture is printed there.

**Verified in this pass:** both fusion cases 0 FAIL on score checks. Not yet listened to with earshot.

---

## Mix and deliver

Each recipe ends the same way: `listen.py` against the sheet; one or two levers from `music-direction.md` section 6;
`scripts/mixer.py` or `video-mixer/video_program_mix.py` for the final balance under voice or picture; deliver the WAV, the MIDI, the
sheet and the report.
