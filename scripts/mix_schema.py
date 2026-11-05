# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""mix_schema.py - the default value and the checking rule of every mix setting.

Three jobs:

  1. `DEFAULTS` names every knob the mixer knows, with the value the engine used before this file existed.
     A preset writes only what it changes; `with_defaults()` lays the defaults underneath.
  2. `validate(mix)` reports a key the engine would ignore, an out-of-range number or a wrong type, with
     the path of the problem. A render never guesses: an unknown key is reported, and the value is kept in
     the dict (so a newer preset is not silently rewritten) but never used.
  3. `role_chains` and `spectral.profiles` live here as starting points rather than inline in mixer.py, so a
     project can replace them from JSON without touching code.

Nothing musical is decided here: these are the values the engine shipped with, restated so they can be
changed.
"""
import copy

import deep_merge

EPS = 1e-9

# ---------------------------------------------------------------------------------------------
# role chains: the EQ + compression a role starts with. A preset's "role_chains" replaces one role.
# ---------------------------------------------------------------------------------------------

ROLE_CHAINS = {
    'melody': {'eq': [{'type': 'hp', 'f': 90}, {'type': 'peak', 'f': 280, 'gain': -2.0, 'q': 1.0},
                      {'type': 'peak', 'f': 3500, 'gain': 1.5, 'q': 0.8},
                      {'type': 'highshelf', 'f': 10000, 'gain': 1.5, 'q': 0.7}],
               'comp': {'thr': -22, 'ratio': 2.2, 'attack': 18, 'release': 160}},
    'counter': {'eq': [{'type': 'hp', 'f': 110}, {'type': 'peak', 'f': 300, 'gain': -2.0, 'q': 1.0},
                       {'type': 'peak', 'f': 2800, 'gain': 0.8, 'q': 0.9}],
                'comp': {'thr': -24, 'ratio': 2.0, 'attack': 20, 'release': 160}},
    'chord': {'eq': [{'type': 'hp', 'f': 90}, {'type': 'peak', 'f': 350, 'gain': -2.5, 'q': 1.0},
                     {'type': 'peak', 'f': 2600, 'gain': -2.0, 'q': 1.0}],
              'comp': {'thr': -24, 'ratio': 2.0, 'attack': 25, 'release': 180}},
    'pad': {'eq': [{'type': 'hp', 'f': 160}, {'type': 'peak', 'f': 300, 'gain': -3.0, 'q': 0.9},
                   {'type': 'peak', 'f': 3000, 'gain': -3.0, 'q': 0.9}, {'type': 'lp', 'f': 9500}],
            'comp': {'thr': -26, 'ratio': 1.8, 'attack': 40, 'release': 300}},
    'bass': {'eq': [{'type': 'hp', 'f': 32}, {'type': 'lowshelf', 'f': 90, 'gain': 1.5, 'q': 0.7},
                    {'type': 'peak', 'f': 250, 'gain': -3.0, 'q': 1.0},
                    {'type': 'peak', 'f': 900, 'gain': 1.5, 'q': 0.9}, {'type': 'lp', 'f': 5000}],
             'comp': {'thr': -24, 'ratio': 3.0, 'attack': 22, 'release': 130}},
    'arp': {'eq': [{'type': 'hp', 'f': 200}, {'type': 'peak', 'f': 3000, 'gain': -2.0, 'q': 1.0},
                   {'type': 'lp', 'f': 12000}],
            'comp': {'thr': -24, 'ratio': 2.0, 'attack': 15, 'release': 120}},
    'drum': {'eq': [{'type': 'hp', 'f': 30}, {'type': 'lowshelf', 'f': 80, 'gain': 1.2, 'q': 0.7},
                    {'type': 'peak', 'f': 380, 'gain': -2.0, 'q': 1.1},
                    {'type': 'peak', 'f': 5000, 'gain': 1.5, 'q': 0.9}],
             'comp': {'thr': -18, 'ratio': 2.8, 'attack': 28, 'release': 90}},
    'environment': {'eq': [{'type': 'hp', 'f': 280}, {'type': 'peak', 'f': 450, 'gain': -2.5, 'q': 1.0},
                           {'type': 'peak', 'f': 2400, 'gain': -3.5, 'q': 0.9}, {'type': 'lp', 'f': 7200}],
                    'comp': {'thr': -24, 'ratio': 2.0, 'attack': 30, 'release': 250}},
    'fx': {'eq': [{'type': 'hp', 'f': 100}], 'comp': None},
}
ROLE_CHAINS['default'] = ROLE_CHAINS['fx']          # an unknown role gets the effect chain, as before

# ---------------------------------------------------------------------------------------------
# spectral profiles: what replaces the one universal environment chain when a source says what it is.
# A preset asks for one with "spectral_profile": "rain". No profile = the role chain, unchanged.
# ---------------------------------------------------------------------------------------------

SPECTRAL_PROFILES = {
    'rain': {'eq': [{'type': 'hp', 'f': 300}, {'type': 'peak', 'f': 450, 'gain': -2.0, 'q': 1.0},
                    {'type': 'peak', 'f': 4200, 'gain': 1.0, 'q': 1.0}, {'type': 'lp', 'f': 7500}],
             'comp': None},
    'water': {'eq': [{'type': 'hp', 'f': 280}, {'type': 'peak', 'f': 520, 'gain': -2.0, 'q': 1.0},
                     {'type': 'lp', 'f': 7000}],
              'comp': None},
    'wind': {'eq': [{'type': 'hp', 'f': 120}, {'type': 'peak', 'f': 300, 'gain': -2.0, 'q': 1.0},
                    {'type': 'peak', 'f': 2500, 'gain': -2.0, 'q': 0.9}, {'type': 'lp', 'f': 6000}],
             'comp': None},
    'foliage': {'eq': [{'type': 'hp', 'f': 200}, {'type': 'peak', 'f': 400, 'gain': -1.5, 'q': 1.0},
                       {'type': 'peak', 'f': 3000, 'gain': -2.0, 'q': 1.0}, {'type': 'lp', 'f': 8500}],
                'comp': None},
    'insect': {'eq': [{'type': 'hp', 'f': 900}, {'type': 'peak', 'f': 5000, 'gain': 1.0, 'q': 1.0},
                      {'type': 'lp', 'f': 15000}],
               'comp': None},
    'voice': {'eq': [{'type': 'hp', 'f': 80}, {'type': 'peak', 'f': 500, 'gain': -1.5, 'q': 1.0},
                     {'type': 'peak', 'f': 3000, 'gain': 1.0, 'q': 0.9},
                     {'type': 'peak', 'f': 7000, 'gain': -1.5, 'q': 1.2}],
              'comp': {'thr': -22, 'ratio': 2.0, 'attack': 10, 'release': 120}},
    'strings': {'eq': [{'type': 'hp', 'f': 70}, {'type': 'peak', 'f': 330, 'gain': -1.5, 'q': 1.0},
                       {'type': 'peak', 'f': 4500, 'gain': 1.0, 'q': 1.0}],
                'comp': None},
    'flute': {'eq': [{'type': 'hp', 'f': 220}, {'type': 'peak', 'f': 3200, 'gain': -2.0, 'q': 1.0}],
              'comp': None},
    'bed': ROLE_CHAINS['environment'],          # the legacy environment chain, still available by name
}

# ---------------------------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------------------------

DEFAULTS = {
    'gain_staging': {
        'strategy': 'legacy',          # legacy: min(ref - active_lufs, max_boost_db). adaptive: see mixer.gain_stage
        'ref_lufs': -24.0,
        'block_s': 0.4,
        'active_db': -55.0,
        'max_boost_db': 12.0,
        'max_cut_db': 24.0,
        'ref_by_role': {},             # adaptive only: {"pad": -28, "melody": -22}
        'peak_headroom_db': -1.0,      # adaptive only: a boost may not push this stem's peak above it
        'crest_preserve_db': 0.0,      # adaptive only: if boost would drop crest below this, take less
        'sparse_active_frac': 0.0,     # adaptive only: below this share of playing windows, halve the boost
        'env_fallback_rms_scale': 0.5,
    },
    # Carve the beds only while the lead is sounding in the band they share. Off by default because it is a
    # decision about the piece, not a house rule: a preset that enables it states which roles yield and how far.
    'lead_carve': {
        'enabled': False,
        'source': None,                # a track name; None = the loudest melody track
        'bands_hz': [[250.0, 1200.0], [1200.0, 4500.0]],
        'ratio': 2.0,
        'threshold_db': -30.0,
        'attack_ms': 6.0,
        'release_ms': 120.0,
        'roles': ['chord', 'pad', 'arp', 'counter'],
        'skip_ducked': True,           # a role the sidechain already moves under the lead is not carved twice
    },
    'dynamics': {
        'engine': 'pedalboard',        # pedalboard (threshold/ratio/attack/release) | dsp (the full set)
        'knee_db': 0.0,
        'detector': 'peak',
        'stereo_link': True,
        'lookahead_ms': 0.0,
        'makeup_db': 0.0,
        'parallel': 1.0,               # 1.0 = serial; 0.5 = parallel (NY) compression
        'multiband': None,             # [{lo, hi, threshold_db, ratio, attack_ms, release_ms}]
        'dynamic_eq': None,            # [{f, q, threshold_db, ratio, attack_ms, release_ms, gain_db}]
        'transient': None,             # {attack_db, sustain_db}
        'sidechain_hp_hz': 0.0,
        'sidechain_lp_hz': 0.0,
    },
    'spectral': {
        'profiles': SPECTRAL_PROFILES,
        'preserve_spectrum_roles': ['environment'],   # where "preserve_spectrum": true is honoured by default
        'mid_bands': None,             # [{type, f, gain, q}] on the mid channel
        'side_bands': None,            # [{type, f, gain, q}] on the side channel
        'max_auto_cut_db': 0.0,        # 0 = no clamp: carve_db is used as the preset says. Set 3.0 to bound it
    },
    'space': {
        'auto_env_blend': {'enabled': True, 'chord': 0.22, 'arp': 0.22, 'melody': 0.26,
                           'drum': 0.14, 'environment': 0.20},
        'drr': {'enabled': False, 'target_db': 0.0, 'ref_m': 1.5, 'exponent': 0.65},
        'er': {'gain_from_tail': True, 'level': 0.35},     # gain_from_tail=True keeps the old IR construction
        'cache_ir': True,
        'tail_guard_db': -62.0,
    },
    'sidechain': {
        'mode': 'legacy',              # legacy (auto: env ducks to the first drum track) | explicit | off
        'band_hz': [250.0, 3800.0],
        'residual': 0.3,
        'threshold': 0.05,
        'attack_ms': {},               # per role overrides, e.g. {"environment": 25}
        'release_ms': {},
        'env_plateau': True,           # lock a bed to a steady duck plateau across the musical body
    },
    'automation': {
        'curve': 'linear',             # linear | cosine | exponential, for the fades and the swells
        'phrase_boundaries': False,
    },
    # How far above the lead an accompaniment may sit before the gate complains. A per-piece decision
    # (a dub bass is not a pad): change it in the project's mix preset, not in quality_gate.py.
    'balance': {
        'allow_db': {'bass': 6.0, 'drum': 6.0, 'chord': 3.0, 'pad': 3.0, 'counter': 3.0, 'arp': 3.0},
    },
    # What the mixing diagnostics call mud, harsh, a collision or a held-still transient. Advisory
    # thresholds belong to the piece too: a lo-fi cue may want a wider mud allowance.
    'diagnostics': {
        'mud_db': 3.0,             # <400 Hz over 400 Hz-4 kHz before it is called muddy
        'harsh_db': 6.0,           # 1.2-4 kHz over 400-1200 Hz
        'dull_db': 12.0,           # 1.2-4 kHz this far under the mids is reported as a dark top
        'overlap_db': 4.0,         # two stems within this in a band collide
        'overlap_bands': 3,        # ... in this many bands
        'stem_spread_db': 40.0,    # levels this far apart is a balance problem, not an EQ one
        'drum_crest_min_db': 5.0,  # a percussive stem below this crest is being held still
        'crest_min_db': 4.0,       # a sustained stem below this is being held still
        'env_wet_db': 3.0,         # an ambience this far over the music is too wet
        'env_over_median_db': 6.0, # an ambience this far over the median stem masks the music
        'lead_over_beds_db': 0.0,  # the lead must sit at least this far over the beds in 1-4 kHz
    },
    'mastering': {
        'profile': 'default',          # a name in "profiles"; the score's master block still wins
        'profiles': {
            'default': {'lufs': -14.0, 'true_peak': -1.5, 'tone': 'neutral', 'glue': True},
            'streaming': {'lufs': -14.0, 'true_peak': -2.0, 'tone': 'neutral', 'glue': True},
            'podcast': {'lufs': -16.0, 'true_peak': -1.0, 'tone': 'warm', 'glue': True},
            'broadcast': {'lufs': -23.0, 'true_peak': -1.0, 'tone': 'neutral', 'glue': True},
            'cinema': {'lufs': -18.0, 'true_peak': -1.5, 'tone': 'neutral', 'glue': True},
        },
        'lra_target_lu': None,         # only reported, never forced
        'crest_floor_db': 0.0,         # if limiting would take crest below this, stop and report
        'validate_export': True,       # check the written file: peak, true peak, length, channels
        'report': True,
    },
    # headphone immersion (references/spatial/immersive-spatial.md). Off by default, so an older piece mixes exactly as before.
    # `pair` is how a stereo stem keeps its width: two sources at +-width/2, level normalised for input coherence.
    'immersive': {
        'enabled': False,
        'height_by_role': {'melody': 6.0, 'pad': 15.0, 'environment': 40.0, 'chord': 0.0, 'bass': 0.0, 'drum': 0.0},
        'max_elevation': 60.0,
        'min_height_tracks': 1,
        # a listener's own head set: '' = the bundled FABIAN set, else a name in <project>/presets/hrtf/ or a path
        'hrtf': {'dataset': ''},
        'pair': {'width_deg_bed': 40.0, 'width_deg_stereo': 12.0},
        'gate': {'max_late_iacc': 0.4},
    },
    # rendering: how the sampler is driven. `oversample` renders the SoundFont at that multiple of the rate and
    # decimates, which pushes the linear-interpolation images of a transposed sample down (measured: up two octaves
    # on the flute, energy above 15 kHz was -46.2 dB of the note at 1x). `mechanics` is the table mechanics.py reads:
    # the noises a real player and instrument make that a sampled patch does not contain.
    'render': {
        'oversample': 2,
        'mechanics': {
            'enabled': True,
            'default_class': 'keys',
            'level_db': 0.0,
            # which class a preset gets when it does not set `mechanics_class` (prefix match on the instrument name)
            'class_by_instrument': {
                'violin': 'bowed', 'viola': 'bowed', 'cello': 'bowed', 'double_bass': 'bowed', 'contrabass': 'bowed',
                'strings': 'bowed', 'string_ensemble': 'bowed', 'slow_strings': 'bowed', 'erhu': 'bowed', 'sarangi': 'bowed',
                'flute': 'wind', 'piccolo': 'wind', 'oboe': 'wind', 'clarinet': 'wind', 'bassoon': 'wind', 'sax': 'wind',
                'trumpet': 'wind', 'trombone': 'wind', 'horn': 'wind', 'tuba': 'wind', 'bansuri': 'wind', 'ney': 'wind',
                'shakuhachi': 'wind', 'pan_flute': 'wind', 'recorder': 'wind',
                'guitar': 'plucked', 'harp': 'plucked', 'banjo': 'plucked', 'mandolin': 'plucked', 'lute': 'plucked',
                'sitar': 'plucked', 'koto': 'plucked', 'oud': 'plucked', 'ukulele': 'plucked', 'pizzicato': 'plucked',
                'piano': 'keys', 'organ': 'keys', 'harpsichord': 'keys', 'accordion': 'keys', 'vibraphone': 'keys',
                'drum': 'drum', 'kick': 'drum', 'snare': 'drum', 'hat': 'drum', 'perc': 'drum', 'tabla': 'drum',
            },
            'classes': {
                'bowed': {'onset': {'gain_db': -44.0, 'lo_hz': 1800.0, 'hi_hz': 7000.0, 'ms': 26.0},
                          'offset': {'gain_db': -48.0, 'lo_hz': 900.0, 'hi_hz': 4000.0, 'ms': 60.0}},
                'wind': {'onset': {'gain_db': -42.0, 'lo_hz': 1200.0, 'hi_hz': 6000.0, 'ms': 55.0},
                         'offset': {'gain_db': -50.0, 'lo_hz': 600.0, 'hi_hz': 3000.0, 'ms': 70.0}},
                'plucked': {'onset': {'gain_db': -46.0, 'lo_hz': 1500.0, 'hi_hz': 8000.0, 'ms': 12.0},
                            'offset': {'gain_db': -60.0, 'lo_hz': 400.0, 'hi_hz': 2500.0, 'ms': 40.0}},
                'keys': {'onset': {'gain_db': -44.0, 'lo_hz': 120.0, 'hi_hz': 2600.0, 'ms': 22.0},
                         'offset': {'gain_db': -52.0, 'lo_hz': 100.0, 'hi_hz': 1800.0, 'ms': 45.0}},
                'drum': {'onset': {'gain_db': -60.0, 'lo_hz': 200.0, 'hi_hz': 5000.0, 'ms': 8.0},
                         'offset': {'gain_db': -96.0, 'lo_hz': 200.0, 'hi_hz': 2000.0, 'ms': 0.0}},
            },
        },
    },
    'role_chains': ROLE_CHAINS,
}

# legacy mix-preset keys the engine reads directly (they are not in DEFAULTS because they are flat)
LEGACY_KEYS = {'lead_band_hz', 'carve_db', 'max_boost_db', 'active_db', 'lead_db_margin', 'inst_eq',
               'seating', 'level_by_role', 'widen_by_role', 'saturation', 'spatial', 'env_target_lufs',
               'immersive', 'name', 'character', 'note', '_source', 'role_chains', 'spectral_profiles'}

# (section, key) -> (kind, low, high) for every number with a meaningful range
RANGES = {
    ('gain_staging', 'ref_lufs'): ('db', -70.0, -1.0),
    ('gain_staging', 'max_boost_db'): ('num', 0.0, 30.0),
    ('gain_staging', 'max_cut_db'): ('num', 0.0, 60.0),
    ('gain_staging', 'block_s'): ('num', 0.05, 5.0),
    ('gain_staging', 'active_db'): ('db', -80.0, -20.0),
    ('gain_staging', 'peak_headroom_db'): ('db', -12.0, 0.0),
    ('gain_staging', 'crest_preserve_db'): ('num', 0.0, 40.0),
    ('gain_staging', 'sparse_active_frac'): ('num', 0.0, 1.0),
    ('dynamics', 'knee_db'): ('num', 0.0, 40.0),
    ('dynamics', 'lookahead_ms'): ('num', 0.0, 50.0),
    ('dynamics', 'parallel'): ('num', 0.0, 1.0),
    ('spectral', 'max_auto_cut_db'): ('num', 0.0, 24.0),
    ('render', 'oversample'): ('num', 1, 8),
    ('sidechain', 'residual'): ('num', 0.0, 1.0),
    ('sidechain', 'threshold'): ('num', 0.0, 1.0),
    ('lead_carve', 'ratio'): ('num', 1.0, 20.0),
    ('lead_carve', 'threshold_db'): ('db', -60.0, 0.0),
    ('lead_carve', 'attack_ms'): ('num', 0.0, 100.0),
    ('lead_carve', 'release_ms'): ('num', 5.0, 2000.0),
    ('mastering', 'crest_floor_db'): ('num', 0.0, 30.0),
    ('immersive', 'max_elevation'): ('num', 0.0, 90.0),
    ('immersive', 'min_height_tracks'): ('num', 0.0, 24.0),
}

ENUMS = {
    ('gain_staging', 'strategy'): ('legacy', 'adaptive'),
    ('dynamics', 'engine'): ('pedalboard', 'dsp'),
    ('dynamics', 'detector'): ('peak', 'rms'),
    ('sidechain', 'mode'): ('legacy', 'explicit', 'off'),
    ('automation', 'curve'): ('linear', 'cosine', 'exponential'),
}

OPEN_SECTIONS = {'role_chains', 'spectral_profiles'}     # keyed by a name the project chooses
EQ_TYPES_OK = ('peak', 'bell', 'notch', 'hp', 'lp', 'lowshelf', 'highshelf')
BAND_KEYS_OK = {'type', 'f', 'freq', 'gain', 'q', 'bandwidth', 'load', 'order'}


def with_defaults(mix):
    """The preset laid over the schema defaults, without mutating either."""
    out = copy.deepcopy(DEFAULTS)
    for k, v in (mix or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _merge(base, over):
    """Delegates to the one merge in deep_merge.py."""
    return deep_merge.merge(base, over)


def section(mix, name):
    """One section of an already-resolved mix dict, with the defaults for that section."""
    got = (mix or {}).get(name) or {}
    return _merge(DEFAULTS.get(name, {}), got)


def validate(mix):
    """Problems with a mix preset: unknown keys, bad types, out-of-range numbers, malformed EQ bands.
    Returns a list of strings (empty = good). Never raises."""
    problems = []
    if not isinstance(mix, dict):
        return ['mix preset is not an object']
    for key in mix:
        if key not in DEFAULTS and key not in LEGACY_KEYS:
            problems.append(f'mix: unknown key "{key}" (the engine would ignore it); '
                            f'known sections: {", ".join(sorted(DEFAULTS))}')
    for sec, defaults in DEFAULTS.items():
        got = mix.get(sec)
        if not isinstance(got, dict) or sec in OPEN_SECTIONS:
            continue                       # role_chains is keyed by role name, which is open ended
        for key in got:
            if key not in defaults:
                problems.append(f'mix.{sec}.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(defaults))}')
    for (sec, key), (kind, lo, hi) in RANGES.items():
        val = (mix.get(sec) or {}).get(key) if isinstance(mix.get(sec), dict) else None
        if val is None:
            continue
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            problems.append(f'mix.{sec}.{key}: expected a number, got {type(val).__name__}')
        elif not (lo - EPS <= float(val) <= hi + EPS):
            problems.append(f'mix.{sec}.{key}: {val} is outside {lo}..{hi}')
    for (sec, key), allowed in ENUMS.items():
        val = (mix.get(sec) or {}).get(key) if isinstance(mix.get(sec), dict) else None
        if val is not None and val not in allowed:
            problems.append(f'mix.{sec}.{key}: "{val}" is not one of {", ".join(allowed)}')
    for sec in ('role_chains', 'spectral_profiles'):
        for name, chain in ((mix.get(sec) or {}) if isinstance(mix.get(sec), dict) else {}).items():
            problems += _chain_problems(f'mix.{sec}.{name}', chain)
    for prof, p in ((mix.get('mastering') or {}).get('profiles') or {}).items():
        if not isinstance(p, dict):
            problems.append(f'mix.mastering.profiles.{prof}: expected an object')
            continue
        if 'lufs' in p and not (-40.0 <= float(p['lufs']) <= 0.0):
            problems.append(f'mix.mastering.profiles.{prof}.lufs: {p["lufs"]} is outside -40..0')
        if 'true_peak' in p and not (-12.0 <= float(p['true_peak']) <= 0.0):
            problems.append(f'mix.mastering.profiles.{prof}.true_peak: {p["true_peak"]} is outside -12..0')
    return problems


def _chain_problems(path, chain):
    out = []
    if not isinstance(chain, dict):
        return [f'{path}: expected an object with "eq" and/or "comp"']
    for key in chain:
        if key not in ('eq', 'comp', 'dynamics', 'gain_db'):
            out.append(f'{path}: unknown key "{key}" (known: eq, comp, dynamics, gain_db)')
    for i, band in enumerate(chain.get('eq') or []):
        out += _band_problems(f'{path}.eq[{i}]', band)
    return out


def _band_problems(path, band):
    if not isinstance(band, dict):
        return [f'{path}: expected an object']
    out = [f'{path}: unknown key "{k}" (known: {", ".join(sorted(BAND_KEYS_OK))})'
           for k in band if k not in BAND_KEYS_OK]
    if 'type' not in band:
        out.append(f'{path}: missing "type"')
    elif band['type'] not in EQ_TYPES_OK:
        out.append(f'{path}.type: "{band["type"]}" is not one of {", ".join(EQ_TYPES_OK)}')
    f = band.get('f', band.get('freq'))
    if f is None:
        out.append(f'{path}: missing "f"')
    elif not isinstance(f, (int, float)) or not (10.0 <= float(f) <= 24000.0):
        out.append(f'{path}.f: {f} is outside 10..24000 Hz')
    return out


