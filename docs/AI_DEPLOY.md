# 使用 AI 部署 Sheng Kali Linux

本指南面向可执行终端命令的 AI 编程助手及负责验收的开发者。目标是分阶段、有证据地部署 `sheng`，不是把其他机型套用本仓库分区表。先读 [部署手册](DEPLOYMENT.md) 与 [硬件矩阵](HARDWARE.md)。

## 可直接交给 AI 的提示词

```text
请基于 https://github.com/LuKeyC-NetSEC/sheng-kali-linux 部署原生 Kali ARM64/KDE。
先读仓库 AGENTS.md、docs/DEPLOYMENT.md、docs/DESKTOP_AND_INTERACTIONS.md
和 docs/VALIDATION.md，检查当前代码及固定来源，不依赖作者 .work 或 out 目录。

首先只读识别已连接的设备、Bootloader 状态、分区/槽位与现有系统；
核对必须是 Xiaomi Pad 6S Pro 12.4 / sheng，并记录内核与 Plasma ABI。
先备份及准备镜像、manifest 和恢复方案。未取得清空 userdata 的明确授权前不要刷写。
已有明确授权时继续执行，不反复请求同一确认。

按“基础镜像 → 硬件修复 → 桌面增量 → 可选实验输入法”逐步部署。
每一步记录改动、版本、验收与回退；不要为检查关闭用户应用或绕过锁屏。
从源码构建缺失产物，遇到 ABI/源码缺口如实报告，不拿其他版本二进制替代。
最终依据 docs/VALIDATION.md 验收，区分命令检查、实机测试和用户确认。
交付去敏日志与仍未支持项，不把当前设备的账户、token、Wi-Fi 密码或用户目录上传。
```

## 阶段 1：识别与备份

主机上运行 `adb devices -l` 或 `fastboot devices`；多台设备连接时先隔离目标，不猜测序列号。Android 模式只读查看 `adb shell getprop ro.product.device`。fastboot 模式只读查看 product、unlocked、current-slot 及相关分区大小；以刷写脚本实际使用的命令为准。

如果已经在 Linux 中运行，先检查：

```bash
cat /etc/os-release
uname -a
dpkg --print-architecture
cat /sys/firmware/devicetree/base/model
lsblk -o NAME,SIZE,FSTYPE,LABEL,PARTLABEL,MOUNTPOINTS
dpkg-query -W plasma-workspace plasma-nm linux-xiaomi-sheng
```

将重要数据备份到独立介质，确认可读。分开备份桌面配置、网络/应用数据与原厂恢复资料；秘密备份保留在本地。不能从“平板连接电脑”推断 Bootloader 已解锁，也不能从“可以清数据”推断可以刷另一台设备。

## 阶段 2：构建与静态校验

克隆仓库并记录提交。运行源码检查；Linux 环境按部署手册构建。下载固定的硬件依赖并验证 SHA-256，保留本次 `packages.tsv`。构建目录已有镜像时换新目录；`RESUME=1` 只用于同一已确认的 Kali ARM64 构建。

执行 `validate-images.py`，检查 boot/rootfs/manifest。校验通过只说明产物满足脚本规则，不说明触屏、Wi-Fi、音频已经工作。**不要将作者历史实机成绩登记为本次设备的验收。**

## 阶段 3：具体刷写授权与启动

列出目标设备、机型、槽位，以及 `userdata`、`boot_b`、`dtbo_b` 的变更影响。用户明确允许清空后使用仓库刷写脚本；不要改写成全盘 erase 或擦除 recovery。已授权具体擦写影响时不必再问一次。

刷写过程中保留日志，错误即停止后续写入；等待真实 fastboot 成功结果。首启验证 aarch64/arm64、Kali、Wayland、触屏及 USB 入口。进入桌面后立即修改默认密码。保存恢复路径，再部署增量。

## 阶段 4：分层增量

遵循 [部署手册的组件顺序](DEPLOYMENT.md#增量组件部署)。先基础网络/音频/键盘，再用户会话桌面、控制中心/隐私。内核模块需要精确源码、配置、符号和工具链；热点面板绑定 Plasma 版本。只打包已编译产物的脚本不能补足编译缺口。

用户会话命令以桌面用户运行，系统服务命令以 root 运行；不要将所有 QML 配置写入 root 的 HOME。主题配置需按新设备的面板/widget ID 建立，不复制作者 applet ID。输入法先保持基础 Plasma Keyboard 可用，水杉作为可回退实验单独验收。

## 阶段 5：交互与硬件验收

按 [验证清单](VALIDATION.md) 记录真实状态：

1. 无鼠标触屏输入、连接 PIN 后禁止自动软键盘、保持连接休眠/恢复后输入。
2. 手机连接热点并实际访问网络；不能只看 hostapd active。
3. 低音量扬声器、音量键；避免大音量扫频或声学校准假设。
4. Dock 动画、时钟固定居中、原生 Alt+Tab 方向、控制中心列表/滑条手势例外。
5. AC 与电池的锁屏、息屏和服务策略；保护用户应用。
6. 隐私开关测试使用无敏感内容的测试进程，不采集真实音频/摄像画面。恢复关闭状态并确认播放/输入正常。

锁屏时停下依赖解锁的视觉/输入验收，继续能独立完成的源码工作；不要将锁屏造成的无输入误判为引擎崩溃。

## 记录格式

每个阶段保存 `设备代号 / 仓库提交 / 内核 / Plasma / 包版本 / 检查命令 / 结果 / 用户确认 / 回退`。输出报告可放本机 `out/`，公开时只提交去敏摘要。Wi-Fi 扫描、设备序列号、定位坐标、输入内容、项目名称和截图都需要检查后再分享。

本仓库的 [AGENTS.md](../AGENTS.md) 是 AI 操作契约；[VALIDATION.md](VALIDATION.md) 是历史实机摘要，不是每次部署的自动合格证。
