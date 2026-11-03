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

"""Pitch-resolved spectrum: harmonic part of the mix -> constant-Q magnitude -> one row per semitone of the tuned scale."""
import numpy as np

from .music_db import hz


def harmonic_part(y_mono, cfg):
    """Drums and clicks removed by median-filter HPSS; margin > 1 keeps only clearly tonal energy."""
    s = cfg['spectrum']
    if not s['hpss']:
        return y_mono
    import librosa
    return librosa.effects.harmonic(y_mono, margin=s['hpss_margin'])


def semitone_spectrum(y_mono, sr, tuning_cents, cfg):
    """{'S': (semitones, frames) compressed magnitude, 'midi_lo', 'hop_s', 'times'}. Row i is MIDI midi_lo + i at the tuned pitch."""
    import librosa
    s = cfg['spectrum']
    bpo = s['bins_per_octave']
    per = bpo // 12                                           # sub-bins per semitone; the centre one sits exactly on the pitch
    lo, hi = s['midi_lo'], s['midi_hi']
    n_bins = (hi - lo) * per + 1
    C = np.abs(librosa.cqt(y_mono, sr=sr, hop_length=s['hop'], fmin=hz(lo, tuning_cents), n_bins=n_bins,
                           bins_per_octave=bpo, filter_scale=s['filter_scale']))
    # a semitone's value is the strongest sub-bin within half a semitone, so vibrato and small tuning error do not lose the note
    padded = np.pad(C, ((per // 2, per // 2), (0, 0)))
    centre = np.arange(hi - lo + 1) * per + per // 2
    S = np.max([padded[centre + d] for d in range(-(per // 2), per // 2 + 1)], axis=0)
    S = S ** s['compress']
    return {'S': S.astype('float32'), 'midi_lo': lo, 'hop_s': s['hop'] / sr, 'times': np.arange(S.shape[1]) * s['hop'] / sr}


def harmonic_offsets(count):
    """Semitone distance from a fundamental to its h-th harmonic: 0, 12, 19, 24, 28, 31, ..."""
    return [int(round(12 * np.log2(h))) for h in range(1, count + 1)]
