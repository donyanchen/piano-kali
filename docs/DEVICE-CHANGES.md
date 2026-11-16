# 设备侧改动记录（2026-11-16）

> 这些是**直接改在运行中的平板上**的，不属于仓库代码。重装系统后要按这里重做，
> 或者（更好的做法）让 `build-kali.sh` 把它们变成构建步骤。

主机：`192.168.0.13`（DHCP，会变），`kali` / `kali`，系统 Kali rolling + KDE Wayland。

## 1. OSK（Fcitx5 屏幕键盘）

| 动作 | 命令 / 值 |
|---|---|
| 补装启动器 | `install -m 0755 device/input-method/sheng-msime-launcher /usr/libexec/sheng-msime-launcher` |
| 写入布局与主题 | `python3 scripts/osk-mode.py dock --sheng-ui`（需登录且**未锁屏**） |
| 关掉悬浮指示器 | `~/.config/fcitx5-osk/config.toml`: `indicator_display = "AlwaysOff"` |
| 去掉拖动长按 | 同文件：`holding_timeout = "0ms"` |

坑：

- `indicator_display` 只接受 `Auto` / `AlwaysOn` / `AlwaysOff`。写成别的值会让**整份配置解析失败**，
  OSK 静默回退默认值（表现为指示器还在、布局不生效），日志只有 `try to use default config`。
- 磁吸键盘接着时 `nanosic_hinge/keyboard_attached = 1`，`sheng-keyboard-policy` 会把 KWin
  虚拟键盘模式设为 `Never`，此时点 OSK 会「闪一下就关」——上游设计，不是崩溃。
- 拖动生硬：OSK 是 layer-shell 客户端自己 `set_position()`，每次移动都要 configure 往返；
  改配置救不了，只能改代码（Float 模式走 `xdg_toplevel` + `drag_window()`）。当前选择：保持现状。

## 2. 桌面策略（Dock 收起逻辑）

```bash
sudo cp -a /usr/libexec/sheng-desktop-policy /usr/libexec/sheng-desktop-policy.bak-$(date +%Y%m%d-%H%M)
sudo install -m 0755 <upstream>/device/desktop-policy/desktop-policy.py /usr/libexec/sheng-desktop-policy
systemctl --user restart sheng-desktop-policy
```

注意：装的是**上游原文**（`org.sheng.DesktopPolicy`），不能用本仓库里改过名的副本，否则
BusName 与 unit 对不上，服务起不来。

## 3. 顶栏去掉重复电池

系统托盘里有一个电池（小胶囊），面板上还有一个（右侧）。保留面板那个：

```bash
# 备份
cp ~/.config/plasma-org.kde.plasma.desktop-appletsrc /tmp/appletsrc.bak-$(date +%H%M)
# 去掉托盘项（运行时改配置，避免手改文件 + 重启丢失）
qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
var p = panels().filter(function(x){return x.id==22})[0];
p.widgets().forEach(function(w){
  if (w.type == "org.kde.plasma.systemtray") {
    w.currentConfigGroup = ["General"];
    var items = String(w.readConfig("extraItems","")).split(",");
    var keep = items.filter(function(i){ return i && i.indexOf("battery") < 0; });
    w.writeConfig("extraItems", keep.join(","));
    w.reloadConfig();
  }
});'
systemctl --user restart plasma-plasmashell.service
```

副作用：`org.sheng.panel-style`（部件 32）原本给托盘电池做外观，托盘项删掉后它的样式不再生效，
右侧电池变成 KDE 原生图标；重启 plasmashell 后布局也可能重新落位一次。

## 4. 待办：把这些变成构建步骤

目前都靠手工，重装必丢。P4 要做的是：

1. `build-kali.sh` 调 `device/input-method/build-device-package.py` 打包 OSK 集成（启动器 + 桌面项 + `sheng-osk-mode`）。
2. 镜像里预置 `osk-mode` 结果（或首次登录服务自动执行一次）。
3. 顶栏布局用 `device/theme/layout.js` 种子生成，而不是事后手删部件。