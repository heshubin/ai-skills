---
name: wms-inventory-transfer-guide
description: 分析、修改或调试 wms-cloud-service 库存转移（adjustLocation）链路、新增 actionType、排查库存数量不一致或库位释放异常时使用。触发词：库存转移, adjustLocation, actionType, dealInventoryTransaction, dealItemTransaction, 库位释放, 库存不一致
---
# WMS 库存转移核心逻辑指南

当分析、修改或调试 wms-cloud-service 中库存转移（adjustLocation）相关代码时，加载本 skill 获取核心逻辑上下文。

## 触发场景

- 分析 LocationService.adjustLocation() 调用链
- 修改库存转移逻辑、新增 actionType 处理
- 调试库存数量不一致、库位释放异常等问题
- 审查涉及 dealInventoryTransaction / dealItemTransaction 的代码变更

## 核心调用链

```
业务服务层 → LocationService.adjustLocation()
  → checkLocation()           // 阶段1：校验
  → dealInventoryTransaction() // 阶段2：准备聚合库存数据
  → saveInventoryTransactionLog() // 阶段3：准备日志
  → TransactionDealService.adjustLocationTrans() // 阶段4：统一事务写入 + 释放库位
```

## 关键文件位置

| 文件 | 路径 |
|------|------|
| LocationService | `wms-cloud-service/wms-cloud-service/src/main/java/com/yamibuy/wms/cloud/service/LocationService.java` |
| TransactionDealService | `wms-cloud-service/wms-cloud-service/src/main/java/com/yamibuy/wms/cloud/service/TransactionDealService.java` |
| LocationProcessEnum | `wms-cloud-service/wms-cloud-api/src/main/java/com/yamibuy/wms/cloud/entity/enu/LocationProcessEnum.java` |
| LocationProcessRelationEnum | `wms-cloud-service/wms-cloud-api/src/main/java/com/yamibuy/wms/cloud/entity/enu/LocationProcessRelationEnum.java` |
| AdjustLocationRequest | `wms-cloud-service/wms-cloud-api/src/main/java/com/yamibuy/wms/cloud/entity/wms/request/AdjustLocationRequest.java` |
| LocationItemRequest | `wms-cloud-service/wms-cloud-api/src/main/java/com/yamibuy/wms/cloud/entity/wms/request/LocationItemRequest.java` |
| DealBatchSaveOrUpdateVo | `wms-cloud-service/wms-cloud-api/src/main/java/com/yamibuy/wms/cloud/entity/common/DealBatchSaveOrUpdateVo.java` |
| InventoryTransactionLog | `wms-cloud-service/wms-cloud-api/src/main/java/com/yamibuy/wms/cloud/entity/wms/InventoryTransactionLog.java` |
| ReceiveService | `wms-cloud-service/wms-cloud-service/src/main/java/com/yamibuy/wms/cloud/service/ReceiveService.java` |

## 关键规则（必读）

### 规则 1：Opera 字段无效
`LocationProcessRelationEnum` 中的 Opera（ADD/SUBTRACT/CONSTANT）在代码中完全没有被使用（`getOpera()` 零调用）。实际行为由 `fromType`/`toType` + `isIDLocationEnum()` 决定。**分析代码时必须忽略 Opera 对逻辑的干扰。**

### 规则 2：方向判断逻辑
```java
// dealInventoryTransaction() 中的核心判断 — 不依赖 Opera
if (fromType != LocationTypeEnum.NONE && !isIDLocationEnum(fromType)) {
    dealItemTransaction(request, item, true);   // 源库位扣减
}
if (toType != LocationTypeEnum.NONE && !isIDLocationEnum(toType)) {
    dealItemTransaction(request, item, false);  // 目标库位增加
}
```

### 规则 3：6 种虚拟库位（isIDLocationEnum 返回 true，跳过处理）
- `ID_LOCATION` — 订单出库目标
- `TRANSHIPMENT_SELLABLE_ID` — 良品调拨 QC 确认目标
- `TRANSHIPMENT_UNSELLABLE_ID` — 不良品调拨 QC 确认目标
- `VENDOR_RETURN_ID_SELLABLE` — 良品供应商退货 QC 确认目标
- `VENDOR_RETURN_ID_UNSELLABLE` — 不良品供应商退货 QC 确认目标
- `LIQUIDATION` — 清算库位

### 规则 4：7 个 Picking 类走 allocated_qty 扣减
以下 actionType 在 isFrom=true 时扣减 `allocated_qty` 而非 `quantity`：
1. BATCH_PICKING(21)
2. B2B_PICKING(22)
3. PUT_WALL_PICKING_TOTE(23)
4. SINGLE_ORDER_OVERSIZE_PICKING_TOTE(25)
5. REPLENISH_PICK(13)
6. TRANSSHIPMENT_PICKING_BIN(124)
7. TRANSSHIPMENT_PICKING_STOCK(125)

### 规则 5：ADJUST(-2) 特殊处理
- `from=NONE`（跳过），只走 to 方向（isFrom=false）
- 盘盈：`available_qty > 0`；盘亏：`available_qty < 0`
- 代码中不乘以 -1：`inventoryTransaction.setQuantity(item.getAvailable_qty())`
- **其他所有场景 available_qty 都是正数，只有 ADJUST 盘亏为负数**

### 规则 6：MOVING_TOOLS(-1)
- `from=ANY_LOCATION, to=ANY_LOCATION`，两个方向都处理
- 不允许扣为负库存（空库存或库存不足时抛异常）
- 转移规则配置在 `yamibuy_wh.wh_movetool_rules` 表（70 条启用规则）

## 线上未使用的 actionType

以下 actionType 在 DB 日志表（当前表 + 2024/2025 历史表）中均无记录：
- **CANCEL_ORDER(81)**：无 CANCEL_ORDER_SLOT(location_type=27) 类型库位
- **RETURN_ORDER_UNSELLABLE(92)**
- **PACKING_PROBLEM_TOTE_NONE(310)**

## 数据库关键表

| 表 | 说明 |
|---|------|
| `yamibuy_wh.wh_inventory_transaction` | 聚合库存（warehouse, location, item 三元组） |
| `yamibuy_wh.wh_inventory_transaction_log` | 库存流水日志（3596 万条），按年分表：`_2024`、`_2025` |
| `yamibuy_wh.wh_storage_location` | 库位定义 |
| `yamibuy_wh.wh_location_type` | 库位类型定义 |
| `yamibuy_wh.wh_movetool_rules` | 通用工具转移规则（from_type, to_type, is_enabled） |

## 日志查询

Kibana 查询 adjustLocation 请求日志：
```
index: k8s-central-wms-service-log-*
query: "c.y.wms.cloud.service.LocationService : adjustLocation request :"
```

## 常用 DB 验证 SQL

```sql
-- 检查某个 actionType 是否在线上使用过（reference_type 用 = 查询，不用 LIKE）
SELECT rec_id, reference_type FROM yamibuy_wh.wh_inventory_transaction_log 
WHERE reference_type = '{actionType的name}' ORDER BY rec_id DESC LIMIT 5;

-- 检查某个库位类型是否有实际库位
SELECT location_no FROM yamibuy_wh.wh_storage_location 
WHERE location_type = {typeCode} LIMIT 5;

-- 查看通用工具转移规则
SELECT rec_id, from_type, from_description, to_type, to_description, description 
FROM yamibuy_wh.wh_movetool_rules WHERE is_enabled = 1;
```
