# Research step (knowledge base first, then web)

Moved verbatim from the old SKILL.md loop, step 0.

0. **Research Preflight (Mandatory before authoring presets or custom scores):**
   Before creating or scaffolding any instrument, vocal style, cultural fusion soul, DSP synthesis model, or ambient soundscape preset, conduct grounded ethnomusicological, acoustic, and environmental research in two distinct, sequential steps:
   - **Step 0.1 - Knowledge Base Consultation (First):** Search and read the internal `knowledgebase/` folder (`knowledgebase/*.md`, fully indexed in `knowledgebase/README.md`). The documents feature YAML frontmatter (`document_id`, `target_consumers`, `schema_version`) and a table of contents:
     1. *Compositional Flow & Emotion Ontologies:* `DYNAMIC_MUSICAL_FLOW_v2.md` (`DYNAMIC_MUSICAL_FLOW_AND_EXTENDED_GENRE_ONTOLOGY_V2`) and `PSYCHOACOUSTIC_GENRE.md` (`PSYCHOACOUSTIC_GENRE_AND_FEEL_ONTOLOGY_V1`).
     2. *Commercial, Corporate, Voice-Over & Reverb DSP:* `COMMERCIAL_CORPORATE_PROMO.md` (`COMMERCIAL_CORPORATE_PROMO_MUSICALS_AND_REVERB_DSP_V1`).
     3. *Interactive Game Music & Adaptive Audio:* `GAME_MUSIC_ADAPTIVE_DSP.md` (`GAME_MUSIC_ADAPTIVE_AND_INTERACTIVE_DSP_ONTOLOGY_V1`).
     4. *Interactive Game SFX & Combat/Locomotion Physics:* `GAME_SFX_INTERACTIVE_SYSTEMS.md` (`GAME_SFX_INTERACTIVE_SYSTEMS_AND_PHYSICS_DSP_ONTOLOGY_V1`).
     5. *Motion Graphics & Frame-Accurate Video Scoring:* `MOTION_GRAPHICS_VIDEO_SCORING.md` (`MOTION_GRAPHICS_VIDEO_SCORING_AND_KEYFRAME_SYNC_ONTOLOGY_V1`).
     6. *World & Ethnomusicological Traditions:* `PAN_INDIAN_MUSICAL.md` (`PAN_INDIAN_MUSICAL_TRADITIONS_AND_INSTRUMENT_DSP_ONTOLOGY_V1`), `The Arabic Desert Vocal.md` (`ARABIC_DESERT_VOCAL_AND_MAGICAL_CHORDS_ONTOLOGY_V1`), `tamil_music_dsp_knowledgebase.md` (`TAMIL_CARNATIC_KUTHU_DSP_ONTOLOGY_V1`), `arabic_dsp_knowledge.md` (`PAN_ARAB_MAQAM_IQAAT_DSP_ONTOLOGY_V1`), `afro_dsp_knowledge.md` (`PAN_AFRICAN_POLYRHYTHM_AND_DSP_ONTOLOGY_V1`), `chinese_japanese_dsp_knowledge.md` (`EAST_ASIAN_CHINESE_JAPANESE_DSP_ONTOLOGY_V1`), `rio_brazil_turkic_mogol_dsp_knowledge.md` (`AMERICAS_BRAZIL_CENTRAL_ASIAN_MONGOLIAN_DSP_ONTOLOGY_V1`), `western_dsp_knowledge.md` (`WESTERN_CLASSICAL_CINEMATIC_TRAILER_DSP_ONTOLOGY_V1`), and `world_music_dsp.md` (`GLOBAL_HUMMING_CELTIC_GERMANIC_BALKAN_GAMELAN_DSP_ONTOLOGY_V1`).
     7. *Procedural SFX & Ambience Physics:* `PROCEDURAL_SFX_AMBIENCE.md` (`PROCEDURAL_SFX_AMBIENCE_AND_ZERO_OVERLAP_MIXING_ONTOLOGY_V1`).
     8. *Timbral Analysis & Machine Audition Cloning:* `PROGRAMMATIC_AUDIO_CLONING.md` (`PROGRAMMATIC_AUDIO_CLONING_AND_TIMBRAL_ANALYSIS_ONTOLOGY_V1`).
     Extract the documented physical acoustics (formant frequencies, spectral balance, envelope dynamics), cultural idioms (modes/ragas/maqamat, ornamentation/gamakas, breathing pauses), rhythm matrices (Tala, Iqa, polyrhythmic Nadai cycles), and Python DSP synthesis algorithms already curated.
   - **Step 0.2 - Supplemental Web Research (Second):** Perform targeted web search to augment and cross-reference anything missing, contemporary production techniques (e.g., modern Anirudh/Rahman studio mixing tricks), specific artist aesthetics, or hyper-local folklore nuances not captured in the knowledgebase.
   - **Step 0.2b - Real ambient sounds and effects (required for every `env:` and `sfx:` sound in the score):** the knowledge base gives formulas,
     not measured real sounds. For each sound, the report gets a section `## Real-world references: <slug>` (create the stubs with
     `research_kb.py <project> --topic ... --sounds rain_roof,frog_chorus`). Find, with TinyFish `search` then `fetch_content`:
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
