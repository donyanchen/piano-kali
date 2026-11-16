#!/usr/bin/env python3
"""Check Android boot and sparse rootfs metadata before permitting a flash."""
import argparse
import hashlib
import json
import pathlib
import struct

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=pathlib.Path)
parser.add_argument("--write-manifest", action="store_true")
args = parser.parse_args()
directory = args.directory.resolve()
boot = directory / "boot-kali-sheng.img"
rootfs = directory / "rootfs-kali-arm64-kde-sheng.img"
with boot.open("rb") as stream:
    header = stream.read(1632)
if header[:8] != b"ANDROID!":
    raise SystemExit("Invalid Android boot image")
kernel_size, _, ramdisk_size, _, _, _, _, page_size, version = struct.unpack_from("<9I", header, 8)
cmdline = (header[64:576].split(b"\0")[0] + header[608:1632].split(b"\0")[0]).decode()
if version != 0 or page_size != 4096 or ramdisk_size != 0 or kernel_size < 1024 * 1024:
    raise SystemExit("Unexpected sheng boot image geometry")
if cmdline.split() != ["root=PARTLABEL=userdata"]:
    raise SystemExit(f"Unexpected root partition in boot image: {cmdline}")
with rootfs.open("rb") as stream:
    data = stream.read(28)
    magic, major, minor, file_header_size, chunk_header_size, block_size, blocks, chunks, _ = struct.unpack("<I4H4I", data)
    if magic != 0xED26FF3A or major != 1 or file_header_size != 28 or chunk_header_size != 12:
        raise SystemExit("Invalid Android sparse rootfs image")
    if block_size != 4096 or not blocks or not chunks:
        raise SystemExit("Invalid sparse geometry")
    expanded_blocks = 0
    superblock_bytes = None
    for _ in range(chunks):
        chunk_type, _, count, total = struct.unpack("<2H2I", stream.read(12))
        payload = total - chunk_header_size
        if chunk_type == 0xCAC1:
            if payload != count * block_size:
                raise SystemExit("Invalid sparse RAW chunk")
            if expanded_blocks == 0:
                prefix = stream.read(min(payload, 2048))
                superblock_bytes = prefix
                stream.seek(payload - len(prefix), 1)
            else:
                stream.seek(payload, 1)
        elif chunk_type == 0xCAC2 and payload == 4:
            stream.seek(4, 1)
        elif chunk_type == 0xCAC3 and payload == 0:
            pass
        elif chunk_type == 0xCAC4 and payload == 4 and count == 0:
            stream.seek(4, 1)
        else:
            raise SystemExit("Unknown or malformed sparse chunk")
        expanded_blocks += count
    if expanded_blocks != blocks or stream.tell() != rootfs.stat().st_size:
        raise SystemExit("Truncated or inconsistent sparse image")
if not superblock_bytes or superblock_bytes[1080:1082] != b"\x53\xef":
    raise SystemExit("Rootfs does not contain an ext4 superblock")
packages = (directory / "packages.tsv").read_text()
for package in ("kali-desktop-kde", "plasma-workspace", "sddm", "linux-xiaomi-sheng", "xiaomi-sheng-thp", "libssc"):
    if not any(line.startswith(package + "\t") or line.startswith(package + ":arm64\t") for line in packages.splitlines()):
        raise SystemExit(f"Missing target package: {package}")
files = {}
for path in (boot, rootfs):
    with path.open("rb") as stream:
        digest_state = hashlib.sha256()
        while chunk := stream.read(1024 * 1024):
            digest_state.update(chunk)
        digest = digest_state.hexdigest()
    files[path.name] = {"bytes": path.stat().st_size, "sha256": digest}
manifest = {"device": "sheng", "architecture": "arm64", "distribution": "kali",
            "desktop": "kde", "root_partition": "userdata", "boot_cmdline": cmdline,
            "expanded_rootfs_bytes": blocks * block_size, "files": files,
            "host_image_validation": "passed", "device_boot_verified": False}
if args.write_manifest:
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
else:
    expected = json.loads((directory / "manifest.json").read_text())
    if expected["files"] != files or expected["expanded_rootfs_bytes"] != blocks * block_size:
        raise SystemExit("Image contents differ from the manifest")
print(json.dumps(manifest, indent=2))
