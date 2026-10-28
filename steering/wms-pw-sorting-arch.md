---
inclusion: auto
name: wms-pw-sorting-arch
description: 修改或排查 PW Sorting、Putwall 初始化、跨 Zone 订单 sorting 数量不全时使用。触发词：PW, Sorting, Putwall, initPutwall, wall_goods, 跨 Zone, Zone2 商品不显示, queryCartDetail, queryOrderItemByTaskId, Bug#10360
---

# WMS PW Sorting 跨 Zone 架构约束

## 背景

2026-08 Bug#10360：PW 跨 Zone 订单合并完成后，sorting 时只显示 Zone1 数量就提示 COMPLETE，
Zone2 商品从未出现在 sorting 界面。根因是 wall_goods 初始化时漏掉了 Zone2 商品。
整理成约束，防止后续同类问题。

---

## 核心数据结构认知

### wh_picking_cart 只记录一个 picking_task_id

```
wh_picking_cart.picking_task_id = Zone1 的 task_id
```

PW Cart（如 PW009）只有一个 `picking_task_id`，指向 Zone1（Primary Zone）的拣货任务。
Zone2 的 `picking_task_id` 存在于 `wh_consolidation_task_detail` 里，Cart 本身不记录。

### 跨 Zone 订单在 wh_picking_order 有两条记录

```sql
-- 同一个 order_no，分属两个不同的 picking_task_id
wh_picking_order: order_no=1241108270, picking_task_id=871723  ← Zone1
wh_picking_order: order_no=1241108270, picking_task_id=871724  ← Zone2
```

### queryOrderItemByTaskId 只返回指定 task 的商品

```xml
WHERE o.picking_task_id = #{picking_task_id}
  AND (item.picking_task_id = #{picking_task_id} OR ...)
```

这是设计意图——Zone 隔离。但在 PW Sorting 场景下需要**所有 Zone 的商品**。

---

## PW Sorting 初始化链路（Bug#10360 修复后）

```
WMS App 扫 PW009 进入 Sorting

PutwallServiceImpl.initPutwall()
  └─ checkRequestWithTaskId(cart="PW009")        ← 查 Zone1 orders + zone1TaskId
       └─ PackingService.queryCartDetail()         ← 只取 Zone1 商品（设计如此，不改）
  └─ checkConsolidationCompleted()                ← Zone Picking 门控
  └─ mergeOtherZoneItemsForSorting()              ← [补偿] 查 Zone2 商品并追加
       ├─ selectOtherZonePickingTaskIds()           ← 查 consolidation_task_detail
       └─ queryOrderItemByTaskIds([zone2TaskId])   ← 批量查 Zone2 商品（一次查库）
  └─ initWallSlotGoods()                          ← wall_goods 写入包含全部 Zone 商品
```

---

## 关键约束

### 约束1：修复只在 initPutwall 层做，不改 queryCartDetail

`queryCartDetail` 是通用方法，其他调用者（如直接 REST 查询）只需要当前 Zone 商品。
跨 Zone 补偿逻辑**只属于 PW Sorting 初始化**这条链路。

### 约束2：判据用数据本身，不用 Zone Picking 开关

```
❌ 错误：if (ZonePickingSwitchGuard.isEnabled()) { 补偿... }
✅ 正确：直接查 consolidation_task_detail，查不到就跳过
```

原因：Zone Picking 开关控制「新订单是否走分 Zone」，不控制「已有跨 Zone 订单的后续处理」。
开关关闭后，已完成合并的订单仍需正确 sorting 才能打包。若依赖开关，这些订单将永远卡住。

### 约束3：补偿查询必须批量，禁止循环内查库

```java
// ❌ N+1 写法
for (Integer otherTaskId : otherTaskIds) {
    queryOrderItemByTaskId(otherTaskId, wh);  // 有几个 Zone 就查几次
}

// ✅ 批量查询
queryOrderItemByTaskIds(otherTaskIds, wh);  // 一次查库
```

已新增 `OrderPickDao.queryOrderItemByTaskIds`（对应 `OrderPickMapper.xml` 批量版 SQL）。

---

## 修复涉及的方法/文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `PutwallServiceImpl.java` | `checkRequest` → `checkRequestWithTaskId`，新增内部类 `CheckRequestResult` | 透传 zone1TaskId |
| `PutwallServiceImpl.java` | 新增 `mergeOtherZoneItemsForSorting()` | Zone2 商品补偿 |
| `WhConsolidationTaskDetailMapper.java` | 新增 `selectOtherZonePickingTaskIds()` | 查其他 Zone task_id |
| `WhConsolidationTaskDetailMapper.xml` | 新增对应 SQL | 有空集合守卫防 IN() |
| `OrderPickDao.java` | 新增 `queryOrderItemByTaskIds()` | 批量查多个 task 的商品 |
| `OrderPickMapper.xml` | 新增批量版 SQL | 保留原有 GROUP BY+SUM 逻辑 |

---

## 快速排查 PW Sorting 相关问题的 SQL

```sql
-- 1. 确认 wall 和 orders
SELECT w.id, w.wall_id, w.cart_number FROM YMB_WH.walls w
WHERE w.warehouse_number = '002' AND w.cart_number = 'PW009'
ORDER BY w.created_at DESC LIMIT 1;

-- 2. 查 wall_goods，看商品数量是否正确
SELECT wg.* FROM YMB_WH.wall_goods wg
WHERE wg.slot_id IN (SELECT id FROM YMB_WH.wall_slots WHERE wall_id = {wall_id});

-- 3. 查 wh_picking_order_item，确认两个 Zone 的商品
SELECT poi.rec_id, poi.order_no, poi.item_number, poi.item_quantity,
       poi.picking_quantity, poi.sorting_pick_quantity, poi.picking_task_id
FROM yamibuy_wh.wh_picking_order_item poi
WHERE poi.order_no = {order_no};

-- 4. 查 consolidation detail，确认跨 Zone 任务状态
SELECT ctd.* FROM yamibuy_wh.wh_consolidation_task_detail ctd
WHERE ctd.task_id IN (
    SELECT rec_id FROM yamibuy_wh.wh_consolidation_task WHERE order_id = {order_no}
);
```

---

## 典型症状识别

| 症状 | 可能原因 | 排查方向 |
|------|---------|---------|
| Sorting 界面商品数量不全，提前 COMPLETE | wall_goods 缺少 Zone2 商品 | 查 wall_goods vs wh_picking_order_item 的商品数差异 |
| wall_goods 商品数 < wh_picking_order_item 总数 | initPutwall 时 Zone2 商品未补偿 | 确认 mergeOtherZoneItemsForSorting 是否执行，查日志 |
| sorting_pick_quantity 为 0 | consolidation 后未同步更新该字段 | 手动执行数据修复 SQL |
