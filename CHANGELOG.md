# 更新日志

## 0.1.9.post4（最新）

### AI-bot 与 API 配置

- **eb75c8d** `refactor(config): remove hard-coded proxy URLs and allow explicit ai_provider`
  - 移除硬编码的第三方代理域名（`cc.580ai.net`、`api.zhizengzeng.com`），只保留官方 `api.anthropic.com`。
  - 支持在 `~/.config/seeed-jetson-tool/config.json` 中通过 `ai_provider` 字段强制指定 `anthropic` 或 `openai`。
  - OpenAI 端点通过匹配本地 Codex 配置中的 `base_url` 来识别，适配每个人不同的代理地址。

- **adbeccc** `feat(ai): auto-detect Anthropic/OpenAI provider and support Codex endpoints`
  - 自动识别 AI provider：当 `base_url` 与本地 Codex 配置一致时走 OpenAI 协议，否则走 Anthropic 协议。
  - 完整读取 Codex CLI 配置中的 `api_key`（支持 `OPENAI_API_KEY` 环境变量作为 fallback）。
  - OpenAI 分支自动补全 `/v1` 路径，支持 function-calling/tool 调用。
  - Anthropic 与 OpenAI 两个分支均使用 `httpx.Client(trust_env=False)`，避免系统 socks 代理导致崩溃。

- **fb60968** `fix(ai|flash|data): fallback to local Claude/Codex config, sort L4T descending, remove duplicate products`
  - AI 配置新增 Claude Code / Claude Desktop `settings.json` 和 Codex CLI `config.toml` 作为 fallback 来源。
  - 修复 AI 聊天因系统 socks 代理（如 `socks://127.0.0.1:7890/`）报 `Unknown scheme for proxy URL` 的问题。

### 刷机与 BSP 数据

- **8a8125e** `feat: add JetPack 7.2 BSP records and fix cache merge`
  - 合并 Wiki 中的 JetPack 7.2 BSP 记录（共 27 条，覆盖 J401/J301/ReServer Industrial 等产品）。
  - 修复 `data_update.py` 缓存与包内数据合并逻辑，避免旧缓存覆盖新 BSP 记录。

- **fb60968**（同上）
  - Flash 页面 L4T 版本下拉框改为按版本号降序排列，默认选中最新 JetPack 7.2。
  - 删除重复的 `j401-robotics-orin-nx/nano-*` 4 条 BSP 记录。

### 远程文件传输

- **873f0df** `fix(remote): enable folder navigation and selected-row download in dialog`
- **978253d** `feat(remote): double-click folder to navigate in download dialog`
- **32b5147** `feat(remote): add Jetson → PC file download`
- **850c55f** `feat(remote): add SSH drag-and-drop file transfer`

---

## 0.1.9.post3 及更早

历史提交请查看 `git log`。
