# 桌面主题、天气与布局

参考 [KDE 美化方案](https://blog.sotkg.com/2025/08/kde-customization) 的布局，并适配当前 Kali/Plasma Wayland。最终交互见 [桌面说明](../../docs/DESKTOP_AND_INTERACTIONS.md)，不要用早期美化截图推断当前效果。

## 最终外观

- BreezeLight 默认配色、Breeze Plasma/应用/窗口样式；不使用壁纸强调色或 Moe 的旧粉色配色。
- Colloid-Light 图标；**Breeze_Light 24px** 光标，白色主体、深色描边。
- 上面板 40、底部居中 Linexin Dock 84 逻辑像素；200% 屏幕缩放；一个虚拟桌面。
- 顶栏时钟 24 小时、常显秒（`showSeconds=2`）、日期 `MM-dd`（时间大、日期小）。由控制中心 `PanelIntegration.qml` 放到独立居中层；前景白色，电池由独立部件绘制。
- Panel Colorizer 顶栏关闭背景；Dock 关闭宿主背景，由 Linexin 绘制圆角底板；原生面板几何不由预设覆盖。Redmi Clock 前景白色。Lagtrain 为可选欢迎屏幕，不影响功能。

`layout.js` 是一次性布局种子：迁移现有任务面板、创建顶栏、建立角色标记；已经存在 Sheng 顶栏时停止。保留现有收藏，不绑定作者的 Burp desktop 文件。需要先安装依赖、准备壁纸或修改图片路径，且部署前备份。它不含完整 Panel Colorizer 用户预设，电池白色遮罩等仍需按新 widget ID 设置。步骤见 [部署手册](../../docs/DEPLOYMENT.md)。

后续增量已改用单一 Linexin Dock（84px）和独立的白色电池绘制。电池图形向右移 4 逻辑像素，保留原生百分比/插电/弹窗后端；Burp 使用圆角矢量图标。锁屏采用明确字体与上滑显示密码页，修复 MDI 误参与 ASCII 回退造成的 Firefox/锁屏缺字。最新部署、版本核验和回退见[触控与字体说明](../../docs/TOUCH_LOCKSCREEN_FONTS.md)。

当前会话的允许项快照见 [desktop-profile.json](desktop-profile.json)，188 个运行/构建源文件和生成资源的对应核对见 [source-audit.json](source-audit.json)。快照包含 FUTO/水杉外观和 400/300px 悬浮尺寸；审计已包含 Dock 外部点击收起及第三段上滑回桌面的新插件。[配置同步说明](../../docs/DESKTOP_PROFILE.md)描述统计口径、角色映射、复现和未导出范围，不包含用户完整配置。

## 来源

| 资产 | 固定来源/记录 |
| --- | --- |
| Panel Colorizer | `luisbocanegra/plasma-panel-colorizer@a8f8b1cee7bbc670cf2a5f5d194c24c314073b82`，需匹配本机 Qt/Plasma 的 C++ 插件 |
| Colloid | `vinceliuice/Colloid-icon-theme@ceac6608ecd0e40025cbc2ebbd32bf0e0f4ebc6a` |
| Redmi Clock / Lagtrain | KDE Store 2175475 / 2124802；外部安装，原包不入库 |
| 桌面壁纸 | cloudyman，Miku White Dress 3840×2160；[作者、链接和哈希](wallpaper.json) |
| 锁屏壁纸 | 冷蝉，暗色 Miku「深海少女」3840×2160；[作者、链接和哈希](lockscreen-wallpaper.json) |

图片不随仓库重新分发。来源记录不等于再分发授权，请选择自己有权使用的图片。锁屏图片通过 `kscreenlockerrc` 的图片插件等比填充；桌面同样 PreserveAspectCrop。

## 天气修复

[WeatherData.qml](WeatherData.qml) 使用 HTTPS GeoJS 近似定位与 Open-Meteo 当前天气，坐标仅在内存中。有效天气缓存到部件配置，断网不删除最后一次有效天气；首次尚无数据固定显示 `—°`，旧数据降低不透明度并提供获取时间提示。

超时 12 秒，失败从 15 秒开始退避到最多 5 分钟；正常每 15 分钟刷新。部署时替换 Redmi Clock 的 `contents/ui/components/WeatherData.qml`，并在原部件根目录应用 [weather-ui.patch](weather-ui.patch) 补齐配置和界面。不同原包版本需先 `git apply --check`，不要盲目覆盖。

## 验证与恢复

本机已验证时钟固定居中、天气缓存/失败保留、Dock 动画及托盘鼠标/触屏区分，见 [公开摘要](../../docs/VALIDATION.md)。本地历史 JSON/截图不公开。`restore.py` 是本机备份恢复参考，会读取该用户自己的备份位置；新部署需先建立自己的完整配置备份，不依赖作者的时间戳目录。不要在运行中直接覆盖整份 Plasma 配置、强制退出已有应用以刷新外观。
