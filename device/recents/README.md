# 平板后台任务与三指手势

适用于当前 Xiaomi sheng 的 Kali ARM64、Plasma/KWin 6.7 Wayland 会话。虚拟桌面合并为一个，原有窗口保留。左右滑直接调用系统原生 Alt+Tab，不绘制另一套横向切换界面。按用户最终要求，独立三指上下滑不再调用任务卡片。

## 交互

- 独立三指上下滑：不打开任务卡片，也不切换桌面。起手竖向意图锁定后，后续横向晃动不会转为 Alt+Tab。
- 触摸板三指左右滑：按住虚拟 Alt 并发送原生 Tab／Shift+Tab，显示现有系统窗口切换器。保持三指接触时，左右、上下移动都在原生切换器内选择窗口，松手释放 Alt、确认当前选择。
- 原生切换期间，上下移动不调用任务卡片。左／右／上／下移动直接发送对应方向键，由原生网格选择相同方向的窗口；原生窗口排序、过滤和样式沿用 Alt+Tab 设置。
- 选窗采用方向确认、最小位移、反向滞回和 180 毫秒间隔，并丢弃不连续的触点跳变。方向键导航到网格首尾后停住，避免同向滑动连续绕回；普通键盘 Alt+Tab 仍按原生方式循环。短手势取消、设备移除、服务停止时释放按键；丢失结束事件时有 30 秒超时兜底。
- 任务卡片可点选打开、上滑单卡关闭、点击底部圆形叉号全部关闭。关闭使用应用自己的窗口关闭流程，保留其保存提示。
- `Meta+W` 保留任务卡片入口；卡片使用实时窗口缩略图、圆角、应用图标和当前壁纸，支持浅色／深色。进入和退出均有 220 毫秒淡入淡出，背景的 GPU 模糊同步渐变。原有 Alt+Tab 键盘快捷键继续可用。

## 实现

[gesture-bridge.cpp](gesture-bridge.cpp) 使用系统 libinput 读取触摸板手势，经过 `/dev/uinput` 发送限定的 Alt、Shift、Tab、Esc 及四个方向键。它只添加 udev 标记为触摸板的设备，不读取普通键盘事件，不独占输入设备，不修改 PIN 键盘驱动或认证服务。热插拔通过 inotify 更新设备列表，并为保存的 libinput 设备持有独立引用。

[sheng-task-gestures.service](sheng-task-gestures.service) 运行该小型本地桥接器；[udev 规则](83-sheng-task-gestures.rules) 仅允许 `kali` 会话访问它创建的专用按键设备。服务通过降权到 UID/GID 1000 的固定 `qdbus6` 调用与当前桌面连接，不执行拼接的 shell 命令。当前安装针对本机 `kali` 用户；迁移到其他账户时须相应修改这些路径和 UID。

`contents/ui/` 是 KWin `SceneEffect`，通过 `WindowThumbnail` 直接显示合成器的 GPU 缩略图。关闭后场景卸载，不保持缩略图渲染或定时轮询。原有 Overview 效果停用，避免其三指触屏手势冲突。

[install-native-tabbox.py](install-native-tabbox.py) 复用系统安装的 `thumbnail_grid` 原生布局，保留其源码、作者、许可证和视觉样式，仅把 `keyNavigationWraps` 改为 `false`，保存为用户目录中的原生布局配置。它仍由 `KWin.TabBoxSwitcher` 和系统原生窗口模型驱动；没有单独绘制横向切换窗口。

KWin 会缓存同一路径的 QML。部署时将源文件散列加入插件 ID，使用新的加载路径，同时停用旧 ID，确保运行新逻辑而不重启桌面会话。当前插件 ID、安装包和验证结果见本机 `out/recents-verification.json`。

## 构建与恢复

在仓库根运行 `python3 scripts/build-task-cards.py` 可独立打包 KWin 效果；`--install` 只把带源码散列 ID 的文件放到当前用户目录，仍需按输出启用，并停用旧 ID。公开脚本不依赖作者的 `.work/recents-build.json` 或 SSH 信息。

桥接器使用 C++17，依赖系统的 libinput、libudev 和 Linux uinput。安装开发头文件后可构建：

```sh
g++ -std=c++17 -O2 -Wall -Wextra -Werror gesture-bridge.cpp \
    -o sheng-task-gestures $(pkg-config --cflags --libs libinput libudev)
python3 build-device-package.py ./sheng-task-gestures ./sheng-task-gestures_1.0-1_arm64.deb
```

本机 `out/packages/sheng-task-gestures_1.0-1_arm64.deb` 包含桥接器、服务、专用 udev 规则及原生布局设置脚本。KWin 界面另存为 `out/packages/sheng-task-cards_1.0.0-*.zip`；解压到 `~/.local/share/kwin-wayland/effects/<包内 KPlugin.Id>/`，启用对应 `<KPlugin.Id>Enabled` 并加载该效果。以桌面用户运行 `install-native-tabbox.py`，或包内 `/usr/libexec/sheng-native-tabbox-setup`，应用原生网格导航边界设置。

修改前 `kwinrc`、快捷键配置保存在平板 `~/.local/state/sheng-recents/backup-*`，具体位置由 `backup-path` 文件记录。回退时先停用桥接服务和本插件，再恢复备份中的配置、加载原生 Overview。虚拟桌面可依据备份重建，已经归并的窗口保留在当前桌面。

实现依据 KDE 的 [QML 效果接口](https://develop.kde.org/docs/plasma/kwineffect/)、[KWin 6.7.4 原生 TabBox](https://github.com/KDE/kwin/blob/v6.7.4/src/tabbox/tabbox.cpp) 和平板所安装 libinput 的 API 头文件；界面与桥接代码为本项目定制。
