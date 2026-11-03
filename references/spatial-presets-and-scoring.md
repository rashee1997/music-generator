# Modular Presets, Direction, Declarative Scores & 3D Spatial Mixing

This document codifies the production architecture for realistic acoustic and spatial music scoring in this skill (modeled on the reference production in `amazon_3d_spatial`).

---

## 1. The Core Law: Modularity over Monolithic Scripts

### The Anti-Pattern (Instruction Failure):
Writing monolithic, one-off Python scripts (`compose_main.py` with 500+ lines) that hardcode notes, instrument synthesis, EQ filters, gains, and spatial maths all together in code. This makes compositions non-reusable, unmaintainable, obscures the direction, and frequently skips 3D spatial physical acoustic modeling.

### The Mandated 5-Stage Architecture:
Every piece must be directed, authored, and executed in clean, modular layers:

```
<project>/
├── direction/
│   └── direction_<title>.json        # Stage 1: Direction & Spatial Intent
├── presets/
│   ├── instruments/                  # Stage 2a: Modular Instrument Presets (EQ, 3D Spatial, GM)
│   ├── vocals/                       # Stage 2b: Formant & Choral Vocal Presets
│   └── environments/                 # Stage 2c: 3D Spatial Soundscapes (Bio-acoustics, Foley)
├── scores/
│   └── <title>_score.json            # Stage 3: Declarative Master Score referencing presets
├── midi/
│   └── <title>_score.mid             # Standard MIDI export
├── stems/                            # Rendered stem tracks
├── reports/
│   ├── research_<topic>.md           # Ethnomusicological and acoustic research notes
│   └── ci_report.json                # Automated CI/CD quality report
├── out/
│   └── master.wav                    # Certified release master audio
├── scripts/
│   └── analyze_music21.py            # Dynamic music21 analysis quality gate
└── STATUS.md                         # Milestone tracking and decisions
```

---

## 2. Directory & File Schemas

### Stage 1: Direction Sheet (`direction/direction_<title>.json`)
Defines the creative brief, musical targets, temporal landmarks, and 3D soundstage coordinates before writing a single note:

```json
{
  "title": "Amazon Arabic Forest Fusion",
  "purpose": "60s cinematic cross-cultural fusion score",
  "duration_s": 60.0,
  "tempo_bpm": 96.0,
  "key": "D",
  "mode": "charukesi_to_hijaz",
  "feel": ["mystical", "grounded", "passionate", "organic"],
  "avoid_feel": ["synthetic", "robotic", "flat", "latin_salsa"],
  "spatial_staging": {
    "lead_vocal": {"azimuth": -15.0, "elevation": 8.0, "distance": 1.7, "space": "forest_canopy"},
    "oud": {"azimuth": 35.0, "elevation": -2.0, "distance": 1.6, "space": "forest_canopy"},
    "bansuri": {"azimuth": -35.0, "elevation": 4.0, "distance": 1.8, "space": "forest_canopy"},
    "sub_bass": {"azimuth": 0.0, "elevation": -8.0, "distance": 1.2, "space": "forest_canopy"},
    "canopy_birds": {"trajectory": {"start_azimuth": -75.0, "end_azimuth": 65.0, "distance": 5.5}}
  },
  "loudness_lufs": -16.0,
  "true_peak_max": -1.5,
  "hits_at": [15.0, 30.0, 45.0, 55.0]
}
```

---

### Stage 2: Modular JSON Presets (`presets/`)

Presets define sound generation, EQ filters, humanization feel, and physical 3D spatial staging. Once defined, they are referenced simply by name in scores.

#### A. Instrument Preset (`presets/instruments/<name>.json`):
```json
{
  "name": "arabic_oud_lute",
  "description": "Fretless Arabic short-necked lute with risha plectrum articulation and warm wooden body",
  "instrument": "acoustic_guitar",
  "role": "chord",
  "program": 24,
  "bank": 0,
  "humanize": {
    "preset": "natural",
    "timing_ms": 6.5,
    "drift_ms": 7.0,
    "vel_sigma": 4.8,
    "strum_ms": 8.0
  },
  "spatial": {
    "azimuth": 35.0,
    "elevation": -2.0,
    "distance": 1.6,
    "space": "forest_canopy"
  },
  "eq": [
    {"type": "hp", "f": 110.0},
    {"type": "peak", "f": 260.0, "gain": 2.2, "q": 1.2},
    {"type": "notch", "f": 420.0, "q": 2.0},
    {"type": "peak", "f": 2800.0, "gain": 2.0, "q": 1.0},
    {"type": "lp", "f": 9500.0}
  ],
  "gain_db": -1.5,
  "reverb": 0.32
}
```

#### B. Vocal Preset (`presets/vocals/<name>.json`):
```json
{
  "name": "vocal_arabic_mawwal",
  "description": "Solo traditional Arabic vocal (Mawwal) in Maqam Hijaz with expressive open vowels",
  "synthesis": "formant",
  "vowel": "a",
  "formants": [720, 1450, 2750],
  "bandwidths": [85.0, 105.0, 135.0],
  "voices": 2,
  "spread_cents": 6.0,
  "vib_cents": 34.0,
  "vib_hz": 5.2,
  "vib_delay": 0.20,
  "breath": 0.035,
  "attack": 0.15,
  "release": 0.35,
  "gain_db": -0.8,
  "reverb": 0.52,
  "spatial": {
    "azimuth": -15.0,
    "elevation": 8.0,
    "distance": 1.7,
    "space": "forest_canopy"
  },
  "eq": [
    {"type": "hp", "f": 140.0},
    {"type": "peak", "f": 720.0, "gain": 2.2, "q": 1.1},
    {"type": "peak", "f": 2600.0, "gain": 2.5, "q": 1.2},
    {"type": "lp", "f": 10500.0}
  ]
}
```

#### C. Environmental Soundscape Preset (`presets/environments/<name>.json`):
```json
{
  "name": "amazon_deep_canopy_3d",
  "description": "Multi-tier 3D Amazon rainforest soundscape with moving bird trajectories and canopy breeze",
  "layers": [
    {
      "name": "canopy_bird_moving",
      "primitive": "fm_chirp_cluster",
      "f0_low": 1800.0,
      "f0_high": 3400.0,
      "mod_rate_hz": 26.0,
      "mod_depth_hz": 140.0,
      "event_rate": 0.7,
      "dur_low": 0.18,
      "dur_high": 0.38,
      "gain_db": -14.0,
      "trajectory": {
        "start_azimuth": -75.0,
        "end_azimuth": 65.0,
        "start_distance": 6.0,
        "end_distance": 4.5
      }
    },
    {
      "name": "canopy_breeze",
      "primitive": "noise_bed",
      "color": "pink",
      "cutoff_hz": 1100.0,
      "gain_db": -20.0,
      "spatial": {
        "azimuth": 0.0,
        "distance": 5.0
      }
    }
  ]
}
```

---

### Stage 3: Declarative Master Score (`scores/<title>_score.json`)

The score holds the composition, notes, sections, and dynamics. Tracks declare their preset by name (`"instrument": "<preset_name>"`). All EQ, 3D spatial staging, gains, and reverb settings are automatically inherited from the preset.

```json
{
  "title": "Amazon Arabic Forest Masterpiece",
  "bpm": 96.0,
  "ts": [4, 4],
  "key": "D",
  "mode": "hijaz",
  "room": "forest_canopy",
  "dynamics": [
    [0.0, 0.40],
    [16.0, 0.55],
    [32.0, 0.75],
    [48.0, 0.95],
    [56.0, 0.80],
    [60.0, 0.30]
  ],
  "master": {
    "lufs": -16.0,
    "true_peak": -1.5,
    "tone": "earthy"
  },
  "tracks": [
    {
      "name": "lead_mawwal",
      "instrument": "vocal_arabic_mawwal",
      "role": "melody",
      "notes": [
        {"t": 16.0, "d": 3.5, "p": 62, "v": 85},
        {"t": 19.5, "d": 4.0, "p": 63, "v": 88}
      ]
    },
    {
      "name": "oud_arps",
      "instrument": "arabic_oud_lute",
      "role": "chord",
      "notes": [
        {"t": 16.0, "d": 0.9, "p": 50, "v": 78},
        {"t": 17.0, "d": 0.9, "p": 54, "v": 76}
      ]
    },
    {
      "name": "forest_ambience",
      "instrument": "env:amazon_deep_canopy_3d",
      "role": "environment",
      "notes": []
    }
  ]
}
```

---

## 3. Physical 3D Spatial Audio & Realism Laws

What `scripts/mixer.py` applies per stem (read from the preset's `spatial` block): `azimuth` -> constant-power pan; `distance` -> air low-pass, direct-level falloff and a reverb-send scale; `width` / `widen` -> mid/side width; one shared room for all stems. **By default `elevation` and `space` are stored but NOT applied**, and no inter-aural delays are used (mono and phone playback stay phase-safe). **Exception: a mix preset with `"immersive": {"enabled": true, ...}`** puts every placed track on the measured-head route with height from `height_by_role`, stereo stems as left/right pairs and directional early reflections; its rules and gate rows are in `references/immersive-spatial.md`. Set `"binaural": true` in a preset's `spatial` block to route that stem through `scripts/spatial.py` instead: Brown-Duda head shadow, Kuhn ITD, pinna/elevation cues, 1/r level, ISO 9613-1 air loss and the early reflections of `space` (`outdoor_open`, `forest_canopy`, `desert_vast`, `bazaar_alley`, `hall`). It folds the stem to mono first, is meant for headphones and point sources (not wide beds), and the mono check in Stage 6 still judges the result. `"binaural": "hrtf"` uses measured head data instead (`scripts/spatial_hrtf`, vendored from spaudiopy, FABIAN set, order-5 MagLS): about 11-12 dB and 0.5 ms between the ears at 60 degrees, plus real height and front/back colour. It needs the one-time data download (`python -m spatial_hrtf.data`, run by `setup_project.py`) and falls back to `spatial.py` with a printed note when the data is missing. It ignores `space` (the shared reverb is the room) and still applies 1/r level and ISO air loss. A moving source (a bird crossing the canopy) takes `"trajectory": {"start_azimuth", "end_azimuth", "start_distance", "end_distance", "start_elevation", "end_elevation", "doppler"}` in its `spatial` block; it always uses the binaural route (`spatial.render_trajectory`). Stage 6 `spatial_staging` warns when tracks are staged off-centre or at a height but the master is nearly mono (L/R correlation above 0.95) and no track uses `binaural` or `trajectory`: the default path is amplitude pan only. Presets must also agree with the direction sheet's `spatial_staging` (azimuth within 10 degrees, distance within 0.75 m). The five principles below are what is modelled:

1. **Distance air filter** (a first-order low-pass by default; give the spatial block `temp_c` or `rh` to use the real ISO 9613-1 filter in `airabs.py`):
   - High frequencies are absorbed by air over distance.
   - Nearby instruments ($d \le 1.5\text{ m}$) preserve 100% of their crisp highs and air ($>12\text{ kHz}$).
   - Distant calls ($d \ge 4.0\text{ m}$) progressively roll off highs via a 1st-order Butterworth low-pass:
     $$f_{cut} = \max\left(3200\text{ Hz}, \frac{22000}{1.0 + 0.40 \cdot (d - 1.5)}\right)$$
   - *Never allow a distant bird, flute, or background soundscape to sizzle with direct 16 kHz highs.*

2. **Distance Direct-to-Reverberant Ratio ($DRR$)**:
   - As a sound source moves further away, direct sound level falls off while diffuse reverberant energy remains steady:
     $$G_{\text{direct}} = \frac{1.0}{1.0 + 0.18 \cdot (d - 1.0)}, \quad \text{Reverb}_{\text{mult}} = \left(\frac{d}{1.5}\right)^{0.65}$$
   - Distant instruments naturally sit inside the acoustic space rather than on top of the listener's eardrum.

3. **Apparent Source Width ($ASW$)**:
   - Solo acoustic leads (flute, solo vocal, oud pluck) have a focused, narrow point-source width ($ASW = 0.85\text{--}1.0$).
   - Harmonic beds, choir pads, and canopy foliage have wide diffused envelopes ($ASW = 1.3\text{--}1.8$).

4. **Azimuth soundstaging** (elevation is rendered only on the binaural route: always when the mix preset is immersive, otherwise per track with `binaural`):
   - Never stack multiple acoustic instruments at $(0^\circ, 0^\circ)$.
   - Position lead instruments at slight elevation ($+4^\circ\text{ to }+8^\circ$) to mimic a standing singer or solo performer.
   - Ground bass instruments at negative elevation ($-5^\circ\text{ to }-8^\circ$) to simulate floor coupling and stage gravity.
   - Spread conversational dialogue (e.g. Bansuri at $-35^\circ$, Oud at $+35^\circ$) across the azimuth arc.

5. **Shared Environmental Acoustic Space**:
   - All instruments, vocals, and procedural soundscapes must route through the **SAME** convolution room space (`forest_canopy`, `large_hall`, `cathedral`).
   - Placing one dry stock MIDI instrument in a wet acoustic soundscape destroys the auditory illusion.

---

## 4. Execution Workflow

To render and certify any piece, run the master CI/CD pipeline pointing directly to the score JSON:

```bash
# Project gate (research, direction, exact presets), then render stems, mix, CI gate. Outputs default to the project:
# out/master.wav, midi/<score>.mid, stems/*.wav, reports/ci_report.json. Exit code 1 while any gate FAILs.
.venv/Scripts/python.exe scripts/pipeline.py scores/amazon_arabic_forest_score.json --project .
```

The pipeline automatically:
1. Discovers and registers `<project>/presets/` (`instruments/`, `vocals/`, `environments/`).
2. Adopts preset spatial coordinates, EQ, and gains into the tracks.
3. Renders stems via `tinysoundfont`, `vocals.py`, and `environment.py`.
4. Mixes with the distance air filter, width, and the distance-scaled reverb send ($DRR$).
5. Masters with `pb.BrickwallLimiter` (-16.0 LUFS, -1.5 dBTP).
6. Audits with the 7 Stage CI Quality Gate.
