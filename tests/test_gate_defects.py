"""Every injected defect reaches its own row on both stages; nothing is missed, and the clean baseline is clean."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, HERE)

import gate_defects  # noqa: E402


class DefectMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = gate_defects.run_matrix()

    def test_no_injection_is_missed(self):
        print('\n' + gate_defects.markdown(self.matrix))
        self.assertEqual(self.matrix['missed'], [], gate_defects.markdown(self.matrix))

    def test_the_clean_baseline_has_no_fail(self):
        self.assertEqual(self.matrix['baseline_fails'], 0)

    def test_every_case_names_a_row(self):
        for r in self.matrix['rows']:
            if r['expect'] != 'none':
                self.assertIn(r['expect'], r['rows_failed'] + [r['expect']], r)


if __name__ == '__main__':
    unittest.main()
