---
name: wms-batch-priority-guide
description: 分析或修改 WMS Batch 优先级（wh_batch.batch_priority）、解释生产里几百万的优先级值、设计 Zone / Group 选批排序、处理 Central 手动提权时使用。触发词：batch_priority, Batch 优先级, 提权, promote, resetBatchPriority, updateBatchPriority, 选批排序, EXSD 梯度, Zone 优先级, Group 优先级
---
# WMS Batch 优先级速查

结论来自 OP-40026 二期调研（2026-10-28，代码 master@879ebc2 + 生产只读库）。完整证据与二期方案：`d:\code\kiroWP\docs\active\OP-40026-zone-picking-phase2\priority-analysis.md`。

## 一个字段，三层来源（wms-cloud-service）

1. **系统自动（Batch Picking / PW）**：`BatchService.resetBatchPriority:792`，`N*100 + (int)(x/y*100)`，`Math.max(新值, 原值)` 只升不降。
   - 只重算 `status=1` 的 Batch；`generate` 本轮建出 Batch 才会调用（`:208`）。
   - N = Batch 最早 EXSD（UTC 整点）在「未组批订单 + status=1 Batch 订单」EXSD 去重倒序列表中的位置，是动态排名。N=1 的占比必为 100%，所以 200 最常见。
   - 生成时 BP/PW/Oversize 一律先写 0（各 Generator），由 reset 填值。
2. **订单优先级（Oversize 单件单、生鲜）**：`OrderSortHandler.getBatchOrderPriority`，`100000 − 距 EXSD 小时数×100`，生鲜 9,999,999；组批 job 同时投递的 `updateUnpickBatchPriority` 只刷新非 BP/PW 的 Batch。
3. **Central 手动**（central-wh-web `orderRecordController.js`）：「↑」= `min(1,000,000 + MAX(batch_priority WHERE status=1 AND 仓), 99,999,999)`；直接改数 = `min(输入, 99,999,999)`，输入框失焦即提交。

## 读数规律

- ≥1,000,000 基本都是「↑」阶梯：值 = k×1,000,000 + 点击时全仓最大值的尾数。尾数 `096x00` 来自待拣 Oversize 单件单（EXSD 剩 30–36 小时），`000200`/`000366` 来自自动值，`x00200` 来自手输。尾数没有业务含义。
- 99,999,999 = 手输「紧急置顶」，或已有 99,999,999 待拣时点 ↑ 被封顶。
- 002 仓 2026 年 8–10 月每周 13%–33% 的 Batch 被 ↑，约 30% 的 Batch 由 Central 手动建；自动值只有几百（可确认的 N 最大约 8）。
- 识别手输小数值：占比只能是 `⌊x/y×100⌋` 的离散值（y=12 时只有 8、16、25…100；y=50 时只有偶数），对不上的就是 Central 手输（如 601、801、999、1,499）。
- 任一 Zone 领取后 Batch 变 status=2，优先级冻结，不再重算，也不计入 ↑ 的基数。

## 选批排序的坑

- `queryBatchInfo` 只 `ORDER BY batch_priority DESC`，没有次排序（执行计划 filesort），而生产里同值非常普遍。
- 跨 Zone 批 `selectByZoneIdAndStatus` 多一个 `bz.rec_id ASC`；`selectHighestPriorityBatch` 同值时跨 Zone 赢（`>=`）。
- `BatchService.get` 不按车尺寸过滤（`boxSize` 没进查询条件）。
- 不要把新的加权直接加在现有 `batch_priority` 上：`ZoneQTY×10`、尺寸位会打乱 x/y 与梯度顺序；`+100000` 对 ↑ 过的 Batch 无效。二期推荐做分层排序：`层级×10^10 + batch_priority×100 + ZoneQTY×10 + 尺寸位`，实时派生，不改写路径。

## 二期（OP-40026）已定算法 v1

2026-10-28 确认按推荐口径实现，后续可能再调。权威记录：`d:\code\kiroWP\docs\active\OP-40026-zone-picking-phase2\requirement-decisions.md` §J。

- 只在二期开关仓改选批读路径，`batch_priority` 写路径全部不变；001/101 与关开关沿用一期 SQL。
- `zone_sort_value = tier×10^10 + batch_priority×100 + zone_qty×10 + size_digit`；tier：2 = 99,999,999 紧急置顶，1 = 对方 Zone 已领取，0 = 其他；size_digit：XL 9、L 3、S/PW 0；同值 `batch_id` 升序。
- Group 取成员 Zone 2 侧最大值；「↑」基数改为所有仍有待领 Zone 任务的 Batch，无候选时按 0（同时修空指针）。
- 改算法只改公共 SQL 片段 + Java 计算方法两处，并在 §J9 追加版本记录。

## 验证「Multi Zone > Single Zone」时的坑（Bug#10881，11/09）

- 跨 Zone 加权（`zone_qty×10`）只在排序值里，不写 `batch_priority`；Central 只显示原值，同为 700 的跨 Zone 与单 Zone 行看不出先后。验证要看 Zone 1 车领到哪张 Batch，不看原值。
- `zone_qty` 排在「梯度 + 占比」之后（D4）：同一最早 EXSD、占比不同（跨 Zone 2/3 = 666 对单 Zone 3/3 = 700）时单 Zone 在前；N 是动态排名、只升不降，同 EXSD 不同轮次建的 Batch 也可能差 100，都会盖过 b。
- gqc 有测试直接改库的 `wh_batch.status = 0`（不是合法 BatchStatus），这类 Batch 不进任何候选；gqc 池里有 2022 年 EXSD 的订单，N 被撑到 140 左右，不代表生产。
