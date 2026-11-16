#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A supervised AP on a second virtual interface, sharing wlan0 Internet."""
import configparser
import os
import pathlib
import signal
import subprocess
import time

RUNTIME = pathlib.Path('/run/sheng-hotspot')
INTERFACE = 'sheng-ap'
stopping = False


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def stop_handler(*_):
    global stopping
    stopping = True


def main():
    if b'xiaomi,sheng' not in pathlib.Path('/proc/device-tree/compatible').read_bytes():
        raise SystemExit('This service is for Xiaomi sheng')
    settings = configparser.ConfigParser(interpolation=None)
    settings.read('/etc/sheng-hotspot/settings.ini')
    ssid, password = settings['hotspot']['ssid'], settings['hotspot']['password']
    if not 1 <= len(ssid.encode()) <= 32 or any(c in ssid for c in '\r\n'):
        raise SystemExit('Invalid SSID')
    if not 8 <= len(password) <= 63 or any(ord(c) < 32 or ord(c) > 126 for c in password):
        raise SystemExit('Invalid WPA2 passphrase')
    RUNTIME.mkdir(mode=0o755, exist_ok=True)
    children = []
    for item in (signal.SIGTERM, signal.SIGINT):
        signal.signal(item, stop_handler)
    try:
        for _ in range(30):
            if pathlib.Path('/sys/class/net/wlan0').exists():
                break
            time.sleep(1)
        else:
            raise RuntimeError('wlan0 did not appear')
        if pathlib.Path('/sys/class/net/' + INTERFACE).exists():
            raise RuntimeError('Reserved hotspot interface already exists')
        run('iw', 'dev', 'wlan0', 'interface', 'add', INTERFACE, 'type', '__ap')
        run('udevadm', 'settle', '--timeout=5')
        run('nmcli', 'device', 'set', INTERFACE, 'managed', 'no')
        run('ip', 'link', 'set', INTERFACE, 'down')
        run('iw', 'dev', INTERFACE, 'set', 'type', '__ap')
        address = bytearray.fromhex(pathlib.Path('/sys/class/net/wlan0/address').read_text().strip().replace(':', ''))
        address[0] = (address[0] | 2) ^ 4
        run('ip', 'link', 'set', INTERFACE, 'address', ':'.join(f'{n:02x}' for n in address))
        hostapd = RUNTIME / 'hostapd.conf'
        hostapd.write_text(f'''interface={INTERFACE}
driver=nl80211
ssid={ssid}
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
beacon_int=100
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase={password}
ctrl_interface=/run/sheng-hotspot/control
''')
        hostapd.chmod(0o600)
        children.append(subprocess.Popen(['hostapd', str(hostapd)]))
        for _ in range(60):
            if stopping or children[0].poll() is not None:
                raise RuntimeError('Access point failed to start')
            status = subprocess.run(['hostapd_cli', '-p', str(RUNTIME/'control'), '-i', INTERFACE, 'status'],
                                    capture_output=True, text=True)
            if 'state=ENABLED' in status.stdout:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError('Access point startup timeout')
        run('ip', 'address', 'add', '10.42.0.1/24', 'dev', INTERFACE)
        run('sysctl', '-q', '-w', 'net.ipv4.ip_forward=1')
        subprocess.run(['nft', 'delete', 'table', 'ip', 'sheng_hotspot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run('nft', '-f', '-', input='''table ip sheng_hotspot {
  chain postrouting {
    type nat hook postrouting priority srcnat; policy accept;
    ip saddr 10.42.0.0/24 oifname "wlan0" masquerade
  }
  chain forward {
    type filter hook forward priority filter; policy accept;
    iifname "sheng-ap" oifname "wlan0" accept
    iifname "wlan0" oifname "sheng-ap" ct state established,related accept
  }
}
''', text=True)
        dns = RUNTIME / 'dnsmasq.conf'
        dns.write_text('''interface=sheng-ap
bind-interfaces
listen-address=10.42.0.1
dhcp-range=10.42.0.20,10.42.0.200,255.255.255.0,12h
dhcp-option=option:router,10.42.0.1
dhcp-option=option:dns-server,10.42.0.1
dhcp-leasefile=/run/sheng-hotspot/leases
pid-file=/run/sheng-hotspot/dnsmasq.pid
domain-needed
bogus-priv
no-hosts
''')
        children.append(subprocess.Popen(['dnsmasq', '--keep-in-foreground', '--conf-file=' + str(dns)]))
        time.sleep(0.5)
        if any(child.poll() is not None for child in children):
            raise RuntimeError('Hotspot DHCP service failed')
        (RUNTIME / 'ready').write_text(ssid + '\n10.42.0.1\n')
        print('Secured hotspot ready; upstream wlan0 remains managed by NetworkManager', flush=True)
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('A hotspot worker exited')
            time.sleep(0.5)
    finally:
        (RUNTIME / 'ready').unlink(missing_ok=True)
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        subprocess.run(['nft','delete','table','ip','sheng_hotspot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['iw','dev',INTERFACE,'del'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
