"""A sound-effect track's trigger note (p=60, held for the whole effect) is not harmony: the tonal-tension audit must not read it."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import pattern_audit  # noqa: E402
import roles  # noqa: E402


def _score(with_sfx):
    notes = [{'t': float(i), 'd': 1.0, 'p': p, 'v': 0.7} for i, p in enumerate([53, 56, 60, 53] * 8)]
    tracks = [{'name': 'bass', 'instrument': 'x', 'role': 'bass', 'notes': notes}]
    if with_sfx:
        tracks.append({'name': 'engine', 'instrument': 'sfx:engine', 'role': 'fx', 'notes': [{'t': 0.0, 'd': 32.0, 'p': 60, 'v': 1.0}]})
    return {'bpm': 120, 'ts': [4, 4], 'key': 'F', 'mode': 'minor', 'tracks': tracks}


def test_is_sound_effect():
    assert roles.is_sound_effect({'instrument': 'sfx:np_engine'}) and roles.is_sound_effect({'instrument': 'env:rain'})
    assert not roles.is_sound_effect({'instrument': 'qf_horns'}) and not roles.is_sound_effect({})


def test_the_tension_series_ignores_an_sfx_trigger():
    a, b = pattern_audit._spiral_series(_score(False)), pattern_audit._spiral_series(_score(True))
    assert [list(map(float, c)) for c in a[0]] == [list(map(float, c)) for c in b[0]]
    assert a[1] == b[1]
