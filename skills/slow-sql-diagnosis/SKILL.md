---
name: slow-sql-diagnosis
description: >
  MySQL/MariaDB 慢 SQL 诊断与优化。当需要分析慢查询、排查 SQL 性能问题、优化数据库查询时使用。
  触发词：慢查询, slow query, SQL优化, EXPLAIN, 执行计划, 查询超时, 数据库性能, CTE物化, 索引优化, JOIN慢, 全表扫描
---

# MySQL 慢 SQL 诊断

系统化排查慢 SQL 的根因并给出修复方案。

## 血泪教训（从实际踩坑中总结）

以下是真实排查中犯过的错误，**每次诊断前必须回顾**：

### ❌ 错误 1：看到数据量小就假设"不会慢"

**踩坑经过：** CTE 只有 68 行，三层 JOIN 的组合也就几千次，按理毫秒级完成。于是假设"数据量小不是问题"，把注意力放在索引缺失和 SQL 改写上。

**真相：** MySQL 优化器把 CTE merge 回了原表（5300万行），每次 JOIN 实际是在原表上扫描。68 行的假象完全是错的。

**教训：** 永远用 `EXPLAIN FORMAT=TREE` 确认 MySQL 实际在哪张表/哪个数据集上操作。不要相信 CTE 的行数 = JOIN 时的扫描行数。

### ❌ 错误 2：一上来就想改写 SQL 和加索引

**踩坑经过：** 看到慢 SQL 后立即想出了 3 种改写方案（拆 UNION、限定 reference_type、加复合索引），花了大量时间讨论优化方向。结果最终的修复只是加一行 `LIMIT 10000`。

**真相：** 问题不在 SQL 逻辑本身，而在 MySQL 优化器的执行策略选择（merge vs materialize）。改写 SQL 逻辑是过度工程化。

**教训：** 诊断的第一步永远是 `EXPLAIN FORMAT=TREE`，搞清楚优化器到底在做什么。先理解现状，再决定改什么。

### ❌ 错误 3：根据特定数据反推通用方案

**踩坑经过：** 看到当前 item 的流转路径是"RECG0001 → C21945"和"RECG0001 → Stock → RS → C21945"，就把优化 SQL 限定为这两种固定路径。被用户指出"这只适用于当前 case"。

**真相：** `moving tools` 可以把货物从任意库位移到任意库位，路径跳数不确定。原 SQL 的三层通用回溯设计是正确的。

**教训：** 优化 SQL 前必须理解业务全貌。看代码中的枚举值、看所有可能的数据路径，不能只基于一条数据反推通用方案。

### ❌ 错误 4：把"加索引"当万能解法

**踩坑经过：** 分析了索引选择性、提议加复合索引。虽然索引确实能改善，但没有直击核心问题。

**真相：** 即使加了索引，如果 MySQL 仍然选择 merge CTE，性能提升有限（从22秒到几秒，而非毫秒）。真正的根因是优化器的执行策略。

**教训：** 加索引是对症下药的手段之一，但如果病因是"优化器决策错误"，索引只是缓解而非根治。

---

## 正确的诊断流程

### 第一步：获取完整 SQL 和参数

- 从慢查询日志、Kibana、APM 中获取完整 SQL
- 确认实际执行参数（不同参数可能有完全不同的执行计划）
- 记录实际耗时和返回行数

### 第二步：EXPLAIN FORMAT=TREE（最重要的一步）

```sql
EXPLAIN FORMAT=TREE <完整SQL>;
```

**这是诊断的核心。** 不是 `EXPLAIN`（表格格式信息不够），必须是 `FORMAT=TREE`。

**阅读 TREE 输出时重点看：**

1. **是否物化了 CTE？**
   - 看到 `Materialize CTE rec if needed` → 物化了（好）
   - 看到直接 `Index lookup on k using <index>` → merge 了（可能有问题）

2. **每层 JOIN 实际查的是什么数据源？**
   - `Index lookup on r1 using <auto_key>` → 在物化临时表上查（好）
   - `Index lookup on k using IDX_xxx (column=...)` → 在原表上查（可能有问题）

3. **过滤器的位置**
   - `Filter: ...` 出现在 Index lookup 之后 → 说明索引没覆盖所有条件，需要回表过滤

### 第三步：验证"为什么优化器选了这个计划"

搞清楚 TREE 中慢的那一步，然后用数据验证：

```sql
-- 确认 JOIN 时索引命中了多少行
SELECT COUNT(*) FROM table WHERE <join_condition_column> = '<实际的值>';

-- 确认 CTE 的实际行数
SELECT COUNT(*) FROM (<CTE的SELECT语句>) t;

-- 确认热点值
SELECT <column>, COUNT(*) as cnt FROM table 
WHERE <基础过滤条件> 
GROUP BY <column> ORDER BY cnt DESC LIMIT 10;
```

### 第四步：确定瓶颈模式并修复

#### 模式 A：CTE 被 Merge 而非物化（本次案例）

**确认方法：** EXPLAIN TREE 中没有 `Materialize CTE`

**修复：** CTE 末尾加 `LIMIT <大数字>`
```sql
WITH rec AS (
  SELECT ... FROM big_table WHERE ...
  ORDER BY ...
  LIMIT 10000  -- 强制物化，不影响业务（正常不可能超过这个数）
)
```

**原理：** 带 LIMIT 的子查询在语义上无法 merge 展开，MySQL 被迫物化。物化后会在临时表上自动建 auto_key 索引，后续 JOIN 在小表上进行。

#### 模式 B：索引选择性差 / 热点值

**确认方法：** `SELECT COUNT(*) WHERE index_col = '热点值'` 返回极大数字

**修复：** 加复合索引（把高选择性字段放前面），或强制物化避免回原表

#### 模式 C：JOIN 范围条件导致扇出

**确认方法：** `a.time > b.time` 这类范围 JOIN，验证每行 a 匹配了多少行 b

**修复：** 加时间窗口限制、或用子查询只取最相关的一条

#### 模式 D：回表代价高

**确认方法：** EXPLAIN 显示 `Using where` 且索引不覆盖过滤字段

**修复：** 建覆盖索引或复合索引

#### 模式 E：NOT LIKE / 函数导致索引失效

**确认方法：** WHERE 中有对列使用函数或 NOT LIKE

**修复：** 用正向 IN 替代、或用生成列

### 第五步：验证修复效果

```sql
-- 修复前
EXPLAIN FORMAT=TREE <原SQL>;
-- 记录执行计划

-- 修复后  
EXPLAIN FORMAT=TREE <新SQL>;
-- 对比：是否出现了 Materialize / 索引命中行数是否下降

-- 执行对比
-- 确认结果集一致
-- 确认耗时改善
```

### 第六步：确认通用性

**必须检查：**
- 修复是否适用于所有可能的参数值？（不同 item、不同 location）
- 修复是否在极端情况下仍然安全？（数据量极大/极小时）
- LIMIT 值是否合理？（正常业务范围内不会超过该值）

---

## 给方案时的检查清单

给出优化方案前，逐条过：

- [ ] 我用 `EXPLAIN FORMAT=TREE` 确认了优化器的实际执行路径吗？
- [ ] 我确认了慢在哪一步（而非猜测）吗？
- [ ] 修复方案是针对根因还是只缓解症状？
- [ ] 修复后的 SQL 语义与原 SQL 完全等价吗？
- [ ] 方案适用于所有场景还是只适用于当前 case？
- [ ] 我有没有过度工程化？（能一行解决的别改十行）

---

## 复盘：正确的排查路线 vs 我走过的弯路

```
正确路线：
SQL → EXPLAIN FORMAT=TREE → 发现没物化 CTE → 验证 merge 后的代价 → 加 LIMIT 强制物化 → 完成

我的弯路：
SQL → 看 CTE 行数少，假设 JOIN 不慢 → 看索引情况 → 提议加复合索引 
→ 改写 SQL 拆成 UNION → 被指出不通用 → 重新分析业务路径 
→ 再次提议加索引 → 最终才想到看 EXPLAIN TREE → 发现 CTE 没物化 → 完成

多走了 5 步，多花了 80% 的时间。
```

**根本教训：永远先做 `EXPLAIN FORMAT=TREE`，别急着给方案。**
