---
inclusion: auto
name: wms_inventory_sync_rule
description: 修改 wh_inventory_transaction 或 wh_lot_inventory、选择 FIFO/FEFO/Allocated 查询方法、处理库存两表同步时使用。触发词：库存同步, wh_inventory_transaction, wh_lot_inventory, allocated_qty, FIFO, FEFO, queryAvailableLots, queryAllocatedLots, 预占, 拣货
---

# WMS 库存同步规则（核心）

## 铁律：凡是 wh_inventory_transaction 变化的地方，wh_lot_inventory 必须同步

任何修改 `wh_inventory_transaction` 表的 `quantity` 或 `allocated_qty` 的代码入口，都必须同步修改 `wh_lot_inventory` 表的对应字段。

## 两套库存的字段对应关系

| 阶段 | wh_inventory_transaction | wh_lot_inventory | 说明 |
|------|-------------------------|-----------------|------|
| 初始 | qty=20, alloc=0 | qty=20, alloc=0 | |
| 预占后 | qty=0, alloc=20 | qty=0, alloc=20 | 两套都是 qty 减、alloc 加 |
| 拣货后 | qty=0, alloc=0 | qty=0, alloc=0 | 两套都是只减 alloc，qty 不动 |

## SQL 方法职责对照表（严格遵守）

### 查询方法
| SQL | WHERE 条件 | 使用场景 |
|-----|-----------|---------|
| `queryAvailableLotsFIFO/FEFO` | `quantity > 0` | 普通扣减（盘亏、移动）、预占分配 |
| `queryAllocatedLotsFIFO/FEFO` | `allocated_qty > 0` | 拣货、调拨拣货（isAllocated=true） |

**排序策略**（LEFT JOIN wh_lot_master，lot_id=1 没有 master 记录也能查到）：
- FIFO：lot_id=1（LOT_LEGACY）排最前 → receive_time ASC → lot_id ASC（优先消耗老库存）
- FEFO：expire_dtm=0 排最前 → expire_dtm ASC → lot_id ASC（优先消耗无过期时间的老库存）

### 更新方法
| SQL | 操作 | 使用场景 |
|-----|------|---------|
| `updateAllocatedQty` | qty 减, alloc 加（正数=预占）；qty 加, alloc 减（负数=取消预占） | 单条预占/取消预占 |
| `batchUpdateAllocatedQty` | 同上，批量版 | 批量预占/取消预占（savePreoccupancyInfo） |
| `decreaseAllocatedQtyOnly` | **只减 alloc，qty 不动** | 拣货/调拨拣货（因为预占时已减过 qty） |
| `decreaseQuantity` | **只减 qty** | 普通扣减（盘亏、库存移动） |
| `increaseQuantity` | 只加 qty | 收货、上架等增加场景 |
| `insertOrUpdate` | INSERT ON DUPLICATE KEY UPDATE qty 累加 | 批次库存增加（并发安全） |

### 禁止混用
- **禁止**在拣货场景用 `updateAllocatedQty` 传负数 — 会导致 qty 被加回去
- **禁止**在拣货场景用 `decreaseQuantity` — qty 预占时已减过，再减会变负数
- 拣货场景**只能用** `decreaseAllocatedQtyOnly`

## 日志 quantity 正负号规则

`wh_inventory_transaction_log.quantity` 必须保持与系统原有逻辑一致的正负号：

| 场景 | quantity 符号 | 说明 |
|------|-------------|------|
| 预占 Preoccupancy Success | **负数** | `lotAllocQty * -1` |
| 二次预占 Secondary Preoccupancy | **负数** | `avaliableQty * -1` |
| 盘亏 adjust | **负数** | `detail.getQuantity() * sign`，sign 由 `available_qty < 0` 决定 |
| 盘盈 adjust | **正数** | 同上，`available_qty > 0` 时 sign=1 |
| 收货/上架/补货/移动 | **正数** | 正常转移 |
| Receiving return po/sp | **负数** | 错收冲减（独立逻辑，不走 adjustLocation） |

### 批次日志拆分时保持符号
`LocationService.saveInventoryTransactionLog()` 场景A 中，批次消耗明细的 quantity 永远是正数，需要乘以 `sign` 保持原始符号：
```java
int sign = item.getAvailable_qty() < 0 ? -1 : 1;
log.setQuantity(detail.getQuantity() * sign);
```

## 库存转移日志必须带 lot_id（铁律）

**禁止 lotId=null 写入 `wh_inventory_transaction_log`。** 每条库存转移日志都必须带上 lot_id。

### 实现要求
- 所有写入日志的入口，必须在写入前完成批次分配（`prepareBatchAllocate`），拿到 lotId 后按 lot 拆分日志
- `batchInsertInventoryLog` SQL 中用 `IFNULL(#{log.lotId}, 0)` 兜底，但这只是防御性编程，不能依赖
- 如果走到 IFNULL 兜底（lotId=0），说明有遗漏，必须排查修复

### 已确认的写入入口
| SQL | 调用方 | lot_id 来源 | 状态 |
|-----|--------|-----------|------|
| `saveInventoryTransactionLog` | `adjustLocationTrans` | Java 层 `dealLotInventoryTransaction` 设置 | ✅ |
| `batchInsertInventoryLog` | `savePreoccupancyInfo`（首次预占） | Java 层 `prepareBatchAllocate` 按 lot 拆分 | ✅ |
| `batchInsertInventoryLog` | `itemPreoccupancy`（二次预占） | Java 层 `prepareBatchAllocate` 按 lot 拆分 | ✅ |
| `batchCancelPreoccupancy` | `PreoccupancyDao`（批量取消预占） | SQL LEFT JOIN `wh_lot_inventory`（allocated_qty > 0） | ✅ |
| `singleOrderCancelPreoccupancy` | `PreoccupancyDao`（单品OOS取消预占） | SQL LEFT JOIN `wh_lot_inventory`（allocated_qty > 0） | ✅ |
| `insertInventoryLog` | `ReceiveReturnDao`（错收冲减） | SQL IFNULL(#{lotId}, 0) 兜底 | ✅ |
| `insertTransactionLog` | `TSInboundMapper`（调拨入库） | SQL LEFT JOIN `wh_lot_inventory`（quantity > 0） | ✅ |
| 取消预占日志×2 | `TSPickingMapper`（调拨取消预占） | SQL LEFT JOIN `wh_lot_inventory`（allocated_qty > 0） | ✅ |
| `insertTransactionLog` | `TSTruckMapper`（调拨出库） | SQL LEFT JOIN `wh_lot_inventory`（quantity > 0） | ✅ |

### 新增库存操作入口时的检查清单
1. 是否写入了 `wh_inventory_transaction_log`？如果是，lot_id 必须有值
2. Java 层：是否调用了 `prepareBatchAllocate` 获取批次分配方案？是否按 lot 拆分了日志？
3. SQL 层：是否 LEFT JOIN 了 `wh_lot_inventory` 获取 lot_id？
4. `before_quantity` 和 `before_allocated` 是否逐条累计？
5. quantity 的正负号是否与系统原有逻辑一致？

## 库存变更的所有入口

### 1. LocationService.adjustLocation() — 库位调整（已改造）
- 通过 `dealLotInventoryTransaction()` 同步批次库存
- 覆盖：收货、上架、补货、拣货、出库、损益、通用工具转移等 70+ 种 actionType

### 2. PreoccupancyService — 订单预占（核心预占入口）
- `preoccupancy()` → `finishPreoccupancy()` → `transactionDealService.savePreoccupancyInfo()` — 已改造
- `itemPreoccupancy()` — 二次预占，已改造
- `batchCancelPreoccupancy()` — 取消预占，已改造
- `singleOrderBatchCancelPreoccupancy()` — 单品OOS取消预占，已改造

### 3. TSPickingService — 调拨预占（非核心）
- `preoccupancySuccess()` — 调拨预占，已改造

### 4. PreoccupancyDao.batchCancelPreoccupancy() — 批量取消预占SQL
- 直接操作聚合库存的复杂SQL，批次释放在调用方处理

### 5. ReceiveReturnService — 错收冲减（已改造）
- `returnRECGReceive()` — 好货冲减，已增加 `lotInventoryService.decreaseLotInventory` 同步
- `returnWhInventoryData()` — 坏货冲减，已增加 `lotInventoryService.decreaseLotInventory` 同步

### 6. 调拨全链路（6步，全部已改造）

| 步骤 | 库位变化 | 仓库 | 批次同步方式 | 代码位置 |
|------|---------|------|-----------|---------|
| TS预占 | Stock/Bin: alloc+ | 001 | `prepareBatchAllocate` + `executeBatchAllocateUpdate` | TSPickingService.preoccupancySuccess |
| TS Pick | Stock/Bin: alloc-; Pallet(43): qty+ | 001 | `dealLotInventoryTransaction`（TRANSSHIPMENT_PICKING） | LocationService.adjustLocation |
| TS QC | Pallet(43): qty-; TSOZ001(47): qty+ | 001 | `dealLotInventoryTransaction`（QC_CONFIRM） | LocationService.adjustLocation |
| Truck manage | TSOZ001(47): qty-; TSOZ002(47): qty+ | 001→002 | `transferLotInventory` | TSTruckService.completeLoading |
| TS Receive | TSOZ002(47): qty-; TRANSIN(44): qty+ | 002 | `transferLotInventory` | TSInboundService.tsInbound |
| TS put away | TRANSIN(44): qty-; Stock/Bin: qty+ | 002 | `dealLotInventoryTransaction`（TS_PUT_AWAY） | LocationService.adjustLocation |

## 批次库存（Lot Inventory）核心方法速查

### Service 层关键方法

| 方法 | 所在类 | 作用 | 使用场景 |
|------|--------|------|---------|
| `dealLotInventoryTransaction` | LotInventoryTransactionHandler | 根据 actionType 自动处理批次库存（from扣减+to增加） | adjustLocation 链路（70+种 actionType） |
| `prepareBatchAllocate` | LotInventoryServiceImpl | 按 FIFO/FEFO 计算批次预占分配方案（纯计算，不写DB） | 预占场景 |
| `prepareBatchRelease` | LotInventoryServiceImpl | 计算批次释放方案（纯计算，不写DB） | 取消预占场景 |
| `executeBatchAllocateUpdate` | LotInventoryServiceImpl | 批量执行预占/释放的DB写入 | 预占/取消预占场景 |
| `transferLotInventory` | LotInventoryServiceImpl | 从源库位按 FIFO 扣减，在目标库位增加对应批次 | 调拨 Truck manage / TS Receive |
| `decreaseLotInventory(isAllocated=false)` | LotInventoryServiceImpl | 按 FIFO 从 quantity 中扣减 | 盘亏、库存移动、错收冲减 |
| `decreaseLotInventory(isAllocated=true)` | LotInventoryServiceImpl | 按 FIFO 从 allocated_qty 中扣减 | 拣货、调拨拣货 |
| `increaseLotInventory` | LotInventoryServiceImpl | 增加批次库存（INSERT ON DUPLICATE KEY UPDATE） | 收货、上架、盘盈、转移目标 |
| `allocateLotInventory` | LotInventoryServiceImpl | 单条预占（qty减 alloc加） | 调拨预占 |

### DAO/SQL 层关键方法（严格按场景使用，禁止混用）

| SQL 方法 | 所在 Mapper | 操作 | 使用场景 | 禁止用于 |
|---------|------------|------|---------|---------|
| `queryAvailableLotsFIFO/FEFO` | LotInventoryMapper | 查 `quantity > 0` 的批次 | 普通扣减（盘亏、移动）、预占分配 | ❌ 拣货（预占后 qty=0 查不到） |
| `queryAllocatedLotsFIFO/FEFO` | LotInventoryMapper | 查 `allocated_qty > 0` 的批次 | 拣货、调拨拣货 | ❌ 普通扣减、预占 |
| `updateAllocatedQty` | LotInventoryMapper | qty 减 + alloc 加（正数=预占，负数=取消预占） | 预占、取消预占 | ❌ 拣货（会导致 qty 被加回） |
| `batchUpdateAllocatedQty` | LotInventoryMapper | 同上，批量版 | 批量预占/取消预占 | ❌ 拣货 |
| `decreaseAllocatedQtyOnly` | LotInventoryMapper | 只减 alloc，qty 不动 | 拣货、调拨拣货 | ❌ 预占、普通扣减 |
| `decreaseQuantity` | LotInventoryMapper | 只减 qty | 普通扣减（盘亏、移动） | ❌ 拣货（qty 预占时已减过） |
| `insertOrUpdate` | LotInventoryMapper | INSERT ON DUPLICATE KEY UPDATE qty 累加 | 批次库存增加 | — |

## 前台库存分析注意事项

### 可用的表

| 表 | 说明 |
|----|------|
| `yamibuy_inventory.inventory_master` | **前台库存主表**，存储每个 item_number 的 accounting_qty / available_qty / order_qty / allocated_qty 等字段 |
| `yamibuy_inventory.inventory_log` | **前台库存变更流水**，记录每次库存变化，按 item_number + in_dtm 索引 |
| `yamibuy_inventory.inventory_log_2024` 等 | 历史年份分表 |
| `yamibuy_wh.wh_inventory_transaction_log_2025` 等 | **WMS 内部库位级别库存流水**，记录 reference_id / reference_type / before_quantity 等 |
| `yamibuy_wh.wh_preoccupancy_info` | WMS 预占明细 |
| `yamibuy_wh.wh_preoccupancy_log` | WMS 预占日志 |

### ❌ 禁止使用的表/字段

| 表/字段 | 原因 |
|---------|------|
| `yamibuy_wh.wh_inventory_master` | **该表未被系统实际使用**，数据不准确，禁止用于任何前台库存分析 |
| `*.accounting_qty`（inventory_master / inventory_log 中的该列） | 系统未正确维护，数值不可信，分析时忽略此列及 change_feild='accounting_qty' 的流水行 |

### 关键字段说明（inventory_master）

| 字段 | 含义 |
|------|------|
| `available_qty` | 可售库存（前台展示）|
| `order_qty` | 已被订单占用但未出库 |
| `allocated_qty` | 被手工锁定/分配的库存（InvTransfer 转入）|
| `accounting_qty` | 财务账面库存 |
| `purchase_qty` | PO 采购中的库存（POAudit 后加，POInStock 后减）|
| `receive_qty` | 已收货待上架库存（POInStock 后加，POPutaway 后减）|

### inventory_log 常见 operation_type

| operation_type | 说明 |
|---------------|------|
| `POAudit` | PO 审核，purchase_qty 增加 |
| `POInStock` | 收货入库，receive_qty+、accounting_qty+、purchase_qty- |
| `POPutaway` | 上架，available_qty+、receive_qty- |
| `PreOccupyOrderSO` | 订单预占，available_qty- |
| `CreateSO` | 下单，order_qty+、pre_qty- |
| `soOutStock` | 出库，order_qty-（OOS时 available_qty+）|
| `CancelPreOccupyOrderSO` | 取消预占，available_qty+ |
| `InvTransfer` | 手工转移，available↔allocated 之间互转 |

## 已发现的问题与教训

### 教训1：不要把调拨预占当成核心预占
- `TSPickingService.preoccupancySuccess()` 是调拨预占，不是核心订单预占
- `PreoccupancyService.preoccupancy()` 才是核心订单预占入口

### 教训2：预占和拣货的 SQL 方法必须分开
- 预占用 `updateAllocatedQty`（同时操作 qty 和 alloc）
- 拣货用 `decreaseAllocatedQtyOnly`（只操作 alloc）
- 混用会导致 qty 被错误加回或重复扣减

### 教训3：查询条件必须匹配扣减来源
- 从 quantity 扣减 → 查 `quantity > 0`（queryAvailableLots）
- 从 allocated_qty 扣减 → 查 `allocated_qty > 0`（queryAllocatedLots）
- 预占后 quantity 可能为 0，用 `quantity > 0` 查不到

### 教训4：批次操作必须和聚合操作在同一事务中
- `dealLotInventoryTransaction()` 在 `adjustLocationTrans()` 事务之外
- 批次是影子表，不一致可通过定期校验修复
- 根本修复：批次操作只准备数据，在 `adjustLocationTrans()` 中统一写入

### 教训5：edit_user/in_user 必须做 null 保护
- `PreoccupancyRequest.getIn_user()` 可能为 null
- 所有写入 DB 的 user 字段必须有兜底值（从日志中获取或用 "SYSTEM"）

### 教训6：strReplace 后必须立即验证
- 每次 strReplace 后必须用 grepSearch 确认改动已写入
- strReplace 返回 success 不代表真的写入成功

### 教训7：禁止用 PowerShell Set-Content 修改 Java 文件
- 会破坏 UTF-8 编码，只能用 `strReplace` 或 `fsWrite`

### 教训8：新增 @Autowired 必须同步添加 import
- 禁止使用全限定类名声明字段

### 教训9：排查问题时必须输出完整调用链路
- 从接口入口开始，逐层列出方法调用、文件名、行号
- **每一层调用必须用 grepSearch 验证**，禁止凭记忆或推测编写链路
- 标注问题节点（❌）和正确节点（✅）
- 方便用户直接定位代码查看

### 教训10：order_id 和 order_sn 是两个不同字段，不能混用
- `order_id`：数字型订单ID（如 1241106830），`wh_order_lot_consumption.order_id` 存的是这个
- `order_sn`：字符串型订单编号（如 "2026041398937"），前端/APP 传参通常用这个
- 两者一对一关系，通过 `wh_order_info` 表关联
- **查 `wh_order_lot_consumption` 必须用 `order_id`**，不能用 `order_sn`
- 如果只有 `order_sn`，先通过 `queryOrderIdByOrderSn()` 转换为 `order_id`

### 教训11：方法中有提前 return 时，必须检查 return 前是否遗漏批次同步
- `TSPickingService.preoccupancySuccess()` 中单库位足够时提前 return，跳过了底部的批次预占代码
- 任何涉及批次同步的方法，如果有多个 return 出口，每个出口前都必须确保批次同步已执行
- 建议：将批次同步逻辑抽取为独立方法，在每个出口前调用

### 教训12：两张表一对一关系必须通过精确字段关联，不能依赖反查匹配
- `wh_lot_master` 和 `wh_inbound_batch` 是一对一关系（每次收货同时创建），但没有外键关联
- 上架时用 `sourceNumber + itemNumber` 反查 `wh_lot_master`，同一 PO 同一商品多次收货时取到第一条（错误的 lot_id）
- 修复：`wh_inbound_batch` 加 `lot_id` 列，收货时回写，上架时直接读取
- 原则：**两张表有一对一关系时，必须在其中一张表存储另一张表的 ID，不能依赖业务字段反查**

### 教训13：批次预占/释放后，日志必须按 lot 拆分
- `syncTsLotPreoccupancy` 只做了批次库存写入，没有把分配结果回传到日志列表
- 导致调拨预占日志 lot_id=0，无法追溯预占了哪些批次
- 原则：**凡是做了批次分配（prepareBatchAllocate），分配结果必须同时传递给日志写入逻辑，按 lot 拆分日志**

### 教训14：LOT_LEGACY(lot_id=1) 没有 wh_lot_master 记录，查询必须用 LEFT JOIN
- `wh_lot_master` 的主键是 `lot_id`，一个 lot_id 只能对应一条记录（一个商品+仓库）
- lot_id=1 是所有老库存的兜底标识，无法在 master 中为每个商品都创建 lot_id=1 的记录
- 因此 lot_id=1 只存在于 `wh_lot_inventory`，不存在于 `wh_lot_master`
- 所有查询 SQL 必须用 **LEFT JOIN** wh_lot_master，排序字段用 **COALESCE** 兜底
- 原则：**AUTO_INCREMENT 主键不能用固定值覆盖多条不同业务数据**

### 教训15：prepareBatchRelease/prepareBatchAllocate 的 quantity 必须为正数
- `itemPreoccupancy` 中取消预占时传了 `-pl.getQty()`（负数），`prepareBatchRelease` 中 `remaining <= 0` 直接跳过
- `batchCancelPreoccupancy` 和 `singleOrderBatchCancelPreoccupancy` 中都用的是正数（正确）
- 原则：**prepareBatchRelease 和 prepareBatchAllocate 都期望正数，方法内部处理方向，调用方不需要取反**

### 教训16：调用复杂 SQL 时必须确认所有必要参数都已设置
- `qcDao.queryInboundBatch` 的 SQL 中 JOIN 子查询需要 `inbound_number` 和 `item_number`，但调用方只设了 `rec_id`
- 为 null 的参数导致 JOIN 失败，整个查询返回 null
- 原则：**优先用简单查询（单表 WHERE 主键）代替复杂 JOIN；如果必须用复杂 SQL，确认所有参数都已设置**

### 教训17：SQL 中禁止在 LEFT JOIN 条件中使用 SELECT 子句中赋值的变量
- MySQL 执行顺序：FROM/JOIN 先于 SELECT，`@locationNo` 在 LEFT JOIN 时还没被赋值
- `TSTruckMapper.xml` 中 `@locationNo := (SELECT ...)` 在 SELECT 中赋值，LEFT JOIN 中引用时为 NULL
- 修复：LEFT JOIN 中改用内联子查询 `(SELECT sl.location_no FROM ... LIMIT 1)`
- 原则：**需要动态值参与 JOIN 条件时，用内联子查询而非用户变量**

### 教训18：上架场景有明确 lot_id 时，必须用指定批次而非 FIFO
- 上架（PUT_AWAY_BIN/STOCK）走通用转移逻辑，from 方向按 FIFO 扣减收货区
- 收货区有 LOT_LEGACY（lot_id=1）排最前面，先被扣了，导致上架到 Bin 的批次是 lot_id=1
- 修复：新增 `dealPutawayLotInventory`，from/to 都用 `request.getLotId()` 指定的批次
- 原则：**有明确 lot_id 的场景（收货、上架），必须用指定批次，不能走 FIFO 自动选择**

### 教训19：同一操作中有损益和转移时，必须先损益再转移
- 转补单中先转移再损益，转移按 FIFO 先转走老批次，剩下新批次被盘亏，违背 FIFO 原则
- 先损益再转移：盘亏按 FIFO 先扣老批次，转移时剩余的批次结构正确
- 原则：**损益和转移在同一操作中时，先损益再转移，确保两步都遵守 FIFO/FEFO**

### 教训20：MyBatis 中禁止 Java 方法重载映射到同一个 SQL id
- `queryByLotId` 有两个重载（单参数和三参数），XML 中只有一个 SQL，动态条件引用了三参数版本的参数
- 调用单参数版本时 MyBatis 找不到参数，抛出 `BindingException`
- 原则：**不同参数的查询必须用不同的方法名和 SQL id，MyBatis 不支持方法重载**

### 教训21：SQL 中 LEFT JOIN 获取 lot_id 时必须查源库位（有数据的一方）
- TSInboundMapper LEFT JOIN 查目标库位 TRANSIN，但日志写入时 TRANSIN 上还没有 lot_inventory
- 应该查源库位 TSOZ（通过 location_type=47 子查询），此时源库位上还有数据
- 原则：**日志写入在批次转移之前执行时，LEFT JOIN 必须查源库位**

### 教训22：SQL 中日志 quantity 必须用本次操作量而非全量
- TSPickingMapper 取消预占日志用了 `li.allocated_qty`（该 lot 全部预占量），而不是 `task.qty`（本次取消量）
- 当库位上有多个调拨单的预占时，全量会远大于本次取消量
- 原则：**日志 quantity 必须来自业务操作的数量（task/topi），不能来自 lot_inventory 的全量字段**

### 教训23：取消预占时必须按原始预占的 lot 精确释放
- `prepareBatchRelease` 按 `allocated_qty` 从大到小释放，不区分是哪个调拨单的预占
- 当多个调拨单预占了同一库位的不同 lot 时，释放了错误的 lot
- 修复：从 `wh_inventory_transaction_log` 中反查该调拨单的预占日志，按原始预占的 lot 精确释放
- 原则：**取消预占时不能用通用释放方法，必须反查原始预占明细精确释放**

### 教训24：MyBatis SQL 返回类型必须匹配实际查询的表，不要用占位符凑 resultMap
- `queryTsPreoccupancyLotDetails` 查的是 `wh_inventory_transaction_log` 表，但用了 `wh_lot_inventory` 的 `resultMap`，需要 `0 AS rec_id` 等占位符
- 这样代码不优雅，给读代码的人带来误解
- 原则：**SQL 返回类型必须匹配实际查询的数据结构。跨表查询用 `resultType=HashMap` 或专用 DTO，不要复用其他表的 resultMap**

### 教训25：wh_lot_inventory 的 quantity 就是可用量，计算时不要再减 allocated_qty
- `prepareBatchAllocate` 中用 `lot.getQuantity() - lot.getAllocated_qty()` 计算可用量
- 但 `wh_lot_inventory` 的设计是：预占时 quantity 减少、allocated_qty 增加，quantity 本身就是"剩余可预占量"
- 当同一 lot 已被其他订单预占过时，`quantity - allocated_qty` 得到负数，该 lot 被跳过
- 原则：**`wh_lot_inventory.quantity` = 可用量，`allocated_qty` = 已预占量，总库存 = quantity + allocated_qty。计算可用量直接用 quantity，不要再减 allocated_qty**

### 教训26：从收货区（RECG）转移库存时，必须传递收货时的 lot_id
- PIC 转移走通用 `adjustLocation`，from 方向按 FIFO 扣减
- 同一 PO 多次收货时，RECG 上有多个 lot，FIFO 取到最早的 lot 而非当前收货的 lot
- 修复：收货时把 lot_id 传给 `ItemPicStatus`，PIC 转移时设置到 `AdjustLocationRequest.setLotId()` 和 `LocationItemRequest.setLotId()`
- 原则：**所有从 RECG 转移库存的场景（PIC 转移、上架等），如果有明确的 lot_id，必须传递给 adjustLocation，不能依赖 FIFO**

### 教训27：上架时获取 lot_id 必须按 batch 精确匹配，不能用入库单号反查取第一条
- `queryLotIdBySourceNumber` 用入库单号反查 `wh_lot_master`，多次收货时返回多条，取第一条可能已上架过
- 修复：`getAllocationResult` 新增按 `reference_id` 查 batch 列表分配的逻辑，每个 batch 有自己的 lot_id
- 优先级：`group_batch_no` > `batch_no` > `reference_id 按 batch 分配` > `queryLotIdBySourceNumber 兜底`
- 原则：**上架时 lot_id 必须来自 batch 级别的精确匹配，不能依赖入库单号级别的反查（一对多关系）**

### 教训28：更新数据库后，如果后续代码还需要读取该对象，必须同步更新 Java 对象
- `writeLotIdToBatch` 调用 `inboundDao.updateBatchLotId` 更新了数据库，但没有 `batch.setLot_id(lotId)`
- 后续 `batch.getLot_id()` 返回初始值 0/null，导致 PIC 转移时 lotId 为 null
- 原则：**数据库更新 ≠ Java 对象更新。如果同一事务中后续代码还需要读取该字段，必须同步更新 Java 对象**

### 教训29：影子表操作异常不能导致主流程事务回滚
- `dealLotInventoryTransaction` 的 catch 块中 throw 了异常，导致批次处理失败时整个 `adjustLocation` 事务回滚
- 打包出库时聚合库存和日志都没有更新，订单无法正常出库
- 原则：**影子表（wh_lot_inventory）的操作必须在 catch 块中吞掉异常，只记录日志。影子表异常绝不能导致主流程事务回滚**

### 教训30：批次库存不足时必须尽力扣减，不能抛异常中断
- 打包出库时 packing 传入的扣减数可能大于 lot 实际库存（已知的操作漏洞）
- `decreaseLotInventory` 中 `totalAvailable < quantity` 时 throw 异常，导致 lot 相关数据全部丢失
- 修复：改为 warn 日志 + 尽力扣减（扣到没有为止），按实际扣减的 lot 明细记录
- 原则：**批次是影子表，任何场景下都不应因批次库存不足而中断处理。尽力扣减 + warn 日志 + 定期校验**

### 教训31：扣减指定 lot 前必须确认该 lot 在目标库位上有库存
- 错收冲减时 `queryLotIdsByPoAndItem` 查出该 PO 的所有 lot（好货+坏货），遍历时尝试在 RECN0001 上扣减好货的 lot（只在 RECG0001 上有库存）
- `decreaseLotInventory` 内部 `decreaseQuantity` 返回 0，抛异常标记事务 rollback-only
- 修复：先查目标库位上有库存的 lot 集合，遍历时 `contains` 过滤
- 原则：**扣减指定 lot 前必须先确认该 lot 在目标库位上有库存，不能盲目遍历 PO 级别的 lot 列表**

### 教训32：批次相关的所有 catch 块必须全局检查，不能有遗漏的 throw
- BUG-028 修复时改了 `dealLotInventoryTransaction` 和 `LocationService` 的 catch 块，但遗漏了 `dealPutawayLotInventory` 内部的 catch 块
- 生产上架时该 catch 块 throw 导致事务回滚
- 原则：**修复"不抛异常"类问题时，必须全局搜索 `throw new YamibuyException` 确认所有相关 catch 块都已处理**

### 教训33：不要在高频操作中同步执行全表扫描的状态检查
- `checkAndUpdateLotStatus(lotId)` 在每次批次扣减后调用，用 `queryAllByLotId` 查该 lot 的所有库存记录
- lot_id=1（LOT_LEGACY）有 15 万条记录，单次查询耗时 5 秒，严重影响接口响应
- 原则：**状态检查如果涉及大量数据查询，不能在每次操作后同步执行。要么加条件跳过（如 lot_id=1 直接跳过），要么改为异步定时任务，要么直接移除（如果业务上不需要）**

### 教训34：批量 Job 必须具备幂等性，防止重复执行产生脏数据
- `LotLegacyMigrationHandler` 每次执行都创建新的 lot_id + lot_inventory，没有检查是否已处理过
- Job 被执行多次后，同一个 (warehouse, location, item) 有 2~30 条重复记录，lot_inventory 总量是聚合库存的数倍
- 原则：**批量 Job 必须在执行前检查是否已处理（如 `WHERE NOT EXISTS` 或 `INSERT ... ON DUPLICATE KEY`），确保多次执行结果一致**

### 教训28：JOIN 关联表时必须确认关联字段有唯一索引，否则用 EXISTS 代替
- `queryLegacyOnBinStock` 用 `INNER JOIN wh_storage_location` 过滤 Bin/Stock 库位
- `wh_storage_location` 中有 102 个库位存在重复记录（同一 warehouse_number + location_no 多条），JOIN 产生笛卡尔积
- Job 对同一条 lot_id=1 的记录处理了多次，创建了重复的新批次，导致总量不守恒（多出 15484）
- 修复：`INNER JOIN` 改为 `EXISTS (SELECT 1 FROM wh_storage_location ...)`
- 原则：**JOIN 关联表时，如果关联字段没有唯一索引，必须用 EXISTS 或加 DISTINCT 防止笛卡尔积。批量 Job 中尤其危险——查询结果驱动逐条写入时，重复记录会导致数据膨胀**

## OOS（Out of Stock）流程与批次追踪

### OOS 业务说明
拣货人员拣订单时发现库位上库存不够，扫描 OOS 码锁住该库位。系统自动执行：
1. 取消当前订单在该库位的预占
2. 取消其他订单在该库位的预占（防止后续订单也拣不够）
3. 将库位上的库存全部盘为 0（等待盘点人员重新盘点）

### OOS 代码链路（PickingOosService.removeOrder4OutOfStock）

```
步骤1: batchCancelPreoccupancy(orderNumberSet)
  → 取消当前订单的预占（聚合库存 alloc 减 qty 加）
  → 批次库存同步释放（prepareBatchRelease + executeBatchAllocateUpdate）
  → 写取消预占日志（Cancel Preoccupancy）
  注意：只有 batchUpdateOrderStatusForOOS 返回 >0 才执行

步骤2: 等待3秒

步骤3: itemPreoccupancy(orderId=-1, CANCEL_PREOCCUPANCY)
  → 释放该库位上该商品的所有剩余预占（不限订单）
  → 聚合库存 alloc 全部归零，qty 加回
  → 批次库存同步释放
  → 写日志（Secondary Cancel Preoccupancy）

步骤4: oosLoss() 异步
  → 将库位上该商品的 quantity 盘为 0
  → 走 adjustLocation(ADJUST) → dealLotInventoryTransaction 同步批次
```

### OOS 批次追踪检查点
- 步骤1 和步骤3 都需要同步释放 `wh_lot_inventory` 的 `allocated_qty`
- 步骤4 的 oosLoss 走 ADJUST 盘亏逻辑，会自动扣减 `wh_lot_inventory` 的 `quantity`
- 步骤1 可能不执行（订单状态不满足），此时步骤3 承担全部释放工作

### 教训35：LotInventoryService 所有方法必须用 REQUIRES_NEW 事务传播
- `decreaseLotInventory`（自动选择版本）标注 `@Transactional(rollbackFor=Exception.class)` 默认传播 REQUIRED
- 被 `dealLotInventoryTransaction` 调用时加入了外层事务（`OrderPickService.adjustLocation` 的 `@Transactional`）
- 内部抛异常时 Spring 标记外层事务为 rollback-only，即使异常被 catch 吞掉，事务提交时仍报 `UnexpectedRollbackException`
- 修复：`LotInventoryServiceImpl` 所有 public 方法统一改为 `@Transactional(propagation = REQUIRES_NEW)`
- 原则：**批次操作（影子表）的 @Transactional 必须用 REQUIRES_NEW，开启独立事务。失败时只回滚自己，不污染外层事务。REQUIRED 传播级别在"被 catch 吞异常"的场景下会导致 UnexpectedRollbackException**

### 教训36：dealPutawayLotInventory 中 from 和 to 必须独立 try-catch
- 之前 from 和 to 在同一个 try 块中，from 失败后 to 不执行
- 上架时如果 RECG 上没有对应 lot 的记录（老数据），from 扣减失败，目标库位也没有插入批次记录
- 后续拣货时查不到批次记录，触发教训35的事务回滚问题
- 修复：from 方向单独 try-catch，失败只记日志不阻止 to 方向执行
- 原则：**批次操作中 from 和 to 是独立的两步，一方失败不能阻止另一方。特别是 to 方向（目标库位增加记录）比 from 方向更重要——没有 to 记录会导致后续所有操作失败**

### 教训37：老 batch 上架时不能走 queryLotIdBySourceNumber，必须直接用 LOT_LEGACY
- 老 batch（上线前收货）`wh_inbound_batch.lot_id=0`，`queryBatchLotId` 返回 null
- `queryLotIdBySourceNumber` 会查到 Job 反推创建的 lot_id（如70983），但这个 lot 对应的是已上架的库存，不是 RECG 区等待上架的这批货
- RECG 区的老库存在初始化时是 lot_id=1（LOT_LEGACY），上架时应该用 lot_id=1 扣减 RECG
- 修复：有 batch（`rec_id > 0`）但 `lot_id=0` 时，直接用 `lot_id=1`（LOT_LEGACY），跳过 `queryLotIdBySourceNumber`
- 原则：**上架时 lotId 获取优先级：batch.lot_id（精确）> 有 batch 但 lot_id=0 → LOT_LEGACY > 无 batch 信息 → queryLotIdBySourceNumber > 最终兜底 LOT_LEGACY。老 batch 绝不能走 queryLotIdBySourceNumber，因为 Job 反推的 lot 对应的是已上架库存，不是 RECG 区的货**


### 教训38：有保留 ID 的表必须设置 AUTO_INCREMENT 跳过保留值
- `wh_lot_master` 的 `lot_id=1` 保留给 LOT_LEGACY（老库存兜底标识）
- 建表时没有设置 `AUTO_INCREMENT = 2`，默认从1开始
- 上线后第一次收货 `createLot` 返回 `lot_id=1`，与 LOT_LEGACY 冲突
- 修复：建表 SQL 加 `ENGINE=InnoDB AUTO_INCREMENT=2`
- 原则：**当系统设计中有保留 ID（如 lot_id=1 = LOT_LEGACY、user_id=0 = SYSTEM），建表时必须设置 AUTO_INCREMENT 跳过这些保留值，避免正常业务数据与保留标识冲突**


### 教训39：拣货时必须从预占日志反推精确批次，不能盲目按排序扣减
- `prepareBatchFromPlan` 中拣货场景用 `batchQueryByLocationAndItems`（按 `rec_id ASC`），lot_id=1 的 rec_id 最小被优先扣减
- 预占时正确分配到 lot_id=3336，但拣货时扣了 lot_id=1（因为 lot_id=1 的 allocated_qty 来自其他订单的预占）
- 修复：拣货场景优先查 `wh_inventory_transaction_log`（Preoccupancy Success + orderId）反推该订单预占了哪些批次，按明细精确扣减
- 兜底：反推不出来时（老数据 lot_id=0），用 `strategySelector` 选 FIFO/FEFO，拣货专用查询中 lot_id=1 排最后
- 原则：**预占和拣货是配对操作。拣货扣减的 lot 必须与预占分配的 lot 一致。不能依赖通用排序（rec_id ASC / FIFO / FEFO）来"猜"应该扣哪个 lot，因为同一库位可能有多个订单的预占混在一起**


### 教训39：from 方向无批次记录时，to 方向不能直接跳过
- Problem Inventory（TOOL_ADD）场景：EXT 库位上从来没有聚合库存记录，也没有 lot_inventory 记录
- `dealProblemItem` 转出时 from 方向查不到批次 → consumptionDetails 为空 → to 方向被跳过
- 目标 Bin 上没有 lot_inventory 记录，后续预占时 lot_id=0
- 修复：`LOCATION_TOOL_TASK` 场景 from 无批次记录时，to 方向用 LOT_LEGACY 兜底（类似盘盈）
- 原则：**转移场景中，如果 from 方向的库位可能没有批次记录（EXT、虚拟库位等），to 方向必须有兜底策略。不能因为 from 无记录就跳过 to，否则目标库位永远没有批次记录**


### 教训40：批量操作中多条记录指向同一行时，必须先合并再处理
- `prepareBatchRelease` 对每条 releaseItem 独立查询快照，多条指向同一 (location, item) 时都看到相同的 allocated_qty
- 每条都选了同一个 lot 释放，但 `executeBatchAllocateUpdate` 批量执行时第3次 WHERE 条件不满足
- 修复：先按 (location, item) 合并数量（3条各1个 → 1条3个），再统一查询分配
- 原则：**批量操作中如果多条记录可能指向同一行（同一库位同一商品），必须先合并数量再处理。逐条独立查询+分配会基于相同快照重复分配，导致实际执行时部分失败**


### 教训41：Restock 链路中 from 方向无批次记录时 to 方向必须兜底
- Stock 库位可能没有 lot_inventory 记录（初始化遗漏或 Job 反推后清理了 lot_id=1）
- Restock Pick 从 Stock 拣到 RS 时 from 无批次 → to 跳过 → RS 也没有批次
- Restock Bin Load 从 RS 到 Bin 时同样跳过 → Bin 上没有批次记录
- 后续所有在该 Bin 上的操作（预占、拣货、出库）全部 lot_id=0
- 修复：`prepareBatchToPlan` 中 `RESTOCK_PICK` 和 `RESTOCK_PUT_AWAY` 也加入兜底列表
- 原则：**任何转移链路中，只要 from 方向的库位可能没有批次记录，to 方向都必须有 LOT_LEGACY 兜底。不能让"无批次"状态沿着转移链路传播**


### 教训42：新建表的关联字段类型必须与被关联表完全一致
- `wh_order_lot_consumption.order_id` 设计为 `varchar(20)`，但 `wh_order_info.order_id` 是 `bigint`
- 类型不一致导致 JOIN 查询时 MySQL 对 varchar 列做隐式类型转换，索引失效退化为全表扫描
- 246 万行表全表扫描会严重影响性能
- 修复：ALTER TABLE 将 `order_id` 从 `varchar(20)` 改为 `bigint`，重建索引
- 原则：**新建表时，所有关联字段（用于 JOIN/WHERE 条件的字段）类型必须与被关联表一致。设计阶段必须 `SHOW COLUMNS FROM` 或查 `information_schema` 确认目标表字段类型，禁止凭印象定义**


### 教训43：事务内调用外部资源（Redis/HTTP）必须有降级方案
- `createLot()` 使用 `@Transactional(REQUIRED)` 加入外层 `receiveConfirm()` 事务
- `generateLotNo()` 调用 Redis 生成序号，Redis 超时抛异常 → Spring 标记事务 rollback-only
- 外层 `createLotForReceiving()` 虽然 catch 了异常，但事务标记已不可逆，收货整体回滚
- 修复：`createLot()` 改 `REQUIRES_NEW`（独立事务） + `generateLotNo()` 增加本地 AtomicLong 降级
- 原则：**事务内的外部资源调用（Redis、HTTP、MQ）必须有降级方案，不能让外部资源故障传导到核心业务。降级方案要保证不会产生脏数据（如用隔离序号段避免冲突）**


### 教训42：批量操作的日志必须按业务维度（订单）分别记录
- `batchCancelPreoccupancy` 中 `prepareBatchRelease` 合并了多个订单的释放量，`lotUpdates` 无法区分哪条属于哪个订单
- 日志用 `orderNumberSet.iterator().next()` 只取了第一个订单号，其他订单没有日志
- 修复：遍历每个订单，分别查询预占日志获取释放信息，按订单维度写入日志
- 原则：**日志记录必须按业务维度（订单/调拨单）分别记录。不能用合并后的批量结果统一记录，否则无法按订单追溯**


### 教训44：取消预占日志的 lot_id 必须从预占成功日志批量反查，不能从释放结果推导
- Cancel Preoccupancy 日志的 lot_id 最初从 `prepareBatchRelease` 的释放结果推导（按 allocated_qty 排序后按量消费）
- 但释放结果是合并后的（多个订单合并为一次 FIFO 释放），丢失了"哪个订单对应哪个 lot"的信息
- 正确做法：`batchQueryPreoccupancyLotLogs(orderIds, warehouseNumber)` 一次 IN 查询所有订单的预占日志，内存中按 `(orderId|item|location)` 分组
- reference_type 必须同时包含 `Preoccupancy Success`（主预占）和 `Secondary Preoccupancy`（二次预占/多库位预占），两者都会占用 allocated_qty 并记录 lot_id
- 禁止在循环中逐个查询 DB（N+1 问题），能批量的就批量
- 原则：**预占和取消预占是配对操作。取消时的日志字段（lot_id、quantity）必须从预占时的日志反查，不能从中间结果（释放/合并/排序后的结果）推导。批量查询 + 内存分组是性能最优解**


### 教训45：写入 wh_inventory_transaction_log 时 before_quantity/before_allocated 不能为空
- Cancel Preoccupancy 的 Java 层写入日志时没有设置 `before_quantity` 和 `before_allocated`，DB 中为 null
- 这两个字段记录操作前的聚合库存快照，是审计追溯的关键
- 修复：在释放操作执行前（`executeBatchAllocateUpdate` 之前），按去重的 `(location, item)` 查询 `wh_inventory_transaction` 表获取快照
- 原则：**所有 Java 层手工构造 InventoryTransactionLog 的代码，都必须设置 before_quantity 和 before_allocated（从操作前的聚合库存查询）。SQL 层的日志由 SQL 本身通过子查询获取，Java 层没有自动机制必须手动设置**


## 已发现的问题与教训

### 教训-02（2026-08-08）: MyBatis resultType="map" 中禁止对数字字段硬强转 Integer
- **场景**: `ShippingService.batchUpdateArrivalStatus()` 中 `(Integer)e.get("cancel")` 强转失败，Job 每半小时崩溃一次
- **根因**: MySQL JDBC 类型推断规则——被 `IFNULL / COALESCE / CASE WHEN / 聚合函数` 包裹的整数字段，驱动统一推断为 `Long`，而普通 `INT` 列才推断为 `Integer`。Map 里存的是 `Long`，强转 `(Integer)` 在运行时抛 `ClassCastException`
- **规则**:
  1. `resultType="map"` 查询结果中，**禁止对数字字段用 `(Integer)` 或 `(Long)` 硬强转**
  2. 安全写法：`((Number) map.get("field")).intValue()` —— `Number` 是 `Integer`/`Long`/`BigDecimal` 的公共父类，通过 `.intValue()` 统一取值
  3. 另一种安全写法：`Integer.parseInt(map.get("field").toString())`
  4. **根本解法**：用 `resultType` 指向明确的 DTO/Entity 类，MyBatis 自动完成类型转换，完全避免 Map 强转问题
  5. 高风险字段：SQL 中凡是用了函数包裹（`IFNULL/COALESCE/SUM/COUNT/CASE`）的整数列，必须按 Long 处理

### 教训-01（2026-07-25）: 包装类字段自动拆箱 NPE 风险
- **场景**: `CubiscanService.markItemBubble()` 中 `double msrp = item.getMarket_price()` 自动拆箱
- **教训**: 从数据库查回来的 `Double`/`Integer`/`Long` 包装类字段，直接赋值给基本类型时会触发自动拆箱。当字段值为 NULL 时（SQL 未设置 NOT NULL DEFAULT 或 IFNULL 兜底），自动拆箱抛 NPE
- **规则**:
  1. 包装类字段赋给基本类型前必须 null 检查：`field != null ? field : defaultValue`
  2. 或在 SQL 中用 `IFNULL(field, 0)` / `COALESCE(field, 0)` 保证非空
  3. 高风险字段：`market_price`、`weight`、`length`、`width`、`height` 等尺寸重量字段，数据库默认值可能为空

### 教训48（2026-08-07）: LEAST(虚增量, 缺发量) 是「名额维度」上限，不是「订单维度」的因果数量

- **背景**: BUG-044 分析中，用 `SUM(LEAST(各item虚增量, 缺发量))=34件` 作为"bug导致的缺发上限"，并据此推导"受影响订单数 ≤ 34单"，导致将真实的90单缺发低估为34单
- **错误根因**: LEAST 计算的是「虚增了多少个名额，最多多卖出多少件」，是**库存名额维度的静态上限**，忽略了 WMS 库存的动态循环机制：
  ```
  order_qty 被扣成负数（如 -1）
    → OOS 触发：order_qty -1→-2，available_qty +1（OOS归还）
    → available 变成1后前台又可下单
    → 下单：order_qty -1→0，available -1→0
    → 再次 OOS：order_qty 0→-1，available +1
    → 如此往复，虚增会持续"再生"，导致持续缺发
  ```
  因此**1个虚增名额可以循环触发多次缺发**，34件名额可以导致远超34单的缺发
- **正确分析方法**: 
  - 统计「缺发发生在虚增之后」且「该 item 有 soCancel 虚增记录」的 OOS 订单数 → **90单**，这才是 bug 真实导致的缺发订单数
  - `LEAST(虚增量, 缺发量)` 是名额维度的参考值，可用于估算「虚增耗尽需要多少单」，**不能用于推断因果订单数**
- **规则**:
  1. 库存分析中涉及「虚增→超卖→缺发」链路时，必须考虑 OOS 归还 available 的循环效应
  2. `LEAST(虚增量, 缺发量)` 只能说明「名额层面最多影响多少件」，不等于「订单层面只影响这么多单」
  3. 真实影响订单数 = 时序命中（缺发发生在虚增之后）的 OOS 订单去重数，不是 LEAST 之和

### 教训47（2026-08-07）: inventory 幂等校验必须覆盖所有互斥释放路径
- **场景**: `central-inventory-service` 的 `soCancelAction` 幂等只查 `operation_type='soCancel'`；货已通过 `soOutStock` 出库（order_qty 已释放）后，若订单整单取消，查不到 soCancel 记录 → 放行 → order_qty 被第二次释放
- **实测影响**（101 仓）: 4 单多扣 24 个（227426174 -16、227277858 -6 等）
- **规则**:
  1. **释放 order_qty 的幂等校验必须把所有互斥操作作为集合一并查询**：soCancel / WMSCancelOrder / soOutStock / OOS 中任意一个存在即视为已处理，禁止只查单一 operation_type
  2. `batchUpdateOrderQty` 必须加 `AND t.order_qty + #{item.quantity} >= 0` 下限保护，把静默扣穿变成可观测失败（order_qty 不能为负）
  3. 幂等查询的过滤条件不能带 `seller_type / business_type` 等业务属性，粒度应下沉到 `item_number + change_feild` 级别，避免非自营商品幂等直接失效

### 教训46（2026-08-06）: MQ 消费线程必须显式建立 siteCode 上下文，多站点过滤条件禁止静默兜底
- **场景**: `CancelOrderReceiver.process()` 从 MQ 消费取消订单消息 → `CancelOrderService.cancelOrder()` → `orderInfoService.queryOrderInfo(orderNumber)`。该查询的 SQL 带 `AND xoi.vendor_id = #{vendor_id}` 条件，vendor_id 来自 `VendorService.getSelfVendorId()`，而它依赖 `SiteCodeUtil.getSiteCode()`
- **问题链**:
  1. 上游 MQ 消息头 `site_code` 恒为 `us`（即使订单属于 CA 站）
  2. `getSelfVendorId()` 取不到正确站点时 `return vendorId != null ? vendorId : 0`，静默兜底为 US 的 0
  3. CA 站（ON 仓 101）订单 `vendor_id=5000`，用 0 去查 `wh_order_info` 必然查不到
  4. `cancelOrder()` 中 `needSaveCache = true`（wh 库查不到 → 退化查 master 库）
  5. 触发"场景3"：`needSaveCache && order_status==4 && shipping_status==8 && pay_status==3` → `sendMQToInventory()` 发 `so_cancel` 归还 order_qty
  6. 但货其实已拣到 Tote，打包台后续走 `/packing/cancel` → `WMSCancelOrder` 再归还一次 → **order_qty 双扣**
- **数据验证**（近两个月）：101 仓 11 单 WMSCancelOrder 全部伴随 soCancel（100%），001/002 共 441 单一次都没有。US 站因 `vendor_id=0` 恰好与兜底值相同而幸免
- **规则**:
  1. **MQ / 定时任务 / 线程池等无 HTTP 请求上下文的入口，必须显式建立 siteCode 上下文**，不能依赖 ThreadLocal 里的残留值或兜底默认值
  2. **多站点数据过滤条件（vendor_id / site_code）的取值失败必须显性化**，禁止静默 fallback 到某个站点的值——"查不到数据"和"查错站点"是两种完全不同的语义，混淆后会被上层误判为业务状态
  3. 业务判断禁止用"查不到记录"代理"业务状态"（此处用查不到订单代理"订单未下发到仓库"）。状态判断要查明确的状态字段（如 `wh_order_pool` 是否存在）
  4. 已有 `WarehouseProvider.getWarehouseMap()` 提供仓库→站点映射（001/002→us，101→ca），需要按仓库定站点时直接复用，禁止另写 if-else 或硬编码仓库号
