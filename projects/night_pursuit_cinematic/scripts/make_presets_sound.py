#!/usr/bin/env python3
"""make_presets_sound.py - writes the physical sounds of Night Pursuit Cinematic as presets: four cars, two sirens, the helicopter, the expansion
joints, the landing, the crash and the city.

Nothing here makes a sound. Each preset is a sound model (excitation -> resonator -> time process, scripts/sound_model.py) or a layered
environment; this script only fills in the curves that depend on the story's clock (each car's rpm through its gears, the sirens' sweeps, the
joints' spacing) from `timeline.py` and `cars.py`, and writes the JSON. The relations it uses are written next to the number: the firing
frequency of a four-stroke engine is rpm x cylinders / 120, road speed is 2 pi r rpm / (60 G), and a source that passes the listener is placed
by a trajectory whose Doppler shift the spatial engine computes. Every number without a source is a starting value (the research note).
There is no falling rain and no wiper in this piece: the wet is the road (tyre hiss and spray).
"""
import json
import math
import os

import cars
import timeline as T

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'presets')
TM = T.tempo_map()
EV = T.events(TM)
START = T.sfx_start()
SPACE = 'np_street_canyon'
END = round(EV['end'] + 1.0, 1)
SECONDS = END
OFF = 0.0
S = lambda name: float(T.seconds(T.start(name), 0, TM))                  # noqa: E731  first second of a section
E_ = lambda name: float(T.seconds(T.end(name), 0, TM))                   # noqa: E731  first second after a section
SLOMO = [(EV['jump'], EV['land'])]
SLOMO_RAMP_S = 3.0


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def dive(t, depth=0.5):
    for a, b in SLOMO:
        if a <= t < b:
            return 1.0 - (1.0 - depth) * smooth((t - a) / SLOMO_RAMP_S)
    return 1.0


def slowness(t):
    return 1.0 - dive(t, 0.0)


def sample(fn, t0, t1, dt):
    t0, t1 = max(t0, OFF), min(t1, END)
    n = max(1, int(round((t1 - t0) / dt)))
    return [[round(t0 - OFF + i * dt, 3), round(float(fn(t0 + i * dt)), 4)] for i in range(n + 1)]


def rel(points):
    return [[round(t - OFF, 3), v] for t, v in points]


def begin(name, until=None):
    """The effect's own clock starts at its trigger note; its model lasts until `until` (a piece second) or the end of the cue."""
    global OFF, SECONDS
    OFF = START[name]
    SECONDS = round((until if until is not None else END) + 0.5 - OFF, 1)
    return OFF


def write(kind, name, body):
    est = [x for x in body.get('sources', []) if x.startswith('ESTIMATE')]
    if est:
        body['sources'] = [x for x in body['sources'] if not x.startswith('ESTIMATE')]
        body['note'] = (body.get('note', '') + ' ' + ' '.join(est)).strip()
    d = os.path.join(P, kind)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(name=name, **body), fh, indent=1)


def slowmo_fx(cutoff_hz, gain_db=0.0):
    """A low-pass that closes inside each slow-motion window and opens over the last 0.6 s (so the snap-back is not a step)."""
    chain = []
    for a, b in SLOMO:
        chain.append(dict(type='filter_sweep', kind='lowpass', f_start_hz=14000.0, f_end_hz=float(cutoff_hz), q=0.8, start_s=round(a, 3),
                          end_s=round(a + 2.5, 3), after='bypass', edge_ms=10.0))
        chain.append(dict(type='filter_sweep', kind='lowpass', f_start_hz=float(cutoff_hz), f_end_hz=float(cutoff_hz), q=0.8,
                          start_s=round(a + 2.5, 3), end_s=round(b - 0.6, 3), after='bypass', edge_ms=10.0))
        chain.append(dict(type='filter_sweep', kind='lowpass', f_start_hz=float(cutoff_hz), f_end_hz=14000.0, q=0.8, start_s=round(b - 0.6, 3),
                          end_s=round(b, 3), after='bypass', edge_ms=10.0))
        if gain_db:
            chain.append(dict(type='pedalboard', plugin='Gain', params=dict(gain_db=float(gain_db)), start_s=round(a, 3), end_s=round(b, 3), edge_ms=400.0))
    return chain


# ================================================================================================ where each source is, shot by shot
def passby(t_p, side=1):
    """A pass at the kerb (the roadside shot): in from far, close at t_p, out again; the Doppler shift is the spatial engine's."""
    return [(t_p - 2.6, -88.0 * side, 45.0), (t_p - 1.0, -70.0 * side, 14.0), (t_p, 0.0, 7.0), (t_p + 1.0, 70.0 * side, 14.0), (t_p + 2.6, 88.0 * side, 45.0)]


def car_keys(car):
    """(t_s, azimuth, distance, elevation) for a car. The listener is inside the Ferrari in the race and the bumps, on the kerb at the pass,
    behind the pack in the chase and the flyover, far from the cars (looking up at the helicopter) in the aerial shot."""
    sp = S('spotted')
    keys = []
    if car == 'ferrari':
        keys += [(0.0, 180.0, 1.2), (sp - 1.0, 180.0, 1.2)] + passby(sp + 5.2) + [(S('the_chase') + 3.0, 0.0, 12.0), (S('the_tunnel') - 1.0, 0.0, 12.0),
                 (S('the_tunnel') + 6.0, 0.0, 10.0), (S('the_helicopter') + 2.0, 12.0, 70.0), (E_('the_helicopter') - 2.0, 12.0, 70.0),
                 (S('the_bumps') + 2.0, 180.0, 1.2), (S('the_flyover') - 1.0, 180.0, 1.2), (S('the_flyover') + 2.0, 0.0, 12.0), (EV['evade'] + 1.0, 0.0, 14.0),
                 (EV['end'], 0.0, 150.0)]
    elif car == 'lamborghini':
        keys += [(0.0, -55.0, 7.0), (sp - 1.0, -50.0, 9.0)] + passby(sp + 2.4) + [(S('the_chase') + 3.0, -25.0, 15.0), (S('the_tunnel') + 6.0, -20.0, 14.0),
                 (S('the_helicopter') + 2.0, -25.0, 80.0), (E_('the_helicopter') - 2.0, -25.0, 80.0), (S('the_bumps') + 2.0, -45.0, 8.0),
                 (S('the_flyover') + 2.0, -30.0, 14.0), (EV['lost'], -30.0, 14.0), (EV['lost'] + 3.0, -100.0, 40.0)]
    elif car == 'mustang':
        keys += [(0.0, 45.0, 9.0), (sp - 1.0, 40.0, 11.0)] + passby(sp + 5.0, side=-1) + [(S('the_chase') + 3.0, 28.0, 18.0), (EV['crash'] - 1.0, 28.0, 18.0),
                 (EV['crash'] + 1.6, 40.0, 30.0)]
    else:
        keys += [(0.0, 150.0, 12.0), (sp - 1.0, 160.0, 18.0)] + passby(sp + 6.5) + [(S('the_chase') + 3.0, 165.0, 30.0), (S('the_tunnel') + 6.0, 170.0, 22.0),
                 (S('the_helicopter') + 2.0, 150.0, 110.0), (E_('the_helicopter') - 2.0, 150.0, 110.0), (S('the_bumps') + 2.0, 150.0, 14.0),
                 (S('the_flyover') + 2.0, 160.0, 40.0), (EV['evade'], 165.0, 80.0), (EV['end'], 170.0, 220.0)]
    out, last = [], -1.0
    for k in sorted(keys):
        t = max(k[0], last + 0.05)
        out.append((t, k[1], k[2], k[3] if len(k) > 3 else 0.0))
        last = t
    return out


def keyframes(keys):
    return [dict(t_s=round(t - OFF, 2), azimuth=round(a, 1), distance=round(d, 1), elevation=round(e, 1)) for t, a, d, e in keys if t >= OFF - 1e-6]


# ================================================================================================ the cars
CAR_LEVEL_DB = -12.0          # every effect sits under the music (a film mix): the mix preset trims these again after measurement
SQUEAL_F0 = dict(ferrari=1150.0, lamborghini=1050.0, mustang=950.0, porsche=1000.0)

for car in ('ferrari', 'lamborghini', 'mustang', 'porsche'):
    c = cars.CARS[car]
    d = cars.drive(car, EV, dt=0.05, tm=TM)
    t_end = cars.end_of(car, EV)
    begin(car, t_end)
    T_ = d['t']
    rpm = lambda t: cars.interp(list(zip(T_, d['rpm'])), t)                  # noqa: E731
    v_of = lambda t: cars.interp(list(zip(T_, d['v'])), t)                   # noqa: E731
    load = lambda t: cars.interp(list(zip(T_, d['load'])), t)                # noqa: E731
    f_idle = cars.firing_hz(car, c['idle'])
    END_FADE = 2.5 if t_end >= EV['end'] - 0.5 else 0.8          # the cars that run to the end of the cue fade slowly; one that leaves the scene is gone in under a second
    ending = lambda t, L=END_FADE: (-90.0 * smooth((t - (t_end - L)) / L)) if t > t_end - L else 0.0     # noqa: E731  the engine dies or the car leaves
    fade_in = lambda t: -90.0 * (1.0 - smooth((t - OFF) / 0.4)) if t - OFF < 0.4 else 0.0           # noqa: E731

    def pitch(t, rpm=rpm, c=c, f=None):
        return rpm(t) / c['idle'] * dive(t, 0.5)

    def gain_engine(t, load=load, ending=ending, fade_in=fade_in):
        return -15.0 + 13.0 * load(t) - 5.0 * slowness(t) + ending(t) + fade_in(t)

    def hiss_db(t, v_of=v_of, ending=ending, fade_in=fade_in):
        v = v_of(t) * (1.0 - 0.5 * slowness(t))
        return -52.0 + 40.0 * min(1.0, v / 42.0) ** 1.2 + ending(t) + fade_in(t)         # wet road: 3-4 dB(A) louder than dry (research), hiss grows with speed

    def spray_db(t, v_of=v_of, ending=ending, fade_in=fade_in):
        v = v_of(t)
        return -60.0 + 46.0 * min(1.0, v / 42.0) ** 2.0 + ending(t) + fade_in(t)

    corners = [tc for tc in cars.CORNERS.get(car, []) if OFF < tc < t_end]

    def squeal_db(t, corners=corners, ending=ending):
        best = -90.0
        for tc in corners:
            u = (t - tc) / 1.3
            if abs(u) < 1.0:
                best = max(best, -90.0 + 74.0 * (0.5 + 0.5 * math.cos(math.pi * u)))
        return best + ending(t) - 6.0 * slowness(t)

    pops = [x for x in cars.overrun_pop_times(car, d, EV) if x + 0.4 < t_end]
    voices = [
        dict(name='firing', gain_db=-2.0, excite=dict(kind='periodic', f0=round(f_idle, 2), harmonics=c['harmonics'], jitter=c['jitter']),
             resonator=dict(kind='formant', formants=c['formants']), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(pitch, 0.0, t_end, 0.05))], gain_db=[dict(kind='curve', points=sample(gain_engine, 0.0, t_end, 0.1))])),
        dict(name='exhaust', gain_db=-12.0, excite=dict(kind='noise', color='brown'), resonator=dict(kind='bandpass', band=[50, 1000], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: gain_engine(t) - 3.0, 0.0, t_end, 0.2))])),
        dict(name='intake', gain_db=-22.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[900, 3200], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -40.0 + 36.0 * max(0.0, min(1.0, (rpm(t) - 0.35 * c['redline']) / (0.5 * c['redline']))) + ending(t) + fade_in(t), 0.0, t_end, 0.2))])),
        dict(name='tyre_hiss', gain_db=-14.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[700, 5500], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(hiss_db, 0.0, t_end, 0.2))])),
        dict(name='spray', gain_db=-20.0, excite=dict(kind='noise', color='white'), resonator=dict(kind='bandpass', band=[2500, 9000], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(spray_db, 0.0, t_end, 0.2))])),
    ]
    if c['burble']:               # a cross-plane V8 fires unevenly: a second, lower and rougher pulse train at half the firing frequency
        voices.append(dict(name='burble', gain_db=-9.0, excite=dict(kind='periodic', f0=round(f_idle / 2.0, 2), harmonics=18, jitter=0.07),
                           resonator=dict(kind='formant', formants=[[70, 40, 1.0], [160, 70, 0.8], [420, 160, 0.3]]), events=dict(kind='continuous'),
                           control=dict(pitch=[dict(kind='curve', points=sample(pitch, 0.0, t_end, 0.05))], gain_db=[dict(kind='curve', points=sample(gain_engine, 0.0, t_end, 0.1))])))
    if corners:
        voices.append(dict(name='squeal', gain_db=-16.0, excite=dict(kind='periodic', f0=SQUEAL_F0[car], harmonics=8, jitter=0.03, noise_mix=0.12),
                           resonator=dict(kind='formant', formants=[[900, 300, 1.0], [2400, 600, 0.5]]), events=dict(kind='continuous'),
                           control=dict(gain_db=[dict(kind='curve', points=sample(squeal_db, 0.0, t_end, 0.05))])))
    if pops:
        voices.append(dict(name='overrun_pops', gain_db=-14.0, excite=dict(kind='impact', tau=0.0012),
                           resonator=dict(kind='modal', law='bar', f1=520.0, n=5, t60=0.06),
                           events=dict(kind='sequence', times=[round(x - OFF, 3) for x in pops], levels=[round(0.5 + 0.5 * ((i * 7) % 5) / 4.0, 2) for i in range(len(pops))])))
    write('sfx', 'np_car_' + car, dict(
        kind='sfx', seconds=SECONDS,
        character=f'{c["label"]} on a wet road at night: a firing-frequency pulse train through the body that follows the rpm through its gears, tyre hiss and spray under it, '
                  f'a squeal at each corner{", an uneven burble" if c["burble"] else ""} and pops when the throttle lifts; it dives in the slow motion.',
        note=f'f0 is the firing frequency rpm x {c["cyl"]} / 120 ({f_idle:.1f} Hz at {c["idle"]:.0f} rpm idle, {cars.firing_hz(car, c["redline"]):.0f} Hz at the {c["redline"]:.0f} rpm redline); '
             f'the speed profile (km/h) and the gear choice are in cars.py; road speed is 2 pi r rpm / (60 G).',
        model=dict(seconds=SECONDS, voices=voices), role='fx', gain_db=CAR_LEVEL_DB, reverb=0.04,
        spatial=dict(azimuth=car_keys(car)[0][1], elevation=0.0, distance=car_keys(car)[0][2], space=SPACE, binaural=True, kind='spot',
                     trajectory=dict(spatial_role='mover', doppler_strength=1.0, keyframes=keyframes(car_keys(car)))),
        eq=[dict(type='hp', f=30.0), dict(type='lp', f=11000.0)], fx=slowmo_fx(900.0, -2.0),
        sources=['car_engine_v8', {'ferrari': 'car_ferrari_v8', 'lamborghini': 'car_lamborghini_v10', 'mustang': 'car_mustang_v8', 'porsche': 'car_porsche_flat6'}[car],
                 'wet_road_tyre', 'tyre_squeal_wet', 'exhaust_overrun_pops', 'doppler_passby', 'cabin_interior',
                 'ESTIMATE: gear ratios, final drive, tyre radius, speed profile, formants and levels are starting values; no recording of this car was measured']))


# ================================================================================================ the sirens
def wail(t, lo=600.0, hi=1400.0, cpm=20.0):
    return 1.0 + (hi / lo - 1.0) * (0.5 - 0.5 * math.cos(2 * math.pi * t * cpm / 60.0))


def yelp(t, lo=700.0, hi=1500.0, cpm=240.0):
    return 1.0 + (hi / lo - 1.0) * (0.5 - 0.5 * math.cos(2 * math.pi * t * cpm / 60.0))


def hilo(t, low=435.0, high=580.0, cpm=55.0):
    phase = (t * cpm / 60.0) % 1.0
    k = smooth(min(1.0, phase / 0.03)) if phase < 0.5 else 1.0 - smooth(min(1.0, (phase - 0.5) / 0.03))
    return (low + (high - low) * k) / low


def gate_db(t, t_on, t_off, occl=(), fade=0.5):
    if t < t_on or t > t_off:
        return -90.0
    g = -90.0 + 90.0 * smooth(min(1.0, (t - t_on) / fade, (t_off - t) / fade))
    for a, b in occl:
        if a <= t <= b:
            g -= 9.0 * smooth(min(1.0, (t - a) / 0.4, (b - t) / 0.4))
    return g


def occlusion_fx(windows, cutoff=900.0):
    chain = []
    for a, b in windows:
        chain += [dict(type='filter_sweep', kind='lowpass', f_start_hz=12000.0, f_end_hz=cutoff, q=0.7, start_s=round(a, 3), end_s=round(a + 0.5, 3), after='bypass', edge_ms=10.0),
                  dict(type='filter_sweep', kind='lowpass', f_start_hz=cutoff, f_end_hz=cutoff, q=0.7, start_s=round(a + 0.5, 3), end_s=round(b - 0.5, 3), after='bypass', edge_ms=10.0),
                  dict(type='filter_sweep', kind='lowpass', f_start_hz=cutoff, f_end_hz=12000.0, q=0.7, start_s=round(b - 0.5, 3), end_s=round(b, 3), after='bypass', edge_ms=10.0)]
    return chain


S1_ON, S1_OFF = EV['spot'], EV['evade'] + 5.0
OCC1 = [(S('the_tunnel') + 1.0, S('the_tunnel') + 5.0)]                        # behind the tunnel mouth, then inside it
begin('siren_first', S1_OFF)
write('sfx', 'np_siren_wail', dict(
    kind='sfx', seconds=SECONDS,
    character='The first cruiser: a police siren in wail, a slow sweep between 600 and 1400 Hz at 20 cycles a minute with six harmonics; it starts far at the kerb, then closes in behind the cars and stops when the chase is lost.',
    note='600-1400 Hz sits inside the 500-1800 Hz band the first project cited for SAE J1849; 20 cycles a minute is the NIJ example for a wail.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='wail', gain_db=0.0, excite=dict(kind='periodic', f0=600.0, harmonics=6, jitter=0.002), resonator=dict(kind='none'), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(lambda t: wail(t) * dive(t, 0.7), S1_ON, S1_OFF, 0.1))],
                          gain_db=[dict(kind='curve', points=sample(lambda t: gate_db(t, S1_ON, S1_OFF, OCC1) - 3.0 * slowness(t), 0.0, S1_OFF, 0.1))]))]),
    role='fx', gain_db=CAR_LEVEL_DB - 2.0, reverb=0.10,
    spatial=dict(azimuth=-30.0, elevation=0.0, distance=90.0, space=SPACE, binaural=True, kind='spot', trajectory=dict(spatial_role='mover', doppler_strength=1.0, keyframes=keyframes(
        [(EV['spot'], -30.0, 90.0, 0.0), (EV['spot'] + 8.0, -20.0, 40.0, 0.0), (S('the_chase') + 2.0, 170.0, 20.0, 0.0), (S('the_tunnel'), 175.0, 12.0, 0.0),
         (S('the_helicopter') + 2.0, 160.0, 30.0, 0.0), (S('the_bumps') + 2.0, 170.0, 24.0, 0.0), (S('the_flyover') + 4.0, 175.0, 18.0, 0.0),
         (EV['evade'], 180.0, 30.0, 0.0), (S1_OFF, 150.0, 120.0, 0.0)]))),
    eq=[dict(type='hp', f=300.0), dict(type='lp', f=8000.0)], fx=occlusion_fx(OCC1, 900.0) + slowmo_fx(2500.0, 0.0),
    sources=['police_siren', 'ESTIMATE: sweep limits, six harmonics and levels are starting values']))

S2_ON, S2_OFF = S('the_chase'), EV['evade'] + 2.0
begin('siren_second', S2_OFF)
write('sfx', 'np_siren_second', dict(
    kind='sfx', seconds=SECONDS,
    character='The second cruiser: a two-tone 435/580 Hz hi-lo at 55 cycles a minute while it joins, then a fast yelp from 700 to 1500 Hz at 240 cycles a minute once the helicopter is overhead; it never shares a pitch with the first.',
    note='The two-tone pattern and the NIJ yelp rate; it switches pattern when the helicopter arrives.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='second', gain_db=0.0, excite=dict(kind='periodic', f0=600.0, harmonics=6, jitter=0.002), resonator=dict(kind='none'), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(lambda t: (hilo(t) * 435.0 / 600.0 if t < S('the_helicopter') else yelp(t) * 700.0 / 600.0) * dive(t, 0.7), S2_ON, S2_OFF + 0.2, 0.02))],
                          gain_db=[dict(kind='curve', points=sample(lambda t: gate_db(t, S2_ON, S2_OFF, [(S('the_tunnel') + 2.0, S('the_tunnel') + 6.0)], fade=0.12) - 3.0 * slowness(t), 0.0, S2_OFF, 0.1))]))]),
    role='fx', gain_db=CAR_LEVEL_DB - 3.0, reverb=0.10,
    spatial=dict(azimuth=60.0, elevation=0.0, distance=70.0, space=SPACE, binaural=True, kind='spot', trajectory=dict(spatial_role='mover', doppler_strength=1.0, keyframes=keyframes(
        [(S2_ON, 60.0, 70.0, 0.0), (S('the_chase') + 8.0, 140.0, 24.0, 0.0), (S('the_tunnel') + 2.0, 100.0, 14.0, 0.0), (S('the_helicopter') + 2.0, 60.0, 40.0, 0.0),
         (S('the_bumps') + 2.0, 100.0, 20.0, 0.0), (S('the_flyover') + 6.0, 120.0, 16.0, 0.0), (EV['evade'], 150.0, 40.0, 0.0), (S2_OFF, 150.0, 90.0, 0.0)]))),
    eq=[dict(type='hp', f=300.0), dict(type='lp', f=8000.0)], fx=occlusion_fx([(S('the_tunnel') + 2.0, S('the_tunnel') + 6.0)], 700.0) + slowmo_fx(2500.0, 0.0),
    sources=['police_siren', 'ESTIMATE: the two patterns and their levels are starting values']))

# ================================================================================================ the helicopter
H_ON = START['helicopter']                       # the trigger note and the model's own start are one second
H_OFF = S('the_flyover') + 12.0
BLADE_PASS_HZ = 4 * 400.0 / 60.0               # 4 blades at 400 rpm: general knowledge (the research note), a starting value


def heli_gain(t):
    up = smooth((t - H_ON) / 0.3)          # in at once (the distance, not a fade, makes it far): the stem gate judges an effect from its onset
    down = 1.0 - smooth((t - (H_OFF - 6.0)) / 6.0)
    near = 0.0 if t < E_('the_helicopter') else -9.0                      # after its shot it is heard from the chase at a lower level
    return -90.0 + 90.0 * min(up, down) + near


begin('helicopter', H_OFF)
write('sfx', 'np_helicopter', dict(
    kind='sfx', seconds=SECONDS,
    character='A police helicopter: a thump at the blade-passing frequency with a dozen harmonics, a faster and higher tail rotor and a rough turbine hiss; it comes in high and far, crosses overhead and stays above the flyover.',
    note=f'Main rotor blade-pass {BLADE_PASS_HZ:.1f} Hz (4 blades at 400 rpm, general knowledge); tail rotor tones higher and faster (the research note).',
    model=dict(seconds=SECONDS, voices=[
        dict(name='main_rotor', gain_db=0.0, excite=dict(kind='periodic', f0=round(BLADE_PASS_HZ, 2), harmonics=14, jitter=0.012),
             resonator=dict(kind='formant', formants=[[60, 40, 1.0], [180, 80, 0.8], [440, 200, 0.35]]), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(heli_gain, H_ON, H_OFF, 0.2))])),
        dict(name='tail_rotor', gain_db=-9.0, excite=dict(kind='periodic', f0=118.0, harmonics=8, jitter=0.02),
             resonator=dict(kind='bandpass', band=[150, 1400], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(heli_gain, H_ON, H_OFF, 0.2))])),
        dict(name='turbine', gain_db=-20.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[1500, 6000], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: heli_gain(t) - 4.0, H_ON, H_OFF, 0.2))]))]),
    role='fx', gain_db=CAR_LEVEL_DB, reverb=0.08,
    spatial=dict(azimuth=-100.0, elevation=50.0, distance=150.0, space=SPACE, binaural=True, kind='spot', trajectory=dict(spatial_role='mover', doppler_strength=1.0, keyframes=keyframes(
        [(H_ON, -100.0, 90.0, 50.0), (S('the_helicopter') + 4.0, -40.0, 50.0, 50.0), (S('the_helicopter') + 10.0, 0.0, 18.0, 62.0), (E_('the_helicopter') - 2.0, 70.0, 60.0, 48.0),
         (S('the_bumps') + 4.0, 120.0, 100.0, 40.0), (S('the_flyover') + 2.0, 40.0, 45.0, 45.0), (H_OFF, 90.0, 140.0, 40.0)]))),
    eq=[dict(type='hp', f=30.0), dict(type='lp', f=9000.0)], fx=slowmo_fx(2000.0, 0.0),
    sources=['helicopter_rotor', 'doppler_passby', 'ESTIMATE: blade count, rotor speed, tail-rotor frequency and levels are starting values']))

# ================================================================================================ expansion joints, landing, crash
def hero_distance(t):
    d = cars.drive('ferrari', EV, dt=0.05, tm=TM)
    return d


HD = cars.drive('ferrari', EV, dt=0.05, tm=TM)
JOINT_SPACING_M = 12.0              # a starting value: expansion joints on a flyover deck
joint_times, x = [], 0.0
t_a, t_b = S('the_bumps'), EV['jump']
for i, (t, v) in enumerate(zip(HD['t'], HD['v'])):
    if i == 0:
        continue
    if t_a <= t <= t_b:
        x += v * 0.05
        if x >= JOINT_SPACING_M:
            x -= JOINT_SPACING_M
            joint_times.append((round(t, 3), v))
begin('bumps', t_b)
write('sfx', 'np_bumps', dict(
    kind='sfx', seconds=SECONDS,
    character='The flyover deck at speed: a thump at every expansion joint, a low body under 200 Hz and a tonal part near 650 Hz, louder the faster the car goes.',
    note=f'A joint every {JOINT_SPACING_M:.0f} m (starting value); the research note gives 500-800 Hz above the deck and up to 200 Hz below; {len(joint_times)} joints between the start of the deck and the take-off.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='joint_body', gain_db=0.0, excite=dict(kind='impact', tau=0.006), resonator=dict(kind='modal', law='bar', f1=85.0, n=3, t60=0.14),
             events=dict(kind='sequence', times=[round(t - OFF, 3) for t, v in joint_times], levels=[round(min(1.0, v / 42.0) ** 1.5, 3) for t, v in joint_times])),
        dict(name='joint_air', gain_db=-5.0, excite=dict(kind='impact', tau=0.002), resonator=dict(kind='modal', law='bar', f1=650.0, n=4, t60=0.05),
             events=dict(kind='sequence', times=[round(t - OFF, 3) for t, v in joint_times], levels=[round(min(1.0, v / 42.0) ** 1.5, 3) for t, v in joint_times])),
        dict(name='deck_hum', gain_db=-26.0, excite=dict(kind='noise', color='brown'), resonator=dict(kind='bandpass', band=[40, 300], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -6.0 * (1.0 - smooth((t - t_a) / 2.0)) * 0.0 - 4.0, t_a, t_b, 0.5))]))]),
    role='fx', gain_db=CAR_LEVEL_DB + 2.0, reverb=0.04,
    spatial=dict(azimuth=180.0, elevation=25.0, distance=1.3, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=30.0), dict(type='lp', f=6000.0)],
    sources=['bridge_expansion_joint', 'ESTIMATE: joint spacing, the two modes and the levels are starting values']))

T_LAND = EV['land']
begin('landing', T_LAND + 3.0)
write('sfx', 'np_landing', dict(
    kind='sfx', seconds=SECONDS,
    character='The landing after the jump: a deep thump as the suspension bottoms out, a metal knock on the deck and a short scrape.',
    note='A layered impact: a transient, a body, a sub and a tail (the crash research); starting values.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='sub_thump', gain_db=0.0, excite=dict(kind='impact', tau=0.012), resonator=dict(kind='modal', law='bar', f1=48.0, n=3, t60=0.6), events=dict(kind='single', at=0.02)),
        dict(name='body_knock', gain_db=-4.0, excite=dict(kind='impact', tau=0.004), resonator=dict(kind='modal', law='bar', f1=190.0, n=6, t60=0.3), events=dict(kind='single', at=0.02)),
        dict(name='scrape', gain_db=-12.0, excite=dict(kind='friction', beta=-1.5, speed=1.0, amp_exp=1.0), resonator=dict(kind='bandpass', band=[600, 5000], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=[[0.0, -90.0], [0.04, 0.0], [0.5, -20.0], [0.9, -90.0], [SECONDS, -90.0]])]))]),
    role='fx', gain_db=CAR_LEVEL_DB + 6.0, reverb=0.10,
    spatial=dict(azimuth=180.0, elevation=0.0, distance=6.0, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=28.0), dict(type='lp', f=9000.0)],
    sources=['car_crash_impact', 'ESTIMATE: no recording was measured; the modes and the scrape are starting values']))

T_CRASH = EV['crash']
begin('crash', T_CRASH + 3.0)
write('sfx', 'np_crash', dict(
    kind='sfx', seconds=SECONDS,
    character='The Mustang hitting the barrier at the tunnel mouth: one impact on a damped panel, a tear of metal and the tinkle of glass.',
    note='A collision is a short impact, a tearing tail and glass (the research note); every level is a starting value.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='panel_hit', gain_db=0.0, excite=dict(kind='impact', tau=0.003), resonator=dict(kind='modal', law='free', f1=210.0, ratios=[1.0, 2.3, 3.9, 5.6, 7.7, 10.1, 12.8], t60=1.1),
             events=dict(kind='single', at=0.05)),
        dict(name='sub_thud', gain_db=-3.0, excite=dict(kind='impact', tau=0.008), resonator=dict(kind='modal', law='bar', f1=55.0, n=3, t60=0.5), events=dict(kind='single', at=0.05)),
        dict(name='tear', gain_db=-8.0, excite=dict(kind='friction', beta=-1.5, speed=1.0, amp_exp=1.0), resonator=dict(kind='bandpass', band=[500, 5000], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=[[0.0, -90.0], [0.05, -90.0], [0.1, 0.0], [1.3, -30.0], [1.9, -90.0], [SECONDS, -90.0]])])),
        dict(name='glass', gain_db=-6.0, excite=dict(kind='impact', tau=0.0006), resonator=dict(kind='modal', law='bar', f1=3300.0, n=10, t60=0.25),
             events=dict(kind='poisson', rate=26.0, start=0.13, end=2.45))]),
    role='fx', gain_db=CAR_LEVEL_DB + 4.0, reverb=0.12,
    spatial=dict(azimuth=115.0, elevation=0.0, distance=22.0, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=40.0), dict(type='lp', f=12000.0)],
    sources=['car_crash_impact', 'ESTIMATE: no collision recording was measured; the plate modes, the tear and the glass rate are starting values']))

# ================================================================================================ the city and the drips (environments)
begin('ferrari')
write('environments', 'np_city_far', dict(
    description='The far city at night after rain: traffic as a low hum and an air of distant streets.',
    character='A far, low traffic hum after the rain with a thin air of distant streets and no event: the city is a bed under the music, never a foreground.',
    atmosphere=dict(temp_c=10.0, rh=95.0),
    layers=[dict(name='traffic', primitive='noise_bed', kind='bed', color='brown', low_hz=45, high_hz=450, mod_rate_hz=0.04, mod_depth=0.25, gain_db=-20.0,
                 decorrelate=1.0, spatial=dict(azimuth=0, elevation=0, distance=80)),
            dict(name='city_air', primitive='noise_bed', kind='bed', color='pink', low_hz=450, high_hz=2500, mod_rate_hz=0.06, mod_depth=0.2, gain_db=-30.0,
                 decorrelate=1.0, spatial=dict(azimuth=0, elevation=0, distance=90))],
    blending=dict(), sources=['city_traffic_far', 'ESTIMATE: no night-time New York spectrum was found; bands and levels are starting values']))

write('environments', 'np_drips', dict(
    description='Water dripping from the fronts and the awnings onto the wet street after the rain, sparse, at the quiet end.',
    character='Single drops falling from metal awnings and ledges onto a wet street after the rain: sparse, tonal and unhurried, never a patter.',
    atmosphere=dict(temp_c=10.0, rh=95.0),
    layers=[dict(name='drip_left', primitive='model_layer', kind='spot', gain_db=-22.0, spatial=dict(azimuth=-80, elevation=0, distance=7),
                 voices=[dict(name='drops', excite=dict(kind='impact', tau=0.0015), resonator=dict(kind='modal', law='free', f1=520.0, ratios=[1.0, 2.2, 3.7, 5.4, 7.6, 10.0], t60=0.35),
                              events=dict(kind='poisson', rate=1.6), vary=dict(size=dict(dist='exp', rate_mm_h=3.0, min=0.5, max=2.0), pitch_exp=0.3, amp_exp=1.0))]),
            dict(name='drip_right', primitive='model_layer', kind='spot', gain_db=-24.0, spatial=dict(azimuth=85, elevation=0, distance=8),
                 voices=[dict(name='drops', excite=dict(kind='impact', tau=0.0015), resonator=dict(kind='modal', law='free', f1=410.0, ratios=[1.0, 2.1, 3.6, 5.2, 7.3, 9.6], t60=0.4),
                              events=dict(kind='poisson', rate=1.2), vary=dict(size=dict(dist='exp', rate_mm_h=3.0, min=0.5, max=2.0), pitch_exp=0.3, amp_exp=1.0))])],
    blending=dict(), sources=['wet_road_tyre', 'ESTIMATE: the modes of a ledge and the drip rate are starting values']))

if __name__ == '__main__':
    print(f'wrote 4 cars, two sirens, the helicopter, {len(joint_times)} expansion joints, the landing, the crash, the city and the drips; {END} s')
    for c in cars.CARS:
        d = cars.drive(c, EV)
        print(f'  {c:12s} {cars.CARS[c]["label"]:26s} rpm {min(d["rpm"]):6.0f}-{max(d["rpm"]):6.0f}  shifts {len(d["shifts"])}  ends {cars.end_of(c, EV):6.1f} s')
