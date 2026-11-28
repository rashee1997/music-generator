"""timeline.py - the story clock of Quiet Frequency, read by the score builder and the sound presets so they cannot disagree.

120 BPM, 4/4, 60 bars: one bar is 2.0 s and one beat 0.5 s, so a bar number is a second count with no tempo map to drift.
"""
BPM, BEATS, BARS = 120, 4, 60
BAR_S = BEATS * 60.0 / BPM            # 2.0 s
TOTAL_S = BARS * BAR_S                # 120.0 s


def at(bar, beat=0.0):
    """Seconds at a bar (1-based) and a beat inside it."""
    return round(((bar - 1) * BEATS + beat) * 60.0 / BPM, 4)


def beat_of(bar, beat=0.0):
    return (bar - 1) * BEATS + beat


# (name, role, first bar, last bar, energy, what the camera does)
SECTIONS = [
    ('the_lab', 'establish', 1, 6, 0.25, 'a sealed lab at night: an alarm, a radio, a case on a bench'),
    ('the_take', 'transition', 7, 12, 0.45, 'the Hero takes the device and runs for the bike; the gate opens'),
    ('the_alert', 'build', 13, 18, 0.65, 'the Villain finds the empty case; the Hero is already on the highway'),
    ('the_chase', 'peak', 19, 26, 0.9, 'a tunnel bore and open road: the black car closes, the bike drifts'),
    ('the_flyover', 'build', 27, 29, 0.8, 'high angle over the flyover deck: the car alongside'),
    ('the_truck', 'rupture', 30, 32, 0.6, 'a truck, an air horn, one second of nothing'),
    ('the_escalation', 'peak', 33, 44, 0.95, 'handheld, low to the road: a hard drift, the car tries to ram'),
    ('the_wall', 'peak', 45, 52, 1.0, 'the widest shot and the loudest bars: the barrier, the tunnel again'),
    ('the_dropout', 'release', 53, 55, 0.35, 'the music leaves: two engines idling, a radio, a breath'),
    ('the_signal', 'button', 56, 60, 0.3, 'the bike stops; the case opens; the device pulses; cut to black'),
]

# the pictures the music answers (seconds); each has a hit in the direction sheet
T = dict(take=at(7), start_v8=at(13), chase=at(19), flyover=at(27), horn=at(31, 1), stop=at(32), back=at(33), wall=at(45),
         mid_wall=at(49), dropout=at(53), signal=at(56), last=at(59, 2.0))

# the one declared silence: the music, the engines and the room all stop for a second after the truck (hit at T['stop'])
SILENCE = (T['stop'], T['stop'] + 1.0)

# ---- the engines: gears, rpm and the story ---------------------------------------------------------------------------------------
# Yamaha R15 V3 (155 cc, single cylinder): six-speed ratios from one listing (maxabout); idle and limit are ESTIMATES (research note)
BIKE_GEARS = {1: 2.833, 2: 1.875, 3: 1.364, 4: 1.143, 5: 0.957, 6: 0.840}
BIKE_IDLE, BIKE_LIMIT, BIKE_CYL_FACTOR = 1400.0, 10500.0, 1.0     # firing frequency = rpm * 1 / 120 (single cylinder, four-stroke)
# the villain's car: a V8 with a six-speed box (starting values; no particular car)
CAR_GEARS = {1: 3.6, 2: 2.2, 3: 1.5, 4: 1.1, 5: 0.85, 6: 0.68}
CAR_IDLE, CAR_LIMIT, CAR_CYL = 700.0, 6500.0, 8                   # firing frequency = rpm * 8 / 120


class Drive:
    """A vehicle driven by events. ('rpm', t, rpm) sets where the rpm is at t in the current gear (straight lines between); ('shift', t, gear)
    changes gear: the rpm after the shift is the rpm before times the ratio of the new gear over the old, with a power gap on an upshift
    (a quickshifter cuts ignition for a moment, so the note dips) and a blip on a downshift (the revs rise to match)."""

    def __init__(self, gears, idle, limit):
        self.gears, self.idle, self.limit = gears, idle, limit
        self.w = []                  # (t, rpm, gear)
        self.shifts = []             # (t, gap_s, direction)
        self.gear = 0

    def _rpm_now(self, t):
        if not self.w:
            return self.idle
        (t0, r0, _g0) = self.w[-1]
        return r0

    def rpm(self, t, rpm, gear=None):
        g = self.gear if gear is None else gear
        self.gear = g
        self.w.append((round(t, 3), float(min(rpm, self.limit)), g))
        return self

    def shift(self, t, gear):
        old, new = self.gear, gear
        r0 = self._rpm_now(t)
        self.w.append((round(t, 3), r0, old))
        if old and new:
            target = r0 * self.gears[new] / self.gears[old]
            if target > self.limit * 1.001:
                raise ValueError(f'shift at {t}: gear {old}->{new} from {r0:.0f} rpm would reach {target:.0f} rpm, over the {self.limit:.0f} limit')
            up = new > old
            gap, k = (0.09, 0.88) if up else (0.12, 1.13)
            self.w.append((round(t + gap, 3), min(self.limit, target * k), new))
            self.w.append((round(t + gap + 0.18, 3), min(self.limit, target), new))
            self.shifts.append((round(t, 3), gap, 'up' if up else 'down'))
        else:
            self.w.append((round(t + 0.1, 3), r0, new))
        self.gear = new
        return self

    def rpm_at(self, t):
        w = self.w
        if t <= w[0][0]:
            return w[0][1]
        for (t0, r0, _), (t1, r1, _) in zip(w, w[1:]):
            if t0 <= t <= t1:
                return r0 + (r1 - r0) * (t - t0) / max(1e-9, t1 - t0)
        return w[-1][1]

    def gear_at(self, t):
        g = self.w[0][2]
        for tt, _r, gg in self.w:
            if tt <= t:
                g = gg
        return g

    def power_gap(self, t):
        """0..1: how deep inside a shift's power gap t is (an upshift cuts the engine for a moment)."""
        for ts, gap, d in self.shifts:
            if d == 'up' and ts <= t <= ts + gap + 0.05:
                return 1.0
        return 0.0


def hero_bike():
    """The Hero's R15: a start in the lab yard at 14 s, the gate at 22 s, six gears up the highway, a downshift for each drift."""
    d = Drive(BIKE_GEARS, BIKE_IDLE, BIKE_LIMIT)
    d.rpm(13.8, 1400, 0).rpm(15.0, 1400).rpm(15.4, 3600).rpm(15.9, 1500).rpm(18.0, 1450).rpm(19.2, 4200).rpm(19.7, 1450)
    d.rpm(21.5, 1450)
    d.shift(21.6, 1).rpm(21.7, 2600).rpm(23.2, 9400)
    d.shift(23.3, 2).rpm(25.0, 9300)
    d.shift(25.1, 3).rpm(27.0, 9200)
    d.shift(27.1, 4).rpm(30.0, 8900)
    d.shift(30.1, 5).rpm(35.0, 8200)
    d.shift(35.1, 6).rpm(39.0, 7600).rpm(43.0, 8300)
    d.rpm(43.2, 7600).shift(43.4, 5).rpm(43.8, 8700)   # the drift: two gears down one at a time, a blip each
    d.shift(43.95, 4).rpm(44.6, 9900).rpm(46.0, 9800)
    d.shift(46.2, 5).rpm(48.0, 8800)
    d.shift(48.2, 6).rpm(53.0, 8400).rpm(59.2, 8700)
    d.rpm(61.0, 6200).rpm(61.9, 1450)                # the truck: off the throttle; the music, the engines and the room stop at 62
    d.rpm(63.2, 1500).rpm(63.6, 3000, 0)
    d.rpm(63.7, 3000)
    d.shift(63.8, 1).rpm(63.9, 3600).rpm(65.0, 9300)
    d.shift(65.1, 2).rpm(66.5, 9300)
    d.shift(66.6, 3).rpm(68.5, 9400)
    d.shift(68.6, 4).rpm(71.0, 7800)
    d.shift(72.9, 3).rpm(73.4, 9600)                 # the hard drift to the right
    d.shift(75.4, 4).rpm(77.0, 9500)
    d.shift(77.1, 5).rpm(80.0, 9000)
    d.shift(80.1, 6).rpm(85.0, 8600).rpm(88.0, 7400)
    d.shift(89.4, 5).rpm(89.8, 8500)                 # the wall
    d.shift(90.0, 4).rpm(91.0, 9800)
    d.shift(91.8, 5).rpm(93.0, 9500)
    d.shift(93.1, 6).rpm(95.0, 7600)
    d.shift(95.2, 5).rpm(95.8, 8700)
    d.shift(96.0, 4).rpm(97.5, 9900)
    d.shift(99.4, 5).rpm(100.5, 9600)
    d.shift(100.6, 6).rpm(103.0, 9300)
    d.rpm(104.0, 8200).rpm(105.5, 3500).rpm(107.0, 1450, 0).rpm(114.0, 1450)   # the bike coasts to a stop
    d.rpm(114.6, 1450).rpm(116.0, 1450)
    return d


def villain_car():
    """The Villain's V8: asleep until the alert at 24 s, six gears, a downshift under braking at the truck, a lunge at the wall."""
    d = Drive(CAR_GEARS, CAR_IDLE, CAR_LIMIT)
    d.rpm(24.0, 700, 0).rpm(26.0, 700).rpm(26.4, 3200).rpm(27.0, 900).rpm(28.5, 900)
    d.shift(28.6, 1).rpm(28.7, 2200).rpm(30.5, 6000)
    d.shift(30.6, 2).rpm(32.5, 6100)
    d.shift(32.6, 3).rpm(35.0, 6200)
    d.shift(35.1, 4).rpm(38.0, 6000)
    d.shift(38.1, 5).rpm(44.0, 4700)
    d.shift(44.1, 4).rpm(47.0, 6100)
    d.shift(47.1, 5).rpm(52.0, 5800).rpm(58.0, 5000)
    d.shift(58.1, 4).rpm(59.4, 4300)
    d.shift(59.6, 3).rpm(60.4, 6300)                 # two downshifts into the truck
    d.rpm(61.9, 1500, 3).rpm(63.4, 1100)
    d.shift(63.6, 1).rpm(64.0, 3000).rpm(65.0, 6300)
    d.shift(65.1, 2).rpm(67.0, 6300)
    d.shift(67.1, 3).rpm(69.0, 6400)
    d.shift(69.1, 4).rpm(72.0, 4700)
    d.shift(72.1, 3).rpm(74.0, 6300)
    d.shift(74.1, 4).rpm(78.0, 6200)
    d.shift(78.1, 5).rpm(84.0, 4900)
    d.shift(84.1, 4).rpm(88.0, 4600)
    d.shift(88.1, 3).rpm(91.0, 6400)
    d.shift(91.1, 4).rpm(94.5, 4700)
    d.shift(94.6, 3).rpm(97.0, 6450)                 # the lunge at the barrier
    d.shift(97.1, 4).rpm(101.0, 6200)
    d.rpm(104.0, 5000).rpm(106.5, 1600).rpm(108.0, 800, 0).rpm(113.5, 760).rpm(116.0, 720)
    return d
