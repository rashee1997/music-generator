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

"""Performance context: what the music asks of the singer, derived from the notes and the preset.

The phrase renderer needs more than the notes in front of it: tempo (metric weight), where a phrase sits in
the line (a first phrase opens, a last phrase closes), the melodic direction, the register, the ensemble's
energy, the expression profile and the track's role in the arrangement. This module computes those once per
render (`analyse`) and once per phrase (`phrase_context`); render_phrase only reads the dictionary.

Nothing here changes the sound by itself. It is input to the choices in performance.py, and every number it
uses comes from cfg['phrasing'] (references/vocal-engine/defaults.json).
"""
import numpy as np


def analyse(events, cfg):
    """Piece-level context from the vocal events and the resolved config.

    tempo_bpm comes from the score (render_natural fills it in) or the preset; 0 means unknown and switches
    metric accents and tempo scaling off rather than guessing a grid."""
    ph = cfg.get('phrasing') or {}
    tempo = float(ph.get('tempo_bpm') or 0.0)
    vs = np.array([float(e.get('v', 80)) for e in events], dtype=float) if events else np.array([80.0])
    pitches = np.array([float(e['p']) for e in events], dtype=float) if events else np.array([60.0])
    onsets = np.array([float(e['t']) for e in events], dtype=float) if events else np.array([0.0])
    span = float(onsets.max() - onsets.min()) + 1e-6
    density = float(len(events)) / span if len(events) > 1 else 1.0
    return dict(tempo_bpm=tempo,
                beat_s=(60.0 / tempo) if tempo > 0 else None,
                beats_per_bar=int(ph.get('beats_per_bar', 4)),
                energy=float(np.clip((vs.mean() - 55.0) / 65.0, 0.0, 1.0)),
                velocity_span=float(np.clip((vs.max() - vs.min()) / 50.0, 0.0, 1.0)),
                density=float(np.clip(density, 0.0, 8.0)),
                register=float(np.clip((pitches.mean() - 45.0) / 35.0, 0.0, 1.0)),
                expression=str((cfg.get('ensemble') or {}).get('expression') or ''),
                intensity=float((cfg.get('ensemble') or {}).get('expression_intensity', 1.0)),
                role=str(ph.get('role') or 'melody'))


def phrase_context(notes, ctx, cfg, index, count):
    """Per-phrase context: position in the line, melodic direction, length, energy, register."""
    add = cfg.get('phrasing') or {}
    first, last = float(notes[0]['p']), float(notes[-1]['p'])
    lo = min(float(n['p']) for n in notes)
    hi = max(float(n['p']) for n in notes)
    dead = float(add.get('direction_deadband_semitones', 2.0))
    step = last - first
    direction = 0.0 if abs(step) < dead else (1.0 if step > 0 else -1.0)
    span_s = float(notes[-1]['t'] + notes[-1].get('dur', 0.0) - notes[0]['t'])
    vel = np.array([float(n.get('v', 80)) for n in notes], dtype=float)
    return dict(ctx, index=index, count=count, position=(index / max(count - 1, 1)),
                is_first=index == 0, is_last=index == count - 1, direction=direction,
                span_s=span_s, amp_semitones=hi - lo, mean_velocity=float(vel.mean()),
                note_count=len(notes),
                phrase_energy=float(np.clip((vel.mean() - 50.0) / 70.0, 0.0, 1.0)))
