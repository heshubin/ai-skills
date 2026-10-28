---
inclusion: fileMatch
fileMatchPattern: "**/*.java,**/*.groovy,**/mapper/*.xml"
---
# 后端禁止行为 · 代码示例与案例

本文件是 `server_forbidden_rules.md`（always）的示例展开，规则本身以那份为准。内容原样拆自 myBot 版 server_forbidden_rules。

## 第 2 条：禁止在循环中逐条查询数据库（N+1 问题）

**识别信号**：`for (id : ids) { dao.queryById(id) }` 出现在业务方法里，就是 N+1。

**修复范式**：
- 新增支持 `Collection<T>` 入参的批量 DAO 方法，原单条方法不动（保持其他调用者行为不变）
- MyBatis XML 用 `<foreach>` 拼 `IN` 条件，保留原有 `GROUP BY / SUM` 聚合逻辑
- 加空集合守卫（`<choose>` 短路），防止 `IN ()` 语法错误

```java
// ❌ N+1
for (Integer taskId : taskIds) {
    orderPickDao.queryOrderItemByTaskId(taskId, wh);
}

// ✅ 批量
orderPickDao.queryOrderItemByTaskIds(taskIds, wh);  // 一次 IN 查询
```

```xml
<!-- MyBatis 批量 SQL 模板 -->
<select id="queryXxxByIds" resultType="...">
  <choose>
    <when test="ids == null or ids.size() == 0">
      SELECT NULL WHERE 1 = 0  <!-- 空集合守卫，防止 IN() 语法错误 -->
    </when>
    <otherwise>
      SELECT ... FROM ...
      WHERE id IN
      <foreach collection="ids" item="id" open="(" separator="," close=")">
        #{id}
      </foreach>
    </otherwise>
  </choose>
</select>
```

**真实案例（Bug#10360）**：`mergeOtherZoneItemsForSorting` 原实现对每个跨 Zone task_id
循环调 `queryOrderItemByTaskId`，有几个 Zone 就查几次。
修复：新增 `queryOrderItemByTaskIds`，一次批量查，DB 调用从 N 次降为 1 次。

## 第 4 条：禁止硬编码魔法数字/字符串

**写代码时就要做，不等审查提醒。**

**识别信号**：代码里出现裸露的 `0`、`1`、`2`、`-1` 或 `"S"`、`"Y"` 等字面量，且没有变量名解释其业务含义。

```java
// ❌ 读者不知道 1 和 2 代表什么
Integer.valueOf(1).equals(log.getAction())
locZoneMap.containsValue(2)
if (status == 1) { ... }

// ✅ 常量/枚举，语义自解释
PreoccupancyActionEnum.PREOCCUPANCY.getCode().equals(log.getAction())
locZoneMap.containsValue(ZONE2_ID)   // 同类文件顶部: private static final int ZONE2_ID = 2;
if (status == BatchStatus.PICKED.getCode()) { ... }
```

**强制自问（写完每行代码后）**：
> 我刚写的这个数字，读者能一眼看懂它的业务含义吗？不能 → 立刻提取常量。

## 第 8 条：`Collectors.toMap` 必须提供 merge function

不加 merge function 时遇到重复 key 会抛 `IllegalStateException`（Sonar Bug 规则）。

```java
// ❌ Sonar Bug：重复 key 时抛 IllegalStateException
.collect(Collectors.toMap(Item::getId, o -> o));

// ✅ 提供 merge function，重复时保留已有值并打警告
.collect(Collectors.toMap(
    Item::getId,
    o -> o,
    (existing, duplicate) -> {
        log.warn("duplicate key={}, keeping existing", existing.getId());
        return existing;
    }));
```
