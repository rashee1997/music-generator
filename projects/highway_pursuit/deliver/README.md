# Highway Pursuit — deliveries

Audio lives here, not in `out/`: `out/` is pipeline scratch (a re-render overwrites the draft, and
`.gitignore` drops the whole folder), while `deliver/` is the copy that stays. The WAVs are ignored by
git (`projects/*/deliver/*.wav`), so a clone stays small and the audio is never committed by accident.

| File | Status |
|---|---|
| `highway_pursuit_DRAFT_uncertified.wav` | stereo 44.1 kHz, 60.64 s, from the last `pipeline.py` run. **Not certified**: the master gate returned 3 FAILs (below). |

When the master is certified, `out/highway_pursuit.wav` (stereo) and `out/highway_pursuit_ambix.wav`
(fifth-order AmbiX, 36 channels) are copied here as `highway_pursuit.wav` and
`highway_pursuit_ambix.wav`, and this table is updated with the version number and the gate verdict.

## The last render

Stems: 0 FAIL / 0 WARN over 156 rows. Master: 3 FAIL.

- `scene.silence_honoured` — the declared second of silence after the near miss reads −36 dBFS
  (limit −50): the release of the notes cut at 52.97 s and the room's tail are still decaying.
- `dropout` — 3 holes, longest 145 ms, floor −63 dB.
- `pattern` — 4 repetition/flatness flags: the cue is a 60 s chase and several parts hold one figure.
