#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Enable the native FUTO adapter while preserving Metasequoia Chinese input."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import time


def update_config(original, values):
    import tomllib
    updated = original
    for key, value in values.items():
        line = key + ' = ' + json.dumps(value, ensure_ascii=False)
        if re.search(r'^' + re.escape(key) + r'\s*=', updated, re.M):
            updated = re.sub(r'^' + re.escape(key) + r'\s*=.*$', lambda _: line, updated, count=1, flags=re.M)
        else:
            updated = line + '\n' + updated
    parsed = tomllib.loads(updated)
    if any(parsed.get(key) != value for key, value in values.items()):
        raise ValueError('OSK root settings validation failed')
    return updated


def main():
    import dbus
    import tomllib
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--refresh', action='store_true', help='Reload upgraded UI while retaining the original rollback backup')
    parser.add_argument('--compact', action='store_true', help='Use 400/300 logical-pixel floating widths on the Sheng tablet')
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise SystemExit('Run as the desktop user, without sudo')
    bus = dbus.SessionBus()
    saver = dbus.Interface(bus.get_object('org.freedesktop.ScreenSaver', '/ScreenSaver'), 'org.freedesktop.ScreenSaver')
    if saver.GetActive():
        raise SystemExit('Unlock normally before changing the input panel')
    method = subprocess.check_output(['kreadconfig6', '--file', 'kwinrc', '--group', 'Wayland', '--key', 'InputMethod'], text=True).strip()
    if not method.endswith('/sheng-msime-fcitx5.desktop'):
        raise SystemExit('First install the existing Sheng Fcitx integration; no changes made')
    config = pathlib.Path.home() / '.config/fcitx5-osk/config.toml'
    state = pathlib.Path.home() / '.local/state/sheng-futo-keyboard'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = state / 'installed.json'
    original = config.read_text(encoding='utf-8')
    previous = tomllib.loads(original)
    if args.restore:
        installed = json.loads(record.read_text(encoding='utf-8'))
        if hashlib.sha256(original.encode()).hexdigest() != installed['config_sha256']:
            raise SystemExit('OSK settings changed after setup; inspect your private backup before restoring')
        updated = pathlib.Path(installed['backup']).read_text(encoding='utf-8')
    else:
        subprocess.run(['sheng-futo-tool', '--self-test', '/usr/share/sheng-futo-keyboard/en_US'], check=True)
        for relative in ('layouts/sheng-futo-landscape.toml', 'layouts/sheng-futo-portrait.toml', 'themes/sheng-futo-light.toml', 'themes/sheng-futo-dark.toml'):
            if not (pathlib.Path('/usr/share/fcitx5-osk') / relative).is_file():
                raise SystemExit('Install the native FUTO package and layouts first')
        if not (args.refresh or args.compact) and record.exists() and json.loads(record.read_text()).get('completed') and previous.get('default_landscape_layout') == 'sheng-futo-landscape':
            print('FUTO keyboard settings are already enabled; no input process was restarted.')
            return
        values = {'default_landscape_layout': 'sheng-futo-landscape', 'default_portrait_layout': 'sheng-futo-portrait',
                  'theme': 'Auto', 'light_theme': 'FUTO Light', 'dark_theme': 'FUTO Dark', 'default_font': 'Roboto'}
        if args.compact and previous.get('placement') == 'Float':
            values.update(landscape_width=400.0, portrait_width=300.0)
        for key, category in [('key_area_layout_folders', 'layouts'), ('key_set_folders', 'key_sets'), ('theme_folders', 'themes')]:
            system = '/usr/share/fcitx5-osk/' + category
            folders = previous.get(key, [])
            values[key] = [system] + [folder for folder in folders if folder != system]
        updated = update_config(original, values)
    backup = state / ('before-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.toml')
    shutil.copyfile(config, backup)
    backup.chmod(0o600)

    def select(value):
        subprocess.run(['kwriteconfig6', '--file', 'kwinrc', '--group', 'Wayland', '--key', 'InputMethod', '--notify', value], check=True)

    old_owner = str(bus.get_name_owner('org.fcitx.Fcitx5')) if bus.name_has_owner('org.fcitx.Fcitx5') else ''
    old_engine = ''
    if old_owner:
        old_controller = dbus.Interface(bus.get_object('org.fcitx.Fcitx5', '/controller'), 'org.fcitx.Fcitx.Controller1')
        old_engine = str(old_controller.CurrentInputMethod())
    if not args.restore:
        rollback_backup = str(backup)
        if (args.refresh or args.compact) and record.exists() and previous.get('default_landscape_layout') == 'sheng-futo-landscape':
            rollback_backup = json.loads(record.read_text(encoding='utf-8'))['backup']
        # Write recovery metadata before touching the running panel, so a failed
        # discovery/reload can still be reverted with --restore.
        record.write_text(json.dumps({'backup': rollback_backup, 'config_sha256': hashlib.sha256(updated.encode()).hexdigest(), 'completed': False}, indent=2) + '\n', encoding='utf-8')
        record.chmod(0o600)
    try:
        select('')
        time.sleep(1)
        config.write_text(updated, encoding='utf-8')
    finally:
        select(method)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if bus.name_has_owner('org.fcitx.Fcitx5') and str(bus.get_name_owner('org.fcitx.Fcitx5')) != old_owner:
            break
        time.sleep(0.2)
    else:
        raise SystemExit('Input panel did not reload in time; saved private backup is available')
    controller = dbus.Interface(bus.get_object('org.fcitx.Fcitx5', '/controller'), 'org.fcitx.Fcitx.Controller1')
    group = controller.CurrentInputMethodGroup()
    layout, items = controller.InputMethodGroupInfo(group)
    new_items = [(str(name), str(item_layout)) for name, item_layout in items if str(name) != 'sheng-futo']
    if not args.restore:
        available = {str(item[0]) for item in controller.AvailableInputMethods()}
        if 'sheng-futo' not in available:
            raise SystemExit('FUTO engine was not discovered; use --restore to return to the saved OSK settings')
        new_items.append(('sheng-futo', ''))
    controller.SetInputMethodGroupInfo(group, layout, dbus.Array([dbus.Struct(item, signature='ss') for item in new_items], signature='(ss)'))
    if not args.restore:
        # Listing a .conf is not proof that the compiled addon can actually load.
        # Probe activation, then restore the original engine for this context.
        current = old_engine if old_engine in {name for name, _ in new_items} else str(controller.CurrentInputMethod())
        try:
            controller.SetCurrentIM('sheng-futo')
            if str(controller.CurrentInputMethod()) != 'sheng-futo':
                raise SystemExit('FUTO addon activation failed; appearance can be reverted with --restore')
        finally:
            if current and current != 'sheng-futo':
                controller.SetCurrentIM(current)
    if args.restore:
        record.unlink()
        print('Restored the previous keyboard appearance and removed the FUTO English entry from this group.')
    else:
        installed = json.loads(record.read_text(encoding='utf-8'))
        installed['completed'] = True
        record.write_text(json.dumps(installed, indent=2) + '\n', encoding='utf-8')
        print('Enabled FUTO layouts/English adapter; Metasequoia Chinese, physical-keyboard suppression and placement retained.')
    print('Only the input panel was reloaded. Applications, KWin and the lockscreen were not restarted.')


if __name__ == '__main__':
    main()
