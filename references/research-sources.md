# Research behind this skill: what was read, and what it changed

The earlier version generated every sound from equations, used a fixed grid, had almost no performance variation,
and mixed with one fixed chain. This version was reworked in two passes. The first added real samples, humanization,
emotion-driven composition, a mix and master, cloning and custom scripts. The second (this one) adds the **direction
workflow**: decide what the piece must do, render, listen, judge against the decision, revise one lever. It also
removed the legacy synth engine and the scripts that only served it.

Where a source could not be read in full, this file says so.

## 1. Direction and scoring practice (second pass)

| Source | What was read | What it changed |
|---|---|---|
| Eerola, Friberg & Bresin (2013), Frontiers in Psychology, "Emotional expression in music: contribution, linearity, and additivity of primary musical cues" | Full summary of the study: six cues, four excerpts, 200 stimuli, 46 listeners, two labs. Mode strongest for happy and sad (sr² about 0.5); dynamics for scary and peaceful; cues additive; no significant two-way interactions; limits stated | The order of decisions (mode, tempo, register, dynamics, articulation, timbre); the caution that the cues are tested on synthetic timbres and four excerpts |
| Juslin's mechanism review, Behavioral and Brain Sciences (2008), "Emotional responses to music: the need to consider underlying mechanisms" | Six mechanisms (brain stem reflex, emotional contagion, musical expectancy, evaluative conditioning, visual imagery, episodic memory), each with its composer-facing use | The mechanism table in `music-direction.md` section 3. The full framework also has rhythmic entrainment and aesthetic judgment; those are from background knowledge, not from the fetched text |
| Ableton, "Learn how to make high-impact sounds for movies and trailers" (fr locale) | Hits (layers low to high, transient plus reverb tail), risers (pitch and filter automation, peak then hit or silence), braams (octave-stacked low brass, pitched down), sub drops, silence before impact | The trailer construction in `music-direction.md` section 4. Downlifters and reverse cymbals were not covered by this page, so they are not described |
| Guy Jones on adaptive game music (gamedeveloper.com) | Vertical layering (base loop plus stems that fade), horizontal re-sequencing, synced transitions, loopable stems, 1-2 minute loops | The adaptive-music section and the three-state game recipe |
| beverlyboy.com, "What is a spotting session in film" | Who attends, the decisions (timing, emotional purpose, style, problem areas, timeline), cue construction against click tracks | The spotting section (how to turn a rough cut into direction sheets) |
| earshot (github.com/Leonxlnx/earshot, MIT), README, docs, skills, source | Two open models (CLAP text-audio similarity, AST AudioSet tags), measurements, forced-choice matching, timeline and pulse clarity (thresholds 0.30 clear, 0.15 weak), and its own warnings that mood labels are wrong about 1 in 5 and key estimates are weak | `scripts/listen.py` (the ears), the limits in `music-direction.md` section 7, and the install note in `setup_project.py` |

Not read in full: the IRPR Sound glossary on vertical layering (the redirect was not followed; the adaptive
definitions here come from the gamedeveloper article), and a Frontiers HTML page that was not on the allowlist (the
PDF version was read instead). Ableton's English page was not on the allowlist either; the French locale was used.

## 2. Open-source skills and repos (first pass, still used)

| Source | What it taught | Where it lives now |
|---|---|---|
| **Lemo-Opuscar** (github.com/lemomo-ai/lemo-opuscar) `core/audio/sampler.py` | Velocity-layer choice by distance in semitones and velocity, round-robin, softer notes darker, long notes extended with cross-correlation-aligned grains | `clone_instrument.py` (sampler mode); `natural-instruments.md` |
| **OpenMontage** (github.com/calesthio/openmontage) `skills/creative/sound-design.md`, `music-gen-usage.md`, `tools/audio/audio_mixer.py` | Platform loudness table, music 18-20 dB under narration, 6-12 dB ducks, a 2-4 kHz carve under speech, voice chain (HPF 80 Hz, 3:1), SFX timing, BPM/key/mood tables | `video_program_mix.py`, `mixing-and-mastering.md` |
| **GeneralUser GS** (github.com/mrbumpy409/GeneralUser-GS) | A free SoundFont for music, including commercial use | the default sample bank, `soundbank.py` |
| **TinySoundFont** | An SF2 synthesiser with velocity layers, controllers and pitch bend, no system fluidsynth needed | `render_natural.py` |
| **pedalboard** (Spotify), **pyloudnorm** | Studio EQ, compression, convolution; ITU-R BS.1770 loudness | `mixer.py`, `naturalness_check.py` |

## 3. Performance and acoustics (first pass, still used)

| Topic | Source | Used for |
|---|---|---|
| Melody lead | Goebl (2001), "Melody lead in piano performance: expressive device or artifact?" | Melody 10-30 ms ahead and louder (`humanize.py`) |
| Expressive performance rules | Friberg, Bresin, Sundberg, KTH rule system | Phrase arch, final ritardando, duration contrast |
| Microtiming | Studies of drummers' inter-beat intervals; 1/f drift; anti-correlated errors | Timing model: drift plus `e[i] - 0.5 e[i-1]`, standard deviation 7-15 ms |
| Vibrato | Singing and string vibrato studies (about 5-6.5 Hz) | Rate, depth and delay per note |
| Piano inharmonicity | `f_n = n f0 sqrt(1 + B n^2)` | `clone_instrument.py` harmonic mode |
| Pitch tracking | de Cheveigne & Kawahara (2002), YIN | Note segmentation and tuning in the cloner |
| Loudness | ITU-R BS.1770, EBU R128; YouTube, Spotify, Apple Podcasts, TikTok specs | Targets and true-peak ceilings (`mixing-and-mastering.md`) |

## 4. Instrument cloning (first pass, documented only where not run)

| Source | Status here |
|---|---|
| DDSP (Engel et al., ICLR 2020, Magenta) | Documented only; a neural clone needs a GPU and is not run in this environment |
| Few-shot DDSP (DAFx 2022) | Documented only |
| TokenSynth (zero-shot cloning from about 5 s) | Documented only; not verified here |

The DSP cloner in `clone_instrument.py` is classical: YIN, segmentation, multisampling, re-pitch with resampling,
or a harmonic model from a single note. Its measured numbers were on a stand-in recording, not on a real microphone
take.

## 5. Honesty about the numbers

The first pass reported measured differences between the old synth and the new pipeline (loudness, crest factor,
loudness range, timing spread). Those show differences in dynamics and performance. They do not show that a piece
sounds natural. The second pass added an ear (earshot). Its readings are model readings: useful for a forced choice
between two feel words, a pulse check, an instrument check and a version comparison. They are not a taste test, and
its mood labels are wrong about one time in five by its own account. Read `music-direction.md` section 7 before you
quote a reading to a user.

## 6. Genres and moods (third pass)

| Source | What was read | What it changed |
|---|---|---|
| Bühler, "Day of Honour" paper on epic film music | Epic as power, loudness, bombast, aggression; percussion battery, synth bass and choir as typical elements | The epic definition in `genres-and-moods.md` section 1; the percussion threshold in `compose.py` |
| Micallef Grimaud & Eerola (2022), film-music cue table (Durham repository) | Power and anger with minor, fast, loud; triumph and joy with major, fast, loud | Heroic `epic` (major) vs `dark_epic` (minor); the mood table in `emotion-and-scoring.md` |
| Northwestern University, braam page | The braam: low stacked brass, pitched down, a trailer device | A texture note on hits, not a whole-cue style |
| GEMS, Zentner et al. (2008), via the Wikipedia summary | Nine factors: wonder, transcendence, tenderness, nostalgia, peacefulness, power, joyful activation, tension, sadness | Aliases from each factor to a preset |
| Basic-emotion factor-analysis study (dovepress, abstract) | Basic-emotion factors | The basic-emotion mapping; disgust and surprise recorded as gaps |
| Tzanetakis & Cook (2002), genre classification (PDF) | Feature families: timbral texture, rhythmic content, pitch content | Context only; features for classification, not a recipe |
| musical-u rhythm guide (read through a search excerpt) | The hip-hop 16-step pattern (kick 1, 9, 11; snare 5, 13; eighth hats) | The `boom_bap` groove, labelled sourced |
| learningmusic tempo guide and musical-u | Genre tempo ranges | Cross-check for the practice tempos; not measured |

Not used: the orchestraltools page (its content is not recorded here). Full citations for the Bühler paper and the
dovepress study still need checking against their pages before anyone cites them.

Earshot tests on the new genres and moods are in `genres-and-moods.md` section 7. They are model readings with the
limits stated there: metal and drum and bass fail, and dark epic does not separate from heroic epic.


## 7. Pixabay Music genres (fourth pass)

| Source | What was read | What it changed |
|---|---|---|
| Pixabay API docs (curl, 200) | Image and video endpoints only; `/api/music/` returns 404 | Recorded that the API cannot list music genres; the key the user supplied is not stored in the skill |
| pixabay.com/music pages (shell: Cloudflare 403, not worked around) | Genre labels read through the session's page reader from locale pages, playlists and genre index pages; some pages returned the same listing | The label-to-genre map in `genres-and-moods.md` section 3a and `GENRE_ALIASES`; a sample, not the full catalogue |
| Three reference tracks the user attached (lo-fi courtyard, upbeat corporate, sport rock) | Measured with earshot: tempo, pulse, forced choice | `lofi` and `corporate` tuning; `rock` compared |

New genres written from that map are practice values (tempo ranges and grooves from common knowledge of the styles, cross-checked
against nothing measured). Their earshot readings are in `genres-and-moods.md` section 7.

**Models looked at and not added.** NanoMaestro Realtime (utkucoban, Hugging Face): a 14 MB or 54 MB piano-only note generator,
CC BY-NC-4.0, tested here with earshot (reads as solo piano, steady pulse) but not bundled because it is non-commercial and has no
mood, key or genre control. Stable Audio 3 (Stability AI): text-to-audio, weights gated on Hugging Face under the Stability AI
Community License, not downloaded.


## 8. World music pass (fifth pass)

Read with TinyFish search and fetch. Full list and the unverified items: `world-music.md` section 9.

| Source | What was read | What it changed |
|---|---|---|
| maqamworld.com (iqa'at index, maqsum, baladi, saidi, malfuf, wahda, ayyub, zaffa, masmudi kabir) | Dum and tak as the two basic sounds; time signature of each iqa'; "ornamentation depends on genre"; quarter-tones in rast, bayati, saba, sikah (search excerpt) | The Arabic cycles' lengths; the quarter-flat (-50 cent) degrees. Stroke positions are practice (the pages show notation as images) |
| ritmik.net, "Bendir Usulleri" | Nine Turkish usuller (2/4 to 10/8) with their dum-tek patterns | `CYCLES` nim_sofyan to curcuna, `sofyan` and `duyek` grooves |
| compmusic.upf.edu (usul examples) | Duyek 8/8 and aksak 9/8 | Cross-check |
| microtonaltheory.com (Turkish makams) | 53-comma system, comma about 22-23 cents, AEU | `makam_rast` cents (author's arithmetic from the comma steps) |
| ragajunglism.org (tala index); raag-hindustani.com and search results | Tala lengths (tintal 16, ektal 12, jhaptal 10, rupak 7, keherwa 8, dadra 6, others); the ten thaats | `GROOVES` teental and keherwa, `CYCLES` dadra to ektal, the `raga_*` scales |
| masterthescore.com (Japanese scales) | Hirajoshi, in/miyako-bushi, insen, iwato, yo, with koto and shakuhachi practice | `MODES` and the Japanese notes in `world-music.md` |
| Search results: ISMIR 2022 paper, CUNY textbook, Wikipedia (Chinese musicology) | Five Chinese modes as rotations of the pentatonic | `chinese_*` modes |
| lumbeat.com (Brazilian rhythms) | Rio and northeastern styles, instruments, tempo ranges | The Brazilian genres and tempos; groove shapes are practice |
| melodigging.com and songbrain.ai (K-pop) | Structure, killing part, drop, key change, tempo and harmony | The K-pop genres and the form advice |
| beatkey.app, Wikipedia, idiom.ucsd.edu (flamenco) | Phrygian dominant, Andalusian cadence, 12-count compas, tempo ranges | `phrygian_dominant`, flamenco genre, the 12-count cycles |
| gamelan pages (Wesleyan, Dartmouth, microtonaltheory.com) | Slendro near-equal five steps (240 cents ideal), pelog seven tones, each set tuned differently | `slendro`, `pelog` and the caveat |
| polyphone.io, dskmusic.com | SoundFont sources (not downloaded or tested) | Section 8 of `world-music.md` |

| spardhaschoolofmusic.com (types of Indian music) | Folk (bhangra, gidda, baul, bihu, lavani, maand, yakshagana), devotional (bhajan, qawwali, kirtan, shabad), film, indie, fusion | The 16 Indian genres added in the sixth pass |
| melodigging.com (Tamil film music) | Pallavi/anupallavi/charanam form, ragas (Kalyani, Kharaharapriya, Mohanam), adi / misra chapu (7) / kanda chapu (5), thavil, parai, mridangam, nadaswaram | `tamil_film`, `gaana`, `misra_chapu`, `kanda_chapu` |
| Search results: ragajunglism.org, shankarmahadevanacademy.com | Raga times of day; Hindustani-Carnatic equivalents (Bhairav = Mayamalavagowla, Bhairavi = Todi) | Carnatic mode names |

Not read: a Garba/Dandiya guide (furtadosschoolofmusic.com, unreachable), musical-artifacts.com (bot-blocked). The Arabic stroke skeletons are standard practice, not read from a page. No listening test (earshot or
human) has been run on the world genres.

Also fixed in this pass: `setup_project.py` asked for the current Python even when it was 3.11, but `requirements.txt` pins numpy 2.5, which needs 3.12; with uv it now
requests 3.12.

## 9. Genre fusion and country sub-styles (seventh pass)

Read through TinyFish (search, then fetch of the pages that returned text). The points in `genre-fusion.md` that come from these are marked there; the masking and consonance points are background knowledge.

| Source | What was read | What it changed |
|---|---|---|
| melodigging.com, "Indian Fusion" genre page | Raga-tala frameworks plus jazz, rock and electronic; tala under a backbeat ("hybrid feel"); tanpura or synth drone on Sa and Pa; modal harmony that avoids the raga's restricted notes; interleaved ambient interludes; history of Shakti, Asian Underground, A. R. Rahman | Rules 1 to 3 of `genre-fusion.md` section 1; recipe R4; section 2 |
| withfeeling.com, "Arabic Fusion Music" | Arabic scales and melodies over Western chord structures and instruments (a company page, so treated as a description, not a study) | Rule 3, the common-tones check |
| PBS Ken Burns, "How Country Music Genres Evolved" | Branches: singing cowboys, Western swing, bluegrass, honky-tonk, rockabilly, Texas shuffle, Nashville Sound, Bakersfield, Countrypolitan, outlaws; "it's all intertwined" | The country table in section 3 |
| Wikipedia, "Country music" (via search snippet) | Americana blends country, bluegrass, folk, blues, gospel, R&B, roots rock and southern soul | The Americana row |
| The Story of Texas, "Música Tejana" | The 12-string bajo sexto bass guitar and accordion, violin, saxophone as standard Tejano instruments | The Tejano row; the bajo sexto stand-in |
| Kennedy Center, "Music of the Gulf Coast Highway" (search snippet) | Tejano draws on corridos, norteño polkas, Anglo fiddle and mariachi | The Tejano row |
| Melodigging, "Tejano" (search snippet) | Accordion and bajo sexto, supported by electric bass and drum kit | The Tejano instrument set |
| Pirate Studios, "Recording and Mixing Techniques for Different Music Genres" | Parallel compression on drums, layered guitars, mono checking for club systems, sub and mid bass split, top-down versus bottom-up mixing | The glue checks in rule 7; the dance-mono check |
| TinyFish search only (not read in full): layering guides (Ear to the Ground, WA Production, a Reddit thread on blending genres) | Layering and blending advice; the WA Production page returned no text on fetch | Not used for any claim |

Not read: Smithsonian and TSHA conjunto pages (search snippets only); the Wikipedia Americana section in full. No listening test of the fusion recipes has been run.

## 10. Global music theory knowledge base (eighth pass)

The user supplied `global_music_theory_algorithmic_synthesis_guide.md` (in the skill folder) and asked for the skill to be updated from it. It is one author's document with no citations, so nothing from it is marked as sourced; the values added are labelled `practice` in `world.py`. The full mapping, the errors found and the gaps are in `references/global-theory-kb.md`.

| What was checked | Result | What changed |
|---|---|---|
| 55 KB scales against `world.MODES` and `theory.MODES` by interval set | 52 already present under another name or as a shape; 3 new | `ethiopian_tizita_maj`, `ethiopian_bati`, `western_octatonic` added |
| KB rhythm cycles against `world.CYCLES` | Most present; 4 missing | `adi_8`, `rupaka_3`, `samai_thaqil`, `gankogui_12_8` added (the rupaka grouping is the KB's and is unverified) |
| KB drum names (dum, tak, ka, riq, daf, taiko_don, ghatam, mridangam, bendir, talking_drum) | all in `soundbank` | none |
| KB section 8 helpers against the code | gamaka, meri, guzheng sweep and pentatonic spine missing; strum spread and phrase arch present in `humanize.py` | four helpers added to `theory.py`, covered by `tests/test_world_integrity.py` |
| KB section 10 golden rules against `humanize.py`, `pattern_audit.py`, `naturalness_check.py` | rules 2 and 3 enforced; 1, 4 and 5 not enforced; 6 by hand | listed in `global-theory-kb.md` section 5, not coded |

Not checked: a listening test of the new cycles and scales, and any render using the new helpers. `tests/test_world_integrity.py` passes.

## 11. Voices, choirs, sound effects and the quality gate (ninth pass)

Read through TinyFish: search results for formant synthesis, choir production and procedural sound effects; fetched pages: the CCRMA vocal-model comparison, the Aalto formant chapter (its text is long, and the vowel table was not in it), and the GDC procedural-audio slides (text returned). The vowel formants in `vocals.py` are from memory (Peterson and Barney style averages), not from a fetched table.

| Source | What was read | What it changed |
|---|---|---|
| CCRMA, "Vocal Models for Data Sonification" (fetched) | FM voice is cheap but hard to make convincing; formant (source-filter) synthesis for vowels | the choice of formant synthesis in `vocals.py` |
| Aalto thesis, chapter 5 (fetched, long) | three formants for intelligible speech, five for high quality; two-pole resonators; impulse train for voiced sound, noise for unvoiced | three resonators, glottal harmonics |
| Praat KlattGrid manual (search snippet) | example vowel "a" with F1 800 Hz, F2 1200 Hz; the Klatt design | the formant model; the example is not used as data |
| GDC slides, "Procedural Audio for Video Games" (fetched) | sound made in real time from exposed parameters | the seeded, parameter-driven generators in `sfx.py` |
| Production threads on choirs and stacked vocals (search snippets) | several singers slightly out of tune, different vibrato, spread across the stereo field; high-pass 100-150 Hz, cut 200-400 Hz, light glue compression | `render_choir` voice spread, pan, and the mix advice in `vocals-and-choirs.md` |
| Sound-design tutorials on whooshes, risers and impacts (search snippets) | filtered noise with a moving filter and level; impacts layered from low to high | `whoosh`, `riser`, `downlifter`, `impact` |
| Crackdown impact synthesis (search snippet, a paper) | physically based impact sound from a recorded hit | noted as the research route; not implemented |
| Fréchet Audio Distance studies (search snippets, arXiv 2311.01616) | FAD depends on sample-size bias, the embedding and the reference set | why the gate uses direct measurements, not FAD (`quality-gate.md`) |

Verified in this pass (self-tests and one test score):
- `vocals.py selftest`: vowel brightness ordering (i against u, hum against a) and a five-voice choir's finiteness and stereo spread.
- `sfx.py selftest`: 28 effects finite, right length, not silent, repeatable for a seed; the audio check rejects a bare tone and accepts a hit; a stereo timeline.
- A choir and a hum routed through `render_natural` and the gate (test score: loudness within 0.3 LU of its target, true peak −2.4 dBTP, no clicks, no silent gap; the pattern warnings are expected for an 8-bar loop).

Decision on Neural AI Generation:
All generative neural AI models (e.g. Stable Audio Open, MusicGen, AudioLDM) have been removed. Sound effects, composition, instrument cloning, and vocal formant synthesis are 100% deterministic, procedural, and physically modeled using DSP, SoundFonts, and Pedalboard.

## 12. Very small models for effects and voices (tenth pass)

Read through TinyFish (search results; fetched: the MOSS-TTS-Nano repository and Kyutai's Pocket TTS post).

| Model | Task | Size | Runs on CPU | Licence | Verdict for this skill |
|---|---|---|---|---|---|
| Pocket TTS (Kyutai, Jan 2026) | speech with voice cloning from about 5 s of audio | 100M (90M generator, 10M decoder) | yes, faster than real time on a laptop (fetched) | MIT | speech only, not singing; use for spoken lines |
| MOSS-TTS-Nano (OpenMOSS, Apr 2026) | multilingual speech, 20 languages, 48 kHz stereo | 0.1B | yes; ONNX CPU path (fetched) | Apache-2.0 (per the repository) | speech only; the strongest small option for narration |
| Kokoro | speech, fixed voices, no cloning | 82M | yes (search, Kyutai's comparison) | Apache-2.0 | speech only |
| Kitten TTS / Supertonic 3 | speech | about 99M and under | yes (search snippets) | not checked | speech only |
| LHQ-SVC (arXiv 2409.08583) | singing voice conversion, CPU-compatible | not stated in the snippet | yes (claimed) | not checked | needs a sung recording as input; not text-to-sing |
| MOSS-SoundEffect (in the MOSS-TTS family) | text to sound effects | 8B (fetched table) | not on this laptop | not checked | too large |
| Stable Audio Open Small | text to sound effects | 341M | ran out of memory here before | Stability community licence | the smallest SFX model found; too heavy for this laptop |
| AudioLDM 2 | text to audio and music | about 0.3B and up (search) | not tested | not checked | larger than Stable Audio Open Small |

Findings:
- No singing model was found that generates a sung line from text on a CPU. Pocket TTS, MOSS-TTS-Nano and Kokoro speak; they do not sing. LHQ-SVC converts a singer's recording, so it needs a human take.
- No tiny text-to-sound-effect model was found. The smallest that does the job is about 341M parameters, and it is too heavy for this laptop.
- So code synthesis is the only practical path for effects on this machine, and the choir stays formant synthesis. A speech model could be used for spoken lines (narration, announcements), not for choirs.

---

## 4. Physical sound engine (three-engine upgrade)

| Topic | Source | Status | What it changed |
|---|---|---|---|
| Contact sound, modal bank, friction, rolling | van den Doel, Kry, Pai, *FoleyAutomatic*, SIGGRAPH 2001 — https://www.cs.mcgill.ca/~kry/pubs/foleyautomatic/foleyautomatic.pdf | paper text read (already cited in `SFX_MODEL_FORMULAS.md`) | modal response driven by a contact force; `1 - cos` impact pulse; fractal surface for scraping |
| Modal synthesis with material and geometry separated | van den Doel & Pai, *Modal Synthesis for Vibrating Objects* — http://persianney.com/kvdoelcsubc/publications/modalpaper.pdf | indexed, not fetched | the material / geometry / strike-point split in `phys_core` |
| Brittle fracture sound | Zheng & James, *Rigid-Body Fracture Sound* (SIGGRAPH 2010) — https://www.cs.cornell.edu/projects/FractureSound/ | project page read | the event graph: stress -> crack impulses -> fragment bodies -> radiation |
| Footsteps | Turchet, Serafin, Dimitrov, Nordahl, DAFx-10 — https://dafx10.iem.at/papers/TurchetSerafinDimitrovNordahl_DAFx10_P50.pdf; Turchet 2016, Applied Acoustics — https://www.sciencedirect.com/science/article/abs/pii/S0003682X15001747 | abstract only | gait as a ground-reaction-force contact on a surface material, not a per-surface thump |
| Granular material sound | Marko, *Sound simulation of granular materials*, ACM SPY 2013 — https://www.itspy.cz/wp-content/uploads/2014/05/acmspy2013_submission_50.pdf | snippet | Poisson grain contacts with a size distribution |
| Porous absorption | Delany-Bazley-Miki — https://apmr.matelys.com/PropagationModels/MotionlessSkeleton/DelanyBazleyMikiModel.html | formulas read verbatim | leaves, fabric and soil get real absorption from flow resistivity |
| Rain impact | Guo, *Drop impact sound and rain noise*, JFM 1991 — https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/theoretical-study-on-drop-impact-sound-and-rain-noise/7A703959CA20067BB96BE8037030143E | abstract | momentum-dependent impact; the per-surface Hz table was dropped |
| Stick-slip | *Squeaking at soft-rigid frictional interfaces* — http://perso.univ-lemans.fr/~vtournat/wafx_res/Files/Squeaking_preprint.pdf; Harvard SEAS, *The Physics of a Squeak* — https://seas.harvard.edu/news/physics-squeak | snippets | stick-slip as a self-excited limit cycle, not an LFO |
| Peer system: Sound Design Toolkit (GPLv3) | https://skat-vg.github.io/SDT/ | page read | validated the decomposition (solid / liquid / gas / machine) and its "cartoonification" stance |
| Peer system: IRCAM Modalys | https://support.ircam.fr/docs/Modalys/3.4.1/co/Introduction.html | indexed | material and geometry as declared objects |

Not read in full: Turchet's DAFx-10 and journal papers, Zheng & James's PDF, Guo's paper, the squeak preprint and the
Modalys manual. Their *shapes* are used and cited above; their numbers are not claimed. Every place a number came
from judgement instead, the code says ESTIMATE.

## Use

Reference only (what was read and what it changed). New research goes into the project's `reports/research_<topic>.md` via `research_kb.py`, not here.
