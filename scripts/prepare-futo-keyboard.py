#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare pinned FUTO source for the non-commercial native Linux port."""
import argparse
import base64
import gzip
import hashlib
import io
import json
import pathlib
import re
import subprocess
import tarfile
import urllib.request
import xml.etree.ElementTree as ET

PROJECT = pathlib.Path(__file__).resolve().parents[1]
LOCAL = PROJECT / 'device/futo-keyboard'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def download_or_read(archive, url, expected):
    if archive:
        data = archive.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
    if sha(data) != expected:
        raise ValueError('Archive SHA-256 mismatch')
    return data


def extract(data, output):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive.getmembers():
            parts = pathlib.PurePosixPath(member.name).parts[1:]
            if not parts or member.isdir():
                continue
            if not member.isfile() or '..' in parts or any('\\' in p or ':' in p for p in parts):
                raise ValueError('Unsupported archive member')
            target = output.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def wordlist(data):
    """Convert public combined-format unigrams, excluding offensive/non-words."""
    words = {}
    for line in gzip.decompress(data).decode('utf-8').splitlines():
        match = re.match(r'^ word=([^,\t\r\n]+),f=(\d+)(?:,|$)', line)
        if not match or 'not_a_word=true' in line:
            continue
        word, frequency = match[1], int(match[2])
        if 0 < frequency <= 255 and len(word) < 48:
            words[word] = max(frequency, words.get(word, 0))
    return ''.join(f'{word}\t{frequency}\n' for word, frequency in words.items())


def layout_rows(data):
    # This port supports the pinned simple QWERTY schema, not all Android layouts.
    rows = re.findall(r'^  - letters: ([a-z ]+)$', data, re.M)
    if rows != ['q w e r t y u i o p', 'a s d f g h j k l', 'z x c v b n m']:
        raise ValueError('Unsupported FUTO layout schema; review the adapter')
    return [row.split() for row in rows]


def make_layout(rows, orientation):
    elements = [rows[0], ['p:5'] + rows[1] + ['p:5'],
                ['shift:15'] + rows[2] + ['backspace:15'], ['tab:12', 'comma:10', 'space:50', 'dot:10', 'enter:18']]
    names = dict(zip('1234567890', ['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'zero']))
    used = set()
    text = '# FUTO QWERTY layout, Apache-2.0; Linux mapping, MIT.\n'
    text += f'name = "sheng-futo-{orientation}"\nprimary_text_size = 3\nsecondary_text_size = 1\nmin_toolbar_height = 6\nspacing = 1\n'
    for row in elements:
        values = []
        for key in row:
            if key.startswith('p:'):
                values.append(key)
                continue
            key = 'k_' + names.get(key, key)
            key = key.replace('k_shift:', 'k_left_shift:')
            used.add(key.split(':')[0])
            values.append(key)
        text += '\n[[elements]]\nheight = 7\nspacing = 1\nelements = ' + json.dumps(values) + '\n'
    text += '\n[key_mappings]\n'
    # Extra mappings are needed by the native symbol/edit panels, even when
    # their keys aren't in the alphabet grid's visible rows.
    used.update('k_' + c for c in 'abcdefghijklmnopqrstuvwxyz')
    used.update('k_u' + format(ord(c), 'x') for c in SYMBOLS if c.isascii())
    for key in sorted(used):
        text += f'{key} = "sheng-futo:{key}"\n'
    return text


SYMBOLS = '1234567890@#$_%&-+()*"\':;!?~`|•√π÷×¶∆£€¥¢^°={}\\©®™℅[]<>,./'


def make_keyset():
    codes = {}
    for row, start in [('1234567890', 10), ('qwertyuiop', 24), ('asdfghjkl', 38), ('zxcvbnm', 52)]:
        codes.update({c: start + index for index, c in enumerate(row)})
    codes.update({' ': 65, ',': 59, '.': 60, '/': 61, '-': 20, '=': 21, '[': 34, ']': 35, '\\': 51, ';': 47, "'": 48, '`': 49})
    for shifted, normal in zip('!@#$%^&*()_+{}|:"<>?~', '1234567890-=[]\\;\',./`'):
        codes[shifted] = -codes[normal]
    def value(c, label=None):
        fields = ['c = ' + json.dumps(c, ensure_ascii=False)]
        if label:
            fields.append('s = ' + json.dumps(label, ensure_ascii=False))
        if c in codes:
            fields.append('kc = ' + str(codes[c]))
        return '{' + ', '.join(fields) + '}'
    text = '# FUTO QWERTY hint/functional mapping; Linux adapter MIT.\nname = "sheng-futo"\n'
    hints = dict(zip('qwertyuiopasdfghjklzxcvbnm', '1234567890@#$%&-+()*"\':;!'))
    for c in 'abcdefghijklmnopqrstuvwxyz':
        text += f'\n[keys.k_{c}]\nauto_case = true\np = {value(c)}\n'
        if c in hints:
            text += f's = [{value(hints[c])}]\n'
    for c in sorted(set(SYMBOLS)):
        if c.isascii():
            text += f'\n[keys.k_u{ord(c):x}]\np = {value(c)}\n'
    for name, c in [('space', ' '), ('comma', ','), ('dot', '.')]:
        definition = value(c)
        if name == 'space':
            definition = definition[:-1] + ', s = ""}'
        text += f'\n[keys.k_{name}]\np = {definition}\n'
    for name, sym, code, label in [('enter', 0xff0d, 36, '↵'), ('backspace', 0xff08, 22, '⌫'), ('left_shift', 0xffe1, 50, '⇧'), ('tab', 0xff09, 23, '⇥')]:
        text += f'\n[keys.k_{name}]\np = {{ks = {sym}, kc = {code}, s = {json.dumps(label, ensure_ascii=False)}}}\n'
    return text


def make_themes(source):
    """Map the actual pinned FUTO default palettes to the Linux renderer."""
    result = {}
    for scheme, title in [('light', 'FUTO Light'), ('dark', 'FUTO Dark')]:
        block = source.split('private val ' + scheme + 'Scheme = ', 1)[1].split('\n)', 1)[0]
        colors = dict(re.findall(r'(\w+)=Color\(0xFF([0-9A-Fa-f]{6})\)', block))
        result[scheme] = (f'# Derived from FUTO default {scheme} palette; see installed LICENSE.md.\n'
                          f'name = "{title}"\n\n[palette]\n'
                          f'background = "#{colors["keyboardSurface"]}"\n'
                          f'text = "#{colors["onKeyboardContainer"]}"\n'
                          f'primary = "#{colors["primary"]}"\n'
                          'success = "#34a853"\n'
                          f'danger = "#{colors["error"]}"\n'
                          'warning = "#e5a126"\n')
    return result


def make_emoji(source):
    arrays = {node.get('name'): node for node in ET.fromstring(source).findall('array')}
    result = []
    for name, label, icon in [('faces', '表情', '☺'), ('nature', '自然', '🌸'), ('objects', '物品', '☕'), ('places', '地点', '🌍'), ('symbols', '符号', '♡')]:
        entries = []
        for item in arrays.get('emoji_' + name, []):
            raw = (item.text or '').strip().split('|')
            points = raw[1] if len(raw) > 1 and raw[1] else raw[0]
            try:
                values = [int(code, 16) for code in points.split(',')]
                if any(code < 0x20 or 0xE000 <= code <= 0xF8FF or 0xF0000 <= code <= 0x10FFFF for code in values):
                    continue
                value = ''.join(chr(code) for code in values)
                if value and value not in entries:
                    entries.append(value)
            except ValueError:
                continue
        result.append({'label': label, 'icon': icon, 'items': entries})
    return result


def make_icons(source, target):
    """Preserve the actual pinned Android paths, not font lookalikes."""
    android = '{http://schemas.android.com/apk/res/android}'
    target.mkdir()
    for name in ['chevron_right', 'chevron_left', 'chevron_up', 'chevron_down', 'shift', 'shiftshifted', 'delete', 'smile', 'settings', 'mic', 'globe', 'edit_text', 'clipboard', 'undo', 'redo', 'keyboard_icon']:
        raw = source / 'java/res/drawable' / (name + '.xml')
        root = ET.fromstring(raw.read_text(encoding='utf-8'))
        svg = ET.Element('svg', {'xmlns': 'http://www.w3.org/2000/svg', 'viewBox': '0 0 ' + root.get(android + 'viewportWidth') + ' ' + root.get(android + 'viewportHeight')})
        clip_index = [0]
        def convert(parent, node):
            if node.tag == 'group':
                group = ET.SubElement(parent, 'g')
                for child in node:
                    convert(group, child)
                return
            if node.tag == 'clip-path':
                clip_index[0] += 1
                identifier = 'android-clip-' + str(clip_index[0])
                defs = ET.SubElement(svg, 'defs')
                clip = ET.SubElement(defs, 'clipPath', {'id': identifier})
                ET.SubElement(clip, 'path', {'d': node.get(android + 'pathData')})
                parent.set('clip-path', 'url(#' + identifier + ')')
                return
            if node.tag != 'path':
                raise ValueError('Review unsupported icon element: ' + name + '/' + node.tag)
            values = {'d': node.get(android + 'pathData')}
            fill = node.get(android + 'fillColor', '#ffffff')
            values['fill'] = 'none' if fill in ('#00000000', '@android:color/transparent') else '#ffffff'
            if node.get(android + 'strokeColor'):
                values['stroke'] = '#ffffff'
                for original, output in [('strokeWidth', 'stroke-width'), ('strokeLineJoin', 'stroke-linejoin'), ('strokeLineCap', 'stroke-linecap')]:
                    if node.get(android + original):
                        values[output] = node.get(android + original)
            ET.SubElement(parent, 'path', values)
        for child in root:
            convert(svg, child)
        (target / (name + '.svg')).write_bytes(('<!-- Original FUTO Android vector paths; source/license in installed NOTICE. -->\n' + ET.tostring(svg, encoding='unicode') + '\n').encode())
    # Preserve the original return glyph; tinting is performed by the SVG renderer.
    image = (source / 'java/res/drawable-xxxhdpi/sym_keyboard_return_lxx_light.png').read_bytes()
    encoded = base64.b64encode(image).decode('ascii')
    (target / 'return.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24"><image width="24" height="24" xlink:href="data:image/png;base64,' + encoded + '"/></svg>\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=pathlib.Path)
    parser.add_argument('--layouts-archive', type=pathlib.Path)
    parser.add_argument('--output-dir', type=pathlib.Path, default=PROJECT / 'out/futo-source')
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit('Select a fresh, empty output directory')
    pin = json.loads((LOCAL / 'provenance.json').read_text(encoding='utf-8'))
    patch = (LOCAL / 'linux-core.patch').read_bytes().replace(b'\r\n', b'\n')
    if sha(patch) != pin['patch_sha256']:
        raise SystemExit('Patch SHA-256 mismatch; review provenance first')
    source = download_or_read(args.archive, 'https://codeload.github.com/futo-org/android-keyboard/tar.gz/' + pin['commit'], pin['archive_sha256'])
    layouts = download_or_read(args.layouts_archive, 'https://codeload.github.com/futo-org/futo-keyboard-layouts/tar.gz/' + pin['layouts_commit'], pin['layouts_archive_sha256'])
    extract(source, args.output_dir)
    for name, expected in pin['base_files'].items():
        if sha((args.output_dir / name).read_bytes()) != expected:
            raise SystemExit('Unexpected base file: ' + name)
    layouts_dir = args.output_dir / 'java/assets/layouts'
    extract(layouts, layouts_dir)
    subprocess.run(['git', 'apply', '--check', '-'], input=patch, cwd=args.output_dir, check=True)
    subprocess.run(['git', 'apply', '-'], input=patch, cwd=args.output_dir, check=True)
    generated = args.output_dir / 'linux-data'
    generated.mkdir()
    tsv = wordlist((args.output_dir / 'dictionaries/en_US_wordlist.combined.gz').read_bytes())
    (generated / 'en_US.tsv').write_bytes(tsv.encode('utf-8'))
    rows = layout_rows((layouts_dir / pin['layout']).read_text(encoding='utf-8'))
    for orientation in ('landscape', 'portrait'):
        (generated / f'sheng-futo-{orientation}.toml').write_bytes(make_layout(rows, orientation).encode('utf-8'))
    (generated / 'sheng-futo-keys.toml').write_bytes(make_keyset().encode('utf-8'))
    emojis = make_emoji((args.output_dir / 'java/res/values-v19/emoji-categories.xml').read_text(encoding='utf-8'))
    emoji_toml = '# Public FUTO/AOSP bundled emoji categories; original notices retained.\n'
    for category in emojis:
        emoji_toml += '\n[[categories]]\n' + ''.join(key + ' = ' + json.dumps(category[key], ensure_ascii=False) + '\n' for key in ('label', 'icon', 'items'))
    (generated / 'emoji.toml').write_bytes(emoji_toml.encode('utf-8'))
    make_icons(args.output_dir, generated / 'icons')
    palettes = args.output_dir / 'java/src/org/futo/inputmethod/latin/uix/theme/presets/DefaultLightDark.kt'
    for scheme, content in make_themes(palettes.read_text(encoding='utf-8')).items():
        (generated / f'sheng-futo-{scheme}.toml').write_bytes(content.encode('utf-8'))
    (args.output_dir / 'NOTICE.sheng').write_text(
        'EXPERIMENTAL MODIFIED LINUX PORT; not an official FUTO product.\n'
        'Original FUTO Keyboard: ' + pin['repository'] + '\nCommit: ' + pin['commit'] + '\n'
        'FUTO Source First License 1.1-kb and all per-file notices apply.\n'
        'Only native dictionary/typing components are built. Android UI, payment,\n'
        'models and settings source remain unmodified in the prepared tree.\n'
        'No Android APK, payment bypass, neural model, account or learning data is shipped.\n'
        'Support the original project: https://keyboard.futo.org/\n'
        'QWERTY layouts: Apache-2.0. Linux adapters: MIT.\n', encoding='utf-8')
    (generated / 'manifest.json').write_text(json.dumps(pin, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'upstream_commit': pin['commit'], 'public_unigrams': len(tsv.splitlines()), 'layout': pin['layout']}, indent=2))


if __name__ == '__main__':
    main()
