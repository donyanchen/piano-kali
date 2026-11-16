#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the pinned Plasma applet without a device or private build cache."""
import argparse
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

PROJECT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = PROJECT / 'device/control-center'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=pathlib.Path, help='Optional locally downloaded pinned tar.gz')
    parser.add_argument('--output', type=pathlib.Path, default=PROJECT / 'out/packages/sheng-control-center.plasmoid')
    args = parser.parse_args()
    pin = json.loads((SOURCE / 'provenance.json').read_text(encoding='utf-8'))
    url = pin['upstream'].replace('https://github.com/', 'https://codeload.github.com/') + '/tar.gz/' + pin['commit']
    if args.archive:
        data = args.archive.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
    if digest(data) != pin['upstream_archive_sha256']:
        raise SystemExit('Upstream archive SHA-256 mismatch')
    patch = (SOURCE / 'upstream-integration.patch').read_bytes().replace(b'\r\n', b'\n')
    if digest(patch) != pin['upstream_patch_sha256']:
        raise SystemExit('Patch SHA-256 mismatch; review and update provenance.json')
    with tempfile.TemporaryDirectory(prefix='sheng-control-center-') as temporary:
        stage = pathlib.Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            for member in archive.getmembers():
                parts = pathlib.PurePosixPath(member.name).parts
                if len(parts) < 3 or parts[1] != 'org.kontrol.center':
                    continue
                relative = pathlib.PurePosixPath(*parts[2:])
                if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
                    raise SystemExit('Unsafe archive path')
                if member.isdir():
                    continue
                if not member.isfile():
                    raise SystemExit('Unsupported archive entry')
                target = stage.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
        for extra in ['LICENSE', 'metadata.json', 'contents/ui/main.qml']:
            if not (stage / extra).is_file():
                raise SystemExit('Incomplete upstream package: ' + extra)
        subprocess.run(['git', 'apply', '--check', '-'], input=patch, cwd=stage, check=True)
        subprocess.run(['git', 'apply', '-'], input=patch, cwd=stage, check=True)
        for name in pin['local_files']:
            if pathlib.PurePath(name).name != name:
                raise SystemExit('Invalid local file name')
            if name.endswith('.qml'):
                target = stage / 'contents/ui' / name
            elif name.endswith('.svg'):
                target = stage / 'contents/icons' / ('sheng-' + name)
            else:
                raise SystemExit('Unsupported local asset')
            shutil.copyfile(SOURCE / name, target)
        metadata = json.loads((stage / 'metadata.json').read_text(encoding='utf-8'))
        metadata['KPlugin']['Version'] = '0.7.7-sheng-privacy4'
        (stage / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / 'NOTICE.sheng').write_text(
            'Kontrol Center by ItsNotMeBro87 (Agon A.), GPL-3.0-or-later.\n'
            'Upstream: ' + pin['upstream'] + '\nCommit: ' + pin['commit'] + '\n'
            'Modified by Sheng Kali contributors: tablet touch UI, services, privacy, panel integration.\n'
            'Source: https://github.com/LuKeyC-NetSEC/sheng-kali-linux\n', encoding='utf-8')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as output:
            for file in sorted(stage.rglob('*')):
                if not file.is_file():
                    continue
                relative = file.relative_to(stage).as_posix()
                entry = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                mode = 0o755 if relative.startswith('contents/scripts/') and file.suffix in ('.sh', '.py') else 0o644
                entry.external_attr = (0o100000 | mode) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                output.writestr(entry, file.read_bytes().replace(b'\r\n', b'\n'))
    manifest = {'upstream': pin['upstream'], 'commit': pin['commit'],
                'upstream_archive_sha256': digest(data), 'patch_sha256': digest(patch),
                'artifact': args.output.name, 'sha256': digest(args.output.read_bytes())}
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
