#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
set -eu
project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=${1:-"$project_dir/out/build-desktop-touch-guard"}
plugin_dir=$(qmake6 -query QT_INSTALL_PLUGINS)
cmake -S "$project_dir/device/desktop-touch-guard" -B "$build_dir" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DKDE_INSTALL_PLUGINDIR="$plugin_dir"
cmake --build "$build_dir" --parallel 2
printf 'Built with the local KWin development ABI. Install on this same system:\n'
printf 'sudo cmake --install "%s"\n' "$build_dir"
