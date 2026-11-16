#!/usr/bin/env python3
"""Package an already-built ARM64 gesture bridge; run on the Linux tablet."""
import pathlib
import shutil
import subprocess
import sys
import tempfile

source = pathlib.Path(__file__).resolve().parent
binary = pathlib.Path(sys.argv[1]).resolve()
output = pathlib.Path(sys.argv[2]).resolve()
output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='sheng-task-gestures-package-') as directory:
    stage = pathlib.Path(directory)
    for local, relative, mode in [
        (binary, 'usr/libexec/sheng-task-gestures', 0o755),
        (source/'sheng-task-gestures.service', 'etc/systemd/system/sheng-task-gestures.service', 0o644),
        (source/'83-sheng-task-gestures.rules', 'etc/udev/rules.d/83-sheng-task-gestures.rules', 0o644),
        (source/'install-native-tabbox.py', 'usr/libexec/sheng-native-tabbox-setup', 0o755),
        (source/'LICENSE', 'usr/share/doc/sheng-task-gestures/copyright', 0o644),
        (source/'README.md', 'usr/share/doc/sheng-task-gestures/README.md', 0o644),
    ]:
        target = stage/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, target)
        target.chmod(mode)
    control = stage/'DEBIAN'
    control.mkdir()
    (control/'control').write_text('''Package: sheng-task-gestures
Version: 1.0-1
Architecture: arm64
Maintainer: Sheng tablet local setup
Depends: libc6 (>= 2.38), libstdc++6, libgcc-s1, libinput10, libudev1, systemd, udev, qdbus-qt6, python3
Description: Native three-finger Alt+Tab and task cards bridge for Xiaomi sheng
 Uses the current Kali user session and the separately installed task-card effect.
''')
    (control/'conffiles').write_text('/etc/systemd/system/sheng-task-gestures.service\n/etc/udev/rules.d/83-sheng-task-gestures.rules\n')
    scripts = {
        'postinst': '''#!/bin/sh
set -e
if [ "$1" = configure ]; then
    udevadm control --reload-rules || true
    systemctl daemon-reload
    systemctl enable sheng-task-gestures.service
    systemctl restart sheng-task-gestures.service
fi
''',
        'prerm': '''#!/bin/sh
set -e
if [ "$1" = remove ]; then
    systemctl disable --now sheng-task-gestures.service || true
fi
''',
        'postrm': '''#!/bin/sh
if [ "$1" = remove ] || [ "$1" = purge ]; then
    udevadm control --reload-rules || true
    systemctl daemon-reload || true
fi
''',
    }
    for name, content in scripts.items():
        target = control/name
        target.write_text(content)
        target.chmod(0o755)
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(output)], check=True)
print(output)
