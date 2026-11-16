# Kali 侧怎么用上我们自己的内核

> 目标：Kali 镜像不再消费第三方的 `linux-image-*.deb` 和 `boot.zip`，整条链只吃
> `kernel.yml` 的产物 + upstream 的 Kali 用户态。
> 现状：脚本已接好（`PIANO_KERNEL_DIR`），等 P2/P3 的内核在真机上过验收后切默认。

## 1. 三层怎么拼

```
kernel.yml (ubuntu-24.04-arm, LLVM=1)
  └─ Image / sm8750-piano.dtb / modules/ / kernel-release / config   ← artifact
        │
        ▼
build.yml  (download-artifact, run-id 指向一次成功的 kernel 跑批)
  └─ scripts/build-kali.sh   PIANO_KERNEL_DIR=<artifact>
        ├─ modules → rootfs /lib/modules/<krel>  + depmod
        ├─ mkinitramfs → /boot/initrd.img-<krel>
        └─ scripts/mk-bootimg.sh → boot.img / init_boot.img / vendor_boot.img
```

`build-kali.sh` 里的分支：**有 `PIANO_KERNEL_DIR` 就走自建**；没有就退回旧的
第三方 `boot.zip` 路径（保留只是为了能在内核还没验收时继续造镜像，P4 完成后删掉）。

## 2. 三个镜像怎么生成

| 镜像 | 内容 | 依据 |
|---|---|---|
| `boot.img` | `Image` + 我们的 initramfs（gzip），cmdline `root=PARTLABEL=linux_rootfs rootwait ro console=ttyMSM0,115200n8` | 原厂 boot 就是 header v4、kernel 36.8 MB、cmdline 为空（`KERNEL-TRUTH.md` §1.2）；cmdline 我们自己在 boot 里写 |
| `init_boot.img` | **空 ramdisk** 的合法 header v4 镜像 | Android 13+ 的 bootloader 会把 init_boot 的 ramdisk 和 boot 的拼一起；留空的才能保证跑的是我们的 `/init` |
| `vendor_boot.img` | `sm8750-piano.dtb` + 空 vendor ramdisk + `androidboot.hardware=qcom` | 原厂 vendor_boot 就是「DTB + ramdisk + bootconfig」三段（§1.4） |

不签 AVB：设备 `verifiedbootstate=orange`，原厂 boot 的签名我们不碰也不伪造；
刷的是我们自己的分区，vbmeta 一律不动。

## 3. initramfs 里必须有的东西

`mkinitramfs` 在 chroot 里跑，用的是 **rootfs 里已装好的模块**，所以：

- `depmod -a <krel>` 必须先生效，否则 initramfs 里没有 ufs/phy 之类；
- `MODULES=most`（Debian 默认）够用，但要把 `ufs_qcom`、`phy-qcom-ufs`、
  `pinctrl-sm8750`、`clk` 相关留在 initramfs 里（`/etc/initramfs-tools/modules`）；
- `root=PARTLABEL=linux_rootfs` 依赖 udev 生成 `/dev/disk/by-partlabel`，
  Kali 的 initramfs-tools 自带，不需要自己写 busybox init。

如果哪天要一个不依赖 udev 的最小 initramfs，再补 `scripts/mk-initramfs.sh`
（busybox + 扫 `/sys/class/block/*/uevent` 找 PARTNAME），现在没必要。

## 4. 固件

内核驱动要的 blob（ath12k、adsp、gmu/zap）来自原厂 `/vendor/firmware`，
属于「设备真值」，不是代码：

```bash
# 从备份的 firmware_mnt.tgz / vendor-firmware.tgz 解出来
tar xzf firmware/vendor-firmware.tgz -C "$ROOTFS/lib/firmware"
tar xzf firmware/firmware_mnt.tgz  -C "$ROOTFS/lib/firmware"
```

ath12k 需要的是 **linux-firmware 格式**（`ath12k/WCN7850/hw2.0/*`），厂商分区里是
qca_cld 格式，两者不通用 —— P3d 会补 `linux-firmware` 包或自带 blob。

## 5. 怎么跑一次

1. Actions → **kernel** → Run workflow（等它绿，拿到 run id）。
2. Actions → **Build Kali for Xiaomi Pad 8 Pro (piano)** → Run workflow，
   `kernel_run_id` 填上一步的 run id（留空 = 回退第三方）。
3. 产物里 `boot.img` / `init_boot.img` / `vendor_boot.img` 就是我们的内核了。

真机第一次验证**不要刷**，先：

```bash
fastboot boot boot.img        # 只起一次，不写分区
```

看串口/`dmesg` 确认 UFS、显示、触摸起来之后再 `flash-piano.sh`。

## 6. 还差的（按顺序）

1. **P2**：DTB 编译通过（CI 正在验证）→ 真机 `fastboot boot` 能看到 UFS 和屏。
2. **P3a**：面板驱动 + 背光 → 有画面。
3. **P3b**：Novatek SPI 触摸 → 能操作。
4. **P3c/d**：GPU 节点、ath12k 固件 → 桌面流畅 + 联网。
5. **P4**：`mk-bootimg.sh` 进 CI 自动跑；`build.yml` 默认 `kernel_run_id` 必填；
   删掉第三方 fallback 与 `sources.json` 里的上游 deb 条目。

## 7. 已知缺口：OSK 集成包没进镜像构建

`device/input-method/build-device-package.py` 才会安装
`/usr/libexec/sheng-msime-launcher`、`/usr/share/applications/sheng-msime-fcitx5.desktop`
和 `/usr/bin/sheng-osk-mode`；`scripts/build-kali.sh` 目前只调了 `scripts/build-osk.sh`
（二进制 + 布局），**没有打包这一步**，所以新装的系统会出现「KWin 有输入法但 OSK 起不来」。
P4 要在 OSK 段后补：

```bash
python3 device/input-method/build-device-package.py \
    .work/osk/stage scripts/keyboard-policy.py \
    out/packages/sheng-msime-integration_1.0-1_arm64.deb
chroot "$ROOTFS" dpkg -i /tmp/sheng-msime-integration_1.0-1_arm64.deb
```

另一个坑：`scripts/osk-mode.py` 必须在**已登录、未锁屏**的会话里以桌面用户跑一次
（`osk-mode.py dock --sheng-ui`），否则 `~/.config/fcitx5-osk/config.toml` 里
`default_landscape_layout` 是空字符串，OSK 起来也没布局。
