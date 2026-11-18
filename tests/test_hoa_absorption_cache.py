"""The absorption-spectrum cache of the reflection taps is bounded by bytes, not by count."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from spatial_engine import hoa

COEFFS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]


class AbsorptionCache(unittest.TestCase):
    def setUp(self):
        hoa._ABS_CACHE.clear()
        self._cap = hoa._ABS_CACHE_BYTES

    def tearDown(self):
        hoa._ABS_CACHE_BYTES = self._cap
        hoa._ABS_CACHE.clear()

    def test_the_cache_never_holds_more_than_its_byte_budget(self):
        hoa._ABS_CACHE_BYTES = 1_000_000
        for size in range(20000, 60000, 2000):           # forty different spans, each about 160-480 kB
            hoa._absorption_response(COEFFS, size, 44100)
            self.assertLessEqual(sum(v.nbytes for v in hoa._ABS_CACHE.values()), 1_000_000)
        self.assertGreater(len(hoa._ABS_CACHE), 0)

    def test_an_entry_larger_than_the_budget_is_computed_but_not_kept(self):
        hoa._ABS_CACHE_BYTES = 1000
        got = hoa._absorption_response(COEFFS, 20000, 44100)
        self.assertEqual(len(got), 20000 // 2 + 1)
        self.assertEqual(len(hoa._ABS_CACHE), 0)

    def test_a_repeat_is_the_same_spectrum(self):
        a = hoa._absorption_response(COEFFS, 4096, 44100)
        b = hoa._absorption_response(COEFFS, 4096, 44100)
        self.assertIs(a, b)

    def test_the_least_recently_used_goes_first(self):
        hoa._ABS_CACHE_BYTES = 3 * (4096 // 2 + 1) * 16 + 10
        for size in (4096, 4098, 4100):
            hoa._absorption_response(COEFFS, size, 44100)
        hoa._absorption_response(COEFFS, 4096, 44100)      # touch the oldest
        hoa._absorption_response(COEFFS, 4102, 44100)      # forces one out
        keys = [k[1] for k in hoa._ABS_CACHE]
        self.assertIn(4096, keys)
        self.assertNotIn(4098, keys)


if __name__ == '__main__':
    unittest.main()


class TempField(unittest.TestCase):
    def test_a_field_on_disk_leaves_no_file_behind_on_posix(self):
        import glob
        import tempfile
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), '*.hoa')))
        old = hoa.IN_RAM_BYTES
        hoa.IN_RAM_BYTES = 1000
        try:
            arr, path = hoa._alloc(2000, 4)
            arr[:10] = 1.0
            self.assertEqual(float(arr[:10].sum()), 40.0)          # ten rows of four columns: still usable
            after = set(glob.glob(os.path.join(tempfile.gettempdir(), '*.hoa')))
            if os.name != 'nt':
                self.assertIsNone(path)
                self.assertEqual(after - before, set())
        finally:
            hoa.IN_RAM_BYTES = old
            del arr
            if path:
                os.remove(path)
