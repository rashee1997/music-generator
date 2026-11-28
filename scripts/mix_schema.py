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
  3. `role_chains` and `spectral.profiles` live here as starting points rather than inline in `mix_engine/`, so a
     project can replace them from JSON without touching code.

Nothing musical is decided here: these are the values the engine shipped with, restated so they can be
changed.
"""
import copy

import deep_merge
import json
import os


MASTER_TARGETS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'references', 'data',
                                   'master_targets.json')


def master_targets():
    """The mastering profiles and the one default, from references/data/master_targets.json.

    Returns {'default': {...}, 'profiles': {name: {...}}} with each entry's keys `lufs`, `true_peak`, `tone`, `glue`
    (the `source` note stays in the file). The numbers used to be compiled here and in three other modules.
    """
    with open(MASTER_TARGETS_PATH, encoding='utf-8') as f:
        doc = json.load(f)
    keep = ('lufs', 'true_peak', 'tone', 'glue')
    clean = lambda e: {k: v for k, v in e.items() if k in keep}
    return {'default': clean(doc['default']), 'profiles': {n: clean(e) for n, e in (doc.get('profiles') or {}).items()}}


def _master_profiles():
    t = master_targets()
    return dict({'default': t['default']}, **t['profiles'])

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
# Every canonical role (scripts/roles.py) has a chain. These are the same numbers under the other name: a
# `lead` is a melody and an `ostinato` is an arp, so renaming a track never moves its mix.
ROLE_CHAINS['lead'] = ROLE_CHAINS['melody']
ROLE_CHAINS['texture'] = ROLE_CHAINS['pad']
ROLE_CHAINS['ostinato'] = ROLE_CHAINS['arp']
ROLE_CHAINS['percussion'] = ROLE_CHAINS['drum']
# A held centre is not a pad with a low-pass: it has no attack to shape, so almost no compression, and it must
# not be carved where its fundamental and its fifth live.
ROLE_CHAINS['drone'] = {'eq': [{'type': 'hp', 'f': 28}, {'type': 'peak', 'f': 220, 'gain': -1.5, 'q': 0.8},
                               {'type': 'peak', 'f': 2600, 'gain': -2.0, 'q': 0.9}, {'type': 'lp', 'f': 7000}],
                        'comp': {'thr': -30, 'ratio': 1.4, 'attack': 60, 'release': 400}}
ROLE_CHAINS['vocal'] = {'eq': [{'type': 'hp', 'f': 75}, {'type': 'peak', 'f': 500, 'gain': -1.5, 'q': 1.0},
                               {'type': 'peak', 'f': 3000, 'gain': 1.0, 'q': 0.9},
                               {'type': 'peak', 'f': 7000, 'gain': -1.5, 'q': 1.2}],
                        'comp': {'thr': -22, 'ratio': 2.0, 'attack': 12, 'release': 140}}
# An unlisted role used to be mixed as an effect (a high-pass at 100 Hz and no compression), which is how a
# `drone` came out thin. The vocabulary now raises on an unknown role (roles.canonical), so this chain is only a
# last resort for a name a project invents - and a neutral accompaniment is a better last resort than an effect.
ROLE_CHAINS['default'] = ROLE_CHAINS['chord']

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
        'mode': 'bands',               # bands: the fixed bands below. masking: the bands measured over the lead
        'mask_floor_db': 0.0,          # masking mode: only bands where the beds are this far over the lead
        'max_bands': 3,                # masking mode: how many of the worst bands may be carved
        'source': None,                # a track name; None = the loudest melody track
        'bands_hz': [[250.0, 1200.0], [1200.0, 4500.0]],
        'ratio': 2.0,
        'threshold_db': -30.0,
        'attack_ms': 6.0,
        'release_ms': 120.0,
        'roles': ['chord', 'pad', 'arp', 'counter'],
        'skip_ducked': True,           # a role the sidechain already moves under the lead is not carved twice
        # take the source and the band from the score's `mix_intent` (hero, leave_free_hz) when it carries one
        'from_intent': False,
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
        'dynamic_eq': None,            # [{f, q, threshold_db, ratio, attack_ms, release_ms, knee_db, gain_db}]
        'comp': None,                  # {thr, ratio, attack, release} (missing keys: COMP_DEFAULTS), or None/False = no compressor
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
                           'drum': 0.14, 'environment': 0.20,
                           # role -> [the send below which the blend acts, which number above it is raised to]
                           'floors': {'chord': [0.20, 'chord'], 'arp': [0.20, 'chord'], 'melody': [0.22, 'melody'],
                                      'drum': [0.12, 'drum'], 'environment': [0.15, 'environment']}},
        # role -> [the send below which the blend acts, which of the numbers above it is raised to]
        # the room send a track starts with. `default` is every role; add a role to give it its own
        # (a starting set for a new piece: bass 0.0, drum 0.08, pad 0.30, drone 0.26, melody 0.22).
        'send_by_role': {'default': 0.18},
        # extra delay on a role's send, in ms (the dry path is never delayed). A starting range for a
        # vocal is 20-80 ms (iZotope); values are the piece's, not a house rule.
        'predelay_ms_by_role': {},
        'drr': {'enabled': False, 'target_db': 0.0, 'ref_m': 1.5, 'exponent': 0.65},
        # early reflections of the synthesised room: `taps` impulses per channel inside `window_s`, the first at
        # `first_gain`, each next one `tap_decay` of the one before; their RMS is `level` x the tail's RMS
        'er': {'gain_from_tail': True, 'level': 0.35, 'taps': 12, 'first_gain': 0.9, 'tap_decay': 0.82,
               'window_s': [0.006, 0.085]},
        # the synthesised tail (used when the space has no geometry of its own): band-limited noise, each band
        # decaying over rt60 x base x hf_decay^power. A band is [lo_hz, hi_hz, base, power, level].
        'ir': {'bands': [[20, 500, 1.15, 0, 1.0], [500, 3000, 1.0, 0, 1.0], [3000, 9000, 1.0, 1, 0.8],
                         [9000, 18000, 0.6, 1, 0.8]],
               'length_factor': 1.15, 'length_pad_s': 0.05, 'onset_s': 0.012},
        'return': {'highpass_hz': 150.0, 'lowpass_hz': 7500.0},   # the band the shared reverb returns in
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
        # roles ducked only in `band_hz` (the rest of their spectrum follows at `residual` of the duck)
        'band_roles': ['pad', 'texture', 'chord', 'arp', 'ostinato', 'counter', 'environment'],
        'default_duck_db': -4.0,       # a track that names `duck_by` and no depth
        'legacy_env_duck_db': -3.0,    # mode "legacy": how far a bed ducks under the first drum track
        'lookahead_ms': 10.0,
        # follower times when neither the track nor attack_ms/release_ms above names one
        'timing': {'default': {'attack_ms': 8.0, 'release_ms': 180.0, 'smooth_s': 0.0},
                   'environment': {'attack_ms': 25.0, 'release_ms': 1600.0, 'smooth_s': 0.35}},
        'plateau_percentile': 25.0,    # the plateau is this percentile of the duck curve over the musical body
        'plateau_fade_max_s': 2.0,     # ... reached over this long at most,
        'plateau_fade_frac': 0.25,     # ... or this share of the body when the body is short
    },
    'automation': {
        'curve': 'linear',             # linear | cosine | exponential, for the fades and the swells
        'phrase_boundaries': False,
    },
    # How far above the lead an accompaniment may sit before the gate complains. A per-piece decision
    # (a dub bass is not a pad): change it in the project's mix preset, not in quality_gate.py.
    'balance': {
        'allow_db': {'bass': 6.0, 'drum': 6.0, 'chord': 3.0, 'pad': 3.0, 'counter': 3.0, 'arp': 3.0,
                     'texture': 3.0, 'drone': 3.0, 'ostinato': 3.0, 'percussion': 6.0},
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
        'standard': None,              # ebu_r128 | atsc_a85 | aes_td1008 | spotify: the document this profile implements
        'profiles': _master_profiles(),   # references/data/master_targets.json: no loudness is compiled here
        # the chain itself. `tones` maps a tone name to EQ bands (the same band objects as everywhere else);
        # a master block or a profile picks one by name, and a project adds its own by listing it here.
        'highpass_hz': 24.0,           # 0 = none
        'highpass_order': 1,           # first-order filters in cascade: 1 is 6 dB/octave, 3 is 18 dB/octave
        'tones': {
            'neutral': [],
            'warm': [{'type': 'lowshelf', 'f': 120, 'gain': 1.0, 'q': 0.7},
                     {'type': 'highshelf', 'f': 8000, 'gain': -1.5, 'q': 0.7}],
            'earthy': [{'type': 'lowshelf', 'f': 110, 'gain': 1.4, 'q': 0.7},
                       {'type': 'peak', 'f': 320, 'gain': 1.2, 'q': 0.9},
                       {'type': 'highshelf', 'f': 8200, 'gain': -1.8, 'q': 0.7}],
            'forest': [{'type': 'lowshelf', 'f': 110, 'gain': 1.4, 'q': 0.7},
                       {'type': 'peak', 'f': 320, 'gain': 1.2, 'q': 0.9},
                       {'type': 'highshelf', 'f': 8200, 'gain': -1.8, 'q': 0.7}],
            'bright': [{'type': 'highshelf', 'f': 7000, 'gain': 1.8, 'q': 0.7}],
        },
        'glue': {'threshold_db': -18.0, 'ratio': 1.6, 'attack_ms': 40.0, 'release_ms': 250.0},
        # how the limiter loop reaches the loudness target: at most `max_iterations` passes, done within
        # `tolerance_lu`, each correction scaled by `step` (above 1.0 a saturating limiter overshoots);
        # a miss larger than `report_miss_lu` is said on stderr.
        'converge': {'max_iterations': 6, 'tolerance_lu': 0.3, 'step': 0.75, 'report_miss_lu': 1.0},
        'fallback_limiter': {'margin_db': 0.6, 'release_ms': 120.0},   # only if the true-peak limiter is missing
        'min_crest_db': 8.0,           # suggest_master_target: below this much crest a target is called infeasible
        'lra_target_lu': None,         # only reported, never forced
        # Section levels: a gain curve from the plan's section `energy`, applied before the limiter loop, so the loud sections stand above
        # the quiet ones by up to `range_db` between energy 0 and 1 while the integrated loudness still lands on the target. None = off.
        'section_levels': None,        # {"range_db": 10.0, "ramp_s": 1.5}
        'crest_floor_db': 0.0,         # if limiting would take crest below this, stop and report
        # the write (float32, then a 24-bit word) moves a true peak by about 1e-6 dB, so a peak trimmed to exactly the
        # ceiling can land a hair over it. The last safety trim after the DC servo aims this far below the ceiling.
        'true_peak_write_guard_db': 0.001,
        'validate_export': True,       # check the written file: peak, true peak, length, channels
        'report': True,
    },
    # Theatrical realism (references/mixing/theatrical-realism.md). Off by default: every number here is a
    # decision about a cue, not a house rule. `low_mid` keeps the 180-420 Hz region from thickening a dense
    # peak; `air` retains the top octave as the programme gets loud; `detail` lets the direct sound lead the
    # room on attacks, so close detail sits in front of the hall instead of inside it. Starting values.
    'theatrical': {
        'enabled': False,
        'low_mid': {'enabled': True, 'low_hz': 180.0, 'high_hz': 420.0, 'max_dip_db': 2.0,
                    'range_db': 10.0, 'ratio': 2.0, 'attack_ms': 20.0, 'release_ms': 180.0,
                    'knee_db': 6.0},
        'air': {'enabled': True, 'hz': 9000.0, 'max_lift_db': 1.5, 'window_db': 6.0},
        'detail': {'enabled': True, 'duck_db': 2.5, 'attack_ms': 4.0, 'release_ms': 40.0,
                   'ref_db': 18.0},
    },
    # headphone immersion (references/spatial/immersive-spatial.md). Off by default, so an older piece mixes exactly as before.
    # `pair` is how a stereo stem keeps its width: two sources at +-width/2, level normalised for input coherence.
    'immersive': {
        'enabled': False,
        'height_by_role': {'melody': 6.0, 'lead': 6.0, 'vocal': 6.0, 'pad': 15.0, 'texture': 15.0,
                           'environment': 40.0, 'chord': 0.0, 'bass': 0.0, 'drum': 0.0, 'percussion': 0.0,
                           'drone': 0.0, 'ostinato': 0.0},
        'max_elevation': 60.0,
        'min_height_tracks': 1,
        # a listener's own head set: '' = the bundled FABIAN set, else a name in <project>/presets/hrtf/ or a path.
        # f_trans_hz is where MagLS takes over from the linear solution; 1500 Hz is the psychoacoustic crossover
        # (Engel et al. 2022; MMagLS 2025), not the order-dependent N*600 = 3 kHz at order 5.
        # diffuse_eq corrects plain MagLS's high-frequency diffuse-field excess from the loaded head data.
        'hrtf': {'dataset': '', 'f_trans_hz': 1500.0, 'diffuse_eq': True},
        'pair': {'width_deg_bed': 40.0, 'width_deg_stereo': 12.0},
        'gate': {'max_late_iacc': 0.4},
        # 'per_stem' places each track with its own head filter (the engine every older piece was mixed with);
        # 'hoa_bus' writes every source, reflection and tail into one ambisonic field and decodes it once
        # (scripts/spatial_engine/hoa.py): moving sources keep their room, and keyframes and scenes need it.
        'engine': 'per_stem',
        'order': 5,
        # how the TWO-CHANNEL master is decoded from the ambisonic bus: 'binaural' (head-filtered, for headphones;
        # the left and right ears disagree on purpose, so the sum of the two channels loses level in the mid band)
        # or 'speakers' (a loudspeaker pair, layout `stereo_layout`, no head filter: what fold.mono assumes)
        'stereo_decode': 'binaural',
        'stereo_layout': 'stereo_bs775',
        # how an ambisonic field is decoded to loudspeakers: 'allrad2' (panning-invariant loudness, Zotter & Frank
        # 2018) or 'allrad' (the pre-3.1 matrix). Applies to the bus's speaker decode and the ambix QA decode.
        'decoder': 'allrad2',
        # Near-field-coded encoding (Daniel 2003): a source closer than `max_m` gets per-order distance filters
        # so the field keeps a spherical wavefront. Off by default: it changes what every decoder receives, and the
        # low-frequency boost is capped (Favrot & Buchholz regularise at 30 dB). Direct sound only.
        'nfc': {'enabled': False, 'max_m': 1.0, 'ref_m': 1.0, 'max_gain_db': 30.0},
        # how far an "anchor" source (bass, drums, or `spatial_role: "anchor"`) may sway around its place
        'anchor_max_span_deg': 6.0,
        # the fastest a source may travel, read by the imm_kinematics row. Starting values, not measured limits.
        'max_deg_per_sec': {'anchor': 10.0, 'mover': 120.0},
    },
    # strings that are never played but ring with the music (sitar taraf, sarangi, piano with the pedal down).
    # Tuned once per piece: "score_scale" takes the `strings` most-used pitch classes of the source tracks, placed
    # upward from `low_hz`; or give `tuning` as a list of Hz. `level_db` is against the level of the sources.
    'sympathetic_resonance': {
        'enabled': False,
        'sources': [],                # track names or roles; [] = every track that is not drums or a place
        'tuning': 'score_scale',
        'low_hz': 110.0,
        'strings': 7,
        'partials': 3,
        'q': 300.0,
        'level_db': -26.0,
        'width': 0.5,
        'spatial': {},                # where the bed sits on the ambisonic bus ({} = not placed)
    },
    # rendering: how the sampler is driven. `oversample` renders the SoundFont at that multiple of the rate and
    # decimates, which pushes the linear-interpolation images of a transposed sample down (measured: up two octaves
    # on the flute, energy above 15 kHz was -46.2 dB of the note at 1x). `mechanics` is the table mechanics.py reads:
    # the noises a real player and instrument make that a sampled patch does not contain.
    'render': {
        'oversample': 2,
        # where the heavy array work runs (scripts/compute.py). "auto" takes a GPU when torch reports one, and the
        # CPU otherwise; "cpu" never looks. The MUSICGEN_DEVICE environment variable overrides this for one run.
        # `workers` is the FFT thread count on the CPU ("auto" = every core).
        'compute': {'device': 'auto', 'workers': 'auto'},
        # how many stems are processed at once in the mix ("auto" = one per core, 1 = one after another).
        # The count is then capped by the memory this process may still take: `mix_worker_mb_per_second` is the
        # measured working set of one stem per second of audio, so a 16 GB machine fits about a dozen 3-minute
        # stems at once instead of every core's worth (a 7.1.2 mix peaked at 13-14 GB before the cap existed).
        # starting value: derived from a 180 s stem's chain at 44.1 kHz stereo (about 350 MB of working arrays).
        'mix_workers': 'auto',
        'mix_worker_mb_per_second': 2.0,
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
    ('render', 'mix_worker_mb_per_second'): ('num', 0.1, 64.0),
    ('sidechain', 'residual'): ('num', 0.0, 1.0),
    ('sidechain', 'threshold'): ('num', 0.0, 1.0),
    # mixer.py applies the plateau fade only when 2 * fade < body; fade = body * frac, so frac must stay under 0.5
    # (0.5 itself yields no fade); 0.25 is the shipped starting value.
    ('sidechain', 'plateau_fade_frac'): ('num', 0.0, 0.5),
    ('lead_carve', 'ratio'): ('num', 1.0, 20.0),
    ('lead_carve', 'threshold_db'): ('db', -60.0, 0.0),
    ('lead_carve', 'attack_ms'): ('num', 0.0, 100.0),
    ('lead_carve', 'release_ms'): ('num', 5.0, 2000.0),
    ('lead_carve', 'mask_floor_db'): ('db', -24.0, 24.0),
    ('lead_carve', 'max_bands'): ('num', 1, 8),
    ('mastering', 'crest_floor_db'): ('num', 0.0, 30.0),
    ('mastering', 'true_peak_write_guard_db'): ('num', 0.0, 0.5),
    ('mastering', 'highpass_order'): ('num', 1.0, 6.0),
    ('immersive', 'max_elevation'): ('num', 0.0, 90.0),
    ('immersive', 'min_height_tracks'): ('num', 0.0, 24.0),
    ('immersive', 'order'): ('num', 1.0, 7.0),
    ('sympathetic_resonance', 'low_hz'): ('num', 27.5, 2000.0),
    ('sympathetic_resonance', 'strings'): ('num', 1.0, 24.0),
    ('sympathetic_resonance', 'partials'): ('num', 1.0, 8.0),
    ('sympathetic_resonance', 'q'): ('num', 5.0, 2000.0),
    ('sympathetic_resonance', 'level_db'): ('db', -60.0, -6.0),
    ('sympathetic_resonance', 'width'): ('num', 0.0, 1.0),
    ('immersive', 'anchor_max_span_deg'): ('num', 0.0, 45.0),
}

ENUMS = {
    ('gain_staging', 'strategy'): ('legacy', 'adaptive'),
    ('immersive', 'engine'): ('per_stem', 'hoa_bus'),
    ('immersive', 'stereo_decode'): ('binaural', 'speakers'),
    ('immersive', 'decoder'): ('allrad', 'allrad2'),
    ('dynamics', 'engine'): ('pedalboard', 'dsp'),
    ('dynamics', 'detector'): ('peak', 'rms'),
    ('sidechain', 'mode'): ('legacy', 'explicit', 'off'),
    ('lead_carve', 'mode'): ('bands', 'masking'),
    ('mastering', 'standard'): ('ebu_r128', 'atsc_a85', 'aes_td1008', 'spotify'),
    ('automation', 'curve'): ('linear', 'cosine', 'exponential'),
}
COMPUTE_DEVICES = ('auto', 'cpu', 'cuda', 'mps')

OPEN_SECTIONS = {'role_chains', 'spectral_profiles'}     # keyed by a name the project chooses
EQ_TYPES_OK = ('peak', 'bell', 'notch', 'hp', 'lp', 'lowshelf', 'highshelf')
BAND_KEYS_OK = {'type', 'f', 'freq', 'gain', 'q', 'bandwidth', 'load', 'order'}
# dynamics.dynamic_eq entries (read by mixer._dsp_dynamics -> dsp.dynamic_eq); `freq` is the alias _band() accepts
DYNAMIC_EQ_KEYS_OK = {'f', 'freq', 'q', 'threshold_db', 'ratio', 'attack_ms', 'release_ms', 'knee_db', 'gain_db'}
# dynamics.comp: the keys the engine reads and the values used for any the preset leaves out (starting values:
# a gentle 2.5:1 glue compressor, 15 ms / 150 ms, the figures the engine always used before they moved here).
COMP_KEYS_OK = ('thr', 'ratio', 'attack', 'release')
COMP_DEFAULTS = {'thr': -22, 'ratio': 2.5, 'attack': 15, 'release': 150}


def comp_params(comp):
    """One stem's compressor settings: `comp` (a dict) over COMP_DEFAULTS."""
    return _merge(COMP_DEFAULTS, comp)


def with_defaults(mix):
    """The preset laid over the schema defaults, without mutating either."""
    return deep_merge.merge(DEFAULTS, mix)


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
    th = mix.get('theatrical')
    if isinstance(th, dict):
        for key in th:
            if key not in DEFAULTS['theatrical']:
                problems.append(f'mix.theatrical.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(DEFAULTS["theatrical"]))}')
        for part in ('low_mid', 'air', 'detail'):
            got_part = th.get(part)
            if isinstance(got_part, dict):
                for key in got_part:
                    if key not in DEFAULTS['theatrical'][part]:
                        problems.append(f'mix.theatrical.{part}.{key}: unknown key (the engine would ignore it); '
                                        f'known: {", ".join(sorted(DEFAULTS["theatrical"][part]))}')
    imm = mix.get('immersive')
    if isinstance(imm, dict) and isinstance(imm.get('hrtf'), dict):
        for key in imm['hrtf']:
            if key not in DEFAULTS['immersive']['hrtf']:
                problems.append(f'mix.immersive.hrtf.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(DEFAULTS["immersive"]["hrtf"]))}')
        ft = imm['hrtf'].get('f_trans_hz')
        if ft is not None and (not isinstance(ft, (int, float)) or isinstance(ft, bool)
                               or not 200.0 <= float(ft) <= 12000.0):
            problems.append(f'mix.immersive.hrtf.f_trans_hz: {ft} is outside 200..12000 Hz')
    if isinstance(imm, dict) and isinstance(imm.get('nfc'), dict):
        for key in imm['nfc']:
            if key not in DEFAULTS['immersive']['nfc']:
                problems.append(f'mix.immersive.nfc.{key}: unknown key (the engine would ignore it); '
                                f'known: {", ".join(sorted(DEFAULTS["immersive"]["nfc"]))}')
        for key, (lo, hi) in (('max_m', (0.2, 2.0)), ('ref_m', (0.2, 3.0)), ('max_gain_db', (0.0, 40.0))):
            v = imm['nfc'].get(key)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool)
                                  or not lo <= float(v) <= hi):
                problems.append(f'mix.immersive.nfc.{key}: {v} is outside {lo}..{hi}')
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
    dyn = mix.get('dynamics') if isinstance(mix.get('dynamics'), dict) else {}
    cp = dyn.get('comp')
    if cp not in (None, False, 0):
        if not isinstance(cp, dict):
            problems.append('mix.dynamics.comp: expected an object {thr, ratio, attack, release} or false')
        else:
            for k, v in cp.items():
                if k not in COMP_KEYS_OK:
                    problems.append(f'mix.dynamics.comp.{k}: unknown key; known: {", ".join(COMP_KEYS_OK)}')
                elif not isinstance(v, (int, float)) or isinstance(v, bool):
                    problems.append(f'mix.dynamics.comp.{k}: expected a number, got {type(v).__name__}')
    deq = dyn.get('dynamic_eq')
    if deq is not None:
        if not isinstance(deq, list):
            problems.append('mix.dynamics.dynamic_eq: expected a list of bands')
        for i, b in enumerate(deq if isinstance(deq, list) else []):
            path = f'mix.dynamics.dynamic_eq[{i}]'
            if not isinstance(b, dict):
                problems.append(f'{path}: expected an object')
                continue
            problems += [f'{path}: unknown key "{k}" (known: {", ".join(sorted(DYNAMIC_EQ_KEYS_OK))})'
                         for k in b if k not in DYNAMIC_EQ_KEYS_OK]
            f = b.get('f', b.get('freq'))
            if f is None:
                problems.append(f'{path}: missing "f"')
            elif not isinstance(f, (int, float)) or not (10.0 <= float(f) <= 24000.0):
                problems.append(f'{path}.f: {f} is outside 10..24000 Hz')
    comp = (mix.get('render') or {}).get('compute') if isinstance(mix.get('render'), dict) else None
    if comp is not None:
        if not isinstance(comp, dict):
            problems.append('mix.render.compute: expected an object {device, workers}')
        else:
            for key in comp:
                if key not in ('device', 'workers'):
                    problems.append(f'mix.render.compute.{key}: unknown key; known: device, workers')
            if comp.get('device') is not None and comp['device'] not in COMPUTE_DEVICES:
                problems.append(f'mix.render.compute.device: "{comp["device"]}" is not one of {", ".join(COMPUTE_DEVICES)}')
    for name, bands in (((mix.get('mastering') or {}).get('tones') or {}).items()
                        if isinstance(mix.get('mastering'), dict) else ()):
        if not isinstance(bands, list):
            problems.append(f'mix.mastering.tones.{name}: expected a list of EQ bands')
            continue
        problems += _chain_problems(f'mix.mastering.tones.{name}', {'eq': bands})
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


def inert_dynamics(mix):
    """Dynamics keys a preset sets that the chosen engine never reads.

    With `engine: pedalboard` (the default) the compressor is the four-knob one (thr, ratio, attack, release); knee, detector,
    lookahead, makeup, parallel, sidechain filters, multiband, dynamic EQ and the transient shaper only run on
    `engine: dsp` (or on a stem that carries its own `dynamics`). A value that differs from the default under the
    pedalboard engine therefore changes nothing and says nothing: report it so the preset writer picks the engine.
    Returns [(key, value)], empty when the engine is dsp or every such key is at its default."""
    dyn = (mix or {}).get('dynamics')
    if not isinstance(dyn, dict) or str(dyn.get('engine', DEFAULTS['dynamics']['engine'])) != 'pedalboard':
        return []
    base = DEFAULTS['dynamics']
    return [(k, dyn[k]) for k in INERT_UNDER_PEDALBOARD if k in dyn and dyn[k] != base.get(k)]


INERT_UNDER_PEDALBOARD = ('knee_db', 'detector', 'stereo_link', 'lookahead_ms', 'makeup_db', 'parallel', 'multiband', 'dynamic_eq',
                          'transient', 'sidechain_hp_hz', 'sidechain_lp_hz')


def redundant_chains(mix):
    """Names of `role_chains` / `spectral.profiles` entries a preset repeats exactly as the schema ships them. A copy is not
    wrong, but it stops following the schema defaults: a later tuning there never reaches this preset. List only what differs."""
    out = []
    shipped = {'role_chains': ROLE_CHAINS, 'spectral.profiles': (DEFAULTS.get('spectral') or {}).get('profiles') or {}}
    got = {'role_chains': (mix or {}).get('role_chains') or {},
           'spectral.profiles': ((mix or {}).get('spectral') or {}).get('profiles') or {}}
    for sec, items in got.items():
        if isinstance(items, dict):
            out += [f'{sec}.{k}' for k, v in items.items() if shipped[sec].get(k) == v]
    return out


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


