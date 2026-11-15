#!/bin/bash
# Build Mesa 26.2.6 with the xiaomipad-8pro-mainline Adreno 830 patches and
# install it into the Kali root filesystem under /opt/piano/mesa-26.2.6.
#
# Kali's own Mesa stays installed as a fallback; the image selects the patched
# stack through /etc/ld.so.conf.d and LIBGL_DRIVERS_PATH / VK_ICD_FILENAMES.
set -euo pipefail

PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ROOTFS=${1:?rootfs path required}
WORK=${WORK:-"$PROJECT/.work/mesa"}
PREFIX=/opt/piano/mesa-26.2.6
ARCHIVE_SHA=b9436b3e1a8be76fbd4823dc884f90596ab7c6ac5e1867a305e66ffccfb31a92
PATCHES="piano-fixes.patch turnip-a8xx-runtime-unroll.patch turnip-ssbo-wide-reads.patch
turnip-a8xx-word-reuse.patch freedreno-thread-safe-tex-seqno.patch freedreno-explicit-sync.patch
freedreno-a830v1.patch freedreno-syncobj-fd.patch ir3-relative-const-alias.patch
ir3-float-helper-order.patch ir3-float-saturation.patch"

step() { echo; echo "===== MESA: $* ====="; }
mkdir -p "$WORK"
cd "$WORK"

step "host build dependencies"
sudo apt-get install -y --no-install-recommends \
    meson ninja-build pkg-config python3-mako python3-yaml python3-packaging \
    bison flex libdrm-dev libwayland-dev wayland-protocols libwayland-egl-backend-dev \
    libx11-dev libx11-xcb-dev libxcb1-dev libxcb-dri3-dev libxcb-present-dev \
    libxcb-shm0-dev libxcb-randr0-dev libxshmfence-dev libexpat1-dev libzstd-dev \
    libglvnd-dev libllvm-dev llvm-dev libclc-dev zlib1g-dev

step "fetch mesa 26.2.6"
if [[ ! -d src ]]; then
    curl --fail --location --retry 3 -o mesa.tar.xz \
        "https://archive.mesa3d.org/mesa-26.2.6.tar.xz"
    echo "$ARCHIVE_SHA  mesa.tar.xz" | sha256sum -c -
    mkdir src && tar xf mesa.tar.xz -C src --strip-components=1
    ( cd src && git init -q )
    for patch in $PATCHES; do
        ( cd src && git apply --check "$PROJECT/vendor/mesa/$patch" && git apply "$PROJECT/vendor/mesa/$patch" )
    done
fi

step "configure"
if [[ ! -d build ]]; then
    meson setup build src \
        --prefix="$PREFIX" \
        --libdir=lib/aarch64-linux-gnu \
        --buildtype=release \
        -Dplatforms=wayland,x11 \
        -Dgallium-drivers=freedreno,llvmpipe \
        -Dvulkan-drivers=freedreno \
        -Dglx=dri \
        -Degl=enabled -Dgles2=enabled \
        -Dllvm=enabled \
        -Dvideo-codecs=
fi

step "build (this is the long step)"
ninja -C build -j "$(nproc)"

step "install into the image"
rm -rf stage && mkdir stage
DESTDIR="$PWD/stage" ninja -C build install
install -d "$ROOTFS$PREFIX"
cp -a "stage$PREFIX/." "$ROOTFS$PREFIX/"

step "select the patched stack"
install -Dm 0644 /dev/stdin "$ROOTFS/etc/ld.so.conf.d/90-piano-mesa.conf" <<EOF
$PREFIX/lib/aarch64-linux-gnu
EOF
cat >> "$ROOTFS/etc/environment" <<EOF
LIBGL_DRIVERS_PATH=$PREFIX/lib/aarch64-linux-gnu/dri
GBM_BACKENDS_PATH=$PREFIX/lib/aarch64-linux-gnu/gbm
VK_ICD_FILENAMES=$PREFIX/share/vulkan/icd.d/freedreno_icd.aarch64.json
MESA_LOADER_DRIVER_OVERRIDE=msm
EOF
chroot "$ROOTFS" ldconfig || true

step "done"
ls "$ROOTFS$PREFIX/lib/aarch64-linux-gnu/dri" 2>/dev/null | head -5
