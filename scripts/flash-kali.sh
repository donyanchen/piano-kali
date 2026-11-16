#!/bin/bash
set -euo pipefail
if [[ "${1:-}" != --erase-userdata ]]; then
    echo 'Usage: SERIAL=<device> bash scripts/flash-kali.sh --erase-userdata' >&2
    exit 1
fi
PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT_DIR=${OUT_DIR:-"$PROJECT/out"}
FASTBOOT=${FASTBOOT:-fastboot}
python3 "$PROJECT/scripts/validate-images.py" "$OUT_DIR"
mapfile -t devices < <("$FASTBOOT" devices | awk '$2 == "fastboot" {print $1}')
if [[ -z "${SERIAL:-}" ]]; then
    (( ${#devices[@]} == 1 )) || { echo 'Connect exactly one tablet, or set SERIAL.' >&2; exit 1; }
    SERIAL=${devices[0]}
fi
printf '%s\n' "${devices[@]}" | grep -Fxq "$SERIAL" || { echo 'Selected tablet is not connected.' >&2; exit 1; }
getvar() {
    local response
    response=$("$FASTBOOT" -s "$SERIAL" getvar "$1" 2>&1)
    printf '%s\n' "$response" | sed -n "s/^$1: *//p" | head -n 1 | tr -d '\r'
}
[[ "$(getvar product)" == sheng ]] || { echo 'Wrong tablet model.' >&2; exit 1; }
[[ "$(getvar unlocked)" == yes ]] || { echo 'Bootloader is locked.' >&2; exit 1; }
userdata_size=$(getvar partition-size:userdata)
boot_size=$(getvar partition-size:boot_b)
previous_slot=$(getvar current-slot)
python3 - "$OUT_DIR" "$userdata_size" "$boot_size" "$SERIAL" "$previous_slot" <<'PY'
import datetime, json, pathlib, sys
out = pathlib.Path(sys.argv[1])
manifest = json.loads((out / 'manifest.json').read_text())
assert (manifest['device'], manifest['architecture'], manifest['distribution'], manifest['desktop'], manifest['root_partition']) == ('sheng', 'arm64', 'kali', 'kde', 'userdata')
assert manifest['host_image_validation'] == 'passed'
assert int(sys.argv[2], 16) >= manifest['expanded_rootfs_bytes']
assert int(sys.argv[3], 16) >= manifest['files']['boot-kali-sheng.img']['bytes']
record = dict(serial=sys.argv[4], product='sheng', previous_slot=sys.argv[5],
              userdata_bytes=int(sys.argv[2], 16),
              started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              completed=False, device_boot_verified=False)
(out / 'flash-record.json').write_text(json.dumps(record, indent=2) + '\n')
PY
run() {
    "$FASTBOOT" -s "$SERIAL" "$@" 2>&1 | tee -a "$OUT_DIR/flash-log.txt"
}
echo 'Installing native Kali ARM64 KDE: all Android user data will be erased.'
run -S 256M flash userdata "$OUT_DIR/rootfs-kali-arm64-kde-sheng.img"
run flash boot_b "$OUT_DIR/boot-kali-sheng.img"
run erase dtbo_b
run set_active b
run reboot
python3 - "$OUT_DIR/flash-record.json" <<'PY'
import datetime, json, pathlib, sys
path = pathlib.Path(sys.argv[1])
record = json.loads(path.read_text())
record.update(completed=True, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
path.write_text(json.dumps(record, indent=2) + '\n')
PY
echo FLASH_COMPLETE_BOOT_UNVERIFIED
