#!/usr/bin/env python
"""The vocabulary a brief is written in, and the checks that keep it honest.

A score may declare what the piece IS instead of only what it plays:

    "intent": {"scenes": ["farewell"], "emotions": ["grief"], "registers": ["cinematic"],
               "tensions": ["unresolved_dominant"], "avoid": ["four_on_floor", "drum_kit"],
               "must_hear": ["the cello above the room"], "words": ["eerie"]}

Every entry resolves to one concept in `references/data/presets/intent/` (emotions, registers, scenes,
tensions) through `synonyms.json`. A word that does not resolve is an error naming the closest words that do,
because a small model writing a score must never invent a mood name the engine has no meaning for.

The gate's `intent.vocabulary` row calls `normalise_block`; the `intent.avoid` row calls `gesture_hits`, which
measures the gestures the score said it would avoid. A gesture with no score-side measurement is reported as
unmeasured, never as passed.

CLI:  python scripts/intent.py check | list | explain <word> | resolve "<free text>"
"""

import difflib
import json
import os
import sys

import compose
import presets
import roles

KINDS = ('emotions', 'registers', 'scenes', 'tensions', 'synonyms')

# The gestures a score can be asked to avoid. Only the ones with `measure` below can be checked against a score;
# the rest are declared here so the vocabulary is complete and the gate can report them as unmeasured.
GESTURES = {
    'drum_kit': 'a drum-kit groove (snare, hats or ride, 8 hits or more)',
    'four_on_floor': 'a kick on every beat for four bars or more',
    'bright_staccato': 'more than 40 % of the pitched notes as short, hard attacks',
    'major_cadence': 'a major-mode piece that ends on its own tonic',
    'sudden_loud': 'one note jumping more than 0.4 of the velocity scale within a beat',
    'thin_texture_throughout': 'never more than one track sounding at once',
    'min_silence_long': 'a silence of four bars or more somewhere in the piece',
    'steady_pulse': 'one pitch repeated at even spacing eight times or more',
    'tritone_pedal': 'an augmented fourth held against a sounding note',
    'cut_synced_hits': 'a hit placed on a picture cut',
    'rubato_on_the_cell': 'a repeating cell whose spacing drifts by more than 5 %',
    'wide_open_voicing': 'a chord spanning more than two octaves',
    'descending_resolution': 'the last interval of the focus line falling',
    'bed_through_the_gap': 'a bed sounding across a declared silence',
    'compressed_crest': 'less than 8 dB of crest on the master',
    'speech_band_energy': 'music energy inside 250-3800 Hz while speech is present',
    'cinematic_tail': 'a reverb tail longer than the register allows',
    'grid_locked_to_nothing': 'a fixed grid with no musical or picture reason',
    'wide_range': 'one track spanning more than two octaves',
    'pedal_drone_throughout': 'a single held pitch sounding under more than 80 % of the piece',
}

QA_KEYS = ('max_onsets_per_s', 'min_onsets_per_s', 'min_long_note_frac', 'crest_floor_db',
           'min_layers_at_peak', 'min_range_frac', 'max_range_frac', 'min_dissonance_frac',
           'min_repeat_frac', 'min_silences', 'ends_on')


class IntentError(ValueError):
    pass


CONCEPT_KINDS = ('emotions', 'registers', 'scenes', 'tensions')


def vocabulary():
    """{kind: {id: entry}} for the four concept kinds, merged across the preset layers.

    presets.load('intent') is keyed by the file's `name`, which is the kind; the concepts sit one level down
    under a key of the same name. One read for all five files, then pick each kind out.
    """
    loaded = presets.load('intent')
    return {kind: ((loaded.get(kind) or {}).get(kind) or {}) for kind in CONCEPT_KINDS}


def _synonyms():
    cfg = presets.load('intent').get('synonyms') or {}
    return {str(k).lower().strip(): v for k, v in (cfg.get('words') or {}).items()}


def concepts():
    """Every (kind, id) a score may declare, gestures included: a brief can avoid a gesture by name."""
    out = {(kind, cid) for kind, entries in vocabulary().items() for cid in entries}
    out |= {('gestures', g) for g in GESTURES}
    return out


def resolve_word(word):
    """[(kind, id)] for one word, looked up as an id first and then as a synonym. Never guesses."""
    w = str(word).lower().strip().replace(' ', '_').replace('-', '_')
    hits = []
    if w in GESTURES:
        hits.append(('gestures', w))
    for kind, entries in vocabulary().items():
        if w in entries:
            hits.append((kind, w))
    for target in _synonyms().get(w) or []:
        kind, cid = (target + [None, None])[:2]
        if (kind, cid) in concepts() and (kind, cid) not in hits:
            hits.append((kind, cid))
    return hits


def resolve(word):
    """[(kind, id)] or IntentError naming the closest words that do resolve."""
    hits = resolve_word(word)
    if hits:
        return hits
    known = sorted(set(list(_synonyms()) + [cid for _k, cid in concepts()]))
    near = difflib.get_close_matches(str(word).lower().strip(), known, n=5, cutoff=0.6)
    raise IntentError(f'intent word "{word}" resolves to nothing. '
                      + (f'Closest words that do: {", ".join(near)}. ' if near else '')
                      + 'Add it to references/data/presets/intent/synonyms.json pointing at a concept, '
                        'or use one of: ' + ', '.join(sorted(cid for _k, cid in concepts())))


def normalise_block(block):
    """Resolve a score's `intent` block into ids. Raises IntentError on any word it cannot place."""
    if block is None:
        return {}
    if not isinstance(block, dict):
        raise IntentError('intent must be an object (emotions, scenes, registers, tensions, avoid, must_hear)')
    out = {kind: [] for kind in CONCEPT_KINDS}
    out.update({'avoid': [], 'must_hear': [], 'words': list(block.get('words') or [])})
    for kind in ('emotions', 'registers', 'scenes', 'tensions'):
        for w in block.get(kind) or []:
            hits = [h for h in resolve(w) if h[0] == kind]
            if not hits:
                found = resolve(w)
                raise IntentError(f'intent.{kind} "{w}" is not a {kind[:-1]}: it resolves to '
                                  + ', '.join(f'{k}/{i}' for k, i in found))
            out[kind].extend(i for _k, i in hits if i not in out[kind])
    for kind in ('emotions', 'registers', 'scenes', 'tensions'):      # what a concept forbids is part of the promise
        for cid in out[kind]:
            for g in (vocabulary()[kind].get(cid) or {}).get('forbidden') or []:
                if g in GESTURES and g not in out['avoid']:
                    out['avoid'].append(g)
    for w in block.get('avoid') or []:
        hits = resolve(w)
        for kind, cid in hits:
            if kind == 'gestures':
                if cid not in out['avoid']:
                    out['avoid'].append(cid)
                continue
            for g in (vocabulary()[kind].get(cid) or {}).get('forbidden') or []:
                if g in GESTURES and g not in out['avoid']:
                    out['avoid'].append(g)
    for w in block.get('words') or []:
        resolve(w)          # a word kept for the record must still resolve
    out['must_hear'] = [str(m) for m in block.get('must_hear') or []]
    return out


# --------------------------------------------------------------------------------------------- measurements
# Each returns (hit: bool, detail: str). They read the score only: no audio, so they cannot be fooled by a
# render and they cannot claim anything about timbre.

def _pitched(score):
    for t in score.get('tracks') or []:
        if roles.canonical(t.get('role') or '') in ('drum', 'sfx', 'environment'):
            continue
        for n in t.get('notes') or []:
            yield t, n


def _tracks(score, role):
    return [t for t in score.get('tracks') or []
            if roles.canonical(t.get('role') or '') == role and t.get('notes')]


def _span(score):
    bpm = float(score.get('bpm') or 120.0)
    end = 0.0
    for t in score.get('tracks') or []:
        for n in t.get('notes') or []:
            end = max(end, float(n.get('t', 0.0)) + float(n.get('d', 0.0) or 0.0))
    return bpm, end


KIT_PIECES = {'snare', 'hat', 'hihat', 'hat_closed', 'hat_open', 'closed_hat', 'open_hat', 'ride', 'clap', 'rim',
              'rimshot'}


def m_drum_kit(score):
    """A kit GROOVE, not any percussion. A timpani hit or a single boom is not a groove, and a grief cue is
    allowed one; a snare and hats playing a backbeat is what the avoidance words actually mean."""
    for t in _tracks(score, 'drum'):
        kit = [n for n in t['notes'] if str(n.get('p', '')) in KIT_PIECES]
        if len(kit) >= 8:
            return True, f'{t.get("name")} plays {len(kit)} kit hits ({t.get("instrument")})'
    return False, 'no drum-kit groove (percussion only)'


KICK_PITCHES = {'kick', 'kick2', 'kick_hard', 'sub_kick', '36', '35'}


def m_four_on_floor(score):
    """A KICK on every beat. Counting every percussion onset called a backbeat (kick on 1 and 3, snare on
    2 and 4) a four-on-the-floor, which is the one groove the gesture is meant to exclude."""
    bpm, _end = _span(score)
    for t in _tracks(score, 'drum'):
        beats = sorted(float(n.get('t', 0.0)) for n in t['notes'] if str(n.get('p', '')).lower() in KICK_PITCHES)
        run, best = 0, 0
        for a, b in zip(beats, beats[1:]):
            run = run + 1 if abs((b - a) - 1.0) < 0.02 else 0
            best = max(best, run)
        if best >= 15:          # sixteen evenly spaced hits is four bars of four
            return True, f'{t.get("name")} on every beat for {best + 1} beats'
    return False, 'no kick on every beat'


def m_bright_staccato(score):
    short = total = 0
    for _t, n in _pitched(score):
        total += 1
        if float(n.get('d', 1.0)) <= 0.25:
            short += 1
    frac = short / total if total else 0.0
    return frac > 0.40, f'{frac * 100:.0f} % of {total} pitched notes shorter than a 16th'


_PC = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


def m_major_cadence(score):
    """A cadence is a major-mode piece whose low line comes to rest on its own tonic. Major mode alone is not a
    cadence: a piece can sit in the relative major and never close on it."""
    key = str(score.get('key') or '').strip()
    mode = str(score.get('mode') or (key.split()[-1] if ' ' in key else '')).lower()
    if 'major' not in mode:
        return False, f'mode is {mode or "unset"}'
    tonic = _PC.get(key[:1].upper())
    if tonic is None:
        return True, f'major mode and the key "{key}" cannot be read, so it is treated as a cadence'
    low = [t for t in score.get('tracks') or []
           if roles.canonical(t.get('role') or '') in ('bass', 'drone') and t.get('notes')]
    notes = (low[0]['notes'] if low else [n for _t, n in _pitched(score)])
    if not notes:
        return False, 'no notes to cadence on'
    last = sorted(notes, key=lambda n: float(n.get('t', 0.0)))[-1]
    pitch = float(last.get('p', last.get('pitch', 60)))
    return int(pitch) % 12 == tonic, f'major mode, low line ends on pc {int(pitch) % 12} (tonic {tonic})'


def m_thin_texture(score):
    bpm, end = _span(score)
    if end <= 0:
        return True, 'no notes'
    steps = int(end) + 1
    best = 0
    for b in range(steps):
        live = sum(1 for t in score.get('tracks') or []
                   if any(float(n.get('t', 0.0)) <= b < float(n.get('t', 0.0)) + max(0.1, float(n.get('d', 0.5) or 0.5))
                          for n in t.get('notes') or []))
        best = max(best, live)
    return best <= 1, f'at most {best} track(s) sound at once'


def m_min_silence_long(score):
    bpm, end = _span(score)
    events = sorted((float(n.get('t', 0.0)), float(n.get('t', 0.0)) + float(n.get('d', 0.0) or 0.0))
                    for _t, n in _pitched(score) if roles.canonical(_t.get('role') or '') != 'sfx')
    if not events:
        return True, 'the piece is silent'
    reach = events[0][1]
    gap = 0.0
    for s, e in events[1:]:
        gap = max(gap, s - reach)
        reach = max(reach, e)
    gap = max(gap, end - reach)
    bars = gap / 4.0
    return bars >= 4.0, f'longest silence {bars:.1f} bars'


def m_sudden_loud(score):
    for t in score.get('tracks') or []:
        prev = None
        for n in sorted(t.get('notes') or [], key=lambda n: float(n.get('t', 0.0))):
            if prev is not None:
                dt = float(n.get('t', 0.0)) - float(prev.get('t', 0.0))
                dv = abs(float(n.get('v', 0.5)) - float(prev.get('v', 0.5)))
                if dt <= 1.0 and dv > 0.40:
                    return True, f'{t.get("name")} jumps {dv:.2f} of velocity in {dt:.2f} beats'
            prev = n
    return False, 'no velocity jump above 0.4 within a beat'


def m_steady_pulse(score):
    groups = {}
    for t, n in _pitched(score):
        groups.setdefault((t.get('name'), round(float(n.get('p', n.get('pitch', 0))))), []).append(
            float(n.get('t', 0.0)))
    for (_name, _p), ts in groups.items():
        ts.sort()
        if len(ts) >= 8 and all(abs((b - a) - (ts[1] - ts[0])) < 1e-3 for a, b in zip(ts, ts[1:])):
            return True, f'{_name} repeats one pitch {len(ts)} times at even spacing'
    return False, 'no single pitch repeated eight times at even spacing'


def m_cut_synced_hits(score):
    hits = ((score.get('video') or {}).get('hits') or [])
    return bool(hits), f'{len(hits)} picture hit(s) in the score'


def m_wide_range(score):
    for t in score.get('tracks') or []:
        ps = [float(n.get('p', n.get('pitch', 60))) for n in t.get('notes') or []
              if roles.canonical(t.get('role') or '') not in ('drum', 'sfx', 'environment')]
        if ps and max(ps) - min(ps) > 24:
            return True, f'{t.get("name")} spans {int(max(ps) - min(ps))} semitones'
    return False, 'no track spans more than two octaves'


def m_pedal_throughout(score):
    bpm, end = _span(score)
    if end <= 0:
        return False, 'no notes'
    for t in score.get('tracks') or []:
        ps = [int(float(n.get('p', n.get('pitch', 60)))) for n in t.get('notes') or []]
        if not ps:
            continue
        pc = max(set(ps), key=ps.count)
        held = sum(float(n.get('d', 0.0) or 0.0) for n in t['notes'] if int(float(n.get('p', 60))) == pc)
        if held / end > 0.8:
            return True, f'{t.get("name")} holds one pitch for {held / end * 100:.0f} % of the piece'
    return False, 'no pitch held under most of the piece'


MEASURE = {
    'wide_range': m_wide_range,
    'pedal_drone_throughout': m_pedal_throughout,
    'drum_kit': m_drum_kit,
    'four_on_floor': m_four_on_floor,
    'bright_staccato': m_bright_staccato,
    'major_cadence': m_major_cadence,
    'thin_texture_throughout': m_thin_texture,
    'min_silence_long': m_min_silence_long,
    'sudden_loud': m_sudden_loud,
    'steady_pulse': m_steady_pulse,
    'cut_synced_hits': m_cut_synced_hits,
}


def gesture_hits(score, avoid):
    """(hits, unmeasured) for the gestures a score said it would avoid."""
    hits, unmeasured = [], []
    for g in avoid:
        fn = MEASURE.get(g)
        if fn is None:
            unmeasured.append(g)
            continue
        try:
            got, detail = fn(score)
        except Exception as exc:                      # a measurement that cannot run is not a pass
            unmeasured.append(f'{g} (measurement failed: {exc})')
            continue
        if got:
            hits.append((g, detail))
    return hits, unmeasured


# --------------------------------------------------------------------------------------------- validation

def problems():
    """Everything wrong with the intent data. Empty list means the vocabulary is honest."""
    out = []
    voc = vocabulary()
    for kind in ('emotions', 'registers', 'scenes', 'tensions'):
        if not voc.get(kind):
            out.append(f'{kind}: no concepts loaded (is references/data/presets/intent/{kind}.json there?)')
    emo_known = set(compose.EMOTIONS)
    for missing in sorted(emo_known - set(voc.get('emotions') or {})):
        out.append(f'emotions.{missing}: compose knows this mood and the intent presets do not, so a brief can '
                   'choose it and the vocabulary cannot describe it')
    for cid, e in (voc.get('emotions') or {}).items():
        if cid not in emo_known:
            out.append(f'emotions.{cid}: not in compose.EMOTIONS, so no numbers exist for it')
        if not e.get('character'):
            out.append(f'emotions.{cid}: no character sentence')
        if not e.get('sources'):
            out.append(f'emotions.{cid}: no sources')
        for g in e.get('forbidden') or []:
            if g not in GESTURES:
                out.append(f'emotions.{cid}: forbidden gesture "{g}" is not in intent.GESTURES')
    for cid, r in (voc.get('registers') or {}).items():
        for band in ('lra_lu', 'crest_db', 'reverb_tail_s'):
            v = r.get(band)
            if not (isinstance(v, list) and len(v) == 2 and float(v[0]) <= float(v[1])):
                out.append(f'registers.{cid}: {band} must be [low, high] with low <= high')
        if not r.get('sources'):
            out.append(f'registers.{cid}: no sources')
    for cid, s in (voc.get('scenes') or {}).items():
        if s.get('focus') not in roles.FOCUS:
            out.append(f'scenes.{cid}: focus "{s.get("focus")}" is not one of {sorted(roles.FOCUS)}')
        if len(s.get('energy_arc') or []) != 3:
            out.append(f'scenes.{cid}: energy_arc must be three points (start, peak, end)')
        if s.get('register') not in (voc.get('registers') or {}):
            out.append(f'scenes.{cid}: register "{s.get("register")}" is not a register')
        for g in s.get('forbidden') or []:
            if g not in GESTURES:
                out.append(f'scenes.{cid}: forbidden gesture "{g}" is not in intent.GESTURES')
    for kind, entries in voc.items():
        for cid, e in entries.items():
            if not e.get('character'):
                out.append(f'{kind}.{cid}: no character sentence')
            for k in (e.get('qa') or {}):
                if k not in QA_KEYS:
                    out.append(f'{kind}.{cid}: qa key "{k}" is not one the report reads ({QA_KEYS})')
    for w, targets in _synonyms().items():
        if not targets:
            out.append(f'synonyms.{w}: points at nothing')
        for t in targets:
            if not isinstance(t, list) or len(t) != 2 or (t[0], t[1]) not in concepts():
                out.append(f'synonyms.{w}: target {t} is not a (kind, id) that exists')
    return out


def main(argv):
    cmd = (argv[1] if len(argv) > 1 else 'check').lower()
    if cmd == 'check':
        bad = problems()
        for p in bad:
            print(f'FAIL {p}')
        if not bad:
            voc = vocabulary()
            print(f'OK {len(voc.get("emotions") or {})} emotions, {len(voc.get("registers") or {})} registers, '
                  f'{len(voc.get("scenes") or {})} scenes, {len(voc.get("tensions") or {})} tensions, '
                  f'{len(_synonyms())} words, {len(GESTURES)} gestures ({len(MEASURE)} measurable from a score)')
        return 1 if bad else 0
    if cmd == 'list':
        for kind in ('emotions', 'registers', 'scenes', 'tensions'):
            print(kind + ':')
            for cid, e in sorted((vocabulary().get(kind) or {}).items()):
                print(f'  {cid:22s} {e.get("character", "")[:90]}')
        return 0
    if cmd == 'explain':
        if len(argv) < 3:
            print('usage: intent.py explain <word>')
            return 2
        for kind, cid in resolve(argv[2]):
            print(f'{argv[2]} -> {kind}/{cid}')
            print(json.dumps((vocabulary()[kind].get(cid) or {}), indent=2, ensure_ascii=False))
        return 0
    if cmd == 'resolve':
        text = ' '.join(argv[2:])
        found = {}
        for word in text.replace(',', ' ').split():
            for kind, cid in resolve_word(word):
                found.setdefault(kind, [])
                if cid not in found[kind]:
                    found[kind].append(cid)
        print(json.dumps(found, indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
