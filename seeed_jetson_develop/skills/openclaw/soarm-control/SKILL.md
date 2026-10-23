---
name: soarm-control
description: Read or control an already configured SO-ARM101 on DevelopTool's selected Jetson through its existing LeRobot/controller setup, and publish actual readings to the host data panel.
---

# SO-ARM101 with DevelopTool

Use this skill only after identifying the actual arm as SO-ARM101. reBot/CAN
arms use their own skill and controller. The task context provides the
DevelopTool bridge command prefix; `ssh --command ...` executes on the selected
Jetson with the application's saved authentication. Do not run a hardware
command on the PC by mistake.

## Reuse configured hardware

1. Identify serial devices using `ls -l /dev/serial/by-id /dev/ttyACM*
   /dev/ttyUSB* 2>/dev/null` and inspect the known running controller/configuration.
   Prefer its existing state API or ROS topic; don't start a second serial owner.
2. Check only the exact remote skill paths:
   `~/.agents/skills/soarm-control/SKILL.md`,
   `~/.codex/skills/soarm-control/SKILL.md`,
   `~/.claude/skills/soarm-control/SKILL.md`,
   `~/.openclaw/workspace/skills/soarm-control/SKILL.md`.
   If a hardware-specific skill is installed there, read its actual scripts and
   configuration before using them. A skill file on the PC does not establish
   that its script paths or Conda environment exist on the Jetson.
3. Reuse the configured LeRobot environment, arm ID, port and calibration.
   If setup is missing, use the matched `lerobot-env-setup` guide. Do not blindly
   install dependencies into the system Python or replace a working environment.

## Read-only task

Use the current controller's observation endpoint. A deployed skill may supply
`scripts/soarm_status.py`; inspect the actual implementation and CLI first. Do
not assume connecting/disconnecting its motor bus is a read-only operation:
some wrappers change torque state on connect/disconnect. If no read-only state
endpoint exists, report that limitation instead of creating a competing owner.

Publish measured joint positions, gripper and state with the bridge:
`publish --source soarm --json '{"shoulder_pan_deg":<actual measurement>}'`.
Use the units and normalization of the actual controller; a LeRobot normalized
position is not automatically degrees. Missing values are unknown, not zero.
Update after fresh observations and let the panel show sample times.

Reading status does not authorize motion, calibration, opening the gripper,
changing torque or disabling the arm.

## Requested movement

- Obtain the user's target action/pose when absent. Do not run a home pose or
  movement demo merely because the control preset was selected.
- Verify calibration belongs to this arm ID and physical installation. Reuse
  the configured workspace, joint limits and speed limits. Do not copy reference
  calibration or angles from another arm.
- Use the existing controller's supported motion API. Where the actual deployed
  skill exposes `pinocchio_xyz_drive.py` or `soarm_set_joints.py`, inspect its
  units/options, prerequisites and bus ownership first. For Cartesian motion,
  confirm the base frame, meters versus other units and IK configuration.
- Start with a bounded low-speed action within verified limits. Preserve the
  active connection/torque when holding a load; do not call disable/disconnect
  as automatic cleanup. Follow the current hardware's actual stop procedure.
- Read actual post-action observations, publish them and report what was
  measured. Command acceptance does not prove the arm reached the target.

This bundled routing guide does not install a hardware driver, calibrate an arm
or supply a universal motion API. Unsupported controllers need their verified
hardware integration before commands can be executed.
