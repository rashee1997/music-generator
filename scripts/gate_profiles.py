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
"""gate_profiles.py - the quality gate adapts to the type of piece, and every adaptation is a preset (kind 'gate').

    python3 scripts/gate_profiles.py list                         # profiles and what each changes against 'melodic'
    python3 scripts/gate_profiles.py explain score.json [--project D]   # chosen profile, why, and every row's final mode
    python3 scripts/gate_profiles.py new horror --from tense --project D  # scaffold a project profile
    python3 scripts/gate_profiles.py check [--project D]          # validate every profile (project_gate calls the same)
    python3 scripts/gate_profiles.py rows                         # every gate row, its parameters and limits

A profile (references/data/presets/gate/<name>.json, or <project>/presets/gate/) says, per gate row, `apply`, `relax`
(new parameter values) or `skip`, and every relax/skip carries a reason. `extends` inherits another profile. `detect`
(keywords, pulse words, drone ratio) lets the gate infer a type when the score does not declare one. `flags` keep the
old feel-check switches (ambient / tense / dance). The score picks with "piece_type": "tense" or a list; a one-off row
change goes in score["gate"] = {row: {"mode": "relax", "reason": "...", param: value}}.

Hard limits (a profile cannot switch the gate off): PROTECTED rows stay `apply` with default numbers, every parameter has a
range, relax/skip need a reason. A relaxed row still prints (with its reason); a skipped row prints SKIP.
"""
import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import presets

MODES = ('apply', 'relax', 'skip')
FLAGS = ('ambient', 'tense', 'dance')
DEFAULT_PROFILE = 'melodic'
TRAITS = {'drone_ratio_min': (0.0, 1.0)}

# id -> meaning, params {name: (default, lo, hi)}, protected. A bool default means a bool parameter.
ROWS = {
    # protected: measured faults no type of music excuses
    'loudness':    dict(meaning='integrated loudness against the target', protected=True),
    'true_peak':   dict(meaning='true peak under the ceiling', protected=True),
    'clipping':    dict(meaning='clipped bends / samples', protected=True),
    'silence':     dict(meaning='silent gap in the middle', protected=True),
    'clicks':      dict(meaning='single-sample jumps', protected=True),
    # stem gate (scripts/stem_gate.py, before mixing)
    'stem.clicks': dict(meaning='click/impulse on one stem (high-pass MAD + LPC residual)', params={
        'mad_z': (8.0, 5.0, 15.0), 'floor_fs': (0.02, 0.005, 0.1),
        'cluster_gap_ms': (1.5, 0.5, 5.0), 'isolate_ms': (10.0, 5.0, 30.0)}, no_skip=True),
    'stem.dropout': dict(meaning='a short hole in one stem', params={
        'min_ms': (20.0, 5.0, 50.0), 'max_ms': (1000.0, 500.0, 2000.0), 'floor_below_db': (45.0, 30.0, 60.0)}),
    'stem.cut': dict(meaning='a level step with no release at a section boundary or the end', params={
        'drop_db': (12.0, 8.0, 20.0), 'location_ms': (75.0, 25.0, 200.0)}),
    'stem.end': dict(meaning='a stem truncated at full level', params={
        'min_decay_db': (12.0, 8.0, 20.0), 'floor_db': (-45.0, -60.0, -30.0)}),
    'stem.edge': dict(meaning='a stem starts or stops away from its own score notes', params={
        'max_silence_ms': (25.0, 5.0, 100.0)}),
    'stem.tick': dict(meaning='a periodic tick in a stem that should have no beat', params={
        'rho': (0.35, 0.2, 0.6), 'min_events': (6, 3, 12), 'cv_max': (0.05, 0.01, 0.2)}),
    'stem.dead': dict(meaning='a part missing/dropped against the score dynamics', params={
        'under_db': (12.0, 6.0, 24.0), 'floor_db': (-70.0, -80.0, -50.0)}),
    'stem.clipping': dict(meaning='clipped samples on one stem', protected=True),
    'stem.dc': dict(meaning='DC offset on one stem', params={'dc_max': (0.001, 0.0005, 0.01)}),
    'stem.flatness': dict(meaning='a noise burst in a tonal stem', params={
        'threshold': (0.10, 0.03, 0.4), 'min_ms': (50.0, 20.0, 200.0)}),
    'stem.vocal': dict(meaning='vocal stem integrity (finite, DC, clicks)'),
    'stem.present': dict(meaning='every score track with notes has a stem'),
    'stem.duplicate': dict(meaning='two stems are the same signal', params={'max_corr': (0.999, 0.99, 1.0)}),
    # master rows added by the mix gate
    'dropout': dict(meaning='a short hole in the master', params={
        'min_ms': (20.0, 5.0, 50.0), 'max_ms': (1000.0, 500.0, 2000.0), 'floor_below_db': (45.0, 30.0, 60.0)}),
    'cut.hard': dict(meaning='a hard cut at a boundary/end in the master', params={
        'drop_db': (12.0, 8.0, 20.0), 'location_ms': (75.0, 25.0, 200.0)}),
    'end.abrupt': dict(meaning='the master ends at full level with no release', params={
        'min_decay_db': (12.0, 8.0, 20.0), 'floor_db': (-45.0, -60.0, -30.0)}),
    'master.dc': dict(meaning='DC offset on the master', params={'dc_max': (0.001, 0.0005, 0.01)}),
    'tempo.audio': dict(meaning='measured tempo against the score/sheet', params={
        'tol_bpm': (2.0, 1.0, 5.0), 'tol_pct': (2.0, 1.0, 5.0), 'drift_bpm': (2.0, 1.0, 5.0)}),
    'section.energy': dict(meaning='section level against the promised energy arc', params={
        'fail_rho': (0.5, 0.3, 0.8), 'warn_rho': (0.7, 0.5, 0.9)}),
    'channels':    dict(meaning='note started on a channel still sounding', protected=True),
    # score patterns (pattern_audit.audit)
    'pattern.drums_few':     dict(meaning='drums play only a few different bars', params={'distinct_div': (8, 2, 32)}),
    'pattern.loop_short':    dict(meaning='chord/pad/arp/bass loops every few bars for the whole piece',
                                  params={'max_period_bars': (4, 1, 16), 'max_distinct': (4, 1, 16), 'min_bars': (16, 8, 64)}),
    'pattern.melody_notes':  dict(meaning='melody: few note lengths, on-grid starts, repeated pitches',
                                  params={'min_lengths': (3, 1, 6), 'on_beat_max': (0.9, 0.5, 1.0), 'repeat_max': (0.35, 0.2, 0.8)}),
    'pattern.bass_pitches':  dict(meaning='bass uses very few pitch classes', params={'max_classes': (3, 1, 6)}),
    'pattern.velocity_flat': dict(meaning='velocity barely moves', params={'sd_frac': (0.05, 0.01, 0.05)}),
    'pattern.flat_dynamics': dict(meaning='whole piece stays in a narrow dynamic range', params={'min_range_frac': (0.25, 0.05, 0.25)}),
    'pattern.four_on_floor': dict(meaning='a kick on every beat and nothing else'),
    'pattern.flags_max':     dict(meaning='how many pattern flags make a FAIL', params={'max': (6, 3, 12)}, no_skip=True),
    # audio / mix
    # `model` switches the estimator: 'legacy' is the original Plomp-Levelt/Sethares pair weight with per-frame
    # normalisation; 'level_aware' adds absolute partial level, simultaneous masking and the Vassilakis amplitude
    # terms (knowledgebase/sound-design/roughness.md). Default stays 'legacy' until the listening check in
    # docs/roughness_model.md is answered. The other params are read only by 'level_aware'.
    'roughness':             dict(meaning='cochlear sensory roughness', params={
        'scale': (1.0, 0.5, 2.0),
        'outro_resolve': (True,),
        'model': ('legacy', 'level_aware'),
        'median': (0.024, 0.02, 0.40),                    # calibrated on tests/fixtures/roughness, not on a cue
        'calib_spl_db': (70.0, 60.0, 80.0),              # Zwicker & Fastl measure roughness at 60-70 dB SPL
        'mask_band_bark': (1.0, 0.5, 3.0),               # Daniel & Weber use 1-Bark filters
        'mask_slope_up_db_bark': (10.5, 5.0, 20.0),      # measured upper masking slope, 64-70 dB near 450 Hz
        'mask_slope_down_db_bark': (27.0, 15.0, 40.0),   # Daniel & Weber lower slope, -27 dB/Bark
    }, no_skip=True),
    'ambient_bed':           dict(meaning='an ambient bed that drops out or pumps', params={'pump_db': (3.8, 3.0, 6.0)}, no_skip=True),
    'modulation_flutter':    dict(meaning='6-25 Hz amplitude flutter in a sustained part', params={'warn': (0.18, 0.10, 0.30)}, no_skip=True),
    # score checks (pattern_audit.acoustic_checks). No numbers to retune, but a type of music may legitimately have them:
    # an ambient piece has no chord voicing, an effects piece has no notes, a percussion-only loop has no "flam".
    'note_collision':        dict(meaning='a pitch attacked twice on one beat or re-attacked while ringing'),
    'chord_voicing_and_strum': dict(meaning='chord voicing and strum shape'),
    'choked_resonance':      dict(meaning='a note cut before its resonance can speak'),
    'machine_gun_percussion': dict(meaning='percussion repeated at one velocity and one interval'),
    'percussion_flam':       dict(meaning='two percussion hits too close to read as one or two'),
    'low_interval_mud':      dict(meaning='low intervals closer than a minor third'),
    'balance.vs_lead':       dict(meaning='accompaniment against the lead', params={'warn_over_db': (3.0, 1.0, 6.0), 'fail_over_db': (6.0, 3.0, 12.0)}),
    'balance.layers':        dict(meaning='each layer against the median layer (no lead needed)',
                                  params={'warn_db': (9.0, 4.0, 18.0), 'fail_db': (15.0, 8.0, 24.0)}),
    'masking.vs_melody':     dict(meaning='ERB-band masking of the melody by beds', params={'margin_db': (3.0, 1.0, 6.0)}),
    'spatial.z_separation':  dict(meaning='parts that fight for the same midrange share one place in the climax (azimuth + elevation)',
                                  params={'overlap_min': (0.5, 0.2, 0.9), 'min_sep_deg': (25.0, 5.0, 90.0), 'min_elev_deg': (15.0, 0.0, 45.0)}),
    'spectral.equal_loudness': dict(meaning='2.5-5 kHz sits far louder than the mids once ear sensitivity is weighted',
                                    params={'warn_db': (6.0, 3.0, 12.0), 'fail_db': (10.0, 6.0, 20.0),
                                            'band_lo_hz': (2500.0, 2000.0, 3000.0), 'band_hi_hz': (5000.0, 4000.0, 6000.0),
                                            'max_trim_db': (3.0, 1.0, 6.0)}),
    'bow.breath_gap':        dict(meaning='bowed/wind melody has a breath or bow gap', params={'gap_beats': (0.08, 0.02, 0.2)}),
    'chroma.concordance':    dict(meaning='ambient beds against the key (semitone clash)', params={'max_dissonance': (0.28, 0.1, 0.5)}),
    'kick.grid':             dict(meaning='kick transients locked to the beat grid', params={'min_lock': (0.70, 0.3, 0.9)}),
    # immersive headphone route (scripts/quality_gate.py::immersive_rows, references/spatial/immersive-spatial.md). Registered here
    # so a type of piece can skip or relax one with a measured reason; the numbers below are the gate's starting points.
    'imm.cues':          dict(meaning='binaural probe at +-60 deg: level difference and which ear arrives first',
                              params={'min_ild_db': (8.0, 4.0, 20.0), 'min_itd_ms': (0.3, 0.1, 1.0)}),
    'imm.elevation':     dict(meaning='the high-frequency tilt grows with height', params={'min_tilt_db': (3.0, 1.0, 10.0)}),
    'imm.frontback':     dict(meaning='front and rear colour differ', params={'min_tilt_db': (2.0, 1.0, 10.0)}),
    'imm.height_rules':  dict(meaning='heights legal, bass and drums flat, enough tracks lifted'),
    'imm.band':          dict(meaning='a lifted stem holds energy above 4 kHz to carry its height',
                              params={'min_hf_frac': (0.003, 0.001, 0.02)}),
    'imm.externalization': dict(meaning='reflections arrive from several directions at a sane level',
                                params={'min_directions': (3, 1, 6), 'min_db': (-30.0, -40.0, -12.0), 'max_db': (-3.0, -12.0, 0.0)}),
    'imm.envelopment':   dict(meaning='late-tail interaural correlation', params={'max_late_iacc': (0.4, 0.1, 0.9)}),
    'imm.width':         dict(meaning='master L/R correlation', params={'max_corr': (0.95, 0.7, 1.0)}),
    'imm.foldown':       dict(meaning='mono fold-down level loss', params={'max_lu': (3.0, 1.0, 8.0)}),
    'imm.coloration':    dict(meaning='the measured head set colours the front of the mix no more than tolerance',
                              params={'max_dev_db': (3.5, 1.0, 8.0), 'lo_hz': (500.0, 200.0, 1000.0),
                                      'hi_hz': (5000.0, 3000.0, 10000.0)}),
    'imm.route_parity':  dict(meaning='the measured-head route and the analytic route agree on level and time difference',
                              params={'max_ild_db': (3.0, 1.0, 8.0), 'max_itd_ms': (0.20, 0.05, 0.6)}),
    # rendering naturalness (references/instruments-and-vocals/natural-instruments.md, humanization.md)
    'natural.aliasing':  dict(meaning='energy above 15 kHz that a transposed sample should not have (interpolation images)',
                              params={'max_hf_share_db': (-45.0, -70.0, -20.0)}),
    # delivery traceability (scripts/helpers/, written at certification; the gate only reads it)
    'meta.tags':     dict(meaning='standard metadata written beside the certified master',
                          params={'max_missing': (0, 0, 12)}),
    # the direction sheet is the promise the delivery is judged against (scripts/quality_gate.py direction_rows)
    'delivery.sample_rate': dict(meaning='delivered sample rate against the direction sheet'),
    'delivery.bit_depth':   dict(meaning='delivered bit depth against the direction sheet'),
    'delivery.channels':    dict(meaning='delivered channel count against the direction sheet'),
    'delivery.duration':    dict(meaning='delivered length against the direction sheet',
                                  params={'tolerance_s': (0.5, 0.1, 5.0)}),
    'tempo.bpm':            dict(meaning='score tempo inside the range the direction sheet promises'),
    'key.mode':             dict(meaning='score key and mode against the direction sheet'),
    'meta.version':  dict(meaning='a version record for the certified master, and its versioned file still on disk',
                          params={'max_missing': (0, 0, 5)}),
    # video delivery (scripts/video_score.py; measured by video-mixer/video_gate.py)
    'video.duration_lock':   dict(meaning='program length against the picture', params={'tolerance_ms': (50, 10, 200)}, protected=True),
    'video.cut_sync':        dict(meaning='every hit against its cut, early and late measured separately',
                                  params={'early_ms': (45, 10, 150), 'late_ms': (125, 20, 300), 'aim_ms': (40, 5, 120)}),
    'video.dialogue_snr':    dict(meaning='music level under speech', params={'min_db': (15.0, 6.0, 30.0)}),
    'video.master_compliance': dict(meaning='delivered loudness and true peak against the master profile',
                                    params={'tolerance_lu': (1.0, 0.3, 3.0)}, protected=True),
    # vocal tracks (scripts/vocals.py + vocal_engine; measured by quality_gate.vocal_rows from the render's vocal report)
    'vocal.integrity':    dict(meaning='vocal stems finite, no DC offset, no limiter hit', params={'dc_max': (0.005, 0.0005, 0.02)}, protected=True),
    'vocal.clicks':       dict(meaning='single-sample jumps inside a vocal stem (joins between notes)', params={'max_clicks': (0, 0, 5)}),
    'vocal.breath':       dict(meaning='a phrase longer than the singers can hold on one breath',
                               params={'over_capacity_factor': (1.0, 0.8, 2.0)}),
    'vocal.ensemble':     dict(meaning='3+ voices that are really one voice copied (stem correlation)', params={'max_corr': (0.6, 0.3, 0.9)}),
    'vocal.intonation':   dict(meaning='sung pitch against the written pitch, vibrato excluded', params={'max_cents': (60.0, 20.0, 150.0)}),
    'vocal.dynamics':     dict(meaning='note level follows note velocity (no per-note normalisation)', params={'min_corr': (0.5, 0.0, 0.9)}),
    'vocal.hum_tone':     dict(meaning='a hum stays dark and murmur-like, not a bright instrument tone', params={'max_hf_frac': (0.02, 0.001, 0.2)}),
    'vocal.ring':         dict(meaning="the singer's formant is an F3-F5 cluster near 2.8-3.2 kHz, not a boost pole",
                               params={'max_spread_hz': (400.0, 150.0, 900.0),
                                       'spread_at_zero_hz': (1600.0, 800.0, 3000.0)}),
    'vocal.formant_tuning': dict(meaning='a note whose f0 is above F1 keeps its fundamental out of a spectral valley',
                                 params={'max_deficit_db': (6.0, 2.0, 12.0)}),
    'vocal.consonant':    dict(meaning='consonants sit in their declared band before the onset, at the declared VOT',
                               params={'vot_tol': (0.3, 0.1, 0.6), 'centroid_margin': (2.0, 1.2, 4.0)}),
    'vocal.coarticulation': dict(meaning='the formant track moves toward the next vowel before the note boundary',
                                 params={'min_lead_ms': (20.0, 5.0, 60.0)}),
    'vocal.perturbation': dict(meaning='period-to-period jitter measured on the rendered signal (not flutter)',
                               params={'min_pct': (0.3, 0.1, 1.0), 'max_pct': (2.0, 1.0, 4.0)}, no_skip=True),
    'vocal.passaggio':    dict(meaning='no register step across the break (open quotient stays continuous)',
                               params={'max_step': (0.01, 0.002, 0.05)}),
    'vocal.vibrato':      dict(meaning='vibrato carries amplitude modulation in step with f0',
                               params={'min_corr': (0.5, 0.2, 0.9), 'min_db': (0.2, 0.05, 2.0)}),
    'vocal.identity':     dict(meaning='two singers have measurably different tracts (formant distance)',
                               params={'min_pct': (2.0, 1.0, 8.0)}),
    # cognitive feel checks (pattern_audit.cognitive_feel_checks); modes apply/skip, relaxing is by the profile's flags
    'feel.contour':    dict(meaning='melodic arch / gap-fill'),
    'feel.resolution': dict(meaning='harmonic tension to resolution'),
    'feel.groove':     dict(meaning='groove pocket lock'),
    'feel.effort':     dict(meaning='kinematic effort / respiration'),
    'feel.spiral':     dict(meaning='tonal tension arc'),
    'feel.witek':      dict(meaning='groove pleasure curve'),
    'feel.entropy':    dict(meaning='melodic information entropy'),
}


# The report and the profile must name the same row, or nobody can tell which rule was relaxed. The gate prints some rows
# under a descriptive id (cochlear_roughness, spiral_tension_arc); the profile owns them under a stable one (roughness,
# feel.spiral). canonical() maps a reported id to its profile row, so `on`/`mode`/`param` work whichever id the caller has.
ALIASES = {
    'cochlear_roughness': 'roughness',
    'kick_grid': 'kick.grid',
    'harmonic_concordance': 'chroma.concordance',
    'erb_binaural_masking': 'masking.vs_melody',
    'balance': 'balance.vs_lead',
    'melodic_contour_feel': 'feel.contour',
    'harmonic_resolution_feel': 'feel.resolution',
    'groove_pocket_lock': 'feel.groove',
    'kinematic_effort_feel': 'feel.effort',
    'spiral_tension_arc': 'feel.spiral',
    'witek_groove_curve': 'feel.witek',
    'melodic_information_entropy': 'feel.entropy',
    'imm_cues': 'imm.cues',
    'imm_elevation': 'imm.elevation',
    'imm_frontback': 'imm.frontback',
    'imm_height_rules': 'imm.height_rules',
    'imm_band': 'imm.band',
    'imm_externalization': 'imm.externalization',
    'imm_envelopment': 'imm.envelopment',
    'imm_width': 'imm.width',
    'imm_foldown': 'imm.foldown',
    'imm_coloration': 'imm.coloration',
    'imm_route_parity': 'imm.route_parity',
    'natural_aliasing': 'natural.aliasing',
}
REPORT_IDS = {}
for _reported, _row in ALIASES.items():
    REPORT_IDS.setdefault(_row, []).append(_reported)


def canonical(rid):
    """The profile row that owns a reported row id (identity when it already is a profile row)."""
    return ALIASES.get(rid, rid)


def _pspec(row, name):
    row = canonical(row)
    return (ROWS[row].get('params') or {}).get(name)


def defaults(row):
    return {k: v[0] for k, v in (ROWS[row].get('params') or {}).items()}


def _check_range(row, name, val, problems, where):
    spec = _pspec(row, name)
    if spec is None:
        problems.append(f'{where}: row "{row}" has no parameter "{name}". Parameters: {sorted(ROWS[row].get("params") or {}) or "none"}')
        return
    if isinstance(spec[0], bool):
        if not isinstance(val, bool):
            problems.append(f'{where}: {row}.{name} must be true or false')
        return
    if isinstance(spec[0], str):                     # an enumerated parameter: the tuple lists the allowed values
        if val not in spec:
            problems.append(f'{where}: {row}.{name} must be one of {list(spec)}, not {val!r}')
        return
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        problems.append(f'{where}: {row}.{name} must be a number')
    elif not spec[1] <= val <= spec[2]:
        problems.append(f'{where}: {row}.{name} = {val} is outside {spec[1]}..{spec[2]} (that would switch the check off, not adapt it)')


def row_problems(rows, where):
    """Problems in a {row: {mode, reason, params}} mapping (a preset's "rows" or a score's "gate")."""
    problems = []
    if not isinstance(rows, dict):
        return [f'{where}: "rows" must be an object {{row: {{mode, reason, ...}}}}']
    for rid0, cfg in rows.items():
        rid = canonical(rid0)
        if rid not in ROWS:
            problems.append(f'{where}: unknown row "{rid0}". Rows: {", ".join(sorted(ROWS))}')
            continue
        if not isinstance(cfg, dict):
            problems.append(f'{where}: row "{rid}" must be an object')
            continue
        mode = cfg.get('mode', 'apply')
        if mode not in MODES:
            problems.append(f'{where}: {rid}.mode "{mode}" is not one of {MODES}')
            continue
        extra = [k for k in cfg if k not in ('mode', 'reason', 'fallback') and k not in (ROWS[rid].get('params') or {})]
        for k in extra:
            problems.append(f'{where}: row "{rid}" has no parameter "{k}". Parameters: {sorted(ROWS[rid].get("params") or {}) or "none"}')
        if ROWS[rid].get('protected'):
            if mode != 'apply' or len(cfg) > (1 if 'mode' in cfg else 0):
                problems.append(f'{where}: "{rid}" is a protected row: it cannot be relaxed, skipped or retuned by any type of music')
            continue
        if mode == 'skip' and ROWS[rid].get('no_skip'):
            problems.append(f'{where}: "{rid}" cannot be skipped (it is the rule that makes the others safe); relax its numbers instead')
        if mode in ('relax', 'skip') and not str(cfg.get('reason', '')).strip():
            problems.append(f'{where}: {rid} is {mode} but has no "reason" (say why this type of music needs it)')
        if mode == 'skip' and any(k in (ROWS[rid].get('params') or {}) for k in cfg):
            problems.append(f'{where}: {rid} is skip and also sets parameters; pick one')
        if 'fallback' in cfg and cfg['fallback'] not in ROWS:
            problems.append(f'{where}: {rid}.fallback "{cfg["fallback"]}" is not a row')
        for k, v in cfg.items():
            if k in (ROWS[rid].get('params') or {}):
                _check_range(rid, k, v, problems, where)
    return problems


def profile_problems(name, p, all_profiles):
    where = f'gate/{name}'
    problems = []
    if not str(p.get('character', '')).strip():
        problems.append(f'{where}: missing "character" (one sentence: the type of music and why these rules suit it)')
    ext = p.get('extends')
    if ext is not None:
        seen, cur = [name], ext
        while cur is not None:
            if cur not in all_profiles:
                problems.append(f'{where}: extends "{cur}", which does not exist. Known: {sorted(all_profiles)}')
                break
            if cur in seen:
                problems.append(f'{where}: extends loops: {" -> ".join(seen + [cur])}')
                break
            seen.append(cur)
            cur = all_profiles[cur].get('extends')
    for f in p.get('flags', []):
        if f not in FLAGS:
            problems.append(f'{where}: flag "{f}" is not one of {FLAGS}')
    det = p.get('detect') or {}
    for k in det:
        if k not in ('keywords', 'pulse', 'traits'):
            problems.append(f'{where}: detect has unknown key "{k}" (keywords, pulse, traits)')
    for k in ('keywords', 'pulse'):
        if not all(isinstance(w, str) for w in det.get(k, [])):
            problems.append(f'{where}: detect.{k} must be a list of words')
    for k, v in (det.get('traits') or {}).items():
        if k not in TRAITS:
            problems.append(f'{where}: unknown trait "{k}". Traits: {sorted(TRAITS)}')
        elif not (isinstance(v, (int, float)) and TRAITS[k][0] <= v <= TRAITS[k][1]):
            problems.append(f'{where}: trait {k} must be {TRAITS[k][0]}..{TRAITS[k][1]}')
    problems += row_problems(p.get('rows', {}), where)
    return problems


def shipped_names():
    """Names of the profiles shipped with the skill (from the folder, so a project profile can never look shipped)."""
    folder = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate')
    try:
        return {os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith('.json')}
    except OSError:
        return set()


def problems(project_dirs=()):
    """Problems in every gate profile (shipped and project). Empty = good.

    A project may add a profile and `extends` any shipped one, but it may not reuse a shipped profile's NAME: that would
    retune the whole type in every piece of the project at once, which is exactly how a gate gets quietly switched off.
    """
    shipped = shipped_names()
    shipped_dir = os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'gate').replace('\\', '/')
    for d in project_dirs:
        presets.add_project(d)
    allp = presets.load('gate')
    out = []
    for name, p in allp.items():
        src = str(p.get('_source') or '').replace('\\', '/')
        if name in shipped and src and not src.startswith(shipped_dir):
            out.append(f'gate/{name}: a project profile may not redefine the shipped profile "{name}". Give it its own name '
                       f'and "extends": "{name}", so the report says which type this piece was judged as')
    if DEFAULT_PROFILE not in allp:
        out.append(f'gate/{DEFAULT_PROFILE}: the default profile is missing')
    for name, p in allp.items():
        out += profile_problems(name, p, allp)
    return out


def _chain(name, allp):
    """Profile names from the root ancestor down to `name`."""
    chain, cur = [], name
    while cur is not None and cur not in chain:
        chain.append(cur)
        cur = allp[cur].get('extends')
    return chain[::-1]


def _merge_profile(name, allp):
    flags, rows, why = set(), {}, []
    for n in _chain(name, allp):
        p = allp[n]
        flags |= set(p.get('flags', []))
        for rid, cfg in (p.get('rows') or {}).items():
            rows[rid] = presets._deep_merge(rows.get(rid, {}), cfg)
    return flags, rows


def _drone_ratio(score):
    tr = [t for t in score.get('tracks', []) if t.get('role') not in ('drum', 'environment') and 'notes' in t]
    if not tr:
        return 0.0
    return sum(1 for t in tr if t.get('is_drone') or t.get('allow_ostinato') or t.get('role') in ('drone', 'pad')) / len(tr)


def _score_text(score):
    meta = score.get('meta') or {}
    emotion = str(meta.get('emotion') or score.get('emotion', '')).lower()
    genre = str(meta.get('genre') or score.get('genre', '')).lower()
    feels = [str(f).lower() for f in (score.get('feel') or meta.get('mood_notes') or [])]
    pulse = str(score.get('pulse', '')).lower()
    return emotion + ' ' + genre + ' ' + ' '.join(feels) + ' ' + pulse, pulse


def infer(score, allp):
    """[(name, hits, why)] for every profile whose `detect` matches the score, strongest last."""
    text, pulse = _score_text(score)
    drone = _drone_ratio(score)
    found = []
    for name, p in allp.items():
        det = p.get('detect') or {}
        hits, why = 0, []
        for k in det.get('keywords', []):
            if k in text:
                hits += 1
                why.append(f'"{k}"')
        if pulse and pulse in det.get('pulse', []):
            hits += 1
            why.append(f'pulse={pulse}')
        dm = (det.get('traits') or {}).get('drone_ratio_min')
        if dm is not None and drone > dm:
            hits += 1
            why.append(f'drone_ratio {drone:.2f}')
        if hits:
            found.append((name, hits, ', '.join(why)))
    found.sort(key=lambda f: f[1])
    return found


class Profile:
    def __init__(self, names, how, why, flags, rows, errors):
        self.names, self.how, self.why, self.flags, self.rows, self.errors = names, how, why, flags, rows, errors

    @property
    def label(self):
        return '+'.join(self.names)

    def mode(self, rid):
        return self.rows.get(canonical(rid), {}).get('mode', 'apply')

    def on(self, rid):
        """False when the row is skipped by this type of piece."""
        return self.mode(rid) != 'skip'

    def param(self, rid, name):
        rid = canonical(rid)
        return self.rows.get(rid, {}).get(name, defaults(rid)[name])

    def fallback(self, rid):
        return self.rows.get(canonical(rid), {}).get('fallback')

    def notes(self):
        """Report rows: the chosen type, then every relaxed or skipped row with its reason."""
        out = [('INFO', 'piece_type', f'{self.label} ({self.how}{": " + self.why if self.why else ""})')]
        for rid in sorted(self.rows):
            cfg = self.rows[rid]
            m = cfg.get('mode', 'apply')
            shown = rid if rid not in REPORT_IDS else f'{rid} (reported as {", ".join(REPORT_IDS[rid])})'
            if m == 'skip':
                out.append(('INFO', 'gate_skip', f'SKIP {shown}: {cfg.get("reason", "")}'))
            elif m == 'relax':
                nums = ', '.join(f'{k}={v}' for k, v in cfg.items() if k not in ('mode', 'reason', 'fallback'))
                out.append(('INFO', 'gate_relax', f'{shown}: {nums or "relaxed"} ({cfg.get("reason", "")})'))
        for e in self.errors:
            out.append(('FAIL', 'piece_type', e))
        return out


def resolve(score):
    """The profile for this score: declared piece_type (name or list, merged in order), else inferred, else 'melodic'.
    score["gate"] row overrides are merged last. Never raises: an unknown type becomes a FAIL row (Profile.errors)."""
    allp = presets.load('gate')
    errors = []
    decl = score.get('piece_type')
    names, how, why = [], 'default', ''
    if decl:
        want = [decl] if isinstance(decl, str) else list(decl)
        want = [presets._norm(w) for w in want]
        for w in want:
            if w in allp:
                names.append(w)
            else:
                errors.append(f'piece_type "{w}" is not a gate profile. Known: {sorted(allp)}. Write one: gate_profiles.py new {w} --project <dir>')
        how = 'declared'
    if not names and not decl:
        found = infer(score, allp)
        if found:
            names = [f[0] for f in found]
            how = 'inferred'
            why = '; '.join(f'{n}: {w}' for n, _, w in found)
    if not names:
        names = [DEFAULT_PROFILE] if DEFAULT_PROFILE in allp else []
    flags, rows = set(), {}
    for n in names:
        f, r = _merge_profile(n, allp)
        flags |= f
        for rid, cfg in r.items():
            rows[rid] = presets._deep_merge(rows.get(rid, {}), cfg)
    over = score.get('gate')
    if over:
        errors += row_problems(over, 'score "gate"')
        for rid, cfg in over.items():
            rid = canonical(rid)
            if rid in ROWS and not ROWS[rid].get('protected'):
                rows[rid] = presets._deep_merge(rows.get(rid, {}), cfg)
    return Profile(names, how, why, flags, rows, errors)


# ---------- command line ----------
def _row_line(rid, cfg):
    m = cfg.get('mode', 'apply')
    nums = ', '.join(f'{k}={v}' for k, v in cfg.items() if k not in ('mode', 'reason', 'fallback'))
    return f'    {rid:22s} {m:5s} {nums}  - {cfg.get("reason", "")}'


def cmd_list():
    allp = presets.load('gate')
    for name in sorted(allp):
        p = allp[name]
        flags, rows = _merge_profile(name, allp)
        print(f'{name}: {p.get("character", "")}   [{p.get("_source")}]')
        if p.get('extends'):
            print(f'  extends {p["extends"]}; flags {sorted(flags) or "-"}')
        for rid in sorted(rows):
            print(_row_line(rid, rows[rid]))


def cmd_rows():
    for rid, r in ROWS.items():
        ps = ', '.join(f'{k}={v[0]} ({v[1]}..{v[2]})' if len(v) == 3 and not isinstance(v[0], str) else f'{k}={"|".join(str(x) for x in v)}' for k, v in (r.get('params') or {}).items())
        print(f'{rid:22s} {"PROTECTED " if r.get("protected") else ""}{r["meaning"]}' + (f'  [{ps}]' if ps else ''))


def cmd_explain(score_path):
    score = json.load(open(score_path, encoding='utf-8'))
    p = resolve(score)
    for lv, name, d in p.notes():
        print(f'[{lv}] {name}: {d}')
    print(f'flags: {sorted(p.flags) or "-"}')
    print('every row (final):')
    for rid in ROWS:
        cfg = dict(defaults(rid) if not ROWS[rid].get('protected') else {}, **p.rows.get(rid, {}))
        cfg.setdefault('mode', 'apply')
        print(_row_line(rid, cfg))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['list', 'explain', 'new', 'check', 'rows'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--project', default=None)
    ap.add_argument('--from', dest='from_name', default=None)
    a = ap.parse_args()
    if a.project:
        presets.add_project(a.project)
    if a.cmd == 'list':
        cmd_list()
    elif a.cmd == 'rows':
        cmd_rows()
    elif a.cmd == 'explain':
        cmd_explain(a.arg)
    elif a.cmd == 'new':
        print('wrote', presets.scaffold('gate', a.arg, a.project or '.', a.from_name))
    elif a.cmd == 'check':
        bad = problems()
        print('\n'.join(bad) if bad else 'all gate profiles are valid')
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
