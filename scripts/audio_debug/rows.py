"""rows.py - which domain owns a gate row, and which rows can never bind.

The engine must not analyse what is not in question, so every row is mapped to one domain by its name and every
domain module is imported only when a row it owns has failed. The advisory rows are named here too: the virtual ears
and the inferred chemistry can WARN or report, never FAIL, so they never justify work.
"""
from __future__ import annotations

# Ordered longest-prefix-first at lookup time; a row belongs to the first domain whose prefix it starts with.
DOMAINS = {
    'master': ('loudness', 'true peak', 'clipping', 'silence', 'clicks', 'master.', 'dc', 'crest',
               'natural_aliasing', 'delivery.standard', 'audio'),
    'stems': ('stem.',),
    'spectral': ('spectral.', 'masking.', 'erb_binaural_masking', 'cochlear_roughness', 'phase.', 'timbre.'),
    'spatial': ('spatial.', 'imm.', 'mix.', 'ambient_glue', 'modulation_flutter', 'depth.', 'width.'),
    'channels': ('delivery.', 'channel.', 'fold.', 'layout.', 'objects.', 'adm.'),
    'hrtf': ('hrtf.', 'binaural.', 'imm_cues'),
    'chem': ('chem.',),
    'ears': ('ear.',),
    'direction': ('focus', 'intent.', 'balance.', 'expression.', 'direction.'),
}

# Rows that report a prediction and cannot fail. They are read for the report and never become a lever problem.
ADVISORY = ('chem.', 'ear.', 'imm.cues', 'modulation_flutter', 'ambient_glue', 'master.micro_dynamics',
            'music21_', 'melodic_', 'harmonic_', 'groove_', 'kinematic_', 'spiral_', 'witek_', 'expr.')

# Rows the engine treats as "in question". WARN is only used when nothing FAILs.
BINDING_LEVELS = ('FAIL',)


def _ordered():
    pairs = [(p, d) for d, prefixes in DOMAINS.items() for p in prefixes]
    return sorted(pairs, key=lambda pd: -len(pd[0]))


def domain_of(row_name):
    """The domain that owns a row, or None when no module claims it."""
    name = (row_name or '').lower()
    for prefix, dom in _ordered():
        if name.startswith(prefix.lower()):
            return dom
    return None


def is_advisory(row_name):
    name = (row_name or '').lower()
    return any(name.startswith(p) for p in ADVISORY)


def domains_for(rows):
    """The domains that own a set of rows, in a stable order."""
    seen = []
    for r in rows:
        d = domain_of(r.get('row'))
        if d and d not in seen:
            seen.append(d)
    return seen


def skipped_domains(rows, run):
    """Domains that own rows but were not run, with the reason. Printed so nothing looks unexamined."""
    out = {}
    for r in rows:
        d = domain_of(r.get('row'))
        if d and d not in run:
            out.setdefault(d, 0)
            out[d] += 1
    return out
