# Kali Linux for Xiaomi Pad 8 Pro (`piano`)

在小米平板 8 Pro（`piano` / `25091RP04C`，骁龙 8 至尊版 SM8750）上跑原生 **Kali Linux ARM64 + KDE Plasma Wayland**，内核由本项目自己从 upstream 构建。

## GPU 长时间卡顿候选修复

当前 kernel 工作流使用 `v7.4-rc3`、固定 piano 来源和单独校验的 MSM 回收/同步补丁。
候选 ABI 为 `-piano9`，重建完整匹配模块，并生成 Image/config/DTB 的来源与哈希清单。
源码应用检查已通过，完整编译和真机回归分别记录，不把源码检查当作已修复硬件。
方法与回退见 [GPU-RECLAIM.md](docs/GPU-RECLAIM.md)。

## 仓库结构：两条独立流水线

| 线 | 目录 / 工作流 | 来源 | 触发 |
|---|---|---|---|
| **内核** | `kernel/`、`.github/workflows/kernel.yml`、`docs/GPU-RECLAIM.md` | upstream `v7.4-rc3` + 固定 piano 回放 + 两项 MSM 回收修复 | 手动；GPU 修复专用分支按受限路径触发 |
| **Kali** | `device/`、`scripts/`、`docs/`（sheng 那批）、`.github/workflows/build.yml` | 1:1 同步 sheng-kali-linux（`scripts/sync-sheng-base.sh`） | 手动 / 每周同步 |

两条线的唯一接口是 `scripts/build-kali.sh` 的 `PIANO_KERNEL_DIR`：Kali 镜像构建时把内核
artifact 拿过去装模块、做 initramfs、拼 boot 三件套。除此之外互不依赖，改内核不会动 Kali 用户态，
同步 Kali 也不会动内核（`.sheng-sync-exclude` 里锁死了）。

## 三条来源原则

| 层 | 来源 | 说明 |
|---|---|---|
| 内核 / 设备树 | upstream `v7.4-rc3` + `yzddmr6/linux-sm8750-piano@1c21cb9895d69c1c5e83ceae68952fedf522644a` + [固定回收补丁](kernel/patches/README.md) | Actions 回放源码并合并其九个配置片段；`kernel/configs/piano.config` 是早期记录，不是当前工作流输入 |
| Kali 用户态 | **1:1 复刻 [sheng-kali-linux](https://github.com/LuKeyC-NetSEC/sheng-kali-linux)**，按 piano 换设备值 | `scripts/build-kali.sh` + `device/` + `docs/` |
| 参考（**不作代码来源**） | [xiaomipad-8pro-mainline](https://github.com/yzddmr6/xiaomipad-8pro-mainline) | 只用来对照行为，不 clone、不 cherry-pick、不复制 DTS/驱动 |

判断依据一律是**设备真值**：原厂 `boot_b` / `vendor_boot_b` / `dtbo_b` 与运行态 DTB，逐项记录在 [docs/KERNEL-TRUTH.md](docs/KERNEL-TRUTH.md)。

## 现在到哪一步了

| 阶段 | 状态 |
|---|---|
| P0 取证 | ✅ `docs/KERNEL-TRUTH.md`（原厂三件套解包、8 个 base DTB、1 条 piano overlay、硬件清单） |
| P1 差距矩阵 | ✅ `docs/KERNEL-GAP.md`（mainline v7.3 支持度、自写面、v1 边界） |
| P2 设备树 | 🚧 `kernel/dts/sm8750-piano.dts` v0（显示/触摸/键盘/键/背光/UFS/USB/PCIe），CI 编译验证中 |
| P3 驱动缺口 | ⏳ 面板、FS19xx 功放、Novatek SPI 触摸、GPU 节点、WCN7850 固件 |
| P4 打包 | ⏳ 自建 `Image`+`dtb`+`modules` → 自己的 `boot.img`/`vendor_boot.img`，deb 交给 `build-kali.sh` |

> `scripts/build-kali.sh` 现在仍按旧流程消费第三方的 `linux-image-*.deb`；P4 会把它换成我们自己的 deb。这是仓库里最后一处第三方依赖，替换前不会被删。

## 这台机器的真值（摘要）

| 项 | 值 |
|---|---|
| 屏幕 | 双 DSI，单边 1600×2136 → **3200×2136**，120/144/90 三套时序，DSC + video mode |
| 面板 | `p81_35_02_0b`（备选 `p81_42_02_0a`），亮度 0–0xfff，两颗 `ktz8866` 背光 |
| 触屏 | Novatek **SPI**（`novatek,NVT-ts-spi`），需 `invert_y` |
| 音频 | 4× `foursemi,fs16xx` @ I2C 0x34–0x37，单条 **TDM 4 slot**；WSA884x 那条路在官方 DT 里是关的（`wsa-max-devs = 0`） |
| 键盘 | 磁吸 `nanosic,803` @ I2C 0x4c，纯 HID |
| 存储 | UFS 4.0，跑在 **MCQ** 模式（DT 里带 `mcq_sqd`/`mcq_vs`） |
| Wi-Fi/BT | WCN7850（`cnss-peach`）走 PCIe0 |
| GPU | Adreno 830（`0x44070001`，8xx Gen2） |
| 槽位 | `_b`（`boot_b`/`init_boot_b`/`vendor_boot_b`），`verifiedbootstate=orange` |
| 根分区 | `userdata` 改名 `linux_rootfs`，cmdline `root=PARTLABEL=linux_rootfs` |

## 构建

### 1. 内核（Actions）

**Actions → kernel → Run workflow**（或直接 push `kernel/**`）。

流水线做的事：固定 piano 源码回放到 `v7.4-rc3` → 校验并应用两项 MSM 回收修复 → 保留 chip-ID 修正 → 合并固定配置与 piano9 ABI → 编译 `Image`/`dtbs`/`modules` → 沿原有流程准备启动 DTB → 记录来源、哈希并上传 artifact。

产物：`Image`、`sm8750-piano.dtb`、`modules/`、`config`、`kernel-release`、`gpu-reclaim-fixes.json` 和 `kernel-build-manifest.json`。正常安装使用完整模块构建，先按清单核对实际运行镜像。

### 2. Kali 根文件系统（Actions）

**Actions → Build Kali for Xiaomi Pad 8 Pro (piano) → Run workflow**。

debootstrap 造 Kali ARM64 根文件系统、装 KDE 与 Kali 工具、打包 sparse 镜像。可选 Secret：`KALI_PASSWORD`、`THP_BOE_B64` / `THP_CSOT_B64`（触摸标定）。

产物：

```
root.sparse.img.zst      Kali 根文件系统（ext4，20 GiB 起始，首启扩到整个 userdata）
boot.img                 Image + DTB，cmdline root=PARTLABEL=linux_rootfs
init_boot.img            第一段 init（Android 原厂格式）
vendor_boot.img          设备树 + 模块 + initramfs
flash-piano.sh           刷写脚本
INSTALL.md / SHA256SUMS
```

## 安装

主机需要 `adb`、`fastboot`、`zstd`。

```bash
zstd -d root.sparse.img.zst -o root.sparse.img
fastboot devices
bash flash-piano.sh --serial <SERIAL> --dir . --yes
```

顺序：`boot` → `init_boot` → `vendor_boot` → `erase linux_rootfs` → `flash linux_rootfs`。**不要**写 `_b` 槽以外的槽、不要 `--set-active`、不要刷 `vbmeta`/`dtbo`。

> ⚠️ 只适用于已解锁 Bootloader 的 `piano`。首次安装会**清空 Android 用户数据**（本方案是 Kali-only）。`ipados`、`vbmeta`、`dtbo`、`persist`、基带/标定分区一律不碰。

## 和 UniXNU 的关系（能兼容）

| | Kali（本项目） | UniXNU |
|---|---|---|
| 常驻内容 | `linux_rootfs` 分区里的根文件系统 | `ipados` 分区（32 GiB）里的 `payload.img` |
| 启动方式 | 正常开机，ABL 从当前槽起 | `fastboot boot boot.img`，纯 RAM 启动，不写分区 |

Kali 里 `adb reboot bootloader`，主机 `fastboot boot <unixnu>/boot.img` 进 UniXNU；重启回 Fastboot 再 `fastboot reboot` 回 Kali。`ipados` 分区本项目一个字节都不写。

## 首次启动

- 自动登录 `kali` / `kali`（SSH 同账号，root 禁止登录），登录后立刻改密码。
- 根文件系统自动扩到整个 `linux_rootfs`。
- 触屏标定：`piano-thp-calibrate` 从原厂 `odm` 读 `piano_nova_*_thp_config.ini`，按面板类型（csot/boe）写 `/etc/piano/thp-calibration.json`；失败时先用磁吸键盘或 USB 键鼠。
- 回 Fastboot：`sudo piano-reboot-bootloader` 或长按电源 + 音量下。

## 已知限制

- 手写笔、指纹（TEE 侧，AP 无节点）不做。
- 充电：v1 只做 UCSI 基础（能充、能读电压电流），PPS 曲线后置；厂商 `mca` 框架不移植。
- 相机、NFC、无线充、触觉：不在范围内。
- 构建成功 ≠ 真机可用：每个驱动都要按 `docs/KERNEL-GAP.md` §7 的验收门逐条过，刷机前确认你能用 `fastboot boot` 恢复。

## 许可

- 内核：GPL-2.0-only（upstream + 本项目补丁）。
- Kali 用户态脚本思路来自 [sheng-kali-linux](https://github.com/LuKeyC-NetSEC/sheng-kali-linux)（GPL-2.0-only）。
- `vendor/extract-thp-calibration.py`：来自上游 `tools/`，MIT。

不是小米、Kali 或任何上游项目的官方支持版本。
