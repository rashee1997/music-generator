# A.R. Rahman style: what the production voice is

A production style is an overlay on a culture mix (`scripts/fusion.py`, `STYLES`). It changes which instruments lead
each role, not the cultures' scales, tempos or soul rules. Researched with TinyFish search, June 2026.

## What the sources say
- **Lush strings married with the melody.** Rahman is known for lush string sounds married with Indian melody.
  (theconversation.com, "How A R Rahman brought Bollywood soundtracks to the Western world")
- **Counterpoint, orchestration and the human voice.** His compositions use counterpoint, orchestration and voices,
  melding Indian pop with a distinct timbre and form. (en.wikipedia.org, A. R. Rahman)
- **Symphonic themes with leitmotif.** Orchestral themes accompany his scores, with leitmotifs. (medium.com, WorldMuslimPedia)
- **Ragas with electronic elements.** Classical ragas blended with modern production, without losing the soul.
  (liberalarts.dpu.edu.in, "Significance of Classical Music for Contemporary Film Songs")
- **Choral and voice-led songs.** Choirs and vocal layers are part of the Tamil film sound (Roja, 1992).
  (instagram, "The genius of AR Rahman's early production")
- **Western and Indian at once.** The Western orchestra and Indian melody share one song; the fusion is the signature.
  (ohiolink.edu thesis, Jackson 2010)

## How the style is built into the planner (`STYLES['rahman']`)
- **Pad:** `slow_strings` first, so the lush bed is the Rahman string sound.
- **Lift (counter line):** `violin` first, the leitmotif voice above the melody.
- **Chorus:** `choir_formant` first, the choral layer that enters with the build.

Use it with `"style": "rahman"` in a fusion brief. The cultures' soul rules still apply: the soul gate checks them
on the piece, and the mix gate checks the lead's band.

## What is not in the overlay
- Electronic drum programming and reggae or jungle rhythms (sources mention them; not modelled here).
- Sung words. The choir and hum are texture only (see SKILL.md limits).

---

## How to create / use

Use or make a production style:
1. Use: `"style": "rahman"` in the brief (the overlay lives in `references/data/styles/rahman.json`).
2. Make another: `python scripts/presets.py scaffold styles <name> --project <project>` and fill `roles_add` (which instruments lead each role) and `sources`.
3. Research the artist first (`research_kb.py` then web); styles change instruments, not scales or soul rules.
