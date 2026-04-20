---
name: clawdbot-development
description: Use for Seeed Jetson topic "Develop reComputer Jetson using Clawdbot". Includes local references and execution-safe workflow with prerequisites, commands, and validation checks.
---

# Develop reComputer Jetson using Clawdbot

## Execution model
1. Confirm board model and JetPack/L4T version before applying commands.
2. Read `references/source.body.md` first to extract prerequisites and command order.
3. Execute steps in smallest reproducible sequence and record command outputs.
4. Validate final expected results and keep rollback notes.

## Source
- Original markdown: `/home/darklee/tmp/jetson-develop/refer-参考完后会清除/Application/Developer_Tools/Develop_reComputer_Jetson_using_Clawdbot.md`
- Scope: `application` (Developer_Tools)

## Topic summary
Traditionally, developing on a Jetson edge device required a physical setup with a monitor, keyboard, and mouse. Even with remote SSH access, developers still depended on terminal-based workflows and additional tools for monitoring and deployment. With Clawdbo

## Key sections
- Introduction
- Prerequisites
- Hardware Connection
- Getting Started
- Effect Demonstration
- Tech Support & Product Discussion

## Reference files
- `references/source.md`
- `references/source.body.md`

## Agent instruction
- Do not skip prerequisite checks.
- If command output differs from expected behavior, pause and ask user before destructive steps.
- Prefer reversible changes and include verification commands.
