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
"""soundbank.py - find (or download) a General MIDI SoundFont and name its instruments.

The natural-music pipeline plays REAL recorded instrument samples from a SoundFont through
`tinysoundfont` (pure pip wheel, no system fluidsynth needed). This file:

  * ensure_soundfont()  -> path to a usable .sf2/.sf3 (env MUSICGEN_SF2, local cache, download,
                           or the small TimGM6mb that ships inside the pretty_midi package)
  * resolve("cello")    -> (bank, program, is_drums)   friendly names -> General MIDI program
  * DRUM_KITS           -> kit names -> drum preset numbers (bank 128)

    python3 soundbank.py            # prints the SoundFont path and checks it loads
    python3 soundbank.py --list     # lists every friendly instrument name
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.environ.get('MUSICGEN_CACHE', os.path.join(os.path.expanduser('~'), '.cache', 'music-generator'))
SF_URLS = [
    # GeneralUser GS (S. Christian Collins): free for any use incl. commercial music, ~32 MB, very good GM set.
    'https://github.com/mrbumpy409/GeneralUser-GS/raw/main/GeneralUser-GS.sf2',
    'https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2',
]
SF_NAME = 'GeneralUser-GS.sf2'

# friendly name -> General MIDI program (0-based). Many aliases so a brief can say what it means.
GM = {
    'piano': 0, 'grand_piano': 0, 'bright_piano': 1, 'electric_grand': 2, 'honky_tonk': 3,
    'epiano': 4, 'rhodes': 4, 'electric_piano': 4, 'fm_piano': 5, 'harpsichord': 6, 'clavinet': 7,
    'celesta': 8, 'glockenspiel': 9, 'music_box': 10, 'vibraphone': 11, 'vibes': 11, 'marimba': 12,
    'xylophone': 13, 'tubular_bells': 14, 'bells': 14, 'dulcimer': 15,
    'organ': 16, 'tonewheel_organ': 16, 'percussive_organ': 17, 'rock_organ': 18, 'pipe_organ': 19,
    'church_organ': 19, 'reed_organ': 20, 'harmonium': 20, 'accordion': 21, 'harmonica': 22, 'bandoneon': 23,
    'nylon_guitar': 24, 'classical_guitar': 24, 'acoustic_guitar': 25, 'steel_guitar': 25, 'jazz_guitar': 26,
    'clean_guitar': 27, 'electric_guitar': 27, 'muted_guitar': 28, 'overdrive_guitar': 29,
    'distortion_guitar': 30, 'guitar_harmonics': 31,
    'acoustic_bass': 32, 'upright_bass': 32, 'finger_bass': 33, 'bass': 33, 'pick_bass': 34,
    'fretless_bass': 35, 'slap_bass': 36, 'synth_bass': 38, 'synth_bass_2': 39,
    'violin': 40, 'viola': 41, 'cello': 42, 'double_bass': 43, 'contrabass': 43,
    'tremolo_strings': 44, 'pizzicato': 45, 'pizzicato_strings': 45, 'harp': 46, 'timpani': 47,
    'strings': 48, 'string_ensemble': 48, 'fast_strings': 48, 'slow_strings': 49, 'synth_strings': 50,
    'choir': 52, 'choir_aahs': 52, 'oohs': 53, 'voice_oohs': 53, 'synth_voice': 54, 'orchestra_hit': 55,
    'trumpet': 56, 'trombone': 57, 'tuba': 58, 'muted_trumpet': 59, 'horn': 60, 'french_horn': 60,
    'brass': 61, 'brass_section': 61, 'synth_brass': 62,
    'soprano_sax': 64, 'alto_sax': 65, 'sax': 65, 'tenor_sax': 66, 'baritone_sax': 67,
    'oboe': 68, 'english_horn': 69, 'bassoon': 70, 'clarinet': 71,
    'piccolo': 72, 'flute': 73, 'recorder': 74, 'pan_flute': 75, 'bottle': 76, 'shakuhachi': 77,
    'whistle': 78, 'ocarina': 79,
    'square_lead': 80, 'saw_lead': 81, 'calliope': 82, 'chiff': 83, 'solo_vox': 85,
    'warm_pad': 89, 'pad': 89, 'polysynth': 90, 'choir_pad': 91, 'space_voice': 91, 'bowed_pad': 92,
    'metal_pad': 93, 'halo_pad': 94, 'sweep_pad': 95, 'ice_rain': 96, 'soundtrack': 97,
    'crystal': 98, 'atmosphere': 99, 'brightness': 100, 'echo_drops': 102,
    'sitar': 104, 'banjo': 105, 'shamisen': 106, 'koto': 107, 'kalimba': 108, 'bagpipes': 109,
    'fiddle': 110, 'shehnai': 111, 'shenai': 111, 'tinkle_bell': 112, 'agogo': 113, 'steel_drums': 114,
    'woodblock': 115, 'taiko': 116, 'melodic_tom': 117, 'synth_drum': 118, 'reverse_cymbal': 119,
    'fret_noise': 120, 'breath_noise': 121, 'seashore': 122, 'birds': 123,
}

import world as _world      # world instruments are named stand-ins for General MIDI sounds; world drum names for GM percussion keys
GM.update({name: GM[target] for name, target in _world.INSTRUMENTS.items()})

# Drum kits live in bank 128 of the SoundFont
DRUM_KITS = {
    'standard': 0, 'room': 8, 'power': 16, 'electronic': 24, '808': 25, 'jazz': 32,
    'brush': 40, 'brushes': 40, 'orchestral': 48,
}
DRUM_ALIASES = {'drums': 'standard', 'kit': 'standard', 'rock_kit': 'power', 'jazz_kit': 'jazz', 'drum_kit': 'standard'}

# General MIDI drum map (key numbers on the drum channel)
DRUM_KEYS = {
    'kick': 36, 'kick2': 35, 'rim': 37, 'snare': 38, 'clap': 39, 'snare2': 40,
    'tom_low': 41, 'hat_closed': 42, 'tom_floor': 43, 'hat_pedal': 44, 'tom_mid': 45, 'hat_open': 46,
    'tom_mid2': 47, 'tom_high': 48, 'crash': 49, 'tom_high2': 50, 'ride': 51, 'chinese': 52,
    'ride_bell': 53, 'tambourine': 54, 'splash': 55, 'cowbell': 56, 'crash2': 57, 'vibraslap': 58,
    'ride2': 59, 'bongo_high': 60, 'bongo_low': 61, 'conga_mute': 62, 'conga_open': 63, 'conga_low': 64,
    'timbale_high': 65, 'timbale_low': 66, 'agogo_high': 67, 'agogo_low': 68, 'cabasa': 69,
    'maracas': 70, 'whistle_short': 71, 'whistle_long': 72, 'guiro': 73, 'claves': 75, 'wood_high': 76,
    'wood_low': 77, 'triangle': 81, 'shaker': 82, 'sleigh_bells': 83, 'bell_tree': 84, 'castanets': 85,
}

DRUM_KEYS.update(_world.DRUM_KEYS)

# sensible playable range per instrument (MIDI keys). Used to clamp / warn on impossible notes.
RANGES = {
    'violin': (55, 100), 'viola': (48, 88), 'cello': (36, 76), 'double_bass': (28, 60), 'flute': (60, 96),
    'oboe': (58, 91), 'clarinet': (50, 94), 'bassoon': (34, 75), 'trumpet': (55, 82), 'horn': (34, 77),
    'trombone': (40, 72), 'tuba': (28, 58), 'harp': (24, 103), 'piano': (21, 108), 'nylon_guitar': (40, 84),
    'acoustic_guitar': (40, 84), 'bass': (28, 55), 'acoustic_bass': (28, 55), 'koto': (50, 85),
}


SF_SHA256 = None            # pin a digest here to refuse any other bank; None records it instead of rejecting
_DIGESTS = {}               # (path, size, mtime) -> sha256, so a 32 MB bank is hashed once per process


def file_sha256(path, chunk=1 << 20):
    import hashlib
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_size, int(st.st_mtime))
    if key in _DIGESTS:
        return _DIGESTS[key]
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(chunk), b''):
            h.update(block)
    _DIGESTS[key] = h.hexdigest()
    return _DIGESTS[key]


def verify_digest(path):
    """Provenance for the SoundFont: record its sha256, and refuse it when SF_SHA256 is pinned and differs.
    A truncated or swapped bank is otherwise only noticed when it fails to load (or loads as a different sound)."""
    got = file_sha256(path)
    if SF_SHA256 and got != SF_SHA256:
        sys.stderr.write(f'[soundbank] {os.path.basename(path)} sha256 {got[:16]}... does not match the pinned '
                         f'{SF_SHA256[:16]}...: refusing it.\n')
        return False
    return True


def _try_load(path):
    try:
        import tinysoundfont
        s = tinysoundfont.Synth(samplerate=22050, gain=0)
        s.sfload(path)
        return True
    except Exception:
        return False


def _download(dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    last = None
    for url in SF_URLS:
        try:
            tmp = dst + '.part'
            urllib.request.urlretrieve(url, tmp)
            if os.path.getsize(tmp) > 5_000_000:
                os.replace(tmp, dst)
                return True
        except Exception as e:  # network blocked etc.
            last = e
    sys.stderr.write(f'[soundbank] download failed: {last}\n')
    return False


def ensure_soundfont(verbose=False):
    """Return a path to a loadable SoundFont, trying (in order): $MUSICGEN_SF2, skill-local
    assets, cache, download, pretty_midi's bundled TimGM6mb (small, lower quality)."""
    cands = []
    if os.environ.get('MUSICGEN_SF2'):
        cands.append(os.environ['MUSICGEN_SF2'])
    cands += [os.path.join(HERE, '..', 'assets', 'soundfonts', SF_NAME),
              os.path.join(CACHE_DIR, SF_NAME)]
    for c in cands:
        if os.path.exists(c) and verify_digest(c) and _try_load(c):
            if verbose:
                print(f'[soundbank] {c} sha256 {file_sha256(c)}')
            return os.path.abspath(c)
    dst = os.path.join(CACHE_DIR, SF_NAME)
    if _download(dst) and verify_digest(dst) and _try_load(dst):
        return dst
    try:
        import pretty_midi
        fb = os.path.join(os.path.dirname(pretty_midi.__file__), 'TimGM6mb.sf2')
        if os.path.exists(fb) and _try_load(fb):
            sys.stderr.write('[soundbank] using small fallback TimGM6mb.sf2 - quality is noticeably lower. '
                             'Set MUSICGEN_SF2 to a better .sf2/.sf3 (e.g. GeneralUser GS, MuseScore General) if you can.\n')
            return fb
    except Exception:
        pass
    raise RuntimeError('No SoundFont found. pip install pretty_midi tinysoundfont (--no-deps) or set MUSICGEN_SF2=/path/to.sf2')


def resolve(name):
    """'cello' -> (0, 42, False);  'drums'/'808' -> (128, 25, True);  int -> that GM program."""
    if isinstance(name, int):
        return (0, name, False)
    key = str(name).lower().strip().replace(' ', '_').replace('-', '_')
    key = DRUM_ALIASES.get(key, key)
    if key in DRUM_KITS:
        return (128, DRUM_KITS[key], True)
    if key in GM:
        return (0, GM[key], False)
    # fuzzy: first GM key containing the text
    for k, v in GM.items():
        if key in k or k in key:
            return (0, v, False)
    raise KeyError(f'unknown instrument "{name}". Run soundbank.py --list')


if __name__ == '__main__':
    if '--list' in sys.argv:
        print('PITCHED:', ', '.join(sorted(GM)))
        print('DRUM KITS:', ', '.join(sorted(DRUM_KITS)))
        print('DRUM PIECES:', ', '.join(sorted(DRUM_KEYS)))
    else:
        p = ensure_soundfont()
        print('SoundFont OK:', p, f'({os.path.getsize(p)/1e6:.1f} MB)')
