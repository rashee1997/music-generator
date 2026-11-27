"""Western Ghats Sunrise: writes the presets, the direction sheet and the score of this project.

Run from anywhere:  python projects/western_ghats_sunrise/scripts/build_project.py
Everything it writes is data (presets/, direction/, scores/). No sound is generated here: sound and space belong in presets/.
Numbers cite research/research_western_ghats_sunrise_rahman_fusion.md (KB ids indian-film-fusion, pan-indian, flutes) or say ESTIMATE.
"""
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.abspath(os.path.join(HERE, '..'))
SKILL = os.path.abspath(os.path.join(P, '..', '..'))
TITLE = 'Western Ghats Sunrise'
SLUG = 'western_ghats_sunrise'
SRC = ['KB indian-film-fusion (Mohanam pentatonic, raga-safe voicings, gamaka, 3+3+2 tala grids)',
       'KB pan-indian and flutes (bansuri range and breath)',
       'research_western_ghats_sunrise_rahman_fusion.md (web sources, search-result text only)',
       'ESTIMATE: azimuth, distance, level and EQ are starting values for this piece, not measured; trim and balance are set after the first measured render']

# ------------------------------------------------------------------ time: 88 BPM, 22 bars = 60 s
BPM = 88.0
BAR_S = 4 * 60.0 / BPM
BARS = 22
SECTIONS = [  # name, first bar, last bar, energy, role, key offset (semitones above Sa=D)
    ('mist', 1, 5, 0.12, 'place', 0),
    ('first_light', 6, 11, 0.38, 'establish', 0),
    ('sunrise', 12, 18, 0.85, 'peak', 2),
    ('morning', 19, 22, 0.35, 'release', 0)]
PENT = [0, 2, 4, 7, 9]           # Mohanam / Bhupali: Sa Re Ga Pa Dha (KB indian-film-fusion 2.1)
SA = 62                          # D4


def beat(bar, b=0.0):
    return (bar - 1) * 4.0 + b


def pit(idx, sa=SA):
    return sa + PENT[idx % 5] + 12 * (idx // 5)


def n(bar, b, d, p, v, **kw):
    out = dict(t=round(beat(bar, b), 4), d=round(d, 4), p=(p if isinstance(p, str) else int(p)), v=round(v, 3))
    out.update(kw)
    return out


def sa_of(bar):
    for _, a, b, _, _, off in SECTIONS:
        if a <= bar <= b:
            return SA + off
    return SA


def write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write('\n')


# ------------------------------------------------------------------ instrument presets
STAGE = dict(bansuri=(0, 6, 1.5), sitar=(-28, 0, 1.9), violins_counter=(28, 12, 2.4), violas=(-56, 0, 2.6), celli=(56, 0, 2.8),
             violins_long=(122, 22, 4.0), tanpura=(-88, -2, 2.6), santoor=(86, 30, 2.8), tabla=(-150, 0, 2.4), pipes=(172, 5, 7.5))


def vel_points(ref, soft=(0.25, 0.50), loud=(4.0, 8.0)):
    return [[25, round(soft[0] * ref)], [55, round(soft[1] * ref)], [100, min(16000, round(loud[0] * ref))], [127, min(16000, round(loud[1] * ref))]]


def inst(name, gm, role, family, character, gain, reverb, eq, hum=None, extra=None):
    az, el, dist = STAGE[name]
    d = dict(name=f'ghats_{name}', description=character, character=character, instrument=gm, role=role, family=family,
             humanize=hum or dict(preset='natural', timing_ms=8.0, drift_ms=8.0, vel_sigma=5.0),
             spatial=dict(azimuth=az, elevation=el, distance=dist, space=f'{SLUG}_room', binaural=True, kind='spot'),
             eq=eq, gain_db=gain, reverb=reverb, sources=list(SRC), soundfont='muse_general')
    d.update(extra or {})
    return d


HP = lambda f: dict(type='hp', f=float(f))
PK = lambda f, g, q=1.0: dict(type='peak', f=float(f), gain=float(g), q=float(q))
LP = lambda f: dict(type='lp', f=float(f))

INSTRUMENTS = [
    inst('pipes', 'bagpipes', 'counter', 'blown_reed',
         'A Scottish Highland piper on the far ridge: a steady drone on A, the Pa of the tanpura, and a chanter that plays the same five notes as the bansuri with a snap and a neighbour gracenote; no swell, no vibrato (a pipe has no dynamics), heard across the valley.',
         -7.0, 0.34, [HP(220), PK(2800, -1.0, 1.0), LP(7000)],
         hum=dict(preset='tight', timing_ms=4.0, lead_ms=6.0),
         extra=dict(bloom=None, noise=None, vibrato=dict(depth_cents=0), expression='flat')),
    inst('bansuri', 'flute', 'melody', 'blown_reed',
         'The lead: a bansuri (bamboo flute) breathing through the Mohanam phrase, pure at the start of each long note and warming as it holds, with a slide into the notes the gamaka asks for.',
         -2.0, 0.22, [HP(220), PK(2600, 1.4, 1.1), LP(11000)],
         hum=dict(preset='natural', timing_ms=6.0, drift_ms=7.0, vel_sigma=4.0, lead_ms=18.0, anticipate_ms=22.0, bar_breath_ms=70.0),
         extra=dict(vibrato=dict(depth_cents=15, rate_hz=5.2, delay_ms=420, model='ou'), expression='breath',
                    velocity_timbre=dict(points=vel_points(1400), zones=10, attack_ms=[[25, 40], [127, 8]]))),
    inst('sitar', 'veena', 'arp', 'plucked',
         'A plucked veena-sitar figure that answers the flute in running eighths, soft in the first light and brighter at the sunrise.',
         -6.0, 0.16, [HP(180), PK(3000, 1.5, 1.0), LP(9000)],
         extra=dict(velocity_timbre=dict(points=vel_points(900, soft=(0.3, 0.6), loud=(3.5, 7.0)), zones=8))),
    inst('violins_counter', 'violin', 'counter', 'bowed',
         "Rahman's string answer: a violin section playing the hook a third below the flute in the flute's rests, bowed and singing, with the vibrato growing on the held notes.",
         -3.5, 0.2, [HP(200), PK(3500, -2.0, 1.0), LP(10000)],
         hum=dict(preset='natural', timing_ms=9.0, drift_ms=8.0, vel_sigma=6.0, anticipate_ms=18.0),
         extra=dict(ensemble=dict(players=4, spread_cents=9, spread_ms=11, vel_spread=5), vibrato=dict(depth_cents=18, rate_hz=5.6, delay_ms=350, model='ou'),
                    velocity_timbre=dict(points=vel_points(2200), zones=10, attack_ms=[[25, 30], [127, 6]]))),
    inst('violas', 'viola', 'ostinato', 'bowed',
         'The pulse of the sunrise: violas bowing the 3+3+2 eighth-note figure, short and a little ahead of the beat, swelling with the section.',
         -5.0, 0.12, [HP(130), PK(300, -2.0, 0.9), PK(2400, 1.0, 1.0), LP(9000)],
         hum=dict(preset='natural', timing_ms=8.0, drift_ms=8.0, vel_sigma=6.0, anticipate_ms=14.0),
         extra=dict(ensemble=dict(players=4, spread_cents=6, spread_ms=7, vel_spread=4), mono_below=700.0,
                    velocity_timbre=dict(points=vel_points(900), zones=12, attack_ms=[[25, 22], [127, 5]]))),
    inst('celli', 'cello', 'bass', 'bowed',
         'The warm floor: celli holding the roots of the raga-safe chords with a slow bow, opening up at the sunrise.',
         -4.0, 0.14, [HP(60), PK(300, -2.5, 0.9), LP(5000)],
         extra=dict(ensemble=dict(players=3, spread_cents=7, spread_ms=9, vel_spread=4), vibrato=dict(depth_cents=14, rate_hz=5.0, delay_ms=500, model='ou'),
                    velocity_timbre=dict(points=vel_points(1200), zones=10, attack_ms=[[25, 26], [127, 5]]))),
    inst('violins_long', 'strings', 'chord', 'bowed',
         'The lush bed: a violin and viola section sustaining the add9, sus2 and minor chords built from the five raga notes, with a slow swell into each chord.',
         -7.0, 0.3, [HP(180), PK(350, -2.0, 0.9), LP(9500)],
         extra=dict(ensemble=dict(players=6, spread_cents=10, spread_ms=14, vel_spread=5),
                    velocity_timbre=dict(points=vel_points(2200), zones=8))),   # no onset ramp: a ramp on a held bed opened a 50 ms hole (stem.dropout, measured)
    inst('tanpura', 'sitar', 'drone', 'plucked',
         'The tanpura drone: the four-string cycle Pa, Sa, Sa, low Sa, plucked softly and left to ring under everything, the anchor of the one key centre.',
         -11.0, 0.3, [HP(70), PK(300, -2.0, 0.9), LP(6500)],
         extra=dict(humanize=dict(preset='natural', timing_ms=10.0, drift_ms=12.0, vel_sigma=4.0))),
    inst('santoor', 'santoor', 'texture', 'struck_pitched',
         'Dew on the leaves: sparse high santoor notes from the five-note scale, soft and bright, scattered over the first light and the morning.',
         -12.0, 0.34, [HP(400), PK(4200, 1.0, 1.0)]),
]

for _i in INSTRUMENTS:
    if _i['name'] == 'ghats_bansuri':       # the one mover: it enters left in the mist, crosses the centre as the sun clears the ridge, settles right for the last breath
        _i['spatial']['trajectory'] = dict(spatial_role='mover', doppler_strength=0.0, keyframes=[
            dict(t_s=0.0, azimuth=-30.0, distance=1.7, elevation=6.0), dict(t_s=13.6, azimuth=-14.0, distance=1.6, elevation=8.0),
            dict(t_s=30.0, azimuth=0.0, distance=1.5, elevation=12.0), dict(t_s=49.1, azimuth=14.0, distance=1.6, elevation=8.0),
            dict(t_s=60.0, azimuth=22.0, distance=1.8, elevation=6.0)])

TABLA = dict(name='ghats_tabla', description='Tabla and daf', instrument='standard', role='drum', family='struck_membrane',
             character='Tabla strokes (ge, na, tin) with a shaker underneath in the 3+3+2 pattern, and one low daf stroke where the sun clears the ridge: light hands, never a kit.',
             humanize=dict(preset='tight', timing_ms=4.0, drum_ms=3.0), gain_db=-4.0, reverb=0.14,
             spatial=dict(azimuth=-150, elevation=0, distance=2.4, space=f'{SLUG}_room', binaural=True, kind='spot'),
             eq=[HP(70), PK(250, -2.0, 0.9), PK(3800, 1.2, 1.0), LP(12000)], sources=list(SRC))


def vocal_choir():
    with open(os.path.join(SKILL, 'references', 'data', 'presets', 'vocals', 'vocal_choir_cinematic.json'), encoding='utf-8') as fh:
        d = json.load(fh)
    d.update(name='ghats_choir', character='A choir of sections that opens with the sun: a breathy high oo at pp, women and men in octaves on the long vowels, and an aa tutti with the singer\'s formant at the crest; the same voices never sing at every dynamic.',
             category='choir_layered', role='pad', gain_db=-6.5, reverb=0.4, sources=list(SRC) + ['scripts/vocal_engine/layers.py; references/data/presets/vocals/vocal_choir_cinematic.json'],
             spatial=dict(azimuth=-125, elevation=24, distance=4.5, space=f'{SLUG}_room', binaural=True, kind='spot'),
             vowel='u', expression='hopeful')
    d['ensemble']['voices'] = 12
    return d


# ------------------------------------------------------------------ the ambience: a shola edge at sunrise (shipped example adapted)
def environment():
    with open(os.path.join(SKILL, 'references', 'data', 'presets', 'environments', 'western_ghats_monsoon.json'), encoding='utf-8') as fh:
        e = json.load(fh)
    e['name'] = SLUG
    e['character'] = ('A shola forest edge in the Western Ghats about 1000 m up as the sun clears the ridge: a stream below, a little mist drip and a light canopy wind '
                      'under a dawn chorus that arrives bird by bird as the light rises, while the tree frogs of the night fall silent.')
    e['medium']['state'] = dict(temperature_k=289.15, pressure_pa=89900, rh_percent=92)
    e['medium']['sources'] = ['ISO 9613-1 for the absorption', '89.9 kPa is the standard atmosphere at 1000 m (starting value)', '16 C and 92 % RH: a clear misty dawn (ESTIMATE)']
    e['controls'] = {'light': {'curve': [[0, 0.12], [14, 0.4], [30, 0.85], [48, 1.0], [60, 0.9]]},
                     'night_fade': {'curve': [[0, 1.0], [12, 0.8], [26, 0.25], [40, 0.05], [60, 0.0]]},
                     'mist_drip': {'curve': [[0, 3], [30, 1.5], [60, 0.5]]}}
    gens = {g['name']: g for g in e['generators']}
    drip = gens['canopy_rain']
    drip['name'] = 'mist_drip'
    drip['population']['rate_mm_h'] = {'control': 'mist_drip'}
    drip['population']['d_mm'] = [0.5, 2.5]
    drip['sources'] = ['Marshall-Palmer drop sizes (scripts/biome/physics.py)', 'ESTIMATE: a light drip from wet leaves after the night, 0.5-3 mm/h; replace once a recording is measured']
    stream = gens['stream']
    stream['spatial'].update(azimuth=-75.0, distance=16.0)
    stream['population']['rate_mm_h'] = 80.0                # ESTIMATE: a brook at 16 m is the steady bed under the birds (measured against the 1 s level steps of the render)
    stream['surface']['area_m2'] = 6.0
    wind = gens['canopy_wind']
    wind['flow']['u_m_s'] = 2.6
    wind['flow']['intensity'] = 0.5
    e['generators'] = [drip, stream, wind]
    frogs = copy.deepcopy(e['fauna'][1])
    frogs.update(first_s=0.5)
    frogs['niche']['active'] = {'control': 'night_fade'}
    frogs['sources'] = ['https://bioone.org/journals/herpetologica/volume-69/issue-1/HERPETOLOGICA-D-11-00042/Vocal-Behavior-of-the-Ponmudi-Bush-Frog-Raorchestes-graminirupes/10.1655/HERPETOLOGICA-D-11-00042.full (dominant frequency steady within a frog)',
                        'https://en.wikipedia.org/wiki/Raorchestes_sanjappai (2.4 kHz dominant frequency)', 'ESTIMATE: pulse structure; a stridulation stand-in']

    def bird(name, call, power, bouts, first_s, band, pos, tube_cm, individuals=2, salience='foreground', sources=()):
        return dict(name=name, call=call, salience=salience, power_w=power, bouts_per_min=bouts, individuals=individuals, first_s=first_s,
                    resonator=dict(kind='tube', length_cm=tube_cm), niche=dict(band_hz=list(band), active={'control': 'light'}),
                    position=dict(azimuth=pos[0], elevation=pos[1], distance=pos[2]), sources=list(sources) + ['ESTIMATE: element contours, lengths and rates (qualitative descriptions only); replace from a measured spectrogram'])
    birds = [
        bird('malabar_whistling_thrush', 'ghats_whistling_thrush', 1.5e-05, 3.0, 4.0, (1300, 3000), (25.0, 20.0, 14.0), 4.5,
             sources=['https://en.wikipedia.org/wiki/Malabar_whistling_thrush (a human-like whistle; longer, melodious phrases in the morning, short sharp whistles later)']),
        bird('malabar_grey_hornbill', 'ghats_hornbill', 4.0e-05, 2.0, 16.0, (700, 2600), (-100.0, 30.0, 40.0), 12.0, individuals=2,
             sources=['https://iucnhornbills.org/malabar-grey-hornbill/ (an assortment of loud, harsh chuckles and squawks with raucous cackling like mock laughter)',
                      'https://app.birdweather.com/species/malabar-gray-hornbill (loud cackling and laughing call; endemic to the Western Ghats)']),
        bird('malabar_barbet', 'ghats_barbet', 1.0e-05, 1.5, 21.0, (800, 1400), (110.0, 38.0, 30.0), 6.0, individuals=1,
             sources=['https://macaulaylibrary.org/asset/646733603 (Kerala recording: a sharp single-note call like a coppersmith barbet, repeated)',
                      'https://en.wikipedia.org/wiki/Malabar_barbet (similar to the coppersmith barbet, a more rapid call)']),
        bird('racket_tailed_drongo', 'ghats_drongo', 1.2e-05, 4.0, 11.0, (1800, 4000), (62.0, 34.0, 17.0), 3.5,
             sources=['https://en.wikipedia.org/wiki/Greater_racket-tailed_drongo (a wide range of loud calls including near-perfect imitations of other birds)',
                      'https://pmc.ncbi.nlm.nih.gov/articles/PMC3945749/ (mimicked notes sit in its repertoire)']),
        bird('flame_throated_bulbul', 'ghats_bulbul', 1.0e-05, 6.0, 14.0, (2800, 4200), (-48.0, 26.0, 11.0), 3.0, individuals=3,
             sources=['https://sanctuarynaturefoundation.org/public/article/shhh-can-you-hear-me%3F (an endemic dawn voice of the Valparai rainforest)'])]
    e['fauna'] = [frogs] + birds
    e['ecology'] = {'density_budget': {'events_per_s_max': 1.2}, 'niches': {'auto': True, 'min_separation': 'D<=0.4'}, 'rules': [],
                    'score': {'occupancy': 'from_score', 'protect_roles': ['melody', 'lead', 'vocal'], 'margin_db': 3, 'pocket_threshold': 0.7}}
    e['spatial_coupling'] = {'field': {'kind': 'diffuse', 'emitters': 12, 'order': 5, 'correlation_target': 0.2}, 'room': {'space': f'{SLUG}_room'}, 'decode_hint': ['stereo', 'immersive_7_1']}
    e['reference'] = {'full_scale_pa': 0.1}                  # ESTIMATE: calibrates the physical levels to a stem that sits near -40 dBFS rms (the shipped 2.0 renders at -65)
    e['sources'] = ['malabar_thrush', 'tree_frogs']      # the sound slugs of research/research_*.md (Real-world references); the other layers carry ESTIMATE in their own blocks
    return e



# ------------------------------------------------------------------ native bird calls (the `calls` presets of this project)
def calls():
    """Species calls built from qualitative descriptions (every number is an ESTIMATE until a spectrogram is measured): a call is a
    sequence of different elements, not a chirp: slides, held whistles with vibrato, pulsed trills, a cackle with noise and a
    register break, a metronomic repeated note, a metallic note beside a rasp."""
    est = ['ESTIMATE: pitch contours, element lengths and pulse rates are written from the qualitative descriptions cited in the fauna block, not measured; replace from xeno-canto spectrograms (analysed only, not kept)']
    def el(f0, ms, **kw):
        d = dict(f0_hz=f0, ms=ms)
        d.update(kw)
        return d
    return {
        'ghats_whistling_thrush': dict(
            name='ghats_whistling_thrush', character='A mellow, meandering human-like whistle: a rising slide, a long held note with a slow vibrato, a falling slide and a quick flutter, answered by the same line.',
            elements=dict(up=el([[0, 1500], [0.45, 2350], [1, 2050]], [500, 700], harmonics=3, rolloff=2.4, vibrato_hz=5.5, vibrato_cents=35, attack=0.15, release=0.3),
                          hold=el([[0, 2000], [0.5, 2060], [1, 1950]], [700, 1000], harmonics=2, rolloff=2.8, vibrato_hz=6.0, vibrato_cents=55, attack=0.2, release=0.35),
                          down=el([[0, 2900], [0.6, 1900], [1, 1350]], [380, 520], harmonics=3, rolloff=2.4, attack=0.1, release=0.3),
                          flutter=el([[0, 2300], [1, 2500]], [260, 380], harmonics=3, rolloff=2.2, pulse_hz=16, pulse_duty=0.6)),
            sequence=['up', 'hold', 'down', ['flutter', 1, 2], 'up', 'hold', 'down'], gap_ms=[90, 220], sources=est),
        'ghats_hornbill': dict(
            name='ghats_hornbill', character='A loud cackle like mock laughter: a run of harsh chuckles, a squawk with a register break, and more chuckles.',
            elements=dict(chuckle=el([[0, 950], [1, 720]], [90, 140], harmonics=14, rolloff=1.0, noise=0.28, subharmonic=0.25, attack=0.04, release=0.3),
                          squawk=el([[0, 1250], [0.4, 1800], [1, 1100]], [380, 520], harmonics=14, rolloff=1.1, noise=0.35, subharmonic=0.3, jump=[0.55, 1.12], attack=0.05, release=0.3)),
            sequence=[['chuckle', 5, 9], 'squawk', ['chuckle', 3, 6]], gap_ms=[60, 120], sources=est),
        'ghats_barbet': dict(
            name='ghats_barbet', character='A sharp, metronomic single note repeated for a long time, a little faster than a coppersmith barbet.',
            elements=dict(tuk=el([[0, 1050], [1, 980]], [55, 80], harmonics=5, rolloff=1.8, attack=0.02, release=0.5)),
            sequence=[['tuk', 14, 30]], gap_ms=[190, 230], sources=est),
        'ghats_drongo': dict(
            name='ghats_drongo', character='A mixed repertoire: a clear metallic note, a held whistle, a harsh pulsed creak and an imitated call with a register break.',
            elements=dict(tink=el([[0, 3300], [0.3, 3000], [1, 2700]], [110, 160], harmonics=6, rolloff=1.4, attack=0.03, release=0.4),
                          whistle=el([[0, 2300], [0.5, 2800], [1, 2400]], [260, 380], harmonics=3, rolloff=2.0, vibrato_hz=7.0, vibrato_cents=40),
                          creak=el([[0, 1900], [1, 1700]], [180, 260], harmonics=10, rolloff=1.2, noise=0.5, pulse_hz=60, pulse_duty=0.5),
                          mimic=el([[0, 3800], [0.5, 2200], [1, 3600]], [200, 320], harmonics=4, rolloff=1.8, jump=[0.5, 0.8])),
            sequence=['tink', 'whistle', ['creak', 1, 2], 'tink', 'mimic', 'whistle'], gap_ms=[80, 240], sources=est),
        'ghats_bulbul': dict(
            name='ghats_bulbul', character='A bright three-to-four note phrase, up, down and a falling last note, repeated.',
            elements=dict(p1=el([[0, 3000], [1, 3300]], [110, 150], harmonics=2, rolloff=2.0), p2=el([[0, 3400], [1, 3000]], [120, 160], harmonics=2, rolloff=2.0),
                          p3=el([[0, 3600], [0.6, 2800], [1, 2500]], [180, 260], harmonics=2, rolloff=2.0, attack=0.1)),
            sequence=['p1', 'p2', 'p1', 'p3'], gap_ms=[70, 120], sources=est)}


# ------------------------------------------------------------------ space and mix: edit the scaffolds
def space():
    path = os.path.join(P, 'presets', 'spaces', f'{SLUG}_room.json')
    with open(path, encoding='utf-8') as fh:
        s = json.load(fh)
    s['character'] = 'An open hillside at sunrise with a ridge across the valley: little early reflection, a soft tail from the slope and the far trees, no walls close by.'
    s['room'] = dict(rt60=1.5, pre_delay_ms=34, hf_decay=0.45, early_level=0.22)
    s['reflections'].update(ground_gain=0.45, lateral_gain=0.22, ceiling_gain=0.0, rear_gain=0.3, reverb_decay_s=1.4)
    s['sources'] = ['ESTIMATE: an open slope has a short tail (about 1.5 s from a facing ridge); starting value, tune against the measured DRR']
    return path, s


def mix():
    path = os.path.join(P, 'presets', 'mix', f'{SLUG}_mix.json')
    with open(path, encoding='utf-8') as fh:
        m = json.load(fh)
    m['character'] = ('A warm acoustic mix: the bansuri is the hero and the beds yield to it in the middle, the strings and choir swell around it, '
                      'the tabla stays under the hands of the strings, and the dawn ambience sits under it all and opens out as the light rises.')
    m['note'] = 'Written for Western Ghats Sunrise; the scaffold copy was replaced.'
    m['mastering'] = dict(m.get('mastering') or {}, profile='cinema', crest_floor_db=7.0, highpass_hz=60.0, highpass_order=2,
                          profiles={'cinema': dict(lufs=-16.0, true_peak=-1.5, tone='neutral', glue=True, fade_out=0.8)},
                          section_levels=dict(range_db=9.0, ramp_s=1.8))
    m['lead_carve'] = dict(enabled=True, from_intent=True)
    m['level_by_role'] = {'environment': -9.0, 'texture': -2.0}
    m['render'] = {'mix_workers': 2}
    m['immersive'] = dict(enabled=True, engine='hoa_bus', order=5, anchor_max_span_deg=6.0, max_deg_per_sec={'anchor': 10.0, 'mover': 120.0},
                          height_by_role={r: 0.0 for r in ('melody', 'lead', 'vocal', 'pad', 'texture', 'environment', 'chord', 'bass', 'drum', 'percussion', 'drone', 'ostinato', 'arp', 'counter', 'fx')},
                          max_elevation=70.0, min_height_tracks=2, stereo_decode='speakers')       # a fifth-order ambisonic bus decoded once to the 7.1 layout and to stereo
    return path, m


def gate():
    path = os.path.join(P, 'presets', 'gate', f'{SLUG}.json')
    with open(path, encoding='utf-8') as fh:
        g = json.load(fh)
    g['character'] = ('A melody-led acoustic piece with an ambience, judged by the melodic rows unchanged: a bansuri line the ear can follow over strings, '
                      'a drone and light percussion; it departs from `melodic` by nothing until a render measures a reason.')
    return path, g


# ------------------------------------------------------------------ the music
HOOK = [(0.0, 1.0, 0), (1.0, 0.5, 1), (1.5, 0.5, 2), (2.0, 1.5, 3), (3.5, 0.5, 2)]            # D E F# A F#: rise, leap of a fifth, step back
HOOK2 = [(0.0, 1.0, 1), (1.0, 1.5, 0), (2.5, 0.5, 1), (3.0, 1.0, 0)]                         # E D E D: the answer, settling


def hook(bar, idx_shift, vel, sa, rhythm_scale=1.0, answer=True, tail_to=None):
    out = []
    for b, d, i in HOOK:
        out.append(n(bar, b, d * rhythm_scale, pit(i + idx_shift, sa), vel))
    if answer:
        for b, d, i in HOOK2:
            out.append(n(bar + 1, b, d * rhythm_scale, pit(i + idx_shift, sa), vel * 0.92))
    return out


def breaths(notes, max_run=13.0, gap=0.45):
    """A wind player needs air: shorten the note that ends a run longer than `max_run` beats (about 9 s at 88 BPM) so a gap of `gap` beats opens."""
    out = sorted((dict(x) for x in notes), key=lambda x: x['t'])
    run0 = None
    for i, x in enumerate(out):
        if run0 is None:
            run0 = x['t']
        end = x['t'] + x['d']
        nxt = out[i + 1]['t'] if i + 1 < len(out) else None
        if nxt is not None and nxt - end < gap:
            if end - run0 > max_run:
                x['d'] = round(max(0.25, nxt - x['t'] - gap), 4)
                run0 = None
        else:
            run0 = None
    return out


def flute():
    S0 = SA + 12                                   # the bansuri sings from D5
    s = []
    # mist (bars 1-5): the breath, one long note then a slow phrase; a slide up into the fifth
    s += [n(1, 0, 4.0, pit(0, S0), 0.45, gl=-180), n(2, 0, 2.0, pit(1, S0), 0.5), n(2, 2, 2.0, pit(2, S0), 0.52),
          n(3, 0, 3.0, pit(3, S0), 0.55, gl=-140), n(3, 3, 1.0, pit(2, S0), 0.5), n(4, 0, 2.0, pit(1, S0), 0.5), n(4, 2, 2.0, pit(0, S0), 0.48),
          n(5, 0, 3.5, pit(0, S0), 0.5)]
    # first light (bars 6-11): the hook, its answer, the hook again, then higher and more ornamented
    s += hook(6, 0, 0.58, S0) + hook(8, 0, 0.62, S0) + hook(10, 2, 0.68, S0)
    # sunrise (bars 12-18) in E: the hook a step up, then running eighths with a leap to the sixth (Dha)
    sa = S0 + 2
    s += hook(12, 0, 0.82, sa)
    s += [n(14, 0, 1.0, pit(3, sa), 0.84), n(14, 1, 0.5, pit(4, sa), 0.85), n(14, 1.5, 0.5, pit(5, sa), 0.86), n(14, 2, 1.5, pit(6, sa), 0.9, gl=-120),
          n(14, 3.5, 0.5, pit(5, sa), 0.84), n(15, 0, 1.0, pit(4, sa), 0.84), n(15, 1, 0.5, pit(5, sa), 0.86), n(15, 1.5, 0.5, pit(6, sa), 0.88),
          n(15, 2, 2.0, pit(7, sa), 0.92, gl=-160), n(16, 0, 1.75, pit(6, sa), 0.9),                                # the flute rests for six beats: the pipes take bars 16-17
          n(18, 0, 4.0, pit(4, sa), 0.8, gl=-100)]
    # morning (bars 19-22): back in D: the hook once, softly, then Sa alone
    s += hook(19, 0, 0.5, S0) + [n(21, 0, 2.0, pit(2, S0), 0.42), n(21, 2, 2.0, pit(0, S0), 0.4), n(22, 0, 4.0, pit(0, S0), 0.32, gl=-100)]
    return breaths(s)


def up_step(p, sa):
    """The next pitch above `p` that belongs to the raga's five notes (Sa = sa): the neighbour a gracenote leans on."""
    ok = {(sa + x) % 12 for x in PENT}
    q = p + 1
    while q % 12 not in ok:
        q += 1
    return q


def with_grace(notes, sa, lead=0.1):
    """A piper's cut: a very short neighbour note just before each main note of 0.5 beat or more (Scottish ornament, ESTIMATE timing)."""
    out = []
    for x in sorted(notes, key=lambda y: y['t']):
        if x['d'] >= 0.5:
            out.append(dict(t=round(x['t'] - lead, 4), d=round(lead, 4), p=up_step(x['p'], sa), v=round(x['v'] * 0.8, 3)))
        out.append(x)
    return [x for x in out if x['t'] >= 0]


def pipes():
    s = []
    # the drone swells in under the tanpura (A = Pa and D = Sa, the highland drones' own A): bars 9-11 and again at the end, bars 19-20
    for first, last, v in ((9, 11, 0.42), (19, 20, 0.36)):
        s += bar_notes(first, last, pit(3, SA - 24), v)                                          # A2: a bass drone, clear of the strings' notes above
    # the chanter doubles the hook an octave below the flute in the new key (heterophony), cut by gracenotes: bars 12-13
    sa = SA + 2
    s += with_grace([x for x in hook(12, 0, 0.6, sa)], sa)
    # the call: a dotted figure of snaps with a gracenote, in the flute's six rests, bars 16-17 (key E: the pipes' B mixolydian is the same E major notes)
    call = [(2.0, 0.75, 3), (2.75, 0.25, 4), (3.0, 0.75, 5), (3.75, 0.25, 4)]
    call2 = [(0.0, 0.75, 3), (0.75, 0.25, 2), (1.0, 1.0, 3), (2.0, 0.75, 1), (2.75, 0.25, 2), (3.0, 1.0, 0)]
    notes = [n(16, b, d, pit(i, sa), 0.62) for b, d, i in call] + [n(17, b, d, pit(i, sa), 0.62) for b, d, i in call2]
    s += with_grace(notes, sa)
    s += bar_notes(16, 17, pit(3, sa - 12), 0.4)[:0]
    return s



def counter():
    s = []
    for bar, vel, sa, sh in ((7, 0.5, SA, -2), (9, 0.55, SA, -2), (11, 0.6, SA, -2)):                  # answers in the flute's rests, a third below
        s += [n(bar, 2.0, 1.0, pit(1 + sh, sa), vel), n(bar, 3.0, 1.0, pit(2 + sh, sa), vel), n(bar + 1, 0.0, 2.0, pit(3 + sh, sa), vel + 0.05)]
    sa = SA + 2
    for bar in (13, 15, 17):
        s += [n(bar, 2.0, 0.5, pit(3, sa), 0.8), n(bar, 2.5, 0.5, pit(4, sa), 0.82), n(bar, 3.0, 1.0, pit(5, sa), 0.88), n(bar + 1, 0.0, 2.0, pit(6, sa), 0.9)]
    s += [n(20, 2.0, 1.0, pit(1), 0.4), n(20, 3.0, 1.0, pit(2), 0.4), n(21, 0.0, 2.0, pit(3), 0.38)]
    return s


# chords from the five raga notes only (raga-safe voicings, KB indian-film-fusion 3.1): (bars, degree indices, Sa)
D_ADD9, BM, ASUS2, D_TRIAD = [0, 1, 2, 3], [-1, 0, 2], [3, 4, 6], [0, 2, 3]       # D E F# A | B D F# | A B E


def chords():
    out = []
    for bars, idxs, sa in (((6, 7), D_ADD9, SA), ((8, 9), BM, SA), ((10,), D_ADD9, SA), ((11,), ASUS2, SA),
                           ((12, 13), D_ADD9, SA + 2), ((14, 15), BM, SA + 2), ((16,), D_ADD9, SA + 2), ((17, 18), ASUS2, SA + 2),
                           ((19, 20), D_ADD9, SA), ((21, 22), D_TRIAD, SA)):
        out.append((bars, idxs, sa))
    return out


def bar_notes(first, last, pitch, vel, tail_bar=BARS):
    """A held chord tone as one note per bar, each overlapping the next by half a beat: a sampled sustain that is held for six seconds ends
    before the written note does (measured: stem.dropout at the chord changes), and a re-attack that overlaps never opens a hole."""
    out = []
    for bar in range(first, last + 1):
        out.append(n(bar, 0.0, 4.0 if bar == tail_bar else 4.5, pitch, vel))
    return out


def strings_bed():
    s = []
    for p, v in ((pit(0, SA), 0.5), (pit(3, SA), 0.48)):
        s += bar_notes(3, 5, p, v)                                                               # open fifth under the end of the mist
    for bars, idxs, sa in chords():
        v = 0.52 if bars[0] < 12 else (0.84 if bars[0] < 19 else 0.48)
        for i in idxs:
            s += bar_notes(bars[0], bars[-1], pit(i, sa), v - 0.04 * (i % 2))
    return s


def violas():
    s = []
    for bar in range(12, 19):
        sa = SA + 2
        root, fifth, nine = pit(0, sa - 12), pit(3, sa - 12), pit(1, sa - 12)
        if bar in (14, 15):
            root, fifth, nine = pit(-1, sa - 12), pit(2, sa - 12), pit(0, sa - 12)                  # the minor colour (Dha)
        v0 = 0.62 + 0.04 * (bar - 12)
        for b, p, vv in ((0.0, root, v0 + 0.08), (1.5, nine, v0), (3.0, fifth, v0 - 0.04)):         # 3+3+2 eighths
            s.append(n(bar, b, 0.5, p, vv))
            s.append(n(bar, b + 0.5, 0.5, root if b != 0.0 else nine, vv - 0.1))
    return s


def celli():
    s = bar_notes(1, 5, pit(0, SA - 24), 0.5)
    for bars, idxs, sa in chords():
        v = 0.56 if bars[0] < 12 else (0.82 if bars[0] < 19 else 0.5)
        s += bar_notes(bars[0], bars[-1], pit(idxs[0], sa - 24) + (12 if idxs[0] < 0 else 0), v)
    return s


def basses():
    s = []
    for bar in range(12, 19):
        sa = SA + 2
        s.append(n(bar, 0.0, 4.25, pit(0, sa - 24), 0.7))
    s.append(n(19, 0.0, 8.0, pit(0, SA - 24), 0.62))
    return s


def tanpura():
    s = []
    for bar in range(1, BARS + 1):
        sa = sa_of(bar)
        for b, d, p, v in ((0.0, 1.4, pit(3, sa - 24), 0.34), (1.5, 0.95, pit(0, sa - 12), 0.32), (2.5, 1.4, pit(0, sa - 12), 0.3), (3.5, 2.2, pit(0, sa - 24), 0.3)):
            s.append(n(bar, b, d, p, v))
    return s


def sitar():
    s = []
    for bars, sa, vel in (((6, 7, 8, 9, 10, 11), SA, 0.4), ((12, 13, 14, 15, 16, 17, 18), SA + 2, 0.62), ((19, 20), SA, 0.36)):
        for bar in bars:
            for k, (b, idx) in enumerate(((0.0, 0), (0.5, 2), (1.0, 3), (1.5, 2), (2.0, 4), (2.5, 3), (3.0, 2), (3.5, 1))):
                if bar < 12 and k % 2:
                    continue
                s.append(n(bar, b, 0.5, pit(idx, sa), vel + (0.06 if k % 4 == 0 else 0.0)))
    return s


def santoor():
    s = []
    for bar in list(range(8, 12)) + [19, 20]:
        sa = sa_of(bar)
        for k, (b, idx) in enumerate(((0.5, 8 + (bar % 3)), (2.5, 10 + (bar % 2)))):
            s.append(n(bar, b, 1.2, pit(idx, sa), 0.46 + 0.04 * k))
    return s


def tabla():
    s = []
    names = ('tabla_ge', 'tabla_na', 'tabla_tin', 'shaker', 'daf')
    for bar in range(6, 12):                       # first light: sparse
        s += [n(bar, 0.0, 0.4, 'tabla_ge', 0.5), n(bar, 2.0, 0.3, 'tabla_na', 0.4), n(bar, 3.5, 0.3, 'tabla_tin', 0.36)]
    for bar in range(12, 19):                      # sunrise: 3+3+2
        v = 0.62 + 0.02 * (bar - 12)
        s += [n(bar, 0.0, 0.4, 'tabla_ge', v), n(bar, 1.5, 0.3, 'tabla_na', v - 0.12), n(bar, 3.0, 0.3, 'tabla_tin', v - 0.1), n(bar, 3.5, 0.3, 'tabla_na', v - 0.2)]
        s += [n(bar, k * 0.5, 0.2, 'shaker', 0.42 + 0.05 * (k % 2)) for k in range(8)]
    s.append(n(12, 0.0, 1.5, 'daf', 0.78))          # the sun clears the ridge
    for bar in range(19, 22):                       # morning: thinning
        s += [n(bar, 0.0, 0.4, 'tabla_ge', 0.4), n(bar, 2.0, 0.3, 'tabla_na', 0.3)]
    return s


def choir():
    """Sections enter by velocity (ensemble.layers): pp is the breathy high air alone, mf adds women and men, above 0.75 the tutti. The pitches
    are the strings' own chord an octave lower, so nothing beats against them (roughness)."""
    s = []
    for bars, idxs, sa in chords():
        for bar in bars:
            if bar < 8:
                continue
            if bar < 12:
                vel = {8: 0.30, 9: 0.34, 10: 0.38, 11: 0.42}[bar]
            elif bar < 19:
                vel = min(0.97, 0.56 + 0.06 * (bar - 12))
            else:
                vel = {19: 0.5, 20: 0.4, 21: 0.3, 22: 0.22}[bar]
            for i in idxs:
                s.append(n(bar, 0.0, 4.0, pit(i, sa + 12), vel))
    return s


# ------------------------------------------------------------------ score
def score(plan_times=None):
    tracks = [
        dict(name='ambience', instrument=f'env:{SLUG}', role='environment', notes=[dict(t=0.0, d=BARS * 4.0, p=60, v=1.0)]),
        dict(name='tanpura', instrument='ghats_tanpura', role='drone', notes=tanpura()),
        dict(name='bansuri', instrument='ghats_bansuri', role='melody', notes=flute()),
        dict(name='violins_counter', instrument='ghats_violins_counter', role='counter', notes=counter()),
        dict(name='pipes', instrument='ghats_pipes', role='counter', notes=pipes()),
        dict(name='violins_long', instrument='ghats_violins_long', role='chord', notes=strings_bed()),
        dict(name='violas', instrument='ghats_violas', role='ostinato', notes=violas()),
        dict(name='celli', instrument='ghats_celli', role='bass', notes=celli()),
        dict(name='sitar', instrument='ghats_sitar', role='arp', notes=sitar()),
        dict(name='santoor', instrument='ghats_santoor', role='texture', notes=santoor()),
        dict(name='tabla', instrument='ghats_tabla', role='drum', notes=tabla()),
        dict(name='choir', instrument='ghats_choir', role='pad', notes=choir()),
    ]
    sections = []
    for name, a, b, en, role, off in SECTIONS:
        sec = dict(name=name, role=role, energy=en, start_bar=a, end_bar=b)
        if plan_times:
            sec.update(plan_times[name])
        else:
            sec.update(start_s=round((a - 1) * BAR_S, 3), end_s=round(b * BAR_S, 3))
        sections.append(sec)
    sections[0]['pedal'] = True
    return {
        'title': TITLE, 'bpm': BPM, 'ts': [4, 4], 'seed': 2611, 'humanize': 'natural', 'key': 'D', 'mode': 'major',
        'rubato': 0.0, 'wander': 0.0, 'ritard': 0.0,
        'dynamics': [[0.0, 0.78], [20.0, 0.8], [44.0, 0.86], [64.0, 0.97], [72.0, 1.0], [76.0, 0.92], [84.0, 0.8], [88.0, 0.76]],
        'space': f'{SLUG}_room', 'mix_preset': f'{SLUG}_mix', 'output_targets': ['stereo', 'immersive_7_1'],
        'master': {'lufs': -16.0, 'true_peak': -1.5, 'tone': 'neutral', 'fade_out': 0.8},
        'piece_type': SLUG, 'focus': 'melody',
        'intent': {'emotions': ['hopeful', 'wonder'], 'registers': ['natural', 'cinematic'], 'scenes': ['establish', 'arrival'],
                   'tensions': ['rising_line'], 'avoid': ['four_on_the_floor']},
        'mix_intent': {'hero': 'bansuri', 'leave_free_hz': [500.0, 3000.0]},
        'foreground': ['bansuri', 'violins_counter'],
        'medium': {'model': 'iso9613', 'state': {'temperature_k': 289.15, 'pressure_pa': 89900, 'rh_percent': 92}},
        'plan': {'sections': sections},
        'tracks': tracks,
    }


def direction():
    with open(os.path.join(SKILL, 'templates', 'direction_sheet.json'), encoding='utf-8') as fh:
        d = json.load(fh)
    d.update(
        title=TITLE, project='Western Ghats Sunrise (a 60 s cue, fusion of Carnatic and orchestral writing)', version=1, medium='audio',
        brief='A 60 second A.R. Rahman style cultural mix with his signature; the ambience of a sunrise in the Western Ghats.',
        audience='a listener on headphones or speakers, a travel-film or album-opener context; they know the sound of Indian film fusion',
        purpose='a one-minute fusion cue: a bansuri line in the Mohanam pentatonic over a lush string bed, tanpura, tabla and a layered choir, set in a living Western Ghats dawn, rising to the sun clearing the ridge and landing softly',
        point_of_view='an observer on the ridge: the world wakes around the music, and the music gives it a voice',
        job=['open on the bansuri alone in the mist', 'turn the harmony up a whole tone when the sun clears the ridge and bring it home to the tonic', 'let the ambience open out as the light rises', 'end with Sa alone and the birds'],
        story='Mist, then first light, then the sun on the ridge, then a calm morning: one breath that crests at 36 s.',
        duration_s=60.0, in_point_s=0.0, out_point_s=60.0, ending='tail_out',
        feel=['hopeful', 'warm', 'luminous', 'rooted'], avoid_feel=['synthetic', 'robotic', 'aggressive', 'new-age cliche', 'busy'],
        sections=[
            dict(name='mist', start_s=0.0, end_s=13.6, energy=0.12, action='mist over the valley, a stream below, the first bird', role='place',
                 music='bansuri alone over the tanpura; the first strings arrive as a bare fifth at the end; no pulse'),
            dict(name='first_light', start_s=13.6, end_s=30.0, energy=0.38, action='the light finds the ridge', role='establish',
                 music='the hook on the bansuri, answered by the violins a third below; light tabla; veena plucks; the pipes\' drone swells in under the tanpura at 25 s; pp choir enters at the end'),
            dict(name='sunrise', start_s=30.0, end_s=49.1, energy=0.85, action='the sun clears the ridge', role='peak',
                 music='a whole-tone key raise; the hook an octave up with a distant Highland piper doubling it an octave below; violas in 3+3+2; tabla and daf; the pipes answer alone in the flute\'s rests at 41 s; the choir builds from pp to ff'),
            dict(name='morning', start_s=49.1, end_s=60.0, energy=0.35, action='full daylight, birds everywhere', role='release',
                 music='back in the home key: the hook once, softly, then Sa alone; the choir returns to pp; the birds remain')],
        motifs=[dict(name='the hook', first_at_s=13.6, shape='D E F# then a leap of a fifth to A and a step back (Sa Re Ga, leap to Pa), then an answer E D E D', returns='a third below on the violins at 19 s, an octave higher at 27 s and in the new key at 30 s doubled an octave below by a Highland piper on the far ridge, a dotted answer on the pipes alone at 41 s, once softly in D at 49 s, then Sa alone at 55 s')],
        instruments=['bansuri', 'strings', 'celli', 'sitar', 'santoor', 'tanpura', 'tabla', 'choir', 'bagpipes', 'environment'],
        avoid_sounds=['synth pad', 'drum kit', 'electric guitar', 'reverb wash'],
        pulse='none for 14 s, then a light tabla, then a 3+3+2 eighth-note pulse from 30 s', tempo_bpm=[88, 88], key='D', mode='major',
        energy=0.5, space=f'{SLUG}_room',
        hits_at=[30.0], hits=[dict(t=30.0, kind='musical', sync='soft', sound='a low daf stroke and the first chord of the new key as the sun clears the ridge', why='the harmonic turn of the piece; the strings keep sounding, so it is a musical hit, not a cut')],
        mix_intent=dict(hero='bansuri', support=['violins_counter', 'violins_long', 'celli'], sits_under=[], must_hear=['the bansuri in the first 2 s', 'the choir growing from 30 s', 'the thrush and the stream from the start'], leave_free_hz=[500.0, 3000.0]),
        loudness_lufs=-16.0, true_peak_max=-1.5,
        delivery=dict(format='wav', sample_rate=44100, bit_depth=24, stage='streaming', output_targets=['stereo', 'immersive_7_1'], played_on='headphones and speakers (stereo), and an 8-channel 7.1 bed (a fifth-order ambisonic mix decoded once)'),
        references=['in words, not a track: a solo bansuri over strings and a drone, the layered warmth of an Indian film fusion cue, with a living forest under it'],
        spatial_staging={k: dict(azimuth=float(v[0]), elevation=float(v[1]), distance=float(v[2]), space=f'{SLUG}_room') for k, v in STAGE.items()},
        immersive=dict(enabled=True, why='the valley is a field: the birds sit high and far around the listener, the stream is below left, the piper stands far behind on the ridge, and the bansuri is the one part that moves',
                       engine='hoa_bus', anchors=['tanpura', 'celli', 'tabla', 'pipes', 'ambience'],
                       movers=[dict(part='bansuri', why='it walks into the valley', path='enters 30 degrees left in the mist, crosses the centre as the sun clears the ridge, settles 22 degrees right for the last breath')],
                       height=dict(violins_long=22, choir=24, santoor=30), room_changes=[], must_hear=['the bansuri crossing the centre at 30 s', 'the piper far behind at 25 s and 41 s'],
                       deliverables=['stereo', 'immersive_7_1'], notes='Heights, trajectory keyframes and the room live in the presets; this block records the intent.'),
        focus='melody',
        intent=dict(emotions=['hopeful', 'wonder'], registers=['natural', 'cinematic'], scenes=['establish', 'arrival'], tensions=['rising_line'], avoid=['four_on_the_floor']),
        piece_type=SLUG,
        gate_reason='A melody-led acoustic piece: the melodic rows judge it unchanged; nothing is relaxed in advance.',
        video=dict(d['video'], enabled=False),
        notes='Mohanam pentatonic over raga-safe chords; Rahman overlay: lush strings, a violin answer, a layered choir, layered production.')
    d['expression'] = dict(
        sonic_picture='The first ten seconds are a bansuri alone in a wide-open valley over a soft tanpura, a stream and one bird; by the middle the strings sing the hook back to it and a light tabla enters; the last note is Sa alone with the morning birds.',
        performer='The flute breathes in the phrase gaps and the long notes start pure and warm up; the strings lean on beat one and ease the bow off before each change; the violins answer in the flute\'s rests; the choir is people in sections who join as the sound grows.',
        producer_moves='The key rises a whole tone as the sun clears the ridge and comes home; the tutti choir enters only above forte; the ambience opens out over the second half; the mix carries section loudness from the plan.',
        anti_generic='The generic version is a pad, a flute loop and a drum loop on a fixed key; what stops it is a theme with a leap on the weak beat, a harmonic turn and return, and a choir that changes make-up with its dynamic.',
        cues=[dict(section='mist', arousal='low', mode_register='major pentatonic, mid-high flute', tempo_trend='free-feeling, no pulse', dynamics='pp rising to mp', articulation='legato with slides', timbre='breathy, soft attack'),
              dict(section='first_light', arousal='low-medium', mode_register='same, strings below', tempo_trend='steady 88', dynamics='mp rising to mf', articulation='legato, plucked answers', timbre='warm'),
              dict(section='sunrise', arousal='high', mode_register='up a whole tone, octave up', tempo_trend='steady, 3+3+2 pulse', dynamics='f to ff', articulation='driving eighths, held choir', timbre='bright, open vowels'),
              dict(section='morning', arousal='low', mode_register='home key, mid', tempo_trend='settling', dynamics='mp falling to pp', articulation='long tails', timbre='warm, thin')],
        theme=dict(contour='arch: a step-wise rise, a leap of a fifth, and a step back', interval_character='steps with one leap of a fifth (Sa to Pa)', rhythm_cell='long, short, short, long-short',
                   why_memorable='the leap lands on the long note and returns by steps; the answer repeats the first notes',
                   variation_plan='a third below on the violins, an octave up with a faster run in the new key, once softly in the home key, alone on Sa at the end'))
    d['harmony_plan'] = [dict(section='mist', root='D', pedal=True, why='the dawn holds one note: Sa and Pa on the tanpura'),
                         dict(section='first_light', move='the bass moves D, Bm, D, Asus2 under the hook', counter_hook='violins answer a third below in the flute rests'),
                         dict(section='sunrise', key='raise a whole tone to E', move='E(add9), C#m, E(add9), Bsus2 over the same pulse', counter_hook='violins carry the hook in thirds above the flute\'s run'),
                         dict(section='morning', key='return to D', move='D(add9) then Asus2, ending on Sa', counter_hook='the flute alone, the strings thin out')]
    return d


def main():
    for i in INSTRUMENTS:
        write(os.path.join(P, 'presets', 'instruments', i['name'] + '.json'), i)
    write(os.path.join(P, 'presets', 'instruments', 'ghats_tabla.json'), TABLA)
    write(os.path.join(P, 'presets', 'vocals', 'ghats_choir.json'), vocal_choir())
    write(os.path.join(P, 'presets', 'environments', SLUG + '.json'), environment())
    for cname, cdoc in calls().items():
        write(os.path.join(P, 'presets', 'calls', cname + '.json'), cdoc)
    for fn in (space, mix, gate):
        path, doc = fn()
        write(path, doc)
    for stale in ('lead_flute.json', 'warm_piano.json', 'acoustic_bass.json'):
        pth = os.path.join(P, 'presets', 'instruments', stale)
        if os.path.exists(pth):
            os.remove(pth)
    for stale in (os.path.join(P, 'presets', 'vocals', 'vocal_hum.json'), os.path.join(P, 'presets', 'environments', 'forest_canopy_3d.json'),
                  os.path.join(P, 'direction', 'direction_sheet.json')):
        if os.path.exists(stale):
            os.remove(stale)
    write(os.path.join(P, 'direction', f'direction_{SLUG}.json'), direction())
    plan_times = None
    pt = os.path.join(P, 'reports', 'plan_times.json')
    if os.path.exists(pt):
        with open(pt, encoding='utf-8') as fh:
            plan_times = json.load(fh)
    write(os.path.join(P, 'scores', f'{SLUG}_score.json'), score(plan_times))
    if os.path.exists(os.path.join(P, 'scores', 'main_score.json')):
        os.remove(os.path.join(P, 'scores', 'main_score.json'))
    print('written: 10 instrument presets, choir, environment, space, mix, gate, direction sheet, score')


if __name__ == '__main__':
    main()
