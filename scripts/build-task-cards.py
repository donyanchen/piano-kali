#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package the KWin effect with a content-derived ID; optionally install files."""
import argparse
import hashlib
import json
import pathlib
import zipfile

PROJECT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=pathlib.Path, default=PROJECT / 'out/packages')
    parser.add_argument('--install', action='store_true', help='Install to the current user; does not enable effect')
    args = parser.parse_args()
    source = PROJECT / 'device/recents'
    files = {p.relative_to(source).as_posix(): p.read_bytes().replace(b'\r\n', b'\n')
             for p in sorted((source / 'contents').rglob('*')) if p.is_file()}
    for name in ('metadata.json', 'LICENSE', 'README.md'):
        files[name] = (source / name).read_bytes().replace(b'\r\n', b'\n')
    revision = hashlib.sha256(b''.join(k.encode() + b'\0' + v for k, v in sorted(files.items()))).hexdigest()[:12]
    identifier = 'sheng-task-cards-' + revision
    metadata = json.loads(files['metadata.json'])
    metadata['KPlugin']['Id'] = identifier
    metadata['KPlugin']['Version'] = '1.0.0+' + revision
    files['metadata.json'] = (json.dumps(metadata, ensure_ascii=False, indent=2) + '\n').encode()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / (identifier + '.zip')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    if args.install:
        destination = pathlib.Path.home() / '.local/share/kwin-wayland/effects' / identifier
        for name, data in files.items():
            target = destination / name
            if target.exists() and target.read_bytes() != data:
                raise SystemExit('Existing effect differs; refusing to overwrite: ' + str(target))
        for name, data in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    manifest = {'id': identifier, 'artifact': output.name, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))
    print('After disabling older Sheng effect IDs, enable as the desktop user:')
    print('kwriteconfig6 --file kwinrc --group Plugins --key ' + identifier + 'Enabled true')
    print('qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect ' + identifier)


if __name__ == '__main__':
    main()
