# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Audit fixes in the render engine: cache touch on hit, project from the argument, download timeout, cache keys,
REPORT reset, one code hash, and the vectorized helpers against the formulations they replaced."""
import hashlib
import glob
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / 'scripts'))
sys.path.insert(0, str(SK / 'tests'))

import render_natural as rn
import sfz_render
import soundbank
import stem_cache


class TestCacheHitTouchesFile(unittest.TestCase):
    def test_hit_refreshes_mtime_so_prune_keeps_it(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            with mock.patch.object(rn, '_track_cache_dir', return_value=d), \
                    mock.patch.object(rn, '_track_cache_key', return_value='k1'), \
                    mock.patch.object(rn, 'render_track', side_effect=lambda *a, **k: (calls.append(1), np.zeros((rn.SR // 10, 2), np.float32))[1]):
                rn._render_cached({}, 'a', None, None, None, None, 0, (4, 4), 0.5)
                wav, meta = os.path.join(d, 'k1.wav'), os.path.join(d, 'k1.report.json')
                Path(meta).write_text('{}')
                old = time.time() - 10000
                os.utime(wav, (old, old))
                os.utime(meta, (old, old))
                rn._render_cached({}, 'a', None, None, None, None, 0, (4, 4), 0.5)
                self.assertEqual(len(calls), 1, 'second call must be a hit')
                self.assertGreater(os.stat(wav).st_mtime, old + 5000)
                self.assertGreater(os.stat(meta).st_mtime, old + 5000)
                other = os.path.join(d, 'other.wav')
                Path(other).write_bytes(b'0' * 1000)
                os.utime(other, (old + 100, old + 100))           # older than the hit stem would be, newer than it was
                size = os.stat(wav).st_size
                stem_cache.prune(d, max_bytes=size + 10)
                self.assertTrue(os.path.exists(wav), 'the reused stem must outlive an unused one')
                self.assertFalse(os.path.exists(other))


class TestMusic21ProjectNotFromOutPath(unittest.TestCase):
    def test_out_path_never_picks_the_script(self):
        import pipeline
        import presets
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'scripts').mkdir()
            (Path(d) / 'scripts' / 'analyze_music21.py').write_text(
                "def analyze(score, **k):\n    return [('FAIL', 'planted', 'ran')]\n")
            (Path(d) / 'y').mkdir()
            out = str(Path(d) / 'y' / 'z.wav')
            saved = list(presets.PROJECT_ROOTS)
            presets.PROJECT_ROOTS[:] = []
            try:
                p = pipeline.MusicPipeline(verbose=False)
                rows = p.discover_and_run_music21_analysis({'tracks': []}, out)
                self.assertFalse(any(r[1] == 'planted' for r in rows or []))
                rows = p.discover_and_run_music21_analysis({'tracks': []}, out, project_dir=d)
                self.assertTrue(any(r[1] == 'planted' for r in rows or []))
            finally:
                presets.PROJECT_ROOTS[:] = saved


class TestDownload(unittest.TestCase):
    def test_timeout_and_part_removed(self):
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, 'x.sf2')
            seen = {}

            class Boom:
                def __enter__(self):
                    raise OSError('stalled')

                def __exit__(self, *a):
                    return False

            def fake_open(url, timeout=None):
                seen.setdefault('timeouts', []).append(timeout)
                Path(dst + '.part').write_bytes(b'x')
                raise OSError('stalled')
            with mock.patch.object(soundbank.urllib.request, 'urlopen', side_effect=fake_open):
                self.assertFalse(soundbank._download(dst))
            self.assertEqual(seen['timeouts'], [60] * len(soundbank.SF_URLS))
            self.assertFalse(os.path.exists(dst + '.part'))

    def test_small_file_rejected_and_removed(self):
        import io
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, 'x.sf2')
            with mock.patch.object(soundbank.urllib.request, 'urlopen',
                                   side_effect=lambda url, timeout=None: io.BytesIO(b'tiny')):
                self.assertFalse(soundbank._download(dst))
            self.assertFalse(os.path.exists(dst + '.part'))
            self.assertFalse(os.path.exists(dst))

    def test_good_file_accepted(self):
        import io
        with tempfile.TemporaryDirectory() as d:
            dst = os.path.join(d, 'x.sf2')
            with mock.patch.object(soundbank.urllib.request, 'urlopen',
                                   side_effect=lambda url, timeout=None: io.BytesIO(b'0' * 5_000_001)):
                self.assertTrue(soundbank._download(dst))
            self.assertTrue(os.path.exists(dst))
            self.assertFalse(os.path.exists(dst + '.part'))


class TestCacheKey(unittest.TestCase):
    def test_sfz_libs_in_hashed_code(self):
        self.assertIn('sfz_libs.py', rn._RENDER_CODE)

    def test_sfz_patch_changes_key(self):
        tr = {'name': 'v', 'instrument': 'sfz:lib/Patch', 'notes': []}

        class TM:
            secs = np.arange(4.0)
        with tempfile.TemporaryDirectory() as d:
            patch = Path(d) / 'Patch.sfz'
            patch.write_text('<region>')
            import sfz_libs
            with mock.patch.object(sfz_libs, 'find_patch', return_value=patch):
                k1 = rn._track_cache_key(tr, 1, (4, 4), 0.5, TM(), None, rn.SR)
                patch.write_text('<region> sample=other.wav')
                os.utime(patch, (time.time() + 100, time.time() + 100))
                k2 = rn._track_cache_key(tr, 1, (4, 4), 0.5, TM(), None, rn.SR)
            self.assertNotEqual(k1, k2)
        gm = {'name': 'p', 'instrument': 'piano', 'notes': []}
        self.assertIsNone(rn._sfz_patch_id(gm))


class TestReportReset(unittest.TestCase):
    def test_build_stems_clears_report(self):
        rn.REPORT['ghost'] = {'sfz_fallback': 'stale'}
        score = {'tracks': [], 'ts': [4, 4]}
        with mock.patch.object(rn.hz, 'tempo_map_for', return_value=None):
            try:
                rn.build_stems(score, sfpath='x.sf2', verbose=False)
            except Exception:
                pass
        self.assertNotIn('ghost', rn.REPORT)


class TestCodeHashShared(unittest.TestCase):
    def test_same_as_stem_cache(self):
        rn._CODE_HASH = None
        here = os.path.dirname(os.path.abspath(rn.__file__))
        self.assertEqual(rn._code_hash(), stem_cache.code_hash(here, rn._RENDER_CODE, rn._RENDER_PACKAGES))
        # not identical to the pre-change sha1 digest (blake2b vs sha1): a one-time cache invalidation
        rn._CODE_HASH = None


def _old_mark(tr, tracks):
    if tr.get('role') not in ('melody', 'counter'):
        return tr
    others = [(n['t'], n['t'] + n.get('d', 0)) for o in tracks if o is not tr and o.get('role') != 'drum'
              for n in o.get('notes', [])]
    notes = []
    for n in tr.get('notes', []):
        sounding = any(a <= n['t'] < b for a, b in others)
        notes.append(dict(n, acc=1.0 if sounding else 0.0))
    return dict(tr, notes=notes)


class TestMarkAccompanied(unittest.TestCase):
    def test_equal_to_scan(self):
        rng = np.random.default_rng(3)

        def mk(role, n):
            return {'role': role, 'notes': [{'t': float(round(rng.uniform(0, 30) * 4) / 4), 'd': float(rng.choice([0, 0.25, 1, 4])), 'p': 60}
                                            for _ in range(n)]}
        for _ in range(20):
            tracks = [mk('melody', 40), mk('chord', 30), mk('bass', 20), mk('drum', 20), mk('counter', 10)]
            for tr in tracks:
                self.assertEqual(rn._mark_accompanied(tr, tracks), _old_mark(tr, tracks))
        solo = [mk('melody', 5)]
        self.assertEqual(rn._mark_accompanied(solo[0], solo), _old_mark(solo[0], solo))


class TestCurves(unittest.TestCase):
    def test_curve_at_vector_equals_scalar(self):
        pts = [[0, 0.5], [8, 1.0], [16, 0.7]]
        b = np.linspace(-2, 20, 97)
        old = np.array([float(np.interp(x, [p[0] for p in pts], [p[1] for p in pts])) for x in b])
        np.testing.assert_array_equal(rn.curve_at(pts, b), old)
        np.testing.assert_array_equal(rn.curve_at(rn.curve_arrays(pts), b), old)
        self.assertEqual(rn.curve_at(pts, 3.0), float(np.interp(3.0, [0, 8, 16], [0.5, 1.0, 0.7])))
        self.assertEqual(rn.curve_at(None, 3.0), 1.0)
        self.assertEqual(rn.curve_at([], 3.0), 1.0)

    def test_dict_envelope_equals_loop(self):
        def old(kind, n_steps, dur):
            x = np.linspace(0, 1, n_steps)
            t = x * dur
            atk, dec = float(kind.get('attack_s', 0.05)), float(kind.get('decay_s', 0.1))
            sus, rel = float(kind.get('sustain_level', 0.7)), float(kind.get('release_s', 0.1))
            g = np.ones(n_steps)
            for i, ti in enumerate(t):
                if ti < atk:
                    g[i] = ti / max(atk, 1e-4)
                elif ti < atk + dec:
                    g[i] = 1.0 - (1.0 - sus) * ((ti - atk) / max(dec, 1e-4))
                elif ti < dur - rel:
                    g[i] = sus
                else:
                    g[i] = sus * max(0.0, (dur - ti) / max(rel, 1e-4))
            return np.clip(g, 0.05, 1.0)
        for kind in ({}, {'attack_s': 0.2, 'decay_s': 0.3, 'sustain_level': 0.5, 'release_s': 0.4},
                     {'attack_s': 0.0, 'decay_s': 0.0, 'release_s': 0.0}):
            for dur, n in ((0.02, 2), (0.5, 80), (3.0, 500)):
                np.testing.assert_allclose(rn._expr_curve(kind, n, dur, None), old(kind, n, dur), rtol=0, atol=1e-12)


class TestSfzOnsetLookup(unittest.TestCase):
    def test_note_offs_equal_head_version(self):
        src = subprocess.run(['git', 'show', 'HEAD:scripts/sfz_render.py'], cwd=SK, capture_output=True, text=True).stdout
        if not src:
            self.skipTest('no git history')
        old = type(sys)('sfz_render_head')
        old.__file__ = str(SK / 'scripts' / 'sfz_render.py')
        exec(compile(src, old.__file__, 'exec'), old.__dict__)
        rng = np.random.default_rng(5)
        for art in (None, 'legato', 'sustain'):
            for patch, blk in (('Strings Legato', {}), ('Strings Sustain', {}), ('Strings Legato', {'legato_overlap_s': 0.0})):
                ev = []
                for t in np.sort(rng.uniform(0, 20, 120)):
                    e = dict(t=float(t), dur=float(rng.uniform(0.05, 1.5)), p=int(rng.choice([60, 62, 64, 67])), v=80)
                    if art:
                        e['art'] = art
                    ev.append(e)
                if art is None:
                    pass
                offs = np.array([e['t'] + e['dur'] for e in ev])
                dyn = lambda t: 0.8
                a = old.midi_for(ev, offs, dict(blk), dyn, patch)
                b = sfz_render.midi_for(ev, offs, dict(blk), dyn, patch)
                na = [(n.pitch, n.start, n.end) for n in a.instruments[0].notes]
                nb = [(n.pitch, n.start, n.end) for n in b.instruments[0].notes]
                self.assertEqual(na, nb)
        # events not in time order: the first listed later onset decides, as before
        ev = [dict(t=2.0, dur=3.0, p=60, v=80), dict(t=4.0, dur=1.0, p=60, v=80), dict(t=1.0, dur=3.0, p=60, v=80)]
        offs = np.array([e['t'] + e['dur'] for e in ev])
        a = old.midi_for(ev, offs, {}, lambda t: 0.8, 'x')
        b = sfz_render.midi_for(ev, offs, {}, lambda t: 0.8, 'x')
        self.assertEqual([(n.pitch, n.start, n.end) for n in a.instruments[0].notes],
                         [(n.pitch, n.start, n.end) for n in b.instruments[0].notes])


if __name__ == '__main__':
    unittest.main()
