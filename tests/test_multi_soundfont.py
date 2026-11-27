# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Multiple SoundFont banks: the manifest, per-track routing, program maps, the fetcher, and bank-by-bank rendering.

No large bank is needed: the two "banks" of the render tests are copies of the 6 MB TimGM6mb that ships in the pretty_midi
package, registered under mock names in a temporary manifest. Nothing here touches assets/soundfonts/ or the network
(the fetch tests use a local HTTP server).
"""
import gc
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import weakref

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)

import presets  # noqa: E402
import render_natural as rn  # noqa: E402
import soundbank as sb  # noqa: E402
import soundfont_fetch as sff  # noqa: E402


def tim():
    import pretty_midi
    return os.path.join(os.path.dirname(pretty_midi.__file__), 'TimGM6mb.sf2')


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


class Manifest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(SCRIPTS, '..', 'assets', 'soundfonts', 'MANIFEST.json'), encoding='utf-8') as fh:
            self.man = json.load(fh)

    def test_the_banks_and_their_required_fields(self):
        banks = self.man['banks']
        self.assertEqual(list(banks), ['generaluser_gs', 'timgm6mb', 'muse_general', 'fluid_r3_gm', 'sonatina_sf2',
                                       'cinematic_default', 'cc0_orchestra', 'neo_orchestra_hq'])
        self.assertEqual(self.man['default'], 'generaluser_gs')
        for key, b in banks.items():
            for field in ('file', 'label', 'type', 'size_mb', 'urls', 'sha256', 'license', 'gm_order', 'pin'):
                self.assertIn(field, b, (key, field))
            self.assertIn(b['type'], ('gm_gs', 'orchestral'), key)
            for field in ('name', 'holder', 'url', 'attribution'):
                self.assertTrue(b['license'].get(field), (key, field))
            if b['sha256'] is not None:
                self.assertRegex(b['sha256'], r'^[0-9a-f]{64}$', key)
            self.assertTrue(b['file'].endswith('.sf2'), key)

    def test_no_checksum_is_claimed_that_was_not_taken_and_pins_have_one(self):
        for key, b in self.man['banks'].items():
            if b['pin']:
                self.assertIsNotNone(b['sha256'], key)
            if b['sha256'] is None:
                self.assertIn('not taken', b['sha256_status'], key)
        self.assertEqual(self.man['banks']['timgm6mb']['sha256'], sha(tim()))       # the one measured against the real file

    def test_only_the_non_gm_orchestral_banks_are_outside_general_midi_order(self):
        order = {k: b['gm_order'] for k, b in self.man['banks'].items()}
        self.assertEqual([k for k, v in order.items() if not v], ['sonatina_sf2', 'cc0_orchestra', 'neo_orchestra_hq'])
        self.assertEqual(self.man['banks']['sonatina_sf2']['type'], 'orchestral')

    def test_the_default_bank_is_what_the_engine_already_used(self):
        self.assertEqual(sb.DEFAULT_BANK, 'generaluser_gs')
        self.assertEqual(self.man['banks']['generaluser_gs']['file'], sb.SF_NAME)


class Routing(unittest.TestCase):
    def test_an_unrouted_track_plays_the_default_bank_unchanged(self):
        self.assertEqual(sb.bank_key({'name': 't', 'instrument': 'piano'}), 'generaluser_gs')
        resolved = sb.resolve('cello')
        self.assertEqual(sb.program_for('generaluser_gs', resolved, {}, {'name': 't'}), resolved)

    def test_a_track_beats_its_preset_and_the_preset_beats_the_default(self):
        self.assertEqual(sb.bank_key({'soundfont': 'timgm6mb'}, {'soundfont': 'muse_general'}), 'timgm6mb')
        self.assertEqual(sb.bank_key({}, {'soundfont': 'muse_general'}), 'muse_general')

    def test_an_unknown_bank_names_the_known_ones(self):
        with self.assertRaises(ValueError) as cm:
            sb.bank_key({'name': 'x', 'soundfont': 'nope'})
        self.assertIn('muse_general', str(cm.exception))

    def test_a_general_midi_bank_without_a_map_keeps_the_gm_program(self):
        resolved = sb.resolve('flute')
        self.assertEqual(sb.program_for('muse_general', resolved, {}, {}), resolved)

    def test_a_non_gm_bank_needs_a_program_map_and_names_the_key_to_add(self):
        with self.assertRaises(ValueError) as cm:
            sb.program_for('sonatina_sf2', sb.resolve('violin'), {'name': 'solo_violin'}, {})
        self.assertIn('program_map', str(cm.exception))
        self.assertIn('sonatina_sf2', str(cm.exception))

    def test_a_program_map_on_the_preset_or_the_track_decides_the_preset(self):
        resolved = sb.resolve('violin')
        preset_map = {'program_map': {'sonatina_sf2': {'bank': 3, 'program': 17}}}
        self.assertEqual(sb.program_for('sonatina_sf2', resolved, preset_map, {}), (3, 17, False))
        track_map = {'program_map': {'sonatina_sf2': {'bank': 0, 'program': 5}}}
        self.assertEqual(sb.program_for('sonatina_sf2', resolved, preset_map, track_map), (0, 5, False))
        kit = {'program_map': {'sonatina_sf2': {'bank': 128, 'program': 2}}}
        self.assertEqual(sb.program_for('sonatina_sf2', resolved, kit, {}), (128, 2, True))
        self.assertEqual(sb.program_for('generaluser_gs', resolved, preset_map, {}), resolved)   # a map for another bank is ignored

    def test_preset_validation_of_the_new_keys(self):
        self.assertEqual(presets.soundfont_problems({'name': 'x'}), [])
        self.assertEqual(presets.soundfont_problems({'soundfont': 'sonatina_sf2',
                                                     'program_map': {'sonatina_sf2': {'bank': 0, 'program': 9}}}), [])
        bad = presets.soundfont_problems({'soundfont': 'bogus', 'program_map': {'nope': {'bank': 'a'}, 'muse_general': {'bank': 0, 'program': 200}}})
        self.assertEqual(len(bad), 4)
        self.assertTrue(presets.soundfont_problems({'program_map': [1]}))

    def test_no_shipped_preset_breaks_validation(self):
        self.assertEqual(presets.validate(), [])


class Missing(unittest.TestCase):
    def test_a_missing_bank_names_the_exact_command(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(SCRIPTS, '..', 'assets', 'soundfonts', 'MANIFEST.json'), d)
            old = sb.SF_DIR
            sb.SF_DIR = d
            try:
                with self.assertRaises(sb.SoundFontMissing) as cm:
                    sb.bank_path('muse_general')
            finally:
                sb.SF_DIR = old
        msg = str(cm.exception)
        self.assertIn('python scripts/setup_project.py --soundfonts muse_general', msg)
        self.assertNotIsInstance(cm.exception, FileNotFoundError)

    def test_every_missing_bank_is_reported_at_once(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(SCRIPTS, '..', 'assets', 'soundfonts', 'MANIFEST.json'), d)
            old = sb.SF_DIR
            sb.SF_DIR = d
            try:
                with self.assertRaises(sb.SoundFontMissing) as cm:
                    sb.bank_paths(['muse_general', 'fluid_r3_gm', 'muse_general'])
            finally:
                sb.SF_DIR = old
        self.assertIn('--soundfonts muse_general', str(cm.exception))
        self.assertIn('--soundfonts fluid_r3_gm', str(cm.exception))


class TempBanks(unittest.TestCase):
    """A temporary manifest with two mock banks, both copies of TimGM6mb."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        base = json.load(open(os.path.join(SCRIPTS, '..', 'assets', 'soundfonts', 'MANIFEST.json'), encoding='utf-8'))
        self.gm_a, self.gm_b, self.orch = (os.path.join(d, n) for n in ('a.sf2', 'b.sf2', 'o.sf2'))
        for p in (self.gm_a, self.gm_b, self.orch):
            shutil.copyfile(tim(), p)
        digest = sha(tim())

        def bank(file, gm=True):
            b = json.loads(json.dumps(base['banks']['timgm6mb']))
            b.update(file=file, sha256=digest, pin=True, gm_order=gm, local_source=None, label=file)
            return b
        base['banks'].update(mock_a=bank('a.sf2'), mock_b=bank('b.sf2'), mock_orch=bank('o.sf2', gm=False))
        json.dump(base, open(os.path.join(d, 'MANIFEST.json'), 'w'))
        self.old = sb.SF_DIR
        sb.SF_DIR = d
        rn.release_synths()

    def tearDown(self):
        sb.SF_DIR = self.old
        rn.release_synths()
        self.tmp.cleanup()

    def score(self, extra=None, banks=('mock_b',)):
        notes = [dict(t=i * 0.5, d=0.45, p=60 + (i * 3) % 9, v=0.7) for i in range(8)]
        tracks = [dict(name='p0', instrument='piano', role='melody', notes=notes),
                  dict(name='c0', instrument='cello', role='bass', notes=[dict(n, p=n['p'] - 24) for n in notes]),
                  dict(name='f0', instrument='flute', role='counter', notes=[dict(n, p=n['p'] + 12) for n in notes])]
        for i, b in enumerate(banks):
            tracks.append(dict(name=f'x{i}', instrument='violin', role='counter', soundfont=b, notes=notes))
        return dict(bpm=100, ts=[4, 4], seed=3, tracks=tracks, **(extra or {}))

    def test_a_missing_bank_stops_the_render_before_any_track_is_rendered(self):
        sc = self.score(banks=('muse_general',))
        with self.assertRaises(sb.SoundFontMissing) as cm:
            rn.build_stems(sc, sfpath=self.gm_a, verbose=False)
        self.assertIn('--soundfonts muse_general', str(cm.exception))
        self.assertEqual(rn._SYNTH_CACHE, {})

    def test_a_corrupted_bank_fails_its_checksum_with_a_remedy(self):
        with open(self.gm_b, 'r+b') as fh:
            fh.seek(1000)
            fh.write(b'\x00\x01\x02')
        with self.assertRaises(sb.SoundFontMissing) as cm:
            sb.bank_path('mock_b')
        self.assertIn('checksum', str(cm.exception))
        self.assertIn('--soundfonts mock_b', str(cm.exception))

    def test_tracks_render_bank_by_bank_and_every_bank_is_released(self):
        loaded, refs = [], []
        real_borrow = rn._borrow_synth

        def spy(sfpath, sample_rate, max_instances=1):
            loaded.append(os.path.basename(str(sfpath)))
            slot = real_borrow(sfpath, sample_rate, max_instances)
            try:
                refs.append(weakref.ref(slot.synth))
            except TypeError:
                pass
            return slot
        rn._borrow_synth = spy
        try:
            stems, _ = rn.build_stems(self.score(banks=('mock_b', 'mock_b')), sfpath=self.gm_a, verbose=False)
        finally:
            rn._borrow_synth = real_borrow
        self.assertEqual(sorted(stems), ['c0', 'f0', 'p0', 'x0', 'x1'])
        for name, stem in stems.items():
            self.assertGreater(float(abs(stem).max()), 1e-4, name)
        # bank by bank: no return to a bank after leaving it
        order = [k for i, k in enumerate(loaded) if i == 0 or k != loaded[i - 1]]
        self.assertEqual(order, ['a.sf2', 'b.sf2'])
        self.assertEqual(loaded.count('b.sf2'), 2)
        # and every synth of both banks is gone before the stage returns
        self.assertEqual(rn._SYNTH_CACHE, {})
        gc.collect()
        self.assertTrue(refs)
        self.assertTrue(all(r() is None for r in refs), 'a Synth is still alive after its bank was released')

    def test_the_default_only_score_keeps_its_bank_cached_as_before(self):
        rn.build_stems(self.score(banks=()), sfpath=self.gm_a, verbose=False)
        self.assertEqual(len(rn._SYNTH_CACHE), 1)
        self.assertEqual(os.path.basename(next(iter(rn._SYNTH_CACHE))[1]), 'a.sf2')

    def test_a_non_gm_bank_plays_the_preset_the_map_names_and_refuses_without_one(self):
        sc = self.score(banks=('mock_orch',))
        with self.assertRaises(ValueError) as cm:
            rn.build_stems(sc, sfpath=self.gm_a, verbose=False)
        self.assertIn('program_map', str(cm.exception))
        sc['tracks'][-1]['program_map'] = {'mock_orch': {'bank': 0, 'program': 40}}
        stems, _ = rn.build_stems(sc, sfpath=self.gm_a, verbose=False)
        self.assertGreater(float(abs(stems['x0']).max()), 1e-4)
        self.assertEqual(rn._SYNTH_CACHE, {})

    def test_the_bank_is_part_of_the_render_identity(self):
        notes = [dict(t=0, d=1, p=60, v=0.7)]
        tr = dict(name='a', instrument='piano', role='melody', notes=notes)
        tm = rn.hz.tempo_map_for(dict(bpm=90, ts=[4, 4], tracks=[tr]), seed=1)
        k1 = rn._track_cache_key(tr, 1, [4, 4], 0.5, tm, None, rn.SR, self.gm_a)
        k2 = rn._track_cache_key(tr, 1, [4, 4], 0.5, tm, None, rn.SR, self.gm_b)
        self.assertNotEqual(k1, k2)


class Handler(http.server.BaseHTTPRequestHandler):
    data = b''
    fail_first = 0
    seen = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        cls = type(self)
        cls.seen.append(self.headers.get('Range'))
        if len(cls.seen) <= cls.fail_first:
            self.send_response(503)
            self.end_headers()
            return
        rng = self.headers.get('Range')
        start = int(rng.split('=')[1].split('-')[0]) if rng else 0
        if start >= len(cls.data):
            self.send_response(416)
            self.end_headers()
            return
        body = cls.data[start:]
        self.send_response(206 if rng else 200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Handler.data = os.urandom(3_000_000)
        Handler.fail_first, Handler.seen = 0, []
        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.srv.server_address[1]}/x.sf2'
        self.digest = hashlib.sha256(Handler.data).hexdigest()
        self.old = (sff.BACKOFF_S, sff.RETRIES)
        sff.BACKOFF_S = 0.0
        self.log = []

    def tearDown(self):
        sff.BACKOFF_S, sff.RETRIES = self.old
        self.srv.shutdown()
        self.tmp.cleanup()

    def man(self, pin=True, digest=None):
        return {'banks': {'bank_x': dict(file='x.sf2', label='Bank X', type='gm_gs', size_mb=3, urls=[self.url], pin=pin,
                                          sha256=digest if digest is not None else (self.digest if pin else None),
                                          license=dict(name='Test Licence', holder='Nobody', url='https://example.invalid/l',
                                                       attribution='Bank X by Nobody.'), gm_order=True)}}

    def test_a_download_is_verified_and_documented(self):
        path = sff.fetch('bank_x', self.tmp.name, self.log.append, self.man())
        self.assertEqual(sff.sha256_of(path), self.digest)
        text = sff.write_licenses(self.tmp.name, self.man())
        self.assertIn('Test Licence', text)
        self.assertIn('Bank X by Nobody.', text)
        self.assertIn(self.digest, text)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, 'LICENSES.md')))

    def test_a_partial_file_is_resumed_not_restarted(self):
        part = os.path.join(self.tmp.name, 'x.sf2.part')
        with open(part, 'wb') as fh:
            fh.write(Handler.data[:1_000_000])
        path = sff.fetch('bank_x', self.tmp.name, self.log.append, self.man())
        self.assertEqual(sff.sha256_of(path), self.digest)
        self.assertEqual(Handler.seen, ['bytes=1000000-'])
        self.assertFalse(os.path.exists(part))

    def test_a_flaky_server_is_retried(self):
        Handler.fail_first = 2
        sff.RETRIES = 3
        # 503 is not in the do-not-retry list, so the third attempt succeeds
        path = sff.fetch('bank_x', self.tmp.name, self.log.append, self.man())
        self.assertEqual(sff.sha256_of(path), self.digest)
        self.assertEqual(len(Handler.seen), 3)

    def test_a_wrong_checksum_deletes_the_file_and_says_so(self):
        with self.assertRaises(sff.FetchError) as cm:
            sff.fetch('bank_x', self.tmp.name, self.log.append, self.man(digest='0' * 64))
        self.assertIn('does not match', str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'x.sf2')))

    def test_an_unpinned_bank_is_recorded_on_first_use_and_checked_afterwards(self):
        man = self.man(pin=False)
        path = sff.fetch('bank_x', self.tmp.name, self.log.append, man)
        rec = json.load(open(os.path.join(self.tmp.name, 'INSTALLED.json')))
        self.assertEqual(rec['bank_x']['sha256'], self.digest)
        ok, _ = sff.verify(path, 'bank_x', man['banks']['bank_x'], self.tmp.name)
        self.assertTrue(ok)
        with open(path, 'r+b') as fh:
            fh.write(b'XX')
        sff._DIGESTS.clear()
        ok, msg = sff.verify(path, 'bank_x', man['banks']['bank_x'], self.tmp.name)
        self.assertFalse(ok)
        self.assertIn('INSTALLED.json', msg)

    def test_a_bank_with_no_url_says_how_to_supply_one(self):
        man = self.man()
        man['banks']['bank_x']['urls'] = []
        with self.assertRaises(sff.FetchError) as cm:
            sff.fetch('bank_x', self.tmp.name, self.log.append, man)
        self.assertIn('MUSICGEN_SOUNDFONT_URL_BANK_X', str(cm.exception))

    def test_the_environment_url_is_tried_first(self):
        man = self.man()
        man['banks']['bank_x']['urls'] = []
        os.environ['MUSICGEN_SOUNDFONT_URL_BANK_X'] = self.url
        try:
            path = sff.fetch('bank_x', self.tmp.name, self.log.append, man)
        finally:
            del os.environ['MUSICGEN_SOUNDFONT_URL_BANK_X']
        self.assertEqual(sff.sha256_of(path), self.digest)

    def test_selection_parsing(self):
        man = self.man()
        self.assertEqual(sff.parse_selection('all', man), ['bank_x'])
        self.assertEqual(sff.parse_selection('bank_x', man), ['bank_x'])
        with self.assertRaises(sff.FetchError):
            sff.parse_selection('bank_x,zzz', man)

    def test_timgm6mb_is_copied_from_the_pretty_midi_package_and_verified(self):
        man = sff.manifest()
        path = sff.fetch('timgm6mb', self.tmp.name, self.log.append, man)
        self.assertEqual(sff.sha256_of(path), man['banks']['timgm6mb']['sha256'])
        self.assertIn('TimGM6mb', sff.write_licenses(self.tmp.name, man))


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, 'setup_project.py'), *args], capture_output=True, text=True, timeout=120)

    def test_an_unknown_bank_is_a_usage_error_naming_the_known_ones(self):
        r = self.run_cli('--soundfonts', 'bogus')
        self.assertEqual(r.returncode, 2)
        self.assertIn('muse_general', r.stdout)

    def test_the_flag_is_documented_and_default_setup_does_not_fetch_banks(self):
        r = self.run_cli('--help')
        self.assertIn('--soundfonts', r.stdout)
        src = open(os.path.join(SCRIPTS, 'setup_project.py'), encoding='utf-8').read()
        self.assertEqual(src.count('soundfont_fetch'), 2)     # the import and the call, both behind `args.soundfonts is not None`


if __name__ == '__main__':
    unittest.main()
