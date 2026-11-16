# Burp Suite 平板配置

本仓库仅提供 ARM64 平板的公开性能和显示参数。Burp 本体从 [PortSwigger 官方](https://portswigger.net/burp/releases) 获取并校验；Community 可免费使用，Professional 使用有效许可证，按[官方激活步骤](https://portswigger.net/burp/documentation/desktop/getting-started/activating-burp-license)配置。仓库不含安装包、许可证、用户项目或第三方激活组件。

## 安装与性能

下载适合 Linux ARM64 的官方安装包，安装到自己的应用目录。参考启动器 [sheng-burpsuite.sh](../scripts/sheng-burpsuite.sh) 默认路径为 `$HOME/.local/opt/BurpSuite/BurpSuite`，其他安装位置先修改该路径。它仅为 Burp 设置 `MALLOC_ARENA_MAX=4`，清除旧 Zink/Turnip 环境覆盖，使用系统默认 freedreno/OpenGL，不更换全局 Java。

将 [JVM 参数模板](../configs/burp-user.vmoptions) 合并到该安装器支持的应用专用 `user.vmoptions`；先备份，不要覆盖厂商默认文件或用户已有的必要选项：

```text
-Xms128m
-Xmx6g
-XX:+UseG1GC
-Dsun.java2d.opengl=True
-Dflatlaf.uiScale=1.7
-Xshare:auto
```

最大堆 6 GiB 不包括本机库、图形缓冲区和 Chromium 子进程。本次参考设备约 12 GB RAM；较小内存设备应降低上限，不能仅靠 swap 保证大型扫描可用。G1 与较小初始堆是本机选择，不承诺所有项目更快。

## 高分屏

当前目标为 170% 应用缩放，菜单字体约 14、HTTP报文字体约 15。示例使用 FlatLaf 的 `uiScale=1.7`；在 Burp 中避免再次叠加等比例缩放。更换 Burp/JRE 后重新检查字体和实际合成倍率，保存项目后重启才生效。参考 [Burp 显示设置](https://portswigger.net/burp/documentation/desktop/settings/ui/display) 和 [FlatLaf 参数](https://www.formdev.com/flatlaf/system-properties/)。

## GPU 与启动

当前 Burp 主界面采用 Java2D OpenGL，由 freedreno 承载。JRE 不一定带原生 Vulkan UI 管线；Zink → Turnip 只改变 OpenGL 底层承载，不等于把 Burp UI 重写为 Vulkan。[实机基准](gpu-efficiency-measurement.md) 中 Java2D 小样本没有证明完整 Burp 工作流稳定提速，因此公开默认参数使用直接 OpenGL。

`-Xshare:auto` 使用可用的 CDS 缓存；没有兼容缓存时不保证启动提速。自定义 CDS 必须使用相同 JRE 和类路径生成，不能复用其他机器/JRE 的缓存。内置浏览器 GPU 设置独立于 Java2D，需要按[官方浏览器设置](https://portswigger.net/burp/documentation/desktop/settings/tools/burps-browser)另行检查。

## 验收与回退

先用空白项目检查主窗口、菜单和请求编辑器可读；确认 bundled Java 的堆限制和 OpenGL 实际启用。不要为了性能测试关闭或重开用户未保存项目。性能测量记录相同版本、项目、插件、冷热启动、RSS/PSS 与就绪条件，区分 JVM 和浏览器子进程。

关闭 Burp 后恢复自己的 `user.vmoptions`、显示设置和菜单入口备份即可回退。参数不进入系统级 Java 环境，不改动用户项目内容。基础 rootfs 未自动安装此商业应用。
