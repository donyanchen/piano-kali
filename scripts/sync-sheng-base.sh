#!/bin/bash
# Fetch the pinned sheng-kali-linux tree that supplies the userland components.
#
# We do not vendor the whole repository: it carries images and author-local
# captures. This clones the exact commit into vendor/sheng-kali so the build can
# copy device/*, scripts/* and docs/* from a verifiable source.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOCK="$ROOT/vendor/sheng-kali.lock.json"
DEST="$ROOT/vendor/sheng-kali"

read -r URL COMMIT < <(python3 - "$LOCK" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(d['upstream'], d['commit'])
PY
)

if [ -d "$DEST/.git" ] && [ "$(git -C "$DEST" rev-parse HEAD)" = "$COMMIT" ]; then
    echo "vendor/sheng-kali already at $COMMIT"
    exit 0
fi

rm -rf "$DEST"
git clone --filter=blob:none --no-checkout "$URL" "$DEST"
git -C "$DEST" checkout --detach "$COMMIT"
echo "vendor/sheng-kali at $COMMIT"
