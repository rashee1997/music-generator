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
"""sfz_libs.py - free multisampled SFZ libraries and the SFZ engine, kept inside a project (never inside the skill).

    python3 scripts/sfz_libs.py list                              # known libraries: size, licence, installed or not
    python3 scripts/sfz_libs.py get sso --part strings,brass --project D     # download + unpack into D/libs/sfz/sso/
    python3 scripts/sfz_libs.py get sso --dry-run                 # sizes, licence, destination; downloads nothing
    python3 scripts/sfz_libs.py engine --project D                # sfizz_render into D/libs/engine/
    python3 scripts/sfz_libs.py install-local vpo wave.zip --part wave --project D   # a zip you downloaded by hand
    python3 scripts/sfz_libs.py check sso --project D             # every sample= in every .sfz exists?
    python3 scripts/sfz_libs.py verify --project D                # files still match the checksums taken at install
    python3 scripts/sfz_libs.py find sso "1st Violins Legato" --project D
    python3 scripts/sfz_libs.py remove sso --project D
    python3 scripts/sfz_libs.py registry                          # validate the library presets (shipped + project)

The library list is a preset kind (references/data/presets/sfzlib/, project presets/sfzlib/ overrides or adds). Nothing is
downloaded unless you run `get` or `engine`. Downloads: https only, from the hosts named in the preset; archives are
unpacked with path-escape and size checks; nothing downloaded is ever executed. The first download of a part records its
checksum in libs/sfz/lock.json (a preset sha256, or --sha256, is checked first); `verify` compares later.
Licences are summarised in libs/sfz/LICENCES.md. Libraries are the authors' work under their licences: keep them in the
project and do not redistribute the sample files unless the licence says you may.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import presets

TEST_LOOPBACK = False             # tests only: allow http://127.0.0.1 so the downloader can be exercised without the network
CONFIRM_ABOVE_MB = 500
MAX_UNPACK_GB = 8.0
LIB_KEYS = {'name', 'character', 'type', 'licence', 'licence_url', 'share_alike', 'attribution', 'homepage', 'source', 'entry',
            'parts', 'default_parts', 'notes', 'trim_db', '_source', 'kind'}
ENGINE_KEYS = {'name', 'character', 'type', 'licence', 'licence_url', 'share_alike', 'attribution', 'homepage', 'platforms', 'notes',
               '_source', 'kind'}
PART_KEYS = {'size_mb', 'what', 'paths', 'url', 'hosts', 'sha256', 'manual', 'manual_note'}


# ---------------------------------------------------------------- registry
def entry_problems(name, e):
    where = f'sfzlib/{name}'
    out = []
    kind = e.get('type')
    if kind not in ('library', 'engine'):
        return [f'{where}: "type" must be "library" or "engine"']
    for k in e:
        if k not in (LIB_KEYS if kind == 'library' else ENGINE_KEYS):
            out.append(f'{where}: unknown key "{k}"')
    for k in ('character', 'licence'):
        if not str(e.get(k, '')).strip():
            out.append(f'{where}: missing "{k}"')
    if not isinstance(e.get('share_alike', False), bool):
        out.append(f'{where}: share_alike must be true or false')
    if kind == 'library':
        if not str(e.get('attribution', '')).strip():
            out.append(f'{where}: missing "attribution" (the credit line a project must carry)')
        if not e.get('entry'):
            out.append(f'{where}: missing "entry" (the folder inside the library that holds the .sfz files)')
        parts = e.get('parts')
        if not isinstance(parts, dict) or not parts:
            return out + [f'{where}: "parts" must list at least one part']
        src = e.get('source') or {}
        for pn, p in parts.items():
            w = f'{where}.parts.{pn}'
            for k in p:
                if k not in PART_KEYS:
                    out.append(f'{w}: unknown key "{k}"')
            how = [k for k in ('paths', 'url', 'manual') if k in p]
            if len(how) != 1:
                out.append(f'{w}: needs exactly one of paths (git), url (zip) or manual')
            if 'url' in p:
                if not _scheme_ok(str(p['url'])):
                    out.append(f'{w}: url must be https')
                if not p.get('hosts'):
                    out.append(f'{w}: url parts need "hosts" (the only hosts the download may start from)')
                elif urllib.parse.urlparse(p['url']).hostname not in p['hosts']:
                    out.append(f'{w}: url host is not in "hosts"')
            if 'manual' in p and not str(p['manual']).startswith('https://'):
                out.append(f'{w}: manual page must be https')
            if 'paths' in p and src.get('kind') != 'git':
                out.append(f'{w}: "paths" parts need source.kind "git"')
            if 'sha256' in p and not re.fullmatch(r'[0-9a-f]{64}', str(p['sha256'])):
                out.append(f'{w}: sha256 must be 64 hex characters')
        if src.get('kind') == 'git':
            if not str(src.get('repo', '')).startswith('https://'):
                out.append(f'{where}: source.repo must be https')
        for d in e.get('default_parts', []):
            if d not in parts:
                out.append(f'{where}: default_parts names unknown part "{d}"')
    else:
        pl = e.get('platforms')
        if not isinstance(pl, dict) or not pl:
            out.append(f'{where}: engine needs "platforms"')
        else:
            for plat, a in pl.items():
                if a.get('url') and not str(a['url']).startswith('https://'):
                    out.append(f'{where}.{plat}: url must be https')
                if a.get('url') and not a.get('hosts'):
                    out.append(f'{where}.{plat}: url needs "hosts"')
    return out


def problems(project_dirs=()):
    for d in project_dirs:
        presets.add_project(d)
    out = []
    for name, e in presets.load('sfzlib').items():
        out += entry_problems(name, e)
    return out


def registry():
    return presets.load('sfzlib')


def get_entry(name, kind=None):
    e = registry().get(presets._norm(name))
    if e is None:
        raise SystemExit(f'no sfzlib preset "{name}". Known: {sorted(registry())}. See: sfz_libs.py list (or write presets/sfzlib/{name}.json in the project)')
    bad = entry_problems(name, e)
    if bad:
        raise SystemExit('\n'.join(bad))
    if kind and e['type'] != kind:
        raise SystemExit(f'"{name}" is a {e["type"]}, not a {kind}')
    return e


# ---------------------------------------------------------------- places
def libs_root(project, dest=None):
    return Path(dest) if dest else Path(project) / 'libs' / 'sfz'


def project_dirs():
    """Projects added to the preset layers (render time): the parent of each presets/ root, latest first."""
    return [Path(r).parent for r in reversed(presets.PROJECT_ROOTS)]


def lock_path(root):
    return Path(root) / 'lock.json'


def read_lock(root):
    p = lock_path(root)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def write_lock(root, lock):
    Path(root).mkdir(parents=True, exist_ok=True)
    lock_path(root).write_text(json.dumps(lock, indent=2, sort_keys=True), encoding='utf-8')


def lib_dir(root, name):
    return Path(root) / presets._norm(name)


def entry_dir(root, name, e):
    return lib_dir(root, name) / e['entry']


# ---------------------------------------------------------------- safe download and unpack
def _scheme_ok(url):
    u = urllib.parse.urlparse(url)
    if u.scheme == 'https':
        return True
    return TEST_LOOPBACK and u.scheme == 'http' and u.hostname in ('127.0.0.1', 'localhost')


class _Https(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _scheme_ok(newurl):
            raise urllib.error.URLError(f'refused a redirect to a non-https address: {newurl}')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, dst, hosts, resume=True, quiet=False):
    """Download to `dst` (resuming a .part file). Returns sha256. The first host must be in `hosts`; every redirect must be https."""
    u = urllib.parse.urlparse(url)
    if not _scheme_ok(url):
        raise SystemExit(f'refused {url}: https only')
    if u.hostname not in hosts and not (TEST_LOOPBACK and u.hostname in ('127.0.0.1', 'localhost')):
        raise SystemExit(f'refused {url}: host {u.hostname} is not in the preset\'s hosts {hosts}')
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_suffix(dst.suffix + '.part')
    have = part.stat().st_size if (resume and part.exists()) else 0
    req = urllib.request.Request(url, headers={'User-Agent': 'music-generator-sfz-libs'})
    if have:
        req.add_header('Range', f'bytes={have}-')
    opener = urllib.request.build_opener(_Https)
    with opener.open(req, timeout=60) as r:
        if have and r.status != 206:
            have = 0                                    # the server ignored Range: start again
        mode = 'ab' if have else 'wb'
        total = r.headers.get('Content-Length')
        total = int(total) + have if total else None
        done, t0, shown = have, time.time(), -1
        with open(part, mode) as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total and not quiet:
                    pct = int(100 * done / total) // 10 * 10
                    if pct != shown:
                        shown = pct
                        print(f'  {dst.name}: {pct}% ({done / 1e6:.0f} of {total / 1e6:.0f} MB, {time.time() - t0:.0f}s)', flush=True)
    if total and part.stat().st_size != total:
        raise SystemExit(f'{dst.name}: got {part.stat().st_size} bytes, expected {total}. Run the same command again to resume')
    os.replace(part, dst)
    return sha256_file(dst)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def safe_extract(zip_path, dest, max_gb=MAX_UNPACK_GB):
    """Unpack a zip into dest. Refuses absolute paths, '..', links, and archives that unpack larger than max_gb."""
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    names = []
    with zipfile.ZipFile(zip_path) as z:
        total = sum(i.file_size for i in z.infolist())
        if total > max_gb * 1e9:
            raise SystemExit(f'{Path(zip_path).name} unpacks to {total / 1e9:.1f} GB, above the {max_gb} GB limit (--max-gb)')
        for i in z.infolist():
            target = (dest / i.filename).resolve()
            mode = (i.external_attr >> 16) & 0o170000
            if i.filename.startswith(('/', '\\')) or '..' in Path(i.filename).parts or not str(target).startswith(str(dest)):
                raise SystemExit(f'refused {Path(zip_path).name}: member "{i.filename}" would leave the library folder')
            if mode == 0o120000:
                raise SystemExit(f'refused {Path(zip_path).name}: member "{i.filename}" is a symbolic link')
        z.extractall(dest)
        names = [i.filename for i in z.infolist() if not i.is_dir()]
    return names


def manifest_of(folder, skip=('.git',)):
    """{relative path: [size, sha256]} for every file under folder."""
    out = {}
    folder = Path(folder)
    for p in sorted(folder.rglob('*')):
        if p.is_file() and not any(s in p.relative_to(folder).parts for s in skip):
            out[p.relative_to(folder).as_posix()] = [p.stat().st_size, sha256_file(p)]
    return out


# ---------------------------------------------------------------- licences
def write_licences(root):
    root = Path(root)
    lock = read_lock(root)
    reg = registry()
    lines = ['# Sample libraries in this project', '',
             'Written by sfz_libs.py. These are other people\'s work under their own licences. Keep them in the project; do not',
             'redistribute the sample files unless the licence says you may. Credit lines below belong in the project credits.', '']
    for name in sorted(lock.get('libs', {})):
        e = reg.get(name, {})
        lines += [f'## {name}', f'- licence: {e.get("licence", "unknown")}' + (' (share-alike parts: keep the same terms on anything derived)' if e.get('share_alike') else ''),
                  f'- licence text: {e.get("licence_url", "")}', f'- credit: {e.get("attribution", "")}',
                  f'- from: {e.get("homepage", "")}', f'- parts installed: {", ".join(sorted(lock["libs"][name].get("parts", {})))}', '']
    (root / 'LICENCES.md').write_text('\n'.join(lines), encoding='utf-8')


# ---------------------------------------------------------------- get
def _choose_parts(e, part, variant):
    names = list(e['parts'])
    if not part:
        chosen = list(e.get('default_parts') or names)
    elif part == 'all':
        chosen = names
    else:
        chosen = [p.strip() for p in part.split(',') if p.strip()]
    if variant:
        pick = [n for n in names if n.endswith('_' + variant)]
        drop = [n for n in names if n.startswith(tuple({x.rsplit('_', 1)[0] + '_' for x in names if '_' in x})) and n not in pick and '_' in n
                and n.rsplit('_', 1)[0] in {x.rsplit('_', 1)[0] for x in pick}]
        chosen = [c for c in chosen if c not in drop]
        for p in pick:
            if p not in chosen:
                chosen.append(p)
    bad = [c for c in chosen if c not in e['parts']]
    if bad:
        raise SystemExit(f'unknown part(s) {bad}. Parts: {names}')
    if e.get('source', {}).get('kind') == 'git' and 'core' in e['parts'] and 'core' not in chosen:
        chosen.insert(0, 'core')
    return chosen


def plan_text(name, e, chosen, root):
    total = sum(float(e['parts'][p].get('size_mb', 0)) for p in chosen)
    lines = [f'{name}: {e["character"]}', f'  licence: {e["licence"]}' + ('   [share-alike parts]' if e.get('share_alike') else ''),
             f'  credit : {e["attribution"]}', f'  to     : {lib_dir(root, name)}']
    for p in chosen:
        pd = e['parts'][p]
        how = 'git (sparse)' if 'paths' in pd else ('zip' if 'url' in pd else 'MANUAL download')
        lines.append(f'  part {p:20s} {pd.get("size_mb", "?"):>7} MB  {how:14s} {pd.get("what", "")}')
    lines.append(f'  total about {total:.0f} MB')
    return '\n'.join(lines), total


def _git(args, cwd=None):
    if not shutil.which('git'):
        raise SystemExit('git is needed for this library (it fetches only the folders you ask for). Install git, or download by hand and use install-local')
    r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f'git {" ".join(args[:3])} failed: {r.stderr.strip()[-400:]}')
    return r.stdout.strip()


def _git_paths(e, chosen):
    root = e['source'].get('root', '')
    out = []
    for p in chosen:
        for path in e['parts'][p].get('paths', []):
            rel = path[1:] if path.startswith('/') else (root + '/' + path if root else path)
            out.append('/' + rel.strip('/') + ('/' if '.' not in Path(rel).name else ''))
    return out


def get(name, project, part=None, variant=None, dry_run=False, yes=False, max_gb=None, keep_archives=False, no_extract=False,
        sha256=None, mirror=None, dest=None, ref=None, force=False, quiet=False):
    e = get_entry(name, 'library')
    root = libs_root(project, dest)
    chosen = _choose_parts(e, part, variant)
    text, total = plan_text(name, e, chosen, root)
    print(text)
    if max_gb is not None and total > max_gb * 1000:
        raise SystemExit(f'refused: about {total / 1000:.1f} GB is above --max-gb {max_gb}')
    if dry_run:
        print('dry run: nothing downloaded')
        return 0
    if total > CONFIRM_ABOVE_MB and not yes:
        if not sys.stdin.isatty():
            raise SystemExit(f'about {total:.0f} MB: add --yes to download without a prompt')
        if input('download? [y/N] ').strip().lower() != 'y':
            raise SystemExit('cancelled')
    lock = read_lock(root)
    rec = lock.setdefault('libs', {}).setdefault(presets._norm(name), {'parts': {}})
    pending = []
    src = e['source']
    ldir = lib_dir(root, name)
    git_parts = [p for p in chosen if 'paths' in e['parts'][p]]
    if git_parts:
        have = [p for p in rec['parts'] if p in e['parts'] and 'paths' in e['parts'][p]]
        every = sorted(set(have) | set(git_parts), key=lambda x: list(e['parts']).index(x))
        paths = _git_paths(e, every)
        if not (ldir / '.git').exists():
            ldir.mkdir(parents=True, exist_ok=True)
            _git(['clone', '--depth', '1', '--filter=blob:none', '--sparse', '--no-checkout'] + (['--branch', ref or src.get('ref', 'master')]) +
                 [src['repo'], str(ldir)])
        elif ref:
            _git(['fetch', '--depth', '1', 'origin', ref], cwd=ldir)
        _git(['sparse-checkout', 'set', '--no-cone'] + paths, cwd=ldir)
        _git(['checkout'] + (['FETCH_HEAD'] if (ref and (ldir / '.git').exists() and rec['parts']) else []), cwd=ldir) if False else _git(['checkout'], cwd=ldir)
        commit = _git(['rev-parse', 'HEAD'], cwd=ldir)
        for p in git_parts:
            rec['parts'][p] = {'kind': 'git', 'commit': commit, 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
        rec['commit'] = commit
        print(f'  git: {len(paths)} path pattern(s) checked out at {commit[:10]}')
    for p in chosen:
        pd = e['parts'][p]
        if 'paths' in pd:
            continue
        if 'manual' in pd:
            if p not in rec['parts']:
                pending.append((p, pd))
            continue
        url = (mirror.rstrip('/') + '/' + url_name(pd['url'])) if mirror else pd['url']
        arc = Path(root) / '.downloads' / f'{presets._norm(name)}-{p}.zip'
        if force and arc.exists():
            arc.unlink()
        if not arc.exists():
            digest = download(url, arc, pd['hosts'] + ([urllib.parse.urlparse(mirror).hostname] if mirror else []), quiet=quiet)
        else:
            digest = sha256_file(arc)
        want = sha256 if (sha256 and len(chosen) == 1) else pd.get('sha256')
        if want and digest != want:
            arc.unlink()
            raise SystemExit(f'{p}: checksum {digest[:16]}... does not match the expected {want[:16]}...; the file was deleted')
        locked = rec['parts'].get(p, {}).get('sha256')
        if locked and locked != digest and not force:
            raise SystemExit(f'{p}: checksum changed since the first download ({locked[:12]} -> {digest[:12]}). The host may have updated the file; use --force to accept it')
        if not no_extract:
            safe_extract(arc, ldir, max_gb or MAX_UNPACK_GB)
        rec['parts'][p] = {'kind': 'zip', 'sha256': digest, 'url': pd['url'], 'bytes': arc.stat().st_size, 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
        if not keep_archives:
            arc.unlink()
    rec['manifest_when'] = time.strftime('%Y-%m-%d %H:%M:%S')
    if ldir.exists() and not no_extract:
        rec['manifest'] = manifest_of(ldir)
    write_lock(root, lock)
    write_licences(root)
    for p, pd in pending:
        print(f'\nMANUAL STEP for part "{p}": {pd.get("manual_note", pd["manual"])}')
    print(f'\ninstalled in {ldir}\nlicence summary: {Path(root) / "LICENCES.md"}')
    return 2 if pending else 0


def url_name(url):
    return Path(urllib.parse.urlparse(url).path).name


def install_local(name, archive, project, part=None, dest=None):
    e = get_entry(name, 'library')
    root = libs_root(project, dest)
    archive = Path(archive)
    if not archive.exists():
        raise SystemExit(f'{archive} does not exist')
    part = part or next((p for p, pd in e['parts'].items() if 'manual' in pd), None)
    if part not in e['parts']:
        raise SystemExit(f'give --part: one of {list(e["parts"])}')
    ldir = lib_dir(root, name)
    safe_extract(archive, ldir)
    lock = read_lock(root)
    rec = lock.setdefault('libs', {}).setdefault(presets._norm(name), {'parts': {}})
    rec['parts'][part] = {'kind': 'local', 'sha256': sha256_file(archive), 'bytes': archive.stat().st_size, 'when': time.strftime('%Y-%m-%d %H:%M:%S')}
    rec['manifest'] = manifest_of(ldir)
    write_lock(root, lock)
    write_licences(root)
    print(f'unpacked {archive.name} into {ldir} as part "{part}"')


# ---------------------------------------------------------------- engine
def engine_name():
    return 'sfizz_render.exe' if os.name == 'nt' else 'sfizz_render'


def find_engine(project=None):
    """Path to sfizz_render: $SFIZZ_RENDER, then <project>/libs/engine/**, then PATH. None when not found."""
    if os.environ.get('SFIZZ_RENDER') and Path(os.environ['SFIZZ_RENDER']).exists():
        return Path(os.environ['SFIZZ_RENDER'])
    for pr in ([Path(project)] if project else []) + project_dirs():
        hits = sorted((pr / 'libs' / 'engine').rglob(engine_name())) if (pr / 'libs' / 'engine').is_dir() else []
        if hits:
            return hits[0]
    w = shutil.which('sfizz_render')
    return Path(w) if w else None


def install_engine(project, dest=None, yes=True, quiet=False):
    e = get_entry('sfizz', 'engine')
    plat = {'win32': 'win32', 'darwin': 'darwin'}.get(sys.platform, 'linux')
    a = e['platforms'][plat]
    if not a.get('url') or not a.get('exe'):
        raise SystemExit(f'no prebuilt sfizz_render for {plat}: {a.get("note", "")}')
    root = Path(dest) if dest else Path(project) / 'libs' / 'engine'
    target = root / 'sfizz'
    arc = root / '.downloads' / url_name(a['url'])
    print(f'sfizz {a["url"]}\n  licence {e["licence"]}; to {target}')
    digest = download(a['url'], arc, a['hosts'], quiet=quiet)
    if a.get('sha256') and digest != a['sha256']:
        arc.unlink()
        raise SystemExit(f'sfizz archive checksum {digest[:16]}... does not match the preset; deleted')
    safe_extract(arc, target)
    arc.unlink()
    exe = target / a['exe']
    if not exe.exists():
        raise SystemExit(f'unpacked, but {a["exe"]} is not in the archive')
    print(f'engine ready: {exe}')
    return exe


# ---------------------------------------------------------------- check / verify / find / remove
_SAMPLE = re.compile(r'(?<![A-Za-z0-9_])sample=(.*?)(?=\s+[A-Za-z_][A-Za-z_0-9$]*=|\s*<|\r?\n|$)')
_INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"', re.M)
_DEFPATH = re.compile(r'default_path=(.*?)(?=\s+[A-Za-z_][A-Za-z_0-9$]*=|\s*<|\r?\n|$)')


def sfz_samples(sfz, _seen=None, _depth=0, _root=None):
    """Absolute sample paths an .sfz uses (following #include; $variables are skipped). Returns (list, includes_missing)."""
    sfz = Path(sfz)
    _seen = _seen if _seen is not None else set()
    if sfz in _seen or _depth > 8 or not sfz.exists():
        return [], ([sfz] if not sfz.exists() else [])
    _seen.add(sfz)
    _root = _root or sfz.parent  # sfizz resolves sample paths from the main .sfz folder, even inside an #include
    text = sfz.read_text(encoding='utf-8', errors='replace')
    text = re.sub(r'//[^\n]*', '', text)
    dp = _DEFPATH.search(text)
    base = _root / (_posix(dp.group(1).strip()) if dp else '')
    samples, missing = [], []
    for m in _SAMPLE.finditer(text):
        s = _posix(m.group(1).strip())
        if s and '$' not in s and not s.startswith('*'):
            samples.append((base / s).resolve() if not Path(s).is_absolute() else Path(s))
    for inc in _INCLUDE.findall(text):
        s2, m2 = sfz_samples(sfz.parent / _posix(inc), _seen, _depth + 1, _root)
        samples += s2
        missing += m2
    return samples, missing


def check(name, project, dest=None, limit=40):
    e = get_entry(name, 'library')
    ed = entry_dir(libs_root(project, dest), name, e)
    if not ed.exists():
        raise SystemExit(f'{name} is not installed in {ed}. Run: sfz_libs.py get {name} --project {project}')
    n_sfz, bad = 0, {}
    for f in sorted(ed.rglob('*.sfz')):
        if 'includes' in f.parts:
            continue
        n_sfz += 1
        s, inc = sfz_samples(f)
        miss = sorted({str(x) for x in s if not x.exists()}) + [f'include {i}' for i in inc]
        if miss:
            bad[f.relative_to(ed).as_posix()] = miss
    return n_sfz, bad


def verify(project, dest=None, names=None):
    root = libs_root(project, dest)
    lock = read_lock(root)
    problems_ = []
    for name, rec in lock.get('libs', {}).items():
        if names and name not in names:
            continue
        man = rec.get('manifest') or {}
        ldir = lib_dir(root, name)
        for rel, (size, digest) in man.items():
            p = ldir / rel
            if not p.exists():
                problems_.append(f'{name}: missing {rel}')
            elif p.stat().st_size != size or sha256_file(p) != digest:
                problems_.append(f'{name}: changed {rel}')
        print(f'{name}: {len(man)} files checked')
    return problems_


def find_patch(name, ref, project=None, dest=None):
    """Resolve 'Strings - Notation/1st Violins Legato' (with or without .sfz) inside an installed library. Raises LookupError with the fix."""
    e = get_entry(name, 'library')
    for pr in ([Path(project)] if project else []) + project_dirs():
        ed = entry_dir(libs_root(pr, dest), name, e)
        if ed.exists():
            break
    else:
        raise LookupError(f'library "{name}" is not installed in this project. Run: sfz_libs.py get {name} --project <project>')
    ref = _posix(ref).strip('/')
    want = ref if ref.lower().endswith('.sfz') else ref + '.sfz'
    direct = ed / want
    if direct.exists():
        return direct
    low = want.lower()
    cands = [p for p in ed.rglob('*.sfz') if p.relative_to(ed).as_posix().lower() == low]
    if cands:
        return cands[0]
    stem = Path(want).name.lower()
    near = [p.relative_to(ed).as_posix() for p in ed.rglob('*.sfz') if stem[:-4] in p.name.lower()][:6]
    raise LookupError(f'no patch "{ref}" in {name}.' + (f' Similar: {near}' if near else ' Run: sfz_libs.py find ' + name + ' <words>'))


def _posix(p):
    """A sample or include path as an .sfz file writes it: forward slashes, whatever the host OS."""
    return str(p).replace('\\', '/')


def search(name, words, project, dest=None, limit=30):
    e = get_entry(name, 'library')
    ed = entry_dir(libs_root(project, dest), name, e)
    ws = [w.lower() for w in words]
    return [p.relative_to(ed).as_posix() for p in sorted(ed.rglob('*.sfz')) if 'includes' not in p.parts
            and all(w in p.relative_to(ed).as_posix().lower() for w in ws)][:limit]


def remove(name, project, dest=None):
    root = libs_root(project, dest).resolve()
    ldir = lib_dir(root, name).resolve()
    if ldir.parent != root or not ldir.exists():
        raise SystemExit(f'nothing to remove at {ldir}')
    if not str(ldir).startswith(str(root)):
        raise SystemExit('refused: path outside libs/sfz')

    def _rw(fn, p, exc):                      # git marks pack files read-only on Windows
        os.chmod(p, 0o700)
        fn(p)
    shutil.rmtree(ldir, onerror=_rw)
    lock = read_lock(root)
    lock.get('libs', {}).pop(presets._norm(name), None)
    write_lock(root, lock)
    write_licences(root)
    print(f'removed {ldir}')


# ---------------------------------------------------------------- score references
def score_refs(score):
    """[(track name, library, patch ref)] for tracks that play an SFZ library: instrument 'sfz:lib/patch' or a preset's sfz block."""
    out = []
    for t in score.get('tracks', []):
        inst = str(t.get('instrument', ''))
        blk = t.get('sfz')
        if inst.startswith('sfz:'):
            blk = {'patch': inst[4:]}
        else:
            cfg = presets.find_instrument(inst)
            if not blk and cfg:
                blk = cfg.get('sfz')
        if blk:
            lib, _, ref = str(blk.get('patch') or '').partition('/')
            out.append((t.get('name', inst), blk.get('library') or lib, ref if not blk.get('library') else blk.get('patch')))
    return out


def sfz_problems(score, project):
    """Project gate: an SFZ track needs its library, its patch and an engine. Messages carry the fix command."""
    out = []
    for track, lib, ref in score_refs(score):
        try:
            get_entry(lib, 'library')
            find_patch(lib, ref, project)
        except (LookupError, SystemExit) as ex:
            out.append(f'track "{track}": {ex}')
    if score_refs(score) and not find_engine(project):
        out.append('SFZ tracks need the sfizz engine. Run: sfz_libs.py engine --project <project>')
    return out


def sfz_warnings(score, project):
    out, seen = [], set()
    reg = registry()
    for track, lib, ref in score_refs(score):
        e = reg.get(presets._norm(lib))
        if e and lib not in seen:
            seen.add(lib)
            msg = f'SFZ library "{lib}" ({e["licence"]}): put "{e["attribution"]}" in the project credits'
            out.append(msg + ('; it has share-alike parts, so do not redistribute the sample files' if e.get('share_alike') else ''))
    return out


# ---------------------------------------------------------------- command line
def cmd_list(project, dest=None):
    root = libs_root(project, dest)
    lock = read_lock(root)
    for name, e in sorted(registry().items()):
        if e.get('type') == 'engine':
            f = find_engine(project)
            print(f'{name:8s} engine   {e["licence"]:34s} {"found: " + str(f) if f else "not installed (sfz_libs.py engine)"}')
            continue
        have = sorted(lock.get('libs', {}).get(name, {}).get('parts', {}))
        total = sum(float(p.get('size_mb', 0)) for p in e['parts'].values())
        print(f'{name:8s} library  {e["licence"][:34]:34s} {total:6.0f} MB all parts   installed: {", ".join(have) or "no"}')
        for p, pd in e['parts'].items():
            print(f'           part {p:20s} {pd.get("size_mb", "?"):>7} MB  {pd.get("what", "")}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['list', 'get', 'engine', 'install-local', 'check', 'verify', 'find', 'remove', 'registry'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--project', default='.')
    ap.add_argument('--part', default=None, help='comma list of parts, or all (default: the library\'s default parts)')
    ap.add_argument('--variant', default=None, help='script set where a library has several (vpo: standard or performance)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--yes', action='store_true', help='do not ask before a download above 500 MB')
    ap.add_argument('--max-gb', type=float, default=None)
    ap.add_argument('--keep-archives', action='store_true')
    ap.add_argument('--no-extract', action='store_true')
    ap.add_argument('--sha256', default=None, help='expected checksum (a single part)')
    ap.add_argument('--mirror', default=None, help='base URL that serves the same file names')
    ap.add_argument('--dest', default=None, help='use this folder instead of <project>/libs/sfz')
    ap.add_argument('--ref', default=None, help='git libraries: branch, tag or commit')
    ap.add_argument('--all-free', action='store_true', help='get: every library in the registry')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    presets.add_project(a.project)
    if a.cmd == 'registry':
        bad = problems()
        print('\n'.join(bad) if bad else 'all sfzlib presets are valid')
        sys.exit(1 if bad else 0)
    if a.cmd == 'list':
        return cmd_list(a.project, a.dest)
    if a.cmd == 'engine':
        install_engine(a.project, a.dest)
    elif a.cmd == 'get':
        names = [n for n, e in registry().items() if e.get('type') == 'library'] if a.all_free else a.args
        if not names:
            sys.exit('name a library (sfz_libs.py list) or use --all-free')
        code = 0
        for n in names:
            code = max(code, get(n, a.project, a.part, a.variant, a.dry_run, a.yes, a.max_gb, a.keep_archives, a.no_extract, a.sha256,
                                 a.mirror, a.dest, a.ref, a.force))
        sys.exit(code)
    elif a.cmd == 'install-local':
        install_local(a.args[0], a.args[1], a.project, a.part, a.dest)
    elif a.cmd == 'check':
        n, bad = check(a.args[0], a.project, a.dest)
        print(f'{n} .sfz files; {len(bad)} with missing samples')
        for k, v in list(bad.items())[:15]:
            print(f'  {k}: {len(v)} missing, e.g. {v[0]}')
        sys.exit(1 if bad else 0)
    elif a.cmd == 'verify':
        bad = verify(a.project, a.dest, a.args or None)
        print('\n'.join(bad) if bad else 'all files match')
        sys.exit(1 if bad else 0)
    elif a.cmd == 'find':
        for p in search(a.args[0], a.args[1:], a.project, a.dest):
            print(p)
    elif a.cmd == 'remove':
        remove(a.args[0], a.project, a.dest)


if __name__ == '__main__':
    main()
