# sheng 的 freedreno / Turnip 实机对比

日期：2026-11-14。设备：小米平板 6S Pro 12.4，Adreno 740，Kali ARM64，Mesa 26.1.6。结论限于本次工作负载：原生 Vulkan 的重着色器场景中，Turnip 三轮均快约 22%–24%；将现有 OpenGL 程序经 Zink 转到 Turnip，没有获得同样的收益。当前 KDE 和 Burp 使用 freedreno/OpenGL，原生 Vulkan 应用可使用已安装的 Turnip。后续应用配置调整未改变下列测试数据和结论。

freedreno 是 OpenGL 路径，Turnip 是 Vulkan 路径，当前同时存在。原生 Vulkan 的结果也包含 API 与应用代码实现差异；对现有 OpenGL 程序更直接的比较是 freedreno 与 Zink/Turnip。[Mesa 路径说明](https://docs.mesa3d.org/drivers/freedreno.html)，[Zink 说明](https://docs.mesa3d.org/drivers/zink.html)。

当前平板使用主线 `drm/msm`，提供 `/dev/dri/renderD128`，没有 `/dev/kgsl-3d0`。常见 Android 自定义驱动工具 [libadrenotools](https://github.com/bylaws/libadrenotools) 明确仅支持 Android 9+ ARM64，其实现使用 Android 链接器命名空间及 KGSL 接口。因此，不能将 Android 闭源或定制驱动包作为当前原生 Kali 的直接替换；另用高通 BSP/闭源栈需要匹配的内核与用户态集成，本次未找到已验证适配本机且整体更快的替代。对 KDE/Burp 保持 freedreno，对原生 Vulkan 应用使用已安装的 Turnip。现有软件源列表中的 Mesa 候选与已安装版本均为 26.1.6-1；没有执行驱动替换或升级。

## 主测试

3048×2032、RGBA8、无 MSAA、无深度、离屏渲染，无显示刷新率限制。GPU 临时固定在已有合法档位 550 MHz，实际采样全程也是 550 MHz；CPU 保持原 governor，进程限制在核心 4–7。每个进程预热 1 秒、测量 4 秒，每项三轮，并在每个场景中让三条路径各占一次第一、第二、第三测试位置。每帧等待 GPU 完成，Vulkan 每帧重新录制命令缓冲。

三条路径使用相同着色器算术、图元、目标尺寸、透明混合和裁剪设置。最终主系列 `verified` 共 27 次运行、38,465 个计时帧；三个场景所有路径和重复轮次的读回图像 SHA-256 完全一致。读回和文件写入均在计时及内存采样之外。GPU 温度传感器范围为 40.4–63.0°C，CPU 与内存系统仍自适应，故保留全部重复数据和波动范围。

下表为每组三次运行的 FPS 中位数，越高越好。它们是离屏测试值，不是 KDE 可见刷新率。

| 场景 | freedreno / OpenGL | Turnip / Vulkan | OpenGL → Zink → Turnip |
| --- | ---: | ---: | ---: |
| 全屏像素填充 | 739.7 | 995.4 | 767.7 |
| 2048 次界面式透明绘制 | 220.4 | 204.6 | 177.1 |
| 64 次迭代的重着色器 | 51.0 | 62.9 | 51.4 |

逐轮配对比单独相除中位数更能体现稳定性。原生 Turnip 在重着色器场景分别提高约 24.3%、23.9%、22.4%；界面场景为 +5.0%、−11.8%、−2.3%，没有稳定的领先。Zink/Turnip 的界面成绩分别降低约 9.1%、25.0%、13.5%，重着色器成绩则与 freedreno 接近。像素填充的帧率波动较大，原生 Turnip 三轮为 +57.2%、+34.6%、−7.4%，不能据此承诺稳定的 35% 加速。

界面场景的每帧墙钟耗时约为 4.53 / 4.88 / 5.64 ms，CPU 时间约为 0.81 / 0.37 / 1.38 ms。原生 Vulkan 虽减少了 CPU 开销，最终帧时间仍取决于 GPU 和同步成本。

测试进程 RSS 约为 freedreno 93–94 MiB、原生 Turnip 18.5 MiB、Zink/Turnip 110–114 MiB。这仅包含测试进程的常驻页面，不包含未映射到 CPU 的全部 GPU 分配，也不包含完整 KDE/Burp/浏览器，不能换算为完整应用的内存节省比例。没有直接测量电功率或每帧能耗，因此本次不判定谁更省电。

## Java2D 补充测试

使用 Burp 自带的 ARM64 Java 26.0.2，测试 1600×1000 的表格、文字和透明图形绘制，两组都启用 Java2D OpenGL，分别由 freedreno 与 Zink/Turnip 承载。每批 120 次绘制，批末读回以等待 GPU；每次运行五批，排除首批，三次运行交替先后顺序。GLX 诊断确认 Zink 组实际运行在 Turnip/Adreno 740。

平均每次绘制耗时的三次运行中位数是 freedreno 3.390 ms、Zink/Turnip 3.069 ms；但 Zink 的第三次运行升至 3.805 ms，慢于对应 freedreno 的 3.390 ms。这个小样本的局部中位数改善不能作为完整 Burp UI 稳定加速的证据。两组的进程 CPU 时间中位数均约 2.146 ms/次。测试结束时保留原驱动；后续按用户要求完成的 Burp 切换见 [应用配置](burp-tablet.md)，其验证记录为本机 `out/default-colors-turnip-verification.json`。

## 记录与恢复

源码及复现方法见 [device/gpu-bench](../device/gpu-bench/README.md)。本机原始逐帧数据、遥测、图像校验和摘要位于 `out/gpu-bench-verified/`，摘要为 `summary.json`；图像原件仍在平板 `~/.local/state/sheng-gpu-bench/results-verified/`。仅使用通过写入检查、完整运行和图像校验的 `verified` 系列生成主表。

测试结束后已核对 GPU 范围恢复为 220–680 MHz、governor 恢复原来的 `simple_ondemand`；测试服务及临时睡眠抑制均已结束。测试本身未更改 KDE/Burp 的默认驱动；Burp 后续调整过应用专用渲染环境，现已按用户最新要求恢复 OpenGL。完整 Metal → metal2vulkan → Turnip 路径不在本次测试中，详见 [UniXNU 路径说明](unixnu-gpu-comparison.md)。
