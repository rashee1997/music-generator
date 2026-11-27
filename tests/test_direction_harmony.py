"""direction.harmony_plan and direction.stinger rows."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import quality_gate as qg   # noqa: E402


def sheet(**kw):
    s = dict(duration_s=60.0, sections=[dict(name='a'), dict(name='b'), dict(name='c')])
    s.update(kw)
    return s


SCORE = {'bpm': 120, 'ts': [4, 4], 'tracks': [dict(name='lead', role='lead', notes=[dict(t=0, d=1, p=60, v=0.8), dict(t=8, d=1, p=62, v=0.8)])]}


class Harmony(unittest.TestCase):
    def rows(self, sh):
        out = []
        qg._harmony_rows(SCORE, sh, out)
        return out

    def test_missing_plan_warns_only_for_a_long_multi_section_piece(self):
        self.assertEqual(self.rows(sheet())[0][:2], ('WARN', 'direction.harmony_plan'))
        self.assertEqual(self.rows(sheet(duration_s=20.0)), [])
        self.assertEqual(self.rows(sheet(sections=[dict(name='a')])), [])

    def test_plan_that_names_changes_passes_and_an_empty_entry_warns(self):
        ok = [dict(section='a', pedal=True, why='the dawn holds one note'), dict(section='b', move='D to G'), dict(section='c', key='E')]
        self.assertEqual(self.rows(sheet(harmony_plan=ok))[0][0], 'PASS')
        bad = [dict(section='a'), dict(section='zzz', move='x')]
        r = self.rows(sheet(harmony_plan=bad))[0]
        self.assertEqual(r[0], 'WARN')
        self.assertIn('zzz', r[2])


class Stinger(unittest.TestCase):
    def rows(self, hits):
        out = []
        qg._stinger_rows(SCORE, dict(hits=hits), out)
        return out

    def test_notes_after_the_hit_break_the_promise(self):
        # the next note starts at 4 s (beat 8 at 120 bpm)
        self.assertEqual(self.rows([dict(t=3.0, kind='cut', silence_after_s=0.8)])[0][0], 'PASS')
        self.assertEqual(self.rows([dict(t=3.0, kind='cut', silence_after_s=1.5)])[0][0], 'WARN')
        self.assertEqual(self.rows([dict(t=3.0, kind='cut', silence_after_s=5.0)])[0][0], 'WARN')

    def test_no_promise_no_row(self):
        self.assertEqual(self.rows([dict(t=3.0, kind='cut')]), [])


if __name__ == '__main__':
    unittest.main()
