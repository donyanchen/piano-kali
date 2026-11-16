# Dock 与桌面触屏策略

当前平板只有一个虚拟桌面。活动应用最大化或全屏时，KWin 的 [DesktopPolicy.qml](../recents/contents/ui/DesktopPolicy.qml) 通知用户会话服务，将底部 Linexin Dock 的宿主面板切为自动隐藏；还原小窗口或最小化后恢复 `windowsgobelow` 覆盖显示，不占窗口可用空间。滑入/滑出由 Plasma 原生底边动画处理。Sheng 全屏抽屉排除在隐藏规则之外，由原生 KWin 插件保持同一个 Dock 在其上方，不复制另一份 Dock 参与动画。覆盖式最大化显隐及最终抽屉开关稳定性已获用户确认。

[desktop-policy.py](desktop-policy.py) 通过 KWin 输入设备信号识别鼠标、触摸板。PIN 键盘的输入节点在脱离后可能仍存在，额外以 `nanosic_hinge/keyboard_attached` 判断实际连接；该内存属性每 250 毫秒只读检查一次，变化时才更新配置。触摸板按用户要求计入鼠标。

无鼠标和触摸板时，[桌面手势部件](desktop-gesture/contents/ui/main.qml) 将触屏下滑区域放到现有桌面窗口的整个右半区；桌面全区域上滑打开 Linexin 全屏抽屉，不要求断开 PIN。它在拖动完成时调用已有服务，不添加另一个主屏幕；应用窗口、状态栏、Dock 使用各自窗口的触控。应用内的整条最右侧入口已删除。原状态栏的下滑入口继续沿用。

防框选依靠[原生 KWin 桌面触控插件](../desktop-touch-guard/README.md)，在触摸移动进入 Folder View 模拟鼠标路径前发送 cancel；单靠 QML 抢事件不可靠。该插件也管理全屏抽屉与真实 Dock 的堆叠约束。部署、源码来源、全面板手势与回退见[抽屉专用文档](../../docs/DESKTOP_DRAWER.md)。

右半区通过被动 PointHandler 从触摸按下开始临时保护桌面长按计时器，普通点击仍交给原部件。下滑接管后，Plasma 的 C++ 布局过滤器可能收不到结束事件，原先启动的长按计时器会错误进入编辑模式；现在该触摸序列及原长按超时窗口内临时使用 Locked 条件，随后由 Binding 恢复原编辑规则。已经手动进入编辑模式时，控制中心桌面入口暂停，便于正常调整桌面；鼠标与左半区原有操作不变。服务同时识别规范插件 ID 与用于避开 QML 缓存的热更新实例后缀。

2026-11-15 已将 `sheng-tablet-controls 1.0-2` 安装到实机，日志确认找到桌面布局及原生 800ms 长按设置；用户以断开键盘/鼠标后的右半区慢速下滑确认“正常，不再进入编辑模式”。热更新通过新的插件实例路径避开 QML 缓存，没有重启整个桌面会话。

用户服务为 `sheng-desktop-policy.service`，会话总线为 `org.sheng.DesktopPolicy`，状态保存在 `~/.local/state/sheng-desktop-policy/state.json`。服务在 Plasma 重启后重新同步输入状态。原有物理键盘软键盘策略保持不变。

本地历史隐私验证产物不随仓库分发。抽屉安装器在 `~/.local/state/sheng-desktop-drawer/backup-*` 备份面板配置，不依赖作者私有缓存。构建包需提供本机已编译的隐私 BPF 程序；从仓库根运行：

```sh
python3 device/desktop-policy/build-device-package.py /usr/libexec/sheng-privacy-bpf out/packages/sheng-tablet-controls_1.0-4_arm64.deb
```

此包安装会话服务、桌面手势和隐私后端。控制中心与 KWin 效果分别使用 `out/packages/` 下的 `.plasmoid` 和任务卡片 `.zip` 包，保留现有插件 ID／部件布局配置。当前实现针对本机 `kali` 用户（UID 1000）。
