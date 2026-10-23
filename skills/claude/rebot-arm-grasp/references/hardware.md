# reBot B601 RobStride 现场准备

只在接入实机时加载本文件。现场约束是本 skill 的适用条件，静态 checker 不能证明设备实际上符合这些条件。

## 身份、机械与总线

- 确认 B601 使用 RobStride RS 电机，而不是 DM 版；profile `type: rebot_rs`、6 个关节、真实夹爪。URDF 的 `joint_signs: [-1,-1,-1,-1,-1,-1]` 是资产约定，不能当作 CAN feedback sign 随意改。
- 确认连接前手臂有机械支撑/处于正确 rest；`connect()` 清除 fault 的 stop frame 会暂时切断扭矩，不要通过重连救起悬空负载。
- 检查实际夹爪行程、开口宽度、stall/reference、腕部相机支架和附属几何。参考 RS 行程 closed=0、open≈6.2 rad、最大宽度≈0.09 m，仅在该配置中测得；角度到宽度仍要在本机核验。软/易碎物体使用相应 material，不随意加大增益或 squeeze。
- Linux 检查 `ip -details link show can0`；预期 1 Mbps。只有用户要求接入且确认正确接口后才配置 `ip link`，不要自动重置一个正在承载其他设备的 CAN 总线。
- CAN 的 SDK、MotorBridge Studio/gateway、LeRobot 或其他 agent 只能有一个 owner。`scripts/diag_rebot_mb.py` 默认只读也会打开总线；必须先核实 ownership。带 jog/hold 或 `home_rebot_rs.py` 是运动，不当作静态检查。

`rebot_rs_mb` 的部分 wire signs、伸展负载和 MIT gains 尚未完成同等验证，且 profile contact monitor 是 measure。本包硬件启动器拒绝它；不能为了避开 SDK/地图要求悄悄换此 profile。

## 相机与标定

主摄像头必须看见抓取工作区，提供真实 RGB-D，并绑定确定的设备 serial。多相机列表第一项是 manipulation camera；非主 camera 的 detector 覆盖不生效，3D fusion 要各自的 extrinsics。

`d455f_scene` 中的 serial 和 hand-eye JSON 是原参考台面数据。即使数值质量 gate 通过，相机/底座/支架位置变化也使它失效。新现场创建 camera profile，绑定本机 serial，使用本机记录，并按仓库 `docs/HANDEYE_CALIBRATION.md` 的独立已知点验证。不要复制旧 T、换 serial 文字或把 `acceptable` 改为 true。

标定 CLI 的 `--dry-run` 是离线；普通 ArUco/markerless sweep 会移动机械臂，需要相应授权和现场 supervision。这里不把标定自动纳入普通抓取任务。eye-in-hand 使用随捕获时刻的 `T_cam2gripper` 和测量关节，不能以固定 world transform 代替。static checker 使用 runtime 自己的 `load_hand_eye` gate，并核对 mode、camera、serial、arm、ee_frame；还要由现场证据确认安装位置和有效性。

## 实时安全与 sidecars

现有 `rebot_rs` 强制：fresh observed occupancy、URDF mesh body mask（含实际腕部相机 attachment）、tool volume、wrist camera 朝上限制、motor feedback contact monitor enforce。模型 mesh 必须是真文件，不能是 Git LFS 指针。新安装几何不同需要测量并修改 profile attachment，不能删掉它。

占用图使用仓库的独立 bridge，先按 `docs/NVBLOX.md` 准备。已准备环境可在另一个终端运行：

```bash
"$REPO/.venv/bin/python" "$REPO/scripts/serve_occupancy_bridge.py" \
  --port 5557 --voxel-size 0.01 --backend auto
```

端口与实际 runtime 的 `CASCADE_OCCUPANCY_PORT` 保持一致。不启动/清空/重启其他 session 共享的 map；freshness 与正确 robot masking 比端口 up 更重要。LazyArm standby 没有关节状态时地图可能不能 ready；首个合法运动的 runtime admission 会等待 masked refresh，超时就拒绝，不通过绕过检查唤醒。

GraspGen-X 是独立模型 server，不在 skill 内复制模型。按 `scripts/install_graspgenx.sh`、`scripts/serve_graspgenx.sh` 和相关 runtime guide 准备，保留 profile 的真实 RS swept gripper geometry。本地 CUDA/远程 server、CPU analytic OBB 要报告实际 backend；stub 仅测协议，不算 learned inference。可选 profile 的 OBB fallback 不提供模型成功证据；required 模型路径必须真实推理就绪，不降级。Spark presenter 的 CUDA/模型验收要求留在其专用 guide，不假定每个 reBot 都需要 Spark。

检查 `world_state` 的地图状态、stop、holding 和异常；current 图像确认 target 与 destination、台面高度和净空。默认 workspace 内也未必满足 top-down IK，`preview_grasp` 不是授权扩大 reach。新的 workspace/gain/profile 是需要重新验证的工程更改。
