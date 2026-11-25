"""M0: the shipped Earth presets render to their frozen sound. Every later Immersive 3.3 change must keep this green
(or regenerate the baseline on purpose, in its own commit)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biome_baseline as bb  # noqa: E402


class Baseline(unittest.TestCase):
    def test_the_manifest_covers_every_shipped_environment_and_call(self):
        rows = bb.verify()
        self.assertEqual([r for r in rows if r[0] in ('NEW', 'MISSING')], [])
        self.assertGreaterEqual(len(rows), 12)           # 4 environments + 8 calls at the time of writing

    def test_every_target_is_the_frozen_sound(self):
        bad = [r for r in bb.verify() if r[0] not in ('PASS', 'CLOSE')]
        self.assertEqual(bad, [])

    def test_a_render_is_reproducible_run_to_run(self):
        t = bb.targets()[0]
        self.assertEqual(bb._digest(bb.build(t)), bb._digest(bb.build(t)))

    def test_the_check_can_fail(self):
        import numpy as np
        x = bb.build(bb.targets()[0])
        self.assertNotEqual(bb._digest(x), bb._digest(x * np.float32(0.5)))


if __name__ == '__main__':
    unittest.main()
