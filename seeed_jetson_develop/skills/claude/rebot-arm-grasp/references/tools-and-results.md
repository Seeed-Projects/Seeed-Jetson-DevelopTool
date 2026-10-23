# MCP 调用与结果

运行中 `tools/list` 是参数与可用能力的权威。下列示例绑定本包 source manifest 中的 arm runtime，MCP 名称可能带 server prefix。不要把脚本中的内部 Python 参数传到工具。

| 任务 | Tool / arguments | 注意 |
|---|---|---|
| 运行状态 | `world_state {}` | `backends`、`tracked_holding`、`gripper_contents`、`stopped`、capability/withheld；缓存状态不测量实机 |
| 当前视觉 | `get_observation {}` 或 `describe_scene {}` | 新图像和 freshness；未识别不等于不存在 |
| 指定相机 | `camera_snapshot {"camera":"exact_name"}` | camera 是 rig name，不是任意 device path |
| 定位目标 | `localize_object {"label":"red cube","spatial_hint":"left"}` | hint 枚举 left/right/front/back/near/far；position/extent_m 为米 |
| 候选预览 | `preview_grasp {"label":"red cube","spatial_hint":"left"}` | 无运动，仅候选；不缓存为下一次已通过的安全计划 |
| 抓住保持 | `grasp_object {"label":"red cube","material":"rigid"}` | material 可省略；不要擅自放下 |
| 抓取搬放 | `pick_and_place {"object":"red cube","destination":"drop zone","material":"rigid"}` | 参数是 object，不是 label；含内部重试与 home |
| 放到对象 | `place_on_object {"label":"bowl"}` | 实际支撑/容器需本次定位，不杜撰 place_in 工具 |
| 放到坐标 | `place_at {"x":0.30,"y":-0.20}` | 此坐标仅示例，实机必须现场测得；z 缺省是 table 上方 release |
| 历史核验 | `verify_last_action {}` | recent/contradictions 是历史 verdict，无新测量 |
| 多步记忆 | `task_memory {}` | 历史前后图像、action/verdict 与 fresh current view |
| 优先停机 | `emergency_stop {}` | soft stop + latch，保持扭矩；不是硬切电 |
| 就绪位 | `move_home {}` | 抬起 home_q，保持电机，不能代替 shutdown park |
| 支撑停放 | `move_to_rest {}` | 空爪且无 pending 故障时，测量 park_q 后释放扭矩 |

material 枚举：`rigid`, `fragile`, `soft`, `deformable`, `slippery`, `heavy`。不把中文枚举传入，也不将未知重量当作已验证 payload capacity。

多臂 schema 若保留 `arm`，值必须取自 `list_arms`，只传给实际支持的 motion tool。单臂服务会移除该属性，本包 helper 只启动单臂。

## 解码和判定

MCP `tools/call` 返回 content：其中可能有 image 和多个 text 块。查看 JSON text 中业务结果，不能只判断 JSON-RPC response 没有 error。

- MCP `isError: true` 或业务 `ok: false`：失败，即使日志显示此前某阶段执行了。检查是否物体仍被握持；不自动重复完整 pick。
- `execution_ok`（若有）：命令执行层结果，与物理 postcondition 分开。
- `postcondition.status: confirmed`：该 skill 的指定后置条件由 channel 中的独立证据确认。它不额外证明每段路径/负载保持或另一动作成功。
- `refuted`：后置条件反驳成功；runtime 可降级 ok。`unverified`：证据缺失、禁用、静态 mock 相机 abstain、遮挡或 verifier 故障。缺少 postcondition 也不能当作 confirmed。
- `return_home` 失败：放置是否确认与回 home 是否完成分别报告；不追加盲目返回。
- `world_state.tracked_holding` 是 session 记录，并不是持物测量；`gripper_contents: not_measured` 和 `live_arm_feedback: false` 明示无新反馈。其他 runtime 界面可能称 holding。不能仅靠此工具确认空爪；需要当前夹爪/视觉 evidence。`localize_object` 对 configured destination 返回配置来源，非视觉确认。

报告示例：

> 已执行红色方块抓取搬放；放置的 postcondition 为 confirmed，channel=physics。返回 home 完成。trace 保存在本次 run_dir。

> 抓取命令已执行，但 postcondition 为 unverified，当前遮挡无法独立确认；保持当前会话与夹爪状态，未追加动作。

物理证据应绑定当前 checkout、process/session、target、capture 与 action；另一 run 的成功录像或经验统计不能证明当前动作。
