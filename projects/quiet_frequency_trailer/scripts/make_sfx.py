#!/usr/bin/env python3
"""make_sfx.py - writes the sounds of Quiet Frequency as sound-model presets (presets/sfx/*.json).

Nothing here makes a sound. Each preset is a sound model (excitation -> resonator -> time process, scripts/sound_model.py); this script only
fills in the curves that depend on the story's clock (the rpm through the gears, the squeals, the radio's transmissions) from timeline.py and
writes the JSON. The relations it uses are written next to the number: the firing frequency of a four-stroke engine is rpm x cylinders / 120;
a gear change multiplies the rpm by the ratio of the new gear to the old.
Every number without a source is a starting value, as the research note says. No recording of any vehicle was analysed.
"""
import json
import math
import os

import timeline as T

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'presets', 'sfx')
SPACE = 'quiet_frequency_room'
END = 119.9
OFF = 0.0
SECONDS = END


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def begin(t_on, t_off):
    """The effect's own clock starts at t_on (its trigger note); it runs to t_off."""
    global OFF, SECONDS
    OFF, SECONDS = float(t_on), round(float(t_off) - float(t_on), 2)


def sample(fn, dt):
    t0, t1 = OFF, OFF + SECONDS
    n = int(round((t1 - t0) / dt))
    return [[round(i * dt, 3), round(float(fn(t0 + i * dt)), 3)] for i in range(n + 1)]


def rel(points):
    return [round(float(t) - OFF, 3) for t in points]


def write(name, body):
    est = [x for x in body.get('sources', []) if x.startswith('ESTIMATE')]
    if est:
        body['sources'] = [x for x in body['sources'] if not x.startswith('ESTIMATE')]
        body['note'] = (body.get('note', '') + ' ' + ' '.join(est)).strip()
    os.makedirs(P, exist_ok=True)
    with open(os.path.join(P, name + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(dict(name=name, kind='sfx', **body), fh, indent=1)
    print('wrote presets/sfx/' + name + '.json', f'({SECONDS} s from {OFF} s)')


def in_silence(t, edge=0.15):
    """-90 dB inside the declared second of nothing, with short edges so the room falls away instead of clicking."""
    a, b = T.SILENCE
    if a - edge <= t <= b + edge:
        k = min(1.0, (t - (a - edge)) / edge, ((b + edge) - t) / edge)
        return -90.0 * smooth(k)
    return 0.0


def window(t, a, b, fade=0.3):
    """0 dB inside [a, b], -90 outside, with raised-cosine edges `fade` s wide."""
    if t < a or t > b:
        return -90.0
    k = min(1.0, (t - a) / fade, (b - t) / fade)
    return -90.0 + 90.0 * smooth(k)


def traj(points):
    """keyframes from (t_s, azimuth, distance) triples; piece seconds."""
    return dict(spatial_role='mover', keyframes=[dict(t_s=round(t, 2), azimuth=a, distance=d) for t, a, d in points])


# ================================================================================================ the Hero's bike (single cylinder)
BIKE = T.hero_bike()
CAR = T.villain_car()
BIKE_F_IDLE = T.BIKE_IDLE * T.BIKE_CYL_FACTOR / 120.0       # 11.67 Hz at 1,400 rpm
CAR_F_IDLE = T.CAR_IDLE * T.CAR_CYL / 120.0                  # 46.7 Hz at 700 rpm


def speed_rel(drive, t):
    """Road speed relative to the top: rpm / (gear ratio x its top-gear value), 0 in neutral."""
    g = drive.gear_at(t)
    if not g:
        return 0.0
    return min(1.0, (drive.rpm_at(t) / drive.gears[g]) / (drive.limit / min(drive.gears.values())))


def bike_pitch(t):
    return BIKE.rpm_at(t) / T.BIKE_IDLE


def bike_gain_db(t):
    load = min(1.0, max(0.0, (BIKE.rpm_at(t) - T.BIKE_IDLE) / (T.BIKE_LIMIT - T.BIKE_IDLE)))
    g = -17.0 + 13.0 * load - 7.0 * BIKE.power_gap(t)          # an upshift cuts the ignition: the note dips
    g += window(t, 13.9, 116.6, 0.25) + in_silence(t)
    return max(-90.0, g)


def bike_aux_db(base, span, t, rise_rpm=2500.0):
    g = base + span * min(1.0, max(0.0, (BIKE.rpm_at(t) - rise_rpm) / (T.BIKE_LIMIT - rise_rpm)))
    return max(-90.0, g + window(t, 13.9, 116.6, 0.25) + in_silence(t))


def after_downshift_pops(drive):
    """Overrun pops: small bursts in the 0.15-0.6 s after a downshift (a closed throttle on a quickshifter bike)."""
    out = []
    for ts, _gap, d in drive.shifts:
        if d == 'down':
            out += [round(ts + 0.15 + 0.11 * k, 3) for k in range(4)]
    return out


begin(13.8, 118.0)
bike_down_pops = [t for t in after_downshift_pops(BIKE) if t < 116]
write('qf_bike', dict(
    character='A single-cylinder 155 cc sport bike followed from behind: one firing pulse per two revolutions through a short exhaust, its pitch following the rpm through six gears, a gap and a dip on every upshift, a blip and a burble on every downshift, and the valvetrain behind it.',
    seconds=SECONDS,
    note=f'f0 is the firing frequency rpm x 1 / 120 ({BIKE_F_IDLE:.2f} Hz at {T.BIKE_IDLE:.0f} rpm idle, {T.BIKE_LIMIT / 120:.1f} Hz at the {T.BIKE_LIMIT:.0f} limit); '
         'the pitch curve is rpm / idle rpm through the gears of timeline.hero_bike (a shift multiplies the rpm by the ratio of the new gear to the old, '
         'with a 90 ms power gap on an upshift and a 120 ms blip on a downshift). Gear ratios are one listing\'s six-speed set.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='firing', gain_db=-5.0, excite=dict(kind='periodic', f0=round(BIKE_F_IDLE, 3), harmonics=40, jitter=0.10, noise_mix=0.30),
             resonator=dict(kind='formant', formants=[[190, 100, 1.0], [430, 150, 0.85], [950, 320, 0.55], [2300, 800, 0.3]]),
             events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(bike_pitch, 0.05))], gain_db=[dict(kind='curve', points=sample(bike_gain_db, 0.05))])),
        dict(name='exhaust_body', gain_db=-13.0, excite=dict(kind='noise', color='brown'), resonator=dict(kind='bandpass', band=[60, 500], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: bike_gain_db(t) - 5.0, 0.1))])),
        dict(name='intake_rasp', gain_db=-27.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[1200, 4200], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: bike_aux_db(-38.0, 30.0, t), 0.1))])),
        dict(name='valvetrain', gain_db=-30.0, excite=dict(kind='impact', tau=0.0006), resonator=dict(kind='modal', law='bar', f1=2400.0, n=4, t60=0.05),
             events=dict(kind='poisson', rate=45.0, start=0.2),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: bike_gain_db(t) + 12.0, 0.1))])),
        dict(name='shift_clunk', gain_db=-14.0, excite=dict(kind='impact', tau=0.004), resonator=dict(kind='modal', law='bar', f1=170.0, n=4, t60=0.12),
             events=dict(kind='sequence', times=rel([s[0] for s in BIKE.shifts if OFF < s[0] < OFF + SECONDS]),
                         levels=[1.0] * len([s for s in BIKE.shifts if OFF < s[0] < OFF + SECONDS]))),
        dict(name='overrun_pops', gain_db=-16.0, excite=dict(kind='impact', tau=0.003), resonator=dict(kind='bandpass', band=[120, 900], order=2),
             events=dict(kind='sequence', times=rel(bike_down_pops), levels=[round(0.9 - 0.15 * (i % 4), 2) for i in range(len(bike_down_pops))])),
    ]),
    role='fx', gain_db=-2.0, reverb=0.04,
    spatial=dict(azimuth=0.0, elevation=30.0, distance=5.5, space=SPACE, binaural=True, kind='spot', trajectory=traj([
        (13.8, -10.0, 8.0), (21.6, -10.0, 8.0), (24.0, -5.0, 6.5), (36.0, -3.0, 5.5), (43.0, -3.0, 5.5), (44.4, -30.0, 4.2),
        (46.2, -3.0, 5.2), (58.0, 0.0, 5.0), (61.9, 0.0, 5.0), (64.0, 0.0, 5.5), (72.6, 5.0, 5.0), (73.6, 38.0, 4.0), (75.2, 5.0, 4.8),
        (88.0, 0.0, 4.6), (90.0, -22.0, 4.0), (97.0, 12.0, 4.3), (104.0, 0.0, 5.5), (107.0, -6.0, 6.0), (118.0, -8.0, 6.5)])),
    eq=[dict(type='hp', f=40.0), dict(type='lp', f=9500.0)],
    sources=['engine', 'ESTIMATE: the exhaust and intake formants, the gain curves and every level are starting values; the rev limiter (10,500 rpm) and the idle (1,400 rpm) '
             'are estimates (no source gave them); no recording of a bike was analysed']))

# ================================================================================================ the Villain's V8
CAR_ON, CAR_OFF = 24.0, 118.0


def car_pitch(t):
    return CAR.rpm_at(t) / T.CAR_IDLE


def car_gain_db(t):
    load = min(1.0, max(0.0, (CAR.rpm_at(t) - T.CAR_IDLE) / (T.CAR_LIMIT - T.CAR_IDLE)))
    g = -16.0 + 12.0 * load - 5.0 * CAR.power_gap(t)
    return max(-90.0, g + window(t, CAR_ON, 116.8, 0.5) + in_silence(t))


def car_aux_db(base, span, t, rise=2500.0):
    g = base + span * min(1.0, max(0.0, (CAR.rpm_at(t) - rise) / (T.CAR_LIMIT - rise)))
    return max(-90.0, g + window(t, CAR_ON, 116.8, 0.5) + in_silence(t))


begin(CAR_ON, CAR_OFF)
car_pops = [t for t in after_downshift_pops(CAR) if t < 116]
write('qf_v8', dict(
    character='A black V8 car behind and beside the camera: an uneven firing pulse (rpm x 8 / 120) through a big exhaust, its pitch following the rpm through six gears, a lope at idle, a burble on every downshift and the whole body heavier than the bike.',
    seconds=SECONDS,
    note=f'f0 is the firing frequency rpm x {T.CAR_CYL} / 120 ({CAR_F_IDLE:.1f} Hz at {T.CAR_IDLE:.0f} rpm idle, {T.CAR_LIMIT * T.CAR_CYL / 120:.0f} Hz at the {T.CAR_LIMIT:.0f} limit); '
         'the pitch curve is rpm / idle rpm through timeline.villain_car, a shift multiplies the rpm by the ratio of the new gear to the old.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='firing', gain_db=-5.0,
             excite=dict(kind='periodic', f0=round(CAR_F_IDLE, 2), harmonics=32, jitter=0.05, noise_mix=0.20, am_hz=5.5, am_depth=0.30),
             resonator=dict(kind='formant', formants=[[85, 60, 1.0], [160, 80, 0.9], [330, 120, 0.7], [700, 260, 0.45], [1500, 500, 0.2]]),
             events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(car_pitch, 0.05))], gain_db=[dict(kind='curve', points=sample(car_gain_db, 0.05))])),
        dict(name='exhaust_body', gain_db=-12.0, excite=dict(kind='noise', color='brown'), resonator=dict(kind='bandpass', band=[40, 420], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: car_gain_db(t) - 3.0, 0.1))])),
        dict(name='intake', gain_db=-22.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[700, 2600], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: car_aux_db(-40.0, 34.0, t), 0.1))])),
        dict(name='shift_clunk', gain_db=-16.0, excite=dict(kind='impact', tau=0.005), resonator=dict(kind='modal', law='bar', f1=120.0, n=4, t60=0.16),
             events=dict(kind='sequence', times=rel([s[0] for s in CAR.shifts if OFF < s[0] < OFF + SECONDS]),
                         levels=[1.0] * len([s for s in CAR.shifts if OFF < s[0] < OFF + SECONDS]))),
        dict(name='burble', gain_db=-14.0, excite=dict(kind='impact', tau=0.006), resonator=dict(kind='bandpass', band=[60, 500], order=2),
             events=dict(kind='sequence', times=rel(car_pops), levels=[round(0.95 - 0.12 * (i % 4), 2) for i in range(len(car_pops))])),
    ]),
    role='fx', gain_db=-2.0, reverb=0.05,
    spatial=dict(azimuth=178.0, elevation=0.0, distance=26.0, space=SPACE, binaural=True, kind='spot', trajectory=traj([
        (24.0, 172.0, 28.0), (30.0, 175.0, 22.0), (36.0, 172.0, 14.0), (48.0, 150.0, 8.0), (52.0, 125.0, 5.0), (58.0, 120.0, 4.0),
        (61.9, 150.0, 7.0), (64.0, 130.0, 6.0), (68.0, 100.0, 3.8), (72.0, 85.0, 3.2), (75.0, 140.0, 5.0), (82.0, 168.0, 7.0), (88.0, 172.0, 5.5),
        (94.0, 120.0, 3.4), (96.5, 70.0, 2.6), (99.0, 150.0, 4.5), (104.0, 175.0, 22.0), (110.0, 176.0, 30.0), (118.0, 176.0, 34.0)])),
    eq=[dict(type='hp', f=32.0), dict(type='lp', f=8000.0)],
    sources=['engine', 'ESTIMATE: gear ratios, formants and every level are starting values; no recording of a car was analysed']))

# ================================================================================================ the tyres
BIKE_SQUEALS = [(21.7, 22.7, 0.85, 1.15, -16.0), (43.5, 45.9, 1.0, 0.95, -9.0), (73.0, 75.3, 1.0, 0.9, -8.0), (89.6, 91.0, 1.0, 1.1, -11.0),
                (96.2, 97.8, 0.95, 1.05, -10.0)]
CAR_SQUEALS = [(55.4, 56.6, 0.9, 1.0, -12.0), (69.0, 70.6, 1.0, 0.92, -9.0), (94.7, 96.6, 0.9, 1.1, -7.0)]


def squeal_env_db(squeals, t):
    best = -90.0
    for a, b, _m0, _m1, peak in squeals:
        if a - 0.05 <= t <= b + 0.05:
            up = smooth((t - a + 0.05) / 0.12)
            down = 1.0 - smooth((t - (b - 0.15)) / 0.15)
            best = max(best, -90.0 + (peak + 90.0) * min(up, down))
    return best + in_silence(t)


def squeal_pitch(squeals, t):
    for a, b, m0, m1, _ in squeals:
        if a <= t <= b:
            return (m0 + (m1 - m0) * (t - a) / (b - a)) * (1.0 + 0.02 * math.sin(2 * math.pi * 7.0 * t))     # a slip wobble near 7 Hz
    return 1.0


def tyre_preset(name, squeals, f0, character, track_points, az, dist, hp):
    begin(squeals[0][0] - 0.05, squeals[-1][1] + 0.7)          # the stem gate listens to the first 0.5 s after the trigger: the first squeal is inside it
    write(name, dict(
        character=character, seconds=SECONDS,
        note=f'The tone is a pulse train at {f0:.0f} Hz with harmonics through a tyre-cavity resonance, wobbling near 7 Hz with the slip, over a scrub of noise; '
             'its pitch and level follow the slide (stick-slip: a self-excited oscillation at the contact, lateral creep the trigger).',
        model=dict(seconds=SECONDS, voices=[
            dict(name='squeal', gain_db=0.0, excite=dict(kind='periodic', f0=f0, harmonics=4, jitter=0.06, noise_mix=0.50),
                 resonator=dict(kind='formant', formants=[[f0 * 0.85, 300, 1.0], [f0 * 2.2, 600, 0.5]]), events=dict(kind='continuous'),
                 control=dict(pitch=[dict(kind='curve', points=sample(lambda t: squeal_pitch(squeals, t), 0.04))],
                              gain_db=[dict(kind='curve', points=sample(lambda t: squeal_env_db(squeals, t), 0.04))])),
            dict(name='scrub', gain_db=-12.0, excite=dict(kind='noise', color='white'), resonator=dict(kind='bandpass', band=[1500, 6500], order=2),
                 events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: squeal_env_db(squeals, t) - 4.0, 0.04))])),
        ]),
        role='fx', gain_db=-4.0, reverb=0.05,
        spatial=dict(azimuth=az, elevation=0.0, distance=dist, space=SPACE, binaural=True, kind='spot', trajectory=traj(track_points)),
        eq=[dict(type='hp', f=hp), dict(type='lp', f=9000.0)],
        sources=['tyre_squeal', 'ESTIMATE: the tone, its harmonics and the cavity formants are starting values (no source gave a tyre-squeal frequency); '
                 'the squeal times are the drift and corner moments of the picture']))


tyre_preset('qf_tyres_bike', BIKE_SQUEALS, 1400.0,
            'The Hero\'s tyres letting go: a narrow-tyre stick-slip tone near 1.4 kHz with its harmonics and a scrub of noise at the launch, the drift, the hard slide, the wall and the last corner.',
            [(21.2, -10.0, 8.0), (24.0, -5.0, 6.5), (43.0, -3.0, 5.0), (44.6, -42.0, 3.6), (45.9, -6.0, 5.0), (72.6, 5.0, 5.0), (73.6, 50.0, 3.4),
             (75.3, 6.0, 4.8), (89.4, -4.0, 4.6), (90.4, -26.0, 3.8), (91.2, 0.0, 4.6), (96.0, 10.0, 4.4), (97.0, 28.0, 3.6), (97.9, 6.0, 4.4)],
            55.0, 4.4, 420.0)
tyre_preset('qf_tyres_v8', CAR_SQUEALS, 900.0,
            'The Villain\'s wide tyres on a corner: a lower, broader stick-slip tone near 0.9 kHz and a heavier scrub, behind and beside the camera.',
            [(54.9, 140.0, 5.0), (55.9, 118.0, 4.0), (57.0, 125.0, 4.4), (68.5, 105.0, 4.0), (69.8, 82.0, 3.3), (71.2, 95.0, 3.8),
             (94.2, 128.0, 3.6), (95.6, 70.0, 2.6), (97.3, 120.0, 3.8)],
            105.0, 4.6, 300.0)

# ================================================================================================ the road and the wind (the camera at speed)
begin(21.5, 119.0)
write('qf_road', dict(
    character='The highway under the camera: tyre noise on asphalt and the wind of the Hero\'s speed, rising with the bike\'s road speed, gone in the declared second of silence.',
    seconds=SECONDS,
    note='The level follows the bike\'s relative road speed (rpm over gear ratio); the wind is a band of noise and the road a lower band; both stop in the second of silence.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='road', gain_db=-14.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[200, 3000], order=2),
             events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: (-48.0 + 32.0 * speed_rel(BIKE, t) ** 0.9 if t < 107.5 else -48.0 + 14.0 * smooth(1 - (t - 107.5) / 3.0))
                                                                      + window(t, 21.5, 118.6, 0.15) + in_silence(t), 0.2))])),
        dict(name='wind', gain_db=-20.0, excite=dict(kind='noise', color='white'), resonator=dict(kind='bandpass', band=[400, 6000], order=2),
             events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: (-56.0 + 40.0 * speed_rel(BIKE, t) ** 1.8 if t < 107.5 else -56.0)
                                                                      + window(t, 21.5, 118.6, 0.15) + in_silence(t), 0.2))])),
    ]),
    role='fx', gain_db=-16.0, reverb=0.1,
    spatial=dict(azimuth=105.0, elevation=15.0, distance=2.0, space=SPACE, binaural=True, kind='bed'),
    eq=[dict(type='hp', f=140.0), dict(type='lp', f=8000.0)],
    sources=['engine', 'ESTIMATE: road and wind levels are starting values; the speed is a ratio, not metres per second']))

# ================================================================================================ the truck
TRUCK_ON, TRUCK_OFF = 58.5, 62.0
TRUCK_PEAK = T.at(31, 1.0)             # 60.5: alongside


def truck_gain(t):
    k = (t - TRUCK_ON) / (TRUCK_PEAK - TRUCK_ON) if t < TRUCK_PEAK else (TRUCK_OFF - t) / (TRUCK_OFF - TRUCK_PEAK)
    return max(-90.0, -34.0 + 34.0 * smooth(k) ** 1.2 + in_silence(t))


def horn_gain(t):
    on, off = 59.9, 61.55
    if t < on or t > off:
        return -90.0
    return max(-90.0, -2.0 + in_silence(t) - 90.0 * (1.0 - smooth((off - t) / 0.08)) - 90.0 * (1.0 - smooth((t - on) / 0.03)))


begin(TRUCK_ON, TRUCK_OFF)
write('qf_truck', dict(
    character='A loaded truck coming up from behind and past the camera on its air horn: a six-cylinder diesel at about 1,400 rpm (firing rate rpm x 6 / 120), a double-note air horn on a minor third, and the pass of its own tyres.',
    seconds=SECONDS,
    note='The diesel f0 is rpm x 6 / 120 = 70 Hz at 1,400 rpm; the horn is two notes (311 and 391 Hz) with harmonics through a bell-like resonance; the camera moves relative to the truck on a trajectory, so the Doppler shift is the engine\'s, not an effect.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='diesel', gain_db=-4.0, excite=dict(kind='periodic', f0=70.0, harmonics=30, jitter=0.02),
             resonator=dict(kind='formant', formants=[[90, 60, 1.0], [250, 100, 0.7], [800, 300, 0.4]]), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(truck_gain, 0.05))])),
        dict(name='tyres', gain_db=-10.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[200, 3500], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: truck_gain(t) - 6.0, 0.05))])),
        dict(name='horn_low', gain_db=-5.0, excite=dict(kind='periodic', f0=311.0, harmonics=16, jitter=0.004, noise_mix=0.08),
             resonator=dict(kind='formant', formants=[[400, 150, 1.0], [1100, 300, 0.6], [2400, 700, 0.25]]), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(horn_gain, 0.02))])),
        dict(name='horn_high', gain_db=-6.5, excite=dict(kind='periodic', f0=391.0, harmonics=14, jitter=0.004, noise_mix=0.08),
             resonator=dict(kind='formant', formants=[[500, 160, 1.0], [1300, 320, 0.6], [2600, 700, 0.25]]), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(horn_gain, 0.02))])),
    ]),
    role='fx', gain_db=3.0, reverb=0.08,
    spatial=dict(azimuth=175.0, elevation=15.0, distance=40.0, space=SPACE, binaural=True, kind='spot', trajectory=traj([
        (58.5, 178.0, 40.0), (59.6, 170.0, 14.0), (60.2, 140.0, 5.0), (60.7, 90.0, 2.4), (61.3, 30.0, 6.0), (61.9, 5.0, 24.0)])),
    eq=[dict(type='hp', f=40.0), dict(type='lp', f=9000.0)],
    sources=['engine', 'ESTIMATE: horn notes, diesel formants and levels are starting values; no recording of a truck was analysed']))

# ================================================================================================ the radio
# (start, end): transmissions. Each has a squelch pop at the start, a carrier of unintelligible band-limited sound, a roger beep and a squelch tail at the end.
TX = [(6.4, 8.6), (25.6, 28.4), (31.2, 33.0), (105.6, 107.4), (109.0, 111.6)]
RADIO_ON, RADIO_OFF = 6.0, 112.0
begin(RADIO_ON, RADIO_OFF)


def tx_gate(t, pad=0.0):
    for a, b in TX:
        if a - pad <= t <= b + pad:
            return 0.0
    return -90.0


def beep_gate(t):
    for _a, b in TX:
        if b + 0.05 <= t <= b + 0.14:
            return 0.0
    return -90.0


def squelch_times():
    out = []
    for a, b in TX:
        out += [a, b + 0.16]
    return rel(out)


write('qf_walkie', dict(
    character='A hand-held two-way radio on the Villain\'s side of the story: a squelch pop opening each transmission, a clipped band-limited carrier that is voice-like but never words, a roger beep and a squelch tail closing it.',
    seconds=SECONDS,
    note='No speech is synthesised. The carrier is a pulse train near 140 Hz amplitude-modulated at 5.5 Hz (a syllable rate) with noise, through three formant bands and the telephone band, then driven hard; the squelch tail is the burst of static after a transmission ends; the beep is 1.2 kHz for 90 ms.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='carrier', gain_db=-3.0, excite=dict(kind='periodic', f0=140.0, harmonics=8, jitter=0.12, noise_mix=0.95, am_hz=5.5, am_depth=0.85),
             resonator=dict(kind='formant', formants=[[500, 130, 1.0], [1500, 300, 0.6], [2500, 500, 0.3]]), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -8.0 + tx_gate(t), 0.04))])),
        dict(name='static', gain_db=-14.0, excite=dict(kind='noise', color='white'), resonator=dict(kind='bandpass', band=[800, 3400], order=2), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -10.0 + tx_gate(t, 0.18), 0.04))])),
        dict(name='squelch', gain_db=-8.0, excite=dict(kind='noise', color='white', attack=0.006, tau=0.06), resonator=dict(kind='bandpass', band=[500, 3400], order=2),
             events=dict(kind='sequence', times=squelch_times(), levels=[1.0] * len(squelch_times()))),
        dict(name='roger_beep', gain_db=-9.0, excite=dict(kind='periodic', f0=1200.0, harmonics=2), resonator=dict(kind='none'), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -4.0 + beep_gate(t), 0.01))])),
    ]),
    role='fx', gain_db=-5.0, reverb=0.12,
    spatial=dict(azimuth=-155.0, elevation=0.0, distance=1.4, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=300.0), dict(type='lp', f=3400.0)],
    fx=[dict(type='pedalboard', plugin='Distortion', params=dict(drive_db=16.0))],
    sources=['walkie_talkie', 'ESTIMATE: the 300-3400 Hz band is the telephone band (no source gave the radio passband); every level and formant is a starting value']))

# ================================================================================================ the lab: alarm, hum, heartbeat
begin(0.0, 12.0)
ALARM_ON, ALARM_OFF = 0.8, 10.6


def alarm_pitch(t):
    return 1.0 + 0.34 * (0.5 + 0.5 * math.tanh(4.0 * math.sin(2 * math.pi * 1.7 * t)))   # two tones 520 / 700 Hz, a quick glide between them


def alarm_gain(t):
    """A lab alarm: three short beeps a second (0.12 s on, 0.12 off), in the window the story gives it, fading as the Hero leaves."""
    ph = t % 1.0
    beep = 0.0 if (ph < 0.12 or 0.24 <= ph < 0.36 or 0.48 <= ph < 0.60) else -90.0
    return max(-90.0, -12.0 + beep + window(t, ALARM_ON, ALARM_OFF, 0.05) - 14.0 * smooth((t - 8.0) / 2.6))


write('qf_alarm', dict(
    character='A lab alarm in a small hard room: three short 1 kHz beeps a second that keep going while the first minute of the story happens, with the 50 Hz hum of the building under it, both fading as the Hero leaves.',
    seconds=SECONDS,
    note='The klaxon is a pulse train with ten harmonics at 520 Hz and a glide to 700 Hz at 1.7 cycles a second; the hum is the 50 Hz mains and its harmonics.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='klaxon', gain_db=0.0, excite=dict(kind='periodic', f0=1000.0, harmonics=3, jitter=0.002),
             resonator=dict(kind='formant', formants=[[600, 300, 1.0], [1800, 600, 0.4]]), events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(alarm_gain, 0.01))])),
        dict(name='hum', gain_db=-30.0, excite=dict(kind='periodic', f0=50.0, harmonics=8, jitter=0.0), resonator=dict(kind='formant', formants=[[100, 60, 1.0], [250, 100, 0.5]]),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -4.0 - 24.0 * smooth((t - 9.0) / 3.0), 0.1))])),
    ]),
    role='fx', gain_db=-6.0, reverb=0.3,
    spatial=dict(azimuth=-150.0, elevation=50.0, distance=4.0, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=60.0), dict(type='lp', f=7000.0)],
    sources=['walkie_talkie', 'ESTIMATE: alarm notes and the hum level are starting values; no recording of an alarm was analysed']))


def beats(t0, t1, bpm0, bpm1):
    """Heartbeat times: a lub every 60 / bpm seconds with the bpm moving linearly from bpm0 to bpm1; a dub 0.28 s after each lub."""
    t, out = t0, []
    while t < t1:
        out.append(round(t, 3))
        bpm = bpm0 + (bpm1 - bpm0) * (t - t0) / max(1e-9, t1 - t0)
        t += 60.0 / bpm
    return out


HB1 = beats(3.0, 12.0, 62.0, 100.0)
HB2 = beats(104.4, 118.6, 74.0, 46.0)
begin(3.0, 118.8)
lubs = rel(HB1 + HB2)
dubs = rel([x + 0.28 for x in HB1 + HB2])
write('qf_heartbeat', dict(
    character='The Hero\'s pulse, close and low: a lub and a dub that speed up in the lab and fall away again at the end, because the story ends on a held breath.',
    seconds=SECONDS,
    note='Two soft low thumps per beat (a membrane at 55 Hz), 0.28 s apart; the rate rises from 62 to 100 beats a minute in the lab and falls from 74 to 46 in the last fifteen seconds.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='lub', gain_db=-4.0, excite=dict(kind='impact', tau=0.012), resonator=dict(kind='modal', law='membrane', f1=55.0, n=3, t60=0.22),
             events=dict(kind='sequence', times=lubs, levels=[1.0] * len(lubs))),
        dict(name='dub', gain_db=-9.0, excite=dict(kind='impact', tau=0.012), resonator=dict(kind='modal', law='membrane', f1=62.0, n=3, t60=0.18),
             events=dict(kind='sequence', times=dubs, levels=[0.8] * len(dubs))),
    ]),
    role='fx', gain_db=-9.0, reverb=0.02,
    spatial=dict(azimuth=0.0, elevation=-15.0, distance=0.9, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=30.0), dict(type='lp', f=400.0)],
    sources=['engine', 'ESTIMATE: the membrane frequency, the beat rates and the levels are starting values']))

# ================================================================================================ the device
begin(8.4, 119.9)
DEV = [(8.4, 11.6, -30.0), (110.5, 119.3, -12.0)]         # ends before the file does: an amplitude-modulated tail dips under the dropout floor


def dev_gain(t):
    best = -90.0
    for a, b, peak in DEV:
        if a <= t <= b:
            up = smooth((t - a) / 0.25 + 0.0)
            down = 1.0 - smooth((t - (b - 0.5)) / 0.5)
            best = max(best, -90.0 + (peak + 90.0) * min(up, down))
    return best + in_silence(t)


def dev_pitch(t):
    if t < 12.0:
        return 1.0 + 0.04 * (t - 8.4)
    return 1.0 + 0.35 * smooth((t - 110.5) / 8.0)


write('qf_device', dict(
    character='The device that controls people, heard once in the lab and once at the end: a sub pulse under a thin carrier near 3 kHz that wobbles at 7.5 Hz and creeps upward, never resolving.',
    seconds=SECONDS,
    note='A 41 Hz tone with a slow 1 Hz swell, and a carrier at 1.85 kHz amplitude-modulated at 7.5 Hz; the carrier rises by a third of an octave over the last nine seconds; the cue is not a signal to any real system.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='sub', gain_db=-6.0, excite=dict(kind='periodic', f0=41.0, harmonics=3, jitter=0.0, am_hz=1.0, am_depth=0.5), resonator=dict(kind='none'),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: dev_gain(t) - 4.0, 0.1))])),
        dict(name='carrier', gain_db=-14.0, excite=dict(kind='periodic', f0=1850.0, harmonics=4, jitter=0.08, noise_mix=0.85, am_hz=7.5, am_depth=0.6), resonator=dict(kind='none'),
             events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(dev_gain, 0.1))])),
    ]),
    role='fx', gain_db=-6.0, reverb=0.25,
    spatial=dict(azimuth=-30.0, elevation=45.0, distance=3.0, space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=30.0), dict(type='lp', f=9500.0)],
    sources=['walkie_talkie', 'ESTIMATE: the pulse and carrier frequencies and the levels are starting values']))
