#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package compiled native FUTO adapter/data; does not build ELF files."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

PROJECT = pathlib.Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=pathlib.Path)
    parser.add_argument('source', type=pathlib.Path)
    parser.add_argument('dictionary', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    args.build = args.build.resolve()
    args.source = args.source.resolve()
    args.dictionary = args.dictionary.resolve()
    args.output = args.output.resolve()
    for name in ('sheng-futo.so', 'sheng-futo-tool'):
        header = (args.build / name).read_bytes()[:20]
        if header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != 183:
            raise SystemExit('Expected ARM64 ELF: ' + name)
    pin = json.loads((PROJECT / 'device/futo-keyboard/provenance.json').read_text(encoding='utf-8'))
    if json.loads((args.source / 'linux-data/manifest.json').read_text()) != pin:
        raise SystemExit('Prepared source manifest does not match this port')
    subprocess.run([str(args.build / 'sheng-futo-tool'), '--self-test', str(args.dictionary)], check=True)
    fcitx_version = subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', 'fcitx5'], text=True).strip()
    with tempfile.TemporaryDirectory(prefix='sheng-futo-package-') as tmp:
        stage = pathlib.Path(tmp)
        subprocess.run(['cmake', '--install', str(args.build), '--prefix', '/usr'],
                       env={**os.environ, 'DESTDIR': str(stage)}, check=True)
        target = stage / 'usr/share/sheng-futo-keyboard/en_US'
        shutil.copytree(args.dictionary, target)
        shutil.copytree(args.source / 'linux-data/icons', stage / 'usr/share/sheng-futo-keyboard/icons')
        # Upstream creates private user dictionaries (0700/0600). This is a
        # fixed public system dictionary owned by root after dpkg installation.
        target.chmod(0o755)
        for entry in target.rglob('*'):
            entry.chmod(0o755 if entry.is_dir() else 0o644)
        for asset in (args.source / 'linux-data').glob('*.toml'):
            if asset.name == 'emoji.toml':
                dest = stage / 'usr/share/sheng-futo-keyboard/emoji.toml'
                shutil.copyfile(asset, dest)
                dest.chmod(0o644)
                continue
            category = 'key_sets' if asset.name.endswith('-keys.toml') else 'layouts' if asset.name.endswith(('-landscape.toml', '-portrait.toml')) else 'themes'
            dest = stage / 'usr/share/fcitx5-osk' / category / asset.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(asset, dest)
        for original, relative in [
            (PROJECT / 'scripts/futo-keyboard-setup.py', 'usr/bin/sheng-futo-keyboard-setup'),
            (PROJECT / 'device/futo-keyboard/README.md', 'usr/share/doc/sheng-futo-keyboard/README.md'),
            (PROJECT / 'device/futo-keyboard/provenance.json', 'usr/share/doc/sheng-futo-keyboard/provenance.json'),
            (args.source / 'java/assets/layouts/LICENSE', 'usr/share/doc/sheng-futo-keyboard/LAYOUTS-LICENSE'),
            (PROJECT / 'device/futo-keyboard/LICENSE', 'usr/share/doc/sheng-futo-keyboard/ADAPTER-LICENSE'),
        ]:
            dest = stage / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, dest)
            dest.chmod(0o755 if relative.startswith('usr/bin/') else 0o644)
        control = stage / 'DEBIAN'
        control.mkdir()
        (control / 'control').write_text(f'''Package: sheng-futo-keyboard
Version: 0.3.0-3
Architecture: arm64
Maintainer: Sheng tablet local setup
Section: non-free/text
Priority: optional
Depends: fcitx5 (= {fcitx_version}), fcitx5-modules, sheng-msime-integration (>= 0.2.1-8), libfcitx5core7, libfcitx5utils2, libfcitx5config6, libqt6core6t64 (>= 6.11.2), libc6 (>= 2.38), libstdc++6, libgcc-s1, python3 (>= 3.11), python3-dbus, fonts-noto-color-emoji, fonts-roboto
Description: Experimental native FUTO typing/layout adapter for Sheng
 FUTO native dictionary and QWERTY layout adapted to Fcitx5/Wayland.
 Non-commercial FUTO Source First terms apply to upstream components.
 Chinese input continues to use the separately installed Metasequoia engine.
''', encoding='utf-8')
        # dpkg preserves an existing directory's permissions during upgrades.
        # Repair only these fixed public files from the first experimental pack.
        (control / 'postinst').write_text('''#!/bin/sh
set -eu
if [ "$1" = configure ]; then
    directory=/usr/share/sheng-futo-keyboard/en_US
    test -d "$directory" && test ! -L "$directory"
    chmod 0755 "$directory"
    for name in en_US.header en_US.body; do
        test -f "$directory/$name" && test ! -L "$directory/$name"
        chmod 0644 "$directory/$name"
    done
fi
''', encoding='utf-8')
        (control / 'postinst').chmod(0o755)
        stage.chmod(0o755)
        for entry in stage.rglob('*'):
            if entry.is_dir():
                entry.chmod(0o755)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(args.output)], check=True)
    print(args.output)


if __name__ == '__main__':
    main()
