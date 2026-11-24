"""Mix and master stems: the public surface of `mix_engine`.

The engine itself lives in `scripts/mix_engine/`, one module per stage, in dependency order:

    core.py        the active mix context, preset lookup, role targets (no audio)
    dsp_utils.py   signal helpers: loudness, true peak, width, reverb, ducking
    chains.py      per-role EQ/compression chains, gain staging, the stem cache
    placement.py   where a stem sits: distance, pan, reverb send, heights
    theatrical.py  theatrical and immersive beds
    mastering.py   the master chain and its measurements
    carve.py       the lead carve (static and measured masking modes)
    bus.py         mix_stems, mix_and_master, main()

This module re-exports every name from those modules, so `import mixer` and `mixer.foo(...)` keep
working for callers that predate the split. Tests that patch a name here (for example
`mixer._space_owned`) are honoured: the engine asks this module's copy at call time.
"""
import types

from mix_engine import bus as _bus
from mix_engine import carve as _carve
from mix_engine import chains as _chains
from mix_engine import core as _core
from mix_engine import dsp_utils as _dsp_utils
from mix_engine import mastering as _mastering
from mix_engine import placement as _placement
from mix_engine import theatrical as _theatrical

_MODULES = (_core, _dsp_utils, _chains, _placement, _theatrical, _mastering, _carve, _bus)
_SKIP = {'annotations'}

for _module in _MODULES:
    for _name, _value in vars(_module).items():
        if _name.startswith('__') or _name in _SKIP or isinstance(_value, types.ModuleType):
            continue          # imported modules (numpy, os, ...) are not part of the mixer's surface
        globals()[_name] = _value

# what `from mixer import *` gives: the API, not helpers and not imported modules. Underscore names stay reachable
# as attributes (`mixer._space_owned`) because tests patch this module's copy; they are simply not star-imported.
__all__ = sorted(n for n, _v in globals().items()
                 if not n.startswith('_') and not isinstance(_v, types.ModuleType))

del _module, _name, _value

if __name__ == '__main__':
    from mix_engine.bus import main

    main()
