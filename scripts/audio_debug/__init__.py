"""audio_debug - the measurement side of one render, as a solvable system.

The gate answers "did it pass". This package answers "what would make every row pass at once, what cannot, and which
of these moves has already been tried", and it answers it without rendering anything.

    import audio_debug
    case = audio_debug.Case.load('projects/<piece>')
    rep = audio_debug.autopsy(case)          # runs only the domains that own a failing row
    print(rep.text)                          # also written to <project>/reports/debug_audio.md

Modules
    artifacts   one render's rows, score, presets and stems as a Case
    rows        which domain owns a row; which rows are advisory and can never bind
    margins     every row as a signed safety in units of its own tolerance
    catalog     the levers a project's presets and score actually declare
    domains/*   one module per domain (master, stems, spectral, spatial, channels, hrtf, chem, ears, direction),
                each imported only when a row it owns is in question
    solve       one linear programme over all margins, granularity snapping, conflict intervals
    history     attempts already made, so a failed lever is never proposed twice
    report      JSON + Markdown into the project's reports folder

The form of the problem is the one the mixing literature uses: a model of the measured metrics in terms of the control
parameters, then an optimiser over those parameters (Barchiesi & Reiss, DAFx-09; "The Mathematics of Mixing", JAES
62/1, 2014; constraint-programme mixer-limiter, Luo et al., ICASSP 2025). The difference here is that the constraints
are a gate's pass marks, several of them discrete (an impulse count, a hole length), so the model is piecewise:
continuous rows get a band-energy sensitivity, discrete rows get event attribution, and a row that no admissible move
can satisfy is reported as a conflict with the interval that has no solution instead of becoming another render.
"""
from .artifacts import Case                                  # noqa: F401
from .engine import autopsy, classify                        # noqa: F401
from . import catalog, history, margins, rows, solve          # noqa: F401

__all__ = ['Case', 'autopsy', 'catalog', 'classify', 'history', 'margins', 'rows', 'solve']
