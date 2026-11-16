#!/bin/bash
# P0 evidence extraction: unpack the stock piano images and dump every DTB.
#
# Input  : the factory B-slot images pulled from the tablet
#          (boot_b / init_boot_b / vendor_boot_b / dtbo_b) plus the live DT dump.
# Output : $WORK/{boot,init_boot,vendor_boot,vb-dtbs,dtbo,live.dts,real.dts,stock-config.txt}
#
#   sudo ./scripts/p0-unpack.sh /path/to/pad8pro  [workdir]
#
# Needs: python3 avbtool unpack_bootimg dtc lz4 cpio. Nothing is written back.
set -euo pipefail

SRC=${1:?usage: p0-unpack.sh <dir with *_b.img> [workdir]}
WORK=${2:-/var/minis/shared/piano/p0}
mkdir -p "$WORK"/{boot,init_boot,vendor_boot,vb-dtbs,dtbo}

echo "== sha256 of inputs"
( cd "$SRC" && sha256sum boot_b.img init_boot_b.img vendor_boot_b.img dtbo_b.img ) | tee "$WORK/SHA256SUMS.inputs"

echo "== avb footers"
for f in boot_b.img init_boot_b.img vendor_boot_b.img vbmeta_b.img; do
    echo "--- $f"
    avbtool info_image --image "$SRC/$f" 2>&1 | sed -n '1,12p'
done || true

echo "== boot / init_boot / vendor_boot"
unpack_bootimg --boot_img "$SRC/boot_b.img"       --out "$WORK/boot"       | tee "$WORK/boot/header.txt"
unpack_bootimg --boot_img "$SRC/init_boot_b.img"  --out "$WORK/init_boot"  | tee "$WORK/init_boot/header.txt"
unpack_bootimg --boot_img "$SRC/vendor_boot_b.img" --out "$WORK/vendor_boot" | tee "$WORK/vendor_boot/header.txt"

echo "== kernel version string + embedded config"
strings -n 8 "$WORK/boot/kernel" | grep -m1 '^Linux version'
python3 - "$WORK/boot/kernel" "$WORK/stock-config.txt" <<'PY'
import gzip, io, sys
d = open(sys.argv[1], 'rb').read()
i = d.find(b'IKCFG_ST')
assert i > 0, 'no IKCONFIG blob'
t = gzip.GzipFile(fileobj=io.BytesIO(d[i + 8:])).read()
open(sys.argv[2], 'wb').write(t)
print('config bytes', len(t))
PY

echo "== vendor_boot contains N concatenated base DTBs"
python3 - "$WORK/vendor_boot/dtb" "$WORK/vb-dtbs" <<'PY'
import struct, sys, os
d = open(sys.argv[1], 'rb').read()
out, n, off = sys.argv[2], 0, 0
while off + 8 <= len(d):
    if d[off:off+4] != b'\xd0\x0d\xfe\xed':
        off += 1
        continue
    sz = struct.unpack('>I', d[off+4:off+8])[0]
    open(os.path.join(out, 'dtb%d.dtb' % n), 'wb').write(d[off:off+sz])
    print('dtb%d  offset=%d size=%d' % (n, off, sz))
    n += 1
    off += sz
PY

echo "== dtbo: big-endian dt_table_header, 1 entry"
python3 - "$SRC/dtbo_b.img" "$WORK/dtbo/piano_entry.dtb" <<'PY'
import struct, sys
d = open(sys.argv[1], 'rb').read()
magic, total, hsz, esz, ecnt, eoff, psz, ver = struct.unpack('>8I', d[:32])
assert magic == 0xd7b7ab1e, hex(magic)
sz, off, did, rev = struct.unpack('>4I', d[eoff:eoff+16])
print('total=%d entries=%d entry_size=%d entry: size=%d off=%d id=%#x' % (total, ecnt, esz, sz, off, did))
open(sys.argv[2], 'wb').write(d[off:off+sz])
PY

echo "== decompile"
for f in "$WORK"/vb-dtbs/*.dtb "$WORK"/dtbo/*.dtb; do
    dtc -I dtb -O dts -o "${f%.dtb}.dts" "$f" 2>/dev/null || true
done
for f in "${LIVE_DTB:-}" "${REAL_DTB:-}"; do
    [ -n "$f" ] && dtc -I dtb -O dts -o "$WORK/$(basename "${f%.dtb}").dts" "$f" 2>/dev/null || true
done

echo "== inventory"
python3 "$(dirname "$0")/dt-inventory.py" "$WORK/real.dts" --stats
echo "done -> $WORK"