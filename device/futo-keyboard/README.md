# FUTO 键盘的原生 Linux 移植（实验）

针对 sheng / Kali ARM64 / Fcitx5 5.1.23 / Plasma Wayland 6.7.4 / Qt 6.11.2。本组件将 **FUTO/LatinIME 的真实 C++ 词典与英文输入候选核心**编译为 Linux ELF，并把固定版本的 FUTO QWERTY 布局和默认浅/深色调色板接入现有原生屏幕键盘。没有运行 Android 容器、APK 或 Java 虚拟机，也不只是更换键盘外观。

这是有范围限制的原生移植，**不是完整 FUTO Android 应用**。中文继续使用已经安装的水杉；Wayland 窗口、悬浮/停靠和实体键盘抑制复用 [Fcitx5 OSK 集成](../input-method/README.md)。`0.2.0` 将核心 UI/UX 重绘为原生 Rust/Iced 组件：候选/动作栏、字母和符号页、分类表情、文本编辑、设置与关于页。没有运行 Android Compose。滑行解码、空格滑动光标、神经语言模型、语音、完整 Android 设置、表情搜索/肤色选择尚未移植；英文只支持 QWERTY/en_US。

## FUTO UI/UX

- 四行 QWERTY、原版 Roboto 字体、9dp 键帽圆角、主题主色的椭圆回车；保留长按数字/符号，默认不显示提示。当前设备使用较小字号：中文键帽默认大写、英文默认小写；大写显示不改变发给水杉的拼音。Shift 点一次用于下一字母，再点锁定大写，第三次恢复小写。
- 顶部保留 FUTO 的「候选 ↔ 动作」结构；候选为纯文字与分隔线，去掉自创品牌标题和候选胶囊；展开动作时新增一行动作图标，保留候选行。更多候选可展开网格并翻页。原版麦克风图标保留，点击明确说明离线语音尚未移植，不进行录音。
- `?123` / `ABC` 切换字母和符号，两层符号页；表情页按原项目内附 XML 分为五类，共 844 个条目，保留多码点序列。它不是全部最新 Unicode 表情库。
- 文本编辑页提供全选、剪切、复制、粘贴、撤销/重做、方向键、行首/行末和退格。仅在用户点击时发送原生按键，不轮询或导出剪贴板。
- 设置页可切换悬浮/停靠、进入键盘配置和关于页；浮窗底部手柄长按约 0.7 秒拖动，底部键盘图标切换中英。锁屏不开放表情/剪贴板/文本编辑页。
- 中文仍用水杉。表情通过 Fcitx 内部 Unicode 提交桥上屏，不靠剪贴板替换；只接受当前键盘连接，拒绝密码/敏感框及尚未完成的组合输入。应先选定中文候选，再插入表情。

源码为 [futo_ui.rs](ui/futo_ui.rs) 和 [futo-ui.patch](futo-ui.patch)，由 `prepare-osk-ui.py --futo-ui` 应用。参照固定 FUTO 源码的 `ActionBar.kt`、`v2keyboard/Keyboard.kt`、`DefaultLightDark.kt` 和布局 schema，将交互接到 Linux 输入接口；不是修改 Android 包后在容器中显示。

原版箭头、Shift、退格、表情、麦克风等矢量路径由准备器从固定源码转换为 SVG；回车保留原始图形。图标不再由 Unicode 字符代替。[官方外观参考](https://keyboard.futo.tech/)用于人工对照，原图不入仓库。Linux 的字体/DPI 与 Android 不同，字号和浮窗大小另有设备偏好配置；没有把源码检查登记为逐像素一致的视觉验收。

## 架构与范围

```text
实体键盘 / Linux 原生触屏键盘
                  ↓ Fcitx5 VirtualKeyboard / 原生输入上下文
     中文 msime ← 中英切换 → sheng-futo 英文引擎
                                ↓
                    FUTO/LatinIME C++ 输入候选核心
                                ↓
                  上游公开词条转换的只读 v403 词典
                                ↓
                       原应用预编辑 / 候选上屏
```

- `linux-core.patch` 增加无 JNI 对象的布局构造器和原生候选读取。Android 构造器与原有算法保留。JDK 仅提供构建头文件；运行时不链接 JVM。
- `futo-core.cpp` 调用上游 `Dictionary::getSuggestions`，不是自建模糊词典；英文拼写错误可通过触屏选择纠正。空格默认保留原输入，避免未经确认的自动替换。
- `fcitx-engine.cpp` 使用每个输入上下文独立的预编辑状态；密码/敏感输入直接交回 Fcitx，不查询词典。不保存输入记录、学习词库或联网请求。
- `prepare-futo-keyboard.py` 验证固定 archive/patch SHA；从上游布局生成 Linux 键位映射、从 Kotlin 默认配色生成 Linux 主题。当前只接受明确支持的 QWERTY schema，其他布局拒绝并要求适配。
- 保留数字行、长按候选键、中文、水杉候选、悬浮/停靠和自动弹出策略。英文工具栏入口只在检测到 `sheng-futo` 引擎后启用，未安装时保持原来的中英切换。

## 来源与许可

原项目：[FUTO Keyboard](https://github.com/futo-org/android-keyboard)，主仓库为 [FUTO GitLab](https://gitlab.futo.org/keyboard/latinime)。固定 commit、布局子模块 commit 与 SHA 见 [provenance.json](provenance.json)。

上游使用 **FUTO Source First License 1.1-kb**，对修改及分发有非商业限制，不应称为 OSI 开源或改标为本仓库 GPL/MIT。请阅读准备后的 `LICENSE.md`、`NOTICE` 和每个文件的声明；不得删除其声明或绕过付款限制。本构建只使用原生输入组件，不改动上游 Android 支付相关源码，也不分发其 APK。[支持原项目](https://keyboard.futo.org/)。布局独立使用 Apache-2.0；新 Linux 适配代码的 MIT 范围见 [LICENSE](LICENSE)。生成的主题、词典、合并二进制仍保留相应上游许可，不能仅套用适配器许可。

## 从公开源码构建

在 ARM64 Kali Linux 上操作；Windows 只负责源码准备与传输。先按水杉集成说明安装可用的 `sheng-msime-integration 0.2.1-8`；构建该版本时使用下面的 `--futo-ui` 入口，否则只有原界面中的英文引擎入口。不要用 PowerShell 编译 Linux ELF。

```bash
# Rust/Cargo 和 OSK 开发依赖见 input-method/README.md
python3 scripts/prepare-osk-ui.py --futo-ui --output-dir out/futo-osk-source
cmake -S out/futo-osk-source -B out/futo-osk-build \
  -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=lib/aarch64-linux-gnu
CARGO_BUILD_JOBS=2 cmake --build out/futo-osk-build --parallel 2
DESTDIR="$PWD/out/futo-osk-stage" cmake --install out/futo-osk-build --component Fcitx5Osk
DESTDIR="$PWD/out/futo-osk-stage" cmake --install out/futo-osk-build --component Fcitx5OskKwinLauncher
python3 device/input-method/build-device-package.py out/futo-osk-stage \
  scripts/keyboard-policy.py out/packages/sheng-msime-integration_0.2.1-8_arm64.deb
sudo apt-get install ./out/packages/sheng-msime-integration_0.2.1-8_arm64.deb
```

```bash
sudo apt-get install -y build-essential cmake ninja-build git python3 \
  default-jdk-headless qt6-base-dev libfcitx5core-dev \
  libfcitx5config-dev libfcitx5utils-dev fcitx5-modules-dev
python3 scripts/prepare-futo-keyboard.py
cmake -S device/futo-keyboard -B out/futo-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
  -DFUTO_SOURCE="$PWD/out/futo-source"
cmake --build out/futo-build --parallel 2
out/futo-build/sheng-futo-tool --import \
  out/futo-source/linux-data/en_US.tsv out/futo-en_US
cmake -S device/futo-keyboard -B out/futo-build \
  -DFUTO_DICTIONARY="$PWD/out/futo-en_US"
ctest --test-dir out/futo-build --output-on-failure
python3 device/futo-keyboard/build-device-package.py \
  out/futo-build out/futo-source out/futo-en_US \
  out/packages/sheng-futo-keyboard_0.3.0-3_arm64.deb
sudo apt-get install ./out/packages/sheng-futo-keyboard_0.3.0-3_arm64.deb
# 解锁状态，以桌面用户执行；只重载输入面板
sheng-futo-keyboard-setup
# 已启用过旧版时，保留原回退备份并重新加载升级后的界面
sheng-futo-keyboard-setup --refresh --compact
```

准备器和词典导入要求新的空输出目录；重复构建应指定新目录。第三方源码与二进制不提交，其他开发者不需要作者 `.work`。打包器只打包编译产物并复验词典，不代替 C++ 编译。包依赖匹配 Fcitx5 与 Qt ABI，不能跳过依赖或移植其他架构二进制。

## 使用与回退

中文使用水杉；触屏工具栏/底行的「中/EN」切到 FUTO 英文，再点可返回中文。英文输入显示原词及纠错候选，点击候选会提交该词和一个空格。空格提交原词，退格修改组合，Esc 取消。物理键盘可在 Fcitx 配置中选择该英文引擎；水杉默认项仍保留。

原布局和当前悬浮/停靠尺寸保留；安装程序只改允许的 OSK 根键和当前输入法组，私有备份位于 `~/.local/state/sheng-futo-keyboard`。不导出用户词库或 Fcitx 账号信息。

`--compact` 在悬浮状态使用横屏 400、竖屏 300 逻辑像素宽，等比例缩小键盘；普通 setup 保留原尺寸。当前设备选择此模式。字体按键高的较小比例显示；切回旧界面可使用下面的完整回退，或自行在设置中调整尺寸。

```bash
# 先恢复界面与中英入口，再卸载新引擎；水杉集成继续保留
sheng-futo-keyboard-setup --restore
sudo apt-get remove sheng-futo-keyboard
```

若启用后又修改过键盘设置，回退器会停止覆盖并要求核对自己的备份。不能通过全局重启 Plasma/KWin 刷新。锁屏、挂起恢复和物理触屏输入需要分别验收，不能用 CTest 通过替代用户实际输入确认。

## 本机验证

2026-11-15，sheng / ARM64 / 上述 ABI：已安装 `sheng-futo-keyboard 0.3.0-3`、`sheng-msime-integration 0.2.1-8`；原生核心及模块编译通过，导入 160325 条公开 unigram。`hellp → hello`、`tge → the`、空/超长输入通过；60 次查询约 52 ms（仅本轮轻量检查，非功耗或完整输入延迟基准）。隔离 Fcitx 实例验证候选/上屏、预编辑、退格、空格、按键释放、上下文隔离、密码/敏感框直通，通过。

用户确认新尺寸/字号、中文大写/英文默认小写键帽、双层符号、分类表情上屏及动作栏正常；专用测试窗记录中英已知样本均匹配。翻页修复后用户确认前后翻页与选词上屏正常。最终 OSK 的 `cargo check` 和 ARM64 优化构建成功，安装/运行 ELF 与本机构建一致；编译峰值约 5.8 GiB，不等于运行时占用。PIN 接入/拔下抑制、锁屏解锁、挂起恢复、竖屏仍需在此版本独立回归。
