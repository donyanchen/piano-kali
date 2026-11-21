# 启动 DTB 的板级 ID：为什么我们的内核一直起不来

## 现象

2026-11-18 之前，CI 编出来的内核（`7.4.0-rc1-piano8+` / `rc3`）在真机上：

- A 槽、B 槽各试一次，都是 **Mi logo → 直接跳 fastboot**
- `boot-log.txt` **从未生成** —— 说明内核连 initramfs 的 `/init` 都没跑到，
  不是 systemd 挂载失败那么晚
- 显示、触摸、Wi-Fi、蓝牙、音频、充电、休眠：**全部未验证**

## 根因

ABL 只有在 DTB 的 `qcom,board-id` / `qcom,msm-id` 命中时才会把原厂 DTBO 叠上去。
我们当时的生成脚本是「照抄原厂 stock-base.dtb 里的这两条属性」：

| | 我们的产物 | 原厂 stock-base | 能启动的 DTB |
|---|---|---|---|
| `qcom,board-id` | `<0x08 0x00>` | `<0x08 0x00>` | `<0x00 0x00>` |
| `qcom,msm-id` | 8 条（`0x294`/`0x295` 各种组合） | 同左 | `<0x100027f 0x20000>` |

抄原厂 → ABL 判定不命中 → **DTBO 被跳过** → `memory@a0000000` 保持
`reg = <0x00 0xa0000000 0x00 0x00>`（大小为 0）→ 内核拿到 0 字节内存，秒崩，
连一行日志都留不下。

## 证据（决定性）

把 CI 产物和参考项目发布包里能启动的 DTB 逐行比：

```
$ diff ref.dts ci.dts | wc -l
13
```

13 行差异里只有 **两条** 真属性：

```
- qcom,board-id = <0x00 0x00>;
- qcom,msm-id = <0x100027f 0x20000>;
+ qcom,board-id = <0x08 0x00>;
+ qcom,msm-id = <0x295 0x20000 0x294 0x10000 ... >;
```

节点数完全相同（1392），其它属性、层级、`memory` 节点结构完全一致。
把那两条改回去再 dump，`diff` = **0 行**。

## 修复

`tools/prepare-boot-dtb.py` 不再从 `stock-base.dtb` 拷这两条，而是显式写入：

```python
mainline.setprop(0, 'qcom,board-id', struct.pack('>II', 0x00, 0x00))
mainline.setprop(0, 'qcom,msm-id',   struct.pack('>II', 0x100027F, 0x20000))
```

并在写出后立刻断言，防止以后有人「顺手改回跟随原厂」：

```python
got = written.getprop(0, name).as_uint32_list()
if got != want:
    raise RuntimeError(f'{name} = {got}, expected {want}: ABL would skip the stock DTBO')
```

## 现在的状态（别高估）

| 环节 | 状态 |
|---|---|
| 板级 ID → ABL 叠 DTBO → 内核进用户态 | ✅ 真机验证（A/B 两槽都进过 KDE） |
| 带隔离 overlay 的完整 DTB（`piano-boot.dtb`） | ⚠️ 只在离线模拟里过（`stock-overlay-simulated.dtb`），**运行时叠 overlay 没在真机上验过** |
| 最近两次内核构建（v4l2loopback） | ❌ 从未在设备上启动过，设备跑的还是 11-18 23:20 那次（`/lib/modules/7.4.0-rc3-piano8+`，没有 v4l2loopback） |
| 显示/触摸/Wi-Fi/蓝牙/音频/充电/休眠 | 在「ID 修好 + 参考 DTB」那次启动里验过；`piano-boot.dtb` 这条路仍未验 |

换 DTB、换内核之后，这套验证要重做一遍，不要拿「镜像能编出来」当「能启动」。
