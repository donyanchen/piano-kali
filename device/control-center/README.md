# 平板下滑控制中心

公开源码构建入口：在仓库根运行 `python3 scripts/build-control-center.py`。无需作者本地缓存或连接平板；构建器验证固定上游 archive 与 patch 哈希，生成 `out/packages/sheng-control-center.plasmoid` 及独立 manifest。下文旧 artifact 散列是历史设备包，不是新构建的预期散列。安装顺序与主题依赖见 [部署手册](../../docs/DEPLOYMENT.md)。

当前平板使用参考澎湃 OS 重写的卡片界面：Wi-Fi 和蓝牙大卡片、媒体卡片、竖向亮度和音量滑条、含热点的圆形快捷开关。热点使用独立的共享网络图标，“夜间模式”文字已改为“护眼模式”；麦克风按钮改为[统一隐私开关](../privacy/README.md)。面板缩放为 85%，颜色随系统浅色／深色模式切换。入口位于顶部状态栏右侧，单指向下拖动并松手展开；在滑条和列表以外的区域向上拖动、点击外部可收起。从亮度或音量滑条内开始上滑只实时调节数值；从 Wi-Fi、蓝牙列表内开始上滑只滚动列表，均不收起面板。用户已确认下滑展开、滑条例外及两个列表滚动均符合要求。

状态栏没有控制中心点击按钮。原有蓝牙、Wi-Fi、亮度图标增加仅拦截触屏事件的覆盖层，鼠标仍可点击；触屏统一使用下滑控制中心。蓝牙、Wi-Fi 图标的鼠标／触屏区分和右侧下滑已经用户实机确认，亮度采用相同拦截方式。原生时钟移至同一面板窗口内的独立居中层，保留日历和时间格式；启动终端前后八次采样中心均为屏幕中心 762 逻辑像素。电池图标通过现有 Panel Colorizer 设为白色符号遮罩，百分比徽标增加深色底以保证可读性。

界面文件为本目录的 `Hyper*.qml`、`PanelIntegration.qml` 和 SVG；后端基于 GPL-3.0-or-later 的 [Kontrol Center](https://github.com/ItsNotMeBro87/plasma6-kontrol-center)，固定提交、包散列见 [provenance.json](provenance.json)。[upstream-integration.patch](upstream-integration.patch) 包含后端、触屏入口、弹层锚点和默认 85% 缩放适配。复现时在固定上游提交的插件根目录应用补丁，将本目录 `Hyper*.qml` 及 `PanelIntegration.qml` 复制到插件 `contents/ui/`，四个 SVG 分别复制为 `contents/icons/sheng-music.svg`、`sheng-capture.svg`、`sheng-hotspot.svg`、`sheng-privacy.svg`。发行包版本为 `0.7.7-sheng-privacy4`，保留上游许可证及说明，位于本机 `out/packages/sheng-control-center_0.7.7-privacy.plasmoid`。电池的白色遮罩规则保存在平板现有 Panel Colorizer 配置中，复现完整状态栏时也须保留该配置。

原生系统负责 Wi-Fi、蓝牙的持久状态，控制中心加载时只读取状态。热点调用已有补丁服务 `sheng-hotspot.service`，等待其 ready 文件后更新状态，不另建 NetworkManager 热点。亮度优先使用 Plasma API，当前平板通过 brightnessctl 和 brightness-udev 回退路径控制内屏。亮度、音量同值写入、蓝牙开关往返、热点启动就绪和停止测试通过；热点测试保留上游 Wi-Fi 连接和原开关状态。关闭面板后不持续轮询状态和颜色。

新布局基于普通 Plasma 桌面，不切换桌面会话。初始面板、快捷键和 KWin 配置备份位于平板 `~/.local/state/sheng-control-center/backup-*`。本轮修改前的桌面、锁屏和天气配置备份由 `~/.local/state/sheng-control-center/polish-backup` 指向。最新布局、源文件散列、时钟采样及用户实机确认见本机 `out/tablet-polish-verification.json`，此前后端验证见 `out/tablet-controls-verification.json`；原有 rootfs/boot 导出未重新打包此次桌面调整。

列表手势补丁的备份位于 `~/.local/state/sheng-control-center/before-list-gestures-*`，最新安装包与用户确认见本机 `out/recents-verification.json` 的 `control_center` 字段。

后续 Dock、桌面右半区手势及进程隐私拦截的最新验证见本机 `out/desktop-privacy-verification.json`。桌面手势遵循[鼠标／触摸板存在策略](../desktop-policy/README.md)，应用内整条最右侧入口已删除。状态栏亮度使用触屏覆盖层，并对可见的指针处理器排除触屏设备，保留鼠标操作；用户已确认此行为正常。
