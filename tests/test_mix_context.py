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

"""The mixer's configuration is per thread: two pieces mixed at once must not see each other.

The old design kept eight module globals rebound by `_install()`, so whichever piece was installed
last won for every thread. These tests lock in the thread-local behaviour that replaced them.
"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import mix_context  # noqa: E402
import mixer  # noqa: E402


class MixContextIsolation(unittest.TestCase):
    def test_two_threads_read_their_own_mix(self):
        seen, barrier = {}, threading.Barrier(2)

        def work(name, carve, lead_band):
            mix = mix_context.mix_for('default')
            mix['carve_db'] = carve
            mix['lead_band_hz'] = lead_band
            mix['seating'] = {name: -0.5}
            mixer._install(mix, {})
            barrier.wait(timeout=5)            # both threads are inside their own context now
            time.sleep(0.02)
            seen[name] = (mixer._carve_db(), mixer._lead_band_hz(), mixer._seating())

        a = threading.Thread(target=work, args=('a', -3.0, 1500.0))
        b = threading.Thread(target=work, args=('b', -7.0, 3000.0))
        a.start()
        b.start()
        a.join(10)
        b.join(10)
        self.assertEqual(seen['a'][:2], (-3.0, 1500.0))
        self.assertEqual(seen['b'][:2], (-7.0, 3000.0))
        self.assertEqual(seen['a'][2], {'a': -0.5})
        self.assertEqual(seen['b'][2], {'b': -0.5})

    def test_a_new_piece_does_not_inherit_the_previous_one(self):
        mix = mix_context.mix_for('default')
        mix['carve_db'] = -9.0
        mixer._install(mix, {})
        self.assertEqual(mixer._carve_db(), -9.0)
        mixer._install(mix_context.mix_for('default'), {})
        self.assertNotEqual(mixer._carve_db(), -9.0)

    def test_bare_import_reads_the_shipped_defaults(self):
        self.assertIn('gain_staging', mixer._mix())
        self.assertEqual(mixer._space(), {})


if __name__ == '__main__':
    unittest.main()
