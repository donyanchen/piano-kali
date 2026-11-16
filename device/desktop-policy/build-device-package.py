#!/usr/bin/env python3
"""Build the tablet policy package on Linux from the device/ source tree."""
import pathlib
import shutil
import subprocess
import sys
import tempfile

here = pathlib.Path(__file__).resolve().parent
privacy = here.parent/'privacy'
binary = pathlib.Path(sys.argv[1]).resolve()
output = pathlib.Path(sys.argv[2]).resolve()
output.parent.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='piano-tablet-controls-package-') as directory:
    stage = pathlib.Path(directory)
    files = [
        (here.parents[1]/'scripts/install-desktop-drawer.py','usr/bin/piano-desktop-drawer-setup',0o755),
        (here/'desktop-policy.py','usr/libexec/piano-desktop-policy',0o755),
        (here/'piano-desktop-policy.service','usr/lib/systemd/user/piano-desktop-policy.service',0o644),
        (here/'org.piano.DesktopPolicy.service','usr/share/dbus-1/services/org.piano.DesktopPolicy.service',0o644),
        (privacy/'privacy-control.py','usr/libexec/piano-privacyctl',0o755),
        (privacy/'privacy-client.py','usr/bin/piano-privacy',0o755),
        (binary,'usr/libexec/piano-privacy-bpf',0o755),
        (privacy/'piano-privacy@.service','etc/systemd/system/piano-privacy@.service',0o644),
        (privacy/'piano-privacy-restore.service','etc/systemd/system/piano-privacy-restore.service',0o644),
        (privacy/'99-piano-privacy.rules','etc/udev/rules.d/99-piano-privacy.rules',0o644),
        (privacy/'51-piano-privacy.rules','etc/polkit-1/rules.d/51-piano-privacy.rules',0o644),
        (privacy/'README.md','usr/share/doc/piano-tablet-controls/privacy.md',0o644),
        (here/'README.md','usr/share/doc/piano-tablet-controls/desktop.md',0o644),
        (here.parent/'recents/LICENSE','usr/share/doc/piano-tablet-controls/copyright',0o644),
    ]
    for source,relative,mode in files:
        target = stage/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target);target.chmod(mode)
    gesture = here/'desktop-gesture'
    for source in gesture.rglob('*'):
        if source.is_file():
            target = stage/'usr/share/plasma/plasmoids/org.piano.desktop-gesture'/source.relative_to(gesture)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for bus in ['system','session']:
        target = stage/('etc/dbus-1/'+bus+'.d/51-piano-privacy.conf')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text('<busconfig>\n</busconfig>\n')
    control = stage/'DEBIAN';control.mkdir()
    (control/'control').write_text('''Package: piano-tablet-controls
Version: 1.0-6
Architecture: arm64
Maintainer: Piano tablet local setup
Depends: libc6 (>= 2.38), python3, python3-dbus, python3-gi, systemd, udev, polkitd, dbus, qdbus-qt6, alsa-utils, pulseaudio-utils, pipewire-bin, plasma-workspace, plasma-desktop, qml6-module-org-kde-plasma-workspace, kpackagetool6
Description: Dock, desktop gesture and process-level sensor privacy for piano
 Includes the Linexin setup helper and uses a cgroup BPF device guard.
''')
    (control/'conffiles').write_text('\n'.join('/'+relative for _,relative,_ in files if relative.startswith('etc/'))+'\n/etc/dbus-1/system.d/51-piano-privacy.conf\n/etc/dbus-1/session.d/51-piano-privacy.conf\n')
    scripts = {
        'postinst': '''#!/bin/sh
set -e
if [ "$1" = configure ]; then
    udevadm control --reload-rules || true
    systemctl daemon-reload
    systemctl enable piano-privacy-restore.service
    systemctl start piano-privacy-restore.service
    runuser -u kali -- mkdir -p /home/kali/.config/systemd/user/plasma-workspace.target.wants
    runuser -u kali -- ln -sfn /usr/lib/systemd/user/piano-desktop-policy.service /home/kali/.config/systemd/user/plasma-workspace.target.wants/piano-desktop-policy.service
    if [ -S /run/user/1000/bus ]; then
        runuser -u kali -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user daemon-reload
        runuser -u kali -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user restart piano-desktop-policy.service
    fi
fi
''',
        'prerm': '''#!/bin/sh
set -e
if [ "$1" = remove ]; then
    /usr/libexec/piano-privacyctl off
    systemctl disable piano-privacy-restore.service || true
    if [ -S /run/user/1000/bus ]; then
        runuser -u kali -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus systemctl --user disable --now piano-desktop-policy.service || true
    fi
fi
''',
        'postrm': '''#!/bin/sh
systemctl daemon-reload || true
udevadm control --reload-rules || true
''',
    }
    for name,text in scripts.items():
        target = control/name;target.write_text(text);target.chmod(0o755)
    subprocess.run(['dpkg-deb','--root-owner-group','--build',str(stage),str(output)],check=True)
print(output)
