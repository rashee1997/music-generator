"""sfz_catalog.py - which open SFZ libraries exist, which one a score is missing, and how to put another one in its place.

No library is required. A score plays from whatever is installed in its project, and an instrument preset can name
other libraries to try when its own is not installed:

    "sfz": {"library": "sso", "patch": "Strings - Notation/1st Violins Legato",
            "alternatives": [{"library": "vpo", "patch": "Strings/1st Violins Legato"}]}

    python3 scripts/sfz_catalog.py list [--family piano] [--licence cc0] [--project D]
    python3 scripts/sfz_catalog.py info salamander
    python3 scripts/sfz_catalog.py search "double bass"
    python3 scripts/sfz_catalog.py recommend scores/<title>_score.json --project D     # what is missing, and what could fill it
    python3 scripts/sfz_catalog.py install salamander --project D                        # downloads a part with a url, else says where to get it
    python3 scripts/sfz_catalog.py add-alternative presets/instruments/x.json vpo "Strings/Violin Legato"

The catalog is the `sfzlib` preset kind (references/data/presets/sfzlib/*.json; a project's presets/sfzlib/ overrides or adds).
Each entry says its families, licence, credit line and homepage, and `verified`: true only when someone read the page and the
licence. An unverified entry came from a search result; open its page and read the licence before using it. Downloads are
done by sfz_libs.py (https only, from the hosts the entry names, never executed); a part that has only a page is installed
by hand with `sfz_libs.py install-local`.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import presets
import sfz_libs

# a word in a patch or an instrument name -> the family of library that has it
FAMILY_WORDS = (
    ('piano', ('piano', 'grand', 'upright')), ('electric_piano', ('rhodes', 'epiano', 'electric piano', 'wurlitzer')),
    ('strings', ('violin', 'viola', 'cello', 'celli', 'bass solo', 'basses', 'double bass', 'strings', 'pizzicato', 'tremolo')),
    ('brass', ('horn', 'trumpet', 'trombone', 'tuba', 'brass')),
    ('woodwinds', ('flute', 'clarinet', 'oboe', 'bassoon', 'piccolo', 'woodwind')),
    ('choir', ('choir', 'chorus', 'voice', 'vocal')), ('harp', ('harp',)),
    ('drums', ('drum kit', 'snare', 'kick', 'hi-hat', 'hihat', 'toms')),
    ('percussion', ('timpani', 'cymbal', 'conga', 'marimba', 'xylophone', 'glockenspiel', 'chimes', 'percussion', 'bass drum')),
    ('guitar', ('guitar', 'nylon', 'steel')), ('keys', ('celeste', 'harpsichord', 'organ')),
)


def catalog():
    """{name: entry} for every library (engines are not listed)."""
    return {n: e for n, e in sorted(sfz_libs.registry().items()) if e.get('type') == 'library'}


def family_of(text):
    t = str(text).lower()
    for fam, words in FAMILY_WORDS:
        if any(w in t for w in words):
            return fam
    return None


def installed(name, project):
    if not project:
        return False
    try:
        e = sfz_libs.get_entry(name, 'library')
        return sfz_libs.entry_dir(sfz_libs.libs_root(project), name, e).exists()
    except (SystemExit, LookupError, OSError):
        return False


def rows(family=None, licence=None, project=None):
    out = []
    for n, e in catalog().items():
        fam = e.get('families') or []
        if family and family not in fam:
            continue
        if licence and licence.lower() not in str(e.get('licence', '')).lower():
            continue
        out.append(dict(name=n, families=fam, licence=e.get('licence', ''), verified=bool(e.get('verified')), installed=installed(n, project),
                        homepage=e.get('homepage', '')))
    return out


def search(words):
    ws = [w.lower() for w in words]
    out = []
    for n, e in catalog().items():
        blob = ' '.join([n, e.get('character', ''), ' '.join(e.get('families') or []), e.get('licence', ''), e.get('attribution', '')]).lower()
        if all(w in blob for w in ws):
            out.append(n)
    return out


def needs(score, project):
    """[(track, family, status, choices)] for every SFZ track: status 'ok' when one of its libraries has the patch installed."""
    out = []
    for track, blk in sfz_libs.score_blocks(score):
        choices = sfz_libs.block_choices(blk)
        try:
            eff = sfz_libs.effective_block(blk, project)
            status = 'ok'
            used = (eff['library'], eff['patch'])
        except LookupError:
            status, used = 'missing', None
        out.append((track, family_of(blk.get('patch') or '') or family_of(track), status, choices, used))
    return out


def recommend(score, project):
    """For each missing track: the catalog libraries of its family, those already installed first."""
    out = []
    for track, fam, status, choices, used in needs(score, project):
        if status == 'ok':
            continue
        cands = [r for r in rows(family=fam, project=project)] if fam else []
        cands.sort(key=lambda r: (not r['installed'], not r['verified'], r['name']))
        out.append(dict(track=track, family=fam, wanted=choices[0], candidates=cands))
    return out


def add_alternative(preset_path, library, patch):
    """Append {library, patch} to an instrument preset's sfz.alternatives (a copy of the file is rewritten in place)."""
    with open(preset_path, encoding='utf-8') as fh:
        d = json.load(fh)
    blk = d.get('sfz')
    if not isinstance(blk, dict):
        raise SystemExit(f'{preset_path} has no "sfz" block')
    sfz_libs.get_entry(library, 'library')
    alts = blk.setdefault('alternatives', [])
    if {'library': library, 'patch': patch} not in alts:
        alts.append({'library': library, 'patch': patch})
    with open(preset_path, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, indent=2)
        fh.write('\n')
    return alts


def install(name, project, part=None, yes=False):
    """Download what the entry can download; for a part that only has a page, print where to get it and the install-local command.
    Returns sfz_libs.get's code: 0 installed, 2 when a manual step is left."""
    sfz_libs.get_entry(name, 'library')
    return sfz_libs.get(name, project, part=part, yes=yes)


def _fmt(rowd):
    flag = 'verified' if rowd['verified'] else 'unverified'
    inst = ' installed' if rowd['installed'] else ''
    return f'{rowd["name"]:<26}{",".join(rowd["families"]):<42}{flag:<11}{inst}\n    {rowd["licence"]}\n    {rowd["homepage"]}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('list')
    a.add_argument('--family')
    a.add_argument('--licence')
    a.add_argument('--project')
    a = sub.add_parser('info')
    a.add_argument('name')
    a = sub.add_parser('search')
    a.add_argument('words', nargs='+')
    a = sub.add_parser('recommend')
    a.add_argument('score')
    a.add_argument('--project', required=True)
    a = sub.add_parser('install')
    a.add_argument('name')
    a.add_argument('--project', required=True)
    a.add_argument('--part')
    a.add_argument('--yes', action='store_true')
    a = sub.add_parser('add-alternative')
    a.add_argument('preset')
    a.add_argument('library')
    a.add_argument('patch')
    args = ap.parse_args(argv)
    if getattr(args, 'project', None):
        presets.add_project(args.project)
    if args.cmd == 'list':
        for r in rows(args.family, args.licence, args.project):
            print(_fmt(r))
    elif args.cmd == 'info':
        e = sfz_libs.get_entry(args.name, 'library')
        print(json.dumps({k: v for k, v in e.items() if k != '_source'}, indent=2))
    elif args.cmd == 'search':
        print('\n'.join(search(args.words)) or 'no library matches')
    elif args.cmd == 'recommend':
        with open(args.score, encoding='utf-8') as fh:
            score = json.load(fh)
        for t, fam, status, choices, used in needs(score, args.project):
            print(f'  {t:<22}{status:<8}{fam or "?":<14}' + (f'plays {used[1]} from {used[0]}' if used else f'wants {choices[0][1]} ({choices[0][0]})'))
        miss = recommend(score, args.project)
        for m in miss:
            print(f'\n{m["track"]} ({m["family"]}) needs {m["wanted"][1]} from {m["wanted"][0]}. Libraries with that family:')
            for c in m['candidates'][:6]:
                print('  ' + _fmt(c).replace('\n', '\n  '))
                print(f'  install: python3 scripts/sfz_catalog.py install {c["name"]} --project {args.project}')
        if not miss:
            print('\nevery SFZ track has a library installed')
        return 1 if miss else 0
    elif args.cmd == 'install':
        install(args.name, args.project, args.part, args.yes)
    elif args.cmd == 'add-alternative':
        print(json.dumps(add_alternative(args.preset, args.library, args.patch), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
