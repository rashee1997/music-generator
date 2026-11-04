# Copyright (C) 2026 rasheedh <rasheedhmech03@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""spatial_engine - discrete multichannel placement, bass management and fold-down.

Everything a format needs is data: the loudspeaker layout (references/data/presets/layouts/), the target's channel
order, files and true-peak ceiling (references/data/presets/outputs/). Nothing here holds an azimuth, a crossover or a
threshold; this package reads the presets and does the arithmetic.

    from spatial_engine import render
    audio = render.render_stems(stems, 'itu_bs2051_system_j')

Modules:
    config        the data seam: a layout preset, a target preset, their validation
    pan           vector base amplitude panning (Pulkki, 1997) over whatever loudspeakers the layout names
    bass          Linkwitz-Riley 4th-order crossover and the low-frequency channel (Linkwitz, 1976)
    decorrelate   short all-pass decorrelation for surround and height channels (Kendall, 1995)
    downmix       the two-channel fold-down (ITU-R BS.775)
    render        mix placed stems into a discrete multichannel bus and write it
"""
