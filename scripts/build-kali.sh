#!/bin/bash
# Build a Kali Linux ARM64 (KDE Plasma) root filesystem for the Xiaomi Pad 8 Pro
# (piano, SM8750P), using the kernel, firmware and device packages released by
# the xiaomipad-8pro-mainline project.
#
# The device port is not modified here: this script only installs its released
# binaries into a Kali userland and rewrites the boot image command line so the
# root filesystem lives on the existing `userdata` partition (Kali-only device,
# Android is intentionally discarded, the `ipados` partition used by UniXNU is
# never touched).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export LC_ALL=C.UTF-8 LANG=C.UTF-8

PROJECT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG="$PROJECT/configs/piano.json"
BUILD_DIR=${BUILD_DIR:-"$PROJECT/.work/build"}
ASSET_DIR=${ASSET_DIR:-"$PROJECT/.work/assets"}
OUT_DIR=${OUT_DIR:-"$PROJECT/out"}
IMAGE_SIZE=${IMAGE_SIZE:-20G}
KALI_MIRROR=${KALI_MIRROR:-https://kali.download/kali}
KALI_PASSWORD=${KALI_PASSWORD:-kali}
ROOTFS="$BUILD_DIR/rootfs"
ROOT_IMG="$BUILD_DIR/root.img"

cfg() { python3 -c "import json;d=json.load(open('$CONFIG'));print($1)"; }
DEVICE_KERNEL=$(cfg "d['upstream']['kernel_release']")
RELEASE=$(cfg "d['upstream']['release']")
HOSTNAME=$(cfg "d['kali']['hostname']")

step() { echo; echo "===== $* ====="; }

if (( EUID != 0 )); then
    echo 'Run this script as root on Linux.' >&2
    exit 1
fi
for tool in debootstrap img2simg mkfs.ext4 e2fsck python3 curl unzip; do
    command -v "$tool" >/dev/null || { echo "Missing build dependency: $tool" >&2; exit 1; }
done
NATIVE=0
[[ "$(uname -m)" == aarch64 ]] && NATIVE=1
QEMU=''
if (( ! NATIVE )); then
    QEMU=$(command -v qemu-aarch64-static || command -v qemu-aarch64)
    [[ -n "$QEMU" ]] || { echo 'qemu-aarch64-static is required on non-ARM64 builders' >&2; exit 1; }
fi

mkdir -p "$BUILD_DIR" "$ROOTFS" "$ASSET_DIR" "$OUT_DIR"
cleanup() {
    for target in dev/pts dev proc sys ''; do
        if mountpoint -q "$ROOTFS${target:+/$target}"; then
            umount "$ROOTFS${target:+/$target}" || true
        fi
    done
}
trap cleanup EXIT

step "fetch pinned piano release assets"
ASSET_DIR="$ASSET_DIR" bash "$PROJECT/scripts/fetch-assets.sh"

step "create Kali root filesystem image ($IMAGE_SIZE)"
KEYRING=/usr/share/keyrings/kali-archive-keyring.gpg
if [[ ! -s "$KEYRING" ]]; then
    KEYRING="$ASSET_DIR/kali-archive-keyring.gpg"
    curl --fail --location --retry 3 https://archive.kali.org/archive-keyring.gpg -o "$KEYRING"
fi
[[ -e "$ROOT_IMG" ]] && { echo "$ROOT_IMG exists; remove $BUILD_DIR first" >&2; exit 1; }
truncate -s "$IMAGE_SIZE" "$ROOT_IMG"
mkfs.ext4 -F -L kali-piano -O '^metadata_csum_seed,^orphan_file' "$ROOT_IMG"
mount -o loop "$ROOT_IMG" "$ROOTFS"
[[ -f /usr/share/debootstrap/scripts/kali-rolling ]] || ln -s sid /usr/share/debootstrap/scripts/kali-rolling
if (( NATIVE )); then
    debootstrap --arch=arm64 --keyring="$KEYRING" \
        --components=main,contrib,non-free,non-free-firmware \
        kali-rolling "$ROOTFS" "$KALI_MIRROR"
else
    debootstrap --foreign --arch=arm64 --keyring="$KEYRING" \
        --components=main,contrib,non-free,non-free-firmware \
        kali-rolling "$ROOTFS" "$KALI_MIRROR"
    install -m 0755 "$QEMU" "$ROOTFS/usr/bin/qemu-aarch64-static"
    chroot "$ROOTFS" /debootstrap/debootstrap --second-stage
fi

mount --bind /dev "$ROOTFS/dev"
mount -t devpts devpts "$ROOTFS/dev/pts"
mount -t proc proc "$ROOTFS/proc"
mount -t sysfs sysfs "$ROOTFS/sys"
rm -f "$ROOTFS/etc/resolv.conf"
cp -L /etc/resolv.conf "$ROOTFS/etc/resolv.conf"
install -Dm 0644 "$KEYRING" "$ROOTFS/usr/share/keyrings/kali-archive-keyring.gpg"
printf 'deb [signed-by=/usr/share/keyrings/kali-archive-keyring.gpg] %s kali-rolling main contrib non-free non-free-firmware\n' \
    "$KALI_MIRROR" > "$ROOTFS/etc/apt/sources.list"
printf '#!/bin/sh\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
chmod 0755 "$ROOTFS/usr/sbin/policy-rc.d"

step "install Kali desktop and tools"
chroot "$ROOTFS" apt-get update
chroot "$ROOTFS" apt-get install -y --no-install-recommends \
    kali-archive-keyring kali-defaults kali-desktop-kde kali-tools-top10 \
    systemd-sysv sudo locales tzdata ca-certificates openssh-server \
    network-manager plasma-nm bluedevil wpasupplicant wireless-regdb iw rfkill \
    sddm systemsettings plasma-keyboard qt6-virtualkeyboard-plugin konsole dolphin \
    kscreen kinfocenter kde-config-gtk-style kwin-addons breeze-gtk-theme \
    plasma-workspace-wallpapers filelight kclock \
    pipewire-audio pulseaudio-utils playerctl brightnessctl brightness-udev wl-clipboard \
    libgl1-mesa-dri mesa-vulkan-drivers xserver-xorg-input-libinput \
    fonts-noto-cjk fonts-noto-color-emoji firefox-esr \
    dbus-user-session python3-dbus python3-gi python3-pyudev polkitd pkexec usbutils pciutils dnsmasq-base \
    e2fsprogs kmod qrtr-tools rmtfs tqftpserv bluez libkscreen-bin \
    systemd-timesyncd util-linux-extra zstd systemd-zram-generator \
    alsa-utils alsa-ucm-conf rtkit powerdevil plasma-pa hostapd kdialog \
    fcitx5 fcitx5-frontend-qt6 fcitx5-chinese-addons fcitx5-config-qt \
    xdg-desktop-portal xdg-desktop-portal-kde dbus-x11 \
    device-tree-compiler dracut libpam-modules openssl

step "extract piano packages"
mkdir -p "$BUILD_DIR/debs"
unzip -o -j "$ASSET_DIR/piano-ubuntu-$RELEASE-packages.zip" 'debs/*' -d "$BUILD_DIR/debs" >/dev/null
ls "$BUILD_DIR/debs" | sed -n '1,20p'
DEB="$BUILD_DIR/debs"

step "install piano kernel, firmware and device packages"
install -m 0755 "$PROJECT/device/install-piano-debs.sh" "$ROOTFS/tmp/install-piano-debs.sh"
mkdir -p "$ROOTFS/tmp/piano-debs"
cp "$DEB"/*.deb "$ROOTFS/tmp/piano-debs/"
set +e
chroot "$ROOTFS" /bin/sh /tmp/install-piano-debs.sh > "$OUT_DIR/piano-debs.log" 2>&1
DEB_STATUS=$?
set -e
tail -n 25 "$OUT_DIR/piano-debs.log"
echo "package installer exit=$DEB_STATUS"
chroot "$ROOTFS" dpkg --configure -a >/dev/null 2>&1 || true
chroot "$ROOTFS" apt-get -f install -y --no-install-recommends >/dev/null 2>&1 || true

step "configure Kali for piano"
ln -sf /usr/share/zoneinfo/Asia/Shanghai "$ROOTFS/etc/localtime"
printf 'Asia/Shanghai\n' > "$ROOTFS/etc/timezone"
printf 'en_US.UTF-8 UTF-8\nzh_CN.UTF-8 UTF-8\n' > "$ROOTFS/etc/locale.gen"
chroot "$ROOTFS" locale-gen
printf 'LANG=zh_CN.UTF-8\n' > "$ROOTFS/etc/default/locale"
printf '%s\n' "$HOSTNAME" > "$ROOTFS/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 %s\n::1 localhost ip6-localhost ip6-loopback\n' "$HOSTNAME" > "$ROOTFS/etc/hosts"
install -m 0644 "$PROJECT/device/fstab" "$ROOTFS/etc/fstab"
install -Dm 0755 "$PROJECT/device/piano-grow" "$ROOTFS/usr/libexec/piano/piano-grow"
install -Dm 0644 "$PROJECT/device/piano-grow.service" "$ROOTFS/etc/systemd/system/piano-grow.service"
install -Dm 0755 "$PROJECT/device/piano-thp-calibrate" "$ROOTFS/usr/libexec/piano/piano-thp-calibrate"
install -Dm 0644 "$PROJECT/device/piano-thp-calibrate.service" "$ROOTFS/etc/systemd/system/piano-thp-calibrate.service"
install -d "$ROOTFS/usr/share/alsa/ucm2"
cp -a "$PROJECT/vendor/audio/ucm2/." "$ROOTFS/usr/share/alsa/ucm2/"
chmod -R a+rX "$ROOTFS/usr/share/alsa/ucm2"
install -Dm 0755 "$PROJECT/device/piano-powerkey" "$ROOTFS/usr/local/bin/piano-powerkey"
install -Dm 0644 /dev/stdin "$ROOTFS/etc/systemd/system/piano-powerkey.service" <<'EOF'
[Unit]
Description=Piano power key DPMS toggle
After=graphical.target
[Service]
ExecStart=/usr/local/bin/piano-powerkey
Restart=always
[Install]
WantedBy=multi-user.target
EOF
install -d "$ROOTFS/etc/systemd/logind.conf.d"
printf '[Login]\nHandleLidSwitch=lock\nHandleLidSwitchExternalPower=lock\nHandleLidSwitchDocked=ignore\nHandlePowerKey=ignore\nHandlePowerKeyLongPress=ignore\n' \
    > "$ROOTFS/etc/systemd/logind.conf.d/99-kali-tablet.conf"
install -Dm 0755 "$PROJECT/device/piano-ipados" "$ROOTFS/usr/sbin/piano-ipados"
install -Dm 0644 "$PROJECT/device/90-piano-ipados.rules" "$ROOTFS/etc/udev/rules.d/90-piano-ipados.rules"
install -Dm 0755 "$PROJECT/vendor/extract-thp-calibration.py" "$ROOTFS/usr/lib/piano/extract-thp-calibration.py"
install -d "$ROOTFS/etc/piano"
printf 'THP calibration is unit specific. piano-thp-calibrate extracts it from the stock odm partition\non first boot; if that fails, copy the JSON from the Android side to /etc/piano/thp-calibration.json.\n' \
    > "$ROOTFS/etc/piano/README"

if [[ -f "$ROOTFS/usr/share/wayland-sessions/plasma.desktop" ]]; then
    SESSION=plasma.desktop
elif [[ -f "$ROOTFS/usr/share/wayland-sessions/plasmawayland.desktop" ]]; then
    SESSION=plasmawayland.desktop
else
    echo 'Plasma Wayland session was not installed.' >&2
    exit 1
fi
install -d "$ROOTFS/etc/sddm.conf.d"
printf '[Autologin]\nUser=kali\nSession=%s\nRelogin=false\n\n[General]\nDisplayServer=wayland\n' "$SESSION" \
    > "$ROOTFS/etc/sddm.conf.d/10-kali-piano.conf"
install -d "$ROOTFS/home/kali/.config"
cat > "$ROOTFS/home/kali/.config/kwinrc" <<'EOF'
[Wayland]
InputMethod=/usr/share/applications/org.kde.plasma.keyboard.desktop
VirtualKeyboardEnabled=true
[Xwayland]
Scale=2
EOF
if ! chroot "$ROOTFS" id kali >/dev/null 2>&1; then
    chroot "$ROOTFS" useradd -m -s /bin/bash -G sudo,adm,audio,video,plugdev,netdev,dialout,render kali
fi
printf 'kali:%s\n' "$KALI_PASSWORD" | chroot "$ROOTFS" chpasswd
chroot "$ROOTFS" passwd -l root
chroot "$ROOTFS" chown -R kali:kali /home/kali
install -d "$ROOTFS/etc/ssh/sshd_config.d"
printf 'PermitRootLogin no\n' > "$ROOTFS/etc/ssh/sshd_config.d/10-kali-piano.conf"
rm -f "$ROOTFS"/etc/ssh/ssh_host_*
cat > "$ROOTFS/etc/systemd/system/kali-ssh-keys.service" <<'EOF'
[Unit]
Description=Generate unique SSH host keys
Before=ssh.service
[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
[Install]
WantedBy=multi-user.target
EOF
printf 'vm.swappiness=100\n' > "$ROOTFS/etc/sysctl.d/80-piano-zram.conf"
printf '[zram0]\nzram-size = min(ram / 2, 6144)\ncompression-algorithm = zstd\n' > "$ROOTFS/etc/systemd/zram-generator.conf"
chroot "$ROOTFS" systemctl enable NetworkManager ssh sddm systemd-timesyncd bluetooth kali-ssh-keys piano-grow piano-thp-calibrate piano-powerkey
chroot "$ROOTFS" systemctl set-default graphical.target

step "validate image contents"
chroot "$ROOTFS" /bin/bash -ec '
    test "$(dpkg --print-architecture)" = arm64
    . /etc/os-release
    test "$ID" = kali
    test -d /lib/modules/'"$DEVICE_KERNEL"'
    test -e /usr/share/wayland-sessions/plasma.desktop -o -e /usr/share/wayland-sessions/plasmawayland.desktop
    test -d /lib/firmware/qcom
    test -x /usr/libexec/piano/piano-thp-live
    dpkg-query -W linux-image-'"$DEVICE_KERNEL"' piano-device-support piano-local-firmware
' | tee "$OUT_DIR/validation.txt"
chroot "$ROOTFS" dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\n' > "$OUT_DIR/packages.tsv"

step "check piano binaries against the Kali userland"
{
  echo "== dpkg --audit"
  chroot "$ROOTFS" dpkg --audit || true
  echo "== missing shared libraries"
  chroot "$ROOTFS" /bin/bash -ec '
    for f in /usr/libexec/piano/piano-thp-live /usr/libexec/piano/bluetooth-address \
             /usr/bin/piano-camerad /usr/sbin/piano-devmode /usr/sbin/piano-boot-update \
             /usr/sbin/piano-ipados; do
        [ -x "$f" ] || continue
        missing=$(ldd "$f" 2>/dev/null | grep "not found" || true)
        [ -n "$missing" ] && printf "%s\n%s\n" "$f" "$missing"
    done
  ' || true
} 2>&1 | tee "$OUT_DIR/kali-compat.txt"

step "inject private touch calibration"
mkdir -p "$ROOTFS/usr/share/piano"
for panel in csot boe; do
    upper=$(echo "$panel" | tr '[:lower:]' '[:upper:]')
    var="THP_${upper}_B64"
    value=${!var:-}
    if [[ -n "$value" ]]; then
        printf '%s' "$value" | base64 -d > "$ROOTFS/usr/share/piano/thp-$panel.json"
        chmod 600 "$ROOTFS/usr/share/piano/thp-$panel.json"
        echo "installed private $panel touch calibration"
    fi
done

step "on-screen keyboard (optional)"
if [[ "${WITH_OSK:-1}" == 1 ]]; then
    if ! WITH_OSK_WORK="$PROJECT/.work/osk" bash "$PROJECT/scripts/build-osk.sh" "$ROOTFS" > "$OUT_DIR/osk.log" 2>&1; then
        echo "WARN: OSK stage failed; image keeps plasma-keyboard (see osk.log)"
    else
        echo "OSK installed"
    fi
    tail -n 5 "$OUT_DIR/osk.log" || true
fi

step "patched Mesa (optional)"
if [[ "${WITH_PIANO_MESA:-1}" == 1 ]]; then
    if ! WORK="$PROJECT/.work/mesa" bash "$PROJECT/scripts/build-mesa.sh" "$ROOTFS" > "$OUT_DIR/mesa.log" 2>&1; then
        echo "WARN: Mesa stage failed; image keeps Kali Mesa (see mesa.log)"
    else
        echo "patched Mesa installed"
    fi
    tail -n 5 "$OUT_DIR/mesa.log" || true
fi

step "finalise root filesystem"
chroot "$ROOTFS" apt-get clean
rm -f "$ROOTFS/etc/resolv.conf" "$ROOTFS/usr/sbin/policy-rc.d"
[[ -e "$ROOTFS/usr/bin/qemu-aarch64-static" ]] && rm -f "$ROOTFS/usr/bin/qemu-aarch64-static" || true
rm -rf "$ROOTFS/tmp/piano-debs" "$ROOTFS/tmp/install-piano-debs.sh"
ln -sf /run/NetworkManager/resolv.conf "$ROOTFS/etc/resolv.conf"
truncate -s 0 "$ROOTFS/etc/machine-id"
rm -f "$ROOTFS/var/lib/dbus/machine-id"
ln -s /etc/machine-id "$ROOTFS/var/lib/dbus/machine-id"
cleanup
e2fsck -f -n "$ROOT_IMG"
img2simg "$ROOT_IMG" "$OUT_DIR/root.sparse.img"

step "build the boot image set"
mkdir -p "$BUILD_DIR/bootset"
set +e
unzip -o -q "$ASSET_DIR/piano-ubuntu-$RELEASE-boot.zip" 'boot/*.img' -d "$BUILD_DIR/bootset"
set -e
BOOT_SRC=$(find "$BUILD_DIR/bootset" -name boot.img -type f | head -n 1)
INIT_SRC=$(find "$BUILD_DIR/bootset" -name init_boot.img -type f | head -n 1)
VENDOR_SRC=$(find "$BUILD_DIR/bootset" -name vendor_boot.img -type f | head -n 1)
# The upstream boot.img is AVB-signed. On this tablet a modified boot image
# fails the bootloader verification screen, so ship it byte-identical and
# rename the root partition to what its command line already expects
# (root=PARTLABEL=linux_rootfs). See docs/INSTALL.md step 3a.
cp "$BOOT_SRC" "$OUT_DIR/boot.img"
python3 - "$OUT_DIR/boot.img" <<'PY2'
import sys
d = open(sys.argv[1], 'rb').read()
cmd = d[0x2c:0x2c+1536].split(b'\0')[0].decode()
print('boot.img cmdline:', cmd)
assert 'root=PARTLABEL=linux_rootfs' in cmd, 'unexpected cmdline in upstream boot.img'
PY2
cp "$INIT_SRC" "$OUT_DIR/init_boot.img"
cp "$VENDOR_SRC" "$OUT_DIR/vendor_boot.img"
MAINT_SRC=$(find "$BUILD_DIR/bootset" -name boot-ram-maintenance.img -type f | head -n 1)
[[ -n "$MAINT_SRC" ]] && cp "$MAINT_SRC" "$OUT_DIR/boot-ram-maintenance.img"

step "write manifest"
python3 - "$CONFIG" "$OUT_DIR" <<'PY'
import hashlib, json, os, sys
cfg = json.load(open(sys.argv[1]))
out = sys.argv[2]
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()
files = {}
for name in sorted(os.listdir(out)):
    p = os.path.join(out, name)
    if os.path.isfile(p) and name.endswith(('.img', '.json', '.txt', '.tsv', '.log')):
        files[name] = {'bytes': os.path.getsize(p), 'sha256': sha(p)}
manifest = {
    'name': 'kali-piano',
    'device': cfg['device'],
    'upstream': cfg['upstream'],
    'kali': cfg['kali'],
    'kernel_release': cfg['upstream']['kernel_release'],
    'root_partition': 'userdata',
    'images': files,
    'scope': 'Root filesystem and boot image set only; not booted on hardware by the builder',
}
json.dump(manifest, open(os.path.join(out, 'manifest.json'), 'w'), indent=2)
print(json.dumps(manifest['images'], indent=2))
PY

echo BUILD_COMPLETE
