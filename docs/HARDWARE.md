# 设备与版本兼容矩阵

参考实机：Xiaomi Pad 6S Pro 12.4，代号 `sheng`，型号 `24018RPACC`，本次测试约 12 GB RAM。其他容量/SKU、键盘固件、其他平板未独立验证。

| 层 | 本次参考版本 | 约束 |
| --- | --- | --- |
| 用户空间 | Kali rolling ARM64 | 不混用 Debian 软件源；rolling 不保证未来仍提供同版包 |
| 内核 ABI | `7.3.4-sm8550-00104-g87ac0f2347eb` | PIN 修复模块必须完全匹配 |
| 内核源码 | `ianchb/sm8550-mainline@87ac0f2347eb433933841e6854950dd90e96e6b2` | 工具链 Clang 21.1.8-13、相同配置/导出符号 |
| Plasma/KWin | 6.7.4，Wayland | QML 效果及内部面板对象依赖此接口，升级需复测 |
| 原生网络 applet | `plasma-nm 4:6.7.4-2+b1` | 补丁包严格绑定此 Debian 包版本 |
| 图形 | Adreno 740、Mesa 26.1.6、主线 drm/msm | freedreno GL、Turnip Vulkan；无 Android KGSL |
| 触屏 | `xiaomi-sheng-thp 0.3.9`、libssc | 固定资产与哈希见 sources.json |
| PIN | `sheng-dock-fix 1.2-2`、模块 `1.2-shengfix` | 必须配合安全存储认证服务 |
| 控制中心 | `0.7.7-sheng-privacy4` | 固定 Kontrol Center 上游 + 本地 patch |
| 输入法集成 | msime-linux 0.16.1、Fcitx5 5.1.23、OSK 0.2.1 + 集成包 0.2.1-3 | PIN/触屏中文、抑制软键盘、连续弹出及新界面拖动/模式切换已确认；锁屏/挂起恢复待验收 |

## 硬件范围

| 硬件 | 已有证据 | 未覆盖范围 |
| --- | --- | --- |
| 显示/触屏 | Wayland 桌面、200% 缩放、触屏可用；恢复后缩放/键盘曾用户确认 | 长期恢复/多屏矩阵 |
| Wi-Fi/热点 | 上网、并发 AP、另一设备连接上网、面板开关用户确认 | 监听/注入能力、多客户端压力与所有路由器组合 |
| 扬声器/音量键 | 出声、加减音量用户确认 | 非声学校准，无测量麦克风的全频声压评价 |
| PIN 键盘/触摸板 | 未拔插恢复、自动唤醒后输入用户确认 | 所有固件、长时间压力与机械接触故障 |
| 蓝牙 | 控制器开关/扫描 | 实际配对、传输、蓝牙音频未验收 |
| 电池 | 电量图标、充电状态接口 | 电池寿命或功耗精确测量 |
| USB | RNDIS/SSH、CDC ACM 串口 | 所有 Windows 驱动组合 |
| 摄像头/麦克风 | 隐私阻断与恢复路径、测试采集句柄 | 摄像质量、实际录音质量未验收 |
| GNSS/GPS | 接口拒绝策略 | 未检测到可用 GNSS 硬件，未做实际定位 |
| 指纹/手写笔 | 无完成证据 | 尚未验证 |

## GPU 选择

freedreno 和 Turnip 分别提供 OpenGL 与 Vulkan，当前可以同时安装，底层使用同一主线内核路径。现有 OpenGL 应用通过 Zink 转到 Turnip 会增加另一层转换；不能把原生 Vulkan 的局部成绩当作所有桌面软件收益。

本次选择 KDE/Burp 使用直接 OpenGL，原生 Vulkan 程序使用 Turnip。GPU 共享内存已计入 RAM，监视器不提供独立显存；全局指标不保证逐进程 GPU 列。基准数字、方法与限制见 [GPU 对比](gpu-efficiency-measurement.md)。[UniXNU 路径分析](unixnu-gpu-comparison.md) 未得到当前 Kali 可直接替换且更快的 Metal 栈，不把无法运行的链路写成完成实测。
