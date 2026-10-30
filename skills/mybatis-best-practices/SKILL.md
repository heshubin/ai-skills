---
name: mybatis-best-practices
description: 编写或审查 MyBatis Mapper XML、DAO 接口，排查 SQL 执行异常或性能问题时使用。触发词：mybatis, mapper, dao, xml映射, 参数化占位符, foreach, resultMap, 批量插入
---
# MyBatis 开发最佳实践

编写或审查 MyBatis Mapper XML、DAO 接口时使用。基于 Spring Boot + MyBatis 项目实践总结。

## 触发场景

- 编写新的 Mapper XML 或 DAO 接口
- 审查 MyBatis 相关代码变更
- 排查 SQL 执行异常、性能问题
- 提到"mybatis"、"mapper"、"dao"、"xml映射"时

## 参数安全

### `#{}` vs `${}`
- `#{}` 预编译参数化，防 SQL 注入 → **始终优先使用**
- `${}` 字符串直接替换，仅用于动态表名/列名等无法参数化的场景

```xml
<!-- ✅ 正确：参数化查询 -->
<select id="findByItemNumber" resultType="LotInventory">
    SELECT lot_id, item_number, quantity
    FROM yamibuy_wh.wh_lot_inventory
    WHERE item_number = #{itemNumber}
</select>

<!-- ❌ 错误：字符串拼接，有注入风险 -->
<select id="findByItemNumber" resultType="LotInventory">
    SELECT lot_id, item_number, quantity
    FROM yamibuy_wh.wh_lot_inventory
    WHERE item_number = '${itemNumber}'
</select>
```

## 动态 SQL 规范

### if 标签
- 字符串判断同时检查 null 和空串
- 数字类型只检查 null（0 是合法值）

```xml
<!-- 字符串 -->
<if test="itemNumber != null and itemNumber != ''">
    AND item_number = #{itemNumber}
</if>

<!-- 数字（不要加 != ''，否则 0 会被跳过） -->
<if test="status != null">
    AND status = #{status}
</if>
```

### foreach 批量操作
- collection 属性：List 用 "list"，数组用 "array"，Map 中的 key 用 key 名
- 批量插入每批不超过 1000 条，避免 SQL 过长

```xml
<!-- 批量查询 -->
<select id="findByLotIds" resultType="LotInventory">
    SELECT lot_id, item_number, quantity
    FROM yamibuy_wh.wh_lot_inventory
    WHERE lot_id IN
    <foreach collection="lotIds" item="id" open="(" separator="," close=")">
        #{id}
    </foreach>
</select>

<!-- 批量插入 -->
<insert id="batchInsert">
    INSERT INTO yamibuy_wh.wh_lot_inventory
    (lot_id, item_number, warehouse_number, location_no, quantity)
    VALUES
    <foreach collection="list" item="item" separator=",">
        (#{item.lotId}, #{item.itemNumber}, #{item.warehouseNumber},
         #{item.locationNo}, #{item.quantity})
    </foreach>
</insert>
```

### where 标签
- 使用 `<where>` 替代手写 `WHERE 1=1`，自动处理多余的 AND/OR

```xml
<!-- ✅ 推荐 -->
<select id="search" resultType="LotMaster">
    SELECT lot_id, lot_no, sku
    FROM yamibuy_wh.wh_lot_master
    <where>
        <if test="lotNo != null and lotNo != ''">
            AND lot_no = #{lotNo}
        </if>
        <if test="sku != null and sku != ''">
            AND sku = #{sku}
        </if>
    </where>
</select>
```

## ResultMap vs ResultType 选择规范

### 核心原则：SQL 返回类型必须匹配实际查询的数据结构

| 场景 | 推荐方式 | 说明 |
|------|---------|------|
| 查询单表，字段与实体类一一对应 | `resultMap` 或 `resultType=实体类` | 标准用法 |
| 跨表查询，字段来自多张表 | `resultType=HashMap` 或专用 DTO | 禁止复用其他表的 resultMap |
| 聚合查询（GROUP BY + SUM/COUNT） | `resultType=HashMap` 或专用 DTO | 聚合结果不属于任何一张表 |
| 只查少量字段（如 lot_id + quantity） | `resultType=HashMap` | 不值得为此创建 DTO |

### ❌ 反模式：用占位符凑 resultMap

```xml
<!-- ❌ 错误：查的是 wh_inventory_transaction_log，却用 wh_lot_inventory 的 resultMap -->
<!-- 需要 0 AS rec_id 等占位符来凑齐 resultMap 的字段，代码不优雅，误导读者 -->
<select id="queryTsPreoccupancyLotDetails" resultMap="lotInventoryMap">
    SELECT 
        0 AS rec_id,
        #{warehouseNumber} AS warehouse_number,
        l.to_location AS location_no,
        l.item_number,
        l.lot_id,
        ABS(SUM(l.quantity)) AS allocated_qty,
        0 AS quantity,
        '' AS in_user, 0 AS in_dtm, '' AS edit_user, 0 AS edit_dtm
    FROM yamibuy_wh.wh_inventory_transaction_log l
    ...
</select>

<!-- ✅ 正确：跨表聚合查询用 resultType=HashMap，只返回需要的字段 -->
<select id="queryTsPreoccupancyLotDetails" resultType="java.util.HashMap">
    SELECT 
        l.to_location AS location_no,
        l.item_number,
        l.lot_id,
        ABS(SUM(l.quantity)) AS allocated_qty
    FROM yamibuy_wh.wh_inventory_transaction_log l
    ...
</select>
```

### 为什么占位符凑 resultMap 是坏实践？
1. **误导读者**：`0 AS rec_id` 让人以为 rec_id 有业务含义，实际只是为了满足 resultMap
2. **脆弱**：resultMap 字段变化时，所有复用它的 SQL 都要跟着改
3. **违反单一职责**：一个 resultMap 应该只服务于一张表的标准查询

### ResultMap 字段映射规范

- 禁止在 XML 中做字段名转换（如 `column="lot_id" property="lotNumber"`）
- 数据库字段与 Java 实体类保持原始映射
- 使用 MyBatis 的驼峰自动映射（`mapUnderscoreToCamelCase=true`）或保持一致命名

## N+1 问题防范

```java
// ❌ 错误：循环内逐条查询
for (String lotNo : lotNoList) {
    LotMaster lot = lotMasterDao.findByLotNo(lotNo);
    // ...
}

// ✅ 正确：批量查询后转 Map
List<LotMaster> lots = lotMasterDao.findByLotNos(lotNoList);
Map<String, LotMaster> lotMap = lots.stream()
    .collect(Collectors.toMap(LotMaster::getLotNo, Function.identity()));
```

## 分页查询

- 使用 PageHelper 或手动 LIMIT，禁止查询全表后内存分页
- 深分页优化：使用 `WHERE id > #{lastId} LIMIT #{pageSize}` 替代 `LIMIT offset, size`

## 常见陷阱

| 陷阱 | 说明 | 解决方案 |
|------|------|---------|
| Integer 类型 `!= ''` | MyBatis 中 Integer 与空串比较会报错 | 数字类型只判断 `!= null` |
| foreach 空集合 | 空集合会生成 `IN ()` 语法错误 | 调用前检查集合非空 |
| 批量插入过大 | 超过 max_allowed_packet | 分批插入，每批 500-1000 |
| 缓存脏读 | 一级缓存在同一 SqlSession 内有效 | 写操作后刷新缓存或关闭一级缓存 |
| LIKE 注入 | `LIKE '%${keyword}%'` | 使用 `LIKE CONCAT('%', #{keyword}, '%')` |
| 「渲染 SQL 与改造前逐字相同」的回归断言必失败，只折叠空白也不够 | MyBatis 3.5.6 的 `DynamicContext` 用分隔符为一个空格的 `StringJoiner` 拼接各个文本节点（3.4.x 是每段之后追加一个空格，结论相同），每个 `<if>`、`<include>` 边界都会插入一个空格，`<if>` 不成立时也一样；原文在边界处本来没有空白时，把连续空白折叠成一个空格也消不掉它。例：值清单 `…,IFNULL(#{parent_task_id},0))` 在最后一个 `)` 前加 `<if>`，渲染为 `IFNULL(?,0) )`，改造前是 `IFNULL(?,0))`；`…limit 1))upc,` 改成 `<include refid="…"/>,` 后渲染为 `upc ,`，改造前是 `upc,` | 改造前后用同一组参数取 `BoundSql.getSql()`，两边经同一个 `normalizeSql(s) = s.replaceAll("\\s+", " ").replaceAll(" ?([(),]) ?", "$1").trim()`（先折叠连续空白，再去掉括号与逗号两侧的空格，最后去掉首尾空白）后断言相等；方法放在 `src/test/java` 的测试公共工具类里，用 Groovy 写时替换串用单引号 `'$1'`（双引号是 GString，编译不过）（OP-40026 `insertPickingTask`、`queryPickingData`，2026-10-30，o7-r2 审查修正） |
| 单表 UPDATE 里多列 `IF` 共用一个判定列 | MySQL 单表 UPDATE 的 SET 按书写顺序从左到右求值，后面的赋值读到的是前面已改过的值；如 `a = IF(a = 0, …)` 之后再写 `b = IF(a = 0, …)`，b 永远看不到 0 | 每列只判断自身的未写值：`b = IF(b = #{bUnset}, …, b)`（OP-40026 首次领取两列，2026-10-30） |
