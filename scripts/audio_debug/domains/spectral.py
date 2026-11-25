"""spectral.py - the band rows: equal loudness, band folds, masking, roughness.

These rows are mostly ratios, and a ratio does not move when a stem's trim moves; only a change inside the band the
row measures does. That is why the coefficient here is a measured energy share of the EQ band that covers the row's
band, and why a trim-only change is reported as having no effect on these rows.
"""
from __future__ import annotations

from .. import catalog, margins
from . import base


def analyse(case, rows, history=()):
    stems = sorted({r.get('stem') for r in rows if r.get('stem')})
    levers = catalog.eq_levers(case, 'spectral', stems or None) + catalog.gain_levers(case, 'spectral', stems or None)
    coef, notes = {}, []
    for r in rows:
        key = margins.row_key(r)
        band = margins.band_of(r)
        if not band:
            notes.append(f"{r['row']}: no band in the profile or the detail, so no EQ lever can be priced")
            continue
        for lv in levers:
            if lv.kind == 'eq':
                share = catalog.band_share_for(case, lv, r)
                if share:
                    coef[(key, lv.id)] = share      # the band moves by gain x the share of the row's energy it covers
            elif lv.kind == 'gain':
                coef[(key, lv.id)] = 0.0            # a ratio row cancels a stem trim; recorded so it is not retried
        notes.append(f"{r['row']} measures {band[0]:.0f}-{band[1]:.0f} Hz; a trim of its stem cannot move it "
                     f"(the row is a ratio), only a band that overlaps those frequencies")
    return base.Analysis(rows=rows, levers=levers, coefficients=coef, notes=notes,
                         measured=[r['row'] for r in rows])
