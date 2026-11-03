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
"""mix_context.py - one immutable description of how one piece is mixed.

The mixer used to read module globals that `use_mix()` and `mix_stems()` overwrote, so the result of
mixing two pieces in one process depended on the order they were mixed. A MixContext is resolved once
per piece (preset merged over the schema defaults, space resolved, ownership decided) and installed for
the duration of that piece. The mixer reads every value through `mixer._mix()` / `mixer._space()`, which
return this thread's context, so no module global is rebound and a previous piece leaves nothing behind.

    import mix_context
    ctx = mix_context.resolve(score, space_resolver=mixer.resolve_space)
    ctx.mix['gain_staging']['strategy']   # the resolved value
    ctx.space, ctx.space_owned, ctx.name

The installed context is thread-local: two pieces mixed in two threads no longer overwrite each other's
globals between a check and a use (that check-then-act race was the audit's F43).
"""
import copy
import os
import threading

import presets
import mix_schema

_LOCAL = threading.local()


class MixContext:
    """The resolved configuration of one mix: the mix preset, the space, and where they came from."""

    __slots__ = ('mix', 'space', 'name', 'space_name', 'space_owned', 'preset_source')

    def __init__(self, mix, space=None, name='default', space_name=None, space_owned=False, preset_source=None):
        self.mix = mix
        self.space = space or {}
        self.name = name
        self.space_name = space_name
        self.space_owned = bool(space_owned)
        self.preset_source = preset_source

    # -- reading -------------------------------------------------------------
    def get(self, key, default=None):
        return self.mix.get(key, default)

    def section(self, key):
        return mix_schema.section(self.mix, key)

    def param(self, section, key, default=None):
        return (self.mix.get(section) or {}).get(key, default)

    @property
    def immersive(self):
        c = self.mix.get('immersive') or {}
        return c if c.get('enabled') else None

    @property
    def room(self):
        """The impulse-response description, or the legacy room name when the space has none."""
        return self.space if self.space.get('room') else None

    def __repr__(self):
        return f'MixContext({self.name!r}, space={self.space_name!r}, owned={self.space_owned})'


def current():
    return getattr(_LOCAL, 'ctx', None)


def make_current(ctx):
    """Install ctx for this thread only; returns the context it replaced."""
    prev = current()
    _LOCAL.ctx = ctx
    return prev


def mix_for(name='default'):
    """The mix preset `name` laid over the schema defaults. Unknown name -> KeyError from presets."""
    base = presets.mix()
    if name and name not in ('default', None):
        override = {k: v for k, v in presets.get('mix', name).items() if k not in ('name', '_source')}
        base = presets._deep_merge(base, override)
    return mix_schema.with_defaults(base)


def space_owned(space):
    """True when the space preset lives in a project. A shipped space is a fallback: its reverb and walls
    apply, but its distance law does not override the mix preset."""
    src = (space or {}).get('_source')
    return bool(src) and not os.path.abspath(src).startswith(presets.SKILL_PRESETS)


def resolve(score=None, space_resolver=None, mix_name=None):
    """Build and install the context for `score`.

    score           a score dict (mix_preset, space / room) or None for the shipped defaults
    space_resolver  mixer.resolve_space; passed in so this module does not import the mixer
    mix_name        overrides score["mix_preset"]
    """
    score = score or {}
    name = mix_name or score.get('mix_preset') or 'default'
    mix = mix_for(name)
    space_name = score.get('space') or score.get('room', 'hall')
    space = {}
    if space_name and space_name != 'none' and space_resolver is not None:
        space = space_resolver(space_name) or {}
    ctx = MixContext(mix, space, name=name, space_name=space_name,
                     space_owned=space_owned(space), preset_source=mix.get('_source'))
    make_current(ctx)
    return ctx


def clone(ctx):
    """A deep copy, for a comparison render that must not share mutable state with the original."""
    return MixContext(copy.deepcopy(ctx.mix), copy.deepcopy(ctx.space), ctx.name, ctx.space_name,
                      ctx.space_owned, ctx.preset_source)
