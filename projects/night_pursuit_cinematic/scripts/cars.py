"""cars.py - the four cars of Night Pursuit Cinematic as data and as physics: a speed profile (km/h) through the story, a gearbox that picks the
gear, and from those the rpm, the firing frequency, the shifts and the throttle lifts.

The relations (the research note, slugs car_*):
    firing frequency   f = rpm x cylinders / 120                       (a four-stroke: every cylinder fires once in two turns)
    road speed         v = 2 pi r rpm / (60 G)                         (G = the gear's ratio x the final drive, r the tyre radius)
So the pitch of an engine follows the speed through the gears, and a shift is a step by the ratio of two gears, never an invented curve.
Every ratio, radius and speed below is a starting value: no figure for a particular car was read (the research note says so).
"""
import math

import timeline as T

G_RATIOS = [3.55, 2.35, 1.75, 1.38, 1.12, 0.92]      # a six-speed box; starting values for all four cars (the cars differ in final drive and rpm)

CARS = dict(
    ferrari=dict(label='Ferrari flat-plane V8', cyl=8, idle=1000.0, redline=9000.0, final=3.45, tyre_r=0.34,
                 up=0.80, down=0.46, harmonics=48, jitter=0.012, burble=0.0, pops=0.5,
                 formants=[[160, 90, 1.0], [420, 140, 0.8], [1200, 400, 0.5], [3200, 900, 0.3]]),
    lamborghini=dict(label='Lamborghini V10', cyl=10, idle=1100.0, redline=8500.0, final=3.55, tyre_r=0.345,
                     up=0.80, down=0.46, harmonics=56, jitter=0.014, burble=0.0, pops=0.45,
                     formants=[[180, 100, 1.0], [520, 160, 0.9], [1500, 450, 0.55], [3600, 1000, 0.3]]),
    mustang=dict(label='Mustang cross-plane V8', cyl=8, idle=700.0, redline=7000.0, final=3.73, tyre_r=0.335,
                 up=0.80, down=0.46, harmonics=36, jitter=0.03, burble=1.0, pops=0.8,
                 formants=[[95, 60, 1.0], [210, 90, 0.9], [620, 220, 0.5], [1400, 480, 0.2]]),
    porsche=dict(label='Porsche flat-six', cyl=6, idle=900.0, redline=8800.0, final=3.62, tyre_r=0.33,
                 up=0.80, down=0.46, harmonics=44, jitter=0.02, burble=0.0, pops=0.2,
                 formants=[[140, 80, 1.0], [380, 130, 0.9], [900, 300, 0.55], [2400, 700, 0.3]]),
)


def kmh(v):
    return v / 3.6


def firing_hz(car, rpm):
    return rpm * CARS[car]['cyl'] / 120.0


def rpm_for(car, v_ms, gear):
    c = CARS[car]
    return v_ms * 60.0 * G_RATIOS[gear] * c['final'] / (2.0 * math.pi * c['tyre_r'])


def speed_waypoints(car, ev, tm=None):
    """(t_s, km/h) for a car. ev = timeline.events(): the story's moments. Not all cars go at the same speed, and the Porsche never changes."""
    tm = tm or T.tempo_map()
    S = lambda name: T.seconds(T.start(name), 0, tm)          # noqa: E731
    if car == 'porsche':
        return [(0.0, 100.0), (ev['end'], 100.0)]
    if car == 'ferrari':
        return [(0.0, 115.0), (8.0, 138.0), (S('spotted') - 1, 150.0), (S('spotted') + 8, 140.0), (S('the_chase'), 132.0), (ev['crash'] - 3, 152.0),
                (S('the_tunnel') + 4, 140.0), (S('the_helicopter'), 150.0), (S('the_bumps'), 138.0), (S('the_flyover'), 150.0),
                (ev['jump'], 150.0), (ev['land'], 128.0), (ev['lost'], 150.0), (ev['evade'], 118.0), (ev['end'] - 6, 70.0), (ev['end'], 45.0)]
    if car == 'lamborghini':
        return [(0.0, 108.0), (8.0, 128.0), (S('spotted') - 1, 140.0), (S('the_chase'), 125.0), (S('the_tunnel') + 4, 135.0), (S('the_helicopter'), 145.0),
                (S('the_bumps'), 130.0), (S('the_flyover'), 145.0), (ev['jump'], 145.0), (ev['land'], 120.0), (ev['lost'], 105.0), (ev['lost'] + 2.5, 0.0)]
    if car == 'mustang':
        return [(0.0, 105.0), (8.0, 118.0), (S('spotted') - 1, 125.0), (S('the_chase'), 120.0), (ev['crash'] - 4, 128.0), (ev['crash'], 125.0), (ev['crash'] + 1.4, 0.0)]
    raise KeyError(car)


CORNERS = dict(ferrari=[43.0, 48.0, 54.5, 59.0, 64.0, 99.5, 106.0, 119.0, 126.0, 168.0, 176.0],
               lamborghini=[43.6, 49.0, 55.0, 60.2, 65.0, 99.0, 107.0, 119.8, 127.0],
               mustang=[43.3, 48.6, 54.0, 59.6, 63.0],
               porsche=[])          # the Porsche never changes speed
CORNER_DEPTH = 0.42                 # a corner takes 42 % off the speed at its apex (150 km/h -> 87 km/h)
CORNER_S = 3.2                      # seconds the corner lasts


def corner_factor(car, t):
    f = 1.0
    for tc in CORNERS.get(car, []):
        u = (t - tc) / CORNER_S
        if abs(u) < 1.0:
            f *= 1.0 - CORNER_DEPTH * 0.5 * (1.0 + math.cos(math.pi * u))
    return f


def end_of(car, ev):
    """The second a car's sound ends (it left the scene), or the end of the cue."""
    # the two that run on drive out of the scene 3.5 s before the cue ends: the Porsche's constant partials and the Ferrari's are not in the key, and the
    # last seconds are judged as the cadence (cochlear_roughness read 0.055 against 0.044 with both still sounding)
    return dict(mustang=ev['crash'] + 1.6, lamborghini=ev['lost'] + 3.0, ferrari=ev['end'] - 3.5, porsche=ev['end'] - 3.5).get(car, ev['end'])


def interp(points, t):
    if t <= points[0][0]:
        return points[0][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / max(1e-9, t1 - t0)
    return points[-1][1]


def drive(car, ev, dt=0.05, tm=None):
    """Walk the story at `dt` seconds: speed -> gear (with hysteresis) -> rpm. Returns dict of lists: t, v (m/s), gear, rpm, load, and the shift and lift
    times. A shift lifts the throttle for 0.16 s and the rpm steps by the ratio of the gears; a car at rest idles."""
    c = CARS[car]
    wp = speed_waypoints(car, ev)
    t_end = end_of(car, ev)
    n = int(t_end / dt) + 1
    gear, t_shift_end = 0, -1.0
    out = dict(t=[], v=[], gear=[], rpm=[], load=[], shifts=[], lifts=[])
    prev_v = kmh(interp(wp, 0.0)) * corner_factor(car, 0.0)
    airborne = (ev['jump'], ev['land'])
    for i in range(n):
        t = i * dt
        v = kmh(interp(wp, t)) * corner_factor(car, t)
        if v < 0.5:
            rpm, load, gear = c['idle'], 0.0, 0
        else:
            # the gear whose rpm is nearest 70 % of the redline; the gear is changed only when the rpm leaves the band (hysteresis)
            r_now = rpm_for(car, v, gear)
            if gear == 0 or r_now > c['up'] * c['redline'] or r_now < c['down'] * c['redline'] * 0.9:
                want = min(range(len(G_RATIOS)), key=lambda g: abs(rpm_for(car, v, g) - 0.7 * c['redline']))
                if want != gear and t >= t_shift_end:
                    if t > 0.0 and gear != 0:
                        out['shifts'].append(round(t, 3))
                        out['lifts'].append(round(t, 3))
                    gear, t_shift_end = want, t + 0.16
            rpm = rpm_for(car, v, gear)
            accel = (v - prev_v) / dt
            load = max(0.0, min(1.0, 0.35 + 0.65 * (rpm - c['idle']) / (c['redline'] - c['idle']) + 0.1 * accel))
            if t < t_shift_end:
                load *= 0.2
        prev_v = v
        out['t'].append(t)
        out['v'].append(v)
        out['gear'].append(gear)
        out['rpm'].append(rpm)
        out['load'].append(load)
    return out


def overrun_pop_times(car, d, ev):
    """Short pops after each throttle lift (decel pops are unburnt fuel igniting in a hot exhaust; the research note). A pseudo-random but
    seeded set, more of them for the loud V8s: `pops` is the car's tendency (0..1)."""
    import random
    rnd = random.Random(hash(car) % 100000 + 11)
    out = []
    for t in d['lifts']:
        if rnd.random() < CARS[car]['pops'] + 0.2:
            for k in range(rnd.randint(2, 5)):
                out.append(round(t + 0.1 + k * rnd.uniform(0.05, 0.14), 3))
    return out
