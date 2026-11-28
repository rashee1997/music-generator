"""Bank audit, family defaults, the SF2 builder. Synthetic samples only: no network, no shipped bank needed."""
import json
import os
import sys
import tempfile
import unittest
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import families          # noqa: E402
import sf2_read          # noqa: E402
import soundbank         # noqa: E402
import soundbank_audit as au   # noqa: E402
import soundbank_build as sbb  # noqa: E402


def write_wav(d, name, rolloff):
    sr = 44100
    t = np.arange(sr) / sr
    x = sum(np.sin(2 * np.pi * 261.63 * k * t) / k ** rolloff for k in range(1, 20))
    x = (x / abs(x).max() * 20000).astype('<i2')
    with wave.open(os.path.join(d, name), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())


def spec(layers):
    zs = []
    edges = np.linspace(0, 127, layers + 1).astype(int)
    for i in range(layers):
        zs.append(dict(wav='soft.wav' if i == 0 else 'loud.wav', source='s', root=60, keys=[0, 127],
                       vel=[int(edges[i]) + (1 if i else 0), int(edges[i + 1])], loop=[1000, 40000]))
    return dict(name='t', sources=[dict(id='s', licence='CC0 1.0', licence_read=True)],
                programs=[dict(bank=0, program=42, name='Cello', zones=zs)])


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        write_wav(cls.d, 'soft.wav', 2.0)
        write_wav(cls.d, 'loud.wav', 0.7)
        for n, layers in (('flat', 1), ('layered', 2)):
            with open(os.path.join(cls.d, n + '.sf2'), 'wb') as fh:
                fh.write(sbb.build(spec(layers), cls.d))

    def test_reader_counts_velocity_layers(self):
        self.assertEqual(sf2_read.read(os.path.join(self.d, 'layered.sf2'))[(0, 42)]['layers'], 2)
        self.assertEqual(sf2_read.read(os.path.join(self.d, 'flat.sf2'))[(0, 42)]['layers'], 0)

    def test_reader_rejects_a_non_soundfont(self):
        p = os.path.join(self.d, 'x.sf2')
        open(p, 'wb').write(b'not a soundfont at all')
        with self.assertRaises(ValueError):
            sf2_read.read(p)

    def test_audit_separates_a_layered_bank_from_a_flat_one(self):
        flat = au.audit_program(os.path.join(self.d, 'flat.sf2'), 42)
        lay = au.audit_program(os.path.join(self.d, 'layered.sf2'), 42)
        self.assertLess(flat['centroid_ratio'], 1.05)
        self.assertGreater(lay['centroid_ratio'], 1.5)
        self.assertTrue(lay['sustain_ok'])

    def test_builder_refuses_an_unread_licence(self):
        s = spec(2)
        s['sources'][0]['licence_read'] = False
        with self.assertRaises(sbb.BuildError):
            sbb.build(s, self.d)
        s = spec(2)
        s['programs'][0]['zones'][0]['source'] = 'nobody'
        with self.assertRaises(sbb.BuildError):
            sbb.build(s, self.d)

    def test_builder_refuses_stereo_samples(self):
        with wave.open(os.path.join(self.d, 'st.wav'), 'wb') as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(bytes(400))
        s = spec(1)
        s['programs'][0]['zones'][0]['wav'] = 'st.wav'
        with self.assertRaises(sbb.BuildError):
            sbb.build(s, self.d)


class Choose(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.pol = au.policy()

    def put(self, key, fam, layers, ratio, air=-50.0):
        doc = dict(bank=key, families={fam: dict(layers=layers, centroid_ratio=ratio, air_db=air, sustained=1.0, programs=[])})
        json.dump(doc, open(os.path.join(self.d, key + '.json'), 'w'))

    def test_a_single_layer_bank_never_wins(self):
        self.put('muse_general', 'bowed', 0, 1.0)
        key, why = au.choose('bowed', {'muse_general', 'generaluser_gs'}, self.pol, self.d)
        self.assertEqual(key, 'generaluser_gs')
        self.assertIn('muse_general', why)

    def test_the_first_passing_bank_wins(self):
        self.put('cinematic_default', 'bowed', 3, 2.0)
        self.put('muse_general', 'bowed', 4, 2.0)
        key, _ = au.choose('bowed', {'cinematic_default', 'muse_general', 'generaluser_gs'}, self.pol, self.d)
        self.assertEqual(key, 'cinematic_default')

    def test_a_bank_that_is_not_installed_or_not_audited_is_skipped(self):
        self.put('cinematic_default', 'bowed', 3, 2.0)
        self.assertEqual(au.choose('bowed', {'generaluser_gs'}, self.pol, self.d)[0], 'generaluser_gs')
        key, why = au.choose('blown_brass', {'cinematic_default', 'generaluser_gs'}, self.pol, self.d)
        self.assertEqual(key, 'generaluser_gs')
        self.assertIn('not audited', why)

    def test_a_family_with_no_list_gets_the_fallback(self):
        self.assertEqual(au.choose('no_such_family', set(), self.pol, self.d)[0], self.pol['fallback'])

    def test_every_listed_bank_is_in_the_manifest(self):
        known = set(soundbank.catalog())
        for fam, order in self.pol['order'].items():
            for key in order:
                self.assertIn(key, known, (fam, key))
            self.assertIn(fam, families.names())


class Families(unittest.TestCase):
    def test_declared_family_wins_and_unknown_is_an_error(self):
        self.assertEqual(families.family_of({'family': 'voice', 'instrument': 'cello'}), 'voice')
        with self.assertRaises(ValueError):
            families.family_of({'family': 'kazoo'})

    def test_legacy_names_map_without_a_declaration(self):
        self.assertEqual(families.family_of({'instrument': 'cello'}), 'bowed')
        self.assertEqual(families.family_of({'instrument': 'french_horn'}), 'blown_brass')
        self.assertIsNone(families.family_of({'instrument': 'mystery_lute'}))

    def test_every_family_has_audit_programs_and_a_policy_list(self):
        pol = au.policy()
        for fam, e in families.table()['families'].items():
            self.assertTrue(e['audit_programs'], fam)
            self.assertIn(fam, pol['order'], fam)

    def test_bank_key_keeps_the_default_when_nothing_beats_it(self):
        self.assertEqual(soundbank.bank_key({'name': 'x'}, {'instrument': 'cello'}), soundbank.DEFAULT_BANK)
        self.assertEqual(soundbank.bank_key({'soundfont': 'muse_general'}, {'instrument': 'cello'}), 'muse_general')


if __name__ == '__main__':
    unittest.main()
