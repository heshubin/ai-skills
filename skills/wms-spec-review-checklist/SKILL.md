---
name: wms-spec-review-checklist
description: 审查 WMS 需求/设计/实现计划（requirements.md、design.md、tasks.md），验证 adjustLocation 链路与 actionType 覆盖完整性时使用。触发词：spec 审查, 设计审查, 需求审查, requirements, design.md, tasks.md, actionType 覆盖, 设计漏洞
---
# WMS Spec 设计审查清单

当审查 WMS 相关的需求文档、设计文档或实现计划时使用本 skill。基于库存批次追踪项目中发现的 10 个设计漏洞总结而成。

## 触发场景

- 审查 WMS 功能的 spec 文档（requirements.md / design.md / tasks.md）
- 新增或修改涉及 adjustLocation 链路的功能设计
- 验证设计方案对所有 actionType 的覆盖完整性

## 审查清单

### 1. actionType 覆盖完整性
- [ ] 检查 `LocationProcessRelationEnum` 中所有枚举值是否在设计矩阵中覆盖
- [ ] 通过 DB 日志表验证 actionType 是否在线上实际使用（用 `=` 查询 reference_type，不用 LIKE）
- [ ] 标注"线上未使用"的 actionType，降低实现优先级
- [ ] 检查 `LocationProcessEnum` 中是否有枚举在 `LocationProcessRelationEnum` 中无对应定义（如 TRANSSHIPMENT_RECEIVE(127)）

### 2. 方向判断一致性
- [ ] 确认设计中的 from/to 方向判断与代码中 `fromType/toType + isIDLocationEnum()` 逻辑一致
- [ ] **忽略 Opera 字段**（ADD/SUBTRACT/CONSTANT 在代码中未使用，getOpera() 零调用）
- [ ] 特别检查 ADJUST(-2)：只走 to 方向，根据 available_qty 正负判断盘盈/盘亏
- [ ] 特别检查 6 种虚拟库位的跳过逻辑

### 3. 特殊 actionType 处理
- [ ] ADJUST(-2)：盘盈/盘亏的 available_qty 正负判断，不乘以 -1
- [ ] MOVING_TOOLS(-1)：不允许扣为负库存，规则在 wh_movetool_rules 表
- [ ] 7 个 Picking 类：allocated_qty 扣减而非 quantity（21,22,23,25,13,124,125）
- [ ] 5 个 SHIPPING_* 出库类：需记录 order_lot_consumption（31,32,33,34,50）
- [ ] 退货/取消类：需查询 consumption 表回补原批次
- [ ] to=NONE 的纯损耗场景（如 PACKING_PROBLEM_TOTE_NONE(310)）

### 4. 数据一致性
- [ ] 新增表与聚合库存表（wh_inventory_transaction）的数量一致性保证
- [ ] 事务边界：所有写入在同一个 @Transactional（adjustLocationTrans）中
- [ ] 库位释放（releaseLocation）时的数据清理策略 — 不能影响主流程
- [ ] 并发控制：SELECT FOR UPDATE + CHECK 约束 + 重试机制

### 5. 日志完整性
- [ ] 多批次操作时日志拆分逻辑（一个 item 多个批次 → 多条日志）
- [ ] before_quantity 的计算方案（基于聚合库存，多条日志共享）
- [ ] lot_id 字段在日志中的填充策略（三种场景：有消耗明细/有lot_id/都没有）

### 6. 跨服务一致性
- [ ] central-packing-service 的请求对象与 wms-cloud-service 保持同步
- [ ] HTTP 调用时新增字段的序列化/反序列化兼容性

## DB 数据验证方法

```sql
-- 1. 检查某个 actionType 是否在线上使用过
SELECT rec_id, reference_type, from_type, to_type, quantity 
FROM yamibuy_wh.wh_inventory_transaction_log 
WHERE reference_type = '{actionType的name}' ORDER BY rec_id DESC LIMIT 5;

-- 也查历史表
SELECT rec_id, reference_type FROM yamibuy_wh.wh_inventory_transaction_log_2025 
WHERE reference_type = '{actionType的name}' ORDER BY rec_id DESC LIMIT 5;

-- 2. 检查某个库位类型是否有实际库位
SELECT location_no, warehouse_number FROM yamibuy_wh.wh_storage_location 
WHERE location_type = {typeCode} LIMIT 5;

-- 3. 检查通用工具转移规则
SELECT rec_id, from_type, from_description, to_type, to_description, description 
FROM yamibuy_wh.wh_movetool_rules WHERE is_enabled = 1;

-- 4. 查看某个订单的退货日志（验证一单一单归还）
SELECT rec_id, from_type, from_location, to_type, to_location, item_number, quantity, reference_id 
FROM yamibuy_wh.wh_inventory_transaction_log 
WHERE reference_type = 'Return Order(sellable)' AND reference_id = '{订单号}';
```

## 常见漏洞模式

基于实际项目经验，以下是 WMS spec 审查中最容易遗漏的模式：

| 漏洞模式 | 说明 | 检查方法 |
|---------|------|---------|
| Opera 误导 | 依赖 Opera 字段做分支判断 | 确认代码中 getOpera() 零调用 |
| ADJUST 方向错误 | 按 from/to 两个方向处理 ADJUST | 确认 from=NONE 被跳过 |
| Picking 类遗漏 | 只覆盖 BATCH_PICKING 和 B2B_PICKING | 确认 7 个枚举值全部覆盖 |
| 虚拟库位遗漏 | 未跳过 isIDLocationEnum 的库位 | 确认 6 种虚拟库位全部跳过 |
| 线上未使用 | 为从未使用的 actionType 投入大量设计 | 先查 DB 日志确认是否使用 |
| 日志拆分遗漏 | 多批次操作仍生成一条日志 | 确认日志拆分的三种场景 |
| 库位释放影响 | 新增逻辑阻塞了库位释放 | 确认 try-catch 包裹，不影响主流程 |
