# Project Status: Highway Pursuit

## Flow (SKILL.md): tick each step, note decisions below
- [x] 1. Project scaffolded (direction/ presets/ scores/ midi/ stems/ reports/ scripts/ out/)
- [ ] 2. Research: `research_kb.py` note citing the knowledge base + web sources (reports/research_<topic>.md);
      for every ambience or effect the score uses: `--sounds a,b` and fill each "Real-world references" section (2 sources, licence)
- [ ] 3. Direction sheet filled (direction/direction_sheet.json)
- [ ] 4. Presets for every non-built-in instrument / vocal (presets/instruments, presets/vocals), each ambience (presets/environments)
      and tuned one-hit effect (presets/sfx), each listing its "sources"
- [ ] 5. Score written (scores/*.json) referencing presets by exact name
- [ ] 6. `pipeline.py scores/<title>_score.json --project .` renders out/<project>.wav, midi/, stems/, reports/ci_report.json
- [ ] 7. Revise one lever at a time until 0 FAIL (max 5 attempts, then report)
- [ ] 8. listen.py on out/<project>.wav; deliver

## Rules
1. Never monolithic: sound and space in presets/, notes in scores/, intent in direction/.
2. Sample presets here (lead_flute, warm_piano, ...) are examples: rename or replace them.
3. The mixer applies azimuth (pan), distance (air filter, level, reverb send), width and one shared room.
4. The mix preset owns the strategies: gain_staging (legacy|adaptive), dynamics.engine (pedalboard|dsp),
   spectral profiles, space, sidechain.mode (legacy|explicit|off) and the mastering profile.
   `python scripts/presets.py show mix default` prints every key with its shipped value.
   `spatial.elevation` and `spatial.space` are stored but not applied.

## Decisions / feedback
