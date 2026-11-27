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

# ------------------------------------------------------------------ time: 104 BPM, 26 bars = 60 s
# 104 sits inside the Highland reel's dance range (102-116) and under the KB's 106 BPM ceiling for tabla and microtonal bends (genre-fusion section 7)
BPM = 104.0
BAR_S = 4 * 60.0 / BPM
BARS = 26
SECTIONS = [  # name, first bar, last bar, energy, role, key offset (semitones above Sa=D)
    ('mist', 1, 2, 0.3, 'place', 0),
    ('groove', 3, 9, 0.55, 'establish', 0),
    ('sunrise', 10, 13, 0.8, 'peak', 0),
    ('piper', 14, 17, 0.75, 'transition', 0),
    ('crest', 18, 21, 1.0, 'peak', 2),
    ('morning', 22, 26, 0.4, 'button', 0)]
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
STAGE = dict(bansuri=(0, 6, 1.5), sitar=(-55, 0, 1.9), violins_counter=(70, 14, 2.4), violas=(-80, 0, 2.6), celli=(100, 0, 2.8),
             violins_long=(150, 22, 4.0), tanpura=(-108, -2, 2.6), santoor=(118, 30, 2.8), tabla=(-150, 0, 2.4), pipes=(172, 5, 7.5),
             pipes_drone=(180, 22, 7.5), kit=(40, 0, 2.6), bass=(-125, 0, 2.2), guitar_drive=(130, 4, 2.4), guitar_clean=(-60, 18, 2.4))
# the sections sit on the sides and behind (measured: imm.surround_ratio read -9.9 and then -10.1 dB against a -9.0 window with the strings at +-56 deg)


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
    inst('bass', 'finger_bass', 'bass', 'plucked',
         'The only bass: a finger-style electric bass locking with the kick on the 3+3+2 accents, root and fifth, round and a little dark; the celli do not play bass.',
         -5.0, 0.05, [HP(38), PK(250, -1.0, 0.9), LP(3500)],
         hum=dict(preset='tight', timing_ms=3.0), extra=dict(snap=None, onset_fade_ms=3.0)),
    inst('guitar_drive', 'overdrive_guitar', 'chord', 'plucked',
         'The rock engine: a palm-muted overdriven guitar chugging eighth notes on root-and-fifth power chords in the 3+3+2 pattern, tight and dry, the Western half of the groove.',
         -6.0, 0.12, [HP(90), PK(400, -2.0, 0.9), PK(2500, 1.0, 1.0), LP(6500)],
         hum=dict(preset='tight', timing_ms=3.0, lead_ms=4.0),
         extra=dict(snap=None, onset_fade_ms=3.0)),
    inst('guitar_clean', 'clean_guitar', 'arp', 'plucked',
         'A clean electric guitar playing a dotted arpeggio over the chords, the rhythmic shimmer Indian film fusion puts under a flute: bright, a little echo, never loud.',
         -9.0, 0.28, [HP(160), PK(3200, 0.5, 1.0), LP(8000)],
         extra=dict(snap=None, onset_fade_ms=3.0)),
    inst('pipes', 'bagpipes', 'counter', 'blown_reed',
         'A Highland piper on the far ridge: the chanter plays fast eighth-note reels with a cut on the beats and a gracenote between repeated notes, steady in level with no swell and no vibrato (a pipe has no dynamics), heard across the valley.',
         -7.0, 0.34, [HP(220), PK(2800, -1.0, 1.0), LP(7000)],
         hum=dict(preset='tight', timing_ms=3.0, lead_ms=4.0),
         extra=dict(bloom=None, noise=None, vibrato=dict(depth_cents=0), expression='flat', onset_fade_ms=3.0)),
    inst('pipes_drone', 'bagpipes', 'drone', 'blown_reed',
         'The pipes\' drone: a low continuous note on the Pa of the key (A in D, B in E) that never stops while the piper plays, the same A the tanpura plucks.',
         -10.0, 0.34, [HP(60), LP(2200)],
         extra=dict(bloom=None, noise=None, vibrato=dict(depth_cents=0), expression='flat', onset_fade_ms=20.0)),
    inst('bansuri', 'flute', 'melody', 'blown_reed',
         'The lead: a bansuri (bamboo flute) breathing through the Mohanam phrase, pure at the start of each long note and warming as it holds, with a slide into the notes the gamaka asks for.',
         -2.0, 0.22, [HP(220), PK(2600, 1.4, 1.1), LP(11000)],
         hum=dict(preset='natural', timing_ms=6.0, drift_ms=7.0, vel_sigma=4.0, lead_ms=18.0, anticipate_ms=22.0, bar_breath_ms=70.0),
         extra=dict(vibrato=dict(depth_cents=10, rate_hz=5.2, delay_ms=420, model='ou'), expression='breath',
                    velocity_timbre=dict(points=vel_points(1400), zones=10, attack_ms=[[25, 40], [127, 8]]))),
    inst('sitar', 'veena', 'arp', 'plucked',
         'A plucked veena-sitar figure that answers the flute in running eighths, soft in the first light and brighter at the sunrise.',
         -6.0, 0.16, [HP(180), PK(3500, -4.0, 2.0), LP(8000)],
         extra=dict(snap=None, velocity_timbre=dict(points=vel_points(900, soft=(0.3, 0.6), loud=(3.5, 7.0)), zones=8))),
    inst('violins_counter', 'violin', 'counter', 'bowed',
         "Rahman's string answer: a violin section playing the hook a third below the flute in the flute's rests, bowed and singing, with the vibrato growing on the held notes.",
         -3.5, 0.2, [HP(200), PK(3500, -2.0, 1.0), LP(7000)],
         hum=dict(preset='natural', timing_ms=9.0, drift_ms=8.0, vel_sigma=6.0, anticipate_ms=18.0),
         extra=dict(ensemble=dict(players=4, spread_cents=9, spread_ms=11, vel_spread=5), vibrato=dict(depth_cents=18, rate_hz=5.6, delay_ms=350, model='ou'),
                    velocity_timbre=dict(points=vel_points(2200), zones=10, attack_ms=[[25, 30], [127, 6]]))),
    inst('violas', 'viola', 'ostinato', 'bowed',
         'The pulse of the sunrise: violas bowing the 3+3+2 eighth-note figure, short and a little ahead of the beat, swelling with the section.',
         -5.0, 0.12, [HP(150), PK(300, -2.0, 0.9), PK(2400, 1.0, 1.0), LP(7000)],
         hum=dict(preset='natural', timing_ms=8.0, drift_ms=8.0, vel_sigma=6.0, anticipate_ms=14.0),
         extra=dict(ensemble=dict(players=4, spread_cents=6, spread_ms=7, vel_spread=4), mono_below=700.0,
                    velocity_timbre=dict(points=vel_points(900), zones=12, attack_ms=[[25, 22], [127, 5]]))),
    inst('celli', 'cello', 'chord', 'bowed',
         'The warm middle: celli sustaining a chord tone of the raga-safe chords with a slow bow, opening up at the sunrise (the bass guitar is the one bass).',
         -4.0, 0.14, [HP(60), PK(300, -2.5, 0.9), LP(5000)],
         extra=dict(ensemble=dict(players=3, spread_cents=7, spread_ms=9, vel_spread=4), vibrato=dict(depth_cents=14, rate_hz=5.0, delay_ms=500, model='ou'),
                    velocity_timbre=dict(points=vel_points(1200), zones=10, attack_ms=[[25, 26], [127, 5]]))),
    inst('violins_long', 'strings', 'chord', 'bowed',
         'The lush bed: a violin and viola section sustaining the add9, sus2 and minor chords built from the five raga notes, with a slow swell into each chord.',
         -7.0, 0.3, [HP(180), PK(350, -2.0, 0.9), LP(7000)],
         extra=dict(ensemble=dict(players=6, spread_cents=10, spread_ms=14, vel_spread=5),
                    velocity_timbre=dict(points=vel_points(2200), zones=8))),   # no onset ramp: a ramp on a held bed opened a 50 ms hole (stem.dropout, measured)
    inst('tanpura', 'sitar', 'drone', 'plucked',
         'The tanpura drone: the four-string cycle Pa, Sa, Sa, low Sa, plucked softly and left to ring under everything, the anchor of the one key centre.',
         -11.0, 0.3, [HP(70), PK(300, -2.0, 0.9), LP(4000)],
         extra=dict(snap=None, onset_fade_ms=3.0, humanize=dict(preset='natural', timing_ms=10.0, drift_ms=12.0, vel_sigma=4.0))),
    inst('santoor', 'santoor', 'texture', 'struck_pitched',
         'Dew on the leaves: sparse high santoor notes from the five-note scale, soft and bright, scattered over the first light and the morning.',
         -12.0, 0.34, [HP(400), PK(4200, 1.0, 1.0)], extra=dict(snap=None)),
]

for _i in INSTRUMENTS:
    if _i['name'] == 'ghats_bansuri':       # the one mover: it enters left in the mist, crosses the centre as the sun clears the ridge, settles right for the last breath
        _i['spatial']['trajectory'] = dict(spatial_role='mover', doppler_strength=0.0, keyframes=[
            dict(t_s=0.0, azimuth=-30.0, distance=1.7, elevation=6.0), dict(t_s=4.6, azimuth=-18.0, distance=1.6, elevation=8.0),
            dict(t_s=20.8, azimuth=0.0, distance=1.5, elevation=12.0), dict(t_s=46.2, azimuth=14.0, distance=1.6, elevation=8.0),
            dict(t_s=60.0, azimuth=22.0, distance=1.8, elevation=6.0)])

KIT = dict(name='ghats_kit', description='Rock drum kit', instrument='power', role='drum', family='struck_membrane',
           character='A Western rock kit playing the groove owner\'s part: kick on the 3+3+2 accents, snare on two and four, eighth-note hats, a crash at each turn and tom fills; the tabla keeps only the accents between its strokes.',
           humanize=dict(preset='tight', timing_ms=3.0, drum_ms=2.5), gain_db=-5.0, reverb=0.16, onset_fade_ms=2.0, snap=None,
           spatial=dict(azimuth=40, elevation=0, distance=2.6, space=f'{SLUG}_room', binaural=True, kind='spot'),
           eq=[HP(45), PK(300, -2.0, 0.9), PK(4000, 0.0, 1.0), LP(9000)], sources=list(SRC) + ['references/scoring/genre-fusion.md (one kit, one bass: the other tradition\'s percussion is a fill or an accent); the pattern is an ESTIMATE'])

TABLA = dict(name='ghats_tabla', description='Tabla and daf', instrument='standard', role='drum', family='struck_membrane',
             character='Tabla strokes (ge, na, tin) with a shaker underneath in the 3+3+2 pattern, and one low daf stroke where the sun clears the ridge: light hands, never a kit.',
             humanize=dict(preset='tight', timing_ms=4.0, drum_ms=3.0), gain_db=-7.0, reverb=0.14, onset_fade_ms=2.0, snap=None,
             spatial=dict(azimuth=-150, elevation=0, distance=2.4, space=f'{SLUG}_room', binaural=True, kind='spot'),
             eq=[HP(70), PK(250, -2.0, 0.9), PK(3800, 0.5, 1.0), LP(8500)], sources=list(SRC))


def vocal_choir():
    with open(os.path.join(SKILL, 'references', 'data', 'presets', 'vocals', 'vocal_choir_cinematic.json'), encoding='utf-8') as fh:
        d = json.load(fh)
    d.update(name='ghats_choir', character='A choir of sections that opens with the sun: a breathy high oo at pp, women and men in octaves on the long vowels, and an aa tutti with the singer\'s formant at the crest; the same voices never sing at every dynamic.',
             category='choir_layered', role='pad', gain_db=-6.5, reverb=0.4, sources=list(SRC) + ['scripts/vocal_engine/layers.py; references/data/presets/vocals/vocal_choir_cinematic.json'],
             spatial=dict(azimuth=-140, elevation=24, distance=4.5, space=f'{SLUG}_room', binaural=True, kind='spot'),
             vowel='u', expression='hopeful')
    d['ensemble']['voices'] = 12
    d['peak_trim'] = 0.85
    d['ensemble']['layers'][-1]['overrides']['technique']['singer_formant'] = 0.5     # measured clicks near the tutti: a gentler singer's formant                  # the sum of five sections clipped (275 samples at full scale, measured): cap it before the soft limit
    for L in d['ensemble']['layers']:
        L['level_db'] = round(L.get('level_db', 0.0) - 2.0, 2)
        # the choir stem alone measured 0.070 on cochlear_roughness (limit 0.070): 25 singers beat against each other; a tighter, smaller section beats less
        L['cohesion'] = 0.78
        L['voices'] = max(3, round(L['voices'] * 0.7))
        L.setdefault('overrides', {}).setdefault('ensemble', {}).update(pitch_spread_cents=4.0, pitch_drift_cents=3.0)
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
    e['controls'] = {'light': {'curve': [[0, 0.04], [8, 0.1], [20, 0.35], [30, 0.85], [48, 1.0], [60, 0.9]]},
                     'wind_u': {'curve': [[0, 1.6], [18, 1.8], [30, 2.7], [60, 3.0]]},
                     'stream_rate': {'curve': [[0, 10], [18, 14], [30, 55], [60, 80]]},
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
    stream['population']['rate_mm_h'] = {'control': 'stream_rate'}      # quiet in the first 20 s (the user heard too much ambience there), at full level after the sun                # ESTIMATE: a brook at 16 m is the steady bed under the birds (measured against the 1 s level steps of the render)
    stream['surface']['area_m2'] = 6.0
    stream['gain_db'] = 20.0                                  # the brook is steady but 24 dB under the wind at these rates (measured), so it is lifted here
    drip['gain_db'] = 0.0
    wind = gens['canopy_wind']
    wind['flow']['u_m_s'] = {'control': 'wind_u'}
    wind['flow']['intensity'] = 0.08                        # measured: intensity 0.35 gusted 33 dB over 30 s, 0.08 moves 6 dB (ambient_bed pumping)
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
        bird('malabar_whistling_thrush', 'ghats_whistling_thrush', 1.5e-05, 3.0, 14.0, (1300, 3000), (25.0, 20.0, 14.0), 4.5,
             sources=['https://en.wikipedia.org/wiki/Malabar_whistling_thrush (a human-like whistle; longer, melodious phrases in the morning, short sharp whistles later)']),
        bird('malabar_grey_hornbill', 'ghats_hornbill', 4.0e-05, 2.0, 22.0, (700, 2600), (-100.0, 30.0, 40.0), 12.0, individuals=2, salience='bed',
             sources=['https://iucnhornbills.org/malabar-grey-hornbill/ (an assortment of loud, harsh chuckles and squawks with raucous cackling like mock laughter)',
                      'https://app.birdweather.com/species/malabar-gray-hornbill (loud cackling and laughing call; endemic to the Western Ghats)']),
        bird('malabar_barbet', 'ghats_barbet', 1.0e-05, 1.5, 34.0, (800, 1400), (110.0, 38.0, 30.0), 6.0, individuals=1, salience='bed',
             sources=['https://macaulaylibrary.org/asset/646733603 (Kerala recording: a sharp single-note call like a coppersmith barbet, repeated)',
                      'https://en.wikipedia.org/wiki/Malabar_barbet (similar to the coppersmith barbet, a more rapid call)']),
        bird('racket_tailed_drongo', 'ghats_drongo', 1.2e-05, 4.0, 18.0, (4000, 7500), (62.0, 34.0, 17.0), 3.5,
             sources=['https://en.wikipedia.org/wiki/Greater_racket-tailed_drongo (a wide range of loud calls including near-perfect imitations of other birds)',
                      'https://pmc.ncbi.nlm.nih.gov/articles/PMC3945749/ (mimicked notes sit in its repertoire)']),
        bird('flame_throated_bulbul', 'ghats_bulbul', 1.0e-05, 6.0, 28.0, (4500, 8000), (-48.0, 26.0, 11.0), 3.0, individuals=3,
             sources=['https://sanctuarynaturefoundation.org/public/article/shhh-can-you-hear-me%3F (an endemic dawn voice of the Valparai rainforest)'])]
    e['fauna'] = [frogs] + birds
    e['ecology'] = {'density_budget': {'events_per_s_max': 1.2}, 'niches': {'auto': True, 'min_separation': 'D<=0.4'}, 'rules': [],
                    'score': {'occupancy': 'from_score', 'protect_roles': ['melody', 'lead', 'vocal'], 'margin_db': 3, 'pocket_threshold': 0.7}}
    e['spatial_coupling'] = {'field': {'kind': 'diffuse', 'emitters': 12, 'order': 5, 'correlation_target': 0.2}, 'room': {'space': f'{SLUG}_room'}, 'decode_hint': ['stereo', 'immersive_7_1']}
    e['reference'] = {'full_scale_pa': 0.1}                  # ESTIMATE: calibrates the physical levels to a stem that sits near -40 dBFS rms (the shipped 2.0 renders at -65)
    e['sources'] = ['malabar_whistling_thrush', 'malabar_grey_hornbill', 'malabar_barbet', 'racket_tailed_drongo', 'flame_throated_bulbul', 'tree_frogs']      # the sound slugs of research/research_*.md (Real-world references); the other layers carry ESTIMATE in their own blocks
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
            elements=dict(tink=el([[0, 5200], [0.3, 4800], [1, 4300]], [110, 160], harmonics=6, rolloff=1.4, attack=0.03, release=0.4),
                          whistle=el([[0, 4200], [0.5, 4900], [1, 4300]], [260, 380], harmonics=2, rolloff=2.0, vibrato_hz=7.0, vibrato_cents=40),
                          creak=el([[0, 4100], [1, 3900]], [180, 260], harmonics=6, rolloff=1.2, noise=0.5, pulse_hz=60, pulse_duty=0.5),
                          mimic=el([[0, 6200], [0.5, 4300], [1, 5800]], [200, 320], harmonics=4, rolloff=1.8, jump=[0.5, 0.8])),
            sequence=['tink', 'whistle', ['creak', 1, 2], 'tink', 'mimic', 'whistle'], gap_ms=[80, 240], sources=est),
        'ghats_bulbul': dict(
            name='ghats_bulbul', character='A bright tinkling call of two or three notes, up, down and a falling last note (birdweather: a tinkling sound of two or three notes).',
            elements=dict(p1=el([[0, 5200], [1, 5400]], [80, 110], harmonics=2, rolloff=2.0), p2=el([[0, 5600], [1, 5000]], [90, 120], harmonics=2, rolloff=2.0),
                          p3=el([[0, 5900], [0.5, 5000], [1, 4500]], [140, 200], harmonics=2, rolloff=2.0, attack=0.1)),
            sequence=['p1', 'p2', ['p3', 0, 1]], gap_ms=[50, 90], sources=est)}


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
    m['level_by_role'] = {'environment': -8.0, 'texture': -2.0}      # +3 dB on the diffuse ambience field: imm.surround_ratio measured -9.9 dB against the -9.0 limit (more surround energy needed)
    m['render'] = {'mix_workers': 2}
    # debug_audio.py attributed all six `clicks` events to the tabla (hf. above 6 kHz, 95-99 % of each step) and priced a -9 dB high shelf at the row's 6 kHz corner as clearing 6 -> 0
    m['inst_eq'] = {'ghats_tabla': [{'type': 'highshelf', 'f': 6000, 'gain': -15.0, 'q': 0.7}]}
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
# The riff: syncopated, a leap of a fifth on the off-beat (D . E . F# A F# A | B A F# E F# D). Every note of the bansuri stays in octaves 4-5 (genre-fusion section 7 rule 3).
H1 = [(0.0, 0.75, 0), (0.75, 0.75, 1), (1.5, 0.5, 2), (2.0, 1.0, 3), (3.0, 0.5, 2), (3.5, 0.5, 3)]
H2 = [(0.0, 0.75, 4), (0.75, 0.25, 3), (1.0, 1.0, 2), (2.0, 0.5, 1), (2.5, 0.5, 2), (3.0, 0.7, 0)]


def hook(bar, idx_shift, vel, sa):
    out = [n(bar, b, d, pit(i + idx_shift, sa), vel) for b, d, i in H1]
    out += [n(bar + 1, b, d, pit(i + idx_shift, sa), vel * 0.94) for b, d, i in H2]
    return out


def breaths(notes, max_run=14.0, gap=0.45):
    """A wind player needs air: shorten the note that ends a run longer than `max_run` beats so a gap of `gap` beats opens."""
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
    S0 = SA + 12                                   # the bansuri sings from D5 and never above B5 (83)
    s = []
    # mist (bars 1-2): a breath and a slide into the fifth, the riff's first bar as a pickup at the end of bar 2
    s += [n(1, 0, 3.4, pit(0, S0), 0.5, gl=-180), n(1, 3.5, 0.5, pit(1, S0), 0.5), n(2, 0, 1.5, pit(2, S0), 0.55), n(2, 1.5, 0.5, pit(3, S0), 0.56), n(2, 2, 1.5, pit(2, S0), 0.52)]
    s += [n(2, 3.5, 0.5, pit(1, S0), 0.56)]
    # groove (bars 3-9): the riff, again and again; bars 7-8 louder with the leap leaning in; bar 9 a rising pickup into the sun
    s += hook(3, 0, 0.62, S0) + hook(5, 0, 0.66, S0) + hook(7, 0, 0.74, S0)
    s += [n(9, 0, 1.5, pit(3, S0), 0.7, gl=-120), n(9, 2.0, 0.25, pit(1, S0), 0.72), n(9, 2.25, 0.25, pit(2, S0), 0.74), n(9, 2.5, 0.25, pit(3, S0), 0.78), n(9, 2.75, 0.25, pit(4, S0), 0.8), n(9, 3.0, 0.5, pit(3, S0), 0.8), n(9, 3.5, 0.5, pit(4, S0), 0.82)]
    # sunrise (bars 10-13): the riff in full light, then a second time with a ghost-note run at the end, handing over at bar 14
    s += hook(10, 0, 0.84, S0) + hook(12, 0, 0.88, S0)
    # crest (bars 18-21) in E: the riff a degree lower (keeps the top at B5), then a long note on the fifth
    sa = S0 + 2
    s += hook(18, -1, 0.92, sa) + hook(20, -1, 0.95, sa)
    # morning (bars 22-26): back in D: the riff once, softly, the first bar echoed, then Sa alone
    s += hook(22, 0, 0.55, S0) + [n(24, b, d, pit(i, S0), 0.45) for b, d, i in H1[:3]] + [n(25, 0, 3.6, pit(0, S0), 0.4, gl=-100), n(26, 0, 3.6, pit(0, S0), 0.3)]
    return breaths(s)


# ------------------------------------------------------------------ the pipes: a Highland piper plays FAST (eighth notes, a reel), never a held note: a
# gracenote on every beat, a birl on low A at the end of the strain, and a continuous drone under it. A mixolydian on A = the D major notes.
HI_G, LO_G = 79, 67                                     # the chanter's high G and low G (G5, G4)


def ornament(notes, cut=0.0625):
    """A gracenote ON each beat (the tutor): the gracenote takes the beat and the melody note follows it by `cut`; a repeated note is separated by one too.
    The gracenote is the high G (a D when the note itself is a G or an A: the tutor's G, D and E set). ESTIMATE timing (the sources give none)."""
    out = []
    for x in sorted((dict(y) for y in notes), key=lambda y: y['t']):
        on_beat = abs(x['t'] - round(x['t'])) < 1e-6
        prev = out[-1] if out else None
        repeat = prev is not None and prev['p'] == x['p'] and abs(prev['t'] + prev['d'] - x['t']) < 0.01
        if (on_beat or repeat) and x['d'] > cut * 3:
            gn = 74 if x['p'] >= HI_G else HI_G
            if prev is not None and prev['t'] + prev['d'] > x['t']:
                prev['d'] = round(x['t'] - prev['t'], 4)
            out.append(dict(t=x['t'], d=cut, p=gn, v=round(x['v'], 3)))
            x = dict(x, t=round(x['t'] + cut, 4), d=round(x['d'] - cut, 4))
        out.append(x)
    return out


def birl(bar, b, vel, hold=1.0):
    """The birl on low A: A, low G, A, low G, A (five very quick notes), then the note held."""
    t0 = beat(bar, b)
    out = []
    for k, p in enumerate((69, LO_G, 69, LO_G)):
        out.append(dict(t=round(t0 + 0.0625 * k, 4), d=0.0625, p=p, v=round(vel, 3)))
    out.append(dict(t=round(t0 + 0.25, 4), d=round(hold - 0.25, 4), p=69, v=round(vel, 3)))
    return out


def reel_strain(bar, vel):
    """One four-bar strain of a reel on the chanter (A4-A5): eight eighths to the bar, a gracenote on each beat, ending on a birl. An original tune on the A mixolydian."""
    A = [[81, 78, 76, 78, 81, 78, 76, 74], [76, 74, 71, 74, 76, 78, 76, 74], [81, 78, 76, 78, 81, 79, 78, 76], [74, 76, 78, 76, 74]]
    notes = []
    for bi, row in enumerate(A):
        for k, p in enumerate(row):
            notes.append(n(bar + bi, k * 0.5, 0.5, p, vel + (0.04 if k % 4 == 0 else 0.0)))
    notes = ornament(notes)
    return notes + birl(bar + 3, 2.5, vel, hold=1.5)


def pipes():
    s = reel_strain(14, 0.68)                                                   # the piper plays alone for four bars (bars 14-17)
    s += ornament([n(23, b, 0.5, p, 0.5) for b, p in ((0.0, 74), (0.5, 76), (1.0, 78), (1.5, 76), (2.0, 74), (2.5, 71), (3.0, 69))]) + birl(23, 3.5, 0.5, hold=0.5)   # a distant flourish in the morning
    return s


def pipes_drone():
    """The continuous drone on A (the bass drone A2): the pipes never stop sounding. It swells in under the end of the groove and goes with the reel."""
    s = []
    s += bar_notes(8, 17, 45, 0.46)          # the bass drone A2 only: the tenor A3 would sit a second under the strings' B in Bm7 (measured by preflight.roughness)
    return s


def counter():
    s = []
    sa = SA
    for bar in (5, 7):                                             # the violins sing the riff a third below the flute (the same rhythm: heterophony)
        s += [n(bar, b, d, pit(i - 2, sa), 0.5) for b, d, i in H1] + [n(bar + 1, b, d, pit(i - 2, sa), 0.48) for b, d, i in H2]
    for bar in (10, 12):
        s += [n(bar, b, d, pit(i - 2, sa), 0.72) for b, d, i in H1] + [n(bar + 1, b, d, pit(i - 2, sa), 0.7) for b, d, i in H2]
    for bar in (14, 16):                                           # over the reel: held thirds, never the reel's own notes, two to a bar
        s += [n(bar, 0.0, 1.9, pit(4, sa), 0.55), n(bar, 2.0, 1.9, pit(3, sa), 0.55), n(bar + 1, 0.0, 1.9, pit(4, sa), 0.57), n(bar + 1, 2.0, 1.9, pit(2, sa), 0.55)]
    sa = SA + 2
    for bar in (18, 20):                                           # the crest, a third below the flute in E
        s += [n(bar, b, d, pit(i - 2 + 5, sa), 0.78) for b, d, i in H1] + [n(bar + 1, b, d, pit(i - 2 + 5, sa), 0.76) for b, d, i in H2]
    return s


# chords from the five raga notes only (raga-safe voicings, KB indian-film-fusion 3.1): D F# A | B D F# A (Bm7: every chord under the pipes holds their A) | A E A
D_TRI, BM7, A_OPEN = [0, 2, 3], [-1, 0, 2, 3], [3, 6, 8]


def chords():
    out = []
    for bars, idxs, sa in (((3, 4), D_TRI, SA), ((5, 6), BM7, SA), ((7, 8), D_TRI, SA), ((9,), A_OPEN, SA),
                           ((10, 11), D_TRI, SA), ((12, 13), BM7, SA),
                           ((14,), D_TRI, SA), ((15,), BM7, SA), ((16,), D_TRI, SA), ((17,), A_OPEN, SA),
                           ((18,), D_TRI, SA + 2), ((19,), BM7, SA + 2), ((20,), D_TRI, SA + 2), ((21,), A_OPEN, SA + 2),
                           ((22, 23), D_TRI, SA), ((24,), A_OPEN, SA), ((25, 26), D_TRI, SA)):
        out.append((bars, idxs, sa))
    return out


def bar_notes(first, last, pitch, vel, tail_bar=BARS, voice=0):
    """A held tone as one note per bar, each overlapping the next by half a beat: a sampled sustain held for six seconds ends before the written note
    does (measured: stem.dropout at the chord changes), and a re-attack that overlaps never opens a hole. The restrikes inside a chord are offset by
    `voice` x 0.4 beat, so the voices of one section do not all attack on the bar line (stem.tick measured 0.62 against 0.35)."""
    cuts = [beat(first)] + [beat(bar) + 0.4 * voice for bar in range(first + 1, last + 1)] + [beat(last) + 4.0]
    out = []
    for i in range(len(cuts) - 1):
        last_piece = i == len(cuts) - 2
        end = cuts[i + 1] + (0.0 if last_piece and last >= tail_bar else 0.5)
        out.append(dict(t=round(cuts[i], 4), d=round(end - cuts[i], 4), p=int(pitch), v=round(vel, 3)))
    return out


def level(bar, soft, mid, loud):
    return soft if bar < 3 else (mid if bar < 10 else (loud if bar < 22 else soft))


def strings_bed():
    s = []
    for p, v in ((pit(0, SA), 0.5), (pit(3, SA), 0.48)):
        s += bar_notes(2, 2, p, v)                                                               # an open fifth under the end of the mist
    for bars, idxs, sa in chords():
        if bars[0] in (14, 15, 16, 17):
            v = 0.5                                                                              # under the reel the strings only hold
        else:
            v = level(bars[0], 0.46, 0.54, 0.84)
        for j, i in enumerate(idxs):
            s += bar_notes(bars[0], bars[-1], pit(i, sa), v - 0.04 * (i % 2), voice=j)
    return s


def violas():
    """The pulse: 3+3+2 eighths with a sixteenth pickup into the next bar."""
    s = []
    for bar in range(6, 22):
        sa = SA + 2 if bar >= 18 else SA
        root, fifth, nine = pit(0, sa - 12), pit(3, sa - 12), pit(1, sa - 12)
        if bar in (6, 12, 15, 19):
            root, fifth, nine = pit(-1, sa - 12), pit(2, sa - 12), pit(0, sa - 12)                  # the minor colour (Bm7)
            root, fifth, nine = [q + 12 if q < 48 else q for q in (root, fifth, nine)]               # inside the viola's range (C3 = 48)
        v0 = 0.5 if bar < 10 else (0.5 if 14 <= bar <= 17 else 0.66)
        for b, p, vv in ((0.0, root, v0 + 0.08), (1.5, nine, v0), (3.0, fifth, v0 - 0.04)):
            s.append(n(bar, b, 0.5, p, vv))
            s.append(n(bar, b + 0.5, 0.5, root if b != 0.0 else nine, vv - 0.1))
        s.append(n(bar, 3.5, 0.25, fifth, v0 - 0.1))
    return s


def celli():
    """Sustained mid-low chord tones (the fifth of each chord): the warm middle, not the bass."""
    s = bar_notes(2, 2, pit(0, SA - 12), 0.5)
    for bars, idxs, sa in chords():
        v = 0.5 if bars[0] in (14, 15, 16, 17) else level(bars[0], 0.5, 0.56, 0.8)
        tone = idxs[1] if idxs[1] < 5 else idxs[1] - 5                      # the second chord tone, an octave under the strings: never a second against them, never the bass's fifth
        s += bar_notes(bars[0], bars[-1], pit(tone, sa - 12), v)
    return s


def bass_guitar():
    """The one bass: root on the 3+3+2 accents, locked to the kick. Range E1-G3 (28-55)."""
    s = []
    roots = {}
    for bars, idxs, sa in chords():
        for bar in bars:
            roots[bar] = (idxs[0], sa)
    for bar in range(3, 27):
        r, sa = roots[bar]
        p = pit(r, sa - 24)
        if p < 28:
            p += 12
        v = 0.5 if bar < 10 else (0.6 if bar >= 22 else 0.72)
        if bar < 22:                                           # each note runs into the next onset (stem.dropout measured 60 ms holes between short plucks)
            s += [n(bar, 0.0, 1.6, p, v + 0.06), n(bar, 1.5, 1.1, p, v), n(bar, 2.5, 1.1, p + 7 if r == 0 else p, v - 0.06), n(bar, 3.5, 0.6, p, v - 0.08)]
        else:                                                  # the morning: two plucks a bar, the last one ends before the file does (stem.dropout and stem.edge, measured)
            s += [n(bar, 0.0, 2.6, p, v + 0.06), n(bar, 2.5, 1.2 if bar < 26 else 0.9, p, v - 0.04)]
    return s


def tanpura():
    """The tanpura holds the drone until the pipes' drone takes over (bar 8) and again after it (bars 18-26): the drone role is handed over, never doubled."""
    s = []
    for bar in list(range(1, 8)) + list(range(18, 27)):
        sa = sa_of(bar)
        for b, d, p, v in ((0.0, 1.4, pit(3, sa - 24), 0.34), (1.5, 0.95, pit(0, sa - 12), 0.32), (2.5, 1.4, pit(0, sa - 12), 0.3), (3.5, 2.2, pit(0, sa - 24), 0.3)):
            s.append(n(bar, b, d, p, v))
    return s


def sitar():
    """Plucked eighths with a different syncopated rhythm in each bar (a plucked part that repeats one bar reads as a tick: stem.tick measured 0.43 at one beat)."""
    rhythms = {3: (0.0, 1.5, 2.5), 4: (0.0, 1.0, 2.5, 3.5), 5: (0.5, 1.5, 3.0), 6: (0.0, 1.5, 2.0, 3.5), 22: (0.0, 1.5, 3.0), 23: (0.5, 2.0, 3.5)}
    s = []
    for bar, offs in rhythms.items():
        sa = SA
        for k, b in enumerate(offs):
            idx = (0, 2, 3, 2, 4, 3)[(bar + k) % 6]
            s.append(n(bar, b, 0.4, pit(idx + 5, sa), 0.4 + (0.06 if k == 0 else 0.0)))
    return s


def santoor():
    s = []
    for bar in [8, 9, 22, 23, 24]:
        sa = sa_of(bar)
        for k, (b, idx) in enumerate(((0.5, 8 + (bar % 3)), (2.5, 10 + (bar % 2)))):
            s.append(n(bar, b, 1.2, pit(idx, sa), 0.46 + 0.04 * k))
    return s


def tabla():
    """The kit owns the groove (one kit, KB genre-fusion): the tabla plays the Indian accents between its strokes and a fill at the turns."""
    s = []
    for bar in (2,):
        s += [n(bar, 0.0, 0.4, 'tabla_ge', 0.46), n(bar, 2.0, 0.3, 'tabla_na', 0.36), n(bar, 3.5, 0.3, 'tabla_tin', 0.34)]
    for bar in range(3, 22):
        v = 0.4 if bar < 10 else 0.5
        s += [n(bar, 1.5, 0.3, 'tabla_na', v - 0.06), n(bar, 3.5, 0.3, 'tabla_tin', v - 0.06)]
        if bar % 2:
            s += [n(bar, 2.0, 0.3, 'tabla_ge', v - 0.1)]
    s.append(n(10, 0.0, 1.5, 'daf', 0.7))          # the sun clears the ridge
    for bar in range(22, 26):
        s += [n(bar, 0.0, 0.4, 'tabla_ge', 0.4), n(bar, 2.0, 0.3, 'tabla_na', 0.3)]
    return s


def choir():
    """Sections enter by velocity (ensemble.layers): pp is the breathy high air alone, mf adds women and men, above 0.75 the tutti. Pitches are the strings' chord an octave higher."""
    s = []
    for bars, idxs, sa in chords():
        for bar in bars:
            if bar < 7:
                continue
            if bar < 10:
                vel = {7: 0.30, 8: 0.34, 9: 0.40}[bar]
            elif bar < 14:
                vel = 0.56 + 0.06 * (bar - 10)
            elif bar < 18:
                vel = 0.42                                         # under the reel: held, soft
            elif bar < 22:
                vel = 0.78 + 0.05 * (bar - 18)
            else:
                vel = {22: 0.46, 23: 0.4, 24: 0.32, 25: 0.24, 26: 0.16}[bar]
            for i in idxs:
                s.append(n(bar, 0.0, 4.0, pit(i, sa + 12), vel))
    return s


def kit():
    """A rock kit on the groove: kick on the 3+3+2 accents, snare on two and four, eighth hats; the reel (bars 14-17) takes it to kick, snare and hats."""
    s = []
    for bar in range(3, 26):
        groove = bar < 10
        morning = bar >= 22
        v = 0.62 if groove else (0.6 if morning else 0.64 + 0.008 * (bar - 10))       # intent.avoid sudden_loud: no two simultaneous notes more than 0.4 apart
        s += [n(bar, 0.0, 0.2, 'kick', v), n(bar, 2.5, 0.2, 'kick', v - 0.1)]
        if not groove and not morning:
            s += [n(bar, 1.5, 0.2, 'kick', v - 0.12)]
        if groove or morning:
            s += [n(bar, 1.0, 0.2, 'snare', v - 0.12), n(bar, 3.0, 0.2, 'snare', v - 0.12)]            # a quiet snare backbeat, not a rim click (the stem measured 11 dB under the sunrise)
        else:
            s += [n(bar, 1.0, 0.2, 'snare', v), n(bar, 3.0, 0.2, 'snare', v + 0.04)]
        s += [n(bar, k * 0.5, 0.15, 'hat_closed', 0.4 + 0.06 * (k % 2) + (0.04 if not groove else 0.0)) for k in range(8)]
    for bar in (3, 10, 18, 22):                                                  # a crash at each turn
        s.append(n(bar, 0.0, 1.5, 'crash', 0.62))
    for bar in (9, 13, 17, 21):                                                  # tom fills into the next section
        s += [n(bar, 3.0, 0.2, 'tom_high', 0.55), n(bar, 3.25, 0.2, 'tom_mid', 0.58), n(bar, 3.5, 0.2, 'tom_low', 0.62), n(bar, 3.75, 0.2, 'tom_low', 0.66)]
    return s


def guitar_drive():
    """Palm-muted power-chord chugs on the chord's root and fifth in the 3+3+2 accents: the sunrise (10-13) and the crest (18-21); the piper has the stage in 14-17."""
    s = []
    roots = {}
    for bars, idxs, sa in chords():
        r, f = {tuple(D_TRI): (0, 3), tuple(BM7): (-1, 2), tuple(A_OPEN): (3, 6)}[tuple(idxs)]
        for bar in bars:
            roots[bar] = (r, f, sa)
    for bar in list(range(10, 14)) + list(range(18, 22)):
        r, f, sa = roots[bar]
        lo, hi = pit(r, sa - 12), pit(f, sa - 12)
        if lo < 40:
            lo, hi = lo + 12, hi + 12
        for b, d, vv in ((0.0, 0.45, 0.72), (0.5, 0.2, 0.5), (1.0, 0.2, 0.5), (1.5, 0.45, 0.68), (2.0, 0.2, 0.5), (2.5, 0.2, 0.5), (3.0, 0.45, 0.7), (3.5, 0.2, 0.52)):
            s += [n(bar, b, d, lo, vv), n(bar, b, d, hi, vv - 0.04)]
    return s


def guitar_clean():
    """A dotted arpeggio on the chord tones: bars 7-13 and 18-24."""
    s = []
    for bars, idxs, sa in chords():
        for bar in bars:
            if not (7 <= bar <= 13 or 18 <= bar <= 24):
                continue
            tones = [pit(i, sa) for i in idxs]
            order = [0, 1, 2, 1, 2, 0]
            for k, (b, d) in enumerate(((0.0, 0.7), (0.75, 0.7), (1.5, 0.7), (2.25, 0.7), (3.0, 0.45), (3.5, 0.45))):
                s.append(n(bar, b, d, tones[order[k % len(order)] % len(tones)], 0.4 + (0.05 if k == 0 else 0.0)))
    return s


# ------------------------------------------------------------------ score
def score(plan_times=None):
    tracks = [
        dict(name='ambience', instrument=f'env:{SLUG}', role='environment', notes=[dict(t=0.0, d=BARS * 4.0, p=60, v=1.0)]),
        dict(name='tanpura', instrument='ghats_tanpura', role='drone', notes=tanpura()),
        dict(name='bansuri', instrument='ghats_bansuri', role='melody', notes=flute()),
        dict(name='violins_counter', instrument='ghats_violins_counter', role='counter', notes=counter()),
        dict(name='pipes', instrument='ghats_pipes', role='counter', notes=pipes()),
        dict(name='pipes_drone', instrument='ghats_pipes_drone', role='drone', notes=pipes_drone()),
        dict(name='violins_long', instrument='ghats_violins_long', role='chord', notes=strings_bed()),
        dict(name='violas', instrument='ghats_violas', role='ostinato', notes=violas()),
        dict(name='celli', instrument='ghats_celli', role='chord', notes=celli()),
        dict(name='bass', instrument='ghats_bass', role='bass', notes=bass_guitar()),
        dict(name='sitar', instrument='ghats_sitar', role='arp', notes=sitar()),
        dict(name='santoor', instrument='ghats_santoor', role='texture', notes=santoor()),
        dict(name='kit', instrument='ghats_kit', role='drum', notes=kit()),
        dict(name='tabla', instrument='ghats_tabla', role='drum', notes=tabla()),
        dict(name='guitar_drive', instrument='ghats_guitar_drive', role='chord', notes=guitar_drive()),
        dict(name='guitar_clean', instrument='ghats_guitar_clean', role='arp', notes=guitar_clean()),
        dict(name='choir', instrument='ghats_choir', role='pad', notes=choir()),
    ]
    sections = []
    for name, a, b, en, role, off in SECTIONS:
        sec = dict(name=name, role=role, energy=en, start_bar=a, end_bar=b)
        sec.update(start_s=round((a - 1) * BAR_S, 3), end_s=round(b * BAR_S, 3))
        sections.append(sec)
    sections[0]['pedal'] = True
    return {
        'title': TITLE, 'bpm': BPM, 'ts': [4, 4], 'seed': 2611, 'humanize': 'natural', 'key': 'D', 'mode': 'major',
        'rubato': 0.0, 'wander': 0.0, 'ritard': 0.0,
        'dynamics': [[0.0, 0.78], [16.0, 0.8], [36.0, 0.86], [52.0, 0.9], [68.0, 1.0], [80.0, 1.0], [88.0, 0.88], [100.0, 0.78], [104.0, 0.74]],
        'space': f'{SLUG}_room', 'mix_preset': f'{SLUG}_mix', 'output_targets': ['stereo', 'immersive_7_1'],
        'master': {'lufs': -16.0, 'true_peak': -1.5, 'tone': 'neutral', 'fade_out': 0.8},
        'piece_type': SLUG, 'focus': 'melody',
        'intent': {'emotions': ['hopeful', 'wonder'], 'registers': ['natural', 'cinematic'], 'scenes': ['establish', 'arrival'],
                   'tensions': ['rising_line'], 'avoid': ['four_on_the_floor']},
        'mix_intent': {'hero': 'bansuri', 'leave_free_hz': []},
        'foreground': ['bansuri', 'pipes'],
        'medium': {'model': 'iso9613', 'state': {'temperature_k': 289.15, 'pressure_pa': 89900, 'rh_percent': 92}},
        'plan': {'sections': sections},
        'tracks': tracks,
    }


def direction():
    """The direction sheet, filled field by field (references/workflow/music-direction.md section 2) after the research of
    reports/research_western_ghats_sunrise_rahman_fusion_bagpipes_rock_band.md."""
    with open(os.path.join(SKILL, 'templates', 'direction_sheet.json'), encoding='utf-8') as fh:
        d = json.load(fh)
    t = lambda bar: round((bar - 1) * BAR_S, 1)
    d.update(
        title=TITLE, project='Western Ghats Sunrise (a 60 s cue: Carnatic melody, Highland pipes, a Western rock band, a sectioned choir and a living dawn)', version=1, medium='audio',
        brief='A 60 second A.R. Rahman style cultural mix with his signature; the ambience of a sunrise in the Western Ghats; real Scottish bagpipes that play fast; upbeat and catchy, with a Western drum kit and electric guitars; the ambience quiet for the first 20 to 30 seconds; stereo and 8-channel 7.1 from a fifth-order ambisonic bus.',
        audience='a listener on headphones or speakers, a travel-film, trailer-bumper or album-opener context; they know the sound of Indian film fusion and want to move to it',
        purpose='to hook inside six seconds with a syncopated flute riff over a rock groove, to bring the Highland pipes in as a real fast reel, to turn the key up a whole tone for a crest after the pipes have stopped, and to land softly in a dawn that was there all along',
        point_of_view='an observer on the ridge as the valley wakes: the band is the energy of the morning, the pipes are another village answering from the next hill',
        job=['hook within 6 s: the riff, the kit and the tabla together', 'let the Highland pipes play a fast, ornamented reel on their own for four bars', 'raise the key a whole tone only after the pipes stop (a pipe cannot change key)', 'keep the ambience under the music for the first 30 s and let it open in the crest and the morning'],
        story='Two bars of mist and the groove drops in; the riff repeats and climbs; the sun clears the ridge at 20.8 s; a piper on the next hill plays a reel at 30 s; the whole band lifts a whole tone for the crest at 39.2 s; a calm morning follows.',
        duration_s=60.0, in_point_s=0.0, out_point_s=60.0, ending='tail_out',
        feel=['upbeat', 'catchy', 'driving', 'luminous', 'warm'], avoid_feel=['sleepy', 'ambient wash', 'synthetic', 'robotic', 'new-age cliche', 'aggressive'],
        sections=[
            dict(name='mist', start_s=t(1), end_s=t(3), energy=0.3, action='mist, a stream, one far bird', role='place',
                 music='the bansuri over the tanpura; the tabla comes in at bar 2; the riff arrives as a pickup'),
            dict(name='groove', start_s=t(3), end_s=t(10), energy=0.55, action='the light finds the ridge', role='establish',
                 music='the riff repeats on the bansuri; the rock kit plays kick, rim and hats; the bass guitar; the clean guitar arpeggios from bar 7; violins a third below; pp choir; the pipes\' drone swells in at bar 8; a tom fill into the sun'),
            dict(name='sunrise', start_s=t(10), end_s=t(14), energy=0.8, action='the sun clears the ridge', role='peak',
                 music='a crash and a daf stroke; the full kit; the palm-muted drive guitar chugs 3+3+2; the riff in full light; violas drive; the choir builds'),
            dict(name='piper', start_s=t(14), end_s=t(18), energy=0.75, action='the next hill answers', role='transition',
                 music='the Highland piper plays a fast reel (one four-bar strain) over the drone; the kit on kick, snare and hats; the guitar chugs rest and so does the flute; held choir and violin thirds'),
            dict(name='crest', start_s=t(18), end_s=t(22), energy=1.0, action='full light', role='peak',
                 music='the key rises a whole tone as the pipes stop; the flute plays the riff high; drive guitar, full kit, tutti choir, strings pulse; the tanpura returns'),
            dict(name='morning', start_s=t(22), end_s=t(27), energy=0.4, action='full daylight, birds everywhere', role='button',
                 music='back in D: the riff once softly, a distant flourish on the pipes, the band thins to hats and kick, Sa alone, the birds')],
        motifs=[dict(name='the riff', first_at_s=t(3), shape='a syncopated rise D . E . F# A F# A, then B A F# E F# D: a leap of a fifth (Sa to Pa) on the off-beat', returns='bars 3, 5, 7; a third below on the violins at 9 s; in full light at 20.8 s; high in E at 39.2 s a degree lower; once softly in D at 48.5 s; the first notes alone at the end'),
               dict(name='the reel', first_at_s=t(14), shape='eight even eighth-notes to the bar for four bars on the chanter (A4 to A5), a gracenote on every beat, ending on a birl on low A', returns='once at 30 s; a distant one-bar flourish at 51 s')],
        instruments=['bansuri', 'rock drum kit', 'bass guitar', 'clean electric guitar', 'overdriven electric guitar', 'strings (violins, violas, celli)', 'Highland bagpipes (chanter and drone)', 'tabla and daf', 'tanpura', 'sitar', 'santoor', 'sectioned choir', 'environment'],
        avoid_sounds=['synth pad', 'reverb wash', 'four-on-the-floor kick', 'drone alone'],
        pulse='the tabla and a kick from 2 s; the rock groove (kick on 3+3+2, snare on 2 and 4, eighth hats) from 4.6 s; the full groove from 20.8 s', tempo_bpm=[104, 104], key='D', mode='major',
        energy=0.7, space=f'{SLUG}_room',
        hits_at=[t(10), t(18)], hits=[dict(t=t(10), kind='musical', sync='soft', sound='a crash, a daf stroke and the first drive-guitar chug as the sun clears the ridge', why='the first turn: the band arrives in full; the strings keep sounding, so a musical hit and not a cut'),
                                       dict(t=t(18), kind='musical', sync='soft', sound='the key rises a whole tone as the pipes stop: a crash and a tom fill', why='the crest: the harmonic turn the piece is built for')],
        mix_intent=dict(hero='bansuri', support=['violins_counter', 'guitar_clean', 'pipes'], sits_under=[], must_hear=['the riff in the first 6 s', 'the reel on the pipes at 30 s', 'the key rise at 39.2 s', 'the stream and one bird, quietly, from the start'], leave_free_hz=[]),
        loudness_lufs=-16.0, true_peak_max=-1.5,
        delivery=dict(format='wav', sample_rate=44100, bit_depth=24, stage='streaming', output_targets=['stereo', 'immersive_7_1'], played_on='headphones and speakers (stereo), and an 8-channel 7.1 bed (a fifth-order ambisonic mix decoded once)'),
        references=['in words, not a track: an upbeat Indian film fusion cue with a flute riff over a rock groove, strings and a choir; a piper playing a reel on a far hill; a living forest under it'],
        spatial_staging={k: dict(azimuth=float(v[0]), elevation=float(v[1]), distance=float(v[2]), space=f'{SLUG}_room') for k, v in STAGE.items()},
        immersive=dict(enabled=True, why='the valley is a field: the birds sit high and far around the listener, the stream is below left, the piper stands far behind on the ridge, the band is a stage in front and around; the bansuri is the one part that moves',
                       engine='hoa_bus', anchors=['kit', 'bass', 'tanpura', 'celli', 'tabla', 'pipes', 'pipes_drone', 'ambience'],
                       movers=[dict(part='bansuri', why='it walks into the valley', path='enters 30 degrees left in the mist, crosses the centre as the sun clears the ridge at 20.8 s, settles 22 degrees right for the last breath')],
                       height=dict(violins_long=22, choir=24, santoor=30, pipes_drone=22, guitar_clean=18), room_changes=[], must_hear=['the bansuri crossing the centre at 20.8 s', 'the piper far behind at 30 s'],
                       deliverables=['stereo', 'immersive_7_1'], notes='Heights, trajectory keyframes and the room live in the presets; this block records the intent.'),
        focus='melody',
        intent=dict(emotions=['hopeful', 'wonder'], registers=['natural', 'cinematic'], scenes=['establish', 'arrival'], tensions=['rising_line'], avoid=['four_on_the_floor']),
        piece_type=SLUG,
        gate_reason='A melody-led band piece: the melodic rows judge it unchanged; nothing is relaxed in advance.',
        video=dict(d['video'], enabled=False),
        notes='Rahman overlay: layered idioms, a drone, a rhythm that is the protagonist, a held-back rock build, a sectioned choir. The pipes stay in D (their scale is A mixolydian, the same notes): the whole-tone raise comes only after they stop. 104 BPM is inside the reel dance range and under the KB ceiling for tabla and bends.')
    d['expression'] = dict(
        sonic_picture='In the first six seconds a bansuri sings over a tanpura and a light tabla, a stream and one far bird, and a rock groove drops in with a syncopated riff; in the middle a palm-muted guitar chugs and the sun-lit band drives, then everything gives way to a piper on a far hill playing a fast reel over a drone; the band comes back a whole tone higher for the crest and settles into a quiet morning with Sa alone and the birds.',
        performer='The flute breathes between phrases and warms into long notes; the drummer pushes the snare a little behind and rides the hats; the bass player locks with the kick; the guitarist mutes with the palm and lets the clean guitar ring; the piper never stops the drone, places a gracenote on every beat and runs the notes in a steady stream; the choir are people in sections who join as the sound grows.',
        producer_moves='The rock build is held to the crest; the pipes are the only lead for four bars; the key rises only when the pipes stop; the ambience opens after 30 s; section loudness follows the plan.',
        anti_generic='The generic version is a pad, a flute loop, a drum loop and a bird sample; what stops it is a syncopated riff with a leap on the off-beat, a fast ornamented pipe reel that takes over the stage, and a whole-tone lift after the pipes stop.',
        cues=[dict(section='mist', arousal='mid', mode_register='major pentatonic, mid-high flute', tempo_trend='steady 104 with a pulse from bar 2', dynamics='mp rising to mf', articulation='legato with slides', timbre='breathy, soft attack'),
              dict(section='groove', arousal='mid', mode_register='same, band below', tempo_trend='steady 104', dynamics='mf', articulation='syncopated riff, clean arpeggio, rim and hats', timbre='warm, rhythmic'),
              dict(section='sunrise', arousal='high', mode_register='riff in full light', tempo_trend='steady, 3+3+2 chugs', dynamics='f', articulation='palm-muted chugs, snare backbeat', timbre='bright, driving'),
              dict(section='piper', arousal='high', mode_register='pipes in A mixolydian (the D major notes), A4 to A5', tempo_trend='steady, a reel of eighths', dynamics='mf with no swell (a pipe has none)', articulation='gracenote on every beat, a birl at the strain end', timbre='reedy, continuous'),
              dict(section='crest', arousal='high', mode_register='up a whole tone, flute high', tempo_trend='steady', dynamics='ff', articulation='full band, held tutti choir', timbre='open vowels, bright'),
              dict(section='morning', arousal='low', mode_register='home key, mid', tempo_trend='settling', dynamics='mp falling to pp', articulation='long tails', timbre='warm, thin')],
        theme=dict(contour='arch: a syncopated step-wise rise, a leap of a fifth, and a step back', interval_character='steps with one leap of a fifth (Sa to Pa) on the off-beat', rhythm_cell='dotted, short, short, long, short-short',
                   why_memorable='a short riff that repeats with small changes; its leap lands off the beat; the reel answers it with a completely different gesture, eight even notes',
                   variation_plan='a third below on the violins, in full light at the sun, a degree lower and high in E at the crest, once softly at the end, the first notes alone'))
    d['harmony_plan'] = [dict(section='mist', root='D', pedal=True, why='the dawn holds one note: Sa and Pa on the tanpura'),
                         dict(section='groove', move='D, Bm7, D, A under the riff', counter_hook='violins sing it a third below; the clean guitar arpeggiates the chord'),
                         dict(section='sunrise', move='D, Bm7: every chord holds the pipes\' A', counter_hook='the drive guitar chugs the roots and fifths'),
                         dict(section='piper', move='D, Bm7, D, A under the reel; the drone on A throughout', counter_hook='violins hold thirds above the reel and never double it'),
                         dict(section='crest', key='raise a whole tone to E once the pipes have stopped', move='E, C#m7, E, B', counter_hook='the flute plays the riff high, a degree lower, over the guitars'),
                         dict(section='morning', key='return to D', move='D, A, D, ending on a D triad', counter_hook='the flute alone, the pipes a distant flourish, the band thins out')]
    return d


def main():
    for i in INSTRUMENTS:
        write(os.path.join(P, 'presets', 'instruments', i['name'] + '.json'), i)
    write(os.path.join(P, 'presets', 'instruments', 'ghats_tabla.json'), TABLA)
    write(os.path.join(P, 'presets', 'instruments', 'ghats_kit.json'), KIT)
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
