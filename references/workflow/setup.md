---
title: Setup
summary: One-time environment setup: the venv, the SoundFont, earshot and what each install buys.
tags: [setup, install, venv, soundfont, earshot, environment]
load_when:
  - a fresh machine
  - a dependency is missing
---

# One-time setup (venv, SoundFont, earshot)


## One-time setup

One command, from the skill folder:

```bash
python3 scripts/setup_project.py          # core: .venv, packages, SoundFont, smoke test
python3 scripts/setup_project.py --ears   # also earshot (listen.py hears the music) and its models, about 1 GB
```
The script uses uv, which is quick to install (`pip install uv`). Without uv it uses
`python -m venv` and pip. Then use the environment: `source .venv/bin/activate` (Windows: `.venv\Scripts\activate`), or
call `.venv/bin/python` directly.

What gets installed, and where it is pinned:
- `requirements.txt`: the core packages, pinned to the versions tested here. The script installs tinysoundfont with
  `--no-deps` as well.
- `requirements-ears.txt`: earshot at a pinned commit, plus librosa, transformers and their friends. Torch comes from
  the PyTorch CPU index, and the script installs it first.
- The SoundFont (GeneralUser GS, about 32 MB) goes to `~/.cache/music-generator`. Set `MUSICGEN_SF2=/path/bank.sf2` to
  use another bank.
- earshot's models go to `~/.cache/music-generator/earshot`, which `listen.py` reads by default. `--earshot-home` changes it.

Without earshot, `listen.py` still reports the measurements (loudness, peaks, clipping, length) and says plainly that
the feel, instrument, pulse, tempo and key checks were skipped.
