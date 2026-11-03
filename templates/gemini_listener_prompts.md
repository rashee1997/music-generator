# Gemini listener prompts (music_db)

Paste the song into the model, then run the modules in order. Each module returns ONE JSON document. Save them as
`<extraction project>/music_db/song.json`, `instruments.json`, `drums.json`, `effects.json`, `spatial.json`.
Module 3 is run once per instrument (or for a batch of ids) and its entries are added to `instruments.json`.

---

## SHARED RULES (put this first, once per chat)

```
You are a mastering engineer and orchestrator with perfect pitch. You will LISTEN to the attached song and write a
machine-readable description of what you hear. A program will read your JSON and use it as hints for signal
processing, then measure the real numbers itself, so honesty matters more than completeness.

RULES
1. Return ONLY valid JSON. No markdown fences, no comments, no text before or after.
2. Times are seconds as plain numbers (12.5), never "0:12". Frequencies are Hz. Notes use scientific pitch (C4 = middle C).
3. Listen to the WHOLE song. Do not describe only the intro. Give start/end times for when each sound is audible.
4. If you cannot hear or cannot estimate a field, use null. Never invent a number to fill a gap.
5. Every numeric timbre field is an estimate by ear; also give a confidence (0 to 1) as asked. Prefer ranges to false precision.
6. Use snake_case ids. An id must be identical in every module (the same sound = the same id).
7. Do not name a real instrument you cannot actually distinguish; use the closest family and lower the confidence.
8. Synthesised and electronic sounds are instruments too. Describe them by how they are made (waveform, filter, envelope).
9. Keep every string under 200 characters.
10. SCOPE: we want INSTRUMENTS, SPACE and AMBIENCE only. Do NOT describe singing, rapping, spoken words, ad-libs or
    hype shouts as instruments. The only voice we want is HUMMING (closed-mouth hum, wordless "mm", "ooh/aah" pads
    used as a texture). If a sung/rapped/spoken part is present, do not make an instrument, drum, effect or spatial
    entry for it; just list its time ranges once in song.json "ignored_vocals" so the program can stay away from them.
    Vocal chops and scratched vocal samples count as effects only when they work as a rhythmic or electronic texture
    (module 5), never as lyrics.
11. Say what the ROOM and the AIR sound like everywhere you can hear them: reverb tails, hiss, crackle, hum, wind,
    crowd, room tone, stereo movement. That is as important as the notes.

KNOWN INSTRUMENT IDS (put the closest one in "similar_to"; if none fits, use null and describe it):
humming_voice, bass, drums, guitar, piano, strings_pad, wind_flute, pan_flute, quena, bansuri, ney, shakuhachi, dizi,
tin_whistle, flute, duduk, oboe_english_horn, clarinet_bassoon, saxophone, sitar, oud, qanun, kora, nylon_guitar,
acoustic_guitar, clean_guitar_muted, distortion_overdrive_guitar, harp, violin_fiddle, viola, cello,
erhu_sarangi_morin_khuur, string_ensemble_slow_strings, pizzicato_strings, french_horn, trumpet_muted_trumpet,
trombone_tuba_brass_section, epiano_rhodes_clavinet, organ_harmonium_accordion, marimba_balafon_xylophone,
vibraphone_kalimba, celesta_glockenspiel_music_box, gamelan_metallophone_gong, finger_bass_pick_bass,
acoustic_bass_contrabass, synth_bass_reese_808, sub_bass_forest_drone, warm_pad_sweep_pad_polysynth,
saw_lead_square_lead, choir_aahs, voice_oohs, tabla_dholak, darbuka_doumbek_riq, djembe_conga_bongo_talking_drum,
taiko_orchestral_timpani, brush_kit_808_kit, ambient_sfx
```

---

## MODULE 1 - song overview  ->  `song.json`

```
Listen to the whole song and return this JSON:

{
  "schema": "music_db.song/1",
  "title": "string or null",
  "duration_s": 0.0,
  "tempo_bpm": { "value": 0.0, "stable": true, "changes": [ { "at_s": 0.0, "bpm": 0.0 } ] },
  "time_signature": "4/4",
  "key": { "tonic": "C", "mode": "major|minor|dorian|phrygian|lydian|mixolydian|other", "confidence": 0.0,
           "modulations": [ { "at_s": 0.0, "tonic": "D", "mode": "minor" } ] },
  "genre": ["string"],
  "mood": ["string"],
  "sections": [ { "name": "intro", "start_s": 0.0, "end_s": 0.0, "energy_0_10": 0,
                  "what_changes": "which sounds enter or leave" } ],
  "mix": {
    "loudness": "quiet|moderate|loud|very_loud",
    "dynamic_range": "crushed|compressed|moderate|wide",
    "stereo_width_0_1": 0.0,
    "low_end": "thin|balanced|heavy|sub_heavy",
    "space": "dry|room|hall|cathedral|wide_electronic",
    "era_or_production_style": "string"
  },
  "sound_inventory": ["short noun phrase for EVERY distinct instrument, drum, electronic effect and ambience you hear; leave out sung, rapped and spoken vocals"],
  "ignored_vocals": [ { "start_s": 0.0, "end_s": 0.0, "kind": "sung|rapped|spoken|shouted|backing", "note": "string" } ],
  "notes": "anything unusual (tempo drift, tape artifacts, samples from other records, spoken parts)"
}
```

---

## MODULE 2 - instrument census  ->  start of `instruments.json`

```
List EVERY distinct instrument you hear: melodic instruments, bass, pads, keys, brass, strings, guitars, synths and
electronic textures. Do NOT list singers, rappers, spoken or shouted voices, or backing vocals with words (they go in
song.json "ignored_vocals"). A HUMMING or wordless "mm/ooh/aah" voice used as a pad IS allowed, as family "voice",
id starting "humming_". Split two sounds of the same family if they sound different (e.g. open
trumpet and muted trumpet; piano and electric piano). Do not describe drums here (module 4) or one-shot effects
(module 5), but DO include any tonal drums (808, timpani, toms) if they carry pitch.

Return this JSON:

{
  "schema": "music_db.instruments/1",
  "instruments": [
    {
      "id": "trumpet_lead",
      "label": "Open trumpet playing the main hook",
      "family": "brass|woodwind|strings_bowed|strings_plucked|keys|mallet|voice|synth|bass|pad|texture|other",
      "role": "lead|counter_melody|chords|arpeggio|bass|pad|rhythm|stab|texture|fx_pitched",
      "similar_to": ["trumpet_muted_trumpet"],
      "first_s": 0.0,
      "last_s": 0.0,
      "prominence_0_10": 0,
      "confidence": 0.0
    }
  ]
}
```

---

## MODULE 3 - instrument deep dive  ->  full entries for `instruments.json`

Run once per id (replace `IDS`), or for a batch of ids.

```
Now study these instruments in detail: IDS.
For each one, replace its census entry with the full entry below. Listen to its isolated moments (the places
where it plays alone or is loudest) to judge timbre. Return this JSON:

{
  "schema": "music_db.instruments/1",
  "instruments": [
    {
      "id": "trumpet_lead",
      "label": "string",
      "family": "brass",
      "role": "lead",
      "similar_to": ["trumpet_muted_trumpet"],
      "range": { "lowest_note": "E4", "highest_note": "C6", "typical_low": "G4", "typical_high": "G5" },
      "polyphony": 1,
      "timbre": {
        "harmonics_rel": [1.0, 0.9, 0.7, 0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.08, 0.05, 0.03],
        "harmonics_note": "relative loudness of harmonics 1..12 on a middle-register note, strongest = 1.0; null if unsure",
        "odd_even": "balanced|odd_heavy|even_heavy",
        "centroid_hz": { "low": 0, "high": 0 },
        "brightness": "dark|warm|neutral|bright|harsh",
        "formants_hz": [],
        "noise_ratio_0_1": 0.0,
        "noise_kind": "none|breath|bow|pick|key_click|hiss|distortion",
        "inharmonicity": "none|low|medium|high",
        "distortion": "none|light|heavy"
      },
      "envelope": {
        "attack_ms": { "min": 0, "max": 0 },
        "decay": "none|short|medium|long",
        "sustain_level_0_1": 0.0,
        "release_ms": 0,
        "t60_s": null
      },
      "pitch_behavior": {
        "vibrato": { "present": false, "rate_hz": null, "depth_cents": null, "onset_delay_ms": null },
        "glides": "none|occasional|frequent",
        "bends": false,
        "pitch_stability": "tight|natural|loose",
        "tuning_offset_cents": null
      },
      "articulation": ["legato", "staccato", "tremolo", "fall", "doit", "muted", "slap", "harmonics", "pizzicato"],
      "dynamics": { "typical": "p|mp|mf|f|ff", "range_db": null },
      "space": {
        "pan_minus1_to_1": 0.0,
        "width_0_1": 0.0,
        "distance": "close|mid|far",
        "reverb": "dry|small|medium|large",
        "effects": ["delay", "chorus", "phaser", "flanger", "filter_sweep", "sidechain_pump", "bitcrush", "tape_wobble"]
      },
      "activity": [ { "start_s": 0.0, "end_s": 0.0, "level_0_10": 0, "doing": "plays the hook" } ],
      "melodic_content": {
        "description": "string",
        "motifs": [ { "at_s": 0.0, "approx_notes": ["G4", "A4", "C5"], "rhythm": "short-short-long" } ]
      },
      "synthesis_hint": { "gm_program": null, "recipe": "e.g. saw wave, low-pass 2 kHz, 30 ms attack" },
      "confidence": { "identification": 0.0, "timbre_numbers": 0.0 },
      "uncertain_fields": ["timbre.harmonics_rel"]
    }
  ]
}

Notes: motifs are approximate and only a few per instrument, a program will measure the exact notes.
For a drum that carries pitch (808, timpani), also fill range.
```

---

## MODULE 4 - drums and percussion  ->  `drums.json`

```
Describe the drum kit and percussion. Name every different piece you hear (several snares or hats are different
pieces). Return this JSON:

{
  "schema": "music_db.drums/1",
  "kit_type": "acoustic|electronic|hybrid|sampled|none",
  "groove": { "feel": "straight|swing|shuffle|half_time|double_time|free",
              "pattern_notes": "string", "fills": [ { "at_s": 0.0, "kind": "snare roll" } ] },
  "pieces": [
    {
      "id": "kick_808",
      "kind": "kick|snare|clap|rim|hat_closed|hat_open|ride|crash|tom_low|tom_mid|tom_high|shaker|tambourine|cowbell|conga|bongo|perc_other|sub_drop",
      "label": "string",
      "sample_based": true,
      "character": ["punchy", "boomy", "tight", "dry", "roomy", "gated", "distorted"],
      "pitch_hz": { "fundamental": null, "sweep_to": null },
      "centroid_hz": null,
      "tail_s": null,
      "noise_ratio_0_1": null,
      "layers": ["click", "body", "sub"],
      "level_0_10": 0,
      "pan_minus1_to_1": 0.0,
      "processing": ["compression", "saturation", "gated_reverb", "sidechain_source"],
      "pattern": { "grid": "16th", "steps": "x...x...x...x...", "bars_described": "1-8" },
      "hit_times_s": [],
      "active": [ { "start_s": 0.0, "end_s": 0.0 } ],
      "similar_to": "kick",
      "confidence": 0.0
    }
  ]
}

hit_times_s: list up to 24 clear example hits (seconds), spread across the song, not only the intro.
```

---

## MODULE 5 - electronic touches and effects  ->  `effects.json`

```
List every electronic effect, transition and production gimmick: risers, downlifters, impacts, sub drops, reverse
swells, tape stops, CD or record fast-forward / rewind scanning sounds, CD skips, stutters and glitches, vinyl
scratches, filter sweeps, lasers, sirens, noise bursts, whooshes, bit-crush bursts, sampled
noises (crowd, radio, telephone). Skip anything that is a person singing, rapping or speaking; a scratched vocal
sample counts only as "vinyl_scratch" with its rhythm and pitch motion, not its words. Give each occurrence its own entry. A "CD fast-forward" is a fast, high, scanning
sound made of many tiny repeated slices of the music played quickly. Return this JSON:

{
  "schema": "music_db.effects/1",
  "events": [
    {
      "id": "fx_01",
      "type": "riser|downlifter|impact|sub_drop|reverse_swell|tape_stop|cd_fast_forward|cd_skip|record_rewind|stutter|glitch|vinyl_scratch|filter_sweep|laser|siren|noise_burst|whoosh|vocal_chop|bitcrush_burst|sampled_noise|other",
      "description": "string",
      "start_s": 0.0,
      "end_s": 0.0,
      "pitch_motion": { "direction": "up|down|none", "from_hz": null, "to_hz": null },
      "spectral_motion": { "centroid_from_hz": null, "centroid_to_hz": null, "bandwidth": "narrow|wide|full" },
      "loudness_motion": "constant|rising|falling|swell|burst",
      "repetition": { "slice_ms": null, "rate_hz": null },
      "stereo_motion": "static|left_to_right|right_to_left|circling|widening",
      "level_0_10": 0,
      "over": "which instruments it plays over, or 'music cut out'",
      "how_to_synthesise": "e.g. white noise through a band-pass swept 300 Hz to 8 kHz, 4 s, plus 12 dB gain rise",
      "confidence": 0.0
    }
  ],
  "textures": [
    { "id": "tex_01", "kind": "tape_hiss|vinyl_crackle|room_tone|crowd|wind|rain|synth_drone|amp_hum|mains_hum|other",
      "start_s": 0.0, "end_s": 0.0, "level_0_10": 0,
      "level_db_estimate": null, "spectrum": "dark|mid|bright|full", "stereo": "mono|narrow|wide",
      "steady": true, "where_audible": "e.g. only when the music drops out, 12.0-14.5 s" }
  ]
}
```

---

## MODULE 6 - space and stereo movement  ->  `spatial.json`

Run after modules 2-5, so the ids already exist. Use the SAME ids as `instruments.json`, `drums.json` and `effects.json`.

```
Now describe the SPACE of the mix: where each sound sits and how that changes over the song. Use the same ids as
before. Conventions: azimuth_deg is -90 (hard left) to +90 (hard right), 0 = centre. distance_m is the distance from
the listener you estimate (close-mic'd = 0.3 to 1, mid = 2 to 4, far = 6 or more). If two copies of one sound sit
left and right (double-tracking), list them as ONE source with technique "double_tracked_LR" and give the pair in
"pair_azimuth_deg". Do not invent movement: if a sound never moves, "moves" is an empty list.

Return this JSON:

{
  "schema": "music_db.spatial/1",
  "space": {
    "room_type": "dry_booth|small_room|studio|hall|cathedral|plate|spring|wide_electronic|outdoor|mixed",
    "rt60_s": { "overall": null, "low": null, "high": null },
    "predelay_ms": null,
    "early_reflections": "none|few|dense",
    "stereo_width_0_1": 0.0,
    "mono_compatibility": "good|fair|poor",
    "low_end_mono_below_hz": null,
    "notes": "where you can hear the room most clearly (for example when the music drops out), with times"
  },
  "sources": [
    {
      "id": "trumpet_lead",
      "baseline": {
        "azimuth_deg": 0.0,
        "pair_azimuth_deg": null,
        "width_0_1": 0.0,
        "distance_m": null,
        "distance_word": "close|mid|far",
        "elevation": "low|ear|high",
        "reverb_send_0_1": 0.0,
        "stereo_technique": "mono|double_tracked_LR|stereo_sample|mid_side|haas|chorus_wide|ping_pong|other"
      },
      "per_section": [
        { "section": "chorus_1", "azimuth_deg": 0.0, "width_0_1": 0.0, "distance_m": null, "reverb_send_0_1": 0.0 }
      ],
      "moves": [
        { "start_s": 0.0, "end_s": 0.0,
          "kind": "pan|widen|narrow|approach|recede|reverb_up|reverb_down|filter_dark|filter_bright",
          "from": { "azimuth_deg": null, "width_0_1": null, "distance_m": null, "reverb_send_0_1": null },
          "to":   { "azimuth_deg": null, "width_0_1": null, "distance_m": null, "reverb_send_0_1": null },
          "curve": "linear|ease|step" }
      ],
      "confidence": 0.0
    }
  ],
  "transitions": [
    { "at_s": 0.0, "kind": "reverb_throw|delay_throw|drop_to_mono|widen_hit|dry_cut|stereo_swap|other",
      "affects": ["id"], "description": "string" }
  ]
}
```

---

## AFTER YOU PASTE THE FILES

Put them in `<extraction project>/music_db/` (`song.json`, `instruments.json`, `drums.json`, `effects.json`, `spatial.json`). The extractor will:
1. validate every file against these shapes (unknown ids, times outside the song and ranges that are not note names are reported, not guessed);
2. use them as hints: how many voices to look for, their pitch ranges and when they play, which drum pieces exist, where the effects are;
3. measure the real values by signal processing and write them back next to your estimates (`measured`), so a wrong ear estimate is corrected, not trusted. For space it measures, per voice and over time: azimuth from the level and time difference between the channels, width from the side/mid balance and inter-channel correlation, the room decay from the tails left when the music drops out, a distance cue from the direct-to-reverb balance, and mono compatibility;
4. add new instruments to the shared database (`knowledgebase/instrument_signatures.json`), which is the fallback when no `music_db/` exists.
