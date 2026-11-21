# Piano GPU 内存回收修复

这两份补丁来自 `yzddmr6/linux-sm8750-piano`，保留原作者、提交说明和
Co-Authored-By。源码遵循 GPL-2.0-only；这里没有添加或代签 Signed-off-by。

| 顺序 | 固定提交 | 修复 |
| --- | --- | --- |
| 1 | `e11a25e13387eee5df54ce8f610ba1d50fff7b01` | 完成的硬件 fence 从 IRQ 退休路径发出信号，不再依赖需要 BO reservation 锁的清理 worker |
| 2 | `da4b783e34bd05d7451a6f904fbf567af1215f99` | 只有 kswapd 可以等待活跃 BO，前台直接内存回收不阻塞等待 GPU |

SHA-256 固定在 [gpu-reclaim-fixes.json](gpu-reclaim-fixes.json)。构建器先回放原有
piano 补丁，再应用本目录补丁；不整体更新 piano 来源，也不修改板级 ID、充电或触屏代码。

```bash
# linux 是按 kernel workflow 准备好的真实内核源码检出。
python3 tools/apply-gpu-reclaim-fixes.py --kernel-tree linux --check-only
python3 tools/apply-gpu-reclaim-fixes.py --kernel-tree linux --report out/gpu-reclaim-fixes.json
python3 tools/apply-gpu-reclaim-fixes.py --kernel-tree linux --verify-only
python3 -m unittest discover -s tests -p test_gpu_reclaim_fixes.py -v
```

输入哈希或补丁上下文不匹配时停止；不会使用 `--reject`、忽略失败或自动偏向某一方。
已经完整应用的补丁可以重复检查。补丁校验和源码检查不等于内核编译或真机验收。

完整诊断、候选 ABI 和回退见 [GPU-RECLAIM.md](../../docs/GPU-RECLAIM.md)。
