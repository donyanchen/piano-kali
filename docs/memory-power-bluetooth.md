# 平板内存、电源键与蓝牙

2026-11-14 已在当前约 12GB RAM 的 sheng 平板应用，记录为本机 `out/system-tuning-verification.json`。

使用发行版 `systemd-zram-generator 1.2.1-2+b2` 创建 `/dev/zram0`，逻辑容量 6GiB、Zstd 压缩、swap 优先级 100。原有 `/swapfile` 保持 8GiB、优先级 10；分区未改动。配置源为 [zram-generator.conf](../device/zram-generator.conf)。ZRAM 按实际使用分配压缩存储，不预留 6GiB 物理内存。

`vm.swappiness` 按最新要求提高到 160，`vm.page-cluster` 保持 0。优先级决定先使用哪一个交换设备，swappiness 控制匿名内存与文件缓存的回收倾向，不是 swap 使用率目标；内存充足时低占用正常。实机对独立 32MiB 匿名映射执行页出，并确认 ZRAM 接收页面、读回 SHA-256 一致，随后释放测试映射。没有全局清空缓存、强制回收用户应用或为了提高表盘数值持续占用内存。参考 [内核内存管理参数](https://docs.kernel.org/admin-guide/sysctl/vm.html) 和 [ZRAM](https://docs.kernel.org/admin-guide/blockdev/zram.html)。

电源键短按在 AC、Battery、LowBattery 三种配置中均设为 `LockScreen=32`，长按仍关机。插电闲置 3600 秒后锁屏并息屏，不自动挂起；离电闲置 1800 秒后锁屏、息屏并挂起，后台进程随系统暂停。配置脚本为 [configure-power-buttons.sh](../scripts/configure-power-buttons.sh)。logind 的备用行为为 `HandlePowerKey=lock`，已通过 reload 更新到运行态并核对 D-Bus 属性。桌面由 PowerDevil 接管按键时使用相同锁屏动作。

Plasma 的锁屏超时是全局设置，显示关闭超时则按电源配置分别设置。每个电源配置的 `RunScript/ProfileLoadCommand` 调用 [set-screen-lock-timeout.sh](../scripts/set-screen-lock-timeout.sh)，自动将全局锁屏超时切换为 60 或 30 分钟并通知锁屏服务重读。进入锁屏时立即息屏，不使用默认额外 60 秒等待；锁屏后的用户操作仍能唤醒屏幕用于输入密码。已实测强制重载当前电源配置后，原生 ProfileLoadCommand 自动恢复正确锁屏超时；未实际等待 30/60 分钟，也未主动锁定或熄灭用户正在使用的屏幕。最新记录为本机 `out/idle-lock-policy-verification.json`，含此次修改前配置的备份路径。

蓝牙为 WCN7850，hci0 固件加载正常，已安装 BlueDevil 并启用 BlueZ 开机启动，状态栏始终显示蓝牙入口。控制中心也可切换蓝牙及打开设备列表；开关往返测试通过并恢复原状态。此前约 8 秒扫描收到 54 个不同设备地址。配对、蓝牙音频和外设输入尚未实测，未连接未知设备。界面与后端的最新记录为 `out/tablet-controls-verification.json`。

实体键盘策略使用 [keyboard-policy.py](../scripts/keyboard-policy.py) 和用户级 [sheng-keyboard-policy.service](../device/sheng-keyboard-policy.service)。PIN 口读取驱动的 `keyboard_attached`，USB/蓝牙读取 udev 键盘属性，不读取实际按键内容。连接时将 KWin 虚拟键盘模式设为 Never，断开后恢复 NonMouseInput；用户已确认接入 PIN 键盘后触屏文本框不再弹出软键盘。[resume-desktop.py](../scripts/resume-desktop.py) 恢复输入面板时遵循相同判定，避免再次强制弹出。
