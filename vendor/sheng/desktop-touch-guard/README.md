# 原桌面的触屏手势与防框选

本组件在 KWin Wayland 内处理**桌面窗口**的触摸移动，桌面上滑打开 Linexin 抽屉；没有鼠标/触摸板时，右半区下滑打开已有控制中心。普通应用、鼠标与触摸板事件不经过此策略。不读取或独占 `/dev/input/event*`。

首次桌面触摸移动达到 3 逻辑像素时，向桌面发送 Wayland touch cancel，避免 Folder View 的模拟鼠标路径启动框选。手势结束仍向下层 KWin 过滤器传递 touch up，清理屏幕边缘及多指跟踪状态；多指序列不触发抽屉/控制中心。点击与长按仍使用桌面原有规则。这里只拦截桌面表面的移动，因此桌面部件上的触屏拖动也会受限；编辑布局请使用鼠标/触摸板。

它调用 `org.sheng.DesktopPolicy` 的 `OpenAppDrawer` / `OpenControlCenter`，缓存服务发布的指针状态；没有添加另一个主屏幕，也没有全局应用内导航入口。QML 桌面手势部件保留原有长按防误触保护。

全屏 Sheng 抽屉存在时，还为同一输出的底部 Plasma 面板添加 KWin stacking constraint，使真实 Dock 保持在抽屉上方；关闭抽屉后移除。Dock 不进入抽屉自身的缩放/淡入动画，不再显示两份。输入命中也使用同一窗口堆叠顺序。

## 构建与加载

仅在目标 Linux 系统或与其开发包完全匹配的构建环境编译。已验证 KWin `4:6.7.4-2+b1`、Qt `6.11.2`、ARM64；KWin 内部输入 API 不稳定，CMake 当前严格要求 `6.7.4 EXACT`。更新 KWin/Qt 后必须重新审核源码和编译，不能复制旧 `.so` 或仅删除版本检查。

在仓库根目录：

```bash
sudo apt-get install build-essential cmake ninja-build extra-cmake-modules \
    kwin-dev qt6-base-dev qt6-declarative-dev
bash scripts/build-desktop-touch-guard.sh
sudo cmake --install out/build-desktop-touch-guard
# 以下以正在运行 Plasma 的用户执行
guard_id=$(cat out/build-desktop-touch-guard/touch-guard-id.txt)
kwriteconfig6 --file kwinrc --group Plugins --key "${guard_id}Enabled" true
qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.loadEffect "$guard_id"
qdbus6 org.sheng.DesktopTouch /org/sheng/DesktopTouch org.sheng.DesktopTouch.GetStatus
```

先按[抽屉部署说明](../../docs/DESKTOP_DRAWER.md)安装用户会话服务和启动器。`GetStatus` 仅返回次数、范围、指针和 Dock 约束状态，不记录输入内容或坐标。热加载无需重启 KWin。构建从 C++、元数据和 CMake 内容生成不同的插件 ID/文件名，避开 Qt 插件工厂缓存；升级先卸载并将旧 ID 的 Enabled 写成 false，再启用新 ID，不能同时加载两个 guard，也不在同一路径覆盖已映射的二进制。

## 验收与回退

已获用户确认：原桌面左/中/右上滑打开抽屉；触屏横拖、下拖、上滑无框选，鼠标仍使用原输入路径。当前版本没有 USB/蓝牙鼠标实机验收条件，也未独立完成横竖屏、挂起恢复回归。

停用后恢复原生桌面触控行为，用户应用继续运行：

```bash
guard_id=$(cat out/build-desktop-touch-guard/touch-guard-id.txt)
kwriteconfig6 --file kwinrc --group Plugins --key "${guard_id}Enabled" false
qdbus6 org.kde.KWin /Effects org.kde.kwin.Effects.unloadEffect "$guard_id"
```

源码为 GPL-3.0-or-later，许可证见仓库根 [LICENSE](../../LICENSE)。
