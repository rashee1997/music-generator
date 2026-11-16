# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""stem_cache.py - content addressing for the two expensive stages.

Stage 4 (stem rendering) and Stage 4b (the per-stem gate) used to redo all 21 stems on every attempt, so one note fix
cost the whole piece. Both are cached by content now:

  .cache/stems/<key>.wav     the dry stem, keyed on what changes its bytes: that track's notes, the tempo map, the
                             presets the renderer reads, the renderer code and the SoundFont. Staging and mix values
                             (`spatial`, `eq`, `gain_db`, `reverb`, `pan`, ...) are EXCLUDED: they belong to stage 5 and
                             never touch a dry stem, so re-staging the orchestra must not re-render it.
  .cache/gate/stem_qa.json   the stem-gate rows measured on a given stem's bytes, keyed by that stem's hash plus the
                             track, the sections, the tempo and the resolved gate profile.

This module measures and renders nothing. It only decides whether a result already on disk may be reused, and it is
the single place that answers "is this the same stem?" for both stages.
"""
import glob
import hashlib
import json
import os

CACHE_VERSION = 1

# Stage 5 owns every one of these: none of them changes a dry stem's bytes, so none of them may invalidate one.
MIX_KEYS = ('spatial', 'eq', 'gain_db', 'reverb', 'send', 'pan', 'width', 'duck', 'level_db', 'automation',
            'azimuth', 'elevation', 'distance', 'space', 'mix')


def canonical(obj):
    """One deterministic JSON string for any value: dict key order can never change a hash."""
    return json.dumps(obj, sort_keys=True, default=str, separators=(',', ':'))


def digest(obj, size=32):
    return hashlib.blake2b(canonical(obj).encode('utf-8'), digest_size=size).hexdigest()


def audio_hash(x, size=32, stride=4):
    """Identity of the audio itself: two stems with the same samples are the same stem, whatever made them.

    The frame count plus every `stride`-th frame, hashed from the buffer with no `tobytes()` copy. One full pass over 23
    stems of 85 s (690 MB) costs ~3 s, which alone would break the "a cached Stage 4b is under 2 s" budget; a re-render
    or a renderer edit changes the whole file, not isolated frames, so the 4x cheaper fingerprint identifies it just as
    safely. Pass stride=1 where byte identity is required (the stem manifest).
    """
    import numpy as np
    a = np.ascontiguousarray(x, dtype=np.float32)
    if stride > 1:
        a = np.ascontiguousarray(a[::int(stride)])
    h = hashlib.blake2b(digest_size=size)
    h.update(str(int(np.shape(x)[0])).encode('utf-8'))
    h.update(memoryview(a).cast('B'))
    return h.hexdigest()


def dry_track(tr):
    """The track as the renderer sees it: everything except the stage-5 staging/mix values."""
    return {k: v for k, v in (tr or {}).items() if k not in MIX_KEYS}


def dry_presets(fp):
    """A resolved-preset map with the stage-5 sections removed from every preset."""
    out = {}
    for kind, cfg in (fp or {}).items():
        out[kind] = ({k: v for k, v in cfg.items() if k not in MIX_KEYS} if isinstance(cfg, dict) else cfg)
    return out


def code_hash(here, files=(), packages=()):
    """Identity of the code behind a cached result: a cache must never hand back another version's output."""
    h = hashlib.blake2b(digest_size=20)
    for f in files:
        h.update(f.encode('utf-8'))
        try:
            with open(os.path.join(here, f), 'rb') as fh:
                h.update(fh.read())
        except OSError:
            h.update(b'missing')
    for pkg in packages:
        for p in sorted(glob.glob(os.path.join(here, pkg, '*.py'))):
            h.update(os.path.relpath(p, here).replace(os.sep, '/').encode('utf-8'))
            try:
                with open(p, 'rb') as fh:
                    h.update(fh.read())
            except OSError:
                h.update(b'missing')
    return h.hexdigest()


def load_json(path, default=None):
    """A cache file, or the default when it is missing, unreadable or from another cache version."""
    if not path or not os.path.isfile(path):
        return default
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return default
    if not isinstance(data, dict) or data.get('version') != CACHE_VERSION:
        return default
    return data


def save_json(path, data):
    """Atomic: a killed run never leaves a half-written cache that the next run would trust."""
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + f'.tmp{os.getpid()}'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass          # caching is an optimization; never fail a render over it


def jsonable(obj):
    """Cache values that survive a JSON round trip: numpy scalars and arrays become plain numbers and lists."""
    import numpy as np
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    return obj if obj is None or isinstance(obj, (str, int, float)) else str(obj)
