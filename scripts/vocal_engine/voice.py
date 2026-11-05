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

"""voice.synth: f0 track -> voiced signal (source -> tract or nasal hum). No envelope, no peak normalisation:
dynamics and articulation are applied by the caller, so loudness is never re-normalised per note."""
import numpy as np

from . import data, nasal, source, tract


def resolve_register(cfg, name=None):
    regs = cfg['source']['registers']
    reg = dict(regs.get(name or cfg['source']['register'], regs['modal']))
    return reg


def register_track(cfg, name, f0):
    """Register parameters per sample: the chosen register blended toward the next rung of `source.register_ladder`
    across `source.passaggio` (a semitone band around `midi`). Without this, a line crossing into head voice either
    never changes register or switches dicts at a note boundary - a hard passaggio break is a synthetic cue."""
    s = cfg['source']
    base = resolve_register(cfg, name)
    p = s.get('passaggio') or {}
    if not p.get('enabled', False):
        return base
    ladder = list(s.get('register_ladder') or [])
    nm = name or s['register']
    if nm not in ladder or ladder.index(nm) + 1 >= len(ladder):
        return base
    other = resolve_register(cfg, ladder[ladder.index(nm) + 1])
    f0 = np.asarray(f0, dtype=float)
    midi = 69.0 + 12.0 * np.log2(np.maximum(f0, 20.0) / 440.0)
    width = max(float(p.get('width_semitones', 2.0)), 1e-3)
    w = np.clip((midi - float(p.get('midi', 60.0)) + 0.5 * width) / width, 0.0, 1.0)
    out = {}
    for k, v in base.items():
        out[k] = (1.0 - w) * float(v) + w * float(other[k]) if isinstance(v, (int, float)) and k in other else v
    return out


def synth(f0, sr, rng, cfg, formants=None, bandwidths=None, gains=None, hum=False, nasality=0.0, register=None,
          style=None, breathiness=None, phase0=0.0, tilt_hz=None, formant_scale=1.0, creak=0.0, stats=None,
          vib_am=None, stats_gate=None, stats_notes=None):
    """f0: Hz per sample. formants/bandwidths: (k,) or (k,n) arrays (moving vowel). cfg: merged defaults.
    `creak` is a 0..1 track for period-doubling (vocal fry) at phrase ends and low pitches.
    Returns (signal, end_cycles)."""
    f0 = np.asarray(f0, dtype=float)
    n = len(f0)
    if n == 0:
        return np.zeros(0), phase0
    s = cfg['source']
    st = style or {}
    reg = register_track(cfg, register or (cfg['humming']['register'] if hum else st.get('register')), f0)
    block = max(16, int(cfg['tract']['block_ms'] * 1e-3 * sr))
    br = s['breathiness'] if breathiness is None else breathiness
    src, c, flow = source.glottal_source(
        f0, sr, rng, reg, breathiness=br, phase0=phase0,
        subharmonic=bool(st.get('subharmonic')), sub_weight=s['subharmonic_weight'],
        whistle_hz=s['whistle_hz'] if st.get('whistle_overtone') else 0.0, whistle_weight=s['whistle_weight'],
        aspiration_depth=s['aspiration_pulse_depth'], tilt_hz=tilt_hz,
        jitter_pct=float(s.get('jitter_period_pct', 0.0)),
        jitter_shimmer_corr=float(s.get('jitter_shimmer_corr', 0.5)), sub_extra=creak, stats=stats, amp_mod=vib_am,
        stats_gate=stats_gate, stats_notes=stats_notes)
    if hum:
        y = nasal.hum_branch(src, sr, cfg['humming'], rng, flow=flow, block=block)
    else:
        F = np.asarray(formants if formants is not None else cfg['tract']['vowels']['a'], dtype=float) * formant_scale
        k = len(F)
        BW = np.asarray(bandwidths if bandwidths is not None else cfg['tract']['bandwidths'][:k], dtype=float)
        G = list(gains if gains is not None else cfg['tract']['gains'])[:k]
        if st.get('harmonic_lock'):
            F = tract.lock_to_harmonics(F.reshape(k, -1), f0[None, :] if F.ndim > 1 else np.mean(f0), s['harmonic_lock_amount'])
        y = tract.bank(src, list(F), list(np.broadcast_to(BW, (k,) + BW.shape[1:]) if BW.ndim > 1 else BW), G, sr, block)
        if nasality > 0:
            y = nasal.nasalize(y, src, sr, nasality, cfg['humming'], block)
    return y, float(c[-1])
