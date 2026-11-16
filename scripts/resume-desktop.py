#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Preserve the existing locked Wayland session and refresh its input panel."""
import json
import os
import pathlib
import pwd
import subprocess
import sys
import time

STATE = pathlib.Path('/run/sheng-desktop-resume.json')


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def capture():
    session = output('loginctl', 'show-seat', 'seat0', '-p', 'ActiveSession', '--value')
    details = output('loginctl', 'show-session', session, '-p', 'Name', '-p', 'Type', '-p', 'Class', '-p', 'User')
    fields = dict(line.split('=', 1) for line in details.splitlines() if '=' in line)
    if fields.get('Name') == 'kali' and fields.get('Type') == 'wayland' and fields.get('Class') == 'user':
        STATE.write_text(json.dumps({'session': session, 'uid': int(fields['User'])}))
        STATE.chmod(0o600)
    else:
        STATE.unlink(missing_ok=True)


def user_restore():
    environment = os.environ.copy()
    environment.update(XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}',
                       DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus',
                       WAYLAND_DISPLAY='wayland-0', QT_QPA_PLATFORM='wayland')
    # KWin has already persisted the user's desired scale. Reload it only after
    # reactivating the original VT; inactive sessions reject output changes.
    config = pathlib.Path.home() / '.config/kwinoutputconfig.json'
    try:
        entries = json.loads(config.read_text())
        for section in entries:
            if section.get('name') == 'outputs':
                for screen in section.get('data', []):
                    if screen.get('connectorName') == 'DSI-1':
                        scale = float(screen['scale'])
                        if 1 <= scale <= 4:
                            subprocess.run(['kscreen-doctor', f'output.DSI-1.scale.{scale:g}'], env=environment, timeout=10, check=False)
    except (OSError, ValueError, KeyError):
        pass
    subprocess.run(['pkill', '-TERM', '-x', 'plasma-keyboard'], check=False)
    for _ in range(15):
        time.sleep(0.2)
        if subprocess.run(['pgrep', '-x', 'plasma-keyboard'], stdout=subprocess.DEVNULL).returncode == 0:
            policy = subprocess.run(['/usr/bin/python3', '/usr/libexec/sheng-keyboard-policy.py', '--apply-once'],
                                    env=environment, timeout=10, capture_output=True, text=True, check=False)
            try:
                physical_keyboard = json.loads(policy.stdout)['physical_keyboard_present']
            except (ValueError, KeyError):
                physical_keyboard = True  # Keep a keyboard hidden if its status cannot be established.
            if not physical_keyboard:
                subprocess.run(['qdbus6', 'org.kde.KWin', '/VirtualKeyboard',
                                'org.kde.kwin.VirtualKeyboard.forceActivate'],
                               env=environment, timeout=10, check=False)
            break
    print('Refreshed the keyboard input panel; desktop applications and lock state were preserved')


def restore():
    if not STATE.exists():
        return
    state = json.loads(STATE.read_text())
    session = state['session']
    if output('loginctl', 'show-session', session, '-p', 'State', '--value') == 'closing':
        return
    active = output('loginctl', 'show-seat', 'seat0', '-p', 'ActiveSession', '--value')
    # Return from a greeter only; never switch away from another user's session.
    if active != session:
        session_class = output('loginctl', 'show-session', active, '-p', 'Class', '--value') if active else ''
        if session_class not in ('', 'greeter'):
            return
        subprocess.run(['loginctl', 'activate', session], check=True)
    owner = pwd.getpwuid(state['uid'])
    subprocess.run(['runuser', '-u', owner.pw_name, '--', '/usr/bin/python3',
                    '/usr/libexec/sheng-desktop-resume.py', 'user'], check=True)


if __name__ == '__main__':
    {'capture': capture, 'restore': restore, 'user': user_restore}[sys.argv[1]]()
