# UniXNU 与当前 Kali GPU 路径

检查日期：2026-11-14。未发现可将 UniXNU 判为更高效的同条件测试，因此保留当前已验证的 Linux GPU 驱动。

当前 Kali 使用 Linux MSM DRM/KMS，OpenGL 由 Mesa freedreno 提供，Vulkan 由 Mesa Turnip 提供。实机已确认 FD740 硬件加速、OpenGL 4.6、Turnip Adreno 740 Vulkan 1.4；先前约 144 FPS 的 glxgears 结果受屏幕垂直同步限制，不是 GPU 最大性能分数。

[AdrenoMetal README](https://github.com/UniXNU/AdrenoMetal/blob/73d582fd4d5772b1f5fa83581a25077a16f2b6cd/README.md) 描述的是 Metal 前端经 metal2vulkan 转换，再使用 Turnip 的路径。其 GPU 内核接口和运行时针对所选 Apple OS ABI；[设备项目](https://github.com/UniXNU/UniXNU-sheng) 使用 XNU、IOKit/IOGPU、IOSurface 及 Apple 系统镜像。它不是可直接替换 Linux DRM 驱动的内核模块。当前 Kali 本来就已有它所复用的 Turnip 后端。

[porting.toml](https://github.com/UniXNU/UniXNU-sheng/blob/main/porting.toml) 的帧率记录比较的是 iPadOS 上不同 Metal runtime 选项，部分其他验证在 Apple M1/MoltenVK 主机完成。这些记录没有和 Linux 下同一工作负载、分辨率、采样数、时钟、温度、同步方式和功耗进行比较。不能把它们与 KDE 桌面或 glxgears 的帧率直接相除得出效率结论。

要证明替换更高效，应在相同硬件上使用相同渲染任务，比较正确渲染结果、帧时间分布、CPU/GPU 时间、驻留内存和每帧能耗。现有资料不能满足这个条件。Metal 到 Vulkan 的转换是兼容性路径；仅增加这一层不会使现有 Kali OpenGL/Vulkan 程序自动变快。

后续实机检查确认：当前 Kali 没有 `xcrun` 和 `/System/Library/Frameworks/Metal.framework`，因此无法执行所述完整 Metal 路径。上游 [host qualification 脚本](https://github.com/UniXNU/UniXNU/blob/main/scripts/check-native-metal-frontend-host.py) 链接 Foundation、Metal、IOSurface 和 CoreFoundation，并明确说明主机检查不建立 Turnip、Adreno 740 或 SMMU 的正确性。完整的跨系统效率对比仍未完成，也未据此替换系统或驱动。

Burp 调优期间，使用其自带的 ARM64 Java 26.0.2 在平板运行了独立 Java2D 测试和空白 Burp 项目。OpenGL 配置返回 `sun.java2d.opengl.GLXGraphicsConfig`、加速图像能力为真，并通过 MSM DRM fdinfo 记录了 GPU 引擎时间；正式启动器同样输出 OpenGL 管线启用并打开 `/dev/dri/renderD128`。这些结果验证 Linux GPU 加速可用，不能作为 Metal 与 freedreno 的对比成绩。测试原始记录保存在本机 `out/burp/`，验证摘要为 `out/burp-verification.json`。

随后完成了 [freedreno / Turnip 实机测试](gpu-efficiency-measurement.md)，比较原生 OpenGL、原生 Vulkan，以及 OpenGL 经 Zink 调用 Turnip。这次原生 Linux 测试包含相同输出的渲染校验，仍不构成 Metal 路径的跨系统对比。
