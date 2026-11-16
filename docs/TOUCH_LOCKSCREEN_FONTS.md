# 两段上滑 Dock、锁屏触控与字体回退修复

本次增量针对 sheng / Kali ARM64 / Plasma Wayland 6.7.4 / Qt 6.11.2。它继续使用原 Plasma 会话、全屏 Linexin 抽屉及同一个 Dock，不关闭用户应用。

## 最大化后的两段 Dock 手势

Dock 随普通应用最大化/全屏向下隐藏后，从物理屏幕最底部的 **10 逻辑像素**区域上滑：

1. 第一次有效上滑仅显示一个与 Dock 背景同宽的白条；贴齐屏幕底部，上方两角圆、下方两角直。
2. 白条保留 **3 秒**；消失前再次从底边上滑，Dock 由下向上覆盖当前窗口。
3. 临时显示默认 **8 秒**，触摸 Dock 可延长。点击外部应用立即向下隐藏，原点击仍生效；Dock 自身、其弹出菜单和全屏抽屉不误收起。
4. 临时 Dock 显示时，再从同一底边上滑一次，通过 KWin 原生“显示桌面”返回主页，应用保留在后台。重新进入最大化/全屏应用后 Dock 恢复自动隐藏；还原小窗口后沿用正常显示。
5. 横向拖动、过短滑动、多指或过期后的第二次上滑不会直接唤出 Dock。过期后需重新执行第一段。

入口只在 Dock 隐藏时生效，位于 KWin 的原生 screen-edge 过滤器之前；从应用普通内容区开始的触摸不被拦截。不读取/独占 evdev，也不向应用注入按键。锁屏时取消白条和手势状态。全屏应用上的临时 Dock 使用堆叠约束，显示与输入命中一致。

源码为 [touchguard.cpp](../device/desktop-touch-guard/touchguard.cpp)、[DockRevealHint.qml](../device/desktop-touch-guard/DockRevealHint.qml) 和 [desktop-policy.py](../device/desktop-policy/desktop-policy.py)。白条通过 KWin OffscreenQuickScene 合成，不创建可窃取焦点的普通窗口。宽度扣除本布局宿主左右各 12px 的留白；改动宿主留白时也要调整这一参数。

按[原生插件说明](../device/desktop-touch-guard/README.md)重建匹配 ABI 的新插件，先停用旧 ID；升级 `sheng-tablet-controls 1.0-5` 后，重新加载当前任务效果以同步活动窗口。源码 hash 同时覆盖 QML 资源，避免热加载继续使用旧资源。禁止同时启用两个原生 guard。

## 字体问题的证据与处理

本机曾出现 Firefox 页面只显示大写字母、小写和数字消失，锁屏数字也异常。系统时间、RTC、上海时区及 NTP 均正常。`fc-validate` 验证 Noto CJK 文件正常，但缺少实际的 `Noto Sans` 正文字体：

```text
修复前 fc-match 'Noto Sans:charset=0061' → Material Design Icons version 6
修复前 fc-match 'Noto Sans:charset=0030' → Material Design Icons version 6
修复后两个查询均为 Noto Sans Regular
```

安装的 `fonts-materialdesignicons-legacy 5.9.55+6.9.96+dfsg-3` 宣称覆盖 `30-39`、`61-7a` 等 ASCII，但这些映射不能用于正文。补齐 Noto/Liberation 字体，并在 Fontconfig 扫描阶段仅从 MDI 的声明字符集中减去 ASCII，保留实际私用区图标。没有卸载图标字体，没有禁用 Firefox GPU 加速，也没有清空浏览器资料。Fontconfig 的匹配顺序和扫描规则见[官方手册](https://fontconfig.pages.freedesktop.org/fontconfig/fontconfig-user.html)。

```bash
sudo bash scripts/install-font-fallback.sh
fc-match 'Noto Sans:charset=0061'
fc-match 'Noto Sans:charset=0030'
fc-match 'Material Design Icons version 6:charset=f0001'
# 应无结果：MDI 不再声称能绘制小写 a
fc-list ':family=Material Design Icons version 6:charset=0061' family
```

刷新受影响网页即可重新验证；本机用户已确认 Firefox 恢复完整文字。若其他页面还有异常，应检查实际字体和页面样式，不把本次个案推广成所有 GPU/浏览器故障的结论。回退规则只需移除 `/etc/fonts/conf.d/31-sheng-material-icons-charset.conf` 并重新运行 `sudo fc-cache -f`；新增正文字体可保留。

## 锁屏

显示采用明确的 24 小时 `HH:mm` 与 `M月d日 星期`，Noto Sans CJK SC、Qt text 渲染，每秒读取系统时间，显示恢复时立即刷新。时钟位于上方独立区域，不随用户名布局挤压。

触屏轻点空白处保持时钟画面；**向上滑动 56 逻辑像素以上**且纵向占优才显示密码页。密码页出现时隐藏时间与日期，返回锁屏封面时重新显示并刷新时间。鼠标与实体键盘沿用原生入口。显示密码页后仍是 KDE 原来的 MainBlock / PAM authenticator，没有修改验证结果、自动提交密码或绕过锁屏。

```bash
sudo python3 scripts/install-lockscreen-touch.py
# 可选：在当前用户会话运行原生预览，只验 UI，不必输入密码
/usr/lib/aarch64-linux-gnu/libexec/kscreenlocker_greet --testing --shell org.kde.plasma.desktop
# 回退
sudo python3 scripts/install-lockscreen-touch.py --restore
```

安装器校验当前 `LockScreenUi.qml` 的固定 SHA-256，再应用[表现层 patch](../device/theme/lockscreen/LockScreenUi.patch)。使用 dpkg-divert 保存发行版文件，并在 `/var/lib/sheng-lockscreen` 保存私有回退记录。更新适用于下一次启动的 greeter，不杀死正在运行的真实锁屏；锁屏仍在时请正常解锁后再验。发行版更新后若原文件 SHA 改变，需要审阅并重新适配，不能跳过校验。

## 电池与 Burp 图标

以 Plasma 用户执行：

```bash
python3 scripts/install-tablet-appearance.py
# 多个 Burp launcher 时显式指定自己的文件
python3 scripts/install-tablet-appearance.py --burp-desktop /path/to/BurpSuite.desktop
```

小型顶栏样式部件仅替换原生电池紧凑视图的绘制；百分比、插电状态、鼠标点击、工具提示和电源弹窗继续使用原生后端。图形为白色横向圆角电池、内部数字、插电小圆点，向右偏移 4 逻辑像素。卸载此部件恢复原视觉绑定，不改电源策略。

Burp 使用[圆角矢量图标](../device/theme/icons/burpsuite-rounded.svg)，替换当前用户 desktop 文件的 Icon 并刷新 KService 缓存；Dock/抽屉也提供一致的本地图标映射，避免旧窗口图标缓存和绝对路径图标在上游模型中的加载异常。它不改变 Burp 启动参数、项目或许可证。Burp 名称/标识权利仍属于原权利人，不表示官方关联。

安装器在 `~/.local/state/sheng-tablet-appearance/backup-*` 备份自己的 desktop 文件和面板配置。回退图标恢复自己的 desktop 文件 Icon 行，运行 `kbuildsycoca6 --noincremental`；回退电池外观仅需在面板编辑器删除 Sheng battery appearance 部件，不覆盖整份运行中会话配置。

## 验证边界

用户已确认两段上滑及 Firefox 修复；锁屏预览已检查时间日期完整。用户暂不便测试锁屏触控，因此上滑密码页与真实解锁明确保留为待验；测试进程已关闭，没有重启真实锁屏。最终截图检查了抽屉/Dock 的圆角图标及电池绘制，右移后的图标仍待用户最终复验。挂起恢复、横竖屏、多输出需各设备独立验收。服务 active 或插件加载成功不能替代视觉验收；截图、浏览器配置、用户图标缓存及认证资料不提交到仓库。
