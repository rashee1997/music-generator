# Documentation

Everything a reader or an agent needs beyond the front page. Each entry below is a file in this folder unless stated otherwise.

## Files in this folder

| File | What it is | When to open it |
|---|---|---|
| [README.md](README.md) | This index — the map of every document, plus the engine's known limits. | First, to find the right file. |
| [PSYCHOACOUSTICS.md](PSYCHOACOUSTICS.md) | The perceptual laws the gate enforces: thresholds, equations and the peer-reviewed sources behind each one (Chew, Huron, Moore–Glasberg, Plomp–Levelt, Sethares, Witek, Krumhansl, Pearce, Meyer, ITU-R BS.1770). | When a gate row cites a perceptual rule, or when you need the citation for one. |
| [listen.html](listen.html) | The audio player page served by GitHub Pages, because GitHub strips `<audio>` from Markdown. Plays `../assets/samples/black-jaguar-cinematic-chase.mp3`. | When you want to hear a rendered demo. |
| [audits/2026-11-03-mixer-video.md](audits/2026-11-03-mixer-video.md) | The mixer, DSP, gate and `video-mixer/` audit from 2026-11-03: every number measured on this machine during the pass, and no code changed for it. | When you need the evidence behind a mixing or video-path number. |

## Documents outside this folder

The README links here rather than repeating these:

| Path | What it covers |
|---|---|
| [../SKILL.md](../SKILL.md) | What the skill does and the eight-step workflow. |
| [../AGENTS.md](../AGENTS.md) | The rule book: read table, research requirements, preset rules, gate profile choice, self-check. |
| [../references/](../references/) | The reference set — brief reading, music direction, mixing and mastering, quality gate, vocals, spatial audio, SFZ libraries, video scoring, troubleshooting. |
| [../knowledgebase/](../knowledgebase/) | Genre, culture and DSP knowledge: Indian, Arabic, African, East Asian, Latin, Western, electronic, game, video. |
| [../templates/](../templates/) | Project scaffold, direction sheet and custom score templates. |
| [../scripts/helpers/](../scripts/helpers/) | Certification helpers: standard metadata (`presets/metadata/metadata.json`), master versioning into `out/master_vNN.wav` with `out/versions.json`, and manual MP3 compression. |

## Limitations

These are properties of the engine, not bugs. Any delivery should state them.

**Sound**

- The default bank is a General MIDI SoundFont. It is good, not concert-grade; a real multisampled library (SFZ) must be installed per project and even then is a free library, not a commercial one.
- Synthesised voices have no words and no consonants. Choirs, "oohs" and hums are texture, not language, and a hum-to-vowel change starts a new phrase.
- Vocal styles are literature-informed profiles, not authentic reproductions of a tradition.
- Traditional idioms (raga, maqam, regional ornament) are approximations unless a preset or a user recording supplies the real sound.

**Judgement**

- The pipeline cannot hear. Numbers and `listen.py` stand in for ears; the first render is a draft.
- `listen.py` needs earshot; without it the report is measurement only, and the reply must say the ears did not run.
- Even with earshot, it is a model's opinion: it cannot judge taste, whether a raga or maqam is correct, whether an instrument sounds convincing, or how the music sits against picture.
- Aesthetic fit, realism and taste are never measured, only the technical gates are.

**Spatial and mix**

- The default mix pans, filters by distance, sets width and shares one room. Head-related delays, elevation and `space` apply only to presets with `spatial.binaural: true`.
- Mix diagnostics measure energy, correlation and crest per band. They report; they never edit, and no threshold in them is a statement of taste.
- Loudness targets are standard summaries (−16 LUFS default, true peak ≤ −1.5 dBTP). Verify against the current platform spec before publishing.

**Picture**

- Nothing in the video path is auditioned by `listen.py`; it judges the music bed, not the bed under speech.
- Cut detection (`scdet`) misses fades and dissolves, so detected cuts are candidates, not an edit list.

**Scope**

- The engine produces the music and its measurements. It does not master for a specific loudness war, does not guarantee a commercial release, and does not replace a mixing engineer's judgement on a finished record.
