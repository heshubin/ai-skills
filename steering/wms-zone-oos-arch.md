---
inclusion: auto
name: wms-zone-oos-arch
description: 处理 Zone Picking 与 OOS（缺货）交互、预建未领取 Task、Scan Tote 报 Allocated Qty Less Than 时使用。触发词：OOS, 缺货, outOfStock, Zone 拆分, 预建任务, status=0, 未领取, Allocated Qty Less Than, 99998, updateAllItemSkip, ZonePickingOosHandler
---
# WMS Zone Picking × OOS 架构约束

## 背景

2026-09-26/27：002 仓 PW 拣货在 Picking App Scan Tote 频繁报 Business Exception（24 小时内 9 起，全部靠 IT 手工改数据放行）。
后端真实异常是 `LocationService.dealItemTransaction` 抛出的 `Allocated Qty Less Than N,Can Not Picking!`，
`OrderPickService.adjustLocation` 再把它包装成 `Error OrderPick Adjust Location!`（99998）。

---

## 核心认知：Zone 拆分会预建「未领取」任务

- `ZoneSplitServiceImpl` 拆批时，一次性为所有 Zone 建 Task（`status=0` 待领取），并一次性插入全部 `wh_picking_order_item`
- 先领取的一方触发拆分，另一侧 Task 一直停在 `status=0`，直到被领取才变成 1
  - PW 批次从 9/23 起常见 Zone2（nj.outbound 走 Print 页）先领，Zone1 PW Task 平均要等 10~14 小时，最长 48 小时
- 订单池状态在任一侧领取时就变成 `5 PICKING`

## OOS 的两道保护，都覆盖不到 status=0 的预建任务

`PickingOosService.outOfStock → removeOrder4OutOfStock`：

| 保护 | 条件 | 预建任务 |
|---|---|---|
| 标记 skip：`updateAllItemSkip` | `task.status = 1` | ❌ 不覆盖 |
| 踢单 + 取消预占：`queryOrderForBatch` | `pool.status = 0` | ❌ 此时已是 5 |
| `orderId=-1` 库位释放 | 按库位+SKU 把 allocated 清零 | ⚠️ 连它们的预占一起清 |

结果：明细 `skip_flag=0` 仍然可拣，但库位 allocated 已被清零。领取后一扫 Tote 就报 `Allocated Qty Less Than`。

拣货端两道兜底也接不住：
- `getPickingIndex` 按 `wh_storage_location_item.flag==1` 自动 skip：盘点完成后 flag 会复位成 0，而预建任务往往在那之后才被领取
- `getPickingIndex` 里按 allocated 自动 skip 的代码被注释了

## 排查规律

- 看到 Scan Tote 报 Business Exception，先查该明细所在 Task 的「拆分时间（task.in_dtm）」和「领取时间（wh_batch_zone.edit_dtm）」之间，
  该库位+SKU 有没有 `wh_preoccupancy_log.order_id=-1, action=2` 的释放记录。有，就是本类问题
- 对账方法：OOS 那一刻 `-1` 释放的 qty，等于 OOS 拣货员自己的数量 + 所有预建任务明细的数量
- Kibana 检索 trace 时要用 `"traceId,spanId"` 整体作短语（例 `"faa511ae...,187cb8ce..."`），只搜 traceId 会 0 命中

## 现场临时处理

- IT 手工改 `skip_flag=3` = 替系统补做 `updateAllItemSkip`。改完拣货员需要重新登录，App 才会重新加载明细
- 手工给库位 `allocated_qty +1` 只在库位实物确实有货时才成立，而且会造出一条没有 preoccupancy_log 对应的预占

## 风险 SQL：领取前就能找出会爆的明细

```sql
SELECT t.rec_id task_id, i.order_no, i.location_no, i.item_number,
       FROM_UNIXTIME(t.in_dtm) split_utc
FROM yamibuy_wh.wh_picking_task t
JOIN yamibuy_wh.wh_batch_zone bz ON bz.picking_task_id = t.rec_id
JOIN yamibuy_wh.wh_picking_order_item i ON i.picking_task_id = t.rec_id AND i.warehouse_number = t.warehouse_number
WHERE t.warehouse_number = '002' AND t.status IN (0, 1)
  AND i.skip_flag = 0 AND i.picking_quantity = 0
  AND EXISTS (SELECT 1 FROM yamibuy_wh.wh_preoccupancy_log p
              WHERE p.warehouse_number = '002' AND p.order_id = -1 AND p.action = 2
                AND p.location_no = i.location_no AND p.item_number = i.item_number
                AND p.in_dtm > t.in_dtm
                AND p.in_dtm < IF(t.status = 0, UNIX_TIMESTAMP(), bz.edit_dtm));
```

## 订单在 OOS 时刻的四种状态（第 4 种是 Zone Picking 新增）

| 订单所处阶段 | wh_order_pool.status | 拣货 Task | OOS 的处理 |
|---|---|---|---|
| 只预占，未进 batch | 0 | 无 | 取消预占 ✅ |
| 进 batch，未生成 task（生成 batch 不改 pool 状态） | 0 | 无 | 踢单 + 取消预占 ✅ |
| task 已被本 Zone 领取 | 5 | status=1 | 改 skip_flag ✅ |
| **另一个 Zone 先领取，连带生成了本 Zone 的 task 和明细，但本 Zone 还没领** | 5 | status=0 | **都不命中，只被 -1 清掉预占** ❌ |

- Zone2 Print（`Zone2PrintServiceImpl.claimAndPrint`）领取后，只把 **Zone2 task 里的订单** 异步置 `pool.status=5`
- Zone2 Print 页上 Pending = batch 未拆分（点 Claim & Print 会同时建出 Zone1 主任务，status=0）；Ready = 已被 Zone1 扫车拆分过
- App 的 `scan-tote.tsx` 在 body 为空时显示 `enError`。99998 的 enError 固定是 "Business Exception"，真实原因在 `messageParameter` 里，App 不显示

## 修复方案：updateAllItemSkip 覆盖未领取 Task（2026-09-27）

- `OrderPickMapper.xml` `updateAllItemSkip`：`task.status = 1` → `task.status IN #{task_statuses}`，取值 `Constant.OOS_SKIP_TASK_STATUSES`（`ZoneTaskClaimStatus.UNCLAIMED` + `PICKING`），SQL 不写字面量
- 4 个调用方同步传参：`PickingOosService.outOfStock`（拣货、补单两处）、`outOfStock4SingleOrderOverSize`、`ExpireDtmService.outOfStock`
- status=0 只会出现在 Zone 拆分预建的 Task 上（旧流程 `createPickingTask` 直接建 status=1），所以改动只多覆盖第 4 种状态
- 踢单逻辑不用改，数据依据：
  - 跨 Zone batch 里每个订单在两侧 Task 都有 `wh_picking_order`（9/1 起 2,252 个 batch、24,940 单无例外），任一侧领取就把全部订单置 `pool=5`，`queryOrderForBatch`（pool=0）命中不到
  - 拆分只在领取时发生（9/10 起 7,663 个 batch，首次领取都在建 Task 后 10 分钟内），不存在「两侧都未领取」的窗口，`ZonePickingOosHandler` 的三步清理分支实际走不到
- 修复后：OOS 时预建 Task 里该库位该商品的明细直接是 `skip_flag=1`，领取时 App 加载即跳过，不需要 IT 改数据、也不用重新登录
- 唯一行为差异：OOS 之后库位即使又有货，预建 Task 里的明细也按跳过处理，和已领取 Task 的现有行为一致（9/10 起 66 条暴露明细中有 5 条领取时 allocated 已回升、拣成功了，回升原因未逐条核实）
