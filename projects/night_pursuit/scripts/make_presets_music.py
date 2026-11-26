#!/usr/bin/env python3
"""make_presets_music.py - writes the music-side presets of Night Pursuit: instruments, the street materials, the street-canyon space
(with the underpass, the bridge and the cliff as room scenes), the mix and the gate profile.

A preset is data: this script only writes the JSON files, so a number can be changed in one place and the files regenerated. Every
number that is not sourced is a starting value and says so in the preset's `sources`.
"""
import json
import os

import timeline as T

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'presets')
SPACE = 'np_street_canyon'
KB = {
    'hybrid': 'KB cinematic-hybrid-scoring (a pulse that does not stop, low brass and sub weight at the turning points, constant percussion, a rising device)',
    'sf': 'KB soundfont-velocity-and-realism (a General MIDI SoundFont has one sample per key: velocity moves level, so the colour is added by velocity_timbre and the section by ensemble)',
    'orch': 'KB orchestral-writing (playable ranges, section sizes and note rates of the instrument)',
    'theat': 'KB theatrical-realism (a section is several players; colour follows loudness)',
    'west': 'KB western (orchestral weight: low strings and timpani carry the pulse, brass the weight)',
}
EST = 'ESTIMATE: azimuth, distance, level and EQ are starting values for this piece, not measured; trim and balance are set after the first measured render'


def write(kind, name, body):
    d = os.path.join(P, kind)
    os.makedirs(d, exist_ok=True)
    body = dict(name=name, **body)
    with open(os.path.join(d, name + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(body, fh, indent=2)


def place(az, dist, el=0.0):
    return dict(azimuth=float(az), elevation=float(el), distance=float(dist), space=SPACE, binaural=True, kind='spot')


def inst(name, gm, role, character, az, dist, gain, reverb, eq, humanize=None, extra=None, sources=()):
    body = dict(character=character, description=character, instrument=gm, role=role,
                humanize=humanize or dict(preset='natural', timing_ms=6.0, drift_ms=6.0, vel_sigma=4.0),
                spatial=place(az, dist), eq=eq, gain_db=float(gain), reverb=float(reverb),
                sources=list(sources) + [EST])
    body.update(extra or {})
    write('instruments', name, body)


HP = lambda f: dict(type='hp', f=float(f))                                  # noqa: E731
LP = lambda f: dict(type='lp', f=float(f))                                  # noqa: E731
PK = lambda f, g, q=1.0: dict(type='peak', f=float(f), gain=float(g), q=float(q))      # noqa: E731

# ----------------------------------------------------------------------------------------------- instruments
inst('pursuit_piano', 'piano', 'ostinato',
     'The pulse: a hard piano playing sixteenths in the lower middle, a little ahead of the beat, the one constant in the 1-3 kHz middle.',
     -75, 2.0, -3.0, 0.10, [HP(90), PK(2200, 1.5, 1.0), LP(11000)],
     humanize=dict(preset='tight', timing_ms=3.0, drift_ms=3.0, vel_sigma=3.0),
     extra=dict(velocity_timbre=dict(points=[[25, 2500], [60, 4500], [127, 9500]], bands=4)),
     sources=[KB['hybrid'], KB['sf']])
inst('pursuit_piano_low', 'piano', 'ostinato',
     'The weight: a low piano octave that doubles the basses on the downbeats and the hits.',
     0, 1.2, -4.0, 0.06, [HP(32), LP(4500)], humanize=dict(preset='tight', timing_ms=3.0, drift_ms=3.0, vel_sigma=3.0),
     sources=[KB['hybrid'], KB['sf']])
inst('pursuit_basses', 'double_bass', 'bass',
     'The low-end owner: double basses on the root and the pedal, long and dark, the one part that holds the lowest octave.',
     0, 1.5, -3.0, 0.04, [HP(36), PK(90, 1.5, 0.9), LP(3000)],
     extra=dict(ensemble=dict(players=3, spread_cents=6, spread_ms=9, vel_spread=3)), sources=[KB['hybrid'], KB['orch'], KB['theat']])
inst('pursuit_celli', 'cello', 'ostinato',
     'The engine of the pulse: staccato celli on eighths and sixteenths, digging into the first beat of each bar.',
     75, 2.2, -4.0, 0.10, [HP(60), PK(1800, 1.5, 1.0), LP(8500)],
     extra=dict(ensemble=dict(players=4, spread_cents=8, spread_ms=10, vel_spread=3)), sources=[KB['hybrid'], KB['orch'], KB['theat']])
inst('pursuit_violins_staccato', 'violin', 'arp',
     'The bridge runs: fast staccato violin figures that pass round the left side, high and dry.',
     -110, 3.0, -6.0, 0.14, [HP(300), PK(3200, 1.0, 1.0), LP(10000)],
     extra=dict(ensemble=dict(players=4, spread_cents=9, spread_ms=11, vel_spread=3)), sources=[KB['hybrid'], KB['orch'], KB['theat']])
inst('pursuit_violins_tremolo', 'synth_strings', 'pad',
     'The tension bed: high tremolo strings that grow by adding players, wide behind the listener on the right.',
     140, 4.0, -9.0, 0.22, [HP(280), LP(9000)],
     extra=dict(ensemble=dict(players=6, spread_cents=10, spread_ms=14, vel_spread=3)), sources=[KB['hybrid'], KB['orch'], KB['theat']])
inst('pursuit_bass_clarinet', 'clarinet', 'counter',
     'The whisper: a clarinet in its low register playing the semitone, the first voice of the motif; close to the right ear.',
     105, 2.4, -6.0, 0.12, [HP(120), PK(900, 1.5, 1.0), LP(7000)], sources=[KB['hybrid'], KB['orch']])
inst('pursuit_horns', 'french_horn', 'melody',
     'The figure: four horns that state the tick, late on each entry and leaning on the leap; the hero of the cue.',
     35, 2.6, -2.0, 0.14, [HP(110), PK(1600, 1.5, 1.0), LP(7500)],
     extra=dict(ensemble=dict(players=4, spread_cents=7, spread_ms=9, vel_spread=3),
                timbre_dynamics=dict(drive=0.45, tilt_db=2.0, tilt_hz=2600, band_hz=[140, 6500], amount=0.5, smooth_s=0.35)),
     sources=[KB['hybrid'], KB['orch'], KB['theat']])
inst('pursuit_trombones', 'trombone', 'chord',
     'The stabs: three trombones on the hits and the clusters, low and hard, in the left half of the stage.',
     -40, 2.8, -4.0, 0.12, [HP(70), PK(1200, 1.5, 1.0), LP(6500)],
     extra=dict(ensemble=dict(players=3, spread_cents=7, spread_ms=9, vel_spread=3)), sources=[KB['hybrid'], KB['orch'], KB['theat']])
inst('pursuit_tuba', 'tuba', 'chord',
     'The floor under the stabs: a tuba doubling the basses on the turning points, never a sustained part.',
     150, 1.8, -5.0, 0.06, [HP(34), LP(2500)], sources=[KB['hybrid'], KB['orch']])
inst('pursuit_sub_drop', 'synth_bass_2', 'texture',
     'The cinematic drop: a single low note that dives an octave and rings, struck only at the snap of the slow motion and at the crash.',
     0, 1.0, -4.0, 0.0, [HP(28), LP(900)],
     extra=dict(mechanics_class='sub'), sources=[KB['hybrid'], 'web research: slow-motion sound design pairs a pitched-down low end with a stretched tail (see the research note)'])
inst('pursuit_timpani', 'timpani', 'drum',
     'The heartbeat and the collapse: two soft strokes a bar in the quiet, a roll into each hit, one big stroke on the turning points.',
     55, 3.0, -4.0, 0.14, [HP(40), LP(5000)], humanize=dict(preset='natural', timing_ms=6.0, drift_ms=6.0, vel_sigma=5.0),
     sources=[KB['hybrid'], KB['sf']])
inst('pursuit_bass_drum', 'standard', 'drum',
     'The heartbeat of the stakeout and the downbeats of the chase: a concert bass drum, felt and low.',
     0, 2.2, -5.0, 0.12, [HP(30), LP(3500)], humanize=dict(preset='tight', timing_ms=4.0, drift_ms=4.0, vel_sigma=4.0),
     extra=dict(gm='orchestral', mechanics_class='drum', onset_fade_ms=1.5, onset_fade_all=True), sources=[KB['hybrid'], KB['sf']])
inst('pursuit_snare', 'standard', 'drum',
     'The 3+3+2 cell and the roll into the crash: a concert snare, dry and sharp.',
     -28, 2.6, -6.0, 0.10, [HP(120), PK(4000, 1.5, 1.0), LP(12000)], humanize=dict(preset='tight', timing_ms=4.0, drift_ms=4.0, vel_sigma=5.0),
     extra=dict(gm='orchestral', mechanics_class='drum', onset_fade_ms=1.5, onset_fade_all=True), sources=[KB['hybrid'], KB['sf']])
inst('pursuit_cymbals', 'standard', 'texture',
     'The air: crashes on the turning points and a long swell into the crash, behind the listener on the left.',
     -150, 3.6, -8.0, 0.20, [HP(500), LP(13000)], humanize=dict(preset='natural', timing_ms=8.0, drift_ms=8.0, vel_sigma=5.0),
     extra=dict(gm='orchestral', mechanics_class='drum', onset_fade_ms=0.3, onset_fade_all=True), sources=[KB['hybrid'], KB['sf']])

# the GM drum kit presets carry `gm`, not `instrument`
for n in ('pursuit_bass_drum', 'pursuit_snare', 'pursuit_cymbals'):
    path = os.path.join(P, 'instruments', n + '.json')
    d = json.load(open(path, encoding='utf-8'))
    d.pop('instrument', None)
    json.dump(d, open(path, 'w', encoding='utf-8'), indent=2)

# ----------------------------------------------------------------------------------------------- the street materials
write('materials', 'np_street', dict(
    kind='materials', character='The surfaces of the street, the underpass and the bridge: a brick facade, a glass front, wet asphalt, painted underpass concrete and a steel deck.',
    note='Absorption coefficients per octave band. The facade value follows the reported facade reflection coefficient of 0.9-0.95 (energy absorption 1 - R^2 = 0.10-0.19); '
         'asphalt, concrete, glass and the steel deck are starting values.',
    bands_hz=[125, 250, 500, 1000, 2000, 4000, 8000],
    surfaces={'brick_facade': [0.14, 0.13, 0.12, 0.12, 0.12, 0.13, 0.15],
              'glass_front': [0.18, 0.06, 0.04, 0.03, 0.02, 0.02, 0.02],
              'asphalt_wet': [0.02, 0.02, 0.03, 0.03, 0.03, 0.04, 0.05],
              'underpass_concrete': [0.01, 0.01, 0.02, 0.02, 0.02, 0.03, 0.04],
              'steel_deck': [0.02, 0.02, 0.02, 0.02, 0.03, 0.04, 0.05],
              'open': [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]},
    sources=['research note: Real-world references: tunnel_air (a street canyon facade reflects 0.9-0.95 of the sound; an underpass rings longer than a street)',
             'ESTIMATE: wet asphalt, steel deck, glass and painted concrete are starting values; the library values for glass and concrete are from Everest & Pohlmann (room_materials)']))

# ----------------------------------------------------------------------------------------------- the space: the street, with scenes
STREET = dict(width_m=18.0, depth_m=140.0, height_m=45.0, listener=dict(x=9.0, y=60.0, z=1.2),
              materials=dict(floor='asphalt_wet', ceiling='open', walls='brick_facade'), material_set='np_street', max_order=3, max_taps=14, min_level_db=-34.0)
UNDERPASS = dict(width_m=16.0, depth_m=140.0, height_m=6.0, materials=dict(floor='asphalt_wet', ceiling='underpass_concrete', walls='underpass_concrete'))
BRIDGE = dict(width_m=24.0, depth_m=140.0, height_m=45.0, materials=dict(floor='steel_deck', ceiling='open', walls='open'))
write('spaces', SPACE, dict(
    kind='spaces',
    character='A wet city street between brick and glass fronts under open sky, with an underpass and a bridge as room changes: a short bright tail, strong side reflections and a long late tail only under the bridge.',
    room=dict(rt60=1.1, pre_delay_ms=10, hf_decay=0.5, early_level=0.45),
    reflections=dict(path_physics=True, ref_m=1.5, ground_delay_ms=5.0, ground_gain=0.5, ground_cutoff_hz=5000, lateral_delay_ms=11.0, lateral_gain=0.55,
                     lateral_cutoff_hz=4200, ceiling_delay_ms=18.0, ceiling_gain=0.05, rear_delay_ms=30.0, rear_gain=0.3,
                     geometry=STREET,
                     late=dict(enabled=True, rt60_s=1.1, hf_decay=0.5, level_db=-21.0, count=8, spread_deg=90.0, rise_s=0.02, seed=2611),
                     ),
    scenes=[
        dict(anchor=dict(section='under_the_bridge'), transition_s=3.0,
             space_overrides=dict(geometry=UNDERPASS, late=dict(rt60_s=2.5, level_db=-12.0, hf_decay=0.45))),
        dict(anchor=dict(section='the_bridge'), transition_s=3.0,
             space_overrides=dict(geometry=BRIDGE, late=dict(rt60_s=0.6, level_db=-28.0, hf_decay=0.6))),
        dict(anchor=dict(section='the_cliff'), transition_s=2.0,
             space_overrides=dict(geometry=dict(STREET, listener=dict(x=9.0, y=60.0, z=1.2)), late=dict(rt60_s=1.1, level_db=-21.0, hf_decay=0.5))),
    ],
    distance=dict(ref_m=1.5, falloff=0.18, air_damping=0.4, min_cutoff_hz=3200, reverb_exponent=0.65,
                  pre_delay_law=dict(base_ms=12.0, per_m=1.5, max_ms=30.0)),
    binaural=dict(bed=False, spot=True),
    sources=['research note: Real-world references: tunnel_air (rt60 of an underpass about 2.5 s is a starting value between a street and a long tunnel; a facade absorbs 0.10-0.19)',
             'ESTIMATE: the street is 18 m between the fronts, 45 m high, open to the sky, with the listener at the centre 1.2 m up (a driver)']))

# ----------------------------------------------------------------------------------------------- the mix
mix_src = os.path.join(P, 'mix', 'night_pursuit_mix.json')
mix = json.load(open(mix_src, encoding='utf-8'))
mix['character'] = ('A loud, close, wet chase: the pulse and the low end carry it, the beds sit under the engine, and the 7.1 field is a fifth-order ambisonic bus decoded once '
                    'to eight speakers with no height.')
mix['note'] = 'Written for Night Pursuit; the scaffold copy of the default was replaced.'
mix['gain_staging']['ref_lufs'] = -22.0
mix['space'] = dict(auto_env_blend=dict(enabled=True),
                    send_by_role=dict(default=0.12, bass=0.0, drum=0.08, percussion=0.08, pad=0.16, texture=0.12, melody=0.12, lead=0.12, counter=0.1, chord=0.1,
                                      ostinato=0.08, arp=0.12, drone=0.1, fx=0.06, environment=0.08),
                    drr=dict(enabled=False, target_db=0.0))
mix['mastering'] = dict(profile='cinema', crest_floor_db=7.0, profiles=dict(cinema=dict(lufs=-16.0, true_peak=-1.5, tone='neutral', glue=True)),
                        highpass_hz=105.0, highpass_order=4)
mix['immersive'] = dict(enabled=True, engine='hoa_bus', order=5, anchor_max_span_deg=6.0, max_deg_per_sec=dict(anchor=10.0, mover=120.0),
                        height_by_role=dict(melody=0.0, lead=0.0, vocal=0.0, pad=0.0, texture=0.0, environment=0.0, chord=0.0, bass=0.0, drum=0.0,
                                            percussion=0.0, drone=0.0, ostinato=0.0, arp=0.0, counter=0.0, fx=0.0),
                        max_elevation=60.0, min_height_tracks=0, stereo_decode='speakers')
mix['lead_carve'] = dict(enabled=True, from_intent=True, roles=['pad', 'texture', 'chord', 'arp', 'counter', 'environment'], ratio=2.0, threshold_db=-34.0)
mix['sidechain'] = dict(mode='legacy', band_hz=[250.0, 3800.0], residual=0.3, env_plateau=True)
mix['dynamics'] = dict(engine='pedalboard', knee_db=0.0, detector='peak', stereo_link=True, lookahead_ms=0.0, parallel=1.0)
write('mix', 'night_pursuit_mix', {k: v for k, v in mix.items() if k != 'name'})

# ----------------------------------------------------------------------------------------------- the space file of the scaffold and the sample presets go
for f in ('spaces/night_pursuit_room.json', 'instruments/lead_flute.json', 'instruments/warm_piano.json', 'instruments/acoustic_bass.json', 'vocals/vocal_hum.json'):
    path = os.path.join(P, f)
    if os.path.exists(path):
        os.remove(path)

# ----------------------------------------------------------------------------------------------- the gate profile (the project's own)
gate_path = os.path.join(P, 'gate', 'night_pursuit.json')
gate = json.load(open(gate_path, encoding='utf-8'))
gate['character'] = ('A film chase cue judged as a build-hit-release piece: a motif on the horns, a pulse that never stops and two slow-motion passages; it starts as `melodic` '
                     'and changes nothing until a render measures a reason.')
gate['extends'] = 'cinematic'
json.dump(gate, open(gate_path, 'w', encoding='utf-8'), indent=1)

if __name__ == '__main__':
    print('wrote', len(os.listdir(os.path.join(P, 'instruments'))), 'instruments, the street materials, the space, the mix and the gate profile')
