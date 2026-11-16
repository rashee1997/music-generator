# spatial_hrtf

Binaural (headphone) rendering with measured head data. Turn it on per track: `"spatial": {"azimuth": -60, "elevation": 20, "distance": 3, "binaural": "hrtf"}`.
A moving source uses `"trajectory"` as before. Without the head data the mixer prints a note and uses `spatial.py` instead.

## Attribution

Most of this folder is a vendored copy of **spaudiopy** by Chris Hold, MIT licence (`LICENSE` here is theirs).
Source: https://github.com/chris-hld/spaudiopy, master at commit a75c282 (2026-10-18).
Method: Zotter & Frank, *Ambisonics* (Springer 2019); Hold, Meyer-Kahlen & Pulkki, "Magnitude-Least-Squares Binaural Ambisonic Rendering
with Phase Continuation", DAGA 2023.

Head data: **FABIAN HRTF database**, TU Berlin, CC BY 4.0, https://doi.org/10.14279/depositonce-5718.5 (Brinkmann et al.).
It is downloaded by `python -m spatial_hrtf.data` (setup_project.py runs this) into `data/HRIRs/` and is not part of the skill's files.

## Files

| file | whose | what |
|---|---|---|
| `decoder.py`, `sph.py`, `io.py`, `sig.py`, `process.py`, `grids.py`, `parsa.py`, `utils.py`, `plot.py` | spaudiopy | used: `sph.sh_matrix`, `decoder.magls_bin`, `io.load_hrirs` / `get_default_hrirs`. The rest is kept so the copy is whole. |
| `data/Grids/` | spaudiopy | sampling grids, unchanged |
| `binaural.py` | ours | what the mixer calls: place a mono stem at an angle, order 5 MagLS, 1/r and air loss, near field (geometric or the rigid-sphere distance variation function), moving sources (STFT), geometry reflections, directional late field, head-set selection |
| `room.py` | ours | a room as data: shoebox image sources (still or followed along a path), per-surface absorption filters, the late field's IR and directions, Eyring reverberation time and mixing time from the geometry |
| `data.py` | ours | `python -m spatial_hrtf.data`: download and prepare the head data |

The ambisonic bus (`scripts/spatial_engine/hoa.py`, mix preset `immersive.engine: "hoa_bus"`) uses `sph.sh_matrix`,
`sph.max_rE_weights` and `decoder.magls_bin` from here and builds its own all-round loudspeaker decoder on the
engine's VBAP (`spatial_engine/pan.py`), so `decoder.allrad` / `allrad2` and their loudspeaker hull are not used.

## Changes to their files

- `__init__.py`: fixed version string (theirs runs `git describe` on every import).
- `io.py`: data path is `data/` inside this folder (was `../data/`); `int(np.squeeze(...))` for the sampling rate, because numpy 2.5 rejects `int()` of a one-element array; the download has a timeout and `raise_for_status()`.
- `grids.py`: data path only, as in `io.py`.

PyPI `spaudiopy 0.2.0` does not run on numpy 2.5 / scipy 1.18 (`sph_harm`, `int()` of arrays, undeclared `requests`); upstream master fixed `sph_harm` and not the `int()` calls.
