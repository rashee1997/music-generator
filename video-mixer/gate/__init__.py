# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""gate - the video gate, as its own pass.

`pass_rows()` is called from `pipeline.stage6_ci_quality_suite`, in the same
row list as every music row, before the verdict is written. There is no second
author of the certification any more: the old `video_gate.attach()` rewrote a
report that had already been certified.

Rows (limits live in the film presets and in `gate_profiles.ROWS`):

    video.duration_lock      program length against the picture          protected
    video.cut_sync           a cut hit against its cut
    video.motion_sync        a movement hit against its movement beat
    video.hit_class          a delayed accent must land after its moment
    video.grid_phase         the cuts' residual against the fitted grid
    video.hit_density        accents per minute, and no Mickey Mousing
    video.cue_silence        music where the spotting asked for silence
    video.dialogue_snr       music level under speech
    video.dialogue_band      music energy in the consonant band under speech
    video.shot_scale         density against the camera distance
    video.master_compliance  delivered loudness in the declared gating mode  protected
    video.gating_mode        the declared gating mode was actually measured  protected
"""
from .rows import (cut_sync_row, cue_silence_row, dialogue_band_row, dialogue_row,  # noqa: F401
                   duration_row, gating_mode_row, grid_phase_row, hit_class_row,
                   hit_density_row, master_row, motion_sync_row, shot_scale_row)
from .pass_ import pass_rows, film_presets, probe_rows  # noqa: F401

__all__ = ['pass_rows', 'film_presets', 'probe_rows', 'duration_row', 'cut_sync_row',
           'motion_sync_row', 'hit_class_row', 'grid_phase_row', 'hit_density_row',
           'cue_silence_row', 'dialogue_row', 'dialogue_band_row', 'shot_scale_row',
           'master_row', 'gating_mode_row']
