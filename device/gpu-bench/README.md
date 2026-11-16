# sheng 上的 OpenGL / Vulkan 实机对比

测试三条路径：Mesa freedreno 的原生 OpenGL、Mesa Turnip 的原生 Vulkan，以及同一 OpenGL 程序通过 Zink 调用 Turnip。二者属于不同 API，通常同时安装。原生 Vulkan 的成绩不能直接作为现有 OpenGL 程序的迁移收益；Zink 组用于观察后一种情况。

`bench.cpp` 在两种 API 中使用同一全屏三角形、片元着色器算术、3048×2032 RGBA8 目标和混合／裁剪设置。三种负载是单次填充、两层 32×32 网格共 2048 次透明混合绘制，以及 64 次向量／正弦迭代。各路径将最终图像读回并用 SHA-256 比较，图像处理不计入计时。

这是无显示、无垂直同步、每次等待一帧完成的测试。Vulkan 每帧重新录制命令缓冲区。测量墙钟帧时间、进程 CPU 时间、API GPU 时间戳及进程 RSS/PSS；不测量直接电功率，也不把这些结果视作 KDE 或 Burp 的帧率。未映射到 CPU 的 GPU 分配不包含在 RSS/PSS 中。

每次进程先预热 1 秒，再计时 4 秒，共重复三轮。`run.py` 在每个负载内轮换三种路径的先后顺序，并轮换负载顺序；各路径分别占据一次第一、第二、第三测试位置。GPU 限制临时设为已有合法档位 550 MHz，记录实际频率及 GPU 温度；CPU 保持原有 governor，进程使用核心 4–7。脚本的 `finally` 和服务的 `ExecStopPost` 都会恢复原先 GPU 范围。测试程序以普通 kali 用户运行。

在平板准备依赖，将本目录文件复制到 `~/.local/state/sheng-gpu-bench/`，然后运行：

```sh
sudo apt-get install --no-install-recommends libegl-dev libepoxy-dev libvulkan-dev glslang-tools pkg-config g++
bash ~/.local/state/sheng-gpu-bench/build.sh
sudo bash ~/.local/state/sheng-gpu-bench/start.sh balanced
journalctl -fu sheng-gpu-benchmark.service
```

服务结束后运行 `python3 ~/.local/state/sheng-gpu-bench/verify-images.py balanced`。结果位于 `results-balanced/`、`run-report-balanced.json`、`telemetry-balanced.json` 和 `image-validation-balanced.json`。仅在生成原始结果后分析；本机导出目录使用不含 `-balanced` 后缀的报告名称，再以 `python device/gpu-bench/analyze.py out/gpu-bench-balanced` 生成摘要，需要 NumPy。

`Java2DDriverBench.java` 补充测试 Java2D 的表格、文字和透明图形绘制。它通过进程环境分别使用 freedreno 和 Zink/Turnip，保持现有桌面配置不变，并在每个 120 帧批次末尾读回图像以等待 GPU 完成。每次五个批次，第一个排除，重复三次；它仍不是完整 Burp 操作延迟测试。运行前应确认 C++ 测试已经完成，避免并发测试相互干扰。

2026-11-14 的初步系列保存在本机 `out/gpu-bench/`，当时不同负载轮换顺序，但同一负载内部的路径顺序固定。完整交换顺序并验证输出的复测使用 `verified` 标签，另存为 `out/gpu-bench-verified/`，用于最终主结果，不覆盖初步记录。完整 Metal → metal2vulkan 路径不属于此次测试。

参考：[Mesa freedreno / Turnip](https://docs.mesa3d.org/drivers/freedreno.html)、[Zink](https://docs.mesa3d.org/drivers/zink.html)、[Khronos GPU 时间戳](https://docs.vulkan.org/guide/latest/profiling.html)。
