#!/bin/sh
# Install the released piano .debs inside the Kali root filesystem.
# apt resolves everything it can from Kali; a package that cannot be satisfied
# is installed with --force-depends so one Ubuntu-only dependency does not stop
# the whole image. Every failure is printed and summarised at the end.
set -u
DIR=/tmp/piano-debs
FAILED=''

install_one() {
    pkg=$1
    file=$(ls "$DIR"/${pkg}_*.deb "$DIR"/${pkg}-*_*.deb 2>/dev/null | head -n 1)
    [ -n "$file" ] || { echo "MISSING DEB: $pkg"; FAILED="$FAILED $pkg"; return; }
    echo "--- $pkg"
    if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$file"; then
        return
    fi
    echo "WARN: apt could not satisfy $pkg, trying --force-depends"
    if dpkg -i --force-depends "$file"; then
        FAILED="$FAILED $pkg(forced)"
    else
        FAILED="$FAILED $pkg(FAILED)"
    fi
}

# dracut Conflicts initramfs-tools, so Kali gets dracut only. dracut's kernel
# hook would rebuild an initrd we never boot (the vendor_boot ramdisk is used),
# and under qemu it is very slow: park the hooks for the kernel install.
mkdir -p /tmp/kernel-hooks-off
for hook in /etc/kernel/postinst.d/*dracut* /etc/kernel/postrm.d/*dracut* /etc/initramfs/post-update.d/*dracut*; do
    [ -e "$hook" ] && mv "$hook" /tmp/kernel-hooks-off/ || true
done

install_one piano-local-firmware
install_one piano-npu-firmware
install_one linux-image-7.4.0-rc2-piano88
install_one piano-device-support
install_one piano-sensors
install_one piano-iio-sensor-proxy
install_one piano-iris-vaapi
install_one piano-camerad
install_one piano-camera-loopback-7.4.0-rc2-piano88

for hook in /tmp/kernel-hooks-off/*; do
    [ -e "$hook" ] || continue
    case "$hook" in
        *postinst*) install -m 755 "$hook" /etc/kernel/postinst.d/ ;;
        *postrm*) install -m 755 "$hook" /etc/kernel/postrm.d/ ;;
        *) install -m 755 "$hook" /etc/initramfs/post-update.d/ ;;
    esac
done
rm -rf /tmp/kernel-hooks-off

depmod -a 7.4.0-rc2-piano88 || true
echo "SUMMARY:$FAILED"
