#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Export an allowlisted, portable Plasma desktop profile, without changing the session."""
import argparse
import configparser
import datetime
import json
import os
import pathlib
import re
import subprocess

KCONFIG = {
    'kdeglobals': {
        'General': ['ColorScheme', 'accentColorFromWallpaper', 'AccentColor', 'font', 'fixed', 'menuFont', 'smallestReadableFont', 'toolBarFont'],
        'KDE': ['LookAndFeelPackage', 'widgetStyle', 'SingleClick'],
        'Icons': ['Theme'], 'WM': ['activeFont'],
    },
    'kcminputrc': {'Mouse': ['cursorTheme', 'cursorSize']},
    'plasmarc': {'Theme': ['name']},
    'kwinrc': {
        'Desktops': ['Number', 'Rows'],
        'org.kde.kdecoration2': ['library', 'theme', 'BorderSize', 'BorderSizeAuto'],
        'TabBox': ['LayoutName', 'LayoutNameAlternative'],
        'Wayland': ['InputMethod', 'VirtualKeyboardEnabled'],
    },
    'kscreenlockerrc': {'Daemon': ['Autolock', 'LockGrace', 'Timeout'], 'Greeter': ['WallpaperPlugin']},
    'powerdevilrc': {
        **{profile + '][SuspendAndShutdown': ['PowerButtonAction', 'PowerDownAction', 'SleepMode', 'AutoSuspendAction', 'AutoSuspendIdleTimeoutSec'] for profile in ['AC', 'Battery', 'LowBattery']},
        **{profile + '][Display': ['TurnOffDisplayWhenIdle', 'TurnOffDisplayIdleTimeoutSec', 'TurnOffDisplayIdleTimeoutWhenLockedSec', 'LockBeforeTurnOffDisplay'] for profile in ['AC', 'Battery', 'LowBattery']},
    },
}
WIDGETS = {
    'org.kde.plasma.kickoff': {'General': ['icon']},
    'org.kde.plasma.systemtray': {'General': ['scaleIconsToFit', 'iconSpacing', 'showAllItems']},
    'org.kde.plasma.digitalclock': {'Appearance': ['showDate', 'dateFormat', 'customDateFormat', 'showSeconds', 'use24hFormat', 'dateDisplayFormat', 'autoFontAndSize', 'fontSize', 'boldText', 'fontFamily']},
    'org.kde.plasma.battery': {'General': ['showPercentage']},
    'org.kde.plasma.windowlist': {}, 'org.kde.plasma.appmenu': {}, 'org.kde.plasma.panelspacer': {},
    'luisbocanegra.panel.colorizer': {'General': ['hideWidget', 'isEnabled', 'globalSettings']},
    'org.kontrol.center': {'Appearance': ['panelWidth', 'panelHeight', 'opacity', 'transparency', 'showButton', 'hideButton']},
    'org.sheng.linexin.launcher': {'General': ['appNameFormat', 'alphaSort', 'recentOrdering', 'showRecentApps', 'showRecentDocs', 'showRecentFolders', 'useExtraRunners', 'appsIconSize', 'favsIconSize', 'systemIconSize', 'categoryFontSize', 'dashboardFontSize', 'allAppsFontSize', 'recentAppsFontSize', 'recentFilesFontSize', 'animationDuration', 'iconEntranceDuration', 'hoverEffectDuration', 'folderPopupDuration', 'appLaunchDuration', 'dragMoveDuration', 'folderCreateDuration', 'folderAddDuration', 'folderRemoveDuration', 'backgroundOpacity', 'useCustomBackgroundColor', 'backgroundColor', 'defaultCategory', 'showActiveApps', 'showAllAppsInDashboard']},
    'org.sheng.panel-style': {}, 'org.sheng.desktop-gesture': {},
    'Redmi.Clock': {'General': ['colorHex', 'boldfonts', 'showSeconds', 'fontSize', 'timeFormat', 'dateFormat', 'use24hFormat']},
}
OSK_KEYS = ['placement', 'landscape_width', 'portrait_width', 'default_font', 'default_nerd_font', 'default_landscape_layout', 'default_portrait_layout', 'theme', 'light_theme', 'dark_theme', 'ignore_fcitx_show']
PACKAGES = ['kwin-wayland', 'plasma-workspace', 'plasma-desktop', 'libqt6core6t64', 'sheng-tablet-controls', 'sheng-msime-integration', 'sheng-futo-keyboard', 'fcitx5', 'fonts-noto-core', 'fonts-noto-cjk', 'fonts-materialdesignicons-legacy', 'fonts-roboto']
PRIVATE = re.compile(r'/(?:home|root|run/user|tmp|var/tmp)/|file://|\b[A-Za-z]:[\\/]|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', re.I)
STYLE_KEY = re.compile(r'password|secret|token|path|filename|image|url|uri|uuid|latitude|longitude|location|cache', re.I)


def canonical(plugin):
    for prefix in ['org.sheng.linexin.launcher', 'org.sheng.panel-style', 'org.sheng.desktop-gesture']:
        if plugin == prefix or plugin.startswith(prefix + '.'):
            return prefix
    return plugin


def safe_style(value):
    """Keep appearance primitives, never file/image sources or free-form content."""
    if isinstance(value, dict):
        if value.get('enabled') is False:
            return {'enabled': False}
        result = {}
        for key, item in value.items():
            if STYLE_KEY.search(key) or key in ['text', 'label', 'description', 'associations', 'overrides']:
                continue
            clean = safe_style(item)
            if clean is not None:
                result[key] = clean
        return result
    if isinstance(value, list):
        return [clean for item in value if (clean := safe_style(item)) is not None]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str) and not PRIVATE.search(value) and re.fullmatch(r'[A-Za-z0-9_ .#(),%+\-]*', value) and len(value) <= 120:
        return value
    return None


def launcher_role(value):
    # No custom desktop filename, home path, Exec or activation helper is exported.
    name = str(value).lower()
    for needle, role in [('burpsuite', 'burp-suite'), ('dolphin', 'file-manager'), ('firefox', 'browser'), ('konsole', 'terminal'), ('systemsettings', 'system-settings')]:
        if needle in name:
            return role
    return None


def read_kconfig(home):
    result = {}
    for name, groups in KCONFIG.items():
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read(home / '.config' / name, encoding='utf-8')
        selected = {}
        for group, keys in groups.items():
            values = {key: parser.get(group, key) for key in keys if parser.has_option(group, key)}
            if values:
                selected[group] = values
        if selected:
            result[name] = selected
    return result


def sanitize_layout(raw):
    result = []
    for containment in raw:
        widgets, ids, counts = [], {}, {}
        for widget in containment['widgets']:
            plugin = canonical(widget['plugin'])
            if plugin not in WIDGETS:
                continue
            counts[plugin] = counts.get(plugin, 0) + 1
            role = plugin + '#' + str(counts[plugin])
            ids[str(widget['id'])] = role
            settings = {}
            for group, allowed in WIDGETS[plugin].items():
                values = {key: value for key, value in widget['settings'].get(group, {}).items() if key in allowed}
                if 'globalSettings' in values:
                    appearance = json.loads(values.pop('globalSettings'))
                    values['globalSettings'] = safe_style({key: appearance[key] for key in ['panel', 'widgets', 'trayWidgets', 'nativePanel'] if key in appearance})
                if values:
                    settings[group] = values
            entry = {'role': role, 'plugin': plugin, 'settings': settings}
            if containment['kind'] == 'desktop' and plugin == 'Redmi.Clock':
                entry['geometry'] = widget['geometry']
            if plugin == 'org.sheng.linexin.launcher':
                launchers = widget.get('launchers', [])
                if isinstance(launchers, str):
                    launchers = launchers.split(',')
                entry['pinnedApplicationRoles'] = list(dict.fromkeys(role for value in launchers if (role := launcher_role(value))))
            widgets.append(entry)
        entry = {key: containment[key] for key in ['kind', 'position', 'height', 'alignment', 'lengthMode', 'maximumLength', 'minimumLength', 'floating'] if key in containment}
        order = [ids[value] for value in str(containment.get('order', '')).split(';') if value in ids]
        entry.update(applets=widgets, appletOrder=order)
        entry['detachedApplets'] = [widget['role'] for widget in widgets if widget['role'] not in order] if containment['kind'] == 'panel' else []
        result.append(entry)
    return result


def validate(profile):
    expected = {'schemaVersion', 'capturedAtUTC', 'platform', 'kconfig', 'layout', 'displays', 'screenKeyboard', 'wallpapers'}
    if set(profile) != expected or profile['schemaVersion'] != 1:
        raise ValueError('Unexpected profile schema')
    if PRIVATE.search(json.dumps(profile, ensure_ascii=False)):
        raise ValueError('Profile contains a private path or runtime identifier')
    for filename, groups in profile['kconfig'].items():
        if filename not in KCONFIG:
            raise ValueError('Unexpected KConfig file')
        for group, values in groups.items():
            if group not in KCONFIG[filename]:
                raise ValueError('Unexpected KConfig group')
            if set(values) - set(KCONFIG.get(filename, {}).get(group, [])):
                raise ValueError('Unexpected KConfig key')
    for containment in profile['layout']:
        if set(containment) - {'kind', 'position', 'height', 'alignment', 'lengthMode', 'maximumLength', 'minimumLength', 'floating', 'applets', 'appletOrder', 'detachedApplets'}:
            raise ValueError('Unexpected containment data')
        roles = {widget['role'] for widget in containment['applets']}
        if set(containment['appletOrder']) - roles:
            raise ValueError('Unresolved applet order')
        for widget in containment['applets']:
            if set(widget) - {'role', 'plugin', 'settings', 'geometry', 'pinnedApplicationRoles'}:
                raise ValueError('Unexpected widget data')
            if widget['plugin'] not in WIDGETS:
                raise ValueError('Unexpected applet')
            for group, values in widget['settings'].items():
                if group not in WIDGETS[widget['plugin']]:
                    raise ValueError('Unexpected widget group')
                if set(values) - set(WIDGETS[widget['plugin']].get(group, [])):
                    raise ValueError('Unexpected widget key')
    if set(profile['screenKeyboard']) - set(OSK_KEYS):
        raise ValueError('Unexpected OSK key')


def export_profile():
    if os.geteuid() == 0:
        raise SystemExit('Run as the Plasma desktop user, without sudo')
    import dbus
    import tomllib
    device_tree = pathlib.Path('/sys/firmware/devicetree/base')
    compatible = (device_tree / 'compatible').read_bytes() if (device_tree / 'compatible').exists() else b''
    model = (device_tree / 'model').read_text(errors='replace') if (device_tree / 'model').exists() else ''
    if b'xiaomi,sheng' not in compatible and 'pad 6s pro' not in model.lower():
        raise SystemExit('This profile exporter is scoped to Xiaomi sheng; target model did not match')
    home = pathlib.Path.home()
    bus = dbus.SessionBus()
    plasma = dbus.Interface(bus.get_object('org.kde.plasmashell', '/PlasmaShell'), 'org.kde.PlasmaShell')
    script = '''
var spec=SPEC;var result=[];
panels().concat(desktops()).forEach(function(p){
    var panel=p.location!==undefined; p.currentConfigGroup=["General"];
    var c={kind:panel?"panel":"desktop",widgets:[],order:p.readConfig("AppletOrder","")};
    if(panel){c.position=p.location;c.height=p.height;c.alignment=p.alignment;c.lengthMode=p.lengthMode;c.maximumLength=p.maximumLength;c.minimumLength=p.minimumLength;c.floating=p.floating;}
    p.widgets().forEach(function(w){
        var plugin=w.type;Object.keys(spec).forEach(function(k){if(k.indexOf("org.sheng.")===0&&(plugin===k||plugin.indexOf(k+".")===0))plugin=k;});
        if(!(plugin in spec))return;
        var entry={id:w.id,plugin:plugin,settings:{},geometry:w.geometry};
        Object.keys(spec[plugin]).forEach(function(group){w.currentConfigGroup=[group];var keys=w.configKeys;var values={};spec[plugin][group].forEach(function(key){if(keys.indexOf(key)>=0)values[key]=w.readConfig(key);});entry.settings[group]=values;});
        if(plugin==="org.sheng.linexin.launcher"){w.currentConfigGroup=["General"];entry.launchers=w.readConfig("launchers",[]);}
        c.widgets.push(entry);
    });result.push(c);
});print(JSON.stringify(result));
'''.replace('SPEC', json.dumps(WIDGETS))
    layout = sanitize_layout(json.loads(str(plasma.evaluateScript(script, timeout=15))))
    display_data = json.loads(subprocess.check_output(['kscreen-doctor', '-j'], text=True, timeout=20))
    displays = []
    for output in display_data.get('outputs', []):
        if not output.get('enabled'):
            continue
        mode = next((item for item in output.get('modes', []) if item['id'] == output.get('currentModeId')), {})
        displays.append({'scale': output.get('scale'), 'rotation': output.get('rotation'), 'size': mode.get('size'), 'refreshRate': mode.get('refreshRate')})
    packages = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'] + PACKAGES, text=True, capture_output=True, check=False)
    versions = dict(line.split('\t', 1) for line in packages.stdout.splitlines() if '\t' in line)
    osk = {}
    path = home / '.config/fcitx5-osk/config.toml'
    if path.exists():
        config = tomllib.loads(path.read_text(encoding='utf-8'))
        osk = {key: config[key] for key in OSK_KEYS if key in config}
    profile = {'schemaVersion': 1, 'capturedAtUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
               'platform': {'device': 'sheng', 'architecture': subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip(), 'kernel': subprocess.check_output(['uname', '-r'], text=True).strip(), 'packages': versions},
               'kconfig': read_kconfig(home), 'layout': layout, 'displays': displays, 'screenKeyboard': osk,
               'wallpapers': {'desktopSource': 'device/theme/wallpaper.json', 'lockscreenSource': 'device/theme/lockscreen-wallpaper.json'}}
    validate(profile)
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path, default=pathlib.Path('out/desktop-profile.json'))
    parser.add_argument('--validate', type=pathlib.Path, help='Validate an existing public profile without a desktop or D-Bus')
    args = parser.parse_args()
    if args.validate:
        validate(json.loads(args.validate.read_text(encoding='utf-8')))
        print('Desktop profile schema and publication checks passed')
        return
    profile = export_profile()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'containments': len(profile['layout']), 'applets': sum(len(item['applets']) for item in profile['layout'])}))


if __name__ == '__main__':
    main()
