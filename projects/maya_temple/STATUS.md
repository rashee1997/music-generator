# The Temple Wakes - status

Delivered: master v04 (stereo, speaker decode), mono, 5.1, 7.1.4, AmbiX order 5, ADM (55 objects). Pipeline: CERTIFIED PASS, 0 FAIL, 22 WARN (see out/*.json).

## Self-check
- [x] pipeline.py ended with 0 FAIL; every WARN is a mix or flutter note, none is a loosened row
- [x] one score `gate` entry: `tempo.audio` skipped, with its measured reason in the score
- [x] arc measured (arc_report.py): integrated -14.6 LUFS, LRA 20.7 LU, loudest 3 s -10.8 LUFS, last section is the peak (vs top +0.0)
- [ ] arc agrees with the brief: NO in the opening. the_approach averages -33.5 LUFS and 0-28.5 s sits more than 12 LU under the integrated level; pressure share is 47 % (reference file says under 50 % reads as more atmosphere than threat)
- [x] expression_report.py: written notes follow declared section energy (rank correlation +0.97); figure line 2.49 bits interval entropy, 20 semitones, 54 % of bars repeat an earlier bar (warn limit 60 %)
- [ ] listen.py: NOT run (earshot not installed). Nothing here was auditioned.
- [ ] direction sheet has no `expression` block (written before that block existed): direction.expression is a WARN

## Honest limits
- Sounds: Sonatina SSO (free, dry); ritual calls, jungle night, steps and stone are synthesised from presets, researched from search-result text only; levels, f0 contours and bout rates are ESTIMATE.
- Stereo master is a loudspeaker decode (immersive.stereo_decode speakers); master high-pass 95 Hz order 4 and -14.5 LUFS were chosen to satisfy master.dc.
- The 7.1 layout files carry the wrong BS.2051 system letters (see README Limits).
- Mono, 5.1 and 7.1.4 are about 2 s shorter than stereo and AmbiX; not yet explained.
