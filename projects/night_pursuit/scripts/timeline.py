"""timeline.py - the one place Night Pursuit's bars, tempo map and section times are decided.

The direction sheet, the score and the generated preset curves (the engine's rpm, the sirens' sweeps) all read this file, so a
section that moves moves everywhere. Only structure lives here: bars, tempo points and times. No sound, no note.

The cue (4/4, 1-based bars):

    the_stakeout        the courier idles at a red light in the rain; a far siren; one low pulse
    spotted             a cruiser crosses the junction, its lights come on, the siren starts
    the_avenue          launch on the wet avenue: wheelspin, four shifts, the pulse starts and never stops
    the_turn            a drift into a side street; at its crest time slows (a slow-motion drift), then snaps back
    under_the_bridge    an underpass: the room changes, the sirens echo, the music thins, then breaks open
    the_roadblock       a roadblock: a handbrake 180 degrees through the gap; a cruiser spins out (slow motion, then the crash)
    the_bridge          the run across the bridge; the tempo still climbs
    the_cliff           a hard cut at the first beat; then rain, a ticking engine and one far siren, unresolved
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'scripts'))

BB = 4                                   # beats per bar

# (name, first bar, bars, energy, role)
SECTIONS = [
    ('the_stakeout',       1,  6, 0.30, 'place'),
    ('spotted',            7,  6, 0.45, 'establish'),
    ('the_avenue',        13, 14, 0.70, 'build'),
    ('the_turn',          27, 14, 0.85, 'build'),
    ('under_the_bridge',  41, 14, 0.90, 'peak'),
    ('the_roadblock',     55, 18, 1.00, 'peak'),
    ('the_bridge',        73, 14, 0.95, 'peak'),
    ('the_cliff',         87,  8, 0.20, 'button'),
]
END_BAR = SECTIONS[-1][1] + SECTIONS[-1][2]          # first bar after the cue


def start(name):
    return next(s[1] for s in SECTIONS if s[0] == name)


def B(bar, beat=0.0):
    """Absolute beat of a 1-based bar and a beat inside it."""
    return (bar - 1) * BB + beat


# the two slow-motion passages: (first bar of the slowdown, bars to reach the floor, bars held at the floor, floor bpm)
SLOMO_DRIFT = dict(bar=start('the_turn') + 8, ramp_bars=2.0, hold_bars=1.0, floor=60.0)
SLOMO_SPIN = dict(bar=start('the_roadblock') + 12, ramp_bars=1.0, hold_bars=1.0, floor=64.0)
SNAP_DRIFT = SLOMO_DRIFT['bar'] + SLOMO_DRIFT['ramp_bars'] + SLOMO_DRIFT['hold_bars']        # bar where it snaps back
SNAP_SPIN = SLOMO_SPIN['bar'] + SLOMO_SPIN['ramp_bars'] + SLOMO_SPIN['hold_bars']
CRASH_BAR = SNAP_SPIN                                                  # the crash lands on the snap back
CUT_BAR = start('the_cliff')


def tempo_points():
    """[[beat, bpm], ...]: a climb 128 -> 154 BPM with two slow-motion dips that snap back, and a slow cliff."""
    pts = [[B(1), 128.0], [B(start('spotted')), 128.0], [B(start('the_avenue')), 132.0], [B(start('the_turn')), 142.0],
           [B(SLOMO_DRIFT['bar']), 146.0]]
    d = SLOMO_DRIFT
    pts += [[B(d['bar'] + d['ramp_bars']) - 0.1, d['floor']], [B(SNAP_DRIFT) - 0.1, d['floor']], [B(SNAP_DRIFT), 150.0]]
    pts += [[B(start('under_the_bridge')), 150.0], [B(start('the_roadblock')), 150.0], [B(SLOMO_SPIN['bar']), 152.0]]
    s = SLOMO_SPIN
    pts += [[B(s['bar'] + s['ramp_bars']) - 0.1, s['floor']], [B(SNAP_SPIN) - 0.1, s['floor']], [B(SNAP_SPIN), 152.0]]
    pts += [[B(start('the_bridge')), 152.0], [B(CUT_BAR) - 0.1, 156.0], [B(CUT_BAR), 96.0], [B(END_BAR), 84.0]]
    return pts


# A chase is locked to its grid: the tempo map carries no rubato, no wander and no final ritardando (the cue ends on a hard cut),
# so a section starts exactly where its bar says. The players still move by milliseconds (the `natural` humanizer).
TEMPO_FLAGS = dict(rubato=0.0, wander=0.0, ritard=0.0)
SEED = 2611


def score_tempo():
    """The score-level keys that fix the tempo map; the score and this module both use them."""
    return dict(bpm=128, ts=[BB, 4], seed=SEED, humanize='natural', key='C', mode='minor', tempo_points=tempo_points(), **TEMPO_FLAGS)


def tempo_map():
    import humanize as hz
    # The renderer builds its map from the whole score, and the map's length comes from the last note: a map sized for the default
    # 64 beats extrapolates at its last tempo and reads seconds that are wrong by ten. One stub note as long as the cue gives the same map.
    sc = score_tempo()
    sc['tracks'] = [dict(notes=[dict(t=0.0, d=float(B(END_BAR)))])]
    return hz.tempo_map_for(sc, seed=SEED)


def seconds(bar, beat=0.0, tm=None):
    return float((tm or tempo_map()).sec(B(bar, beat)))


def sections_with_seconds(tm=None):
    tm = tm or tempo_map()
    out = []
    for name, first, bars, energy, role in SECTIONS:
        out.append(dict(name=name, role=role, energy=energy, start_bar=first, end_bar=first + bars - 1,
                        start_s=round(seconds(first, 0, tm), 3), end_s=round(seconds(first + bars, 0, tm), 3)))
    return out


def sfx_start():
    """Piece second at which each effect's trigger note sits. The effect's own clock starts there, and the stem gate judges an effect from
    its onset, so a sound that is silent for its first half second would read as a part that never played."""
    tm = tempo_map()
    return dict(engine=0.0, wipers=0.5, siren_first=4.0, tyres=seconds(start('the_avenue'), 0, tm) + 0.1,
                siren_second=seconds(start('the_turn'), 0, tm), crash=seconds(SLOMO_SPIN['bar'] + SLOMO_SPIN['ramp_bars'] + SLOMO_SPIN['hold_bars'] - 2, 0, tm))


if __name__ == '__main__':
    tm = tempo_map()
    for s in sections_with_seconds(tm):
        print(f'  {s["name"]:18s} bars {s["start_bar"]:3d}-{s["end_bar"]:3d}  {s["start_s"]:7.2f} - {s["end_s"]:7.2f} s  energy {s["energy"]}')
    print(f'  drift slow-mo {seconds(SLOMO_DRIFT["bar"], 0, tm):.1f} s -> snap {seconds(SNAP_DRIFT, 0, tm):.1f} s;  '
          f'spin slow-mo {seconds(SLOMO_SPIN["bar"], 0, tm):.1f} s -> crash {seconds(CRASH_BAR, 0, tm):.1f} s;  cut {seconds(CUT_BAR, 0, tm):.1f} s')
    print(f'  total {seconds(END_BAR, 0, tm):.1f} s')
