#!/usr/bin/env python3
"""make_presets_sound.py - writes the physical sounds of Night Pursuit as presets: the car, the tyres, the sirens, the wipers, the crash,
the rain and the city.

Nothing here makes a sound. Each preset is a sound model (excitation -> resonator -> time process, scripts/sound_model.py) or a layered
environment; this script only fills in the curves that depend on the story's clock (the rpm through the gears, the sirens' sweeps, the
moments the squeal and the wipers happen) from `timeline.py`, and writes the JSON. The physical relations it uses are written next to
the number: the firing frequency of a four-stroke engine is rpm x cylinders / 120, and road speed is 2 pi r rpm / (60 G).
Every number without a source is a starting value, as the research note says.
"""
import json
import math
import os

import timeline as T
from staging import STAGE

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, '..', 'presets')
TM = T.tempo_map()
START = T.sfx_start()
DUR = float(T.seconds(T.END_BAR, 0, TM))
END = round(DUR + 1.0, 1)
SECONDS = END
SPACE = 'np_street_canyon'


def sec(bar, beat=0.0):
    return float(T.seconds(bar, beat, TM))


A = sec(T.start('the_avenue'))                       # launch
T_SPOT = sec(T.start('spotted') + 1, 2)
T_TURN = sec(T.start('the_turn'))
T_DRIFT, T_SNAP = sec(T.SLOMO_DRIFT['bar']), sec(T.SNAP_DRIFT)
T_UNDER = sec(T.start('under_the_bridge'))
T_ROAD = sec(T.start('the_roadblock'))
T_SPIN, T_CRASH = sec(T.SLOMO_SPIN['bar']), sec(T.CRASH_BAR)
T_BRIDGE = sec(T.start('the_bridge'))
T_CUT = sec(T.CUT_BAR)
SLOMO = [(T_DRIFT, T_SNAP), (T_SPIN, T_CRASH)]
SLOMO_RAMP_S = 3.0                                   # a slowdown falls over this long and then holds until the snap

# the research note: car_engine_v8
CYL, IDLE_RPM, REDLINE = 8, 800.0, 7000.0
GEARS = {0: None, 1: 3.6, 2: 2.2, 3: 1.5, 4: 1.1}    # starting values: a sports-car box, no source for a particular car
FINAL_DRIVE, TYRE_R = 3.7, 0.33                      # starting values; 0.33 m is a loaded radius of a 255/40-18 tyre


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def dive(t, depth=0.5):
    """The slow-motion factor on pitch: 1 outside, falls to `depth` over SLOMO_RAMP_S, holds to the snap, snaps back."""
    for a, b in SLOMO:
        if a <= t < b:
            return 1.0 - (1.0 - depth) * smooth((t - a) / SLOMO_RAMP_S)
    return 1.0


def slowness(t):
    return 1.0 - dive(t, 0.0)                        # 0 outside, up to 1 deep in the slow motion


OFF = 0.0                                            # the piece second the current effect's own clock starts at (its trigger note)


def sample(fn, t0, t1, dt):
    t0, t1 = max(t0, OFF), min(t1, END)
    n = int(round((t1 - t0) / dt))
    return [[round(t0 - OFF + i * dt, 3), round(float(fn(t0 + i * dt)), 4)] for i in range(n + 1)]


def rel(points):
    return [[round(t - OFF, 3), v] for t, v in points]


def begin(name):
    global OFF, SECONDS
    OFF = START[name]
    SECONDS = round(DUR + 1.0 - OFF, 1)
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
    """The fx chain that muffles a stem inside each slow-motion window: a low-pass that closes, a hold, and the dry sound back at the
    snap, with an optional dip in level. Times are stem time."""
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


# ================================================================================================ the hero car
# (t, rpm, gear): the driving written as the driver does it. A shift is two waypoints a tenth of a second apart; the rpm after a shift is the rpm
# before it times the ratio of the gears (so the engine's pitch follows the gearbox, not an invented curve).
def rpm_waypoints():
    r = lambda g0, g1, x: x * GEARS[g1] / GEARS[g0]                      # noqa: E731
    W = [(0.0, 800, 0), (T_SPOT - 0.1, 800, 0), (T_SPOT + 0.4, 2600, 0), (T_SPOT + 1.3, 800, 0), (A - 0.2, 800, 0), (A, 900, 1),
         (A + 2.0, 6400, 1), (A + 2.12, r(1, 2, 6400), 2), (A + 4.6, 6200, 2), (A + 4.72, r(2, 3, 6200), 3), (A + 9.0, 5200, 3), (A + 12.5, 4300, 3),
         (A + 14.0, 3000, 3), (A + 14.2, r(3, 2, 3000), 2), (A + 16.0, 5600, 2), (A + 16.12, r(2, 3, 5600), 3), (A + 22.0, 5400, 3), (T_TURN, 5000, 3),
         (T_TURN + 6.0, 5800, 3), (T_DRIFT - 1.0, 5600, 3), (T_DRIFT, 6600, 3), (T_DRIFT + 2.5, 6000, 3), (T_SNAP - 0.3, 5600, 3), (T_SNAP, 5200, 3),
         (T_SNAP + 3.0, 6200, 3), (T_UNDER - 0.5, 6000, 3), (T_UNDER + 8.0, 6300, 3), (T_ROAD - 4.0, 6000, 3), (T_ROAD + 6.0, 5000, 3),
         (T_ROAD + 8.0, 3000, 3), (T_ROAD + 8.2, 6800, 0), (T_ROAD + 10.5, 6800, 0), (T_ROAD + 10.7, 3900, 2), (T_ROAD + 14.0, 6200, 2),
         (T_ROAD + 14.12, r(2, 3, 6200), 3), (T_SPIN + 2.0, 6000, 3), (T_CRASH + 1.0, 5200, 3), (T_BRIDGE - 0.5, 6200, 3), (T_BRIDGE + 0.0, 6200, 3),
         (T_BRIDGE + 0.12, r(3, 4, 6200), 4), (T_BRIDGE + 10.0, 5600, 4), (T_CUT - 0.05, 5800, 4)]
    return W


def speed(gear, rpm):
    return 0.0 if not gear else 2.0 * math.pi * TYRE_R * rpm / (60.0 * GEARS[gear] * FINAL_DRIVE)       # m/s


def at_waypoints(W, t):
    if t <= W[0][0]:
        return W[0][1], W[0][2]
    for (t0, r0, g0), (t1, r1, g1) in zip(W, W[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / max(1e-9, t1 - t0)
            return r0 + (r1 - r0) * u, (g0 if u < 0.5 else g1)
    return W[-1][1], W[-1][2]


W = rpm_waypoints()


def rpm_at(t):
    return at_waypoints(W, t)[0]


def v_at(t):
    r, g = at_waypoints(W, t)
    return speed(g, r) * (1.0 - 0.0 * slowness(t))


def engine_pitch(t):
    """Multiplier on the idle firing frequency: rpm / idle rpm (f = rpm x 8 / 120 is 53.3 Hz at idle), with the slow-motion dive."""
    return rpm_at(t) / IDLE_RPM * dive(t, 0.5)


def engine_gain_db(t):
    return _engine_gain_db(t) + (-90.0 + 90.0 * smooth((t - OFF) / 0.4) if t - OFF < 0.4 else 0.0)


def _engine_gain_db(t):
    if t >= T_CUT:
        return -90.0 if t > T_CUT + 0.04 else -90.0 * (t - T_CUT) / 0.04
    load = min(1.0, max(0.0, (rpm_at(t) - IDLE_RPM) / 5800.0))
    return -15.0 + 12.0 * load - 4.0 * slowness(t)


def road_db(t):
    v = v_at(t) * (1.0 - 0.5 * slowness(t))
    return (-90.0 if t >= T_CUT else -52.0 + 40.0 * min(1.0, v / 40.0) ** 0.8)


def spray_db(t):
    v = v_at(t)
    return (-90.0 if t >= T_CUT else -58.0 + 46.0 * min(1.0, v / 40.0) ** 2.0)


SHIFT_TIMES = [round(a, 3) for (a, _, g0), (b, _, g1) in zip(W, W[1:]) if g0 != g1 and g0 and g1 and 0 < b - a < 0.3]
f_idle = IDLE_RPM * CYL / 120.0

begin('engine')
write('sfx', 'np_engine', dict(
    kind='sfx',
    character='A V8 in a car the listener sits in: a firing-frequency pulse train through the body, its pitch following the rpm through four gears, with the road and the spray behind it and the clunk of each shift; it dives in the slow motion and stops dead at the cut.',
    seconds=SECONDS,
    note=f'f0 is the firing frequency rpm x {CYL} / 120 ({f_idle:.1f} Hz at {IDLE_RPM:.0f} rpm idle); the pitch curve is rpm / idle rpm through the gears of the waypoints in make_presets_sound.py, '
         'the road speed is 2 pi r rpm / (60 G) with G the box ratio times a 3.7 final drive and r = 0.33 m, and the slow motion drops the pitch an octave until the snap.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='firing', gain_db=-6.0,
             excite=dict(kind='periodic', f0=round(f_idle, 2), harmonics=40, jitter=0.02),
             resonator=dict(kind='formant', formants=[[110, 70, 1.0], [240, 90, 0.9], [680, 240, 0.5], [1500, 500, 0.2]]),
             events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(engine_pitch, 0.0, END, 0.1))],
                          gain_db=[dict(kind='curve', points=sample(engine_gain_db, 0.0, END, 0.1))])),
        dict(name='exhaust_noise', gain_db=-12.0, excite=dict(kind='noise', color='brown'), resonator=dict(kind='bandpass', band=[50, 900], order=2),
             events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: engine_gain_db(t) - 4.0, 0.0, END, 0.2))])),
        dict(name='intake', gain_db=-22.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[900, 2800], order=2),
             events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -40.0 + 36.0 * min(1.0, max(0.0, (rpm_at(t) - 2500.0) / 4000.0)) if t < T_CUT else -90.0, 0.0, END, 0.2))])),
        dict(name='road', gain_db=-14.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[300, 3500], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(road_db, 0.0, END, 0.2))])),
        dict(name='spray', gain_db=-20.0, excite=dict(kind='noise', color='white'), resonator=dict(kind='bandpass', band=[2500, 9000], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(spray_db, 0.0, END, 0.2))])),
        dict(name='shift_clunk', gain_db=-18.0, excite=dict(kind='impact', tau=0.004),
             resonator=dict(kind='modal', law='bar', f1=140.0, n=4, t60=0.18),
             events=dict(kind='sequence', times=[round(t - OFF, 3) for t in SHIFT_TIMES], levels=[1.0] * len(SHIFT_TIMES))),
        dict(name='cabin_tone', gain_db=-26.0, excite=dict(kind='noise', color='brown'), resonator=dict(kind='bandpass', band=[60, 400], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: -50.0 if t < T_CUT else -16.0 - 4.0 * smooth((t - T_CUT) / 20.0), 0.0, END, 0.25))])),
        dict(name='cooling_tick', gain_db=-20.0, excite=dict(kind='impact', tau=0.0008),
             resonator=dict(kind='modal', law='bar', f1=1800.0, n=6, t60=0.12),
             events=dict(kind='poisson', rate=0.8, start=round(T_CUT + 1.2 - OFF, 2))),
    ]),
    role='fx', gain_db=-3.0, reverb=0.02,
    spatial=dict(azimuth=STAGE['np_engine'][0], elevation=STAGE['np_engine'][1], distance=STAGE['np_engine'][2], space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=30.0), dict(type='lp', f=9000.0)],
    fx=slowmo_fx(900.0, -2.0),
    sources=['car_engine_v8',
             'ESTIMATE: gear ratios, final drive, tyre radius, the body formants and every level are starting values; no recording of an engine was measured']))

# ================================================================================================ the tyres
# (start, end, pitch multiplier at start and end, peak dB): wheelspin chirp, the drift, the handbrake turn, two curves on the bridge
SQUEALS = [(A + 0.1, A + 1.8, 0.8, 1.15, -14.0), (T_DRIFT - 0.9, T_SNAP, 1.0, 1.0, -8.0), (T_ROAD + 8.4, T_ROAD + 10.6, 0.9, 1.25, -7.0),
           (T_BRIDGE + 5.0, T_BRIDGE + 6.4, 0.95, 1.1, -16.0), (T_BRIDGE + 13.0, T_BRIDGE + 14.4, 0.95, 1.1, -15.0)]


def squeal_env_db(t):
    best = -90.0
    for a, b, _, _, peak in SQUEALS:
        if a - 0.05 <= t <= b + 0.05:
            up = smooth((t - a) / 0.35)
            down = 1.0 - smooth((t - (b - 0.1)) / 0.1)
            amp = min(up, down)
            best = max(best, -90.0 + (peak + 90.0) * amp)
    return best - 6.0 * slowness(t)


def squeal_pitch(t):
    for a, b, m0, m1, _ in SQUEALS:
        if a <= t <= b:
            base = m0 + (m1 - m0) * (t - a) / (b - a)
            return base * dive(t, 0.5) * (1.0 + 0.05 * math.sin(2 * math.pi * 7.0 * t))        # a slip wobble of about 7 Hz
    return 1.0


begin('tyres')
write('sfx', 'np_drift_squeal', dict(
    kind='sfx',
    character='Tyres losing grip on a wet road: a stick-slip tone near 1 kHz with its harmonics and a scrub of noise, rising and falling with the slip, diving in the slow motion and cutting off when the tyres bite.',
    seconds=SECONDS,
    note='The tone is a pulse train at 1.1 kHz (the squeal band the research found, 500-1500 Hz with energy to several kHz) through a tyre-cavity resonance; wet grip is about 20 % below dry, so the level is below a dry squeal.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='squeal', gain_db=0.0, excite=dict(kind='periodic', f0=1100.0, harmonics=8, jitter=0.03, noise_mix=0.12),
             resonator=dict(kind='formant', formants=[[900, 300, 1.0], [2400, 600, 0.5]]), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(squeal_pitch, 0.0, END, 0.05))],
                          gain_db=[dict(kind='curve', points=sample(squeal_env_db, 0.0, END, 0.05))])),
        dict(name='scrub', gain_db=-10.0, excite=dict(kind='noise', color='white'), resonator=dict(kind='bandpass', band=[1500, 6500], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: squeal_env_db(t) - 4.0, 0.0, END, 0.05))])),
    ]),
    role='fx', gain_db=-4.0, reverb=0.05,
    spatial=dict(azimuth=-150.0, elevation=0.0, distance=1.7, space=SPACE, binaural=True, kind='spot', trajectory=dict(
        spatial_role='mover', doppler_strength=0.0,
        keyframes=[dict(bar=1, azimuth=-150.0, distance=1.7),
                   dict(t_s=round(T_DRIFT - 1.0, 2), azimuth=-150.0, distance=1.7), dict(t_s=round((T_DRIFT + T_SNAP) / 2, 2), azimuth=-180.0, distance=1.9),
                   dict(t_s=round(T_SNAP, 2), azimuth=-210.0, distance=1.7), dict(t_s=round(T_ROAD + 8.0, 2), azimuth=-210.0, distance=1.7),
                   dict(t_s=round(T_ROAD + 9.5, 2), azimuth=-290.0, distance=1.8), dict(t_s=round(T_ROAD + 11.0, 2), azimuth=-330.0, distance=1.7),
                   dict(t_s=round(T_BRIDGE, 2), azimuth=-330.0, distance=1.7)])),
    eq=[dict(type='hp', f=400.0), dict(type='lp', f=9000.0)],
    fx=slowmo_fx(2500.0, 0.0),
    sources=['tyre_squeal_wet', 'ESTIMATE: the tone, its harmonics and the cavity formants are starting values; wet friction 20 % under dry is from the research note']))

# ================================================================================================ the wipers
def wiper_times():
    """One cycle is a sweep up and a sweep back; 70 cycles a minute (the research: highest speed about 70 double strokes). Slow motion stretches
    the interval, so the wipers fall behind with the music and catch up at the snap."""
    base = 60.0 / 70.0 / 2.0
    out, t = [], 1.35
    while t < T_CUT:
        out.append(round(t, 3))
        t += base * (1.0 + 1.0 * slowness(t))
    return out


WT = wiper_times()
begin('wipers')
write('sfx', 'np_wipers', dict(
    kind='sfx',
    character='Windscreen wipers on a wet screen: a swish of rubber on glass every half cycle and a soft thump at each turn, 70 cycles a minute, slowing in the slow motion.',
    seconds=SECONDS,
    note='One sweep every 0.43 s (70 double strokes a minute); the interval grows up to four times in the slow motion.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='swish', gain_db=0.0, excite=dict(kind='noise', color='pink', attack=0.07, tau=0.14), resonator=dict(kind='bandpass', band=[900, 4500], order=2),
             events=dict(kind='sequence', times=[round(t - OFF, 3) for t in WT], levels=[1.0] * len(WT))),
        dict(name='turn_thump', gain_db=-9.0, excite=dict(kind='impact', tau=0.006), resonator=dict(kind='modal', law='bar', f1=95.0, n=3, t60=0.08),
             events=dict(kind='sequence', times=[round(t + 0.2 - OFF, 3) for t in WT], levels=[1.0] * len(WT))),
        dict(name='wet_glass', gain_db=-22.0, excite=dict(kind='noise', color='pink'), resonator=dict(kind='bandpass', band=[1500, 6000], order=2),
             events=dict(kind='continuous'), control=dict(gain_db=[dict(kind='curve', points=sample(lambda t: (-90.0 + 78.0 * smooth((t - OFF) / 0.15)) if t < T_CUT else -90.0, 0.0, END, 0.25))])),
    ]),
    role='fx', gain_db=-8.0, reverb=0.0,
    spatial=dict(azimuth=STAGE['np_wipers'][0], elevation=STAGE['np_wipers'][1], distance=STAGE['np_wipers'][2], space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=250.0), dict(type='lp', f=7000.0)],
    sources=['wiper_blades', 'ESTIMATE: the swish band, the thump and the levels are starting values; the rate is from FMVSS 104 and service data in the research note']))

# ================================================================================================ the sirens
def wail(t, lo=600.0, hi=1400.0, cpm=20.0):
    """The wail: a slow sweep between lo and hi at cpm cycles a minute (the NIJ example is 20); the pitch multiplier on `lo`."""
    return 1.0 + (hi / lo - 1.0) * (0.5 - 0.5 * math.cos(2 * math.pi * t * cpm / 60.0))


def yelp(t, lo=700.0, hi=1500.0, cpm=240.0):
    """The yelp: the same sweep, fast (the NIJ example is 240 cycles a minute)."""
    return 1.0 + (hi / lo - 1.0) * (0.5 - 0.5 * math.cos(2 * math.pi * t * cpm / 60.0))


def hilo(t, low=435.0, high=580.0, cpm=55.0):
    """The two-tone pattern: 435 / 580 Hz at 50-60 cycles a minute (a European pattern in a patent); a 25 ms glide between the tones."""
    phase = (t * cpm / 60.0) % 1.0
    k = smooth(min(1.0, phase / 0.03)) if phase < 0.5 else 1.0 - smooth(min(1.0, (phase - 0.5) / 0.03))
    return (low + (high - low) * k) / low


def gate_db(t, t_on, t_off, occl, fade=0.5):
    # fade: seconds the siren takes to come in and go out
    """0 dB while the siren is present, -90 outside; `occl` windows are behind an obstacle: -9 dB and a muffled tone (the lowpass is in the fx chain)."""
    if t < t_on or t > t_off:
        return -90.0
    edge = min(1.0, (t - t_on) / fade, (t_off - t) / fade)
    g = -90.0 + 90.0 * smooth(edge)
    for a, b in occl:
        if a <= t <= b:
            g -= 9.0 * smooth(min(1.0, (t - a) / 0.4, (b - t) / 0.4))
    return g


OCC1 = [(T_DRIFT - 2.5, T_DRIFT + 3.0)]                          # behind the corner building as the car turns into the side street
OCC2 = [(T_UNDER + 4.0, T_UNDER + 7.0), (T_ROAD + 18.0, T_ROAD + 20.0)]       # behind the pillars of the underpass, behind the barrier


def occlusion_fx(windows, cutoff=900.0):
    chain = []
    for a, b in windows:
        chain += [dict(type='filter_sweep', kind='lowpass', f_start_hz=12000.0, f_end_hz=cutoff, q=0.7, start_s=round(a, 3), end_s=round(a + 0.5, 3), after='bypass', edge_ms=10.0),
                  dict(type='filter_sweep', kind='lowpass', f_start_hz=cutoff, f_end_hz=cutoff, q=0.7, start_s=round(a + 0.5, 3), end_s=round(b - 0.5, 3), after='bypass', edge_ms=10.0),
                  dict(type='filter_sweep', kind='lowpass', f_start_hz=cutoff, f_end_hz=12000.0, q=0.7, start_s=round(b - 0.5, 3), end_s=round(b, 3), after='bypass', edge_ms=10.0)]
    return chain


S1_ON, S1_OFF = 4.0, T_CUT
S1_FAR_ON, S1_FAR_OFF = T_CUT + 2.5, SECONDS - 0.5          # the one far siren left at the cliff
S2_ON, S2_OFF = T_TURN + 0.1, T_CUT


def siren1_pitch(t):
    return wail(t) * dive(t, 0.7)


def siren1_gain(t):
    return max(gate_db(t, S1_ON, S1_OFF, OCC1), gate_db(t, S1_FAR_ON, S1_FAR_OFF, [], fade=1.5) - 6.0) - 3.0 * slowness(t)


begin('siren_first')
write('sfx', 'np_siren_wail', dict(
    kind='sfx',
    character='A police siren in wail: a slow sweep between 600 and 1400 Hz at 20 cycles a minute, harmonics to six, the first cruiser; it moves round the car (Doppler from its path) and is muffled behind the corner building.',
    seconds=SECONDS,
    note='600-1400 Hz sits inside the 500-1800 Hz band reported for SAE J1849; 20 cycles a minute is the NIJ example for a wail. The pitch is dropped a little in the slow motion.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='wail', gain_db=0.0, excite=dict(kind='periodic', f0=600.0, harmonics=6, jitter=0.002),
             resonator=dict(kind='none'), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(siren1_pitch, S1_ON, END, 0.1))],
                          gain_db=[dict(kind='curve', points=sample(siren1_gain, 0.0, END, 0.1))])),
    ]),
    role='fx', gain_db=-9.0, reverb=0.10,
    spatial=dict(azimuth=-30.0, elevation=0.0, distance=90.0, space=SPACE, binaural=True, kind='spot', trajectory=dict(
        spatial_role='mover', doppler_strength=1.0,
        keyframes=[dict(bar=1, azimuth=-30.0, distance=90.0), dict(section='spotted', azimuth=-35.0, distance=45.0), dict(t_s=round(T_SPOT, 2), azimuth=-20.0, distance=28.0),
                   dict(section='the_avenue', azimuth=-160.0, distance=26.0), dict(section='the_turn', azimuth=-150.0, distance=22.0),
                   dict(t_s=round(T_DRIFT, 2), azimuth=-110.0, distance=11.0), dict(t_s=round(T_SNAP, 2), azimuth=-95.0, distance=9.0),
                   dict(section='under_the_bridge', azimuth=175.0, distance=24.0), dict(section='the_roadblock', azimuth=160.0, distance=40.0),
                   dict(section='the_bridge', azimuth=150.0, distance=80.0), dict(section='the_cliff', azimuth=-40.0, distance=160.0)])),
    eq=[dict(type='hp', f=300.0), dict(type='lp', f=8000.0)],
    fx=occlusion_fx(OCC1, 900.0) + slowmo_fx(2500.0, 0.0),
    sources=['police_siren', 'ESTIMATE: the exact J1849 tables were not read; the sweep limits, six harmonics and the levels are starting values']))


def siren2_pitch(t):
    if t < T_ROAD:
        return hilo(t) * 600.0 / 600.0 * (435.0 / 600.0)         # relative to f0 = 600 Hz: 435 Hz low tone, 580 Hz high
    return yelp(t) * (700.0 / 600.0)


def siren2_gain(t):
    return gate_db(t, S2_ON, S2_OFF, OCC2, fade=0.12) - 3.0 * slowness(t)


begin('siren_second')
write('sfx', 'np_siren_second', dict(
    kind='sfx',
    character='The second cruiser: a two-tone 435/580 Hz hi-lo at 55 cycles a minute while it joins, then a fast yelp from 700 to 1500 Hz at 240 cycles a minute once the roadblock is close; it never shares a pitch with the first.',
    seconds=SECONDS,
    note='The European two-tone pattern (435/580 Hz at 50-60 per minute) and the NIJ yelp (240 per minute); the car switches pattern at the roadblock.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='second', gain_db=0.0, excite=dict(kind='periodic', f0=600.0, harmonics=6, jitter=0.002),
             resonator=dict(kind='none'), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(lambda t: (hilo(t) * 435.0 / 600.0) if t < T_ROAD else yelp(t) * 700.0 / 600.0, S2_ON, S2_OFF + 0.2, 0.02))],
                          gain_db=[dict(kind='curve', points=sample(siren2_gain, 0.0, END, 0.1))])),
    ]),
    role='fx', gain_db=-10.0, reverb=0.10,
    spatial=dict(azimuth=60.0, elevation=0.0, distance=70.0, space=SPACE, binaural=True, kind='spot', trajectory=dict(
        spatial_role='mover', doppler_strength=1.0,
        keyframes=[dict(bar=1, azimuth=60.0, distance=70.0), dict(section='the_turn', azimuth=60.0, distance=70.0), dict(section='under_the_bridge', azimuth=100.0, distance=14.0),
                   dict(section='the_roadblock', azimuth=20.0, distance=30.0), dict(t_s=round(T_ROAD + 8.0, 2), azimuth=35.0, distance=14.0),
                   dict(t_s=round(T_ROAD + 16.0, 2), azimuth=-10.0, distance=12.0), dict(section='the_bridge', azimuth=120.0, distance=20.0),
                   dict(t_s=round(T_CUT - 1.0, 2), azimuth=150.0, distance=60.0)])),
    eq=[dict(type='hp', f=300.0), dict(type='lp', f=8000.0)],
    fx=occlusion_fx(OCC2, 700.0) + slowmo_fx(2500.0, 0.0),
    sources=['police_siren', 'ESTIMATE: the two patterns and their levels are starting values; the hi-lo pair is from a patent summary, not read in full']))

# ================================================================================================ the crash
def cruiser_squeal_pitch(t):
    return (1.0 - 0.35 * smooth((t - T_SPIN) / (T_CRASH - T_SPIN))) * dive(t, 0.6) if T_SPIN <= t <= T_CRASH else 1.0


def cruiser_squeal_gain(t):
    if T_SPIN <= t <= T_CRASH:
        return -14.0 + 8.0 * smooth((t - T_SPIN) / 2.0) - 90.0 * smooth((t - (T_CRASH - 0.05)) / 0.05)
    return -90.0


begin('crash')
write('sfx', 'np_crash', dict(
    kind='sfx',
    character='A cruiser losing the road and hitting the barrier: its tyres squealing down in the slow motion, then one impact on a damped panel, a tear of metal and the tinkle of glass.',
    seconds=SECONDS,
    note='A collision is a short impact, a tearing tail and glass (the research note); the panel is a modal plate, the glass the existing glass_break laws; every level is a starting value.',
    model=dict(seconds=SECONDS, voices=[
        dict(name='cruiser_squeal', gain_db=0.0, excite=dict(kind='periodic', f0=950.0, harmonics=8, jitter=0.03, noise_mix=0.15),
             resonator=dict(kind='formant', formants=[[800, 300, 1.0], [2200, 600, 0.5]]), events=dict(kind='continuous'),
             control=dict(pitch=[dict(kind='curve', points=sample(cruiser_squeal_pitch, T_SPIN - 0.5, T_CRASH + 0.2, 0.05))],
                          gain_db=[dict(kind='curve', points=sample(cruiser_squeal_gain, 0.0, END, 0.05))])),
        dict(name='panel_hit', gain_db=0.0, excite=dict(kind='impact', tau=0.003), resonator=dict(kind='modal', law='free', f1=210.0, ratios=[1.0, 2.3, 3.9, 5.6, 7.7, 10.1, 12.8], t60=1.1),
             events=dict(kind='single', at=round(T_CRASH - OFF, 3))),
        dict(name='sub_thud', gain_db=-3.0, excite=dict(kind='impact', tau=0.008), resonator=dict(kind='modal', law='bar', f1=55.0, n=3, t60=0.5),
             events=dict(kind='single', at=round(T_CRASH - OFF, 3))),
        dict(name='tear', gain_db=-8.0, excite=dict(kind='friction', beta=-1.5, speed=1.0, amp_exp=1.0), resonator=dict(kind='bandpass', band=[500, 5000], order=2),
             events=dict(kind='continuous'),
             control=dict(gain_db=[dict(kind='curve', points=rel([[OFF, -90.0], [T_CRASH, -90.0], [T_CRASH + 0.05, 0.0], [T_CRASH + 1.2, -30.0], [T_CRASH + 1.8, -90.0], [OFF + SECONDS, -90.0]]))])),
        dict(name='glass', gain_db=-6.0, excite=dict(kind='impact', tau=0.0006), resonator=dict(kind='modal', law='bar', f1=3300.0, n=10, t60=0.25),
             events=dict(kind='poisson', rate=26.0, start=round(T_CRASH + 0.08 - OFF, 3), end=round(T_CRASH + 2.4 - OFF, 3))),
    ]),
    role='fx', gain_db=-4.0, reverb=0.12,
    spatial=dict(azimuth=STAGE['np_crash'][0], elevation=STAGE['np_crash'][1], distance=STAGE['np_crash'][2], space=SPACE, binaural=True, kind='spot'),
    eq=[dict(type='hp', f=40.0), dict(type='lp', f=12000.0)],
    sources=['car_crash_impact', 'ESTIMATE: no collision recording was measured; the plate modes, the tear and the glass rate are starting values']))

# ================================================================================================ rain and the city
RAIN_FX = []                                        # water does not pitch or filter down convincingly: the rain stays, the music and the car slow
begin('engine')
write('environments', 'np_rain_street', dict(
    description='Heavy rain at 30 mm/h on a wet asphalt street at night: the patter of drops on the road, a film of water hissing, all round.',
    character='Heavy rain at 30 mm/h falling on a wet street and a film of water on the asphalt, all round the car; in the slow motion it thins and darkens rather than pitching down.',
    atmosphere=dict(temp_c=10.0, rh=95.0),
    layers=[dict(name='drops', primitive='rain_physical', kind='bed', rate_mm_h=30.0, surface='solid', bubble_prob=0.02, gain_db=-22.0, decorrelate=1.0,
                 spatial=dict(azimuth=0, elevation=0, distance=6)),
            dict(name='water_film', primitive='noise_bed', kind='bed', color='pink', low_hz=1800, high_hz=7000, mod_rate_hz=0.08, mod_depth=0.2, gain_db=-27.0,
                 decorrelate=1.0, spatial=dict(azimuth=0, elevation=0, distance=6))],
    blending=dict(),
    fx=RAIN_FX,
    sources=['rain_wet_asphalt', 'ESTIMATE: 30 mm/h and the film band are starting values; no street-rain recording was measured']))

write('environments', 'np_rain_awnings', dict(
    description='Rain on metal awnings and a dumpster either side of the street.',
    character='Rain ringing on thin metal awnings and a dumpster lid on both sides of the street: a sparse, tonal patter that is louder than the road.',
    atmosphere=dict(temp_c=10.0, rh=95.0),
    layers=[dict(name='awning_left', primitive='model_layer', kind='spot', gain_db=-27.0, spatial=dict(azimuth=-80, elevation=0, distance=7),
                 voices=[dict(name='drops', excite=dict(kind='impact', tau=0.0015), resonator=dict(kind='modal', law='free', f1=420.0, ratios=[1.0, 2.3, 3.9, 5.6, 7.7, 10.1], t60=0.28),
                              events=dict(kind='poisson', rate=120.0), vary=dict(size=dict(dist='marshall_palmer', rate_mm_h=12.0, min=0.4, max=2.5), pitch_exp=0.3, amp_exp=2.0))]),
            dict(name='awning_right', primitive='model_layer', kind='spot', gain_db=-23.0, spatial=dict(azimuth=85, elevation=0, distance=8),
                 voices=[dict(name='drops', excite=dict(kind='impact', tau=0.0015), resonator=dict(kind='modal', law='free', f1=360.0, ratios=[1.0, 2.1, 3.6, 5.2, 7.3, 9.6], t60=0.32),
                              events=dict(kind='poisson', rate=110.0), vary=dict(size=dict(dist='marshall_palmer', rate_mm_h=12.0, min=0.4, max=2.5), pitch_exp=0.3, amp_exp=2.0))])],
    blending=dict(),
    fx=RAIN_FX,
    sources=['rain_metal_awning', 'ESTIMATE: the modes of an awning and a dumpster lid are starting values; the louder-than-asphalt ordering is from the research note']))

write('environments', 'np_city_far', dict(
    description='The far city at night: traffic as a low hum and an air of distant streets.',
    character='A far, low traffic hum under the rain with a thin air of distant streets and no event: the city is a bed, never a foreground.',
    atmosphere=dict(temp_c=10.0, rh=95.0),
    layers=[dict(name='traffic', primitive='noise_bed', kind='bed', color='brown', low_hz=45, high_hz=450, mod_rate_hz=0.04, mod_depth=0.25, gain_db=-20.0,
                 decorrelate=1.0, spatial=dict(azimuth=0, elevation=0, distance=80)),
            dict(name='city_air', primitive='noise_bed', kind='bed', color='pink', low_hz=450, high_hz=2500, mod_rate_hz=0.06, mod_depth=0.2, gain_db=-30.0,
                 decorrelate=1.0, spatial=dict(azimuth=0, elevation=0, distance=90))],
    blending=dict(),
    sources=['city_traffic_far', 'ESTIMATE: no New York night spectrum was found; the bands and levels are starting values (the research note gives daytime street levels only)']))

if __name__ == '__main__':
    print(f'wrote np_engine ({len(SHIFT_TIMES)} shifts), np_drift_squeal ({len(SQUEALS)} squeals), np_wipers ({len(WT)} sweeps), two sirens, np_crash, three environments; {SECONDS} s')
    print(f'  launch {A:.1f}  drift {T_DRIFT:.1f}-{T_SNAP:.1f}  underpass {T_UNDER:.1f}  spin {T_SPIN:.1f}  crash {T_CRASH:.1f}  bridge {T_BRIDGE:.1f}  cut {T_CUT:.1f}')
