# Cultural soul: what makes each music feel alive

The soul is the thing a listener recognises before they can name it. It is data, in `scripts/soul.py` (built-in table)
and `references/data/presets/soul/<culture>.json` and each project's `presets/soul/` (editable, one file per culture). `scripts/soul_check.py` checks a score against it
before release.

For complete mathematical definitions, instrument physics, frequency allocations, and pure-Python DSP algorithms, consult the authoritative machine-parsable knowledge bases in [`knowledgebase/`](../../knowledgebase):
- Pan-Indian & Hindustani Traditions: [`knowledgebase/cultures/pan-indian.md`](../../knowledgebase/cultures/pan-indian.md)
- Tamil Folk, Kuthu & Carnatic: [`knowledgebase/cultures/tamil.md`](../../knowledgebase/cultures/tamil.md)
- Arabic Desert Vocals & Magical Chords: [`knowledgebase/cultures/arabic-desert-vocal.md`](../../knowledgebase/cultures/arabic-desert-vocal.md)
- Pan-Arab Maqamat & Iqa'at: [`knowledgebase/cultures/arabic.md`](../../knowledgebase/cultures/arabic.md)
- East Asian (China & Japan): [`knowledgebase/cultures/chinese-japanese.md`](../../knowledgebase/cultures/chinese-japanese.md)
- Sub-Saharan & West African Polyrhythms: [`knowledgebase/cultures/african.md`](../../knowledgebase/cultures/african.md)
- Americas, Brazil (Samba/Bossa) & Central Asian Throat-Singing: [`knowledgebase/cultures/brazil-turkic-mongolian.md`](../../knowledgebase/cultures/brazil-turkic-mongolian.md)
- Global Humming Atlas, Celtic, Nordic, Balkan & Gamelan: [`knowledgebase/cultures/world-other.md`](../../knowledgebase/cultures/world-other.md)
- Western Classical, Film & Trailer Scoring: [`knowledgebase/cultures/western.md`](../../knowledgebase/cultures/western.md)

---

## Indian (Hindustani and Carnatic)
- **Hindustani vs. Carnatic Ear:** Hindustani moves through continuous *Meend* sigmoid glides and cyclic *Sam/Khali* balance, whereas Carnatic uses angular oscillatory *Kampita* gamakas and additive *Kanakku* subdivisions.
- **The 10 Thaats & Prahar:** Bilawal (Ionian), Kalyan (Lydian), Khamaj (Mixolydian), Kafi (Dorian), Asavari (Aeolian), Bhairav (Double Harmonic), Bhairavi (Phrygian), Todi, Purvi, Marwa. Each thaat commands a specific time of day (*Prahar*).
- **Sitar & Tanpura Jawari:** Parabolic bridge buzz (*Jawari*) produces dynamic non-linear overtones up to 12 kHz, triggering sympathetic resonance in 11–13 *Taraf* steel strings running beneath frets.
- **Tabla Physics:** Center black tuning paste (*Syahi*) loads the membrane non-uniformly, tuning circular Bessel modes into near-integer harmonic ratios. Left-hand *Bayan* delivers non-linear pitch bends.
- **Regional Folk Ecosystems:** Punjab *Dhol Chaal* (3+3+2 triplet bounce), Rajasthan Manganiyar *Kamaicha* & *Khartal*, Bengal Baul (*Ektara/Khamak*), Sufi Qawwali claps and harmonium ecstasy. Detailed in [`knowledgebase/cultures/pan-indian.md`](../../knowledgebase/cultures/pan-indian.md).

## Tamil (temple and festival)
- **Nadaswaram and thavil:** a melodic wind and a barrel drum in partnership; the thavil is the rhythmic partner
  to the nadaswaram in temple and ceremonial music. (kalasudha.com, ragarasa.in)
- **Power and ritual:** the music marks festivals and temples; the drums carry it. (prastara.in)
- **Parai, thambattam, urumi:** festival percussion. (instagram Tamil culture post, June 2026)

## Tamil Folk, Gaana & Dappankuthu (Street & Festival Kuthu)
- **Tisra Nadai (6/8 compound bounce):** Authentic Tamil Kuthu lives in a galloping 6/8 triplet bounce (12 subdivisions per bar, "DA-ka-ta DA-ka-ta"). Straight 4/4 or syncopated Latin piano montunos instantly break the illusion; Kuthu requires galloping compound swing.
- **Thavil and Parai interlock:** The buffalo-hide Parai drives the continuous syncopated gallop (`[0, 2, 3, 5, 6, 8, 9, 11]`), while the Thavil delivers heavy stick backbeats (`3, 9`) and sharp plaster-capped finger whips on upbeats (`1, 4, 7, 10`).
- **Gumtha Sub-Bass:** The signature chest-hitting low-end thump. Synthesized with a sine wave dropping rapidly from 150 Hz to 55 Hz over 80 ms with soft-clipping tanh saturation on the primary Doums.
- **Urumi Melam (sweeping friction drum):** The signature hypnotic curved drum sound that sweeps up and down in pitch like a siren (120 Hz -> 280 Hz -> 120 Hz over 0.5s) right before drops and transitions.
- **Double-Reed Nadaswaram & Gamakas:** Nadaswaram or Mizmar lead synthesized via pulse/saw wave through dual resonant bandpass/formant filters (centered at 800 Hz–1.5 kHz) with nasal saturation. Every note scoops 30–50 cents flat over the first 40 ms, with 6–7 Hz embouchure/vibrato wobble on sustained notes. Never play flat, static Western frequencies.
- **Hype Energy:** Sharp street finger-whistles (2.5 kHz to 3.2 kHz upward swoop with breath noise) on transition drops, backed by raw folk rhythm shouts ("Thannane!", "Hey!", "Aiyo!").

## West African
- **Call and response:** a leader creates a melody and the group answers; the basis of the music. (study.com, pressbooks.cuny.edu)
- **Polyrhythm:** several conflicting rhythms in one piece; the tension is the point. (scalar.usc.edu)
- **Cyclical grooves:** the 12/8 bell (seven strokes over twelve pulses) is the timeline of Ewe, Yoruba and Bembé
  drumming and the basis of the Cuban 6/8 clave. (rhythmdictionary.com, britannica.com, uvic.ca)
- **Kora:** kumbengo (thumb bass pattern) under birimintingo (fast index-finger melodic runs). (alpharhythmroots.com, thekoracafe.com, metmuseum.org)
- **Griot tradition:** the jeli carries history and song. (melodigging.com)

## Western tonal
- **Tension and release:** dissonance and cadence create the narrative; the cadence lands home. (fretboardfoundation.com)
- **Major and minor:** major mode conveys happy, bright or martial; minor, sad or tender (Bowling et al., 2012, pmc.ncbi.nlm.nih.gov).
- **Dynamic contrast and climax:** build, peak, release. (serenademagazine.com)
- **Film cadences:** a cadence's placement shapes the emotional arc (Lehman, MTO 2013).

## Chinese
- **Pentatonic:** the gong, shang, jue, zhi and yu modes; the gong hexatonic is most used. (pressbooks.cuny.edu)
- **Qin (guqin) aesthetics:** tied to yin-yang thought; three kinds of tone (open string, stopped, harmonic); the
  music is built on restraint and on the slow sounding of a note. (torguqin.wordpress.com, en.wikipedia.org Guqin)
- **Guzheng:** the five-tone system creates a peaceful, flowing character. (anniezhouguzheng.com)
- **Qi and breath:** the phrase is a breath; the rest between phrases is part of the line (general aesthetics sources).

## Japanese
- **Ma:** the silence or space between sounds, felt as part of the music. (newmusicusa.org, ethnomusicologyreview.ucla.edu)
- **Shakuhachi:** breath and tone colour are the expression; the silence is not empty. (ethnomusicologyreview.ucla.edu)
- **Yo:** a bright pentatonic scale in Japanese music. (pressbooks / general sources)

## Arabic
- **Maqam with a feeling:** Rast pride and power; Bayati warmth, joy and tenderness; Hijaz longing and mystery;
  Saba sadness and pain; Sikah love; Nahawand sadness or nostalgia. (en.wikipedia.org Arabic maqam, classicalarabicmusic.com)
- **Tarab:** the state in which the listener is carried by the music. (general sources)
- **Quarter-tone notes** and the iqa (rhythmic mode) define the sound. (oudforguitarists.com)

## Celtic
- **Lilt and dance:** jigs and reels in 6/8 and 9/8; the fiddle sings, the drone holds the ground.

## How to add a culture
1. Research the soul: what the music is for, its rhythm, what the phrase does, what the rest means.
2. Write `references/soul/<culture>.json` with the fields in `scripts/soul.py`, citing the sources in this file.
3. Add its scales, tempo and instruments to `scripts/fusion.py` (CULTURES).
4. Run `soul_check.py` on a piece in that culture before release.

## Fields the gate checks
`feel` (words, shown in the report), `breath_beats` (rest between phrases), `groove` (`offbeat`, `cycle`, or none),
`call_response`, `ornament`, `cadence`, `tempo`, `avoid_instruments`.

---
