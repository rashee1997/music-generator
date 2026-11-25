---
title: Theatrical realism
summary: How to ask the engine for loudness-dependent timbre, section scatter, macro breathing, low-mid clarity, air at density and attack-led depth, and how to measure whether it happened.
tags: [realism, theatrical, hollywood, timbre, ensemble, section, rubato, depth, low-mid, air, distance]
load_when:
  - a brief asks for a theatrical, cinematic, Hollywood, orchestral or "less synthetic" sound
  - a render passes the gate but reads as clean, unified or loud rather than physical
  - a section part sounds like one player multiplied
---

# Theatrical realism

Facts and sources: `knowledgebase/sound-design/theatrical-realism.md`. This page is the rules and the levers. The
gate stays the authority: nothing here relaxes a row, and every change is made in a preset, a track block or a
score, never in a script that writes sound for one project.

## 1. The order

1. Decide the eight qualities in the direction sheet (`expression.sonic_picture`, `performer`, `cues[].timbre`,
   `mix_intent`) before the score. A cue that does not say how loud playing changes colour, how many players are
   in a section and where the listener sits will get the generic version.
2. Declare them where the engine reads them: `timbre_dynamics` and `ensemble` on a track, `elastic` on the score,
   `theatrical` in the mix preset.
3. Render, then measure with `python scripts/realism_report.py out/master.wav --score ... --stems out/stems
   --project .`. A WARN names a quality that is absent; fix the part or the preset, never the threshold.
4. Run the normal gate. The realism stage is opt-in and must not buy its effect with roughness, masking, a
   low-end fold or a loudness overshoot.

## 2. Loudness-dependent timbre (`timbre_dynamics`)

On a track, or on its instrument preset:

```json
"timbre_dynamics": {"drive": 0.5, "tilt_db": 2.0, "tilt_hz": 2800,
                    "band_hz": [140, 7000], "amount": 0.6, "smooth_s": 0.35}
```

`drive` is how far the nonlinear residue grows at the stem's loud end, `tilt_db` the high shelf that follows it,
`amount` the blend, `band_hz` the band that receives the nonlinearity (keep the sub out), `smooth_s` how slowly
the level measure moves. It is level-compensated, so it changes colour not pattern level. Use it on a sustained
orchestral part whose written dynamics already span a real range; a part written at one velocity has nothing to
follow. Values are starting values; put the researched figures in the preset's `sources`.

Do not use it on `sfx:`, `env:` or `clone:` tracks. It is not a substitute for `velocity_timbre` on a SoundFont:
`velocity_timbre` splits written velocities into timbral bands, `timbre_dynamics` follows the rendered level
continuously. They can be used together on different parts, not as two names for one thing.

## 3. A section is several players (`ensemble`)

```json
"ensemble": {"players": 4, "spread_cents": 5, "spread_ms": 10, "vel_spread": 3}
```

The renderer expands every written note into `players` copies before humanisation. Each player has one fixed
intonation, timing and level offset for the whole piece, plus per-note jitter, so the section is stable rather
than chorused. `spread_ms` is a peak offset in milliseconds at the score's tempo.

- Pitched section parts only: a drum, environment or effect part raises. A solo declares no block.
- 2-8 players. Above that, use a multisampled section: eight copies of one sample is not a larger section.
- Cost is linear in players: a four-player chord part costs four times the notes. Check polyphony and render time.
- The measured scatter is 2-13 cents and 20-50 ms between players; 5 cents and 10 ms are deliberately at the
  tight end because sampled copies correlate more than independent players.

### High register (`register`)

```json
"register": {"split_pitch": 74, "ref_pitch": 72, "pivot_hz": 1500, "db_per_oct": 1.5, "max_db": 6}
```

The renderer splits the track at `split_pitch`, renders the upper notes as their own branch, and applies a high
shelf that falls `db_per_oct` for every octave the branch's mean note sits above `ref_pitch`, capped at `max_db`.
This is a first-order correction for the formant shift of an upward-resampled sample, not a formant-preserving
resynthesis. Use it on a sampled part whose top octave sounds glassy; do not use it to brighten a dull low part
(it does nothing below the split).

### Repeated attacks (`transient_variety`)

```json
"transient_variety": {"gain_db": 1.0, "tilt_db": 1.5, "width_ms": 25}
```

Each written onset gets a deterministic gain of +/-`gain_db` and a short high-band emphasis of +/-`tilt_db` inside a
`width_ms` window. It changes no onset time and cannot create a new sample; it is for a repeated pluck, a
percussion family or a doubled line that still reads as one trigger. Zero on both values is a no-op; environments
raise. Do not use it on a sustained section where every note is a bow change.

## 4. Macro phrase breathing (`elastic`)

In the score:

```json
"elastic": {"amount": 0.04, "corr_beats": 12, "breaths": [16, 48], "breath_s": 0.08}
```

`amount` is the peak long-range tempo deviation (0.04 = about +/-4 %), centred so the average tempo is unchanged;
`corr_beats` is how many beats a deviation lasts (about two bars is a phrase); `breaths` are beats where the whole
ensemble takes a short collective breath of `breath_s` seconds, useful before a harmonic turn or a section
change. This is on top of the per-phrase rubato and the final ritardando, not a replacement for them.

Do not use it to make a dance or trailer pulse elastic: the pulse must stay the pulse. Use it on conducted or
chamber material where the bar, not the note, is the unit of expression.

## 5. Theatrical mix stage

In the mix preset:

```json
"theatrical": {
  "enabled": true,
  "low_mid": {"enabled": true, "low_hz": 180, "high_hz": 420, "max_dip_db": 2.0,
              "range_db": 10, "ratio": 2.0, "attack_ms": 20, "release_ms": 180},
  "air": {"enabled": true, "hz": 9000, "max_lift_db": 1.5, "window_db": 6},
  "detail": {"enabled": true, "duck_db": 2.5, "attack_ms": 4, "release_ms": 40, "ref_db": 18}
}
```

- `low_mid` compresses only 180-420 Hz when that band is loud, so stacked heavy layers cannot thicken the region
  where weight is localised. Its threshold is `range_db` below the band's own 95th-percentile level, not an absolute
  dBFS: the stage runs before the master, so a fixed threshold would depend on pre-master gain. It is a dynamic EQ,
  not a static cut: a sparse passage keeps its body.
- `air` lifts 9 kHz and above near the piece's own loud end, capped at `max_lift_db` and fading out `window_db`
  below it. It is relative, not an absolute LUFS, because this stage runs before the master: a quiet passage gets
  little or none, a dense peak keeps its top octave instead of folding inward.
- `detail` dips the shared reverb send only while the direct sound is attacking, then returns it. That is how
  close detail sits in front of a hall rather than inside it; a sustained body keeps its send.
- It runs on the stereo mix bus and on a discrete multichannel master: every full-range channel gets the linked
  low-mid lean and the same air curve, and the LFE is skipped. AmbiX/ADM keep their own levelling and are not
  processed by this stage.
- Every value is a starting value. Measure the piece, then move the number in the preset.

## 6. Distance

The engine has ISO 9613-1 air absorption (`scripts/airabs.py`, `spatial.iso9613_air_absorption`), near-field
divergence, a distance-scaled send, and now the two missing distance decisions in the space preset:

```json
"distance": {"proximity_db": 3.0, "proximity_hz": 200, "er_distance_exponent": 1.2}
```

- `proximity_db` is a low shelf that grows linearly as a source moves inside the 1.5 m reference; `proximity_hz`
  sets its corner. It is a close-source cue, not a bass boost: at 2 m it is a no-op, so a distant part cannot be
  thickened with it.
- `er_distance_exponent` makes the early-reflection field fall faster (or slower) with distance than the 1/r law,
  separately from the reverb tail. 1.0 is the old behaviour; use a value above 1 when a scene should close in
  without the hall getting drier.
- A source beyond 4 m names `temp_c` and `rh` on its spatial block, or the preset states why the simpler damping
  is enough. The realism report predicts the 4 kHz loss from the distance.
- A source within 1.5 m still needs the near-field route where one exists; proximity is a spectral cue, not a
  substitute for the near-field head model.

## 7. What this cannot do

- It cannot add a velocity layer that was never recorded. `timbre_dynamics` adds a plausible coupling, not the
  real ff sample.
- It cannot preserve formants on a resampled note. The high-register correction is a planned register stage;
  until it exists, a sampled part that sounds glassy in its top register should move to a path with real high
  samples, or the register should be rewritten.
- It cannot make one player a section, or eight copies independent players. `ensemble` is scatter, not a room.
- It does not measure taste. `realism_report.py` says the structure is present; it does not say the cue is good.

## 8. Gate and report

The realism measurements are advisory rows, not gate rows: they are new, their thresholds are starting values,
and a WARN is a reason to listen, not a failed render. The gate rows that a theatrical change can break are the
ones to check every time: `cochlear_roughness` (more harmonics), `masking` and `balance` (a lifted air band or a
carve), `master.dc` and `fold.mono` (a low-mid stage that shifts phase), `loudness` and `true_peak` (the air lift
adds level). Fix the part, the preset or the placement; never loosen the row.

Report: which blocks were used and with what values, which parts declare players, whether `elastic` was set and
where the breaths are, which theatrical stage ran, the realism report's verdicts, and that nothing was auditioned
unless `listen.py` ran.
