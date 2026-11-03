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
"""soul.py - what makes a music feel alive, per culture, as DATA. Any culture works: a profile is loaded from
references/soul/<culture>.json when that file exists, otherwise from the built-in SOUL table below. A brief can also
carry its own "soul" block, which overrides either. Nothing here is hard-coded to one piece.

    from soul import profile, merged
    p = profile('west_african')                  # dict: feel, breath_beats, groove, call_response, ornament, cadence, ...
    req = merged(['indian', 'west_african'])     # the union of the requirements, for a fusion

Fields
  feel             words for the emotional core (the soul), from references/cultural-soul.md
  breath_beats     the silence that must sit between phrases (ma); 0 = no requirement
  groove           'offbeat' (accents off the beat must be present), 'cycle' (a repeating tala), or None
  call_response    True: a leader and an answer must alternate
  ornament         True: some short notes, slides or microtones are expected
  cadence          True: phrases must close on the key's tonic (tension and release)
  tempo            (lo, hi) bpm the culture plays in
  avoid_instruments  instruments that read as another culture
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOUL_DIR = os.path.join(HERE, '..', 'references', 'soul')

# Sources for each entry: references/cultural-soul.md (researched with TinyFish, June 2026 notes).
import presets  # noqa: E402  (soul profiles are the 'soul' presets: references/presets/soul and each project's presets/soul)


def profile(culture):
    """A culture's soul, from the 'soul' presets. A project's preset with the same name wins over the skill's."""
    key = str(culture).lower().strip().replace(' ', '_').replace('-', '_')
    presets_ = presets.load('soul')
    if key not in presets_:
        raise KeyError(f'no soul profile for "{culture}". Add one: presets.py scaffold soul {key} --project <dir>')
    return {k: v for k, v in presets_[key].items() if k != '_source'}


def merged(cultures, override=None):
    """The requirements of a mix: a requirement holds if any culture in the mix needs it. A brief's own
    'soul' block (override) wins over all of them."""
    ps = [profile(c) for c in cultures]
    out = dict(
        feel=[f for p in ps for f in p.get('feel', [])],
        breath_beats=max(p.get('breath_beats', 0.0) for p in ps),
        groove='offbeat' if any(p.get('groove') == 'offbeat' for p in ps) else next((p['groove'] for p in ps if p.get('groove')), None),
        call_response=any(p.get('call_response') for p in ps),
        ornament=any(p.get('ornament') for p in ps),
        cadence=any(p.get('cadence') for p in ps),
        tempo=(max(p['tempo'][0] for p in ps), min(p['tempo'][1] for p in ps)),
        avoid_instruments=sorted({i for p in ps for i in p.get('avoid_instruments', [])}),
    )
    # an instrument the mix itself plays is not foreign to it (an Arabic mix keeps its oud and ney)
    try:
        from fusion import CULTURES
        owned = {n for c in cultures if c in CULTURES for names in CULTURES[c]['roles'].values() for n in names}
    except ImportError:
        owned = set()
    out['avoid_instruments'] = [i for i in out['avoid_instruments'] if i not in owned]
    if override:
        out.update(override)
    return out


if __name__ == '__main__':
    import sys
    names = sys.argv[1:] or sorted(presets.load('soul'))
    for n in names:
        print(n, json.dumps(profile(n)))
