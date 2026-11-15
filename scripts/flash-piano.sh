#!/bin/bash
# Flash Kali onto a Xiaomi Pad 8 Pro (piano) from the bootloader.
#   ./flash-piano.sh --serial <SERIAL> --dir . --yes [--slot a|b|current]
#
# Writes the A/B slot the device is currently booting by default. The upstream
# xiaomipad-8pro-mainline notes assume slot A; units updated to newer HyperOS
# builds may be running from slot B, so the slot is detected and printed instead
# of hard-coded. `userdata` receives the Kali root filesystem; `ipados` (UniXNU),
# `vbmeta`, `dtbo`, `persist`, modem and calibration partitions are untouched.
set -euo pipefail

SERIAL=''
DIR='.'
SLOT='current'
YES=0
while (($#)); do
    case "$1" in
        --serial) SERIAL=$2; shift 2 ;;
        --dir) DIR=$2; shift 2 ;;
        --slot) SLOT=$2; shift 2 ;;
        --yes) YES=1; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

[[ -n "$SERIAL" ]] || { echo 'usage: flash-piano.sh --serial <SERIAL> [--dir DIR] [--slot current|a|b] --yes' >&2; exit 2; }
cd "$DIR"
for f in boot.img init_boot.img vendor_boot.img root.sparse.img; do
    [[ -f "$f" ]] || { echo "missing $f in $PWD" >&2; exit 1; }
done

product=$(fastboot -s "$SERIAL" getvar product 2>&1 | sed -n 's/^product: //p' | head -n 1)
[[ "$product" == piano ]] || { echo "refusing: product is '$product', expected 'piano'" >&2; exit 1; }
current=$(fastboot -s "$SERIAL" getvar current-slot 2>&1 | sed -n 's/^current-slot: //p' | head -n 1)
[[ "$SLOT" == current ]] && SLOT=$current
case "$SLOT" in a|b) ;; *) echo "cannot determine slot (got '$SLOT')" >&2; exit 1 ;; esac
echo "product: $product   current slot: $current   writing slot: $SLOT"

if (( ! YES )); then
    echo "This writes boot_$SLOT/init_boot_$SLOT/vendor_boot_$SLOT and ERASES the Android userdata partition."
    echo "Keep a copy of the current boot set first: fastboot getvar current-slot; adb pull before leaving Android."
    read -r -p "Type ERASE to continue: " answer
    [[ "$answer" == ERASE ]] || { echo 'aborted'; exit 1; }
fi

ipados=$(fastboot -s "$SERIAL" getvar partition-size:ipados 2>&1 | sed -n 's/^partition-size:ipados: //p' | head -n 1)
echo "ipados partition size: ${ipados:-unknown} (never written by this script)"

fastboot -s "$SERIAL" --slot "$SLOT" flash boot boot.img
fastboot -s "$SERIAL" --slot "$SLOT" flash init_boot init_boot.img
fastboot -s "$SERIAL" --slot "$SLOT" flash vendor_boot vendor_boot.img
fastboot -s "$SERIAL" erase userdata
fastboot -s "$SERIAL" flash userdata root.sparse.img
fastboot -s "$SERIAL" reboot
echo "Kali is booting from slot $SLOT. First boot grows the root filesystem to the full userdata partition."
echo "UniXNU stays in the ipados partition; manage its payload from Kali with: sudo piano-ipados status"
