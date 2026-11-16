# SPDX-License-Identifier: MIT
import gzip
import importlib.util
import io
import pathlib
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


PREP = module('prepare_futo', 'scripts/prepare-futo-keyboard.py')
SETUP = module('setup_futo', 'scripts/futo-keyboard-setup.py')


class FutoPreparationTest(unittest.TestCase):
    def test_public_dictionary_filter(self):
        data = ('dictionary=public\n word=hello,f=100,flags=\n word=bad,f=0,flags=\n'
                ' word=internal,f=100,not_a_word=true\n word=hello,f=110\n'
                ' word=' + 'x' * 48 + ',f=100\n').encode()
        self.assertEqual(PREP.wordlist(gzip.compress(data)), 'hello\t110\n')

    def test_layout_mapping_and_explicit_support(self):
        rows = PREP.layout_rows('name: QWERTY\nrows:\n  - letters: q w e r t y u i o p\n  - letters: a s d f g h j k l\n  - letters: z x c v b n m\n')
        layout = PREP.make_layout(rows, 'portrait')
        self.assertIn('name = "sheng-futo-portrait"', layout)
        self.assertIn('k_q = "sheng-futo:k_q"', layout)
        self.assertIn('k_left_shift:15', layout)
        with self.assertRaises(ValueError):
            PREP.layout_rows('rows:\n  - letters: a z e r t y\n')

    def test_emoji_sequences_and_private_codes(self):
        source = '<resources><array name="emoji_faces"><item>1f600</item><item>1f600</item></array><array name="emoji_symbols"><item>fe82e|0031,20e3|99</item><item>fe82e</item></array></resources>'
        result = PREP.make_emoji(source)
        self.assertEqual(result[0]['items'], ['😀'])
        self.assertEqual(result[-1]['items'], ['1\u20e3'])

    def test_keyset_preserves_characters_and_case_metadata(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest('Target asset validation requires Python 3.11 tomllib')
        keys = tomllib.loads(PREP.make_keyset())['keys']
        self.assertTrue(keys['k_q']['auto_case'])
        self.assertEqual(keys['k_q']['s'][0]['c'], '1')
        self.assertEqual(keys['k_space']['p']['c'], ' ')
        self.assertEqual(keys['k_u40']['p']['kc'], -11)
        self.assertEqual(keys['k_u3c']['p']['kc'], -59)

    def test_archive_rejects_traversal_and_links(self):
        for name, kind in [('root/../escape', tarfile.REGTYPE), ('root/link', tarfile.SYMTYPE)]:
            data = io.BytesIO()
            with tarfile.open(fileobj=data, mode='w:gz') as archive:
                item = tarfile.TarInfo(name)
                item.type = kind
                item.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
                archive.addfile(item)
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    PREP.extract(data.getvalue(), pathlib.Path(tmp))

    def test_digest_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = pathlib.Path(tmp) / 'archive'
            archive.write_bytes(b'wrong source')
            with self.assertRaises(ValueError):
                PREP.download_or_read(archive, '', '0' * 64)

    def test_setup_keeps_placement_and_nested_settings(self):
        try:
            import tomllib
        except ImportError:
            self.skipTest('Target setup requires Python 3.11 tomllib')
        original = 'placement = "Float"\nlandscape_width = 640.0\n[application]\ncustom = "kept"\n'
        output = SETUP.update_config(original, {'theme': 'Auto', 'light_theme': 'FUTO Light'})
        values = tomllib.loads(output)
        self.assertEqual(values['placement'], 'Float')
        self.assertEqual(values['landscape_width'], 640.0)
        self.assertEqual(values['application']['custom'], 'kept')
        self.assertEqual(values['light_theme'], 'FUTO Light')


if __name__ == '__main__':
    unittest.main()
