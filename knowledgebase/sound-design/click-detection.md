---
# Not verified: each line is what a search result or the project's own notes said about the page; none was opened in the session that moved this list
id: click-detection
title: Click detection methods behind the gate and the debug engine
domain: sound-design
status: partly-sourced
sources: [https://essentia.upf.edu/reference/std_ClickDetector.html, https://pub.dev/packages/audio_defect_detector, https://lirias.kuleuven.be/retrieve/731585, https://sigproc.eng.cam.ac.uk/Main/SJGSpringer, https://arxiv.org/pdf/2608.15685]
used_by: [references/mixing/debug-engine.md, scripts/gate_checks.py, scripts/audio_debug/forensics.py]
updated: 2026-11-26
---

> **Not verified.** The list was moved here from `references/mixing/debug-engine.md`, where it was a list of links; the
> pages above were not opened when it was moved. Read each as "a method of this family exists", not as a calibration of
> the gate's thresholds (those are measured in `references/mixing/gate-maths.md`).

# Click detection methods behind the gate and the debug engine

| Method | What it is | Where this repository uses the idea | Basis |
|---|---|---|---|
| Noise-power threshold click detector | a detector with a threshold set from the noise power of the signal | `gate_checks.check_clicks` (a threshold that follows the signal's own floor) | per project note (Essentia `ClickDetector` documentation) |
| MAD-based local-noise detection | threshold = MAD x 1.4826 x k over a local window | the modified z-score `0.6745 (x - median) / MAD` in `check_clicks` | per project note (a Dart package's documentation) |
| High-pass residual detection | detect a click as an outlier in the high-passed signal | the 6 kHz high-pass first difference in `check_clicks`; it fails on high-frequency-rich material, which is why a dense burst and a steep attack are rejected | per project note (KU Leuven thesis) |
| Autoregressive prediction error | a click is a sample the signal's own AR model cannot predict | the order-16 LPC check in `check_clicks` | per project note (Godsill and Rayner, *Digital Audio Restoration*) |
| Sham intervention | run the probe with no change first, and trust the replay only if it reproduces the baseline | `forensics.validate` in the debug engine: a replay that cannot reproduce the gate's own events is labelled UNVERIFIED | per project note (an arXiv preprint) |
