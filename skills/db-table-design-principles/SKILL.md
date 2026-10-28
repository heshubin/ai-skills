---
name: db-table-design-principles
description: 设计新表或审查表结构时使用，展开主键、索引、字段类型选择等原则（基于 WMS 实践）。触发词：表设计, 建表, DDL 审查, 主键, bigint 自增, 索引, 字段类型, 表结构
---
# 数据库表设计原则

当设计新表或审查表结构时使用本 skill。基于 WMS 项目实际经验总结。

## 触发场景

- 设计新的数据库表结构
- 审查 DDL 脚本
- 评估主键、索引、字段类型选择

## 主键设计原则

### 优先使用 bigint 自增主键
- 主键和外键关联使用 bigint，JOIN 性能远优于 varchar
- 自增主键无容量上限，不存在序号耗尽风险
- 如果需要人类可读的业务编号，单独用一个 varchar 字段 + UNIQUE INDEX

### 反模式：varchar 作为主键
- varchar 比较慢于整数比较，影响索引和 JOIN 性能
- 如果编号包含日期+序号（如 LOT250715000001），每天序号有上限风险
- 所有关联表的外键也必须是 varchar，存储和比较开销大

### 推荐模式
```sql
-- 推荐：bigint 自增主键 + varchar 可读编号
CREATE TABLE example (
  id bigint NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  code varchar(20) NOT NULL COMMENT '人类可读编号',
  PRIMARY KEY (id),
  UNIQUE INDEX uk_code (code)
);
```

## 字段冗余原则

### 避免冗余可通过关联查询获取的字段
- 如果字段值可以通过外键关联到其他表查询获取，不要冗余存储
- 冗余字段增加维护成本（源数据变更时需要同步更新）
- 例外：高频查询且关联表数据量大时，可以考虑冗余以避免 JOIN

### 示例
```
❌ 错误：在 lot_master 表中冗余 supplier_id
   → 可以通过 source_number(PO号) JOIN po_purchase_order 获取

✅ 正确：只存储 source_type + source_number，需要时关联查询
```

## 时间字段设计

- 使用 int 类型存储 Unix 时间戳（秒），不使用 datetime
- in_dtm 和 edit_dtm 统一使用 `int NOT NULL DEFAULT 0`
- 与现有系统保持一致（wh_inventory_transaction 等表均使用 int 时间戳）

## 外键约束原则

- 不使用数据库外键约束（FOREIGN KEY），通过应用层逻辑和统计校验控制数据一致性
- 外键约束在高并发场景下会增加锁竞争和死锁风险
- 数据一致性通过以下方式保障：
  1. 应用层在插入关联记录前校验主表记录是否存在
  2. 定期统计校验脚本检查孤立记录
  3. 事务保证同一次操作的原子性

## 索引设计原则

- 联合唯一索引的列顺序按查询频率从高到低排列
- 外键字段必须建立索引
- 避免在低基数字段（如 status）上单独建索引
- 联合索引可以覆盖前缀查询，避免重复建索引

## SQL 编写规范

- 写 SQL 时必须带上库名前缀，如 `yamibuy_wh.wh_lot_master`，不要只写表名
- 避免跨库查询时的歧义，也方便直接复制执行

```sql
-- ✅ 正确
SELECT lot_id, lot_no FROM yamibuy_wh.wh_lot_master WHERE status = 1;

-- ❌ 错误
SELECT lot_id, lot_no FROM wh_lot_master WHERE status = 1;
```

## 命名规范

- 表名：`wh_` 前缀 + 蛇形命名（如 `wh_lot_master`）
- 字段名：蛇形命名（如 `warehouse_number`）
- 索引名：`idx_` 前缀（普通索引）、`uk_` 前缀（唯一索引）、`fk_` 前缀（外键）
- 与 Java 实体类字段保持一致映射，禁止 MyBatis XML 中做字段名转换
