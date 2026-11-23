"""The mixing engine, split by stage.

`core` owns the active-mix context and the settings lookups; `dsp_utils`, `chains`, `placement`,
`theatrical`, `mastering` and `carve` are the stages; `bus` runs them. `meters`, `standards` and
`masking` are the measurement and delivery layer the gate reads.

`scripts/mixer.py` is the facade: it re-exports every name from these modules so existing callers
and tests keep working.
"""
from . import bus, carve, chains, core, dsp_utils, masking, mastering, meters, placement, standards, theatrical

__all__ = ['bus', 'carve', 'chains', 'core', 'dsp_utils', 'masking', 'mastering', 'meters',
           'placement', 'standards', 'theatrical']
