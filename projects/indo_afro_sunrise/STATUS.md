# Project Status: Indo-Afro Sunrise

## Flow (SKILL.md): tick each step, note decisions below
- [x] 1. Project scaffolded (direction/ presets/ scores/ midi/ stems/ reports/ scripts/ out/)
- [ ] 2. Research: `research_kb.py` note citing the knowledge base + web sources (reports/research_<topic>.md);
      for every ambience or effect the score uses: `--sounds a,b` and fill each "Real-world references" section (2 sources, licence)
- [ ] 3. Direction sheet filled (direction/direction_sheet.json)
- [ ] 4. Presets for every non-built-in instrument / vocal (presets/instruments, presets/vocals), each ambience (presets/environments)
      and tuned one-hit effect (presets/sfx), each listing its "sources"
- [ ] 5. Score written (scores/*.json) referencing presets by exact name
- [ ] 6. `pipeline.py scores/<title>_score.json --project .` renders out/master.wav, midi/, stems/, reports/ci_report.json
- [ ] 7. Revise one lever at a time until 0 FAIL (max 5 attempts, then report)
- [ ] 8. listen.py on out/master.wav; deliver

## Rules
1. Never monolithic: sound and space in presets/, notes in scores/, intent in direction/.
2. Sample presets here (lead_flute, warm_piano, ...) are examples: rename or replace them.
3. The mixer applies azimuth (pan), distance (air filter, level, reverb send), width and one shared room.
4. The mix preset owns the strategies: gain_staging (legacy|adaptive), dynamics.engine (pedalboard|dsp),
   spectral profiles, space, sidechain.mode (legacy|explicit|off) and the mastering profile.
   `python scripts/presets.py show mix default` prints every key with its shipped value.
   `spatial.elevation` and `spatial.space` are stored but not applied.

## Decisions / feedback

## State at the 2026-11-25 render (attempt 1)

- Gate profile: `presets/gate/indo_afro_sunrise.json` (own profile, `extends: melodic`, no row changed), and the
  score declares `piece_type: indo_afro_sunrise`. Gate data in `presets/gate/data/`, figures in `presets/gate/figures/`.
- Stem gate: **green** — 102 rows, 0 FAIL. The kit needed its hi-hats at 16ths with a note shorter than the step
  (a longer written length puts a short GM sample's dead tail inside a sounding note and the row calls it a dropout).
- Master: **2 FAIL**
  - `clicks` — 69 high-pass-MAD events on the summed master, none of them single-sample jumps; each stem passes on
    its own, so the row is reading the stack of on-beat percussion attacks, not a cut. Changes tried and measured:
    a softer master (`dynamics.engine: dsp`, knee 6 dB, 5 ms lookahead), −15 LUFS and a crest floor of 8 dB, hats moved
    off the beat. None moved the count; the arrangement fix (spreading the percussion onsets by 10–30 ms) raised the
    kit's dropout count instead, so it was reverted.
  - `spectral.equal_loudness` — shekere 17.2 dB bright in 2.5–5 kHz. The `inst_eq` cuts written for it (−4, then −10 dB
    at 3536 Hz plus a 6 kHz low-pass) do not reach the processed stem: the value is identical before and after, so the
    instrument preset's own `eq` is not in the chain the row measures.
- Not run yet: `listen.py` (nothing auditioned), `arc_report.py`, `expression_report.py`, `chem_report.py`, and the
  CI report is not written because the run stopped at the master rows.
- Cache note: `projects/<dir>/.cache` holds the processed stems; a stale entry there hides a preset change, so clear it
  before judging an EQ edit.
