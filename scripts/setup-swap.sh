#!/bin/bash
# Add a persistent swap file without replacing an existing file or active swap.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run as root.' >&2; exit 1; }
size_gib=${SWAP_SIZE_GIB:-8}
[[ "$size_gib" =~ ^[1-9][0-9]*$ ]] && (( size_gib <= 32 )) || {
    echo 'SWAP_SIZE_GIB must be an integer between 1 and 32.' >&2; exit 1;
}
swapfile=/swapfile
if [[ -L "$swapfile" ]]; then
    echo 'Refusing to use a symbolic link for /swapfile.' >&2; exit 1
fi
if [[ ! -e "$swapfile" ]]; then
    free_bytes=$(df -B1 --output=avail / | tail -n 1)
    (( free_bytes >= (size_gib + 2) * 1024 * 1024 * 1024 )) || {
        echo 'Insufficient storage for swap and a 2 GiB free-space reserve.' >&2; exit 1;
    }
    umask 077
    install -m 0600 /dev/null "$swapfile"
    fallocate -l "${size_gib}G" "$swapfile"
    mkswap -L kali-swap "$swapfile"
elif [[ ! -f "$swapfile" || $(blkid -p -s TYPE -o value "$swapfile") != swap ]]; then
    echo 'Existing /swapfile is not a swap file; leaving it untouched.' >&2; exit 1
fi
if ! swapon --show=NAME --noheadings | grep -Fxq "$swapfile"; then
    swapon --priority 10 "$swapfile"
fi
if ! awk '$1 == "/swapfile" && $3 == "swap" {found=1} END {exit !found}' /etc/fstab; then
    printf '/swapfile none swap defaults,pri=10 0 0\n' >> /etc/fstab
fi
if [[ ! -e /etc/sysctl.d/80-sheng-swap.conf ]]; then
    printf 'vm.swappiness = 160\nvm.page-cluster = 0\n' > /etc/sysctl.d/80-sheng-swap.conf
    sysctl -p /etc/sysctl.d/80-sheng-swap.conf
fi
sysctl vm.swappiness
systemctl daemon-reload
swapon --show
free -h
