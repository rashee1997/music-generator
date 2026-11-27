# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""lint_coverage.py - for every gate row, what catches it before a render, or why only audio can.

`tests/test_lint_coverage.py` fails when a row in `gate_profiles.ROWS` is missing here, or when a rule named here does
not exist. A render that fails a row with no pre-render rule is then a decision: write the rule, or write the reason.

Each value is (kind, detail):
    'preflight'  detail = the pre-render rows that catch it, in preflight_lint, preflight_levels or preset_probe
    'stage2'     detail = the stage-2 module that already checks it from the notes
    'score'      detail = a row judged from the score (and sheet) alone; `focus.declared` and `intent.*` also run in stage 2
    'audio'      detail = why it needs rendered audio
"""
A = 'audio'
COVERAGE = {
    'loudness': (A, 'integrated loudness of the finished mix'),
    'true_peak': (A, 'the limiter and the room decide the peak'),
    'clipping': (A, 'sums of stems and the limiter; a single sound is checked by probe.clip'),
    'silence': (A, 'a gap in the finished mix'),
    'clicks': (A, 'mix-level clicks; a one-shot cut short is caught by preflight.sfx_length and probe.start'),
    'stem.clicks': ('preflight', ['preflight.sfx_length', 'probe.start']),
    'stem.dropout': ('preflight', ['preflight.range', 'preflight.section_edge']),
    'stem.cut': ('preflight', ['preflight.sfx_length']),
    'stem.end': ('preflight', ['probe.tail']),
    'stem.edge': ('preflight', ['preflight.sfx_length', 'preflight.range']),
    'stem.tick': (A, 'periodicity of rendered onsets'),
    'stem.dead': ('preflight', ['preflight.stem_level', 'preflight.figure_level', 'preflight.section_edge']),
    'stem.clipping': ('preflight', ['probe.clip']),
    'stem.dc': ('preflight', ['probe.dc']),
    'stem.flatness': (A, 'noise inside a tonal stem'),
    'stem.vocal': (A, 'the vocal engine output'),
    'stem.present': ('score', 'every track with notes must have a stem; the renderer raises when one is missing'),
    'stem.duplicate': (A, 'two rendered stems compared'),
    'dropout': (A, 'a hole in the finished mix'),
    'cut.hard': (A, 'a step in the finished mix'),
    'end.abrupt': (A, 'the end of the finished mix'),
    'master.dc': (A, 'the mix and the master high-pass'),
    'tempo.audio': ('preflight', ['preflight.tempo']),
    'section.energy': ('preflight', ['preflight.arc', 'preflight.figure_level']),
    'channels': ('stage2', 'pattern_audit.note_collision'),
    'pattern.drums_few': ('stage2', 'pattern_audit.audit'),
    'pattern.loop_short': ('stage2', 'pattern_audit.audit'),
    'pattern.melody_notes': ('stage2', 'pattern_audit.audit'),
    'pattern.bass_pitches': ('stage2', 'pattern_audit.audit'),
    'pattern.velocity_flat': ('stage2', 'pattern_audit.audit'),
    'pattern.flat_dynamics': ('stage2', 'pattern_audit.audit'),
    'pattern.four_on_floor': ('stage2', 'pattern_audit.audit'),
    'pattern.flags_max': ('stage2', 'pattern_audit.audit'),
    'pattern.track_flags_max': ('stage2', 'pattern_audit.audit_detail'),
    'shape.contrast': ('stage2', 'pattern_audit.shape_contrast'),
    'roughness': ('preflight', ['preflight.roughness', 'preflight.unison']),
    'ambient_bed': (A, 'the level of a rendered bed against the mix; the tempo-map bug is covered by tests/test_gate_clock.py'),
    'modulation_flutter': (A, 'amplitude modulation of rendered stems'),
    'note_collision': ('stage2', 'pattern_audit.note_collision'),
    'chord_voicing_and_strum': ('stage2', 'pattern_audit.chord_voicing_and_strum'),
    'choked_resonance': ('stage2', 'pattern_audit.choked_resonance'),
    'machine_gun_percussion': ('stage2', 'pattern_audit.machine_gun_percussion'),
    'percussion_flam': ('stage2', 'pattern_audit.percussion_flam'),
    'low_interval_mud': ('stage2', 'pattern_audit.low_interval_mud'),
    'orch.range': ('stage2', 'orch_rows.range_rows'),
    'orch.voice_leading': ('stage2', 'orch_rows.voice_leading_rows'),
    'orch.playable': ('stage2', 'orch_rows.playable_rows'),
    'orch.legato': ('stage2', 'orch_rows.legato_rows'),
    'balance.vs_lead': (A, 'stem levels after gain staging'),
    'focus.declared': ('score', 'quality_gate.focus_rows, run in stage 2'),
    'intent.vocabulary': ('score', 'quality_gate.intent_rows, run in stage 2'),
    'intent.avoid': ('score', 'quality_gate.intent_rows, run in stage 2'),
    'balance.layers': (A, 'stem levels after gain staging'),
    'masking.vs_melody': (A, 'ERB-band masking of rendered stems'),
    'spatial.z_separation': ('preflight', ['preflight.placement']),
    'spectral.equal_loudness': (A, 'the spectrum of the finished mix'),
    'bow.breath_gap': ('stage2', 'pattern_audit.cognitive_feel_checks'),
    'chroma.concordance': (A, 'the pitch content of rendered beds'),
    'kick.grid': (A, 'rendered kick transients'),
    'imm.cues': (A, 'a binaural probe of the finished mix'),
    'imm.elevation': (A, 'a binaural probe of the finished mix'),
    'imm.frontback': (A, 'a binaural probe of the finished mix'),
    'imm.height_rules': ('score', 'heights and roles come from the score and the presets; checked by the immersive config'),
    'imm.band': (A, 'energy above 4 kHz in a rendered stem'),
    'imm.externalization': (A, 'the room reflections of the finished mix'),
    'imm.envelopment': (A, 'late interaural correlation of the finished mix'),
    'imm.width': (A, 'the finished mix'),
    'imm.foldown': (A, 'the finished mix'),
    'imm.coloration': (A, 'the finished mix'),
    'imm.route_parity': (A, 'two renders compared'),
    'natural.aliasing': (A, 'the spectrum of a rendered transposed sample'),
    'meta.tags': (A, 'written beside the certified master'),
    'delivery.sample_rate': (A, 'the delivered file'),
    'delivery.bit_depth': (A, 'the delivered file'),
    'delivery.channels': (A, 'the delivered file'),
    'delivery.duration': (A, 'the delivered file'),
    'tempo.bpm': ('score', 'quality_gate.direction_rows compares the score with the sheet'),
    'key.mode': ('score', 'quality_gate.direction_rows compares the score with the sheet'),
    'meta.version': (A, 'written when a render is certified'),
}
for _name in ('video.duration_lock', 'video.cut_sync', 'video.dialogue_snr', 'video.master_compliance', 'video.motion_sync', 'video.hit_class',
              'video.grid_phase', 'video.hit_density', 'video.cue_silence', 'video.dialogue_band', 'video.shot_scale', 'video.gating_mode'):
    COVERAGE[_name] = (A, 'measured on the program against the picture (video-mixer)')
for _name in ('vocal.integrity', 'vocal.clicks', 'vocal.breath', 'vocal.ensemble', 'vocal.intonation', 'vocal.dynamics', 'vocal.hum_tone', 'vocal.ring',
              'vocal.formant_tuning', 'vocal.consonant', 'vocal.coarticulation', 'vocal.perturbation', 'vocal.passaggio', 'vocal.vibrato',
              'vocal.identity', 'vocal.spatial'):
    COVERAGE[_name] = (A, 'measured on the rendered vocal stems')
for _name in ('feel.contour', 'feel.resolution', 'feel.groove', 'feel.effort', 'feel.spiral', 'feel.witek', 'feel.entropy', 'expr.ic_profile', 'expr.surprise_grounded', 'expr.tension_ic'):
    COVERAGE[_name] = ('stage2', 'pattern_audit.cognitive_feel_checks')
for _name in ('imm.iacc_early', 'imm.clarity', 'imm.low_fold', 'mix.band_fold', 'imm.kinematics', 'render.finite'):
    COVERAGE[_name] = (A, 'the room, the fold-down or the delivered channels of the render')
for _name in ('lfe.sum_coherence', 'lfe.polarity', 'lfe.fold_loss', 'lfe.modal_spread', 'front.fold_phantom'):
    COVERAGE[_name] = (A, 'the two low-frequency channels and the front stage of the delivered programme')
for _name in ('ear.fatigue', 'ear.masking', 'ear.mod_roughness', 'ear.pitch_salience', 'ear.iacc'):
    COVERAGE[_name] = (A, 'the neural activity pattern of the rendered master and stems')
for _name in ('chem.model', 'chem.reward_build', 'chem.reward_arrival', 'chem.stress_load', 'chem.affiliation',
              'chem.motor_drive', 'chem.recovery', 'chem.arc_variety', 'chem.mood_connection', 'chem.genre_connection'):
    COVERAGE[_name] = (A, 'the traced pools from the score, the rendered master and the virtual ear (scripts/chem_model)')
for _name in ('env.declaration', 'env.medium_consistency', 'env.niche_collision', 'env.score_pocket', 'env.foreground_salience', 'env.loop_stationarity',
              'env.density_budget', 'env.level_physical', 'env.diffuse_field', 'env.ecology_rules', 'env.cpu_budget'):
    COVERAGE[_name] = (A, 'the biome presets of the score rendered and planned against the score')
COVERAGE['emotion.arc_arousal'] = (A, 'the rendered sections against the direction sheet')
COVERAGE['emotion.arc_valence'] = (A, 'the rendered sections against the direction sheet')
COVERAGE['expr.agogic_coupling'] = (A, 'the humanized events of the rendered figure lines')
for _name in ('channel.bars', 'channel.virtual'):
    COVERAGE[_name] = (A, 'the delivered channels of the render, bar by bar or through a virtual speaker')
for _name in ('delivery.conform', 'delivery.loudness_ceiling', 'delivery.standard', 'iamf.container'):
    COVERAGE[_name] = (A, 'the delivered file measured against its format or standard')
for _name in ('imm.decode_uniformity', 'masking.excess', 'master.micro_dynamics', 'master.mono_bands'):
    COVERAGE[_name] = (A, 'the rendered master and its decodes')
COVERAGE['imm.kinematics'] = ('score', 'the trajectories are in the presets and the score; checked by the immersive config')

PREFLIGHT_ROWS = (
    'preflight.range', 'preflight.sfx_length', 'preflight.fx', 'preflight.section_edge', 'preflight.unison', 'preflight.figure_level', 'preflight.placement',
    'preflight.stem_level', 'preflight.arc', 'preflight.tempo', 'preflight.roughness', 'preflight.roughness_partials',
    'probe.silent', 'probe.clip', 'probe.start', 'probe.tail', 'probe.dc',
)


def missing(rows):
    """Rows with no entry."""
    return sorted(r for r in rows if r not in COVERAGE)


def tier_problems():
    """Rows with no tier, or a row listed in two: the tier map is data (scripts/gate_tiers.py reads
    references/data/presets/gate/tiers.json). Checked with the coverage, so a new row needs both an entry here and a
    tier there before it can ship."""
    import gate_tiers
    return gate_tiers.problems()


def unknown_rules():
    """Preflight rules named in the table that do not exist."""
    named = {r for kind, detail in COVERAGE.values() if kind == 'preflight' for r in detail}
    return sorted(named - set(PREFLIGHT_ROWS))
