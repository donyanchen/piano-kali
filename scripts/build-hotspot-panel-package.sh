#!/bin/bash
set -euo pipefail
binary=$1
project=$2
source_root=$project/device/hotspot-panel
output=$3
[[ $(dpkg --print-architecture) == arm64 ]]
version=$(dpkg-query -W -f='${Version}' plasma-nm)
[[ $version == 4:6.7.4-2+b1 ]]
target=/usr/lib/aarch64-linux-gnu/qt6/plugins/plasma/applets/org.kde.plasma.networkmanagement.so
work=$(mktemp -d /tmp/piano-hotspot-panel.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/DEBIAN" "$work$(dirname "$target")" "$work/usr/share/doc/piano-hotspot-panel" "$output"
install -m644 "$binary" "$work$target"
cp "$source_root/pianohotspotcontroller.cpp" "$source_root/pianohotspotcontroller.h" \
    "$work/usr/share/doc/piano-hotspot-panel/"
install -m644 "$source_root/applet.patch" "$work/usr/share/doc/piano-hotspot-panel/applet.patch"
install -m644 /usr/share/common-licenses/GPL-3 "$work/usr/share/doc/piano-hotspot-panel/GPL-3"
install -m644 /usr/share/common-licenses/LGPL-2.1 "$work/usr/share/doc/piano-hotspot-panel/LGPL-2.1"
# Package repository sources, never files copied from a running user's system.
install -Dm755 "$project/scripts/setup-hotspot.py" "$work/usr/libexec/piano-hotspot/setup.py"
install -Dm755 "$project/scripts/piano-hotspot.py" "$work/usr/libexec/piano-hotspot/hotspot.py"
install -Dm644 "$project/device/piano-hotspot.service" "$work/etc/systemd/system/piano-hotspot.service"
install -Dm644 "$project/device/piano-hotspot-setup.service" "$work/etc/systemd/system/piano-hotspot-setup.service"
install -Dm644 "$project/device/50-piano-hotspot.rules" "$work/etc/polkit-1/rules.d/50-piano-hotspot.rules"
install -Dm644 "$project/device/81-piano-hotspot.rules" "$work/etc/udev/rules.d/81-piano-hotspot.rules"
install -Dm755 "$project/device/piano-hotspot-sleep" "$work/usr/lib/systemd/system-sleep/50-piano-hotspot"
printf '%s\n' /etc/systemd/system/piano-hotspot.service /etc/systemd/system/piano-hotspot-setup.service \
    /etc/polkit-1/rules.d/50-piano-hotspot.rules /etc/udev/rules.d/81-piano-hotspot.rules > "$work/DEBIAN/conffiles"
cat > "$work/usr/share/doc/piano-hotspot-panel/provenance" <<'EOF'
Plasma NM 6.7.4 source: KDE/plasma-nm b6c03fe24b30d2a963a41dd83784e36086d7257e
Only the network applet is rebuilt. The stock network-management libraries are retained.
On Xiaomi piano the toolbar hotspot button controls piano-hotspot.service.
Readiness is monitored through /run/piano-hotspot/ready using inotify.
The patched applet owns its canonical path; original copies were removed at the user's request.
EOF
cat > "$work/DEBIAN/control" <<EOF
Package: piano-hotspot-panel
Version: 1.0-2
Section: kde
Priority: optional
Architecture: arm64
Maintainer: Piano Kali builders <noreply@localhost>
Depends: plasma-nm (= $version), libstdc++6, libc6, python3, network-manager, hostapd, dnsmasq-base, nftables, iw, iproute2, systemd
Replaces: plasma-nm (= $version)
Description: Native Plasma network toolbar control for the piano concurrent AP
 Uses the existing AP service while preserving the upstream Wi-Fi connection.
EOF
cat > "$work/DEBIAN/preinst" <<EOF
#!/bin/sh
set -e
owner=\$(dpkg-divert --listpackage '$target')
if [ "\$owner" = piano-hotspot-panel ]; then
    dpkg-divert --package piano-hotspot-panel --remove --no-rename --divert '$target.distrib' '$target'
elif [ -n "\$owner" ]; then
    echo 'Unexpected third-party diversion for the network applet' >&2
    exit 1
fi
EOF
cat > "$work/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
systemctl daemon-reload
udevadm control --reload-rules || true
EOF
chmod 755 "$work/DEBIAN/preinst" "$work/DEBIAN/postinst"
(cd "$work" && find . -type f ! -path './DEBIAN/*' -print0 | sort -z | xargs -0 md5sum | sed 's@  \./@  @' > DEBIAN/md5sums)
dpkg-deb --build --root-owner-group "$work" "$output/piano-hotspot-panel_1.0-2_arm64.deb"
