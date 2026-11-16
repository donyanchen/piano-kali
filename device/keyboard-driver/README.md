# sheng PIN 键盘驱动修复

2026-11-14 已在连接的平板安装 `sheng-dock-fix 1.2-2`，模块版本 `1.2-shengfix`。只适用于 `7.3.4-sm8550-00104-g87ac0f2347eb` 内核。当前驱动与上游 `ianchb/sm8550-mainline` 提交 `87ac0f2347eb433933841e6854950dd90e96e6b2` 使用相同配置和 Clang 21.1.8-13 编译；配置重生成的差异仅为未使用的 Rust/pahole 工具能力标志。

[驱动补丁](0001-fix-auth-and-resume.patch) 修改以下路径：

- 认证客户端接入、键盘连接和唤醒时主动安排握手，避免客户端启动较晚时只能等待下一次固件请求。
- 将最多 5 秒的用户态认证等待移出 IRQ 线程；等待期间中断线程继续接收数据。
- 恢复后重新安排原来的 12 秒键盘保活任务；原驱动在挂起时取消它，恢复路径没有重新安排。
- 正确取消新增认证任务，增加只读输入/认证计数，便于诊断，不记录按键内容、触摸坐标或认证材料。

认证还需要配套用户态服务。使用 `ianchb/sheng_devauth` 提交 `bac03b5bcfefa1467ebad490edd910a6cef8a207`，配合 [认证补丁](../keyboard-auth/service-fixes.patch)。当前 Kali 没有公共 qteesupplicant，因此服务自身必须注册上游原版使用的 RPMB 回调；只发送一个非零 token 不能证明键盘接受了认证。服务不记录 UID 或 token。

上游源码包 SHA-256：`bc48c5263c607ddf798cbc21a2aecde8e72bbbab3843aa662e99668d8722bfb4`。该源码包包含 ARM64 静态依赖及许可证，认证程序在平板本地编译，链接 `-lrpmbservice -lminkadaptor -lqcomtee -lqcbor`。

## 验证

用户先后确认了保持原连接时恢复，以及自动休眠唤醒后键盘和触摸板均正常。驱动计数由零恢复增长。系统级挂起约 12.8 秒后自动唤醒，认证服务保持活动，认证计数继续增长，键盘与触摸板的事件节点保持不变；没有通过拔插或重绑定来通过恢复测试。

最终记录合并到本机 `out/keyboard-hotspot-cleanup-verification.json`，包括此前休眠、保活和用户确认结果。安装包为 `out/packages/sheng-dock-fix_1.2-2_arm64.deb`。旧报告、构建日志和测试缓存已清理；此前 83 个运行时导出符号检查通过。这是一轮实机修复验证，不承诺所有键盘固件版本或长期使用场景均已覆盖。

## 安装与回退

在同一内核的 ARM64 平板上安装包后，模块从 `/lib/modules/7.3.4-sm8550-00104-g87ac0f2347eb/kernel/drivers/hid/hid-nanosic-wn8030.ko.zst` 加载，认证服务开机自启。补丁包通过 `Replaces` 接管原文件；旧 `updates/sheng/` 副本已移除。无需重新刷写 boot 或清除用户数据。打包脚本为 [build-dock-fix-package.sh](../../scripts/build-dock-fix-package.sh)。

按用户要求，平板只保留补丁版模块，原版备份和试验认证程序已删除。卸载补丁不会自动恢复原版；如需回退，必须重新安装原内核包。原模块仍有先前的间歇失灵问题。

```sh
sudo apt remove sheng-dock-fix
sudo apt install --reinstall linux-xiaomi-sheng
sudo reboot
```

若需不停机回退，应先停止认证服务，再只卸载 `hid_nanosic_wn8030`，保留 `qcom_battmgr`，重新安装原内核包后加载原模块。不要在认证客户端仍持有字符设备时直接重绑定控制器。

新模块的编译需要精确匹配的内核源码、配置和工具链。本次使用 `make LLVM=-21 olddefconfig` 与 `prepare modules_prepare` 准备源码树，在独立模块目录编译。该内核 `CONFIG_MODVERSIONS=n`，从运行中内核的 `__ksymtab_*` 列表取得导出符号及所属模块，生成不使用 CRC 的符号表；最终 83 个依赖全部匹配，构建不再有未解析符号警告。没有强制加载不匹配 ABI 的模块。

旧的重绑定休眠脚本已停用；最终方案由驱动自身恢复保活与认证。此前导出的 rootfs/boot 镜像尚未重新打包此修复，重新安装旧镜像需另行安装该包。更换内核后需要重新编译，不能把此模块用于另一内核版本。
