# 更新日志

## Unreleased

### 新功能

- **feat(bootstrap): 新 Ubuntu 启动时自动安装 Python 与 GUI 系统依赖**
  - `python run_v2.py` 缺 PyQt6、qtpy 及其他运行依赖时自动用当前解释器的 pip 安装；没有 pip 时先 `ensurepip`，Ubuntu 上再回退安装 `python3-pip`。
  - 系统 Python 受 PEP 668 限制时，自动改用 `--break-system-packages`。
  - Linux 上默认补齐 Qt xcb / OpenGL 运行库和 Xvfb，不再只打印 apt 命令后退出。`SEEED_AUTO_INSTALL_SYSTEM=0` 可关闭系统包自动安装。

- **feat(agent): 预设任务、已配置 SSH 复用与上位机可视化**
  - 增加连接设备、网络共享、摄像头、机械臂读数/动作等 7 个紧凑预设；按明确任务路由只检查对应技能文件，双语提示词每轮携带当前设备与技能路径。
  - 本机 CLI 通过临时、带认证的回环入口复用 DevelopTool 的 SSH/端口/sudo 配置，支持保存配置重连；密码不进入提示词，自动执行关闭时拒绝桥接命令，切换目标后拒绝旧请求。
  - 对话旁新增摄像头与数据标签：远端 OpenCV 预览支持设备路径、RTSP 与 GStreamer；独立后台线程采集系统数据，并接收 Agent 回传的带单位机械臂/传感器读数及采样时间。
  - 网络共享直接打开已有工具；新增 `developtool-device`、`jetson-pc-wired-share` 与 `soarm-control` 路由指引并同步两套目录、三种 Agent marker。续聊绑定实际会话 ID，避免混入其他 CLI 会话；普通工作目录可直接启动 Codex。
  - 修正状态徽标背景透明度；新增桥接鉴权、配置重连、目标切换、技能匹配、数据校验、双语占位符与技能副本一致性测试。

- **feat(skills): 内置新技能 `rebot-arm-grasp`（reBot DevArm B601 机械臂抓取），新增「机器人」分类**
  - 三棵 skills 树（repo `skills/` 与包内 `seeed_jetson_develop/skills/`，openclaw/claude/codex 三变体）同步合入 CASCADE MCP 驱动的机械臂抓取技能：观察 → 定位 → 抓取/搬放 → 核验，含 `references/`（setup/hardware/recovery 等）与 `scripts/`（runtime.py / mock_fixture_server.py / smoke_test.py）。
  - `engine.py` 新增 `CATEGORY_ROBOTICS`（图标 🦾、i18n key `skills.category.robotics` 双语），slug 关键词 `rebot/grasp/robotic/soarm/moveit/-arm` 归入该分类；Skills 页分类映射同步补充。

- **feat(agent): 新增「AI Agent」页面 —— 复用本机 Claude Code / Codex CLI 驱动 Jetson 与 Physical AI 开发**
  - 新模块 `modules/agent/`：`backend.py` 以非交互模式包装本机 `claude`（stream-json）/ `codex`（exec --json JSONL）CLI，逐行解析为文本/工具事件流，支持续聊（`--continue` / `exec resume --last`）与「自动执行」权限开关（`--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox`）。
  - 页面内置 Physical AI 快捷场景卡片（📷 摄像头接入、📡 雷达/传感器、🦾 SO-ARM101 机械臂、🧭 自由任务）一键填充预设提示词；支持工作目录选择、Jetson SSH 连接状态徽标（首轮自动注入设备上下文，引导 agent 经 `ssh` 操控设备）。
  - `cli_tools.py` 统一 agent 目录约定（本机 claude→`~/.claude/skills`、codex→`~/.agents/skills`(+`~/.codex/skills`)；Jetson→`~/.claude|codex/skills`）与本机 CLI 检测。
  - `agent_setup_dialog.py`：本机 PC 缺少 claude/codex CLI 时一键 `npm install -g` 补装（Node.js 缺失时给出安装引导）。

- **refactor(ai_chat): AI 悬浮球重写为 Agent 页入口**
  - 点击悬浮球进入新「AI Agent」页（侧边栏导航同步新增），移除原 LLM API 直连浮窗面板；`inject_context/inject_topic/inject_error` API 保持不变，自动跳页并预填输入框（Skills/Apps 页调用点零改动）。

- **feat(skills): NVIDIA Skills 一键安装区分「运行目标 + Agent」**
  - 对话框新增「安装到：本机 PC / Jetson 设备」与「Agent：Claude Code / Codex」选择器；本机安装命令携带 `--agent <claude-code|codex>` 落到对应目录，Jetson 安装经 SFTP 推送到所选 agent 的 skills 目录（不再仅限 Codex）。
  - Jetson 目标安装前自动检测所选 agent CLI，缺失时可选调起 `AgentInstallDialog` 补装；本机缺 CLI 时仅提示不阻断（skills 为纯文件）。
  - 场景/目标标签全部改为 i18n key（`skills.nvidia.*`，双语），分类新增 soarm/lerobot/isaac → 机器人与物理 AI。

- **test**: 新增 `tests/test_agent_backend.py`（命令构造 / Claude 与 Codex 事件解析 / ANSI 清洗 / 目录约定 / 安装线程签名）；扩展 NVIDIA 安装线程 agent 参数用例。

## 0.2.0.post2（最新）

### 新功能

- **feat(skills): 「获取 NVIDIA Skills」接入 Jetson Codex 流程**
  - SSH 已连接 Jetson 时点击该按钮：先检测 Jetson 上 Codex CLI（`codex --version`），未安装则弹出 Codex 安装对话框（复用 `AgentInstallDialog`，新增 `only_agents` 模式只装 Codex），安装成功后进入 NVIDIA Skills 浏览/安装。
  - Jetson 模式下技能安装改为「本机 npx 拉取 + SFTP 推送至 Jetson `~/.codex/skills/<name>`」，规避 Jetson 直连 GitHub 克隆超时问题；已安装状态改为远程目录检测（`~/.codex|agents|claude/skills`）。
  - 未连接 Jetson 时保持原有本机 PC 安装流程不变；按钮文案改为 i18n key（`skills.banner.get_nvidia`）。

- **feat(apps): 应用市场新增「Codex CLI」卡片**
  - `apps.json` 新增 `codex-cli`：自动保障 Node.js ≥ 20（NodeSource 22.x，回退 apt）→ `npm install -g @openai/codex`，支持状态检测与卸载。

- **feat(remote): Agent 安装对话框 Node.js 保障升级**
  - `build_node_ensure_cmd()`：检测 Node 主版本 ≥ 20 跳过；否则 NodeSource 22.x 优先、apt 兜底（此前仅 apt，Ubuntu 24.04 源仅 18.x）。

- **feat(remote): 网络共享重构为 NetworkManager `ipv4.method shared` 优先（参照 jetson-pc-wired-share 技能）**
  - 开启共享：LAN 网卡受 NM 管理时改用专用 `jetson-wired-share` 连接（autoconnect no / never-default yes / 保留既有静态 IP，不断 SSH），NM 自动接管 NAT + DHCP + DNS 转发；nmcli 缺失/网卡 unmanaged/NM 失败时自动回退原 iptables 方案。
  - 关闭共享：down 共享连接并自动恢复原始有线连接（状态存于 `~/.cache/seeed-jetson/net_share_state.json`），同时幂等清理旧 iptables 规则；Jetson 端经 SSH 还原默认路由/resolvectl/nmcli 持久化配置（`build_jetson_restore_cmd`）。
  - Jetson 联网验证改为分级检测（ping PC 网关 → ping 公网 → DNS → HTTPS， `build_jetson_verify_cmd`），按首个失败环节给出精确排障提示，不再只报「ping 8.8.8.8 失败」。

- **fix(theme): 消息框标准按钮（Yes/No/Cancel/OK）硬编码中文**
  - `ThemedMessageBox._STANDARD_TEXT` 改为经 `gui.i18n.t("common.yes/no/cancel/ok")` 按当前语言取值，英文界面下按钮不再显示「是/否/取消」。

- **test**: `test_nvidia_skills_load.py` 新增远程技能名解析/新线程导入/Node 保障命令用例；`test_apps_registry.py` 新增 `codex-cli` 注册校验。真机（reComputer, Ubuntu 24.04）验证 Codex 安装与 skill SFTP 推送通过。

- **feat(backup_restore): 新增系统备份/恢复页面**
  - 包装官方 `l4t_backup_restore.sh` 的 Seeed 全机型备份/恢复脚本（`modules/backup_restore/scripts/jetson-backup-restore.sh`）。
  - 支持板型自动发现（`*.conf`）、L4T 树自动探测/手动选择、等待 APX (Recovery) 模式、目标设备盘符配置。
  - 内置磁盘空间与 NFS (mountd/rpc-statd) 预检；备份完成后逐项 SHA256 校验镜像。
  - 恢复操作二次危险确认；后台线程执行 + 实时日志 + 可取消。
  - 新增侧边栏导航「系统备份 / Backup & Restore」，双语（en/zh-CN）文案齐备。
  - 打包配置（pyproject/MANIFEST）纳入脚本资源。

- **feat(backup_restore): 备份页集成「一键准备」环境脚本**
  - 内置改造版 `setup-workspace.sh`（新增 `--root`/`--minimal`/`SUDO_PASS` 支持）：随包发行，可从零下载 NVIDIA 官方 BSP 与 Seeed 定制层并组装出可备份的 `Linux_for_Tegra` 树。
  - 页面整合为单张「备份 / 恢复」主卡（准备 → 配置 → 执行三步指示）：选版本 + 工作区 + sudo 密码后一键准备，完成后自动填充 L4T 路径并刷新板型。
  - 极简模式跳过内核源码与工具链（约省 1GB 下载），备份/恢复所需文件完整保留；准备线程与备份/恢复线程互斥。
  - 修复上游脚本在「本机代理可用且直连 GitHub 也通」时克隆两次导致失败的问题（直连成功则不再二次克隆）。

- **feat(backup_restore): 一键准备交互加固**
  - 准备启动时捕获版本/工作区,完成自动填充不再受运行中改动影响(修复竞态)。
  - 启动前预检 curl/git,缺失时明确提示,不再以晦涩脚本报错收场。
  - `discover_l4t_dirs` 跳过不可读/失效挂载点,避免单个坏盘导致页面崩溃。
  - 新增 `tests/test_backup_prepare.py` 回归测试(版本提取、线程命令/环境构造)。

- **feat(backup_restore): 备份页交互简化——一键准备为主路径**
  - 目录类型设置不再用输入框:工作区为带当前路径的按钮(点击弹目录选择),「已有环境」折叠成一行低调入口,主流程 = 选版本 → 一键准备。
  - 无现成树时页面默认引导一键准备;自动探测/手动选择作为展开后的备选。
  - 修复已有环境面板在窗口未显示时只能展开不能折叠的状态判断(`isVisible` → `isHidden`)。


### 修复（备份/恢复实战跑通）

- **fix(backup_restore): 真机备份跑通——host pty 损坏诊断与防护**
  - 实战根因: 本机 `/dev/pts` 被之前 flash/chroot 类操作挂坏 (`ptmxmode=000`, 无 `ptmx` 节点), sshpass 本机申请 pty 全部 ENXIO, 报「Failed to get a pseudo terminal: No such device」且与设备无关。诊断修复: 重新挂载 devpts。
  - wrapper 新增 host pty 预检: `/dev/pts/ptmx` 缺失时直接给出修复命令, 不再让 sshpass 报费解错误。

- **fix(backup_restore): 备份失败误报成功**
  - backup 分支此前不检查官方脚本退出码, 且 `images` 目录刚 mkdir 过必然存在 → 0 产物也报「✓ Backup completed」。现在: 退出码非 0 即 die; 必须存在 `nvpartitionmap.txt` + ≥1 个镜像文件才算成功。
  - 校验计数器原子 bug: 在子 shell 里自增导致「全部 0 个镜像校验通过」; 改 `pushd`/`popd` 主 shell 执行, 实测输出正确计数。
  - 修复 `verify_checksums` 的 `done < "${map}"` 卡死 (此前挂在死循环)。

- **feat(backup_restore): 多套备份自动归档**
  - 每次备份前把 `images` 根的上一套自动归档为 `images/<板型>_<时间戳>/` (同盘 mv 零拷贝), `images` 根永远放最新一套; 恢复时可在 UI 备份集下拉选择任意历史集。
  - 修复数据安全隐患: 恢复历史集同步改用真拷贝 `cp -a` (原 `cp -al` 硬链接使归档与根共享 inode, 下次备份就地截断会写坏归档)。
  - 备份集下拉显示可读标签「板型 · 备份时间 · 大小」(取自 `nvpartitionmap.txt` 的 board_spec 与 mtime), 历史集按时间倒序; 任务完成后即时刷新。

- **fix(i18n): 清零审计告警 26 处**
  - 真文案 14 处补翻译 (runner 登录错误、AI 悬浮球 tooltip、net_share ICS/NAT 状态、skills 日志计数), 插值串改为「模板翻译 + format」并修复旧表碎片式条目永不匹配的 bug。
  - 误报 12 处 (sudo 密码检测、wsl 中文输出检测、已双语 `_msg` 对) 入审计 ignore 白名单。
  - `scripts/i18n_audit.py` 现全绿: locale 键集 1040 对齐, 代码 0 未翻译字面量。

## 0.1.9.post4

### 修复

- **fcacc07** `fix(gui): convert QPoint to QPointF for QLinearGradient on PyQt6/macOS`
  - 修复 macOS + PyQt6 启动时 `QLinearGradient` 因参数类型不匹配导致的崩溃。

### OTA 数据

- **80f26e3** `feat(ota): add JP6.1/6.2 → JP7.2 OTA paths for Industrial/Robotics series`
  - 新增 reComputer Industrial、Robotics J501、Robotics Mini J501、Robotics J401 四个系列的 JetPack 6.1/6.2 → JetPack 7.2 OTA 升级路径。
  - 均为含 SDK 的 payload，共用 L4T 39.2.0 的 OTA tools。

### 文档与统计

- **ff0728d** `docs(readme): add dynamic PyPI downloads chart`
  - 新增 `scripts/generate_downloads_chart.py`，从 pypistats.org 拉取近 90 天下载数据并生成 SVG 趋势图。
  - 新增 GitHub Actions 工作流，每天自动更新 `assets/downloads-chart.svg`。
  - 在 `README.md` 和 `README_zh.md` 中加入 PyPI 总下载量/月下载量徽章和动态下载曲线图。

### AI-bot 与 API 配置

- **eb75c8d** `refactor(config): remove hard-coded proxy URLs and allow explicit ai_provider`
  - 移除硬编码的第三方代理域名（`cc.580ai.net`、`api.zhizengzeng.com`），只保留官方 `api.anthropic.com`。
  - 支持在 `~/.config/seeed-jetson-tool/config.json` 中通过 `ai_provider` 字段强制指定 `anthropic` 或 `openai`。
  - OpenAI 端点通过匹配本地 Codex 配置中的 `base_url` 来识别，适配每个人不同的代理地址。

- **9b12c8f** `docs(ai_chat): remove specific gateway name from comment`
  - 清理代码注释中的具体网关名称，避免误导。

- **adbeccc** `feat(ai): auto-detect Anthropic/OpenAI provider and support Codex endpoints`
  - 自动识别 AI provider：当 `base_url` 与本地 Codex 配置一致时走 OpenAI 协议，否则走 Anthropic 协议。
  - 完整读取 Codex CLI 配置中的 `api_key`（支持 `OPENAI_API_KEY` 环境变量作为 fallback）。
  - OpenAI 分支自动补全 `/v1` 路径，支持 function-calling/tool 调用。
  - Anthropic 与 OpenAI 两个分支均使用 `httpx.Client(trust_env=False)`，避免系统 socks 代理导致崩溃。

- **fb60968** `fix(ai|flash|data): fallback to local Claude/Codex config, sort L4T descending, remove duplicate products`
  - AI 配置新增 Claude Code / Claude Desktop `settings.json` 和 Codex CLI `config.toml` 作为 fallback 来源。
  - 修复 AI 聊天因系统 socks 代理（如 `socks://127.0.0.1:7890/`）报 `Unknown scheme for proxy URL` 的问题。

### 刷机与 BSP 数据

- **4abcefd** `fix(data): update AGX Orin 64G JP7.2 BSP link`
  - 将 AGX Orin DevKit 64G / L4T 39.2.0（JetPack 7.2）的 BSP 下载链接替换为正确的 `mfi_seeed-agx-orin-64g-kit.tar.gz`。

- **54410ed** `docs(recovery): replace confusing 2/S3 and 3/S2 labels with button numbers for AGX Orin`
  - 将 AGX Orin 官方套件的 Recovery 步骤中 `2/S3`、`3/S2` 的标注改为 `2 号按钮`、`3 号按钮`，避免用户看不懂。

- **8a8125e** `feat: add JetPack 7.2 BSP records and fix cache merge`
  - 合并 Wiki 中的 JetPack 7.2 BSP 记录（共 27 条，覆盖 J401/J301/ReServer Industrial 等产品）。
  - 修复 `data_update.py` 缓存与包内数据合并逻辑，避免旧缓存覆盖新 BSP 记录。

- **fb60968**（同上）
  - Flash 页面 L4T 版本下拉框改为按版本号降序排列，默认选中最新 JetPack 7.2。
  - 删除重复的 `j401-robotics-orin-nx/nano-*` 4 条 BSP 记录。

### 远程与串口网络配置

- **0fb908d** `style(remote): make Jetson Init network buttons green`
  - 将 Jetson Initialization 页面的 `Configure Network IP` 和 `Network Share` 按钮也设为主题绿色（primary）。

- **0525259** `feat(remote): recursive folder upload/download over SFTP`
  - 上传线程支持递归上传本地文件夹，保持目录结构并汇总字节总进度。
  - 下载线程支持递归下载远程文件夹，按原目录结构保存到 PC。
  - 下载选择对话框允许勾选文件夹以下载其全部内容；双击仍进入文件夹。
  - 更新中英文 locale 提示文案。

- **fe71d6f** `fix(remote): emit byte-based overall progress during SFTP upload/download`
  - 修复文件传输时日志已显示 4% 但顶部进度条仍显示 0% 的问题。
  - 上传/下载线程现在先计算总字节数，并在传输过程中按总进度实时更新进度条。

- **8025ff0** `fix(remote): disable competing NM connections before applying static IP on JetPack 5`
  - 串口配置静态 IP 前，先断开目标网口、禁用该网口上其他 NetworkManager 连接的自动连接，再添加静态连接。
  - 解决 JetPack 5 上默认有线连接抢占 `eth1` 导致静态 IP 配置后无法 SSH 的问题。

- **873f0df** `fix(remote): enable folder navigation and selected-row download in dialog`
- **978253d** `feat(remote): double-click folder to navigate in download dialog`
- **32b5147** `feat(remote): add Jetson → PC file download`
- **850c55f** `feat(remote): add SSH drag-and-drop file transfer`

---

## 0.1.9.post3 及更早

历史提交请查看 `git log`。
