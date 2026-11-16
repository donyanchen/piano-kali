# piano ↔ sheng 对照（哪些照搬、哪些必须改）

上游：`LuKeyC-NetSEC/sheng-kali-linux`，锁定提交见 `vendor/sheng-kali.lock.json`。
本仓库只保存**差异**：能直接用的组件由 `scripts/sync-sheng-base.sh` 拉取上游后原样安装，本文记录
必须为 piano 修改的部分，避免下次再从零摸索。

## 1. 可以直接照搬（用户态，与 SoC 无关）

| 组件 | 上游路径 | 安装方式 |
| --- | --- | --- |
| 控制中心 | `device/control-center` | plasmoid，直接放进 `~/.local/share/plasma/plasmoids` |
| Linexin Dock / 抽屉 | `device/linexin-dock` | `scripts/build-desktop-drawer.py` 构建，`install-desktop-drawer.py` 迁移 |
| 面板样式（白电池） | `device/theme/panel-style` | plasmoid |
| 桌面手势 + 隐私策略 | `device/desktop-policy`、`device/privacy` | `device-guard.c` 用 gcc 编译后打包 |
| KWin 桌面触摸守卫 | `device/desktop-touch-guard` | `scripts/build-desktop-touch-guard.sh`（按本机 KWin ABI 编译） |
| 任务卡片 / 三指切窗 | `device/recents` | `gesture-bridge.cpp` + `build-task-cards.py --install` + `install-native-tabbox.py` |
| 软键盘 | `device/input-method`、`scripts/prepare-osk-ui.py` | fcitx5-osk 0.2.1 + `hyperos-ui.patch` / `--futo-ui` |
| FUTO 英文引擎 | `device/futo-keyboard`、`scripts/prepare-futo-keyboard.py` | 上游词典 core 编成 `sheng-futo.so` |
| OSK 键盘策略 | `scripts/keyboard-policy.py` | 用户级 systemd 服务 |
| GPU 监控 | `device/gpu-monitor` | ksystemstats 插件 + collector |
| 桌面配置 | `device/theme/desktop-profile.json`、`layout.js`、`WeatherData.qml` | 本仓库 `scripts/apply-sheng-desktop.py` 套用 |

## 2. 必须为 piano 改的（硬件相关）

| 上游做法 | piano 事实 | 处理 |
| --- | --- | --- |
| `sheng-hotspot` 独立 AP（hostapd + sheng-ap） | **已验证可用**：ath12k_wifi7 报告 `#{managed}<=1, #{AP,...}<=16, total<=16, #channels<=2`，实测 `sheng-ap` 起来后 wlan0 仍保持上游连接 | 照搬上游，仅把 `xiaomi,sheng` 设备守卫放宽为 `sheng` 或 `piano`；脚本装到 `/usr/libexec/sheng-hotspot/{setup,hotspot}.py` |
| `device/keyboard-auth`（sheng_devauth） | piano 是 Nanosic WN8030，走 `nanosic_auth`/`nanosic_hinge` | 不装，PIN 解锁不适用 |
| UCM `Qualcomm/sm8750/Xiaomi-Pad-8-Pro/HiFi.conf` 用 sheng 的声道假设 | piano 四个功放分别挂 TDM slot 0–3（摄像头侧 L/R、触点侧 L/R） | 保留 piano 自己的 UCM；四扬声器需要 ASoC 侧复制，见第 3 节 |
| `sheng-desktop-sleep` 挂起钩子 | piano 挂起不稳（已关自动挂起） | 钩子脚本照搬，但 `AutoSuspendAction` 保持 0，只在手动挂起时生效 |
| 隐私 udev 规则按 sheng 的 `/dev/video*` 命名 | piano 视频节点是 `qcom-camss` + ad27000 ISP，名称与 sheng 不同 | 保留上游规则并用 piano 的实际节点名补一条，不改语义（只封摄像头/麦克风/定位） |
| `20-sheng-sddm-display.conf` 里 `InputMethod=qtvirtualkeyboard` | 我们走 fcitx5-osk | 保留我们的 sddm 配置 |

## 3. 已知未完成项（真差异，非配置问题）

1. **下排两个扬声器**（已定位，未修）
   官方运行 DTB（取自 `os4-backup/piano-live.dtb`）与主线 DTB（`piano-boot.dtb`）对比结论：

   | | 官方 Android DT | 主线 piano DT |
   | --- | --- | --- |
   | 功放 | 2× WSA macro，4× `qcom,wsa884x`（SoundWire） | **4× Foursemi FS19xx**（I2C 0x34–0x37），`sound-name-prefix` = Top Left / Top Right / Bottom Left / Bottom Right |
   | 声卡 | `qcom,sun-asoc-snd`，`qcom,dedicated-wsa2`，`tdm-max-slots=4` | `xiaomi,piano-sndcard`，单条 `speaker-dai-link` |
   | TDM | — | `dai-tdm-slot-num=4`，`dai-tdm-slot-rx-mask=<1 1 1 1>`，codec 顺序 TL,TR,BL,BR |

   实测声道：ch0=Top Left（摄像头侧）、ch1=Top Right（触点侧）、ch2=Bottom Left、ch3=Bottom Right。
   **硬件链路是通的**（4 个 slot 各自对应一个 FS19xx），缺的只是“立体声 → 4 slot”的复制：
   L 应进 slot 0/2，R 进 slot 1/3。

   已排除：PipeWire `channelmix.upmix`（psd/simple）、`module-loopback`、`module-remap-sink`、
   ALSA `route` PCM（ACP 只认 UCM 里的 hw PCM，会把名字加 `_ucm0001.` 前缀）。
   可行修法（按代价排序）：
   1. DTB 拆成两条 `speaker-dai-link`（TL+TR / BL+BR，各 2 slot）+ machine driver DPCM 复制 —— 要改内核；
   2. machine driver `hw_params` 里把 2ch 扩成 4ch 并按上表复制 —— 要改内核；
   3. 让 ACP 接受自定义 ALSA PCM（改 WirePlumber 策略）—— 无内核改动，但要对 ACP 打补丁。

2. **指纹**：`mi_fp` 走 TEE（QSEE/Goodix TA），主线内核无 DT 节点，不可达。
3. **摄像头**：`piano-camerad` 已装，KDE 侧没有应用集成，只能用 pianocam/V4L2。

## 4. 复现顺序（按上游 DEPLOYMENT.md）

```bash
scripts/sync-sheng-base.sh                 # 拉取锁定提交
bash scripts/build-kali.sh                 # Kali 根文件系统 + 设备包
python3 scripts/apply-sheng-desktop.py     # 主题/面板/时钟/profile
# 用户态组件（均为上游脚本）
python3 vendor/sheng-kali/scripts/build-desktop-drawer.py
python3 vendor/sheng-kali/scripts/install-desktop-drawer.py --launcher-id <plugin>
bash  vendor/sheng-kali/scripts/build-desktop-touch-guard.sh
python3 vendor/sheng-kali/scripts/build-task-cards.py --install
python3 vendor/sheng-kali/device/recents/install-native-tabbox.py
```

每一步验收按上游 `docs/VALIDATION.md`，不把作者实机成绩当成本机结果。
