#!/bin/bash
# Push a kernel artifact to the running tablet WITHOUT touching the Kali image.
#
#   SUDO_PASS=kali scripts/push-kernel-to-device.sh kali@192.168.0.13 <artifact-dir> [--flash]
#
# <artifact-dir> is the bundle from .github/workflows/kernel.yml:
#     Image  sm8750-piano.dtb  modules/lib/modules/<krel>/  kernel-release  config
#
# What it does:
#   1. install the modules into /lib/modules/<krel> on the device
#   2. build a fresh initramfs there (installs kmod + initramfs-tools if missing)
#   3. assemble boot.img / init_boot.img / vendor_boot.img here (mkbootimg lives
#      in the sandbox, not on the tablet)
#   4. with --flash: back up the current partitions, then dd the new ones
#
# Without --flash the images are left in /tmp/piano-boot on the device.
# The Kali root filesystem is never touched.
set -euo pipefail

HOST=${1:?usage: push-kernel-to-device.sh <user@host> <artifact-dir> [--flash]}
ART=${2:?artifact dir required}
FLASH=${3:-}
SUDO_PASS=${SUDO_PASS:-}

PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

# sudo on the device: passwordless if SUDO_PASS is empty, otherwise feed it once
# per remote command (each ssh invocation is its own process).
rsh() {
    if [[ -n $SUDO_PASS ]]; then
        ssh $SSH_OPTS "$HOST" "printf '%s\n' '$SUDO_PASS' | sudo -S -p '' bash -c '$1'"
    else
        ssh $SSH_OPTS "$HOST" "sudo -n bash -c '$1'"
    fi
}

KREL=$(tr -d '[:space:]' < "$ART/kernel-release")
[[ -n $KREL ]] || { echo "missing kernel-release in $ART" >&2; exit 1; }
echo "kernel release: $KREL"

echo "== 1/4 install modules into /lib/modules/$KREL"
tar -C "$ART/modules" -czf /tmp/modules-$KREL.tgz "lib/modules/$KREL"
scp $SSH_OPTS "/tmp/modules-$KREL.tgz" "$HOST:/tmp/" >/dev/null
rsh "tar -C / -xzf /tmp/modules-$KREL.tgz && depmod -a $KREL"
rm -f "/tmp/modules-$KREL.tgz"

echo "== 2/4 build initramfs on the device"
ssh $SSH_OPTS "$HOST" "command -v mkinitramfs >/dev/null" || \
    rsh "apt-get install -y --no-install-recommends kmod initramfs-tools"
rsh "mkinitramfs -o /tmp/initrd-$KREL $KREL"
scp $SSH_OPTS "$HOST:/tmp/initrd-$KREL" "/tmp/initrd-$KREL" >/dev/null

echo "== 3/4 assemble the boot image set"
OUT=$(mktemp -d)
INITRD="/tmp/initrd-$KREL" bash "$PROJECT/scripts/mk-bootimg.sh" "$ART" "$OUT"
ssh $SSH_OPTS "$HOST" "mkdir -p /tmp/piano-boot"
scp $SSH_OPTS "$OUT"/boot.img "$OUT"/init_boot.img "$OUT"/vendor_boot.img "$HOST:/tmp/piano-boot/" >/dev/null
rm -rf "$OUT"

if [[ $FLASH != --flash ]]; then
    cat <<EOF

Images are on the device under /tmp/piano-boot/. To write them by hand:

  SLOT=\$(grep -o 'slot_suffix *= *_[ab]' /proc/bootconfig | grep -o '_[ab]')
  sudo dd if=/tmp/piano-boot/boot.img        of=/dev/block/by-name/boot\$SLOT        bs=4M conv=fsync
  sudo dd if=/tmp/piano-boot/init_boot.img   of=/dev/block/by-name/init_boot\$SLOT   bs=4M conv=fsync
  sudo dd if=/tmp/piano-boot/vendor_boot.img of=/dev/block/by-name/vendor_boot\$SLOT bs=4M conv=fsync
  sudo reboot
EOF
    exit 0
fi

echo "== 4/4 back up and write the partitions"
rsh 'set -e
SLOT=$(grep -o "slot_suffix *= *_[ab]" /proc/bootconfig 2>/dev/null | grep -o "_[ab]" || true)
[ -n "$SLOT" ] || SLOT=_b
BK=/var/backups/piano-boot-$(date +%Y%m%d-%H%M)
mkdir -p "$BK"
for p in boot init_boot vendor_boot; do
    echo "backup $p$SLOT -> $BK"
    dd if="/dev/block/by-name/$p$SLOT" of="$BK/$p$SLOT.img" bs=4M status=none
done
for p in boot init_boot vendor_boot; do
    echo "write  $p$SLOT"
    dd if="/tmp/piano-boot/$p.img" of="/dev/block/by-name/$p$SLOT" bs=4M conv=fsync status=none
done
sync
echo "backups: $BK"'

echo
echo "Reboot to try it: sudo reboot"
echo "Recovery: fastboot flash boot <backup>/boot$SLOT.img (and init_boot / vendor_boot)"