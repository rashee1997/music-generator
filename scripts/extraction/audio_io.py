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

"""Audio in/out and the per-project cache. Stereo is kept everywhere: arrays are (channels, samples)."""
import hashlib
import json
import os
import pickle

import numpy as np
import soundfile as sf


def load(path, sr):
    """Stereo float32 (2, n) at `sr`. A mono file is duplicated to two channels."""
    try:
        y, file_sr = sf.read(path, always_2d=True, dtype='float32')
        y = y.T
    except Exception:                      # formats libsndfile cannot decode: fall back to librosa/audioread
        import librosa
        y, file_sr = librosa.load(path, sr=None, mono=False)
        y = np.atleast_2d(y).astype('float32')
    if y.shape[0] == 1:
        y = np.vstack([y, y])
    y = y[:2]
    if file_sr != sr:
        import librosa
        y = np.stack([librosa.resample(c, orig_sr=file_sr, target_sr=sr) for c in y])
    return y


def mono(y):
    return y.mean(axis=0)


def write(path, y, sr):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, y.T if y.ndim == 2 else y, sr, subtype='PCM_24')


class Cache:
    """Pickle cache in <project>/reports/cache, keyed by the song and the settings that feed the stage."""

    def __init__(self, root, song, enabled=True):
        self.dir = os.path.join(root, 'reports', 'cache')
        self.enabled = enabled
        st = os.stat(song)
        self.song_key = f'{os.path.basename(song)}:{st.st_size}:{int(st.st_mtime)}'

    def key(self, name, *settings):
        blob = json.dumps([self.song_key, name, settings], sort_keys=True, default=str)
        return hashlib.sha1(blob.encode()).hexdigest()[:16]

    def get(self, name, *settings):
        p = os.path.join(self.dir, f'{name}.pkl')
        if self.enabled and os.path.isfile(p):
            with open(p, 'rb') as f:
                key, value = pickle.load(f)
            if key == self.key(name, *settings):
                return value
        return None

    def put(self, name, value, *settings):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, f'{name}.pkl'), 'wb') as f:
            pickle.dump((self.key(name, *settings), value), f, protocol=4)
        return value
