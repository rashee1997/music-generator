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
"""sfz_render.py - play a track through an SFZ library (sfizz_render) and return a stereo stem.

A track plays through SFZ when its instrument is "sfz:<library>/<patch>", or its instrument preset (or the track) carries an
"sfz" block:

    "sfz": {"library": "sso", "patch": "Strings - Notation/1st Violins Legato",
            "cc": "expression",            # which controller carries the dynamics curve: expression (CC11), volume (CC7), modwheel (CC1), none
            "controls": {"21": 50},        # constant controllers sent at t=0 (e.g. the library's own vibrato knob)
            "keyswitches": {"pizz": 36},   # articulation name (a note's "art") -> key-switch note, for KS patches
            "legato_overlap_s": 0.04,      # legato patches: each note ends this long after the next starts
            "tail_s": 3.0,                 # room for the release to ring out
            "trim_db": 0.0,                # level of the stem (the library's own level differs from the GM bank)
            "fallback": null}              # "gm": play the GM SoundFont instead when the library is missing (reported, never silent)

Humanization (timing, velocity) happens before this, in render_natural, exactly as for the GM path. Dynamics become controller curves.
Nothing here is random: the same score gives the same samples (sfizz_render is reproducible, measured).
"""
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import sfz_libs

CC_NUMBERS = {'expression': 11, 'volume': 7, 'modwheel': 1, 'none': None}
CC_STEP_S = 0.015


class SfzUnavailable(RuntimeError):
    """The library, patch or engine is missing. The message says the command that fixes it."""


def block_of(raw_inst, tr, inst_cfg):
    """The sfz block for a track, or None. `sfz:<library>/<patch>` is shorthand for {library, patch}."""
    if raw_inst.startswith('sfz:'):
        lib, _, patch = raw_inst[4:].partition('/')
        return dict(tr.get('sfz') or {}, library=lib, patch=patch)
    blk = tr.get('sfz') or ((inst_cfg or {}).get('sfz'))
    return dict(blk) if blk else None


def resolve(blk, project=None):
    """(engine path, sfz path) or SfzUnavailable."""
    try:
        sfz = sfz_libs.find_patch(blk['library'], blk['patch'], project)
    except (LookupError, SystemExit) as ex:
        raise SfzUnavailable(str(ex))
    exe = sfz_libs.find_engine(project)
    if not exe:
        raise SfzUnavailable('the sfizz engine is not installed. Run: sfz_libs.py engine --project <project>')
    return exe, sfz


LEAD_S = 0.05          # controllers go out first: a note that starts on the same tick as its controller can sound before it applies
TRACK_HEADROOM_S = 120.0   # a fixed allowance on top of the length-proportional budget below (library load, disk cache cold)
RENDER_SLOWDOWN = 6.0      # q=10 measures ~0.3x realtime; 6x is the point where a stuck engine is reported, not waited on


def midi_for(ev, offs, blk, dyn_level, patch_name, lead=0.0):
    """pretty_midi object for the humanized events. ev: dicts with t (s), p, v (1-127), art. offs: note-off times (s).
    `lead` shifts every note and curve later by that many seconds (the caller trims it from the audio)."""
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    inst = pretty_midi.Instrument(0)
    ev = [dict(e, t=e['t'] + lead) for e in ev]
    offs = [float(o) + lead for o in offs]
    ccn = CC_NUMBERS.get(str(blk.get('cc', 'expression')), 11)
    for num, val in (blk.get('controls') or {}).items():
        inst.control_changes.append(pretty_midi.ControlChange(int(num), int(val), 0.0))
    ks = blk.get('keyswitches') or {}
    overlap = float(blk.get('legato_overlap_s', 0.04))
    pname = patch_name.lower()
    patch_legato = 'legato' in pname and overlap > 0
    per_note = any('art' in e for e in ev)
    # Slurred legato (AGENTS.md section 3b): consecutive notes with art "legato" are one bow stroke. Only on bowed/blown sustaining patches.
    slur_ok = per_note and not any(w in pname for w in ('staccato', 'marcato', 'pizz', 'tremolo', 'spiccato', 'col legno', 'harmonics'))
    slur_ov = float(blk.get('slur_overlap_s', 0.025))                    # 20-30 ms into the next note's attack
    glide_c = float(blk.get('slur_glide_cents', -20.0))                  # tiny pitch glide into a slurred note
    glide_s = float(blk.get('slur_glide_s', 0.04))
    soft_v = float(blk.get('slur_vel_scale', 0.88))                      # the rosin bite of a slurred note is softer
    starts = sorted(set(round(e['t'], 4) for e in ev))
    # Onsets per pitch, so no note-off can reach a later note of the same pitch. sfizz hands an off that lands at or
    # after the next same-pitch note-on to the note that just started, and the retrigger comes back silent: measured
    # -84 dBFS on a p69 -> p69 repeat 100 ms inside the first note, against -51 dBFS with a clear gap and -54 dBFS for
    # p69 -> p70 at the same spacing. Velocity makes no difference, the pitch repeat alone decides.
    onsets_by_pitch = {}
    for _e in ev:
        onsets_by_pitch.setdefault(int(_e['p']), []).append(float(_e['t']))
    last_art = None
    slurred_in = [False] * len(ev)                                       # note j continues a slur begun earlier
    slur_next = {}                                                       # note i -> the note it slurs into
    if slur_ok:
        order = sorted(range(len(ev)), key=lambda i: ev[i]['t'])
        for a_i, b_i in zip(order, order[1:]):
            if ev[a_i].get('art') == 'legato' and ev[b_i].get('art') == 'legato' and ev[b_i]['t'] > ev[a_i]['t'] + 0.01                     and ev[b_i]['t'] - float(offs[a_i]) < 0.15:
                slurred_in[b_i] = True
                slur_next[a_i] = b_i
    pm._slur_onsets = []
    for j, e in enumerate(ev):
        off = float(offs[j])
        if slur_ok:
            if j in slur_next:
                off = ev[slur_next[j]]['t'] + slur_ov
        elif patch_legato:                                 # old behaviour: the patch name decides (scores with no per-note "art")
            later = [s for s in starts if s > e['t'] + 0.01]
            if later and later[0] - off < 0.15:
                off = later[0] + overlap
        later_same = [s for s in onsets_by_pitch.get(int(e['p']), ()) if s > e['t'] + 0.01]
        if later_same and off > later_same[0] - 0.01:
            off = later_same[0] - 0.01
        art = e.get('art')
        if art in ks and art != last_art:
            inst.notes.append(pretty_midi.Note(velocity=100, pitch=int(ks[art]), start=max(0.0, e['t'] - 0.05), end=e['t'] - 0.01 if e['t'] > 0.06 else 0.01))
            last_art = art
        vel = float(e['v']) * (soft_v if slurred_in[j] else 1.0)
        if slurred_in[j]:
            pm._slur_onsets.append(float(e['t']))
            if glide_c and glide_s > 0:                    # -20 cents falling to 0 over 40 ms; a bend of +-200 cents is 8192 units
                for k in range(5):
                    inst.pitch_bends.append(pretty_midi.PitchBend(int(round(glide_c / 200.0 * 8192.0 * (1 - k / 4.0))), float(e['t']) + k * glide_s / 4.0))
        inst.notes.append(pretty_midi.Note(velocity=int(np.clip(round(vel), 1, 127)), pitch=int(e['p']), start=float(e['t']), end=max(off, e['t'] + 0.02)))
    t_end = max((n.end for n in inst.notes), default=0.0)
    if ccn is not None:
        last = None
        for t in np.arange(0.0, t_end + 0.01, CC_STEP_S):
            v = int(np.clip(round(float(dyn_level(max(0.0, t - lead))) * 127.0), 1, 127))
            if v != last:
                inst.control_changes.append(pretty_midi.ControlChange(ccn, v, float(t)))
                last = v
    inst.control_changes.append(pretty_midi.ControlChange(64, 0, t_end + float(blk.get('tail_s', 3.0))))   # sustain-off marker: keeps the render open for the release
    pm.instruments.append(inst)
    return pm


def _is_mono(ev, tol=0.03):
    """True when no two notes start together (a single line), so a gain ramp at a note start cannot touch another voice."""
    ts = sorted(round(e['t'], 3) for e in ev)
    return all(b - a > tol for a, b in zip(ts, ts[1:]))


def render(ev, offs, tm, blk, dyn_level, sr, project=None, quality=10, polyphony=256):
    """Stereo float32 stem for one track. Raises SfzUnavailable when the library or engine is missing."""
    import soundfile as sf
    exe, sfz = resolve(blk, project)
    pm = midi_for(ev, offs, blk, dyn_level, sfz.name, lead=LEAD_S)
    with tempfile.TemporaryDirectory() as td:
        mid, wav = os.path.join(td, 'in.mid'), os.path.join(td, 'out.wav')
        pm.write(mid)
        # --use-eot is required, not tuning: without it sfizz_render keeps rendering past the end of the MIDI (measured:
        # 66 s of celli notes produced a 1353 s WAV and still had not stopped after 400 s), so the render never returns
        # and the pipeline stalls forever. With it, rendering ends at the MIDI's End-of-Track, which midi_for() places at
        # t_end + tail_s, so the release still rings out. The timeout is a backstop; q=10 measures ~0.3x realtime.
        timeout_s = TRACK_HEADROOM_S + pm.get_end_time() * RENDER_SLOWDOWN
        try:
            r = subprocess.run([str(exe), '--sfz', str(sfz), '--midi', mid, '--wav', wav, '-s', str(sr), '-q', str(quality),
                                '-p', str(polyphony), '--use-eot'],
                               capture_output=True, text=True, cwd=str(sfz.parent), timeout=timeout_s)
        except subprocess.TimeoutExpired:
            raise SfzUnavailable(f'sfizz_render did not finish {sfz.name} within {timeout_s:.0f}s for '
                                 f'{pm.get_end_time():.1f}s of MIDI; the engine is stuck, not slow')
        if r.returncode or not os.path.exists(wav):
            raise SfzUnavailable(f'sfizz_render failed on {sfz.name}: {(r.stdout + r.stderr).strip()[-300:]}')
        x, file_sr = sf.read(wav, dtype='float32', always_2d=True)
    if file_sr != sr:
        raise SfzUnavailable(f'sfizz_render wrote {file_sr} Hz, expected {sr}')
    x = x[:, :2] if x.shape[1] >= 2 else np.repeat(x, 2, axis=1)
    x = x[int(round(LEAD_S * sr)):]                        # the lead-in
    onsets = getattr(pm, '_slur_onsets', [])
    if onsets and not blk.get('slur_fade_off') and _is_mono(ev):
        fade_n = max(2, int(round(float(blk.get('slur_fade_s', 0.025)) * sr)))
        floor = float(blk.get('slur_fade_floor', 0.85))      # a partial ramp (not from silence), so a line never flutters at note rate
        t = np.linspace(0.0, 1.0, fade_n, dtype=np.float32)
        ramp = floor + (1.0 - floor) * 0.5 * (1.0 - np.cos(np.pi * t))
        for t0 in onsets:
            i0 = int(round((t0 - LEAD_S) * sr))
            if 0 <= i0 < len(x) - fade_n:
                x[i0:i0 + fade_n] *= ramp[:, None]
    # Opt-in: `dc_hp_hz` in a track's sfz block removes a patch's own DC offset and very slow drift,
    # which the stem trim would otherwise multiply (measured on one project: mean -0.0014 FS on a
    # trumpet stem at +33 dB trim, which the stem gate rejects above 0.001 FS). Off unless asked, so
    # nothing changes for a project that has not measured the problem.
    hp_hz = float(blk.get('dc_hp_hz', 0.0) or 0.0)
    if hp_hz > 0:
        try:
            from scipy.signal import butter, sosfilt
            x = sosfilt(butter(2, hp_hz, btype='highpass', fs=sr, output='sos'), x, axis=0).astype(np.float32)
        except Exception:
            x = (x - x.mean(axis=0, keepdims=True)).astype(np.float32)
    # Opt-in: `attack_fade_s` ramps each note onset, for a library whose samples begin on a hard
    # step (one project measured a clustered impulse at every onset with no single-sample jump).
    # Default 0 keeps every existing render bit-identical.
    n_fade = int(round(float(blk.get('attack_fade_s', 0.0) or 0.0) * sr))
    if n_fade >= 2:
        ramp = (0.5 - 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, n_fade))).astype(np.float32)[:, None]
        peak_x = float(np.max(np.abs(x))) if x.size else 0.0
        for e in ev:
            i0 = int(round(float(e['t']) * sr))
            if not (0 < i0 < len(x) - n_fade):
                continue
            # only where the note really starts from silence: at a legato join the previous note is
            # still ringing, and ramping it down from that level is itself a click.
            if float(np.max(np.abs(x[max(0, i0 - 1):i0]))) > 0.02 * peak_x:
                continue
            x[i0:i0 + n_fade] *= ramp
    entry = sfz_libs.registry().get(blk['library'], {})
    trim = float(blk.get('trim_db', entry.get('trim_db', 0.0)))
    return (x * 10 ** (trim / 20.0)).astype(np.float32)
