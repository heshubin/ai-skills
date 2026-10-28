---
name: wms-lot-tracking-guide
description: 修改批次追踪相关代码、排查批次库存问题、为新业务场景增加批次支持时使用。触发词：批次, lot, lot_id, 批次追踪, lot tracking, FIFO, FEFO, 批次库存, 批次消耗
---
# WMS 批次追踪（Lot Tracking）开发指南

> 当修改批次追踪相关代码、排查批次库存问题、或新增业务场景的批次支持时使用。
> 触发词：批次, lot, lot_id, 批次追踪, lot tracking, FIFO, FEFO, 批次库存, 批次消耗

## 1. 架构概览

批次追踪采用"影子表并行写入"策略，在 `LocationService.adjustLocation()` 调用链中插入批次处理，不修改原有聚合库存逻辑。

```
adjustLocation()
  ├── checkLocation()                    — 原有逻辑不变
  ├── dealInventoryTransaction()         — 原有聚合库存逻辑不变
  ├── dealLotInventoryTransaction()      — 【批次】批次库存处理
  ├── saveInventoryTransactionLog()      — 【改造】日志中记录 lot_id
  └── transactionDealService.adjustLocationTrans() — 统一事务提交
```

## 2. 核心文件清单

### 新增文件
| 文件 | 职责 |
|------|------|
| `service/lot/LotService.java` | 批次管理接口（创建、查询、状态管理） |
| `service/lot/LotServiceImpl.java` | 批次管理实现（Redis生成lot_no、createLot） |
| `service/lot/LotInventoryService.java` | 批次库存接口（增减、预占、转移、消耗记录） |
| `service/lot/LotInventoryServiceImpl.java` | 批次库存实现（FIFO/FEFO扣减、跨批次扣减） |
| `service/lot/LotStrategySelector.java` | 策略选择器（根据商品保质期选FIFO/FEFO） |
| `service/lot/LotConsumptionStrategy.java` | 策略枚举（FIFO/FEFO） |
| `service/lot/LotInventoryTransactionHandler.java` | 批次交易处理器（核心调度，含ADJUST特殊处理） |
| `rest/LotQueryRestImpl.java` | 4个查询接口 |
| `dao/wms/LotMasterDao.java` | 批次主表DAO |
| `dao/wms/LotInventoryDao.java` | 批次库存DAO |
| `dao/wms/OrderLotConsumptionDao.java` | 订单消耗DAO |
| `mapper/LotMasterMapper.xml` | 批次主表SQL（驼峰命名映射） |
| `mapper/LotInventoryMapper.xml` | 批次库存SQL（下划线命名映射，含FIFO/FEFO排序） |
| `mapper/OrderLotConsumptionMapper.xml` | 订单消耗SQL（驼峰命名映射） |

### 改造文件
| 文件 | 改造内容 |
|------|---------|
| `LocationService.java` | 新增 dealLotInventoryTransaction() + 改造 saveInventoryTransactionLog() |
| `ReceiveService.java` | 收货时创建批次（determineSourceType + createLotForReceiving） |
| `PutawayServiceHelper.java` | 上架时关联批次（queryLotIdBySourceNumber） |
| `TSPickingService.java` | 调拨预占批次库存（allocateLotInventory） |
| `AdjustService.java` | 损益传递lotId到LocationItemRequest |
| `LocationMapper.xml` | saveInventoryTransactionLog 新增 lot_id 字段（`#{item.lotId}`） |
| `AdjustLocationRequest.java` | 新增 lotId + itemLotConsumptionMap |
| `LocationItemRequest.java` | 新增 lotId |
| `InventoryTransactionLog.java` | 新增 lotId |
| `AdjustItem.java` | 新增 lotId（盘盈时操作员可指定） |

## 3. 关键设计决策

### 3.1 实体类命名规则
- `LotMaster`：**驼峰命名**（lotId, lotNo, itemNumber）— MyBatis resultMap 映射
- `LotInventory`：**下划线命名**（lot_id, item_number）— 与项目中其他老实体类风格一致
- `OrderLotConsumption`：**驼峰命名** — MyBatis resultMap 映射
- ⚠️ **修改 Mapper XML 时注意对应实体类的命名风格**，`#{lotId}` vs `#{lot_id}`

### 3.2 FIFO/FEFO SQL 排序
```sql
-- FIFO：LOT_LEGACY(lot_id=1) 排最后
ORDER BY CASE WHEN li.lot_id = 1 THEN 1 ELSE 0 END ASC, lm.receive_time ASC

-- FEFO：expire_dtm=0 排最后
ORDER BY CASE WHEN lm.expire_dtm = 0 THEN 1 ELSE 0 END ASC, lm.expire_dtm ASC
```

### 3.3 ADJUST 特殊处理
ADJUST 只走 to 方向（from=NONE 被跳过），根据 `available_qty` 正负判断：
- `> 0`（盘盈）：指定 lotId 则用指定的，否则创建 ADJUST 批次
- `< 0`（盘亏）：`Math.abs(available_qty)` 按策略扣减
- `= 0`：跳过

### 3.4 收货场景兼容
收货时 lot_id 为空的处理：
- 已改造的入口（ReceiveService）：保证 lotId 有值
- 未改造的入口（OutboundService 负采购等）：归入 LOT_LEGACY（lot_id=1）

### 3.5 拣货场景（7个枚举）
以下 actionType 在 from 方向走 `allocated_qty` 扣减：
BATCH_PICKING(21), B2B_PICKING(22), PUT_WALL_PICKING_TOTE(23), SINGLE_ORDER_OVERSIZE_PICKING_TOTE(25), REPLENISH_PICK(13), TRANSSHIPMENT_PICKING_BIN(124), TRANSSHIPMENT_PICKING_STOCK(125)

### 3.6 出库场景（5个枚举）
以下 actionType 触发订单批次消耗记录：
SHIPPING_SYSTEM_B2C(31), SHIPPING_SYSTEM_B2B(32), SHIPPING_SYSTEM_SLOT(33), SHIPPING_SYSTEM_REPLENISH(34), SHIPPING_SYSTEM_PALLET(50)

## 4. 常见踩坑点

### 4.1 MyBatis 字段映射
- `LocationMapper.xml` 中日志写入用 `#{item.lotId}`（驼峰），不是 `#{item.lot_id}`
- `OrderLotConsumptionMapper.xml` 用驼峰映射（`#{orderId}`），不是下划线
- `LotInventoryMapper.xml` 用下划线映射（`#{warehouse_number}`），与实体类一致

### 4.2 跨服务同步
wms-cloud-api 和 central-packing-api 中以下类需要保持同步：
- `AdjustLocationRequest`（lotId 字段）
- `LocationItemRequest`（lotId 字段）
- `AdjustItem`（lotId 字段）
- `InventoryTransactionLog`（lotId 字段）

### 4.3 SQL 安全
- 所有 Mapper XML 必须使用 `#{}` 参数化查询
- 禁止使用 `${}` 动态拼接
- `decreaseQuantity` 必须有 `AND quantity >= #{quantity}` 防止超扣
- `updateAllocatedQty` 必须有 `AND allocated_qty + #{allocatedQty} >= 0` 防止负数

## 5. 待优化项（按优先级）

| ID | 问题 | 优先级 |
|----|------|--------|
| OPT-00 | 批次写入与聚合写入不在同一事务 | 高 |
| OPT-01 | 并发重试机制（3次，100ms间隔） | 高 |
| OPT-02 | increaseLotInventory 先查后插并发安全 | 高 |
| OPT-03 | 取消订单精确回补（查询原始消耗批次） | 中 |
| OPT-04 | 退货入库精确回补 | 中 |
| OPT-05 | 供应商退货批次关联 | 中 |
| OPT-06 | LotStrategySelector 查询 storage_form | 中 |
| OPT-10 | 调拨入库创建新批次 | 低 |
| OPT-13 | OutboundService 负采购创建批次 | 高 |

详细说明见 `wms-cloud-service/docs/批次追踪_待优化项.md`

## 6. 测试

- 测试框架：Spock（Groovy）
- 测试文件位置：`wms-cloud-service/src/test/java/com/yamibuy/wms/cloud/service/lot/`
- 7个测试类，147个测试用例
- 运行命令：
```powershell
D:\maven\apache-maven-3.9.11\bin\mvn.cmd test -pl wms-cloud-service -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" "-Dtest=com.yamibuy.wms.cloud.service.lot.LotServiceTest,com.yamibuy.wms.cloud.service.lot.LotInventoryServiceTest,com.yamibuy.wms.cloud.service.lot.LotStrategySelectorTest,com.yamibuy.wms.cloud.service.lot.LotEntityAndDaoTest,com.yamibuy.wms.cloud.service.lot.RequirementsCoverageTest,com.yamibuy.wms.cloud.service.lot.LotInventoryTransactionHandlerTest,com.yamibuy.wms.cloud.service.lot.LotE2EFlowTest"
```

## 7. 相关文档

- 方案介绍：`kiroWP/docs/库存批次追踪方案介绍.md`
- 需求文档：`kiroWP/.kiro/specs/inventory-lot-tracking/requirements.md`
- 设计文档：`kiroWP/.kiro/specs/inventory-lot-tracking/design.md`
- 任务清单：`kiroWP/.kiro/specs/inventory-lot-tracking/tasks.md`
- DDL脚本：`wms-cloud-service/docs/20260408_inventory_lot_tracking_ddl.sql`
- 迁移脚本：`wms-cloud-service/docs/20260408_lot_legacy_migration.sql`
- 待优化项：`wms-cloud-service/docs/批次追踪_待优化项.md`
