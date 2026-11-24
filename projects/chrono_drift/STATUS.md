# Chrono Drift - STATUS

30-second, 8-channel (7.1) cinematic cue for a space / time-travel sequence.
SoundFont: GeneralUser GS (default GM bank). Ambience and SFX: project presets.

## Brief (verbatim)

"create realistic 30 sec 8 channel music and tests all qa gates including ears , use sf2 , SFX ambinces ,
it's about space time travel"

Read as: 30.0 s, 8 channels (`immersive_7_1`, stereo delivered first), SoundFont synthesis, ambience and
SFX allowed and wanted, all gate rows plus the ears pass (`listen.py` with earshot).

## Phase checklist

- [x] 0.1-0.2 AGENTS.md and SKILL.md read
- [x] 0.3 brief-reading.md read; mood "wonder/mysterious", modifiers none, numbers 30 s / 8 ch win
- [x] 0.4 request type: cinematic cue + immersive + ambience/SFX (three READ TABLE rows unioned)
- [x] 1.1 intent block written; every word resolves (`intent.py check`)
- [x] 1.3 project type: single cue, not a film reel
- [x] 2.1 project scaffolded with `--ambience` (ambience was requested)
- [x] 2.3 metadata.json filled with real delivery values
- [x] 3.1 music-direction.md read
- [x] 3.2 KB research: `reports/research_space_time_travel_a_ship_falling_through_a_collapsing_wormhole.md`
- [x] 3.3 web sources: DAFx whoosh paper, Ableton trailer-impact article, NASA plasma-wave page, UIowa Space Audio
- [x] 3.4 ambience/SFX: `whoosh`, `impact`, `deep_space` sections cite two URLs and a Licence line each
- [x] 3.5 decisions written at the end of the research note
- [x] 3.6 reference finder run for the brief
- [x] 4 direction sheet filled (`direction/direction_chrono_drift.json`), every field
- [x] 4.6 focus = melody; piano_theme carries it
- [x] 4.7 immersive block: why, anchors, movers, height, room changes, deliverables
- [x] 4.8 expression block: picture, performer, producer moves, anti_generic, cues, theme
- [x] 4.9 craft pass (below)
- [x] 5 presets: 8 instruments, 1 environment, 2 sfx, 1 space, 1 mix (customised)
- [x] 6 profile: `cinematic`, nothing relaxed
- [x] 7 score: `scores/chrono_drift_score.json`
- [x] 8 render + gate: 0 FAIL, stereo v08 and 8-channel `master_7_1.wav` certified
- [x] 9.1 version record (v08), 9.4b arc, 9.4c expression, 9.4e director's second review, 9.5 listen, 9.6 self-check

## Craft pass (before the first note)

1. **Hook.** Eight chord tones: up a fifth, down a third, up a sixth to the octave, then steps down to the
   second; it never lands on the tonic. The clock ticks under it every beat and never stops.
2. **Arc.** 0.18 (Drift) -> 0.45 (Approach) -> 0.95 (Collapse, impact at 20.0 s) -> 0.20 (Afterglow).
   The quietest section is the last one, and the peak is a single bar, not a long plateau.
3. **Density map.** Drift: pedal + clock + piano. Approach: adds strings, harp, timpani and the whoosh;
   piano rests. Collapse: clock and harp rest; brass, choir, timpani and the impact enter. Afterglow: only
   pedal, one piano D and the room; strings hold a bare fifth.
4. **Lanes.** Carrier piano. Answer harp (only in the piano's rests). Pulse clock, then timpani. Bed strings,
   then choir. Colour whoosh and impact. No two parts share a lane and a register in a section.
5. **Contrast.** At 16.667 s low brass lands over the clock, which keeps ticking; at 23.333 s everything cuts
   to the pedal and one note. What stays is the D pedal, the clock's pulse and the key.
6. **Ending.** `tail_out`: a long piano D5 at 24.0 s and the room tail to 30.0 s; no fade of the impact.

`expression.anti_generic`: the generic version is a pad, a rising arpeggio and a trailer hit; this cue's pulse
is a clock that stops before the impact, and the theme is left alone after the cut.

## Decisions

- 72 BPM, 9 bars of 4/4 = 30.0 s exactly; every section, hit and trajectory key is on a bar line.
- D minor, theme never cadences; the intent word `mysterious` and tension `pedal` are carried by the held D2.
- One low owner (sub_pedal, D2); the timpani and impact are short transients, not a second bass line.
- 7.1 delivery via `hoa_bus`, order 3; whoosh is the only mover, everything else anchored or still.
- Loudness -16 LUFS, -1.5 dBTP (cinematic register, not a trailer's -14).

## Delivered

- `out/master_v08.wav` - stereo, -16.3 LUFS, -1.5 dBTP, 31.8 s file.
- `out/master_7_1.wav` - 8 channels on `itu_bs2051_system_h`, -16.5 LKFS on the delivered channels, worst
  channel true peak -3.1 dBTP, fold correlation +0.73, surround ratio -4.9 dB against the front.
- The cue is 30.0 s (9 bars at 72 BPM); the delivered file is 31.8 s because the room tail is the ending.
  `listen.py` reports the length as CHECK for that reason, not as a failure.
- Pipeline: 0 FAIL, 67 WARN (grouped below). No row was relaxed, skipped or retuned.

## Ear rows (stage 6, v08)

They are advisory by design (AGENTS.md section 6: INFO / WARN, never FAIL); none of them blocked the render.

| row | level | value |
|---|---|---|
| `ear.fatigue` | INFO | adaptation peak 0.58 (warn above 0.6 for 5 s) |
| `ear.mod_roughness` | INFO | peak 0.56 (warn above 0.6 for 3 frames) |
| `ear.masking` | WARN | piano holds >= 50 % of its own channels' activity in 64 % of active frames (want 70 %), median 0.70 |
| `ear.pitch_salience` | WARN | piano keeps its pitch in 42 % of pitched frames (want 50 %) |
| `ear.iacc` | INFO | 0.83 (window 0.1-0.98) |

The optional earshot model did not run (`ffmpeg` is missing in this environment), so `listen.py` measured
loudness, true peak, clipping and length only; no neural ear heard the file.

## Engine fixes (measured, not loosened)

The cue exposed seven engine defects. Each is fixed in the engine, none touches a threshold:

1. **Per-bar correlation was O(n*m).** `channel_qa._corr` called `np.correlate(..., 'full')` on 1.5e5-sample
   bars: ~2e10 multiply-adds per call, and the 8-channel row effectively hung (8+ minutes in one call chain).
   It now uses `scipy.signal.correlate(..., method='fft')`, which both NumPy and SciPy document as the fast
   path for arrays around 1e5 samples, and slices the +-64 lags the row uses. Measured on this master:
   1.40 s for the whole 8-channel analysis (was minutes). A direct fallback keeps it runnable without SciPy.
   Regression covers exact equivalence to the direct correlation (1e-10), an inverted bar (-0.99), and a
   full-bar timing bound. Web sources: NumPy `correlate` notes; SciPy `signal.correlate` / `correlation_lags`.
2. **Group energy depended on speaker count.** `_energy` summed channel means, so a 4-speaker back group read
   ~1.25 dB louder than a 3-speaker front group at the same level. It is now the mean over channels and time;
   a left/right or front/back ratio no longer moves when a layout gives a side more speakers. Test: `_energy`
   is equal for 3 and 4 identical channels.
3. **Group energy was recomputed three times per bar.** Each balance test re-measured its neighbours; the
   per-bar group energies are now precomputed once. Same numbers, less work.
4. **`_place_of` ignored `sfx:` presets.** It searched `presets/instruments` and `presets/vocals` only, so a
   track with `instrument: "sfx:whoosh_warp"` was judged at 0 deg / 10 deg while the mixer played its real
   preset at -120 deg / 28 deg. `z_separation` was failing a position that did not exist. Both `_place_of` and
   `_has_staging` now resolve `sfx:` presets. Test included.
5. **`figure_and_bed` ignored the declared focus.** The `cinematic` profile accepts a line, a texture or a
   drone; with the profile's whole list, a loud pedal was picked as "the figure" for a score that declares
   `melody`, so the masking and pitch rows judged the pedal against itself. It now uses the score's `focus`
   when one is declared. Test included.
6. **A balance finding was labelled with the wrong channel.** Group findings use channel index -1, and the
   record indexed `names[-1]`, naming `SR` on 7.1. It now records `channel: null`, `channel_name: "group"`.
7. **The pipeline could claim "all gates passed" with an uncertified format.** Stage 5b printed each extra
   format's FAIL and left the file as a draft, but the final verdict only counted the stereo gate. It now
   prints `STEREO CERTIFIED, N FORMAT(S) FAILED`, names them, sets `deliverables.failed_formats` and
   `gate.stopped = "extra_format"`, and does not print the all-passed stop. Verified on the run before this
   one, which correctly stopped on `immersive_7_1`.

## Remaining WARNs (grouped, with cause)

- **Preflight:** the impact tail crosses into Afterglow (`section_edge`); strings play Afterglow at 0.70
  velocity against a 0.30 curve (`stem_level`); piano is a figure that is quiet outside the peak
  (`figure_level`); sub pedal and impact sit 8 deg apart (`placement`, mid bands do not overlap); `intent.avoid`
  cannot measure `descending_resolution` from the score.
- **Ears:** masking 64 % vs 70 % and pitch salience 42 % vs 50 %, both naming the piano: the beds sit over it.
- **Melody/expression:** piano is 40 % stepwise (expect >= 45 %); information content and tension correlation
  flags on piano and harp; groove pocket locked at 0.44; harmonic resolution gravity holds.
- **Mix:** four stems carry weight below 120 Hz; spectral overlap brass/harp and clock/brass/choir; low end is
  wide below 120 Hz; no top-octave energy in the high-placed GM parts.
- **Immersive:** `imm_band` (high parts hold < 0.3 % above 4 kHz, so height is weak), `imm_iacc_early`
  (reflections all from the front), `imm_route_parity` (0.68 ms time difference vs 0.2 limit).
- **Score:** strings re-attack sustained pitches at beats 16 and 20 (`note_collision`).

## Director's second review (9.4e)

- **Still possible from section 2:** thick low-mids (realism `low_mid` -1.04, sub growth 8.09 dB), top closing
  at density (`openness` -17.83), bar-locked phrasing (0.73 % bar-scale deviation), distant sources without an
  air model (8 far sources). The measurements say it does not show: every part rests somewhere (density map),
  bars are varied (pattern rows), and the peak is one bar, not a plateau (arc: Collapse -14.8, Afterglow -27.0).
- **The one thing a producer would change first:** the strings re-attacks at beats 16 and 20; shortening the
  previous note would make the pad swell instead of re-articulate. Not changed here: this pass was the engine.
- **Not heard:** no human listening; earshot could not run (`ffmpeg` missing); height with a dummy head is weak
  and was not auditioned.

## Self-check (9.6)

- Read AGENTS.md, SKILL.md and the READ TABLE rows: **yes**.
- Research note cites KB ids and web URLs, with Licence lines for every sfx/env: **yes**.
- Gate profile `cinematic`, no relax/skip: **yes**.
- Direction sheet complete, sections/hits agree, `piece_type` on score: **yes**.
- Every non-built-in preset exists with a real character: **yes** (`presets.py validate` clean).
- Score has `space`, `room`, `mix_preset`, no inline EQ/spatial: **yes**.
- Immersive block, 3+ reflection directions, `imm_*` rows ran: **yes** (4 directions).
- `pipeline.py` ended with 0 FAIL; WARNs listed above: **yes**.
- Balance measured (not only the gate): **partly** - the `balance` row passes; per-stem loudness was not
  tabulated separately in this pass.
- `listen.py` ran: **yes, measurement only**; the earshot model did not run (no `ffmpeg`), so the ears are
  reported, not heard.
- Scene/ambience `physical.py` checks: **N/A** (the ambience is the owned `deep_space` env preset).
- Reply lists what was not checked: **yes**.
