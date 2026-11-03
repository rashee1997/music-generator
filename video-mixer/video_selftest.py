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
"""video_selftest.py - prove the video path works, and prove it can fail.

    python3 scripts/video_score.py --selftest

Builds a synthetic picture with two known cuts and an accelerating box, plus a speech-like audio track, then:

  positive   the probe finds both cuts; the tempo lands inside the preset range; hits land on the cuts;
             the program ducks enough; the mux keeps the video stream identical; all four rows PASS
  negative   each control MUST fail: no ducking, a short program, a hit 250 ms off its cut,
             a master 5 LU down. A selftest that cannot fail proves nothing.

No project, no network, no music render. Temp files only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, '..'))
for p in (HERE, os.path.join(SKILL, 'scripts')):
    if p not in sys.path:
        sys.path.insert(0, p)

import presets              # noqa: E402
import video_probe          # noqa: E402
import video_direction      # noqa: E402
import video_program_mix    # noqa: E402
import video_mux            # noqa: E402
import video_gate           # noqa: E402
import mixer as mx          # noqa: E402

CUT_A, CUT_B, DURATION, FPS = 2.0, 4.0, 6.0, 25.0


def _ffmpeg(args):
    p = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-nostdin'] + args,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace').strip()[-700:])
    return p


def make_fixture(work):
    """A 6 s picture with white flashes at the two cut points and a box crossing the frame."""
    video = os.path.join(work, 'fixture.mp4')
    flash = f"drawbox=x=0:y=0:w=iw:h=ih:color=white@1:t=fill:enable='between(t,{CUT_A - 0.04},{CUT_A})+between(t,{CUT_B - 0.04},{CUT_B})'"
    _ffmpeg(['-f', 'lavfi', '-i', f'testsrc2=size=640x360:rate={FPS:.0f}:duration={DURATION:.0f}',
             '-f', 'lavfi', '-i', f'sine=frequency=200:duration={DURATION:.0f}',
             '-vf', flash, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', video])
    return video


def make_voice(path, sr=44100):
    """Speech-like bursts with gaps, so the duck has something to react to and something to release on."""
    n = int(DURATION * sr)
    y = np.zeros(n, np.float32)
    for a, b in ((0.3, 1.4), (1.8, 3.1), (3.6, 5.2)):
        i, j = int(a * sr), int(b * sr)
        t = np.arange(j - i) / sr
        env = np.minimum(1.0, np.minimum(t * 20.0, ((j - i) / sr - t) * 20.0))
        f0 = 180.0 + 12.0 * np.sin(2 * np.pi * 3.0 * t)
        y[i:j] = (0.28 * (np.sin(2 * np.pi * f0 * t) + 0.4 * np.sin(2 * np.pi * 2 * f0 * t)
                          + 0.2 * np.sin(2 * np.pi * 3 * f0 * t)) * env).astype(np.float32)
    sf.write(path, np.repeat(y[:, None], 2, axis=1), sr, subtype='PCM_24')
    return path


def make_music(path, sr=44100):
    """A bed with a low sine and a mid sine: the mid one must duck, the low one must not."""
    t = np.arange(int(DURATION * sr)) / sr
    y = (0.18 * np.sin(2 * np.pi * 330 * t) + 0.14 * np.sin(2 * np.pi * 70 * t)).astype(np.float32)
    sf.write(path, np.repeat(y[:, None], 2, axis=1), sr, subtype='PCM_24')
    return path


def check(results, name, ok, detail):
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:28s} {detail}")
    return ok


def run():
    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        print('  ffmpeg/ffprobe not on PATH: the video selftest cannot run')
        return False
    cfg = presets.get('video', 'default')
    cfg['name'] = 'default'
    work = tempfile.mkdtemp(prefix='video_selftest_')
    results = []
    try:
        video = make_fixture(work)
        voice_path, music_path = make_voice(os.path.join(work, 'voice.wav')), make_music(os.path.join(work, 'music.wav'))

        # --- probe -------------------------------------------------------------
        rep = video_probe.probe(video, cfg, verbose=False)
        cuts = [c['t'] for c in rep['cuts']]
        frame = 1.0 / FPS
        found_a = any(abs(c - CUT_A) <= frame + 0.02 for c in cuts)
        found_b = any(abs(c - CUT_B) <= frame + 0.02 for c in cuts)
        check(results, 'probe finds both cuts', found_a and found_b, f'cuts at {[round(c, 3) for c in cuts]}')
        check(results, 'probe reads the stream', abs(rep['source']['duration_s'] - DURATION) < 0.1 and rep['source']['fps'] > 0,
              f"{rep['source']['duration_s']:.2f}s @ {rep['source']['fps']:.3f} fps, audio={rep['source']['has_audio']}")

        # --- direction ---------------------------------------------------------
        sheet = video_direction.direction_sheet(rep, cfg, 'calm documentary')
        tc = cfg['direction_map']['tempo_from_cuts']
        bpm_ok = tc['min_bpm'] <= sheet['tempo_bpm'] <= tc['max_bpm']
        check(results, 'tempo inside the preset range', bpm_ok, f"{sheet['tempo_bpm']:.1f} bpm ({sheet['tempo_method']})")
        locked = not tc.get('prefer_frame_lock') or abs(sheet['tempo_bpm'] - FPS * 60.0 / round(FPS * 60.0 / sheet['tempo_bpm'])) < 0.51
        check(results, 'tempo frame-locked', locked, f'{FPS * 60.0 / sheet["tempo_bpm"]:.2f} frames per beat')
        hits = sheet['hits']
        cut_hits = [h for h in hits if h['kind'] == 'cut']
        near = [h for h in cut_hits if any(abs(h['t'] - c) < 0.05 for c in cuts)]
        check(results, 'cut hits land on the cuts', len(near) == len(cut_hits) and len(cut_hits) >= 2,
              f'{len(near)} of {len(cut_hits)} cut hits within 50 ms of a cut, {len(hits) - len(cut_hits)} motion hits')
        score = video_direction.score_from_sheet(sheet, cfg, rep)
        hit_tracks = [t for t in score['tracks'] if t['instrument'].startswith('sfx:')]
        frac = [n['t'] for t in hit_tracks for n in t['notes'] if abs(n['t'] - round(n['t'])) > 1e-6]
        check(results, 'hits placed at fractional beats', bool(hit_tracks) and bool(frac),
              f'{len(hit_tracks)} hit tracks, {len(frac)} off-grid note starts (ms-exact, not beat-rounded)')

        # --- program mix -------------------------------------------------------
        prof = video_program_mix.master_profile(cfg)
        voice, music = video_program_mix.load(voice_path), video_program_mix.load(music_path)
        mix, _, ducked, mask, mix_rep = video_program_mix.build(voice, music, [], cfg['mix'],
                                                                hit_times=sheet['hits_at'], limit_s=DURATION)
        snr = mix_rep.get('music_under_voice_db', 0.0)
        check(results, 'music ducks under speech', snr >= cfg['gate']['dialogue_snr_min_db'],
              f'{snr:.1f} dB under the voice (need {cfg["gate"]["dialogue_snr_min_db"]:.1f})')
        low_band = mx.lufs(np.repeat(ducked[mask][:, :1], 2, axis=1) if mask.any() else ducked, 44100)
        check(results, 'program is finite', bool(np.isfinite(mix).all()), f'{len(mix)} samples, low band {low_band:.1f} LUFS')

        program, sr = video_program_mix.master(mix, prof)
        program_wav = os.path.join(work, 'program.wav')
        sf.write(program_wav, program, sr, subtype='PCM_24')

        # --- mux ---------------------------------------------------------------
        out = os.path.join(work, 'final.mp4')
        mux_rep = video_mux.mux(video, program_wav, out, cfg['mux'], verbose=False)
        check(results, 'video stream copied intact', mux_rep['video_identical'],
              f"{mux_rep['source_video']['codec']} {mux_rep['source_video']['width']}x{mux_rep['source_video']['height']}")

        # --- gate, positive ----------------------------------------------------
        rows_out, offsets = video_gate.rows(rep, program_wav, mix_rep, prof, cfg['gate'], hits=hits)
        for lvl, name, detail in rows_out:
            check(results, f'row {name} passes', lvl == 'PASS', detail)

        # --- gate, negative controls (each must fail) --------------------------
        short = os.path.join(work, 'short.wav')
        sf.write(short, program[:int(len(program) * 0.9)], sr, subtype='PCM_24')
        short_rows = []
        video_gate.duration_row(rep, len(program[:int(len(program) * 0.9)]) / sr, cfg['gate'], short_rows)
        check(results, 'control: short program fails', short_rows[0][0] == 'FAIL', short_rows[0][2])

        shifted = [dict(t_s=h['t'] + 0.25, kind=h['kind']) for h in hits]
        shifted_rows = []
        video_gate.cut_sync_rows(rep, shifted, cfg['gate'], shifted_rows)
        check(results, 'control: late hit fails', shifted_rows[0][0] == 'FAIL', shifted_rows[0][2])

        dry = json.loads(json.dumps(cfg['mix']))
        dry['duck_db'], dry['duck_depth_db'], dry['bed_db'] = 0.0, 0.0, -4.0
        _, _, _, _, dry_rep = video_program_mix.build(voice, music, [], dry, hit_times=[])
        dry_rows = []
        video_gate.dialogue_row(dry_rep, rep, cfg['gate'], dry_rows)
        check(results, 'control: no ducking fails', dry_rows[0][0] == 'FAIL', dry_rows[0][2])

        loud = os.path.join(work, 'loud.wav')
        sf.write(loud, mx.master_chain(program, dict(lufs=prof['lufs'] + 5.0, true_peak=-0.5), sr), sr, subtype='PCM_24')
        loud_rows = []
        video_gate.master_row(loud, prof, cfg['gate'], loud_rows)
        check(results, 'control: loud master fails', loud_rows[0][0] == 'FAIL', loud_rows[0][2])

        ok = all(r[1] for r in results)
        print(f"\n  selftest: {sum(1 for r in results if r[1])}/{len(results)} checks passed -> {'OK' if ok else 'FAILED'}")
        return ok
    except Exception as e:
        print(f'  selftest raised: {type(e).__name__}: {e}')
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
