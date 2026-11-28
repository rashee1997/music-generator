---
section: process
title: How a session goes wrong
lessons:
- id: P01
  title: renders and memory
  keywords: [render, second render, memory, concurrent, pgrep, 15 GB, mixing stage, 8 channel, stereo only]
  symptom: a crash or a killed process in the mix stage
  cause: two renders at once with an order-4 or 5 field and an 8-channel stage
  fix: pgrep -f scripts/pipeline.py before starting; stereo-only renders can overlap a stem stage; check free -g in the mix stage; never two 7.1 renders
  evidence: AGENTS rule 21
- id: P02
  title: a wait loop that waits for itself
  keywords: [pgrep -f, waiter, until loop, deadlock, background, command line]
  symptom: a queued render that never starts
  cause: pgrep -f matches the waiter's own command line
  fix: wait with a script file or a pidfile; never pgrep -f a string that is in your own argv
  evidence: '2026-11-28'
- id: P03
  title: say "running" only after looking
  keywords: [status, running, finished, report, honest, notification, watcher, monitor]
  symptom: the user asks "it's running?" and it was not
  cause: a render ended hours earlier and no watcher had reported
  fix: set a background watcher for every render (until ! pgrep; grep the scoreboard); check pgrep and the log's mtime before answering
  evidence: '2026-11-28'
- id: P04
  title: scaffold leftovers block a render
  keywords: [scaffold, TODO, direction sheet, duration_s, licence, real-world references, material_set, materials preset, research note, BLOCKED]
  symptom: the project gate blocks with TODO placeholders, a missing Licence line or an unknown material set
  cause: a copied scaffold file kept its template values; a space names a material_set the project lacks
  fix: move the template out of direction/; fill project, medium, brief, audience, story, gate_reason, notes, duration_s, in/out points; give every sfx source slug a "Real-world references" section with Licence and Measured lines; copy the materials preset into presets/materials
  evidence: quiet_frequency_trailer, 2026-11-28
- id: P05
  title: stale files in stems/
  keywords: [stems, stale, stems.json, snare_b, leftover, removed part]
  symptom: a KeyError reading stems.json, or a gate row about a part that no longer exists
  cause: a stem file from an earlier render stays after the part was removed
  fix: delete it; code that walks stems/ must filter by stems.json
  evidence: trailer snare_b
- id: P06
  title: changing several things per render
  keywords: [one change at a time, attempts, five attempts, rca, failure log, report, ask]
  symptom: a render that cannot say which change worked
  cause: several levers moved at once
  fix: one cause per render, written in STATUS.md; after 5 renders without a lower FAIL count, stop and ask (AGENTS 8.2)
  evidence: AGENTS 8.2
- id: P07
  title: relaxing, skipping or waiving a row
  keywords: [relax, skip, waive, gate, loosen, ask the user, rule 20, mismatch, protected, auto mode refused]
  symptom: an edit that excuses a row was refused by the permission check
  cause: it was a decision about the piece's ending, not a measurement
  fix: ask, with the row, the value, the cost of the material fix, what the relaxation hides and the bounded change; protected rows are never relaxed; an unimportant row with a mismatch verdict and a measurement needs no question
  evidence: trailer ending, 2026-11-28
- id: P08
  title: map a listening note to its source before editing
  keywords: [listening note, time stamps, feedback, mechanical burst, roar, timeline, source, mapping]
  symptom: a fix aimed at the wrong sound
  cause: the note names times, not parts
  fix: list the events at those times from the story clock (TX, hits, passes) and the continuous beds in the stems; say the mapping to the user, then change only those
  evidence: trailer notes at 0:06, 0:25, 0:31, 1:45, 1:49
---
