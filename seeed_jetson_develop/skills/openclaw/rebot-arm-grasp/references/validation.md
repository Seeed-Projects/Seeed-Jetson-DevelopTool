# 验证与证据边界

本包将可复现软件检查与现场硬件验收分开记录。

## 软件检查

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py "$SKILL"
REBOT_GRASP_REPO="$REPO" "$REPO/.venv/bin/python" -m pytest "$SKILL/scripts/test_runtime.py" -q
python3 "$SKILL/scripts/runtime.py" smoke --repo "$REPO"
```

validator 不属于 runtime 依赖：仅 skill 创作环境需要它。测试随技能包一起分发；本仓库的 `tests/test_rebot_codex_skill.py` 也收集同一组测试。scripts 使用标准库 bootstrap，在选中的 runtime venv 内加载源码；检查脚本不建立 camera/arm/sidecar 连接。

`smoke` 启动原生 MCP server，通过一个先验证 mock 类型的 fixture，仅给 MockArm 设置 synthetic gripper contact（45% 行程停住）。原生默认 mock 没有接触，因此完整 pick 会得到 air-grasp 失败；本 fixture 使成功路径可测，不修改生产控制代码或安全层。测试通过 JSON-RPC initialize、目录、观测、定位、预览、不存在目标的失败、pick_and_place、saved verification、STOP、被停止 motion 的拒绝和 reset 验证 wiring。它显式限定 mock，隔离 CASCADE 环境、所有抓取/操作 envelope 记忆和 run_dir，产出机器可读 receipt 与 server stderr，明确 `physical_validation: not_performed`。成功只说明软件链路可用；静态 mock 图像不会确认真实物体运动。它不会启动 GraspGen-X stub，不碰 CAN/USB，也不运行硬件 pytest。

下面的 occupancy 回归还需要 `grasp-safety` extra 中的 scipy；先在 runtime venv 安装 `.[dev,kinematics,grasp-safety]`。仓库回归（使用本 checkout 的 pytest 和测试配置，从 checkout 工作目录运行）：

```bash
"$REPO/.venv/bin/python" -m pytest tests/test_mcp_server.py \
  tests/test_safety.py tests/test_rebot_rest_and_park.py \
  tests/test_rebot_occupancy_live.py tests/test_contact_rebot_rs.py -q
```

根据变更范围增加 calibration/grasp/safety 的现有测试。完整 suite 另有厨房资产和可选运行时要求；不得将 skip 或 0 selected 说成覆盖。硬件 tests 默认被 deselect，显式 `-m hardware` 才运行，但实机测试需要单独现场范围，不能作为生成 skill 的自动动作。

## 现场验收

在现场授权下，按 hardware reference 完成装置身份/总线单 owner/支撑、gripper 宽度、安装几何、当前标定和已知点验证、masked fresh map、低速运动及接触反馈检查。用一个已知尺寸、可夹持的安全物体做完整 grasp/place/空爪/park 流程，保存本次源码与 profile/SDK 标识、图像、trace、verdict、最终持物和停放证据。不同物体/材质/负载需对应验证，不外推成通用成功率。

`check` 的成功字段叫 `local_configuration_ok`，`runtime_readiness` 始终是 `unverified`。它能够拒绝 missing dependencies、模型、错误类型、未接受/错绑定标定、关键 safety 配置退化、源码漂移；无法确认 CAN ownership、真实 pose、串口设备是否接对、地图 freshness 或摄像头支架是否移动。这些由现场与运行时判定。

维护：新运行时改变核心工具/安全接口时，对照 `source-manifest.json` 重审上述约束、更新 file hashes 与 source commit，再重跑结构、脚本与对应回归/现场检查。不能把改 manifest 当作解决 safety refusal 的办法。
