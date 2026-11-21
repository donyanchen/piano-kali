#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""给 Bluetooth 控制器一个本地管理地址。

piano 的出厂 BT MAC 只存在 Android 的 persist 分区，Kali 读不到；而
bluetooth.service 的 ExecStartPre=/usr/libexec/piano/bluetooth-address 必须
拿到 /etc/piano/bluetooth-address，否则服务直接 exit 1（start-limit-hit），
表现就是「蓝牙完全不能用」。

这个脚本按下面的顺序取一个稳定种子，派生一个 locally-administered 单播地址：
  1. /proc/device-tree/serial-number        （真机序列号，最理想）
  2. /proc/cmdline 里的 androidboot.serialno
  3. /sys/class/android_usb/android0/iSerial
  4. /etc/machine-id                         （兜底，同一 rootfs 镜像内稳定）

已经有 /etc/piano/bluetooth-address 且格式合法时不覆盖——保留用户手工钉住的 MAC。
"""
import hashlib
import os
import pathlib
import re
import subprocess
import sys

TARGET = pathlib.Path("/etc/piano/bluetooth-address")
MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def read(path, binary=False):
    try:
        data = pathlib.Path(path).read_bytes()
    except OSError:
        return ""
    if binary:
        data = data.split(b"\0", 1)[0]
    return data.decode("utf-8", "replace").strip()


def serial_seed():
    for path in ("/proc/device-tree/serial-number", "/sys/firmware/devicetree/base/serial-number"):
        value = read(path, binary=True)
        if value:
            return value
    try:
        cmdline = pathlib.Path("/proc/cmdline").read_text(errors="replace")
    except OSError:
        cmdline = ""
    match = re.search(r"androidboot\.serialno=(\S+)", cmdline)
    if match:
        return match.group(1)
    value = read("/sys/class/android_usb/android0/iSerial")
    if value:
        return value
    value = read("/etc/machine-id")
    if value:
        return value
    return None


def derive(seed):
    digest = hashlib.sha256(("piano-bt:" + seed).encode()).digest()
    octets = bytearray(digest[:6])
    octets[0] = (octets[0] & 0xFC) | 0x02  # locally administered, unicast
    return ":".join(f"{b:02X}" for b in octets)


def main():
    if TARGET.exists():
        current = read(str(TARGET)).lower()
        if MAC_RE.match(current):
            return 0
    seed = serial_seed()
    if not seed:
        print("piano-bluetooth-address: no stable seed, leaving address unset", file=sys.stderr)
        return 1
    address = derive(seed)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(address + "\n")
    os.chmod(TARGET, 0o644)
    print(f"piano-bluetooth-address: {address} (seed {seed[:8]}…)")
    if subprocess.run(["systemctl", "is-active", "--quiet", "bluetooth"]).returncode == 0:
        subprocess.run(["systemctl", "restart", "bluetooth"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
