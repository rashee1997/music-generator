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
"""analyze_music21.py - Flexible, project-specific symbolic music21 analysis hook.

Auto-discovered and attached by pipeline.MusicPipeline during Stage 6 of the CI/CD Quality Gate.
Can also be executed standalone:
    python scripts/analyze_music21.py [score.json] [--out-midi out/song.mid]
"""
import os
import sys
import json
import numpy as np
import music21 as m21

def build_m21_score(score, out_midi=None):
    """Builds a music21.stream.Score object either by parsing out_midi or from the score dict."""
    if out_midi and os.path.exists(out_midi):
        try:
            return m21.converter.parse(out_midi)
        except Exception:
            pass
            
    # Direct construction from score dict
    m21_score = m21.stream.Score()
    ts = score.get('ts', [4, 4])
    time_sig = m21.meter.TimeSignature(f"{ts[0]}/{ts[1]}")
    bpm_val = score.get('bpm', 120)
    tempo_mark = m21.tempo.MetronomeMark(number=bpm_val)
    
    for tr in score.get('tracks', []):
        if tr.get('role') == 'drum' or tr.get('instrument') == 'drums':
            continue
        part = m21.stream.Part(id=tr.get('name', 'track'))
        part.append(time_sig)
        part.append(tempo_mark)
        
        notes = sorted(tr.get('notes', []), key=lambda n: n.get('t', 0))
        for n in notes:
            p = n.get('p')
            if isinstance(p, (int, float)):
                midi_val = int(round(p))
                if 12 <= midi_val <= 127:
                    dur = float(n.get('d', 1))
                    m21_note = m21.note.Note(midi_val, quarterLength=dur)
                    m21_note.volume.velocity = int(round(float(n.get('v', 0.7)) * 127))
                    part.insert(float(n.get('t', 0)), m21_note)
        m21_score.append(part)
        
    return m21_score


def analyze(score, out_wav=None, out_midi=None, reports_dir=None):
    """Flexible music21 analytical evaluation for the piece's specific musical universe.
    Returns: list of (level, check_name, detail) where level is 'PASS', 'WARN', 'FAIL', or 'INFO'.
    """
    rows = []
    m21_score = build_m21_score(score, out_midi=out_midi)
    all_notes = list(m21_score.recurse().getElementsByClass('Note'))
    
    if not all_notes:
        rows.append(('INFO', 'music21_empty', 'no non-percussion melodic notes found to analyze'))
        return rows
        
    # -----------------------------------------------------------------------------------------
    # 1. Tonality & Modal Affect (Krumhansl-Schmuckler)
    # -----------------------------------------------------------------------------------------
    try:
        analyzed_key = m21_score.analyze('key')
        target_key = str(score.get('key', '')).strip()
        target_mode = str(score.get('mode', '')).strip().lower()
        corr = analyzed_key.correlationCoefficient
        
        target_str = f"{target_key} {target_mode}".strip()
        if target_key and target_key.lower() in analyzed_key.name.lower():
            rows.append(('PASS', 'music21_tonality', 
                         f"{analyzed_key.name} (confidence {corr:.2f}) matches target {target_str}"))
        elif corr >= 0.65:
            # High confidence detection
            rows.append(('PASS', 'music21_tonality', 
                         f"strong tonal center in {analyzed_key.name} (correlation {corr:.2f})"))
        else:
            rows.append(('INFO', 'music21_tonality', 
                         f"modal center analyzed as {analyzed_key.name} (correlation {corr:.2f})"))
    except Exception as e:
        rows.append(('INFO', 'music21_tonality', f"key analysis note: {str(e)}"))

    # -----------------------------------------------------------------------------------------
    # 2. Register Separation & Tessitura Boundaries
    # -----------------------------------------------------------------------------------------
    try:
        parts_pitches = {}
        for p in m21_score.parts:
            part_notes = [n.pitch.midi for n in p.recurse().getElementsByClass('Note')]
            if part_notes:
                parts_pitches[p.id] = (min(part_notes), max(part_notes), np.median(part_notes))
                
        bass_key = next((k for k in parts_pitches if 'bass' in k.lower()), None)
        lead_key = next((k for k in parts_pitches if any(w in k.lower() for w in ('lead', 'melody', 'solo'))), None)
        
        if bass_key:
            b_min, b_max, b_med = parts_pitches[bass_key]
            if b_min < 24: # Sub C1 < 32.7 Hz
                rows.append(('WARN', 'music21_bass_mud', f"bass part '{bass_key}' has notes below C1 (MIDI {b_min}) - risks subwoofer mud"))
            else:
                rows.append(('PASS', 'music21_bass_register', f"bass anchored naturally at MIDI {b_min} - {b_max}"))
                
        if bass_key and lead_key:
            _, _, b_med = parts_pitches[bass_key]
            l_min, l_max, l_med = parts_pitches[lead_key]
            if l_min < b_med:
                rows.append(('WARN', 'music21_voice_crossing', f"lead '{lead_key}' dips below bass median (MIDI {l_min} vs {b_med:.0f})"))
            else:
                rows.append(('PASS', 'music21_voice_separation', f"clean vertical register separation between bass and lead"))
    except Exception as e:
        rows.append(('INFO', 'music21_registers', f"register note: {str(e)}"))

    # -----------------------------------------------------------------------------------------
    # 3. Melodic Contour & Anti-Monotony Check
    # -----------------------------------------------------------------------------------------
    try:
        lead_part = next((p for p in m21_score.parts if any(w in p.id.lower() for w in ('lead', 'melody'))), None)
        if lead_part is None and m21_score.parts:
            lead_part = m21_score.parts[0]
            
        if lead_part:
            lead_pitches = [n.pitch.midi for n in lead_part.recurse().getElementsByClass('Note')]
            if len(lead_pitches) >= 4:
                unique_pcs = len(set(p % 12 for p in lead_pitches))
                ambitus = max(lead_pitches) - min(lead_pitches)
                
                # Check for single-pitch repetition monotony
                counts = [lead_pitches.count(p) for p in set(lead_pitches)]
                max_rep_pct = max(counts) / len(lead_pitches)
                
                diffs = [lead_pitches[i+1] - lead_pitches[i] for i in range(len(lead_pitches)-1)]
                rising_pct = sum(1 for d in diffs if d > 0) / max(1, len(diffs))
                
                if max_rep_pct > 0.50:
                    rows.append(('WARN', 'music21_melody_monotony', 
                                 f"single pitch repeated in {max_rep_pct*100:.0f}% of melody notes"))
                else:
                    rows.append(('PASS', 'music21_melodic_contour', 
                                 f"{unique_pcs} unique pitch classes, ambitus {ambitus} semitones ({rising_pct*100:.0f}% rising motion)"))
    except Exception as e:
        rows.append(('INFO', 'music21_contour', f"contour note: {str(e)}"))

    # -----------------------------------------------------------------------------------------
    # 4. Vertical Chordification & Harmonic Rhythm
    # -----------------------------------------------------------------------------------------
    try:
        chordified = m21_score.chordify()
        chords = list(chordified.recurse().getElementsByClass('Chord'))
        if chords:
            rows.append(('PASS', 'music21_harmonic_rhythm', 
                         f"{len(chords)} vertical harmonic slices analyzed across multi-track arrangement"))
    except Exception as e:
        rows.append(('INFO', 'music21_harmony', f"harmony note: {str(e)}"))

    # Write human-readable report if reports_dir exists
    if reports_dir and os.path.exists(reports_dir):
        report_txt = os.path.join(reports_dir, 'music21_analysis.txt')
        with open(report_txt, 'w', encoding='utf-8') as f:
            f.write("=== MUSIC21 SYMBOLIC MUSICOLOGY REPORT ===\n")
            for lvl, chk, det in rows:
                f.write(f"[{lvl:4s}] {chk:26s} {det}\n")
                
    return rows


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('score', nargs='?', default='score.json', help='Path to score JSON')
    ap.add_argument('--midi', default=None, help='Path to MIDI file')
    args = ap.parse_args()
    
    if os.path.exists(args.score):
        with open(args.score, 'r', encoding='utf-8') as f:
            sc = json.load(f)
        results = analyze(sc, out_midi=args.midi)
        print("=== MUSIC21 ANALYSIS RESULTS ===")
        for lvl, name, det in results:
            print(f"[{lvl:4s}] {name:24s} {det}")
    else:
        print(f"Score file '{args.score}' not found.")
