#!/usr/bin/env python3
"""Rewrite the command line inside an Android boot image (header v3/v4).

Only the `cmdline` field of the boot header changes; kernel, DTB, ramdisk and
bootconfig stay byte-identical. `mkbootimg` is not needed and the image keeps
the layout the vendor ABL already accepts. AVB verification is disabled by the
unlocked bootloader, so the stale header signature is not consulted.
"""
import hashlib
import struct
import sys


def main() -> int:
    if len(sys.argv) != 4:
        print('usage: patch-boot-cmdline.py <boot.img> <out.img> <cmdline>', file=sys.stderr)
        return 2
    src, dst, new_cmd = sys.argv[1:]
    data = bytearray(open(src, 'rb').read())
    if data[:8] != b'ANDROID!':
        raise SystemExit('not an Android boot image')
    header_size = struct.unpack('<I', data[0x14:0x18])[0]
    version = struct.unpack('<I', data[0x28:0x2c])[0]
    if version < 3:
        raise SystemExit(f'unsupported boot header version {version}')
    if header_size < 0x2c + 4096:
        raise SystemExit(f'unexpected header size {header_size}')
    field = 0x2c
    old = bytes(data[field:field + 4096]).split(b'\0')[0]
    encoded = new_cmd.encode()
    if len(encoded) > 4095:
        raise SystemExit('command line too long')
    data[field:field + 4096] = encoded + b'\0' * (4096 - len(encoded))
    open(dst, 'wb').write(data)
    print(f'header version : {version}')
    print(f'old cmdline    : {old.decode()}')
    print(f'new cmdline    : {new_cmd}')
    print(f'sha256         : {hashlib.sha256(data).hexdigest()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
