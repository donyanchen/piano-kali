#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read real MSM counters; export aggregate metrics without process details."""
import glob
import json
import os
import pathlib
import re
import time

DEVFREQ = pathlib.Path('/sys/class/devfreq/3d00000.gpu')
OUTPUT = pathlib.Path('/run/sheng-gpu-monitor/metrics.json')


def read_number(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def drm_clients():
    clients = {}
    for process in glob.glob('/proc/[0-9]*'):
        try:
            descriptors = os.listdir(process + '/fd')
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(process + '/fd/' + descriptor)
                if not target.startswith('/dev/dri/'):
                    continue
                info = pathlib.Path(process + '/fdinfo/' + descriptor).read_text()
            except OSError:
                continue
            fields = dict(line.split(':', 1) for line in info.splitlines() if ':' in line)
            if fields.get('drm-driver', '').strip() != 'msm':
                continue
            identity = fields.get('drm-client-id', '').strip()
            value = fields.get('drm-engine-gpu', '').strip().split()
            if identity and len(value) == 2 and value[1] == 'ns':
                # The same DRM client can be shared by several FDs/processes.
                # Taking its largest sample avoids counting those duplicates.
                clients[identity] = max(clients.get(identity, 0), int(value[0]))
    return clients


def graphics_memory():
    for filename in sorted(glob.glob('/sys/kernel/debug/dri/*/gem')):
        try:
            with open(filename) as source:
                values = {}
                for line in source:
                    match = re.fullmatch(r'(Resident|Active):\s+\d+ objects,\s+(\d+) bytes\s*', line)
                    if match:
                        values[match[1]] = int(match[2])
            if 'Resident' in values:
                return values
        except OSError:
            continue
    return {}


def main():
    if b'xiaomi,sheng' not in pathlib.Path('/proc/device-tree/compatible').read_bytes():
        raise SystemExit('This collector is intended for Xiaomi sheng only')
    OUTPUT.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    previous, previous_time = {}, None
    while True:
        start = time.monotonic()
        current = drm_clients()
        now_ns = time.monotonic_ns()
        usage = None
        if previous_time is not None and now_ns > previous_time:
            busy = sum(value - previous[key] for key, value in current.items()
                       if key in previous and value >= previous[key])
            usage = max(0.0, min(100.0, 100.0 * busy / (now_ns - previous_time)))
        memory = graphics_memory()
        total = re.search(r'^MemTotal:\s+(\d+) kB$', pathlib.Path('/proc/meminfo').read_text(), re.M)
        try:
            runtime = (DEVFREQ / 'device/power/runtime_status').read_text().strip()
        except OSError:
            runtime = 'unknown'
        metrics = {
            'timestamp_ms': int(time.time() * 1000),
            'driver': 'msm', 'model': 'Adreno 740', 'memory_type': 'unified',
            'usage_percent': usage,
            'frequency_hz': read_number(DEVFREQ / 'cur_freq'),
            'runtime_status': runtime,
            'memory_total_bytes': int(total[1]) * 1024 if total else None,
            'memory_resident_bytes': memory.get('Resident'),
            'memory_active_bytes': memory.get('Active'),
            'drm_clients': len(current),
        }
        temporary = OUTPUT.with_suffix('.tmp')
        temporary.write_text(json.dumps(metrics) + '\n')
        temporary.chmod(0o644)
        temporary.replace(OUTPUT)
        previous, previous_time = current, now_ns
        time.sleep(max(0.1, 2.0 - (time.monotonic() - start)))


if __name__ == '__main__':
    main()
