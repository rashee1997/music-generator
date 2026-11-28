# Project Status: Highway Pursuit

Certified PASS: `out/highway_pursuit.wav` (v03: the bass is back, see below; v01 and v02 kept), -16.0 LUFS, -1.5 dBTP, 60.1 s, plus `out/highway_pursuit_ambix.wav`. 0 FAIL, 18 attempts in the project's history (14 before the gate work, 4 after). Nothing was listened to: `listen.py` did not run, so taste, realism and fit are not measured.

## Decisions
- Gate profile extends `orchestral` (loud, layered, locked percussion). `build_piece.py` writes it, the sheet and the score; run it, do not hand-edit those files.
- Loudness -16.0 LUFS comes from the declared registers (`cinematic`, `hybrid`: overlap -18..-14, middle -16), not from the earlier -14 (a film-mastering blog figure). The mix preset uses profile `default` so the register applies.
- Bank per family: `muse_general` for strings, brass, choir, piano, bass clarinet; `generaluser_gs` for the kit (render `[bank]` lines). One sample layer per instrument: a loud passage is only louder.

## Failure log
| Row | Cause class | Evidence | Lever | Result |
|---|---|---|---|---|
| stem.dead, stem.tick, stem.dropout, stem.edge (many stems) | gate read arrangement as defect | 15 FAIL per attempt on the old profile; tempo-locked ostinati, declared rests, tuba/snare 12.1-12.8 dB | row parameters (`honour_rests`, `score_match_share`), `orchestral` profile | cleared |
| stem.dead (cymbals) | mismatch | final section 13.6 dB under the sheet's energy ratio vs 12 dB; a fading roll at velocity 0.36-0.6 | `gate_profiles.py relax stem.dead under_db=15` | relaxed, listed as gate_relax |
| dropout | fault (score vs sheet) | rca: no stem sounds at 54.4 s; sheet declares 1 s of nothing, notes left ~2.9 s | a low swell enters when the declared rest ends | cleared |
| cochlear_roughness | partly fault, partly waiver | 0.134 at 18.5 s (violas' 4th/7th against the sliding bass, 368 vs 390 Hz); violas moved to chord tones -> 0.123 at 18.0 s from tails and room | scene role `transition` waives the roughness ceiling for the drift (user-approved) | frames inside 17.1-22.3 s not judged; every other frame still is |

## Director's second review
- Could still show: a loop machine (locked kit and ostinato by design), thin realism from one-layer GM/MuseScore samples, a drift whose roughness is waived rather than removed.
- A human producer would first: re-voice the drift so the bass slide and the violas do not share the 350-400 Hz band, then remove the waiver.
- Not checked: nothing was heard.

## v03: where the bass went (user feedback: no bass, no theatrical or headphone low end)
- Measured on v02: the stems held most of their power at 20-80 Hz, the master kept 22 dB less of it (20-40 Hz share -55 dB, 40-80 Hz -20.7 dB), and
  `realism.sub_weight` read a 31 dB loss as PASS.
- Cause: the mix preset's `mastering.highpass_hz` 105, `highpass_order` 4 (a 24 dB/octave master high-pass, copied from the Night Pursuit preset script),
  plus a `sub_weight` row that also needed the master to be "thin". Fixed: the master high-pass is the shipped 24 Hz, order 1; `preflight.master_highpass`
  fails a bass part the high-pass removes; `sub_weight` warns on the loss alone; the cue uses `master.tone: "theatrical"` and
  `mastering.virtual_bass` (headphones).
- v03 against v02 (share of the master's power): 20-40 Hz -55.0 to -24.3 dB, 40-80 Hz -20.7 to -5.1 dB, sub loss 31 to 5.1 dB.
- The sub tail then read -32 dBFS inside the declared one-second rest: `mastering.rest_dip` (-36 dB over each declared rest) fixed it. The earlier
  v02 had passed only because the high-pass removed that tail too.
- Not checked: nothing was listened to. `realism.velocity_response` on this cue is unchanged (0.44; tuba -0.45, bass_clarinet 0.44): the per-note
  brightness law helped five isolated test lines but not these fast ostinati and low brass.
