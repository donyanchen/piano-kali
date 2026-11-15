# Adreno 740 monitoring for sheng

This device-specific KSystemStats plugin provides the standard `gpu/gpu0/` and
`gpu/all/` sensor paths. The original PCI-only KDE GPU plugin is preserved by a
Debian package diversion, outside the Qt plugin search directory.

- Utilization uses changes in the kernel's `drm-engine-gpu` nanosecond counters.
  Shared file descriptors and inherited DRM clients are deduplicated by client ID.
  Very short-lived clients may finish between samples, so this is sampled engine
  utilization, not a benchmark or a per-process accounting interface.
- Frequency is the latest value reported by GPU devfreq; runtime power status is
  exposed separately because a suspended GPU may retain its last clock setting.
- Resident and active graphics memory come from global MSM GEM summaries, which
  count shared objects once. These bytes are already included in system RAM usage.
- The legacy `totalVram` sensor is explicitly labeled as the shared system RAM
  ceiling. It is not dedicated VRAM, a reservation, or Mesa's per-context budget.
- Missing and stale measurements are reported as unavailable. Temperature, power,
  and memory clocks are omitted when there is no measured data source.

The root collector exports aggregate numbers only. It has no network listener,
uses a read-only filesystem sandbox, and is restricted to 64 MiB and 10% of one
CPU core. It samples every two seconds. The Qt plugin runs as the desktop user.

Remove the adaptation and restore the distribution plugin with:

```bash
sudo apt remove sheng-gpu-monitor
systemctl --user restart plasma-ksystemstats.service
```
