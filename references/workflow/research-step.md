---
title: Research step
summary: The research a piece needs before direction: knowledge base first, web second, decisions written down.
tags: [research, knowledge base, sources, decisions, brief]
load_when:
  - the start of any piece
  - a culture, instrument or voice is unfamiliar
---

# Research step (knowledge base first, then web)


0. **Research Preflight (Mandatory before authoring presets or custom scores):**
   Before creating or scaffolding any instrument, vocal style, cultural fusion soul, DSP synthesis model, or ambient soundscape preset, conduct grounded ethnomusicological, acoustic, and environmental research in two distinct, sequential steps:
   - **Step 0.1 - Knowledge base consultation (first):** the files in `knowledgebase/` are indexed in
     `knowledgebase/README.md`. Each opens with front matter (`id`, `title`, `domain`, `status`, `sources`, `used_by`).
     Read the file for the tradition, genre or sound you are about to write, and quote its `id` in the research note:
     1. *Flow, mood and genre archetypes:* `knowledgebase/genre-and-feel/dynamic-flow.md`, `knowledgebase/genre-and-feel/psychoacoustic-genre.md`.
     2. *Commercial, corporate and voice-over:* `knowledgebase/genre-and-feel/commercial-promo.md`.
     3. *Game music:* `knowledgebase/media/game-music.md`; *game effects:* `knowledgebase/media/game-sfx.md`.
     4. *Video scoring:* `knowledgebase/media/video-scoring.md`.
     5. *Traditions:* `knowledgebase/cultures/pan-indian.md`, `knowledgebase/cultures/tamil.md`, `knowledgebase/cultures/arabic.md`, `knowledgebase/cultures/arabic-desert-vocal.md`,
        `knowledgebase/cultures/african.md`, `knowledgebase/cultures/chinese-japanese.md`, `knowledgebase/cultures/brazil-turkic-mongolian.md`,
        `knowledgebase/cultures/western.md`, `knowledgebase/cultures/world-other.md`, `knowledgebase/cultures/flutes.md`, `knowledgebase/cultures/indian-film-fusion.md`.
     6. *SFX and ambience:* `knowledgebase/sound-design/sfx-ambience.md`, and the formulas in `knowledgebase/sound-design/sfx-formulas.md`.
     7. *Cloning an existing recording:* `knowledgebase/sound-design/audio-cloning.md`.
     Extract the documented physical acoustics (formant frequencies, spectral balance, envelope dynamics), cultural idioms (modes/ragas/maqamat, ornamentation/gamakas, breathing pauses), rhythm matrices (Tala, Iqa, polyrhythmic Nadai cycles), and Python DSP synthesis algorithms already curated.
   - **Step 0.2 - Supplemental Web Research (Second):** Perform targeted web search to augment and cross-reference anything missing, contemporary production techniques (bus-separated film-mix carving, sidechain habits), regional production aesthetics, or hyper-local folklore nuances not captured in the knowledgebase.
   - **Step 0.2b - Real ambient sounds and effects (required for every `env:` and `sfx:` sound in the score):** the knowledge base gives formulas,
     not measured real sounds. For each sound, the report gets a section `## Real-world references: <slug>` (create the stubs with
     `research_kb.py <project> --topic ... --sounds rain_roof,frog_chorus`). Find, with a web search and then a page fetch:
     - at least two sources of the real sound, of these kinds: a published acoustics or bioacoustics paper (drop-size distribution, impact
       frequencies, call rates, spectra); the page of a field recording (place, equipment, season, distance, weather); a measured spectrum;
     - the place matters: rain on leaves, on a tin roof and on a lake are three different sounds, so cite the surface and the rate you are making;
     - `Licence:` for each recording (analysis only unless it says more) and the value you took from it (`Measured:` line);
     - measure what you hold with `scripts/ambience_reference.py measure <wav> --slug <slug> --project <dir>`: it keeps centroid, rolloff, band
       shares and event rate, never the audio. Measure at least two recordings of the sound when you can; one is a weak anchor;
     - if nothing measurable exists, write `No measurement found: ESTIMATE <reason>` so the preset is marked as unmeasured, not made to look measured.
     The preset lists these slugs in `"sources"`. The project gate blocks a score whose `env:` or `sfx:` preset has none.
   - **Preset brief (in the report):** for every room and every ambience the user asked for, write what is audible, which parts are beds and
     which are spots, the weather, and the room's size and surfaces. The presets are written from this brief (`environments-as-presets.md`).
   - **Step 0.3 - Structured Research Report:** Synthesize findings from both the internal knowledge base and web research into a structured note saved in `reports/research_<topic>.md`. Never guess acoustic values or use generic hardcoded presets. Rain, water, wind, fire, birds and insects are ambience (`env:` presets), not `sfx:`.
