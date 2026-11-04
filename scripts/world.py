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
"""world.py - world-music data for the generator: scales (with microtones), instruments, drum names,
rhythm cycles and ready genre presets. Pure data plus two small helpers; compose.py, theory.py,
soundbank.py, humanize.py and render_natural.py merge it in at import.

Labels (same convention as genres-and-moods.md): 'sourced' = read for this skill (listed in
references/scoring/world-music.md section 9); 'practice' = common practice or the author's approximation.

    python3 world.py            # prints what is in here
    from world import cycle_notes
    drums = cycle_notes('aksak', bars=8)      # a 9/8 bar as drum notes (beat = one eighth)
"""
import numpy as np

# ------------------------------------------------------------------------------------------------
# 1. scales. MODES are semitones from the tonic (12-note equal temperament, so the chord code works).
#    MICRO is the real tuning: cents to add to each scale degree (index into the MODES list). The
#    renderer applies it as a per-note pitch bend, so a quarter-flat third really is a quarter-flat.
# ------------------------------------------------------------------------------------------------
_JI = [0, 112, 204, 316, 386, 498, 590, 702, 814, 884, 996, 1088]      # just-intonation cents per semitone slot


def ji(semis):
    """just-intonation deviation per degree: Indian and many folk scales sit on pure intervals"""
    return {i: float(_JI[s] - 100 * s) for i, s in enumerate(semis) if _JI[s] - 100 * s}


def _flat(semis, *degrees):
    """quarter-flat (-50 cents) on the given degrees: the Arabic 'half-flat' notes"""
    return {i: -50.0 for i in degrees}


MODES, MICRO, PARENT = {}, {}, {}


def _add(name, semis, micro=None, parent=None):
    MODES[name] = list(semis)
    if micro:
        MICRO[name] = micro
    if parent:
        PARENT[name] = parent


# -- India (Hindustani thaats and common ragas; just intonation) --------------------------------
for _n, _s, _p in [
    ('raga_bilawal', [0, 2, 4, 5, 7, 9, 11], None), ('raga_yaman', [0, 2, 4, 6, 7, 9, 11], None),
    ('raga_khamaj', [0, 2, 4, 5, 7, 9, 10], None), ('raga_kafi', [0, 2, 3, 5, 7, 9, 10], None),
    ('raga_asavari', [0, 2, 3, 5, 7, 8, 10], None), ('raga_bhairavi', [0, 1, 3, 5, 7, 8, 10], None),
    ('raga_bhairav', [0, 1, 4, 5, 7, 8, 11], None), ('raga_purvi', [0, 1, 4, 6, 7, 8, 11], None),
    ('raga_marwa', [0, 1, 4, 6, 7, 9, 11], None), ('raga_todi', [0, 1, 3, 6, 7, 8, 11], None),
    ('raga_bhoopali', [0, 2, 4, 7, 9], 'major'), ('raga_durga', [0, 2, 5, 7, 9], 'major'),
    ('raga_malkauns', [0, 3, 5, 8, 10], 'aeolian'), ('raga_hindol', [0, 4, 6, 9, 11], 'lydian'),
]:
    _add(_n, _s, ji(_s), _p)

# more ragas (notes from the thaat tables; 'practice' for the mapping), and Carnatic names for the same note sets ('sourced': ragajunglism.org, shankarmahadevanacademy.com)
for _n, _s, _p in [
    ('raga_ahir_bhairav', [0, 1, 4, 5, 7, 9, 10], None), ('raga_charukeshi', [0, 2, 4, 5, 7, 8, 10], None),
    ('raga_megh', [0, 2, 5, 7, 10], 'mixolydian'), ('raga_hamsadhwani', [0, 2, 4, 7, 11], 'major'),
]:
    _add(_n, _s, ji(_s), _p)
for _n, _src in {'raga_kalyani': 'raga_yaman', 'raga_mayamalavagowla': 'raga_bhairav', 'raga_shankarabharanam': 'raga_bilawal',
                 'raga_kharaharapriya': 'raga_kafi', 'raga_natabhairavi': 'raga_asavari', 'raga_harikambhoji': 'raga_khamaj',
                 'raga_hanumatodi': 'raga_bhairavi', 'raga_mohanam': 'raga_bhoopali', 'raga_abheri': 'raga_kafi'}.items():
    _add(_n, MODES[_src], MICRO.get(_src), PARENT.get(_src))

# -- Arabic maqam (quarter-flat notes at -50 cents; 'practice': real players vary by region and by player) --
_add('maqam_rast', [0, 2, 4, 5, 7, 9, 11], _flat(0, 2, 6))
_add('maqam_bayati', [0, 2, 3, 5, 7, 8, 10], _flat(0, 1))
_add('maqam_sikah', [0, 1, 3, 5, 7, 8, 10], _flat(0, 0, 4))             # tonic itself is the half-flat note
_add('maqam_saba', [0, 2, 3, 4, 7, 8, 10], _flat(0, 1))
_add('maqam_hijaz', [0, 1, 4, 5, 7, 8, 10])
_add('maqam_hijaz_kar', [0, 1, 4, 5, 7, 8, 11])
_add('maqam_nahawand', [0, 2, 3, 5, 7, 8, 11])
_add('maqam_kurd', [0, 1, 3, 5, 7, 8, 10])
_add('maqam_ajam', [0, 2, 4, 5, 7, 9, 11])
_add('maqam_nikriz', [0, 2, 3, 6, 7, 9, 10])
# -- Turkish makam: modern theory counts 53 commas per octave (1 comma = 22.6 cents; system described at microtonaltheory.com).
#    Rast is computed here from the Arel-Ezgi-Uzdilek steps 9-8-5-9-9-8-5 commas (author's arithmetic); the others are 12-note approximations.
_add('makam_rast', [0, 2, 4, 5, 7, 9, 11], {1: 3.8, 2: -15.1, 3: -1.9, 4: 2.0, 5: 5.8, 6: -13.2})
_add('makam_hicaz', [0, 1, 4, 5, 7, 8, 10])
_add('makam_ussak', [0, 2, 3, 5, 7, 8, 10], _flat(0, 1))                # the Turkish form of bayati
_add('makam_nihavent', [0, 2, 3, 5, 7, 8, 11])
_add('makam_kurdi', [0, 1, 3, 5, 7, 8, 10])
_add('persian_shur', [0, 2, 3, 5, 7, 8, 10], _flat(0, 1))
_add('phrygian_dominant', [0, 1, 4, 5, 7, 8, 10], None, 'phrygian')    # flamenco, klezmer 'freygish', Greek dromos
_add('freygish', [0, 1, 4, 5, 7, 8, 10], None, 'phrygian')
_add('ukrainian_dorian', [0, 2, 3, 6, 7, 9, 10])                        # klezmer 'mi sheberach'
_add('hungarian_minor', [0, 2, 3, 6, 7, 8, 11])
# -- China: the five modes are rotations of C D E G A ('sourced': ISMIR 2022 paper and Chinese musicology) --
_add('chinese_gong', [0, 2, 4, 7, 9], None, 'major')
_add('chinese_shang', [0, 2, 5, 7, 10], None, 'mixolydian')
_add('chinese_jue', [0, 3, 5, 8, 10], None, 'aeolian')
_add('chinese_zhi', [0, 2, 5, 7, 9], None, 'major')
_add('chinese_yu', [0, 3, 5, 7, 10], None, 'minor')
# -- Japan ('sourced': masterthescore.com) --
_add('hirajoshi', [0, 2, 3, 7, 8], None, 'aeolian')                     # the koto tuning
_add('miyako_bushi', [0, 1, 5, 7, 8], None, 'phrygian')                 # also called the in scale
_add('insen', [0, 1, 5, 7, 10], None, 'phrygian')
_add('iwato', [0, 1, 5, 6, 10], None, 'locrian')
_add('yo', [0, 2, 5, 7, 10], None, 'mixolydian')                        # bright, no semitones
_add('ryukyu', [0, 4, 5, 7, 11], None, 'major')                         # Okinawa
# -- Korea, Indonesia, Andes, Africa, Celtic --
_add('korean_gyemyeonjo', [0, 3, 5, 7, 10], None, 'minor')              # the sad trot / folk pentatonic
_add('korean_pyeongjo', [0, 2, 5, 7, 9], None, 'major')
# gamelan: slendro is close to 5 equal steps of 240 cents; pelog (7 tones) is shown as its common 5-note subset. Every set is tuned differently.
_add('slendro', [0, 2, 5, 7, 10], {1: 40.0, 2: -20.0, 3: 20.0, 4: -40.0}, 'mixolydian')
_add('pelog', [0, 1, 3, 7, 8], None, 'phrygian')
_add('andean_minor', [0, 3, 5, 7, 10], None, 'minor')
_add('african_pentatonic', [0, 2, 4, 7, 9], None, 'major')
_add('celtic_dorian', [0, 2, 3, 5, 7, 9, 10])
_add('mbira_mixolydian', [0, 2, 4, 5, 7, 9, 10])
# -- shapes from global_music_theory_algorithmic_synthesis_guide.md (the other KB scales already exist under the names in its table) --
_add('ethiopian_tizita_maj', [0, 2, 4, 7, 8])                      # practice: nostalgic major-minor blend
_add('ethiopian_bati', [0, 4, 6, 7, 11])                           # practice: luminous Ethio-jazz
_add('western_octatonic', [0, 1, 3, 4, 6, 7, 9, 10])               # practice: diminished chase / thriller

# ------------------------------------------------------------------------------------------------
# 2. instruments. name -> General MIDI name it is played with. These are STAND-INS: the SoundFont has
#    128 sounds, so a sitar here is a sitar-like plucked string, not a recording. Say so in the reply.
#    Better route for any of these: a clone of a real recording (clone_instrument.py) or a SoundFont
#    with the real instrument (MUSICGEN_SF2).
# ------------------------------------------------------------------------------------------------
INSTRUMENTS = {
    # India / South Asia
    'sitar': 'sitar', 'tanpura': 'sitar', 'veena': 'sitar', 'sarod': 'steel_guitar', 'santoor': 'dulcimer',
    'bansuri': 'flute', 'shehnai': 'shehnai', 'nadaswaram': 'shehnai', 'sarangi': 'viola', 'esraj': 'viola',
    'dilruba': 'viola', 'tumbi': 'banjo', 'ektara': 'banjo', 'swarmandal': 'harp', 'indian_harmonium': 'harmonium',
    'dotara': 'banjo', 'rabab': 'banjo',
    # Arabic / Turkish / Persian / Balkan
    'oud': 'nylon_guitar', 'ud': 'nylon_guitar', 'qanun': 'harp', 'kanun': 'harp', 'ney': 'shakuhachi',
    'nay': 'shakuhachi', 'kawala': 'shakuhachi', 'mijwiz': 'oboe', 'mizmar': 'oboe', 'zurna': 'oboe',
    'duduk': 'english_horn', 'kaval': 'flute', 'rebab': 'viola', 'kamancheh': 'violin', 'kemence': 'violin',
    'kemenche': 'violin', 'arabic_violin': 'violin', 'saz': 'steel_guitar', 'baglama': 'steel_guitar',
    'bouzouki': 'steel_guitar', 'baglamas': 'steel_guitar', 'tanbur': 'nylon_guitar', 'cumbus': 'banjo',
    'tar': 'nylon_guitar', 'setar': 'nylon_guitar', 'santur': 'dulcimer', 'santouri': 'dulcimer',
    'cimbalom': 'dulcimer', 'tambura': 'banjo', 'gadulka': 'viola', 'gaida': 'bagpipes', 'tulum': 'bagpipes',
    'clarinet_klezmer': 'clarinet', 'oriental_organ': 'accordion',
    # China
    'erhu': 'violin', 'gaohu': 'violin', 'zhonghu': 'viola', 'guzheng': 'koto', 'zheng': 'koto', 'guqin': 'koto',
    'pipa': 'banjo', 'ruan': 'nylon_guitar', 'liuqin': 'nylon_guitar', 'yangqin': 'dulcimer', 'dizi': 'piccolo',
    'xiao': 'shakuhachi', 'sheng': 'harmonica', 'suona': 'oboe', 'xun': 'ocarina', 'bianzhong': 'tubular_bells',
    # Japan / Korea
    'koto': 'koto', 'shamisen': 'shamisen', 'biwa': 'shamisen', 'shakuhachi': 'shakuhachi', 'shinobue': 'flute',
    'fue': 'flute', 'sho': 'harmonica', 'gayageum': 'koto', 'geomungo': 'koto', 'haegeum': 'violin',
    'daegeum': 'flute', 'piri': 'oboe', 'taiko_pitched': 'taiko',
    # South-east Asia / Pacific
    'gamelan_gender': 'vibraphone', 'gamelan_saron': 'glockenspiel', 'gamelan_bonang': 'tinkle_bell',
    'gamelan_gong': 'tubular_bells', 'suling': 'flute', 'angklung': 'marimba', 'ukulele': 'nylon_guitar',
    'slack_key': 'steel_guitar', 'hawaiian_steel': 'steel_guitar',
    # Africa
    'kora': 'harp', 'ngoni': 'banjo', 'balafon': 'marimba', 'mbira': 'kalimba', 'kalimba_thumb_piano': 'kalimba',
    'likembe': 'kalimba', 'log_drum': 'marimba', 'kamale_ngoni': 'banjo', 'guembri': 'acoustic_bass',
    'ethiopian_krar': 'harp', 'masenqo': 'viola', 'highlife_guitar': 'clean_guitar', 'soukous_guitar': 'clean_guitar',
    # Latin America / Caribbean
    'charango': 'banjo', 'quena': 'shakuhachi', 'zampona': 'pan_flute', 'siku': 'pan_flute', 'cuatro': 'nylon_guitar',
    'tres': 'steel_guitar', 'vihuela': 'nylon_guitar', 'guitarron': 'acoustic_bass', 'requinto': 'nylon_guitar',
    'cavaquinho': 'nylon_guitar', 'violao': 'nylon_guitar', 'violao_7': 'nylon_guitar', 'bandolim': 'steel_guitar',
    'steelpan': 'steel_drums', 'harp_paraguayan': 'harp', 'arpa_llanera': 'harp', 'marimba_guatemala': 'marimba',
    'accordion_vallenato': 'accordion', 'gaita': 'recorder', 'berimbau': 'acoustic_guitar', 'bandoneon': 'bandoneon',
    # Europe / Americas folk and historic
    'mandolin': 'steel_guitar', 'balalaika': 'banjo', 'bagpipe': 'bagpipes', 'uilleann_pipes': 'bagpipes',
    'tin_whistle': 'recorder', 'penny_whistle': 'recorder', 'low_whistle': 'flute', 'concertina': 'accordion',
    'melodica': 'harmonica', 'hurdy_gurdy': 'accordion', 'lute': 'nylon_guitar', 'theorbo': 'nylon_guitar',
    'viola_da_gamba': 'cello', 'cornet': 'trumpet', 'flugelhorn': 'trumpet', 'euphonium': 'trombone',
    'sackbut': 'trombone', 'cembalo': 'harpsichord', 'wurlitzer': 'epiano', 'hammond': 'tonewheel_organ',
    'twelve_string': 'acoustic_guitar', 'dobro': 'steel_guitar', 'lap_steel': 'steel_guitar', 'pedal_steel': 'steel_guitar',
    'glass_harmonica': 'crystal', 'theremin': 'synth_voice', 'chiptune_lead': 'square_lead', '8bit': 'square_lead',
    'tubular_chime': 'tubular_bells',
}
# how each world instrument behaves in the renderer
SUSTAINED = {'ney', 'nay', 'kawala', 'mijwiz', 'mizmar', 'zurna', 'duduk', 'kaval', 'rebab', 'kamancheh', 'kemence',
             'kemenche', 'arabic_violin', 'gadulka', 'gaida', 'tulum', 'clarinet_klezmer', 'oriental_organ', 'erhu',
             'gaohu', 'zhonghu', 'dizi', 'xiao', 'sheng', 'suona', 'xun', 'shinobue', 'fue', 'sho', 'haegeum',
             'daegeum', 'piri', 'suling', 'masenqo', 'quena', 'zampona', 'siku', 'gaita', 'bandoneon', 'bagpipe',
             'uilleann_pipes', 'tin_whistle', 'penny_whistle', 'low_whistle', 'concertina', 'melodica', 'hurdy_gurdy',
             'viola_da_gamba', 'cornet', 'flugelhorn', 'euphonium', 'sackbut', 'glass_harmonica', 'theremin',
             'bansuri', 'shehnai', 'nadaswaram', 'sarangi', 'esraj', 'dilruba', 'indian_harmonium',
             'accordion_vallenato', 'chiptune_lead', '8bit', 'accordion'}
BOWED = {'rebab', 'kamancheh', 'kemence', 'kemenche', 'arabic_violin', 'gadulka', 'erhu', 'gaohu', 'zhonghu',
         'haegeum', 'masenqo', 'viola_da_gamba', 'sarangi', 'esraj', 'dilruba', 'indian_harmonium', 'concertina',
         'melodica', 'hurdy_gurdy', 'accordion_vallenato', 'bandoneon', 'oriental_organ', 'glass_harmonica'}
# plucked / struck: flat loudness over the note (no breath or bow swell) even when the renderer gives each note its own channel
PLUCKED = {'sitar', 'tanpura', 'veena', 'sarod', 'santoor', 'oud', 'ud', 'qanun', 'kanun', 'saz', 'baglama', 'bouzouki',
           'baglamas', 'tanbur', 'cumbus', 'tar', 'setar', 'santur', 'santouri', 'cimbalom', 'tumbi', 'ektara', 'swarmandal',
           'guzheng', 'zheng', 'guqin', 'pipa', 'ruan', 'liuqin', 'yangqin', 'koto', 'shamisen', 'biwa', 'gayageum',
           'geomungo', 'kora', 'ngoni', 'balafon', 'mbira', 'likembe', 'log_drum', 'charango', 'cuatro', 'tres', 'vihuela',
           'guitarron', 'requinto', 'cavaquinho', 'violao', 'violao_7', 'bandolim', 'steelpan', 'mandolin', 'balalaika',
           'lute', 'theorbo', 'ukulele', 'slack_key', 'dobro', 'gamelan_gender', 'gamelan_saron', 'gamelan_bonang',
           'gamelan_gong', 'angklung', 'dotara', 'rabab', 'tambura', 'berimbau', 'guembri', 'ethiopian_krar', 'marimba_guatemala',
           'harp_paraguayan', 'arpa_llanera', 'highlife_guitar', 'soukous_guitar', 'twelve_string', 'kalimba_thumb_piano',
           'pedal_steel', 'lap_steel', 'hawaiian_steel', 'cembalo', 'bianzhong', 'tubular_chime', 'taiko_pitched'}
# (depth cents, rate Hz, delay s): wide, slow vibrato on bowed and voice-like world instruments
VIBRATO = {'erhu': (30, 5.2, 0.25), 'gaohu': (26, 5.6, 0.2), 'kamancheh': (24, 5.4, 0.25), 'kemence': (24, 5.4, 0.25),
           'rebab': (22, 5.0, 0.3), 'sarangi': (34, 5.0, 0.2), 'arabic_violin': (22, 5.5, 0.25), 'haegeum': (28, 5.0, 0.25),
           'ney': (12, 4.6, 0.4), 'nay': (12, 4.6, 0.4), 'duduk': (14, 4.4, 0.3), 'bansuri': (10, 4.8, 0.35),
           'dizi': (8, 5.0, 0.3), 'xiao': (12, 4.6, 0.35), 'shinobue': (7, 5.0, 0.3), 'quena': (7, 4.6, 0.3),
           'indian_harmonium': (0, 5, 0), 'zurna': (6, 5.2, 0.3), 'masenqo': (24, 5.0, 0.3)}

INSTRUMENTS.update({
    'rudra_veena': 'sitar', 'mohan_veena': 'steel_guitar', 'carnatic_mandolin': 'steel_guitar', 'chitravina': 'steel_guitar',
    'gottuvadyam': 'steel_guitar', 'kuzhal': 'oboe', 'pungi': 'shehnai', 'nagaswaram': 'shehnai', 'kamaicha': 'violin',
    'ravanahatha': 'violin', 'khamak': 'banjo', 'gogona': 'kalimba', 'pepa': 'oboe', 'morchang': 'kalimba', 'algoza': 'recorder',
})
SUSTAINED |= {'kuzhal', 'pungi', 'nagaswaram', 'kamaicha', 'ravanahatha', 'pepa', 'algoza'}
BOWED |= {'kamaicha', 'ravanahatha'}
PLUCKED |= {'rudra_veena', 'mohan_veena', 'carnatic_mandolin', 'chitravina', 'gottuvadyam', 'khamak', 'gogona', 'morchang'}
VIBRATO.update({'kamaicha': (28, 5.0, 0.25), 'ravanahatha': (26, 5.0, 0.3), 'kuzhal': (8, 4.8, 0.3)})

# ------------------------------------------------------------------------------------------------
# 3. drum and percussion names (General MIDI percussion keys). The kit is 'standard'; these are only new names.
#    Hands-on drums are stand-ins: a darbuka dum is a low conga, a tabla ge is a low conga, a taiko don is the floor tom.
# ------------------------------------------------------------------------------------------------
DRUM_KEYS = {
    'dum': 64, 'tak': 60, 'ka': 62, 'tek': 60,                                 # darbuka / doumbek: dum bass, tak edge, ka mute
    'riq': 54, 'daf': 41, 'bendir': 41, 'req_jingle': 54, 'zil': 55, 'def': 41,
    'tabla_ge': 64, 'tabla_na': 60, 'tabla_tin': 63, 'tabla_ti': 61, 'tabla_ka': 62,   # bayan open, dayan rim, dayan open, dayan mute
    'dholak_bass': 43, 'dholak_treble': 61, 'dhol_bass': 43, 'dhol_stick': 48, 'mridangam_thom': 64, 'mridangam_tha': 60,
    'ghatam': 62, 'kanjira': 61, 'manjira': 67, 'khartal': 76,
    'taiko_don': 43, 'taiko_ka': 37, 'taiko_high': 48, 'janggu': 45, 'buk': 43, 'gong_small': 53, 'kkwaenggwari': 56,
    'temple_block': 77, 'woodblock_high': 76, 'woodblock_low': 77, 'tom_pair': 45,
    'djembe_bass': 64, 'djembe_tone': 63, 'djembe_slap': 60, 'shekere': 70, 'hosho': 82, 'talking_drum': 47,
    'bombo': 43, 'caja': 61, 'cajon_bass': 36, 'cajon_slap': 38, 'palmas': 39, 'palmas_sorda': 39, 'tambora_low': 41,
    'guira': 73, 'guiro_long': 74, 'cuica_mute': 78, 'cuica_open': 79, 'mute_triangle': 80, 'open_triangle': 81,
    'surdo': 43, 'surdo_mute': 41, 'tamborim': 65, 'repinique': 48, 'caixa': 40, 'pandeiro_hit': 54, 'pandeiro_slap': 60,
    'agogo_hi': 67, 'agogo_lo': 68, 'ganza': 70, 'chocalho': 70, 'zabumba_bass': 43, 'zabumba_treble': 47,
    'cowbell_low': 56, 'bell_tree_up': 84, 'castanets': 85, 'maracas_2': 70, 'conga_slap': 62, 'timbale_rim': 37,
    'log_tom': 45, 'gankogui': 56, 'boomba': 43,
}

DRUM_KEYS.update({
    'pakhawaj_bass': 41, 'pakhawaj_treble': 47, 'thavil_bass': 43, 'thavil_stick': 48, 'chenda_hit': 48, 'chenda_roll': 45,
    'elathalam': 55, 'dandiya_stick': 75, 'dholki_hi': 61, 'parai': 45, 'urumi': 43, 'udukku': 61, 'chimta': 54,
})

# ------------------------------------------------------------------------------------------------
# 4. grooves for the 16-step grid (4/4, step 0 = beat 1). Same format as theory.GROOVES.
#    ('practice' unless the comment says sourced). For odd-length cycles use cycle_notes() below.
# ------------------------------------------------------------------------------------------------
GROOVES = {
    # India
    'teental': ('practice', {'tabla_ge': [0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 14, 15], 'tabla_na': [0, 3, 4, 7, 8, 11, 12, 15],
                             'tabla_tin': [1, 2, 5, 6, 9, 10, 13, 14]},
                {'tabla_ge': .75, 'tabla_na': .6, 'tabla_tin': .5}),           # Dha Dhin Dhin Dha | Dha Dhin Dhin Dha | Dha Tin Tin Ta | Ta Dhin Dhin Dha
    'keherwa': ('practice', {'tabla_ge': [0, 2, 12], 'tabla_na': [0, 4, 8, 14], 'tabla_ti': [6], 'tabla_ka': [10]},
                {'tabla_ge': .8, 'tabla_na': .6, 'tabla_ti': .45, 'tabla_ka': .4}),  # Dha Ge Na Ti Na Ka Dhi Na, one matra = an eighth
    'bollywood': ('practice', {'dholak_bass': [0, 3, 8, 10], 'dholak_treble': [4, 6, 12, 14], 'kick': [0, 8],
                               'tambourine': [2, 6, 10, 14], 'shaker': list(range(0, 16, 2))},
                  {'dholak_bass': .75, 'dholak_treble': .55, 'kick': .6, 'tambourine': .4, 'shaker': .3}),
    'bhangra': ('practice', {'dhol_bass': [0, 4, 8, 10, 12], 'dhol_stick': [2, 6, 10, 14], 'rim': [7, 15]},
                {'dhol_bass': .95, 'dhol_stick': .7, 'rim': .35}),
    'qawwali': ('practice', {'dholak_bass': [0, 3, 8, 11], 'dholak_treble': [4, 6, 12, 14], 'clap': [0, 4, 8, 12],
                             'tambourine': list(range(0, 16, 2))},
                {'dholak_bass': .7, 'dholak_treble': .55, 'clap': .55, 'tambourine': .3}),
    'adi': ('practice', {'mridangam_thom': [0, 6, 8, 10], 'mridangam_tha': [2, 4, 12, 14], 'kanjira': [3, 7, 11, 15]},
            {'mridangam_thom': .8, 'mridangam_tha': .6, 'kanjira': .4}),       # Carnatic adi tala (8 beats) on a 4/4 grid
    # Arabic / Turkish / Persian: dum = bass, tak = edge ('sourced' for the cycles' names and lengths; the stroke positions are standard practice)
    'maqsum': ('practice', {'dum': [0, 8], 'tak': [2, 6, 12], 'riq': list(range(0, 16, 2))}, {'dum': .9, 'tak': .6, 'riq': .25}),
    'baladi': ('practice', {'dum': [0, 2, 8], 'tak': [6, 12], 'riq': list(range(0, 16, 2))}, {'dum': .9, 'tak': .6, 'riq': .25}),
    'saidi': ('practice', {'dum': [0, 6, 8], 'tak': [2, 12], 'riq': list(range(0, 16, 2))}, {'dum': .9, 'tak': .6, 'riq': .25}),
    'wahda': ('practice', {'dum': [0], 'tak': [6, 10], 'riq': list(range(0, 16, 2))}, {'dum': .9, 'tak': .55, 'riq': .2}),
    'ayyub': ('practice', {'dum': [0, 3, 8, 11], 'tak': [4, 6, 12, 14]}, {'dum': .85, 'tak': .55}),    # 2/4 cycle played twice per 4/4 bar
    'dabke': ('practice', {'dum': [0, 4, 8, 12], 'tak': [2, 6, 10, 14], 'riq': list(range(16))}, {'dum': .9, 'tak': .6, 'riq': .22}),
    'mahraganat': ('practice', {'kick': [0, 6, 8, 14], 'clap': [4, 12], 'tak': [2, 10, 15], 'hat_closed': list(range(0, 16, 2))},
                   {'kick': .9, 'clap': .8, 'tak': .55, 'hat_closed': .35}),
    'sofyan': ('practice', {'dum': [0], 'tak': [8, 12]}, {'dum': .9, 'tak': .6}),             # Düüm Tek Tek: 4/4, the first stroke held two beats
    'duyek': ('sourced', {'dum': [0, 8], 'tak': [2, 6, 12]}, {'dum': .9, 'tak': .6}),             # Düm Teek Tek Düm Teek (8/8): same strokes as maqsum
    'zeybek_4': ('practice', {'dum': [0, 8], 'tak': [4, 12], 'daf': [2, 6, 10, 14]}, {'dum': .85, 'tak': .55, 'daf': .3}),
    'tombak': ('practice', {'dum': [0, 3, 8, 10], 'tak': [2, 6, 12, 14], 'ka': [5, 11]}, {'dum': .85, 'tak': .55, 'ka': .35}),
    # East Asia
    'taiko_matsuri': ('practice', {'taiko_don': [0, 3, 8, 10], 'taiko_ka': [4, 12, 14], 'taiko_high': [6, 15]},
                      {'taiko_don': .95, 'taiko_ka': .6, 'taiko_high': .5}),
    'trot': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'tambourine': [2, 6, 10, 14], 'hat_closed': list(range(0, 16, 2))},
             {'kick': .8, 'snare': .75, 'tambourine': .45, 'hat_closed': .3}),                  # ppongjjak: a bouncing two-step
    'kpop': ('practice', {'kick': [0, 6, 8, 14], 'clap': [4, 12], 'snare': [4, 12], 'hat_closed': list(range(16)),
                          'hat_open': [14]},
             {'kick': .95, 'clap': .8, 'snare': .55, 'hat_closed': .3, 'hat_open': .4}),
    'kpop_dance': ('practice', {'kick': [0, 4, 8, 12], 'clap': [4, 12], 'hat_open': [2, 6, 10, 14], 'hat_closed': list(range(1, 16, 2))},
                   {'kick': .95, 'clap': .8, 'hat_open': .4, 'hat_closed': .25}),
    'city_pop': ('practice', {'kick': [0, 7, 10], 'snare': [4, 12], 'hat_closed': list(range(0, 16, 2)), 'hat_open': [14]},
                 {'kick': .85, 'snare': .85, 'hat_closed': .4, 'hat_open': .35}),
    'jpop': ('practice', {'kick': [0, 8, 10], 'snare': [4, 12], 'hat_closed': list(range(0, 16, 2))},
             {'kick': .9, 'snare': .9, 'hat_closed': .45}),
    'gamelan_kendang': ('practice', {'tabla_ge': [0, 8], 'tabla_na': [3, 6, 11, 14], 'tabla_ka': [10]},
                        {'tabla_ge': .8, 'tabla_na': .5, 'tabla_ka': .4}),
    # Rio and Brazil (BPM ranges for most of these are from lumbeat.com's rhythm guide)
    'pagode': ('practice', {'surdo': [8], 'surdo_mute': [0], 'tamborim': [0, 3, 6, 10, 12], 'pandeiro_hit': list(range(0, 16, 2)),
                            'cuica_open': [14], 'ganza': list(range(1, 16, 2))},
               {'surdo': .8, 'surdo_mute': .5, 'tamborim': .5, 'pandeiro_hit': .35, 'cuica_open': .3, 'ganza': .2}),
    'partido_alto': ('practice', {'surdo': [8], 'surdo_mute': [0], 'tamborim': [1, 3, 6, 9, 11, 14], 'pandeiro_hit': list(range(0, 16, 2)),
                                  'agogo_hi': [0, 3, 6, 10, 12], 'ganza': list(range(1, 16, 2))},
                     {'surdo': .8, 'surdo_mute': .5, 'tamborim': .5, 'pandeiro_hit': .35, 'agogo_hi': .4, 'ganza': .2}),
    'samba_enredo': ('practice', {'surdo': [8], 'surdo_mute': [0, 4, 12], 'caixa': list(range(16)), 'tamborim': [0, 3, 6, 10, 12],
                                  'agogo_hi': [0, 3, 6, 10, 12], 'repinique': [14, 15]},
                     {'surdo': .9, 'surdo_mute': .6, 'caixa': .3, 'tamborim': .5, 'agogo_hi': .4, 'repinique': .6}),
    'baiao': ('practice', {'zabumba_bass': [0, 6, 8, 14], 'zabumba_treble': [4, 12], 'triangle': [0, 3, 4, 7, 8, 11, 12, 15]},
              {'zabumba_bass': .8, 'zabumba_treble': .55, 'triangle': .4}),
    'maracatu': ('practice', {'tom_floor': [0, 3, 6, 8, 11, 14], 'caixa': [2, 4, 7, 10, 12, 15], 'agogo_lo': [0, 6, 10], 'ganza': list(range(0, 16, 2))},
                 {'tom_floor': .9, 'caixa': .5, 'agogo_lo': .5, 'ganza': .25}),
    'frevo': ('practice', {'snare': list(range(0, 16, 2)), 'kick': [0, 8], 'rim': [4, 12], 'surdo': [0, 8]},
              {'snare': .4, 'kick': .7, 'rim': .6, 'surdo': .7}),
    'funk_carioca': ('practice', {'kick': [0, 3, 6, 10, 12], 'clap': [4, 12], 'hat_closed': list(range(0, 16, 2)), 'cowbell': [2, 7, 14]},
                     {'kick': .95, 'clap': .75, 'hat_closed': .3, 'cowbell': .35}),         # tamborzao: boom-ch-boom boom-ch, 130-150 BPM
    'choro': ('practice', {'pandeiro_hit': list(range(0, 16, 2)), 'pandeiro_slap': [4, 12], 'tamborim': [3, 11]},
              {'pandeiro_hit': .35, 'pandeiro_slap': .5, 'tamborim': .3}),
    'axe': ('practice', {'surdo': [0, 8], 'repinique': [6, 14], 'caixa': [4, 12], 'agogo_hi': list(range(0, 16, 4)), 'ganza': list(range(0, 16, 2))},
            {'surdo': .9, 'repinique': .6, 'caixa': .6, 'agogo_hi': .4, 'ganza': .25}),
    'samba_reggae': ('practice', {'surdo': [0, 3, 8, 11], 'caixa': [4, 12], 'agogo_lo': [0, 6, 10], 'ganza': list(range(0, 16, 2))},
                     {'surdo': .9, 'caixa': .6, 'agogo_lo': .45, 'ganza': .25}),
    # Latin, Caribbean, Africa, Europe, Americas
    'bachata': ('practice', {'bongo_high': [0, 2, 4, 6, 8, 10, 12, 14], 'guira': list(range(0, 16, 2)), 'kick': [0, 8],
                             'conga_mute': [4, 12]},
                {'bongo_high': .35, 'guira': .3, 'kick': .6, 'conga_mute': .5}),
    'merengue': ('practice', {'tambora_low': [0, 2, 4, 6, 8, 10, 12, 14], 'conga_open': [2, 6, 10, 14], 'guira': list(range(16))},
                 {'tambora_low': .5, 'conga_open': .5, 'guira': .25}),
    'tango': ('practice', {'kick': [0, 4, 8, 12], 'snare': [6, 14], 'tom_floor': [10]}, {'kick': .6, 'snare': .6, 'tom_floor': .5}),
    'ranchera': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'guiro': list(range(0, 16, 4))}, {'kick': .5, 'snare': .5, 'guiro': .25}),
    'soca': ('practice', {'kick': [0, 4, 8, 12], 'snare': [6, 14], 'cowbell': [2, 10], 'shaker': list(range(0, 16, 2))},
             {'kick': .9, 'snare': .7, 'cowbell': .45, 'shaker': .3}),
    'calypso': ('practice', {'kick': [0, 8], 'rim': [3, 6, 11, 14], 'shaker': list(range(0, 16, 2))}, {'kick': .7, 'rim': .5, 'shaker': .3}),
    'highlife': ('practice', {'kick': [0, 8], 'rim': [4, 12], 'agogo_hi': [0, 3, 6, 10, 12], 'shekere': list(range(0, 16, 2))},
                 {'kick': .7, 'rim': .6, 'agogo_hi': .4, 'shekere': .3}),
    'soukous': ('practice', {'kick': [0, 4, 8, 12], 'snare': [4, 12], 'hat_closed': list(range(16)), 'conga_open': [3, 7, 11, 15]},
                {'kick': .8, 'snare': .6, 'hat_closed': .3, 'conga_open': .4}),
    'amapiano': ('practice', {'kick': [0, 8], 'log_tom': [3, 6, 10, 14], 'shaker': list(range(16)), 'clap': [4, 12]},
                 {'kick': .85, 'log_tom': .7, 'shaker': .28, 'clap': .55}),
    'kora_6': ('practice', {'hosho': list(range(0, 16, 2)), 'djembe_bass': [0, 8], 'djembe_tone': [4, 12], 'djembe_slap': [6, 14]},
               {'hosho': .35, 'djembe_bass': .8, 'djembe_tone': .55, 'djembe_slap': .5}),
    'huayno': ('practice', {'bombo': [0, 6, 8, 14], 'caja': [4, 12], 'guiro': list(range(0, 16, 2))}, {'bombo': .8, 'caja': .5, 'guiro': .3}),
    'rumba_flamenca': ('practice', {'cajon_bass': [0, 6, 8], 'cajon_slap': [4, 12], 'palmas': [2, 10, 14]},
                       {'cajon_bass': .8, 'cajon_slap': .65, 'palmas': .45}),
    'oompah': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'hat_closed': list(range(0, 16, 2))}, {'kick': .8, 'snare': .65, 'hat_closed': .3}),
    'bodhran': ('practice', {'tom_low': [0, 2, 4, 6, 8, 10, 12, 14], 'tom_mid': [6, 14]}, {'tom_low': .6, 'tom_mid': .5}),
    'two_step': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'hat_closed': list(range(0, 16, 2))}, {'kick': .75, 'snare': .6, 'hat_closed': .3}),
    'disco': ('practice', {'kick': [0, 4, 8, 12], 'snare': [4, 12], 'clap': [4, 12], 'hat_open': [2, 6, 10, 14], 'hat_closed': list(range(1, 16, 2))},
              {'kick': .9, 'snare': .6, 'clap': .5, 'hat_open': .5, 'hat_closed': .25}),
    'gospel_clap': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'clap': [4, 12], 'tambourine': list(range(0, 16, 2))},
                    {'kick': .6, 'snare': .5, 'clap': .8, 'tambourine': .4}),
}

GROOVES.update({
    'garba': ('practice', {'dhol_bass': [0, 4, 8, 12], 'dholak_treble': [2, 6, 10, 14], 'clap': [0, 4, 8], 'shaker': list(range(1, 16, 2))},
              {'dhol_bass': .9, 'dholak_treble': .55, 'clap': .7, 'shaker': .25}),          # three claps (3 taali) then a gap
    'dandiya': ('practice', {'dhol_bass': [0, 8], 'dhol_stick': [4, 12], 'dandiya_stick': list(range(0, 16, 2)), 'dholak_treble': [6, 14]},
                {'dhol_bass': .9, 'dhol_stick': .7, 'dandiya_stick': .45, 'dholak_treble': .5}),
    'lavani': ('practice', {'dholak_bass': [0, 3, 6, 8, 11, 14], 'dholak_treble': [2, 5, 10, 13], 'manjira': list(range(0, 16, 2))},
               {'dholak_bass': .8, 'dholak_treble': .6, 'manjira': .3}),
    'bihu': ('practice', {'dhol_bass': [0, 3, 8, 11], 'dhol_stick': [4, 6, 12, 14], 'clap': [2, 10]},
             {'dhol_bass': .9, 'dhol_stick': .65, 'clap': .5}),
    'baul': ('practice', {'dholak_treble': [0, 4, 8, 12], 'tabla_ka': [2, 6, 10, 14], 'manjira': [0, 4, 8, 12]},
             {'dholak_treble': .55, 'tabla_ka': .35, 'manjira': .3}),
    'bhajan': ('practice', {'dholak_bass': [0, 8], 'dholak_treble': [2, 4, 6, 12, 14], 'manjira': list(range(0, 16, 2)), 'clap': [4, 12]},
               {'dholak_bass': .75, 'dholak_treble': .5, 'manjira': .3, 'clap': .5}),
    'sufi': ('practice', {'dholak_bass': [0, 3, 8, 11], 'dholak_treble': [6, 14], 'daf': [4, 12], 'tambourine': list(range(0, 16, 4))},
             {'dholak_bass': .7, 'dholak_treble': .5, 'daf': .55, 'tambourine': .3}),
    'dhrupad': ('practice', {'pakhawaj_bass': [0, 4, 8, 10], 'pakhawaj_treble': [2, 6, 12, 14]},
                {'pakhawaj_bass': .8, 'pakhawaj_treble': .5}),
    'rajasthani': ('practice', {'dholak_bass': [0, 4, 8, 12], 'dholak_treble': [2, 6, 10, 14], 'khartal': list(range(1, 16, 2))},
                   {'dholak_bass': .8, 'dholak_treble': .55, 'khartal': .35}),
    'chenda': ('practice', {'chenda_hit': [0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14], 'chenda_roll': [3, 7, 11, 15], 'thavil_bass': [0, 8],
                            'elathalam': [0, 4, 8, 12]},
               {'chenda_hit': .6, 'chenda_roll': .4, 'thavil_bass': .8, 'elathalam': .45}),
    'gaana': ('practice', {'parai': [0, 3, 6, 8, 11, 14], 'thavil_stick': [2, 4, 10, 12], 'kick': [0, 8], 'urumi': [7, 15]},
              {'parai': .85, 'thavil_stick': .6, 'kick': .6, 'urumi': .5}),
    'tamil_film': ('practice', {'kick': [0, 8, 10], 'snare': [4, 12], 'thavil_stick': [3, 6, 14], 'hat_closed': list(range(0, 16, 2)),
                                'udukku': [7, 15]},
                   {'kick': .85, 'snare': .8, 'thavil_stick': .45, 'hat_closed': .35, 'udukku': .35}),
    'desi_hiphop': ('practice', {'kick': [0, 7, 10], 'snare': [4, 12], 'hat_closed': list(range(16)), 'dhol_stick': [6, 14]},
                    {'kick': .95, 'snare': .85, 'hat_closed': .3, 'dhol_stick': .45}),
    'indipop': ('practice', {'kick': [0, 8], 'snare': [4, 12], 'tabla_na': [2, 6, 10, 14], 'hat_closed': list(range(0, 16, 2))},
                {'kick': .75, 'snare': .6, 'tabla_na': .35, 'hat_closed': .3}),
    'retro_filmi': ('practice', {'bongo_high': [0, 3, 6, 8, 11, 14], 'conga_open': [2, 10], 'kick': [0, 8], 'tambourine': list(range(0, 16, 2))},
                    {'bongo_high': .5, 'conga_open': .5, 'kick': .55, 'tambourine': .35}),
    'indian_lofi': ('practice', {'kick': [0, 10], 'rim': [4, 12], 'tabla_na': [6, 14], 'hat_closed': list(range(0, 16, 2))},
                    {'kick': .6, 'rim': .45, 'tabla_na': .3, 'hat_closed': .22}),
})

# ------------------------------------------------------------------------------------------------
# 5. rhythm cycles of any length. One cycle = `beats` matras (counting units; set the bpm to the matra,
#    and the score's ts to [beats, 4]). hits are (position in matras, drum name, weight). 'sourced' lengths and
#    stroke names come from the pages in references/scoring/world-music.md; patterns of 12 are the common accent maps.
# ------------------------------------------------------------------------------------------------
def _hits(pattern):
    """'D..T.D..' style strings -> hit lists. D=dum/bass, T=tak/treble, t=soft, k=mute, X=accent, .=rest"""
    m = {'D': ('dum', .9), 'T': ('tak', .62), 't': ('tak', .38), 'k': ('ka', .4), 'X': ('dum', 1.0), 'b': ('tabla_ge', .8),
         'n': ('tabla_na', .6), 'i': ('tabla_tin', .5), 'c': ('palmas', .75), 's': ('palmas_sorda', .45), 'g': ('cajon_bass', .85),
         'r': ('cajon_slap', .7), 'h': ('hat_closed', .35)}
    return [(i, m[ch][0], m[ch][1]) for i, ch in enumerate(pattern) if ch in m]


CYCLES = {
    # Turkish usul (all 'sourced' from the ritmik.net bendir guide; positions in eighth-note matras). D=düm, T=tek
    'nim_sofyan': dict(beats=4, hits=_hits('D.T.')),
    'semai': dict(beats=6, hits=_hits('D.T.T.')),
    'sofyan': dict(beats=8, hits=_hits('D...T.T.')),
    'turk_aksagi': dict(beats=5, hits=_hits('D.T.T')),
    'yuruk_semai': dict(beats=6, hits=_hits('DTTDT.')),
    'devr_i_hindi': dict(beats=7, hits=_hits('DTTD.T.')),
    'duyek': dict(beats=8, hits=_hits('DT.TD.T.')),
    'aksak': dict(beats=9, hits=_hits('D.TTD.T.T')),
    'karsilama': dict(beats=9, hits=_hits('D.t.tD.TT')),
    'curcuna': dict(beats=10, hits=_hits('D.Tt.D.T.T')),
    # Arabic iqa'at (lengths 'sourced' from maqamworld.com; strokes are the standard dum/tak skeletons)
    'maqsum': dict(beats=8, hits=_hits('DT.TD.T.')),
    'baladi': dict(beats=8, hits=_hits('DD.TD.T.')),
    'saidi': dict(beats=8, hits=_hits('DT.DD.T.')),
    'malfuf': dict(beats=6, hits=_hits('D.TT.T')),
    'ayyub': dict(beats=8, hits=[(0, 'dum', .9), (3, 'dum', .8), (4, 'tak', .6), (6, 'tak', .6)]),
    'masmudi_kabir': dict(beats=16, hits=_hits('DD.T..D.T.D.T...')),
    # Indian tala: matras (pulses). bols as tabla strokes: b=ge(bayan) n=na(dayan) i=tin(open dayan)
    'dadra': dict(beats=6, hits=[(0, 'tabla_ge', .8), (0, 'tabla_na', .6), (2, 'tabla_na', .5), (3, 'tabla_ge', .8), (3, 'tabla_na', .6), (5, 'tabla_na', .5)]),
    'rupak': dict(beats=7, hits=[(0, 'tabla_tin', .55), (1, 'tabla_tin', .5), (2, 'tabla_na', .5), (3, 'tabla_ge', .8), (3, 'tabla_na', .6), (4, 'tabla_na', .5),
                                 (5, 'tabla_ge', .8), (5, 'tabla_na', .6), (6, 'tabla_na', .5)]),                           # 3+2+2, begins on the open (khali) stroke
    'jhaptal': dict(beats=10, hits=[(0, 'tabla_ge', .8), (1, 'tabla_na', .55), (2, 'tabla_ge', .8), (2, 'tabla_na', .6), (3, 'tabla_na', .5),
                                    (4, 'tabla_na', .5), (5, 'tabla_tin', .55), (6, 'tabla_na', .5), (7, 'tabla_ge', .8), (7, 'tabla_na', .6), (8, 'tabla_na', .5), (9, 'tabla_na', .5)]),  # 2+3+2+3
    'ektal': dict(beats=12, hits=[(p, 'tabla_ge', .75) for p in (0, 1, 2, 3, 8, 9, 10, 11)] + [(p, 'tabla_tin', .5) for p in (4, 5, 6, 7)]
                  + [(p, 'tabla_na', .55) for p in (0, 2, 8, 10)]),                                                           # 2+2+2+2+2+2
    # Flamenco compas: 12 counts. c=palmas (clap), s=soft palmas. Accents on 3 6 8 10 12 (counting from the 12 of the last bar)
    'solea': dict(beats=12, hits=[(p, 'palmas', .85 if p in (2, 5, 7, 9, 11) else .4) for p in (2, 5, 7, 9, 11)] + [(p, 'palmas_sorda', .35) for p in (0, 1, 3, 4, 6, 8, 10)]),
    'buleria': dict(beats=12, hits=[(p, 'palmas', .9) for p in (2, 5, 7, 9, 11)] + [(p, 'palmas_sorda', .3) for p in (0, 1, 3, 4, 6, 8, 10)]),
    'alegrias': dict(beats=12, hits=[(p, 'palmas', .85) for p in (2, 5, 7, 9, 11)]),
    'seguiriya': dict(beats=12, hits=[(p, 'palmas', .8) for p in (0, 3, 5, 7, 9)]),                                         # 12 counts that start on beat 1 of a different grouping
    # Balkan / Greek / Celtic / others (practice)
    'zeibekiko': dict(beats=9, hits=_hits('D.t.tD.tt')),                      # 9/4, slow
    'kalamatianos': dict(beats=7, hits=_hits('D.tD.t.')),                    # 7/8, 3+2+2
    'jig': dict(beats=6, hits=[(0, 'tom_low', .8), (3, 'tom_low', .6), (1, 'tom_mid', .35), (2, 'tom_mid', .35), (4, 'tom_mid', .35), (5, 'tom_mid', .35)]),
    'waltz_3': dict(beats=3, hits=[(0, 'kick', .8), (1, 'hat_closed', .4), (2, 'hat_closed', .4)]),
    'take_five_5': dict(beats=5, hits=[(0, 'kick', .85), (3, 'snare', .75), (2, 'hat_closed', .4), (1, 'hat_closed', .3), (4, 'hat_closed', .3)]),
    'seven_8': dict(beats=7, hits=[(0, 'kick', .85), (2, 'snare', .7), (4, 'snare', .7), (1, 'hat_closed', .3), (3, 'hat_closed', .3), (5, 'hat_closed', .3), (6, 'hat_closed', .3)]),
}

# Carnatic chapu cycles: the lengths (7 and 5 beats) are 'sourced' from melodigging.com's Tamil film page; accents are practice
CYCLES.update({
    'misra_chapu': dict(beats=7, hits=[(0, 'mridangam_thom', .85), (1, 'mridangam_tha', .45), (2, 'mridangam_tha', .45), (3, 'mridangam_thom', .7),
                                       (4, 'mridangam_tha', .45), (5, 'mridangam_thom', .7), (6, 'mridangam_tha', .45)]),
    'kanda_chapu': dict(beats=5, hits=[(0, 'mridangam_thom', .85), (1, 'mridangam_tha', .45), (2, 'mridangam_thom', .7), (3, 'mridangam_tha', .45),
                                       (4, 'mridangam_tha', .45)]),
    'chautal': dict(beats=12, hits=[(p, 'pakhawaj_bass', .8) for p in (0, 2, 4, 8, 10)] + [(p, 'pakhawaj_treble', .5) for p in (1, 3, 5, 9, 11)]),
    # from the global theory KB (practice: its groupings, the accents are choices; check by ear)
    'adi_8': dict(beats=8, hits=[(0, 'mridangam_thom', .85), (4, 'mridangam_thom', .7), (6, 'mridangam_thom', .7)]
                  + [(p, 'mridangam_tha', .4) for p in (1, 2, 3, 5, 7)]),                       # 4+2+2
    'rupaka_3': dict(beats=3, hits=[(0, 'mridangam_thom', .8), (1, 'mridangam_tha', .5), (2, 'mridangam_tha', .5)]),   # 1 | 2 3 as the KB writes it
    'samai_thaqil': dict(beats=5, hits=[(0, 'dum', .9), (1.5, 'tak', .6), (2, 'tak', .6), (2.5, 'dum', .8), (3.5, 'tak', .6), (4, 'tak', .6), (4.5, 'ka', .5)]),  # 10/8 = 3+2+2+3 in 5 beats
    'gankogui_12_8': dict(beats=4, hits=[(k / 3, 'gankogui', .55 + .1 * (i == 0)) for i, k in enumerate([0, 2, 4, 5, 7, 9, 11])]),   # West African bell on the 12 grid
})


def cycle_notes(name, bars=1, start=0.0, vel=0.7, matra=0.5, rng=None):
    """A named cycle as drum notes {'t','d','p','v'} for a custom score (see references/scoring/world-music.md section 6).
    `matra` is how many score beats one counting unit lasts (0.5 = an eighth of a quarter-note beat).
    The score's ts should be [beats, 4] with the bpm counted in matras, or write the notes into a 4/4 score and
    accept the offset. Returns notes you can put straight into a drum track."""
    rng = rng or np.random.default_rng(1)
    c = CYCLES[name]
    out = []
    for b in range(int(bars)):
        for pos, piece, w in c['hits']:
            out.append(dict(t=float(start + (b * c['beats'] + pos) * matra), d=0.1, p=piece,
                            v=float(np.clip(vel * w * rng.uniform(0.93, 1.0), 0.05, 1.0))))
    return out


# ------------------------------------------------------------------------------------------------
# 6. genre presets, merged into compose.GENRES. Same layer format as compose.py. Extra layer keys used here:
#      micro (default True) apply the mode's cents to this layer; glide (0..1) share of notes that slide up into the pitch;
#      vibrato {depth_cents, rate_hz, delay_ms}; expression 'flat'|'bow'|'breath'
#    Extra genre keys: mode (default mode), prog (default chord symbols; sus chords avoid the neutral third of a maqam).
# ------------------------------------------------------------------------------------------------
def _L(name, instrument, kind, **k):
    return dict(name=name, instrument=instrument, kind=kind, **k)


_DRONE = lambda inst, lo=36, hi=52, mn=0.0, g=-5: _L('drone', inst, 'bass', bass='half', lo=lo, hi=hi, min=mn, role='bass', gain_db=g)
_PAD = lambda inst, lo=48, hi=67, mn=0.0, g=-8: _L('pad', inst, 'pad', lo=lo, hi=hi, min=mn, role='pad', gain_db=g)
_LEAD = lambda inst, **k: _L('lead', inst, 'melody', oct=k.pop('oct', 0), min=k.pop('min', 0.0), role='melody', **k)
_ALT = lambda inst, **k: _L('counter', inst, 'harmony', oct=k.pop('oct', 0), min=k.pop('min', 0.45), role='counter', **k)
_DR = lambda inst='standard', mn=0.0, g=-4: _L('drums', inst, 'drums', min=mn, role='drum', gain_db=g)
_SPK = lambda inst, lo=72, hi=96, mn=0.3, g=-6: _L('sparkle', inst, 'sparkle', lo=lo, hi=hi, min=mn, role='arp', gain_db=g)
_CH = lambda name, inst, t1, t2, t3, lo=48, hi=70, mn=0.0, g=0, **k: _L(name, inst, 'chords', tex_low=t1, tex_mid=t2, tex_hi=t3, lo=lo, hi=hi, min=mn, role='chord', gain_db=g, **k)
_BS = lambda inst, kind='half', lo=31, hi=48, mn=0.0, g=0: _L('bass', inst, 'bass', bass=kind, lo=lo, hi=hi, min=mn, role='bass', gain_db=g)

GENRES = {
    # ---- India ----
    'hindustani': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='teental', bpm=(60, 92),
                       mode='raga_yaman', prog='Isus2-Isus2-Isus2-Isus2', layers=[
        _DRONE('tanpura', 36, 55, 0.0, -4), _LEAD('bansuri', min=0.0, glide=0.45, gain_db=-1), _ALT('sarangi', min=0.5, glide=0.4, gain_db=-5),
        _SPK('santoor', 72, 91, 0.25, -7), _DR('standard', 0.15, -4)]),
    'carnatic': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-16, groove='adi', bpm=(90, 130),
                     mode='raga_bhairav', prog='Isus2-Isus2-IVsus2-Isus2', layers=[
        _DRONE('tanpura', 36, 55, 0.0, -4), _LEAD('violin', glide=0.5, gain_db=-1), _ALT('bansuri', min=0.4, glide=0.3, gain_db=-5),
        _SPK('veena', 60, 84, 0.3, -6), _DR('standard', 0.1, -4)]),
    'bollywood': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='bollywood', bpm=(96, 128),
                      mode='raga_bhairavi', prog='i-VI-VII-i', layers=[
        _CH('strings', 'string_ensemble', 'block', 'half', 'arp8', 45, 72, 0.0, -4), _LEAD('bansuri', glide=0.3, gain_db=-1),
        _ALT('sitar', min=0.4, gain_db=-5), _BS('finger_bass', 'sync', 31, 46, 0.1, 0), _SPK('santoor', 72, 91, 0.3, -7), _DR('standard', 0.0, -4)]),
    'bhangra': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='bhangra', bpm=(100, 126),
                    mode='mixolydian', prog='I-VII-IV-I', layers=[
        _LEAD('tumbi', oct=1, gain_db=-1), _CH('synth', 'polysynth', 'pulse', 'pulse', 'pulse', 48, 70, 0.2, -6), _BS('synth_bass', 'sync', 31, 46, 0.0, 0),
        _ALT('shehnai', min=0.5, gain_db=-5), _DR('standard', 0.0, -2)]),
    'qawwali': dict(room='hall', swing=0.5, humanize='loose', tone='warm', lufs=-14, groove='qawwali', bpm=(108, 140),
                    mode='raga_bhairavi', prog='Isus2-IVsus2-Isus2-Isus2', layers=[
        _CH('harmonium', 'indian_harmonium', 'block', 'block', 'half', 48, 70, 0.0, -2), _LEAD('sarangi', glide=0.4, gain_db=-1),
        _DRONE('tanpura', 36, 55, 0.0, -6), _DR('standard', 0.0, -3)]),
    'ghazal': dict(room='chamber', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='keherwa', bpm=(66, 90),
                   mode='raga_kafi', prog='i-IV-i-VII', layers=[
        _CH('harmonium', 'indian_harmonium', 'sparse', 'half', 'arp8', 48, 70, 0.0, -3), _LEAD('sarangi', glide=0.4, gain_db=-1),
        _SPK('santoor', 72, 91, 0.2, -6), _DRONE('tanpura', 36, 55, 0.0, -6), _DR('standard', 0.3, -6)]),
    # ---- Arabic, Turkish, Persian, Greek, Balkan, flamenco, klezmer ----
    'arabic_pop': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='maqsum', bpm=(92, 112),
                       mode='maqam_hijaz', prog='Isus2-Isus2-IVsus2-Isus2', layers=[
        _LEAD('arabic_violin', glide=0.35, gain_db=-1), _ALT('oud', min=0.2, gain_db=-4), _CH('strings', 'string_ensemble', 'block', 'half', 'half', 45, 70, 0.3, -7),
        _BS('synth_bass', 'sync', 31, 46, 0.0, -1), _SPK('qanun', 72, 93, 0.25, -6), _DR('standard', 0.0, -3)]),
    'tarab': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='wahda', bpm=(70, 104),
                  mode='maqam_rast', prog='Isus2-Isus2-IVsus2-Isus2', layers=[
        _LEAD('arabic_violin', glide=0.4, gain_db=-1), _ALT('ney', oct=0, min=0.3, glide=0.3, gain_db=-4), _CH('oud', 'oud', 'fingerpick', 'fingerpick', 'strum', 43, 67, 0.0, -2),
        _SPK('qanun', 72, 93, 0.3, -5), _DR('standard', 0.2, -5)]),
    'dabke': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='dabke', bpm=(116, 140),
                  mode='maqam_hijaz', prog='Isus2-IVsus2-Isus2-Isus2', layers=[
        _LEAD('mijwiz', glide=0.3, gain_db=-1), _CH('oud', 'oud', 'pulse', 'strum', 'strum', 43, 67, 0.0, -2),
        _BS('acoustic_bass', 'half', 31, 46, 0.0, 0), _SPK('qanun', 72, 93, 0.4, -6), _DR('standard', 0.0, -3)]),
    'mahraganat': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='mahraganat', bpm=(120, 140),
                       mode='maqam_hijaz', prog='Isus2-Isus2-VIIsus2-Isus2', layers=[
        _LEAD('mizmar', gain_db=-3), _CH('synth', 'saw_lead', 'pulse', 'pulse', 'pulse', 48, 70, 0.0, -9), _BS('synth_bass', 'sync', 28, 43, 0.0, 0), _DR('808', 0.0, -2)]),
    'turkish_classical': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='duyek', bpm=(68, 108),
                              mode='makam_hicaz', prog='Isus2-Isus2-IVsus2-Isus2', layers=[
        _LEAD('kemence', glide=0.35, gain_db=-1), _ALT('ney', min=0.3, glide=0.3, gain_db=-4), _CH('oud', 'oud', 'fingerpick', 'fingerpick', 'strum', 43, 67, 0.0, -2),
        _SPK('kanun', 72, 93, 0.3, -5), _DR('standard', 0.25, -5)]),
    'turkish_folk': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-15, groove='zeybek_4', bpm=(84, 120),
                         mode='makam_ussak', prog='Isus2-Isus2-VIIsus2-Isus2', layers=[
        _LEAD('saz', oct=0, gain_db=-1), _CH('baglama', 'baglama', 'strum', 'strum', 'strum', 43, 67, 0.0, -3), _ALT('zurna', min=0.5, gain_db=-5),
        _BS('acoustic_bass', 'half', 31, 46, 0.2, -1), _DR('standard', 0.0, -4)]),
    'arabesk': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-15, groove='maqsum', bpm=(86, 108),
                    mode='makam_hicaz', prog='Isus2-IVsus2-Isus2-Isus2', layers=[
        _LEAD('kemence', glide=0.4, gain_db=-1), _CH('strings', 'string_ensemble', 'block', 'half', 'half', 45, 70, 0.0, -6), _ALT('oud', min=0.3, gain_db=-4),
        _BS('finger_bass', 'half', 31, 46, 0.2, -1), _DR('standard', 0.0, -4)]),
    'persian': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='tombak', bpm=(76, 108),
                    mode='persian_shur', prog='Isus2-Isus2-IVsus2-Isus2', layers=[
        _LEAD('kamancheh', glide=0.3, gain_db=-1), _CH('santur', 'santur', 'arp16', 'arp16', 'arp16', 55, 84, 0.0, -4), _ALT('ney', min=0.4, glide=0.3, gain_db=-5),
        _DRONE('tar', 36, 52, 0.0, -7), _DR('standard', 0.3, -5)]),
    'flamenco': dict(room='studio', swing=0.5, humanize='loose', tone='bright', lufs=-14, groove='rumba_flamenca', bpm=(96, 124),
                     mode='phrygian_dominant', prog='i-VII-VI-V', layers=[
        _CH('guitar', 'nylon_guitar', 'strum', 'strum', 'arp16', 43, 67, 0.0, -1), _LEAD('nylon_guitar', gain_db=-3), _BS('acoustic_bass', 'half', 31, 46, 0.2, -1),
        _DR('standard', 0.0, -3)]),
    'greek': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-15, groove='two_step', bpm=(92, 124),
                  mode='makam_hicaz', prog='i-VII-i-V', layers=[
        _LEAD('bouzouki', glide=0.2, gain_db=-1), _CH('baglamas', 'baglamas', 'strum', 'strum', 'strum', 50, 74, 0.0, -4), _ALT('accordion', min=0.5, gain_db=-5),
        _BS('acoustic_bass', 'half', 31, 46, 0.1, -1), _DR('standard', 0.2, -5)]),
    'klezmer': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-14, groove='oompah', bpm=(104, 150),
                    mode='freygish', prog='i-iv-i-V', layers=[
        _LEAD('clarinet_klezmer', glide=0.5, gain_db=-1), _ALT('violin', min=0.4, glide=0.3, gain_db=-4), _CH('accordion', 'accordion', 'pulse', 'pulse', 'pulse', 48, 70, 0.0, -4),
        _BS('tuba', 'half', 28, 46, 0.0, 0), _DR('standard', 0.2, -5)]),
    # ---- East Asia ----
    'chinese_classical': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, bpm=(58, 92),
                              mode='chinese_gong', prog='I-vi-IV-V', layers=[
        _LEAD('erhu', glide=0.4, gain_db=-1), _CH('guzheng', 'guzheng', 'arp8', 'arp8', 'arp16', 50, 81, 0.0, -3), _ALT('dizi', oct=1, min=0.4, glide=0.2, gain_db=-5),
        _SPK('pipa', 67, 88, 0.3, -6), _BS('cello', 'whole', 33, 52, 0.5, -3)]),
    'guofeng': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='synthpop', bpm=(88, 112),
                    mode='chinese_yu', prog='i-VI-III-VII', layers=[
        _LEAD('dizi', glide=0.2, gain_db=-1), _CH('guzheng', 'guzheng', 'arp8', 'arp16', 'arp16', 55, 84, 0.0, -3), _ALT('erhu', min=0.4, glide=0.4, gain_db=-4),
        _CH('strings', 'string_ensemble', 'block', 'half', 'half', 45, 70, 0.2, -8), _BS('synth_bass', 'sync', 31, 46, 0.3, -1), _DR('electronic', 0.3, -4)]),
    'cpop': dict(room='studio', swing=0.5, humanize='natural', tone='neutral', lufs=-15, groove='soft_pulse', bpm=(68, 92),
                 mode='major', prog='I-V-vi-IV', layers=[
        _CH('piano', 'piano', 'sparse', 'arp8', 'arp8', 48, 72, 0.0, -2), _LEAD('piano', oct=0, min=0.1, gain_db=-2), _CH('guzheng', 'guzheng', 'arp16', 'arp16', 'arp16', 60, 84, 0.4, -7),
        _CH('strings', 'slow_strings', 'block', 'block', 'block', 45, 69, 0.3, -7), _BS('finger_bass', 'half', 31, 46, 0.4, -1), _DR('standard', 0.35, -6)]),
    'japanese_traditional': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, bpm=(54, 88),
                                 mode='hirajoshi', prog='i-VII-VI-i', layers=[
        _LEAD('shakuhachi', glide=0.35, gain_db=-1), _CH('koto', 'koto', 'arp8', 'arp8', 'arp16', 55, 84, 0.0, -2), _ALT('shamisen', min=0.4, gain_db=-5),
        _SPK('woodblock', 72, 84, 0.5, -10), _DRONE('taiko', 33, 45, 0.6, -10)]),
    'wadaiko': dict(room='large_hall', swing=0.5, humanize='tight', tone='warm', lufs=-13, groove='taiko_matsuri', bpm=(100, 148),
                    mode='yo', prog='I-IV-I-V', layers=[
        _DR('standard', 0.0, 0), _LEAD('shinobue', gain_db=-3), _CH('koto', 'koto', 'arp8', 'arp16', 'arp16', 55, 84, 0.3, -6),
        _BS('taiko', 'half', 33, 48, 0.3, -4)]),
    'enka': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-16, groove='soft_pulse', bpm=(60, 80),
                 mode='miyako_bushi', prog='i-iv-i-V', layers=[
        _LEAD('shakuhachi', glide=0.5, gain_db=-1), _CH('strings', 'slow_strings', 'block', 'block', 'half', 45, 69, 0.0, -5), _ALT('shamisen', min=0.3, gain_db=-4),
        _BS('acoustic_bass', 'half', 31, 46, 0.3, -2), _SPK('koto', 67, 88, 0.3, -6)]),
    'jpop': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='jpop', bpm=(124, 168),
                 mode='major', prog='IVmaj7-V-iii-vi', layers=[
        _CH('piano', 'piano', 'pulse', 'pulse', 'arp16', 50, 74, 0.0, -2), _LEAD('saw_lead', gain_db=-4), _CH('guitar', 'clean_guitar', 'pulse', 'strum', 'strum', 48, 72, 0.2, -4),
        _CH('strings', 'string_ensemble', 'block', 'half', 'half', 45, 70, 0.4, -8), _BS('pick_bass', 'pulse8', 31, 46, 0.1, 0), _DR('standard', 0.0, -3)]),
    'city_pop': dict(room='studio', swing=0.52, humanize='natural', tone='warm', lufs=-14, groove='city_pop', bpm=(98, 120),
                     mode='major', prog='IVmaj7-iii7-vi7-IImaj7', layers=[
        _CH('rhodes', 'epiano', 'comp', 'comp', 'comp', 50, 74, 0.0, -2, color='seventh'), _LEAD('alto_sax', gain_db=-2), _ALT('brass_section', min=0.55, gain_db=-6),
        _BS('slap_bass', 'sync', 31, 48, 0.0, 0), _CH('guitar', 'clean_guitar', 'chop', 'chop', 'chop', 52, 74, 0.3, -5), _DR('standard', 0.0, -4)]),
    'kpop': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='kpop', bpm=(96, 126),
                 mode='major', prog='vi-IV-I-V', layers=[
        _CH('synth', 'polysynth', 'pulse', 'pulse', 'arp16', 50, 74, 0.0, -4), _CH('piano', 'piano', 'pulse', 'pulse', 'pulse', 48, 70, 0.2, -5), _LEAD('saw_lead', gain_db=-4),
        _BS('synth_bass', 'sync', 28, 43, 0.0, 0), _L('pluck', 'pizzicato_strings', 'sparkle', lo=72, hi=96, min=0.35, role='arp', gain_db=-7), _DR('electronic', 0.0, -2)]),
    'kpop_dance': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-11, groove='kpop_dance', bpm=(116, 132),
                       mode='minor', prog='i-VI-III-VII', layers=[
        _CH('stabs', 'saw_lead', 'pulse', 'pulse', 'pulse', 50, 72, 0.0, -7), _LEAD('square_lead', gain_db=-4), _BS('synth_bass', 'pulse8', 28, 43, 0.0, 0),
        _CH('pad', 'warm_pad', 'block', 'block', 'block', 48, 70, 0.1, -9), _DR('electronic', 0.0, -2)]),
    'kpop_ballad': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-15, groove='soft_pulse', bpm=(66, 84),
                        mode='major', prog='I-V-vi-iii-IV-I-IV-V', layers=[
        _CH('piano', 'piano', 'sparse', 'arp8', 'arp8', 48, 72, 0.0, -2), _LEAD('piano', min=0.1, gain_db=-2), _CH('strings', 'slow_strings', 'block', 'block', 'block', 45, 69, 0.3, -5),
        _BS('cello', 'whole', 33, 52, 0.4, -2), _DR('standard', 0.35, -6)]),
    'trot': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-13, groove='trot', bpm=(112, 140),
                 mode='korean_gyemyeonjo', prog='i-iv-i-V', layers=[
        _LEAD('accordion', gain_db=-2), _CH('guitar', 'acoustic_guitar', 'strum', 'strum', 'strum', 45, 69, 0.0, -3), _ALT('violin', min=0.4, gain_db=-5),
        _BS('acoustic_bass', 'half', 31, 46, 0.0, -1), _DR('standard', 0.0, -4)]),
    'gamelan': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='gamelan_kendang', bpm=(60, 96),
                    mode='slendro', prog='I-I-V-I', layers=[
        _LEAD('gamelan_gender', gain_db=-1), _SPK('gamelan_bonang', 72, 96, 0.1, -4), _BS('gamelan_gong', 'whole', 36, 52, 0.0, -2), _ALT('suling', oct=1, min=0.5, gain_db=-5),
        _DR('standard', 0.3, -7)]),
    # ---- Rio and Brazil ----
    'pagode': dict(room='studio', swing=0.5, humanize='loose', tone='warm', lufs=-14, groove='pagode', bpm=(86, 108),
                   mode='major', prog='ii7-V7-Imaj7-vi7', layers=[
        _CH('cavaco', 'cavaquinho', 'strum', 'strum', 'strum', 55, 79, 0.0, -2), _CH('violao', 'violao_7', 'fingerpick', 'strum', 'strum', 45, 69, 0.0, -3, color='seventh'),
        _LEAD('flute', gain_db=-2), _BS('acoustic_bass', 'sync', 31, 48, 0.0, 0), _DR('standard', 0.0, -4)]),
    'samba_enredo': dict(room='large_hall', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='samba_enredo', bpm=(128, 142),
                         mode='major', prog='I-IV-V-I', layers=[
        _DR('standard', 0.0, 0), _CH('cavaco', 'cavaquinho', 'strum', 'strum', 'strum', 55, 79, 0.0, -3), _LEAD('trumpet', gain_db=-2),
        _BS('acoustic_bass', 'sync', 31, 48, 0.2, -1)]),
    'choro': dict(room='room_warm', swing=0.52, humanize='natural', tone='warm', lufs=-15, groove='choro', bpm=(80, 108),
                  mode='minor', prog='i-iv-V7-i', layers=[
        _LEAD('flute', gain_db=-1), _CH('violao', 'violao_7', 'fingerpick', 'fingerpick', 'strum', 45, 69, 0.0, -3), _ALT('cavaquinho', min=0.3, gain_db=-5),
        _BS('acoustic_bass', 'walk', 31, 48, 0.0, 0), _DR('standard', 0.2, -7)]),
    'funk_carioca': dict(room='plate', swing=0.5, humanize='tight', tone='bright', lufs=-11, groove='funk_carioca', bpm=(128, 150),
                         mode='minor', prog='i-i-VI-VII', layers=[
        _BS('synth_bass', 'sync', 26, 40, 0.0, 0), _LEAD('square_lead', gain_db=-5), _CH('stab', 'brass_section', 'pulse', 'pulse', 'pulse', 50, 72, 0.3, -9),
        _DR('808', 0.0, -2)]),
    'baiao': dict(room='studio', swing=0.5, humanize='loose', tone='warm', lufs=-14, groove='baiao', bpm=(86, 116),
                  mode='mixolydian', prog='I-VII-IV-I', layers=[
        _LEAD('accordion', gain_db=-1), _CH('violao', 'nylon_guitar', 'strum', 'strum', 'strum', 45, 69, 0.0, -3), _BS('acoustic_bass', 'sync', 31, 48, 0.0, 0), _DR('standard', 0.0, -5)]),
    'maracatu': dict(room='large_hall', swing=0.5, humanize='tight', tone='warm', lufs=-12, groove='maracatu', bpm=(86, 112),
                     mode='dorian', prog='i-IV-i-VII', layers=[
        _DR('standard', 0.0, 0), _L('alfaia', 'taiko', 'bass', bass='half', lo=33, hi=48, min=0.3, role='bass', gain_db=-5), _LEAD('trumpet', min=0.4, gain_db=-4),
        _CH('guitar', 'nylon_guitar', 'strum', 'strum', 'strum', 45, 69, 0.3, -6)]),
    'axe': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='axe', bpm=(120, 140),
                mode='major', prog='I-IV-V-IV', layers=[
        _CH('guitar', 'clean_guitar', 'chop', 'chop', 'chop', 48, 72, 0.0, -3), _LEAD('trumpet', gain_db=-3), _BS('slap_bass', 'sync', 31, 48, 0.0, 0), _DR('standard', 0.0, -2)]),
    'samba_reggae': dict(room='studio', swing=0.5, humanize='natural', tone='warm', lufs=-13, groove='samba_reggae', bpm=(84, 104),
                         mode='dorian', prog='i-IV-i-V', layers=[
        _DR('standard', 0.0, -1), _CH('guitar', 'clean_guitar', 'skank', 'skank', 'skank', 48, 72, 0.0, -4), _LEAD('trombone', min=0.2, gain_db=-3), _BS('finger_bass', 'sync', 31, 48, 0.0, 0)]),
    # ---- Latin, Caribbean, Africa, Andes ----
    'bachata': dict(room='studio', swing=0.5, humanize='natural', tone='warm', lufs=-14, groove='bachata', bpm=(116, 136),
                    mode='minor', prog='i-iv-V-i', layers=[
        _LEAD('steel_guitar', gain_db=-1), _CH('rhythm', 'nylon_guitar', 'fingerpick', 'fingerpick', 'arp16', 45, 69, 0.0, -4), _BS('finger_bass', 'sync', 31, 48, 0.0, 0), _DR('standard', 0.0, -5)]),
    'merengue': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='merengue', bpm=(126, 160),
                     mode='major', prog='I-IV-V-I', layers=[
        _LEAD('accordion', gain_db=-1), _BS('acoustic_bass', 'half', 31, 48, 0.0, 0), _ALT('alto_sax', min=0.5, gain_db=-5), _DR('standard', 0.0, -3)]),
    'tango': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-15, groove='tango', bpm=(112, 132),
                  mode='harmonic_minor', prog='i-iv-V7-i', layers=[
        _LEAD('bandoneon', gain_db=-1), _ALT('violin', min=0.3, gain_db=-4), _CH('piano', 'piano', 'pulse', 'pulse', 'pulse', 48, 70, 0.0, -4), _BS('double_bass', 'half', 28, 46, 0.0, -1), _DR('standard', 0.35, -8)]),
    'mariachi': dict(room='hall', swing=0.5, humanize='loose', tone='bright', lufs=-14, groove='ranchera', bpm=(100, 132),
                     mode='major', prog='I-IV-V-I', layers=[
        _LEAD('trumpet', gain_db=-2), _ALT('violin', min=0.2, gain_db=-4), _CH('vihuela', 'vihuela', 'strum', 'strum', 'strum', 50, 74, 0.0, -3), _BS('guitarron', 'half', 28, 46, 0.0, -1)]),
    'bolero': dict(room='chamber', swing=0.5, humanize='natural', tone='warm', lufs=-16, groove='soft_pulse', bpm=(66, 88),
                   mode='minor', prog='i-iv-V7-i', layers=[
        _CH('guitar', 'nylon_guitar', 'fingerpick', 'fingerpick', 'strum', 43, 67, 0.0, -2), _LEAD('trumpet', min=0.3, gain_db=-3), _BS('acoustic_bass', 'half', 31, 46, 0.1, -1), _DR('brush', 0.3, -6)]),
    'soca': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='soca', bpm=(120, 150),
                 mode='major', prog='I-IV-V-IV', layers=[
        _LEAD('steelpan', gain_db=-2), _CH('guitar', 'clean_guitar', 'chop', 'chop', 'chop', 48, 72, 0.0, -5), _ALT('brass_section', min=0.5, gain_db=-6), _BS('synth_bass', 'sync', 28, 43, 0.0, 0), _DR('standard', 0.0, -3)]),
    'calypso': dict(room='room_warm', swing=0.54, humanize='loose', tone='warm', lufs=-14, groove='calypso', bpm=(100, 128),
                    mode='major', prog='I-IV-I-V', layers=[
        _LEAD('steelpan', gain_db=-1), _CH('guitar', 'nylon_guitar', 'strum', 'strum', 'strum', 45, 69, 0.0, -4), _BS('acoustic_bass', 'half', 31, 48, 0.0, 0), _DR('standard', 0.0, -6)]),
    'highlife': dict(room='studio', swing=0.54, humanize='loose', tone='warm', lufs=-14, groove='highlife', bpm=(100, 126),
                     mode='major', prog='I-IV-I-V', layers=[
        _CH('guitar', 'highlife_guitar', 'pulse', 'chop', 'chop', 48, 74, 0.0, -2), _LEAD('trumpet', gain_db=-2), _ALT('alto_sax', min=0.4, gain_db=-5), _BS('finger_bass', 'sync', 31, 48, 0.0, 0), _DR('standard', 0.0, -4)]),
    'soukous': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-13, groove='soukous', bpm=(112, 140),
                    mode='major', prog='I-IV-V-IV', layers=[
        _LEAD('soukous_guitar', oct=1, gain_db=-1), _CH('rhythm', 'highlife_guitar', 'arp16', 'arp16', 'arp16', 45, 69, 0.0, -4), _BS('finger_bass', 'sync', 28, 45, 0.0, 0), _DR('standard', 0.0, -4)]),
    'amapiano': dict(room='plate', swing=0.5, humanize='tight', tone='warm', lufs=-12, groove='amapiano', bpm=(108, 116),
                     mode='minor', prog='i-VI-III-VII', layers=[
        _L('log', 'log_drum', 'bass', bass='sync', lo=33, hi=48, min=0.0, role='bass', gain_db=-1), _CH('keys', 'epiano', 'comp', 'comp', 'comp', 50, 74, 0.0, -4, color='seventh'),
        _CH('pad', 'warm_pad', 'block', 'block', 'block', 48, 70, 0.2, -9), _LEAD('pan_flute', min=0.4, gain_db=-5), _DR('standard', 0.0, -3)]),
    'kora': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-16, groove='kora_6', bpm=(88, 118),
                 mode='african_pentatonic', prog='I-IV-I-V', layers=[
        _CH('kora', 'kora', 'arp16', 'arp16', 'arp16', 48, 81, 0.0, -2), _LEAD('balafon', gain_db=-2), _ALT('mbira', oct=1, min=0.4, gain_db=-6), _BS('guembri', 'half', 31, 46, 0.2, -2), _DR('standard', 0.3, -7)]),
    'mbira': dict(room='room_warm', swing=0.5, humanize='loose', tone='warm', lufs=-16, groove='kora_6', bpm=(96, 124),
                  mode='mbira_mixolydian', prog='I-VII-IV-I', layers=[
        _LEAD('mbira', gain_db=-1), _CH('mbira2', 'mbira', 'arp16', 'arp16', 'arp16', 55, 84, 0.0, -4), _BS('mbira', 'half', 36, 55, 0.3, -3), _DR('standard', 0.2, -8)]),
    'andean': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-16, groove='huayno', bpm=(92, 124),
                   mode='andean_minor', prog='i-VII-VI-VII', layers=[
        _LEAD('quena', glide=0.15, gain_db=-1), _ALT('zampona', oct=0, min=0.4, gain_db=-4), _CH('charango', 'charango', 'strum', 'arp16', 'arp16', 55, 79, 0.0, -3),
        _BS('acoustic_bass', 'half', 31, 46, 0.3, -1), _DR('standard', 0.2, -6)]),
    'hawaiian': dict(room='room_warm', swing=0.52, humanize='loose', tone='warm', lufs=-16, groove='brush', bpm=(80, 108),
                     mode='major', prog='I-vi-ii-V', layers=[
        _CH('ukulele', 'ukulele', 'strum', 'strum', 'strum', 55, 79, 0.0, -3), _LEAD('slack_key', gain_db=-2), _BS('acoustic_bass', 'half', 31, 46, 0.2, -2), _DR('brush', 0.3, -8)]),
    # ---- Europe and the Americas ----
    'celtic': dict(room='room_warm', swing=0.54, humanize='loose', tone='warm', lufs=-15, groove='bodhran', bpm=(100, 126),
                   mode='celtic_dorian', prog='i-VII-i-VII', layers=[
        _LEAD('fiddle', glide=0.1, gain_db=-1), _ALT('tin_whistle', oct=1, min=0.4, gain_db=-5), _CH('guitar', 'acoustic_guitar', 'strum', 'strum', 'strum', 45, 69, 0.0, -3),
        _BS('acoustic_bass', 'half', 31, 46, 0.2, -2), _DR('standard', 0.2, -7)]),
    'country': dict(room='studio', swing=0.54, humanize='natural', tone='bright', lufs=-14, groove='two_step', bpm=(96, 132),
                    mode='major', prog='I-IV-V-I', layers=[
        _CH('guitar', 'acoustic_guitar', 'strum', 'strum', 'strum', 45, 69, 0.0, -3), _LEAD('steel_guitar', gain_db=-2), _ALT('fiddle', min=0.4, gain_db=-4), _BS('acoustic_bass', 'half', 31, 46, 0.0, -1), _DR('standard', 0.0, -6)]),
    'bluegrass': dict(room='room_warm', swing=0.5, humanize='loose', tone='bright', lufs=-14, bpm=(120, 160),
                      mode='mixolydian', prog='I-IV-I-V', layers=[
        _LEAD('banjo', gain_db=-1), _ALT('fiddle', min=0.2, gain_db=-3), _CH('guitar', 'acoustic_guitar', 'strum', 'strum', 'strum', 45, 69, 0.0, -4), _BS('acoustic_bass', 'half', 31, 46, 0.0, 0)]),
    'blues': dict(room='room_warm', swing=0.66, humanize='loose', tone='warm', lufs=-15, groove='rock', bpm=(70, 104),
                  mode='blues', prog='I7-I7-I7-I7-IV7-IV7-I7-I7-V7-IV7-I7-V7', layers=[
        _CH('guitar', 'clean_guitar', 'comp', 'comp', 'comp', 45, 69, 0.0, -3, color='seventh'), _LEAD('overdrive_guitar', gain_db=-3), _CH('organ', 'organ', 'block', 'block', 'block', 48, 69, 0.3, -9),
        _BS('acoustic_bass', 'walk', 31, 48, 0.0, 0), _DR('brush', 0.1, -5)]),
    'gospel': dict(room='hall', swing=0.55, humanize='natural', tone='warm', lufs=-14, groove='gospel_clap', bpm=(70, 110),
                   mode='major', prog='I-IV-I-V7-vi-ii-V-I', layers=[
        _CH('organ', 'tonewheel_organ', 'block', 'block', 'block', 48, 72, 0.0, -4), _CH('piano', 'piano', 'comp', 'comp', 'comp', 48, 72, 0.0, -3, color='seventh'), _LEAD('choir_aahs', min=0.2, gain_db=-4),
        _BS('finger_bass', 'half', 31, 46, 0.0, 0), _DR('standard', 0.1, -5)]),
    'swing': dict(room='hall', swing=0.66, humanize='loose', tone='warm', lufs=-15, groove='brush', bpm=(140, 190),
                  mode='major', prog='Imaj7-vi7-ii7-V7', layers=[
        _CH('piano', 'piano', 'comp', 'comp', 'comp', 48, 70, 0.0, -4, color='seventh'), _LEAD('alto_sax', gain_db=-2), _ALT('brass_section', min=0.45, gain_db=-5),
        _BS('acoustic_bass', 'walk', 31, 48, 0.0, 0), _DR('brush', 0.0, -4)]),
    'disco': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='disco', bpm=(108, 124),
                  mode='minor', prog='i7-IV7-i7-V7', layers=[
        _CH('guitar', 'clean_guitar', 'chop', 'chop', 'chop', 48, 72, 0.0, -3), _CH('strings', 'string_ensemble', 'block', 'half', 'half', 45, 72, 0.2, -6), _LEAD('brass_section', min=0.2, gain_db=-4),
        _BS('slap_bass', 'pulse8', 28, 46, 0.0, 0), _DR('standard', 0.0, -3)]),
    'baroque': dict(room='hall', swing=0.5, humanize='natural', tone='neutral', lufs=-17, bpm=(80, 120),
                    mode='major', prog='I-V-vi-iii-IV-I-IV-V', layers=[
        _CH('harpsichord', 'harpsichord', 'arp16', 'arp16', 'arp16', 48, 76, 0.0, -2), _LEAD('violin', gain_db=-1), _BS('cello', 'walk', 36, 55, 0.0, -2), _ALT('oboe', min=0.5, gain_db=-5)]),
    'medieval': dict(room='cave', swing=0.5, humanize='rubato', tone='warm', lufs=-17, groove='bodhran', bpm=(84, 112),
                     mode='dorian', prog='i-VII-i-VII', layers=[
        _LEAD('recorder', gain_db=-1), _CH('lute', 'lute', 'fingerpick', 'fingerpick', 'arp8', 45, 69, 0.0, -3), _DRONE('hurdy_gurdy', 36, 55, 0.0, -6), _DR('standard', 0.4, -10)]),
    'viennese_waltz': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-16, bpm=(150, 186), bb=3,
                           mode='major', prog='I-V7-V7-I', layers=[
        _CH('strings', 'string_ensemble', 'waltz', 'waltz', 'waltz', 45, 70, 0.0, -4), _LEAD('violin', gain_db=-1), _BS('double_bass', 'half', 28, 46, 0.0, -2), _ALT('flute', oct=1, min=0.5, gain_db=-6)]),
    'chiptune': dict(room='room', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='rock', bpm=(120, 168),
                     mode='minor', prog='i-VI-III-VII', layers=[
        _LEAD('chiptune_lead', gain_db=-3), _CH('arp', '8bit', 'arp16', 'arp16', 'arp16', 55, 79, 0.0, -8), _BS('synth_bass', 'pulse8', 28, 43, 0.0, 0), _DR('electronic', 0.0, -4)]),
}

_FILM = dict(room='studio', swing=0.5, humanize='natural', tone='bright')
GENRES.update({
    'tamil_film': dict(**_FILM, lufs=-14, groove='tamil_film', bpm=(90, 128), mode='raga_kharaharapriya', prog='i-IV-i-VII', layers=[
        _CH('strings', 'string_ensemble', 'block', 'half', 'arp8', 45, 72, 0.0, -4), _LEAD('violin', glide=0.3, gain_db=-1),
        _ALT('nadaswaram', min=0.55, glide=0.3, gain_db=-6), _BS('synth_bass', 'sync', 31, 46, 0.1, 0), _SPK('carnatic_mandolin', 60, 84, 0.3, -7), _DR('standard', 0.0, -4)]),
    'gaana': dict(room='studio', swing=0.5, humanize='loose', tone='bright', lufs=-13, groove='gaana', bpm=(108, 138),
                  mode='raga_asavari', prog='i-VII-VI-VII', layers=[
        _LEAD('nadaswaram', glide=0.3, gain_db=-2), _CH('synth', 'polysynth', 'pulse', 'pulse', 'pulse', 48, 70, 0.3, -7),
        _BS('synth_bass', 'sync', 28, 44, 0.0, 0), _DR('standard', 0.0, -2)]),
    'dhrupad': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-18, groove='dhrupad', bpm=(48, 70),
                    mode='raga_asavari', prog='Isus2-Isus2-Isus2-Isus2', layers=[
        _DRONE('tanpura', 36, 55, 0.0, -3), _LEAD('rudra_veena', min=0.0, glide=0.5, gain_db=-1), _ALT('sarangi', min=0.6, glide=0.4, gain_db=-8),
        _DR('standard', 0.25, -5)]),
    'bhajan': dict(room='room', swing=0.5, humanize='loose', tone='warm', lufs=-16, groove='bhajan', bpm=(72, 104),
                   mode='raga_khamaj', prog='Isus2-IVsus2-Isus2-Isus2', layers=[
        _CH('harmonium', 'indian_harmonium', 'block', 'block', 'half', 48, 70, 0.0, -2), _LEAD('bansuri', glide=0.3, min=0.3, gain_db=-3),
        _DRONE('tanpura', 36, 55, 0.0, -7), _DR('standard', 0.0, -4)]),
    'sufi': dict(room='hall', swing=0.5, humanize='rubato', tone='warm', lufs=-16, groove='sufi', bpm=(74, 104),
                 mode='raga_kafi', prog='i-VII-i-IV', layers=[
        _CH('harmonium', 'indian_harmonium', 'half', 'half', 'half', 48, 70, 0.0, -3), _LEAD('sarangi', glide=0.5, gain_db=-2),
        _CH('guitar', 'nylon_guitar', 'fingerpick', 'fingerpick', 'arp8', 45, 69, 0.3, -5), _DRONE('tanpura', 36, 55, 0.0, -7), _DR('standard', 0.0, -5)]),
    'garba': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='garba', bpm=(112, 142),
                  mode='raga_khamaj', prog='I-VII-IV-I', layers=[
        _CH('harmonium', 'indian_harmonium', 'chop', 'chop', 'chop', 48, 70, 0.0, -4), _LEAD('shehnai', gain_db=-2), _ALT('bansuri', oct=1, min=0.5, gain_db=-6),
        _BS('finger_bass', 'sync', 31, 46, 0.2, 0), _DR('standard', 0.0, -2)]),
    'dandiya': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='dandiya', bpm=(130, 164),
                    mode='raga_khamaj', prog='I-VII-IV-I', layers=[
        _CH('harmonium', 'indian_harmonium', 'chop', 'chop', 'chop', 48, 70, 0.0, -4), _LEAD('shehnai', gain_db=-2), _SPK('santoor', 72, 91, 0.3, -7),
        _BS('synth_bass', 'sync', 31, 46, 0.2, 0), _DR('standard', 0.0, -2)]),
    'lavani': dict(room='studio', swing=0.5, humanize='loose', tone='bright', lufs=-13, groove='lavani', bpm=(116, 148),
                   mode='raga_kafi', prog='i-IV-i-VII', layers=[
        _CH('harmonium', 'indian_harmonium', 'chop', 'half', 'half', 48, 70, 0.0, -4), _LEAD('sarangi', glide=0.4, gain_db=-2), _ALT('tumbi', oct=1, min=0.4, gain_db=-6),
        _BS('finger_bass', 'sync', 31, 46, 0.2, 0), _DR('standard', 0.0, -2)]),
    'baul': dict(room='room', swing=0.5, humanize='loose', tone='warm', lufs=-17, groove='baul', bpm=(78, 108),
                 mode='mixolydian', prog='I-VII-I-IV', layers=[
        _LEAD('ektara', gain_db=-2), _CH('dotara', 'dotara', 'fingerpick', 'fingerpick', 'arp8', 45, 69, 0.0, -4),
        _CH('harmonium', 'indian_harmonium', 'half', 'half', 'half', 48, 70, 0.3, -7), _ALT('bansuri', min=0.5, glide=0.3, gain_db=-6), _DR('standard', 0.15, -6)]),
    'rajasthani_folk': dict(room='room', swing=0.5, humanize='loose', tone='warm', lufs=-15, groove='rajasthani', bpm=(100, 136),
                            mode='raga_khamaj', prog='Isus2-IVsus2-Isus2-Isus2', layers=[
        _LEAD('kamaicha', glide=0.45, gain_db=-1), _ALT('algoza', min=0.35, gain_db=-5), _DRONE('tanpura', 36, 55, 0.0, -7),
        _CH('harmonium', 'indian_harmonium', 'half', 'half', 'half', 48, 70, 0.3, -6), _DR('standard', 0.0, -3)]),
    'bihu': dict(room='room', swing=0.5, humanize='tight', tone='bright', lufs=-14, groove='bihu', bpm=(120, 152),
                 mode='raga_bhoopali', prog='Isus2-IVsus2-Isus2-Vsus2', layers=[
        _LEAD('pepa', gain_db=-2), _ALT('gogona', min=0.4, gain_db=-6), _CH('guitar', 'acoustic_guitar', 'comp', 'comp', 'strum', 48, 69, 0.2, -6),
        _DR('standard', 0.0, -2)]),
    'chenda_melam': dict(room='hall', swing=0.5, humanize='tight', tone='bright', lufs=-13, groove='chenda', bpm=(110, 150),
                         mode='raga_mayamalavagowla', prog='Isus2-Isus2-Isus2-Isus2', layers=[
        _LEAD('kuzhal', min=0.2, glide=0.3, gain_db=-3), _DRONE('tanpura', 36, 55, 0.0, -8), _DR('standard', 0.0, -1)]),
    'desi_hiphop': dict(room='studio', swing=0.5, humanize='tight', tone='bright', lufs=-12, groove='desi_hiphop', bpm=(84, 102),
                        mode='raga_asavari', prog='i-VII-VI-VII', layers=[
        _LEAD('sitar', gain_db=-3), _BS('synth_bass', 'sync', 24, 40, 0.0, 0), _SPK('santoor', 72, 91, 0.3, -9),
        _CH('pad', 'string_ensemble', 'half', 'half', 'half', 45, 70, 0.3, -9), _DR('standard', 0.0, -2)]),
    'indipop': dict(room='studio', swing=0.5, humanize='natural', tone='bright', lufs=-14, groove='indipop', bpm=(98, 122),
                    mode='major', prog='I-V-vi-IV', layers=[
        _CH('guitar', 'acoustic_guitar', 'strum', 'strum', 'arp8', 48, 72, 0.0, -4), _CH('piano', 'piano', 'block', 'half', 'arp8', 48, 70, 0.3, -6),
        _LEAD('bansuri', gain_db=-3), _BS('finger_bass', 'sync', 31, 46, 0.0, 0), _DR('standard', 0.0, -4)]),
    'retro_filmi': dict(room='hall', swing=0.5, humanize='natural', tone='warm', lufs=-15, groove='retro_filmi', bpm=(100, 130),
                        mode='raga_bhairavi', prog='i-VI-VII-i', layers=[
        _CH('strings', 'string_ensemble', 'block', 'half', 'half', 45, 72, 0.0, -3), _LEAD('accordion', gain_db=-2), _ALT('sitar', min=0.4, gain_db=-5),
        _SPK('mandolin', 60, 84, 0.3, -7), _BS('acoustic_bass', 'walk', 31, 46, 0.1, 0), _DR('standard', 0.0, -5)]),
    'indian_lofi': dict(room='room', swing=0.54, humanize='loose', tone='warm', lufs=-17, groove='indian_lofi', bpm=(68, 88),
                        mode='raga_kafi', prog='i-IV-i-VII', layers=[
        _CH('keys', 'epiano', 'half', 'half', 'arp8', 48, 70, 0.0, -4, color='seventh'), _LEAD('bansuri', glide=0.3, min=0.3, gain_db=-4),
        _SPK('sitar', 60, 84, 0.4, -9), _BS('finger_bass', 'half', 31, 46, 0.0, 0), _DR('standard', 0.0, -5)]),
})
GENRE_ALIASES = {
    # India
    'indian': 'bollywood', 'india': 'bollywood', 'hindi': 'bollywood', 'filmi': 'bollywood', 'indian_film': 'bollywood',
    'indian_classical': 'hindustani', 'raga': 'hindustani', 'raag': 'hindustani', 'sitar': 'hindustani', 'north_indian': 'hindustani',
    'south_indian': 'carnatic', 'tamil': 'carnatic', 'punjabi': 'bhangra', 'sufi': 'qawwali', 'devotional': 'qawwali', 'bhajan': 'ghazal',
    # Middle East
    'arabic': 'arabic_pop', 'arab': 'arabic_pop', 'middle_eastern': 'arabic_pop', 'oriental': 'arabic_pop', 'belly_dance': 'arabic_pop',
    'egyptian': 'arabic_pop', 'khaleeji': 'arabic_pop', 'levantine': 'dabke', 'shaabi': 'mahraganat', 'mahragan': 'mahraganat',
    'maqam': 'tarab', 'turkish': 'turkish_classical', 'ottoman': 'turkish_classical', 'makam': 'turkish_classical', 'anatolian': 'turkish_folk',
    'turku': 'turkish_folk', 'zeybek': 'turkish_folk', 'iranian': 'persian', 'persian_classical': 'persian', 'rebetiko': 'greek',
    'greek_folk': 'greek', 'syrtaki': 'greek', 'balkan': 'klezmer', 'jewish': 'klezmer', 'andalusian': 'flamenco', 'spanish': 'flamenco',
    # East Asia
    'chinese': 'chinese_classical', 'china': 'chinese_classical', 'guzheng': 'chinese_classical', 'erhu': 'chinese_classical',
    'chinese_traditional': 'chinese_classical', 'chinese_style': 'guofeng', 'mandopop': 'cpop', 'c_pop': 'cpop', 'cantopop': 'cpop',
    'japanese': 'japanese_traditional', 'japan': 'japanese_traditional', 'koto': 'japanese_traditional', 'wafu': 'japanese_traditional',
    'taiko_drumming': 'wadaiko', 'matsuri': 'wadaiko', 'j_pop': 'jpop', 'anime': 'jpop', 'anisong': 'jpop', 'j_rock': 'jpop',
    'citypop': 'city_pop', 'shibuya_kei': 'city_pop', 'k_pop': 'kpop', 'korean': 'kpop', 'korea': 'kpop', 'idol': 'kpop',
    'k_pop_dance': 'kpop_dance', 'kpop_edm': 'kpop_dance', 'k_ballad': 'kpop_ballad', 'korean_ballad': 'kpop_ballad', 'ppongjjak': 'trot',
    'indonesian': 'gamelan', 'javanese': 'gamelan', 'balinese': 'gamelan',
    # Brazil and Latin
    'rio': 'samba_enredo', 'carnival_rio': 'samba_enredo', 'carnaval': 'samba_enredo', 'batucada': 'samba_enredo', 'escola_de_samba': 'samba_enredo',
    'samba_de_roda': 'pagode', 'partido_alto': 'pagode', 'chorinho': 'choro', 'baile_funk': 'funk_carioca', 'funk_brasileiro': 'funk_carioca',
    'tamborzao': 'funk_carioca', 'favela_funk': 'funk_carioca', 'northeastern_brazil': 'baiao', 'xote': 'baiao', 'xaxado': 'baiao',
    'maracatu_de_baque_virado': 'maracatu', 'axe_music': 'axe', 'bahia': 'axe', 'samba_rock': 'samba_reggae', 'merengue_tipico': 'merengue',
    'bachata_romantica': 'bachata', 'argentine': 'tango', 'tango_nuevo': 'tango', 'ranchera': 'mariachi', 'mexican': 'mariachi', 'son': 'bolero',
    'soca_music': 'soca', 'steel_band': 'calypso', 'caribbean': 'calypso', 'trinidad': 'soca', 'west_african': 'kora', 'griot': 'kora',
    'zimbabwean': 'mbira', 'congolese': 'soukous', 'rumba_congolaise': 'soukous', 'ghanaian': 'highlife', 'nigerian_highlife': 'highlife',
    'south_african': 'amapiano', 'amapiano_log_drum': 'amapiano', 'peruvian': 'andean', 'andes': 'andean', 'huayno': 'andean',
    'polynesian': 'hawaiian', 'slack_key_guitar': 'hawaiian', 'irish': 'celtic', 'scottish': 'celtic', 'irish_folk': 'celtic',
    'nashville': 'country', 'honky_tonk': 'country', 'appalachian': 'bluegrass', 'delta_blues': 'blues', 'twelve_bar': 'blues',
    'gospel_choir': 'gospel', 'big_band': 'swing', 'swing_jazz': 'swing', 'disco_funk': 'disco', 'baroque_classical': 'baroque',
    'renaissance': 'medieval', 'early_music': 'medieval', 'waltz': 'viennese_waltz', 'strauss': 'viennese_waltz', '8_bit': 'chiptune', 'retro_game': 'chiptune',
}

for _a in ('sufi', 'bhajan', 'tamil', 'devotional'):       # these were aliases; most are real genres now
    GENRE_ALIASES.pop(_a, None)
GENRE_ALIASES.update({
    'devotional': 'bhajan', 'kirtan': 'bhajan', 'shabad': 'bhajan', 'aarti': 'bhajan', 'abhang': 'bhajan', 'hindu_devotional': 'bhajan',
    'sufi_rock': 'sufi', 'sufiana': 'sufi', 'kalam': 'sufi', 'thumri': 'ghazal', 'dadra': 'ghazal', 'urdu': 'ghazal', 'light_classical': 'ghazal',
    'khayal': 'hindustani', 'alap': 'hindustani', 'sarod': 'hindustani', 'santoor': 'hindustani', 'tabla': 'hindustani',
    'pakhawaj': 'dhrupad', 'temple_music': 'dhrupad', 'kollywood': 'tamil_film', 'tamil': 'tamil_film', 'telugu': 'tamil_film',
    'tollywood': 'tamil_film', 'malayalam': 'tamil_film', 'kannada': 'tamil_film', 'south_indian_film': 'tamil_film', 'rahman': 'tamil_film',
    'ilaiyaraaja': 'tamil_film', 'kuthu': 'gaana', 'dappankuthu': 'gaana', 'chennai_gaana': 'gaana', 'gujarati': 'garba', 'raas': 'garba',
    'navratri': 'garba', 'marathi': 'lavani', 'maharashtrian': 'lavani', 'bengali': 'baul', 'bengali_folk': 'baul', 'rabindra_sangeet': 'baul',
    'rajasthani': 'rajasthani_folk', 'maand': 'rajasthani_folk', 'ghoomar': 'rajasthani_folk', 'langa': 'rajasthani_folk', 'manganiyar': 'rajasthani_folk',
    'assamese': 'bihu', 'northeast_indian': 'bihu', 'kerala': 'chenda_melam', 'melam': 'chenda_melam', 'chenda': 'chenda_melam',
    'panchari_melam': 'chenda_melam', 'thavil': 'chenda_melam', 'indian_hip_hop': 'desi_hiphop', 'desi': 'desi_hiphop', 'gully_rap': 'desi_hiphop',
    'indian_rap': 'desi_hiphop', 'hindi_pop': 'indipop', 'indian_pop': 'indipop', 'indie_india': 'indipop', 'indian_indie': 'indipop',
    'old_hindi': 'retro_filmi', 'golden_age_bollywood': 'retro_filmi', '70s_bollywood': 'retro_filmi', '60s_bollywood': 'retro_filmi',
    'rd_burman': 'retro_filmi', 'hindi_lofi': 'indian_lofi', 'bollywood_lofi': 'indian_lofi', 'slowed_reverb_hindi': 'indian_lofi',
    'punjabi_pop': 'bhangra', 'gidda': 'bhangra', 'dhol': 'bhangra', 'punjabi_folk': 'bhangra', 'kawali': 'qawwali',
})


if __name__ == '__main__':
    print(f'{len(MODES)} scales ({len(MICRO)} microtonal), {len(INSTRUMENTS)} instruments, {len(DRUM_KEYS)} drum names, '
          f'{len(GROOVES)} grooves, {len(CYCLES)} cycles, {len(GENRES)} genres, {len(GENRE_ALIASES)} aliases')
    print('SCALES :', ', '.join(sorted(MODES)))
    print('CYCLES :', ', '.join(sorted(CYCLES)))
