#!/bin/bash
# Run in an ARM64 Kali chroot; build the pinned production library and CLI.
set -euo pipefail
source_dir=$1
output_dir=$2
[[ $(dpkg --print-architecture) == arm64 ]]
work_dir=$(mktemp -d /tmp/sheng-libssc.XXXXXX)
# The optional test server uses git submodules. Only the library and CLI are
# needed by the touchscreen service; their source is unchanged.
sed -i "/^subdir('mocking')$/d; /^subdir('tests')$/d" "$source_dir/meson.build"
meson setup "$work_dir/build" "$source_dir" --prefix=/usr \
    --libdir=lib/aarch64-linux-gnu --buildtype=release
meson compile -C "$work_dir/build" -j 4
DESTDIR="$work_dir/package" meson install -C "$work_dir/build"
mkdir -p "$work_dir/package/DEBIAN" "$work_dir/package/usr/share/doc/libssc" "$output_dir"
install -m 0644 "$source_dir/LICENSE" "$work_dir/package/usr/share/doc/libssc/copyright"
cat > "$work_dir/package/DEBIAN/control" <<'EOF'
Package: libssc
Version: 0.4.4-1
Section: libs
Priority: optional
Architecture: arm64
Maintainer: Sheng Kali builders <noreply@localhost>
Depends: libc6, libglib2.0-0t64, libprotobuf-c1, libqmi-glib5
Description: Qualcomm Sensor Core library for the sheng touch processor
 Built from Dylan Van Assche's libssc 0.4.4, pinned in configs/sources.json.
EOF
dpkg-deb --build --root-owner-group "$work_dir/package" "$output_dir/libssc_0.4.4-1_arm64.deb"
