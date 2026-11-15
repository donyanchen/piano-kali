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
