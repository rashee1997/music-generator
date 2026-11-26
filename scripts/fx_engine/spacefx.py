# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""spacefx.py - tail effects: the reverse swell and the shimmer. Same contract as timefx.py. Both ADD a wet signal levelled
against the stem's own level (`wet_db`), so the dry stem is always there and `mix` scales only the addition."""
import numpy as np
from scipy import signal

from . import core


def reverse_swell(x, sr, p, rng):
    """Reverb the reversed stem with a noise tail that decays 60 dB in decay_s, reverse it back: the tail comes BEFORE each note."""
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    if i1 - i0 < 4:
        return y
    sub = x[i0:i1]
    ln = max(2, int(round(float(p['decay_s']) * sr)))
    t = np.arange(ln) / sr
    ir = rng.standard_normal((ln, 2)) * (10.0 ** (-3.0 * t / float(p['decay_s'])))[:, None]
    wet = np.stack([signal.fftconvolve(sub[::-1, c].astype(np.float64), ir[:, c])[:len(sub)] for c in range(2)], axis=1)[::-1]
    wet = core.match_rms(wet.astype(np.float32), core.rms(sub) * core.db(p['wet_db']))
    y[i0:i1] = sub + wet
    return y


def shimmer(x, sr, p, rng):
    """A reverb whose tail is pitched up and fed back `iterations` times, each pass `shift_semitones` above the last."""
    import pedalboard as pb
    n = len(x)
    i0, i1 = core.span(p, n, sr)
    y = x.copy()
    if i1 - i0 < 64:
        return y
    sub = np.ascontiguousarray(x[i0:i1].T)
    room = dict(room_size=float(p['room_size']), damping=float(p['damping']), wet_level=1.0, dry_level=0.0)
    wet = pb.Reverb(**room)(sub, sr)
    shift = pb.PitchShift(semitones=float(p['shift_semitones']))
    for _ in range(int(p['iterations'])):
        fed = shift(wet, sr) * np.float32(p['feedback'])
        wet = pb.Reverb(**room)(sub + fed[:, :sub.shape[1]], sr)
    wet = core.match_rms(np.ascontiguousarray(wet.T), core.rms(sub) * core.db(p['wet_db']))
    y[i0:i1] = x[i0:i1] + wet
    return y
