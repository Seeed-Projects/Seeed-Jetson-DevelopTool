# 失败处理与会话寿命

| 现象 | 处理 |
|---|---|
| 安全拒绝 / stale map / body-mask fault | 保持停止/持物；读错误和地图绑定，修复观测来源；不放松限制、删除 mask 或换弱 profile |
| 接触检测 / stall / hard fault | `emergency_stop`（若尚未停止），读状态与 trace；不自动 reset_scene/reset_stop/open/home，由操作员排除碰撞和负载问题 |
| STOP 是本包 fresh startup latch | 在已有实机任务授权和现场准备通过后才 reset；这只清软件 latch，不清硬件故障 |
| missing/withheld tool | 看 capabilities、tools_withheld 和 operator hidden；重取 catalog；先修复其真正前置条件 |
| 目标不存在/混淆 | 取新图像，改为证据支持的 label/hint；不能依靠 remembered belief 或猜坐标继续 |
| 没有可行 grasp / IK | 根据尺寸、方向、workspace 判断；要求现场重新摆放目标；不改 joint_signs 或提高 reach |
| learned backend unavailable | 查看实际 fallback 和 profile required 策略；可选 OBB 要明确报告，required/stub 不冒充真实推理 |
| already holding / 失败发生在 carry/place | 先确认所持对象、pending 状态和原目的地；允许的恢复放置走原生工具，不再次抓取另一物体 |
| MCP timeout/cancel/断开 | 不假定动作没执行；尝试当前控制会话的优先 stop、查看其存活状态与日志；禁止同时另起总线 owner。通信失效时现场操作员使用实际停机通道 |
| 用户要求“然后停止” | 完成指定动作后结束动作序列；失败也不自动 retry、home 或 park，可读取证据并报告 |

`pick_and_place` 已经按配置进行内部 retry，可能持续约 120 秒或 profile 指定预算。超时后盲目重发会产生叠加动作或重复预算。若无 contact/stop/标定/地图/payload 问题，且有明确新依据（例如操作者重新摆正目标），可以在原任务范围内再尝试一次；没有新依据就停止并报告。

`move_to_rest` 验证支撑停放，与 `move_home` 的抬起就绪位不同。实机结束前确认空爪、没有可能持物/接触/释放状态且 park 成功；否则保留原进程，不 EOF、disconnect、kill 或重连。agent 会话中止可能导致 MCP host 收回服务器，软件不能保证进程被杀后的扭矩保持；需要现场操作员监督负载和支撑，不能将“保持夹持”托付给短命子进程。

排错证据：本次 `run_dir/trace.jsonl`、前后 keyframes、MCP `server.log`、启动 stderr、grasp evidence（若启用）、当前 world_state 和 verifier verdict。run_dir 从已配置的 `CASCADE_RUN_DIR` 或启动 stderr 的 `log: .../server.log` 获取；world_state 不提供这个路径。记录安全拒绝原文、发生 stage 与持物状态；不要修改历史 trace 或把失败过滤成成功。
