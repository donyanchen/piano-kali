#!/bin/bash
set -euo pipefail
modprobe libcomposite
mountpoint -q /sys/kernel/config || mount -t configfs configfs /sys/kernel/config
GADGET=/sys/kernel/config/usb_gadget/sheng
mkdir -p "$GADGET"
cd "$GADGET"
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0200 > bcdUSB
echo 0x0100 > bcdDevice
echo 0xef > bDeviceClass
echo 0x02 > bDeviceSubClass
echo 0x01 > bDeviceProtocol
mkdir -p strings/0x409 configs/c.1/strings/0x409
echo sheng-kali > strings/0x409/serialnumber
echo 'Kali Linux' > strings/0x409/manufacturer
echo 'Kali sheng USB Network' > strings/0x409/product
echo 'USB network' > configs/c.1/strings/0x409/configuration
mkdir -p functions/rndis.usb0
mkdir -p functions/acm.console
echo 02:77:00:00:00:01 > functions/rndis.usb0/dev_addr
echo 02:77:00:00:00:02 > functions/rndis.usb0/host_addr
echo 1 > os_desc/use
echo 0xcd > os_desc/b_vendor_code
echo MSFT100 > os_desc/qw_sign
echo RNDIS > functions/rndis.usb0/os_desc/interface.rndis/compatible_id
echo 5162001 > functions/rndis.usb0/os_desc/interface.rndis/sub_compatible_id
[[ -e configs/c.1/rndis.usb0 ]] || ln -s "$GADGET/functions/rndis.usb0" configs/c.1/
[[ -e configs/c.1/acm.console ]] || ln -s "$GADGET/functions/acm.console" configs/c.1/
[[ -e os_desc/c.1 ]] || ln -s "$GADGET/configs/c.1" os_desc/
for attempt in {1..30}; do
    controller=$(find /sys/class/udc -mindepth 1 -maxdepth 1 -printf '%f\n' | head -n 1)
    [[ -z "$controller" ]] || break
    sleep 1
done
[[ -n "$controller" ]] || { echo 'USB device controller unavailable' >&2; exit 1; }
echo "$controller" > UDC
systemctl start --no-block serial-getty@ttyGS0.service
if ! nmcli connection show sheng-usb >/dev/null 2>&1; then
    nmcli connection add type ethernet ifname usb0 con-name sheng-usb \
        ipv4.method shared ipv4.addresses 192.168.77.1/24 ipv6.method disabled
fi
nmcli connection up sheng-usb
