# panel-xiaomi-p81 — 面板数据（P3a 第一步）

这里**只有数据**，驱动代码还没写。数据全部从原厂 DTB 直接读出
（`piano-real.dtb`，`fdtget` 逐属性取值），不是任何第三方内核的源码。

## 有什么

| 文件 | 内容 |
|---|---|
| `p81-35-02-0b.json` | 原始提取结果：面板节点属性 + 每个 `timing@NNN` 节点的命令负载 |
| `p81-35-02-0b.h` | 同一份数据的 C 数组，供驱动 `#include` |

面板节点：`/soc/qcom,mdss_mdp@ae00000/qcom,mdss_dsi_p81_35_02_0b_dualdsi_dsc_vid`

三套时序（每套都有**自己独立的初始化序列**，不是共用一份）：

| 模式 | 几何 | `on-command` | `off-command` | `timing-switch-video` | 厂商命令 |
|---|---|---|---|---|---|
| 90 Hz | 1600×2136 | 894 B | 16 B | 36 B | CABC ×4 / dimming / ESD / 插黑 ×2 / 笔 |
| 120 Hz | 1600×2136 | 894 B | 16 B | 36 B | 同上 |
| 144 Hz | 1600×2136 | 894 B | 16 B | 36 B | 同上 |

`off-command`（三种模式相同，16 字节）：`05 00 00 00 14 00 01 28 | 05 00 00 00 64 00 01 10`
—— 即 `wait 0x14 → 0x28(display off)`，`wait 0x64 → 0x10(sleep in)`。

## 怎么再生成

```bash
python3 scripts/extract-panel-seq.py \
    /path/to/piano-real.dtb mdss_dsi_p81_35_02_0b \
    --out kernel/drivers/gpu/drm/panel/panel-xiaomi-p81 --c-header
```

脚本用 `fdtget` 读 dtb：厂商 DTS 里命令既有 `[..]` 字节数组也有 `<0x..>` 32 位单元两种写法，
文本解析会错位，直接读二进制才是设备真正启动时用的那份。

## 驱动还缺什么（P3a 剩下的事）

1. **命令编码**：Qualcomm 的 DSI 命令是 4 字节头 `dtype / last / vc / ack` + `wait` + `len` + payload
   （`39 00 00 40 00 00 02 ff 27` 即 DCS long write、wait 0x40、len 2）。驱动里要有个小解析器把这
   894 字节切成一条条 DSI 消息。
2. **双 DSI**：两块 1600 宽的半边，`qcom,dual-dsi-mode` + master/slave；两条链路跑同一份命令。
3. **DSC**：PPS 参数在 `on-command` 里的 `0x91` 那条（`13 91 89 28 00 28 c2 ...`），要拆出来交给
   `drm_dsc` 配置，不能只当普通命令发。
4. **背光**：`bl_ctrl_external`，走两颗 `ktz8866`，0–0xfff；面板本身没有亮度命令。
5. **ESD**：`mi,esd-err-irq-gpio` = tlmm 0x58（第二块 0x57），flag 0x2004；恢复序列用
   `mi,mdss-dsi-esd-on-command`（18 B）。
6. **面板识别**：`mi,panel-id = <0x503831 0x5035020b>`，读命令 `mi,mdss-dsi-panel-build-id-read-command`；
   备选面板 `p81_42_02_0a` 用同样的表也提取一份，驱动按 id 选。
7. 未定：TE / 帧同步用哪种模式（video mode 下按 vfp 调 fps）、DSC slice 高度、双链路是否要 skew。

## 与上游的关系

驱动骨架用上游 `drivers/gpu/drm/panel/panel-*.c` 的 `drm_panel` + `mipi_dsi_dcs_*` 接口，
`struct mipi_dsi_device` 从 `mdss_dsi0_out` 的 endpoint 拿；binding 自己写
`Documentation/devicetree/bindings/display/panel/xiaomi,p81.yaml`。