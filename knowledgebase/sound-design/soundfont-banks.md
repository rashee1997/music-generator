---
id: soundfont-banks
title: SoundFont banks - what each optional bank is for and what it costs
domain: sound-design
status: unverified
sources: []
used_by: [scripts/soundbank.py, scripts/soundfont_fetch.py, scripts/render_natural.py, knowledgebase/sound-design/soundfont-velocity-and-realism.md]
updated: 2026-11-23
---

> **Not verified**: no bank other than the default was heard, loaded or downloaded when this was written (the network
> allowed none of their hosts). `measured` means a number taken from a file on disk here; `from the request` is a size
> or licence the request gave; `starting value` is advice nobody has auditioned. Every line is a question until it is listened to.

# SoundFont banks

`assets/soundfonts/MANIFEST.json` is the list of banks, their licences and their checksums. `generaluser_gs` is the
default and everything else is optional; a score that names no bank plays exactly as before.

| Bank | Size | Preset order | Licence | Use it for (starting value, not auditioned) |
|---|---|---|---|---|
| `generaluser_gs` | 32.3 MB, measured | General MIDI | GeneralUser GS licence, permissive (from the request) | everything by default; synth pads, leads, effects, drum kits |
| `timgm6mb` | 6.0 MB, measured | General MIDI | GNU GPL v2 (from the request) | smoke tests and CI where RAM or time is the limit; never for a deliverable |
| `muse_general` | about 206 MB, from the request | General MIDI | MIT (from the request) | piano, solo and ensemble acoustic instruments, winds |
| `fluid_r3_gm` | about 142 MB, from the request | General MIDI | MIT (from the request) | brass, percussion, synth sounds that need more punch |
| `sonatina_sf2` | about 517 MB, from the request | its own, not General MIDI | CC Sampling Plus 1.0 (from the request) | solo and ensemble strings, winds, brass and orchestral percussion |

## How a track picks its bank

| Where | Key | Effect |
|---|---|---|
| score track | `"soundfont": "muse_general"` | that track plays that bank |
| instrument preset | `"soundfont": "sonatina_sf2"` | every track using the preset plays that bank, unless the track says otherwise |
| neither | | `generaluser_gs` |
| preset or track | `"program_map": {"sonatina_sf2": {"bank": 0, "program": 12}}` | the preset to play inside a bank whose order is not General MIDI; `"drums": true` for a kit |

A bank that is not in General MIDI order (`gm_order: false` in the manifest) and has no `program_map` entry for the
instrument is an error naming the key to add, never a silent guess. No bank or program number of such a bank is written
in code. The numbers belong to the bank, so read them from the bank (a SoundFont editor, or the list the file carries)
before writing the map; they are not known here.

## Memory

| Fact | Status |
|---|---|
| tinysoundfont parses a whole `.sf2` into RAM, so a 517 MB bank costs about its file size while loaded | from the request; the size in RAM was not measured |
| The renderer plays one bank at a time: tracks are grouped by bank, each group is rendered, the bank's synths are freed and `gc.collect()` runs before the next bank loads and before the mixer and the gate run | `scripts/render_natural.py` (`build_stems`, `release_synths`), exercised by `tests/test_multi_soundfont.py` |
| A score that plays only the default bank keeps its synth cached between builds, as before | tested |
| Tracks of one bank still render in parallel up to `resources.stem_workers`; each worker holds a copy of the bank, so a big bank with many workers multiplies its cost | from reading the code, not measured |

## Licences

Banks are fetched by `python scripts/setup_project.py --soundfonts <names|all>` into `assets/soundfonts/`, ignored by git, and
`assets/soundfonts/LICENSES.md` is written from the manifest for each bank on disk. GPL-2.0-only data (`timgm6mb`) and
Sampling Plus data (`sonatina_sf2`) are used at run time and never committed or re-hosted by this repository; whether
a rendered file's licence is affected by the bank that played it is a question for each bank's own licence text,
which was not read here.

## Audit and default banks (starting values)

`scripts/soundbank_audit.py <bank>` measures, per instrument family, the velocity zones behind the family's programs (`sf2_read.py`),
the spectral-centroid ratio of the same note at velocity 120 over 40, the 8-16 kHz share and whether the note sustains, and writes
`assets/soundfonts/audit/<bank>.json`. Measured here (2026-11): MuseScore General and GeneralUser GS have 0 velocity zones and a centroid ratio
of 1.00 for every orchestral family; TimGM6mb has 0 zones. `references/data/presets/banks/default.json` lists, per family, which banks may
be the default and the thresholds (2 layers, ratio 1.15, starting values); the first installed bank that meets them wins, else GeneralUser GS.
`scripts/soundbank_build.py` builds a multi-layer SF2 from WAV samples with a licence read for every source. Candidate CC0 sources
(VSCO 2 Community Edition, VCSL, CC0 Orchestra compilation) were not downloaded here: the host refused (403), so none has been heard.
