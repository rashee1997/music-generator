"""timeline.py - the one place Night Pursuit Cinematic's bars, shots, tempo map and event times are decided.

The direction sheet, the score and the generated sound presets (every car's rpm, the sirens, the bumps) read this file, so a shot that
moves moves everywhere. Only structure lives here: bars, tempo points and times. No sound, no note.

The cue (4/4, 1-based bars; each section is a camera):

    the_race          inside the hero car, already at speed: a street race, four cars, no slow opening
    spotted           roadside: the cars pass the kerb; a cruiser sees the speeding and its siren starts
    the_chase         beside and behind: the cruisers close; the Mustang runs out of road at the end
    the_tunnel        a tunnel: the room changes, the engines echo
    the_helicopter    high and far: a police helicopter joins; the music goes distant
    the_bumps         a flyover deck: expansion-joint thumps at speed
    the_flyover       the edge: a jump in slow motion, a landing, the Lamborghini spins off
    the_escape        evaded: the cruisers stop, the Ferrari runs on, the engine fades
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'scripts'))

BB = 4

# (name, first bar, bars, energy, role, camera)
SECTIONS = [
    ('the_race',        1, 14, 0.90, 'place',     'inside'),
    ('spotted',        15,  8, 0.80, 'establish', 'roadside'),
    ('the_chase',      23, 20, 0.90, 'build',     'chase'),
    ('the_tunnel',     43, 14, 0.80, 'peak',      'tunnel'),
    ('the_helicopter', 57, 14, 0.80, 'peak',      'aerial'),
    ('the_bumps',      71, 14, 1.00, 'peak',      'flyover'),
    ('the_flyover',    85, 14, 0.80, 'peak',      'flyover'),
    ('the_escape',     99, 12, 0.50, 'release',   'street'),
]
END_BAR = SECTIONS[-1][1] + SECTIONS[-1][2]


def start(name):
    return next(s[1] for s in SECTIONS if s[0] == name)


def end(name):
    s = next(s for s in SECTIONS if s[0] == name)
    return s[1] + s[2]


def B(bar, beat=0.0):
    return (bar - 1) * BB + beat


# the one slow-motion moment: the jump off the flyover edge (bar of the take-off, bars to the floor, bars held, floor bpm)
SLOMO_JUMP = dict(bar=start('the_flyover') + 6, ramp_bars=2.0, hold_bars=1.0, floor=72.0)
SNAP_JUMP = SLOMO_JUMP['bar'] + SLOMO_JUMP['ramp_bars'] + SLOMO_JUMP['hold_bars']      # the landing
SPOT_BAR = start('spotted') + 2                    # the cruiser sees the speeding
CRASH_BAR = end('the_chase') - 1                   # the Mustang hits the barrier at the tunnel mouth
LOST_BAR = SNAP_JUMP + 2                           # the Lamborghini spins off after the landing
EVADE_BAR = start('the_escape')                    # the cruisers stop


def tempo_points():
    d = SLOMO_JUMP
    pts = [[B(1), 132.0], [B(start('spotted')), 136.0], [B(start('the_chase')), 142.0], [B(start('the_tunnel')), 146.0],
           [B(start('the_helicopter')), 148.0], [B(start('the_bumps')), 150.0], [B(start('the_flyover')), 152.0], [B(d['bar']), 152.0],
           [B(d['bar'] + d['ramp_bars']) - 0.1, d['floor']], [B(SNAP_JUMP) - 0.1, d['floor']], [B(SNAP_JUMP), 156.0],
           [B(EVADE_BAR), 124.0], [B(END_BAR), 92.0]]
    return pts


TEMPO_FLAGS = dict(rubato=0.0, wander=0.0, ritard=0.0)
SEED = 4107


def score_tempo():
    return dict(bpm=132, ts=[BB, 4], seed=SEED, humanize='natural', key='C', mode='minor', tempo_points=tempo_points(), **TEMPO_FLAGS)


def tempo_map():
    """The renderer's map. It is sized from the score's notes, so a map built for the default 64 beats extrapolates at its last tempo and
    reads seconds that are wrong by ten: one stub note as long as the cue gives the same map."""
    import humanize as hz
    sc = score_tempo()
    sc['tracks'] = [dict(notes=[dict(t=0.0, d=float(B(END_BAR)))])]
    return hz.tempo_map_for(sc, seed=SEED)


def seconds(bar, beat=0.0, tm=None):
    return float((tm or tempo_map()).sec(B(bar, beat)))


def sections_with_seconds(tm=None):
    tm = tm or tempo_map()
    out = []
    for name, first, bars, energy, role, cam in SECTIONS:
        out.append(dict(name=name, role=role, energy=energy, camera=cam, start_bar=first, end_bar=first + bars - 1,
                        start_s=round(seconds(first, 0, tm), 3), end_s=round(seconds(first + bars, 0, tm), 3)))
    return out


def events(tm=None):
    """The story's moments in piece seconds."""
    tm = tm or tempo_map()
    return dict(spot=seconds(SPOT_BAR, 0, tm), crash=seconds(CRASH_BAR, 2, tm), jump=seconds(SLOMO_JUMP['bar'], 0, tm), land=seconds(SNAP_JUMP, 0, tm),
                lost=seconds(LOST_BAR, 0, tm), evade=seconds(EVADE_BAR, 0, tm), end=seconds(END_BAR, 0, tm))


def sfx_start():
    """Piece second at which each effect's trigger note sits (an effect's own clock starts there; the stem gate judges it from its onset)."""
    tm = tempo_map()
    return dict(ferrari=0.0, lamborghini=0.0, mustang=0.0, porsche=0.0, siren_first=seconds(SPOT_BAR, 0, tm), siren_second=seconds(start('the_chase'), 0, tm),
                helicopter=seconds(start('the_helicopter') - 2, 0, tm), bumps=seconds(start('the_bumps'), 0, tm), crash=seconds(CRASH_BAR, 0, tm),
                landing=seconds(SNAP_JUMP, 0, tm) - 0.01, tunnel=seconds(start('the_tunnel'), 0, tm), drips=seconds(EVADE_BAR, 0, tm))


if __name__ == '__main__':
    tm = tempo_map()
    for s in sections_with_seconds(tm):
        print(f'  {s["name"]:15s} {s["camera"]:9s} bars {s["start_bar"]:3d}-{s["end_bar"]:3d}  {s["start_s"]:7.2f} - {s["end_s"]:7.2f} s  energy {s["energy"]}')
    print('  events', {k: round(v, 1) for k, v in events(tm).items()})
