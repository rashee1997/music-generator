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

"""Stage `enhance`: light, reversible clean-up of each stem. The raw stems in out/stems/ are never touched.

Only what removes extraction artefacts without changing the instrument's sound:
  * high-pass just under the voice's lowest note (rumble and bleed from lower instruments),
  * quiet the stem where the music_db says the instrument is not playing (smoothed, so no clicks),
  * bring the peak to a target level.
The skill's registry chains (EQ, compression) are opt-in: `enhance.use_registry_chain`."""
import os

import numpy as np
from scipy import signal

from .music_db import hz


def highpass(x, sr, f, order=2):
    sos = signal.butter(order, f / (sr / 2), 'high', output='sos')
    return signal.sosfiltfilt(sos, x, axis=-1)


def span_gain(n, sr, spans, pad, floor_db, smooth_s):
    """Per-sample gain: 1 inside (padded) spans, floor outside, smoothed."""
    inside = np.zeros(n, bool)
    for a, b in spans:
        inside[int(max(a - pad, 0) * sr):int((b + pad) * sr)] = True
    g = np.where(inside, 1.0, 10 ** (floor_db / 20.0)).astype('float32')
    k = max(int(smooth_s * sr), 1)
    return np.convolve(g, np.ones(k) / k, mode='same').astype('float32')


def registry_chain(x, sr, entry):
    """Apply an instruments_registry.json dsp_chain with pedalboard (opt-in)."""
    import pedalboard as pb
    plugins = []
    for p in entry.get('dsp_chain', []):
        cls = getattr(pb, p['plugin'], None)
        if cls is None:
            continue
        args = {k: v for k, v in p.items() if k != 'plugin'}
        plugins.append(cls(**args))
    return pb.Pedalboard(plugins)(x.astype('float32'), sr)


def enhance_stem(x, sr, voice, cfg):
    """(processed stem, what was done)."""
    e = cfg['enhance']
    done = {}
    lo = voice.get('midi_lo')
    if lo is not None and e['highpass']:
        f = hz(lo) * e['highpass_ratio']
        x = highpass(x, sr, f)
        done['highpass_hz'] = round(float(f), 1)
    if voice.get('spans') and e['span_gate']:
        x = x * span_gain(x.shape[1], sr, voice['spans'], cfg['music_db']['span_pad_s'], e['span_floor_db'], e['span_smooth_s'])[None]
        done['span_gate_db'] = e['span_floor_db']
    peak = float(np.max(np.abs(x)))
    if peak > 0 and e['target_peak_dbfs'] is not None:
        gain = 10 ** (e['target_peak_dbfs'] / 20.0) / peak
        x = x * gain
        done['gain_db'] = round(float(20 * np.log10(gain)), 1)
    return x.astype('float32'), done


def run(ctx):
    from . import audio_io
    from .config import jdump, jload
    from .music_db import REGISTRY
    cfg, d = ctx['cfg'], ctx['data']
    e = cfg['enhance']
    if not e['enabled']:
        print('  enhancement is off in the profile')
        return
    if 'gate' not in d:
        from . import gate
        gate.run(ctx)
    sr = d['sr']
    by_id = {v['id']: v for v in ctx['priors']['voices']}
    registry = jload(REGISTRY).get('instruments', {}) if (e['use_registry_chain'] and os.path.isfile(REGISTRY)) else {}
    out_dir = os.path.join(ctx['root'], 'out', 'enhanced')
    report = {}
    sources = {i: (a, by_id.get(i, {})) for i, a in d['sep']['voices'].items()}
    sources.update({f'drum_{k}': (p['stem'], {}) for k, p in d['drums']['pieces'].items()})
    for k, (x, voice) in sources.items():
        y, done = enhance_stem(x, sr, voice, cfg)
        sim = voice.get('similar_to') or ''
        ent = registry.get(sim if isinstance(sim, str) else (sim[0] if sim else '')) if registry else None
        if ent:
            y = registry_chain(y, sr, ent)
            done['registry_chain'] = True
        audio_io.write(os.path.join(out_dir, f'{k}.wav'), y, sr)
        report[k] = done
    d['enhance'] = report
    jdump(report, os.path.join(ctx['root'], 'reports', 'enhance.json'))
    print(f'  enhanced {len(report)} stems into out/enhanced/ (raw stems kept in out/stems/)')
