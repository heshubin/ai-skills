---
inclusion: fileMatch
fileMatchPattern: '**/wms-cloud-service/**/*.java,**/central-packing-service/**/*.java,**/wms-cloud-service/**/mapper/*.xml,**/central-packing-service/**/mapper/*.xml'
---

# Zone Picking（OP-37299）编码自查规则

仅当本次改动涉及 Zone Picking 相关链路时适用；不涉及则忽略本文件。
规格来源：`d:\code\kiroWP\.kiro\specs\zone-picking\{requirements,design,tasks}.md`。

## 红线（不可妥协，约束 26）

**未启用 Zone Picking 的仓库行为必须与上线前完全一致。** 上线只给 002 仓，001/101 仓保持原流程。

动到下列任一既有共用链路时，入口**第一段**必须接 `zoneConfigService.isZonePickingEnabled(warehouseNumber)` 短路，`false` 分支必须是「原样返回 / 调用原方法 / 不做任何 Zone Picking 写操作」：

- `PreoccupancyService.markCrossZoneIfNeeded`（预占打标）
- 组批服务（Cross_Zone / Single_Zone 分批）
- `ZoneSplitServiceImpl.ensureBatchSplit`（拆分）
- `OrderPickService` 拣货完成分支
- `PutwallServiceImpl` 打包入口与打包完成钩子
- `ZonePickingOosHandler.handleZonePickingRemoval`（OOS 清理，短路须在任何查询之前，做到零额外 DB 访问）

改完这些链路必须能说明未启用仓库的回归证据（测试指引 E5）。

## 模型口径（唯一口径，写代码前先对齐）

- **格口绑定的对象是 Cart，不是 Tote**。Zone 拣完后整台 Cart 推到 Consolidation_Slot 停放，**Tote 全程不下车**。
- Tote 自被分配到 Cart 起全程承载于该 Cart，含随车运输期间与格口停放期间；**离开 Cart 的唯一路径是在打包台被取走**。
- Cart 停放两态互斥：停于 Parking_Slot（`park_type=1`）或停于 Consolidation_Slot（`park_type=2`），载体是既有 `wh_picking_cart.parking_slot` + 新增 `park_type`。
- 判定权威值取 `wh_consolidation_task_detail`（逐 Zone 一条，各带 `cart_no` 与 `consolidation_no`）；主表 `wh_consolidation_task.primary_cart_no` 与 `consolidation_no` 是 **Zone1 侧冗余快照，只读不判**。

以下写法一律错误，遇到即按上述口径改：把 Tote 绑到 Slot、让 Tote 脱离 Cart、按 Zone 侧写两套释放规则、在上车链路释放 Cart。

## 两个释放入口（各只有一个，不许另写判断）

| 对象 | 唯一入口 | 判据 | 允许的调用点 |
|---|---|---|---|
| Cart | `CartReleaseService.releaseIfEmpty` | 其上不再承载任何 Tote | **仅** 打包完成钩子一处 |
| Consolidation_Slot | `SlotReleaseService.releaseIfNoCart` | 其上不再停放任何 Cart | **仅两处**：Zone2 侧 Cart 上车运走、Zone1 侧合并完成后 Cart 推去打包 |

- 四种 `ScanTargetType` 的**上车一律不释放 Cart**。
- **OOS 踢单、订单取消、Batch 解散都不做 Slot 释放**（需求 11.16）。
- 一次操作影响多个 Cart/Slot 时逐个独立判断，且走批量查询。

## OOS 踢单门控（约束 28）

踢单是连坐式的（`queryOrderForBatch` 按库位+商品捞，同库位所有在拣订单一起命中），一次会波及一批不同阶段的跨 Zone 订单。清理前必须按**该订单所属 Batch 两侧 Zone_Task 的 `wh_picking_task.status`** 逐单判定：

- 两侧全 `status=0`（未领取）→ 才执行清理
- 任一 `status>=1`（已领取）→ **零写操作**，只沿用既有 `updateItemSkip` 跳过标记

绝不能无条件清理：Zone2 已领取/已拣完/已停上格口/已装车时删掉拣货明细并取消 Consolidation，会造成实物已拣出而系统无记录、Tote 成孤儿，且难以在测试环境复现。

`cancelByOrderId` 用正向状态白名单（只允许 CREATED / READY → CANCELLED），按返回受影响行数判断，0 行记 `log.warn` 跳过、不算失败。

## 提交前逐条对照

1. 触碰共用链路的地方，仓库开关短路加了吗？`false` 分支真的零行为变更吗？
2. 释放逻辑走的是那两个唯一入口吗？有没有第二处 `releaseIfEmpty` 调用点？
3. 绑定/解绑操作的对象是 Cart 而不是 Tote 吗？
4. 就绪判定与释放判定取的是明细还是主表？（必须是明细）
5. OOS/取消/解散链路里有没有误加 Slot 释放？
6. 清理类逻辑动手前校验前置状态了吗？
7. 批量查询而非循环单查？无 `SELECT *`？状态值走枚举而非字面量？
8. `@author William.He`，关键逻辑有中文注释？

## 打包台查询有效性（Bug#10XXX 经验）

`queryPackingInfoList` 按 `tote_no` 查 `wh_picking_order` 时，**必须排除已完成合并的 Zone2 picking_order**。

**失效判据**：该 picking_order 对应的 `wh_consolidation_task_detail`（`is_primary=0`）关联到 `wh_consolidation_task.status=80(COMPLETED)` 的合并任务，说明该 Zone2 tote 已被合并走，不再有效。

```sql
AND NOT EXISTS (
    SELECT 1
    FROM Yamibuy_WH.wh_consolidation_task_detail ctd
    INNER JOIN Yamibuy_WH.wh_consolidation_task ct ON ct.rec_id = ctd.task_id
    WHERE ctd.picking_task_id = wpo.picking_task_id
      AND ctd.is_primary = 0   -- Zone2 侧
      AND ct.status = 80       -- COMPLETED
)
```

**根本原因**：Zone2 tote 合并完成后物理释放，但 `wh_picking_order.tote_no` 保留历史值（**不应修改，是真实记录**）。新订单占用同一 tote 后，未加此过滤会同时查出旧订单和新订单，触发 "reference to multiple orders" 报错。

**禁止用 GROUP BY order_id 绕过**：GROUP BY 只是掩盖问题，不解决根因，且会掩盖真正的多订单冲突场景。

**⚠️ 跨服务同步检查**：此 SQL 在两个服务中都有，修复时必须两处同步改：
- `wms-cloud-service/PackingMapper.xml`（取消打包、补单重置流程调用）
- `central-packing-service/PackingMapper.xml`（打包台主入口，`/packing/order` 接口调用）

漏改任一服务，bug 只修了一半。
