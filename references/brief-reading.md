# Reading the brief (mood words, modifiers, numbers)

Moved verbatim from SKILL.md to keep the entry file short.

## Read the brief before you score it

The brief is usually a phrase, not a preset name: "motivational", "adventure", "slow reverb mix", "calm but
corporate". Read every word before choosing anything, in this order:

1. **A mood word sets the emotion.** `compose.py` knows its presets, their aliases and Pixabay's mood words, and
   reads `emotion`, `scene`, `style` and `notes`. `motivational` -> `hopeful` (76-98 BPM), `adventure` ->
   `adventure` (84-104, major/lydian, a journey rather than the `epic` trailer), slow reflective ->
   `dreamy`/`melancholy`.
2. **Modifier words change the arrangement, not the mood.** `slow / slower / ballad / chill / lazy` take the tempo
   to 0.85-0.90 and the energy down 0.12-0.15. `fast / uptempo / driving / frantic` take it to 1.05-1.20 and up
   0.10-0.18. `reverb / wet / spacious / distant` give a `large_hall` and a reverb return of 1.5; `dry / close /
   intimate` give `dry`. `sparse / minimal / bare` enter fewer layers; `dense / full / lush` enter more.
3. **Numbers beat words.** `energy` (0..1, where 0.5 is the mood's own midpoint) replaces the energy a word would
   set; `space` (`dry` ... `cathedral`) replaces the room; `tempo_scale` multiplies the tempo; `intensity` and `bpm`
   are absolute. The CLI has `--energy` and `--space`.
4. **No mood word is not "calm" any more.** With modifiers only, the modifiers choose the mood (slow + wet =
   `dreamy`); with nothing at all, `focused` (neutral, mid-tempo) is used. `meta.mood_notes` and `describe()` print
   what was read, so a wrong reading is visible before the render.
5. **The mood beats the genre on tempo.** When their ranges overlap, use the overlap. When they do not ("calm
   house", "motivational corporate"), the mood wins 2:1 and a note says so; the genre still owns its groove,
   instruments and mix. A fusion plans its tempo as a hint (+-7 BPM) and no longer invents a `joyful` mood.
