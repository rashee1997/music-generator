"""staging.py - where every part sits in the street canyon (azimuth deg, elevation deg, distance m). One table, read by the preset, the
direction sheet and the sound presets, so the three cannot disagree.

The rule behind it (the gate's spatial.z_separation): two parts that hold the same mid band at the climax must be 25 deg apart in azimuth
or 15 deg in height. The low end is stacked in height (the kick under the floor, the basses at the ears, the piano's low octave and the
horns above them) because three anchors share the centre line; the strings sit out to the sides and up. A 7.1 decode has no height
speakers, so height here separates the parts in the field and in the gate; the speaker feed folds it to the ear-level ring.
"""
STAGE = {
    # drums and bass cannot be placed by height (the project gate: no pinna cue at low frequency), so they are separated in azimuth
    'pursuit_basses':          (0.0, 0.0, 1.5),
    'pursuit_sub_drop':        (0.0, 0.0, 1.0),
    'pursuit_bass_drum':       (-40.0, 0.0, 2.2),
    'pursuit_piano_low':       (40.0, 0.0, 1.2),
    'pursuit_snare':           (-80.0, 0.0, 2.6),
    'pursuit_timpani':         (80.0, 0.0, 3.0),
    'pursuit_tuba':            (150.0, 0.0, 1.8),
    # everything that is not bass or drum may be lifted
    'pursuit_horns':           (60.0, 15.0, 2.6),
    'pursuit_trombones':       (-60.0, 15.0, 2.8),
    'pursuit_piano':           (-110.0, 15.0, 2.0),
    'pursuit_celli':           (110.0, 15.0, 2.2),
    'pursuit_bass_clarinet':   (130.0, 30.0, 2.4),
    'pursuit_violins_staccato': (-130.0, 30.0, 3.0),
    'pursuit_violins_tremolo': (180.0, 30.0, 4.0),
    'pursuit_cymbals':         (-160.0, 30.0, 3.6),
    # the sounds
    'np_engine':               (180.0, 0.0, 1.0),
    'np_wipers':               (-60.0, 45.0, 0.7),
    'np_crash':                (120.0, 0.0, 12.0),
}
