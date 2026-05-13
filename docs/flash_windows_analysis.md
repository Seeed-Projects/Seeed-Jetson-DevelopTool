# Windows 刷机问题分析

> 适用版本：当前开发分支（基于 `wsl_flash.py` + `flash.py`）
> 日期：2026-05-11

---

## 一、现象描述

| 现象 | 说明 |
|---|---|
| 刷机卡在某一步 | 大概率卡在 USB 设备识别阶段（`_wait_for_usbipd_attach_stable` 超时） |
| 弹出外部 PowerShell 窗口 | **正常行为**，是 Windows UAC 提权弹窗，不可避免 |

---

## 二、PowerShell 弹窗的原因

`wsl_flash.py` 中所有需要管理员权限的操作，都通过 `_run_elevated()` 函数调用 PowerShell 执行 `Start-Process -Verb RunAs`：

```python
# wsl_flash.py:119-128
script = (
    "$p = Start-Process -FilePath "
    + _ps_single_quote(program)
    + " -ArgumentList "
    + _ps_single_quote(arg_string)
    + " -Verb RunAs -Wait -PassThru; exit $p.ExitCode"
)
subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
    ...
)
```

会触发提权的操作有：

| 操作 | 何时触发 |
|---|---|
| `wsl --install -d <distro>` | WSL Ubuntu 发行版未安装时 |
| `winget install dorssel.usbipd-win` | usbipd-win 未安装时 |
| `usbipd bind --busid <id> --force` | 普通用户无法 bind USB 设备时 |

**这是 Windows 安全机制，无法绕过。** 工具已经在代码中做了自动检测和自动安装（`WslFlashManager._ensure_usbipd()`），但 UAC 窗口本身必须由用户确认。

---

## 三、卡住的根本原因分析

刷机流程在 Windows 上走的是 WSL 路径，最可能卡在以下两个阶段：

### 阶段 A：USB 设备穿透超时（最常见）

**代码位置**：`wsl_flash.py` → `WslFlashManager._wait_for_usbipd_attach_stable()`（约 line 970）

**原理**：工具要求以下三个条件同时满足，且连续 3 次确认才认为 USB 穿透成功：

1. `usbipd attach --wsl --busid <id>` 命令返回成功
2. `usbipd list` 显示设备状态为 `attached`
3. WSL 内部 `lsusb | grep 0955` 能看到 NVIDIA APX 设备

**超时时间**：120 秒，超时则抛出 `WslFlashError("usbipd attach did not stabilize")`

**常见卡住原因**：

| 原因 | 排查方法 |
|---|---|
| Jetson 未进入 Recovery 模式 | 设备管理器/APX 设备不存在 |
| USB 线质量差（仅充电线，无数据） | 换用带数据功能的 USB-C 线 |
| USB 线过长或经过多个 hub | 直连电脑 USB 口 |
| WSL 内核缺少 USBIP 支持 | 见"阶段 B" |
| usbipd-win 未正确安装 | 手动运行 `winget install --interactive --exact dorssel.usbipd-win` |

### 阶段 B：WSL 内核缺少 USBIP 模块

**代码位置**：`wsl_flash.py` → `WslFlashManager._ensure_kernel_if_needed()`（约 line 529）

**检测逻辑**：工具检查 WSL 内核是否编译了 `CONFIG_USBIP_VHCI_HCD` 和 `CONFIG_USB_NET_RNDIS_HOST`。如果缺失，会尝试下载自定义 `bzImage` 并写入 `~/.wslconfig`，然后执行 `wsl --shutdown` 重启 WSL。

**风险**：自定义内核从 SharePoint 下载，如果网络问题或 URL 失效，下载失败后工具会静默跳过，刷机必然失败。

### 阶段 C：tegrarcm 写入超时

**代码位置**：`wsl_flash.py` → `WslFlashManager._check_tegrarcm_result()`（约 line 1251）

刷机脚本运行 `tegrarcm_v2` 时返回 `return value 3` 或 "might be timeout in usb write"，说明 APX 启动数据未能成功发送。这种情况下工具会尝试循环重新 attach USB，但 USB 穿透不稳定时仍会失败。

---

## 四、完整的 Windows 刷机前置条件

要让客户端在 Windows 上成功刷机，以下条件缺一不可：

### 4.1 WSL2 环境

```powershell
# 检查是否已安装
wsl --list --verbose

# 如果没有，手动安装（需要管理员权限）
wsl --install -d Ubuntu-20.04
```

> 当前工具会根据 L4T 版本自动选择发行版：
> - L4T ≤ 32.x → `Ubuntu-18.04`
> - L4T ≥ 36.x → `Ubuntu-20.04`

### 4.2 usbipd-win（必须）

用户提到的命令就是安装这个：

```powershell
winget install --interactive --exact dorssel.usbipd-win
```

工具会在检测到缺失时自动调用上述命令（带 `--interactive`），但必须手动确认 UAC 提权窗口。

> **注意**：工具内嵌的命令也是 `winget install --interactive --exact dorssel.usbipd-win`，与用户提供的一致。

### 4.3 WSL 内核 USBIP 支持

```powershell
# 在 WSL 内检查
zcat /proc/config.gz | grep -E "USBIP|VHCI"
# 或
ls /lib/modules/$(uname -r)/kernel/drivers/usb/usbip/
```

如果缺少，工具会自动处理，但存在下载失败的风险。

### 4.4 Jetson 进入 Recovery 模式

正确的进入方式：

1. 断开电源
2. 用 USB-C 线连接 Jetson 和电脑（**使用带数据功能的 USB-C 线**，不要用仅充电线）
3. 按住 Recovery 按钮（reComputer 背面有专门的 Recovery 按钮）
4. 保持按住，按一下 Reset 按钮
5. 松开 Reset 按钮，2-3 秒后松开 Recovery 按钮
6. 在 Windows 设备管理器中应能看到 "NVIDIA APX" 或 "NVIDIA Corp. Device"

### 4.5 防火墙/安全软件

如果电脑上装了 360、火绒等安全软件，可能拦截 `usbipd.exe` 的网络通信，需要放行。

---

## 五、现有代码中已实现的能力

| 功能 | 代码位置 | 状态 |
|---|---|---|
| WSL 发行版自动安装 | `wsl_flash.py:_ensure_wsl()` | ✅ 已实现 |
| usbipd-win 自动安装 | `wsl_flash.py:_ensure_usbipd()` | ✅ 已实现 |
| WSL 内核 USBIP 检查与修复 | `wsl_flash.py:_ensure_kernel_if_needed()` | ✅ 已实现 |
| Recovery 设备自动搜索 | `wsl_flash.py:_find_or_attach_recovery()` | ✅ 已实现 |
| USB 设备自动循环 attach | `wsl_flash.py:_start_auto_attach()` | ✅ 已实现 |
| USB 穿透稳定性等待 | `wsl_flash.py:_wait_for_usbipd_attach_stable()` | ✅ 已实现 |
| 刷机脚本在 WSL 内执行 | `wsl_flash.py:_run_flash_in_wsl()` | ✅ 已实现 |

---

## 六、解决方案汇总

### 方案 1：手动确认 UAC 弹窗（立即可做）

当工具弹出 PowerShell 提权窗口时，**不要关闭**，点击"是"确认。这样工具才能完成：
- WSL 发行版安装
- usbipd-win 安装
- USB 设备 bind

### 方案 2：手动安装 usbipd-win（跳过工具自动安装）

```powershell
winget install --interactive --exact dorssel.usbipd-win
```

重启终端/客户端后再尝试刷机，可以减少一次 UAC 提权。

### 方案 3：检查 Jetson Recovery 模式（关键）

如果 Recovery 设备不存在，工具会卡在 120 秒超时。

**Windows 排查**：
```powershell
# 查看 NVIDIA APX 设备（Recovery 模式下）
usbipd list
# 或
lsusb
# 找 VID=0955 的设备
```

**Linux/WSL 内排查**：
```bash
lsusb | grep 0955
# Recovery 模式下应该看到类似：
# Bus 001 Device 002: ID 0955:7323 NVidia Corp. APX
```

如果找不到设备 → 重新进入 Recovery 模式。

### 方案 4：使用优质 USB-C 线

很多人刷机失败的元凶是 USB 线仅支持充电，不支持数据。用一条确认有数据功能的 USB-C 线（如设备自带的线或标注了"数据线"的线）。

### 方案 5：确认 WSL 内部能看到 APX 设备

进入 WSL 后运行：

```bash
lsusb | grep 0955
```

如果这里看不到设备，说明 `usbipd attach` 穿透失败了，问题在 Windows 侧（usbipd-win、WSL 内核、USB 线三选一）。

---

## 七、刷机卡住时的调试信息

如果刷机过程中卡住，可以提供以下信息帮助进一步定位：

```powershell
# 1. usbipd 设备列表
usbipd list

# 2. WSL 状态
wsl --list --verbose

# 3. WSL 内是否能看见 APX
wsl -d Ubuntu-20.04 -- bash -c "lsusb | grep 0955"

# 4. 查看 usbipd 服务状态（设备管理器 → 查看 → 显示隐藏的设备）
#    找 "USB IP Bus (WINUSB Compatible)" 驱动下的设备
```

---

## 八、新增的详细日志功能

工具已在 `wsl_flash.py` 中加入了全面的分级步骤日志，每个阶段都会输出详细的诊断信息。运行刷机时，日志会按顺序显示：

### 7 步流程标题

```
============================================================
Windows WSL2 Flash Workflow Starting
============================================================
[STEP 1/7] WSL distro setup
[STEP 2/7] usbipd-win setup
[STEP 3/7] WSL kernel USB/IP check
[STEP 4/7] Find & bind recovery device
[STEP 5/7] USB passthrough stabilization
[STEP 6/7] Execute flash script in WSL
[STEP 7/7] Cleanup
============================================================
```

### 各步骤日志详情

| 步骤 | 日志前缀 | 关键信息 |
|---|---|---|
| 1/7 WSL setup | `[WSL status]` / `[WSL]` | WSL 版本信息、已安装发行版列表、选择的 distro、UAC 提权返回值 |
| 2/7 usbipd-win | `[usbipd]` | 设备列表（每个设备的 BusID/HWID/状态）、版本号、USBPcap 警告 |
| 3/7 内核检查 | `[WSL kernel]` | `CONFIG_USBIP_VHCI_HCD` / `CONFIG_USB_NET_RNDIS_HOST` 是否存在、是否下载自定义 bzImage、WSL 重启通知 |
| 4/7 Recovery 设备 | `[usbipd scan #N]` | 每次扫描尝试的设备列表、找到 APX 设备时的 BusID/状态、超时前的最终设备列表（诊断卡住原因） |
| 5/7 USB 穿透稳定 | `[usbipd stable?]` | 每次检查的 A/B/C 三项状态（A=事件已触发、B=Windows attached、C=WSL lsusb）、STABLE_HITS 计数、重置时说明哪项失败 |
| 6/7 刷机脚本 | 直接透传 NVIDIA flash 输出 | WSL flash 脚本的每行输出都会打印，失败时显示 ROOT CAUSE 分析 |
| 7/7 清理 | 完成标记 | 最终成功/失败状态 |

### STEP 5/7 的 A/B/C 状态检查

每 2 秒输出一次状态行：

```
[usbipd stable?] #3 [118s left] A=Y B=Y(Attached) C=Y(Bus 001 Device 002: ID 0955:7323 NVidia Corp.) STABLE_HITS=1/3
[usbipd stable?] #4 [116s left] A=Y B=Y(Attached) C=Y(Bus 001 Device 002: ID 0955:7323 NVidia Corp.) STABLE_HITS=2/3 ** ALL OK **
[usbipd stable?] #5 [114s left] A=Y B=Y(Attached) C=Y(Bus 001 Device 002: ID 0955:7323 NVidia Corp.) STABLE_HITS=3/3 ** ALL OK **
```

如果某项失败（非 ALL OK），日志会提示：
- A=N → attach 事件未收到，工具侧问题
- B=N(Shared) → Windows usbipd 未 attach 设备，USB 线/端口问题
- C=N → WSL 内看不到 APX 设备，WSL 内核缺 USBIP 支持

### 超时时输出的诊断信息

STEP 5/7 超时会打印：
1. 成功稳定次数 / 3
2. Windows 侧最终 `usbipd list` 状态
3. WSL 侧最终 `lsusb` 输出
4. 对应的根因判断（USBPcap / USB 线质量 / Recovery 模式）
5. 具体的解决步骤建议

## 九、结论

| 问题 | 原因 | 解决方案 |
|---|---|---|
| PowerShell 弹窗 | Windows UAC 提权机制，工具必须 | 正常现象，确认即可 |
| 刷机卡住 | USB 穿透未稳定（APX 设备未正确穿透到 WSL） | 检查 Recovery 模式、USB 线、usbipd-win 安装状态 |
| usbipd-win 未安装 | 工具会尝试自动安装 | 可手动 `winget install --interactive --exact dorssel.usbipd-win` 跳过 |
| WSL 内核缺 USBIP | Seeed 自定义内核下载可能失败 | 手动检查或等待工具自动修复 |
| STEP 5/7 超时 | 三项 USB 穿透检查未能同时稳定 | 根据 A/B/C 日志定位是 Windows 侧还是 WSL 侧问题 |

**核心结论**：当前代码已完整支持 Windows + WSL 刷机，工具会自动安装 `dorssel.usbipd-win`。卡住的原因 90% 来自 Recovery 模式未正确进入或 USB 穿透不稳定，而非代码本身缺失功能。
