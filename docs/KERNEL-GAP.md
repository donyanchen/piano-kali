# KERNEL-GAP — SM8750/piano 在 mainline 上的支持度与自建边界

> 基线候选：**linux-stable v7.3.4**（备选 v7.4-rc3 / v7.3.x 后续）。
> 事实来源：GitHub 上 `torvalds/linux` 的 v7.3 树（按需读单文件，不在本地保存整棵树）。
> 判定口径：**只看上游有没有「驱动 + DT 节点 + binding」三件套**，缺一件就算「部分」。

## 1. 基线选择：v7.3.4

| 候选 | 结论 | 理由 |
|---|---|---|
| **v7.3.4（stable）** | ✅ **选它** | SM8750 全套已在 7.3：`sm8750.dtsi`(163 KB)、`dpu_12_0_sm8750.h`、`sm8750` 各 clock/icc/pinctrl/tsens 驱动、UFS/PCIe/USB/DSI 节点齐全；stable 带半年 bugfix |
| v7.4-rc3 | 备选 | 与 Kali 现役 7.4.0-rc2 同代，若 DSI/DPU 在 7.4 有修复可随时切；rc 不适合长期跑 |
| 6.12 LTS | ❌ | **没有 sm8750 支持**（sm8750 是 7.x 才进主线的），等于从头写 SoC 层 |
| Debian/Kali 7.2.15 | 可用但无优势 | 与 7.3 差别不大，且 Kali 源里就是它；我们要自己的 config/binding，直接用 stable 更干净 |

选择直接影响：**SoC 基础层（时钟、互连、pinctrl、tsens、rpmh、SMMU、remoteproc、PCIe、UFS、USB、显示控制器）全部可复用上游**，自写的只剩「板级 + 面板 + 功放 + 触摸 + 充电策略 + GPU 节点」。

## 2. mainline v7.3 已有的 SM8750 事实

| 能力 | 上游证据 |
|---|---|
| SoC dtsi | `arch/arm64/boot/dts/qcom/sm8750.dtsi`（+ `sm8750-mtp.dts` / `sm8750-qrd.dts` 参考板） |
| 时钟 | `gcc/dispcc/gpucc/camcc/videocc/tcsrcc/cambistmclkcc-sm8750.c` |
| 互连 | `drivers/interconnect/qcom/sm8750.c` |
| pinctrl | `drivers/pinctrl/qcom/pinctrl-sm8750.c` |
| thermal | `qcom,sm8750-tsens` ×4 + `thermal-zones`（每核 2 条 trip） |
| 显示 | `qcom,sm8750-mdss`、`qcom,sm8750-dpu`、`qcom,sm8750-dsi-ctrl`、`qcom,sm8750-dsi-phy-3nm`、DPU catalog `dpu_12_0_sm8750.h`（8 LM / 6 CTL / 4 VIG / 6 DMA / DSC） |
| 双 DSI | `dsi_manager.c` 支持 `qcom,dual-dsi-mode`（bonded DSI，master/slave） |
| UFS | `qcom,sm8750-ufshc` 节点 + `ufs-qcom.c` 的 `.mcq_config_resource / .config_esi / .get_outstanding_cqs`（MCQ 全链路） |
| PCIe | `qcom,pcie-sm8750` ← `qcom,pcie-sm8550`，`pcie-qcom` 驱动 |
| USB | `qcom,sm8750-dwc3` + `qcom,sm8750-qmp-usb3-dp-phy` + `m31-eusb2-phy` |
| PMIC | `pm8550.dtsi` / `pm8550ve` / `pm8550vs` / `pm8010.dtsi` 已有；`qcom,pmk8350-pwrkey` 有驱动 |
| 音频底座 | `lpass-wsa/rx/tx/va-macro`、`wcd939x`（+sdw）、`wsa884x`、`sound/soc/qcom/common.c` 的 **TDM slot 解析** |
| 背光 | `drivers/video/backlight/ktz8866.c`（`kinetic,ktz8866`） |
| Wi-Fi | `ath12k/wifi7/hal_wcn7850.*`（WCN7850 支持） |
| 触摸 | 只有 I2C 版 `novatek-nvt-ts.c`（`novatek,nt11205-ts` / `nt36672a-ts`） |
| 充电 | `ucsi_glink.c`（`qcom,*-pmic-glink`）+ `pmic_glink_altmode` |

## 3. Gap 矩阵

判定：✅ 直接用 / ⚠️ 部分（要补 DT 或小改驱动）/ ❌ 缺（要自己写）。

| # | 子系统 | piano 需要 | mainline v7.3 | 判定 | 自建内容 | 估工 | v1 |
|---|---|---|---|---|---|---|---|
| 1 | SoC 基础 | clk/icc/pinctrl/tsens/rpmh/SMMU/remoteproc | 全套 | ✅ | 只写板级引用 | 0.5d | 必做 |
| 2 | UFS | UFSHCI 4.0 + **MCQ** + Gear5×2 | `qcom,sm8750-ufshc` + ufs-qcom MCQ ops | ✅ | DT 带 `mcq_sqd/mcq_vs` reg；验证 ESI/MCQ 真开 | 1d | 必做 |
| 3 | DPU + 双 DSI + DSC | 3200×2136@144 双链路、DSC、亮度 | DPU catalog + dsi-ctrl/phy + bonded DSI | ⚠️ | **面板驱动**（p81_35_02_0b 初始化序列/DSC/亮度） | 3–5d | 必做 |
| 4 | 背光 | 两颗 ktz8866，0–0xfff | `ktz8866.c` | ✅ | DT 两个实例 + 亮度映射 | 0.5d | 必做 |
| 5 | 触摸 | Novatek **SPI**（NVT-ts-spi） | 仅 I2C 版 | ❌ | 写 SPI 驱动（或扩 nvt-ts 支持 SPI）；`invert_y` | 1–2d | 必做 |
| 6 | USB/Type-C | dwc3 + QMP + UCSI/PD 角色 | dwc3/pcie-qcom/ucsi_glink 全有 | ⚠️ | DT 用上游 compatible（`qcom,sm8550-pmic-glink`）+ 验证 ADSP 通道 | 1d | 必做 |
| 7 | 音频 machine | `sun-asoc-snd`，**TDM 4 slot**，4 功放 | `sc8280xp.c` 里有 `sm8750_priv_data`（`qcom,sm8750-sndcard`）+ `sc8280xp_tdm_hw_params`（`qcom_snd_apply_dai_tdm_slots_cfg`） | ⚠️ | 只写板级 DAI link / DAPM 路由（TDM RX0 → 4 功放），不改驱动 | 1–2d | 必做 |
| 8 | 功放驱动 | 4× `foursemi,fs16xx` @0x34–37 | 只有 `fs210x`（同厂不同型） | ❌ | 写/扩 FS19xx 驱动（I2C 控制 + TDM 播放） | 2–3d | 必做 |
| 9 | Wi-Fi | WCN7850 "peach" | ath12k 支持 WCN7850 | ⚠️ | 换 **linux-firmware 的 ath12k 固件**（厂商固件是 qca_cld 格式）；DT 写 PCIe+WLAN 节点 | 1–2d | 必做 |
| 10 | 蓝牙 | 板载 BT（WCN7850 侧） | `hci_qca`（串口） | ⚠️ | 需要先定位 BT 的 UART/流控引脚（官方 DT 里没直接找到 bt 节点，**待补证**） | 1–2d | 必做 |
| 11 | GPU | Adreno 830 (`0x44070001`, 8xx Gen2) | `a8xx_gpu.c` + `a6xx_catalog.c` 有该 chip id，**但 sm8750.dtsi 没有 gpu/gpucc 节点** | ⚠️ | 写 GPU 节点：gpucc、gpu、gmu、iommu、zap shader、opp table | 2–3d | 必做 |
| 12 | 充电 | UCSI + `mca_*`（PPS 42–50 W） | UCSI ✅；**mca 完全不在上游** | ❌ | v1：UCSI 取 PD/电压电流 + 基础充电；PPS 策略后置 | 2d / 深 | 部分 |
| 13 | 电量计 | `bq27z561` master/slave | `bq27xxx` 有 bq27z561？需核 | ⚠️ | DT + 可能在 `power_supply` 侧补 compatible | 1d | 必做 |
| 14 | 按键/电源键 | vol_up + pmk8350 pwrkey | gpio-keys + pwrkey 驱动 | ✅ | DT | 0.5d | 必做 |
| 15 | 磁吸键盘 | `nanosic,803` | `i2c-hid` 通用 | ⚠️ | 用 `hid-over-i2c` 兼容串 + 描述符/adb 验证 | 1d | 必做 |
| 16 | 挂起/唤醒 | s2idle / 深睡 | 通用 | ⚠️ | 各驱动 `.suspend` + wakeup 源 | 2d | 必做 |
| 17 | 相机 | iris (SM8750) | `iris_platform_sm8750.h` | ⚠️ | 驱动在，但 sensor/CSI 板级描述量大 | — | 不做 |
| 18 | 指纹 | TEE（AP 无节点） | — | — | 不做 | — | 不做 |
| 19 | NFC / 红外 / 无线充 / 触觉 | fm19511 / ir-spi / sc96231 / pmih010x-haptics | 无（pmih010x 0 命中） | ❌ | 不做 | — | 不做 |

## 4. 第一版「最小可用」边界

**v1 必须做到（缺一不可开机可用）**
1. 屏亮 + 3200×2136@144 + 亮度（DPU/双 DSI/DSC/ktz8866×2）
2. 触摸（含 `invert_y`）、磁吸键盘、音量键/电源键、合盖唤醒
3. UFS 正常（MCQ 必须真开，否则复现当前的「写成功但不取描述符」）
4. USB（充电 + adb/ssh 通道）、Wi-Fi、蓝牙
5. **四个喇叭全响**（machine driver 把 L/R 复制到 4 个 TDM slot）
6. GPU 加速（`eglinfo` 认 Adreno 830）
7. 用户态零改动：Kali rootfs 不重装、KDE 配置不动

**v1 可以延后**
- 充电功率上限/PPS 曲线（先保证「能充、能显示电压电流」）
- 相机、NFC、无线充、触觉、触控笔
- 外接显示（DP altmode）

**明确不做**：指纹（TEE 侧）、`mca` 全套厂商框架移植。

## 5. 风险与未知（需要真机才能定）

| 风险 | 说明 | 缓解 |
|---|---|---|
| MCQ 默认开启条件 | `ufshcd` 需要 `mcq_sup` + ESI + `mcq_base`；上游逻辑与厂商可能不同 | v1 第一件事就是打 `show_hba` + `hba->mcq_enabled` 打印验证 |
| ADSP 固件加载 | 音频要 ADSP（`adsp.mbn` / `adsp_dtb`），piano 的固件在 `/vendor/firmware` | 固件是「设备真值」，可直接用；路径走 `firmware_class.path` |
| PMIC glink 通道名 | 厂商 `qcom,qti-pmic-glink` vs 上游 `qcom,sm8550-pmic-glink` | DT 里先用上游串，失败再比对 ADSP 侧 |
| 面板初始化序列 | DSC 参数、per-frame 命令都在官方 DT 的 `qcom,mdss-dsi-*` 属性里（**数据，不是代码**） | P2 直接从 `real.dts` 抄数值，binding 用上游 `panel-dsi` 规范重写 |
| 双 DSI 144 Hz | 上游 bonded DSI 主要用于平板，144 Hz 视频模式没验证过 | 先 60 Hz 出图，再上 120/144 |
| 蓝牙节点 | 官方 DT 没直接给出 BT 的 UART 节点（在 ADSP/`btfm` 侧） | P2 需要从 firmware/`bluetooth` 分区或 dmesg 补证 |
| GPU 节点 | 上游 dtsi 没有 gpu，需要自己拼 gpucc/gmu/zap/iommu | 参考 `sm8650.dtsi` 的 GPU 节点结构（上游代码） |

## 6. 下一步（等你拍板后进 P2）

1. 以 `sm8750.dtsi` 为 SoC 层，新建 `sm8750-piano.dts`：只写板级（i2c/spi 设备、panel、amp、keys、regulators、reserved-memory）。
2. 面板驱动 `panel-xiaomi-p81.c`：初始化序列/DSC/亮度全部取自 `real.dts` 的数值。
3. 音频：板级 DAI link（`qcom,sm8750-sndcard` 已由 `sc8280xp.c` 支持，TDM 走 `PRIMARY_TDM_RX_0`）+ 自写 `fs19xx.c` 功放。
4. UFS 先跑上游原样，用 `show_hba` 验证 MCQ，再决定要不要补 quirk。
5. 打包：`ubuntu-24.04-arm` + LLVM=1，产出 `Image`/`modules`/`dtbs`，deb 名 `linux-image-7.3.4-piano`。

**基线已定 v7.3.4**，P2 见 §7 的决策与实施顺序。
---

## 7. 决策记录（P0 × P1 合成的最终方案）

### 7.1 锁定的选择

| 决策 | 结论 | 依据 |
|---|---|---|
| 基线 | **linux-stable v7.3.4**，LLVM=1，4K 页 | SM8750 全套在 7.3；stable 有 bugfix；与 Kali 现役 7.4-rc2 相邻 |
| 代码来源 | 只允许 upstream + 我们自写；`xiaomipad-8pro-mainline` 仅作对照 | 用户硬性约束 |
| DT 策略 | 以 `sm8750.dtsi` 为 SoC 层，`sm8750-piano.dts` 只写板级；**数值**（面板时序/DSC/GPIO）取自 `piano-real.dts`，**结构/binding** 全部按上游重写 | P0 §1.6–§3 |
| 显示 | DPU + 双 DSI + DSC，bonded DSI（`qcom,dual-dsi-mode`）；面板驱动自写 | upstream `dsi_manager.c` 支持 bonded |
| 音频 | 用上游 `qcom,sm8750-sndcard`（`sc8280xp.c`）+ 板级 TDM DAI link；功放自写 | 已核实 `sm8750_priv_data` 与 TDM hw_params 在 v7.3 |
| UFS | 用上游 `ufs-qcom` 的 MCQ 路径，不自己写控制器代码；先验证 `hba->mcq_enabled` | P0 reg 有 `mcq_sqd/mcq_vs`；P1 有 `mcq_config_resource` |
| GPU | 驱动用上游 a8xx（chip id `0x44070001`），**DT 节点自写**（gpu/gpucc/gmu/iommu/zap） | `sm8750.dtsi` 无 gpu 节点 |
| 充电 | v1 = UCSI（上游 `ucsi_glink`）+ 电量计；**不移植 mca** | mca 38 个厂商模块，无上游对应 |
| 构建 | GitHub Actions `ubuntu-24.04-arm`，产物 `Image`/`modules`/`dtbs` → deb | 用户要求；本地不下载内核树 |

### 7.2 实施顺序（每步都有验收门）

| 阶段 | 交付 | 验收门（不过就回退） |
|---|---|---|
| P2a | `kernel/dts/sm8750-piano.dts` v0（SoC+PMIC+显示+触摸+键盘+键+功放+UFS+USB+PCIe） | CI 编译过 DTB |
| P2b | 面板驱动 `panel-xiaomi-p81.c`（时序/DSC 数值来自 real.dts） | 60 Hz 出图 → 120/144 Hz |
| P3a | `fs19xx.c` 功放 + TDM DAI link | 4 个喇叭逐个响（`speaker-test -c4`） |
| P3b | Novatek SPI 触摸 | 触摸坐标正确（含 invert_y） |
| P3c | GPU DT 节点 + zap/gmu 固件 | `eglinfo` 认 Adreno 830 |
| P3d | PCIe0 + ath12k + linux-firmware 固件 | 扫描到 AP；热点可开 |
| P4 | deb + boot/vendor_boot 打包 + `build-kali.sh` 消费自有 deb | 刷机后用户态零改动可用 |

### 7.3 反直觉但重要的两条

1. **官方 DTB 里的 `qcom,wsa884x` 是死代码**：`wsa-max-devs = 0`。任何照着 WSA SoundWire 去调音频的路线都会走死；必须走 TDM。
2. **官方内核是 GKI + 449 个厂商模块**，所以「config 里没开 UFS/DRM/音频」是假象；判断官方用什么驱动只能看 vendor 模块清单（`KERNEL-TRUTH.md` §4）。