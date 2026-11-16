#!/bin/bash
# Sync the Kali userland layer from LuKeyC-NetSEC/sheng-kali-linux.
#
# This repo is a 1:1 port of that project: device/, scripts/, docs/, tests/ and
# the build/check workflows all come from there, with the device identifiers
# retargeted to piano. "Iterating on Kali" therefore means: pull his commits and
# replay our own deltas, not hand-editing files here.
#
#   scripts/sync-sheng-base.sh                 # clone the pinned commit into vendor/
#   scripts/sync-sheng-base.sh --check         # how far behind are we?
#   scripts/sync-sheng-base.sh --update [REF]  # copy upstream changes in (REF defaults to main)
#
# Files listed in .sheng-sync-exclude are never touched: they are the piano
# kernel, the piano build/flash chain and the docs that describe this device.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOCK="$ROOT/vendor/sheng-kali.lock.json"
VENDOR="$ROOT/vendor/sheng-kali"
EXCLUDE="$ROOT/.sheng-sync-exclude"

read_lock() {
    python3 - "$LOCK" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(d['upstream'], d['commit'])
PY
}

read -r URL COMMIT < <(read_lock)

clone_pinned() {
    if [ -d "$VENDOR/.git" ] && [ "$(git -C "$VENDOR" rev-parse HEAD)" = "$COMMIT" ]; then
        echo "vendor/sheng-kali already at $COMMIT"
        return
    fi
    rm -rf "$VENDOR"
    git clone --filter=blob:none --no-checkout "$URL" "$VENDOR"
    git -C "$VENDOR" checkout --detach "$COMMIT"
    echo "vendor/sheng-kali at $COMMIT"
}

case "${1:-}" in
--check)
    tmp=$(mktemp -d)
    git clone --quiet --filter=blob:none --no-checkout "$URL" "$tmp"
    latest=$(git -C "$tmp" rev-parse origin/main)
    behind=$(git -C "$tmp" rev-list --count "$COMMIT..$latest")
    echo "pinned:  $COMMIT"
    echo "upstream: $latest"
    echo "behind:  $behind commits"
    git -C "$tmp" log --oneline "$COMMIT..$latest" | head -20
    rm -rf "$tmp"
    ;;
--update)
    REF=${2:-main}
    tmp=$(mktemp -d)
    git clone --quiet --filter=blob:none "$URL" "$tmp"
    git -C "$tmp" checkout --quiet "$REF"
    NEW=$(git -C "$tmp" rev-parse HEAD)
    echo "syncing $URL@$REF ($NEW)"

    python3 - "$tmp" "$ROOT" "$EXCLUDE" <<'PY'
import os, re, shutil, sys

src, dst, exclude_file = sys.argv[1], sys.argv[2], sys.argv[3]
excluded = []
for line in open(exclude_file):
    line = line.strip()
    if line and not line.startswith('#'):
        excluded.append(line.rstrip('/'))

REWRITES = [
    ('sheng-kali-linux', 'piano-kali'),
    ('xiaomi-sheng', 'xiaomi-piano'),
    ('sheng', 'piano'),
    ('Sheng', 'Piano'),
    ('SHENG', 'PIANO'),
    ('24018RPACC', '25091RP04C'),
    ('6S Pro', '8 Pro'),
    ('Adreno 740', 'Adreno 830'),
]
KEEP_LINE = ('LuKeyC-NetSEC', 'THIRD_PARTY.md')

def is_excluded(rel):
    return any(rel == e or rel.startswith(e + '/') for e in excluded)

copied = updated = 0
for root, dirs, files in os.walk(src):
    if '.git' in root.split(os.sep):
        continue
    for name in files:
        full = os.path.join(root, name)
        rel = os.path.relpath(full, src)
        if is_excluded(rel) or name.endswith('.png') or name.endswith('.jpg'):
            continue
        target = os.path.join(dst, rel.replace('sheng', 'piano'))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            text = open(full, encoding='utf-8').read()
        except (UnicodeDecodeError, IsADirectoryError):
            shutil.copy2(full, target)
            copied += 1
            continue
        out = []
        for line in text.split('\n'):
            if any(k in line for k in KEEP_LINE):
                out.append(line)
                continue
            for a, b in REWRITES:
                line = line.replace(a, b)
            out.append(line)
        new = '\n'.join(out)
        if os.path.exists(target) and open(target, encoding='utf-8').read() == new:
            continue
        open(target, 'w', encoding='utf-8').write(new)
        updated += 1
print('files copied: %d, updated: %d' % (copied, updated))
PY

    python3 - "$LOCK" "$NEW" <<'PY'
import json, sys, datetime
p, commit = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d['commit'] = commit
d['fetched'] = datetime.date.today().isoformat()
json.dump(d, open(p, 'w'), indent=2)
print('lock updated to', commit)
PY
    rm -rf "$tmp"
    echo "review with: git status / git diff, then commit"
    ;;
*)
    clone_pinned
    ;;
esac