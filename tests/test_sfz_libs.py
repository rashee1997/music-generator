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

"""SFZ libraries at project level: registry, safe downloader (against a local test server, no network), patch checks, gate, render.
Run: python -m unittest tests.test_sfz_libs"""
import hashlib
import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import presets  # noqa: E402
import sfz_libs as sl  # noqa: E402

SPIKE_EXE = Path(os.environ.get('SFIZZ_RENDER', 'sfizz_render.exe'))   # set SFIZZ_RENDER to test against a known engine


def zip_bytes(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


def sine_wav(freq=440.0, sr=44100, secs=1.0):
    import soundfile as sf
    t = np.arange(int(sr * secs)) / sr
    b = io.BytesIO()
    sf.write(b, (0.5 * np.sin(2 * np.pi * freq * t) * np.exp(-t * 2)).astype(np.float32), sr, format='WAV')
    return b.getvalue()


LIB_FILES = {
    'Fake/Patches/Violin Legato.sfz': '<group> lokey=0 hikey=127 pitch_keycenter=69\n<region> sample=../Samples/a note.wav\n',
    'Fake/Patches/Broken.sfz': '<region> sample=../Samples/missing.wav\n',
    'Fake/Patches/inc.sfz': '#include "../Shared/inc.part"\n',
    'Fake/Shared/inc.part': '<region> sample=../Samples/a note.wav lokey=1\n',
    'Fake/Samples/a note.wav': sine_wav(),
}


class Base(unittest.TestCase):
    server = None

    @classmethod
    def setUpClass(cls):
        cls.web = tempfile.mkdtemp()
        cls.files = {'good.zip': zip_bytes(LIB_FILES),
                     'evil.zip': zip_bytes({'../escape.txt': 'x'}),
                     'big.zip': zip_bytes({'Fake/big.bin': 'x' * 10000})}
        for k, v in cls.files.items():
            Path(cls.web, k).write_bytes(v)
        web = cls.web

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=web, **k)

            def log_message(self, *a):
                pass
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Quiet)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(cls.web, ignore_errors=True)

    def setUp(self):
        self.roots = list(presets.PROJECT_ROOTS)
        presets.PROJECT_ROOTS.clear()
        sl.TEST_LOOPBACK = True
        self.proj = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.proj, 'presets', 'sfzlib'))
        presets.add_project(self.proj)
        self.write_entry('fake', 'good.zip')

    def tearDown(self):
        sl.TEST_LOOPBACK = False
        presets.PROJECT_ROOTS[:] = self.roots
        shutil.rmtree(self.proj, ignore_errors=True)

    def write_entry(self, name, zipname, **over):
        e = {'name': name, 'character': 'a fake library for tests', 'type': 'library', 'licence': 'CC0', 'share_alike': False,
             'attribution': 'Fake Orchestra, tests', 'source': {'kind': 'zip'}, 'entry': 'Fake',
             'parts': {'main': {'size_mb': 0.1, 'what': 'everything', 'url': f'http://127.0.0.1:{self.port}/{zipname}', 'hosts': ['127.0.0.1']}},
             'default_parts': ['main']}
        e.update(over)
        with open(os.path.join(self.proj, 'presets', 'sfzlib', name + '.json'), 'w') as f:
            json.dump(e, f)

    def get(self, name='fake', **kw):
        kw.setdefault('yes', True)
        kw.setdefault('quiet', True)
        return sl.get(name, self.proj, **kw)


class Registry(Base):
    def test_shipped_entries_are_valid(self):
        self.assertEqual([p for p in sl.problems() if 'fake' not in p], [])
        self.assertTrue({'sso', 'vpo', 'sfizz'} <= set(sl.registry()))

    def test_shipped_urls_are_https_with_hosts(self):
        for name in ('sso', 'vpo'):
            for pn, p in sl.registry()[name]['parts'].items():
                if 'url' in p:
                    self.assertTrue(p['url'].startswith('https://') and p['hosts'], pn)

    def test_bad_entries_are_rejected(self):
        good = sl.registry()['vpo']
        cases = {
            'http': dict(good, parts={'x': dict(good['parts']['scripts_standard'], url='http://example.com/a.zip', hosts=['example.com'])}),
            'no_hosts': dict(good, parts={'x': {'url': 'https://example.com/a.zip'}}),
            'two_ways': dict(good, parts={'x': {'url': 'https://e.com/a.zip', 'hosts': ['e.com'], 'manual': 'https://e.com'}}),
            'no_licence': {k: v for k, v in good.items() if k != 'licence'},
            'unknown_key': dict(good, surprise=1),
            'bad_default': dict(good, default_parts=['nope']),
            'bad_sha': dict(good, parts={'x': dict(good['parts']['scripts_standard'], sha256='abc')}),
        }
        for key, e in cases.items():
            self.assertTrue(sl.entry_problems('t', e), key)


class Downloader(Base):
    def test_dry_run_downloads_nothing(self):
        self.assertEqual(self.get(dry_run=True), 0)
        self.assertFalse(Path(self.proj, 'libs').exists())

    def test_get_unpacks_records_lock_and_licences(self):
        self.get()
        root = Path(self.proj, 'libs', 'sfz')
        self.assertTrue((root / 'fake' / 'Fake' / 'Patches' / 'Violin Legato.sfz').exists())
        lock = sl.read_lock(root)
        part = lock['libs']['fake']['parts']['main']
        self.assertEqual(part['sha256'], hashlib.sha256(self.files['good.zip']).hexdigest())
        self.assertIn('Fake Orchestra, tests', (root / 'LICENCES.md').read_text())
        self.assertFalse(list((root / '.downloads').glob('*.zip')))            # archives are not kept by default

    def test_second_run_is_safe_and_keeps_the_checksum(self):
        self.get()
        self.get()
        self.assertEqual(len(sl.read_lock(Path(self.proj, 'libs', 'sfz'))['libs']['fake']['parts']), 1)

    def test_wrong_sha256_is_rejected_and_nothing_is_unpacked(self):
        self.write_entry('fake', 'good.zip', parts={'main': dict(sl.registry()['fake']['parts']['main'], sha256='0' * 64)})
        with self.assertRaises(SystemExit):
            self.get()
        self.assertFalse(Path(self.proj, 'libs', 'sfz', 'fake', 'Fake').exists())

    def test_zip_with_escaping_path_is_refused(self):
        self.write_entry('evil', 'evil.zip')
        with self.assertRaises(SystemExit) as cm:
            self.get('evil')
        self.assertIn('leave the library folder', str(cm.exception))
        self.assertFalse(Path(self.proj, 'libs', 'escape.txt').exists())

    def test_max_gb_refuses_before_downloading(self):
        with self.assertRaises(SystemExit):
            self.get(max_gb=0.00001)
        self.assertFalse(Path(self.proj, 'libs').exists())

    def test_unpack_size_cap(self):
        with self.assertRaises(SystemExit):
            sl.safe_extract(Path(self.web, 'big.zip'), Path(self.proj, 'x'), max_gb=0.000001)

    def test_host_not_in_preset_is_refused(self):
        with self.assertRaises(SystemExit):
            sl.download('https://evil.example/a.zip', Path(self.proj, 'a.zip'), ['example.com'], quiet=True)

    def test_non_https_is_refused_outside_tests(self):
        sl.TEST_LOOPBACK = False
        with self.assertRaises(SystemExit):
            sl.download(f'http://127.0.0.1:{self.port}/good.zip', Path(self.proj, 'a.zip'), ['127.0.0.1'], quiet=True)

    def test_resume_continues_a_partial_file(self):
        arc = Path(self.proj, 'a.zip')
        part = arc.with_suffix('.zip.part')
        part.write_bytes(self.files['good.zip'][:200])
        sl.download(f'http://127.0.0.1:{self.port}/good.zip', arc, ['127.0.0.1'], quiet=True)
        self.assertEqual(arc.read_bytes(), self.files['good.zip'])

    def test_verify_catches_an_edit_and_remove_deletes_only_that_library(self):
        self.get()
        self.write_entry('other', 'good.zip')
        self.get('other')
        root = Path(self.proj, 'libs', 'sfz')
        self.assertEqual(sl.verify(self.proj), [])
        (root / 'fake' / 'Fake' / 'Shared' / 'inc.part').write_text('<region> sample=x.wav\n')
        self.assertTrue(any('changed' in p for p in sl.verify(self.proj, names=['fake'])))
        sl.remove('fake', self.proj)
        self.assertFalse((root / 'fake').exists())
        self.assertTrue((root / 'other' / 'Fake').exists())
        self.assertNotIn('fake', sl.read_lock(root)['libs'])

    def test_manual_part_reports_a_pending_step(self):
        self.write_entry('hand', 'good.zip', parts={'wave': {'size_mb': 1, 'manual': 'https://example.com/page', 'manual_note': 'download by hand'}},
                         default_parts=['wave'])
        self.assertEqual(self.get('hand'), 2)

    def test_install_local(self):
        self.write_entry('hand', 'good.zip', parts={'wave': {'size_mb': 1, 'manual': 'https://example.com/page'}}, default_parts=['wave'])
        z = Path(self.proj, 'mine.zip')
        z.write_bytes(self.files['good.zip'])
        sl.install_local('hand', z, self.proj, 'wave')
        self.assertTrue(Path(self.proj, 'libs', 'sfz', 'hand', 'Fake', 'Samples', 'a note.wav').exists())

    def test_licence_summary_flags_share_alike(self):
        self.write_entry('sa', 'good.zip', share_alike=True)
        self.get('sa')
        self.assertIn('share-alike', Path(self.proj, 'libs', 'sfz', 'LICENCES.md').read_text())


class Patches(Base):
    def setUp(self):
        super().setUp()
        self.get()

    def test_check_finds_missing_samples_and_follows_includes_and_spaces(self):
        n, bad = sl.check('fake', self.proj)
        self.assertEqual(n, 3)
        self.assertEqual(list(bad), ['Patches/Broken.sfz'])                  # the other two resolve, incl. 'a note.wav' (space) and #include

    def test_find_patch_is_forgiving_but_exact_about_the_library(self):
        for ref in ('Patches/Violin Legato', 'patches/violin legato.sfz'):
            self.assertEqual(sl.find_patch('fake', ref, self.proj).name.lower(), 'violin legato.sfz')
        with self.assertRaises(LookupError) as cm:
            sl.find_patch('fake', 'Patches/Violin Legatto', self.proj)
        self.assertIn('Run: sfz_libs.py find', str(cm.exception))
        with self.assertRaises(LookupError) as cm:
            sl.find_patch('sso', 'Strings - Notation/x', self.proj)
        self.assertIn('sfz_libs.py get sso', str(cm.exception))

    def test_search(self):
        self.assertEqual(sl.search('fake', ['violin'], self.proj), ['Patches/Violin Legato.sfz'])


class GateAndRefs(Base):
    def score(self, inst='sfz:fake/Patches/Violin Legato'):
        return {'tracks': [{'name': 'v', 'instrument': inst, 'role': 'melody', 'notes': []}]}

    def test_missing_library_is_an_error_with_the_fix(self):
        out = sl.sfz_problems(self.score(), self.proj)
        self.assertTrue(any('sfz_libs.py get fake' in p for p in out), out)

    def test_installed_library_passes_but_engine_is_required(self):
        self.get()
        old = os.environ.pop('SFIZZ_RENDER', None)
        try:
            os.environ['SFIZZ_RENDER'] = str(Path(self.proj, 'no_such.exe'))
            out = sl.sfz_problems(self.score(), self.proj)
        finally:
            os.environ.pop('SFIZZ_RENDER', None)
            if old:
                os.environ['SFIZZ_RENDER'] = old
        self.assertEqual([p for p in out if 'Patches' in p or 'get fake' in p], [])

    def test_no_sfz_track_no_rows(self):
        self.assertEqual(sl.sfz_problems({'tracks': [{'name': 'p', 'instrument': 'piano'}]}, self.proj), [])
        self.assertEqual(sl.sfz_warnings({'tracks': [{'name': 'p', 'instrument': 'piano'}]}, self.proj), [])

    def test_warning_carries_credit_line(self):
        w = sl.sfz_warnings(self.score(), self.proj)
        self.assertTrue(any('Fake Orchestra, tests' in x for x in w), w)

    def test_preset_with_sfz_block_is_found(self):
        os.makedirs(os.path.join(self.proj, 'presets', 'instruments'))
        json.dump({'role': 'melody', 'sfz': {'library': 'fake', 'patch': 'Patches/Violin Legato'}},
                  open(os.path.join(self.proj, 'presets', 'instruments', 'my_violin.json'), 'w'))
        refs = sl.score_refs(self.score('my_violin'))
        self.assertEqual(refs[0][1], 'fake')


@unittest.skipUnless(sl.find_engine() or SPIKE_EXE.exists(), 'no sfizz_render found (run sfz_libs.py engine); engine tests skipped')
class Engine(Base):
    def setUp(self):
        super().setUp()
        self._old = os.environ.get('SFIZZ_RENDER')
        if not sl.find_engine():
            os.environ['SFIZZ_RENDER'] = str(SPIKE_EXE)
        self.get()

    def tearDown(self):
        if self._old is None:
            os.environ.pop('SFIZZ_RENDER', None)
        else:
            os.environ['SFIZZ_RENDER'] = self._old
        super().tearDown()

    def track(self, inst='sfz:fake/Patches/Violin Legato', **extra):
        notes = [dict(t=float(i), d=0.9, p=69, v=0.8) for i in range(4)]
        return dict(name='v', instrument=inst, role='melody', notes=notes, humanize='tight', **extra)

    def render(self, tr):
        import humanize as hz
        import render_natural as rn
        tm = hz.TempoMap(60, total_beats=6)
        return rn.render_track(tr, tm, None, None, 'tight', 3, [4, 4], 0.0)

    def test_renders_audio_with_tail_and_is_reproducible(self):
        a, b = self.render(self.track()), self.render(self.track())
        self.assertEqual(a.ndim, 2)
        self.assertGreater(float(np.abs(a).max()), 0.001)
        self.assertGreater(a.shape[0], 4.5 * 44100)                           # last note ends near 4 s, plus the release tail
        self.assertTrue(np.array_equal(a, b))

    def test_trim_db_scales_the_stem(self):
        a = self.render(self.track())
        b = self.render(self.track(sfz={'trim_db': 6.0}))
        self.assertAlmostEqual(float(np.abs(b).max() / np.abs(a).max()), 10 ** (6 / 20), places=2)

    def test_dynamics_curve_changes_the_level(self):
        loud = self.render(self.track(dynamics=[[0, 1.0], [6, 1.0]]))
        soft = self.render(self.track(dynamics=[[0, 0.2], [6, 0.2]]))
        self.assertGreater(float(np.abs(loud).max()), 1.5 * float(np.abs(soft).max()))

    def test_legato_overlap_extends_the_note_into_the_next(self):
        import sfz_render
        ev = [dict(t=0.0, dur=0.5, p=60, v=80), dict(t=0.6, dur=0.5, p=62, v=80)]
        pm = sfz_render.midi_for(ev, [0.5, 1.1], {'cc': 'none'}, lambda t: 0.8, 'X Legato.sfz')
        ends = sorted(n.end for n in pm.instruments[0].notes)
        self.assertAlmostEqual(ends[0], 0.64, places=2)
        pm2 = sfz_render.midi_for(ev, [0.5, 1.1], {'cc': 'none'}, lambda t: 0.8, 'X Sustain.sfz')
        self.assertAlmostEqual(sorted(n.end for n in pm2.instruments[0].notes)[0], 0.5, places=2)

    def test_keyswitch_note_precedes_the_first_note_of_an_articulation(self):
        import sfz_render
        ev = [dict(t=1.0, dur=0.5, p=60, v=80, art='pizz'), dict(t=2.0, dur=0.5, p=62, v=80, art='pizz')]
        pm = sfz_render.midi_for(ev, [1.5, 2.5], {'cc': 'none', 'keyswitches': {'pizz': 36}}, lambda t: 0.8, 'KS.sfz')
        self.assertEqual([n.pitch for n in pm.instruments[0].notes].count(36), 1)

    def test_missing_library_raises_with_the_fix(self):
        with self.assertRaises(RuntimeError) as cm:
            self.render(self.track('sfz:nolib/x'))
        self.assertIn('sfz_libs.py', str(cm.exception))

    def test_fallback_gm_plays_the_soundfont_and_says_so(self):
        import humanize as hz
        import render_natural as rn
        import soundbank as sb
        tr = self.track('sfz:nolib/x', sfz={'fallback': 'gm'})
        tm = hz.TempoMap(60, total_beats=6)
        before = rn.STATS.get('sfz_fallback', 0)
        x = rn.render_track(tr, tm, sb.ensure_soundfont(), None, 'tight', 3, [4, 4], 0.0)
        self.assertGreater(float(np.abs(x).max()), 0.001)
        self.assertEqual(rn.STATS.get('sfz_fallback', 0), before + 1)


if __name__ == '__main__':
    unittest.main()
