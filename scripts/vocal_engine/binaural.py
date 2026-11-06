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

"""Binaural placement: one dry singer -> the left/right pair that goes into the mix.

This is the only spatial work the engine does, and it is done on the *mix* only. `ensemble.render`
still returns dry mono stems (`info['stems']`, `info['breath_stems']`), so a project's
`spatial.spatialize_stem()` keeps working; a project that folds the mix to mono throws the cues
away, which is a documented limit, not a bug.

Three cues, each weighted by `|pan|` so a centred voice is unchanged:
  * interaural time difference - the far ear is delayed by up to `ensemble.itd_ms` (Woodworth's
    rigid-sphere model, ~0.65 ms at the frontal horizontal limit);
  * head shadow - one-pole low-pass + up to `ensemble.head_shadow_db` on the far ear (the
    one-pole spherical-head filter of Algazi et al.);
  * two early reflections, 8-24 ms, below `ensemble.reflection_gain`, one per ear. Their gain is
    scaled by `(1 - 1/n_total)` so a solo singer renders exactly as the plain pan law did.

All vectorised: fractional delay is linear interpolation, everything else is a filter or a slice.
"""
import numpy as np

from .utils import one_pole_lp


def _delay(x, d):
    """Delay `x` by `d` samples (fractional allowed), zero-filled head. y[t] = x[t - d]. O(n)."""
    n = x.shape[0]
    i = int(np.floor(d))
    if i >= n:
        return np.zeros_like(x)
    f = float(d - i)
    y = np.zeros_like(x)
    y[i:] += (1.0 - f) * x[:n - i]
    if f > 0.0 and i + 1 < n:
        y[i + 1:] += f * x[:n - i - 1]
    return y


def place(x, pan, sr, E, rng, n_total=1):
    """Return (left, right, cues) for one dry singer at `pan` in [-1, 1].

    `E` is the resolved `ensemble` block, `rng` a dedicated generator (deterministic per singer),
    `n_total` the number of singers, which decides how much early-reflection gain the mix can take.
    """
    pan = float(np.clip(pan, -1.0, 1.0))
    left = np.sqrt(0.5 * (1.0 - pan)) * x
    right = np.sqrt(0.5 * (1.0 + pan)) * x
    cues = dict(itd_ms=0.0, shadow_db=0.0, reflection_gains=[])
    side = abs(pan)
    if side <= 0.0:
        pass
    else:
        far = left if pan > 0.0 else right                  # source right -> left ear is far
        itd_ms = float(E['itd_ms']) * side
        cues['itd_ms'] = itd_ms
        if itd_ms > 0.0:
            far[:] = _delay(far, itd_ms * 1e-3 * sr)
        shadow_db = float(E['head_shadow_db']) * side
        cues['shadow_db'] = shadow_db
        dark = one_pole_lp(far, float(E['head_shadow_hz']), sr)
        far[:] = (1.0 - side) * far + side * dark
        far *= 10.0 ** (-shadow_db / 20.0)
    room = max(0.0, 1.0 - 1.0 / max(1, int(n_total)))
    taps = int(E['reflection_taps']) if room > 0.0 else 0
    lo, hi = (float(v) for v in E['reflection_ms'])
    for k in range(taps):
        g = float(E['reflection_gain']) * rng.uniform(0.4, 1.0) * room
        y = one_pole_lp(_delay(x, rng.uniform(lo, hi) * 1e-3 * sr), float(E['reflection_lp_hz']), sr) * g
        (left if k % 2 == 0 else right)[:] += y
        cues['reflection_gains'].append(round(g, 4))
    return left, right, cues
