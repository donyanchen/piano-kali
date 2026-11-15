#!/usr/bin/env python3
"""Apply the whole sheng desktop to this piano install in one pass.

Runs on the device as the desktop user (needs a live Plasma session):

    python3 scripts/apply-sheng-desktop.py --theme-dir vendor/theme

Steps: install the bundled plasmoids (Redmi.Clock, org.sheng.panel-style),
copy the exported kconfig whitelist, create the missing top-bar applets, apply
the Panel Colorizer style from desktop-profile.json and fix the clock.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys

HOME = pathlib.Path.home()
PLASMOIDS = HOME / '.local/share/plasma/plasmoids'
FK = 'kwriteconfig6'


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def k(file, group, key, value):
    sh(FK, '--file', file, '--group', group, '--key', key, str(value))


def plasma(script):
    out = sh('qdbus6', 'org.kde.plasmashell', '/PlasmaShell',
             'org.kde.PlasmaShell.evaluateScript', script)
    return (out.stdout or '') + (out.stderr or '')


def install_plasmoids(theme):
    PLASMOIDS.mkdir(parents=True, exist_ok=True)
    for name in ('Redmi.Clock', 'panel-style'):
        src = theme / name
        if not src.is_dir():
            print('missing asset', src)
            continue
        dst = PLASMOIDS / name
        if name == 'panel-style':
            dst = PLASMOIDS / 'org.sheng.panel-style'
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print('installed', dst.name)


def apply_kconfig(profile):
    kc = profile['kconfig']
    for file, groups in kc.items():
        if file not in ('kdeglobals', 'kcminputrc', 'plasmarc', 'kwinrc',
                        'kscreenlockerrc', 'powerdevilrc'):
            continue
        for group, keys in groups.items():
            for key, value in keys.items():
                if file == 'kwinrc' and key in ('InputMethod',):
                    continue          # our keyboard stack differs
                k(file, group, key, value)
    print('kconfig applied')


def colorizer_style(profile, location):
    for item in profile.get('layout', []):
        if item.get('kind') != 'panel' or item.get('position') != location:
            continue
        for applet in item.get('applets', []):
            if applet.get('plugin') == 'luisbocanegra.panel.colorizer':
                return applet.get('settings', {}).get('General', {})
    return {}


def ensure_applets(profile):
    desired = {
        'top': ['org.kde.plasma.kickoff', 'org.kde.plasma.windowlist',
                'org.kde.plasma.appmenu', 'org.kde.plasma.panelspacer',
                'org.kde.plasma.panelspacer', 'org.kde.plasma.systemtray',
                'org.kde.plasma.battery', 'luisbocanegra.panel.colorizer',
                'org.kontrol.center', 'org.sheng.panel-style'],
        'bottom': ['luisbocanegra.panel.colorizer', 'org.sheng.linexin.launcher'],
    }
    for location, plugins in desired.items():
        for plugin in plugins:
            script = (
                'var ps = panels();'
                f'var p = ps.filter(function(x){{return x.location === "{location}"}})[0];'
                'if (!p) { print("no panel"); } else {'
                f'  var has = p.widgets().some(function(w){{return w.type.indexOf("{plugin}") === 0}});'
                f'  if (!has) {{ var w = p.addWidget("{plugin}"); if (w) w.currentConfigGroup = ["General"]; print("{plugin} " + (w ? "added" : "failed")); }}'
                '}'
            )
            for line in plasma(script).splitlines():
                if 'added' in line or 'failed' in line or 'no panel' in line:
                    print(' ', line.strip())


def apply_colorizer(profile):
    for location in ('top', 'bottom'):
        style = colorizer_style(profile, location)
        if not style:
            continue
        payload = json.dumps(style, separators=(',', ':'))
        script = (
            'var ps = panels();'
            f'var p = ps.filter(function(x){{return x.location === "{location}"}})[0];'
            'if (p) { var ws = p.widgets().filter(function(w){return w.type.indexOf("colorizer") >= 0});'
            '  ws.forEach(function(w){ w.currentConfigGroup = ["General"];'
            f'    w.writeConfig("isEnabled", "true"); w.writeConfig("hideWidget", "true");'
            f'    w.writeConfig("globalSettings", {json.dumps(payload)});'
            '  }); print("colorizer ' + location + ' " + ws.length); }'
        )
        print(' ', plasma(script).strip())


def fix_clock():
    script = (
        'var d = desktops()[0];'
        'd.widgets().forEach(function(w){'
        '  if (w.type.indexOf("Redmi.Clock") >= 0) {'
        '    w.currentConfigGroup = ["General"];'
        '    w.writeConfig("colorHex", "#ffffff");'
        '    w.writeConfig("boldfonts", "false");'
        '  }});'
        'print("clock ok")'
    )
    print(' ', plasma(script).strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--theme-dir', type=pathlib.Path,
                        default=pathlib.Path('vendor/theme'))
    args = parser.parse_args()
    theme = args.theme_dir.resolve()
    profile = json.loads((theme / 'desktop-profile.json').read_text())
    install_plasmoids(theme)
    apply_kconfig(profile)
    ensure_applets(profile)
    apply_colorizer(profile)
    fix_clock()
    sh('qdbus6', 'org.kde.KWin', '/KWin', 'reconfigure')
    print('done')


if __name__ == '__main__':
    sys.exit(main())
