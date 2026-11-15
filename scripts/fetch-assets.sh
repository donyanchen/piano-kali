#!/bin/bash
# Download and verify the pinned xiaomipad-8pro-mainline release assets.
# Everything the Kali image needs from the device port comes from these files:
# the boot image set (kernel + DTB + initramfs), the kernel/device .debs and
# the firmware packages.
set -euo pipefail

PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ASSET_DIR=${ASSET_DIR:-"$PROJECT/.work/assets"}
CONFIG="$PROJECT/configs/piano.json"

REPO=$(python3 -c "import json;print(json.load(open('$CONFIG'))['upstream']['repository'])")
RELEASE=$(python3 -c "import json;print(json.load(open('$CONFIG'))['upstream']['release'])")

mkdir -p "$ASSET_DIR"
cd "$ASSET_DIR"

python3 - "$CONFIG" <<'PY' > assets.list
import json, sys
cfg = json.load(open(sys.argv[1]))
for name, sha in cfg['upstream']['assets'].items():
    print(name, sha)
PY

while read -r name sha; do
    if [[ -f "$name" ]] && echo "$sha  $name" | sha256sum -c --status -; then
        echo "cached $name"
        continue
    fi
    echo "downloading $name"
    url="https://github.com/$REPO/releases/download/$RELEASE/$name"
    curl --fail --location --retry 5 --retry-delay 5 --continue-at - -o "$name" "$url"
    echo "$sha  $name" | sha256sum -c -
done < assets.list

echo "all pinned assets verified in $ASSET_DIR"
