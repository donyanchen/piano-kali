#!/bin/bash
# Build a reversible device-specific replacement for KDE's PCI-only GPU plugin.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=${1:-"$project/out/packages"}
[[ $(dpkg --print-architecture) == arm64 ]] || { echo 'Build on ARM64 Linux.' >&2; exit 1; }
work=$(mktemp -d /tmp/sheng-gpu-build.XXXXXX)
cmake -S "$project/device/gpu-monitor" -B "$work/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$work/build" -j 4
multiarch=$(dpkg-architecture -qDEB_HOST_MULTIARCH)
module=/usr/lib/$multiarch/qt6/plugins/ksystemstats/ksystemstats_plugin_gpu.so
backup=/usr/lib/sheng-gpu-monitor/original/ksystemstats_plugin_gpu.so
package="$work/package"
install -Dm 0644 "$work/build/libksystemstats_plugin_gpu.so" "$package$module"
install -Dm 0755 "$project/scripts/collect-gpu.py" "$package/usr/libexec/sheng-gpu-monitor/collector.py"
install -Dm 0644 "$project/device/gpu-monitor/sheng-gpu-monitor.service" "$package/usr/lib/systemd/system/sheng-gpu-monitor.service"
install -Dm 0644 "$project/LICENSE" "$package/usr/share/doc/sheng-gpu-monitor/copyright"
install -Dm 0644 "$project/device/gpu-monitor/README.md" "$package/usr/share/doc/sheng-gpu-monitor/README.md"
mkdir -p "$package/DEBIAN" "$package/usr/lib/sheng-gpu-monitor/original" "$output"
cat > "$package/DEBIAN/control" <<'EOF'
Package: sheng-gpu-monitor
Version: 1.0.0
Section: utils
Priority: optional
Architecture: arm64
Maintainer: Sheng Kali builders <noreply@localhost>
Depends: ksystemstats, libksysguardsystemstats2, libkf6coreaddons6, libqt6core6t64, libc6, libstdc++6, python3
Description: Adreno 740 statistics for KDE on Xiaomi sheng
 Uses real MSM DRM engine counters and global GEM resident-memory statistics.
 The GPU shares system RAM and has no dedicated VRAM. Original KDE GPU plugin
 is preserved using a package diversion and restored on removal.
EOF
cat > "$package/DEBIAN/preinst" <<EOF
#!/bin/sh
set -e
mkdir -p /usr/lib/sheng-gpu-monitor/original
dpkg-divert --package sheng-gpu-monitor --add --rename --divert '$backup' '$module'
EOF
cat > "$package/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
systemctl daemon-reload || true
systemctl enable sheng-gpu-monitor.service || true
if [ -d /run/systemd/system ]; then
    systemctl restart sheng-gpu-monitor.service || true
fi
EOF
cat > "$package/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = remove ] && [ -d /run/systemd/system ]; then
    systemctl stop sheng-gpu-monitor.service || true
    systemctl disable sheng-gpu-monitor.service || true
fi
EOF
cat > "$package/DEBIAN/postrm" <<EOF
#!/bin/sh
set -e
case "\$1" in
  remove|purge)
    dpkg-divert --package sheng-gpu-monitor --remove --rename --divert '$backup' '$module'
    systemctl daemon-reload || true
    ;;
esac
EOF
chmod 0755 "$package/DEBIAN/preinst" "$package/DEBIAN/postinst" "$package/DEBIAN/prerm" "$package/DEBIAN/postrm"
dpkg-deb --build --root-owner-group "$package" "$output/sheng-gpu-monitor_1.0.0_arm64.deb"
