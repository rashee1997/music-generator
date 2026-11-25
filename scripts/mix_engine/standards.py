"""standards - delivery targets as published data, not as house defaults.

Each entry names the document, its version, the figures it defines and where they were read. A profile
declares which one it implements (`mastering.standard` in the mix preset); the gate then checks that the
declared target and ceiling agree with the document, and reports how far the delivered file is from it.

Only two kinds exist:
  * `standard` - a document defines the figure (EBU, ATSC, AES). A file outside its tolerance is a WARN,
    never a silent pass: the piece still has to be delivered as asked.
  * `policy`   - a platform states the behaviour (Spotify normalises both ways). There is no tolerance to
    comply with, only the platform's own headroom advice.

Figures are quoted, not derived. `lufs_tol` is the document's own tolerance where it states one.
Apple Music and YouTube publish no music loudness target; they are deliberately absent rather than
guessed at.
"""
from __future__ import annotations

STANDARDS = {
    'ebu_r128': dict(
        kind='standard',
        document='EBU R 128 v5 (2023)',
        lufs=-23.0, true_peak=-1.0, lufs_tol=0.2, tp_tol=0.3,
        note='broadcast programme; +-0.2 LU in QC, +-1.0 LU where normalisation is impractical',
        url='https://tech.ebu.ch/docs/r/r128v5_0.pdf',
    ),
    'atsc_a85': dict(
        kind='standard',
        document='ATSC A/85:2026-07',
        lufs=-24.0, true_peak=-2.0, lufs_tol=2.0, tp_tol=0.5,
        note='television; LKFS is the same unit as LUFS, +-2 dB measurement tolerance',
        url='https://www.atsc.org/wp-content/uploads/2026/07/A85-2026-07.pdf',
    ),
    'aes_td1008': dict(
        kind='standard',
        document='AES TD1008 (2021) / AES77-2023',
        lufs=-16.0, true_peak=-1.0, lufs_tol=0.2, tp_tol=0.3,
        note='streaming, track-normalised music; -14 LUFS applies to the loudest track of an album release',
        url='https://www.aes.org/wp-content/uploads/2024/01/20210924_TD1008_v3.13.pdf',
    ),
    'spotify': dict(
        kind='policy',
        document='Spotify loudness normalisation (platform policy)',
        lufs=-14.0, true_peak=-1.0, lufs_tol=None, tp_tol=None,
        note='normalises both ways with 1 dB headroom; -2 dBTP when the master is above -14 LUFS',
        url='https://support.spotify.com/us/artists/article/loudness-normalization',
    ),
}

DECLARATION_TOL = 0.1       # the declared target must match the document this closely


def get(name):
    """The standard called `name`, or a clear error naming the ones that exist."""
    key = str(name or '').strip().lower()
    if key not in STANDARDS:
        raise KeyError(f'delivery standard {name!r} is not known; known: {", ".join(sorted(STANDARDS))}')
    return STANDARDS[key]


def declaration_problems(name, lufs, true_peak):
    """Problems with the *profile's own numbers* against the document it declares.

    A profile that says `standard: "ebu_r128"` and targets -14 LUFS is a configuration bug, not a piece
    judged too loud. The gate fails that, because the report would otherwise name a standard it does not
    implement.
    """
    s = get(name)
    out = []
    try:
        got_lufs = float(lufs)
    except (TypeError, ValueError):
        got_lufs = None
    try:
        got_tp = float(true_peak)
    except (TypeError, ValueError):
        got_tp = None
    if got_lufs is not None and abs(got_lufs - s['lufs']) > DECLARATION_TOL:
        out.append(f'{s["document"]}: declared target {got_lufs:g} LUFS, the document says {s["lufs"]:g} LUFS')
    if got_tp is not None and got_tp > s['true_peak'] + DECLARATION_TOL:
        out.append(f'{s["document"]}: declared ceiling {got_tp:g} dBTP is above the document\'s {s["true_peak"]:g} dBTP')
    return out


def file_problems(name, lufs, true_peak):
    """(level, message) for the delivered file against a declared standard.

    A `standard` gets WARN outside its stated tolerance (a fact about the delivery, not a new hard row);
    a `policy` gets INFO, because a platform's figure describes what it will do to the file, not a rule the
    file has to meet.
    """
    s = get(name)
    if s['kind'] == 'policy':
        msg = (f'{s["document"]}: {lufs:.1f} LUFS / {true_peak:.2f} dBTP (platform target {s["lufs"]:g} LUFS, '
               f'{s["note"]}); the platform normalises at playback, so this is reported, not failed')
        return 'INFO', msg
    miss = max(abs(lufs - s['lufs']) - s['lufs_tol'], true_peak - s['true_peak'] - s['tp_tol'])
    if miss > 0:
        return 'WARN', (f'{s["document"]}: {lufs:.1f} LUFS / {true_peak:.2f} dBTP misses {s["lufs"]:g} LUFS '
                        f'(+-{s["lufs_tol"]:g}) / {s["true_peak"]:g} dBTP by {miss:.2f}; the profile declares this '
                        f'standard, so the delivery is not it')
    return 'PASS', (f'{s["document"]}: {lufs:.1f} LUFS / {true_peak:.2f} dBTP inside {s["lufs"]:g} '
                    f'(+-{s["lufs_tol"]:g}) / {s["true_peak"]:g} dBTP')
