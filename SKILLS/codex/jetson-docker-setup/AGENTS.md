---
name: jetson-docker-setup
description: Use for Seeed Jetson topic "Getting Started with Docker". Includes local references and execution-safe workflow with prerequisites, commands, and validation checks.
---

# Getting Started with Docker

## Execution model
1. Confirm board model and JetPack/L4T version before applying commands.
2. Read `references/source.body.md` first to extract prerequisites and command order.
3. Execute steps in smallest reproducible sequence and record command outputs.
4. Validate final expected results and keep rollback notes.

## Source
- Original markdown: `/home/darklee/tmp/jetson-develop/refer-参考完后会清除/Application/Developer_Tools/jetson-docker-getting-started.md`
- Scope: `application` (Developer_Tools)

## Topic summary
> This is a repost of the [blog](https://collabnix.com/getting-started-with-docker-on-seeed-studios-recomputer-powered-by-nvidia-jetson) written by [Ajeet](https://collabnix.com/author/ajeetraina) on [collabnix.com](https://collabnix.com). All credits goes to 

## Key sections
- What’s unique about reComputer J1020?
- Few Notable Features includes
- Components of reComputer
- Hardware Setup
- Running CUDA deviceQuery
- Running Docker on reComputer Jetson Nano
- Installing Docker Compose
- Install the latest version of CUDA toolkit
- Verify Docker runtime
- Running Your first Python Container

## Reference files
- `references/source.md`
- `references/source.body.md`

## Agent instruction
- Do not skip prerequisite checks.
- If command output differs from expected behavior, pause and ask user before destructive steps.
- Prefer reversible changes and include verification commands.
