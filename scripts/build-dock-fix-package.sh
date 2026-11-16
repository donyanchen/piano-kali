#!/bin/bash
# Package already-built and verified ARM64 artifacts; no kernel image flashing.
set -euo pipefail
module=$1
auth=$2
source_root=$3
output=$4
[[ $(dpkg --print-architecture) == arm64 ]]
kernel=$(modinfo -F vermagic "$module" | cut -d' ' -f1)
[[ $kernel == 7.3.4-sm8550-00104-g87ac0f2347eb ]]
[[ $(modinfo -F version "$module") == 1.2-shengfix ]]
kernel_package_version=$(dpkg-query -W -f='${Version}' linux-xiaomi-sheng)
work=$(mktemp -d /tmp/sheng-dock-package.XXXXXX)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/DEBIAN" "$work/lib/modules/$kernel/kernel/drivers/hid" \
    "$work/usr/libexec" "$work/etc/systemd/system" "$work/etc/udev/rules.d" \
    "$work/usr/share/doc/sheng-dock-fix" "$output"
python3 - "$module" "$work/lib/modules/$kernel/kernel/drivers/hid/hid-nanosic-wn8030.ko.zst" <<'PY'
from pathlib import Path
from compression import zstd
import sys
source=Path(sys.argv[1]); target=Path(sys.argv[2])
data=source.read_bytes()
if source.suffix=='.zst': data=zstd.decompress(data)
target.write_bytes(zstd.compress(data,level=19))
assert zstd.decompress(target.read_bytes())==data
PY
install -m755 "$auth" "$work/usr/libexec/sheng-devauth"
sed 's@/usr/local/libexec/sheng-devauth@/usr/libexec/sheng-devauth@' \
    "$source_root/device/keyboard-auth/sheng-devauth.service" > "$work/etc/systemd/system/sheng-devauth.service"
install -m644 "$source_root/device/keyboard-auth/80-sheng-devauth.rules" "$work/etc/udev/rules.d/80-sheng-devauth.rules"
install -m644 "$source_root/device/keyboard-driver/0001-fix-auth-and-resume.patch" "$work/usr/share/doc/sheng-dock-fix/driver.patch"
install -m644 "$source_root/device/keyboard-auth/service-fixes.patch" "$work/usr/share/doc/sheng-dock-fix/auth.patch"
dependency_license="$(dirname "$auth")/libs/LICENSE"
if [[ ! -f $dependency_license ]]; then dependency_license=/usr/share/doc/sheng-dock-fix/dependency-license; fi
install -m644 "$dependency_license" "$work/usr/share/doc/sheng-dock-fix/dependency-license"
install -m644 /usr/share/common-licenses/GPL-2 "$work/usr/share/doc/sheng-dock-fix/GPL-2"
cat > "$work/usr/share/doc/sheng-dock-fix/provenance" <<EOF
Kernel: ianchb/sm8550-mainline 87ac0f2347eb433933841e6854950dd90e96e6b2
Kernel ABI: $kernel
Compiler: Debian clang 21.1.8-13 (matching the running kernel)
Auth: ianchb/sheng_devauth bac03b5bcfefa1467ebad490edd910a6cef8a207
Auth archive SHA256: bc48c5263c607ddf798cbc21a2aecde8e72bbbab3843aa662e99668d8722bfb4
Local RPMB callback enabled, as required when no qteesupplicant supplies it.
Driver license: GPL-2.0-only. Auth dependency license: upstream libs/LICENSE.
The patched module replaces the distribution module at its canonical path.
Original copies and prototype files are removed at the user's request.
EOF
cat > "$work/DEBIAN/control" <<EOF
Package: sheng-dock-fix
Version: 1.2-2
Section: kernel
Priority: optional
Architecture: arm64
Maintainer: Sheng Kali builders <noreply@localhost>
Depends: libc6, kmod, systemd, udev, linux-xiaomi-sheng (= $kernel_package_version)
Replaces: linux-xiaomi-sheng (= $kernel_package_version)
Description: WN8030 keyboard authentication and resume fixes for sheng
 Compiled only for $kernel. Owns the canonical patched module.
EOF
printf '%s\n' /etc/systemd/system/sheng-devauth.service /etc/udev/rules.d/80-sheng-devauth.rules > "$work/DEBIAN/conffiles"
cat > "$work/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e
depmod '$kernel'
systemctl daemon-reload
udevadm control --reload-rules || true
systemctl enable sheng-devauth.service
if [ -d /run/systemd/system ] && [ "\$(uname -r)" = '$kernel' ]; then
    systemctl start sheng-devauth.service
fi
EOF
cat > "$work/DEBIAN/prerm" <<'EOF'
#!/bin/sh
if [ "$1" = remove ]; then
    systemctl disable --now sheng-devauth.service || true
fi
exit 0
EOF
cat > "$work/DEBIAN/postrm" <<EOF
#!/bin/sh
depmod '$kernel' || true
systemctl daemon-reload || true
udevadm control --reload-rules || true
exit 0
EOF
chmod 755 "$work/DEBIAN/postinst" "$work/DEBIAN/prerm" "$work/DEBIAN/postrm"
(cd "$work" && find . -type f ! -path './DEBIAN/*' -print0 | sort -z | xargs -0 md5sum | sed 's@  \./@  @' > DEBIAN/md5sums)
dpkg-deb --build --root-owner-group "$work" "$output/sheng-dock-fix_1.2-2_arm64.deb"
