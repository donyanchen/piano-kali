# AI 开发与部署约定

本仓库针对 Xiaomi Pad 6S Pro 12.4 (`sheng` / `24018RPACC`) 的原生 Kali ARM64。先读 `README.md`、`docs/AI_DEPLOY.md`、`docs/DEPLOYMENT.md`、`docs/VALIDATION.md`，再操作设备。

## 工作方式

- 先识别主机、目标设备、架构、内核 ABI、Plasma/Qt 版本和现有数据。Windows PowerShell 只负责主机侧准备/刷写；Linux 镜像构建及 ELF 编译使用 Linux。
- 已授权的只读检查、构建、配置备份和可回退修复继续完成。擦除 userdata、分区调整、重新刷写前，必须已有对具体影响的明确授权；普通“部署 Linux”不能替代清数据授权。获得授权后不要反复询问相同事项。
- `.work/` 是本机私有缓存，`out/` 是本机构建产物，不能作为外部开发者必备输入。公开命令必须引用仓库源码、固定上游或明确要求开发者自行构建的产物。
- 不把密码、SSH 私钥/主机密钥、硬件认证 token、MSIME 账户/学习库、Wi-Fi 配置、Burp 项目/许可证、个人截图或完整用户目录写入提交、日志、镜像。
- 更换内核要重建 PIN 模块；更新 Plasma 要重建对应 C++ applet。不得 force-load 模块、跳过哈希或将不同 ABI 的二进制拼装。
- PIN 故障先保留现场，查看无内容计数和服务状态；不要反复重绑 I²C、TEE/RPMB 或电源管理设备。沿用上游安全存储协议，不记录认证材料。
- 桌面修改先备份；保留用户打开的应用、锁屏状态和会话。不得为了截图或验收绕过锁屏、强制重启 KWin/整个会话。
- 功能测试与用户确认分开记录：服务 active 不能证明声音、触屏输入、热点上网或中文上屏可用。未测项目写“未验证”，不要推断成功。

## 入口与检查

- 基础镜像：`sudo bash scripts/build-kali.sh`；校验：`python3 scripts/validate-images.py out`。
- 控制中心：`python3 scripts/build-control-center.py`；任务效果：`python3 scripts/build-task-cards.py`。
- 源码检查：`python3 scripts/check-project.py`；CI 在 Linux 额外运行 shell 语法及 C/C++ 编译检查。
- 增量安装与依赖：`docs/DEPLOYMENT.md`。部分脚本仅打包已编译产物，不能称为完整编译器。
- GPU 基准会改变临时频率/负载，先读 `device/gpu-bench/README.md`，记录并恢复原状态。不根据单个 FPS 数字宣称更省电。

## 修改后

更新对应组件 README 和公开验证矩阵，记录机型、版本、方法、结果及回退。仅运行与变更相关的检查，不为文档修改刷机或重装系统。推送前检查差异与敏感信息。第三方版权和来源不能删除；新增下载固定提交/哈希，禁止不明一键脚本直接 pipe 到 root shell。
