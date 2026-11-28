---
section: mixing
title: Levels, the mix preset, loudness
lessons:
- id: Y01
  title: make the music a fraction while the effects stay
  keywords: [music level, 75 percent, quieter music, louder sfx, level_by_role, gain_db, Gain, fx table, '@role', effects forward]
  symptom: a request for the music at 75 % has no effect when level_by_role is edited
  cause: a preset's own gain_db overrides level_by_role; the master is re-levelled to the LUFS target, so only the balance matters
  fix: 'mix preset fx table {"@bass": Gain -2.5, "@drum": ..., one entry per music role}; the effects keep their level and come forward at the target loudness'
  evidence: trailer v04
- id: Y02
  title: slimming a mix preset removed a block the gate requires
  keywords: [mix preset, prune, defaults, immersive, height_by_role, max_elevation, gate blocked, slim]
  symptom: '"[BLOCKED] immersive needs height_by_role and max_elevation"'
  cause: keys equal to the defaults were pruned, but the project gate asks for them when immersive is enabled
  fix: keep the immersive block whole; prune only sections the gate does not check (gain_staging, spectral, role_chains)
  evidence: indo_afro_sunrise, 2026-11-28
- id: Y03
  title: dynamics keys outside comp are ignored
  keywords: [dynamics, ratio, attack_ms, release_ms, comp, inert, unknown key, validate]
  symptom: '"mix.dynamics.ratio: unknown key (the engine would ignore it)"'
  cause: the compressor values live in dynamics.comp {thr, ratio, attack, release}
  fix: move them there; run presets.py validate after editing a mix preset
  evidence: indo mix preset
- id: Y04
  title: using the mix preset's fx table and master chain
  keywords: [mix fx, mastering.fx, de_esser, saturator, parallel_comp, tilt_eq, band_width, instrument key, sfx key]
  symptom: a chain written in the mix preset does nothing or is refused
  cause: keys are matched as "*", "@role", then the instrument name (sfx tracks are "sfx:<preset>"); the chain runs after the instrument preset's own fx
  fix: validate with mix_schema.validate; test the key with placement._mix_fx_for(inst, role)
  evidence: tests/test_mixfx.py
- id: Y05
  title: loudness is the user's choice
  keywords: [loudness, LUFS, '-16', '-14', trailer, register, master lufs]
  symptom: a default loudness used where the user named one
  cause: master.lufs in the score wins over the register band and the shipped default
  fix: write the user's figure in the score and the sheet; state it in the report
  evidence: trailer -16 LUFS
- id: Y06
  title: SFX stems sit above the music in the mix
  keywords: [sfx level, sfx over music, balance, stem rms, fx table, Gain, engine bed]
  symptom: listener hears the SFX over the music; stem RMS shows SFX +3.3 dB over music overall and +6 to +14 dB in quiet sections and the end
  cause: continuous beds (engines, road, tyres) were left at their preset level while the orchestra was trimmed
  check: sum stem power of sfx_* against the rest per 8 s window before touching a preset
  fix: 'per-sfx Gain in the mix preset fx table: engines -5 dB, road and tyres -4, device and alarm -3; leave impacts, horn, walkie (the cut-scene hits) alone'
  avoid: 'one cut on the whole fx role: it also lowers the hits the brief wants loud'
  evidence: 'quiet_frequency_trailer 2026-11-28: SFX cuts applied and certified in v05, but the stem-level SFX/music ratio (+3.4 dB) is measured before the mix gains, so the new balance in the final mix is not measured. Not listened to'
---
