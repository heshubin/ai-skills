---
name: kiro-cli-unattended-run
description: 用 kiro-cli 无人值守、按组串行执行 spec tasks（夜间跑代码生成）时使用，含已验证的命令参数、PowerShell 5.1 注意事项与串行链的停止条件。触发词：kiro-cli, 无人值守, 夜间执行, 自动执行 tasks, no-interactive, 串行执行, 睡觉前跑, spec run
---
# kiro-cli 无人值守串行执行 tasks

## 已验证（kiro-cli 2.36.0，Windows PowerShell 5.1，2026-10-31）

- `kiro-cli chat --v3 --no-interactive --trust-all-tools --trust-workspace --model <模型> "<prompt>"` 跑完自动退出，返回码 0。
- 标准输出只有模型的回复，不回显 prompt；stderr 有 `[INFO]` 启动日志，PowerShell 5.1 会把它显示成 NativeCommandError，可以忽略。
- 先执行 `[Console]::OutputEncoding = [Text.Encoding]::UTF8`，否则中文输出乱码。
- 加 `--trust-workspace` 后，cwd 仓库 `.kiro/steering/` 下的规则会加载（在 wms-cloud-service 实测问答确认）。不加时，未信任的工作区不加载 steering、hook、MCP。

## 串行链的写法要点

- 一组任务一个 `kiro-cli` 进程，用 `foreach` 串起来，每组都是新会话，上下文不累积；进度靠 tasks.md 勾选与 git 提交保存。
- 让模型最后一行输出结果标记（如 `OVERNIGHT_RESULT=DONE` / `BLOCKED`），用 `Tee-Object` 存日志，再用 `Select-String` 取最后一个标记判断是否继续。prompt 里不要写出完整的标记字面量，改成「OVERNIGHT_RESULT 加等号加 DONE」这类说法，免得误匹配。
- 每组开始前检查 `git status --porcelain`，有未提交改动就停：上一组卡住时，下一组不能在脏工作区上开工。
- prompt 里不要用英文双引号：PowerShell 5.1 给原生程序传含双引号的参数会被拆坏，用「」代替。
- 不要选 `/spec run` 的全部范围：它按依赖图把互不依赖的任务分 wave 并行，同一工作区、同一分支、同一 Maven target 会互相干扰。
- 无人值守时只提交、不推送，第二天检查后再推；开跑前把电脑睡眠设为「从不」。
- 同一份 tasks 同一时间只能有一个会话在执行（IDE 与 CLI 都算）。
