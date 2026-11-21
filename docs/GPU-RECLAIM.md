# Piano GPU：内存压力下的长时间桌面停顿

适用对象：Xiaomi Pad 8 Pro / piano / SM8750 / Adreno 830。
核对基线：`piano-kali@def1d61d1d59818962ebcd40c435243db7d08136`。
当时运行内核为 `7.4.0-rc3-piano8+`，Plasma 6.7.4、Qt 6.11.2、Mesa 26.2.6。

## 源码问题

原工作流将 `linux-sm8750-piano@1c21cb9895d69c1c5e83ceae68952fedf522644a`
回放到 Linux `v7.4-rc3`。两个输入中的 MSM 代码都保留了以下逻辑：

1. `msm_gem_shrinker.c:can_block()` 允许直接回收等待 GPU fence。
   分配内存的前台线程可能已经持有 GPU buffer reservation 锁；扫描大量活跃 BO 时，
   逐个等待超时会放大成很长的桌面停顿。
2. `msm_gpu.c:msm_gpu_retire()` 只更新已完成序号、排队清理 worker。
   完成信号依赖会获取 reservation 锁的退休流程，可能与上述等待互相阻塞。

上游修复说明包含 SM8750 上内存压力触发的实际等待栈：

- [e11a25e：从 IRQ 退休路径发出已完成 fence 信号](https://github.com/yzddmr6/linux-sm8750-piano/commit/e11a25e13387eee5df54ce8f610ba1d50fff7b01)
- [da4b783：只有 kswapd 可以阻塞回收活跃 BO](https://github.com/yzddmr6/linux-sm8750-piano/commit/da4b783e34bd05d7451a6f904fbf567af1215f99)

本机观察到长时间整屏停顿、内存压力和显示提交失败，与该机制吻合；没有取得本次停顿的
完整内核等待栈，因此仍是高优先级候选原因，不登记为已经证明的唯一根因。
THP ALWAYS 会影响内存分配行为，但这次候选先保持原有 THP 策略，单独验证驱动修复。

## 构建接入

补丁和来源哈希在 [kernel/patches](../kernel/patches/README.md)。它们在原回放流程后应用，
之后保留既有 GPU chip-ID 修正、原厂 DTBO 隔离和板级 ID 流程。

候选内核使用 **`-piano9`** ABI，并显式设置空 `LOCALVERSION` 以避免额外的 `+`。
完整构建必须重新编译同 ABI 的模块，包括磁吸键盘模块；不拼接 piano8 的模块。
`fast_only` 产物不作为完整安装包使用。

正常分支仍手动运行 kernel workflow；`fix/gpu-reclaim-stalls` 分支仅在 GPU 补丁、应用器或
该工作流变化时自动构建候选。源代码检查和 kernel 编译是不同的检查。

产物新增 `gpu-reclaim-fixes.json` 与 `kernel-build-manifest.json`，后者固定工作流提交、
内核输入、补丁哈希、运行 ABI 及 Image/config/DTB 的 SHA-256。
核对运行镜像仍需按 [boot-dtb-identity.md](boot-dtb-identity.md) 的证据链；
新 artifact 存在或版本名相似不能说明设备已经运行它。

## 验证状态（2026-11-21）

| 项目 | 方法与结果 |
| --- | --- |
| 原固定 piano 源码 | 两份补丁预检查、应用、源码检查及重复执行通过 |
| 原始 v7.4-rc3 源码 | 同样的两文件应用与源码检查通过 |
| 应用器保护 | 校验失败、上下文失败不留下半套补丁；已应用、半已应用和只检查路径有自动测试 |
| 完整内核/DTB/模块编译 | 等待候选 CI，未登记通过 |
| 真机运行 piano9 | 未安装、未重启验证 |
| 压力下卡顿、休眠及硬件回归 | 未验证；不通过人为耗尽内存来复现 |

## 运行时对照和回退

维护者可在 root 权限下记录 `/sys/module/msm/parameters/eviction_can_block` 的原值，
临时设置为 `N`，观察是否减少内存压力下的长等待。该开关会同时关闭 kswapd 的阻塞阶段，
与正式补丁的策略不同，只用于有限时间的对照；恢复原值或重启即可撤销。
不禁用内存安全 fence，不伪造 GPU 完成，不 force-load 模块。

```bash
sudo python3 tools/msm-reclaim-workaround.py status
sudo python3 tools/msm-reclaim-workaround.py apply
# 对照完成后，恢复第一次 apply 前的值：
sudo python3 tools/msm-reclaim-workaround.py restore
```

工具仅接受 piano，回读验证布尔值，以 root-only 的 `/run` 记录保存原值；重复 apply 不覆盖
原始回退值，记录与运行内核不一致时拒绝恢复，不安装常驻服务或开机修改。
该对照减少了可阻塞的 GPU 回收工作，在高负载下仍需观察可用内存和 OOM，不能替代正式修复。

安装候选前保留可用的 piano8 启动镜像、DTB 和完整匹配模块。源码修复和 CI 不自动刷写
分区、不清数据、不重启用户会话；具体安装按设备已有启动流程另行核对。
