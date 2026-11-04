---
title: Mix rules
summary: The short list of mix rules: one low-end owner, headroom, lane separation, and where the detail lives.
tags: [mix, rules, headroom, low end, lanes, master]
load_when:
  - before touching a mix preset
  - checking a mix against the basics
---

# Mix rules


## Mix rules (so the mix stays clear)

These are enforced by `scripts/mixer.py` and checked by `scripts/quality_gate.py` (the "mix" row):

1. **The lead owns 1–3 kHz.** When a melody leads, every bed that shares that band (pads, chords, arps, counter lines,
   chorus) gets a −2 dB dip at 2 kHz (`carve_for_lead`). A dip the brief or the producer set is kept.
2. **Percussion rises in the climax, not the intro.** A percussion track carries a level curve (`dynamics`): clean and
   sitting in the stereo field in the intro, a touch up in the heavy section, back down after it.
3. **The lead's tail carries.** A lead string or violin may have a larger `reverb` so its tail rings into the next section.
   A track has one reverb setting for the whole piece; a tail that only lasts into one section is a producer's move
   (set it on the lead track and check the next section in the listen report).
4. **The gate checks it.** In every 4-second window where the lead plays in 1–3 kHz, no bed may sit within 3 dB of it in that
   band. The check runs on the separated stems. A WARN means carve the beds or lower them there; more than three
   windows is a FAIL.
5. **The 3-tier hierarchy (never stack competing leads).** At any given moment, there is EXACTLY ONE HERO (lead melody or rhythm break).
   When Lead A speaks, Lead B is silent (Call and Response). Midground beds (arps, plucks, chords) sit −8 to −12 dB below the hero
   and back off during solo phrases. Background foundation (bass, low pads) stays below 1.2 kHz.
6. **The groove pocket tempo.** A cross-cultural or polyrhythmic blend (12/8, dadra, compound meter, traditional ornamentations) must
   never be rushed into high speeds (> 110 BPM) which crowd acoustic transients into muddy noise. The relaxed groove pocket sits
   in 96–105 BPM where hand drums swing, bass notes bloom, and microtonal bends have time to breathe.
7. **Tamil Kuthu & Dappankuthu Rhythmic & Acoustic Architecture.** When scoring Tamil Kuthu, never use flat 4/4 syncopated piano chords (which triggers Latin Salsa/montuno illusions). Authentic Kuthu demands:
   - **Tisra Nadai / 6/8 compound bounce:** 12 subdivisions per bar galloping triplet pocket (`DA-ka-ta DA-ka-ta`).
   - **Thavil & Parai interlock:** Buffalo-hide Parai driving the continuous syncopated gallop, with Thavil stick backbeats (`3, 9`) and plaster-cap finger whips (`1, 4, 7, 10`).
   - **Gumtha Sub-Bass:** 150 Hz -> 55 Hz pitch drop with soft tanh saturation on primary Doums for physical chest thump.
   - **Urumi Melam:** Sweeping friction drum (120 Hz -> 280 Hz -> 120 Hz sine curve over 0.5s) at transitions and pre-drops.
   - **Double-Reed Nadaswaram / Mizmar Lead:** Formant-filtered saw/pulse (800 Hz-1.5 kHz) with nasal saturation; notes scoop 30-50 cents flat with 6-7 Hz embouchure vibrato on held notes.
   - **Street Finger-Whistles:** 2.5 kHz to 3.2 kHz upward swoops with breath noise on drops.
8. **Anti-piercing natural tone.** Never voice lead melodies in screeching high registers (avoid octave 6 in GM). General MIDI brass,
   sitar, and synths require subtractive notches (e.g. sitar 3.5 kHz metallic ping) and low-pass roll-offs (4.5–7 kHz) so they
   blend like warm acoustic instruments rather than piercing digital synthesis.
9. **The Voice-Over First Contract.** The contract lives in `knowledgebase/genre-and-feel/commercial-promo.md`; apply it here. Whenever narration or speech sits over music, speech intelligibility (800 Hz – 3.5 kHz) takes absolute precedence:
   - Apply a static -4 to -6 dB bell notch filter ($Q = 1.2$) centered at 1,800 Hz across all chordal beds (pianos, pads, guitars).
   - Dynamically duck the entire music bed by -8 to -14 dB during vocal phrases (25 ms attack, 250–350 ms release).
   - Commercial temporal milestones: 0–3s thumb-stop hook, 15–30s micro-lifts (glock, claps, staccatos), and final 3s logo mnemonic ringing into silence.
10. **Ambience and SFX blending.** The laws, their numbers and the order to apply them are in
    `references/mixing/mixing-and-mastering.md` section 8. Do not restate them here.
