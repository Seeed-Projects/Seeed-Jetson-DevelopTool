---
name: rebot-arm-grasp
description: 使用 CASCADE 的 MCP 工具让 agent 驱动 Seeed reBot DevArm B601（RobStride）定位、抓取、搬放物体，并检查标定、安全状态和独立执行证据；适用于实机抓取及其 mock 验证。
---

# reBot 物体抓取

让 Codex 作为决策 agent，使用一个持续运行的 CASCADE MCP 会话完成观察 → 定位 → 抓取/搬放 → 结果核验。关节控制、IK、速度限制、障碍物和接触检查继续由 CASCADE 执行。此 skill 是操作层，运行时依赖完整 CASCADE 源码、机器人资产和现场配置；单独安装 skill 不会安装驱动或获得硬件验收。

## 入口与连接

- 已有 CASCADE MCP：先读取 `world_state`，确认当前实际 arm、camera 和能力；不要创建第二个总线控制进程。工具名前缀取决于 MCP 注册名称，以实际 `tools/list` 为准。
- 尚未连接：读 [setup.md](references/setup.md)，运行 `scripts/runtime.py check`。默认是纯 mock。`check` 只检查本地文件/依赖，不访问设备，也不代表实机 READY。
- 实机接入前读 [hardware.md](references/hardware.md)。本包实机启动器支持 `type: rebot_rs` 的 B601 RobStride SDK 路径；`rebot_rs_mb`、DM 电机和其他机械臂需要各自验证，不自动切换。
- 用 `scripts/runtime.py mcp-config` 生成配置，`serve` 持续提供原生 MCP。启动器将实机置于软件 STOP；用户当前抓取指令已授权实机运动且现场检查通过时，可以按实际 schema 调用 `reset_stop`。历史急停、接触故障或操作员禁用的 reset 必须先解决原因，不自动清除。
- 本包没有通用实机 `call`/批量运动脚本。实机调用通过已注册 MCP 会话进行；`smoke_test.py` 被固定为 mock。

命令示例（`SKILL` 是本技能所在目录，`REPO` 是目标 CASCADE checkout 的绝对路径）：

```bash
python3 "$SKILL/scripts/runtime.py" check --repo "$REPO"
python3 "$SKILL/scripts/runtime.py" smoke --repo "$REPO"
python3 "$SKILL/scripts/runtime.py" check --repo "$REPO" \
  --mode hardware --arm rebot_rs --cameras YOUR_CALIBRATED_CAMERA
```

## 每次任务

1. 读 `world_state`，检查 `stopped`、`tracked_holding`、`gripper_contents`、`backends`、`capabilities`、`tools_withheld` 和操作员隐藏项。MCP 的 tracked_holding 是 session 记录，gripper_contents 通常是 not_measured；其他界面可能称 holding/estopped。待接触/释放、可能仍有负载、标定失效或地图错误时，进入 [recovery.md](references/recovery.md)，不要通过改限制恢复运动。
2. 调用 `get_observation` 或 `describe_scene` 获取当前图像。`camera_snapshot` 可选择 exact camera name。确认目标身份、所在工作区域及放置目的地；同类物体不唯一时用 `localize_object(label, spatial_hint)`，仍不明确就澄清。自然语言可用中文；参数保留工具要求的名称/枚举，物体 label 按实际图像和识别结果表达。
3. 实机用 `localize_object` 和 `preview_grasp` 检查目标位置、尺寸、拟议夹爪宽度/方向。位置是机器人基座坐标、米；关节角是弧度。预览仅是候选计划，**不证明完整运动可执行**，实际抓取仍要重新感知并经过 IK/安全检查。configured zone 是配置来源，不证明它可见或为空。
4. 按用户意图选择一个工具：
   - “抓住/拿起来并保持”：`grasp_object({"label": "red cube", "material": "rigid"})`。完成后保留会话及负载；不追加放下、开爪或断电。
   - “抓取并放到 …”：优先 `pick_and_place({"object": "red cube", "destination": "已确认的目的地"})`；仅用户接受当前配置的 drop zone 时才省略 destination。此工具包含有界重试和返回 home，检查 `return_home`，不重复调用 `move_home`。
   - 已持物：先核实持物身份和负载状态，再用 `place_on_object`，或用本次观测/现场确认的基座坐标调用 `place_at`。不重新抓取另一物体。
5. 查看动作结果中的 `ok`、`execution_ok`（若有）、`stage`、`outcome`、`postcondition`、`return_home`；再读 `verify_last_action` 和新观测。`verify_last_action` 读取已保存 verdict，不重新测量，也不能升级缺失证据。多步任务在下一动作前用 `task_memory` 检查已完成步骤。
6. 报告目标、实际动作、结果状态和证据来源，并给出 trace/run 路径。`postcondition.status` 为 `confirmed` 才称该后置条件独立验证成功；`refuted` 是失败；`unverified` 明确说缺乏独立证据。`tracked_holding`、belief 更新、模型置信度、`ok: true`、端口连通都不能单独证明物理成功。Mock 的静态图像通常 abstain，不能声称物体真的移动。

完整参数示例和字段解释见 [tools-and-results.md](references/tools-and-results.md)。每次以运行中服务器提供的 schema 为准；能力目录可能在预热后变化，缺少/拒绝工具时先重新读取状态和目录。单臂 schema 通常没有 `arm` 参数，不能自行添加。

## 实机操作约束

- 当前任务必须包含对实机运动的授权。创建/安装 skill、诊断或模拟测试不授权操作实机。已有授权覆盖任务内必要动作，无需逐动作重复确认；不擅自扩展成标定 sweep、试 jog 或重启硬件。
- 通过原生 MCP → `SkillRuntime.execute` → `SafeArm` 执行运动。不要直接写 CAN、调用 SDK/`SafeArm.raw`、使用任意 exec bridge 或绕过 `_MOTION_SKILLS`。
- 固定相机需要对应这台设备、机器人和**当前安装位置**的已接受标定。仓库附带参考机记录不是新现场的标定。腕部相机需要随捕获时刻绑定的 eye-in-hand transform，不能用一个静态 T 替代。
- 保留 profile 的 `joint_signs`、home seed/回 home 策略、workspace、table、速度上限、mesh body mask、wrist-camera-up、实时 occupancy 和 contact monitor。`rebot_rs` 的 occupancy 是 required；不得通过 `CASCADE_OCCUPANCY=0`、改为可选、扩大工作区、减少 body mask 或调整接触门限让拒绝变成通过。
- 仅一个进程拥有 CAN host-id 0xFD。停止竞争程序要针对确认的控制器；不使用批量 kill，也不因超时另起控制会话。
- `pick_and_place` 已有内部重试预算；失败后先看状态/证据，不循环重发。最多一次有明确新依据且保持原安全配置的外部重试；接触、急停、未知持物、标定/地图故障及用户“然后停止”时没有自动重试。
- 用户叫停立即 `emergency_stop`，不要排在普通读操作之后。运行中的 MCP reader 能优先处理 stop/cancel；默认普通读操作可能排队，不能当作实时制动。
- `move_home` 是抬起的就绪位、仍有扭矩；`move_to_rest` 是验证后的折叠停放。夹持/疑似夹持、pending contact/release 或 STOP 时不自动开爪、park、disconnect、kill/restart。`disconnect()` 和重新连接时的故障清除可能切扭矩。需要结束实机会话时，先完成合法放置、确认空爪，再执行经核验的 `move_to_rest`；失败时保持会话供操作员恢复。

## 验证范围与维护

读 [validation.md](references/validation.md) 运行结构检查、脚本测试和离线 MCP smoke；本次软件检查结果见 [validation-result.json](references/validation-result.json)。硬件验收必须在目标现场另做；软件测试通过不保证每次抓取成功。源码证据登记在 [source-manifest.json](references/source-manifest.json)，`check` 报告核心源码变更；实机启动遇到核心源码漂移会拒绝，需审核新的运行时后更新该 manifest。现场 profile/标定可以调整，但必须重新核实其绑定和物理尺寸。
