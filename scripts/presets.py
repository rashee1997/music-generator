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
"""presets.py - every tunable value of the skill, read from preset files. Nothing musical is hard-coded in the scripts.

Layers (later wins, merged key by key, so a project only writes what it changes):
  1. the skill's presets:    references/data/presets/<kind>/*.json
  2. each project's presets: <project>/presets/<kind>/*.json   (added with use_project)

Kinds (each file is one named preset; the file's "name" or its filename is the key):
  cultures     scales, bpm, meter, pattern, roles, avoid_scales, avoid_instruments, soul, note
  styles       roles_add, note, sources
  soul         feel, breath_beats, groove, call_response, ornament, cadence, tempo, avoid_instruments
  mix          lead_band_hz, carve_db, max_boost_db, active_db, lead_db_margin, inst_eq, seating, level_by_role
  instruments  any instrument: gm (the General MIDI name it plays with), expression, vibrato, sustained, bowed, plucked
  sfx          one-hit effect: character, model (voices; sound_model.py) or generator + params or spec, seconds, sources
  gate         piece type for the quality gate: character, extends, flags, detect, rows {row: mode/reason/params}

    python3 scripts/presets.py list                      # every preset and where it comes from
    python3 scripts/presets.py show cultures tamil       # the merged values
    python3 scripts/presets.py validate                  # check the required keys
    python3 scripts/presets.py scaffold cultures mine --project <project>   # a template with every key, documented
    python3 scripts/presets.py ingest my_style.json --project <project>     # copy a preset in by its "kind" key
"""
import argparse
import copy
import glob
import json
import os
import sys

import deep_merge

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_PRESETS = os.path.abspath(os.path.join(HERE, '..', 'references', 'data', 'presets'))
PROJECT_ROOTS = []                       # the latest project added wins, over the skill

KINDS = {
    'cultures': dict(required=['scales', 'bpm', 'meter', 'roles']),
    'styles': dict(required=['roles_add']),
    'soul': dict(required=['feel', 'breath_beats', 'tempo']),
    'mix': dict(required=['carve_db', 'max_boost_db']),
    'instruments': dict(required=[]),
    'vocals': dict(required=[]),
    'environments': dict(required=[]),
    'spaces': dict(required=['room', 'distance']),
    'materials': dict(required=['bands_hz', 'surfaces']),   # surface absorption library a space's geometry names
    'sfx': dict(required=['character']),       # a one-hit effect; ambience (rain, wind, ...) is an environments preset        'gate': dict(required=['character']),      # a piece type for the quality gate (scripts/gate_profiles.py)
        'materials': dict(required=['bands_hz', 'surfaces']),   # surface absorption library a space's geometry names
    'sfzlib': dict(required=['character', 'licence', 'type']),   # a downloadable SFZ library or engine (scripts/sfz_libs.py)
    'video': dict(required=['character', 'probe', 'direction_map', 'staging', 'mix_preset', 'mix', 'master', 'mux']),   # scoring to picture (scripts/video_score.py)
}


def _deep_merge(base, over):
    """Kept as the public name; the rule itself lives in deep_merge.py."""
    return deep_merge.merge(base, over)


def add_project(project_dir):
    root = os.path.abspath(os.path.join(project_dir, 'presets'))
    if root not in PROJECT_ROOTS:
        PROJECT_ROOTS.append(root)
    return root


def reset_projects():
    """Forget every project added so far: one piece must not inherit another project's presets."""
    PROJECT_ROOTS[:] = []


def _files(kind):
    """(name, path, root) for every preset file of a kind, skill first, then projects."""
    out = []
    for root in [SKILL_PRESETS] + PROJECT_ROOTS:
        d = os.path.join(root, kind)
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.endswith('.json'):
                    out.append((os.path.splitext(fn)[0], os.path.join(d, fn), root))
    return out


def load(kind):
    """All presets of a kind, merged across the layers. Returns {name: dict}; the source of each is in '_source'."""
    out = {}
    for fname, path, root in _files(kind):
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        name = data.get('name', fname)
        merged = _deep_merge(out.get(name, {}), {k: v for k, v in data.items() if k != 'name'})
        merged['_source'] = path
        out[name] = merged
    return out


def get(kind, name):
    presets = load(kind)
    if name not in presets:
        raise KeyError(f'no {kind} preset "{name}". Known: {sorted(presets)}. Add one with: presets.py scaffold {kind} {name}')
    return presets[name]


def mix():
    """The one mix preset (the 'default' of the mix kind, with any project overrides merged in)."""
    return get('mix', 'default')


STRICT = False        # project mode: a name must match a preset exactly, no substring guessing


def _norm(name):
    return str(name).lower().strip().replace(' ', '_').replace('-', '_')


def exact(kind, name):
    """The preset called exactly `name` (file stem or "name" key), or None. Never guesses."""
    return load(kind).get(_norm(name))


def _find(kind, name):
    hit = exact(kind, name)
    if hit is not None or STRICT:
        return hit
    name_clean = _norm(name)
    for k, v in load(kind).items():
        if k in name_clean or name_clean in k:
            return v
    return None


def find_instrument(name):
    return _find('instruments', name)


def find_vocal(name):
    return _find('vocals', name)


def find_environment(name):
    return _find('environments', name)


def find_sfx(name):
    """The one-hit effect preset called exactly `name` (project first, shipped default as fallback), or None."""
    return exact('sfx', name)


def find_space(name):
    """The space preset called exactly `name` (project first, shipped as fallback), or None."""
    return exact('spaces', name)


def validate():
    """Missing required keys, for every preset of every kind. Returns a list of problems (empty = good)."""
    problems = []
    for kind, spec in KINDS.items():
        for name, p in load(kind).items():
            for key in spec['required']:
                if key not in p:
                    problems.append(f'{kind}/{name}: missing "{key}" ({p.get("_source")})')
            if kind == 'vocals':                      # numbers out of range, unknown style / register / expression / vowel
                from vocal_engine import config as vcfg
                problems += [f'vocals/{name}: {w} ({p.get("_source")})' for w in vcfg.validate(p)]
            if kind == 'mix':                         # unknown key, bad range, malformed EQ band, unknown profile
                import mix_schema
                problems += [f'mix/{name}: {w} ({p.get("_source")})' for w in mix_schema.validate(p)]
    return problems


def scaffold(kind, name, project_dir, from_name=None):
    """Write a template preset with every key of the kind, so the user can see and change each value."""
    templates = {
        'cultures': dict(name=name, note='what the music is and does', scales=['major'], bpm=[90, 120], meter=4,
                         pattern=None, roles=dict(lead=['flute'], pluck=['piano'], pad=['slow_strings'], bass=['cello'],
                                                  lift=['violin'], chorus=['choir_aahs']),
                         avoid_scales=[], avoid_instruments=[], soul=dict(feel=['a feeling in words'])),
        'styles': dict(name=name, note='what the production sounds like', roles_add=dict(pad=['slow_strings']), sources=[]),
        'soul': dict(name=name, feel=['a feeling in words'], breath_beats=0.5, groove=None, call_response=False,
                     ornament=True, cadence=True, tempo=[80, 120], avoid_instruments=[]),
        'mix': dict(name=name, character='ONE SENTENCE: what this music is (genre, mood, density) and why the mix below suits it', lead_band_hz=2000, carve_db=-4.0, max_boost_db=12.0, active_db=-55.0,
                    lead_db_margin=3.0, inst_eq={}, seating={}, level_by_role={},
                    note='every key is written out, including role_chains and spectral.profiles: change the ones this piece needs. '
                         'An unlisted key comes from references/data/presets/mix/default.json',
                    # the strategies (references/mixing/mixing-and-mastering.md, section 8b). The defaults are what this engine
                    # always did; switch one on per piece rather than loosening a gate row.
                    gain_staging=dict(strategy='legacy', ref_lufs=-24.0, block_s=0.4, max_cut_db=24.0,
                                      peak_headroom_db=-1.0, crest_preserve_db=0.0, sparse_active_frac=0.0,
                                      ref_by_role={}),                      # adaptive: per-role reference, peak/crest guard
                    dynamics=dict(engine='pedalboard', knee_db=0.0, detector='peak', stereo_link=True,
                                  lookahead_ms=0.0, parallel=1.0, sidechain_hp_hz=0.0, sidechain_lp_hz=0.0,
                                  multiband=None, dynamic_eq=None, transient=None),   # engine='dsp' reaches scripts/dsp.py
                    spectral=dict(max_auto_cut_db=0.0, preserve_spectrum_roles=['environment']),   # 0 = no clamp on carve_db
                    space=dict(auto_env_blend=dict(enabled=True),                                  # lift instrument sends when ambience is present
                               drr=dict(enabled=False, target_db=0.0), tail_guard_db=-62.0),
                    sidechain=dict(mode='legacy', band_hz=[250.0, 3800.0], residual=0.3, env_plateau=True),  # legacy|explicit|off
                    automation=dict(curve='linear'),                                                   # linear|cosine|exponential
                    mastering=dict(profile='default'),                                                 # naming a profile in mastering.profiles
                    # headphone immersion: heights by role, every placed track on the measured-head route, reflections from their own
                    # directions. Off by default; set enabled true for a piece that should surround and lift (references/spatial/immersive-spatial.md)
                    immersive=dict(enabled=False, height_by_role=dict(melody=6, pad=15, environment=40, chord=0, bass=0, drum=0),
                                   max_elevation=60, min_height_tracks=1,
                                   pair=dict(width_deg_bed=40.0, width_deg_stereo=12.0),
                                   # a listener's own head set: empty = the bundled FABIAN; else a name in presets/hrtf/ or a path
                                   hrtf=dict(dataset=''),
                                   gate=dict(max_late_iacc=0.4))),
        # "gm" is the General MIDI sound the instrument is built on (see soundbank.py --list); the rest is the staging
        'instruments': dict(name=name, description='what it is and how it is played', gm='acoustic_guitar',
                            role='melody', humanize=dict(preset='natural', timing_ms=6.0, drift_ms=6.0, vel_sigma=4.0),
                            spatial=dict(azimuth=0.0, distance=1.5),   # overwritten below with a free spot
                            eq=[dict(type='hp', f=120.0), dict(type='lp', f=11000.0)], gain_db=-2.0, reverb=0.25,
                            # articulation: how this instrument joins notes (bowed overlaps, wind leaves a breath,
                            # plucked does not overlap); mechanics_class: which table row of the mix preset's
                            # `render.mechanics` supplies the key/bow/breath noise
                            articulation=dict(overlap_ms=30.0, gate=1.0, release_ms=180.0), mechanics_class='keys'),
        # Every key is optional (defaults: references/data/vocal-engine-data/defaults.json; all ranges in its "ranges"). The old flat keys
        # (voices, attack/release in seconds, vib_*, breath, formants, bandwidths, style) still work next to the sections.
        # expression: gentle reflective melancholic hopeful ethereal cinematic devotional powerful intimate mysterious
        # style: tuvan_kargyraa tuvan_sygyt bulgarian_chant nordic_kulning qawwali_devotional gregorian_monastic ...
        'vocals': dict(name=name, character='ONE SENTENCE: who sings, how, and why this voice for this piece',
                       description='the voice and its character', synthesis='formant', vowel='a', hum=False,
                       expression='gentle', expression_intensity=1.0,
                       formants=[800, 1150, 2900], bandwidths=[80.0, 90.0, 120.0],
                       source=dict(register='modal', breathiness=0.03),
                       humming=dict(brightness=0.5, antiformant_hz=1000.0, oral_coupling=0.25, airflow=0.02),
                       vibrato=dict(depth_cents=14.0, rate_hz=5.0, delay_s=0.4),
                       articulation=dict(mode='legato', attack_ms=300.0, release_ms=400.0),
                       performance=dict(portamento_ms=90.0, pitch_stability=1.0),
                       breathing=dict(capacity_s=7.0, inhale_gain=0.5),
                       ensemble=dict(voices=3, cohesion=0.4, pitch_spread_cents=12.0, timing_spread_ms=22.0, pan_width=0.45, diversity=1.0),
                       spatial=dict(azimuth=0.0, distance=1.5)),
        # a place = at least one BED (steady, wide, nothing recognisable) + SPOTS (events with a position). Run
        # `python environment.py --primitives` for every primitive and its parameters. atmosphere switches distance
        # filtering to ISO 9613-1. per layer: kind, gain_db, gain_curve [[s, dB], ...], decorrelate (0-1 width), spatial
        'environments': dict(name=name, character='ONE SENTENCE: the place, the time, and why these layers make it',
                             description='the place and what is audible in it',
                             atmosphere=dict(temp_c=20.0, rh=50.0), layers=[
            dict(name='air_bed', primitive='noise_bed', kind='bed', color='pink', low_hz=100.0, high_hz=2400.0,
                 gain_db=-22.0, decorrelate=0.8),
            dict(name='call_1', primitive='fm_chirp_cluster', kind='spot', f0_low=2000.0, f0_high=3200.0, event_rate=0.25,
                 gain_db=-18.0, trajectory=dict(start_azimuth=-60.0, end_azimuth=50.0, start_distance=7.0, end_distance=6.0))]),
        # a one-hit effect: either "generator" (a built-in code recipe, `sfx.py list`) with "params", or a "spec" of
        # layers (kinds noise, glide, tone, click; see sfx.py). "sources" names the research sections it rests on.
        # "model": voices of excitation -> resonator -> events (python scripts/sound_model.py laws). Any one-hit sound is data.
        'sfx': dict(name=name, character='ONE SENTENCE: what the sound is, what makes it that sound, and where it is heard',
                    seconds=1.0, sources=[], role='fx', gain_db=-8.0, reverb=0.15,
                    spatial=dict(azimuth=0.0, distance=2.0),      # where it sits and how far: the mixer applies these like an instrument's
                    model=dict(seconds=1.0, voices=[dict(name='body',
                        excite=dict(kind='impact', tau=0.003),
                        resonator=dict(kind='modal', law='bar', f1=400.0, n=6, t60=0.4),
                        events=dict(kind='single', at=0.0), gain_db=0.0)])),
        # a piece type for the quality gate: which rows are applied, relaxed (with new numbers) or skipped, each with a reason.
        # `python scripts/gate_profiles.py rows` lists every row and its parameter limits. "extends" inherits; "detect" infers the type.
        # a surface-absorption library a space preset's geometry names (references/data/presets/materials/room_materials.json)
        'materials': dict(name=name, character='ONE SENTENCE: which surfaces this library describes and where the coefficients come from',
                          bands_hz=[125, 250, 500, 1000, 2000, 4000, 8000],
                          surfaces=dict(wood=[0.15, 0.11, 0.10, 0.07, 0.06, 0.07, 0.09],
                                        plaster=[0.02, 0.02, 0.03, 0.04, 0.05, 0.05, 0.05]),
                          sources=[]),
        'gate': dict(name=name, character='ONE SENTENCE: the type of music and why these rules suit it', extends='melodic',
                     flags=[], detect=dict(keywords=[], pulse=[], traits={}),
                     rows={'pattern.loop_short': dict(mode='relax', max_period_bars=2, max_distinct=2, reason='say why this music repeats on purpose')}),
        # scoring to picture: every number the video path uses. A project preset of the same name deep-merges over this one,
        # so an override can be five lines (references/scoring/video-scoring.md).
        'video': dict(name=name, character='ONE SENTENCE: what the video is and why these numbers suit it',
                      probe=dict(analysis_fps=12, analysis_width=320, analysis_height=180,
                                 scene_cut=dict(threshold=10.0, min_gap_s=0.25),      # scdet: 0-100 scale, 8-14 for film
                                 motion_hit=dict(percentile=92, min_gap_s=0.5), keyframe_probe=True),
                      direction_map=dict(energy_curve_bins=8, default_key='D',
                                         tempo_from_cuts=dict(min_bpm=60, max_bpm=168, quantise_bpm=1, prefer_frame_lock=True),
                                         luminance_to_mode=[dict(below=0.35, mode='minor'), dict(below=1.01, mode='major')],
                                         centre_of_motion_to_pan=dict(range=[-0.7, 0.7], max_azimuth_deg=45.0),
                                         warmth_to_timbre=dict(cold='bright', warm='dark')),
                      staging=dict(space=dict(name='video_room',
                                              character='ONE SENTENCE: the place the cue is heard in, and why its tail and distance law suit the picture',
                                              room=dict(rt60=2.2, pre_delay_ms=20, hf_decay=0.6, early_level=0.4),
                                              reflections=dict(ground_delay_ms=6.5, ground_gain=0.45, ground_cutoff_hz=4500,
                                                               lateral_delay_ms=14.0, lateral_gain=0.45, lateral_cutoff_hz=3600,
                                                               reverb_decay_s=2.2, ceiling_delay_ms=15.0, ceiling_gain=0.4,
                                                               rear_delay_ms=24.0, rear_gain=0.35),
                                              distance=dict(ref_m=1.5, falloff=0.18, air_damping=0.4, min_cutoff_hz=3200,
                                                            reverb_exponent=0.65,
                                                            pre_delay_law=dict(base_ms=32.0, per_m=3.5, max_ms=30.0)),
                                              binaural=dict(bed=False, spot=True)),
                                   lead=dict(elevation=4.0, distance=1.4),
                                   pad=dict(elevation=12.0, distance=2.6),
                                   bass=dict(elevation=-6.0, distance=1.2),
                                   drum=dict(elevation=0.0, distance=1.8)),
                      mix_preset=dict(name='video_bed',
                                      character='ONE SENTENCE: what this music is and why this balance suits a cue under picture',
                                      lead_band_hz=2500, carve_db=-3.0, max_boost_db=9.0, active_db=-55.0,
                                      lead_db_margin=3.0, inst_eq={}, seating={},
                                      level_by_role=dict(lead=-2.0, pad=-15.0, chord=-13.0, arp=-16.0,
                                                         bass=-9.0, drum=-11.0, sfx=-9.0),
                                      immersive=dict(enabled=False)),
                      hits=dict(cut_sound='sfx:impact', motion_sound='sfx:whoosh', max_hits_per_minute=24,
                                min_gap_beats=1.0, duration_s=1.0, cut_velocity=0.9, motion_velocity=0.7),
                      mix=dict(voice_lufs=-16.0, bed_db=-10.0, duck_db=-9.0, music_bed_lufs=-20.0, tail_s=1.5,
                               speech_band_hz=[250, 3800], duck_depth_db=-6.0, attack_ms=25, release_ms=300,
                               lookahead_ms=60, low_end_protect_below_hz=200, sfx_headroom_db=-8.0,
                               voice_hp_hz=80.0, voice_mud_hz=500.0, voice_mud_db=-2.0, voice_presence_hz=3500.0,
                               voice_presence_db=2.5, voice_sibilance_hz=7000.0, voice_sibilance_db=-2.0,
                               voice_comp_threshold_db=-24.0, voice_comp_ratio=3.0, voice_comp_attack_ms=3.0,
                               voice_comp_release_ms=40.0, voice_makeup_db=3.0,
                               speech_envelope_attack_ms=5.0, speech_envelope_release_ms=60.0, speech_threshold_db=-38.0,
                               speech_hold_s=0.35, speech_hold_frac=0.02, duck_threshold=0.02, duck_floor_db=-1.0,
                               duck_smooth_s=0.03, music_carve_hz=3000.0, music_carve_db=-3.0, music_hp_hz=60.0,
                               fade_in_s=0.3, fade_out_s=1.2, loop_crossfade_max_s=2.0, sfx_short_gain=0.3,
                               swell=dict(enabled=True, rise_s=1.2, pre_hit_db=2.0, release_s=2.0)),
                      master=dict(profile='streaming', sample_rate=48000, bit_depth=24),
                      master_profiles=dict(streaming=dict(loudness_mode='full_program', lufs=-14.0, true_peak_db=-1.5, tolerance_lu=1.0),
                                           broadcast=dict(loudness_mode='dialogue_gated', lufs=-24.0, true_peak_db=-2.0, tolerance_lu=2.0),
                                           cinema=dict(loudness_mode='dialogue_gated', lufs=-27.0, true_peak_db=-2.0, tolerance_lu=2.0)),
                      mux=dict(video_copy=True, container='mp4',
                               audio_codec=dict(mp4='aac', mov='pcm_s24le', mkv='aac', webm='libopus'),
                               audio_bitrate='320k', faststart=True, shortest=True),
                      gate=dict(duration_tolerance_ms=50, cut_sync=dict(early_ms=45, late_ms=125, aim_ms=40),
                                dialogue_snr_min_db=15.0, loudness_tolerance_lu=1.0),
                      sources=[]),
        # a space is one place: how long its tail is, where its reflections come from, how distance changes a sound in it
        'spaces': dict(name=name, character='ONE SENTENCE: the place and why its tail, walls and distance law suit this piece',
                       room=dict(rt60=1.8, pre_delay_ms=18.0, hf_decay=0.55, early_level=0.35),
                       reflections=dict(ground_delay_ms=8.0, ground_gain=0.3, ground_cutoff_hz=3000, lateral_delay_ms=20.0,
                                        lateral_gain=0.2, lateral_cutoff_hz=2400, reverb_decay_s=1.8, ceiling_delay_ms=25.0,
                                        ceiling_gain=0.15, rear_delay_ms=30.0, rear_gain=0.1, path_physics=True, ref_m=1.5,
                                        # a shoebox room instead of the four fixed taps: real path lengths, one absorption
                                        # filter per surface (references/data/presets/materials/room_materials.json). Remove the
                                        # block to go back to the four keys above.
                                        geometry=dict(width_m=10.0, depth_m=14.0, height_m=6.0,
                                                      listener=dict(x=5.0, y=4.0, z=1.5),
                                                      materials=dict(floor='wood', ceiling='plaster', walls='plaster'),
                                                      material_set='room_materials', max_order=2, max_taps=8,
                                                      min_level_db=-30.0),
                                        # the late field: decorrelated tails from spread directions, not one tail in both ears
                                        late=dict(enabled=False, rt60_s=1.8, hf_decay=0.55, level_db=-18.0,
                                                  count=6, spread_deg=60.0, rise_s=0.02, seed=7,
                                                  bands_hz=[125, 250, 500, 1000, 2000, 4000, 8000])),
                       distance=dict(ref_m=1.5, falloff=0.18, air_damping=0.40, min_cutoff_hz=3200, reverb_exponent=0.65,
                                     pre_delay_law=dict(base_ms=32.0, per_m=3.5, max_ms=30.0),
                                     # below one metre the ears are different distances from the source; strength 0 turns the cue off
                                     near_field=dict(enabled=True, max_m=1.0, head_radius_m=0.0875, strength=1.0,
                                                     lf_boost=2.0, lf_hz=700.0, min_gain=0.35, max_gain=3.0)),
                       air=dict(temp_c=20.0, rh=50.0), binaural=dict(bed=False, spot=True)),
    }
    d = os.path.join(project_dir, 'presets', kind)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name + '.json')
    if kind in ('instruments', 'vocals'):     # give each new preset its own spot on the stage, spread left/right and near/far
        taken = [f for k in ('instruments', 'vocals') for f in glob.glob(os.path.join(project_dir, 'presets', k, '*.json'))
                 if os.path.abspath(f) != os.path.abspath(path)]
        i = len(taken)
        spots = [0, -35, 35, -60, 60, -15, 15, -80, 80]
        templates[kind]['spatial'] = dict(azimuth=float(spots[i % 9]), distance=1.5 + 0.5 * (i % 3) + 0.25 * (i // 9))
    body = templates[kind]
    if from_name:             # start from an existing preset (shipped or another project's); its text is a starting point, not the answer
        src = get(kind, _norm(from_name))
        body = dict(copy.deepcopy({k: v for k, v in src.items() if k not in ('_source', 'kind')}), name=name)
        if 'character' in templates[kind]:
            body['character'] = templates[kind]['character']
        if kind == 'gate':        # inherit rather than copy: the new type writes only what differs
            body = dict(name=name, character=body['character'], extends=_norm(from_name), flags=[], detect=dict(keywords=[]), rows={})
    if kind == 'mix':         # the whole starting set, written out: every role chain and spectral profile visible and editable
        import mix_schema
        body.setdefault('render', copy.deepcopy(mix_schema.DEFAULTS.get('render') or {}))
        body.setdefault('role_chains', copy.deepcopy(mix_schema.ROLE_CHAINS))
        body['spectral'] = dict(body.get('spectral') or {})
        body['spectral'].setdefault('profiles', copy.deepcopy(mix_schema.SPECTRAL_PROFILES))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(body, fh, indent=2)
    return path


def ingest(src, project_dir):
    """Copy a preset file into a project, into the folder of its kind. The file must name its kind in "kind"."""
    data = json.load(open(src, encoding='utf-8'))
    kind = data.pop('kind', None)
    if kind not in KINDS:
        raise ValueError(f'the file needs "kind": one of {sorted(KINDS)}')
    name = data.get('name', os.path.splitext(os.path.basename(src))[0])
    d = os.path.join(project_dir, 'presets', kind)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, name + '.json')
    json.dump(dict(data, name=name), open(dst, 'w', encoding='utf-8'), indent=2)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['list', 'show', 'validate', 'scaffold', 'ingest'])
    ap.add_argument('kind', nargs='?')
    ap.add_argument('name', nargs='?')
    ap.add_argument('--project', default=None)
    ap.add_argument('--from', dest='from_name', default=None, help='scaffold: start from this existing preset of the same kind')
    a = ap.parse_args()
    if a.project:
        add_project(a.project)
    if a.cmd == 'list':
        for kind in KINDS:
            for name, p in load(kind).items():
                print(f'{kind:12s} {name:18s} {p.get("_source")}')
    elif a.cmd == 'show':
        p = get(a.kind, a.name)
        if a.kind == 'mix':               # every key with its shipped value, role chains and spectral profiles included
            import mix_schema
            p = mix_schema.with_defaults(p)
        print(json.dumps(p, indent=2, ensure_ascii=False))
    elif a.cmd == 'validate':
        probs = validate()
        print('\n'.join(probs) if probs else 'all presets have their required keys')
        sys.exit(1 if probs else 0)
    elif a.cmd == 'scaffold':
        print('wrote', scaffold(a.kind, a.name, a.project or '.', a.from_name))
    elif a.cmd == 'ingest':
        print('ingested', ingest(a.kind, a.project or '.'))


if __name__ == '__main__':
    main()
