#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
if [ "$(id -u)" -ne 0 ]; then
    printf '%s\n' 'Run with sudo on the tablet.' >&2
    exit 1
fi
project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
apt-get install -y fonts-noto-core fonts-noto-ui-core fonts-liberation
install -m 0644 "$project_dir/device/theme/fonts/31-sheng-material-icons-charset.conf" \
    /etc/fonts/conf.d/31-sheng-material-icons-charset.conf
fc-cache -f
printf '%s\n' 'Text fonts installed; MDI private-use icons retained. Refresh affected pages.'
fc-match 'Noto Sans:charset=0061'
fc-match 'Noto Sans:charset=0030'
fc-match 'Material Design Icons version 6:charset=f0001'
