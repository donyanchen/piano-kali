# 状态栏热点按钮适配

公开打包器参数为 `bash scripts/build-hotspot-panel-package.sh COMPILED_SO REPOSITORY_ROOT OUTPUT_DIR`，从本仓库读取后端/服务源码，不复制当前系统的文件或热点密码。它只打包已编译 applet；编译依赖与版本边界见 [部署手册](../../docs/DEPLOYMENT.md)。

2026-11-14 已在平板安装 `sheng-hotspot-panel 1.0-2`。它修复 KDE 网络面板中热点按钮变灰、不能控制实际热点的问题。

原生 Plasma NM 6.7.4 只根据 NetworkManager 管理的连接判断热点支持和状态；当 Wi-Fi 上网占用 `wlan0`，独立 `sheng-ap` 由 hostapd 管理时，按钮会判定所有无线网卡都在使用。本适配仅重建网络面板 applet，让原来的“热点”按钮调用已有 `sheng-hotspot.service`，并根据 `/run/sheng-hotspot/ready` 同步显示状态。普通 Wi-Fi 连接仍使用原来的 NetworkManager 库。

控制器通过系统总线的 StartUnit/StopUnit 调用服务，沿用已有的单服务 Polkit 授权。文件系统监听覆盖 `/run`、服务运行目录和 ready 文件，服务停止、失败重启、挂起恢复后都能重新绑定状态监听。启动或停止期间阻止重复点击，实际失败时才显示错误通知。没有后台轮询，也不读取或修改热点密码。

代码基于 [KDE/plasma-nm](https://github.com/KDE/plasma-nm/tree/v6.7.4) 提交 `b6c03fe24b30d2a963a41dd83784e36086d7257e`，对应当前安装的 `plasma-nm 4:6.7.4-2+b1`。修改见 [applet.patch](applet.patch) 和本目录的控制器源码。使用本目录的精简 CMakeLists 重建原始源码中的 applet，保留其他网络管理组件。

已经完成独立预览加载检查、普通桌面用户权限检查，以及通过实际系统总线执行热点开启/关闭并恢复初始状态的测试。测试前后 `wlan0` 上网连接 UUID 一致。正式状态栏更新后，用户确认按钮可以点击，并能正常开关热点。验证结果合并到本机 `out/keyboard-hotspot-cleanup-verification.json`；旧报告和测试截图已清理。

安装包保存在 `out/packages/sheng-hotspot-panel_1.0-2_arm64.deb`，打包脚本为 [build-hotspot-panel-package.sh](../../scripts/build-hotspot-panel-package.sh)。补丁包通过 `Replaces` 接管原 applet，同时纳管现有热点后端、服务和授权规则。热点名称及密码配置保留在 `/etc/sheng-hotspot/`。平板只保留状态栏控制入口，旧的独立菜单开关已删除。

按用户要求，原版 `.distrib` 备份和旧 diversion 已移除，卸载补丁不会自动恢复原版。若需恢复系统网络面板，必须重新安装发行版包，并重新加载面板：

```sh
sudo systemctl stop sheng-hotspot.service
sudo apt remove sheng-hotspot-panel
sudo apt install --reinstall plasma-nm
sudo systemctl daemon-reload
systemctl --user restart plasma-plasmashell.service
```

修复包依赖精确的 plasma-nm 包版本。升级 Plasma NM 前需要为新版本重建适配或移除此包。此前导出的 rootfs 镜像尚未重新打包此适配。
