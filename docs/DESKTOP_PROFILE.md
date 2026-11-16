# 当前桌面配置与源码对应关系

本次同步的是已经在 sheng 运行的 Plasma 桌面与源码。配置见 [desktop-profile.json](../device/theme/desktop-profile.json)，代码核对结果见 [source-audit.json](../device/theme/source-audit.json)。配置从当前用户会话只读导出，不退出应用或重启桌面。

## 配置内容

| 部分 | 当前值/实现 |
| --- | --- |
| 环境 | Kali ARM64，KWin 6.7.4，Qt 6.11.2；精确 Debian 包版本保存在 profile |
| 内屏 | 3048×2032、144Hz、缩放 200%；一个虚拟桌面 |
| 顶栏 | 40 逻辑像素，启动器、窗口菜单、居中时间、托盘、白色电池与控制中心 |
| Dock | 84 逻辑像素、居中、覆盖式显隐；两次底边上滑唤出，外部点击立即收起，再上滑返回桌面 |
| 抽屉 | Linexin 全屏网格、左右翻页、下滑收起、长按编辑，显示同一个真实 Dock |
| 配色/指针 | BreezeLight / Colloid-Light / Breeze_Light 24px，关闭壁纸强调色 |
| 桌面时钟 | 白色 Redmi Clock，位置与尺寸使用导出的逻辑坐标；天气缓存不导出 |
| 软键盘 | FUTO 原生 UI/英文核心 + 水杉中文 + Fcitx5 OSK；FUTO Light/Dark、Roboto、400/300px 悬浮布局；中文键帽大写/英文默认小写 |
| 锁屏/电源 | 明确字体与上滑显示密码页，密码页隐藏时间/日期；AC 60 分钟、电池 30 分钟策略详见电源配置与交互文档 |

FUTO 增量已从固定源码构建并安装：原生英文候选核心、原版图标/配色和 Linux UI/UX 集成；中文继续使用水杉。构建、范围和回退见 [FUTO 说明](../device/futo-keyboard/README.md)。语音、滑行与完整 Android 设置未移植，不能将当前版本称为完整 Android 应用移植。

Profile 包含允许导出的 KDE 配置项、面板属性、部件参数、Panel Colorizer 全局有效样式、显示模式与软键盘外观。面板/部件的实例 ID 已替换为插件角色，例如 `org.sheng.linexin.launcher#1`；Dock 固定应用使用 `file-manager`、`browser`、`burp-suite`、`terminal` 等角色，不保存自定义启动器路径或 Exec。

顶栏时钟由 `PanelIntegration.qml` 移到独立居中层，因此它列于 `detachedApplets`，没有放回线性 `appletOrder`。不要把它缺席线性排列误认为时钟被删。Dock 的固定项顺序与运行窗口的临时手动排序不同，后者不作为跨会话配置发布。

Panel Colorizer 只记录 `panel`、`widgets`、`trayWidgets`、`nativePanel` 的有效样式。关闭的效果分支仅保留 `enabled=false`；文件/图片路径、预设路径和依赖实例 ID 的覆盖规则不导出。样式需合并到匹配版本的默认配置，新的电池外观由独立部件实现。

## 导出与校验

在目标平板的普通桌面终端，以 Plasma 用户运行：

```bash
python3 scripts/export-desktop-profile.py --output out/desktop-profile.json
# 此项可在 Windows 或 Linux 执行，不依赖 D-Bus
python3 scripts/export-desktop-profile.py --validate device/theme/desktop-profile.json
```

通过 SSH 时先设置当前用户的 `XDG_RUNTIME_DIR`、`DBUS_SESSION_BUS_ADDRESS`、`WAYLAND_DISPLAY` 与 `QT_QPA_PLATFORM=wayland`。导出器只接受 sheng 型号；读取配置项和已安装包版本，不改动会话。KConfig 数据、字体及外观选项均使用代码中的允许列表。

这是公开的可复现配置，不是 HOME 备份。不包括账号、Wi-Fi、浏览器/应用会话、输入学习库、天气坐标、截图、密码、设备 UUID、桌面实例 ID 或用户路径。壁纸只引用已有来源清单；需自行准备有权使用的图片。原始配置备份继续保留在自己的设备中。

## 在新设备复现

1. 按[部署手册](DEPLOYMENT.md)安装匹配的 Plasma/Qt、硬件修复和第三方主题。Profile 不能替代内核/插件 ABI 核对。
2. 读取 profile 的 `kconfig`，按文件、分组、键设置配色、光标、窗口样式和电源策略。输入法路径只在对应集成包已经安装后使用；屏幕锁定的全局 Timeout 会随 AC/电池策略变化。
3. `device/theme/layout.js` 是首次创建面板的种子，已同步当前 Dock 的 84px / 最大宽度1100及桌面时钟几何；它仍不是重复执行的配置管理器。已有桌面请迁移现有面板，不删除后重建。
4. 按[抽屉部署](DESKTOP_DRAWER.md)安装 Linexin、迁移固定应用、添加桌面手势和原生 guard；按[触控/字体增量](TOUCH_LOCKSCREEN_FONTS.md)安装电池样式、圆角图标与锁屏修复。
5. 按插件角色匹配本机部件，恢复 profile 的面板属性、外观参数和有效 Colorizer 样式。自定义应用角色在本机解析为合法的 `.desktop` 启动器；没有安装 Burp 时跳过该角色。不要复用作者的实例 ID。
6. 对照[验证矩阵](VALIDATION.md)重新验收。显示模式、虚拟桌面数量和布局不由导出脚本自动套用到当前会话，先保护已有窗口与配置。

仓库没有“把 JSON 覆盖成整份 Plasma 配置”的导入命令。上述源码安装器和允许列表给 AI/开发者提供具体设置目标，跨版本仍需判断迁移，不绕过本机 ABI 或配置备份。

## 源码核对结果

本次依据 `1548fdc` 的源码，比较安装位置、匹配 ABI 的构建源码及固定上游生成资源；文本统一换行为 LF，其他内容不改。统计不再计入两份安装说明/元数据，历史 190 项与本次 188 项统计口径不同。结果如下：

| 范围 | 比较文件数 | 一致 |
| --- | ---: | ---: |
| Linexin 抽屉/Dock | 20 | 20 |
| 控制中心 | 112 | 112 |
| 任务效果 | 4 | 4 |
| 桌面支持文件、字体、图标、时钟、电池样式、原生插件构建源码 | 11 | 11 |
| 桌面安装器及实体键盘策略 | 2 | 2 |
| 锁屏表现层 patch 应用结果 | 1 | 1 |
| FUTO C++ 构建源码 | 6 | 6 |
| FUTO OSK 原生 UI/输入增量源码 | 6 | 6 |
| FUTO 运行脚本与注册 | 3 | 3 |
| FUTO 布局、键集、配色、表情与原版图标 | 23 | 23 |
| 合计 | 188 | 188 |

原生 guard、FUTO 模块和 OSK 均与本机构建 ELF 的 SHA-256 一致；还核对了正在运行的 OSK 可执行文件，排除仍运行被替换的旧文件。这些二进制不上传仓库。报告保存实际启用的插件 ID、构建 manifest、固定上游提交/哈希；不声称比较了发行版所有文件、内核、固件或商业软件。OSK 整个进程的一次内存快照也被记录，不能把它解释为仅 FUTO 核心的开销或长期基准。

导出和核对只读执行，没有重放桌面布局、刷机或退出会话。用户确认临时 Dock 外部点击即时收起、第三次底边上滑回桌面及进入原应用后自动隐藏均正常。新尺寸/键帽、符号/表情/动作栏和候选前后翻页/选词上屏的记录保留；锁屏上滑、真实解锁与输入法休眠恢复仍待独立验收。
