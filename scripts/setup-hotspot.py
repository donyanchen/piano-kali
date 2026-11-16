#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
import configparser
import grp
import os
import pathlib
import secrets

directory = pathlib.Path('/etc/sheng-hotspot')
directory.mkdir(mode=0o750, exist_ok=True)
group = grp.getgrnam('netdev').gr_gid
os.chown(directory, 0, group)
directory.chmod(0o750)
settings = directory / 'settings.ini'
if not settings.exists():
    fd = os.open(settings, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(fd, 'w') as target:
        target.write('[hotspot]\nssid=Sheng-Kali\npassword=' + secrets.token_urlsafe(12) + '\n')
config = configparser.ConfigParser(interpolation=None)
config.read(settings)
ssid, password = config['hotspot']['ssid'], config['hotspot']['password']
if not 1 <= len(ssid.encode()) <= 32 or any(c in ssid for c in '\r\n'):
    raise SystemExit('Invalid hotspot SSID')
if not 8 <= len(password) <= 63 or any(ord(c) < 32 or ord(c) > 126 for c in password):
    raise SystemExit('Invalid hotspot password')
access = directory / 'access.txt'
access.write_text(f'SSID: {ssid}\nPassword: {password}\nGateway: 10.42.0.1\nSecurity: WPA2-CCMP\n')
for path in (settings, access):
    path.chmod(0o640)
    os.chown(path, 0, group)
