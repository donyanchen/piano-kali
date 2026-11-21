# 设备侧修复（真机上调出来、必须随镜像一起带走的改动）

这些改动原先只存在于刷好的 Kali rootfs 里，重刷一次就全部丢失。现在它们都在
`device/` 和 `configs/` 下，由 `scripts/build-kali.sh` 在构建镜像时安装。

## 四扬声器：立体声上混与声道顺序

piano 的 TDM 实测顺序是 **slot0=左上、slot1=左下、slot2=右上、slot3=右下**，
而 UCM（`vendor/audio/ucm2/.../Xiaomi-Pad-8-Pro/HiFi.conf`）假设
`ch0=TL, ch1=TR, ch2=BL, ch3=BR`。直接用 UCM，右声道会从左下出来。

修法是两段配置，缺一不可：

| 文件 | 作用 |
|---|---|
| `device/99-piano-stereo.conf` → `/etc/alsa/conf.d/` | `type route` PCM，2ch → 4ch：`ttable.0.0/0.1`（左进左上+左下）、`ttable.1.2/1.3`（右进右上+右下） |
| `device/99-piano-upmix.conf` → `/etc/pipewire/pipewire.conf.d/` | 用 `adapter` 工厂把上面的 PCM 注册成 `Audio/Sink`，`priority.session=3000` 抢默认输出 |

**两个坑**：

1. ALSA route 的语法是 `ttable.<输入>.<输出>`，写反了会静音。
2. 这两个文件必须是 `644`。权限不对 PipeWire 以普通用户读不到，sink 直接退回
   `auto_null`（表现为「突然没有声音输出」）。
3. UCM 的 `PlaybackPCM` **不能**指自定义 PCM，PipeWire 会打不开，同样退 `auto_null`。

## 蓝牙：本地生成的控制器地址

`bluetooth.service` 的 `ExecStartPre=/usr/libexec/piano/bluetooth-address` 要有
`/etc/piano/bluetooth-address`，拿不到就 exit 1 → `start-limit-hit`，蓝牙全废。

出厂 BT MAC 只在 Android 的 persist 分区里，Kali 侧读不到，所以用
`scripts/piano-bluetooth-address.py` 从稳定种子派生一个 **locally-administered**
单播地址（序列号 → sha256 → 6 字节，强制 `02` 位）。已经有合法文件时不覆盖，
所以手工钉住的 MAC 会保留。

副作用：重刷后如果种子变了，MAC 会变，之前的配对要重做（重刷本来也会丢配对）。

## 合盖 / 触屏

- `device/60-piano-input-video.rules`：`/dev/input/event*` 归 `video` 组。
  `gpio-keys` 虽然声明了 `SW_LID`，固件却不发事件，所以合盖判断还得读原始设备。
- `device/piano-lid-watch` → `/usr/local/bin/piano-lidwatch`，用户级
  `piano-lid.service` 挂在 `plasma-workspace.target.wants`：合盖锁屏 + DPMS off，
  开盖只恢复显示、不自动解锁。DPMS 关开之后触屏会卡在 `awaiting baseline`，
  这个进程同时负责在那之后重启 `piano-thp.service`。
- `device/piano-thp-override.conf`：`/etc/systemd/system/piano-thp.service.d/override.conf`，
  把 `Restart=on-failure` 改成 `Restart=always`，否则会话切换后触屏不回来。
- `device/piano-touch-reset`、`device/piano-restart-touch`：手工抢救触屏用的快捷命令。

## 并发热点（wlan1）

`wlan0` 保持 STA，`iw dev wlan0 interface add wlan1 type __ap` 起 AP。反复启停
hostapd 会让 ath12k 卡死（`Too many open files in system`），所以：
**hostapd 只起一次，之后用 `hostapd_cli enable/disable` 开关**。

| 文件 | 用途 |
|---|---|
| `device/piano-hotspot` | 建接口 + hostapd + dnsmasq + NAT；已在跑就只 `enable` |
| `device/piano-hotspot-ctl` | `on / off / status` |
| `device/piano-hotspot-toggle` | 控制中心调用的开关（带 kdialog 提示） |
| `device/piano-hotspot.service` | 开机建 AP（默认 **disabled**，按需启动） |

## ToDesk：libdbus 符号冲突

现象：启动即 `SIGSEGV`，栈顶 `pthread_mutex_lock ← libdbus-1.so.3`。

根因：ToDesk 二进制**静态链了旧版 libdbus，并导出 544 个全局 `dbus_*` 符号**。
`libatk-bridge` 拉起系统 `libdbus-1.so.3` 时，动态链接器把 ToDesk 里的那份符号
抢先绑定给系统库，两边结构体布局不一致 → 崩溃。

修法：

```sh
pip install lief            # 或 Kali 的 python3-lief
todesk-dbus-fix.py /opt/todesk/bin/ToDesk /opt/todesk/bin/ToDesk.fixed
mv /opt/todesk/bin/ToDesk.fixed /opt/todesk/bin/ToDesk
```

`device/todesk-dbus-fix.py` 用 LIEF 把这些符号的 binding 改成 `LOCAL`（544 个），
不再参与全局符号解析。配合 `patchelf --set-rpath '$ORIGIN'`。

`device/todesk-launch` 负责补齐 X11 会话环境：找 `$XDG_RUNTIME_DIR/xauth_*` 作为
`XAUTHORITY`、`DISPLAY=:0`、`GDK_BACKEND=x11`，并且 **`GDK_SCALE=2` +
`GDK_DPI_SCALE=0.5` + `QT_SCALE_FACTOR=2`** —— 少了这几项窗口只有一半大
（810×611，实际 1780×1382）。

`device/piano-pulseaudio` 是个 `exit 0` 空壳：ToDesk 会 exec `pulseaudio` 探测
音频子系统，本机是 PipeWire，让它探测成功即可。

**已知未解决**：窗口持续闪烁。已排除 XWayland（rootless 与 Xephyr 嵌套）、软件
渲染、ARGB/SHM 参数、合成器缺失。逐帧抓取显示 ToDesk **空闲时像素完全不变**
（`changed_px=0`），只有 colormap 在变，说明闪烁只在实际远程会话中发生，尚未定位。

## 桌面配色预设

`configs/panel-colorizer/Piano-Dock`、`Piano-Top` 是 Panel Colorizer 8.1.0 的预设，
装到 `~/.config/panel-colorizer/presets/`，再用
`qdbus6 <dbus名> /preset preset <dir>` 应用。
