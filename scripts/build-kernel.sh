#!/bin/bash
# Build the piano kernel ourselves instead of consuming prebuilt debs.
#
# The tree is mainline v7.4-rc2 plus the SM8750/piano device layer (~469 commits,
# ~16k lines: DSI/DPU, touch, UFS, charging, ADSP/audio, WLAN, PMIC, ...).
# We keep that as the *base* and our own patches on top in kernel/patches/.
#
#   sudo ./scripts/build-kernel.sh            # all cores, install deb
#   sudo ./scripts/build-kernel.sh --prepare  # only clone + apply patches
set -euo pipefail

BASE_URL=https://github.com/yzddmr6/linux-sm8750-piano
BASE_COMMIT=29eda7337ed1af7316ea93ea73465b10f8ebeaff
UPSTREAM_TAG=v7.4-rc2
WORK=${WORK:-/var/lib/piano-kernel}
SRC=$WORK/src
PATCHES=$(cd "$(dirname "$0")/.." && pwd)/kernel/patches
JOBS=${JOBS:-$(nproc)}

prepare() {
    mkdir -p "$WORK"
    if [[ ! -d $SRC/.git ]]; then
        git clone --filter=blob:none --branch sm8750/v7.4-dev "$BASE_URL" "$SRC"
    fi
    git -C "$SRC" fetch --all --tags --quiet
    git -C "$SRC" checkout --force "$BASE_COMMIT"

    # our patch queue, applied in name order
    if [[ -d $PATCHES ]]; then
        for p in "$PATCHES"/*.patch; do
            [[ -e $p ]] || continue
            if git -C "$SRC" apply --check "$p" 2>/dev/null; then
                git -C "$SRC" apply "$p"
                echo "applied $(basename "$p")"
            else
                echo "skipped $(basename "$p") (already applied or conflicting)"
            fi
        done
    fi
}

build() {
    cd "$SRC"
    # Same config fragments the release uses, in order.
    local cfg=arch/arm64/configs/piano-diagnostic.config
    make O="$WORK/out" ARCH=arm64 LLVM=1 "$cfg"
    for frag in arch/arm64/configs/sm8750-netfilter.config \
                arch/arm64/configs/sm8750-peripherals.config \
                arch/arm64/configs/sm8750-waydroid.config \
                arch/arm64/configs/sm8750-snap.config \
                arch/arm64/configs/sm8750-virt.config \
                arch/arm64/configs/piano-diagnostic.config \
                arch/arm64/configs/piano-desktop-diag.config \
                arch/arm64/configs/piano-persistent.config \
                arch/arm64/configs/piano-release.config; do
        scripts/kconfig/merge_config.sh -O "$WORK/out" -m "$WORK/out/.config" "$frag" >/dev/null
    done
    make O="$WORK/out" ARCH=arm64 LLVM=1 olddefconfig
    make O="$WORK/out" ARCH=arm64 LLVM=1 -j"$JOBS" Image modules dtbs
    echo "kernel: $WORK/out/arch/arm64/boot/Image"
    echo "dtbs:   $(ls "$WORK"/out/arch/arm64/boot/dts/qcom/*piano*.dtb 2>/dev/null | tr '\n' ' ')"
    echo "Now run tools/build-kernel-deb.py from the upstream tools tree to get a deb,"
    echo "or use scripts/pack-boot.sh to rebuild boot.img/vendor_boot.img directly."
}

prepare
[[ ${1:-} == --prepare ]] && exit 0
build
