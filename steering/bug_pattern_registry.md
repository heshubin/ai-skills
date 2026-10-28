---
inclusion: auto
name: bug_pattern_registry
description: 修改或排查 WMS 批次/库存相关代码、写入库存日志、预占/拣货扣减、需要回顾历史 bug 模式自查时使用。触发词：批次, lot_id, LOT_LEGACY, wh_lot_inventory, 库存日志, inventory_transaction_log, 预占, 拣货扣减, UnexpectedRollbackException, REQUIRES_NEW, bug 自查, BUG-
---

# Bug 模式注册表

每次修复 bug 后记录在此。写代码时自动加载，用于：
1. 回顾已修复的 bug
2. 自查：当前修改是否有类似的错误模式
3. 系统性排查：已实现的功能中是否还有同类问题

## 自查清单（每次写代码前过一遍）

- [ ] 从数据库查回来的 `Double`/`Integer`/`Long` 包装类字段，在直接赋值给基本类型前是否做了 null 检查？避免自动拆箱 NPE（BUG-043）
- [ ] 拣货场景（isPickingProcess）是否从预占日志反推精确批次？不能盲目按 rec_id ASC 扣减（BUG-037）
- [ ] 写入 `wh_inventory_transaction_log` 时，lot_id 是否有值？包括：1)SQL层IFNULL兜底 2)Java层日志对象setLotId 3)批次分配结果是否传递给了日志写入逻辑（BUG-001/002/005/014）
- [ ] 用 `order_id` 还是 `order_sn`？查 `wh_order_lot_consumption` 必须用 `order_id`（BUG-008）
- [ ] 预占/拣货场景用的 SQL 方法是否正确？（BUG-003/004）
- [ ] `strReplace` 后是否用 `grepSearch` 验证写入成功？（BUG-006）
- [ ] 新增 `@Autowired` 是否同步加了 import？禁止全限定类名（BUG-006）
- [ ] 批次日志拆分后 quantity 正负号是否正确？（BUG-007）
- [ ] 方法中有提前 return 时，return 前是否遗漏了批次同步逻辑？（BUG-012）
- [ ] 同一 PO 同一商品多次收货时，上架关联的 lot_id 是否精确到具体 batch？（BUG-013）
- [ ] 查询 SQL 是否用 LEFT JOIN wh_lot_master？lot_id=1 没有 master 记录，INNER JOIN 会过滤掉（BUG-015）
- [ ] 调用 prepareBatchRelease/prepareBatchAllocate 时，quantity 是否为正数？负数会导致 remaining<=0 直接跳过（BUG-016）
- [ ] MyBatis SQL 的 resultMap/resultType 是否匹配实际查询的数据结构？跨表/聚合查询禁止复用其他表的 resultMap，用 `resultType=HashMap` 或专用 DTO（教训24）
- [ ] 取消预占时是否按原始预占的 lot 精确释放？不能用通用的 prepareBatchRelease（BUG-023）
- [ ] LotInventoryService 的方法事务传播是否为 REQUIRES_NEW？REQUIRED 会加入外层事务，抛异常标记 rollback-only 导致主流程回滚（BUG-024）
- [ ] 上架时老 batch（lot_id=0）是否有 LOT_LEGACY 兜底？queryLotIdBySourceNumber 对同 PO 多次收货不安全（BUG-025）
- [ ] dealPutawayLotInventory 中 from 失败是否会阻止 to 执行？必须分别 try-catch（BUG-025）
- [ ] 从队列/列表中分配资源时是否用"消费"语义（poll/remove + 减量）？peek 不会移动指针，多次读取返回同一个元素（BUG-042）
- [ ] 写入 wh_inventory_transaction_log 时是否设置了 before_quantity 和 before_allocated？（BUG-042）
- [ ] 取消预占日志的 lot_id 是否从预占成功日志批量反查（batchQueryPreoccupancyLotLogs）？不能从 prepareBatchRelease 释放结果推导，且要覆盖 Secondary Preoccupancy（BUG-042）
- [ ] JOIN 关联表时，关联字段是否有唯一索引？如果没有，是否用 EXISTS 代替 JOIN 避免笛卡尔积？（BUG-027）
- [ ] 高频操作中是否有全表扫描的同步查询？lot_id=1 等大数据量场景必须跳过或异步处理（BUG-033）
- [ ] 批量 Job 是否具备幂等性？多次执行是否会产生重复数据？（BUG-034）
- [ ] 新建表的关联字段类型是否与被关联表一致？尤其 bigint vs varchar（BUG-040）
- [ ] 批次操作的 @Transactional 是否用了 REQUIRES_NEW？外部资源调用（Redis/HTTP）是否有降级方案？（BUG-041）
- [ ] 新建表的关联字段类型是否与被关联表完全一致？尤其 bigint vs varchar 不能混用（BUG-040）
- [ ] MQ 消费 / 定时任务 / 线程池等无 HTTP 上下文的入口，是否显式建立了 siteCode 上下文？多站点过滤条件（vendor_id/site_code）取值失败时是否静默兜底成了某个站点的值？（BUG-044）
- [ ] 业务判断是否用"查不到记录"代理了"业务状态"？状态判断必须查明确的状态字段（BUG-044）
- [ ] inventory 操作幂等校验是否只查单一 operation_type？取消订单的释放路径有多条（soCancel / WMSCancelOrder / soOutStock / OOS），幂等必须把这些互斥操作作为集合一并查询，防止"已走 soOutStock 路径出库"后再走 soCancel 路径二次归还（OPT-25）
- [ ] MyBatis resultType="map" 查询中，对数字字段（如 cancel、status 等 tinyint/int 列）是否使用了硬强转 `(Integer)`？MySQL JDBC 对 IFNULL/CASE/聚合函数包裹后的字段会推断为 Long，强转 Integer 会在运行时抛 ClassCastException（BUG-045）

---

## BUG-001: batchInsertInventoryLog 缺少 lot_id 字段
- **日期**: 2026-04-22
- **根因**: SQL INSERT 列表没有 lot_id，Java 层设置了但 SQL 没写入
- **修复**: SQL 加 lot_id 列 + IFNULL 兜底
- **防范**: 所有 INSERT wh_inventory_transaction_log 的 SQL 必须包含 lot_id

## BUG-002: 二次预占日志 lotId=null 导致 Column lot_id cannot be null
- **日期**: 2026-04-24
- **根因**: `itemPreoccupancy` 中 `batchInsertInventoryLog` 在批次分配之前执行，日志没有 lotId
- **修复**: 先 `prepareBatchAllocate` 获取 lotId，按 lot 拆分日志后再写入
- **防范**: 写日志前必须先完成批次分配

## BUG-003: 拣货时批次 allocated_qty 扣减失败
- **日期**: 2026-04-24
- **根因**: 预占后 quantity=0，`queryAvailableLotsFIFO`（WHERE qty>0）查不到
- **修复**: 新增 `queryAllocatedLotsFIFO/FEFO`（WHERE alloc>0）+ `decreaseAllocatedQtyOnly`
- **防范**: 拣货场景只能用 queryAllocatedLots + decreaseAllocatedQtyOnly

## BUG-004: 拣货扣减用 updateAllocatedQty 导致 quantity 被错误加回
- **日期**: 2026-04-24
- **根因**: `updateAllocatedQty` 同时操作 qty 和 alloc，传负数时 qty 被加回
- **修复**: 拣货场景改用 `decreaseAllocatedQtyOnly`（只减 alloc）
- **防范**: updateAllocatedQty 只用于预占（正数），禁止在拣货场景使用

## BUG-005: 6 个直接 INSERT 日志的 SQL 缺少 lot_id
- **日期**: 2026-04-24
- **根因**: PreoccupancyMapper/TSPickingMapper/TSInboundMapper/TSTruckMapper/ReceiveReturnMapper 中直接 INSERT 没有 lot_id
- **修复**: LEFT JOIN wh_lot_inventory 获取真实 lot_id
- **防范**: 新增 INSERT wh_inventory_transaction_log 时必须包含 lot_id

## BUG-006: strReplace 返回 success 但实际没写入
- **日期**: 2026-04-24
- **根因**: strReplace 匹配失败但返回了 success
- **修复**: 每次 strReplace 后用 grepSearch 验证
- **防范**: 永远不信任 strReplace 的返回值，必须验证

## BUG-007: 盘亏跨批次日志 before_quantity 逐条递减计算错误
- **日期**: 2026-04-24
- **根因**: 累加时用 `e.getQuantity()`（负数），减负数变加，方向反了
- **修复**: 改用 `Math.abs(e.getQuantity())`
- **防范**: 累加计算时用绝对值，不依赖 quantity 的正负号

## BUG-008: RMA 收货用 orderSN 查 wh_order_lot_consumption 查不到
- **日期**: 2026-04-25
- **根因**: `wh_order_lot_consumption.order_id` 存的是数字型 order_id，不是字符串型 order_sn
- **修复**: 先 `queryOrderIdByOrderSn` 转换，再用 order_id 查
- **防范**: 查 wh_order_lot_consumption 必须用 order_id，不能用 order_sn

## BUG-009: PST return 时 lot_id=1（LOT_LEGACY）
- **日期**: 2026-04-25
- **根因**: 退货回补先查 wh_order_lot_consumption（空），走到 LOT_LEGACY 兜底
- **修复**: 优先用 from 方向（PST）扣减拿到的批次明细回补
- **防范**: 退货回补优先级：from 批次明细 > wh_order_lot_consumption > LOT_LEGACY

## BUG-010: 错收冲减日志未带 lot_id
- **日期**: 2026-04-25
- **根因**: `addInventoryLog` 和 `returnRECGReceive` 中日志写入没有设置 lotId
- **修复**: 从 `decreaseLotInventory` 返回值获取 lot_id，传给日志写入
- **防范**: 批次扣减的返回值（LotConsumptionDetail）必须传递给日志写入

## BUG-011: RMA 收货 adjustInventory 未传 lotId
- **日期**: 2026-04-25
- **根因**: `RmaReceiveService.adjustInventory()` 构造 AdjustLocationRequest 时没有设置 lotId
- **修复**: 通过 orderSN→order_id→wh_order_lot_consumption 获取原始 lot_id
- **防范**: 所有调用 adjustLocation 的入口，如果涉及订单退回，必须传 lotId

## BUG-012: 调拨预占（TS Preoccupancy）未同步 wh_lot_inventory
- **日期**: 2026-04-25
- **根因**: `TSPickingService.preoccupancySuccess()` 中批次预占代码放在方法底部，但单库位库存足够时在第337行 `return` 提前返回，跳过了批次预占代码。导致聚合库存 `allocated_qty` 正确更新，但 `wh_lot_inventory.allocated_qty` 始终为 0
- **影响**: 后续 TS Pick 查 `allocated_qty > 0` 查不到，报"批次库存不足"
- **修复**: 
  1. 将批次预占逻辑抽取为 `syncTsLotPreoccupancy()` 私有方法
  2. 在两个出口（单库位 return 前 + 跨多库位循环结束后）都调用
  3. 改用 `prepareBatchAllocate` + `executeBatchAllocateUpdate`（参考常规预占模式），遵循 FIFO/FEFO 策略
- **防范**: 方法中有提前 return 时，必须检查 return 前是否遗漏了批次同步逻辑

## BUG-013: 上架时 lot_id 取错（同一PO同一商品多次收货）
- **日期**: 2026-04-27
- **根因**: `PutawayServiceHelper.queryLotIdBySourceNumber()` 用 `sourceNumber + itemNumber` 查 `wh_lot_master`，同一 PO 同一商品多次收货时有多条记录，遍历取第一条（最早的 lot_id），无法区分是哪次收货的 batch
- **影响**: 按第二次收货的 batch 上架时，关联到第一次收货的 lot_id（如 lot_id=167 而非 168）
- **修复**:
  1. `wh_inbound_batch` 新增 `lot_id` 列（BIGINT DEFAULT 0）
  2. 收货时 `createLotForReceiving` 返回 lot_id 后，通过 `writeLotIdToBatch` 回写到 batch
  3. 上架时优先从 `batch.lot_id` 精确取值，为 0 时 fallback 到 `queryLotIdBySourceNumber`（兼容老数据）
  4. 三种收货方式（PO/caseID/groupPO）全部覆盖
- **防范**: 两张表之间有一对一关系时，必须通过外键或回写字段建立精确关联，不能依赖反查匹配

## BUG-014: 调拨预占日志 lot_id=0（批次分配结果未回传到日志）
- **日期**: 2026-04-27
- **根因**: `syncTsLotPreoccupancy` 只做了批次库存写入（`prepareBatchAllocate` + `executeBatchAllocateUpdate`），但没有把分配结果回传到 `tsPreoccupancyVo.inventoryTxLogList` 中。日志在 for 循环中构造时 `lotId` 为 null，写入时被 `IFNULL(#{log.lotId}, 0)` 兜底为 0
- **影响**: 调拨预占日志 lot_id=0，无法追溯预占了哪些批次
- **修复**: 在 `syncTsLotPreoccupancy` 中，批次预占写入后，按 lot 拆分 `inventoryTxLogList`（参考常规预占的日志拆分逻辑），替换原日志列表
- **防范**: 批次预占/释放后，必须检查对应的日志列表是否按 lot 拆分并设置了 lotId

## BUG-015: LOT_LEGACY(lot_id=1) 库存在 FIFO/FEFO 查询中被过滤
- **日期**: 2026-04-28
- **根因**: 迁移脚本中 `INSERT INTO wh_lot_master ... SELECT 1 as lot_id`，但 lot_id 是 AUTO_INCREMENT 主键，实际写入了 lot_id=0。`wh_lot_inventory` 中 lot_id=1 的记录在 4 个查询 SQL 中被 INNER JOIN wh_lot_master 过滤掉（因为 master 中没有 lot_id=1）
- **影响**: 所有 lot_id=1 的老库存在预占、扣减、拣货时都查不到，导致"批次库存不足"
- **修复**:
  1. 4 个查询 SQL 从 INNER JOIN 改为 LEFT JOIN + COALESCE 兜底
  2. 迁移脚本重构：lot_id=1 只写 wh_lot_inventory，不写 wh_lot_master（因为 lot_id 是主键，一个值只能对应一条记录，无法覆盖所有商品）
  3. 排序用 COALESCE(lm.receive_time, 0) / COALESCE(lm.expire_dtm, 0) 兜底
- **防范**: wh_lot_master 的 lot_id 是主键，不能用固定值覆盖多个商品；查询 SQL 必须用 LEFT JOIN 兼容没有 master 记录的 lot_id

## BUG-016: OOS 取消预占时 wh_lot_inventory alloc 未释放 + 日志 lot_id=0
- **日期**: 2026-04-28
- **根因**: `PreoccupancyService.itemPreoccupancy()` 中取消预占时，构造 `LotPreoccupancyItem` 的 quantity 传了负数（`-pl.getQty()`），但 `prepareBatchRelease` 期望正数。`remaining = -10`，`remaining <= 0` 直接 break，一条都没释放
- **影响**: 
  1. `wh_lot_inventory` 的 `allocated_qty` 没有释放（聚合库存 alloc=0 但批次 alloc=10）
  2. 日志 `lotUpdates` 为空，无法按 lot 拆分，lot_id=0
- **修复**: 去掉取反，`prepareBatchAllocate` 和 `prepareBatchRelease` 都期望正数
- **防范**: 调用 `prepareBatchRelease`/`prepareBatchAllocate` 时，quantity 必须为正数

## BUG-017: 上架时 qcDao.queryInboundBatch 因缺少 inbound_number 返回 null，lot_id fallback 到 1
- **日期**: 2026-04-28
- **根因**: `PutawayServiceHelper.getAllocationResult()` 中用 `qcDao.queryInboundBatch(bp)` 查 batch 的 lot_id，但只设了 `bp.setRec_id()`，没有设 `inbound_number` 和 `item_number`。SQL 中 JOIN 子查询需要这两个参数，为 null 时 JOIN 失败返回 null。fallback 到 `queryLotIdBySourceNumber` 取到了 lot_id=1（LOT_LEGACY）
- **影响**: case 收货后按 batch 上架，日志 lot_id=1 而非真实的 lot_id=202
- **修复**: 改用 `putawayDao.queryBatchLotId(rec_id)` 简单查询，只需 rec_id 一个参数，不依赖 inbound_number
- **防范**: 调用复杂 SQL 时必须确认所有必要参数都已设置；优先用简单查询代替复杂 JOIN

## BUG-018: 调拨 Truck manage 日志 lot_id=0（SQL 中 @locationNo 变量在 LEFT JOIN 时未赋值）
- **日期**: 2026-04-28
- **根因**: `TSTruckMapper.xml` 的 `insertTransactionLog` SQL 中，`@locationNo` 在 SELECT 子句中赋值，但 LEFT JOIN 在 FROM 阶段先执行。MySQL 执行顺序 FROM/JOIN 先于 SELECT，导致 LEFT JOIN 时 `@locationNo` 为 NULL，匹配不到 `wh_lot_inventory`
- **影响**: transshipment outbound 日志 lot_id=0，无法追溯调拨出库的批次
- **修复**: LEFT JOIN 中的 `@locationNo` 改为内联子查询 `(SELECT sl.location_no FROM wh_storage_location sl WHERE sl.location_type = 47 AND sl.warehouse_number = #{ship_out_warehouse} LIMIT 1)`
- **防范**: SQL 中禁止在 LEFT JOIN 条件中使用 SELECT 子句中赋值的变量；需要动态值时用内联子查询

## BUG-019: 上架时 from 方向走 FIFO 扣到 LOT_LEGACY（应扣指定 lot_id）
- **日期**: 2026-04-28
- **根因**: 上架（PUT_AWAY_BIN/STOCK）走通用转移逻辑，from 方向按 FIFO 扣减收货区（RECG）。收货区有 lot_id=1（LOT_LEGACY，qty=154）排最前面，先被扣了。`request.getLotId()=202` 被忽略
- **影响**: 上架后 Bin 上的批次是 lot_id=1 而非收货时创建的 lot_id=202
- **修复**: 新增 `isPutawayProcess` + `dealPutawayLotInventory`，上架时 from/to 都用 `request.getLotId()` 指定的批次，不走 FIFO
- **防范**: 上架场景有明确的 lot_id（收货时创建），必须用指定批次而非 FIFO 自动选择

## BUG-020: 转补单时盘亏扣错批次（先转移再损益导致 FIFO 顺序不对）
- **日期**: 2026-04-28
- **根因**: `PackingService.packingReplenish()` 中先执行 `adjustLocation`（转移），再执行 `adjustPackingReplenish`（损益）。转移按 FIFO 先转走老批次（203），剩下新批次（209）被盘亏。应该先盘亏老批次再转移
- **影响**: 盘亏记在新批次上，违背 FIFO 原则
- **修复**: 调换执行顺序——先损益再转移。两个项目（wms-cloud-service + central-packing-service）都调整
- **防范**: 同一操作中有损益和转移时，必须先损益再转移，确保 FIFO 原则在两步中都被遵守

## BUG-021: queryByLotId 方法重载导致 MyBatis BindingException
- **日期**: 2026-04-28
- **根因**: `LotInventoryDao` 中有两个 `queryByLotId` 重载方法（单参数和三参数），但 MyBatis XML 中只有一个 `id="queryByLotId"` 的 SQL，包含 `<if test="warehouseNumber">` 动态条件。调用单参数版本时 MyBatis 找不到 `warehouseNumber` 参数，抛出 `BindingException`
- **影响**: `checkAndUpdateLotStatus` 报错，批次状态无法更新
- **修复**: 单参数版本改名为 `queryAllByLotId`，对应独立的 SQL（不带动态条件）
- **防范**: MyBatis 中禁止 Java 方法重载映射到同一个 SQL id；不同参数的查询必须用不同的方法名和 SQL id

## BUG-022: TS Receive 日志 lot_id=0 + 取消调拨单日志 quantity 不对
- **日期**: 2026-04-28
- **根因1**: `TSInboundMapper.xml` 的 `insertTransactionLog` SQL 中 LEFT JOIN 查目标库位 TRANSIN，但日志写入时 TRANSIN 上还没有 lot_inventory（`transferLotInventory` 还没执行）
- **根因2**: `TSPickingMapper.xml` 的 `cancelTSPreoccupancyByTask` SQL 中日志 quantity 用了 `li.allocated_qty`（该 lot 全部预占量），而不是 `task.qty`（本次取消量）
- **影响**: TS Receive 日志 lot_id=0；取消调拨单日志 quantity 是全量而非本次取消量
- **修复**: 
  1. TSInboundMapper: LEFT JOIN 改为查源库位 TSOZ（通过 location_type=47 子查询）
  2. TSPickingMapper: 去掉 CASE WHEN，直接用 task.qty
- **防范**: SQL 中 LEFT JOIN 获取 lot_id 时，必须查源库位（有数据的一方）；日志 quantity 必须用本次操作量而非全量

## BUG-023: 取消调拨预占释放错误的 lot（prepareBatchRelease 按 alloc 大小释放而非按原始预占）
- **日期**: 2026-04-29
- **根因**: `cancelTSPreoccupancy` 和 `deductionTSAllocatedQty` 中用 `prepareBatchRelease` 释放批次预占，该方法按 `allocated_qty` 从大到小释放。当多个调拨单预占了同一库位的不同 lot 时，释放了 alloc 最大的 lot 而非该调拨单实际预占的 lot
- **影响**: 取消调拨单 TS202604280005 时，应释放 lot_id=236 的6个，实际释放了 lot_id=226 的6个
- **修复**: 不用通用的 `prepareBatchRelease`，改为从 `wh_inventory_transaction_log` 中反查该调拨单的预占日志（`preoccupancy success`），按原始预占的 lot 精确释放
- **防范**: 取消预占时必须按原始预占的 lot 精确释放，不能用通用的按 alloc 大小释放

## BUG-024: 多库位预占时 wh_lot_inventory 未正确预占 + 日志 lot_id=0（available 计算错误）
- **日期**: 2026-04-29
- **根因**: `LotInventoryServiceImpl` 中 `prepareBatchAllocate`、`decreaseLotInventory`、`allocateLotInventory` 三个方法计算可用量时用了 `lot.getQuantity() - lot.getAllocated_qty()`。但 `wh_lot_inventory` 的设计是预占时 quantity 减少、allocated_qty 增加，`quantity` 本身就是"剩余可预占量"，不需要再减 `allocated_qty`。当同一 lot 已被其他订单预占过（allocated_qty > 0）时，`quantity - allocated_qty` 得到负数或过小值，该 lot 被跳过
- **影响**: 
  1. `prepareBatchAllocate` 返回空 → 日志无法按 lot 拆分 → lot_id=0
  2. `wh_lot_inventory` 的 allocated_qty 没有正确增加
  3. 所有"同一库位同一商品已有预占"的场景都会触发（首次预占不受影响）
- **修复**: 3 处 `lot.getQuantity() - lot.getAllocated_qty()` 全部改为 `lot.getQuantity()`
- **防范**: `wh_lot_inventory` 的 quantity 就是可用量（预占时已减过），计算可用量时直接用 quantity，不要再减 allocated_qty

## BUG-025: PIC 转移时 lot_id 取错（多次收货时 FIFO 取到最早的批次）
- **日期**: 2026-04-29
- **根因**: PIC 转移（RECG → PIC Tote → PIC_TRANSFER）走通用 `adjustLocation`，from 方向按 FIFO 扣减。同一 PO 多次收货时，RECG 上有多个 lot，FIFO 取到最早的 lot（230）而非当前收货的 lot（247）
- **影响**: PIC 转移日志记录的 lot_id 是之前收货的批次，不是当前收货的批次
- **修复**: 
  1. `ItemPicStatus` 新增 `lotId` 字段
  2. `ReceiveService.picTransfer` 从 `batch.getLot_id()` 获取当前收货的 lot_id，设置到 `itemPicStatus`
  3. `PicWhService.confirmAddItem` 和 `PicIMService.confirmCheckIn` 中把 lotId 设置到 `AdjustLocationRequest` 和 `LocationItemRequest`
- **防范**: 所有从收货区（RECG）转移库存的场景，如果有明确的 lot_id（收货时创建），必须传递给 adjustLocation，不能依赖 FIFO 自动选择

## BUG-026: FBY/YML 多次收货后按入库单号上架报错（queryLotIdBySourceNumber 取到已上架的 lot）
- **日期**: 2026-04-29
- **根因**: FBY/YML 单次收货走 `processSinglePo`，`group_batch_id` 为空。上架时 `getAllocationResult` 中 `group_batch_no` 和 `batch_no` 都为空，走 `queryLotIdBySourceNumber` fallback，取到第一个 lot（可能已上架过，RECG 上 quantity=0），`dealPutawayLotInventory` 扣减时报"批次库存扣减失败"
- **影响**: FBY/YML 多次收货后按入库单号一次性上架报错；单次收货后上架正常（只有一个 lot）
- **修复**: 
  1. 新增 `getBatchUnPutQuantityByReference` SQL：按 `reference_id`（入库单号）查未上架的 batch 列表
  2. `getAllocationResult` 新增第3优先级：当 `group_batch_no` 和 `batch_no` 都为空时，按入库单号查 batch 分配
  3. 抽取 `allocateQuantityFromBatchList` 公共方法，供 `allocateQuantityByBatch` 和新逻辑共用
- **防范**: 上架时获取 lot_id 的优先级：batch.lot_id（精确）> 按 batch 列表分配 > queryLotIdBySourceNumber（兜底）。不能依赖 queryLotIdBySourceNumber 处理多次收货场景

## BUG-027: writeLotIdToBatch 只更新数据库未同步 Java 对象，导致 PIC 转移 lotId 为 null
- **日期**: 2026-04-30
- **根因**: `ReceiveService.writeLotIdToBatch` 调用 `inboundDao.updateBatchLotId` 更新了数据库中 `wh_inbound_batch.lot_id`，但没有同步更新 Java 对象 `batch.setLot_id(lotId)`。后续 `receiveConfirm` 中 `batch.getLot_id()` 返回初始值 0/null，传给 `picTransfer` 的 lotId 为 null，PIC 转移走了 FIFO，取到 lot_id=1（LOT_LEGACY）
- **影响**: 所有收货后需要 PIC 转移的场景，PIC Tote 上的 lot_id 都是 LOT_LEGACY 而非真实批次
- **修复**: 在 `writeLotIdToBatch` 中加 `batch.setLot_id(lotId)`，确保 Java 对象和数据库同步
- **防范**: 更新数据库后，如果后续代码还需要读取该对象的字段，必须同步更新 Java 对象。数据库更新 ≠ Java 对象更新

## BUG-027b: queryLegacyOnBinStock INNER JOIN wh_storage_location 产生笛卡尔积
- **日期**: 2026-04-30
- **根因**: `LotInventoryMapper.xml` 的 `queryLegacyOnBinStock` SQL 使用 `INNER JOIN yamibuy_wh.wh_storage_location`，而 `wh_storage_location` 表中有 102 个库位存在重复记录（同一 warehouse_number + location_no 有多条）。JOIN 产生笛卡尔积，导致同一条 lot_id=1 的记录被返回多次，Job 对它处理了多次——第一次正常反推并删除 lot_id=1，后续次用内存中的旧数据又创建了重复的新批次
- **影响**: `LotLegacyMigrationHandler` Job 执行后 `wh_lot_inventory` 总量 > `wh_inventory_transaction` 总量（多出 15484），数据不守恒
- **修复**: 将 `INNER JOIN wh_storage_location` 改为 `EXISTS (SELECT 1 FROM wh_storage_location ...)`，无论源表有多少重复记录，EXISTS 只返回 true/false，不产生笛卡尔积
- **防范**: 
  1. JOIN 关联表时必须确认关联字段有唯一索引，否则用 EXISTS 代替 JOIN
  2. 批量处理 Job 中，如果查询结果会驱动逐条写入，必须确保查询结果无重复（加 DISTINCT 或用 EXISTS）
  3. 对 `wh_storage_location` 等基础数据表，应排查并清理重复数据，长期加唯一索引防止再次产生

## BUG-028: 打包出库时批次扣减异常导致整个事务回滚，聚合库存未更新
- **日期**: 2026-04-30
- **根因**: 批次处理异常时，异常通过两层 catch + throw 向上传播，导致整个 `adjustLocation` 事务回滚。第一层：`LotInventoryTransactionHandler.dealLotInventoryTransaction` 的 catch 块 throw；第二层：`LocationService.dealLotInventoryTransaction` 的 catch 块 `throw e`
- **影响**: 打包出库时聚合库存（wh_inventory_transaction）和日志（wh_inventory_transaction_log）都没有更新，订单无法正常出库
- **修复**: 两层 catch 块都改为只记录日志不抛异常：1) `LotInventoryTransactionHandler` 2) `LocationService`。批次是影子表，不应影响主流程
- **防范**: 影子表的操作必须在 catch 块中吞掉异常，只记录日志。检查所有调用链路上的 catch 块，确保没有遗漏的 throw

## BUG-029: 批次库存不足时 decreaseLotInventory 抛异常，导致出库场景 lot 相关数据全部丢失
- **日期**: 2026-04-30
- **根因**: `decreaseLotInventory` 中 `totalAvailable < quantity` 时 throw 异常，被外层 catch 吞掉后 `consumptionDetails` 为空，日志 lot_id=0，order_lot_consumption 无记录。场景：打包出库时 packing 传入的扣减数（15）大于 lot 库存实际数（14），因为之前转 D Tote 已扣了 1 个但 packing 仍按原始数量调用
- **影响**: 出库日志 lot_id=0，wh_lot_inventory 未扣减，wh_order_lot_consumption 无记录
- **修复**: `totalAvailable < quantity` 和 `remainingQuantity > 0` 时改为 warn 日志不抛异常，尽力扣减（扣到没有为止），按实际扣减的 lot 明细记录日志和 order_lot_consumption
- **防范**: 批次是影子表，任何场景下都不应因批次库存不足而中断处理。尽力扣减 + warn 日志 + 定期校验

## BUG-030: 错收冲减坏货时尝试扣减好货 lot 导致 UnexpectedRollbackException
- **日期**: 2026-05-06
- **根因**: `ReceiveReturnService.decreaseLotByPo` 用 `queryLotIdsByPoAndItem` 查该 PO 下所有 lot_id（包括好货和坏货的），遍历时尝试在 RECN0001 上扣减好货的 lot_id=54393（该 lot 只在 RECG0001 上有库存）。`decreaseLotInventory` 内部 `decreaseQuantity` 返回 0，抛出异常，由于 `@Transactional(rollbackFor=Exception.class)` 标记事务为 rollback-only。外层 catch 后继续执行，但事务提交时报 `UnexpectedRollbackException`
- **影响**: 错收冲减坏货时报"系统异常"，整个操作回滚
- **修复**: 在 `decreaseLotByPo` 中先查目标库位上实际有库存的 lot 集合（`lotsOnLocationSet`），遍历时用 `contains` 过滤，跳过不在目标库位上的 lot。同时 `decreaseLotInventory`（指定 lotId）改为 `REQUIRES_NEW` 事务传播，避免异常污染外层事务
- **防范**: 扣减指定 lot 前必须先确认该 lot 在目标库位上有库存；批次操作的 @Transactional 应使用 REQUIRES_NEW 避免污染外层事务

## BUG-031: 错收冲减 wh_inbound_batch 未记录 lot_id
- **日期**: 2026-05-06
- **根因**: `ReceiveReturnService` 中好货冲减（`returnRECGReceive`）和坏货冲减（`returnWhInventoryData` → `addinboundbatch`）创建冲减 batch 时没有设置 `batch.setLot_id()`，导致冲减记录的 lot_id=0
- **影响**: 冲减 batch 无法追溯是哪个批次被冲减的
- **修复**: 在两处 `insertInboundBatch` 前，从 `lotDetails`（实际扣减的批次明细）中取第一个 lot_id 设置到 batch
- **防范**: 所有创建 wh_inbound_batch 记录的地方，如果涉及批次操作，必须设置 lot_id

## BUG-032: 生产上架 UnexpectedRollbackException（dealPutawayLotInventory catch 块遗漏 throw）
- **日期**: 2026-05-06
- **根因**: BUG-028 修复时只改了 `dealLotInventoryTransaction` 和 `LocationService` 的 catch 块，遗漏了 `dealPutawayLotInventory` 内部的 catch 块仍在 throw。上架时如果 RECG 上没有对应 lot 的库存（生产环境初始化数据未执行），`decreaseLotInventory` 抛异常，`dealPutawayLotInventory` 的 catch 再次 throw，被外层 catch 捕获但事务已被 `REQUIRES_NEW` 内部标记
- **影响**: 生产环境上架操作报"系统异常"，事务回滚
- **修复**: `dealPutawayLotInventory` 的 catch 块改为只记录日志不抛异常
- **防范**: 批次相关的所有 catch 块都必须检查是否有遗漏的 throw。全局搜索 `throw new YamibuyException` 确认

## BUG-033: checkAndUpdateLotStatus 查询 lot_id=1 返回 15 万条记录导致接口超时
- **日期**: 2026-05-06
- **根因**: `LotServiceImpl.checkAndUpdateLotStatus(lotId)` 调用 `lotInventoryDao.queryAllByLotId(lotId)`，SQL 只按 `lot_id` 查询无其他条件。lot_id=1（LOT_LEGACY）是所有老库存的兜底标识，在 002 仓有 15 万条记录。每次扣减批次库存后都会调用此方法检查批次是否清空，当扣减的是 lot_id=1 时触发全表扫描，耗时 5 秒
- **影响**: 涉及 LOT_LEGACY 的库存操作（出库、盘亏等）接口响应超时
- **修复**: 移除所有 `checkAndUpdateLotStatus` 调用。该功能当前无实际业务价值（LOT_LEGACY 永远不会清空，正常批次清空后也不需要标记状态）
- **防范**: 批次状态检查不应在每次扣减时同步执行；如需此功能，应改为异步定时任务或加 lot_id=1 跳过逻辑

## BUG-034: MIGRATION_JOB 多次执行产生重复 lot_inventory 和 lot_master 记录
- **日期**: 2026-05-06
- **根因**: `LotLegacyMigrationHandler` Job 被执行了多次（2~30次），每次执行都为同一个 (warehouse, location, item) 创建了新的 lot_id 和 lot_inventory 记录。Job 缺少幂等性保护（没有检查是否已存在 MIGRATION_JOB 创建的记录）
- **影响**: 002 仓 lot_inventory 总量是聚合库存的 2~30 倍（12245 条重复记录），数据不一致
- **修复**: SQL 脚本 `08_fix_migration_job_duplicates.sql`，对每个 (warehouse, location, item) 组合保留 rec_id 最小的记录，删除后续重复的 lot_inventory 和 lot_master
- **防范**: 批量 Job 必须具备幂等性——执行前检查是否已处理过（如 `WHERE NOT EXISTS`），或使用 `INSERT ... ON DUPLICATE KEY UPDATE` 避免重复插入

## BUG-035: 拣货时批次库存不足导致 UnexpectedRollbackException（事务传播 REQUIRED + 上架未写入批次记录）
- **日期**: 2026-05-09
- **根因**: 两个问题叠加：
  1. **上架时老 batch（lot_id=0）匹配到错误 lot_id**：`queryBatchLotId` 返回 null（老 batch 无 lot_id），fallback 到 `queryLotIdBySourceNumber` 匹配到同 PO 号上线后创建的 lot_id=70983。RECG 上没有该 lot 的记录，`dealPutawayLotInventory` from 方向扣减失败，to 方向也未执行，目标库位 G12111 上没有 `wh_lot_inventory` 记录
  2. **拣货时 `decreaseLotInventory` 事务传播为 REQUIRED**：加入外层事务（`OrderPickService.adjustLocation` 的 `@Transactional`），查不到批次记录抛异常时 Spring 标记外层事务为 rollback-only。虽然异常被 catch 吞掉，但事务提交时仍报 `UnexpectedRollbackException`，拣货整体回滚
- **影响**: 线上 002 仓拣货受阻，聚合库存有货但批次表无记录的库位全部无法拣货
- **修复**:
  1. `LotInventoryServiceImpl` 所有 public 方法的事务传播统一改为 `REQUIRES_NEW`（独立事务，失败不影响外层）
  2. `dealPutawayLotInventory` 中 from/to 分别 try-catch（from 失败不阻止 to 执行）
  3. `PutawayServiceHelper.createAdjustRequest` 中 lotId 最终兜底为 `1L`（LOT_LEGACY）
- **防范**:
  1. 批次操作（影子表）的所有 `@Transactional` 必须用 `REQUIRES_NEW`，绝不能用 `REQUIRED` 加入外层事务
  2. 上架时 lotId 必须有兜底值（LOT_LEGACY），不能为 null
  3. 批次操作中 from 和 to 必须独立 try-catch，一方失败不能阻止另一方


## BUG-036: wh_lot_master AUTO_INCREMENT 从1开始，收货创建的第一个 lot_id=1 与 LOT_LEGACY 冲突
- **日期**: 2026-05-09
- **根因**: 建表 SQL 中 `wh_lot_master` 没有指定 `AUTO_INCREMENT = 2`，默认从1开始。上线后第一次收货 `createLot` 返回 `lot_id=1`，通过 `writeLotIdToBatch` 回写到 `wh_inbound_batch.lot_id=1`。后续上架时用这个 `lot_id=1` 操作批次库存，与 LOT_LEGACY 的 `lot_id=1` 混淆
- **影响**: 收货创建的真实批次和 LOT_LEGACY 兜底标识共用 `lot_id=1`，数据混乱，无法区分老库存和新收货
- **修复**: 建表 SQL 加 `AUTO_INCREMENT=2`（`01_create_tables.sql` 和 `10_recreate_lot_tables.sql`），确保正常收货从 `lot_id=2` 开始
- **防范**: 当系统中有保留 ID（如 lot_id=1 = LOT_LEGACY），建表时必须设置 `AUTO_INCREMENT` 跳过保留值


## BUG-037: 拣货时 lot_id 与预占不一致（按 rec_id ASC 盲扣导致扣到 lot_id=1）
- **日期**: 2026-05-12
- **根因**: `LotInventoryTransactionHandler.prepareBatchFromPlan` 中拣货场景走 `batchQueryByLocationAndItems`（按 `rec_id ASC` 排序），lot_id=1（LOT_LEGACY，rec_id 最小）的 `allocated_qty > 0`（来自其他订单预占），被优先扣减。预占时正确分配到 lot_id=3336，但拣货时扣了 lot_id=1
- **影响**: 拣货日志记录的 lot_id 与预占时不一致，批次追踪链路断裂。后续出库消耗记录也是错误的 lot_id
- **修复**:
  1. 拣货场景优先从 `wh_inventory_transaction_log`（Preoccupancy Success）反推该订单预占了哪些批次，按明细精确扣减
  2. 反推不出来时（老数据 lot_id=0），走兜底逻辑：调用 `strategySelector` 选 FIFO/FEFO，用拣货专用查询（lot_id=1 排最后）
  3. 新增 3 个 SQL：`queryOrderPreoccupancyLotDetails`、`queryAllocatedLotsForPickingFIFO`、`queryAllocatedLotsForPickingFEFO`
- **防范**: 拣货场景（isPickingProcess）必须从预占日志反推精确批次，不能盲目按 rec_id 或 FIFO 顺序扣减。预占和拣货是配对操作，扣减的 lot 必须与预占的 lot 一致


## BUG-037b: Problem Inventory TOOL_ADD 转出 EXT 库位时 to 方向无批次记录
- **日期**: 2026-05-30
- **根因**: `addProblemItem` 只写 `pending_items`，不操作聚合库存（EXT 库位上没有 `wh_inventory_transaction` 记录）。`dealProblemItem` 转出时走 `adjustLocation(LOCATION_TOOL_TASK)`，from 方向查 EXT 库位的 lot_inventory 为空，`consumptionDetails` 为空。`prepareBatchToPlan` 中 `!consumptionDetails.isEmpty()` 条件不满足，to 方向跳过。目标 Bin 上没有 lot_inventory 记录
- **影响**: 后续预占该 Bin 时批次系统找不到可用批次，lot_id=0
- **修复**: `prepareBatchToPlan` 中新增 `LOCATION_TOOL_TASK` 场景的兜底逻辑：from 无批次记录时，to 方向用 LOT_LEGACY(lot_id=1) 增加库存（类似盘盈处理）
- **防范**: 当 from 方向的库位可能没有批次记录时（如 EXT、虚拟库位），to 方向必须有兜底策略，不能因为 from 无记录就跳过 to


## BUG-038: prepareBatchRelease 多条 releaseItems 指向同一库位时少释放
- **日期**: 2026-05-30
- **根因**: `prepareBatchRelease` 对每条 releaseItem 独立查询 `queryByLocationAndItem` 获取 lot_inventory 快照。当多条 releaseItems 指向同一 (location, item) 时，每次查询看到相同的快照（allocated_qty=2），都选了同一个 lot 释放。最终 `executeBatchAllocateUpdate` 批量执行时，第3次 WHERE `allocated_qty >= 1` 条件不满足（已被前两次扣为0），少释放了
- **影响**: OOS 取消预占时，3个订单各释放1个，但实际只释放了2个（第3个 SQL WHERE 条件不满足）
- **修复**: `prepareBatchRelease` 中先按 (location, item) 合并 releaseItems 的数量（如3条各1个 → 合并为1条3个），再统一查询分配。避免多次查询同一快照导致重复分配
- **防范**: 批量操作中如果多条记录可能指向同一行，必须先合并再处理，不能逐条独立处理


## BUG-039: Restock Pick/Bin Load 链路 from 方向无批次记录导致 to 方向被跳过
- **日期**: 2026-05-30
- **根因**: Stock 库位（如 D20852）上没有 lot_inventory 记录（初始化遗漏或 Job 反推后 lot_id=1 被清理）。Restock Pick 从 Stock 拣到 RS 库位时，from 方向查不到批次 → consumptionDetails 为空 → to 方向跳过。后续 Restock Bin Load 从 RS 到 Bin 同样跳过。最终 Bin 上没有 lot_inventory 记录，所有后续操作 lot_id=0
- **影响**: B11713 等 Bin 库位上的预占、拣货、出库全部 lot_id=0，无法追踪批次
- **修复**: `prepareBatchToPlan` 中扩大兜底范围，`RESTOCK_PICK` 和 `RESTOCK_PUT_AWAY` 场景 from 无批次记录时 to 方向用 LOT_LEGACY 兜底
- **防范**: 所有"from 方向可能无批次记录"的场景都需要在 `prepareBatchToPlan` 中有兜底逻辑


## BUG-040: wh_order_lot_consumption.order_id 类型错误（varchar(20) 应为 bigint）
- **日期**: 2026-06-23
- **根因**: 设计阶段 spec 数据模型中把 `order_id` 定义为 `varchar(20)`（当作"订单号字符串"），没有对齐 `wh_order_info.order_id` 的实际类型 `bigint`。建表脚本照搬了 design 定义
- **修复**: ALTER TABLE 将 `order_id` 从 `varchar(20)` 改为 `bigint NOT NULL DEFAULT 0`，同步删除重建涉及 order_id 的索引（`idx_order_id`、`idx_order_item`）。Java 全链路 String → Long
- **防范**: 新建表时，关联字段的类型必须与被关联表的字段类型完全一致（尤其是 bigint vs varchar）。设计评审时必须核对已有表的字段类型

## BUG-041: createLot 事务传播 REQUIRED 导致 Redis 超时时收货整体回滚
- **日期**: 2026-06-24
- **根因**: `LotServiceImpl.createLot()` 使用 `@Transactional(REQUIRED)`，加入外层 `receiveConfirm()` 的事务。`generateLotNo()` 中 Redis 超时抛异常 → Spring 标记外层事务 rollback-only → `createLotForReceiving()` 虽然 catch 了异常返回 null，但事务提交时仍报 `UnexpectedRollbackException`，整个收货回滚
- **修复**: 
  1. `createLot()` 事务传播改为 `REQUIRES_NEW`（独立事务，失败不污染外层）
  2. `generateLotNo()` 增加本地 `AtomicLong` 降级（从 900000 起步，与 Redis 正常序号完全隔离），Redis 失败时不再抛异常
- **防范**: 批次操作（影子表）的所有 `@Transactional` 必须用 `REQUIRES_NEW`；外部资源调用（Redis/HTTP）必须有降级方案，不能让外部资源故障传导到核心业务事务


## BUG-040: Cancel Preoccupancy 日志 reference_id 只记录第一个订单号，其他订单无日志
- **日期**: 2026-05-30
- **根因**: `batchCancelPreoccupancy` 中 Java 层写日志时，`reference_id` 用 `orderNumberSet.iterator().next()` 只取了集合中的第一个订单号。`prepareBatchRelease` 合并了所有订单的释放量，`lotUpdates` 中无法区分哪条属于哪个订单。导致所有日志都记录了同一个订单号，其他订单没有 Cancel 日志
- **影响**: 3个订单取消预占时，只有第一个订单有 Cancel 日志，其他两个订单无记录
- **修复**: 日志写入改为遍历 `orderNumberSet`，为每个订单分别查询预占日志（`queryPreoccupancySuccessLogs`），按订单维度记录日志：reference_id=该订单号，quantity=该订单的释放量，lot_id=从释放结果中获取
- **防范**: 批量操作的日志必须按业务维度（订单/调拨单）分别记录，不能用合并后的结果统一记录


## BUG-042: Cancel Preoccupancy 日志 lot_id 不精确 + before_quantity/before_allocated 为 null
- **日期**: 2026-06-24
- **根因**: BUG-040 修复时改为按订单遍历写入日志，但 lot_id 从 `lotQueue.peek()` 取值（只看不取）。`prepareBatchRelease` 按 `allocated_qty` 从大到小排序释放，peek 始终取队列头部的第一个 lot。多个订单预占了不同 lot 时（如 610367814→lot 12255, 610367815→lot 12256），Cancel 日志全部记录了 lot_id=12255。同时 `InventoryTransactionLog` 的 `before_quantity` 和 `before_allocated` 未设置，写入 DB 为 null
- **影响**: Cancel Preoccupancy 日志中 lot_id 与预占时不一致，无法追溯订单实际释放的批次；before 快照缺失无法审计
- **修复**: 
  1. 新增 `LocationDao.batchQueryPreoccupancyLotLogs(orderIds, warehouseNumber)` 批量查询方法，一次 IN 查询所有订单的预占日志（`reference_type IN ('Preoccupancy Success', 'Secondary Preoccupancy')`），内存中按 `(orderId|item|location)` 分组
  2. Cancel 日志的 lot_id 直接从预占日志中获取（精确对应），不再从 `prepareBatchRelease` 释放结果推导
  3. 兜底：老数据预占日志中 lot_id=0（不满足 lot_id>0），此时 Cancel 日志 lot_id 记为 0
  4. 在 `executeBatchAllocateUpdate` 之前查询聚合库存快照，设置 `before_quantity` 和 `before_allocated`
  5. `batchCancelPreoccupancy` 和 `singleOrderBatchCancelPreoccupancy` 两处同步修改
- **防范**: 
  - 取消预占日志的 lot_id 必须从预占成功日志反查（`reference_type='Preoccupancy Success'`），不能从释放结果推导——释放是合并后的结果，丢失了订单维度信息
  - 所有写入 `wh_inventory_transaction_log` 的日志都必须设置 `before_quantity` 和 `before_allocated`
  - 预占和取消预占是配对操作，取消时的日志字段（lot_id、quantity）必须与预占时精确对应


## BUG-043: markItemBubble 中 market_price null 自动拆箱 NPE
- **日期**: 2026-07-25
- **根因**: `CubiscanService.markItemBubble()` 中 `double msrp = item.getMarket_price()` 将 `Double`（包装类）自动拆箱为 `double`（基本类型）。当 SQL 查回来的 `market_price` 为 NULL 时，自动拆箱触发 NPE
- **修复**: 改为 `double msrp = item.getMarket_price() != null ? item.getMarket_price() : 0.0D`
- **防范**: 凡是从数据库查回来的 `Double`/`Integer`/`Long` 包装类字段，在直接赋值给基本类型前必须做 null 检查；或统一在 SQL 中用 `IFNULL(field, 0)` 保证非空

## BUG-044: MQ 消费线程 siteCode 恒为 us 导致 CA 站订单 order_qty 被重复归还
- **日期**: 2026-08-06
- **现象**: 101 仓（ON，CA 站）商品 `order_qty` 被扣成负数，如 item 1021199331 达 -8。近两个月 101 仓 11 单 `WMSCancelOrder` **全部**伴随 `soCancel`（100%），而 001/002 共 441 单一次都没有
- **完整影响面**（按 `order_qty` 净和 < 0 统计，101 仓 order_status=4/shipping_status=8）: **共 15 单多扣 88 个**，分属两条独立路径：
  - `CreateSO + soCancel + WMSCancelOrder` — **11 单 -64**，即本 BUG 的路径（227443914 -19、227434046 -13、227054792 -11、227430313 -8、227397142 -7、227122557/619/685/719/808/931 各 -1）
  - `CreateSO + soCancel + soOutStock` — **4 单 -24**，货已出库释放过 order_qty，之后整单取消又释放一次（227426174 -16、227277858 -6、227426289 -1、227441492 -1）。**本次 siteCode 修复不覆盖此路径**，根因在 central-inventory-service `soCancelAction` 的幂等只查 `operation_type='soCancel'`，见待优化项
- **无关对照**: `pay_status=4`（`PARTIAL_CANCEL_ORDER` 部分取消/缺发）197 单本身不是本 BUG 的产物。`partialCancelOrder()` 方法体内不调用 `sendMQToInventory()`，只改订单状态、清缓存、写流程记录，`order_qty` 仅由 `soOutStock` 扣一次，实测 175 单收支全部配平
- **available_qty 同步被虚增（修数据必须一起处理）**: 误发的 `soCancel` 除了多扣 `order_qty`，还会多加 `available_qty`（`soCancelAction4DB` 是 `-order_qty` + `+available_qty` 成对执行）。11 单中 **32 个 item 被 `soCancel` 误加，虚增合计 21 个**，虚增量最大：1021199331 +7、1157110971/1155037621/1023871331/1017174481 各 +2。注意 `WMSCancelOrder + rmaReturn` 那一对是正常配对，不算虚增
- **业务传导链（超卖 → 缺发）**:
  ```
  场景3 误发 soCancel → available_qty 虚增 → 前台超卖 → 打包时无货 → OOS 缺发
                     → OOS 分支执行 AVAILABLE_QTY +1 归还 → 虚假库存被还回去 → 继续超卖
  ```
  `outStockAction` 的 OOS 分支是 `ORDER_QTY -1 / AVAILABLE_QTY +1`，它假设货真实存在，因此会把虚增延续下去（这是固有设计非新 BUG）。实测 1021199331 虚增 7 个却产生 27 单缺发，即虚增在缺发链条中被反复复用
- **缺发归因定量**（101 仓 484 单）: 时序初筛有 81 单 / 144 个缺发落在受影响 item 且发生在虚增之后，但按 `LEAST(虚增量, 缺发量)` 定量后 **最多只能归因 21 个缺发量、涉及 11 个 item**，约占该仓缺发总量（196）的 10.7%。超出部分（如 1157110971 虚增 2 却缺发 40）必然另有原因（真实库存不准、盘点差异、拣货找不到货等），**不可全部归因于本 BUG**
- **数据修复状态（2026-08-06 核对完成，⚠️ 禁止二次修复）**: 库存偏差已由 Jason.Huo 于 08-04 18:33/18:59、08-05 17:10/20:58 分四批通过 `rest interface` 人工修完（每批均为 `available_qty -N` + `order_qty +N` 成对操作）。逐 item 核对结果：
  - `order_qty` 应补 88 / 已补 88，**缺口 0**
  - `available_qty` 应扣 88 / 已扣 85，**45 of 47 个 item 完全修复**
  - 遗留 2 个（1017215531 差 1、1155037041 差 2）判定为**不应再扣**：当前 `available_qty` 已是 0，再扣变负数；且两者 `rmaReturn=0`（实物走损耗路径未回可售位），与后台实物对账前后台均为 0，已一致
  - **此时若再执行「order_qty + N」修复脚本会造成二次错误**（order_qty 虚高、available 虚低）
  - 完整核对过程、45 个已修 item 清单、5 个可复用巡检 SQL 见 `wms-cloud-service/docs/101仓order_qty重复扣减_数据核对报告.md`
  - 逐单逐 item 明细数据（8 个分表：订单15单 / 订单商品59行 / 商品核对47项 / 归因33项 / 缺发影响90行 / 其他异常 / 巡检SQL）见 Google Sheets：<https://docs.google.com/spreadsheets/d/1kIEtbftfIs3EsKFzQF-zRn_euTlZCJ9TmHVhr2ZYUx4>
- **排查 SQL 写法陷阱**: 判定重复扣减必须用 `GROUP BY operation_ref_id HAVING SUM(change_qty) < 0`，**不能用 `EXISTS(WMSCancelOrder) AND EXISTS(soCancel)` 双条件**——后者会漏掉 `soCancel + soOutStock` 路径的 4 单
- **根因**: 
  1. 上游 MQ 消息头 `site_code` 恒为 `us`，`RabbitmqConfig.siteCodeAdvice()` 只能照单接收
  2. `VendorService.getSelfVendorId()` 中 `return vendorId != null ? vendorId : 0`，站点不对时静默兜底为 US 的 `0`（注释已写明 us=0, ca=5000）
  3. `OrderInfoMapper.queryOrderInfo` 带 `AND xoi.vendor_id = #{vendor_id}` 条件，CA 站订单 `vendor_id=5000`，用 `0` 去查 `wh_order_info` 必然查不到
  4. `CancelOrderService.cancelOrder()` 中 `needSaveCache = true`（wh 库查不到 → 退化查 master 库）
  5. 命中"场景3"：`needSaveCache && order_status==4 && shipping_status==8 && pay_status==3` → `sendMQToInventory()` 发 `so_cancel` 归还 `order_qty`
  6. 但货已拣到 Tote，打包台后续走 `/packing/cancel` → `packingPending4WH` → `WMSCancelOrder` 再归还一次 → **order_qty 双扣**，`available_qty` 同时被 `soCancel` 和 `rmaReturn` 各加一次而虚增
- **US 站为何幸免**: 001/002 订单 `vendor_id=0`，恰好与兜底值相同，查询正常返回，`needSaveCache=false`，场景3 不触发
- **修复**: 
  1. 新增 `SiteCodeAligner.alignByWarehouse(scene, warehouseNumber)`（`wms-cloud-service/common`），按仓库编号纠正当前线程站点，映射统一取 `WarehouseProvider`（001/002→us，101→ca），未配置的仓库编号（集运仓 9000 系列）保留上游原值
  2. `CancelOrderReceiver.process()` 在取到 `warehouseNumber` 后立即调用
  3. `DownOrderReceiver.process()` 同步接入（down 单频率高，便于观察 `site_code corrected` 日志验证）
  4. `SiteCodeAlignerTest` 11 个用例覆盖三仓映射、集运仓保留原值、仓库号 null/空
- **防范**: 
  1. **MQ / 定时任务 / 线程池等无 HTTP 请求上下文的入口，必须显式建立 siteCode 上下文**，不能依赖 ThreadLocal 残留值或兜底默认值
  2. **多站点过滤条件（vendor_id / site_code）取值失败必须显性化**，禁止静默 fallback 到某站点的值——"查不到数据"和"查错站点"语义完全不同，混淆后会被上层误判为业务状态
  3. 业务判断禁止用"查不到记录"代理"业务状态"（此处用查不到订单代理"订单未下发到仓库"），状态判断要查明确的状态字段（如 `wh_order_pool` 是否存在）
  4. 需要按仓库定站点时直接复用 `WarehouseProvider.getWarehouseMap()`，禁止另写 if-else 或硬编码仓库号
  5. 排查跨站点问题时，先对比各仓的数据分布（本次正是通过 001/002 零命中、101 百分之百命中定位到 vendor_id 差异）

## BUG-045: BatchUpdateArrivalStatusHandler Job ClassCastException（Long cannot be cast to Integer）
- **日期**: 2026-08-08
- **根因**: `ShippingService.batchUpdateArrivalStatus()` 中对 `resultType="map"` 查询结果做了硬强转 `(Integer)e.get("cancel")`。SQL 中 `IFNULL(pool.cancel, 0) cancel` 经 MySQL JDBC 驱动推断为 `Long`（IFNULL 函数包裹后返回 BIGINT），导致运行时 `java.lang.Long cannot be cast to java.lang.Integer`
- **触发场景**: xxl-job 每半小时执行一次的 BatchUpdateArrivalStatusHandler，从 `wh_order_pool` 分批扫描未到货订单
- **修复**: `(Integer)e.get("cancel")` 改为 `((Number)e.get("cancel")).intValue()`，通过 `Number` 父类接口兼容 JDBC 返回 Long 或 Integer 的情况
- **防范**: 
  1. MyBatis `resultType="map"` 查询中，禁止对数字字段做硬强转 `(Integer)` / `(Long)`
  2. MySQL JDBC 类型推断规则：普通 INT 列 → Integer；BIGINT 列 → Long；被 `IFNULL/COALESCE/CASE/聚合函数` 包裹的任何整数列 → Long
  3. 安全写法：`((Number)map.get("field")).intValue()` 或先 `toString()` 再 `Integer.parseInt()`
  4. 优先改用 resultType 指向明确的 DTO/Entity 类，避免 Map 强转问题
