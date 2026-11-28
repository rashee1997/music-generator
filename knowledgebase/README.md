# Knowledge base

Facts about music and sound: scales, rhythms, instrument physics, genre feel, formulas. Each file opens with
front matter that says what it is and how far its numbers can be trusted; `status: unverified` means the values
are practical starting points, not measurements.

Read one file at a time. `scripts/research_kb.py` pulls the file a piece needs.

| File | Use it for | Status |
|---|---|---|
| `cultures/african.md` | African polyrhythm, griot instruments and modern club tempo and groove values | unverified |
| `cultures/arabic-desert-vocal.md` | Desert vocal formants, vowel bloom and maqam-safe chord voicings | unverified |
| `cultures/arabic.md` | Maqam intervals, iqa'at cycles and Arab instrument ranges | unverified |
| `cultures/brazil-turkic-mongolian.md` | Samba and bossa swing, Amazonian and Andean patterns, haka and throat singing | unverified |
| `cultures/chinese-japanese.md` | Chinese and Japanese scales, instrument timbres and modern genre values | unverified |
| `cultures/flutes.md` | Flute physics, breath and ornament rules, and per-flute DSP parameters | unverified |
| `cultures/indian-film-fusion.md` | Rhythm-first layering, gamaka curves, tala grids and film-mix carving | unverified |
| `cultures/pan-indian.md` | Hindustani thaats and taals, Punjabi, Rajasthani, Sufi and Bengali rhythms | unverified |
| `cultures/tamil.md` | Tamil scales, gaana and kuthu feel, gamaka curves and tala grids | unverified |
| `cultures/western.md` | Western harmony, groove timing and trailer conventions | unverified |
| `cultures/world-other.md` | Humming formants, Celtic rhythms, Germanic motorik and Balkan metres | unverified |
| `genre-and-feel/cinematic-hybrid-scoring.md` | Pressure carriers, tension devices, trailer shape, film-music loudness figures and sample-library realism | partly-sourced |
| `genre-and-feel/emotion-cues.md` | Which musical cues carry emotion (mode, tempo, register, dynamics, articulation, timbre), their direction of effect, and why valence is hard to measure | partly-sourced |
| `genre-and-feel/commercial-promo.md` | Commercial tempo, ducking and voice-over rules, musical-theatre build | unverified |
| `genre-and-feel/dynamic-flow.md` | Section flow rules and lo-fi, ambient, horror, jazz, rock and game values | unverified |
| `genre-and-feel/short-form-functional-music.md` | Phone-speaker band, hook and alert length, alarm and wake-up findings, and the working figures for a ringtone or alarm | partly-sourced |
| `genre-and-feel/orchestral-writing.md` | Playable ranges, polyphony and note rates for orchestral parts a SoundFont plays, parallel fifths and octaves, legato overlap | partly-sourced |
| `genre-and-feel/psychoacoustic-genre.md` | Genre and mood tempo, interval, timbre and reverb values | unverified |
| `media/game-score-dos-and-donts.md` | What a game score should and should not be: platform loudness, loops, layers, states, ducking, instrument families per state | partly-sourced |
| `media/film-scene-score-dos-and-donts.md` | What a scene-based film underscore should and should not be: spotting, hit points, speech band, dialogue carve, instrument families per scene | partly-sourced |
| `media/game-music.md` | Stem layers, transition modes and loop folding | unverified |
| `media/game-sfx.md` | Hit variation, impact stages, footstep surfaces and interface tones | unverified |
| `media/video-scoring.md` | Frame-locked tempo, hit windows and voice-over ducking bands | unverified |
| `sound-design/low-end-and-virtual-bass.md` | Where a theatrical low end goes missing (master high-pass, the sub row), virtual bass for headphones and small speakers, the theatrical tone | unverified |
| `sound-design/sample-realism-equations.md` | Why a SoundFont part sounds like MIDI and the per-note laws (brightness and attack follow velocity) that fix part of it, with ensemble-timing and vibrato figures | unverified |
| `sound-design/audio-cloning.md` | Pitch, timbre, groove and room values read from a recording | unverified |
| `sound-design/click-detection.md` | The click-detection methods the gate and the debug engine rest on: noise-power and MAD thresholds, high-pass residual, autoregressive prediction error, sham intervention | partly-sourced |
| `sound-design/roughness.md` | Auditory roughness: level, masking, critical-band and register values, and the pair model | partly-sourced |
| `sound-design/virtual-ears.md` | Peripheral auditory model stages (middle ear, cochlear filtering and compression, hair cell, adaptation) and the quantities the gate reads from them | partly-sourced |
| `sound-design/layout-3-2.md` | Three-front layout with two low-frequency channels: what is and is not a standard, bass management, fold-down | partly-sourced |
| `sound-design/expectation-idyom.md` | Information content and entropy from a PPM model, and their link to expressive timing | partly-sourced |
| `sound-design/valence-arousal.md` | Valence and arousal: what an audio arc can say about feeling, the mode templates, the limits of the prediction | unverified |
| `sound-design/soundfont-banks.md` | The optional SoundFont banks: size, preset order, licence, what each is for, how a track picks one, and the memory cost of loading several | unverified |
| `sound-design/soundfont-velocity-and-realism.md` | SF2 velocity-to-cutoff, what SF3 is, and orchestral realism techniques; working figures for `velocity_timbre` | partly-sourced |
| `sound-design/sfx-ambience.md` | Weather, bio-acoustic and street ambience models, and blending laws | unverified |
| `sound-design/sfx-formulas.md` | The formulas behind `sound_model.py`, each labelled with where it came from | unverified |
| `sound-design/biome-acoustics.md` | The medium (bulk state, one absorption law, interfaces), weather micro-physics, creature sources and tracts, niche overlap and the score's pockets | partly-sourced |
| `sound-design/theatrical-realism.md` | The eight couplings a theatrical mix has and a clean synthetic one lacks: timbre vs loudness, ensemble scatter, register and transients, direct-to-reverberant depth, low-mid vs sub, air absorption, air at density, macro rubato | partly-sourced |
| `sound-design/virtual-speaker-qa.md` | Standard loudspeaker arrangements, AllRAD decoding of order-5 AmbiX to a virtual array, and per-bar channel-fault thresholds | partly-sourced |

See `SCHEMA.md` for the header format and the rules a new file follows.
