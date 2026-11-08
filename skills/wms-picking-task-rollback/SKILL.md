---
name: wms-picking-task-rollback
description: 撤销被误领（测试账号领走、领错车、领错 Zone）的 WMS 拣货任务时使用：先判断普通 / 单 Zone / 跨 Zone 三种场景，再按领取时写过的表逐项还原，输出带状态守卫和期望行数的生产脚本。触发词：撤销拣货任务, 领错任务, 误领, 回滚拣货任务, rollBackTask, resetPickTask, wh_picking_task, 释放拣货车, 跨Zone任务撤销, wh_batch_zone, wh_consolidation_task, wh_consolidation_task_detail
---

# 撤销误领的拣货任务

依据：wms-cloud-service `master@ff3742284`（2026-11-06，Zone Picking 一期）的代码，加生产只读数据核对（2026-11-07，任务 1468102 实例）。OP-40026 二期上线后（预建 Task、Group 领取、`first_claim_user`）要按二期代码复核本文。

## 一、原则

- sql-query MCP 连的是生产库，只跑 SELECT。写操作只给脚本，由主人执行。
- 只撤销「领了还没拣」的任务：该任务所有 `wh_picking_order_item` 的 `picking_quantity`、`sorting_pick_quantity`、`replenish_quantity` 都是 0。已经拣出实物的不要撤销，改走续接、OOS 或现场处理。
- 执行前让领取人退出 App 上的任务，否则他继续扫 Tote、扫库位会写回脏数据。
- 整个脚本放在一个事务里。每条语句带状态守卫，并写明期望行数。任何一条行数不对就 ROLLBACK。
- 脚本用会话变量（`@task` 等），必须在同一个 SQL 会话里从头执行到尾。
- MySQL 不允许 UPDATE/DELETE 的子查询直接读同一张表（错误 1093）。需要时先把值取到变量里，或者在子查询外再包一层派生表。
- 不撤销的办法：让真实拣货员扫同一辆车。`OrderPickService.checkTask` 会把他写进 `picking_user2`，任务继续往下走。普通任务和 Zone 任务都适用。

## 二、先判断场景

```sql
SET @wh = '001', @task = 1468102;   -- 改成实际值

SELECT t.rec_id, t.status, t.zone_id, t.task_type, t.parent_task_id,
       t.cart_no, t.picking_user, t.picking_user2,
       b.batch_id, b.status AS batch_status, b.is_cross_zone, b.primary_zone_id, b.type,
       (SELECT COUNT(1) FROM Yamibuy_WH.wh_batch_zone bz WHERE bz.batch_id = b.batch_id) AS bz_rows,
       (SELECT COUNT(DISTINCT po2.picking_task_id) FROM Yamibuy_WH.wh_picking_order po2
         WHERE po2.batch_id = b.batch_id) AS batch_task_cnt
FROM Yamibuy_WH.wh_picking_task t
INNER JOIN Yamibuy_WH.wh_batch b
        ON b.batch_id = (SELECT MAX(po.batch_id) FROM Yamibuy_WH.wh_picking_order po
                          WHERE po.picking_task_id = t.rec_id)
WHERE t.rec_id = @task;
```

| 场景 | 判据 | 撤销方式 |
|---|---|---|
| A 普通 | `is_cross_zone = 0`，`primary_zone_id = 0`，`bz_rows = 0`，`batch_task_cnt = 1` | 删任务和拣货数据（第四节） |
| B 单 Zone | `is_cross_zone = 0`，`primary_zone_id > 0`，`bz_rows = 1` | A 的脚本，再复位 `wh_batch_zone`（第四节末尾） |
| C 跨 Zone | `is_cross_zone = 1`，`bz_rows >= 2`，`batch_task_cnt >= 2` | **不删 Task**，只把它退回「待领取」（第五节） |

C 不能删 Task。原因是拆分时已经建好了其他 Zone 的 Task（`parent_task_id` 指向主 Task）、合单主表（`primary_task_id`）、合单明细（`picking_task_id`）和 `wh_batch_zone.picking_task_id`，它们都引用这个 Task。删掉后这些记录就成了孤儿。

**跨 Zone 禁止调用 `POST /orderPick/rollBackTask`（`resetPickTask`）。** 它按 batch_id 删除整个 batch 的 `wh_picking_order` 和 `wh_picking_order_item`，会把其他 Zone 的数据一起删掉。它也不处理 `wh_batch_zone` 和合单表。

## 三、领取时写了哪些表

| 表 | A/B 扫车领取 | C 领取（Zone1 扫车、Zone2 Print 都走 `claimZoneTask`） | 撤销 |
|---|---|---|---|
| wh_batch | status 1→2（`BatchService.getRemoteBatchOrders`） | 任一 Zone 被领取就 1→2（`updateBatchToInPicking`） | A/B 改回 1；C 只在该 batch 没有其他已领取 Task 时改回 1 |
| wh_picking_task | 领取时新增一行，status=1 | 拆分时预建，status=0、cart_no=''、picking_user=''；领取时 CAS 0→1，写 cart_no、picking_user、edit_dtm | A/B 删除；C 改回 0 并清空 cart_no、picking_user |
| wh_picking_cart | status 1→2，picking_task_id=任务 | 同左（Zone2 Print 会自动在本 Zone 挑一辆空车） | status=1，picking_task_id=NULL |
| wh_picking_order / wh_picking_order_item | 领取时新增 | 拆分时每个订单在每个 Zone 各建 1 行 picking_order（cart_no=''、tote_no=NULL）；领取本身不改 | A/B 删除；C 只清空 tote_no、cart_no |
| wh_batch_zone | B：status=1，picking_task_id=任务 | 本 Zone 行 status 0→1；picking_task_id 在拆分时已写入 | B：status=0、picking_task_id=0；C：status=0，**picking_task_id 保留** |
| wh_consolidation_task_detail | 无 | 本 Task 的明细 status 0→1（PICKING），cart_no=车 | status=0、cart_no=''、tote_no=''、done_dtm=0 |
| wh_consolidation_task | 无 | 领取主 Task（task_type=0）时写 primary_cart_no=车，status 仍为 0 | primary_cart_no='' |
| wh_storage_location（Tote 或 PW 框） | 绑 Tote（App `bindToteNumber`）或 PW 车 `bindToteForCartNo` 时 flag 0→3 | 绑 Tote 时 0→3，并同步写明细 tote_no；Zone2 Print 领取时直接占 Tote 并打印标签 | flag 改回 0 |
| wh_order_pool | 本任务订单 status 0→5 | 同左（Zone2 Print 在事务提交后异步写） | 改回 0；C 只改其他 Zone 也没被领取的订单 |
| wh_order_info | shipping_status 2→3，并通知 SO（`OrderPickRestImpl.createPickingTask`，只对新任务） | 同左 | 改回 2；C 的条件同上 |
| wh_order_process_record | 关闭 Wait 记录（写 end_time、isFinished=1），新增 operation_type=3 记录（operation_ref_id=任务，isFinished=0） | 同左；其他 Zone 已领取时，只新增一条 type=3 记录，不再关 Wait | 删掉本任务的 type=3 记录；如果没有其他 Zone 的 type=3 记录，重新打开 Wait |
| wh_process_log | 无 | 写入 CLAIM_ZONE_TASK 追踪事件 | 保留作审计 |
| yamibuy_master.xysc_order_info | SO 同步 shipping_status=3 | 同左 | 这是 SO 的表，不回滚；重新领取时会再同步一次 |

跨 Zone batch 第一次被领取时会触发拆分（`ZoneSplitServiceImpl.splitAndCreateTasks`），一次建好全部 Zone 的 Task、picking_order/item、每个订单的合单主表（status=0）和两条明细（主、从各一条，status=0），并回写 `wh_batch_zone.picking_task_id`。撤销时保留这些数据。这样 batch 改回 1、所有 Task 都是 0 后，仍然是系统能处理的状态：
- 拉取时 `BatchService.get` 识别为「已拆分」，直接走 `claimZoneTask`。
- Zone2 Print 页面按 `wh_batch_zone.status=0` 且 `picking_task_id != 0` 识别为可领取。
- 如果这个 batch 被打散，`cleanupCrossZoneBatchData` 会删除未领取的 Task、status=0 的合单数据和 `wh_batch_zone`。

## 四、场景 A / B 脚本

```sql
-- 目标库：生产 Yamibuy_WH；同一会话执行
SET @wh = '001', @task = 1468102;
SELECT po.batch_id, t.cart_no INTO @batch, @cart
FROM Yamibuy_WH.wh_picking_task t
INNER JOIN Yamibuy_WH.wh_picking_order po ON po.picking_task_id = t.rec_id
WHERE t.rec_id = @task LIMIT 1;
SELECT MIN(start_time) INTO @claim_dtm FROM Yamibuy_WH.wh_order_process_record
WHERE operation_type = 3 AND operation_ref_id = @task;

-- 前置检查
SELECT @batch, @cart, @claim_dtm;
SELECT COUNT(1) AS item_rows,
       SUM(IFNULL(picking_quantity,0) + IFNULL(sorting_pick_quantity,0) + IFNULL(replenish_quantity,0)) AS picked
FROM Yamibuy_WH.wh_picking_order_item WHERE picking_task_id = @task;          -- picked 必须为 0
SELECT COUNT(1) AS po_rows, SUM(tote_no IS NOT NULL AND tote_no <> '') AS tote_bound
FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task;               -- 记下 po_rows（= 订单数 N）
SELECT COUNT(DISTINCT picking_task_id) FROM Yamibuy_WH.wh_picking_order
WHERE batch_id = @batch;                                                       -- 必须为 1

START TRANSACTION;

-- 1. 释放已绑的 Tote（期望 = tote_bound）；PW 车的 cart_no 本身是框号，一并释放（非 PW 为 0）
UPDATE Yamibuy_WH.wh_storage_location SET flag = 0, edit_dtm = UNIX_TIMESTAMP()
WHERE warehouse_number = @wh AND flag = 3
  AND location_no IN (SELECT tote_no FROM Yamibuy_WH.wh_picking_order
                      WHERE picking_task_id = @task AND tote_no IS NOT NULL AND tote_no <> '');
UPDATE Yamibuy_WH.wh_storage_location SET flag = 0, edit_dtm = UNIX_TIMESTAMP()
WHERE warehouse_number = @wh AND location_no = @cart AND flag = 3;

-- 2. 订单池 5 → 0（期望 N）
UPDATE Yamibuy_WH.wh_order_pool SET status = 0
WHERE warehouse_number = @wh AND status = 5
  AND order_no IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task);

-- 3. 订单 shipping_status 3 → 2（期望 N）
UPDATE Yamibuy_WH.wh_order_info SET shipping_status = 2
WHERE order_status = 1 AND shipping_status = 3 AND pay_status = 2
  AND order_id IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task);

-- 4. 流程记录：重开 Wait（期望 N，领取前没有 Wait 记录的订单不会被改），删 type=3（期望 N）
UPDATE Yamibuy_WH.wh_order_process_record SET end_time = NULL, isFinished = 0
WHERE operation_type = 2 AND memo = 'Wait' AND end_time BETWEEN @claim_dtm - 5 AND @claim_dtm + 5
  AND order_id IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task);
DELETE FROM Yamibuy_WH.wh_order_process_record
WHERE operation_type = 3 AND operation_ref_id = @task AND isFinished = 0;

-- 5. batch 改回可领取（期望 1）
UPDATE Yamibuy_WH.wh_batch SET status = 1 WHERE batch_id = @batch AND status = 2;

-- 6. 释放拣货车（期望 1）
UPDATE Yamibuy_WH.wh_picking_cart SET status = 1, picking_task_id = NULL
WHERE warehouse_number = @wh AND cart_no = @cart AND picking_task_id = @task;

-- 7. 删拣货数据：明细（期望 item_rows）、订单（期望 N）、任务（期望 1）
DELETE FROM Yamibuy_WH.wh_picking_order_item WHERE picking_task_id = @task;
DELETE FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task AND batch_id = @batch;
DELETE FROM Yamibuy_WH.wh_picking_task WHERE rec_id = @task AND status = 1;

-- 场景 B 额外加这一条（期望 1）：Zone 行回到「未创建 Task」
-- UPDATE Yamibuy_WH.wh_batch_zone SET status = 0, picking_task_id = 0, edit_dtm = UNIX_TIMESTAMP()
-- WHERE batch_id = @batch AND picking_task_id = @task;

COMMIT;   -- 行数都对才提交，否则 ROLLBACK
```

补充说明：
- 老数据的 `wh_picking_order_item.picking_task_id` 可能是 0。前置检查如果查不到明细，就把相关条件改成 `order_no IN (该任务的订单)`。
- 场景 B 如果是 Zone2 Print 领取的，Task 是 `ensureSingleZoneTaskCreated` 预建的。删除后下次 Print 会重新创建，已打印的标签要作废。
- Batch 的商品数据在 Redis（`batchOrderItemRedisService`），出库时才删。batch 改回 1 后可以被重新领取，也可能被打散任务（`breakUpBatchJob`）重新组批，两种结果都正常。

## 五、场景 C 脚本（跨 Zone：退回待领取）

```sql
-- 目标库：生产 Yamibuy_WH；同一会话执行
SET @wh = '002', @task = 0;   -- 改成被误领的那个 Zone Task
SELECT po.batch_id, t.zone_id, t.cart_no, t.task_type INTO @batch, @zone, @cart, @task_type
FROM Yamibuy_WH.wh_picking_task t
INNER JOIN Yamibuy_WH.wh_picking_order po ON po.picking_task_id = t.rec_id
WHERE t.rec_id = @task LIMIT 1;
SELECT MIN(start_time) INTO @claim_dtm FROM Yamibuy_WH.wh_order_process_record
WHERE operation_type = 3 AND operation_ref_id = @task;

-- 前置检查
SELECT @batch, @zone, @cart, @task_type, @claim_dtm;        -- task_type：0=主 Task，1=从 Task
SELECT COUNT(1) AS item_rows,
       SUM(IFNULL(picking_quantity,0) + IFNULL(sorting_pick_quantity,0) + IFNULL(replenish_quantity,0)) AS picked
FROM Yamibuy_WH.wh_picking_order_item WHERE picking_task_id = @task;          -- picked 必须为 0
SELECT COUNT(1) AS po_rows, SUM(tote_no IS NOT NULL AND tote_no <> '') AS tote_bound
FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task;               -- N = po_rows
SELECT status, COUNT(1) FROM Yamibuy_WH.wh_consolidation_task_detail
WHERE picking_task_id = @task GROUP BY status;                                  -- 必须全是 1（PICKING），共 N 行
SELECT c.status, COUNT(1) FROM Yamibuy_WH.wh_consolidation_task c
WHERE c.order_id IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task)
GROUP BY c.status;                                                              -- 必须全是 0（CREATED）
SELECT t.rec_id, t.zone_id, t.task_type, t.status, t.cart_no, t.picking_user    -- 同 batch 其他 Zone 的 Task
FROM Yamibuy_WH.wh_picking_task t
WHERE t.rec_id IN (SELECT DISTINCT picking_task_id FROM Yamibuy_WH.wh_picking_order WHERE batch_id = @batch)
  AND t.rec_id <> @task;
SELECT zone_id, status, picking_task_id FROM Yamibuy_WH.wh_batch_zone WHERE batch_id = @batch;

START TRANSACTION;

-- 1. 先释放 Tote（期望 = tote_bound），必须在清空 picking_order.tote_no 之前
UPDATE Yamibuy_WH.wh_storage_location SET flag = 0, edit_dtm = UNIX_TIMESTAMP()
WHERE warehouse_number = @wh AND flag = 3
  AND location_no IN (SELECT tote_no FROM Yamibuy_WH.wh_picking_order
                      WHERE picking_task_id = @task AND tote_no IS NOT NULL AND tote_no <> '');

-- 2. picking_order 回到拆分时的样子（期望 = 被改过的行数；没绑 Tote、不是 Zone2 Print 时为 0）
UPDATE Yamibuy_WH.wh_picking_order SET tote_no = NULL, cart_no = ''
WHERE picking_task_id = @task AND (tote_no IS NOT NULL OR cart_no <> '');

-- 3. 合单明细 PICKING → PENDING（期望 N）
UPDATE Yamibuy_WH.wh_consolidation_task_detail
SET status = 0, cart_no = '', tote_no = '', done_dtm = 0
WHERE picking_task_id = @task AND status = 1;

-- 4. 主 Task 才有：合单主表清空 primary_cart_no（主 Task 期望 N，从 Task 期望 0）
UPDATE Yamibuy_WH.wh_consolidation_task SET primary_cart_no = '', edit_dtm = UNIX_TIMESTAMP()
WHERE primary_task_id = @task AND status = 0 AND @task_type = 0;

-- 5. 本 Zone 行回到未领取，picking_task_id 保留（期望 1）
UPDATE Yamibuy_WH.wh_batch_zone SET status = 0, edit_dtm = UNIX_TIMESTAMP()
WHERE batch_id = @batch AND zone_id = @zone AND picking_task_id = @task AND status = 1;

-- 6. Task 退回待领取（期望 1）
UPDATE Yamibuy_WH.wh_picking_task
SET status = 0, cart_no = '', picking_user = '', picking_user2 = NULL, picking2_dtm = NULL,
    edit_dtm = UNIX_TIMESTAMP()
WHERE rec_id = @task AND status = 1;

-- 7. 释放拣货车（期望 1）
UPDATE Yamibuy_WH.wh_picking_cart SET status = 1, picking_task_id = NULL
WHERE warehouse_number = @wh AND cart_no = @cart AND picking_task_id = @task;

-- 8. 订单池 5 → 0：只改其他 Zone 也没领取的订单（期望 = 这类订单数）
UPDATE Yamibuy_WH.wh_order_pool p SET p.status = 0
WHERE p.warehouse_number = @wh AND p.status = 5
  AND p.order_no IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task)
  AND NOT EXISTS (SELECT 1 FROM Yamibuy_WH.wh_picking_order po2
                  INNER JOIN Yamibuy_WH.wh_picking_task t2 ON t2.rec_id = po2.picking_task_id
                  WHERE po2.order_no = p.order_no AND t2.rec_id <> @task AND t2.status >= 1);

-- 9. 订单 shipping_status 3 → 2：条件同上
UPDATE Yamibuy_WH.wh_order_info o SET o.shipping_status = 2
WHERE o.order_status = 1 AND o.shipping_status = 3 AND o.pay_status = 2
  AND o.order_id IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task)
  AND NOT EXISTS (SELECT 1 FROM Yamibuy_WH.wh_picking_order po2
                  INNER JOIN Yamibuy_WH.wh_picking_task t2 ON t2.rec_id = po2.picking_task_id
                  WHERE po2.order_no = o.order_id AND t2.rec_id <> @task AND t2.status >= 1);

-- 10. 流程记录：先删本任务的 type=3（期望 N），再对没有其他 Zone 拣货记录的订单重开 Wait
DELETE FROM Yamibuy_WH.wh_order_process_record
WHERE operation_type = 3 AND operation_ref_id = @task AND isFinished = 0;
UPDATE Yamibuy_WH.wh_order_process_record r SET r.end_time = NULL, r.isFinished = 0
WHERE r.operation_type = 2 AND r.memo = 'Wait'
  AND r.end_time BETWEEN @claim_dtm - 5 AND @claim_dtm + 5
  AND r.order_id IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task)
  AND r.order_id NOT IN (SELECT x.order_id FROM (   -- DISTINCT 强制物化派生表，避免 1093
        SELECT DISTINCT order_id FROM Yamibuy_WH.wh_order_process_record
        WHERE operation_type = 3
          AND order_id IN (SELECT order_no FROM Yamibuy_WH.wh_picking_order WHERE picking_task_id = @task)
      ) x);

-- 11. batch 2 → 1：只在同 batch 没有其他已领取 Task 时（期望 0 或 1，与前置检查一致）
UPDATE Yamibuy_WH.wh_batch b SET b.status = 1
WHERE b.batch_id = @batch AND b.status = 2
  AND NOT EXISTS (SELECT 1 FROM Yamibuy_WH.wh_picking_order po
                  INNER JOIN Yamibuy_WH.wh_picking_task t ON t.rec_id = po.picking_task_id
                  WHERE po.batch_id = @batch AND t.status >= 1);

COMMIT;   -- 行数都对才提交，否则 ROLLBACK
```

执行后验证：Task status=0，Cart status=1，本 Zone 的 `wh_batch_zone.status=0`，明细全是 0。正确的拣货员扫同 Zone 的车（Zone2 走 Print 页面）应该能重新领到这个 Task。

补充说明：
- **Zone2 Print 误领**：车和 Tote 都是系统自动分配的，已经打出来的标签要作废，Tote 由第 1 步释放。
- **要整批重组**：先按本节把 Task 退回待领取，并确认 batch 已改回 1。然后用系统的打散 batch 功能（`breakUpBatch`，内部调用 `cleanupCrossZoneBatchData`），不要手写删除跨 Zone 数据。
- **第 4 步**只在 `@task_type = 0`（主 Task）时生效。主表 `primary_cart_no` 只是主 Zone 车号的冗余快照，权威值在明细的 `cart_no`。
- **别的 Zone 已领取或已拣完**：订单池、shipping_status、batch 状态都保持不变（第 8、9、11 步的 NOT EXISTS 已经处理）。只把被误领的这一侧退回去。
- **第 2 步的期望行数**：MySQL 默认只统计值真正变化的行。没绑 Tote 的任务这一步是 0 行，属于正常。

## 六、实例

- **2026-11-07，001 仓，任务 1468102**：场景 A。测试账号 `nikki.ma(3450)` 用车 M01 领走 batch 2145962，共 12 单 95 行，都没拣、没绑 Tote。按第四节执行，期望行数依次为 batch 1、cart 1、pool 12、order_info 12、item 95、order 12、task 1、process_record 删 12 / 重开 12。
