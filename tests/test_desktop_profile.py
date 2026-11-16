import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_profile', PROJECT / 'scripts/export-desktop-profile.py')
profile_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile_tools)


class DesktopProfileTests(unittest.TestCase):
    def test_committed_profile_is_publishable(self):
        profile_tools.validate(json.loads((PROJECT / 'device/theme/desktop-profile.json').read_text(encoding='utf-8')))

    def test_export_excludes_unlisted_weather_and_runtime_data(self):
        raw = [{'kind': 'desktop', 'order': '', 'widgets': [{
            'id': 9876, 'plugin': 'Redmi.Clock',
            'geometry': {'x': 32, 'y': 104, 'width': 304, 'height': 304},
            'settings': {'General': {'colorHex': '#ffffff', 'weatherLatitude': 41.234, 'cachedWeather': 'private-cache'}},
        }, {'id': 9988, 'plugin': 'org.sheng.desktop-gesture.drawer-test', 'settings': {'Appearance': {'pointerPresent': True}}}]}]
        output = json.dumps(profile_tools.sanitize_layout(raw))
        for unexpected in ['9876', '9988', '41.234', 'private-cache', 'pointerPresent']:
            self.assertNotIn(unexpected, output)
        self.assertIn('#ffffff', output)
        self.assertIn('org.sheng.desktop-gesture#1', output)

    def test_style_removes_file_sources_and_unused_branches(self):
        raw = {'enabled': True, 'foregroundColor': {'enabled': True, 'custom': '#ffffff'},
               'backgroundImage': '/home/example/private.jpg', 'cacheLocation': 'private',
               'animation': {'enabled': False, 'command': '/home/example/run-helper'},
               'overrides': [{'appletId': 9988}]}
        result = profile_tools.safe_style(raw)
        self.assertEqual(result['foregroundColor']['custom'], '#ffffff')
        self.assertEqual(result['animation'], {'enabled': False})
        for key in ['backgroundImage', 'cacheLocation', 'overrides']:
            self.assertNotIn(key, result)

    def test_launcher_roles_do_not_publish_custom_paths(self):
        self.assertEqual(profile_tools.launcher_role('file:///home/example/.local/share/applications/install4j-BurpSuite.desktop'), 'burp-suite')
        self.assertIsNone(profile_tools.launcher_role('file:///home/example/private-project.desktop'))

    def test_public_source_urls_are_not_mistaken_for_drive_paths(self):
        self.assertIsNone(profile_tools.PRIVATE.search('https://github.com/Petexy/Linexin-Launcher'))
        self.assertIsNotNone(profile_tools.PRIVATE.search(r'C:\Users\Example\settings'))

    def test_kconfig_reads_only_the_declared_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = pathlib.Path(tmp)
            (home / '.config').mkdir()
            (home / '.config/kdeglobals').write_text('[General]\nColorScheme=BreezeLight\nPrivateValue=do-not-export\n[Account]\nName=private-name\n')
            result = profile_tools.read_kconfig(home)
        self.assertEqual(result, {'kdeglobals': {'General': {'ColorScheme': 'BreezeLight'}}})

    def test_validator_rejects_raw_config_or_private_paths(self):
        original = json.loads((PROJECT / 'device/theme/desktop-profile.json').read_text(encoding='utf-8'))
        private = copy.deepcopy(original)
        private['screenKeyboard']['default_font'] = '/home/example/private-font.ttf'
        with self.assertRaises(ValueError):
            profile_tools.validate(private)
        extra = copy.deepcopy(original)
        extra['kconfig']['kdeglobals']['Account'] = {'Name': 'private-name'}
        with self.assertRaises(ValueError):
            profile_tools.validate(extra)


if __name__ == '__main__':
    unittest.main()
