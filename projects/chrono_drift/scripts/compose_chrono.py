#!/usr/bin/env python3
"""Chrono Drift: write the score and finish the scaffolded presets.

Run from the skill root:

    PYTHONPATH=/tmp/deps python3 projects/chrono_drift/scripts/compose_chrono.py

Every number here is a decision recorded in direction/direction_chrono_drift.json and
reports/research_space_time_travel_a_ship_falling_through_a_collapsing_wormhole.md.
The score holds notes and preset names only; sound and space live in presets/.
"""
import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SKILL = PROJECT.parents[1]
REPORTS = PROJECT / 'reports'

BPM = 72.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT
D2, E2, F2, C3, D3, F3, G3, A3, C4, D4, E4, F4, G4, A4, C5, D5, F5, A5 = (
    38, 40, 41, 48, 50, 53, 55, 57, 60, 62, 64, 65, 67, 69, 72, 74, 77, 81)
A5_TICK, D6_TICK = 81, 86


def bar(n, beat=0.0):
    """Seconds at 1-based bar n and a beat inside it."""
    return round((n - 1) * BAR + beat * BEAT, 4)


# ---------------------------------------------------------------- the parts

def piano_theme():
    """Eight notes, 0.4 s in: the shape written in the sheet."""
    notes = [(0.4, 1.2, D4, 44), (1.6, 0.8, A4, 50), (2.4, 1.0, F4, 46),
             (3.4, 1.0, D5, 54), (4.4, 0.8, C5, 50), (5.2, 0.8, 70, 47),
             (6.0, 0.8, A4, 45), (6.8, 1.4, F4, 42)]
    out = [{'t': t, 'd': d, 'p': p, 'v': v} for t, d, p, v in notes]
    # the fragment before the fall, and the one note left afterwards
    out += [{'t': 16.9, 'd': 0.8, 'p': A4, 'v': 58},
            {'t': 18.1, 'd': 1.2, 'p': D5, 'v': 66},
            {'t': 24.0, 'd': 5.8, 'p': D5, 'v': 46}]
    return out


def sub_pedal():
    """One low owner: D2 held in halves, never doubled by another part below 120 Hz."""
    out = []
    t = 0.0
    while t < 29.9:
        d = min(4.05, 30.0 - t)          # 50 ms of overlap: a pedal note is re-struck, never gapped
        out.append({'t': round(t, 3), 'd': round(d, 3), 'p': D2, 'v': 52 if t < 16.6 else 62})
        t = round(t + 4.0, 3)
    out[-1]['d'] = round(30.0 - out[-1]['t'], 3)
    out[-1]['v'] = 40
    return out


def clock_tick():
    """One quiet tick per beat, alternating A5/D6, exactly on the grid: the only thing that keeps time."""
    out = []
    t = 0.0
    i = 0
    while t < 29.85:
        v = 38 if i % 4 == 0 else (32 if i % 2 == 0 else 35)
        out.append({'t': round(t, 3), 'd': 0.2, 'p': A5_TICK if i % 2 == 0 else D6_TICK, 'v': v})
        t = round(t + BEAT, 3)
        i += 1
    return out


def strings_swell():
    """Section swell: D minor, then F, then D over an octave, then the bare fifth after the cut."""
    out = []
    chords = [
        (bar(4), 3.9, (D3, F3, A3, D4), 50),
        (bar(5), 3.9, (D3, F3, A3, D4), 56),
        (bar(6), 3.9, (F3, A3, D4, F4), 68),
        (bar(7), 3.9, (D4, F4, A4, D5), 86),
        (bar(8), 6.0, (D3, A3, D4), 38),
    ]
    for t, d, pitches, v in chords:
        for k, p in enumerate(pitches):
            out.append({'t': round(t + 0.006 * k, 3), 'd': d, 'p': p, 'v': v - 2 * k})
    return out


def harp_glint():
    """Two bars of rising arches answering the theme, then rest."""
    out = []
    bars = [
        [(D4, 40), (E4, 42), (F4, 44), (G4, 46), (A4, 48), (D5, 52), (A4, 46), (G4, 44)],
        [(F4, 44), (G4, 46), (A4, 48), (C5, 50), (D5, 54), (C5, 48), (A4, 44), (G4, 42)],
    ]
    for k, pattern in enumerate(bars):
        for j, (p, v) in enumerate(pattern):
            t = bar(4) + k * BAR + j * 0.5 * BEAT
            out.append({'t': round(t, 3), 'd': round(0.45 * BEAT, 3), 'p': p, 'v': v})
    return out


def timpani_hits():
    """Bar hits under the approach, then the fall and its roll."""
    out = [{'t': bar(4), 'd': 0.9, 'p': D2, 'v': 62},
           {'t': bar(5), 'd': 0.9, 'p': 45, 'v': 66},
           {'t': bar(6), 'd': 0.9, 'p': D2, 'v': 84},
           {'t': bar(6, 2), 'd': 0.9, 'p': F2, 'v': 88},
           {'t': bar(7), 'd': 1.2, 'p': D2, 'v': 104},
           {'t': bar(7, 2), 'd': 0.9, 'p': 36, 'v': 92}]
    for k in range(8):                      # a short roll into the cut, exponential arch + alternating accents
        frac = (k + 1) / 8.0
        out.append({'t': round(bar(7, 2.5) + k * 0.13, 3), 'd': 0.16, 'p': D2,
                    'v': round(58 + 42 * frac ** 1.6 + (3 if k % 2 == 0 else -3))})
    return out


def brass_low():
    """Low stabs on the bar: a power chord, never a triad in the mud."""
    return [{'t': bar(6), 'd': 0.9, 'p': D2, 'v': 84},
            {'t': bar(6), 'd': 0.9, 'p': 45, 'v': 80},
            {'t': bar(6), 'd': 0.9, 'p': D3, 'v': 78},
            {'t': bar(6, 2), 'd': 0.9, 'p': F2, 'v': 88},
            {'t': bar(6, 2), 'd': 0.9, 'p': C3, 'v': 84},
            {'t': bar(7), 'd': 1.3, 'p': D2, 'v': 104},
            {'t': bar(7), 'd': 1.3, 'p': 45, 'v': 100},
            {'t': bar(7), 'd': 1.3, 'p': D3, 'v': 98},
            {'t': bar(7), 'd': 1.3, 'p': D4, 'v': 96},
            {'t': bar(7, 2), 'd': 0.8, 'p': C3, 'v': 90},
            {'t': bar(7, 2), 'd': 0.8, 'p': G3, 'v': 86},
            {'t': bar(7, 3), 'd': 0.9, 'p': D3, 'v': 92},
            {'t': bar(7, 3), 'd': 0.9, 'p': A3, 'v': 88}]


def choir_glow():
    """Above the listener, entering with the collapse, one long line after the cut."""
    out = []
    for k, p in enumerate((D4, F4, A4)):
        out.append({'t': round(bar(6) + 0.02 * k, 3), 'd': 6.4, 'p': p, 'v': 52 - 3 * k})
    out.append({'t': bar(8), 'd': 5.6, 'p': D5, 'v': 34})
    return out


def whoosh_and_impact():
    """Proc effects: the wormhole crossing (3 passes) and the fall itself."""
    whoosh = [{'t': 8.7, 'd': 2.6, 'p': 60, 'v': 58},
              {'t': 12.8, 'd': 2.6, 'p': 60, 'v': 78},
              {'t': 18.1, 'd': 2.6, 'p': 60, 'v': 98},
              {'t': 24.2, 'd': 2.6, 'p': 60, 'v': 46}]
    impact = [{'t': 20.0, 'd': 4.8, 'p': 60, 'v': 100}]
    return whoosh, impact


# ---------------------------------------------------------------- score

def score():
    whoosh, impact = whoosh_and_impact()
    score = {
        'title': 'Chrono Drift',
        'bpm': BPM,
        'ts': [4, 4],
        'key': 'D',
        'mode': 'minor',
        'space': 'chrono_drift_room',
        'mix_preset': 'chrono_drift_mix',
        'piece_type': 'cinematic',
        'focus': 'melody',
        'intent': {
            'emotions': ['wonder', 'mysterious'],
            'registers': ['cinematic'],
            'scenes': ['build'],
            'tensions': ['pedal', 'rising_line'],
            'avoid': ['four_on_floor'],
            'must_hear': ['the pedal from the first second', 'the clock stop at 16.7 s',
                          'the impact at 20 s', 'the last piano D alone'],
        },
        'mix_intent': {
            'hero': 'piano_theme',
            'support': ['strings_swell', 'brass_low', 'harp_glint'],
            'sits_under': ['sub_pedal', 'clock_tick', 'choir_glow', 'timpani_hits',
                           'sfx_whoosh', 'sfx_impact', 'deep_field'],
            'leave_free_hz': [],
        },
        'master': {'lufs': -16.0, 'true_peak': -1.5, 'tone': 'warm'},
        'output_targets': ['stereo', 'immersive_7_1'],
        'dynamics': [[0.0, 0.25], [10.0, 0.42], [16.667, 0.72], [20.0, 1.0],
                     [23.333, 0.32], [28.0, 0.18], [30.0, 0.0]],
        'plan': {'sections': [
            {'name': 'Drift', 'start_bar': 1, 'end_bar': 3, 'start_s': 0.0, 'end_s': 10.0,
             'energy': 0.18, 'dyn': 0.25},
            {'name': 'Approach', 'start_bar': 4, 'end_bar': 5, 'start_s': 10.0, 'end_s': 16.667,
             'energy': 0.45, 'dyn': 0.5},
            {'name': 'Collapse', 'start_bar': 6, 'end_bar': 7, 'start_s': 16.667, 'end_s': 23.333,
             'energy': 0.95, 'dyn': 1.0},
            {'name': 'Afterglow', 'start_bar': 8, 'end_bar': 9, 'start_s': 23.333, 'end_s': 30.0,
             'energy': 0.2, 'dyn': 0.2},
        ]},
        'coupling': {'mode': 'phase', 'gain': 0.5, 'anchor': 'auto', 'window_beats': 2.0,
                     'cap_ms': 20.0},
        'tracks': [
            {'name': 'sub_pedal', 'instrument': 'sub_pedal', 'role': 'drone', 'notes': sub_pedal()},
            {'name': 'piano_theme', 'instrument': 'piano_theme', 'role': 'melody', 'notes': piano_theme()},
            {'name': 'clock_tick', 'instrument': 'clock_tick', 'role': 'arp', 'notes': clock_tick()},
            {'name': 'strings_swell', 'instrument': 'strings_swell', 'role': 'pad', 'notes': strings_swell()},
            {'name': 'harp_glint', 'instrument': 'harp_glint', 'role': 'counter', 'notes': harp_glint()},
            {'name': 'timpani_hits', 'instrument': 'timpani_hits', 'role': 'drum', 'notes': timpani_hits()},
            {'name': 'brass_low', 'instrument': 'brass_low', 'role': 'chord', 'notes': brass_low()},
            {'name': 'choir_glow', 'instrument': 'choir_glow', 'role': 'texture', 'notes': choir_glow()},
            {'name': 'sfx_whoosh', 'instrument': 'sfx:whoosh_warp', 'role': 'fx', 'notes': whoosh},
            {'name': 'sfx_impact', 'instrument': 'sfx:impact_collapse', 'role': 'fx', 'notes': impact,
             'dc_hp_hz': 20},
            {'name': 'deep_field', 'instrument': 'env:deep_space', 'role': 'environment', 'notes': []},
        ],
    }
    # The score speaks in beats: 72 BPM means one second is 1.2 beats. The parts above are written in
    # seconds because the direction sheet and the hits are timed in seconds, so convert once, here.
    for tr in score['tracks']:
        for n in tr['notes']:
            n['t'] = round(float(n['t']) / BEAT, 4)
            n['d'] = round(float(n['d']) / BEAT, 4)
    return score


# ---------------------------------------------------------------- scaffolded presets

MIX_EXTRA = {
    'character': ("A dark, wide space cue on one cold hall: a low pedal and a mechanical clock hold the floor, "
                  "the piano carries the theme close, the strings and choir sit above and behind, and the one "
                  "impact at 20 s is allowed to keep its transient."),
    'mastering': {
        'profile': 'cue',
        'profiles': {'cue': {'lufs': -16.0, 'true_peak': -1.5, 'tone': 'warm', 'glue': True}},
        'highpass_hz': 45.0,
        'highpass_order': 3,
    },
    'lead_carve': {'enabled': True, 'from_intent': True},
    'immersive': {
        'enabled': True,
        'engine': 'hoa_bus',
        'order': 3,
        'anchor_max_span_deg': 6.0,
        'max_deg_per_sec': {'anchor': 10.0, 'mover': 120.0},
        'height_by_role': {
            'melody': 6.0, 'lead': 6.0, 'vocal': 6.0, 'pad': 22.0, 'texture': 38.0,
            'environment': 40.0, 'chord': 12.0, 'bass': 0.0, 'drum': 0.0, 'percussion': 0.0,
            'drone': 0.0, 'ostinato': 0.0, 'arp': 18.0, 'counter': 16.0, 'fx': 10.0,
        },
        'max_elevation': 60.0,
        'min_height_tracks': 3,
        'stereo_decode': 'speakers',
    },
}

SPACE_EXTRA = {
    'character': ("A cold, very large hall with a hard floor and a high ceiling: long but controlled, so the "
                  "pedal fills it, the clock stays dry and close, and the last piano note is heard leaving."),
    'room': {'rt60': 2.2, 'pre_delay_ms': 18, 'hf_decay': 0.55, 'early_level': 0.45},
    'reflections': {
        'ground_delay_ms': 7.0, 'ground_gain': 0.5, 'ground_cutoff_hz': 4200,
        'lateral_delay_ms': 15.0, 'lateral_gain': 0.5, 'lateral_cutoff_hz': 3400,
        'ceiling_delay_ms': 16.0, 'ceiling_gain': 0.46,
        'rear_delay_ms': 26.0, 'rear_gain': 0.42,
        'reverb_decay_s': 2.1,
        'late': {'count': 8, 'rt60_s': 2.2, 'hf_decay': 0.55, 'level_db': -14.0, 'rise_s': 0.02},
    },
    'distance': {'ref_m': 1.5, 'falloff': 0.18, 'air_damping': 0.42, 'min_cutoff_hz': 3000,
                 'reverb_exponent': 0.65,
                 'pre_delay_law': {'base_ms': 32.0, 'per_m': 3.5, 'max_ms': 30.0}},
}


def patch_json(path, extra):
    cfg = json.loads(path.read_text(encoding='utf-8'))
    for k, v in extra.items():
        if k in ('room', 'reflections', 'distance', 'mastering', 'immersive'):
            cfg[k] = v
        else:
            cfg[k] = v
    path.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')


# ---------------------------------------------------------------- research note

WHOOSH = """- URL: https://www.dafx.de/paper-archive/2017/papers/DAFx17_paper_53.pdf
- URL: https://www.windytan.com/2025/04/passing-planes-and-other-whoosh-sounds.html
Licence: analysed only; no recording kept, the effect is synthesised by the shipped `whoosh` recipe
Measured: No measurement found: ESTIMATE a band-passed noise sweep from about 400 Hz to 3.2 kHz, 2 s, with the
  spectral centroid rising then falling; the DAFx paper describes whooshes as modulated band-pass noise and the
  windytan analysis shows a real pass-by as a moving comb + downward Doppler sweep. The recipe is a starting value,
  not a copy of either recording.
"""

IMPACT = """- URL: https://www.ableton.com/en/blog/learn-how-to-make-high-impact-sounds-for-movies-and-trailers
- URL: https://sonusgearflow.com/sounddesign/creating-organic-impacts-with-physical-modeling
Licence: analysed only; no recording kept, the effect is synthesised by the shipped `impact` recipe
Measured: No measurement found: ESTIMATE a 48 Hz sine drop with a short low-passed noise crack. Ableton describes
  trailer impacts as layered low-frequency sounds (a sub layer under a cut-down kick/metal layer), and the physical
  modelling guide gives a 45-70 Hz sine thump with a 60-120 ms pitch drop and a 120-200 ms decay as a starting
  point. Both are starting values; the preset keeps the recipe's own 2 s envelope.
"""

DEEP_SPACE = """- URL: https://science.nasa.gov/science-research/planetary-science/01nov_ismsounds
- URL: https://space-audio.org/
Licence: analysed only; no audio is downloaded or kept, the bed is synthesised from noise primitives
Measured: No measurement found: ESTIMATE three noise layers (30-120 Hz brown hull, 200-2500 Hz pink solar wind,
  2-6 kHz air at -38 dB). NASA's Voyager plasma-wave page puts the heliospheric tones around 300 Hz and the
  interstellar medium at 2-3 kHz; the University of Iowa Space Audio page explains that these are plasma waves
  played through a loudspeaker, not pressure sound. The bed borrows that band split, not the recordings.
"""

DECISIONS = """- D minor at 72 BPM: four bars of 4/4 are 3.33 s, so the nine-bar cue is exactly 30.0 s and every
  section, hit and trajectory key lands on a bar line.
- The theme is eight chord tones (D4 A4 F4 D5 C5 A4 G4 E4): a fifth, a third and a sixth leap, then steps down to
  the second, so it never cadences home and can be left on one note after the cut.
- The clock is a celesta on every two beats from 0 to 16.6 s and then it stops; the stop is the drop into the fall,
  not a fade.
- The fall is one impact at 20.0 s (bar 7), the only low-frequency event besides the pedal, so the sub has one owner.
- The ambience is three project noise layers rather than a shipped environment; it has no events, so it cannot
  compete with the clock or the theme.
- The whoosh is the only moving part (trajectory: rear left 12 m at bar 1, centre 1.5 m at the impact, rear right
  12 m at bar 9); the pedal, drums and bass stay anchored on the floor.
"""


def fill_research():
    notes = [n for n in sorted(REPORTS.glob('research_*.md')) if n.name != 'research_brief.md']
    if not notes:
        raise SystemExit('no research note: run research_kb.py first')
    path = max(notes, key=lambda p: p.stat().st_size)
    text = path.read_text(encoding='utf-8')

    def replace_section(text, title, body):
        head = re.search(r'^## ' + re.escape(title) + r'\s*$', text, re.M)
        if not head:
            return text
        nxt = re.search(r'^## ', text[head.end():], re.M)
        end = head.end() + (nxt.start() if nxt else len(text) - head.end())
        return text[:head.end()] + '\n' + body + '\n' + text[end:]

    text = replace_section(text, 'Real-world references: whoosh', WHOOSH)
    text = replace_section(text, 'Real-world references: impact', IMPACT)
    text = replace_section(text, 'Decisions taken from this research', DECISIONS)
    if 'Real-world references: deep_space' not in text:
        marker = '## Web research'
        text = text.replace(marker, '## Real-world references: deep_space\n\n' + DEEP_SPACE + '\n' + marker, 1)
    web = ('## Web research\n\n'
           '- https://www.dafx.de/paper-archive/2017/papers/DAFx17_paper_53.pdf - whoosh = modulated band-pass noise; '
           'spectral centroid movement is the cue.\n'
           '- https://www.ableton.com/en/blog/learn-how-to-make-high-impact-sounds-for-movies-and-trailers - trailer '
           'impacts are layered, with a sub layer under a cut-down transient.\n'
           '- https://science.nasa.gov/science-research/planetary-science/01nov_ismsounds - Voyager plasma tones: '
           'about 300 Hz in the heliosphere, 2-3 kHz in interstellar space.\n'
           '- https://space-audio.org/ - space "sound" is electromagnetic plasma waves played at audio rates.\n')
    text = replace_section(text, 'Web research', web)
    text = re.sub(r'(## Web research\n+)(## Web research\n+)+', r'\1', text)
    path.write_text(text, encoding='utf-8')
    brief = REPORTS / 'research_brief.md'
    brief.write_text(
        '# Research: Chrono Drift\n\nThe full note is `' + path.name + '`. It cites the knowledge-base ids\n'
        '`cinematic-hybrid-scoring` and `soundfont-velocity-and-realism`, and these web sources:\n\n'
        '- https://www.dafx.de/paper-archive/2017/papers/DAFx17_paper_53.pdf\n'
        '- https://www.ableton.com/en/blog/learn-how-to-make-high-impact-sounds-for-movies-and-trailers\n'
        '- https://science.nasa.gov/science-research/planetary-science/01nov_ismsounds\n'
        '- https://space-audio.org/\n\n'
        'Decisions taken: 72 BPM in D minor, 9 bars = 30.0 s; a clock that stops at 16.667 s; one impact at\n'
        '20.0 s; a three-layer noise ambience; the whoosh is the only moving part.\n', encoding='utf-8')
    return path


def main():
    patch_json(PROJECT / 'presets/mix/chrono_drift_mix.json', MIX_EXTRA)
    patch_json(PROJECT / 'presets/spaces/chrono_drift_room.json', SPACE_EXTRA)
    out = PROJECT / 'scores/chrono_drift_score.json'
    out.write_text(json.dumps(score(), indent=1) + '\n', encoding='utf-8')
    note = fill_research()
    print('wrote', out)
    print('research note', note)
    print('tracks', len(score()['tracks']), 'bars', 9, 'seconds', 30.0)


if __name__ == '__main__':
    main()
