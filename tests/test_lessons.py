"""The lessons files parse, stay small, and the finder returns the right entry."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import lessons  # noqa: E402


def test_check_passes():
    assert lessons.check() == []


def test_find_known_symptom():
    ids = [l['id'] for _, l in lessons.find('stem.dropout 35 ms hole after a rest')]
    assert 'S03' in ids


def test_find_by_row():
    assert lessons.find('', ['stem.dead'])


def test_unknown_text_finds_nothing():
    assert lessons.find('zzqx wqvv plorb') == []


def test_duplicate_add_refused(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'lessons.py'), 'add', '--section', 'gate-stem-rows', '--title', 'x',
                        '--keywords', 'stem.dropout,hole,humanizer,articulation gate', '--symptom', 's', '--fix', 'f'],
                       capture_output=True, text=True)
    assert r.returncode == 1 and 'already covers' in r.stderr
