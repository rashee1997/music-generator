# Previous SKILL.md workflow (archived; superseded by the project flow in SKILL.md)

Moved verbatim from SKILL.md to keep the entry file short.

## The loop

0. **Research Preflight (Mandatory before authoring presets or custom scores):**
   Before creating or scaffolding any instrument, vocal style, cultural fusion soul, DSP synthesis model, or ambient soundscape preset, conduct grounded ethnomusicological, acoustic, and environmental research in two distinct, sequential steps:
   - **Step 0.1 - Knowledge Base Consultation (First):** Search and read the internal `knowledgebase/` folder (`knowledgebase/*.md`, fully indexed in `knowledgebase/README.md`). All 17 documents feature machine-parsable YAML frontmatter (`document_id`, `target_consumers`, `schema_version`) and machine-parsable Tables of Contents:
     1. *Compositional Flow & Emotion Ontologies:* `DYNAMIC_MUSICAL_FLOW_v2.md` (`DYNAMIC_MUSICAL_FLOW_AND_EXTENDED_GENRE_ONTOLOGY_V2`) and `PSYCHOACOUSTIC_GENRE.md` (`PSYCHOACOUSTIC_GENRE_AND_FEEL_ONTOLOGY_V1`).
     2. *Commercial, Corporate, Voice-Over & Reverb DSP:* `COMMERCIAL_CORPORATE_PROMO.md` (`COMMERCIAL_CORPORATE_PROMO_MUSICALS_AND_REVERB_DSP_V1`).
     3. *Interactive Game Music & Adaptive Audio:* `GAME_MUSIC_ADAPTIVE_DSP.md` (`GAME_MUSIC_ADAPTIVE_AND_INTERACTIVE_DSP_ONTOLOGY_V1`).
     4. *Interactive Game SFX & Combat/Locomotion Physics:* `GAME_SFX_INTERACTIVE_SYSTEMS.md` (`GAME_SFX_INTERACTIVE_SYSTEMS_AND_PHYSICS_DSP_ONTOLOGY_V1`).
     5. *Motion Graphics & Frame-Accurate Video Scoring:* `MOTION_GRAPHICS_VIDEO_SCORING.md` (`MOTION_GRAPHICS_VIDEO_SCORING_AND_KEYFRAME_SYNC_ONTOLOGY_V1`).
     6. *World & Ethnomusicological Traditions:* `PAN_INDIAN_MUSICAL.md` (`PAN_INDIAN_MUSICAL_TRADITIONS_AND_INSTRUMENT_DSP_ONTOLOGY_V1`), `The Arabic Desert Vocal.md` (`ARABIC_DESERT_VOCAL_AND_MAGICAL_CHORDS_ONTOLOGY_V1`), `tamil_music_dsp_knowledgebase.md` (`TAMIL_CARNATIC_KUTHU_DSP_ONTOLOGY_V1`), `arabic_dsp_knowledge.md` (`PAN_ARAB_MAQAM_IQAAT_DSP_ONTOLOGY_V1`), `afro_dsp_knowledge.md` (`PAN_AFRICAN_POLYRHYTHM_AND_DSP_ONTOLOGY_V1`), `chines_japanese_dsp_knowledge.md` (`EAST_ASIAN_CHINESE_JAPANESE_DSP_ONTOLOGY_V1`), `rio_brazil_turkic_mogol_dsp_knowledge.md` (`AMERICAS_BRAZIL_CENTRAL_ASIAN_MONGOLIAN_DSP_ONTOLOGY_V1`), `western_dsp_knowledge.md` (`WESTERN_CLASSICAL_CINEMATIC_TRAILER_DSP_ONTOLOGY_V1`), and `world_music_dsp.md` (`GLOBAL_HUMMING_CELTIC_GERMANIC_BALKAN_GAMELAN_DSP_ONTOLOGY_V1`).
     7. *Procedural SFX & Ambience Physics:* `PROCEDURAL_SFX_AMBIENCE.md` (`PROCEDURAL_SFX_AMBIENCE_AND_ZERO_OVERLAP_MIXING_ONTOLOGY_V1`).
     8. *Timbral Analysis & Machine Audition Cloning:* `PROGRAMMATIC_AUDIO_CLONING.md` (`PROGRAMMATIC_AUDIO_CLONING_AND_TIMBRAL_ANALYSIS_ONTOLOGY_V1`).
     Extract the documented physical acoustics (formant frequencies, spectral balance, envelope dynamics), cultural idioms (modes/ragas/maqamat, ornamentation/gamakas, breathing pauses), rhythm matrices (Tala, Iqa, polyrhythmic Nadai cycles), and Python DSP synthesis algorithms already curated.
   - **Step 0.2 - Supplemental Web Research (Second):** Perform targeted web search to augment and cross-reference anything missing, contemporary production techniques (e.g., modern Anirudh/Rahman studio mixing tricks), specific artist aesthetics, or hyper-local folklore nuances not captured in the knowledgebase.
   - **Step 0.3 - Structured Research Report:** Synthesize findings from both the internal knowledge base and web research into a structured note saved in `reports/research_<topic>.md`. Never guess acoustic values or use generic hardcoded presets.
1. **Direct.** Fill in a direction sheet (`templates/direction_sheet.json`): purpose, feel, avoid, instruments,
   pulse, tempo range, mode, loudness, hit points, length. Ask only what you cannot guess. Fill the rest from the
   tables in `references/music-direction.md` and `references/emotion-and-scoring.md`, and state the defaults in one line.
2. **Plan, then draft.** Put `"plan": true` in the brief and `scripts/compose.py --brief brief.json` builds the
   section plan first (`scripts/plan.py`): an opening, development, build, climax, hush and reveal, and a release.
   Impact hit points start a climax; silence hit points make a hush and a reveal. Loudness, density, and whether
   the lead plays are separate curves, so the piece does not rise in lockstep. Read the plan
   (`python3 scripts/plan.py score.json`) and its CHECK lines before you render. Without `"plan"` the old single-curve
   draft is produced, unchanged. A copied `templates/custom_score_template.py` is still the route for anything
   specific (a theme, a chord sheet, exact timecodes, game layers).
3. **Direct the draft.** `scripts/direct.py` makes the decisions a director makes: `add_pulse` (a steady grid),
   `add_line` (a fanfare, a hook, a drone), `set_arc`, `set_gain`, `copy_track`, `tempo`, `remove_track`.
4. **Unified CI/CD Execution (Recommended Master Path):**
   Run the single unified orchestrator to execute all 7 stages from composition to certified release:
   ```bash
   python3 scripts/pipeline.py "motivational trailer in D minor, 30s" --out final.wav [--stems stems/] [--midi final.mid]
   # Or with an existing score:
   python3 scripts/pipeline.py score.json --out final.wav
   ```
   This executes acoustic pre-flight linting (Stage 2), humanization (Stage 3), stem rendering (Stage 4), Pedalboard mastering with `pb.BrickwallLimiter` (Stage 5), and the automated CI quality gate (Stage 6), outputting `ci_report.json` and a certified terminal scoreboard.
5. **Listen & Inspect.** For deeper inspection: `python3 scripts/listen.py cue.wav --direction sheet.json`.
   Each target comes back PASS, CHECK or FAIL with the numbers, plus the levers to try. For a planned piece also run
   `python3 scripts/section_report.py score.json cue.wav`: loudness, active tracks and lead per section, and the
   tail. Check that the climax is the loudest and densest section, that the opening is sparse, and that the ending
   has a tail. Then run `python3 scripts/quality_gate.py score.json cue.wav` for the copy-paste and clipping checks.
   Listen to the opening alone, the hush-to-reveal, the climax, and the last 8 seconds before you call it done.
6. **Analyze dynamically with music21 (Mandatory).** Author a custom analysis script tailored specifically to this
   piece's musical universe, cultural lineage, and emotional purpose using `music21` (see `references/music21-analysis.md`).
   Never use a rigid predefined script. Interrogate:
   - *Tonal & Modal Affect:* Krumhansl-Schmuckler / Temperley key determination, pitch-class distribution (e.g. verifying
     that major thirds and sixths dominate when adventure/heroism is requested, eliminating accidental minor-third sadness).
   - *Harmonic Qualities:* `score.chordify()` triad quality distributions (major vs minor vs open fifths).
   - *Melodic Contour:* Rising vs falling transition ratios, heroic ascending leaps vs sorrowful falling sighs.
   - *Voice Leading & Range:* Register separation, voice crossings, and instrument ambitus.
   - *Metric & Polyrhythmic Drive:* Metric accent weights (`analysis.metrical`), compound cross-rhythms (e.g. 12/8 Soli vs flat 4/4).
7. **Revise one lever** from the table in `references/music-direction.md` section 6 and the music21 findings. Render,
   listen, and analyze again. Stop when all targets pass.
8. **Deliver** the WAV, the MIDI, the filled sheet, the listen report, the custom music21 analysis report, and one or two variations.

## The 5-Stage Production Contract (archived; the enforced version is in SKILL.md)

Never write monolithic custom scripts that hardcode synthesis, notes, EQ, and mixing into one giant Python file. Every production follows the modular architecture established in `amazon_3d_spatial`:

```
<project>/
├── direction/
│   └── direction_<title>.json        # Stage 1: Direction & 3D Spatial Staging Intent
├── presets/
│   ├── instruments/                  # Stage 2a: Modular Instrument Presets (GM, role, humanize, EQ, 3D spatial)
│   ├── vocals/                       # Stage 2b: Formant & Choral Vocal Presets (vowels, formants, 3D spatial)
│   └── environments/                 # Stage 2c: 3D Spatial Soundscapes (layers, trajectories, foley)
├── scores/
│   └── <title>_score.json            # Stage 3: Declarative Master Score referencing presets by name
├── midi/
│   └── <title>_score.mid             # Standard MIDI export
├── stems/                            # Rendered stem tracks
├── reports/
│   ├── research_<topic>.md           # Ethnomusicological and acoustic research notes (NO CODE)
│   └── ci_report.json                # Automated CI/CD quality report
├── out/
│   └── master.wav                    # Certified release master audio
├── scripts/
│   ├── compose_main.py               # Custom composition script (populates score & executes pipeline)
│   └── analyze_music21.py            # Dynamic music21 analysis quality gate
└── STATUS.md                         # Milestone tracking and decisions
```

### Critical Rules for AI Agents:
1. **Never Monolithic (Anti-Pattern Ban):**
   - **FORBIDDEN:** Do NOT write 500-line monolithic scripts that synthesize raw waves or hardcode notes, EQ, and gains inside Python code.
   - Author modular JSON presets in `presets/`, declarative scores in `scores/`, and direction sheets in `direction/`. Detailed schemas & spatial rules: [`references/spatial-presets-and-scoring.md`](references/spatial-presets-and-scoring.md).
2. **Modular Presets Define Sound & 3D Space:**
   - Define instrument EQ, gains, reverbs, and 3D spatial coordinates (`azimuth`, `elevation`, `distance`, `space`) inside `presets/instruments/`, `presets/vocals/`, and `presets/environments/`.
   - In `scores/<title>_score.json`, tracks reference presets simply by name (`"instrument": "arabic_oud_lute"`). All acoustic and 3D spatial parameters are automatically inherited by `mixer.py`.
3. **Physical 3D Spatial Mixing for Realism:**
   - Physical acoustic realism is enforced automatically by `mixer.py` and `spatial.py`:
     - **Distance Air Absorption (ISO 9613-1):** High-frequency low-pass roll-off for sources at distance $d > 1.5\text{m}$.
     - **Distance Direct-to-Reverberant Ratio ($DRR$):** Level falloff + scaled reverberation return over distance.
     - **Apparent Source Width ($ASW$):** Narrow point leads vs wide diffused beds.
     - **3D Staging:** Elevated leads ($+4^\circ\text{ to }+8^\circ$), grounded bass ($-5^\circ\text{ to }-8^\circ$), azimuth separation across soundstage.
     - **Shared Acoustic Room:** All tracks route to the same convolution room space.
4. **Execution & CI/CD Pipeline:**
   - Run the master pipeline directly on the score:
     ```bash
     .venv/Scripts/python.exe scripts/pipeline.py scores/<title>_score.json --out out/master.wav --midi out/song.mid
     ```
   - Automatically registers `<project>/presets/`, adopts 3D spatial staging, renders stems, applies physical spatial mixing, and runs the 7-stage CI quality gate.
5. **Scaffolding New Projects:**
   - Use `setup_project.py` to scaffold the complete 5-stage architecture:
     ```bash
     python scripts/setup_project.py --new-project <project_path> --title "Piece Title"
     ```

Worked example (tested in this session): a trailer opener, "epic and triumphant, hit at 24 s, silence at 38 s,
steady drive". The first render read sad. A major mode at 104 BPM, a steady kick on every beat and a brass
fanfare on the reveal moved "epic" from a FAIL to a 55-65 % forced-choice pass, and the pulse from 0.04 to 0.5
(clear from 0.30). The remaining CHECKs were stated, not hidden. Recipe and numbers: `references/scene-recipes.md` section 1.
