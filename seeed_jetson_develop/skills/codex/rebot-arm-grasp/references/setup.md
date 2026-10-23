# 安装与 MCP 连接

## 运行时

保留完整 CASCADE checkout：`src/`、`configs/`、`assets/`、`scripts/`。不要将 Python wheel 当作包含 profile/URDF/mesh 的独立安装；当前路径从源码位置派生。本包代码契约绑定的提交见 `source-manifest.json`，新版本要重审，不能只凭项目名称相同就视为兼容。

如果尚无 runtime venv，在 checkout 内：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev,kinematics]'
```

脚本按 `--python` → checkout `.venv` → 相邻 `.demo` → 当前解释器选取 Python，随后检查它的依赖和真实 import 路径；显式路径不要硬编码另一台机器的地址。另一个 worktree 的 editable install 可能指向旧 checkout，本包显式绑定目标 `src/`。

实机在同一 venv 中增加：

```bash
uv pip install --python .venv/bin/python -e '.[arm,perception,grasping,grasp-safety,occupancy]'
```

另外准备平台匹配的 torch、RealSense `pyrealsense2`（L515 需要仓库说明中的 librealsense fork）、本机检测权重/文本编码缓存和 SDK 的依赖。实机 helper 接受当前 YOLOE 本地路径，检查可提示 checkpoint 和启用 prompt-free 时的 `-pf.pt` checkpoint 都是真文件；不通过 native detector 的 first-use 下载补齐它们。不要假定安装 `perception` 就准备好了 CUDA、模型文件或相机驱动。reBot SDK 位置由 `arm.sdk_path` 确定，通常在 checkout 相邻的 `reBotArm_control_py/`；按上游 SDK 安装说明准备并记录提交。仓库 `scripts/update_rebot_sdk.sh` 会 pull 最新 main、改 origin 并设置代理，已有校验过的 SDK 不自动更新。

本包不会自动下载模型/SDK、更新总线、校准或移动机器人。

## 安装标准 skill

将整个 `rebot-arm-grasp/` 文件夹放入 `${CODEX_HOME:-$HOME/.codex}/skills/`。不要只复制 `SKILL.md`，references 和 scripts 是功能的一部分。重新打开 Codex 会话后用 `$rebot-arm-grasp` 调用；默认允许按描述自动发现。安装 skill 与注册 MCP 是分开的操作。

## 生成配置

先设置本机真实路径：

```bash
SKILL="${CODEX_HOME:-$HOME/.codex}/skills/rebot-arm-grasp"
REPO="/absolute/path/to/cascade"
python3 "$SKILL/scripts/runtime.py" check --repo "$REPO"
python3 "$SKILL/scripts/runtime.py" mcp-config --repo "$REPO"
```

`mcp-config` 输出 `[mcp_servers.cascade_rebot]` TOML，不修改 Codex 配置。把经过检查的 block 加入本机 Codex MCP 配置，保留其他条目。已存在同名 server 时修改该条目，不追加重复 TOML table。`codex mcp list` 检查注册；新会话调用工具核实实际 runtime。也可用 `codex mcp add cascade_rebot -- ...` 注册生成 block 里的 command/args；注册操作不会验收硬件。

实机（camera 必须是已绑定、已标定的 profile）：

```bash
python3 "$SKILL/scripts/runtime.py" check --repo "$REPO" \
  --mode hardware --arm rebot_rs --cameras YOUR_CALIBRATED_CAMERA
python3 "$SKILL/scripts/runtime.py" mcp-config --repo "$REPO" \
  --mode hardware --arm rebot_rs --cameras YOUR_CALIBRATED_CAMERA
```

配置用 skill 启动器 `serve`，再 exec 原生 `cascade.apps.mcp_server`，不会引入第二套安全控制器。实机启动置 STOP；headless 默认 `CASCADE_VIEW=0`、`CASCADE_STREAM=0`。若需要现有 dashboard，使用自己的已审 runtime 配置，避免额外启动总线 owner。

mock 会清除继承的所有 `CASCADE_*`，固定 mock arm/camera、analytic OBB、关闭 sidecar 和跨次 belief/episodic 持久化；mock serve/smoke 的抓取 priors、envelope 和 trace 全部保存在各自临时目录。hardware 会保留其他 `CASCADE_*` 开关，但清除 robot/base/multi-arm selector 并固定显式 arm/cameras、STOP、headless；设备与端口配置由生成 TOML 的 env 固化（不输出 token/key 等秘密）。不要在注册后靠新 shell 的变量改变已启动服务器。runtime 实际的 fallback/required 行为由本次 `world_state.backends` 验证。

会话 timeout 要覆盖 `pick_and_place` 内部预算。生成配置默认 tool timeout 240 秒；timeout 不是任务取消确认，遇到超时按 recovery 流程处理，避免叠加运动。
