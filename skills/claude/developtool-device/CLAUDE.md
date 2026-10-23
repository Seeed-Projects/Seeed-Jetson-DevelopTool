---
name: developtool-device
description: Use Seeed Jetson DevelopTool's configured SSH target, camera preview, network-sharing panel and device/robot readings without rediscovering credentials or searching all skills.
---

# DevelopTool device tasks

The current task context supplies an absolute command prefix ending in
`bridge_client.py --runtime <private manifest>`. Run it on the **PC**; the `ssh`
subcommand executes its argument on the **bound Jetson**. Use that exact prefix,
including its Python executable. Never read or print the private manifest or
application configuration: the helper already handles authentication.

## Direct routes

1. Run `status`; run `connect` if disconnected. Both use the target already
   configured in Remote Dev. `connect` verifies authentication before switching
   the application's active runner. No configured host: ask the user to configure
   Remote Dev. An expired/changed runtime: use the new context; do not retry the
   old target. Auto-execute must be enabled for connect and arbitrary SSH commands.
2. Execute `ssh --command 'hostname; cat /etc/nv_tegra_release' --timeout 30` for
   device facts. Existing SSH authentication, port and sudo setup are reused.
   Quote the remote command as one argument; never put passwords in commands.
3. For networking, use `network` to open the existing sharing panel. The user
   selects interfaces and provides host sudo credentials there. Opening it is
   not sharing success. Verify gateway, public IP, DNS and HTTPS over SSH after
   configuration. Preserve the existing wired SSH address and original network
   profile. The matched `jetson-pc-wired-share` skill describes Linux NM behavior.
4. For cameras, enumerate `/dev/video*` and reuse the installed capture stack.
   `camera start --source /dev/video0` opens the native preview. Sources also
   support RTSP URLs, numeric indexes and an already verified GStreamer pipeline
   ending in appsink. `camera stop` stops the preview. Device python3/cv2 is
   required; report a missing dependency instead of repeatedly guessing sources.
   Do not take a camera away from a robot controller; reuse its existing stream.
5. `monitor start` starts measured CPU, memory, disk, temperature and device
   readings. `monitor stop` stops polling. This does not move hardware.
6. Publish observations with `publish --source arm --json '{"joint_1_deg":12.5}'`.
   Replace the illustrative value with a real measurement. Use scalar values
   and units in field names. Publish after fresh observations; timestamps in
   the panel identify sample age. Never claim a one-time sample is live polling.

## Robot arms and sensors

Read-only arm tasks identify the actual model, port, driver and existing owner
first. Prefer the running controller's state endpoint or ROS topic; do not
launch a second serial/CAN owner or run calibration/motion as a detection step.
Use the pre-matched hardware skill for the actual device:

- SO-ARM101: `soarm-control`; use its existing status reader and verified
  configuration. Local script paths belong to the PC unless the skill is
  actually installed on the Jetson. For environment setup only, the bundled
  `lerobot-env-setup` guide is available.
- reBot B601: `rebot-arm-grasp`; use its existing CASCADE MCP session and
  `world_state`/observations. Motion goes through its supported MCP controller,
  never an arbitrary SSH command that bypasses its safety layer.
- If a named skill exists only on the Jetson, check exactly
  `~/.agents/skills/<name>/SKILL.md`, `~/.codex/skills/<name>/SKILL.md`,
  `~/.claude/skills/<name>/SKILL.md`, and
  `~/.openclaw/workspace/skills/<name>/SKILL.md`. Do not scan the entire filesystem.

Publish actual joints, gripper, stop state and sensor values with their source
and units. Unsupported values stay unknown. A read request does not authorize
motion. For control, follow the user's specified target and the model's verified
calibration and limits; no target means ask for it, not a default home/demo.
Keep a loaded arm's controller alive. Observe and report execution results using
the matching hardware skill's evidence requirements.

Visual commands return `queued`, which proves delivery only. Check actual frames,
readings and controller results before claiming success. Runtime helpers expire
when DevelopTool closes. Do not copy manifests or tokens into persistent skills.
