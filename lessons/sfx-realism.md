---
section: sfx-realism
title: Sound-model effects that sounded fake, loud or repetitive
lessons:
- id: X01
  title: ghost wail ("oiii") from pitched pulse trains
  keywords: [ghost, wail, theremin, oiii, engine, tyre squeal, walkie, alarm, klaxon, periodic, pulse train, pitch sweep, noise_mix, jitter, realistic]
  symptom: engines, tyres, radio and device sound like an old horror film
  cause: a clean periodic excite through a fixed formant filter, with the pitch swept, is a tone that glides
  fix: engines jitter 0.10 and noise_mix 0.30 with 40 harmonics (V8 0.05, 0.20); tyre squeal 4 harmonics and noise_mix 0.5, wobble 2 %; radio carrier 95 % noise; alarm as 1 kHz beeps (3 a second, soft edges); a device as band-limited noise with a smooth AM, no rising tone
  avoid: judging by the number of harmonics; real sources are mostly noise with a faint pitch
  evidence: trailer listening note, 2026-11-28
- id: X02
  title: continuous beds mask the strings and brass
  keywords: [roar, wind, road, ambience, masking, broadband noise, midrange, intake, jet, bed, tilt, strings, brass]
  symptom: a roar at the peaks clouds the orchestra at 1-4 kHz
  cause: road, wind and intake noise ran to 3-6 kHz at the same level through the peaks
  fix: road 100-1400 Hz at -16 dB, wind (brown) 120-1200 Hz, intake 500-1800 Hz at -28 dB, a tilt_eq of -3 dB about 900 Hz on engines in the mix `fx` table
  evidence: trailer 0:48-1:00 and 1:25-1:44
- id: X03
  title: the same sound event repeated is abrasive
  keywords: [repeat, identical, radio, transmission, walkie, mechanical burst, abrasive, 1 kHz, 4 kHz, variation]
  symptom: five bursts at one level and tone read as a buzz at the ear's sensitive band
  cause: one carrier, one level, one length for every event
  fix: 'a table per event: level (-2 to -15 dB), length, voice colour (bright and dark formants), lighter distortion, top cut at 2.8 kHz'
  evidence: qf_walkie TX table
- id: X04
  title: engine and gear-shift model facts
  keywords: [engine, gear, shift, rpm, firing frequency, single cylinder, V8, quickshifter, downshift, blip, ratio]
  symptom: a shift that sounds wrong or a script error "over the limit"
  cause: f0 = rpm x cylinders / 120; a shift multiplies the rpm by the new ratio over the old; a downshift two gears down can pass the limit
  fix: 'Drive.shift raises when the target is over the limit: lift (lower the rpm) first and shift one gear at a time; an upshift has a 90 ms power gap, a downshift a blip'
  evidence: scripts/timeline.py in quiet_frequency_trailer
- id: X05
  title: no sound before the first audible event, no late fades
  keywords: [sfx, preset, start, trigger, begin, window, fade, 0.5 s, audible]
  symptom: stem.dead on an effect that works in the mix
  cause: see S02
  fix: begin() at the first event; fades of 0.15 s or less
  evidence: S02
- id: X06
  title: SFX bursts and the opening pulse sit dry and sharp on top
  keywords: [dry sfx, walkie, burst, opening pulse, alarm, 3-4 kHz, reverb send, ping-pong, sub snap, reverse suck]
  symptom: 'listening note: stutters sit dry above the booms, the opening pulse is sharp on headphones, the last hit lacks weight'
  cause: fx role send 0.12 and no EQ on the alarm; the last hit had no lead-in or sub tail
  check: list the events at the noted times from the story clock (P08), then read the part's send and EQ
  fix: raise orchestral and fx sends and darken the return (9 kHz); PeakFilter -5 dB at 3.5 kHz plus ducked ping_delay on the alarm; 58 Hz sub snap on each walkie close; reverse suck then sub boom into the last hit
  avoid: 'a sfx spec envelope with tau and a long attack: tau decays from t=0 so the sound peaks at once (attack is a fraction of the length). A swell uses attack near 0.97 and no tau. Do not claim it works before a render and a listen'
  evidence: quiet_frequency_trailer v05 certified 2026-11-28 (0 FAIL, 119 WARN). Clicks at 116.4 s fixed by a rising suck envelope; then dropout 70 ms at 120.3 s (boom tail wobbling at the floor) fixed by a faster decay and an earlier end (119.6 s). Not listened to
---
