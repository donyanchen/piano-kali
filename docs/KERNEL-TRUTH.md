---

## 3. 硬件清单（全部来自 board overlay 的真值）

### 3.1 显示

| 项 | 值 |
|---|---|
| 控制器 | `/soc/qcom,mdss_mdp@ae00000`（DPU），`qcom,dsi-ctrl-hw-v2.9` ×2（`ae94000` / `ae96000`） |
| PHY | `qcom,dsi-phy-v7.2` ×2（`ae95500` / `ae97500`） |
| 面板（选中） | `qcom,mdss_dsi_p81_35_02_0b_dualdsi_dsc_vid`，`"xiaomi p81 35 02 0b vid mode dualdsi dsc panel"` |
| 面板（备选） | `qcom,mdss_dsi_p81_42_02_0a_dualdsi_dsc_vid` |
| 分辨率 | `panel-width 0x640 = 1600` × `panel-height 0x858 = 2136`，**双 DSI → 3200×2136** |
| 刷新率 | 三套 timing：`timing@120` / `timing@144` / `timing@90`，`qcom,dsi-supported-dfps-list = <120 144 90 60 50 48 30>` |
| 时钟 | `panel-clockrate 0x47606660`（≈1.196 GHz），phy-timings `[00 27 0a 0a 1b 19 0a 0b 0a 02 04 00 20 0f]` |
| 144 Hz 时序 | hfp 0x15 / hbp 0x10 / hpw 0x10 / vbp 0x68 / vfp 0x44 / vpw 0x02 |
| 120 Hz 时序 | hfp 0x75（其余同 144） |
| 90 Hz 时序 | hfp 0x135（其余同 144） |
| 特性 | DSC、video mode、`non_burst_sync_event`、HDR、动态 FPS（`dfps_immediate_porch_mode_vfp`）、10bit（bpp 0x1e=30） |
| 背光 | `bl_ctrl_external`，`mdss-brightness-max-level 0xfff`，init 0x133，min 0x04 |
| 背光 IC | `ktz,ktz8866` @ i2c `0x11` **两颗**：`i2c@880000` 上 `id=0` + `hwen-gpio`，`i2c@98c000` 上 `id=1` |
| panel 供电 | `oledb` / `ab` / `ibb`（`qcom,panel-supply-entries`） |
| reset GPIO | `<&tlmm 0x62 0>` |
| ESD | `mi,esd-err-irq-gpio` gpio 0x58 / 0x57，flag 0x2004 |
| DP | `mdss_dp0`（`qcom,sm8650-dp`）也在 DT 里 → Type-C 外接显示可用 |

### 3.2 触摸 / 键盘 / 按键

| 设备 | 总线 | 地址 | compatible | 备注 |
|---|---|---|---|---|
| 触屏 | `spi@a88000`（QUPv3_1） | CS0 | `novatek,NVT-ts-spi` | `novatek,irq-gpio = <&tlmm 0xa2 0x2001>`；实测需 `invert_y` |
| 磁吸键盘 | `i2c@a98000` | `0x4c` | `nanosic,803` | 纯 HID，无认证 |
| 音量键 | GPIO | tlmm 0x06 | `gpio-keys` → `vol_up` (KEY_VOLUMEUP 0x73) | 只有 vol_up 一个键节点 |
| 电源键 | PMIC | — | `qcom,pmk8350-pwrkey`（pmk8550 内） | 另有 `pwrkey-bark` |

### 3.3 音频

| 项 | 值 |
|---|---|
| 声卡 | `/soc/spf_core_platform/sound`，`qcom,sun-asoc-snd`，`qcom,model = "sun-mtp-snd-card"` |
| **功放** | `foursemi,fs16xx` ×4 @ i2c `0x34 / 0x35 / 0x36 / 0x37`（`i2c@980000`） |
| TDM | `qcom,tdm-max-slots = <4>`、`qcom,tdm-clk-attribute = <4 …>`、`qcom,mi2s-tdm-is-hw-vote-needed` |
| WSA 路径 | **关闭**：`qcom,wsa-max-devs = <0x00>`；DT 里那 4 个 `qcom,wsa884x` 是模板残留 |
| codec 列表 | `asoc-codec-names = "msm-stub-codec.1", "lpass-cdc", "wcd939x_codec", "swr-haptics"` |
| 耳机 codec | `qcom,wcd939x-i2c` @ i2c `0x0e`（`i2c@a8c000`）+ SWR slave |
| Type-C 模拟开关 | `qcom,fsa4480-i2c` @ `0x42`（同总线） |
| 宏 | `lpass-wsa-macro`（6B00000）、`wsa2-macro`（6AA0000）、`rx-macro`（6AC0000）、`va-macro`（7660000）、`tx-macro` |
| 触觉 | `qcom,pmih010x-swr-haptics` @ wsa2 SWR |
| 实测 slot 映射 | ch0=摄像头侧左，ch1=触点侧左，ch2=摄像头侧右，ch3=触点侧右 |

> **两套描述并存的解释**：官方 DT 同时挂了 WSA884x（SoundWire）和 FS16xx（I2C+TDM），但声卡节点里 `wsa-max-devs = 0` 且 `wcd-disabled = 1`，实际只走 TDM → 4 个 FS19xx。这与逐声道实测完全一致。

### 3.4 充电 / USB / Type-C

| 项 | 值 |
|---|---|
| 角色/PD | `qcom,pmic_glink` (`PMIC_RTR_ADSP_APPS`) → `qcom,ucsi-glink` |
| 主充电 IC | `ti,bq27z561_master` @ `0x55`（`i2c@a94000`）、`ti,bq27z561_slave` @ `0x55`（`i2c@88c000`） |
| 电荷泵 | `sc8541_master` @ `0x6a`（`i2c@a94000`） |
| 副充电 | `qcom,i2c-pmic` → `qcom,smb1501@68` / `@69`（pmic_glink_debug 的 `i2c@106` 虚拟总线） |
| 无线充 | `idt9418@3b`（虚拟 i2c，固件 `idt9418.bin`）、`sc,sc96231-wireless-charger` @ `0x38`（`i2c@894000`） |
| USB | `ssusb@a600000` + `dwc3@a600000`（`snps,dwc3`）+ `qcom,sm8750-qmp-usb3-dp-phy` |
| 厂商框架 | `mca_*`（38 个模块，见 §4） |

### 3.5 存储 / 总线 / 其他

| 项 | 值 |
|---|---|
| UFS | `ufshc@1d84000`，`qcom,ufshc`，reg-names `ufs_mem / ice / mcq_sqd / mcq_vs`；IRQ 0x109；`ufsphy_mem@1d80000` = `qcom,ufs-phy-qmp-v4-sun` |
| PCIe | `pcie@1c00000`（`qcom,pci-msm`）→ `cnss_pci0`（WLAN）；perst gpio 0x66、wake 0x68；`qcom,drv-name = "cesta"` |
| WLAN | `qcom,cnss-peach@b0000000` → **WCN7850 "peach"**；保留内存 `cnss_wlan_region` |
| NFC | `fm,fm19511` @ i2c `0x57`（`i2c@888000`） |
| 红外 | `ir-spi@0`（`spi@89c000`） |
| PMIC | `pm8550@1`、`pm8550ve@3/5/6/8`、`pm8550vs@2/3/4/5/6/9`、`pm8010@c/d`、`pmd802x@4`、`pmih010x@7`、`pmk8550@0`、`pmr735d@a` |
| thermal | 4 组 `qcom,sm8750-tsens`（v2）+ `thermal-zones`（每 CPU 核 2 条、`gpuss0-2`、`aoss0/1`、`cpuss-*` 等） |
| 内存 | `ddr_size = 0x0c`（12 GiB），memory 节点为多段拼接 |
| 显示写保护 | `msm_drm.oled_wp=7f7d5f`、`panel_build_id=Pff`（每台机不同） |
| 指纹 | **AP 侧 DT 里没有节点**（跑在高通 TEE），与本项目无关 |

---

## 4. 官方驱动清单（vendor_boot ramdisk 里的 449 个 .ko）

按功能抽样（原始清单 `$WORK/vendor_boot/vendor_ramdisk00` → `kos.txt`）：

| 类别 | 模块 |
|---|---|
| 显示 | `msm_drm`、`msm-mmrm`、`msm_ext_display`、`dispcc-sun`、`drm_display_helper`、`mca_qcom_panel`、`panel_event_notifier` |
| 存储 | `ufshcd-core` 系列 + `phy-qcom-ufs-qrbtc-sdm845`、`ufs_qcom` |
| USB | `dwc3-msm`、`wcd_usbss_i2c`、`phy-qcom-qmp-*` |
| 高速总线 | `i2c-msm-geni`、`i3c-master-msm-geni`、`msm_geni_serial`、`msm_gpi`、`slimbus`、`slim-qcom-ngd-ctrl` |
| 充电（mca） | `mca_business_charger_comp`、`mca_charge_interface`、`mca_strategy_buckchg`、`mca_strategy_fg_comp`、`mca_buckchg_jeita`、`mca_pd_auth`、`mca_protocol_pd_class`、`mca_qcom_panel`… 共 38 个 |
| 时钟/GDSC | `clk-qcom`、`clk-rpmh`、`clk-scmi`、`gpucc-sun`、`dispcc-sun`、`cambistmclkcc-sun` |
| 其他 | `msm_hw_fence`、`msm_performance`、`governor_msm_adreno_tz`、`mi_ubt` |

**音频 codec / machine driver 不在这个 ramdisk 里**（在 vendor_dlkm，未 dump）——这是当前证据链唯一的空白点，但它不影响结论：声卡走 TDM 已由 DT 明确写死。

---

## 5. 与"现在跑着的系统"的对照

| 项 | 官方（本文档） | 平板当前（第三方 7.4.0-rc2-piano88） |
|---|---|---|
| 设备树 | base0 + piano overlay（官方） | 同一份 DTB 被沿用（`piano-real.dtb` 与官方合并结果一致，仅一处 GUID 差异） |
| 内核 | GKI 6.6.118 + vendor .ko | 单体 7.4.0-rc2，全部驱动内置 |
| UFS | MCQ（reg 有 mcq_sqd/mcq_vs） | **未启用 MCQ → 卡死**（已知坑 #1） |
| 音频 | TDM 4 slot + 4×FS19xx | 只填 2 slot → 下排两喇叭不响 |
| 屏 | 双 DSI + DSC 144 Hz | 可用 |

> 本文没有在平板现网重新采 `/proc/config.gz` 与 `dmesg`（会话内没有到平板的网络通道）。要补这一项：SSH 上去跑
> `zcat /proc/config.gz > /tmp/config.gz; dmesg > /tmp/dmesg.txt; cp /sys/firmware/fdt /tmp/live.dtb`，再回传。

---

## 6. 复现

```bash
# 备份目录里应有 boot_b.img / init_boot_b.img / vendor_boot_b.img / dtbo_b.img / vbmeta_b.img
./scripts/p0-unpack.sh /path/to/pad8pro /tmp/p0

# 硬件清单
python3 scripts/dt-inventory.py /tmp/p0/real.dts --stats
python3 scripts/dt-inventory.py /tmp/p0/real.dts --buses
python3 scripts/dt-inventory.py /tmp/p0/real.dts --compat 'ufshc|mdss'

# 判定 base 变体（节点级匹配率）
#   见 §1.7 的脚本，输出 dtb0 95.3% 最高
```

产物：`$WORK/{boot,init_boot,vendor_boot}/`、`stock-config.txt`、`vb-dtbs/dtb0..7.dtb`、`dtbo/piano_entry.dtb`、`live.dts`、`real.dts`。

## 真值来源优先级（硬规矩）

写驱动/DTS 缺参数时，按这个顺序取，**不允许猜**：

| 优先级 | 来源 | 例子 |
|---|---|---|
| 1 | **跑着的 Android**（sysfs / debugfs / dmesg） | GPU 频率表 `/sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies`；SMMU stream id `/sys/kernel/debug/kgsl/`；触摸模式 `[NVT-ts] nvt_set_cur_value` |
| 2 | **原厂分区镜像**（boot/vendor_boot/dtbo/firmware） | 面板初始化序列、触摸固件、regulator 配置 |
| 3 | upstream mainline / linux-stable | 驱动框架、binding 结构、SoC dtsi |
| — | 第三方内核（yzddmr6 等） | **只能对照，不能抄** |

理由：Android 那套固件是这台机器**唯一跑通过的实现**，它暴露的运行时参数就是硬件真值；
原厂 DTB 缺的字段（GPU 的 iommus/power-domains/opp），Android 的 sysfs 全都有。

### 跨版本取值的边界

Android 跑的是 **6.6.118-android15**（厂商重度改造），我们的基线是 **linux-stable 7.3.4**。因此：

- **可以取**：硬件常量（DSI `clk_rate`、分辨率、regulator 电压、GPIO 编号、频率表）
- **不可照搬**：驱动行为、探测顺序、错误语义、日志格式 —— 版本和树都不一样

一句话：**抄常量，不抄行为。**

### p81 35-02-0b 的 DSC / 拓扑真值（原厂 timing@144）

| 属性 | 值 | 含义 |
|---|---|---|
| `qcom,mdss-dsc-version` | 17 (0x11) | DSC 1.1 |
| `qcom,mdss-dsc-slice-width` | 800 | 每链路 1600 宽 → 2 slice |
| `qcom,mdss-dsc-slice-height` | 24 | 2136/24 = 89 行整 |
| `qcom,mdss-dsc-bit-per-component` | 10 | 10bpc 源 |
| `qcom,mdss-dsc-bit-per-pixel` | 8 | 压缩到 8bpp |
| `qcom,mdss-dsc-block-prediction-enable` | 1 | BP 开 |
| `qcom,compression-mode` | dsc | — |
| `qcom,display-topology` | `<2 2 2>` | 2 mixer / 2 DSC 编码器 / 2 接口 = **bonded 双 DSI** |
| `qcom,dsi-ctrl-num` | `<0 1>` | 两个 DSI 控制器 |
| `qcom,mdss-dsi-panel-clockrate` | 1197500000 | 与 Android 实测一致 |
| `qcom,mdss-dsi-panel-phy-timings` | `[00 39 10 10 27 25 10 11 10 02 04 00 32 15]` | PHY 时序表 |

**结论**：这块屏必须同时满足两件事才能出图 —— ①双 DSI bonded（两条链路各 1600 宽）②host 侧 DSC（800x24 slice, 8bpp, 10bpc, BP 开）。
只开一条链路、或不开 DSC，都不会有正常画面。
