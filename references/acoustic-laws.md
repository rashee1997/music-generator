# Acoustic laws and dynamic musical flow

Moved verbatim from SKILL.md to keep the entry file short.

## Acoustic Laws & Dynamic Musical Flow (so a score does not read as MIDI)

`scripts/pattern_audit.py` carries these, `quality_gate.py` prints them as its own rows, and `--selftest` proves
they fire on a MIDI-style score and stay quiet on a composed one. Enforce the **7 Universal Laws of Natural Musical Flow (`DYNAMIC_MUSICAL_FLOW_v2.md`)**:

1. **The Anti-Loop Mandate ($A \rightarrow A' \rightarrow B \rightarrow A''$).** Never repeat a 2-bar or 4-bar phrase identically. Human ears habituate within 6.5s. Bar 1 introduces motif; Bar 2 varies the final beat; Bar 3 shifts register up (+3 to +5 degrees) for tension; Bar 4 resolves and launches a rhythmic pickup fill into the next cycle.
2. **Phrase Respiration (Lung-Capacity Envelope).** Maximum continuous melodic phrase is 2.5 to 4.5 seconds. Mandate $\ge 0.15$ to $0.25$ beat rests at phrase ends for breath or bow changes. Ascending phrases swell in velocity (+15%) and filter cutoff (+400 Hz); descending phrase ends soften (-20%).
3. **Thermodynamic Energy Conservation ($E(t) \in [0, 1]$).** Drive arrangements through a continuous normalized energy curve: Intro (0.20 $\rightarrow$ 0.45) $\rightarrow$ Groove (0.65) $\rightarrow$ Breakdown/Valley (0.25, strip kick/bass, let solo voice/flute/drone breathe) $\rightarrow$ Climax/Drop (0.95–1.0, sub-bass returns, lead leaps +1 octave or harmonizes) $\rightarrow$ Outro Resolution (0.0).
4. **Conversational Call-and-Response.** Zero simultaneous clutter. When Lead A holds or rests on Beats 3–4, Secondary Counter-Voice speaks in that exact gap: $\text{Density}(\text{Counter}, t) = 1.0 - \text{Activity}(\text{Lead}, t)$.
5. **Transition Physics.** Never cut cold across 8-bar section boundaries. Beat 4 of Bar 8 creates a 250–500 ms micro-vacuum followed by an anticipatory directional vector (pitch sweep, reverse cymbal, snare/Thavil roll, bass drop) landing on Beat 1 of the new section.
6. **5-Band Spectral Slot Allocation.** Band 1 (35–100 Hz Center): Sub-bass/Kick exclusively; Band 2 (120–350 Hz $\pm 0.25$ pan): Warm chord body; Band 3 (400–1000 Hz $\pm 0.65$ wide pan): Plucks, counter-melodies; Band 4 (1.1–3.8 kHz $\pm 0.15$ center): Sacred Lead & Vocal Formant Zone; Band 5 (4.5–16 kHz $\pm 0.80$ ultra-wide): Air, shakers, bells.
7. **Dynamic Parameter Interpolation.** For unseen mood blends, compute weighted vector coordinates across Brightness Centroid, Swing Asymmetry, Harmonic Darkness (Lydian $\rightarrow$ Locrian), and Transient Hardness rather than defaulting to generic templates.
8. **Voice the chord and roll it** (`chord_voicing_and_strum`). The top note leads (+8 % velocity) and the inner voices sit back; chord tones start about 8 ms apart. A guitar strums low-to-high on the beat and high-to-low off it, 18 ms between strings.
9. **Never choke a plucked instrument** (`choked_resonance`). Guitar, harp, kora, oud and guzheng notes last 0.6-1.0 beats with `"art": "legato"`; under half of a part may be short staccato.
10. **A run is never a machine gun** (`machine_gun_percussion`). Repeated same-pitch hits need a contour measured against their own mean: at least 10 % peak-to-trough, alternating accents, and exponential arch `(step/N) ** 1.6`.
11. **Two bright samples never fire together** (`percussion_flam`). Clap and tambourine land 0.02-0.028 beats (10-15 ms) after a snare or rim.
12. **No close intervals low down** (`low_interval_mud`). Below F3 (MIDI 53) keep 5 or more semitones between voices: root-5th-10th, not a triad in the mud.
13. **One room, shared** (`spatial_glue`, WARN). Every acoustic track in a wet score has some reverb; never one dry stock-MIDI track in the middle of a hall.

Dynamics are judged against the track's own level (velocity sd under 5 % of its mean) and the whole-piece curve
must move by 25 % of its mean, so a quiet mood is not punished for being quiet and a loud flat one is not excused.
