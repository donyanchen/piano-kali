#!/bin/bash
# Collect the installable artifacts: compressed root filesystem, boot image set,
# checksums and the install notes.
set -euo pipefail
PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUT="$PROJECT/out"
REL="$OUT/release"
mkdir -p "$REL"

echo "compressing root filesystem"
zstd -T0 -6 -f "$OUT/root.sparse.img" -o "$REL/root.sparse.img.zst"

cp "$OUT/boot.img" "$OUT/init_boot.img" "$OUT/vendor_boot.img" "$REL/"
cp "$OUT/manifest.json" "$OUT/validation.txt" "$OUT/packages.tsv" "$OUT/piano-debs.log" "$REL/" 2>/dev/null || true
cp "$OUT"/osk.log "$OUT"/mesa.log "$OUT"/kali-compat.txt "$REL/" 2>/dev/null || true
cp "$PROJECT/scripts/flash-piano.sh" "$REL/"
cp "$PROJECT/docs/INSTALL.md" "$REL/INSTALL.md"

KERNEL=$(python3 -c "import json;print(json.load(open('$PROJECT/configs/piano.json'))['upstream']['kernel_release'])")
RUN=${GITHUB_RUN_NUMBER:-local}
COMMIT=${GITHUB_SHA:-$(git -C "$PROJECT" rev-parse --short HEAD 2>/dev/null || echo unknown)}

cat > "$REL/RELEASE-NOTES.md" <<EOF
# Kali for Xiaomi Pad 8 Pro (piano) — build $RUN

Kali Linux ARM64 (KDE Plasma, Wayland) for the Xiaomi Pad 8 Pro \`25091RP04C\`,
running the mainline piano kernel \`$KERNEL\` and device packages from
[yzddmr6/xiaomipad-8pro-mainline](https://github.com/yzddmr6/xiaomipad-8pro-mainline).

- Build commit: \`$COMMIT\`
- Root filesystem: \`root.sparse.img.zst\` (ext4, grows to the full \`userdata\` partition on first boot)
- Boot set: \`boot.img\` (cmdline \`root=PARTLABEL=userdata\`), \`init_boot.img\`, \`vendor_boot.img\`
- Other partitions (\`ipados\`, \`vbmeta\`, \`dtbo\`, \`persist\`) are not touched; UniXNU can still be run with \`fastboot boot\`.

**This erases Android userdata.** Read \`INSTALL.md\`.

\`\`\`
$(cd "$REL" && sha256sum *.img *.zst)
\`\`\`
EOF

cd "$REL"
sha256sum ./*.img ./*.zst ./*.json ./*.txt ./*.tsv ./INSTALL.md > SHA256SUMS
ls -la
cat SHA256SUMS
