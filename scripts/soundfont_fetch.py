# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""soundfont_fetch.py - download, verify and document the optional SoundFont banks of assets/soundfonts/MANIFEST.json.

Standard library only, so `python scripts/setup_project.py --soundfonts ...` works before the virtual environment exists.

    python scripts/setup_project.py --soundfonts muse_general,sonatina_sf2
    python scripts/setup_project.py --soundfonts all

For each requested bank: a file already on disk that verifies is left alone; otherwise the bank is copied from a local
source (TimGM6mb ships inside the pretty_midi package) or downloaded from the manifest's URLs in order, each with
`RETRIES` attempts and HTTP range resume of a `.part` file. The result is checked against a sha256:

  * a bank with `pin: true` and a sha256 in the manifest must match it, or the file is refused;
  * any other bank is hashed once on first use and the digest is kept in assets/soundfonts/INSTALLED.json: every later
    run checks the file against that record (trust on first use, said out loud: the manifest could not carry a
    checksum for it). Edit the manifest to pin it once you have verified the file yourself.

assets/soundfonts/LICENSES.md is rewritten from the manifest for every bank on disk: licence, holder, source and sha256.
A bank is never written anywhere but assets/soundfonts/, and none of its files is committed (.gitignore).

`MUSICGEN_SOUNDFONT_URL_<NAME>` (name upper-cased, e.g. MUSICGEN_SOUNDFONT_URL_SONATINA_SF2) puts one URL first in line
for that bank: the way to fetch a bank the manifest has no URL for.
"""
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.normpath(os.path.join(HERE, '..', 'assets', 'soundfonts'))
MANIFEST = os.path.join(DIR, 'MANIFEST.json')
INSTALLED = os.path.join(DIR, 'INSTALLED.json')
LICENSES = os.path.join(DIR, 'LICENSES.md')
RETRIES = 3                  # attempts per URL (starting value)
TIMEOUT_S = 60               # per socket operation: a stalled connection fails instead of hanging
BACKOFF_S = 2.0              # first wait between attempts, doubled each time
CHUNK = 1 << 20


class FetchError(RuntimeError):
    pass


def manifest(path=None):
    with open(path or MANIFEST, encoding='utf-8') as fh:
        return json.load(fh)


_DIGESTS = {}               # (path, size, mtime) -> sha256: a 500 MB bank is hashed once per process, not once per render


def sha256_of(path):
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_size, int(st.st_mtime))
    if key not in _DIGESTS:
        h = hashlib.sha256()
        with open(path, 'rb') as fh:
            for block in iter(lambda: fh.read(CHUNK), b''):
                h.update(block)
        _DIGESTS[key] = h.hexdigest()
    return _DIGESTS[key]


def _installed(directory=None):
    try:
        with open(os.path.join(directory or DIR, 'INSTALLED.json'), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _record(key, digest, size, source, directory=None):
    rec = _installed(directory)
    rec[key] = dict(sha256=digest, size=size, source=source, recorded=time.strftime('%Y-%m-%d'))
    with open(os.path.join(directory or DIR, 'INSTALLED.json'), 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, indent=2, sort_keys=True)
        fh.write('\n')


def expected_digest(key, bank, directory=None):
    """(sha256 the file must have, where that number came from), or (None, why none exists)."""
    if bank.get('pin') and bank.get('sha256'):
        return bank['sha256'], 'the manifest'
    rec = _installed(directory).get(key)
    if rec and rec.get('sha256'):
        return rec['sha256'], f"INSTALLED.json (recorded {rec.get('recorded', '?')} on first use)"
    return None, 'no checksum is pinned or recorded'


def parse_selection(arg, man=None):
    """'all' or 'a,b' -> [bank names], each checked against the manifest. An unknown name is an error naming the known ones."""
    banks = (man or manifest())['banks']
    if arg is None:
        return []
    names = list(banks) if str(arg).strip().lower() in ('all', '') else [s.strip() for s in str(arg).split(',') if s.strip()]
    unknown = [n for n in names if n not in banks]
    if unknown:
        raise FetchError(f'unknown SoundFont bank(s) {", ".join(unknown)}; known: {", ".join(banks)}')
    return names


def verify(path, key, bank, directory=None):
    """(ok, message) for a file on disk against its pinned or recorded digest. A file with neither is accepted and recorded."""
    got = sha256_of(path)
    want, where = expected_digest(key, bank, directory)
    if want is None:
        _record(key, got, os.path.getsize(path), 'first use', directory)
        return True, f'sha256 {got} recorded in INSTALLED.json: {where}; nothing to compare it with yet'
    if got != want:
        return False, f'sha256 {got} does not match {want} from {where}'
    return True, f'sha256 {got} matches {where}'


def _local_source(bank):
    if bank.get('local_source') == 'pretty_midi':
        import importlib.util
        spec = importlib.util.find_spec('pretty_midi')
        if spec and spec.origin:
            p = os.path.join(os.path.dirname(spec.origin), bank['file'])
            if os.path.isfile(p):
                return p
    return None


def _download(url, dest, log):
    """Fetch `url` into dest + '.part' with range resume and retries; rename to dest when complete."""
    part = dest + '.part'
    delay = BACKOFF_S
    last = None
    for attempt in range(1, RETRIES + 1):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        req = urllib.request.Request(url, headers={'Range': f'bytes={have}-'} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                status = getattr(resp, 'status', 200)
                mode = 'ab' if (have and status == 206) else 'wb'      # a server that ignores Range sends 200: start over
                if mode == 'wb':
                    have = 0
                with open(part, mode) as fh:
                    shutil.copyfileobj(resp, fh, CHUNK)
            os.replace(part, dest)
            return
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 416 and have:                               # the .part is already complete
                os.replace(part, dest)
                return
            if exc.code in (401, 403, 404, 410):                       # retrying will not change it
                break
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last = exc
        log(f'    attempt {attempt}/{RETRIES} failed ({last}); ' + ('retrying' if attempt < RETRIES else 'giving up on this URL'))
        if attempt < RETRIES:
            time.sleep(delay)
            delay *= 2
    raise FetchError(f'{url}: {last}')


def fetch(key, directory=None, log=print, man=None):
    """Install one bank. Returns the path of the verified file. Raises FetchError with what to do next."""
    man = man or manifest()
    bank = man['banks'][key]
    directory = directory or DIR
    os.makedirs(directory, exist_ok=True)
    dest = os.path.join(directory, bank['file'])
    if os.path.isfile(dest):
        ok, msg = verify(dest, key, bank, directory)
        if ok:
            log(f'  {key}: already installed, {msg}')
            return dest
        log(f'  {key}: the file on disk is wrong ({msg}); fetching it again')
        os.remove(dest)
    local = _local_source(bank)
    if local:
        shutil.copyfile(local, dest)
        log(f'  {key}: copied from {local}')
    else:
        override = os.environ.get('MUSICGEN_SOUNDFONT_URL_' + key.upper())
        urls = ([override] if override else []) + list(bank.get('urls') or [])
        if not urls:
            raise FetchError(f'{key}: the manifest has no download URL for it. Put the file at {dest} yourself, or set '
                             f'MUSICGEN_SOUNDFONT_URL_{key.upper()}=<url> and run this again')
        errors = []
        for url in urls:
            log(f'  {key}: downloading {url}')
            try:
                _download(url, dest, log)
                break
            except FetchError as exc:
                errors.append(str(exc))
        else:
            raise FetchError(f'{key}: every URL failed ({"; ".join(errors)}). Download it by hand to {dest}, or set '
                             f'MUSICGEN_SOUNDFONT_URL_{key.upper()}=<url>')
    ok, msg = verify(dest, key, bank, directory)
    if not ok:
        os.remove(dest)
        raise FetchError(f'{key}: {msg}: the file was deleted')
    log(f'  {key}: {os.path.getsize(dest) / 1e6:.1f} MB, {msg}')
    return dest


def write_licenses(directory=None, man=None):
    """Rewrite LICENSES.md for every bank that is on disk in `directory`. Returns the text."""
    man = man or manifest()
    directory = directory or DIR
    rec = _installed(directory)
    out = ['# SoundFont licences', '',
           'Generated by `scripts/setup_project.py --soundfonts` from `assets/soundfonts/MANIFEST.json`. One entry per bank on this machine.',
           'The banks themselves are not part of this repository and are not covered by its licence.', '']
    for key, bank in man['banks'].items():
        path = os.path.join(directory, bank['file'])
        if not os.path.isfile(path):
            continue
        lic = bank['license']
        digest = (rec.get(key) or {}).get('sha256') or (bank.get('sha256') if bank.get('pin') else None) or 'not recorded'
        out += [f"## {bank['label']} (`{key}`)", '',
                f"- File: `{bank['file']}`, {os.path.getsize(path) / 1e6:.1f} MB, sha256 `{digest}`",
                f"- Licence: {lic['name']}", f"- Holder: {lic['holder']}", f"- Licence text: {lic['url']}",
                f"- Attribution: {lic['attribution']}",
                f"- Source: {', '.join(bank.get('urls') or []) or bank.get('local_source', 'placed by hand')}", '']
    text = '\n'.join(out)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, 'LICENSES.md'), 'w', encoding='utf-8') as fh:
        fh.write(text)
    return text


def run(selection, directory=None, log=print):
    """What `setup_project.py --soundfonts <selection>` does. Returns 0 when every requested bank is installed."""
    man = manifest()
    try:
        names = parse_selection(selection, man)
    except FetchError as exc:
        log(f'error: {exc}')
        return 2
    failed = []
    for key in names:
        try:
            fetch(key, directory, log, man)
        except FetchError as exc:
            failed.append(key)
            log(f'  FAILED {exc}')
    write_licenses(directory, man)
    log(f'licence notices written to {os.path.join(directory or DIR, "LICENSES.md")}')
    if failed:
        log(f'not installed: {", ".join(failed)}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else 'all'))
