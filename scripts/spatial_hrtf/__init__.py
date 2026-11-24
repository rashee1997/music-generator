"""spatial_hrtf - binaural / Ambisonic rendering with measured head data.

Vendored copy of spaudiopy (https://github.com/chris-hld/spaudiopy), MIT licence, (c) 2019 Chris Hold - see LICENSE and
README.md in this folder. The modules decoder, grids, io, parsa, plot, process, sig, sph and utils are theirs; the changes
we made are listed in README.md. binaural.py is ours: the thin layer the mixer calls.
"""
from pathlib import Path

file_dir = Path(__file__).parent.absolute()
__version__ = "vendored from spaudiopy master a75c282 (2026-10-18)"   # upstream asks git for this; no repo here

import importlib

_SUBMODULES = ('binaural', 'data', 'decoder', 'grids', 'io', 'parsa', 'plot', 'process', 'room', 'sph', 'sig', 'utils')
__all__ = list(_SUBMODULES)


def __getattr__(name):
    """Every submodule loads on first use.

    `plot` alone used to be lazy because it imports matplotlib; the rest were eager, so `from spatial_hrtf import sph`
    (the gate's channel rows) dragged in `decoder -> io` and `process`, and a machine without h5py or resampy could
    not run the quality gate at all. A gate that cannot import a helper must still be able to report the rows it can
    measure, so nothing is imported until a caller asks for it.
    """
    if name in _SUBMODULES:
        return importlib.import_module('.' + name, __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
