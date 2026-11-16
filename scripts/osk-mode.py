#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Switch the Sheng Fcitx5 OSK between draggable float and bottom dock."""
import argparse
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import time


def main():
    import tomllib  # Target Kali Python >= 3.11; source checks need not import it.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['float', 'dock'])
    parser.add_argument('--font-defaults', action='store_true', help='Use installed Noto CJK and Material Design symbol fonts')
    parser.add_argument('--sheng-ui', action='store_true', help='Select the installed Sheng touch layout and automatic light/dark themes')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Run as the desktop user, without sudo')
    method = subprocess.check_output(['kreadconfig6', '--file', 'kwinrc', '--group', 'Wayland', '--key', 'InputMethod'], text=True).strip()
    if not method.endswith('/sheng-msime-fcitx5.desktop'):
        raise SystemExit('The Sheng Fcitx5 input method is not selected; no changes made')
    locked = subprocess.check_output(['qdbus6', 'org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver.GetActive'], text=True).strip()
    if locked != 'false':
        raise SystemExit('Unlock the desktop before switching OSK placement')
    config = pathlib.Path.home() / '.config/fcitx5-osk/config.toml'
    original = config.read_text(encoding='utf-8')
    previous = tomllib.loads(original)
    values = {'placement': 'Float' if args.mode == 'float' else 'Dock',
              'landscape_width': 640.0 if args.mode == 'float' else 1024.0,
              'portrait_width': 480.0 if args.mode == 'float' else 768.0}
    if args.font_defaults:
        for family in ('Noto Sans CJK SC', 'Material Design Icons version 6'):
            found = subprocess.check_output(['fc-match', '-f', '%{family}', family], text=True)
            if family not in found:
                raise SystemExit('Missing font: ' + family + '; install fonts-noto-cjk and fonts-materialdesignicons-legacy')
        values.update(default_font='Noto Sans CJK SC', default_nerd_font='Material Design Icons version 6')
    if args.sheng_ui:
        if not pathlib.Path('/usr/share/fcitx5-osk/layouts/sheng-hyperos-landscape.toml').is_file():
            raise SystemExit('Install the Sheng UI assets and patched OSK first')
        values.update(default_landscape_layout='sheng-hyperos-landscape',
                      default_portrait_layout='sheng-hyperos-portrait',
                      theme='Auto', light_theme='Sheng Light', dark_theme='Sheng Dark')
        for key, category in [('key_area_layout_folders', 'layouts'), ('key_set_folders', 'key_sets'), ('theme_folders', 'themes')]:
            defaults = [str(pathlib.Path(p)/'fcitx5-osk'/category) for p in os.environ.get('XDG_CONFIG_DIRS', '/etc/xdg').split(':') if p]
            defaults.append(str(pathlib.Path.home()/'.config/fcitx5-osk'/category))
            folders = previous.get(key) or defaults
            system = '/usr/share/fcitx5-osk/' + category
            values[key] = [system] + [folder for folder in folders if folder != system]
    updated = original
    for key, value in values.items():
        line = key + ' = ' + json.dumps(value, ensure_ascii=False)
        if re.search(r'^' + key + r'\s*=', updated, re.M):
            updated = re.sub(r'^' + key + r'\s*=.*$', lambda _: line, updated, count=1, flags=re.M)
        else:
            updated = line + '\n' + updated
    parsed = tomllib.loads(updated)
    if any(parsed.get(k) != v for k, v in values.items()):
        raise SystemExit('Could not update root TOML keys; no changes made')
    state = pathlib.Path.home() / '.local/state/sheng-input-method'
    state.mkdir(parents=True, exist_ok=True)
    backup = state / ('osk-before-' + args.mode + '-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.toml')
    shutil.copy2(config, backup)

    def select(value):
        subprocess.run(['kwriteconfig6', '--file', 'kwinrc', '--group', 'Wayland', '--key', 'InputMethod', '--notify', value], check=True)

    try:
        # Restart only the input panel so its cached config/fonts are reloaded.
        select('')
        time.sleep(1)
        config.write_text(updated, encoding='utf-8')
    finally:
        select(method)
    print(json.dumps({'mode': args.mode, 'settings': values, 'backup': str(backup)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
