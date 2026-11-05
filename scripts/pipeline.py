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
"""pipeline.py - Unified CI/CD Music Generation & Quality Verification Pipeline.

A single orchestrator that unifies the entire music generation lifecycle:
  Stage 1: Composition & Score Ingestion (compose.py, theory.py, world.py)
  Stage 2: Acoustic Pre-Flight Linter (pattern_audit.py: 6 Acoustic Laws)
  Stage 3: Humanization & Phrase Respiration (humanize.py: E(t) arcs, microtiming)
  Stage 4: Multi-Engine Stem Rendering (tinysoundfont, vocals.py, environment.py, clone_instrument.py)
  Stage 5: High-Precision Mixing & Mastering (mixer.py: subtractive EQ, shared room, pb.BrickwallLimiter)
  Stage 6: Automated CI Quality Suite (quality_gate.py: loudness, true peak, masking, chroma, mobile mono, kick grid, vocal rows)
  Stage 7: Certified Release Packaging (master WAV, MIDI, stems/, ci_report.json)

Stage 0 (project_gate.py) runs first in project mode: scaffold, research note, direction sheet and exact presets
for every non-built-in instrument must exist, or nothing renders.

Usage:
  python3 scripts/pipeline.py <project>/scores/<title>_score.json [--project <project>]
      project mode (real music): writes out/master.wav, midi/<title>_score.mid, stems/*.wav, reports/ci_report.json
      by default; exit code 1 when any Stage 6 check FAILs; --max-attempts N prints the stop rule.
  python3 scripts/pipeline.py "motivational trailer in D minor, 8s" --test --out x.wav
      test mode: smoke test with generic General MIDI instruments, never a deliverable
  python3 scripts/pipeline.py master.wav --check-only        # audit an existing master
  python3 scripts/pipeline.py --selftest
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# Ensure scripts directory is in sys.path
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS_DIR)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import cli_util
import compose
import envcheck
import gate_report
import stem_gate
from helpers import ingest_metadata, version_manager
import humanize as hz
import mixer
import naturalness_check as nc
import pattern_audit
import presets
import project_gate
import quality_gate as qg
import render_natural as rn
import soundbank as sb

SR = 44100


STEM_FLOOR = 3e-4            # about -70 dBFS: below this a stem is treated as silence


def trim_stem(x, sr=SR, pre_s=0.05):
    """(active part of a stem, start in seconds). A stem that enters in the middle is cut to where it sounds."""
    a = np.abs(np.asarray(x)).max(axis=1) if np.ndim(x) == 2 else np.abs(x)
    idx = np.flatnonzero(a > STEM_FLOOR)
    if len(idx) == 0:
        return np.zeros((1,) + np.shape(x)[1:], np.float32), 0.0
    i0 = max(0, int(idx[0]) - int(pre_s * sr))
    return x[i0:int(idx[-1]) + 1], i0 / sr


def write_stems(stems, stems_dir, full=False, sr=SR):
    """Write stems/<name>.wav. Default: each stem holds only the part where it sounds, and stems.json records
    its start_s so it can be put back on the timeline. full=True writes aligned full-length stems instead."""
    os.makedirs(stems_dir, exist_ok=True)
    total = max((len(x) for x in stems.values()), default=0)
    manifest = {}
    for name, x in stems.items():
        seg, start = (x, 0.0) if full else trim_stem(x, sr)
        if full and len(x) < total:
            seg = np.pad(x, ((0, total - len(x)),) + ((0, 0),) * (x.ndim - 1))
        sf.write(os.path.join(stems_dir, f"{name}.wav"), np.asarray(seg, np.float32), sr)
        manifest[name] = dict(start_s=round(start, 4), length_s=round(len(seg) / sr, 4), timeline_s=round(total / sr, 4))
    with open(os.path.join(stems_dir, 'stems.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


class MusicPipeline:
    """The unified CI/CD Music Generation Pipeline."""

    def __init__(self, verbose=True):
        self.verbose = verbose

    def log(self, stage_num, stage_name, msg=""):
        if self.verbose:
            print(f"\n[CI/CD Stage {stage_num}: {stage_name}] {msg}")

    # -----------------------------------------------------------------------------------------
    # Stage 1: Composition & Score Ingestion
    # -----------------------------------------------------------------------------------------
    def parse_prompt_to_brief(self, text, **overrides):
        """Parse natural language prompt into a structured brief dictionary."""
        brief = {}
        s = text.lower()

        # Duration parsing: "30s", "45 sec", "60 seconds"
        m_dur = re.search(r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\b', s)
        if m_dur:
            brief['duration_s'] = float(m_dur.group(1))

        # BPM parsing: "110 bpm", "72bpm"
        m_bpm = re.search(r'(\d+(?:\.\d+)?)\s*bpm\b', s)
        if m_bpm:
            brief['bpm'] = float(m_bpm.group(1))

        # Key & mode parsing: "in d minor", "c# major", "e dorian"
        m_key = re.search(r'\b(?:in\s+)?([a-g][#b]?)\s+(major|minor|dorian|mixolydian|phrygian|aeolian|lydian)\b', s)
        if m_key:
            brief['key'] = m_key.group(1).upper()
            brief['mode'] = m_key.group(2)

        # Emotion matching
        for emo in sorted(compose.EMOTIONS, key=len, reverse=True):
            if re.search(rf'\b{re.escape(emo)}\b', s):
                brief['emotion'] = emo
                break
        if 'emotion' not in brief:
            for alias, target in compose.EMOTION_ALIASES.items():
                if re.search(rf'\b{re.escape(alias)}\b', s):
                    brief['emotion'] = target
                    break

        # Genre matching
        for gen in sorted(compose.GENRES, key=len, reverse=True):
            if re.search(rf'\b{re.escape(gen)}\b', s):
                brief['genre'] = gen
                break
        if 'genre' not in brief:
            for alias, target in compose.GENRE_ALIASES.items():
                if re.search(rf'\b{re.escape(alias)}\b', s):
                    brief['genre'] = target
                    break

        # Space / Room matching
        for sp in ('dry', 'studio', 'hall', 'large_hall', 'cathedral'):
            if re.search(rf'\b{re.escape(sp)}\b', s):
                brief['space'] = sp
                break

        # Voice-over / Loop flags
        if 'voiceover' in s or 'voice-over' in s or 'speech' in s:
            brief['voiceover'] = True
        if 'loop' in s or 'seamless' in s:
            brief['loop'] = True

        # Apply CLI overrides
        for k, v in overrides.items():
            if v is not None:
                brief[k] = v

        if 'notes' not in brief:
            brief['notes'] = text
        return brief

    def stage1_ingest(self, input_spec, **overrides):
        """Stage 1: Ingest existing score JSON, brief dict, or free-form prompt."""
        self.log(1, "Composition & Score Ingestion")
        if isinstance(input_spec, dict):
            if 'tracks' in input_spec:
                score = input_spec
            else:
                score = compose.compose(input_spec)
        elif isinstance(input_spec, str) and (input_spec.endswith('.json') or os.path.exists(input_spec)):
            p = Path(input_spec)
            cli_util.require_file(str(p), 'score')
            data = json.loads(p.read_text(encoding='utf-8'))
            if 'tracks' in data:
                score = data
            else:
                score = compose.compose(data)
        else:
            brief = self.parse_prompt_to_brief(str(input_spec), **overrides)
            if self.verbose:
                print(f"  Parsed brief: {brief}")
            score = compose.compose(brief)

        cli_util.normalize_pitches(score)   # 'D3' -> 50, so later stages only see numbers

        # Apply any explicit command-line overrides to score
        if overrides.get('bpm'):
            score['bpm'] = overrides['bpm']
        if overrides.get('key'):
            score['key'] = overrides['key']
        if self.verbose:
            print(f"  Score: '{score.get('title', 'Untitled')}' | Key: {score.get('key')} | BPM: {score.get('bpm')} | Tracks: {len(score.get('tracks', []))}")
        return score

    # -----------------------------------------------------------------------------------------
    # Stage 2: Acoustic Pre-Flight Linter (The 6 Acoustic Laws)
    # -----------------------------------------------------------------------------------------
    def stage2_preflight_lint(self, score, strict=False):
        """Stage 2: Check the 6 Acoustic Laws and 4 Cognitive Feel Laws prior to rendering."""
        self.log(2, "Acoustic & Cognitive Pre-Flight Linter (Acoustic Laws + Cognitive Feel Laws)")
        rows = pattern_audit.acoustic_checks(score)
        fails = sum(1 for kind, _, _ in rows if kind == 'FAIL')
        warns = sum(1 for kind, _, _ in rows if kind == 'WARN')
        clean = (fails == 0)
        for kind, name, msg in rows:
            if self.verbose:
                status = "FAIL" if kind == 'FAIL' else "WARN"
                print(f"  [{status}] {name:20s}: {msg}")
            if kind == 'FAIL':
                clean = False

        if not clean and strict:
            raise RuntimeError(f"Pre-Flight linter failed with {fails} FAIL(s) in strict mode.")
        elif clean and self.verbose:
            print("  [PASS] All Acoustic & Cognitive Feel Laws satisfied (Voicing, Resonance, Percussion, Flams, Low Mud, Space, Contour, Harmonic Resolution, Groove Pocket, Kinematic Effort).")
        return rows

    # -----------------------------------------------------------------------------------------
    # Stage 3: Humanization & Respiration
    # -----------------------------------------------------------------------------------------
    def stage3_humanize(self, score):
        """Stage 3: Prepare tempo map, rubato, and phrase respiration."""
        self.log(3, "Humanization & Phrase Respiration")
        # One factory, shared with the renderer: the duration printed here is the duration of the audio.
        tm = hz.tempo_map_for(score)
        if self.verbose:
            h_mode = score.get('humanize', 'natural')
            dur_s = float(tm.secs[-1]) if len(tm.secs) else 0.0
            print(f"  Applied humanization profile: '{h_mode}' | Tempo-map duration: {dur_s:.1f}s")
        return tm

    # -----------------------------------------------------------------------------------------
    # Stage 4: Multi-Engine Stem Rendering
    # -----------------------------------------------------------------------------------------
    def stage4_render_stems(self, score, stems_dir=None, stems_full=False):
        """Stage 4: Render stems using SoundFont, vocals, and environment engines."""
        self.log(4, "Multi-Engine Stem Rendering")
        sb.ensure_soundfont()
        stems, tm = rn.build_stems(score, verbose=self.verbose)
        if stems_dir:
            man = write_stems(stems, stems_dir, full=stems_full)
            if self.verbose:
                kept = sum(m['length_s'] for m in man.values())
                whole = sum(m['timeline_s'] for m in man.values())
                print(f"  Exported {len(stems)} stems to: {stems_dir}/ ({'full length' if stems_full else f'active parts only, {kept:.0f} s of {whole:.0f} s'}; stems.json has each start)")
        return stems, tm

    # -----------------------------------------------------------------------------------------
    # Stage 5: Mixing & Mastering
    # -----------------------------------------------------------------------------------------
    def stage5_mix_and_master(self, score, stems, out_wav, target=None):
        """Stage 5: mix and master one deliverable; the target preset's `renderer` names the route."""
        self.log(5, "Mixing & Mastering (Pedalboard DSP + BrickwallLimiter)")
        os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
        import render_targets
        from spatial_engine import render as spatial_render
        name = target or ((render_targets.resolve(score)['selected'] or ['stereo'])[0])
        renderer = (render_targets.get(name) or {}).get('renderer')
        if renderer in ('spatial', 'binaural'):
            spatial_render.render_deliverable(score, stems, name, out_wav)
            try:                       # the same advisory diagnostics the stereo path leaves for the gate
                import mix_diagnostics
                mixer.STATE['diagnostics'] = mix_diagnostics.analyse(
                    score, mixer.STATE.get('processed') or stems, mix=mixer._mix(),
                    master=mixer.STATE.get('master'))
            except Exception as exc:
                print(f"  [WARN] mixing diagnostics did not run for {name} ({exc})")
        else:
            mixer.mix_and_master(score, stems, out_wav, diagnose=True)
        if self.verbose:
            print(f"  Wrote {name} deliverable: {out_wav}")
        return out_wav

    def discover_and_run_music21_analysis(self, score, out_wav, out_midi=None):
        """Auto-discovers and attaches a flexible music21 analysis script from the project's scripts/ folder.
        If a project provides its own scripts/analyze_music21.py, it runs it.
        Otherwise, falls back to the dynamic music21 analysis engine in templates/analyze_music21_template.py.
        """
        candidates = []
        if score.get('analysis_script'):
            candidates.append(score['analysis_script'])
            
        out_parent = os.path.dirname(os.path.abspath(out_wav))
        proj_dir = os.path.dirname(out_parent)
        # One canonical hook: setup_project.py writes <project>/scripts/analyze_music21.py. No CWD or
        # sibling-folder guesses: the project gate has already proven this folder exists.
        candidates.append(os.path.join(proj_dir, 'scripts', 'analyze_music21.py'))
        
        script_path = None
        for c in candidates:
            if os.path.exists(c):
                script_path = c
                break
                
        reports_dir = os.path.join(proj_dir, 'reports')
        reports_dir = reports_dir if os.path.isdir(reports_dir) else None
        
        if script_path:
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("project_music21_analyzer", script_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, 'analyze'):
                    return mod.analyze(score, out_wav=out_wav, out_midi=out_midi, reports_dir=reports_dir)
                elif hasattr(mod, 'run_checks'):
                    return mod.run_checks(score, out_wav=out_wav, out_midi=out_midi)
            except Exception as e:      # a project's own analysis that crashes must not pass silently
                return [('FAIL', 'music21_hook', f"project analysis script '{os.path.basename(script_path)}' crashed: {e}")]
                
        # Default flexible analyzer fallback
        try:
            tmpl_path = os.path.join(SKILL_DIR, 'templates', 'analyze_music21_template.py')
            if os.path.exists(tmpl_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("default_music21_analyzer", tmpl_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.analyze(score, out_wav=out_wav, out_midi=out_midi, reports_dir=reports_dir)
        except Exception as e:
            return [('WARN', 'music21_hook', f"default music21 analysis did not run: {e}")]
        return []

    # -----------------------------------------------------------------------------------------
    # Stage 6: Automated CI/CD Quality Gate Suite
    # -----------------------------------------------------------------------------------------
    def stage6_ci_quality_suite(self, score, stems, out_wav, out_midi=None, stem_rows=None, mode='full'):
        """Stage 6: Exhaustive battery of objective audio & mix tests.

        One call to quality_gate.run_gate, not a hand-copied subset of it: every row the gate knows (score and render
        checks, ambience against its measured reference, the physics behaviour of each sfx/env stem, balance, vocals,
        chroma, kick grid, soul, masking) runs here, so `pipeline.py <score>` and `quality_gate.py <score>` cannot drift.
        The mixing diagnostics go on top as advisory `mix:` rows."""
        self.log(6, "Automated CI/CD Quality Gate Suite")
        mix_metrics = []
        ci_rows, _ = qg.run_gate(None, wav_path=out_wav, refresh=False, stems=stems, score=score,
                                 mode=mode, metrics=mix_metrics)
        self.mix_metrics = mix_metrics
        if stem_rows:
            ci_rows = list(stem_rows) + ci_rows          # stem rows first: the earlier stage owns the first verdict

        # Mixing diagnostics (mixer.STATE, written by stage 5). Advisory by contract: the gate's own rows own the
        # blocking verdicts (true peak, clipping, silence), so a diagnostic FAIL is reported here as a WARN.
        import mixer
        for lvl, name, detail in mixer.STATE.get('diagnostics') or []:
            if lvl in ('FAIL', 'WARN', 'INFO'):
                ci_rows.append(('WARN' if lvl == 'FAIL' else lvl, f'mix:{name}', detail))

        # Auto-attach flexible music21 symbolic analysis
        m21_rows = self.discover_and_run_music21_analysis(score, out_wav, out_midi=out_midi)
        if m21_rows:
            ci_rows.extend(m21_rows)

        # Print scoreboard
        fails = sum(1 for lvl, _, _ in ci_rows if lvl == 'FAIL')
        warns = sum(1 for lvl, _, _ in ci_rows if lvl == 'WARN')
        passes = sum(1 for lvl, _, _ in ci_rows if lvl == 'PASS')

        if self.verbose:
            print(f"\n  --- CI/CD Quality Scoreboard: {passes} PASS, {warns} WARN, {fails} FAIL ---")
            for lvl, name, detail in ci_rows:
                indicator = f"[{lvl:4s}]"
                print(f"  {indicator} {name:26s} {detail}")

        import mixer
        mixer.release_stems()          # Stage 6 has measured the processed stems; nothing reads them again
        return ci_rows, fails, warns

    # -----------------------------------------------------------------------------------------
    # Stage 7: Certified Release Packaging
    # -----------------------------------------------------------------------------------------
    def stage7_package_release(self, score, out_wav, ci_rows, fails, warns, out_midi=None, json_report=None):
        """Stage 7: Package deliverables, export MIDI, and write CI report."""
        self.log(7, "Certified Release Packaging")
        if out_midi:
            compose.export_midi(score, out_midi)
            if self.verbose:
                print(f"  Exported MIDI: {out_midi}")

        # Measure master file audio attributes and neuro-cognitive perception metrics
        analysis = nc.analyse(out_wav)
        _, rough_metrics = nc.cochlear_roughness_check(out_wav, score=score)
        cog_metrics = pattern_audit.cognitive_metrics(score)

        report = {
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'status': 'PASSED' if fails == 0 else 'FAILED',
            'deliverables': {
                'master_wav': out_wav,
                'midi': out_midi,
                'duration_s': analysis.get('dur'),
                'sample_rate': analysis.get('sr')
            },
            'measurements': {
                'integrated_lufs': analysis.get('lufs'),
                'true_peak_dbtp': analysis.get('true_peak'),
                'crest_factor_db': analysis.get('crest'),
                'mono_loss_db': analysis.get('mono_loss'),
                'mono_phone_loss_db': analysis.get('mono_phone_loss'),
                'clipped_samples': analysis.get('clipped'),
                'mean_roughness': rough_metrics.get('mean_roughness', 0.0),
                'max_roughness': rough_metrics.get('max_roughness', 0.0),
                'witek_bsi': cog_metrics.get('witek_bsi', 0.0),
                'melodic_entropy_bits': cog_metrics.get('melodic_entropy_bits', 2.0),
                'spiral_strain_end': cog_metrics.get('spiral_strain_end', 0.0)
            },
            'ci_summary': {'pass': sum(1 for l, _, _ in ci_rows if l == 'PASS'),
                           'warn': warns,
                           'fail': fails},
            'ci_checks': [{'level': l, 'check': n, 'detail': d} for l, n, d in ci_rows]
        }

        if json_report:
            with open(json_report, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            if self.verbose:
                print(f"  Wrote CI/CD JSON report: {json_report}")

        return report

    # -----------------------------------------------------------------------------------------
    # Preset & Stem Discovery for Pre-Existing Music
    # -----------------------------------------------------------------------------------------
    def adopt_presets(self, score, presets_dir=None, project_dir=None):
        """Auto-discover and adopt presets from project presets/ directory into score tracks.
        Preserves all existing musical notes while attaching spatial, EQ, humanization, and role definitions."""
        candidates = []
        if presets_dir and os.path.exists(presets_dir):
            candidates.append(presets_dir)
        if project_dir and os.path.exists(project_dir):
            candidates.extend([
                os.path.join(project_dir, 'presets'),
                os.path.join(os.path.dirname(project_dir), 'presets'),
            ])
        candidates.extend(['presets', os.path.join('..', 'presets')])

        target_dir = None
        skill_presets = os.path.abspath(os.path.join(SKILL_DIR, 'presets'))
        for c in candidates:
            if not (os.path.exists(c) and os.path.isdir(c)):
                continue
            if os.path.abspath(c) == skill_presets:
                continue          # the skill's own presets are the base layer; they are never a project
            target_dir = c
            break

        if not target_dir:
            return score

        p_dir = Path(target_dir)
        preset_map = {}
        for pf in p_dir.rglob('*.json'):
            try:
                data = json.loads(pf.read_text(encoding='utf-8'))
            except Exception as e:      # the project gate fails on this; outside project mode say so loudly
                print(f"  [WARN] preset '{pf.name}' is not valid JSON and was skipped: {e}")
                continue
            name = data.get('name') or pf.stem
            preset_map[name] = data
            preset_map[pf.stem] = data

        # Sound and place live in the preset, never in the score, so these keys replace whatever a track already
        # says: a stale t['spatial'] must not shadow a later edit of presets/*.json.
        preset_owns = ('spatial', 'synthesis', 'vocal', 'environment', 'formants', 'bandwidths', 'source',
                       'vibrato', 'articulation', 'performance', 'breathing', 'ensemble', 'humming', 'hum',
                       'atmosphere', 'layers', 'blending', 'character', 'vowel', 'expression', 'register_range',
                       'category', 'phonetic_sound', 'program', 'bank', 'gm')
        bookkeeping = ('name', 'kind', 'note', 'notes', 'sources')      # identity and prose stay in the preset file

        adopted = []
        for t in score.get('tracks', []):
            name = t.get('name')
            inst = t.get('instrument')
            matched = preset_map.get(name) or preset_map.get(inst)
            if matched:
                adopted.append(name or inst)
                for k, v in matched.items():
                    if k in bookkeeping:
                        continue
                    if k in preset_owns or k not in t:     # the rest (eq, humanize, gain_db, reverb, role) only fills a gap
                        t[k] = v

        if self.verbose:
            print(f"  Adopted {len(adopted)} preset definitions from: {target_dir}")
        score['_presets_adopted'] = adopted
        return score

    def load_stems_from_dir(self, stems_dir):
        """Load pre-rendered stems from a directory into a dictionary of audio arrays."""
        stems = {}
        if not stems_dir or not os.path.exists(stems_dir):
            return stems
        manifest = {}
        mp = os.path.join(stems_dir, 'stems.json')
        if os.path.isfile(mp):
            try:
                manifest = json.load(open(mp, encoding='utf-8'))
            except Exception as e:
                print(f"  [WARN] stems.json unreadable, stems are taken to start at 0: {e}")
        for f in os.listdir(stems_dir):
            if f.lower().endswith('.wav'):
                p = os.path.join(stems_dir, f)
                try:
                    x, _ = sf.read(p, always_2d=True)
                    m = manifest.get(os.path.splitext(f)[0])        # a trimmed stem goes back to where it starts
                    if m and m.get('start_s'):
                        x = np.pad(x, ((int(round(m['start_s'] * SR)), 0), (0, 0)))
                    stems[os.path.splitext(f)[0]] = x
                except Exception as e:
                    print(f"  [WARN] stem '{f}' could not be read and was skipped: {e}")
        if self.verbose and stems:
            print(f"  Loaded {len(stems)} pre-existing stems from: {stems_dir}")
        return stems

    def discover_project_files(self, target_path):
        """Auto-discover adjacent score, presets, and stems directories for a given audio or project path."""
        target = os.path.abspath(target_path)
        if os.path.isfile(target):
            parent = os.path.dirname(target)
            stem_name = Path(target).stem
        else:
            parent = target
            stem_name = Path(target).name

        proj_dir = parent
        score_path = None
        presets_dir = None
        stems_dir = None

        # Look for scores
        score_cands = [
            os.path.join(proj_dir, 'scores', f"{stem_name}_score.json"),
            os.path.join(proj_dir, 'scores', f"{stem_name.replace('_master', '')}_score.json"),
            os.path.join(proj_dir, f"{stem_name}_score.json"),
            os.path.join(proj_dir, f"{stem_name.replace('_master', '')}_score.json"),
            os.path.join(proj_dir, 'score.json')
        ]
        scores_folder = os.path.join(proj_dir, 'scores')
        if os.path.exists(scores_folder) and os.path.isdir(scores_folder):
            js = [os.path.join(scores_folder, f) for f in os.listdir(scores_folder) if f.endswith('.json')]
            if js:
                score_cands.extend(js)

        for sc in score_cands:
            if os.path.exists(sc) and os.path.isfile(sc):
                score_path = sc
                break

        # Look for presets
        p_cands = [os.path.join(proj_dir, 'presets'), os.path.join(os.path.dirname(proj_dir), 'presets')]
        for pc in p_cands:
            if os.path.exists(pc) and os.path.isdir(pc):
                presets_dir = pc
                break

        # Look for stems
        s_cands = [os.path.join(proj_dir, 'stems'), os.path.join(os.path.dirname(proj_dir), 'stems')]
        for sc in s_cands:
            if os.path.exists(sc) and os.path.isdir(sc):
                stems_dir = sc
                break

        return dict(project_dir=proj_dir, score_path=score_path, presets_dir=presets_dir, stems_dir=stems_dir)

    # -----------------------------------------------------------------------------------------
    # Master Execution Method
    # -----------------------------------------------------------------------------------------
    def execute(self, input_spec=None, out_wav=None, out_midi=None, stems_dir=None,
                strict=False, json_report=None, check_only=False, score_path=None,
                presets_dir=None, adopt_presets=True, wav_path=None, project=None, test=False,
                max_attempts=5, no_stems=False, stems_full=False, draft=False, targets=None, **overrides):
        """Execute the complete CI/CD Music Pipeline or Quality Check existing productions."""
        t_start = time.time()
        explicit_out = out_wav is not None
        out_wav = out_wav or "final.wav"
        print("=" * 80)
        print("  MUSIC-GENERATOR: UNIFIED CI/CD AUDIO PIPELINE")
        print("=" * 80)

        # Auto-detect check-only mode if input is an existing .wav file or if wav_path is provided
        is_wav_input = isinstance(input_spec, str) and (input_spec.lower().endswith('.wav') and os.path.exists(input_spec))
        if is_wav_input or wav_path is not None:
            check_only = True
            if is_wav_input and not wav_path:
                wav_path = input_spec

        if check_only:
            target_wav = wav_path or (out_wav if os.path.exists(out_wav) else input_spec)
            if not target_wav or not os.path.exists(target_wav):
                raise FileNotFoundError(f"Cannot perform quality check: target WAV '{target_wav}' does not exist.")

            discovered = self.discover_project_files(target_wav)
            resolved_score_path = score_path or discovered.get('score_path')
            resolved_presets_dir = presets_dir or discovered.get('presets_dir')
            resolved_stems_dir = stems_dir or discovered.get('stems_dir')

            if self.verbose:
                print(f"\n[CI/CD Mode: QUALITY CHECK ONLY (No Re-Rendering)]")
                print(f"  Target Master Audio : {target_wav}")
                print(f"  Project Root        : {discovered.get('project_dir')}")
                print(f"  Discovered Score    : {resolved_score_path}")
                print(f"  Discovered Presets  : {resolved_presets_dir}")
                print(f"  Discovered Stems    : {resolved_stems_dir}")

            # Stage 1: Ingest Score and Adopt Presets
            self.log(1, "Score Ingestion & Preset Adoption")
            if resolved_score_path and os.path.exists(resolved_score_path):
                score = json.loads(Path(resolved_score_path).read_text(encoding='utf-8'))
            elif isinstance(input_spec, str) and input_spec.endswith('.json') and os.path.exists(input_spec):
                score = json.loads(Path(input_spec).read_text(encoding='utf-8'))
            elif isinstance(input_spec, dict) and 'tracks' in input_spec:
                score = input_spec
            else:
                meas = nc.analyse(target_wav)
                score = {
                    'title': Path(target_wav).stem,
                    'bpm': overrides.get('bpm', 120.0),
                    'key': overrides.get('key', 'C'),
                    'ts': [4, 4],
                    'tracks': [],
                    'master': {'lufs': meas.get('lufs', -16.0), 'true_peak': -1.2}
                }

            if adopt_presets and resolved_presets_dir:
                score = self.adopt_presets(score, presets_dir=resolved_presets_dir, project_dir=discovered.get('project_dir'))

            # Stage 2: Preflight Lint on symbolic score if tracks exist
            if score.get('tracks'):
                self.stage2_preflight_lint(score, strict=strict)

            # Skip Stage 3, 4, 5 (NO RE-GENERATION!)
            stems = self.load_stems_from_dir(resolved_stems_dir) if resolved_stems_dir else {}

            # Stage 6: Automated CI Quality Suite
            ci_rows, fails, warns = self.stage6_ci_quality_suite(score, stems, target_wav, out_midi=out_midi)

            # Stage 7: Packaging & Report
            if not json_report:
                proj_reports = os.path.join(discovered.get('project_dir'), 'reports')
                if os.path.exists(proj_reports) and os.path.isdir(proj_reports):
                    json_report = os.path.join(proj_reports, f"{Path(target_wav).stem}_quality_report.json")

            report = self.stage7_package_release(score, target_wav, ci_rows, fails, warns,
                                                out_midi=out_midi, json_report=json_report)

            elapsed = time.time() - t_start
            print("=" * 80)
            status_str = "CERTIFIED PASS" if fails == 0 else f"AUDITED: {fails} FAILS"
            print(f"  QUALITY AUDIT COMPLETE ({elapsed:.1f}s) -> {status_str}")
            print(f"  Master: {target_wav} ({analysis_summary(report)})")
            print("=" * 80)
            return report

        # Normal Generation Pipeline Flow (Stage 0 gate, then Stages 1 through 7)
        is_file_input = isinstance(input_spec, str) and input_spec.endswith('.json') and os.path.isfile(input_spec)
        project_dir = None
        if not test:
            if project:
                project_dir = os.path.abspath(project)
            elif is_file_input:
                p_cand = os.path.dirname(os.path.abspath(input_spec))
                if os.path.basename(p_cand) in ('scores', 'score', 'direction', 'scripts', 'reports', 'out'):
                    p_cand = os.path.dirname(p_cand)
                project_dir = p_cand
            else:
                raise SystemExit("Real music needs a project: python scripts/setup_project.py --new-project <dir> --title <T>, "
                                 "then pipeline.py <dir>/scores/<title>_score.json --project <dir>. "
                                 "For a throwaway smoke test add --test.")
            if not os.path.isdir(project_dir):
                raise SystemExit(f"project folder not found: {project_dir}")
            presets.STRICT = True
            presets.reset_projects()          # one piece never inherits the previous project's presets
            presets.add_project(project_dir)
            if presets_dir or not adopt_presets:
                raise SystemExit("--presets-dir / --no-adopt-presets are for --test or --check-only; "
                                 "a project always uses <project>/presets.")
            presets_dir = os.path.join(project_dir, 'presets')
        else:
            presets.STRICT = False
            presets.reset_projects()
            print("  *** TEST RENDER - generic General MIDI instruments, not a deliverable ***")

        if project_dir and not explicit_out:
            out_wav = os.path.join(project_dir, 'out', 'master.wav')
        if not out_wav.lower().endswith('.wav'):
            out_wav = out_wav + '.wav'
        if out_midi and not (out_midi.lower().endswith('.mid') or out_midi.lower().endswith('.midi')):
            out_midi = out_midi + '.mid'

        # Stage 1: Ingestion
        score = self.stage1_ingest(input_spec, **overrides)

        # Output formats: the score (a project file) names the deliverables and the presets hold every number about
        # them. Build only what was asked for; block rather than silently downgrade a format the engine cannot build.
        import render_targets
        if targets:
            score['output_targets'] = [t.strip() for t in str(targets).split(',') if t.strip()]
        outputs = render_targets.resolve(score)
        if outputs['problems']:
            for pr in outputs['problems']:
                print(f"  [BLOCKED] {pr}")
            raise SystemExit(f"Output target blocked the render: {len(outputs['problems'])} problem(s) above.")
        if project_dir and not explicit_out and outputs['selected']:
            out_wav = os.path.join(project_dir, 'out', render_targets.filename(outputs['selected'][0]))
        skipped = ''.join(f"; skipped {s['target']} (cannot be built yet)" for s in outputs['skipped'])
        print(f"  [OUTPUTS] {', '.join(outputs['selected']) or 'nothing'}{skipped}")

        # Stage 0: project gate (needs the score to check its tracks), before any audio is made
        if project_dir:
            self.log("1b", "Project Gate (scaffold, research, direction, exact presets)")
            for w in project_gate.warnings(Path(project_dir), score):
                print(f"  [WARN] {w}")
            probs = project_gate.problems(score, project_dir)
            if probs:
                for pr in probs:
                    print(f"  [BLOCKED] {pr}")
                raise SystemExit(f"Project gate blocked the render: {len(probs)} problem(s) above. Fix them and re-run.")
            print("  [PASS] project is complete")
            stem_title = Path(input_spec).stem if is_file_input else score.get('title', 'piece').replace(' ', '_')
            out_midi = out_midi or os.path.join(project_dir, 'midi', f"{stem_title}.mid")
            stems_dir = stems_dir or (None if no_stems else os.path.join(project_dir, 'stems'))
            json_report = json_report or os.path.join(project_dir, 'reports', 'ci_report.json')
            os.makedirs(os.path.dirname(out_midi), exist_ok=True)
            os.makedirs(os.path.dirname(json_report), exist_ok=True)

        if adopt_presets:
            score = self.adopt_presets(score, presets_dir=presets_dir, project_dir=project_dir)

        prev_attempts = []
        if project_dir and json_report and os.path.isfile(json_report):
            try:
                prev_attempts = json.loads(Path(json_report).read_text(encoding='utf-8')).get('attempts', [])
            except Exception:
                prev_attempts = []

        # Stage 2: Acoustic Pre-Flight
        self.stage2_preflight_lint(score, strict=strict)

        # Stage 3: Humanization & Respiration
        self.stage3_humanize(score)

        # Stage 4: Multi-Engine Stem Rendering (stems are written here, before mixing)
        stems, tm = self.stage4_render_stems(score, stems_dir=stems_dir, stems_full=stems_full)

        # Stage 4b: stem gate. A stem FAIL stops here: the mixer would only average the defect into the master.
        self.log('4b', 'Stem Gate (each stem measured alone, before the mix)')
        stem_rows, stem_meta = stem_gate.run_stem_gate(
            score, stems, sr=SR, workers=int(os.environ.get('GATE_WORKERS', '2')),
            report_dir=(os.path.join(project_dir, 'reports', 'gate') if project_dir else None),
            mode='draft' if draft else 'full')
        self.stem_meta = stem_meta
        if self.verbose:
            for lvl, name, detail in stem_rows:
                print(f"  [{lvl:4s}] {name:26s} {detail}")
            print(f"  stem gate: {stem_meta['fails']} FAIL, {stem_meta['warns']} WARN, "
                  f"{len(stem_rows)} rows, {stem_meta['total_ms']:.0f} ms on {stem_meta['workers']} worker(s)")
        if stem_meta['fails']:
            print(f"  [BLOCKED] {stem_meta['fails']} stem FAIL(s): mixing is not allowed until they are fixed")
            failing = [f"{n}: {d}" for l, n, d in stem_rows if l == 'FAIL']
            report = dict(timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), status='FAILED',
                          mode='project' if project_dir else 'test',
                          deliverables=dict(master_wav=None, stems_dir=stems_dir, stem_count=len(stems)),
                          ci_summary=dict(pass_=sum(1 for l, _, _ in stem_rows if l == 'PASS'),
                                          warn=stem_meta['warns'], fail=stem_meta['fails']),
                          ci_checks=[dict(level=l, name=n, detail=d) for l, n, d in stem_rows],
                          gate=dict(mode='draft' if draft else 'full', stopped='stem',
                                    stages=dict(stem=stem_meta, mix=None)))
            if project_dir and json_report:
                report['attempts'] = prev_attempts + [dict(attempt=len(prev_attempts) + 1, time=report['timestamp'],
                                                           fails=stem_meta['fails'], failing=failing)]
                Path(json_report).write_text(json.dumps(report, indent=2), encoding='utf-8')
            return report

        # Stage 5: Mixing & Mastering. Written to a draft path: out/ only receives a master the gate
        # has certified, so a file sitting in out/ is always a finished one, never a stub.
        draft_wav = os.path.join(os.path.dirname(out_wav) or '.', '_draft_' + os.path.basename(out_wav))
        self.stage5_mix_and_master(score, stems, draft_wav)

        # Stage 6: Automated CI Quality Suite
        ci_rows, fails, warns = self.stage6_ci_quality_suite(
            score, stems, draft_wav, out_midi=out_midi, stem_rows=stem_rows,
            mode='draft' if draft else 'full')

        if project_dir:
            try:
                gate_report.write_reports(draft_wav, score, os.path.join(project_dir, 'reports', 'gate'),
                                          stem_meta=stem_meta,
                                          mix_meta=dict(stage='mix', metrics=self.mix_metrics))
            except Exception as exc:              # the gate verdict stands even if a figure could not be drawn
                print(f"  [WARN] gate report figures not written ({exc})")

        published = None
        if fails == 0 and not draft:
            if project_dir:
                # A certified render never destroys the previous one: it becomes master_vNN.wav and
                # out/master.wav is refreshed as a copy of the newest version.
                try:
                    published = version_manager.publish(draft_wav, out_wav, score=score,
                                                        attempts=prev_attempts)
                    print(f"  [VERSION] master v{published['version']:02d}: {published['file']} "
                          f"({published['change']})")
                except Exception as exc:      # never lose a certified master over bookkeeping
                    print(f"  [WARN] versioning failed ({exc}); promoting the draft without a version record")
                    os.replace(draft_wav, out_wav)
            else:
                os.replace(draft_wav, out_wav)
        elif draft:
            print(f"  [DRAFT] --draft run: {fails} FAIL, {warns} WARN. The mix stays at {draft_wav}; nothing was published")
        else:
            print(f"  [DRAFT] {fails} gate FAIL(s): the uncertified mix stays at {draft_wav}, {out_wav} is untouched")

        # Additional requested formats: rendered only after the primary is certified, so one format's failure never
        # takes the certified master with it; each is checked against its own format rows before it enters out/.
        extra_paths = []
        if fails == 0 and not draft and project_dir and len(outputs['selected']) > 1:
            self.log('5b', 'Additional deliverable formats')
            import spatial_gate
            from spatial_engine import render as spatial_render
            for extra in outputs['selected'][1:]:
                rel = render_targets.filename(extra)
                extra_draft = os.path.join(os.path.dirname(out_wav) or '.', '_draft_' + rel)
                spatial_render.render_deliverable(score, stems, extra, extra_draft)
                rows = []
                spatial_gate.output_rows(score, extra_draft, rows)
                bad = [(n, d) for lvl, n, d in rows if lvl == 'FAIL']
                if bad:
                    for n, d in bad:
                        print(f"  [FAIL] {n}: {d}")
                    print(f"  [WARN] {extra} did not pass its own format rows; its file stays at {extra_draft}")
                    continue
                final = os.path.join(project_dir, 'out', rel)
                os.replace(extra_draft, final)
                extra_paths.append(final)
                print(f"  [OUTPUT] {extra}: {final}")

        # Stage 7: Packaging & Report
        report = self.stage7_package_release(score, out_wav if fails == 0 else draft_wav, ci_rows, fails, warns,
                                            out_midi=out_midi, json_report=json_report)
        report['deliverables']['outputs'] = outputs['selected']
        report['deliverables']['outputs_skipped'] = outputs['skipped']
        report['deliverables']['output_files'] = extra_paths if project_dir and fails == 0 else []
        report['mode'] = 'project' if project_dir else 'test'
        report['gate'] = dict(mode='draft' if draft else 'full', stopped=None,
                              stages=dict(stem=stem_meta,
                                          mix=dict(stage='mix', fails=fails, warns=warns,
                                                   metrics=self.mix_metrics,
                                                   images=(os.path.join(project_dir, 'reports', 'gate')
                                                           if project_dir else None))))
        report['deliverables']['stems_dir'] = stems_dir
        report['deliverables']['stem_count'] = len(stems) if stems_dir else 0
        if project_dir:
            failing = [f"{n}: {d}" for l, n, d in ci_rows if l == 'FAIL']
            report['attempts'] = prev_attempts + [dict(attempt=len(prev_attempts) + 1, time=report['timestamp'],
                                                       fails=fails, failing=failing)]
        if json_report:            # stage 7 wrote its dict before the gate block existed; write the complete record
            Path(json_report).write_text(json.dumps(report, indent=2), encoding='utf-8')

        # Only a certified render gets a version record and standard metadata.
        if published:
            try:
                version_manager.update_entry(Path(project_dir) / 'out', published['version'],
                                             measurements=report.get('measurements'))
                sheet = ingest_metadata.find_direction(project_dir)
                numbers = {'version': published['version'],
                           'ci_report': os.path.basename(json_report or '')}
                info = ingest_metadata.ingest(out_wav, score=score, project_dir=project_dir,
                                              extra=numbers, direction=sheet)
                report['deliverables']['metadata'] = info['sidecar']
                report['deliverables']['version'] = published['version']
                report['deliverables']['versioned_master'] = published['file']
                report['deliverables']['metadata_tagged'] = info['tagged']
                if info['tag_error']:
                    report['deliverables']['metadata_tag_error'] = info['tag_error']
                    print(f"  [WARN] tags were NOT written into {out_wav}: {info['tag_error']}")
                    print(f"         the audio is certified; fix the file and run: python scripts/helpers/ingest_metadata.py "
                          f"\"{out_wav}\" --project \"{project_dir}\"")
                versioned_wav = os.path.join(project_dir, 'out', published['file'])
                vinfo = ingest_metadata.ingest(versioned_wav, score=score, project_dir=project_dir,
                                              extra=dict(numbers, version=published['version']), direction=sheet)
                report['deliverables']['versioned_metadata'] = vinfo['sidecar']
                if vinfo['tag_error']:
                    report['deliverables']['versioned_metadata_tag_error'] = vinfo['tag_error']
                    print(f"  [WARN] tags were NOT written into {published['file']}: {vinfo['tag_error']}")
                Path(json_report).write_text(json.dumps(report, indent=2), encoding='utf-8')
                print(f"  [METADATA] {info['sidecar']}")
            except Exception as exc:          # the audio is already certified and safe
                report['deliverables']['metadata_error'] = str(exc)
                print(f"  [WARN] metadata step failed ({exc})")
                Path(json_report).write_text(json.dumps(report, indent=2), encoding='utf-8') if json_report else None

        elapsed = time.time() - t_start
        print("=" * 80)
        status_str = "CERTIFIED PASS" if fails == 0 else f"BUILT WITH {fails} FAILS"
        print(f"  PIPELINE COMPLETE ({elapsed:.1f}s) -> {status_str}")
        print(f"  Master: {out_wav} ({analysis_summary(report)})")
        if project_dir:
            n = len(report['attempts'])
            if fails == 0:
                print(f"  STOP: all gates passed after {n} attempt(s). Run listen.py, then deliver.")
                import importlib.util
                if importlib.util.find_spec('earshot') is None:
                    print("  NOTE: earshot is not installed, so listen.py can only measure; say the ears were not run (setup_project.py --ears).")
            elif n >= max_attempts:
                print(f"  STOP: {n} attempts and {fails} gate(s) still failing. Do not keep retrying; report these to the user:")
                for f_ in failing:
                    print(f"    - {f_}")
            else:
                print(f"  CONTINUE: attempt {n}/{max_attempts}, {fails} FAIL. Change ONE lever "
                      f"(references/workflow/music-direction.md section 6) and run again.")
        print("=" * 80)
        return report


def analysis_summary(rep):
    m = rep.get('measurements', {})
    return f"{m.get('integrated_lufs', 0):.1f} LUFS, {m.get('true_peak_dbtp', 0):.1f} dBTP"


def selftest():
    """Verify that all 7 stages execute cleanly on a test cue, and check-only mode audits existing masters."""
    print("Running Music CI/CD Pipeline Selftest...")
    pipe = MusicPipeline(verbose=True)
    with tempfile.TemporaryDirectory() as td:
        out_wav = os.path.join(td, "selftest.wav")
        out_mid = os.path.join(td, "selftest.mid")
        rep_json = os.path.join(td, "report.json")
        brief = {
            'emotion': 'calm',
            'duration_s': 6.0,
            'bpm': 80.0,
            'key': 'C',
            'mode': 'major',
            'space': 'hall',
            'notes': 'selftest cue'
        }
        rep = pipe.execute(brief, out_wav=out_wav, out_midi=out_mid, json_report=rep_json, test=True)
        assert os.path.exists(out_wav), "Master WAV was not created"
        assert os.path.exists(out_mid), "MIDI file was not created"
        assert os.path.exists(rep_json), "Report JSON was not created"
        assert rep['measurements']['clipped_samples'] == 0, "Clipped samples detected"
        assert rep['measurements']['true_peak_dbtp'] <= -0.5, "True peak ceiling breached"

        # Test check-only auditing on the generated master
        rep_audit = pipe.execute(out_wav, check_only=True)
        assert rep_audit['deliverables']['master_wav'] == out_wav, "Check-only mode failed to target master WAV"

    gate_selftest()
    print("\nALL 7 PIPELINE STAGES, CHECK-ONLY MODE AND THE PROJECT GATE PASSED THE CI/CD SELFTEST SUCCESSFULLY!")


def gate_selftest():
    """Stage 0: an empty scaffold is blocked; research + direction + exact presets unblock it; fuzzy names stay blocked."""
    import setup_project
    kb_id = sorted(project_gate.kb_document_ids())[0]
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / 'p'
        setup_project.scaffold_project(str(proj), title='Gate Test')
        for f in (proj / 'reports').glob('research_*.md'):
            f.unlink()
        for f in (proj / 'presets').rglob('*.json'):
            f.unlink()
        score = dict(title='t', bpm=90, tracks=[dict(name='lead', instrument='arabic_oud_lute', role='melody', notes=[]),
                                                dict(name='pad', instrument='slow_strings', role='pad', notes=[])])
        probs = project_gate.problems(score, proj)
        assert any('research' in x for x in probs) and any('arabic_oud_lute' in x for x in probs), probs
        assert not any('slow_strings' in x for x in probs), "built-in GM name must not need a preset"
        (proj / 'reports' / 'research_t.md').write_text(
            f"# R\n## Knowledge base\n- id: {kb_id}\n## Web research\nhttps://example.org/oud\n", encoding='utf-8')
        fixture = Path(__file__).resolve().parent.parent / 'tests' / 'fixtures' / 'gate_case.json'
        (proj / 'presets' / 'instruments' / 'arabic_oud_lute.json').write_text(
            fixture.read_text(encoding='utf-8'), encoding='utf-8')
        (proj / 'presets' / 'spaces').mkdir(parents=True, exist_ok=True)
        room = json.loads((Path(presets.SKILL_PRESETS) / 'spaces' / 'hall.json').read_text(encoding='utf-8'))
        room.update(name='gate_room', character='a test room')
        (proj / 'presets' / 'spaces' / 'gate_room.json').write_text(json.dumps(room), encoding='utf-8')
        score['space'] = 'gate_room'
        sheet = proj / 'direction' / 'direction_sheet.json'
        assert any('TODO' in x for x in project_gate.problems(score, proj)), "unfilled direction sheet must block"
        sheet.write_text(sheet.read_text(encoding='utf-8').replace('TODO', 'filled'), encoding='utf-8')
        assert project_gate.problems(score, proj) == [], project_gate.problems(score, proj)
        score['tracks'][0]['instrument'] = 'arabic_oud'          # a near miss must not be guessed
        assert any('arabic_oud' in x for x in project_gate.problems(score, proj))
        score['tracks'][0]['instrument'] = 'arabic_oud_lute'
        score['tracks'].append(dict(name='hit', instrument='sfx:coin', role='fx', notes=[]))
        assert project_gate.problems(score, proj) == [], "a one-hit effect needs only its shipped default"
        score['tracks'].append(dict(name='rain', instrument='sfx:rain', role='fx', notes=[]))
        assert any('ambience' in x for x in project_gate.problems(score, proj)), "ambience through sfx: must be blocked"
    presets.STRICT = False
    print("  project gate selftest passed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('input', nargs='?', help='Brief string, path to brief/score JSON, or path to master WAV to check')
    ap.add_argument('--check-only', action='store_true', help='Quality check existing music without re-generating stems or master')
    ap.add_argument('--wav', default=None, help='Path to existing master WAV file for quality checking')
    ap.add_argument('--score', default=None, help='Path to score JSON file for symbolic & acoustic checks')
    ap.add_argument('--presets-dir', default=None, help='Directory to adopt instrument, environment, and vocal presets from')
    ap.add_argument('--adopt-presets', action='store_true', default=True, help='Auto-discover and adopt presets from project directory (default: True)')
    ap.add_argument('--no-adopt-presets', action='store_false', dest='adopt_presets', help='Disable preset adoption')
    ap.add_argument('--stems', '--stems-dir', dest='stems', default=None, help='Folder with pre-existing stems or folder to export stems')
    ap.add_argument('--out', default=None, help='Output master WAV (default: <project>/out/master.wav, or final.wav with --test)')
    ap.add_argument('--midi', default=None, help='Output MIDI (default in a project: <project>/midi/<score>.mid)')
    ap.add_argument('--bpm', type=float, help='Override tempo BPM')
    ap.add_argument('--key', help='Override musical key (e.g. "D minor")')
    ap.add_argument('--report', default=None, help='Optional JSON path to save CI/CD test report')
    ap.add_argument('--strict', action='store_true', help='Fail pipeline if any acoustic law fails')
    ap.add_argument('--selftest', action='store_true', help='Run pipeline selftest')
    ap.add_argument('--project', default=None, help='Project folder (real music). Defaults to the folder holding the score')
    ap.add_argument('--test', action='store_true', help='Smoke test: bare brief allowed, no project gate, not a deliverable')
    ap.add_argument('--no-stems', action='store_true', help='Do not write stems/ (project mode writes them by default)')
    ap.add_argument('--stems-full', action='store_true', help='Export every stem full length and aligned (default: only the part where each stem sounds, with stems.json)')
    ap.add_argument('--max-attempts', type=int, default=5, help='Attempt count after which a failing run says STOP (default 5)')
    ap.add_argument('--draft', action='store_true', help='Fast check: skip tier 2 rows and never publish to out/')
    ap.add_argument('--targets', default=None,
                    help='Deliverable formats, comma separated, overriding the score: stereo, binaural, immersive_7_1, immersive_7_1_4, or all')
    ap.add_argument('--gate-workers', type=int, default=None, help='Threads for the per-stem gate rows (default 2 or $GATE_WORKERS)')
    a = ap.parse_args()
    if a.gate_workers:
        os.environ['GATE_WORKERS'] = str(a.gate_workers)
    sys.stdout.reconfigure(line_buffering=True)     # a redirected log must show each stage as it runs
    for w in envcheck.mismatches():
        print(f"  [WARN] package: {w}")

    if a.selftest:
        selftest()
        return

    if not a.input and not a.wav:
        ap.print_help()
        sys.exit(1)

    pipe = MusicPipeline(verbose=True)
    rep = pipe.execute(a.input, out_wav=a.out, out_midi=a.midi, stems_dir=a.stems,
                       strict=a.strict, json_report=a.report, bpm=a.bpm, key=a.key,
                       check_only=a.check_only, score_path=a.score, presets_dir=a.presets_dir,
                       adopt_presets=a.adopt_presets, wav_path=a.wav, project=a.project, test=a.test,
                       max_attempts=a.max_attempts, no_stems=a.no_stems, stems_full=a.stems_full, draft=a.draft,
                       targets=a.targets)
    sys.exit(1 if rep['ci_summary']['fail'] else 0)        # an agent calling this must see a failed gate


if __name__ == '__main__':
    main()
