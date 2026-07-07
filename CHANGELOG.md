# 更新日志

## 0.1.9.post4（最新）

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
