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

"""Stage `listen`: load the song, settle the tuning, build the pitch-resolved spectrum. Results go to ctx['data'] and the cache."""
import os

from . import audio_io, spectrum, tuning
from .config import jdump


def run(ctx):
    cfg, d = ctx['cfg'], ctx['data']
    cache = audio_io.Cache(ctx['root'], ctx['song'])
    sr = cfg['analysis']['sr']
    csr = cfg['spectrum']['cqt_sr']
    hit = cache.get('listen', cfg['tuning'], cfg['spectrum'], sr, ctx['priors']['tuning_cents'])
    if hit:
        d.update(hit)
        print(f'  from cache: tuning {d["tuning"]["cents"]:+.1f} cents')
        return
    y = audio_io.load(ctx['song'], csr)
    ym = audio_io.mono(y)
    measured = tuning.estimate_cents(ym, csr, cfg)
    prior = ctx['priors']['tuning_cents'] if ctx['db']['instruments'] else None
    tun = tuning.resolve(measured, prior, cfg)
    print(f'  tuning: measured {measured:+.1f} cents, music_db {prior if prior is None else format(prior, "+.1f")} -> using {tun["cents"]:+.1f}')
    spec = spectrum.semitone_spectrum(spectrum.harmonic_part(ym, cfg), csr, tun['cents'], cfg)
    out = {'tuning': tun, 'spec': spec, 'duration_s': y.shape[1] / csr}
    d.update(out)
    cache.put('listen', out, cfg['tuning'], cfg['spectrum'], sr, ctx['priors']['tuning_cents'])
    jdump({'tuning': tun, 'duration_s': out['duration_s']}, os.path.join(ctx['root'], 'reports', 'listen.json'))
