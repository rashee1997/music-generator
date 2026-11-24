# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""roles.py - the one vocabulary for what a track DOES in a piece.

Before this module, every part of the engine carried its own list: the gate looked for `melody`, the
balance for `melody|lead|vocal`, the mixer for `melody|lead`, the film mapping for `melody|lead|pad|...`.
A piece whose leading line was written as `lead` was levelled as a lead and never checked for masking;
a `drone` fell through to the effect chain at -8 dB. That is not a mixing bug, it is four vocabularies.

One list, one alias table, one family per question:

    from roles import canonical, family, is_lead, LEAD

    canonical('harmony')  -> 'counter'      # the alias table is the only place a synonym lives
    family('drone')       -> 'colour'
    is_lead('vocal')      -> True

A role is a *function*, not an instrument and not a register. `pad` means "sustains the harmony",
not "is quiet". `drone` means "holds one centre with no harmonic motion". `melody` and `lead` are
both the figure; they are kept distinct because a score that says `lead` is saying something about
prominence, and collapsing them would move existing pieces by 0 dB only if the tables agree - see
CANONICAL below, where they map to the same numbers.
"""
import re

# ---- the canonical set -----------------------------------------------------------------------------
# The order is the order the engine reports in: figure, harmony, rhythm, colour.
CANONICAL_ROLES = (
    'melody', 'lead', 'vocal',          # the figure: what the ear follows
    'counter', 'chord', 'pad',          # harmony and accompaniment
    'bass', 'drum', 'arp', 'ostinato',  # rhythm and low end
    'drone', 'texture', 'fx', 'environment',   # colour, place, atmosphere
)

# Function families. A check asks a family question, never a name question.
FAMILIES = {
    'figure':    ('melody', 'lead', 'vocal'),
    'harmony':   ('counter', 'chord', 'pad'),
    'rhythm':    ('bass', 'drum', 'arp', 'ostinato'),
    'colour':    ('drone', 'texture', 'fx', 'environment'),
}
FAMILY_OF = {r: f for f, roles in FAMILIES.items() for r in roles}

# The figure family, in the order a piece is asked to provide one. `LEAD` is the historical name and
# stays the same object, so `from roles import LEAD` and `quality_gate.LEAD_ROLES` cannot drift.
LEAD = FAMILIES['figure']

# ---- aliases ---------------------------------------------------------------------------------------
# A synonym may only appear here. `normalise` maps it; nothing downstream branches on the old word.
ALIASES = {
    # harmony
    'harmony': 'counter', 'harm': 'counter', 'counterline': 'counter', 'counter_line': 'counter',
    'countermelody': 'counter', 'counter_melody': 'counter', 'answer': 'counter',
    'chords': 'chord', 'comp': 'chord', 'rhodes': 'chord',
    'strings': 'pad', 'beds': 'pad', 'bed': 'pad', 'warmpad': 'pad', 'warm_pad': 'pad',
    'texture_pad': 'texture', 'atmosphere': 'texture', 'ambience': 'environment', 'ambient': 'environment',
    # figure
    'vox': 'vocal', 'voice': 'vocal', 'choir': 'vocal', 'chant': 'vocal', 'hum': 'vocal',
    'theme': 'melody', 'tune': 'melody', 'hook': 'lead', 'topline': 'lead', 'top_line': 'lead',
    # rhythm
    'percussion': 'drum', 'perc': 'drum', 'drums': 'drum', 'kit': 'drum', 'beat': 'drum', 'rhythm': 'drum',
    'bassline': 'bass', 'bass_line': 'bass', 'sub': 'bass',
    'arpeggio': 'arp', 'arpeggios': 'arp', 'pulse': 'ostinato', 'riff': 'ostinato', 'figure': 'ostinato',
    # colour
    'sfx': 'fx', 'effect': 'fx', 'effects': 'fx', 'one_shot': 'fx', 'oneshot': 'fx',
    'env': 'environment', 'room': 'environment', 'field': 'environment', 'nature': 'environment',
    'drone_bed': 'drone', 'pedal': 'drone',
}

# Focus names a piece can declare instead of a lead. `melody` is the historical default.
FOCUS = ('melody', 'drone', 'groove', 'texture', 'gesture')
FOCUS_ROLES = {
    'melody':  ('melody', 'lead', 'vocal'),
    'drone':   ('drone', 'pad'),
    'groove':  ('drum', 'bass', 'ostinato'),
    'texture': ('texture', 'pad', 'arp'),
    'gesture': ('fx', 'drum', 'arp'),
}

_STRIP = re.compile(r'[^a-z0-9_]+')


class UnknownRole(ValueError):
    """A role that is not in the vocabulary and not in the alias table."""


def normalise(name):
    """`"Counter-Melody"` -> `"counter_melody"`. Spacing and case are not information."""
    return _STRIP.sub('_', str(name or '').strip().lower()).strip('_')


def canonical(name, strict=False, default='chord'):
    """The canonical role for `name`.

    strict=True raises UnknownRole; strict=False returns `default` for an empty name and still raises for
    an unknown non-empty one. Guessing a role silently is how a drone ended up on the effect chain: an
    unknown role must be a caller's decision, not a fallback.
    """
    n = normalise(name)
    if not n:
        if strict:
            raise UnknownRole('empty role')
        return default
    if n in CANONICAL_ROLES:
        return n
    if n in ALIASES:
        return ALIASES[n]
    if strict:
        raise UnknownRole(f'{name!r} is not a role. Canonical: {", ".join(CANONICAL_ROLES)}')
    raise UnknownRole(f'{name!r} is not a role. Canonical: {", ".join(CANONICAL_ROLES)}. '
                      f'Add a synonym to roles.ALIASES if it means one of them')


def family(name):
    """figure | harmony | rhythm | colour."""
    return FAMILY_OF[canonical(name)]


def is_lead(name):
    """True for the figure family: the thing the ear follows."""
    try:
        return canonical(name) in LEAD
    except UnknownRole:
        return False


def is_focus(name, focus):
    """True when `name` can be the reference line of a piece that declared `focus`."""
    if focus not in FOCUS_ROLES:
        raise UnknownRole(f'focus {focus!r} is not one of {FOCUS}')
    try:
        return canonical(name) in FOCUS_ROLES[focus]
    except UnknownRole:
        return False


def focus_of(score, strict=False):
    """The declared focus of a score: meta.focus, then score.focus, then the historical default.

    strict=True raises UnknownRole for a word the engine has no focus for. The gate uses it so a typo is a FAIL
    naming the word, not a silent melody piece; callers that only need the default keep the lenient behaviour.
    """
    meta = score.get('meta') or {}
    raw = score.get('focus') or meta.get('focus') or 'melody'
    n = normalise(raw)
    if n in FOCUS_ROLES:
        return n
    if strict:
        raise UnknownRole(f'focus {raw!r} is not one of {", ".join(FOCUS)}')
    return 'melody'


def focus_roles(focus):
    return FOCUS_ROLES[focus]


def tracks_by_role(score, roles=None, min_notes=0):
    """Score tracks whose canonical role is in `roles` (all roles when None) and that carry `min_notes`."""
    want = None if roles is None else {canonical(r) for r in roles}
    out = []
    for t in score.get('tracks', []) or []:
        try:
            r = canonical(t.get('role'))
        except UnknownRole:
            continue
        if want is not None and r not in want:
            continue
        notes = [n for n in (t.get('notes') or []) if isinstance(n.get('p'), (int, float))]
        if len(notes) < min_notes:
            continue
        out.append((t, r))
    return out


def problems(score):
    """Unknown roles in a score, as report lines. Empty = the piece uses the one vocabulary."""
    out = []
    for t in score.get('tracks', []) or []:
        raw = t.get('role')
        try:
            canonical(raw)
        except UnknownRole as e:
            out.append(f'track "{t.get("name", "?")}": {e}')
    return out


def canonise_score(score):
    """Rewrite every track role to its canonical name, in place, and return the score.

    This is what makes the alias table worth having: after it runs, every downstream module compares
    canonical names and no module needs its own list.
    """
    for t in score.get('tracks', []) or []:
        if 'role' in t:
            try:
                t['role'] = canonical(t['role'])
            except UnknownRole:
                pass                      # left for problems() to report; never silently reassigned
    return score


if __name__ == '__main__':
    for r in CANONICAL_ROLES:
        print(f'{r:12s} {FAMILY_OF[r]:8s}', 'lead' if r in LEAD else '')
    for name in ('harmony', 'vox', 'percussion', 'sfx', 'Counter-Melody'):
        print(f'{name:16s} -> {canonical(name)}')
