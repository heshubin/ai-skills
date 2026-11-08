---
name: zpl-label-layout
description: 设计或排查 WMS ZPL 标签（Load Truck Seal / Ship Out Pallet / Manifest 等）尺寸、截断、旋转时使用。触发词：ZPL, ^PW, ^LL, 标签截断, 打印不全, ZQ520, ^FWR, 竖版标签, Labelary
---

# ZPL 标签排版经验（Bug#10817，2026-11）

## 现场纸张
- NJ 仓 002 Load Truck 用 Zebra ZQ520，标签纸 4 × 3 英寸横向，203 dpi = **799 × 599 点**（`^PW799^LL599`）。
- 按 4 × 6（`^PW812^LL1218`）排版时，y ≥ 600 的字段会被直接截掉，现象是「打到某一行就没了」。先核对 `^LL` 和纸长。

## 竖版（旋转 90°）排版
- 纸的走纸方向改不了，竖版只能用 `^FWR`（或每个字段 `^A0R` / `^BCR`）。读者视角是 599 宽 × 799 高。
- R 方向下 `^FO x,y` 是字段块在物理坐标里的左上角：读者视角越靠上，x 越大。公式：`x = 799 - v0 - 块高`，`y = u0`。
- `^FB w,n` 在 R 方向下块高 = n × 字高，**第一行贴在块的最大 x 一侧**。多行块要按 n 行留高度，否则会压到下一个字段。

## Code128 B 子集宽度
- `>:` 强制 B 子集，模块数 = 11 × (字符数 + 2) + 13；乘 `^BY` 的窄条宽即点数。18 位 × BY3 = 699 点，13 位 × BY3 = 534 点。

## 验证
- 只用假数据 POST 到 `https://api.labelary.com/v1/printers/8dpmm/labels/4x3/0/`（PowerShell 先设 `$ProgressPreference='SilentlyContinue'`，偶发超时重试即可）。
- 单测里解析每个字段的 `^FO/^FT`、`^A0`、`^BC`、`^GB`、`^FB`，断言占用范围不超出 `^PW/^LL`（见 wms-cloud-service `ZoneTruckLabelBuilderTest.outOfBoundFields`）。
