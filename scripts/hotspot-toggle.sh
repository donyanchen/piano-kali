#!/bin/bash
set -euo pipefail
if [[ "${1:-}" == info ]]; then
    exec kdialog --title 'Piano 热点连接信息' --textbox /etc/piano-hotspot/access.txt 500 230
fi
if systemctl is-active --quiet piano-hotspot.service; then
    systemctl stop piano-hotspot.service
    kdialog --passivepopup '热点已关闭' 3
else
    systemctl start piano-hotspot.service
    for attempt in {1..80}; do
        if [[ -f /run/piano-hotspot/ready ]]; then
            kdialog --passivepopup 'Piano-Kali 热点已开启；右键应用可查看连接信息' 5
            exit 0
        fi
        sleep 0.25
    done
    kdialog --error '热点启动失败，请检查 Wi-Fi 是否已连接。'
    exit 1
fi
