# SFZ sample libraries (optional, per project)

The default sound is the GM SoundFont. A track can instead be played by a multisampled **SFZ library** that lives in the project.
Nothing is shipped in the skill and nothing downloads unless you run a command. A score with no SFZ track renders exactly as before.

## What it is and is not
- It plays recorded orchestral samples (velocity layers, round-robins, looped sustains, a legato trigger) through `sfizz_render`, offline.
- It is a clear step up from a 32 MB General MIDI bank for strings, brass and woodwinds. It is **not** a top commercial library:
  the free sets are older recordings in different rooms, mostly dry, with looped sustains. Reverb (the project's `space`) is required.
- Measured here: `sfizz_render` is reproducible. Two renders of a patch that uses random round-robin are byte-identical.

## Commands (all `scripts/sfz_libs.py`, run with the skill's venv)

| Command | What it does |
|---|---|
| `list` | libraries in the registry, sizes, licences, what is installed |
| `get <lib> --project D` | download + unpack into `D/libs/sfz/<lib>/` |
| `engine --project D` | install the sfizz engine into `D/libs/engine/` (Windows prebuilt, checksum-verified) |
| `install-local <lib> <zip> --part P` | unpack a zip you downloaded by hand (for hosts that block scripts) |
| `check <lib>` | every `sample=` of every `.sfz` exists (follows `#include`, handles spaces) |
| `find <lib> words...` | patch names |
| `verify` | files still match the checksums taken at install |
| `remove <lib>` | delete that library only |
| `registry` | validate the library presets |

`get` flags: `--part a,b|all`, `--variant standard|performance`, `--dry-run`, `--yes`, `--max-gb`, `--keep-archives`, `--no-extract`,
`--sha256`, `--mirror URL`, `--dest DIR`, `--ref <branch|tag|commit>`, `--all-free`, `--force`. Above 500 MB it asks first (`--yes` skips).
Safety: https only, only the hosts named in the preset, every redirect must be https, archives cannot write outside the library folder,
unpack size is capped, nothing downloaded is executed. The first download of a part records its checksum in `libs/sfz/lock.json`;
a later different file is refused unless `--force`. `libs/sfz/LICENCES.md` lists each library's licence and credit line.

## Libraries in the registry (`references/presets/sfzlib/`, project `presets/sfzlib/` adds or overrides)
- **sso**: Sonatina Symphonic Orchestra, CC Sampling Plus 1.0, from GitHub (git sparse checkout: `--part strings,brass,woodwinds,percussion,choir,keys`;
  strings about 550 MB, whole library about 1.4 GB). Patches: sustain, staccato, marcato, pizzicato, tremolo, key-switch (KS) and `Legato`
  (the SFZ `trigger=legato` mechanism: overlapping notes of a line), in "Notation" (velocity = loudness) and "Performance" (mod wheel = loudness) folders.
- **vpo**: Virtual Playing Orchestra 3.3. The two script sets download by script. The 603 MB wave files are hosted on OneDrive, which refuses
  scripted download: download them by hand from the page and run `install-local vpo <zip> --part wave`. Mixed licences, some share-alike.
- **sfizz**: the engine, BSD-2-Clause, pinned to 1.2.3 (the project is archived). Windows prebuilt. On macOS/Linux build it or set `SFIZZ_RENDER`.

## Using one in a score
An instrument preset (project `presets/instruments/<name>.json`) carries the block, so scores keep readable names:

```json
{"role": "melody", "reverb": 0.3, "spatial": {"azimuth": -50, "distance": 4},
 "sfz": {"library": "sso", "patch": "Strings - Notation/1st Violins Legato",
         "cc": "expression", "controls": {"21": 50}, "tail_s": 3.0, "trim_db": 0, "fallback": null}}
```
or in the score: `"instrument": "sfz:sso/Strings - Notation/1st Violins Legato"`. Keys:

| Key | Meaning |
|---|---|
| `cc` | controller that carries the dynamics curve: `expression` (CC11), `volume` (CC7), `modwheel` (CC1, for Performance patches), `none` |
| `controls` | constant controllers at start (e.g. `{"21": 50}` is Sonatina's vibrato knob) |
| `keyswitches` | `{"pizz": 36}`: a note's `art` becomes a key-switch note, for KS patches |
| `legato_overlap_s` | legato patches, scores with no per-note `art`: each note ends this long after the next one starts (default 0.04) |
| `slur_overlap_s`, `slur_glide_cents`, `slur_glide_s`, `slur_vel_scale`, `slur_fade_s`, `slur_fade_floor`, `slur_fade_off` | slurred legato for notes marked `"art": "legato"` (defaults 0.025, -20, 0.04, 0.88, 0.025, 0.55, false); see "Slurred legato" below |
| `tail_s` | room for the release (default 3) |
| `trim_db` | stem level; the library's own level differs from the GM bank, set it by measuring |
| `fallback` | `"gm"`: play the SoundFont when the library is missing. Printed, counted in `STATS['sfz_fallback']`, never silent. Default none: a missing library is an error |

Timing and velocity are humanized first (same as the GM path). The dynamics curve is sent as controller values; controllers go out
50 ms before the first note (a controller on the same tick as a note-on arrives too late for that note).

## The gate
Project gate: an SFZ track needs its library installed, the patch to exist, and the engine (the message names the command). Warnings: the credit
line of each library used (and a share-alike reminder), and an SFZ track with no reverb. The mix of such a piece still needs its own `mix_preset`.

## Example
`<project_dir>/grand-canyon/` is an example project with a Grand Canyon style orchestra: `presets/mix/grand_canyon_mix.json`,
`presets/spaces/canyon_open.json` and 13 instrument presets (`canyon_violins1`... `canyon_timpani`) on Sonatina patches.

## Not covered
- True legato-transition samples (commercial libraries record them; the free sets here use the legato trigger on ordinary samples).
- Convolution with a real hall impulse response (the `space` presets are the engine's own reverb).
- Nothing here was auditioned by ear: levels and behaviour are measured.

## Safe rendering (required)

`sfizz_render` must be given **`--use-eot`**. Without it the render never ends: measured here, a 65.8 s MIDI
produced a WAV that was still growing after 400 s (340 s of audio at q=10, 1353 s at q=1), so the pipeline
waits forever and no stem is ever written. `scripts/sfz_render.py` passes `--use-eot` and a timeout
(`120 s + MIDI length x 6`; q=10 measured at ~0.6-1.5x realtime) and raises `SfzUnavailable` by name when a
render does not finish. Never call the binary by hand without both.

- **Diagnosing a stall:** the log stops at `rendering N SFZ track(s) across W workers ...`, no stem is printed,
  and `%TEMP%/tmp*/out.wav` keeps growing. Check the flag before blaming the hardware or the worker count.
- **Workers:** `MUSICGEN_SFZ_WORKERS` (default 4). Each process loads its own copy of the library, so raising it
  costs memory and disk on a cold page cache.
- **Stem cache:** `<project>/.cache/stems`, keyed on the track, tempo map, seed, resolved presets, the SoundFont
  and a hash of `render_natural.py` + `dsp.py`. Editing either file re-renders every stem.

## Slurred legato (the user's rule)

Source: the user, after hearing a render where every note of a run sounded like a new bow stroke (détaché).
The rule is for any `"art": "legato"` run on a bowed or blown legato patch:

- Two or more consecutive `"art": "legato"` notes are **one bow stroke**. Overlap the first note's release into
  the next note's attack by **20-30 ms**.
- On the second and later notes of the slur, **skip the hard attack**: a **25 ms fade-in**, or a sample offset
  that skips the first **15 ms** (the rosin "bite").
- Pair it with a tiny pitch glide into the new note: **-20 cents, glide time 0.04 s**.
- The **first note of each phrase keeps its real bow bite** (no fade, no glide). A phrase starts after a rest or
  a note that is not `legato`.
- Do not apply it to staccato, marcato, pizzicato or tremolo patches.

**Implemented per note** in `sfz_render.py`: a note is slurred into the next when both carry `"art": "legato"`,
the gap is under 150 ms, and the patch is not staccato, marcato, pizzicato, tremolo, spiccato, col legno or
harmonics. Overlap 25 ms (`slur_overlap_s`), glide -20 cents to 0 over 40 ms as MIDI pitch bend
(`slur_glide_cents`, `slur_glide_s`), velocity x0.88 (`slur_vel_scale`), and a 25 ms gain ramp from 0.55 to 1.0
on the continuation onset (`slur_fade_s`, `slur_fade_floor`, only on a monophonic track). A score with no
per-note `art` keeps the older behaviour, where the patch name decides (`legato_overlap_s`).

Limits to state: the ramp is a partial gain ramp, not a true sample-offset skip (sfizz cannot do that from
MIDI), and the glide is a pitch bend on the whole patch. Not auditioned unless `listen.py` ran.
