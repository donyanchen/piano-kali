#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install a battery glyph and round the installed Burp icon without restarting apps."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--burp-desktop', type=pathlib.Path)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Run as the Plasma desktop user without sudo')
    import dbus
    project = pathlib.Path(__file__).resolve().parents[1]
    source = project / 'device/theme/panel-style'
    files = {p.relative_to(source).as_posix(): p.read_bytes().replace(b'\r\n', b'\n')
             for p in source.rglob('*') if p.is_file()}
    revision = hashlib.sha256(b''.join(k.encode() + b'\0' + v for k, v in sorted(files.items()))).hexdigest()[:12]
    identifier = 'org.sheng.panel-style.' + revision
    metadata = json.loads(files['metadata.json'])
    metadata['KPlugin']['Id'] = identifier
    files['metadata.json'] = (json.dumps(metadata, ensure_ascii=False, indent=2) + '\n').encode()
    backup = pathlib.Path.home() / '.local/state/sheng-tablet-appearance' / ('backup-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True, mode=0o700)
    for name in ['plasma-org.kde.plasma.desktop-appletsrc', 'plasmashellrc']:
        path = pathlib.Path.home() / '.config' / name
        if path.exists(): shutil.copy2(path, backup / name)
    desktop = args.burp_desktop
    if not desktop:
        choices = list((pathlib.Path.home() / '.local/share/applications').glob('*BurpSuite.desktop'))
        if len(choices) == 1: desktop = choices[0]
    if desktop:
        data = desktop.read_text(encoding='utf-8')
        match = re.search(r'^Icon=(.+)$', data, re.M)
        previous_icon = pathlib.Path(match.group(1).strip()) if match else None
        if previous_icon and previous_icon.is_file():
            shutil.copy2(desktop, backup / desktop.name)
            icon = pathlib.Path.home() / '.local/share/icons/hicolor/scalable/apps/sheng-burpsuite-rounded.svg'
            icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(project / 'device/theme/icons/burpsuite-rounded.svg', icon)
            desktop.write_text(data[:match.start(1)] + str(icon) + data[match.end(1):], encoding='utf-8')
            subprocess.run(['kbuildsycoca6', '--noincremental'], check=True, stdout=subprocess.DEVNULL)
            print('Rounded the installed Burp icon; no application was restarted.')
    destination = pathlib.Path.home() / '.local/share/plasma/plasmoids' / identifier
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix='sheng-panel-style-') as tmp:
            stage = pathlib.Path(tmp)
            for name, content in files.items():
                path = stage / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            subprocess.run(['kpackagetool6', '--type', 'Plasma/Applet', '--install', str(stage)], check=True)
    bus = dbus.SessionBus()
    plasma = dbus.Interface(bus.get_object('org.kde.plasmashell', '/PlasmaShell'), 'org.kde.PlasmaShell')
    script = '''
var top=panels().find(p=>p.location==="top");
if(!top)throw new Error("Top panel not found");
var old=top.widgets().filter(w=>w.type.indexOf("org.sheng.panel-style.")===0);
var current=old.find(w=>w.type===TARGET)||top.addWidget(TARGET);
if(!current||current.type!==TARGET)throw new Error("Appearance widget failed to load");
old.forEach(w=>{if(w.id!==current.id)w.remove();});
print(JSON.stringify({panel:top.id,widget:current.id,plugin:current.type}));
'''.replace('TARGET', json.dumps(identifier))
    print(str(plasma.evaluateScript(script, timeout=15)).strip())
    print('Private configuration backup:', backup)


if __name__ == '__main__':
    main()
