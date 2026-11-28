#!/usr/bin/env python3
"""media_profile.py - what a game score and a film scene score should and should not be, as parameters.

`references/data/media/game_score.json` and `film_scene_score.json` hold, per state (game) or scene type (film), the energy,
density, instrument families to prefer and avoid (the families of `references/data/presets/families/families.json`), the
mixing figures (duck depth, speech-band carve, loudness range) and the do and do-not lists, each with its source. The
reasoning and the sources are in `knowledgebase/media/game-score-dos-and-donts.md` and `film-scene-score-dos-and-donts.md`.
Every figure without a published source says "starting value" in its `provenance`.

    python scripts/media_profile.py list
    python scripts/media_profile.py show game combat            # a state's parameters and the mixing block
    python scripts/media_profile.py show film dialogue_underscore
    python scripts/media_profile.py rules game                   # the do and do-not lists
    python scripts/media_profile.py check                        # validate both files

`setup_project.py --new-project <dir> --media game|film` seeds the sheet's registers from the profile, so the master is
levelled to the platform (`intent.register_loudness`). The profile does not write notes or presets: an agent reads it to choose
instruments, layers and mixing techniques, and states the choice in the direction sheet.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), 'references', 'data', 'media')
KINDS = {'game': 'game_score', 'film': 'film_scene_score'}
GROUP = {'game': 'states', 'film': 'scenes'}


def load(kind):
    name = KINDS.get(kind, kind)
    if name not in KINDS.values():
        raise KeyError(f'unknown media kind {kind!r}; known: {", ".join(KINDS)}')
    with open(os.path.join(DATA, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def group_name(kind):
    return GROUP[kind if kind in GROUP else {v: k for k, v in KINDS.items()}[kind]]


def state(kind, name):
    """One game state or film scene type with the mixing block and the registers beside it."""
    doc = load(kind)
    table = doc[group_name(kind)]
    if name not in table:
        raise KeyError(f'{kind} has no {name!r}; known: {", ".join(table)}')
    return dict(table[name], name=name, mixing=doc['mixing'], registers=doc['registers'])


def default_register(kind, variant=None):
    """The register id whose loudness band the master follows: `console`/`mobile`/`vr` for a game, `underscore` for a film cue."""
    doc = load(kind)
    regs = doc['registers']
    return regs.get(variant) if variant in regs else next(iter(regs.values()))


def problems():
    out = []
    import intent
    fam = json.load(open(os.path.join(os.path.dirname(HERE), 'references', 'data', 'presets', 'families', 'families.json'),
                         encoding='utf-8'))['families']
    reg = intent.vocabulary()['registers']
    for kind in KINDS:
        doc = load(kind)
        for sec in ('registers', 'structure', group_name(kind), 'mixing', 'dos', 'donts', 'provenance', 'knowledge'):
            if sec not in doc:
                out.append(f'{kind}: missing "{sec}"')
        prov = doc.get('provenance') or {}
        for sec in ('structure', group_name(kind), 'mixing', 'registers'):
            if sec not in prov and not any(k.startswith(sec + '.') for k in prov):
                out.append(f'{kind}.{sec}: no provenance (a source, or the words "starting value")')
        for k, v in prov.items():
            if not str(v).strip():
                out.append(f'{kind}.provenance.{k}: empty')
        for r in (doc.get('registers') or {}).values():
            if r not in reg:
                out.append(f'{kind}: register {r!r} is not in registers.json')
        for name, st in (doc.get(group_name(kind)) or {}).items():
            for key in ('families_prefer', 'families_avoid'):
                for f in st.get(key, []):
                    if f not in fam:
                        out.append(f'{kind}.{name}.{key}: unknown family {f!r}; known: {", ".join(fam)}')
            if set(st.get('families_prefer', [])) & set(st.get('families_avoid', [])):
                out.append(f'{kind}.{name}: a family is both preferred and avoided')
            if not 0.0 <= float(st.get('energy', -1)) <= 1.0:
                out.append(f'{kind}.{name}: energy must be 0..1')
        ids = [r['id'] for r in doc.get('dos', []) + doc.get('donts', [])]
        if len(ids) != len(set(ids)):
            out.append(f'{kind}: a do or do-not id is used twice')
        for r in doc.get('dos', []) + doc.get('donts', []):
            if not r.get('source') or not r.get('text'):
                out.append(f'{kind}.{r.get("id")}: a rule needs text and a source')
        kb = os.path.join(os.path.dirname(HERE), doc.get('knowledge', ''))
        if not os.path.isfile(kb):
            out.append(f'{kind}: knowledge file {doc.get("knowledge")} does not exist')
    return out


def _print(d, indent=0):
    for k, v in d.items():
        if isinstance(v, dict):
            print(' ' * indent + f'{k}:')
            _print(v, indent + 2)
        else:
            print(' ' * indent + f'{k}: {v}')


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'list'
    if cmd == 'list':
        for kind in KINDS:
            doc = load(kind)
            print(f'{kind}: {doc["title"]}\n  {group_name(kind)}: {", ".join(doc[group_name(kind)])}')
    elif cmd == 'show' and len(argv) >= 3:
        if len(argv) == 3:
            _print({k: v for k, v in load(argv[2]).items() if k not in ('dos', 'donts', 'provenance')})
        else:
            _print(state(argv[2], argv[3]))
    elif cmd == 'rules' and len(argv) >= 3:
        doc = load(argv[2])
        for label in ('dos', 'donts'):
            print(label.upper().replace('DONTS', 'DO NOT'))
            for r in doc[label]:
                print(f' - [{r["id"]}] {r["text"]}')
    elif cmd == 'check':
        bad = problems()
        print('\n'.join(bad) if bad else 'media profiles are valid')
        return 1 if bad else 0
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
