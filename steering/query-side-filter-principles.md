---
inclusion: auto
name: query-side-filter-principles
description: 查询结果出现不该有的记录、需要决定改历史数据还是改查询条件、修复 SQL 后排查其他服务同名逻辑时使用。触发词：reference to multiple orders, 查出多条, size=2, 历史数据, NOT EXISTS, 查询侧过滤, 改字段, tote_no, Cart 释放, 多服务同步, queryPackingInfoList
---

# 查询侧过滤原则（历史数据不动，在查询端排除无效记录）

## 背景

2026-08 Bug#10XXX：跨 Zone 订单合并完成后，Zone2 tote 物理释放（`wh_storage_location.flag=0`），
但 `wh_picking_order.tote_no` 保留了真实使用过的 tote 编号（这是正确的历史记录）。
该 tote 随后被新订单占用，打包台扫该 tote 时查出两个订单，报错 "reference to multiple orders"。

错误思路：把 `wh_picking_order.tote_no` 改成 Zone1 tote 或置 NULL → 破坏了 Cart 释放判断链路。
正确思路：历史数据不动，在查询侧加过滤条件排除已失效的记录。

---

## 原则一：历史数据不动，查询侧过滤

**规则**：`wh_picking_order.tote_no` 等记录"真实发生过的操作"的字段，
不因后续流程改变而被修改或清空。

**做法**：当查询结果出现"不该出现的记录"时，优先在 SQL 查询侧加过滤条件：

```sql
-- 排除已完成合并的 Zone2 picking_order
AND NOT EXISTS (
    SELECT 1
    FROM wh_consolidation_task_detail ctd
    INNER JOIN wh_consolidation_task ct ON ct.rec_id = ctd.task_id
    WHERE ctd.picking_task_id = wpo.picking_task_id
      AND ctd.is_primary = 0        -- Zone2 侧
      AND ct.status = 80            -- COMPLETED，合并已完成
)
```

**判断依据**：问这个问题——「这条记录在当前业务状态下还有效吗？」
找到判断无效的系统状态字段，加到 SQL 里过滤，而不是去改源数据。

---

## 原则二：改字段前先问「会不会破坏其他链路」

**规则**：修改任何表字段之前，先搜索该字段在哪些 SQL/Service 里被读取，逐一评估影响。

**排查步骤**：
1. `grep_search` 字段名（如 `tote_no`），找出所有读取该字段的地方
2. 特别关注：该字段是否是某个判断链路的中间节点（如 Cart 释放判断链路）
3. 逐一评估每处读取：「如果字段值变了，这里的逻辑还正确吗？」

**本次案例**：
- `selectTotesByCartNos` 通过 `picking_cart.picking_task_id → picking_order.tote_no → storage_location.flag=3` 判断 Cart 是否可释放
- 若把 tote_no 改成 Zone1 tote（flag=3），Cart 释放判断会误判 → Cart 永远不释放
- 若把 tote_no 置 NULL，虽然 IS NOT NULL 过滤掉该行，但违背了"历史数据不动"的原则

---

## 原则三：循环/逐个执行时，警惕中间状态污染

**场景**：一个 Cart 上有多个 Tote，合并是一个 tote 一个 tote 执行的。

**规则**：当操作是循环/逐个执行时，第 N 次执行留下的副作用，可能影响第 N+1 次执行的判断。

**自检问题**：「如果这个操作执行到一半（只处理了部分数据），下一次执行时会不会读到被污染的中间状态？」

**本次案例**：
- T001、T002 两个 tote 逐个合并
- 若第一次合并把 T001 的 picking_order.tote_no 改成 Zone1 tote（flag=3）
- 第二次合并 T002 时，`releaseIfEmpty` 查 Zone2 Cart 时找到 T001 那条记录 → tote_no=Zone1 tote → flag=3 → 误判 Cart 仍有占用 → Cart 永远不释放

---

## 原则四：「查出了不该有的数据」类报错，优先看 SQL 过滤条件

**报错模式**：`size = 2`、`found multiple records`、`duplicate result` 等

**排查顺序**：
1. 先看 SQL：过滤条件是否覆盖了所有"失效态"？有没有遗漏的状态？
2. 再看数据流：哪个流程产生了"本不该被查到的记录"？
3. 最后考虑：是否需要在产生记录的流程中加状态标记，供查询侧过滤？

**不要第一反应去改数据**：改数据风险高、链路复杂，优先在查询侧解决。

---

## 原则五：修复 Bug 后主动排查涉及的其他服务

**场景**：同一段 SQL 或业务逻辑在多个微服务中都有副本（wms、packing、picking 等），修复一处后容易遗漏其他服务。

**规则**：修复某个 SQL 或方法后，必须主动 `grep_search` 同名方法/SQL id，确认其他服务是否有相同的逻辑需要同步修改。

**排查步骤**：
```
1. grep_search 方法名或 SQL id（如 queryPackingInfoList）
2. 列出所有服务中的出现位置
3. 逐一对比：各处的 SQL/逻辑是否有同样的缺陷？
4. 同步修复，不遗漏任何一处
```

**本次案例**：
- Bug 表现在打包台（`central-packing-service`），但 `wms-cloud-service` 也有同名 `queryPackingInfoList`
- 先修了 wms，差点遗漏 packing（实际主入口）
- 正确做法：修完一处立即 grep 全局，两处同步加 NOT EXISTS

**常见的多服务重复逻辑**：
- 打包查询：`wms-cloud-service` + `central-packing-service` 都有 `queryPackingInfoList`
- 库存调整：多个服务都调同一套库存 API
- 订单状态查询：wms / packing / picking 都可能有类似的 `wh_order_pool` 查询

---

## 快速决策表

| 问题类型 | 优先方案 | 禁止方案 |
|---|---|---|
| 查询结果包含失效记录 | SQL 加 NOT EXISTS / LEFT JOIN IS NULL 过滤 | 修改或清空历史数据字段 |
| 字段在判断链路中间 | 找到上游失效标志，在查询端排除 | 直接改字段值 |
| 循环执行的中间状态 | 确保每步操作对后续步骤幂等/无副作用 | 在中间步骤改写后续步骤依赖的字段 |
| 多订单误判问题 | 精化 SQL 过滤条件（加状态约束） | GROUP BY 去重（掩盖问题，不解决根因） |
