#!/bin/bash
# Install the Fcitx5 on-screen keyboard (with the Sheng tablet UI patch) and the
# Metasequoia (水杉) input engine into the Kali root filesystem.
#
# Runs on the ARM64 builder, outside the chroot: the OSK is a Rust/CMake project
# and building it inside a qemu-free chroot would drag a full toolchain into the
# image. Binaries are linked against Kali's newer glibc, so the host-built
# outputs are ABI-compatible.
#
# Usage: build-osk.sh <rootfs>
set -euo pipefail

PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ROOTFS=${1:?rootfs path required}
WORK=${WORK:-"$PROJECT/.work/osk"}
OSK_COMMIT=76a33b65b1c72519788c09cfb9f94c1df0f61949
OSK_SHA=8501c5fdc1c3ff7e8197c53437351284bd85335b4f69aacaddf7181157298b91
UI_PATCH_SHA=9697e5d2b0450d4b80a13d1aadaba7e7e171c9038c4d750bcf28880edc2e598a
MSIME_URL=https://github.com/metasequoiaime/msime/releases/download/linux-v0.16.1/msime-linux_0.16.1_arm64.deb
MSIME_SHA=1f2542ed775e9bbf74b86aa0a901ce02af8f3f3652ef8aee54392b2b62fa853c

step() { echo; echo "===== OSK: $* ====="; }
mkdir -p "$WORK"

step "host build dependencies"
sudo apt-get install -y --no-install-recommends \
    build-essential pkg-config ninja-build git \
    libwayland-dev wayland-protocols libegl1-mesa-dev libgles2-mesa-dev \
    libxkbcommon-dev libssl-dev libfontconfig1-dev libdbus-1-dev libglib2.0-dev

step "rust toolchain (edition 2024 needs rust >= 1.85)"
if ! command -v cargo >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
fi
. "$HOME/.cargo/env"
cargo --version

step "cmake >= 4.1"
if ! cmake --version 2>/dev/null | head -n1 | grep -qE 'version (4\.[1-9]|[5-9])'; then
    python3 -m pip install --user --break-system-packages 'cmake>=4.1' >/dev/null
fi
export PATH="$HOME/.local/bin:$PATH"
cmake --version | head -n1

step "fetch pinned fcitx5-osk source"
cd "$WORK"
if [[ ! -d src ]]; then
    curl --fail --location --retry 3 -o osk.tgz \
        "https://codeload.github.com/fortime/fcitx5-osk/tar.gz/$OSK_COMMIT"
    echo "$OSK_SHA  osk.tgz" | sha256sum -c -
    mkdir src && tar xzf osk.tgz -C src --strip-components=1
    ( cd src && git init -q && git apply --check "$PROJECT/vendor/osk/hyperos-ui.patch" \
        && git apply "$PROJECT/vendor/osk/hyperos-ui.patch" )
    for f in "$PROJECT"/vendor/osk/ui/*.toml; do
        base=$(basename "$f")
        case "$base" in
            *-keys.toml) dir=key_sets ;;
            *-landscape.toml|*-portrait.toml) dir=layouts ;;
            *) dir=themes ;;
        esac
        mkdir -p "src/pkg/share/fcitx5-osk/$dir"
        cp "$f" "src/pkg/share/fcitx5-osk/$dir/"
    done
fi

step "build"
cmake -S src -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr \
    -DCMAKE_INSTALL_LIBDIR=lib/aarch64-linux-gnu
cmake --build build --parallel "$(nproc)"

step "stage into the Kali root filesystem"
rm -rf stage && mkdir stage
DESTDIR="$PWD/stage" cmake --install build --component Fcitx5Osk
DESTDIR="$PWD/stage" cmake --install build --component Fcitx5OskKwinLauncher
cp -a stage/usr/. "$ROOTFS/usr/"

step "input engine and desktop dependencies inside the image"
cp "$PROJECT/.work/assets/msime-linux_0.16.1_arm64.deb" "$ROOTFS/tmp/msime.deb"
chroot "$ROOTFS" apt-get install -y --no-install-recommends /tmp/msime.deb || {
    echo "WARN: msime package install failed; the OSK will use fcitx5 defaults"
}
rm -f "$ROOTFS/tmp/msime.deb"

step "select the OSK as KWin input method"
launcher=/usr/share/applications/fyi.fortime.Fcitx5Osk.KwinLauncher.desktop
if [[ -f "$ROOTFS$launcher" ]]; then
    install -d "$ROOTFS/home/kali/.config"
    if [[ -f "$ROOTFS/home/kali/.config/kwinrc" ]]; then
        sed -i '/^InputMethod=/d' "$ROOTFS/home/kali/.config/kwinrc"
    fi
    python3 - "$ROOTFS/home/kali/.config/kwinrc" "$launcher" <<'PY'
import sys
path, launcher = sys.argv[1:3]
lines = open(path).read().splitlines() if __import__('os').path.exists(path) else []
out, in_section, done = [], False, False
for line in lines:
    if line.startswith('['):
        if in_section and not done:
            out.append(f'InputMethod={launcher}')
            done = True
        in_section = line.strip() == '[Wayland]'
    out.append(line)
if in_section and not done:
    out.append(f'InputMethod={launcher}')
    done = True
if not any(line.strip() == '[Wayland]' for line in out):
    out += ['[Wayland]', f'InputMethod={launcher}', 'VirtualKeyboardEnabled=true']
elif not done:
    out.insert(out.index('[Wayland]') + 1, f'InputMethod={launcher}')
open(path, 'w').write('\n'.join(out) + '\n')
PY
    chroot "$ROOTFS" chown -R kali:kali /home/kali/.config
else
    echo "WARN: OSK launcher desktop file missing; KWin input method unchanged"
fi

step "done"
ls -l "$ROOTFS/usr/bin/fcitx5-osk" 2>/dev/null || true
