"""The project cache is capped: the oldest files go first, the newest stay."""
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import stem_cache


def make(root, rel, size, age):
    fp = os.path.join(root, rel)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'wb') as fh:
        fh.write(b'x' * size)
    t = time.time() - age
    os.utime(fp, (t, t))
    return fp


class Prune(unittest.TestCase):
    def test_the_oldest_files_go_first_until_it_fits(self):
        with tempfile.TemporaryDirectory() as d:
            old = make(d, 'mix/a/old.npy', 400, 300)
            mid = make(d, 'mix/b/mid.npy', 400, 200)
            new = make(d, 'stems/new.wav', 400, 100)
            freed = stem_cache.prune(d, max_bytes=900)
            self.assertEqual(freed, 400)
            self.assertFalse(os.path.exists(old))
            self.assertTrue(os.path.exists(mid) and os.path.exists(new))
            self.assertFalse(os.path.isdir(os.path.join(d, 'mix', 'a')))        # the emptied key folder is removed

    def test_under_the_cap_nothing_is_removed(self):
        with tempfile.TemporaryDirectory() as d:
            f = make(d, 'x.bin', 100, 10)
            self.assertEqual(stem_cache.prune(d, max_bytes=1000), 0)
            self.assertTrue(os.path.exists(f))

    def test_a_missing_folder_is_not_an_error(self):
        self.assertEqual(stem_cache.prune('/no/such/folder', max_bytes=10), 0)

    def test_the_cap_comes_from_the_environment(self):
        old = os.environ.get('MUSICGEN_CACHE_GB')
        try:
            os.environ['MUSICGEN_CACHE_GB'] = '2.5'
            self.assertEqual(stem_cache.cache_cap_bytes(), 2_500_000_000)
            os.environ['MUSICGEN_CACHE_GB'] = 'abc'
            self.assertEqual(stem_cache.cache_cap_bytes(), int(stem_cache.CACHE_GB_DEFAULT * 1e9))
        finally:
            if old is None:
                os.environ.pop('MUSICGEN_CACHE_GB', None)
            else:
                os.environ['MUSICGEN_CACHE_GB'] = old


if __name__ == '__main__':
    unittest.main()
