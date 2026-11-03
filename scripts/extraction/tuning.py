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

"""Tuning offset of the recording in cents (+ = sharp of A440). Must be applied before any note is named."""
import numpy as np


def estimate_cents(y_mono, sr, cfg):
    """Tuning from the spectral peaks of the harmonic content, in (-50, +50] cents."""
    import librosa
    t = cfg['tuning']
    n = int(t['analysis_s'] * sr)
    if len(y_mono) > n:                                    # the loudest stretch is enough and far cheaper
        hop = n // 2
        starts = range(0, len(y_mono) - n + 1, hop)
        s = max(starts, key=lambda a: float(np.sum(y_mono[a:a + n] ** 2)))
        y_mono = y_mono[s:s + n]
    frac = librosa.estimate_tuning(y=y_mono, sr=sr, resolution=t['resolution_semitones'], bins_per_octave=12)
    return float(frac * 100.0)


def resolve(measured, prior, cfg):
    """Pick the tuning to use and say how the listening model's claim compared.

    {'cents', 'source', 'measured', 'prior', 'agree'}; policy 'measured' trusts the audio, 'prior' the database."""
    t = cfg['tuning']
    if prior is None:
        return {'cents': measured, 'source': 'measured', 'measured': measured, 'prior': None, 'agree': None}
    d = (measured - prior + 50.0) % 100.0 - 50.0          # circular difference: +49 and -49 cents are 2 apart
    agree = abs(d) <= t['agree_cents']
    use = prior if t['policy'] == 'prior' else measured
    return {'cents': use, 'source': t['policy'], 'measured': measured, 'prior': prior, 'agree': agree, 'diff_cents': d}
