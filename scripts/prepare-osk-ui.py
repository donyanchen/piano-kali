#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch pinned Fcitx5 OSK source and apply the Sheng touch UI adaptation."""
import argparse
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import tarfile
import urllib.request

PROJECT = pathlib.Path(__file__).resolve().parents[1]
LOCAL = PROJECT / 'device/input-method'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=pathlib.Path, help='Optional verified upstream archive')
    parser.add_argument('--output-dir', type=pathlib.Path, default=PROJECT / 'out/osk-source')
    parser.add_argument('--futo-ui', action='store_true', help='Also apply the native FUTO UI/UX port (requires its runtime package)')
    args = parser.parse_args()
    pin = json.loads((LOCAL / 'provenance.json').read_text(encoding='utf-8'))
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit('Output directory is not empty; select a fresh build directory')
    if args.archive:
        data = args.archive.read_bytes()
    else:
        url = 'https://codeload.github.com/fortime/fcitx5-osk/tar.gz/' + pin['osk_commit']
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
    if sha(data) != pin['osk_archive_sha256']:
        raise SystemExit('Upstream source archive SHA-256 mismatch')
    patch = (LOCAL / 'hyperos-ui.patch').read_bytes().replace(b'\r\n', b'\n')
    if sha(patch) != pin['ui_patch_sha256']:
        raise SystemExit('UI patch changed; review and update provenance.json')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive.getmembers():
            parts = pathlib.PurePosixPath(member.name).parts[1:]
            if not parts or member.isdir():
                continue
            if '..' in parts or any('\\' in p or ':' in p for p in parts) or not member.isfile():
                raise SystemExit('Unsupported archive entry')
            target = args.output_dir.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    for name, expected in pin['base_files'].items():
        if sha((args.output_dir / name).read_bytes()) != expected:
            raise SystemExit('Unexpected base source: ' + name)
    subprocess.run(['git', 'apply', '--check', '-'], input=patch, cwd=args.output_dir, check=True)
    subprocess.run(['git', 'apply', '-'], input=patch, cwd=args.output_dir, check=True)
    protocol = (LOCAL / 'fcitx5-1.23.patch').read_bytes().replace(b'\r\n', b'\n')
    if sha(protocol) != pin['fcitx_protocol_patch_sha256']:
        raise SystemExit('Fcitx protocol patch SHA-256 mismatch')
    subprocess.run(['git', 'apply', '--check', '-'], input=protocol, cwd=args.output_dir, check=True)
    subprocess.run(['git', 'apply', '-'], input=protocol, cwd=args.output_dir, check=True)
    for source in (LOCAL / 'ui').glob('*.toml'):
        category = 'key_sets' if source.name.endswith('-keys.toml') else 'layouts' if source.name.endswith(('-landscape.toml', '-portrait.toml')) else 'themes'
        target = args.output_dir / 'pkg/share/fcitx5-osk' / category / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if args.futo_ui:
        futo = PROJECT / 'device/futo-keyboard'
        futo_pin = json.loads((futo / 'provenance.json').read_text(encoding='utf-8'))
        ui_patch = (futo / 'futo-ui.patch').read_bytes().replace(b'\r\n', b'\n')
        if sha(ui_patch) != futo_pin['ui_patch_sha256']:
            raise SystemExit('FUTO UI patch SHA-256 mismatch')
        for name, expected in futo_pin['ui_files'].items():
            if sha((futo / name).read_bytes().replace(b'\r\n', b'\n')) != expected:
                raise SystemExit('Unexpected FUTO UI source: ' + name)
        subprocess.run(['git', 'apply', '--check', '-'], input=ui_patch, cwd=args.output_dir, check=True)
        subprocess.run(['git', 'apply', '-'], input=ui_patch, cwd=args.output_dir, check=True)
        shutil.copyfile(futo / 'ui/futo_ui.rs', args.output_dir / 'fcitx5-osk/src/futo_ui.rs')
        shutil.copyfile(futo / 'FUTO-LICENSE.md', args.output_dir / 'FUTO-LICENSE.md')
        (args.output_dir / 'NOTICE.FUTO').write_text('Native Linux FUTO UI/UX adaptation, not an official FUTO build.\n'
            'Upstream references: ' + futo_pin['repository'] + '@' + futo_pin['commit'] + '\n'
            'ActionBar.kt, v2keyboard/Keyboard.kt, DefaultLightDark.kt and layout schemas.\n'
            'FUTO Source First terms and per-file notices remain applicable to upstream content.\n'
            'New Linux rendering/integration: MIT. Support the original: https://keyboard.futo.org/\n', encoding='utf-8')
    (args.output_dir / 'NOTICE.sheng').write_text(
        'Fcitx5 OSK by fortime, MIT.\nSheng touch UI modifications, MIT.\n'
        'Upstream commit: ' + pin['osk_commit'] + '\n'
        'Source: https://github.com/LuKeyC-NetSEC/sheng-kali-linux\n', encoding='utf-8')
    print(json.dumps({'source': str(args.output_dir.resolve()), 'upstream_commit': pin['osk_commit'], 'ui_patch_sha256': sha(patch)}, indent=2))


if __name__ == '__main__':
    main()
