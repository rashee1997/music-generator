# Into the Green Dark - status

Certified: `out/master.wav` (= `master_v05.wav`), -16.0 LUFS, -1.6 dBTP, 97.6 s score + tail (file 102.6 s).
Gate: 0 FAIL, 366 PASS, 23 WARN. Stem gate: 0 FAIL, 0 WARN, 291 rows.

Deliverables (each passed its own rows): stereo, mono (fold.mono +3.1 dB of 3.5), 5.1, 7.1.4, AmbiX order 5, ADM BW64 (66 objects).

## Self-check
- pipeline.py ended with 0 FAIL: yes (WARNs listed in the report)
- Ran listen.py: yes, measuring only (earshot not installed): loudness/true peak/clipping PASS, length CHECK (102.6 s against 97.6 s: the rain's tail)
- Listened to the audio: NO. Nothing was auditioned; taste, realism and fit are not measured.
- Intent words resolved, focus declared (melody), roles canonical: yes (gate rows pass)
- Presets cite research notes with `sources`: yes (reports/research_*.md)
- No synthesis, EQ or mixing in a script: yes (compose_main.py writes notes only)
