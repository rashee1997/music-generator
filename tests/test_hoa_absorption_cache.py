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
        one = hoa._absorption_response(COEFFS, 4096, 44100).nbytes
        hoa._ABS_CACHE.clear()
        hoa._ABS_CACHE_BYTES = 3 * one + 10
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


class WorkersFit(unittest.TestCase):
    def bus(self):
        return hoa.HoaBus(44100, 5, 'binaural', {}, {}, {})

    def test_a_small_machine_gets_one_worker_and_a_big_one_gets_more(self):
        b, n = self.bus(), 44100 * 180
        self.assertEqual(b.workers_that_fit(n, free_bytes=2 * 1024 ** 3), 1)          # less than the headroom: one, never zero
        self.assertEqual(b.workers_that_fit(n, free_bytes=4 * 1024 ** 3), 1)
        many = b.workers_that_fit(n, free_bytes=64 * 1024 ** 3)
        self.assertGreater(many, 4)
        self.assertGreaterEqual(b.workers_that_fit(n, free_bytes=32 * 1024 ** 3), b.workers_that_fit(n, free_bytes=16 * 1024 ** 3))

    def test_a_longer_piece_fits_fewer_workers(self):
        b = self.bus()
        free = 16 * 1024 ** 3
        self.assertGreaterEqual(b.workers_that_fit(44100 * 60, free_bytes=free), b.workers_that_fit(44100 * 600, free_bytes=free))


class WindowedRoom(unittest.TestCase):
    def test_window_span_covers_the_window_and_its_padding(self):
        import numpy as np
        w = np.zeros(44100 * 20)
        w[44100 * 5:44100 * 8] = 1.0
        a, b = hoa.window_span(w, 44100)
        self.assertLessEqual(a, 44100 * 5 - int(hoa.SPAN_LEAD_S * 44100) + 1)
        self.assertGreaterEqual(b, 44100 * 8 + int(hoa.SPAN_PAD_S * 44100) - 1)
        self.assertEqual(hoa.window_span(np.zeros(1000), 44100), (0, 0))
        self.assertEqual(hoa.window_span(np.ones(1000), 44100), (0, 1000))

    def test_rendering_only_the_window_equals_rendering_all_of_it(self):
        import json
        import numpy as np
        refl = json.load(open(os.path.join(ROOT, 'projects', 'palace_chase', 'presets', 'spaces', 'palace_room.json')))['reflections']
        sr, n = 44100, 44100 * 8
        rng = np.random.default_rng(3)
        raw = rng.standard_normal(n)
        w = np.zeros(n)
        w[sr * 3:sr * 4] = 1.0
        feed = raw * w
        bus = hoa.HoaBus(sr, 3, 'binaural', {}, {}, {})
        full = np.zeros((n, bus.k), np.float32)
        bus._reflections(full, feed, refl, 30.0, 0.0, 4.0, None, 0.0, 20.0, 50.0)
        a, b = hoa.window_span(w, sr)
        part = np.zeros((n, bus.k), np.float32)
        bus._reflections(part[a:b], feed[a:b], refl, 30.0, 0.0, 4.0, None, 0.0, 20.0, 50.0)
        self.assertGreater(float(np.abs(full).max()), 1e-3)
        scale = float(np.abs(full).max())
        self.assertLess(float(np.abs(full - part).max()) / scale, 2e-3)
