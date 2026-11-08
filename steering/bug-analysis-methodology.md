---
inclusion: auto
name: bug-analysis-methodology
description: 分析 bug 根因、输出可定位到文件行号的分析报告、给修复方案时使用。触发词：bug 分析, 根因, 定位问题, 排查, 为什么不显示, 数据缺失, 调用链, 修复方案, Bug#
---

# Bug 分析方法论

## 背景

2026-08 Bug#10360 的排查过程总结。一个好的 Bug 分析应该能让开发者
**仅凭分析输出就能定位到具体文件和行号**，并独立验证修复方案的正确性。

---

## 标准分析链路（四层递进）

### 第一层：数据层——先用数据说话

在看任何代码之前，先查数据库确认"现象是否属实"和"数据的实际状态"。

```
目标：用真实数据证明 bug 存在，并找出数据层面的差异点

步骤：
1. 查出现问题的业务实体（wall、order、task...）
2. 对比"应该有的数据"和"实际有的数据"
3. 找到缺失/错误的那一行，就是根因的入口
```

**Bug#10360 示例：**
```sql
-- wall_goods 只有 1 条，但 wh_picking_order_item 有 2 条（两个 Zone 各一）
wall_goods:                item=1021021961, goods_number=2  ← 有
                           item=1021024711                  ← 缺失！
wh_picking_order_item:     item=1021021961, picking_task_id=871723 (Zone1)
                           item=1021024711, picking_task_id=871724 (Zone2)
```
数据对比直接指向"wall_goods 初始化时漏了 Zone2 商品"。

---

### 第二层：调用链——从入口追到出口

确认数据差异后，沿业务链路从触发点往下追，**每一步都要写出文件名和方法名**。

```
格式：
  触发点（用户操作/接口）
    → 文件:行号 方法名()
      → 文件:行号 方法名()
        → 关键判断/写库点（标注字段和值）
```

**Bug#10360 示例：**
```
WMS App 扫 PW009 进入 Sorting

PutwallServiceImpl.java:164  initPutwall()
  └─ PutwallServiceImpl.java:243  checkRequest()
       └─ PackingService.java:420  queryCartDetail()
            └─ OrderPickDao: queryPickingCartById("PW009") → picking_task_id=871723
            └─ OrderPickMapper.xml:182  queryOrderItemByTaskId(871723) 
               ← 只取 Zone1 商品，Zone2(871724) 被 WHERE 条件过滤

PutwallServiceImpl.java:233  initWallSlotGoods()
  └─ assembleParams()  ← 只遍历 Zone1 的 items
  └─ batchInitWallGoods()  ← wall_goods 只插入 1 条
```

---

### 第三层：SQL——找到过滤掉数据的那条 WHERE

调用链找到后，定位执行的 SQL，看是哪个条件把数据过滤掉的。

```
目标：找到 SQL 的"罪魁祸首"条件，确认它是设计意图还是 bug
```

**Bug#10360 示例：**
```xml
<!-- OrderPickMapper.xml:182 -->
WHERE o.picking_task_id = #{picking_task_id}     ← 只匹配 871723
AND (item.picking_task_id = #{picking_task_id}   ← Zone2(871724) 被这里过滤
     OR item.picking_task_id IS NULL ...)
```
结论：这是**设计意图**（Zone 隔离），不是 SQL 写错了。
所以不改 SQL，而是在上层补偿。

---

### 第四层：根因总结——一句话 + 链路图

```
格式：
  [入口] 因为 [限制条件]，导致 [中间状态]，最终引发 [症状]

  链路图：
    A → B（此处因X条件漏掉Y数据）→ C（只有部分数据）→ D（提前判断完成）→ 症状
```

**Bug#10360 示例：**
```
queryCartDetail 通过 wh_picking_cart 只能取到 Zone1 的 picking_task_id，
queryOrderItemByTaskId 的 WHERE 条件只返回该 task 的商品，
导致 Zone2 商品在 wall_goods 初始化时被完全漏掉，
sorting 时只有 Zone1 数量，全部确认后误判为完成，提前提示 COMPLETE。
```

---

## 修复方案输出规范

分析完成后，修复方案必须包含以下内容，让人一眼能判断修的对不对：

```
1. 修复位置：文件名 + 方法名（不是泛泛说"在某层修"）
2. 为什么在这里修，而不在其他地方修（排除其他选项的理由）
3. 修了什么：改/新增的具体逻辑，用代码片段说明
4. 安全边界：哪些场景不受影响，为什么
5. 影响范围：列出该方法/SQL 的所有调用者，逐一确认行为不变
```

**Bug#10360 修复方案示例（标准格式）：**

```
修复位置：PutwallServiceImpl.java，initPutwall() 方法内

为什么在这里：
  - queryCartDetail 是通用方法，其他调用者只需 Zone1 商品，改它会影响其他链路
  - initPutwall 是 PW Sorting 的唯一入口，在此补偿精确、无副作用

修了什么：
  - checkRequest → checkRequestWithTaskId，同时返回 zone1TaskId
  - 新增 mergeOtherZoneItemsForSorting：查其他 Zone task_id，批量查商品，追加到 orders

安全边界：
  - 非跨 Zone 订单：consolidation_task_detail 为空，直接返回，零开销
  - 非 Zone Picking 仓库：同上，天然短路

影响范围：
  - queryCartDetail：完全不改，签名/实现/返回值不变
  - queryOrderItemByTaskId：完全不改，pickingTaskFinish 等调用者行为不变
  - PackingRestImpl.queryCartDetail REST 接口：不改，行为不变
```

---

## 快速自检清单（分析完成后核对）

- [ ] 第一层：已用真实数据证明差异（附 SQL 查询结果）
- [ ] 第二层：调用链每步都写了文件名+方法名+行号
- [ ] 第三层：找到了过滤/丢失数据的具体 SQL 条件
- [ ] 第四层：根因一句话能说清楚
- [ ] 修复方案：说明了为什么在这个位置修，而不在其他位置修
- [ ] 修复方案：列出了所有调用方，确认不受影响

---

## 常见陷阱

### 陷阱1：把"业务开关"当作判据
```
❌ 用 Zone Picking 开关判断是否执行补偿
   → 开关关闭时，已有跨 Zone 订单永远卡住无法打包

✅ 用数据本身（consolidation_task_detail 是否存在）做判断
   → 开关状态与数据状态解耦，历史数据不受影响
```

### 陷阱2：修了 SQL 而不是修了调用层
```
❌ 修改 queryOrderItemByTaskId 的 WHERE 条件让它返回多个 Zone 数据
   → 破坏了 Zone 隔离的设计意图，影响 pickingTaskFinish 等其他调用者

✅ 新增批量版本 queryOrderItemByTaskIds，原方法不动
   → 精确修复，无副作用
```

### 陷阱3：循环内查库（N+1）
```
❌ for (taskId in otherTaskIds) { queryOrderItemByTaskId(taskId) }

✅ queryOrderItemByTaskIds(otherTaskIds)  // 一次 IN 查询
```

### 陷阱4：数据与代码矛盾时深挖代码，不查数据变更审计
```
❌ 代码所有路径都带 restockable=1，却选中了 restockable=0 的库位 → 反复翻代码找漏洞
✅ 先按 rec_id 查编辑接口日志："location/batchEdit" and "request args:" and *<rec_id>*
   → 数据被人工中途修改，代码没问题
```
详见 steering：data-anomaly-audit-first.md

---

## 读取禅道 Bug 截图（2026-11，OP-40026 改 bug 时踩到）

禅道 Bug 的截图常常带着文字里没写的信息（红框位置、实际数值、弹窗文案、测试用的 Seal/Slot 号），必须逐张看完再下结论。

- zentao MCP 读不到 Bug 图片：`zentao_download_attachment` 只支持需求（story），对 Bug 的图片返回 HTTP 400。Bug 正文里的图片是 `file-read-<id>.png` 链接。
- 可用的办法：请主人先在 Playwright 浏览器里登录禅道，然后逐张执行：
  1. `browser_navigate` 打开 `https://bugs.yamibuy.tech/file-read-<id>.png`
  2. `browser_take_screenshot`（scale=device、fullPage=true、filename 放 `docs/tmp/<需求>-bugs/<bug号>-<id>.png`）
  3. `read_file` 打开这个 png 查看
- 截图刚保存时立刻 `read_file` 偶尔报 ENOENT，再读一次即可。
- 看图时把图里的业务单号（Seal、Slot、Tote、Batch、picking_task_id）记进分析，它们是查 gqc 数据、对日志的入口；同一个 Bug 的多张图可能来自不同次操作（单号不同），不要混成一次。
- 测试会在分析之后补图、改正文（OP-40026 Bug#10804：分析时「无截图」，之后补了图 14827，晚上又把期望改成「扫车，扫商品，扫 zone1 Tote」）。实现和推送前各 `zentao_get_bug` 一次，看 `actions` 里 `edited` 的 `history`（steps 的 diff）与 `lastEditedDate`；有新图就补看，期望变了就对照方案，冲突时先问再改。
- 写 report 的 gqc 回归步骤前，重查一次分析时用的样例单（OP-40026 Bug#10804：分析 14:38 时订单 1241111428 / 1241111430 就绪未合单，14:40 已被同事提前结束合单，晚上写报告时已不能用）。gqc 有多人同时测，样例单几小时内就会被用掉；回归步骤里给「找单 SQL + 条件」，不要只写具体单号，正在被别人分拣的单要标出来，提醒测试先协调。
