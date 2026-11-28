"""staging.py - where every music part sits (azimuth deg, elevation deg, distance m). One table, read by the instrument presets and the direction
sheet, so the two cannot disagree.

The rule behind it (the gate's spatial.z_separation): two parts that hold the same mid band at the climax must be 25 deg apart in azimuth or 15 deg in
height. Drums and bass cannot be placed by height (no pinna cue at low frequency: the project gate refuses it), so the low end is separated in azimuth;
everything else that is not bass or drum is lifted to a ring or to the two height speakers of 7.1.2 (the helicopter, the choir, the high strings).
"""
STAGE = {
    'pursuit_basses':           (0.0, 0.0, 1.5),
    'pursuit_bass_drum':        (-25.0, 0.0, 2.2),
    'pursuit_basses_pizz':      (40.0, 0.0, 1.2),
    'pursuit_snare':            (-80.0, 0.0, 2.6),
    'pursuit_timpani':          (80.0, 0.0, 3.0),
    'pursuit_taiko':            (-130.0, 0.0, 3.2),
    'pursuit_tuba':             (150.0, 0.0, 1.8),
    'pursuit_low_swell':        (0.0, 20.0, 1.0),
    'pursuit_horns':            (20.0, 0.0, 2.6),
    'pursuit_trombones':        (-95.0, 0.0, 2.8),
    'pursuit_violas':           (-55.0, 0.0, 2.0),
    'pursuit_celli':            (55.0, 0.0, 2.2),
    'pursuit_bass_clarinet':    (130.0, 30.0, 2.4),
    'pursuit_violins_staccato': (-130.0, 30.0, 3.0),
    'pursuit_violins_long':  (180.0, 45.0, 4.0),
    'pursuit_cymbals':          (-160.0, 30.0, 3.6),
    'pursuit_piano_theme':      (-30.0, 15.0, 1.8),
    'pursuit_choir':            (0.0, 60.0, 5.0),
    'pursuit_solo_violin':      (-35.0, 45.0, 2.4),
}
