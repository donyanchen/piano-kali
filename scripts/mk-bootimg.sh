#!/bin/bash
# Turn our own kernel artifacts into an Android-format boot image set.
#
#   mk-bootimg.sh <kernel-artifact-dir> <out-dir> [cmdline]
#
# <kernel-artifact-dir> is what .github/workflows/kernel.yml uploads:
#     Image                 arch/arm64/boot/Image
#     sm8750-piano.dtb      arch/arm64/boot/dts/qcom/sm8750-piano.dtb
#     modules/lib/modules/<ver>/...
#     kernel-release        one line, e.g. 7.3.4-piano
#     config                the .config that produced it
#
# Produces boot.img + vendor_boot.img with header v4 (the format the piano
# bootloader expects, see docs/KERNEL-TRUTH.md §1.2/§1.4). No AVB signing: the
# device is unlocked (verifiedbootstate=orange) and the factory boot chain is
# not re-signed by us.
set -euo pipefail

SRC=${1:?usage: mk-bootimg.sh <kernel-artifact-dir> <out-dir> [cmdline]}
OUT=${2:?}
CMDLINE=${3:-"root=PARTLABEL=linux_rootfs rootwait ro console=tty0 fbcon=map:0 console=ttyMSM0,115200n8"}

KREL=$(tr -d '[:space:]' < "$SRC/kernel-release")
[[ -n $KREL ]] || { echo "no kernel-release in $SRC" >&2; exit 1; }

mkdir -p "$OUT"
IMG="$SRC/Image"
DTB="$SRC/sm8750-piano.dtb"
[[ -f $IMG ]] || { echo "missing $IMG" >&2; exit 1; }
[[ -f $DTB ]] || { echo "missing $DTB" >&2; exit 1; }

# initramfs: prefer what build-kali.sh generated inside the rootfs (it has the
# matching modules and Kali's udev-based PARTLABEL handling), fall back to a
# stock one if the caller passes INITRD.
INITRD=${INITRD:-}
RAMDISK_ARGS=()
if [[ -n $INITRD && -f $INITRD ]]; then
    RAMDISK_ARGS=(--ramdisk "$INITRD")
fi

python3 - "$IMG" > "$OUT/kernel-size.txt" <<'PY'
import os, sys
print(os.path.getsize(sys.argv[1]))
PY

echo "== boot.img (kernel $KREL)"
mkbootimg \
    --header_version 4 \
    --kernel "$IMG" \
    "${RAMDISK_ARGS[@]}" \
    --cmdline "$CMDLINE" \
    --output "$OUT/boot.img"

echo "== vendor_boot.img (dtb $(basename "$DTB"))"
# Empty vendor ramdisk: our modules live in the rootfs, the DT is what the
# bootloader needs from this partition.
EMPTY=$(mktemp -d)
(cd "$EMPTY" && printf '' | cpio -o -H newc 2>/dev/null | gzip -9) > "$OUT/vendor_ramdisk_empty.gz"
mkbootimg \
    --header_version 4 \
    --vendor_boot "$OUT/vendor_boot.img" \
    --dtb "$DTB" \
    --vendor_ramdisk "$OUT/vendor_ramdisk_empty.gz" \
    --vendor_cmdline "androidboot.hardware=qcom androidboot.memcg=1" \
    --pagesize 4096

rm -f "$OUT/vendor_ramdisk_empty.gz"
rmdir "$EMPTY" 2>/dev/null || true

# init_boot on Android 13+ carries the *generic* ramdisk and is concatenated
# with boot.img's ramdisk by the bootloader. We ship our initramfs in boot.img,
# so this one must be a valid but empty image — otherwise Android's /init would
# race ours.
echo "== init_boot.img (empty, valid header v4)"
EMPTY2=$(mktemp -d)
(cd "$EMPTY2" && printf '' | cpio -o -H newc 2>/dev/null | gzip -9) > "$OUT/init_boot_ramdisk.gz"
mkbootimg \
    --header_version 4 \
    --ramdisk "$OUT/init_boot_ramdisk.gz" \
    --output "$OUT/init_boot.img"
rm -f "$OUT/init_boot_ramdisk.gz"
rmdir "$EMPTY2" 2>/dev/null || true

echo "== result"
for f in boot.img init_boot.img vendor_boot.img; do
    printf '%-18s %10s bytes\n' "$f" "$(stat -c %s "$OUT/$f")"
done
unpack_bootimg --boot_img "$OUT/boot.img" 2>/dev/null | sed -n '1,8p' || true