# 构建、部署与回退

仅针对 `sheng`。版本基线见 [HARDWARE.md](HARDWARE.md)，实际验收见 [VALIDATION.md](VALIDATION.md)。仓库无需连接作者设备、无需作者 `.work/`，也不包含预构建全量镜像或私有软件。

## 分层与依赖

```text
Linux 构建机 → build-kali.sh → boot / sparse rootfs / manifest
                                ↓ 首启并验收
Kali ARM64 / 匹配内核 → PIN 驱动+认证 / 热点 / 音频 / 电源
                                ↓ 同一 Plasma/Qt ABI
Plasma Wayland → KWin 效果+手势 / desktop-policy+隐私 / 控制中心
                                ↓ 用户会话配置
主题/面板/天气 → 可选 Burp 参数 / 实验水杉输入法
```

`build-kali.sh` 已安装基础 KDE、触屏、USB网络/串口、固件、GPU监控、swap、热点后端、基础软键盘和电源脚本。它**尚未自动集成**下面的 PIN 修复包、原生热点面板补丁、定制控制中心、KWin 效果、隐私/桌面策略和完整主题。不要把旧导出镜像当作当前实机全量备份。

## 基础镜像

1. 使用 Linux root、debootstrap、ARM64 binfmt/QEMU，依赖安装命令见根 README。若在 Windows，请使用 Linux 虚拟机；不要在 PowerShell 直接运行 chroot/mount。
2. `sudo bash scripts/build-kali.sh`。默认 `BUILD_DIR=.work/build`、`ASSET_DIR=.work/assets`、`OUT_DIR=out`、`IMAGE_SIZE=16G`，可通过环境变量覆盖。指定新的构建目录可避免覆盖；`RESUME=1` 只恢复已经确认的 Kali ARM64 构建。
3. `python3 scripts/validate-images.py out`。输出包括 boot、sparse rootfs、manifest、`packages.tsv`、`validation.txt`。固定硬件来源和 SHA 在 [sources.json](../configs/sources.json)；rolling 软件源本身不构成软件包快照。
4. 默认 kali/kali、自动登录、USB SSH。自定义密码通过环境变量传入，不写进脚本；首启修改密码。导出会清空 machine-id 和 SSH host keys，目标首启生成自己的身份。

GitHub Actions 的基础镜像和历史 postmarketOS 构建都只手动触发。普通推送只运行源码检查；Actions artifact 有保留期限，不是长期镜像发行承诺。

## 刷写与首启

先完成目标识别、独立数据备份、Bootloader 解锁和明确的 userdata 清空授权。Windows 主机需可用 adb/fastboot；Linux 脚本支持 `SERIAL`、`FASTBOOT`、`OUT_DIR` 环境变量。

```powershell
adb reboot bootloader
python scripts/validate-images.py out
.\scripts\flash-kali.ps1 -ImageDirectory .\out -EraseUserdata
```

```bash
# Linux 主机；仅在已同意清空目标设备后执行
OUT_DIR=out bash scripts/flash-kali.sh --erase-userdata
```

| 对象 | 操作 |
| --- | --- |
| `userdata` | 覆盖为 Linux ext4 根分区，Android 数据全部丢失 |
| `boot_b` | 写入 sheng 专用内核 |
| `dtbo_b` | 清除，为该主线内核使用 |
| 活跃槽位 | 切至 B，重启 |
| A 槽 boot/dtbo、recovery | 脚本不写入，但不能恢复已覆盖 userdata |

Windows 使用 256 MB 分块，部分写入可能较久。保留 `flash-record.json` 与日志，不在没有明确报错时中断写入。脚本检查设备、解锁状态、分区大小、manifest/哈希；不得跳过这些检查。

首启后检查 `uname -m` 为 aarch64、`dpkg --print-architecture` 为 arm64、`/etc/os-release` 为 Kali，确认 Plasma Wayland 与触屏。USB RNDIS 默认平板 `192.168.77.1`，主机 DHCP；SSH `ssh kali@192.168.77.1`。USB CDC ACM 串口可作备用诊断入口。`scripts/verify-device.py` 使用 Paramiko，首次应通过可信渠道核对主机指纹，报告存本地 `out/`。

## 增量组件部署

下列命令除注明外在 **ARM64 平板 Linux** 的仓库根目录执行；用户会话命令不要用 sudo。先备份 `~/.config/kwinrc`、`kglobalshortcutsrc`、`plasma-org.kde.plasma.desktop-appletsrc`、`plasmashellrc`、`kdeglobals`、`kcminputrc`、`kscreenlockerrc`。不要复制其他人的完整 HOME。

### 1. PIN 键盘与热点面板

PIN 先读 [驱动说明](../device/keyboard-driver/README.md)：

- 精确内核源码 `ianchb/sm8550-mainline@87ac0f2347eb433933841e6854950dd90e96e6b2`、运行内核配置和 Clang 21.1.8-13；在源码根应用驱动 patch，执行 `make LLVM=-21 olddefconfig prepare modules_prepare`，编译相应模块。
- `CONFIG_MODVERSIONS=n` 仍需匹配导出符号/配置。没有完整的精确构建树与符号表时不能强行加载；本仓库目前没有一键重建该模块的完整工具链封装。
- 认证使用 `ianchb/sheng_devauth@bac03b5bcfefa1467ebad490edd910a6cef8a207`，应用 [service-fixes.patch](../device/keyboard-auth/service-fixes.patch)，遵循上游构建并链接其授权的依赖。
- `bash scripts/build-dock-fix-package.sh MODULE AUTH_BINARY "$PWD" out/packages` **仅打包已编译、已验 ABI 的产物**。安装后用 `modinfo`/服务状态及真实输入验收，不重绑整条 I²C/TEE 链路。二进制依赖许可需另行确认。

热点后端已在基础镜像安装，SSID/随机新密码位于 `/etc/sheng-hotspot/`，不会从本仓库获取作者密码。`sudo systemctl start sheng-hotspot.service` 开启，`stop` 关闭；本地查看 `/etc/sheng-hotspot/access.txt`，不要提交该文件。热点使用 `sheng-ap` 虚拟 AP、hostapd、dnsmasq 和专用 nftables 表，保留原 wlan 上网连接。默认关闭，必须用另一设备连接并确认互联网访问。

原生状态栏按钮需 [hotspot-panel](../device/hotspot-panel/README.md)。从固定 `KDE/plasma-nm@b6c03fe24b30d2a963a41dd83784e36086d7257e` 获取源码并应用 `applet.patch`；将该源码的 `applet/` 与本仓库该目录的 CMake/controller 文件组成独立源码根，安装相同版本的 Plasma/NetworkManagerQt 开发依赖，用 CMake/Ninja 编译 applet，保留系统网络管理库。打包：

```bash
bash scripts/build-hotspot-panel-package.sh /path/to/org.kde.plasma.networkmanagement.so "$PWD" out/packages
```

这个打包器不编译 applet。绑定 `plasma-nm=4:6.7.4-2+b1`，新版本需要重新移植并构建，不能禁用依赖检查直接覆盖。新会话再加载 applet；不要为发布文档强制退出当前桌面。

### 2. 任务效果、原生三指切窗

```bash
sudo apt-get install -y build-essential pkg-config libinput-dev libudev-dev
mkdir -p out/bin out/packages
g++ -std=c++17 -O2 -Wall -Wextra -Werror device/recents/gesture-bridge.cpp \
  -o out/bin/sheng-task-gestures $(pkg-config --cflags --libs libinput libudev)
python3 device/recents/build-device-package.py out/bin/sheng-task-gestures out/packages/sheng-task-gestures_1.0-1_arm64.deb
sudo apt-get install ./out/packages/sheng-task-gestures_1.0-1_arm64.deb
python3 scripts/build-task-cards.py --install
python3 device/recents/install-native-tabbox.py
```

任务效果构建器打印带源码散列的新插件 ID 和启用命令，按其输出以当前用户启用；升级先停用旧 ID，不能同时加载多个副本。停用原生 Overview，避免手势/Meta+W 冲突；系统设置中保留一个虚拟桌面，将其他桌面的窗口先归并后删除桌面。切窗桥接服务、udev、D-Bus 降权路径针对 `kali`/UID 1000，其他用户需要一起修改。独立三指上下没有动作；进入 Alt+Tab 后才允许四向选择。

### 3. 桌面策略与隐私

```bash
gcc -std=gnu11 -O2 -Wall -Wextra -Werror device/privacy/device-guard.c -o out/bin/sheng-privacy-bpf
sudo out/bin/sheng-privacy-bpf probe
python3 device/desktop-policy/build-device-package.py out/bin/sheng-privacy-bpf out/packages/sheng-tablet-controls_1.0-6_arm64.deb
sudo apt-get install ./out/packages/sheng-tablet-controls_1.0-6_arm64.deb
```

包安装用户会话服务、隐私过滤器及桌面手势部件；还需将 `org.sheng.desktop-gesture` 添加到桌面，并加载上一步 KWin 效果（其 `DesktopPolicy.qml` 通知最大化/全屏）。Dock 按 `ShengThemeRole=dock` 或底部任务面板识别，不依赖作者面板 ID。

使用当前 Linexin Dock/抽屉时，先完成下面的主题面板，再按[抽屉专用说明](DESKTOP_DRAWER.md)构建启动器、运行迁移助手和编译原生桌面触控插件；助手自动添加手势部件、备份和迁移固定项。原生插件必须与当前 KWin/Qt ABI 匹配，它同时负责防框选和真正全屏抽屉上的 Dock 叠层；仅安装 QML 不够。

隐私开关默认为允许访问；先读 [拦截范围](../device/privacy/README.md)。root 运行 `/usr/libexec/sheng-privacyctl off` 可恢复；本地活跃用户通过 `sheng-privacy on/off` 请求有限权限。冻结既有采集进程可能暂停整个相关应用，验收使用测试进程。

### 4. 控制中心

构建主机或平板需 Python 3 和 Git，无需本地秘密缓存：

```bash
python3 scripts/build-control-center.py
# 以下以平板桌面用户执行
kpackagetool6 --type Plasma/Applet --install out/packages/sheng-control-center.plasmoid
# 已安装时使用 --upgrade
```

构建器按固定提交下载上游，校验 archive 和 patch 哈希，应用 patch、复制 QML/SVG，保留许可证，生成本地 manifest。添加 `org.kontrol.center` 到**顶部状态栏**，以便找到同一窗口中的时钟/托盘；即使点击入口隐藏，部件仍须存在。加载后验证右侧下滑、普通区域上滑与滑条/列表例外。隐私按钮依赖上一包，热点依赖基础服务。

### 5. 主题、布局与天气

[theme/README.md](../device/theme/README.md) 记录组件版本、壁纸来源及天气补丁。安装相应 Panel Colorizer（含匹配 Qt/Plasma 的 C++ 插件）、Colloid-Light、Redmi Clock 后，在用户会话通过 Plasma 脚本接口执行 `device/theme/layout.js` 作为布局种子，或手动建立等价面板。

当前配置、插件角色、显示模式和有效全局样式见[桌面配置同步](DESKTOP_PROFILE.md)及其 JSON 快照；按本机部件重新映射，不复制作者的实例 ID。导出脚本只读，校验器无需连接设备。

该脚本会迁移现有任务面板并创建顶栏，**不是可重复执行的配置管理器**；先备份并读取脚本，已存在 Sheng 顶栏时它会停止。默认壁纸路径需先放置你有权使用的图片，或改成自己的路径。不要从作者设备导出整份配置。

在系统设置选择 BreezeLight、Breeze 样式、Colloid-Light、Breeze_Light 24px；关闭壁纸强调色，设置内屏 200% 缩放。Panel Colorizer：顶栏 ChromeOS 预设关闭背景，普通部件和托盘前景白色；Dock 使用 Translucent；按新 widget ID 将电池图标设为白色符号遮罩。配置未全部自动化，须人工/AI检查。`WeatherData.qml` 替换 Redmi Clock 对应组件，再在其根目录应用 `weather-ui.patch`。

当前两段底边唤出、独立电池图形、圆角 Burp 图标、锁屏上滑和缺字修复，按[触控/字体增量说明](TOUCH_LOCKSCREEN_FONTS.md)部署。基础构建已补 Noto/Liberation 正文字体与 MDI ASCII 过滤配置，但完整 rootfs 未在本轮重新构建；锁屏 patch 和桌面部件仍为单独增量。

### 6. 可选应用与实验输入法

Burp 官方安装及 6 GiB/170%/OpenGL 参数见 [burp-tablet.md](burp-tablet.md)。水杉/Fcitx5 OSK 的固定来源与未完成验收见 [input-method](../device/input-method/README.md)，不能作为默认稳定安装步骤。安装新输入法前保留可用的 Plasma Keyboard 回退入口。

实验 [FUTO Linux 移植](../device/futo-keyboard/README.md)需要用 `--futo-ui` 构建并安装 `sheng-msime-integration 0.2.1-8`，再编译原生英文词典/候选模块、准备原版图标/字体/布局并执行用户级 setup。核心 UI/UX 通过 Rust 原生渲染；FUTO 的非商业 Source First 许可、实际范围与回退单独记录。未移植完整 Android 应用、滑行或语音，不替换水杉中文引擎。不要将仅打包 `.deb` 等同于已完成 C++ 构建。

## 回退与故障定位

| 层 | 诊断/回退 |
| --- | --- |
| 无法启动 | fastboot 检查槽位；必要时 `fastboot set_active a`、`fastboot reboot recovery`。恢复 Android 需本机型原厂固件/recovery 重建 userdata，会删除 Kali；A 槽不是用户数据备份 |
| PIN | 查看 `modinfo`、`journalctl -u sheng-devauth`、只读握手计数；卸载修复包后重装匹配原内核包，不能只删除唯一模块 |
| 热点 | `journalctl -u sheng-hotspot`、`iw dev`、专用 nft 表；停服务后重新测试原 wlan 上网，勿 flush 全局防火墙 |
| 网络 applet | 卸载补丁并重装匹配 plasma-nm，下一次会话加载原版 |
| 三指 | 停止 `sheng-task-gestures`，停用本 KWin 效果并恢复备份；bridge 退出会释放虚拟 Alt |
| 隐私 | `sudo /usr/libexec/sheng-privacyctl off`，核对冻结进程恢复后再卸载 |
| 桌面 | 使用自己部署前的备份恢复；作者 `restore.py` 的备份路径不适用于新设备 |

部署完成按 [验证清单](VALIDATION.md) 逐项验收。保留新设备日志于本地，公开 issue 使用去敏摘要。
