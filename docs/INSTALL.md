# 安装 Kali 到 Xiaomi Pad 8 Pro（piano）

本文件随发布产物一起分发。所有写入操作都在你的平板上执行，**会清空 Android 用户数据**。

## 0. 准备

- 平板：`piano` / `25091RP04C`，已解锁 Bootloader，电量 ≥ 40%。
- 主机：`adb`、`fastboot`、`zstd`、`python3`。
- 已下载本目录全部文件，并在目录内执行 `sha256sum -c SHA256SUMS`。
- **先确认你能恢复**：会 `fastboot flash boot` 和 `fastboot boot`，出问题时长按电源 + 音量下进 Fastboot 即可重刷。

## 1. 备份（强烈建议）

Android 还在的时候，至少保住这些分区，刷坏了能回原厂：

```bash
adb -s <SERIAL> shell su -c 'dd if=/dev/block/by-name/boot_a of=/sdcard/boot_a.img'
adb -s <SERIAL> shell su -c 'dd if=/dev/block/by-name/init_boot_a of=/sdcard/init_boot_a.img'
adb -s <SERIAL> shell su -c 'dd if=/dev/block/by-name/vendor_boot_a of=/sdcard/vendor_boot_a.img'
adb -s <SERIAL> pull /sdcard/boot_a.img .
adb -s <SERIAL> pull /sdcard/init_boot_a.img .
adb -s <SERIAL> pull /sdcard/vendor_boot_a.img .
```

`ipados`（UniXNU 的 32 GiB）不要动，也不要在本项目里备份或恢复它。

## 2. 解压镜像

```bash
zstd -d root.sparse.img.zst -o root.sparse.img
sha256sum -c SHA256SUMS
```

## 3. 进 Fastboot

```bash
adb -s <SERIAL> reboot bootloader
# 或长按 电源 + 音量下
fastboot -s <SERIAL> getvar product      # 预期 product: piano
fastboot -s <SERIAL> getvar current-slot # 预期 current-slot: a
```

## 4. 刷写

```bash
bash flash-piano.sh --serial <SERIAL> --dir . --yes
```

等价于：

```bash
fastboot -s <SERIAL> flash boot boot.img
fastboot -s <SERIAL> flash init_boot init_boot.img
fastboot -s <SERIAL> flash vendor_boot vendor_boot.img
fastboot -s <SERIAL> erase userdata
fastboot -s <SERIAL> flash userdata root.sparse.img
fastboot -s <SERIAL> reboot
```

- `Sending`/`Writing` 每行都要 `OKAY`；`erase userdata` 可能要几十秒。
- 写入过程中不要拔线、不要断电。

## 5. 首次启动

- 约 1 分钟进 SDDM，自动登录 `kali`（密码 `kali`）。
- 根文件系统会在首启自动 `resize2fs` 到整个 `userdata`。
- 触屏：首启服务从原厂 `odm` 分区提取标定到 `/etc/piano/thp-calibration.json`。没触屏时用磁吸键盘 / USB 键鼠：
  ```bash
  sudo systemctl status piano-thp-calibrate piano-thp
  ls /sys/class/misc/nvt-thp-*/device/panel_vendor
  ```
- 改密码：`passwd`
- 打开 USB 网络 + SSH（上游工具）：`sudo piano-devmode on`
- 回 Fastboot：`sudo piano-reboot-bootloader`

## 5a. `ipados` 分区（UniXNU）怎么对待

- 大小固定 32 GiB（`34,361,815,040` 字节），布局：前 ~9.38 GB 是 UniXNU 根映像，**12 GiB 偏移处**是 160 MiB 的 `payload.img`，其余留给 Data 卷/以后 macOS。
- 本项目的刷机脚本只写 `boot_<slot>`、`init_boot_<slot>`、`vendor_boot_<slot>`、`userdata`，不碰 `ipados`；脚本开刷前会打印它的分区大小供你核对。
- Kali 里 `ipados` 不带 `/etc/fstab` 条目，`systemd.gpt_auto=0`，另加 udev 规则把 `UDISKS_IGNORE=1` / `SYSTEMD_READY=0`，Dolphin 不会提示挂载，也不会自动 fsck。
- 需要换 UniXNU payload 时在 Kali 里用内置工具，只写那 160 MiB 窗口：

  ```bash
  sudo piano-ipados status              # 大小、两段 sha256
  sudo piano-ipados verify payload.img  # 与设备上现有内容比对
  sudo piano-ipados write payload.img   # dd 到 block 3145728，写完 fsync
  sudo piano-ipados dump old.img        # 备份现有 payload
  ```

## 6. 和 UniXNU 来回切

```bash
# Kali → UniXNU
sudo piano-reboot-bootloader
fastboot boot /path/to/unixnu/boot.img

# UniXNU → Kali
# 在 Fastboot 里直接重启，A 槽仍是 Kali
fastboot reboot
```

`ipados` 分区只属于 UniXNU 的 payload，本项目不读不写。

## 7. 恢复 Android（可选）

用第 1 步备份的三个镜像：

```bash
fastboot -s <SERIAL> flash boot boot_a.img
fastboot -s <SERIAL> flash init_boot init_boot_a.img
fastboot -s <SERIAL> flash vendor_boot vendor_boot_a.img
fastboot -s <SERIAL> erase userdata
fastboot -s <SERIAL> reboot
```

`userdata` 里的 Android 数据已经没了，恢复的是可以重新初始化的 Android 系统。

## 排错

| 现象 | 处理 |
| --- | --- |
| 黑屏无输出 | 长按电源 15 s → 电源 + 音量下进 Fastboot，`fastboot reboot` 回 Kali |
| 卡在 initramfs / 找不到根 | cmdline 必须是 `root=PARTLABEL=userdata`；确认刷的是本包的 `boot.img` |
| 没有触屏 | 看第 5 节，检查 `/etc/piano/thp-calibration.json` |
| Wi-Fi 不能连 | `sudo systemctl status NetworkManager`；上游固件在 `piano-local-firmware` |
