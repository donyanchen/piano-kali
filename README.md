# Kali Linux for Xiaomi Pad 8 Pro (`piano`)

在小米平板 8 Pro（`piano` / `25091RP04C`，骁龙 8 至尊版 SM8750P）上跑原生 **Kali Linux ARM64 + KDE Plasma Wayland**。

构建方式**复刻 [sheng-kali-linux](https://github.com/LuKeyC-NetSEC/sheng-kali-linux)**：在 GitHub Actions 里用 debootstrap 造 Kali 根文件系统、装 KDE 与 Kali 工具、打包成 sparse 镜像。

内核、设备树、initramfs、固件和触摸/音频/充电等设备包**直接复用 [xiaomipad-8pro-mainline](https://github.com/yzddmr6/xiaomipad-8pro-mainline) 的发布产物**（Linux 7.4.0-rc2 piano 内核），本项目不重编内核，也不改它的驱动。

> ⚠️ 只适用于已解锁 Bootloader 的 `piano`。写入会**清空 Android 用户数据**（本项目就是 Kali-only 方案）。`ipados`、`vbmeta`、`dtbo`、`persist`、基带/标定分区一律不碰。

## 和 UniXNU 的关系（能兼容）

能，两者不抢同一块地方：

| | Kali（本项目） | UniXNU |
| --- | --- | --- |
| 常驻内容 | A 槽 `boot_a`/`init_boot_a`/`vendor_boot_a` + `userdata` 分区的根文件系统 | `ipados` 分区（sda35，32 GiB）里的 `payload.img` |
| 启动方式 | 正常开机，ABL 从 A 槽起 | **`fastboot boot boot.img`**，纯 RAM 启动，不写任何分区 |

所以：Kali 里 `adb reboot bootloader`，主机 `fastboot boot <unixnu>/boot.img` 就进 UniXNU；在 UniXNU 里重启回 Fastboot 再 `fastboot reboot` 就回 Kali。`ipados` 分区本项目一个字节都不写。

## 构建（在你的 GitHub 仓库里）

1. 打开 **Actions → Build Kali for Xiaomi Pad 8 Pro (piano) → Run workflow**。
2. 可选：在仓库 Secrets 里建 `KALI_PASSWORD`（默认 `kali`）。
3. 约 1–2 小时后，产物在 Workflow 的 **Artifacts**（`kali-piano-<run>.zip`），或推 `v*` tag 时自动发到 **Releases**。

产物内容：

```
root.sparse.img.zst      Kali 根文件系统（ext4，20 GiB 起始，首启自动扩到整个 userdata）
boot.img                 piano 内核 + DTB，cmdline 改成 root=PARTLABEL=userdata
init_boot.img            上游原样
vendor_boot.img          上游原样（含 piano initramfs 与模块）
flash-piano.sh           主机侧刷写脚本
INSTALL.md               安装步骤
SHA256SUMS
```

## 安装

主机需要 `adb`、`fastboot`、`zstd`。

```bash
# 1. 解压（镜像内已含实际数据，解压后就是 sparse 镜像）
zstd -d root.sparse.img.zst -o root.sparse.img

# 2. 平板进 Fastboot：长按电源 + 音量下
fastboot devices

# 3. 刷写（会二次确认；输入 ERASE 才会清 userdata）
bash flash-piano.sh --serial <SERIAL> --dir . --yes
```

刷写顺序就是脚本里的四步：`boot` → `init_boot` → `vendor_boot` → `erase userdata` → `flash userdata`。**不要**写 `_b` 槽、不要 `--set-active=b`、不要刷 `vbmeta`。

## 首次启动

- 自动登录 `kali` / `kali`（SSH 同账号，root 禁止登录）。登录后请立刻改密码。
- 根文件系统自动扩到整个 `userdata`（约 198.9 GiB）。
- 触屏：`piano-thp-calibrate` 首次启动会从原厂 `odm` 分区读 `piano_nova_*_thp_config.ini`，按内核报的面板类型（csot/boe）提取 `/etc/piano/thp-calibration.json`。**这一步要在刷机前保留 odm 分区**；如果失败，先用磁吸键盘或 USB 键鼠，手动把标定 JSON 放到 `/etc/piano/thp-calibration.json` 再 `sudo systemctl restart piano-thp`。
- USB：`sudo piano-devmode on` 打开开发者模式的 USB 网络 + SSH（上游工具）。
- 回 Android：没有 Android 了。回 Fastboot：`sudo piano-reboot-bootloader` 或长按电源 + 音量下。

## 已知差异：HyperOS 版本与 A/B 槽

上游 v1.3.1 的适配基线是 **OS3.0.303.0.WPYCNXM（Android 15 原厂，A 槽）**。实测本机是 **OS4.0.5.0.XPYCNXM（2026-10-21 构建，B 槽）**，所以：

- 内核、DTB、initramfs 都来自上游预编译产物，**不依赖你的 vendor/system**，能启动；真正的风险在固件层（ADSP 音频、充电 mcs/mca、摄像头 ISP、WLAN/BT blob 是按 OS3 版本锁定）——出问题看 `dmesg`，不会刷不进去。
- **槽位**：`/proc/bootconfig` 的真值是 `slot_suffix = _b`。`flash-piano.sh` 会读 `fastboot getvar current-slot` 并显式写对应槽，不再假设 A 槽。不要 `--set-active` 切槽。
- `getprop ro.boot.flash.locked / verifiedbootstate` 会被 Play Integrity 类模块伪造成 `1/green`；真值看 `/proc/bootconfig` 的 `androidboot.vbmeta.device_state`（橙色/orange = 已解锁）。
- **触摸标定**：`odm` 在 OS4 上是 `super` 里的逻辑分区，没有 `/dev/disk/by-partlabel/odm`。镜像里放 CSOT/BOE 两份私有标定（构建时由 `THP_CSOT_B64` / `THP_BOE_B64` 注入），首启按内核上报的 `panel_vendor` 选一份装到 `/etc/piano/thp-calibration.json`。

## 当前限制

- 手写笔、指纹：上游主线适配暂不支持。
- GPU：用的是 Kali 自带 Mesa，不是上游打过补丁的 `piano-mesa`（那套绑定 Ubuntu 26.04 依赖）。Adreno 830 能出画面，重度图形/游戏可能遇到上游已修的问题。
- 触摸依赖本机标定；没有标定就只有键盘鼠标。
- 不提供预制镜像的硬件验收：构建成功 ≠ 真机可用，刷机前请确认你能用 `fastboot boot` 恢复。

## 来源与许可

- Kali 用户态：Kali Linux（Debian 系），构建脚本思路来自 [LuKeyC-NetSEC/sheng-kali-linux](https://github.com/LuKeyC-NetSEC/sheng-kali-linux)。
- 内核、DTB、initramfs、固件、设备包：[yzddmr6/xiaomipad-8pro-mainline](https://github.com/yzddmr6/xiaomipad-8pro-mainline) v1.3.1 发布产物（GPL-2.0-only，二进制原样分发）。
- `vendor/extract-thp-calibration.py`：来自上游 `tools/`，MIT。
- 本项目脚本：GPL-2.0-only。

不是小米、Kali 或上游项目的官方支持版本。
