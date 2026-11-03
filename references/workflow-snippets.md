# Workflow snippets: direction sheet, direct the draft, listen

Moved verbatim from SKILL.md to keep the entry file short.

## Step 1 in practice: the direction sheet

```json
{"purpose": "45 s product trailer opener", "duration_s": 45,
 "feel": ["epic", "triumphant"], "avoid_feel": ["sad", "calm"],
 "instruments": ["taiko", "brass", "strings"], "pulse": "steady", "tempo_bpm": [96, 112], "mode": "major",
 "loudness_lufs": -16, "true_peak_max": -1.0, "hits_at": [24.0, 38.0]}
```
Feel and avoid are plain English words. `pulse` is `steady`, `loose` or `none`. The `mode` is the strongest cue, so
get it right first. Put the picture in the sheet too: what happens at each second.

## Step 3 in practice: direct the draft

```python
import json, sys; sys.path.insert(0, 'scripts'); import direct
s = json.load(open('score.json'))                     # from compose.py
direct.add_pulse(s, start=0, gain_db=-6, dyn=[[0, .45], [20, .7], [24, 1.0]])
direct.add_line(s, 'fanfare', 'trumpet', at_beat=66, phrase=[(0,.5,70),(.5,.5,74),(1,.5,77),(2,1.5,70)], gain_db=-3)
json.dump(s, open('score2.json', 'w'))
```
Beats = seconds x bpm / 60. `direct.py` also works as a command for `--bpm`, `--remove` and `--pulse`.

## Step 5 in practice: listen

```bash
python3 scripts/listen.py cue.wav --direction sheet.json            # full report (earshot installed)
python3 scripts/listen.py cue.wav --direction sheet.json --no-ears  # measurements only
```
Read the report this way:
- **Forced choice** ("epic music" against the avoid words, as a percentage) is the sharpest test. Above 50 % passes.
- **Earshot hears** is a ranked list of readings. They are not exclusive; a piece can read two feels at once.
- **Pulse clarity** under 0.15 means no beat grid. Tempo estimates can read double or half; with no pulse there is no tempo to trust.
- **FAIL** is a question for the user, not a verdict. Listen to the file yourself if you can, or ask them to listen.
