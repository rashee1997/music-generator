"""spatial_hrtf - binaural / Ambisonic rendering with measured head data.

Vendored copy of spaudiopy (https://github.com/chris-hld/spaudiopy), MIT licence, (c) 2019 Chris Hold - see LICENSE and
README.md in this folder. The modules decoder, grids, io, parsa, plot, process, sig, sph and utils are theirs; the changes
we made are listed in README.md. binaural.py is ours: the thin layer the mixer calls.
"""
from pathlib import Path

file_dir = Path(__file__).parent.absolute()
__version__ = "vendored from spaudiopy master a75c282 (2026-10-18)"   # upstream asks git for this; no repo here

from . import decoder
from . import grids
from . import io
from . import plot
from . import process
from . import parsa
from . import sph
from . import sig
from . import utils
