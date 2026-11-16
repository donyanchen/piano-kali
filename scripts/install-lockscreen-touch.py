#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Patch only the lockscreen presentation; preserve the KDE authenticator."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo on the target tablet')
    source = pathlib.Path(__file__).resolve().parents[1] / 'device/theme/lockscreen'
    pin = json.loads((source / 'provenance.json').read_text(encoding='utf-8'))
    target = pathlib.Path(pin['target'])
    distributed = pathlib.Path(str(target) + '.distrib')
    state = pathlib.Path('/var/lib/sheng-lockscreen')
    installed = state / 'installed.json'
    if args.restore:
        previous = json.loads(installed.read_text())
        if hashlib.sha256(target.read_bytes()).hexdigest() != previous['installed_sha256']:
            raise SystemExit('Lockscreen changed since installation; inspect it before restoring')
        if not distributed.is_file():
            raise SystemExit('Missing distribution backup; refusing to remove the current UI')
        target.unlink()
        subprocess.run(['dpkg-divert', '--local', '--remove', '--rename', str(target)], check=True)
        (target.parent / 'ShengClock.qml').unlink(missing_ok=True)
        print('Restored the KDE lockscreen. Applies to the next greeter; no session was restarted.')
        return
    baseline = distributed if distributed.exists() else target
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != pin['baseline_sha256']:
        raise SystemExit('Unsupported lockscreen version; review the patch against this system first')
    with tempfile.TemporaryDirectory(prefix='sheng-lockscreen-') as tmp:
        stage = pathlib.Path(tmp)
        (stage / target.name).write_bytes(baseline.read_bytes())
        patch = (source / 'LockScreenUi.patch').read_bytes().replace(b'\r\n', b'\n')
        subprocess.run(['git', 'apply', '--check', '-'], input=patch, cwd=stage, check=True)
        subprocess.run(['git', 'apply', '-'], input=patch, cwd=stage, check=True)
        patched = (stage / target.name).read_bytes()
    backup = state / ('backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True, mode=0o700)
    state.chmod(0o700)
    shutil.copy2(target, backup / target.name)
    if not distributed.exists():
        subprocess.run(['dpkg-divert', '--local', '--add', '--rename', str(target)], check=True)
    shutil.copyfile(source / 'ShengClock.qml', target.parent / 'ShengClock.qml')
    (target.parent / 'ShengClock.qml').chmod(0o644)
    temporary = target.with_suffix('.qml.sheng-new')
    temporary.write_bytes(patched)
    temporary.chmod(0o644)
    temporary.replace(target)
    installed.write_text(json.dumps({'backup': str(backup), 'installed_sha256': hashlib.sha256(patched).hexdigest()}, indent=2) + '\n')
    print('Installed clock and touch presentation. The existing PAM/password path is unchanged.')
    print('Applies to the next greeter; the current session/lockscreen was not restarted.')


if __name__ == '__main__':
    main()
