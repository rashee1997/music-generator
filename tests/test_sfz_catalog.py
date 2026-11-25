"""The optional SFZ library catalog: every entry validates, a track can name alternatives, and a missing library falls back."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import sfz_catalog
import sfz_libs


def make_lib(project, name, patch):
    """A fake installed library: libs/sfz/<name>/<patch>.sfz (the registry entry's `entry` is '.' for the manual libraries)."""
    e = sfz_libs.get_entry(name, 'library')
    d = sfz_libs.entry_dir(sfz_libs.libs_root(project), name, e)
    p = d / (patch + '.sfz')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('<region> sample=x.wav\n', encoding='utf-8')
    return p


class CatalogTest(unittest.TestCase):
    def test_registry_is_valid(self):
        self.assertEqual(sfz_libs.registry_problems() if hasattr(sfz_libs, 'registry_problems') else [], [])
        for n, e in sfz_libs.registry().items():
            self.assertEqual(sfz_libs.entry_problems(n, e), [], n)

    def test_at_least_twelve_libraries(self):
        libs = sfz_catalog.catalog()
        self.assertGreaterEqual(len(libs), 12)
        for n, e in libs.items():
            self.assertTrue(e.get('licence'), n)
            self.assertTrue(str(e.get('homepage', '')).startswith('https://'), n)
            self.assertTrue(e.get('attribution'), n)
            self.assertTrue(e.get('families'), n)
            self.assertIsInstance(e.get('verified'), bool, n)

    def test_every_family_has_an_alternative(self):
        for fam in ('piano', 'strings', 'drums'):
            self.assertGreaterEqual(len(sfz_catalog.rows(family=fam)), 2, fam)

    def test_filters(self):
        self.assertTrue(all('piano' in r['families'] for r in sfz_catalog.rows(family='piano')))
        self.assertTrue(all('cc0' in r['licence'].lower() for r in sfz_catalog.rows(licence='cc0')))
        self.assertIn('salamander', sfz_catalog.search(['piano']))

    def test_family_of(self):
        self.assertEqual(sfz_catalog.family_of('Strings - Notation/1st Violins Legato'), 'strings')
        self.assertEqual(sfz_catalog.family_of('Percussion/Timpani'), 'percussion')
        self.assertIsNone(sfz_catalog.family_of('zzz'))


class FallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = self.tmp.name
        self.blk = {'library': 'sso', 'patch': 'Strings/Violins', 'cc': 'expression',
                    'alternatives': [{'library': 'vcsl', 'patch': 'Strings/Violin'}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_none_installed_raises_with_every_reason(self):
        with self.assertRaises(LookupError) as cm:
            sfz_libs.effective_block(self.blk, self.project)
        self.assertIn('sso', str(cm.exception))
        self.assertIn('vcsl', str(cm.exception))

    def test_own_library_wins(self):
        make_lib(self.project, 'sso', 'Strings/Violins')
        make_lib(self.project, 'vcsl', 'Strings/Violin')
        eff = sfz_libs.effective_block(self.blk, self.project)
        self.assertEqual((eff['library'], eff['patch']), ('sso', 'Strings/Violins'))
        self.assertNotIn('alternatives', eff)

    def test_alternative_plays_when_the_first_is_missing(self):
        make_lib(self.project, 'vcsl', 'Strings/Violin')
        eff = sfz_libs.effective_block(self.blk, self.project)
        self.assertEqual((eff['library'], eff['patch']), ('vcsl', 'Strings/Violin'))
        self.assertEqual(eff['cc'], 'expression')                                      # every other setting stays

    def test_block_without_alternatives_behaves_as_before(self):
        blk = {'library': 'sso', 'patch': 'Strings/Violins'}
        with self.assertRaises(LookupError):
            sfz_libs.effective_block(blk, self.project)
        make_lib(self.project, 'sso', 'Strings/Violins')
        self.assertEqual(sfz_libs.effective_block(blk, self.project)['library'], 'sso')

    def test_recommend_lists_candidates_for_a_missing_track(self):
        score = {'tracks': [{'name': 'violins', 'sfz': self.blk}]}
        need = sfz_catalog.needs(score, self.project)
        self.assertEqual(need[0][2], 'missing')
        rec = sfz_catalog.recommend(score, self.project)
        self.assertEqual(rec[0]['track'], 'violins')
        self.assertTrue(rec[0]['candidates'])
        make_lib(self.project, 'vcsl', 'Strings/Violin')
        self.assertEqual(sfz_catalog.recommend(score, self.project), [])

    def test_sfz_problems_names_the_catalog_command(self):
        score = {'tracks': [{'name': 'violins', 'sfz': self.blk}]}
        out = sfz_libs.sfz_problems(score, self.project)
        self.assertTrue(any('sfz_catalog.py recommend' in m for m in out))

    def test_add_alternative_is_idempotent(self):
        p = Path(self.project) / 'inst.json'
        p.write_text(json.dumps({'name': 'x', 'sfz': {'library': 'sso', 'patch': 'a/b'}}), encoding='utf-8')
        sfz_catalog.add_alternative(str(p), 'vpo', 'x/y')
        alts = sfz_catalog.add_alternative(str(p), 'vpo', 'x/y')
        self.assertEqual(alts, [{'library': 'vpo', 'patch': 'x/y'}])
        with self.assertRaises(SystemExit):
            sfz_catalog.add_alternative(str(p), 'no_such_library', 'x/y')


if __name__ == '__main__':
    unittest.main()
