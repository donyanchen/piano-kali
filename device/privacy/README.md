# 统一隐私开关

控制中心的“隐私”开关采用统一策略：开启时拒绝应用、后台进程访问本机摄像头、麦克风及系统定位接口；关闭后恢复访问。当前平板未发现 GNSS 设备，提示中会如实标明“未检测到 GPS 硬件”。

## 拦截层

- [device-guard.c](device-guard.c) 将 cgroup device BPF 程序挂到根 cgroup，按字符设备的主／次设备号限制所有进程的新设备打开、节点创建请求。内置 V4L2 摄像头、ALSA 采集节点、已识别 GNSS 节点以及音视频 USB 原始设备通道被限制。驱动为 `qcom-iris` 的视频编解码节点、ALSA 播放和控制节点保留。
- 系统总线拒绝 GeoClue 的目标地址及接口；会话总线拒绝 Camera、Location、Microphone 门户接口。关闭时恢复空策略，并重新加载总线配置，无须重启桌面总线。
- 暂停音频输入，切断内置麦克风的 `TX SMIC/DMIC MUX` 采集路由，撤回采集设备权限，并解绑独立的 CAMSS 摄像头驱动。关闭后恢复保存的设备权限、采集路由和摄像头绑定。
- 对开启前已持有 ALSA／GNSS 采集句柄的直连进程，保存 PID、启动时间、boot ID 与原 cgroup，移入管理员控制的冻结组。关闭时将同一进程移回并恢复执行。不会终止这些进程；直接采集的应用在此期间可能整体暂停。
- udev 更新热插拔设备的内核过滤条目。状态持久化在 `/var/lib/sheng-privacy/`，开机在用户会话启动前恢复。

当前内核未启用 BPF LSM，因此采用设备打开／创建过滤与旧句柄进程暂停相结合的方式。此开关不是抗系统管理员篡改的安全边界：有权修改内核策略的管理员可以主动移除策略。它不屏蔽屏幕截图、扬声器播放或网站自行根据公网 IP 推测位置。

## 控制与验证

[privacy-control.py](privacy-control.py) 只允许 root 执行固定的 `on`、`off`、`restore` 操作。控制中心通过 [privacy-client.py](privacy-client.py) 请求限定的 systemd 模板实例；Polkit 仅允许本机活跃的 `kali` 会话启动这两个实例，不授予通用 systemd 管理权限。未开启时，没有常驻隐私守护进程。

只读状态位于 `/run/sheng-privacy/status.json`；源码、设备端散列及验证见本机 `out/desktop-privacy-verification.json`。已进行以下验证：

- 开启后 root 进程直接打开麦克风返回 `EPERM`，另建同类采集节点也返回 `EPERM`。
- 摄像头采集驱动解绑，视频编解码节点与音频控制节点仍可用。
- 使用受保护接口向现有总线服务发出无副作用探测，开启时返回 `AccessDenied`；关闭后恢复正常接口分派。当时尚未安装实际 GeoClue／门户服务，因此未将此项当作实际 GPS 定位测试。后续输入法集成已安装 xdg-desktop-portal 和 KDE 后端，但未补做真实定位验收。
- 一个仅打开采集句柄、不读取样本的临时进程，在开启时暂停，关闭后以同一 PID 恢复。
- 关闭后摄像头绑定、采集设备权限和音频输入恢复。

构建设备过滤器：

```sh
gcc -std=gnu11 -O2 -Wall -Wextra -Werror device-guard.c -o sheng-privacy-bpf
sudo ./sheng-privacy-bpf probe
```

实现使用当前内核支持的 cgroup BPF 与标准 Linux 设备接口，不修改平板键盘驱动、热点后端或 GPU 驱动。守护配置、设备权限快照仅由 root 写入。

接口依据：[Linux cgroup v2 设备控制](https://docs.kernel.org/admin-guide/cgroup-v2.html)、[D-Bus 强制消息策略](https://dbus.freedesktop.org/doc/dbus-daemon.1.html)。
