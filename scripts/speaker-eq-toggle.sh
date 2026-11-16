#!/bin/sh
set -eu
dir="${XDG_CONFIG_HOME:-$HOME/.config}/pipewire/filter-chain.conf.d"
enabled="$dir/50-sheng-speaker-balanced.conf"
disabled="$dir/50-sheng-speaker-balanced.conf.disabled"
if test "${1:-}" = --status; then
    if test -f "$enabled"; then echo enabled; else echo disabled; fi
    exit 0
fi
if test -f "$enabled" && ! test -e "$disabled"; then
    mv -- "$enabled" "$disabled"
    message='已切换为原始扬声器音质'
elif test -f "$disabled" && ! test -e "$enabled"; then
    mv -- "$disabled" "$enabled"
    message='已启用均衡扬声器音质'
else
    echo 'Sheng speaker EQ configuration missing or ambiguous' >&2
    exit 1
fi
systemctl --user restart filter-chain.service
if command -v notify-send >/dev/null 2>&1; then
    notify-send -i audio-volume-high '扬声器音质' "$message"
fi
printf '%s\n' "$message"
