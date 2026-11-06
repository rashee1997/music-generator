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


def make_bursts(work, sr=44100):
    """Two speech-like bursts in an otherwise quiet track, for the speech-activity check."""
    n = int(DURATION * sr)
    y = np.zeros((n, 1), np.float32)
    for a, b in ((0.4, 1.1), (3.2, 4.4)):
        i, j = int(a * sr), int(b * sr)
        t = np.arange(j - i) / sr
        env = np.minimum(1.0, np.minimum(t * 30.0, (t[-1] - t) * 30.0))
        f0 = 170.0 + 10.0 * np.sin(2 * np.pi * 4.0 * t)
        sig = sum(0.3 * np.sin(2 * np.pi * k * f0 * t) / k for k in (1, 2, 3, 4, 5))
        y[i:j, 0] = (sig * env).astype(np.float32)
    return y
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

        # --- context model ----------------------------------------------------
        import context as context_mod
        import presets as _p
        film_analysis = _p.get('film', 'analysis')
        film_mapping = _p.get('film', 'mapping')
        film_hits = _p.get('film', 'hits')
        ctx = context_mod.build(rep, film_analysis, film_mapping)
        check(results, 'context groups shots into scenes', len(ctx['scenes']) >= 1 and len(ctx['shots']) >= 2,
              f"{len(ctx['shots'])} shots, {len(ctx['scenes'])} scenes")
        phase = context_mod.cut_phase(cuts, sheet['tempo_bpm'], FPS)
        check(results, 'cut grid phase is fitted', phase['cuts'] >= 2 and phase['confidence'] > 0.5,
              f"offset {phase['offset_s']:.3f}s, worst {phase['worst_residual_ms']:.0f} ms, "
              f"confidence {phase['confidence']:.2f}")
        from analysis import shot_scale as ss, speech as sp_mod
        wide = np.tile((0.5 + 0.45 * np.sin(np.linspace(0.0, 40.0 * np.pi, 160)))[None, :], (90, 1))
        close = np.tile(np.full(160, 0.8)[None, :], (90, 1))
        close[35:55, 70:90] = np.tile((0.5 + 0.45 * np.sin(np.linspace(0.0, 20.0 * np.pi, 20)))[None, :],
                                      (20, 1))
        w_label, _ = ss.classify(wide.astype(np.float32), film_analysis)
        c_label, _ = ss.classify(close.astype(np.float32), film_analysis)
        check(results, 'shot scale reads wide vs close', w_label != c_label,
              f'wide frame -> {w_label}, close frame -> {c_label}')
        act = sp_mod.activity(np.repeat(make_bursts(work), 2, axis=1), 44100, film_analysis)
        check(results, 'speech activity finds the bursts', 2 <= len(act['segments']) <= 4 and act['share'] > 0.1,
              f"{len(act['segments'])} segments, {act['share'] * 100:.0f} % of the track")

        # --- the new rows, positive and negative -------------------------------
        from gate import rows as G
        beats = [{'t': 1.0}]
        sync_rows = []
        G.motion_sync_row(beats, [{'t_s': 1.05, 'kind': 'motion'}], cfg['gate'], sync_rows)
        check(results, 'row motion_sync passes on time', sync_rows[0][0] == 'PASS', sync_rows[0][2])
        sync_rows = []
        G.motion_sync_row(beats, [{'t_s': 1.6, 'kind': 'motion'}], cfg['gate'], sync_rows)
        check(results, 'control: late movement hit fails', sync_rows[0][0] == 'FAIL', sync_rows[0][2])

        cls_rows = []
        G.hit_class_row([{'t': 2.0, 'class': 'dead_on', 'offset_s': 0.0}], film_hits, cls_rows)
        check(results, 'row hit_class passes a dead-on accent', cls_rows[0][0] == 'PASS', cls_rows[0][2])
        cls_rows = []
        G.hit_class_row([{'t': 2.0, 'class': 'dead_on', 'offset_s': 0.5}], film_hits, cls_rows)
        check(results, 'control: a dead-on accent off the frame fails', cls_rows[0][0] == 'FAIL', cls_rows[0][2])

        dens_rows = []
        G.hit_density_row([{'t_s': 1.0}, {'t_s': 3.0}], [1.0, 3.0, 5.0], 60.0,
                          dict(cfg['gate'], density=film_hits['density']), dens_rows)
        check(results, 'row hit_density passes a sparse cue', dens_rows[0][0] == 'PASS', dens_rows[0][2])
        many = [{'t_s': float(i)} for i in range(0, 60)]
        dens_rows = []
        G.hit_density_row(many, [float(i) for i in range(0, 60)], 60.0,
                          dict(cfg['gate'], density=film_hits['density']), dens_rows)
        check(results, 'control: hitting every cut fails', dens_rows[0][0] == 'FAIL', dens_rows[0][2])

        gp_rows = []
        G.grid_phase_row(dict(worst_residual_ms=10.0, tolerance_frames=0.25), cfg['gate'], gp_rows)
        check(results, 'row grid_phase passes a tight grid', gp_rows[0][0] == 'PASS', gp_rows[0][2])
        gp_rows = []
        G.grid_phase_row(dict(worst_residual_ms=200.0, tolerance_frames=5.0), cfg['gate'], gp_rows)
        check(results, 'control: cuts off the grid fail', gp_rows[0][0] == 'FAIL', gp_rows[0][2])

        quiet = os.path.join(work, 'quiet.wav')
        sf.write(quiet, np.zeros((int(sr * 2), 2), np.float32), sr, subtype='PCM_24')
        cs_rows = []
        G.cue_silence_row(quiet, [(0.2, 1.0)], cfg['gate'], cs_rows)
        check(results, 'row cue_silence passes real silence', cs_rows[0][0] == 'PASS', cs_rows[0][2])
        cs_rows = []
        G.cue_silence_row(program_wav, [(0.2, 1.0)], dict(cfg['gate'], cue_silence={'max_dbfs': -70.0}), cs_rows)
        check(results, 'control: music in a silent window fails', cs_rows[0][0] == 'FAIL', cs_rows[0][2])

        band_ok = []
        G.dialogue_band_row({'music_under_voice_band_db': 18.0}, rep, cfg['gate'], band_ok)
        check(results, 'row dialogue_band passes a carved bed', band_ok[0][0] == 'PASS', band_ok[0][2])
        band_bad = []
        G.dialogue_band_row({'music_under_voice_band_db': 2.0}, rep, cfg['gate'], band_bad)
        check(results, 'control: a bed over the consonants fails', band_bad[0][0] == 'FAIL', band_bad[0][2])

        scale_ok = []
        G.shot_scale_row([{'name': 's1', 'shot_scale': 'close', 'density': 0.3}], [],
                         dict(film_mapping, tolerance=0.15), scale_ok)
        check(results, 'row shot_scale passes a close-up', scale_ok[0][0] == 'PASS', scale_ok[0][2])
        scale_bad = []
        G.shot_scale_row([{'name': 's1', 'shot_scale': 'close', 'density': 0.9}], [],
                         dict(film_mapping, tolerance=0.15), scale_bad)
        check(results, 'control: a full band in a close-up fails', scale_bad[0][0] == 'FAIL', scale_bad[0][2])

        gm_ok = []
        G.gating_mode_row({'loudness_mode': 'dialogue'}, 'dialogue', gm_ok)
        check(results, 'row gating_mode passes a real gate', gm_ok[0][0] == 'PASS', gm_ok[0][2])
        gm_bad = []
        G.gating_mode_row({'loudness_mode': 'dialogue'}, 'full_program', gm_bad)
        check(results, 'control: a claimed gate that was not applied fails', gm_bad[0][0] == 'FAIL', gm_bad[0][2])

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
