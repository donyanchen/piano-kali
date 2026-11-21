# 启动 DTB 的板级 ID：到底影响哪条启动路径

## 一句话

`qcom,board-id` / `qcom,msm-id` 只影响 **`fastboot boot` 内存启动**这条路径；
**刷进 vendor_boot 正常启动**时，ABL 会合原厂 DTBO 并自己改写这两条属性，
沿用原厂值就够。所以脚本默认用原厂身份，另给 `--testboot-identity` 给测试镜像用。

## 现象（2026-11-18）

用 `fastboot boot ram-test.img`（header v2，kernel + DTB + ramdisk 全内嵌）测自建内核：

- Mi logo → 直接跳 fastboot
- `boot-log.txt` **从未生成** → 内核连 initramfs 的 `/init` 都没跑到
- A 槽、B 槽各试一次都一样

同一时间，参考项目发布包里的 `refboot/rc/dtb` 塞进同样的 ram-test 镜像就能进 KDE。

## 证据一：两份 DTB 只差两条属性

```
$ diff ref.dts ci.dts | wc -l
13          # 其中只有两条真属性，其余是 diff 的上下文
- qcom,board-id = <0x00 0x00>;
- qcom,msm-id   = <0x100027f 0x20000>;
+ qcom,board-id = <0x08 0x00>;
+ qcom,msm-id   = <0x295 0x20000 0x294 0x10000 0x294 0x20000 0x1000294 ...>;
```

节点数都是 1392，其余全部一致。

## 证据二：设备上跑的就是我们自己的 DTB（所以刷机路径没问题）

从设备的 `boot_b` 直接读回 96 MiB 分区镜像，解 header v4 取内核：

```
boot_b 里的内核 sha256 = 3d32ec46710c8b91473a638fdf9f371594fe8ed6bb1db9143865a07d686528d3
CI run 44318033 的 Image = 3d32ec46…（一致）
CI run 44483481 的 Image = c3ba3fb7…（设备上没有）
```

再从 `/sys/firmware/fdt`（内核实际拿到的 DTB，ABL 合完 DTBO 之后）看：

- 里面出现 **191 次 `piano-stock-overlay`** —— 那是本脚本注入的隔离节点，
  参考项目的 DTB 里是 0 次
- 根上身份属性已被改写为 `<0x40008 0x00>` / 8 条 `0x26a`/`0x27f` 组合

结论：刷机路径下 ABL 确实合了原厂 DTBO，我们这份 DTB 是能启动的。
**`memory@a0000000 { reg = <0 0xa0000000 0 0> }` 大小是 0 也照样启动**
（运行中仍是 0，`MemTotal` 11.4 GB），所以这个节点不是判据，别再拿它当罪证。

## 所以脚本怎么走

```sh
# 默认：身份属性沿用原厂 stock-base.dtb，产出的 DTB 用于 vendor_boot（刷机路径）
prepare-boot-dtb.py --mainline-dtb … --stock-base … --stock-overlay … --ufdt … --output out/

# fastboot boot 测试镜像：加这个开关，身份属性换成参考 DTB 那组
prepare-boot-dtb.py … --testboot-identity
```

两种模式写完后都会断言身份属性符合预期，防止有人只改一半。

## 还没验证的

| 环节 | 状态 |
|---|---|
| vendor_boot 刷机 + 我们的 DTB（原厂身份） | ✅ 真机验证：boot_b 内核 3d32ec46…，运行 DTB 含隔离节点 |
| `--testboot-identity` 的 fastboot 镜像 | ⚠️ 未单独复测（参考 DTB 用同样两条属性进过 KDE） |
| 隔离 overlay 的运行时行为（Gunyah 定时器 fixup） | ⚠️ 只做过离线模拟合并 |
| 最近两次内核构建（`c3ba3fb7…`，含 v4l2loopback 改动） | ❌ 从未上机；模块清单两边都是 1599 个、逐条一致，说明那两次改动的模块根本没进产物，还要查 |
| 显示/触摸/Wi-Fi/蓝牙/音频/充电/休眠 | 在运行中这套（44318033）上验过；换内核要重验 |
