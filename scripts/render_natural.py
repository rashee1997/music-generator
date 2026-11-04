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

#!/usr/bin/env python3
"""render_natural.py - render a "natural score" with REAL sampled instruments, one stem per track.

    python3 render_natural.py score.json --out song.wav            # full pipeline: humanize -> stems -> mix -> master
    python3 render_natural.py score.json --stems-only --stems-dir stems/

What it does for each track (see references/instruments-and-vocals/natural-instruments.md):
  1. humanize the notes (timing drift, melody lead, velocity shaping, strum, legato) - humanize.py
  2. play them through a SoundFont with tinysoundfont, using
       * a separate MIDI channel per sustained note, so each note gets its own
         - vibrato (pitch-bend LFO with delayed onset, random rate/depth per note)
         - expression curve (bow swell / breath attack) instead of a flat organ-like level
         - tiny random detune (no two notes are identical -> round-robin feel)
       * sustain-pedal (CC64) for piano / harp / guitar-like instruments
       * a global/track "dynamics" curve (CC11) so crescendos and diminuendos actually happen
  3. normalise each stem to a common loudness (so gain_db means the same thing everywhere)
  4. hand the stems to mixer.py (EQ, compression, sidechain, reverb, stereo, master)

Score format (JSON). Times are BEATS. Pitches are MIDI numbers (drums may use names: "kick","snare","hat_closed").
{
  "title": "Rain on the window", "bpm": 66, "ts": [4,4], "key": "D minor",
  "seed": 7, "humanize": "natural",          # tight | natural | loose | rubato | {custom dict, see humanize.PRESETS}
  "swing": 0.5, "rubato": 0.03, "ritard": 0.35, "ritard_beats": 6,
  "tempo_points": [[0,66],[48,60]],           # optional tempo map (linear ramps)
  "dynamics": [[0,0.5],[32,0.9],[64,0.4]],    # optional global loudness arc 0..1 (beats) - the emotional shape
  "room": "hall", "master": {"lufs": -14, "true_peak": -1.5},
  "tracks": [
    {"name":"piano","instrument":"piano","role":"chord","gain_db":-4,"pan":-0.1,"reverb":0.2,
     "pedal":"auto", "notes":[{"t":0,"d":4,"p":62,"v":0.55}, ...]},
    {"name":"cello","instrument":"cello","role":"melody","vibrato":{"depth_cents":22,"rate_hz":5.4,"delay_ms":260},
     "expression":"bow","notes":[...]},
    {"name":"drums","instrument":"brush","role":"drum","notes":[{"t":0,"d":0.25,"p":"kick","v":0.7}]}
  ]
}
"""
import argparse
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsp
import humanize as hz
import soundbank as sb
import vocals
import presets
import mix_schema
import mechanics
import cli_util

SR = 44100

# instrument groups: default expression + vibrato + whether each note should get its own channel
SUSTAINED = {'violin', 'viola', 'cello', 'double_bass', 'contrabass', 'strings', 'string_ensemble', 'slow_strings',
             'fast_strings', 'synth_strings', 'tremolo_strings', 'choir', 'choir_aahs', 'oohs', 'voice_oohs',
             'synth_voice', 'flute', 'piccolo', 'recorder', 'pan_flute', 'oboe', 'english_horn', 'clarinet',
             'bassoon', 'sax', 'alto_sax', 'tenor_sax', 'soprano_sax', 'baritone_sax', 'trumpet', 'trombone',
             'horn', 'french_horn', 'tuba', 'brass', 'brass_section', 'muted_trumpet', 'shakuhachi', 'ocarina',
             'whistle', 'harmonica', 'accordion', 'organ', 'reed_organ', 'harmonium', 'pipe_organ', 'church_organ',
             'warm_pad', 'pad', 'halo_pad', 'sweep_pad', 'choir_pad', 'bowed_pad', 'polysynth', 'atmosphere',
             'soundtrack', 'shehnai', 'bagpipes', 'fiddle', 'square_lead', 'saw_lead', 'solo_vox', 'bottle'}
PEDAL = {'piano', 'grand_piano', 'bright_piano', 'epiano', 'rhodes', 'electric_piano', 'harp', 'celesta',
         'glockenspiel', 'vibraphone', 'vibes', 'marimba', 'music_box', 'kalimba', 'koto', 'dulcimer'}
BOWED = {'violin', 'viola', 'cello', 'double_bass', 'contrabass', 'strings', 'string_ensemble', 'slow_strings',
         'fast_strings', 'synth_strings', 'tremolo_strings', 'fiddle', 'bowed_pad', 'choir', 'choir_aahs', 'oohs',
         'voice_oohs', 'warm_pad', 'pad', 'halo_pad', 'sweep_pad', 'choir_pad', 'polysynth', 'atmosphere',
         'soundtrack', 'organ', 'pipe_organ', 'church_organ', 'reed_organ', 'harmonium', 'accordion', 'synth_voice'}
VIBRATO_DEFAULT = {
    'violin': (24, 5.8, 0.22), 'viola': (22, 5.5, 0.25), 'cello': (22, 5.2, 0.28), 'double_bass': (12, 4.8, 0.3),
    'strings': (7, 5.5, 0.3), 'string_ensemble': (7, 5.5, 0.3), 'slow_strings': (7, 5.2, 0.35),
    'fiddle': (20, 6.0, 0.2), 'flute': (4.5, 5.0, 0.3), 'piccolo': (6, 5.2, 0.3), 'oboe': (10, 5.4, 0.3),
    'english_horn': (10, 5.2, 0.3), 'sax': (16, 5.4, 0.35), 'alto_sax': (16, 5.4, 0.35), 'tenor_sax': (18, 5.0, 0.35),
    'soprano_sax': (14, 5.6, 0.3), 'baritone_sax': (14, 4.8, 0.4), 'trumpet': (7, 5.4, 0.4), 'horn': (6, 5.0, 0.4),
    'french_horn': (6, 5.0, 0.4), 'trombone': (8, 5.0, 0.4), 'clarinet': (0, 5, 0), 'bassoon': (6, 5.0, 0.4),
    'choir': (6, 5.4, 0.3), 'oohs': (8, 5.4, 0.3), 'shakuhachi': (14, 5.0, 0.3), 'ocarina': (8, 5.0, 0.3),
    'synth_voice': (10, 5.5, 0.3), 'harmonica': (10, 5.0, 0.3), 'solo_vox': (22, 5.6, 0.3),
}
import world as _world
SUSTAINED |= _world.SUSTAINED
BOWED |= _world.BOWED
VIBRATO_DEFAULT.update(_world.VIBRATO)
GLIDE_S = 0.14          # a note with 'gl' (cents) starts that far off pitch and slides in over this long
HAND_PERC_WORDS = ('tabla', 'darbuka', 'djembe', 'bongo', 'conga', 'doumbek', 'riq', 'kanjira', 'tombak', 'dhol')
# repeated strokes alternate to the family's next sample: {pitch: (alt, probability of a swap)}
ALT_KEY = {60: (62, 0.35), 62: (60, 0.35),          # bongo_high <-> conga_mute (hand percussion)
           38: (40, 0.30), 40: (38, 0.30),          # snare <-> electric snare
           36: (35, 0.25), 35: (36, 0.25),          # kick <-> acoustic bass drum
           42: (44, 0.20), 44: (42, 0.20)}          # closed hat <-> pedal hat
# one-sample percussion: a sample swap would be obvious, so vary level and timing instead
SINGLE_HIT = {39, 54, 82}
PLUCK = {'acoustic_guitar', 'nylon_guitar', 'steel_guitar', 'harp', 'oud', 'kora', 'guzheng'}
PLUCK_TAIL_S = 0.22                                 # minimum body ring after note-off, so a guitar is not cut dead
LEVEL_BY_ROLE = {'melody': -3, 'counter': -6, 'chord': -8, 'pad': -11, 'bass': -6, 'arp': -9, 'drum': -7, 'fx': -10}
DYN_RANGE_DB = 18.0
REPORT = {}


def _name(inst):
    return str(inst).lower().strip().replace(' ', '_').replace('-', '_')


def lvl2cc(level):
    """linear 0..1 loudness (1 = 0 dB) -> CC11 value. TinySoundFont maps expression ~quadratically."""
    level = float(np.clip(level, 0.0, 1.0))
    amp = 10 ** (-(1 - level) * DYN_RANGE_DB / 20.0)
    return int(np.clip(round(127 * np.sqrt(amp)), 0, 127))


def curve_at(points, beat):
    if not points:
        return 1.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return float(np.interp(beat, xs, ys))


# Pitch-bend range per microtone channel, set with RPN 0 at the channel's first note. The old default (+-2 semitones)
# clipped every glide wider than 200 cents, which the KB's talking-drum and gamaka glides exceed.
BEND_SEMIS = 12
STATS = {'clipped': 0, 'collisions': 0}      # filled by a render; quality_gate.py reads them
_STATS_LOCK = threading.RLock()               # re-entrant: a helper may be called inside a guarded block
                                              # SFZ tracks render in parallel threads; every REPORT/STATS write goes through the helpers below


def _record(name, **fields):
    """Merge one track's report fields. One lock for every writer, so no branch can forget it."""
    with _STATS_LOCK:
        REPORT.setdefault(name, {}).update(fields)


def _count(key, n=1):
    with _STATS_LOCK:
        STATS[key] = STATS.get(key, 0) + n


def _report_entry(name):
    """A copy of one track's report (read side of the same lock)."""
    with _STATS_LOCK:
        return dict(REPORT.get(name) or {})


def _reset_stats():
    with _STATS_LOCK:
        STATS.update(clipped=0, collisions=0)


_SYNTH_CACHE = {}                              # (sr, sfpath) -> [Synth, sfid, Lock]: the 32 MB bank is parsed once


def _borrow_synth(sfpath, sample_rate):
    """One loaded SoundFont per (sample rate, path), shared by every track of this process.

    Re-parsing GeneralUser GS costs a disk read and a decode per track; a shared Synth with its channels reset is
    byte-identical to a fresh one for the next track. The lock is held for one track at a time (tracks render
    sequentially), so two tracks can never fight over a channel.
    """
    import tinysoundfont
    key = (int(sample_rate), os.path.abspath(str(sfpath)))
    with _STATS_LOCK:
        ent = _SYNTH_CACHE.get(key)
        if ent is None:
            s = tinysoundfont.Synth(samplerate=int(sample_rate), gain=0)
            ent = [s, s.sfload(sfpath), threading.Lock()]
            _SYNTH_CACHE[key] = ent
    ent[2].acquire()
    s = ent[0]
    try:                                   # a previous track's pedals, bends and expression must not leak
        if hasattr(s, 'notes_off'):
            s.notes_off()
        for ch in range(16):
            s.pitchbend(ch, 8192)
            s.control_change(ch, 11, 127)
            s.control_change(ch, 7, 127)
    except Exception:
        pass
    return s, ent[1], ent[2]


def bend_value(cents):
    if abs(cents) > BEND_SEMIS * 100:
        _count('clipped')
    return int(np.clip(round(8192 + cents * 8192.0 / (BEND_SEMIS * 100.0)), 0, 16383))


def _expr_curve(kind, n_steps, dur, rng):
    """Relative loudness (0..1] over the life of one note."""
    x = np.linspace(0, 1, n_steps)
    t = x * dur
    if isinstance(kind, dict):
        atk = float(kind.get('attack_s', 0.05))
        dec = float(kind.get('decay_s', 0.1))
        sus = float(kind.get('sustain_level', 0.7))
        rel = float(kind.get('release_s', 0.1))
        g = np.ones(n_steps)
        for i, ti in enumerate(t):
            if ti < atk:
                g[i] = ti / max(atk, 1e-4)
            elif ti < atk + dec:
                frac = (ti - atk) / max(dec, 1e-4)
                g[i] = 1.0 - (1.0 - sus) * frac
            elif ti < dur - rel:
                g[i] = sus
            else:
                frac = max(0.0, (dur - ti) / max(rel, 1e-4))
                g[i] = sus * frac
        return np.clip(g, 0.05, 1.0)
    if kind == 'bow':
        g = 0.55 + 0.45 * (0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.14, 0, 1)))      # raised-cosine attack, no hump swell
        g *= 1 - 0.18 * np.clip((x - 0.82) / 0.18, 0, 1) ** 1.5 if dur > 0.5 else 1
    elif kind == 'breath':
        g = 0.7 + 0.3 * (0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.08, 0, 1)))        # raised-cosine attack; no sine tremolo (it reads as flutter)
        g *= 1 - 0.10 * np.clip((x - 0.55) / 0.45, 0, 1)
    elif kind == 'pluck':                 # sitar, kora, guitar: an instant strike, then the string rings down
        g = np.exp(-3.0 * t / max(dur, 0.2))
    elif kind == 'mallet':                # balafon, marimba, kalimba: a bright strike, a softer ring
        g = np.exp(-1.6 * t / max(dur, 0.2))
    else:
        g = np.ones(n_steps)
    return np.clip(g / max(g.max(), 1e-6), 0.05, 1.0)


def _oversample():
    """How many times the render rate to run the sampler at (mix preset `render.oversample`).

    tinysoundfont resamples a sample with linear interpolation; transposing a note up leaves images above the note's
    own band, and measured on GeneralUser GS the share of energy above 15 kHz rose 11 dB from C4 to C7 on the flute and
    19 dB on the violin. Rendering at a multiple of the rate and decimating with a proper filter moves those images
    above the delivered Nyquist instead of folding them into the audible band. 1 = the old behaviour.
    """
    try:
        cfg = mix_schema.with_defaults(presets.mix())
        return max(1, min(8, int((cfg.get('render') or {}).get('oversample', 1))))
    except Exception:
        return 1


class Voice:
    """One Synth instance playing one track; collects events then renders."""

    def __init__(self, sfpath, sample_rate=SR, oversample=1):
        import tinysoundfont
        self.ts = tinysoundfont
        self.os = max(1, int(oversample))
        self.synth, self.sfid, self._lock = _borrow_synth(sfpath, sample_rate * self.os)
        self.sr = sample_rate
        self.events = []        # (sample, order, kind, ch, a, b) at the render rate (sr * os)
        self.prog = {}

    def _release(self):
        """Give the shared Synth back (idempotent). Called at the end of render, and by __del__ if a render raised."""
        lock, self._lock = getattr(self, '_lock', None), None
        if lock is not None:
            try:
                if hasattr(self.synth, 'notes_off'):
                    self.synth.notes_off()
            except Exception:
                pass
            lock.release()

    def __del__(self):
        try:
            self._release()
        except Exception:
            pass

    def program(self, ch, bank, preset, drums=False):
        self.synth.program_select(ch, self.sfid, bank, preset)
        self.prog[ch] = (bank, preset)

    def add(self, t, kind, ch, a=0, b=0):
        order = {'cc': 0, 'bend': 1, 'off': 2, 'on': 3}[kind]
        self.events.append((int(round(t * self.sr * self.os)), order, kind, ch, a, b))

    def render(self, tail=2.5):
        ev = sorted(self.events, key=lambda e: (e[0], e[1]))
        s = self.synth
        chunks, pos = [], 0
        for smp, _, kind, ch, a, b in ev:
            if smp > pos:
                chunks.append(np.frombuffer(bytes(s.generate(smp - pos)), dtype=np.float32).reshape(-1, 2).copy())
                pos = smp
            if kind == 'on':
                s.noteon(ch, a, b)
            elif kind == 'off':
                s.noteoff(ch, a)
            elif kind == 'cc':
                s.control_change(ch, a, b)
            elif kind == 'bend':
                s.pitchbend(ch, a)
        chunks.append(np.frombuffer(bytes(s.generate(int(tail * self.sr * self.os))), dtype=np.float32).reshape(-1, 2).copy())
        s.notes_off() if hasattr(s, 'notes_off') else None
        out = np.concatenate(chunks) if chunks else np.zeros((1, 2), np.float32)
        if self.os > 1 and len(out):                 # decimate with a real filter: the images stay above Nyquist
            from scipy.signal import resample_poly
            out = resample_poly(out, 1, self.os, axis=0).astype(np.float32)
        self._release()
        return out


def _drum_key(p):
    if isinstance(p, str):
        return sb.DRUM_KEYS[p]
    return int(p)


def _mean_vel(ev):
    """The stem's mean MIDI velocity: dsp.enhance_sf2_dynamics uses it to make a soft part darker."""
    return float(np.mean([e['v'] for e in ev])) if ev else None


def _is_sfz_track(tr):
    """True when render_track would take the SFZ path for this track (mirrors its dispatch order)."""
    raw_inst = str(tr.get('instrument', 'piano'))
    if raw_inst.startswith(('clone:', 'sfx:', 'env:')):
        return False
    if raw_inst.startswith('sfz:'):
        return True
    inst_cfg = presets.find_instrument(raw_inst) or presets.find_instrument(_name(raw_inst))
    return bool(tr.get('sfz') or (inst_cfg and inst_cfg.get('sfz')))


def _sfz_track(tr, tm, cfg, seed, ts, swing, global_dyn, raw_inst, inst_cfg, quality=10, polyphony=256):
    """Stem for a track played by an SFZ library. Returns None only when the block says fallback "gm" and the library is missing
    (a warning is printed and recorded in REPORT); any other failure raises with the command that fixes it."""
    import sfz_render
    blk = sfz_render.block_of(raw_inst, tr, inst_cfg)
    name = tr.get('name', raw_inst)
    role = tr.get('role', (inst_cfg or {}).get('role', 'melody'))
    notes = [dict(n, p=cli_util.midi_int(n['p'], f"track {name}: ")) for n in tr.get('notes', [])]
    ev = hz.humanize_track(notes, tm, tr.get('humanize', cfg), role=role, seed=seed, ts=tuple(ts), swing=swing)
    _record(name, **hz.event_stats(ev, tm))
    track_dyn = tr.get('dynamics')

    def dyn_level(t_sec):
        b = float(tm.beat(t_sec))
        return curve_at(global_dyn, b) * (curve_at(track_dyn, b) if track_dyn else 1.0)
    offs = np.array([e['t'] + e['dur'] for e in ev], dtype=float)
    try:
        x = sfz_render.render(ev, offs, tm, blk, dyn_level, SR, quality=quality, polyphony=polyphony)
    except sfz_render.SfzUnavailable as ex:
        if blk.get('fallback') == 'gm':
            msg = f'track "{name}": SFZ library unavailable, played by the GM SoundFont instead ({ex})'
            sys.stderr.write('[sfz] ' + msg + '\n')
            _record(name, sfz_fallback=str(ex))
            _count('sfz_fallback')
            return None
        raise RuntimeError(f'track "{name}": {ex}')
    _record(name, sfz=f"{blk['library']}/{blk['patch']}")
    return x


def render_track(tr, tm, sfpath, global_dyn, cfg, seed, ts, swing, key_lead=None):
    """Return stereo float32 stem for one track (list of notes -> audio)."""
    raw_inst = str(tr.get('instrument', 'piano'))
    if raw_inst.startswith('clone:'):                      # user-cloned instrument (clone_instrument.py)
        import clone_instrument as ci
        path = raw_inst.split(':', 1)[1]
        if not os.path.isabs(path) and not os.path.exists(path):
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', path)
        inst_obj = ci.load_instrument(path)
        role = tr.get('role', 'melody')
        ev = hz.humanize_track([dict(n) for n in tr.get('notes', [])], tm, tr.get('humanize', cfg), role=role,
                               seed=seed, ts=tuple(ts), swing=swing)
        _record(tr.get('name', 'clone'), **hz.event_stats(ev, tm))
        return ci.render_events(inst_obj, ev)
    if raw_inst.startswith('sfx:'):                        # procedural effect from sfx.py; each note = one hit
        import sfx
        name = raw_inst.split(':', 1)[1]
        out = np.zeros((int(tm.sec(tm.total_beats) * SR) + SR, 2), np.float32)
        for i, n in enumerate(tr.get('notes', [])):
            t0, t1 = tm.sec(n['t']), tm.sec(n['t'] + n.get('d', 1.0))
            x, _, _ = sfx.make(name, max(0.1, t1 - t0), SR, seed + i, **n.get('kw', {}))
            amp = float(n.get('v', 0.8))
            x = (x * (amp / 127.0 if amp > 1.0 else amp)).astype(np.float32)     # v: 0..1 gain, or a MIDI velocity
            i0 = int(t0 * SR)
            seg = x[:max(0, len(out) - i0)]
            out[i0:i0 + len(seg)] += seg[:, None]
        _record(tr.get('name', name), sfx=name, hits=len(tr.get('notes', [])))
        return out
    sfz_tried = False
    if raw_inst.startswith('sfz:'):                        # a track played by an SFZ library (sfz_render.py)
        out = _sfz_track(tr, tm, cfg, seed, ts, swing, global_dyn, raw_inst, None)
        if out is not None:
            return out
        sfz_tried = True
        raw_inst = 'piano'                                 # fallback "gm" was set and the library is missing: reported by _sfz_track
    inst = _name(raw_inst)
    inst_cfg = presets.find_instrument(raw_inst) or presets.find_instrument(inst)
    vocal_cfg = presets.find_vocal(raw_inst) or presets.find_vocal(inst)
    if not sfz_tried and (tr.get('sfz') or (inst_cfg and inst_cfg.get('sfz'))):
        out = _sfz_track(tr, tm, cfg, seed, ts, swing, global_dyn, raw_inst, inst_cfg)
        if out is not None:
            return out
        base_gm = (inst_cfg or {}).get('gm') or (inst_cfg or {}).get('instrument')
        inst_cfg = dict(inst_cfg or {}, gm=base_gm or ('violin' if tr.get('role') in ('melody', 'counter') else 'piano'))
        inst_cfg.pop('sfz', None)

    env_name = tr.get('environment') or (inst_cfg and inst_cfg.get('environment'))
    if raw_inst.startswith('env:') or tr.get('role') == 'environment' or env_name:
        import environment
        env_key = env_name or (raw_inst.split(':', 1)[1] if raw_inst.startswith('env:') else inst)
        dur_s = float(tm.sec(tm.total_beats))
        notes = tr.get('notes') or []
        if notes and not tr.get('full_length'):
            # the notes say when the place is audible: render only that span, fade it in and out, leave the rest silent
            t0 = float(tm.sec(min(n['t'] for n in notes)))
            t1 = min(dur_s, float(tm.sec(max(n['t'] + n.get('d', 1.0) for n in notes))))
            span = max(1.0, t1 - t0)
            seg = environment.render_environment_preset(env_key, duration_s=span, sr=SR, seed=seed)
            fade = int(min(2.0, span / 4.0) * SR)
            if fade > 1:
                ramp = np.sin(np.linspace(0.0, np.pi / 2.0, fade)) ** 2
                seg[:fade] *= ramp[:, None]
                seg[-fade:] *= ramp[::-1][:, None]
            out = np.zeros((int(dur_s * SR), 2), np.float32)
            i0 = int(t0 * SR)
            out[i0:i0 + len(seg)] = seg[:max(0, len(out) - i0)]
            _record(tr.get('name', 'environment'), dur_s=round(span, 2), start_s=round(t0, 2), env=str(env_key))
            return out
        _record(tr.get('name', 'environment'), dur_s=round(dur_s, 2), env=str(env_key))
        return environment.render_environment_preset(env_key, duration_s=dur_s, sr=SR, seed=seed)

    if tr.get('synthesis') == 'formant' or (inst_cfg and inst_cfg.get('synthesis') == 'formant') or vocal_cfg or inst in vocals.INSTRUMENTS:
        ev = hz.humanize_track([dict(n, p=cli_util.midi_int(n['p'], f"track {tr.get('name')}: ")) for n in tr.get('notes', [])], tm, tr.get('humanize', cfg),
                               role=tr.get('role', 'melody'), seed=seed, ts=tuple(ts), swing=swing)
        _record(tr.get('name', inst), **hz.event_stats(ev, tm))
        merged_vocal = {}
        if vocal_cfg:
            merged_vocal.update(vocal_cfg)
        if inst_cfg and 'vocal' in inst_cfg:
            merged_vocal.update(inst_cfg['vocal'])
        for k in ('voices', 'vowel', 'formants', 'bandwidths', 'attack', 'release', 'breath', 'vib_cents', 'vib_hz', 'vib_delay',
                  'style', 'spread_cents', 'pan_width', 'formant_scale', 'expression', 'expression_intensity', 'hum'):
            if k in tr:
                merged_vocal[k] = tr[k]
        if isinstance(tr.get('vocal'), dict):          # a track's own `vocal` block: any key or section of the vocal config
            merged_vocal.update(tr['vocal'])
        ph = dict(merged_vocal.get('phrasing') or {})   # copy: never mutate a preset that is shared between tracks
        if not ph.get('tempo_bpm'):                     # the score's tempo is the grid the singer phrases against
            bpm = np.atleast_1d(getattr(tm, 'base_bpm', 0.0)).ravel()
            ph['tempo_bpm'] = float(bpm[0]) if len(bpm) else 0.0
        if not ph.get('beats_per_bar'):
            ph['beats_per_bar'] = int(ts[0] if ts else 4)
        ph.setdefault('role', str(tr.get('role', 'melody')))
        merged_vocal['phrasing'] = ph
        stem, _vinfo = vocals.render_choir(ev, sr=SR, voices=int(merged_vocal.get('voices', tr.get('voices', 5))),
                                           vowel=merged_vocal.get('vowel', tr.get('vowel', 'a')), seed=seed,
                                           formant_scale=float(merged_vocal.get('formant_scale', tr.get('formant_scale', 1.0))),
                                           hum=(inst == 'hum_formant' or merged_vocal.get('hum', False)), config=merged_vocal,
                                           return_stems=True)
        _record(tr.get('name', inst), vocal=dict(_vinfo['report']))   # the gate's vocal.* rows read this
        return stem

    base = inst_cfg and (inst_cfg.get('gm') or inst_cfg.get('instrument'))   # the GM sound a preset is built on
    if base:
        bank, preset, is_drum = sb.resolve(base)
    else:
        bank, preset, is_drum = sb.resolve(inst)
    role = tr.get('role', 'drum' if is_drum else 'chord')
    rng = np.random.default_rng(seed)
    notes = []
    for n in tr.get('notes', []):
        n = dict(n)
        n['p'] = _drum_key(n['p']) if is_drum else cli_util.midi_int(n['p'], f"track {tr.get('name')}: ")
        notes.append(n)
    swing_u = tr.get('swing_unit', 0.25 if tr.get('swing_16th') or (swing > 0.5 and any(abs(n['t'] * 4 - round(n['t'] * 4)) < 1e-4 and abs(n['t'] * 2 - round(n['t'] * 2)) > 1e-4 for n in notes)) else 0.5)
    ev = hz.humanize_track(notes, tm, tr.get('humanize', cfg), role=role, seed=seed, ts=tuple(ts), swing=swing, swing_unit=swing_u,
                           detune_cents=tr.get('detune_cents', 0.0), strum_dir=tr.get('strum', 'alt'), instrument=inst,
                           articulation=(tr.get('articulation') or (inst_cfg or {}).get('articulation')),
                           bpm=float(np.atleast_1d(getattr(tm, 'base_bpm', 96.0)).ravel()[0]))
    _record(tr.get('name', inst), **hz.event_stats(ev, tm))
    vox = Voice(sfpath, SR, _oversample())
    track_dyn = tr.get('dynamics')
    detune = float(tr.get('detune_cents', 0.0))

    def dyn_level(t_sec):
        b = float(tm.beat(t_sec))
        return curve_at(global_dyn, b) * (curve_at(track_dyn, b) if track_dyn else 1.0)

    if is_drum:
        vox.program(9, 128, preset, drums=True)
        # no drum ever repeats one identical PCM sample: accents move, rapid strokes alternate sample or level,
        # and layered handclaps get a second (softer) pair of hands
        hand = any(k in str(tr.get('name', '')).lower() for k in HAND_PERC_WORDS)
        jrng = np.random.default_rng(seed + 7)
        last_t = {}
        for e in ev:
            lvl = dyn_level(e['t'])
            v = e['v'] * (0.72 + 0.28 * lvl)
            p = e['p']
            dt = e['t'] - last_t.get(p, -9.0)
            rapid = dt < (0.4 if p in SINGLE_HIT else 0.35)
            if rapid:
                v *= 1 + jrng.normal(0, 0.05)                      # same sample, never the same level
            if hand:
                v *= 1 + jrng.normal(0, 0.07)                      # accent variation (vel_sigma ~9)
            alt = ALT_KEY.get(p)
            if alt and rapid and jrng.random() < alt[1]:
                p = alt[0]                                         # the family's next sample (round robin)
            if p == 39 and e['v'] > 90 and jrng.random() < 0.35:    # a clap is several pairs of hands, not one sample
                off = jrng.uniform(-0.008, 0.008)
                vox.add(max(0.0, e['t'] + off), 'on', 9, 37, int(np.clip(v * 0.28, 1, 127)))
                vox.add(max(0.0, e['t'] + off) + 0.1, 'off', 9, 37)
            last_t[e['p']] = e['t']
            if hand and jrng.random() < 0.25 and e['v'] > 0.5 and e['t'] > 0.04:   # 32nd-note flam: soft hit 25 ms before
                vox.add(e['t'] - 0.025, 'on', 9, p, int(np.clip(v * 0.3, 1, 127)))
                vox.add(e['t'] - 0.013, 'off', 9, p)
            vox.add(e['t'], 'on', 9, p, int(np.clip(round(v), 1, 127)))
            vox.add(e['t'] + 0.12, 'off', 9, p)
        end = max((e['t'] for e in ev), default=0)
        return dsp.enhance_sf2_dynamics(vox.render(tail=2.5), sr=SR, role=role, velocity=_mean_vel(ev))

    # note-off times: let a plucked body ring past the written note-off, but never into a re-strike of the same pitch
    # (a note-off on a shared channel cuts every sounding instance of that pitch, including the new one).
    offs = np.array([e['t'] + e['dur'] for e in ev], dtype=float)
    nxt = {}
    for i in range(len(ev) - 1, -1, -1):
        e = ev[i]
        off = e['t'] + e['dur']
        if inst in PLUCK and e.get('art') != 'staccato':
            off = max(off, e['t'] + PLUCK_TAIL_S)
        if e['p'] in nxt:
            off = min(off, max(e['t'] + 0.02, nxt[e['p']] - 0.005))
        offs[i] = off
        nxt[e['p']] = e['t']

    per_note = tr.get('per_note_channels')
    if per_note is None and inst_cfg:
        per_note = inst_cfg.get('sustained') or inst_cfg.get('per_note_channels')
    if per_note is None:
        per_note = inst in SUSTAINED or any('c' in e or 'gl' in e for e in ev)
        # a pad on one channel per note gets a different random detune on every note: that beats like a chorus gone wrong.
        # A chord keeps per_note: it is the only way its notes get an attack envelope instead of a flat body.
        if per_note and tr.get('role') == 'pad' and not any('c' in e or 'gl' in e for e in ev):
            per_note = False

    vib = tr.get('vibrato')
    if vib is None and inst_cfg and 'vibrato' in inst_cfg:
        vib = inst_cfg['vibrato']
    if vib is None:
        d = VIBRATO_DEFAULT.get(inst)
        vib = dict(depth_cents=d[0], rate_hz=d[1], delay_ms=d[2] * 1000) if d else dict(depth_cents=0)

    expr_kind = tr.get('expression')
    if expr_kind is None and inst_cfg and 'expression' in inst_cfg:
        expr_kind = inst_cfg['expression']
    if expr_kind is None:
        expr_kind = 'bow' if inst in BOWED else ('flat' if inst in _world.PLUCKED else ('breath' if per_note else 'flat'))
    step = 0.006

    if per_note:
        pool = [c for c in range(16) if c != 9]
        free_at = {c: -1.0 for c in pool}
        busy_until = {c: -1.0 for c in pool}
        open_p = {}                              # the pitch each channel is currently sounding
        for j, e in enumerate(ev):
            ch = min(pool, key=lambda c: (free_at[c] > e['t'] - 0.5, free_at[c]))
            if busy_until[ch] > e['t']:
                _count('collisions')
                # every channel is still sounding: end the note on this one just before the new attack. The stolen
                # note's own scheduled note-off would otherwise land later and silence the note that replaced it,
                # and the bend below would be applied while two notes sound on the same channel.
                if open_p.get(ch):
                    vox.add(max(0.0, e['t'] - 0.002), 'off', ch, open_p[ch])
                    open_p[ch] = None
            if ch not in vox.prog:
                vox.program(ch, bank, preset)
                for num, val in ((101, 0), (100, 0), (6, BEND_SEMIS), (38, 0)):      # RPN 0: pitch-bend range
                    vox.add(0.0, 'cc', ch, num, val)
            dur = max(0.02, float(offs[j] - e['t']))
            busy_until[ch] = offs[j]
            free_at[ch] = offs[j] + 0.8
            n_steps = max(2, int(dur / step) + 1)
            ts_ = e['t'] + np.arange(n_steps) * step
            g = _expr_curve(expr_kind, n_steps, dur, rng)
            if inst in BOWED:                      # a bow change is audible: alternate strokes and dip the first 50 ms
                if j % 2:
                    fade = np.clip(1.0 - np.arange(n_steps) * step / 0.05, 0.0, 1.0)
                    g = g * (1.0 - 0.06 * fade)
            lv = np.array([dyn_level(t) for t in ts_]) * g
            # initial state BEFORE the note-on, so it starts at the right level and pitch
            micro_spread = 0.8 if role in ('chord', 'pad') else 3.0     # a chord's notes must not beat against each other
            micro = rng.normal(0, micro_spread) + detune + e.get('c', 0.0)
            glide = e.get('gl', 0.0)
            gs = e.get('gs', GLIDE_S)                # meend glide length (per note), default GLIDE_S
            if inst in BOWED:                        # bowed strings: glides stay within 2 semitones, 0.08-0.15 s (no siren)
                glide = float(np.clip(glide, -200, 200))
                gs = float(np.clip(gs, 0.08, 0.15))
            depth = vib.get('depth_cents', 0) * (0.8 + 0.4 * rng.random())
            if role in ('chord', 'pad'):
                depth = 0.0     # each note would get its own LFO phase: that is the chorus beating, not the detune
            rate = vib.get('rate_hz', 5.5) * (1 + rng.normal(0, 0.04))
            delay = e.get('vd', vib.get('delay_ms', 250) / 1000.0)     # nyasa notes: vibrato waits longer
            phase = rng.random() * 6.283
            # human perturbation, not a clean LFO: healthy sustained phonation sits near 0.5 % jitter and 3-5 %
            # shimmer (acoustic-voice literature), and a perfectly periodic vibrato is the synth tell
            jitter_cents = float(vib.get('jitter_cents', 0.0))
            shimmer = float(vib.get('shimmer', 0.0))
            t0 = max(0.0, e['t'] - 0.001)
            last_cc, last_b = lvl2cc(lv[0]), bend_value(micro + glide)
            vox.add(t0, 'cc', ch, 11, last_cc)
            vox.add(t0, 'bend', ch, last_b)
            vox.add(e['t'], 'on', ch, e['p'], e['v'])
            open_p[ch] = e['p']
            for k in range(1, n_steps):
                t = ts_[k]
                if t >= offs[j]:
                    break
                cc = lvl2cc(lv[k] * (1.0 + shimmer * np.sin(2 * np.pi * 0.7 * (t - e['t']) + phase * 1.3))
                            if shimmer else lv[k])
                if cc != last_cc:                 # only changes are sent: a fine step costs nothing on a steady note
                    vox.add(t, 'cc', ch, 11, cc)
                    last_cc = cc
                age = t - e['t']
                slide = glide * (1 - min(age / gs, 1.0)) ** 2 if glide else 0.0
                if depth > 0 and dur > 0.30 and age > delay * 0.5:
                    ramp = np.clip((age - delay * 0.5) / 0.35, 0, 1)
                    cents = (micro + slide + depth * ramp * np.sin(2 * np.pi * rate * age + phase)
                             + jitter_cents * np.sin(2 * np.pi * 0.9 * age + phase * 1.7))
                    b = bend_value(cents)
                    if b != last_b:
                        vox.add(t, 'bend', ch, b)
                        last_b = b
                elif glide and age < gs + step:
                    b = bend_value(micro + slide)
                    if b != last_b:
                        vox.add(t, 'bend', ch, b)
                        last_b = b
            vox.add(offs[j], 'off', ch, e['p'])
            if open_p.get(ch) == e['p']:
                open_p[ch] = None
        stem = mechanics.add(vox.render(tail=3.0), tr, ev, sr=SR, seed=seed)
        return dsp.enhance_sf2_dynamics(stem, sr=SR, role=role, velocity=_mean_vel(ev))

    # shared channel (piano, guitar, plucked, mallets)
    vox.program(0, bank, preset)
    pedal = tr.get('pedal', 'auto' if inst in PEDAL else None)
    if pedal:
        if pedal == 'auto':
            changes = tr.get('pedal_beats') or list(np.arange(0, tm.total_beats, 4.0))
        else:
            changes = pedal if isinstance(pedal, list) else pedal.get('changes', [])
        for t, val in hz.auto_pedal(ev, tm, changes):
            vox.add(t, 'cc', 0, 64, val)
    if detune:
        vox.add(0, 'bend', 0, bend_value(detune))
    last_cc, t_cc = None, 0
    for t in np.arange(0, (ev[-1]['t'] if ev else 0) + 1, 0.015):         # dynamics curve
        cc = lvl2cc(dyn_level(t))
        if cc != last_cc:
            vox.add(t, 'cc', 0, 11, cc)
            last_cc = cc
    for j, e in enumerate(ev):
        vox.add(e['t'], 'on', 0, e['p'], e['v'])
        vox.add(offs[j], 'off', 0, e['p'])
    stem = mechanics.add(vox.render(tail=3.5), tr, ev, sr=SR, seed=seed)
    return dsp.enhance_sf2_dynamics(stem, sr=SR, role=role, velocity=_mean_vel(ev))


def _track_cache_dir():
    """Where every rendered stem is cached by content hash, so a killed/re-run pipeline, or a re-render after
    tweaking an unrelated track, skips what is already done. Keyed under the project (or the skill's user cache
    when there is none), never inside stems_dir (that is a deliverable, and may be trimmed/renamed)."""
    if presets.PROJECT_ROOTS:
        proj = os.path.dirname(presets.PROJECT_ROOTS[-1])
        d = os.path.join(proj, '.cache', 'stems')
    else:
        d = os.path.join(os.path.expanduser('~'), '.cache', 'music-generator', 'stems')
    os.makedirs(d, exist_ok=True)
    return d


_RENDERER_VERSION = 'natural-7'   # bump when the renderer changes what a stem sounds like or reports
_CODE_HASH = None


def _code_hash():
    """Identity of the code that makes the bytes: a cache must never return a stem from another renderer version."""
    global _CODE_HASH
    if _CODE_HASH is None:
        h = hashlib.sha1()
        here = os.path.dirname(os.path.abspath(__file__))
        for f in ('render_natural.py', 'dsp.py', 'sfz_render.py', 'environment.py', 'humanize.py'):
            p = os.path.join(here, f)
            try:
                with open(p, 'rb') as fh:
                    h.update(f.encode('utf-8'))
                    h.update(fh.read())
            except OSError:
                h.update(b'missing:' + f.encode('utf-8'))
        _CODE_HASH = h.hexdigest()
    return _CODE_HASH


def _preset_fingerprint(tr):
    """The resolved presets a track plays through. A preset edit must invalidate that track's cached stem."""
    raw = str(tr.get('instrument', ''))
    bare = raw.split(':', 1)[1] if ':' in raw else raw
    out = {}
    for kind in ('instrument', 'vocal', 'environment', 'sfx'):
        fn = getattr(presets, 'find_' + kind, None)
        if fn is None:
            continue
        for cand in (raw, bare, _name(bare)):
            try:
                cfg = fn(cand)
            except Exception:
                cfg = None
            if cfg:
                out[kind] = cfg
                break
    return out


def _track_cache_key(tr, seed, ts, swing, tm, global_dyn, sr, sfpath=None):
    """A hash of everything that changes the rendered bytes: the track, the tempo map, the renderer code, the
    resolved presets and the SoundFont itself. Same score + same project + same code -> same key, any process."""
    sf_id = None
    if sfpath:
        try:
            st = os.stat(sfpath)
            sf_id = [os.path.abspath(str(sfpath)), st.st_size, int(st.st_mtime)]
        except OSError:
            sf_id = str(sfpath)
    sig = json.dumps(dict(tr=tr, seed=seed, ts=list(ts), swing=swing, global_dyn=global_dyn, sr=sr,
                          renderer=_RENDERER_VERSION, code=_code_hash(), sf=sf_id,
                          presets=_preset_fingerprint(tr)),
                     sort_keys=True, default=str)
    h = hashlib.sha1(sig.encode('utf-8'))
    h.update(np.asarray(tm.secs).tobytes())
    return h.hexdigest()


def _render_cached(tr, name, tm, sfpath, global_dyn, cfg, seed, ts, swing):
    """render_track, through a disk cache keyed on everything that changes the bytes (score, presets, tempo, seed).
    Covers every track kind (SFZ, GM, env, sfx, vocal) so a re-run only re-renders what actually changed."""
    import soundfile as sf
    cache_path = os.path.join(_track_cache_dir(), _track_cache_key(tr, seed, ts, swing, tm, global_dyn, SR, sfpath) + '.wav')
    meta_path = os.path.splitext(cache_path)[0] + '.report.json'   # the REPORT entry for those bytes (vocal/sfz/env/...)
    if os.path.isfile(cache_path):
        x, file_sr = sf.read(cache_path, dtype='float32', always_2d=True)
        if file_sr == SR:
            entry = {}
            try:
                with open(meta_path, encoding='utf-8') as fh:
                    entry = json.load(fh)
            except (OSError, ValueError):
                pass                      # no sidecar (old cache): the bytes are still valid, the report is not
            _record(name, **entry, cached=True)
            return x
    x = render_track(tr, tm, sfpath, global_dyn, cfg, seed, ts, swing)
    if x is not None:
        try:
            tmp = cache_path + f'.tmp{os.getpid()}'
            # 32-bit float: the default WAV subtype is PCM_16, which quantized every cached stem (-90 dBFS of noise)
            # and hard-clipped any stem peaking above 1.0 on the way to disk. Cached audio must be the rendered audio.
            sf.write(tmp, np.asarray(x, dtype=np.float32), SR, format='WAV', subtype='FLOAT')
            os.replace(tmp, cache_path)      # atomic: a killed render never leaves a half-written cache file
            entry = _report_entry(name)      # written after the stem, so a half-written entry is never restored
            if entry:
                mt = meta_path + f'.tmp{os.getpid()}'
                with open(mt, 'w', encoding='utf-8') as fh:
                    json.dump(entry, fh, default=str)
                os.replace(mt, meta_path)
        except OSError:
            pass                              # caching is an optimization; a write failure must not break the render
    return x


def _mark_accompanied(tr, tracks):
    """For a melody or counter track, flag each note 'acc' = 1 when another pitched track is sounding at its onset.
    humanize.py leads the melody early only on those notes; a solo line stays on the beat."""
    if tr.get('role') not in ('melody', 'counter'):
        return tr
    others = [(n['t'], n['t'] + n.get('d', 0)) for o in tracks if o is not tr and o.get('role') != 'drum'
              for n in o.get('notes', [])]
    notes = []
    for n in tr.get('notes', []):
        sounding = any(a <= n['t'] < b for a, b in others)
        notes.append(dict(n, acc=1.0 if sounding else 0.0))
    return dict(tr, notes=notes)


def build_stems(score, sfpath=None, seed=None, verbose=True):
    """Humanize + render every track. Returns (stems dict name->(N,2) float32, meta, tempo map)."""
    # The caller registers the project (pipeline.py in project mode, run_gate from the score path). This function
    # must not guess one from the working directory: run from the skill folder it would adopt the skill's own
    # presets as a project and demand a per-piece mix preset from a scratch test cue.
    sfpath = sfpath or sb.ensure_soundfont()
    seed = score.get('seed', 7) if seed is None else seed
    ts = score.get('ts', [4, 4])
    tm = hz.tempo_map_for(score, seed=seed)      # the pipeline's reported duration is built the same way
    cfg = score.get('humanize', 'natural')
    _reset_stats()
    stems = {}
    marked = [(i, tr.get('name', f'track{i}'), _mark_accompanied(tr, score['tracks'])) for i, tr in enumerate(score['tracks'])]
    sfz_jobs = [(i, name, tr) for i, name, tr in marked if _is_sfz_track(tr)]
    other_jobs = [(i, name, tr) for i, name, tr in marked if not _is_sfz_track(tr)]

    for i, name, tr in other_jobs:
        if verbose:
            print(f'  rendering {name:12s} ({tr.get("instrument")}) ...', flush=True)
        stems[name] = _render_cached(tr, name, tm, sfpath, score.get('dynamics'), cfg, seed + 31 * i, ts, score.get('swing', 0.5))
        if verbose and _report_entry(name).get('cached'):
            print(f'  cached    {name}', flush=True)

    if sfz_jobs:
        # sfizz_render is one independent, CPU-bound subprocess per track with no internal thread flag (confirmed via
        # --help): the only real speedup is running several of these subprocesses at once. Each worker keeps its own
        # tempfile and process, so this is safe; _track_cache_dir() makes a killed/re-run pipeline resume for free.
        workers = max(1, min(len(sfz_jobs), int(os.environ.get('MUSICGEN_SFZ_WORKERS', '4'))))
        if verbose:
            print(f'  rendering {len(sfz_jobs)} SFZ track(s) across {workers} parallel worker(s) ...', flush=True)

        def _run(job):
            i, name, tr = job
            return name, _render_cached(tr, name, tm, sfpath, score.get('dynamics'), cfg, seed + 31 * i, ts, score.get('swing', 0.5))

        with ThreadPoolExecutor(max_workers=workers) as ex:
            # as_completed, not map: map yields in submission order, so one slow first track hides every stem that
            # finished behind it and the log looks stalled.
            for fut in as_completed([ex.submit(_run, job) for job in sfz_jobs]):
                name, stem = fut.result()
                if verbose:
                    cached = _report_entry(name).get('cached')
                    print(f'  {"cached   " if cached else "rendered "} {name}', flush=True)
                stems[name] = stem
    return stems, tm


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('score')
    ap.add_argument('--out', default='natural.wav')
    ap.add_argument('--seed', type=int, default=None)
    ap.add_argument('--stems-dir', default=None, help='also save each stem here')
    ap.add_argument('--stems-only', action='store_true')
    ap.add_argument('--soundfont', default=None)
    ap.add_argument('--no-master', action='store_true')
    a = ap.parse_args()
    import cli_util
    cli_util.require_file(a.score, 'score')
    score_path = os.path.abspath(a.score)
    p_dir = os.path.dirname(score_path)
    if os.path.basename(p_dir) in ('scores', 'score'):
        p_dir = os.path.dirname(p_dir)
    if os.path.isdir(os.path.join(p_dir, 'presets')):
        presets.add_project(p_dir)
    score = json.load(open(a.score, encoding='utf-8'))
    stems, tm = build_stems(score, a.soundfont, a.seed)
    print('humanize report (ms offset from the nominal grid, velocity spread):')
    for k, v in REPORT.items():
        print(f'  {k:12s} {v}')
    if a.stems_dir:
        os.makedirs(a.stems_dir, exist_ok=True)
        for k, v in stems.items():
            sf.write(os.path.join(a.stems_dir, k + '.wav'), v, SR)
    if a.stems_only:
        return
    import mixer
    mixer.mix_and_master(score, stems, a.out, master=not a.no_master)


if __name__ == '__main__':
    main()
