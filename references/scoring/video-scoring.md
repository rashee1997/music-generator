---
title: Video scoring
summary: Scoring against a picture: cuts, hits, dialogue, the video block in the sheet and its four gate rows.
tags: [video, picture, sync, cut, dialogue, fps, hits, spotting]
load_when:
  - the brief has a video file
  - a video gate row fails
---

# Scoring to picture

Music written against a film: the cuts set the tempo and the hits, the picture's own audio stays intelligible,
and the finished file carries the original video stream untouched.

```bash
python3 scripts/video_score.py --video clips/source.mp4 --project D:/films/glaciers --brief "calm documentary"
python3 scripts/video_score.py --selftest          # 17 checks, no project, temp files only
```

## What runs, in order

| Stage | File | Does |
|---|---|---|
| probe | `video-mixer/video_probe.py` | ffprobe stream facts, `scdet` cuts, per-frame luma / motion / centre / warmth at `analysis_fps` |
| direction | `video-mixer/video_direction.py` | cuts → tempo and hits, energy → intensity, luma → mode, centre → azimuth, warmth → timbre |
| score | `compose.py` (unchanged) | the music, rendered by `pipeline.py` with every normal music rule |
| program | `video-mixer/video_program_mix.py` | voice chain, music bed under speech, duck, swell into hits, SFX, master to the delivery profile |
| mux | `video-mixer/video_mux.py` | `-c:v copy` + audio, then proves the video stream is identical |
| gate | `video-mixer/video_gate.py` | four delivery rows appended to `reports/ci_report.json` |

`scripts/video_score.py` is the only video file in `scripts/`. `pipeline.py` is not modified: the music is a normal
score, so every existing gate row still applies to it.

## The preset

`references/data/presets/video/default.json` holds every number the path uses. A project preset of the same name in
`<project>/presets/video/` deep-merges over it, so an override can be five lines:

```json
{"name": "default", "character": "glacier documentary: slow, wide, almost no hits",
 "hits": {"max_hits_per_minute": 6},
 "mix": {"bed_db": -14.0},
 "master": {"profile": "broadcast"}}
```

| Block | Holds |
|---|---|
| `probe` | analysis fps and size, `scdet` threshold, motion-hit percentile, keyframe probe |
| `direction_map` | energy bins, default key, tempo range and frame lock, luma→mode, centre→azimuth, warmth→timbre |
| `staging` | the cue's own space preset (`space`), then elevation and distance per role |
| `mix_preset` | the cue's own mix preset: lead band, carve, level per role |
| `hits` | cut and motion sounds, per-minute budget, minimum gap in beats, hit length, velocities |
| `mix` | voice chain, bed and duck levels, speech band, swell, fades, SFX headroom |
| `master` | profile name, sample rate, bit depth |
| `master_profiles` | `streaming` (−14 LUFS, full program), `broadcast` (−24, dialogue gated), `cinema` (−27, dialogue gated) |
| `mux` | container, codec per extension, bitrate, faststart, shortest |
| `gate` | duration tolerance, cut-sync window, dialogue SNR floor, loudness tolerance |

Scaffold a project copy to edit:

```bash
python3 scripts/presets.py scaffold video default --project <dir>
```

The space and the mix preset named by the video preset are written into the project on the first run if they are
not there, because the project gate refuses a shipped fallback and a cue's room and balance belong to the project.

## The workflow, in order

The video path is not a shortcut around the normal one. Scaffold the project, run `research_kb.py` and add web
sources (Steps R1–R2 in `AGENTS.md`), then:

```bash
python3 scripts/video_score.py --video clips/source.mp4 --project <dir> --brief "calm documentary awe"
```

The project gate still blocks the render if research, direction or presets are missing — that is the same gate as
any other piece.

## The direction sheet the picture produces

The video path writes `direction/direction_sheet.json` in the same shape as `templates/direction_sheet.json`, so a
cue to picture and a cue to a brief are read the same way (`listen.py`, the project gate, a human director). What is
filled from the picture is listed in `music-direction.md` section 2.6; what it adds here is the block itself:

```json
"video": {
  "enabled": true, "preset": "default", "source": "clips/source.mp4",
  "in_s": 0.0, "out_s": 12.0, "duration_s": 12.0, "fps": 25.0,
  "cuts": [2.0, 5.0], "cuts_count": 2, "cut_source": "scdet", "motion_hits": 1,
  "cut_sync": {"early_ms": 45, "late_ms": 125, "aim_ms": 40},
  "dialogue": {"present": true, "duck_db": -9.0, "snr_min_db": 15.0},
  "master_profile": "streaming",
  "deliverable": {"container": "mp4", "audio_codec": "aac", "bitrate": "320k", "video_copy": true}
}
```

`cuts` are candidates from `scdet` (or the frame-difference fallback named in `cut_source`), not an edit list. The
`hits` list beside `hits_at` carries the same moments with `kind` and `sync`: a cut is a **hard** sync point and is
judged in `cut_sync`; a movement inside a shot is **soft** and is not judged against any cut. `sections` is the
picture's measured energy, labelled from `direction_map.energy_sections` - what the music does inside a section is
still a hand decision, so the generated sheet leaves `music` out rather than inventing it.

A sheet with `enabled: true` must name `source`, `fps`, `master_profile`, a cut list and a sync window; the project
gate rejects one that claims a picture it cannot describe.

## Tempo and hits

The median interval between cuts is read as 1, 2, 4 or 8 beats, whichever lands closest to the middle of
`min_bpm`..`max_bpm`. With `prefer_frame_lock` the tempo snaps so one beat is a whole number of frames at the
picture's own frame rate. Hits are written at **fractional beats** (`beat = t_s × bpm / 60`), because
`compose.add_hit_points` rounds to half beats and would throw a cut hit up to a beat away.

Every hit carries `kind`: `cut` or `motion`. Only cut hits are judged by `video.cut_sync`; a motion hit accents a
movement inside a shot and has no edit to be late for.

## The four gate rows

Registered in `scripts/gate_profiles.py`, chosen by the `video_cinematic` profile (`"piece_type"` in the score).

| Row | Measures | Protected |
|---|---|---|
| `video.duration_lock` | program length against the picture, ±`duration_tolerance_ms` | yes |
| `video.cut_sync` | every cut hit against its cut; early and late limits separate (ITU-R BT.1359) | no |
| `video.dialogue_snr` | music RMS under the voice while speech is active | no |
| `video.master_compliance` | delivered LUFS and true peak against the chosen master profile | yes |

The music tail runs past the end of the voice but never past the picture. A picture with no audio stream is not
an error: the cue plays alone and `video.dialogue_snr` passes with that reason written in the row.

## Honest limits

- Cuts come from `scdet`, which misses fades and dissolves; motion hits are a frame-difference fallback, not an
  edit list. Both are candidates, and `cut_source` in the report says which one was used.
- The loudness targets are published-standard summaries, not re-read tables. Verify against the current delivery
  spec of the platform you are cutting for.
- Nothing in the video path has been auditioned. `listen.py` judges the music bed, not the program mix under speech.
- The audio is always re-encoded at mux; only the video stream is copied, and that copy is proven by comparing
  codec, size, pixel format and frame count before and after.
