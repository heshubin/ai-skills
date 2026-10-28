---
inclusion: fileMatch
fileMatchPattern: '**/*.sql'
---

# MySQL 兼容性规范

编写 SQL 脚本时必须兼容 MySQL 5.7 和 8.0。

## DDL 注意事项

1. `CREATE TABLE IF NOT EXISTS` — 可以使用
2. `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — MySQL 5.7 不支持，需要用 PREPARE STATEMENT：
   ```sql
   SET @sql = (SELECT IF(
     (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='yamibuy_wh' AND TABLE_NAME='xxx' AND COLUMN_NAME='yyy') = 0,
     'ALTER TABLE yamibuy_wh.xxx ADD COLUMN yyy bigint NOT NULL DEFAULT 0',
     'SELECT 1'
   ));
   PREPARE stmt FROM @sql;
   EXECUTE stmt;
   DEALLOCATE PREPARE stmt;
   ```
3. MySQL 保留字必须加反引号：`match`、`order`、`group` 等
4. CHECK 约束在 MySQL 5.7 中会被解析但不执行，MySQL 8.0.16+ 才真正生效

## 数据类型

- 时间戳用 `int NOT NULL DEFAULT 0`（秒级）
- 自增主键用 `bigint NOT NULL AUTO_INCREMENT`（大表）或 `int NOT NULL AUTO_INCREMENT`（小表）
- 字符串用 `varchar(N) NOT NULL DEFAULT ''`
- 状态字段用 `tinyint NOT NULL DEFAULT 1`

## 索引命名

- 主键：`PRIMARY KEY (column)`
- 唯一索引：`uk_` 前缀，如 `uk_lot_no`
- 普通索引：`idx_` 前缀，如 `idx_item_warehouse`
- 联合索引按查询频率排列列顺序
