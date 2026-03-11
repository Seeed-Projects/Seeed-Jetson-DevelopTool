---
name: yolov5-object-detection
description: Use for Seeed Jetson topic "Getting started with Yolov5 and roboflow". Includes local references and execution-safe workflow with prerequisites, commands, and validation checks.
---

# Getting started with Yolov5 and roboflow

## Execution model
1. Confirm board model and JetPack/L4T version before applying commands.
2. Read `references/source.body.md` first to extract prerequisites and command order.
3. Execute steps in smallest reproducible sequence and record command outputs.
4. Validate final expected results and keep rollback notes.

## Source
- Original markdown: `/home/darklee/tmp/jetson-develop/refer-参考完后会清除/Application/Computer_Vision/YOLOv5-Object-Detection-Jetson.md`
- Scope: `application` (Computer_Vision)

## Topic summary
[YOLO](https://docs.ultralytics.com) is one of the most famous object detection algorithms available. It only needs **few samples for training**, while providing **faster training times** and **high accuracy**. We will demonstrate these features one-by-one in 

## Key sections
- Introduction
- What is YOLOv5?
- What is few-shot object detection?
- Hardware supported
- Prerequisites
- Getting started
- Collect dataset or use publically available dataset
- Annotate dataset using Roboflow
- Train on local PC or cloud
- Inference on Jetson device

## Reference files
- `references/source.md`
- `references/source.body.md`

## Agent instruction
- Do not skip prerequisite checks.
- If command output differs from expected behavior, pause and ask user before destructive steps.
- Prefer reversible changes and include verification commands.
