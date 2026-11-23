# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""ear_model - a streaming peripheral auditory model for the QA gate (numpy / scipy only).

    from ear_model import EarModel, Summariser
    ear = EarModel(sr=44100)
    for nap, depth in ear.stream(mono):        # (channels, frames) float32 chunks at ~2.2 kHz
        ...
    result = Summariser(ear).run(mono)         # per-frame fatigue, excitation, modulation roughness, pitch salience

Memory is bounded by the chunk (5 s of one channel by default), never by the track.
"""
from .model import EarModel, params
from .summary import BinauralSummariser, Summariser, iacc

__all__ = ['BinauralSummariser', 'EarModel', 'Summariser', 'iacc', 'params']
