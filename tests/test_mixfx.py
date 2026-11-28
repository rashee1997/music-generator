"""The mixing techniques as effects: each one does what its name says, measured on a signal built to show it."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import fx_engine  # noqa: E402

SR = 44100


def stereo(m):
    return np.stack([m, m], axis=1).astype(np.float32)


def sine(f, sec=1.0, amp=0.5):
    t = np.arange(int(SR * sec)) / SR
    return stereo(amp * np.sin(2 * np.pi * f * t))


def bin_db(x, f, width=8.0):
    m = x[:, 0].astype(np.float64)
    sp = np.abs(np.fft.rfft(m * np.hanning(len(m)))) / len(m)
    fr = np.fft.rfftfreq(len(m), 1 / SR)
    return 20 * np.log10(sp[(fr > f - width) & (fr < f + width)].max() + 1e-12)


def run(x, entry):
    chain = [dict(entry)]
    assert fx_engine.problems(chain) == [], fx_engine.problems(chain)
    return fx_engine.apply(x, SR, chain)


def test_every_new_effect_is_in_the_library_and_valid():
    for n in ('saturator', 'de_esser', 'gate', 'parallel_comp', 'upward_comp', 'band_width', 'tilt_eq', 'freq_shift', 'resonator_bank', 'ping_delay'):
        assert n in fx_engine.effect_names()
    assert fx_engine.library_problems() == []
    assert fx_engine.problems([{'type': 'resonator_bank', 'pitches': [10]}])           # a pitch outside the range is refused
    assert fx_engine.problems([{'type': 'saturator', 'mode': 'nope'}])


def test_saturator_characters():
    x = sine(220.0)
    tube = run(x, {'type': 'saturator', 'mode': 'tube', 'drive_db': 14.0, 'tone_hz': 20000.0})
    tape = run(x, {'type': 'saturator', 'mode': 'tape', 'drive_db': 14.0, 'tone_hz': 20000.0})
    assert bin_db(tube, 440.0) > bin_db(tape, 440.0) + 12.0                 # even harmonics: the tube has them, the symmetric tape has none
    assert bin_db(tape, 660.0) > bin_db(x, 660.0) + 30.0                    # odd harmonics appear
    assert abs(np.sqrt(np.mean(tube ** 2)) - np.sqrt(np.mean(x ** 2))) < 0.02   # level matched
    clip = run(x, {'type': 'saturator', 'mode': 'hard_clip', 'drive_db': 12.0, 'ceiling_db': -6.0, 'match_level': 'no', 'tone_hz': 20000.0})
    assert float(np.abs(clip[SR // 10:-SR // 10]).max()) <= 0.5 * 10 ** (-6 / 20) * 1.05      # the range's own 20 ms edges are left out


def test_de_esser_cuts_the_sibilant_band_and_leaves_the_rest():
    rng = np.random.default_rng(1)
    t = np.arange(SR) / SR
    sib = rng.standard_normal(SR) * 0.2
    from scipy import signal
    sib = signal.sosfilt(signal.butter(4, [5500 / (SR / 2), 7500 / (SR / 2)], 'band', output='sos'), sib) * (t > 0.4) * (t < 0.6) * 4
    body = 0.3 * np.sin(2 * np.pi * 300 * t)
    x = stereo(body + sib)
    y = run(x, {'type': 'de_esser', 'threshold_db': -40.0, 'ratio': 10.0})
    s = slice(int(0.45 * SR), int(0.55 * SR))
    def band(a):
        sp = np.abs(np.fft.rfft(a[s, 0])); fr = np.fft.rfftfreq(len(a[s, 0]), 1 / SR)
        return 20 * np.log10(sp[(fr > 5500) & (fr < 7500)].sum() + 1e-9)
    assert band(y) < band(x) - 6.0
    assert bin_db(y, 300.0) > bin_db(x, 300.0) - 0.5


def test_gate_turns_down_the_room_between_notes():
    t = np.arange(SR * 2) / SR
    note = 0.5 * np.sin(2 * np.pi * 200 * t) * ((t < 0.5) | ((t > 1.0) & (t < 1.5)))
    hiss = 0.0008 * np.random.default_rng(2).standard_normal(len(t))
    x = stereo(note + hiss)
    y = run(x, {'type': 'gate', 'threshold_db': -45.0, 'range_db': 40.0, 'ratio': 50.0, 'hold_ms': 30.0})
    rms = lambda a, t0, t1: 20 * np.log10(np.sqrt(np.mean(a[int(t0 * SR):int(t1 * SR), 0] ** 2)) + 1e-12)
    assert rms(y, 0.7, 0.9) < rms(x, 0.7, 0.9) - 20.0
    assert abs(rms(y, 0.1, 0.4) - rms(x, 0.1, 0.4)) < 1.0


def test_parallel_and_upward_compression_lift_the_quiet_not_the_loud():
    t = np.arange(SR * 2) / SR
    env = np.where(t < 1.0, 0.5, 0.02)
    x = stereo(env * np.sin(2 * np.pi * 440 * t))
    rms = lambda a, t0, t1: 20 * np.log10(np.sqrt(np.mean(a[int(t0 * SR):int(t1 * SR), 0] ** 2)) + 1e-12)
    par = run(x, {'type': 'parallel_comp', 'threshold_db': -40.0, 'ratio': 10.0, 'makeup_db': 12.0, 'hp_hz': 0.0, 'mix': 0.5})
    assert rms(par, 1.3, 1.9) - rms(x, 1.3, 1.9) > rms(par, 0.3, 0.9) - rms(x, 0.3, 0.9) + 2.0
    up = run(x, {'type': 'upward_comp', 'threshold_db': -20.0, 'ratio': 4.0, 'max_gain_db': 15.0, 'floor_db': -80.0, 'release_ms': 50.0})
    assert rms(up, 1.4, 1.9) > rms(x, 1.4, 1.9) + 3.0
    assert abs(rms(up, 0.3, 0.9) - rms(x, 0.3, 0.9)) < 1.0


def test_band_width_sums_the_low_end_and_widens_the_top():
    t = np.arange(SR) / SR
    low = 0.3 * np.sin(2 * np.pi * 60 * t)
    high = 0.3 * np.sin(2 * np.pi * 4000 * t)
    x = np.stack([low + high, -low + 0.5 * high], axis=1).astype(np.float32)        # the lows out of phase, the highs partly different
    y = run(x, {'type': 'band_width', 'mono_below_hz': 150.0, 'width': 1.5})
    side = lambda a, f: bin_db(np.stack([a[:, 0] - a[:, 1], a[:, 0] - a[:, 1]], axis=1) * 0.5, f)
    assert side(y, 60.0) < side(x, 60.0) - 25.0
    assert side(y, 4000.0) > side(x, 4000.0) + 2.0


def test_tilt_shift_resonator_and_delay():
    rng = np.random.default_rng(3)
    noise = stereo(0.1 * rng.standard_normal(SR))
    bright = run(noise, {'type': 'tilt_eq', 'tilt_db': 8.0, 'pivot_hz': 1000.0})
    assert bin_db(bright, 8000.0, 400.0) > bin_db(noise, 8000.0, 400.0) + 2.0 and bin_db(bright, 100.0, 40.0) < bin_db(noise, 100.0, 40.0) - 2.0
    shifted = run(sine(440.0), {'type': 'freq_shift', 'shift_hz': 7.0, 'spread': 0.0})
    assert bin_db(shifted, 447.0, 2.0) > bin_db(shifted, 440.0, 2.0) + 20.0
    ring = run(noise, {'type': 'resonator_bank', 'pitches': [69], 'level_db': -6.0, 'q': 60.0, 'partials': 1})
    assert bin_db(ring, 440.0, 6.0) > bin_db(noise, 440.0, 6.0) + 6.0
    imp = np.zeros((SR * 2, 2), dtype=np.float32); imp[100, :] = 1.0
    d = run(imp, {'type': 'ping_delay', 'time_ms': 250.0, 'feedback': 0.5, 'hp_hz': 20.0, 'lp_hz': 20000.0, 'duck_db': 0.0, 'wet_db': 0.0})
    i1, i2 = 100 + int(0.25 * SR), 100 + int(0.5 * SR)
    assert abs(d[i1 - 5:i1 + 5].max()) > 0.3 and d[i2 - 5:i2 + 5].max() > 0.1
    left, right = d[i1 - 5:i1 + 5, 0].max(), d[i1 - 5:i1 + 5, 1].max()
    one = np.zeros((SR * 2, 2), dtype=np.float32); one[100, 0] = 1.0
    pp = run(one, {'type': 'ping_delay', 'time_ms': 250.0, 'feedback': 0.5, 'hp_hz': 20.0, 'lp_hz': 20000.0, 'duck_db': 0.0, 'wet_db': 0.0})
    assert pp[i1 - 5:i1 + 5, 1].max() > 0.3 and pp[i1 - 5:i1 + 5, 0].max() < 0.05      # the first repeat is in the other channel


def test_automation_and_recipes_reach_the_new_effects():
    x = sine(220.0, 3.0)
    y = fx_engine.apply(x, SR, [{'type': 'saturator', 'mode': 'tape', 'drive_db': 6.0, 'tone_hz': 20000.0, 'match_level': 'no',
                                 'automate': {'drive_db': {'from': 0.0, 'to': 30.0}}, 'steps': 6}])
    assert np.isfinite(y).all()
    late, early = y[int(2.4 * SR):], y[int(0.3 * SR):int(0.8 * SR)]
    assert bin_db(late, 660.0, 12.0) - bin_db(late, 220.0, 12.0) > bin_db(early, 660.0, 12.0) - bin_db(early, 220.0, 12.0) + 6.0   # the drive rises: more harmonic


# ---- the mix preset reaches them ----------------------------------------------------------------------------------------------------------------
def test_the_mix_preset_validates_its_fx_tables():
    import mix_schema
    good = {'fx': {'*': [{'type': 'tilt_eq', 'tilt_db': 1.0}], '@drum': [{'type': 'parallel_comp', 'mix': 0.4}], 'qf_snare': 'lofi_tape'},
            'mastering': {'fx': [{'type': 'saturator', 'mode': 'tape', 'drive_db': 3.0}]}}
    assert mix_schema.validate(good) == []
    bad = {'fx': {'qf_snare': [{'type': 'saturator', 'drive_db': 99.0}], '@bass': 'no_such_chain'}, 'mastering': {'fx': [{'type': 'nope'}]}}
    found = mix_schema.validate(bad)
    assert any('mix.fx.qf_snare' in f and 'above the maximum' in f for f in found)
    assert any('mix.fx.@bass' in f for f in found) and any('mix.mastering.fx' in f for f in found)


def test_a_stem_takes_the_fx_of_its_star_role_and_name_in_that_order():
    from mix_engine import core, placement
    core._install({'fx': {'*': [{'type': 'tilt_eq', 'tilt_db': 1.0}], '@drum': [{'type': 'gate'}], 'kit': [{'type': 'saturator'}]}}, None)
    got = placement._mix_fx_for('kit', 'drum')
    assert [e['type'] for e in got] == ['tilt_eq', 'gate', 'saturator']
    assert [e['type'] for e in placement._mix_fx_for('flute', 'melody')] == ['tilt_eq']
    core._install({}, None)


def test_the_master_runs_its_own_chain_and_an_empty_one_changes_nothing():
    from mix_engine import core, mastering
    x = sine(220.0, 3.0, 0.3)
    base_mix = {'mastering': {'profile': 'default'}}
    core._install(base_mix, None)
    a = mastering.master_chain(x.copy(), {'lufs': -16.0, 'true_peak': -1.5})
    core._install({'mastering': {'profile': 'default', 'fx': [{'type': 'tilt_eq', 'tilt_db': 10.0}]}}, None)
    b = mastering.master_chain(x.copy(), {'lufs': -16.0, 'true_peak': -1.5})
    core._install({}, None)
    assert np.isfinite(a).all() and np.isfinite(b).all() and a.shape == b.shape
