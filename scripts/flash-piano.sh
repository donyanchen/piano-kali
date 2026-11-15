#!/bin/bash
# Flash Kali onto a Xiaomi Pad 8 Pro (piano) from the bootloader.
#   ./flash-piano.sh --serial <SERIAL> --dir . --yes
# Boots the A slot with the piano kernel and writes the Kali root filesystem to
# the existing `userdata` partition. Nothing else is written: `ipados` (UniXNU),
# `vbmeta`, `dtbo`, `persist`, modem and calibration partitions stay untouched.
set -euo pipefail

SERIAL=''
DIR='.'
YES=0
while (($#)); do
    case "$1" in
        --serial) SERIAL=$2; shift 2 ;;
        --dir) DIR=$2; shift 2 ;;
        --yes) YES=1; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[[ -n "$SERIAL" ]] || { echo 'usage: flash-piano.sh --serial <SERIAL> [--dir DIR] --yes' >&2; exit 2; }
cd "$DIR"
for f in boot.img init_boot.img vendor_boot.img root.sparse.img; do
    [[ -f "$f" ]] || { echo "missing $f in $PWD" >&2; exit 1; }
done

product=$(fastboot -s "$SERIAL" getvar product 2>&1 | sed -n 's/^product: //p' | head -n 1)
[[ "$product" == piano ]] || { echo "refusing: product is '$product', expected 'piano'" >&2; exit 1; }
if (( ! YES )); then
    echo 'This writes boot/init_boot/vendor_boot and ERASES the Android userdata partition.'
    read -r -p "Type ERASE to continue: " answer
    [[ "$answer" == ERASE ]] || { echo 'aborted'; exit 1; }
fi

fastboot -s "$SERIAL" flash boot boot.img
fastboot -s "$SERIAL" flash init_boot init_boot.img
fastboot -s "$SERIAL" flash vendor_boot vendor_boot.img
fastboot -s "$SERIAL" erase userdata
fastboot -s "$SERIAL" flash userdata root.sparse.img
fastboot -s "$SERIAL" reboot
echo 'Kali is booting. First boot takes about a minute; the root filesystem grows to the full partition.'
