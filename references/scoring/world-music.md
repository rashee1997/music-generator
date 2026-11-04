# World music: scales, instruments, rhythm and genres

Use this file when the brief names a country, a tradition or a world instrument: Indian (Hindustani, Carnatic, Bollywood,
bhangra), Arabic, Turkish, Persian, Greek, Chinese, Japanese, K-pop and Korean, Indonesian, Rio and Brazilian, Latin,
Caribbean, African, Andean, Celtic, flamenco, klezmer, and the older Western styles. Everything here lives in
`scripts/world.py` (data) and is merged into `compose.py`, `theory.py`, `soundbank.py`, `humanize.py` and
`render_natural.py`. `python3 scripts/world.py` prints every scale, cycle and genre it knows.

Labels follow `genres-and-moods.md`: **sourced** = read for this skill (section 9); **practice** = common practice or the
author's approximation, not measured on a corpus.

---

## 0. Authoritative Machine-Parsable Knowledge Base Index

For exact acoustic models, microtonal cent offsets, frequency band allocations, and pure-Python synthesis code, consult the primary knowledge base files in [`knowledgebase/`](../../knowledgebase/README.md):

- **Pan-Indian Traditions & Hindustani 10 Thaats:** [`knowledgebase/cultures/pan-indian.md`](../../knowledgebase/cultures/pan-indian.md)
- **Tamil Folk, Kuthu & Carnatic Classical:** [`knowledgebase/cultures/tamil.md`](../../knowledgebase/cultures/tamil.md)
- **Arabic Desert Vocals & Magical Maqam Chords:** [`knowledgebase/cultures/arabic-desert-vocal.md`](../../knowledgebase/cultures/arabic-desert-vocal.md)
- **Pan-Arab Maqamat & Iqa'at Cycles:** [`knowledgebase/cultures/arabic.md`](../../knowledgebase/cultures/arabic.md)
- **East Asian (Chinese Wu Sheng & Japanese Onkai):** [`knowledgebase/cultures/chinese-japanese.md`](../../knowledgebase/cultures/chinese-japanese.md)
- **Sub-Saharan African Polyrhythms & Amapiano:** [`knowledgebase/cultures/african.md`](../../knowledgebase/cultures/african.md)
- **Americas, Brazil (Samba/Bossa) & Central Asian Throat Singing:** [`knowledgebase/cultures/brazil-turkic-mongolian.md`](../../knowledgebase/cultures/brazil-turkic-mongolian.md)
- **Global Humming Atlas, Celtic, Nordic, Balkan & Gamelan:** [`knowledgebase/cultures/world-other.md`](../../knowledgebase/cultures/world-other.md)
- **Western Classical, Orchestral, & Trailer Sound Design:** [`knowledgebase/cultures/western.md`](../../knowledgebase/cultures/western.md)

---

## 2. Pick by region

Tempo is the range the genre uses (practice unless noted). **Mode** is the default scale; override with `--mode`.
Lead and colour instruments are the stand-ins in section 4.

| Region | Genre (`--genre`) | Default mode | BPM | Lead / colour | Rhythm |
|---|---|---|---|---|---|
| India | `hindustani` (alias raga, sitar) | raga_yaman | 60-92 | bansuri, sarangi, santoor, tanpura drone | teental |
| | `carnatic` | raga_bhairav | 90-130 | violin, bansuri, veena | adi (8) |
| | `bollywood` (filmi) | raga_bhairavi | 96-128 | strings, bansuri, sitar, santoor | dholak groove |
| | `bhangra` (punjabi) | mixolydian | 100-126 | tumbi, shehnai, synth | dhol |
| | `qawwali` (kawali) | raga_bhairavi | 108-140 | harmonium, sarangi, claps | dholak, 4 claps |
| | `ghazal` (thumri, dadra, urdu) | raga_kafi | 66-90 | harmonium, sarangi, santoor | keherwa |
| | `dhrupad` (pakhawaj) | raga_asavari | 48-70 | rudra veena, sarangi, tanpura | pakhawaj (chautal 12) |
| | `bhajan` (kirtan, shabad, aarti, abhang) | raga_khamaj | 72-104 | harmonium, bansuri, tanpura | dholak, manjira, claps |
| | `sufi` (sufiana) | raga_kafi | 74-104 | harmonium, sarangi, nylon guitar | dholak, daf |
| | `tamil_film` (kollywood, telugu, malayalam, kannada) | raga_kharaharapriya | 90-128 | strings, violin, nadaswaram, mandolin | kit + thavil |
| | `gaana` (kuthu, dappankuthu) | raga_asavari | 108-138 | nadaswaram, synth, bass | parai, thavil |
| | `kuthu_tisra` (dappankoothu_6_8, marana_gana) | raga_mayamalavagowla | 118-142 | nadaswaram, urumi, whistle | parai, thavil, gumtha_sub |
| | `retro_filmi` (old_hindi, 70s_bollywood) | raga_bhairavi | 100-130 | strings, accordion, sitar, mandolin | bongo, conga |
| | `indipop` (hindi_pop, indie_india) | major | 98-122 | guitar, piano, bansuri | kit + tabla |
| | `indian_lofi` (hindi_lofi) | raga_kafi | 68-88 | e-piano, bansuri, sitar | soft kit + tabla |
| | `desi_hiphop` (indian_hip_hop, desi) | raga_asavari | 84-102 | sitar, 808 bass, santoor | trap-style kit + dhol |
| | `garba` (gujarati, raas, navratri) | raga_khamaj | 112-142 | harmonium, shehnai, bansuri | dhol, 3 claps |
| | `dandiya` | raga_khamaj | 130-164 | harmonium, shehnai, santoor | dhol, stick clicks |
| | `lavani` (marathi) | raga_kafi | 116-148 | harmonium, sarangi, tumbi | dholki, manjira |
| | `baul` (bengali, rabindra_sangeet) | mixolydian | 78-108 | ektara, dotara, harmonium, bansuri | hand drum, manjira |
| | `rajasthani_folk` (maand, ghoomar, manganiyar) | raga_khamaj | 100-136 | kamaicha, algoza, harmonium | dholak, khartal |
| | `bihu` (assamese, northeast_indian) | raga_bhoopali | 120-152 | pepa, gogona, guitar | dhol, claps |
| | `chenda_melam` (kerala, melam, thavil) | raga_mayamalavagowla | 110-150 | kuzhal, drums only otherwise | chenda, thavil, elathalam |
| Arabic | `arabic_pop` | maqam_hijaz | 92-112 | arabic violin, oud, qanun, strings | maqsum |
| | `tarab` (maqam) | maqam_rast | 70-104 | violin, ney, oud, qanun | wahda |
| | `dabke` (levantine) | maqam_hijaz | 116-140 | mijwiz, oud | dabke |
| | `mahraganat` (shaabi) | maqam_hijaz | 120-140 | mizmar, synth | electro-shaabi |
| Turkey | `turkish_classical` (ottoman) | makam_hicaz | 68-108 | kemence, ney, oud, kanun | duyek |
| | `turkish_folk` (anatolian, zeybek) | makam_ussak | 84-120 | saz, baglama, zurna | 4/4 zeybek |
| | `arabesk` | makam_hicaz | 86-108 | kemence, strings, oud | maqsum |
| Persia, Greece, Balkans, Spain | `persian` | persian_shur | 76-108 | kamancheh, santur, ney, tar | tombak |
| | `greek` (rebetiko, syrtaki) | makam_hicaz | 92-124 | bouzouki, baglamas, accordion | two-step |
| | `klezmer` (balkan, jewish) | freygish | 104-150 | clarinet, violin, accordion, tuba | oom-pah |
| | `flamenco` (andalusian, spanish) | phrygian_dominant | 96-124 | nylon guitar, cajon, palmas | rumba flamenca |
| China | `chinese_classical` | chinese_gong | 58-92 | erhu, guzheng, dizi, pipa | none |
| | `guofeng` (chinese_style) | chinese_yu | 88-112 | dizi, guzheng, erhu + electronic kit | synth-pop |
| | `cpop` (mandopop, cantopop) | major | 68-92 | piano, guzheng, strings | soft pulse |
| Japan | `japanese_traditional` (koto, wafu) | hirajoshi | 54-88 | shakuhachi, koto, shamisen | none |
| | `wadaiko` (matsuri, taiko) | yo | 100-148 | shinobue, koto, taiko | matsuri |
| | `enka` | miyako_bushi | 60-80 | shakuhachi, strings, shamisen | soft pulse |
| | `jpop` (anime, j-rock) | major | 124-168 | piano, saw lead, guitar | 4/4 pop rock |
| | `city_pop` | major | 98-120 | rhodes, sax, slap bass, guitar | funk-pop |
| Korea | `kpop` | major | 96-126 | synth, piano, saw lead, 808-style kit | kpop |
| | `kpop_dance` (kpop_edm) | minor | 116-132 | stabs, square lead, pad | four on the floor |
| | `kpop_ballad` (korean ballad) | major | 66-84 | piano, strings, cello | soft pulse |
| | `trot` (ppongjjak) | korean_gyemyeonjo | 112-140 | accordion, guitar, violin | two-step |
| Indonesia | `gamelan` (javanese, balinese) | slendro | 60-96 | gender, bonang, gong, suling | kendang |
| Rio, Brazil | `samba_enredo` (rio, carnaval, batucada) | major | 128-142 | bateria, cavaquinho, trumpet | escola de samba |
| | `pagode` (samba de roda, partido alto) | major | 86-108 | cavaquinho, 7-string guitar, flute | pagode |
| | `choro` (chorinho) | minor | 80-108 | flute, 7-string guitar, cavaquinho | pandeiro |
| | `funk_carioca` (baile funk, tamborzao) | minor | 128-150 | 808 bass, square lead, stabs | tamborzao |
| | `baiao` (xote, xaxado) | mixolydian | 86-116 | accordion, guitar | zabumba and triangle |
| | `maracatu` | dorian | 86-112 | alfaia drums, trumpet | maracatu |
| | `axe` (bahia) | major | 120-140 | guitar, trumpet, slap bass | axe |
| | `samba_reggae` (samba rock) | dorian | 84-104 | trombone, skank guitar | surdo |
| | (older) `samba`, `bossa`, `forro` | | | | already in the skill |
| Latin | `bachata` | minor | 116-136 | steel guitar, nylon arpeggio | bongo and guira |
| | `merengue` | major | 126-160 | accordion, sax | tambora |
| | `tango` (argentine) | harmonic_minor | 112-132 | bandoneon, violin, piano | marcato |
| | `mariachi` (ranchera, mexican) | major | 100-132 | trumpet, violin, vihuela, guitarron | none |
| | `bolero` (son) | minor | 66-88 | nylon guitar, trumpet | soft pulse |
| | (older) `salsa`, `cumbia`, `reggaeton` | | | | already in the skill |
| Caribbean | `soca` | major | 120-150 | steelpan, brass | soca |
| | `calypso` (steel band) | major | 100-128 | steelpan, guitar | calypso |
| Africa | `highlife` | major | 100-126 | highlife guitar, trumpet, sax | highlife |
| | `soukous` (congolese) | major | 112-140 | soukous guitar | soukous |
| | `amapiano` | minor | 108-116 | log drum, rhodes, pad, pan flute | amapiano |
| | `kora` (griot, west african) | african_pentatonic | 88-118 | kora, balafon, mbira | djembe and hosho |
| | `mbira` (zimbabwean) | mbira_mixolydian | 96-124 | mbira | hosho |
| | (older) `afrobeat` | | | | already in the skill |
| Andes, Pacific | `andean` (huayno, peruvian) | andean_minor | 92-124 | quena, zampona, charango | huayno |
| | `hawaiian` (polynesian, slack key) | major | 80-108 | ukulele, slack key guitar | brush |
| Europe, Americas | `celtic` (irish, scottish) | celtic_dorian | 100-126 | fiddle, tin whistle, guitar | bodhran |
| | `country` (nashville, honky tonk) | major | 96-132 | acoustic guitar, steel, fiddle | two-step |
| | `bluegrass` (appalachian) | mixolydian | 120-160 | banjo, fiddle | none |
| | `blues` (twelve bar) | blues | 70-104 | clean and overdrive guitar, organ | shuffle feel (swing 0.66) |
| | `gospel` | major | 70-110 | organ, piano, choir | clap on 2 and 4 |
| | `swing` (big band) | major | 140-190 | sax, brass, piano | brush |
| | `disco` | minor | 108-124 | guitar chops, strings, slap bass | four on the floor |
| | `baroque` | major | 80-120 | harpsichord, violin, cello | none |
| | `medieval` (renaissance) | dorian | 84-112 | recorder, lute, hurdy-gurdy | tabor |
| | `viennese_waltz` (waltz) | major | 150-186 | strings, violin | 3/4 |
| | `chiptune` (8-bit) | minor | 120-168 | square lead, arpeggio | rock |

## 3. Scales

`MODES` are semitones from the tonic (so the chord code works). `MICRO` is the real tuning in cents per scale degree.
Pass the name as `--mode` or `"mode"` in the brief. Chord symbols are read against the scale (`VII` = the scale's 7th degree).

| Tradition | Names | Notes (from the tonic) | Label |
|---|---|---|---|
| Hindustani | `raga_bilawal` `raga_yaman` `raga_khamaj` `raga_kafi` `raga_asavari` `raga_bhairavi` `raga_bhairav` `raga_purvi` `raga_marwa` `raga_todi` (the ten thaats, Yaman standing for Kalyan) | major, lydian, mixolydian, dorian, aeolian, phrygian, Bhairav [0 1 4 5 7 8 11], Purvi [0 1 4 6 7 8 11], Marwa [0 1 4 6 7 9 11], Todi [0 1 3 6 7 8 11] | thaat names sourced; **just-intonation cents** are practice |
| | `raga_bhoopali` `raga_durga` `raga_malkauns` `raga_hindol` | pentatonic: [0 2 4 7 9], [0 2 5 7 9], [0 3 5 8 10], [0 4 6 9 11] | practice |
| Arabic | `maqam_rast` `maqam_bayati` `maqam_sikah` `maqam_saba` | quarter-flat (-50 cents) notes: rast on the 3rd and 7th, bayati and saba on the 2nd, sikah on the tonic and 5th | practice; "rast, bayati, saba, sikah carry quarter-tones" is sourced |
| | `maqam_hijaz` `maqam_hijaz_kar` `maqam_nahawand` `maqam_kurd` `maqam_ajam` `maqam_nikriz` | 12-note: hijaz [0 1 4 5 7 8 10], hijaz kar [0 1 4 5 7 8 11], nahawand = harmonic minor, kurd = phrygian, ajam = major, nikriz [0 2 3 6 7 9 10] | practice |
| Turkish | `makam_rast` | with the Arel-Ezgi-Uzdilek comma steps (9-8-5-9-9-8-5) as cents: +4, -15, -2, +2, +6, -13 | modern theory counts 53 commas of 22.6 cents (sourced); the arithmetic is the author's |
| | `makam_ussak` `makam_hicaz` `makam_nihavent` `makam_kurdi` | ussak is bayati (quarter-flat 2nd); the others are 12-note approximations | practice |
| Persian | `persian_shur` | bayati-like with a quarter-flat 2nd | practice |
| Flamenco, klezmer, Greek | `phrygian_dominant` (= `freygish`), `ukrainian_dorian`, `hungarian_minor` | [0 1 4 5 7 8 10], [0 2 3 6 7 9 10], [0 2 3 6 7 8 11] | sourced for the Phrygian dominant in flamenco |
| China | `chinese_gong` `chinese_shang` `chinese_jue` `chinese_zhi` `chinese_yu` | the five rotations of C D E G A: [0 2 4 7 9], [0 2 5 7 10], [0 3 5 8 10], [0 2 5 7 9], [0 3 5 7 10] | sourced |
| Japan | `hirajoshi` [0 2 3 7 8], `miyako_bushi` (= the in scale) [0 1 5 7 8], `insen` [0 1 5 7 10], `iwato` [0 1 5 6 10], `yo` [0 2 5 7 10], `ryukyu` [0 4 5 7 11] | | sourced (masterthescore.com); ryukyu practice |
| Korea | `korean_gyemyeonjo` [0 3 5 7 10] (the plaintive minor pentatonic of trot and folk), `korean_pyeongjo` [0 2 5 7 9] | | practice |
| Indonesia | `slendro` (five near-equal steps, 240 cents if exactly equal), `pelog` (shown as its 5-note subset) | cents for slendro: +40, -20, +20, -40 | sourced that every gamelan is tuned differently; the numbers are the 5-equal ideal, not any real set |
| Andes, Africa, Celtic | `andean_minor`, `african_pentatonic`, `mbira_mixolydian`, `celtic_dorian` | | practice |

Older names still work: `hijaz`, `double_harmonic`, `blues`, `pentatonic_major`, `pentatonic_minor`, `whole_tone`, the seven modes.

### Microtones and slides in your own score

Every note can carry two optional fields, and `humanize.py` and `render_natural.py` pass them through:
- `"c": -50` is cents off equal temperament (the note's pitch bend). The track then gets one channel per note automatically.
- `"gl": -200` starts the note that many cents off and slides in over 0.14 s (an ease-in, quadratic). Use -100 for a kan, -200 for a meend.

```python
notes = [dict(t=0, d=2, p=64, v=.7, c=-50),            # E half-flat in a maqam rast on C
         dict(t=2, d=1, p=67, v=.7, gl=-200)]          # slide up into G
```
`compose.py` fills `c` from the mode automatically on every pitched layer, and `gl` on layers that set `glide` (0 to 1, the share of
notes that slide). Measured here (render, then a pitch reading): `c=-50` gives -48 to -50 cents and `c=+50` gives +47 to +50 on a violin,
an oud and a ney. The glide reads low and arrives on pitch.

**Harmony rule for microtonal modes.** A maqam's neutral third clashes with a major or minor chord third. The maqam, makam, raga and
shur genres therefore use a drone (root and fifth) plus `sus2` chords (`Isus2`, `IVsus2`). Keep that when you write a progression, or
leave the chords out and let the drone and the percussion carry the harmony. The chords themselves stay in equal temperament.

## 4. Instruments (stand-ins)

`python3 scripts/soundbank.py --list` prints every name. Use them as `"instrument": "oud"` in a track or a genre layer.
Quality is **good for the GM family, stylised for the tradition**: the SoundFont is a fixed General MIDI set, so each name below is played
by the nearest General MIDI sound. Plucked world instruments get flat loudness; bowed and blown ones get bow or breath
swell and a wide, slow vibrato (erhu 30 cents, sarangi 34, ney 12...).

| Region | Names → played as |
|---|---|
| India | sitar, tanpura, veena → sitar · sarod, tumbi... → steel guitar / banjo · santoor → dulcimer · bansuri → flute · shehnai, nadaswaram → shehnai · sarangi, esraj, dilruba → viola · swarmandal → harp · indian_harmonium → harmonium |
| Arabic, Turkish, Persian, Balkan | oud, ud, tanbur, tar, setar → nylon guitar · qanun, kanun → harp · ney, nay, kawala → shakuhachi · mijwiz, mizmar, zurna → oboe · duduk → english horn · kemence, kamancheh, arabic_violin → violin · rebab, gadulka → viola · saz, baglama, bouzouki, baglamas → steel guitar · santur, santouri, cimbalom → dulcimer · gaida, tulum → bagpipes |
| China | erhu, gaohu → violin · zhonghu → viola · guzheng, zheng, guqin → koto · pipa → banjo (bright, tremolo-like; use nylon guitar for a softer pipa) · ruan, liuqin → nylon guitar · yangqin → dulcimer · dizi → piccolo · xiao → shakuhachi · sheng → harmonica · suona → oboe · xun → ocarina |
| Japan, Korea | koto, shamisen, biwa, shakuhachi (direct GM) · shinobue, fue, daegeum → flute · sho → harmonica · gayageum, geomungo → koto · haegeum → violin · piri → oboe |
| South-east Asia, Pacific | gamelan_gender → vibraphone · gamelan_saron → glockenspiel · gamelan_bonang → tinkle bell · gamelan_gong → tubular bells · suling → flute · angklung → marimba · ukulele, slack_key → nylon / steel guitar |
| Africa | kora → harp · ngoni → banjo · balafon, log_drum → marimba · mbira, likembe → kalimba · guembri → acoustic bass · masenqo → viola |
| Latin America | charango → banjo · quena → shakuhachi · zampona, siku → pan flute · cuatro, vihuela, requinto, cavaquinho, violao → nylon guitar · tres, bandolim → steel guitar · guitarron → acoustic bass · steelpan → steel drums · bandoneon (direct) |
| Europe, Americas | mandolin → steel guitar · balalaika → banjo · bagpipe, uilleann_pipes → bagpipes · tin_whistle → recorder · concertina, hurdy_gurdy → accordion · melodica → harmonica · lute, theorbo → nylon guitar · viola_da_gamba → cello · cornet, flugelhorn → trumpet · euphonium, sackbut → trombone · cembalo → harpsichord · wurlitzer → electric piano · hammond → tonewheel organ · dobro, lap_steel, pedal_steel → steel guitar · theremin → synth voice · chiptune_lead, 8bit → square lead |

**Percussion** (`DRUM_KEYS`, on the `standard` kit): `dum tak ka` (darbuka and doumbek), `riq daf bendir`, `tabla_ge tabla_na tabla_tin tabla_ti tabla_ka`,
`dholak_bass dholak_treble dhol_bass dhol_stick mridangam_thom mridangam_tha ghatam kanjira manjira`, `taiko_don taiko_ka taiko_high janggu buk`,
`djembe_bass djembe_tone djembe_slap shekere hosho talking_drum`, `surdo surdo_mute tamborim repinique caixa pandeiro_hit pandeiro_slap agogo_hi agogo_lo ganza
cuica_open cuica_mute guiro_long`, `zabumba_bass zabumba_treble`, `cajon_bass cajon_slap palmas`, `bombo caja guira tambora_low`. They are General MIDI
percussion keys (congas, bongos, toms, woodblocks, cuica, guiro...), so a "darbuka dum" is a low conga. Good for rhythm; not a recording.

Ranges: stay inside the real instrument's range. `compose.py` clamps the lead to 52-82, or 60-88 for flute, violin, oboe, fiddle, celesta, vibraphone, saw lead and muted trumpet; other world leads get the 52-82 window.

## 5. Rhythm

### Grooves (16-step grid, 4/4)
Used by the genres above and by `drums` in a brief (`"drums": "maqsum"`). Names: `teental keherwa bollywood bhangra qawwali adi garba dandiya lavani bihu baul bhajan sufi dhrupad rajasthani chenda gaana tamil_film desi_hiphop indipop retro_filmi indian_lofi`,
`maqsum baladi saidi wahda ayyub dabke mahraganat sofyan duyek zeybek_4 tombak`, `taiko_matsuri trot kpop kpop_dance city_pop jpop gamelan_kendang`,
`pagode partido_alto samba_enredo baiao maracatu frevo funk_carioca choro axe samba_reggae`, `bachata merengue tango ranchera soca calypso highlife soukous
amapiano kora_6 huayno rumba_flamenca oompah bodhran two_step disco gospel_clap`.

Rules that make them correct:
- **Arabic 4/4 iqa'at are one eight-matra skeleton on the 16-step grid** (each matra = 2 steps): maqsum D T . T D . T . ; baladi D D . T D . T . ;
  saidi D T . D D . T . ; wahda has a single dum. Lengths are sourced from maqamworld.com (maqsum 4/4 "by far the most widely used"; baladi = masmudi saghir 4/4;
  saidi 4/4; wahda 4/4; malfuf 2/4; ayyub 2/4; zaffa 4/4; masmudi kabir 8/4). The stroke positions are the standard dum/tak skeletons from practice, because
  the pages show the notation as pictures. Real players ornament them; add a second hand-drum layer for that.
- **Turkish duyek = maqsum's strokes** (Dum Teek Tek Dum Teek over 8 beats; sourced), so the two grooves are the same pattern with different names.
- **Teental**: Dha Dhin Dhin Dha | Dha Dhin Dhin Dha | Dha Tin Tin Ta | Ta Dhin Dhin Dha, one matra per sixteenth step. Set the bpm to a quarter-note beat
  of four matras (60-92 bpm means 240-370 matras a minute, a fast fusion tempo; slow vilambit teental is not what this does).
- **Keherwa** (8 matras) runs on eighth notes: Dha Ge Na Ti Na Ka Dhi Na.
- **Rio**: `samba_enredo` is the escola-de-samba battery (surdo on 2, caixas steady, tamborim and agogo patterns, repinique calls). Tempo for school samba is
  fast (128-142). Grooves in the 90-136 range are for the drum-set samba styles. See tempo notes in section 6.

### Cycles of any length (`world.CYCLES`, `world.cycle_notes`)
For anything that is not 4/4: Turkish usul and Indian tala. One cycle is `beats` counting units (matras). Set the score bpm to the matra, `ts` to `[beats, 4]`,
and use the helper in a custom score (`references/workflow/custom-scripts.md`):
```python
import sys; sys.path.insert(0, 'scripts'); from world import cycle_notes
drums = cycle_notes('aksak', bars=16, vel=.7, matra=1.0)       # 9 matras per bar, matra = one score beat
# score: bpm=170 (eighth-note rate), ts=[9, 4]; track: {'name':'dm','instrument':'standard','role':'drum','notes':drums}
```

| Cycle | Matras | Pattern (D = dum/düm, T = tak/tek, t = light) | Label |
|---|---|---|---|
| `nim_sofyan` | 4 (2/4) | D . T . | sourced (ritmik.net) |
| `semai` | 6 (3/4) | D . T . T . | sourced |
| `sofyan` | 8 (4/4) | D . . . T . T . (the first stroke held) | sourced |
| `turk_aksagi` | 5 (5/8) | D . T . T | sourced |
| `yuruk_semai` | 6 (6/8) | D T T D T . | sourced |
| `devr_i_hindi` | 7 (7/8) | D T T D . T . | sourced |
| `duyek` | 8 (8/8) | D T . T D . T . | sourced |
| `aksak` | 9 (9/8, 2+2+2+3) | D . T T D . T . T | sourced |
| `curcuna` | 10 (10/8) | D . T t . D . T . T | sourced |
| `karsilama`, `zeibekiko` (9), `kalamatianos` (7) | 9, 9, 7 | folk 9/8 and 7/8 | practice |
| `maqsum` `baladi` `saidi` | 8 | as above | length sourced, strokes practice |
| `malfuf`, `ayyub` | 6, 8 | 2/4 folk and Sufi cycles | length sourced, strokes practice |
| `masmudi_kabir` | 16 (8/4) | tarab | length sourced, strokes practice |
| `dadra` | 6 | Dha Dhi Na Dha Tu Na | tala length sourced (ragajunglism.org) |
| `rupak` | 7 (3+2+2) | begins on the open stroke | length sourced |
| `jhaptal` | 10 (2+3+2+3) | | length sourced |
| `ektal` | 12 (2+2+2+2+2+2) | | length sourced |
| `solea` `buleria` `alegrias` `seguiriya` | 12 | clap accents on counts 3 6 8 10 12 (counted from 12 of the previous bar) | practice; the 12-count is sourced |
| `jig` 6, `waltz_3` 3, `take_five_5` 5, `seven_8` 7 | | Western odd meters | practice |

Other Indian talas the source lists (not coded): chautal 12, dhamar 14, rudra 11, sultal 10, tivra 7, jhoomra 14, deepchandi 14,
pancham sawari 15, tilwada 16, sitarkhani 16, shikhar 17, brahma 28.

## 6. Notes on each tradition (so the brief and the reply are accurate)

**India.** A raga is more than a scale: it has a characteristic phrase, a time of day and a mood, and the scale (thaat) is only its container. Hindustani
uses ten parent thaats (Bilawal, Khamaj, Kafi, Asavari, Bhairavi, Bhairav, Poorvi, Marwa, Todi and Kalyan, of which Yaman is the best-known raga). The drone
(tanpura on the tonic and fifth) is the ground; the skill's `bass: half` gives root and fifth. Instruments in film and classical use: tabla, bansuri, sitar,
shehnai, dholak, santoor, harmonium, sarangi; Carnatic adds veena, venu, mridangam, kanjira, ghatam, nadaswaram and violin. Just intonation cents are on
(a major third is 14 cents flat of equal temperament, a minor third 16 cents sharp). What is not done: alap with no pulse, gamak oscillations on specific
notes, and the time-of-day rule. Ask the user which raga and what time; offer `raga_*` modes.

*Which Indian genre?* India is not one style, so pick by the song's home. Classical: `hindustani` (khayal, tabla), `dhrupad` (pakhawaj, slow, temple), `carnatic` (violin, mridangam); light classical: `ghazal`, `thumri` (alias). Devotional: `bhajan` (also kirtan, shabad, aarti), `qawwali` and `sufi`. Film: `bollywood`, `retro_filmi` (1960s-70s strings), `tamil_film` (also telugu, malayalam, kannada: South Indian film), `gaana` (Chennai kuthu). Folk by region: `bhangra` (Punjab), `garba`/`dandiya` (Gujarat), `lavani` (Maharashtra), `baul` (Bengal), `rajasthani_folk`, `bihu` (Assam), `chenda_melam` (Kerala). Modern: `indipop`, `indian_lofi`, `desi_hiphop`. Carnatic scale names work as modes: `raga_kalyani` = yaman, `raga_mayamalavagowla` = bhairav, `raga_shankarabharanam` = bilawal, `raga_kharaharapriya` = kafi, `raga_natabhairavi` = asavari, `raga_harikambhoji` = khamaj, `raga_hanumatodi` = bhairavi, `raga_mohanam` = bhoopali (the equivalences are from ragajunglism.org and shankarmahadevanacademy.com). Extra ragas: `raga_ahir_bhairav`, `raga_charukeshi`, `raga_megh`, `raga_hamsadhwani`. Odd Carnatic cycles for a custom score: `misra_chapu` (7), `kanda_chapu` (5), `chautal` (12).

Not yet covered: Telugu, Malayalam and Kannada film have no sound of their own here (they use `tamil_film`); Odia, Kashmiri, Bhojpuri, Goan and Sikh shabad are not separate genres; the Indian genres have not been listened to (see section 10).

**Arabic.** Maqamat are built from 3-, 4- and 5-note groups (ajnas). Most maqamat have seven notes repeating at the octave. Quarter-tones appear in rast, bayati,
saba and sikah (all coded with -50 cents); hijaz, nahawand, kurd, ajam, nikriz have none. The rhythm is a cycle of two sounds, dum and tak, with players
adding ornament. Use sus chords or a drone. Real tarab has long unmeasured improvisation (taqsim); here the music is metered.

**Turkey.** Makam uses the 53-comma grid (a major second is nine commas). The usul table above is sourced from a bendir teaching site; the nine basic usuller run from
2 to 10 beats and the aksak (limping) ones are 5, 7, 9 and 10. Folk 9/8 (karsilama, roman havasi) needs `cycle_notes`.

**Persia and the Balkans.** `persian_shur` is a bayati-like quarter-flat scale. Rebetiko and Greek folk use hijaz-type scales with minor and major chords and a bouzouki
lead; klezmer uses freygish with a clarinet that sobs (high `glide`).

**Flamenco.** Phrygian dominant with the Andalusian cadence i-VII-VI-V (Am-G-F-E). The 12-count compas has accents on 3, 6, 8, 10 and 12; solea is slow
(about 60-80 BPM) and bulerias fast (about 180-240) per the one guide read. The skill's flamenco genre is a 4/4 rumba flamenca; use `cycle_notes('solea')` for the 12.

**China.** Pentatonic, five modes by choice of tonic (gong major-like, yu minor-like). Erhu: slides and vibrato; guzheng: glissandi and plucked runs; dizi: bright
flute with slides; pipa: tremolo plucking; yangqin: struck strings. Keep the harmony simple (open fifths, I-vi-IV-V in gong) and let the lead carry the idiom.

**Japan.** In-scale (`miyako_bushi`, `insen`, `iwato`) and yo scale. Shakuhachi's home is D minor pentatonic with breathy meri bends (use `glide`). Koto is tuned to
hirajoshi and bends notes by pressing behind the bridge (oshide), so single chromatic inflections are idiomatic and constant chromaticism is not. Do not stack every
signifier at once: an in-scale melody, koto, shamisen, taiko and parallel fourths in one bar reads as a theme park; one or two clear signals go further (sourced advice).
J-pop and anime lean on standard major and minor harmony with the Royal Road progression (`IVmaj7-V-iii-vi`). City pop: seventh chords, slap bass, brass.

**Korea and K-pop.** Sources agree on these traits: a modular structure (intro, verse, pre-chorus, **beat drop** or chorus, post-chorus hook, verse 2 often with rap,
bridge or beat switch, dance break, final chorus with a **key change** or added layers); a 5-10 s "killing part" engineered as the hook; I-V-vi-IV and mixolydian colour
with borrowed chords; tempos 90-110 (groove) or 115-130 (four on the floor), with 70 or 140 half-time for trap sections; EDM sound design (supersaws, risers, filter
sweeps) plus piano and guitar plus 808s. The generator gives you the sound palette and a steady grid; the **form** is yours: build it with `hit_points`
(`drop`, `shift`, `impact`) and `direct.add_line`, and add the key change by writing the last section a whole step up in a custom score. Trot is the older bouncing
two-step on a minor pentatonic.

**Rio and Brazil.** Samba is the umbrella: samba enredo (school parade), partido alto, samba de roda, pagode (a smaller, cavaquinho-led style), plus bossa nova and choro
as the urban chamber styles; funk carioca (tamborzao) is the modern baile. Northeastern styles: baiao, xote, xaxado, coco, forro (triangle and zabumba), maracatu
(alfaias, agogo, caixa), frevo (fast marcha from Recife), and Bahia's axe and samba-reggae. Tempos in the source: coco 100-112, xaxado 104-112, xote 76-120 (faster in the
northeast, slower in the June festivals), coco de roda 105-115, maxixe 95-108, bumba meu boi 106-112, toada 68-100, balaio 120-136, tambor de crioula 130-152, drum-set
samba 90-136, funk partido 90-126, samba rock 76-114, marcha about 120. Instruments named there: surdo, tamborim, pandeiro, cuica, agogo, ganza, caixa, repinique,
berimbau (capoeira), cavaquinho. The 16-step grooves in `world.py` are approximations of the feel; the patterns of the schools are far busier.

**Latin and Caribbean.** Bachata (guitar arpeggios, bongo, guira), merengue (accordion, tambora, guira, fast), tango (bandoneon, staccato marcato), mariachi (trumpets,
violins, vihuela, guitarron), bolero, soca and calypso (steel pan). Salsa, cumbia and reggaeton were already in the skill.

**Africa.** Highlife (guitar and horns, agogo bell), soukous (fast rumba guitar), amapiano (log drum, shakers, rhodes, pad), kora (21-string harp-lute) and balafon,
mbira (thumb piano, cyclical interlocking parts, hosho shaker). Many melodies are pentatonic; West African music is built on cyclical grooves, polyrhythm and call
and response. Afrobeat is the older genre.

## 7. Direction-sheet notes

For any non-Western cue the sheet should say: the tradition, the mode, the instruments **as stand-ins**, and what earshot cannot judge. Example:
```json
{"purpose": "60 s documentary bed, Rajasthan", "duration_s": 60, "feel": ["warm", "timeless"], "avoid_feel": ["tense"],
 "instruments": ["sitar", "bansuri", "tabla"], "pulse": "steady", "tempo_bpm": [70, 90], "mode": "raga_bhairavi",
 "notes": "raga_bhairavi; sitar and bansuri are GM stand-ins; authenticity not checked by earshot"}
```

## 8. Getting real instruments

The honest upgrade paths, in order of effort:
1. **Clone a recording** the user owns (`scripts/clone_instrument.py`, `references/instruments-and-vocals/instrument-cloning.md`).
2. **A SoundFont with the instruments.** Set `MUSICGEN_SF2=/path/file.sf2`. The 128 GM slots then play the bank's sounds, so a world-instrument SoundFont must be GM-mapped
   to be a drop-in; otherwise use one instrument per track with `program` numbers. Sources seen (not downloaded or tested here): polyphone.io has a "ethnic / world"
   category with a "can be used for commercial purposes" filter (check each file's licence); DSK Music's free SF2 set includes a 13-instrument world-strings bank (Celtic
   harp, cumbus, dobro and others) and states its instruments are free for private and commercial use. musical-artifacts.com blocked the fetch.
3. **Give the MIDI and stems to a person** to finish in a DAW with a real library.

## 9. What was read, and what was not

(Turkish makam, 53 commas); ritmik.net (nine Turkish usuller with their dum/tek patterns); compmusic.upf.edu (duyek 8/8, aksak 9/8); ragajunglism.org (tala lengths);
raag-hindustani.com and the search results (ten thaats); masterthescore.com (Japanese scales, koto and shakuhachi); the search results for Chinese pentatonic modes (ISMIR 2022
paper, CUNY open textbook, Chinese musicology); lumbeat.com (Brazilian rhythms, tempos and instruments); melodigging.com and songbrain.ai (K-pop structure and sound);
beatkey.app, Wikipedia and idiom.ucsd.edu results (flamenco, Andalusian cadence, phrygian dominant, 12-count compas); gamelan pages (slendro and pelog); Wikipedia on Indian classical
instruments; polyphone.io and dskmusic.com (SoundFont sources). Indian genres pass: spardhaschoolofmusic.com (types of Indian music: bhangra, baul, bihu, lavani, maand, bhajan, kirtan, shabad, regional film) and melodigging.com (Tamil film music: song form, ragas, tala, instruments, composers). A fetch of a Garba and Dandiya guide failed, so the garba and dandiya grooves rest on search snippets (3 claps, dadra-based 6-beat, dandiya faster) and practice.

**Not verified:** the stroke positions of the Arabic iqa'at (the pages show the notation as pictures; the skeletons are standard practice); every groove's
exact pattern for the Brazilian, Latin, African and K-pop styles (practice); the cent values for just intonation and the quarter-flats (practice, standard values);
the real tuning of any gamelan; how any of these sound next to the real tradition. The musical-artifacts.com SoundFont page and the Pixabay-style label lists for world
music were not read.

## 10. Limits (say these in the reply)

- Stand-in instruments. Not recordings, not authentic timbres.
- No sung words. No taqsim, alap or free improvisation; the output is metered and phrase-structured.
- Ornament is simple: slides into notes and vibrato. Not gamak, not tahrir, not the full vocabulary of any tradition.
- Chords are in equal temperament; microtonal modes use drones and sus chords on purpose.
- The genres were composed, rendered and measured for loudness, and the microtone and glide pitch was measured. **earshot was not run on them** and no person has
  listened, so the genre readings are unknown (see `genres-and-moods.md` section 7a: even the original genres pass the family test only about half the time).
- Cultural fit is a human judgment. Offer the user a version to check with someone from the tradition when it matters (a film, a release).
