# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""resources: worker counts follow the cores and the memory, and an environment variable always wins.

Run: python -m unittest tests.test_resources
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import resources  # noqa: E402


class Workers(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop('MUSICGEN_SFZ_WORKERS', None)
        os.environ.pop('GATE_WORKERS', None)

    def tearDown(self):
        self.env.stop()

    def test_plenty_of_memory_uses_every_core(self):
        self.assertEqual(resources.sfz_workers(n_cores=4, free_gb=14.0), 4)

    def test_little_memory_limits_the_samplers_not_the_cores(self):
        self.assertEqual(resources.sfz_workers(n_cores=8, free_gb=7.0), 1)
        self.assertEqual(resources.sfz_workers(n_cores=8, free_gb=9.0), 2)

    def test_never_fewer_than_one(self):
        self.assertEqual(resources.sfz_workers(n_cores=4, free_gb=0.5), 1)

    def test_never_more_than_the_jobs(self):
        self.assertEqual(resources.sfz_workers(n_jobs=2, n_cores=16, free_gb=60.0), 2)

    def test_the_environment_variable_wins(self):
        os.environ['MUSICGEN_SFZ_WORKERS'] = '3'
        self.assertEqual(resources.sfz_workers(n_cores=1, free_gb=1.0), 3)
        self.assertEqual(resources.sfz_workers(n_jobs=2, n_cores=1, free_gb=1.0), 2)

    def test_gate_threads_follow_the_cores(self):
        self.assertEqual(resources.gate_workers(n_cores=1), 2)
        self.assertEqual(resources.gate_workers(n_cores=4), 3)
        self.assertEqual(resources.gate_workers(n_cores=32), 8)
        os.environ['GATE_WORKERS'] = '5'
        self.assertEqual(resources.gate_workers(n_cores=4), 5)


class Memory(unittest.TestCase):
    def test_a_container_limit_caps_free_memory(self):
        self.assertEqual(resources.available_gb(meminfo=14.0, limit=6.0), 6.0)

    def test_no_limit_uses_free_memory(self):
        self.assertEqual(resources.available_gb(meminfo=14.0, limit=0.0), 14.0)

    def test_the_real_machine_reports_something_sane(self):
        self.assertGreaterEqual(resources.cores(), 1)
        self.assertGreater(resources.available_gb(), 0.0)
        self.assertIn('core(s)', resources.summary())


if __name__ == '__main__':
    unittest.main()
