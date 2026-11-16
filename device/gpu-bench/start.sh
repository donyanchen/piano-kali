#!/bin/bash
set -euo pipefail
state=/home/kali/.local/state/piano-gpu-bench
tag="${1:-balanced}"
systemd-run --quiet --collect --unit=piano-gpu-benchmark \
  -p RuntimeMaxSec=600 \
  -p "ExecStopPost=/usr/bin/python3 $state/restore.py" \
  /usr/bin/systemd-inhibit --what=idle:sleep --mode=block \
    --who=GPU-benchmark --why='Comparing OpenGL and Vulkan on piano' \
    /usr/bin/python3 "$state/run.py" "$tag"
