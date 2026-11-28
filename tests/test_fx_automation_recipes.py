"""fx automation (`automate`, `steps`) and recipes ({"chain": name, "start_s", "end_s"}): data-driven, validated, deterministic."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import fx_engine  # noqa: E402
import presets  # noqa: E402

SR = 22050


def _noise(sec=6.0):
    return (0.3 * np.random.default_rng(3).standard_normal(int(SR * sec))).astype(np.float32)


def _swing(y, a, b):
    s = np.abs(y[int(a * SR):int(b * SR), 0])
    w = s[:len(s) // 221 * 221].reshape(-1, 221).max(1)
    return float(w.max() / max(w.min(), 1e-9))


def test_automation_moves_the_parameter():
    t = np.arange(int(SR * 8)) / SR
    x = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    chain = [{'type': 'tremolo', 'start_s': 1, 'end_s': 7, 'automate': {'rate_hz': {'from': 0.5, 'to': 12, 'curve': 'exp'},
                                                                    'depth': [[0, 0.1], [1, 0.9]]}, 'steps': 12}]
    assert fx_engine.problems(chain) == []
    y = fx_engine.apply(x, SR, chain)
    assert np.isfinite(y).all() and _swing(y, 6.0, 6.9) > 2 * _swing(y, 1.1, 2.1)
    assert np.array_equal(y, fx_engine.apply(x, SR, chain))


def test_automation_is_refused_where_it_cannot_work():
    bad = fx_engine.problems([{'type': 'ring_mod', 'automate': {'bogus': {'from': 1, 'to': 2}}},
                              {'type': 'pedalboard', 'plugin': 'Chorus', 'automate': {'a': {'from': 1, 'to': 2}}},
                              {'type': 'tremolo', 'automate': {'rate_hz': {'from': 0.5, 'to': 900}}},
                              {'type': 'tremolo', 'automate': {'rate_hz': [[0.5, 2.0]]}}])
    assert len(bad) == 4 and any('not allowed' in b for b in bad) and any('above the maximum' in b for b in bad)


def test_every_recipe_places_validates_and_changes_the_stem():
    names = fx_engine.recipes()
    assert {'build_riser', 'breathing_sustain', 'impact_bite'} <= set(names)
    x = _noise()
    for name, meta in names.items():
        assert meta['intent'], name
        chain = [{'chain': name, 'start_s': 1.0, 'end_s': 5.0}]
        assert fx_engine.problems(chain) == [], name
        y = fx_engine.apply(x, SR, chain)
        assert np.isfinite(y).all() and np.abs(y - fx_engine.apply(x, SR, [])).max() > 1e-3, name
        assert np.abs(y[:int(0.9 * SR)] - fx_engine.apply(x, SR, [])[:int(0.9 * SR)]).max() < 1e-6, f'{name} leaks before its span'


def test_recipe_keys_are_checked():
    assert any('unknown key' in p for p in fx_engine.problems([{'chain': 'build_riser', 'start_s': 0, 'end_s': 4, 'bogus': 1}]))
    assert any('start_s < end_s' in p for p in fx_engine.problems([{'chain': 'build_riser', 'start_s': 4, 'end_s': 4}]))
    assert any('no chain preset' in p for p in fx_engine.problems([{'chain': 'nope', 'start_s': 0, 'end_s': 4}]))


def test_the_library_and_presets_validate():
    assert fx_engine.library_problems() == []
    assert [p for p in presets.validate() if p.startswith('fx/')] == []
    assert list(fx_engine.recipes('build')) and not fx_engine.recipes('nonexistent_intent')
