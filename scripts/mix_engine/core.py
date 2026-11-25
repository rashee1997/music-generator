"""core - part of the mixing engine (see scripts/mix_engine/__init__.py)."""
from __future__ import annotations

import mix_context
import mix_schema
import presets

SR = 44100

REF_LUFS = -24.0

ROOMS = {
    #            rt60  predelay(ms) HF-decay-factor  early-reflection level
    'dry':        (0.25, 0, 0.7, 0.0),
    'studio':     (0.55, 6, 0.75, 0.5),
    'room_warm':  (0.85, 8, 0.55, 0.5),
    'chamber':    (1.2, 12, 0.65, 0.5),
    'plate':      (1.8, 4, 0.85, 0.0),
    'hall':       (2.3, 24, 0.55, 0.4),
    'forest_canopy': (2.8, 18, 0.45, 0.35),
    'large_hall': (3.2, 34, 0.5, 0.35),
    'cathedral':  (5.2, 45, 0.45, 0.3),
    'cave':       (6.5, 60, 0.35, 0.2),
}

_FALLBACK_MIX = mix_schema.with_defaults(presets.mix())   # what a bare import reads, with no context

DEFAULT_ACTIVE_DB = -55.0

DEFAULT_MAX_BOOST_DB = 12.0

DEFAULT_LEAD_BAND_HZ = 2000.0

DEFAULT_CARVE_DB = -4.0

STATE = {}           # the last mix: processed stems, sends, per-track gain, master measures, diagnostics


def _mix():
    """The mix preset of the piece being mixed on this thread (never another thread's)."""
    ctx = mix_context.current()
    return ctx.mix if ctx is not None else _FALLBACK_MIX


def _space():
    """The space preset of the piece being mixed on this thread."""
    ctx = mix_context.current()
    return (ctx.space if ctx is not None else None) or {}


def _gs():
    return _mix().get('gain_staging') or {}


def _active_db():
    return float(_gs().get('active_db', _mix().get('active_db', DEFAULT_ACTIVE_DB)))


def _max_boost_db():
    return float(_gs().get('max_boost_db', _mix().get('max_boost_db', DEFAULT_MAX_BOOST_DB)))


def _seating():
    return _mix().get('seating') or {}


def _widen_by_role():
    return _mix().get('widen_by_role') or {}


def _level_by_role():
    return _mix().get('level_by_role') or {}


def _lead_band_hz():
    return float(_mix().get('lead_band_hz', DEFAULT_LEAD_BAND_HZ))


def _carve_db():
    return float(_mix().get('carve_db', DEFAULT_CARVE_DB))


def _install(mix, space=None, ctx=None):
    """Make `mix` (and `space`) the active configuration for THIS THREAD, and return `mix`.

    The resolved values live in the thread-local MixContext, not in module globals: two pieces
    mixed in two threads each read their own preset, and nothing carries over from the piece mixed
    before. A bare import (no context installed) reads the shipped defaults.
    """
    if ctx is None:
        ctx = mix_context.MixContext(mix, {} if space is None else space,
                                     name=str(mix.get('name') or 'default'))
    mix_context.make_current(ctx)
    for key, val in mix_schema.inert_dynamics(mix):
        print(f'  [WARN] mix.dynamics.{key} = {val!r} has no effect with engine "pedalboard" (a four-knob compressor): set '
              f'mix.dynamics.engine to "dsp" to use it, or remove the key', flush=True)
    return mix


def release_stems():
    """Drop the mixed audio arrays; the measures, specs and rows stay for the report.

    `STATE['processed']` is what the gate measures, so it lives until Stage 6 has run. After that it is
    the largest thing this module holds (two float32 stereo buffers per stem) and nothing reads it again.
    """
    STATE.pop('processed', None)
    STATE.pop('sends', None)


def reset_context():
    """Forget this thread's context: later reads fall back to the shipped defaults."""
    mix_context.make_current(None)


def _context_for(score, ctx=None):
    """Resolve (or accept) this piece's context and make it the active one."""
    if ctx is None or ctx is not mix_context.current():
        ctx = ctx or mix_context.resolve(score, space_resolver=resolve_space)
    _install(ctx.mix, ctx.space, ctx)      # idempotent: the same context, this thread's copy
    return ctx


def use_mix(name=None, space=None):
    """Make `name` the active mix preset: the default with that preset laid over it, so a preset only lists
    what differs. name=None or 'default' restores the default. Returns the resolved mix dict."""
    mix = mix_context.mix_for(name or 'default')
    cur = mix_context.current()
    sp = (cur.space if space is None and cur is not None else space) or {}
    ctx = mix_context.MixContext(mix, sp, name=name or 'default', space_owned=_space_owned(sp))
    _install(mix, sp, ctx)
    return mix


def resolve_space(name):
    """A space preset by name (the project's, else the shipped one), else a built-in ROOMS entry as a
    minimal preset, else {}."""
    if isinstance(name, dict):
        return name
    cfg = presets.find_space(name) if name else None
    if cfg:
        return cfg
    if name in ROOMS:
        r = ROOMS[name]
        return dict(room=dict(rt60=r[0], pre_delay_ms=r[1], hf_decay=r[2], early_level=r[3]))
    return {}


def _space_owned(cfg):
    """True when the space preset lives in the project (a shipped one is only a fallback)."""
    return mix_context.space_owned(cfg)


def _space_owned_hook(space):
    """Ask the facade first, so a test that patches `mixer._space_owned` still changes the decision."""
    import mixer
    fn = getattr(mixer, '_space_owned', None)
    return fn(space) if fn is not None else _space_owned(space)
