#!/usr/bin/env python3
"""Verify native ARM64 Kali and the running KDE session over the USB network."""
import argparse
import datetime
import json
import os
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import paramiko
except ImportError:
    raise SystemExit("Install paramiko on the host: python -m pip install paramiko")

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="192.168.77.1")
parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("out/device-verification.json"))
args = parser.parse_args()
project = pathlib.Path(__file__).resolve().parents[1]
known_hosts = project / ".work/device-known-hosts"
known_hosts.parent.mkdir(parents=True, exist_ok=True)
known_hosts.touch(exist_ok=True)
client = paramiko.SSHClient()
client.load_system_host_keys()
client.load_host_keys(str(known_hosts))
# Establish trust through ssh/known_hosts first; never silently trust a new host.
client.set_missing_host_key_policy(paramiko.RejectPolicy())
client.connect(args.host, username="kali", password=os.environ.get("KALI_PASSWORD", "kali"),
               timeout=15, auth_timeout=15, look_for_keys=False, allow_agent=False)
checks = {
    "tablet_model": ("tr -d '\\000' < /proc/device-tree/model", "Xiaomi Pad 6S Pro 12.4"),
    "kernel_architecture": ("uname -m", "aarch64"),
    "userland_architecture": ("dpkg --print-architecture", "arm64"),
    "distribution": (". /etc/os-release; printf '%s' \"$ID\"", "kali"),
    "display_manager": ("systemctl is-active sddm", "active"),
    "plasma_shell": ("pgrep -x plasmashell", None),
    "wayland_compositor": ("pgrep -x kwin_wayland", None),
    "touch_service": ("systemctl is-active xiaomi-sheng-thp", "active"),
    "touch_input": ("grep 'Name=\"NVTCapacitiveTouchScreen\"' /proc/bus/input/devices", None),
}
result = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "checks": {}}
passed = True
try:
    for name, (command, expected) in checks.items():
        _, stdout, stderr = client.exec_command(command, timeout=30)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        status = stdout.channel.recv_exit_status()
        success = status == 0 and (bool(output) if expected is None else output == expected)
        passed = passed and success
        result["checks"][name] = {"passed": success, "output": output, "error": error}
    for name, command in {
        "kernel": "uname -r",
        "boot_id": "cat /proc/sys/kernel/random/boot_id",
        "desktop_packages": "dpkg-query -W kali-desktop-kde plasma-workspace plasma-keyboard xiaomi-sheng-thp libssc",
        "filesystem": "df -h /",
        "time": "date -Is",
        "drm_connectors": "for f in /sys/class/drm/*/status; do echo \"$f: $(cat \"$f\")\"; done",
        "network": "nmcli -t device status",
        "input_devices": "cat /proc/bus/input/devices",
        "boot_errors": "journalctl -b -p err --no-pager -n 40",
    }.items():
        _, stdout, stderr = client.exec_command(command, timeout=30)
        result[name] = stdout.read().decode().strip()
        result[name + "_stderr"] = stderr.read().decode().strip()
finally:
    client.close()
result["device_boot_verified"] = passed
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if passed else 1)
