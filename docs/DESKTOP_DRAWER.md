# 原 Plasma 桌面 + Linexin 抽屉与 Dock

保留原来的 Plasma 桌面、时钟、壁纸、控制中心和用户应用，在桌面增加触屏上滑抽屉。桌面仍只有一个 KWin 虚拟桌面，抽屉的分页与虚拟桌面无关。本组件不安装另一个 Tablet Shell，也不更换输入法、热点或 GPU 驱动。

## 交互

| 位置与动作 | 行为 |
| --- | --- |
| 原桌面任意空白区域触屏上滑 | 打开全屏应用抽屉，PIN 可保持连接 |
| 桌面触屏横向、纵向拖动 | 不产生框选矩形；鼠标/触摸板框选保留 |
| 没有鼠标/触摸板时，桌面右半区下滑 | 打开原控制中心；应用内无此入口 |
| 抽屉 Dashboard 全面板左右触屏滑动 | 翻页，包括图标上方与空白处 |
| 抽屉全面板向下触屏滑动 | 动画收起；长按编辑期间不触发导航 |
| 抽屉图标短触拖动 | 浏览，不重新排列 |
| 抽屉图标长按约 550ms 后拖动 | 编辑位置、沿用上游文件夹操作 |
| Dock 的九圆点图标 | 打开/关闭抽屉 |
| 普通应用最大化/全屏 | Dock 覆盖窗口后由底边向下隐藏，不为 Dock 预留窗口空间 |
| 应用恢复小窗口/最小化 | Dock 从底部向上显示 |
| 最大化后从物理底边上滑两次 | 首次只显示 3 秒白条，期间再次上滑才唤出覆盖式 Dock；见[详细说明](TOUCH_LOCKSCREEN_FONTS.md) |
| 打开/关闭全屏抽屉 | 原来的同一个 Dock 保持位置，不复制另一份参与抽屉淡入/缩放 |

All Apps / Alphabetically 等上游长列表沿用其滚动方式，没有 Dashboard 页码；左右分页针对 Dashboard。长按编辑、文件夹拖动与导航互斥。应用发现、分类与启动继续使用 KDE Kicker/KService 模型及上游功能，没有自行解析后用 shell 拼接 `Exec`。

## 核心文件

| 文件 | 职责 |
| --- | --- |
| [drawer-provenance.json](../device/desktop-policy/drawer-provenance.json) | Linexin 固定提交、归档哈希与许可证 |
| [build-desktop-drawer.py](../scripts/build-desktop-drawer.py) | 校验上游、应用补丁、打包并输出 manifest；源码散列生成新插件 ID |
| [ShengDock.qml](../device/linexin-dock/ShengDock.qml) | 从 Linexin 提取的运行应用 Dock，增加持久固定项、菜单和九点入口 |
| [CompactRepresentation.qml](../device/linexin-dock/CompactRepresentation.qml) | 承载唯一 Dock 和全屏抽屉窗口 |
| [touch-edit.patch](../device/linexin-dock/touch-edit.patch) | 全面板导航、触屏长按编辑；滑动时接管触摸，取消上游背景点击关闭 |
| [install-desktop-drawer.py](../scripts/install-desktop-drawer.py) | 备份、迁移固定应用/抽屉布局、添加手势部件、关闭 Dock 宿主原生背景 |
| [desktop-touch-guard](../device/desktop-touch-guard/README.md) | KWin 原生桌面防框选；把真实 Dock 约束在标记的全屏抽屉上方 |
| [desktop-policy.py](../device/desktop-policy/desktop-policy.py) | 指针检测、D-Bus 激活入口和面板显隐 |
| [DesktopPolicy.qml](../device/recents/contents/ui/DesktopPolicy.qml) | 监视活动应用最大化/全屏；抽屉被排除，不触发 Dock 隐藏 |

KWin 的 stacking constraint 同时用于绘制与输入顺序，因此全屏抽屉中的 Dock 仍能正常点击。约束只针对同一输出上的 Sheng 抽屉和底部 Plasma 面板，关闭后移除；不提升其他应用或锁屏。原生插件与 QML 都不抢占应用窗口的 evdev 输入。

Linexin 来源为 [Petexy/Linexin-Launcher](https://github.com/Petexy/Linexin-Launcher)，固定 `43da5eab6e367f96f8e1aca9a90867a4289a9557`（1.2.1），GPL-3.0-or-later。包中保留上游 LICENSE/NOTICE。新增代码不复制 Android 资源。

## 构建、部署

先按[部署手册](DEPLOYMENT.md)安装桌面策略包、任务效果和主题面板。需要现有底部任务面板，安装器按角色或底部任务管理器识别，不硬编码面板 ID。仅限当前 Plasma 用户执行用户配置命令，不能用 sudo 写进 root 的 HOME。

```bash
# 任意 Python 3 + Git 构建机；没有作者缓存也会下载固定归档并校验
python3 scripts/build-desktop-drawer.py
# 把产物转移到目标后，以 Plasma 用户安装
kpackagetool6 --type Plasma/Applet --install out/packages/sheng-desktop-drawer.plasmoid
python3 scripts/install-desktop-drawer.py --launcher-id "$(python3 -c \
  'import json;print(json.load(open("out/packages/sheng-desktop-drawer.manifest.json"))["plugin"])')"
```

构建器支持 `--archive /path/to/pinned.tar.gz` 离线使用，仍强制校验 SHA-256。升级生成不同插件 ID；安装器迁移旧实例的固定项和 General 配置后删除旧部件实例，不退出用户应用。首次分配一个空闲的内部全局快捷键供桌面手势通过 KGlobalAccel 激活。

随后按[原生插件说明](../device/desktop-touch-guard/README.md)在匹配 KWin/Qt 的目标环境编译、安装并启用。没有此插件，仅 QML 抢触摸无法可靠阻止 Folder View 框选，也不能保证全屏抽屉上方显示原 Dock。不能把其他 Plasma 版本的 `.so` 拼装进来。

任务效果使用 `python3 scripts/build-task-cards.py --install` 构建并按输出启用最新 ID，先停用旧副本。安装策略包/启动器会重启策略用户服务；最后重新加载一次当前任务效果，使其立即发布活动窗口状态，无需重启 KWin 或 Plasma。

## 排查与回退

```bash
systemctl --user status sheng-desktop-policy.service
qdbus6 org.sheng.DesktopPolicy /org/sheng/DesktopPolicy org.sheng.DesktopPolicy.GetState
qdbus6 org.sheng.DesktopTouch /org/sheng/DesktopTouch org.sheng.DesktopTouch.GetStatus
journalctl --user -u plasma-plasmashell.service --since '5 minutes ago'
```

抽屉显示时原生状态应为 `drawerDockLinked=true`；关闭后应为 false。Dock 显示态配置为 `windowsgobelow`，隐藏态 `autohide`。Plasma 6.7 的脚本 getter 漏报前一种模式为 `none`，核验还需查看 `plasmashellrc` 中对应面板的 `panelVisibility=3`；[上游实现](https://github.com/KDE/plasma-workspace/blob/Plasma/6.7/shell/scripting/panel.cpp)可见 getter/setter 的差异。

Dock 尖角来自宿主背景时，必须关闭 Panel Colorizer 的 `nativePanel.background.enabled`，仅设 opacity=0 不够。安装器只改变底部 Dock 的背景/阴影/模糊，上方白色状态栏保留。

每次迁移在 `~/.local/state/sheng-desktop-drawer/backup-*`（0700）备份自己的 `plasma-org.kde.plasma.desktop-appletsrc` / `plasmashellrc`，`installed.json` 指向本次备份。回退先关闭抽屉，停用原生 guard，再通过面板编辑器移除 Linexin、加回系统图标任务管理器。需要完整配置回退时，在下一次正常退出会话后恢复自己的备份；不在 Plasma 运行中覆盖配置、不重启用户当前会话。旧构建包可留作本地回退，不公开用户配置。

## 验证范围

2026-11-15，sheng / ARM64 / KWin `4:6.7.4-2+b1` / Qt `6.11.2`：已从公开源码编译原生插件、热加载，未重启会话。用户确认桌面三处上滑、防触屏框选、长按编辑和圆角背景；随后确认覆盖式最大化隐藏/还原显示；最终确认抽屉真正全屏、原 Dock 在开关时不闪烁/移动、左右翻页与下滑收起正常。检查中没有新增 QML 加载错误。

尚未独立完成新版本的横竖屏、多屏、休眠恢复和 USB/蓝牙外设回归；当前仅有 PIN 键盘/触摸板实机测试条件。不声明已实现完整 Android 导航系统。CI 校验源码和固定上游打包，不替代触屏验收；Ubuntu CI 没有本机精确的 KWin 开发 ABI，因此原生 guard 以目标机编译结果为准。
