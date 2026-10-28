---
inclusion: fileMatch
fileMatchPattern: '**/wms-cloud-service/**'
---

# WMS 项目编码踩坑指南

本次库存批次追踪开发中踩过的坑，后续开发时注意避免。

## 1. RedissonClient 必须用 RedissonClientImp

项目使用 yami-core 封装的 `com.yami.core.common.RedissonClientImp`，不是原生的 `org.redisson.api.RedissonClient`。
- 代码中注入：`@Autowired private RedissonClientImp redissonClient;`
- 测试中 Mock：`def redissonClient = Stub(com.yami.core.common.RedissonClientImp)`
- 错误写法：`@Autowired private RedissonClient redissonClient;` ← 会导致注入失败

## 2. MyBatis XML 参数映射必须与 Java 实体字段名一致

- 如果实体类用驼峰（如 `lotId`），XML 中必须写 `#{lotId}`
- 如果实体类用下划线（如 `lot_id`），XML 中必须写 `#{lot_id}`
- 踩坑案例：`#{item.lot_id}` 应该是 `#{item.lotId}`（因为 LocationItemRequest 用驼峰命名）

## 3. 实体类命名风格要跟项目已有风格一致

- LotMaster / OrderLotConsumption → 驼峰命名（新实体）
- LotInventory → 下划线命名（与项目老实体 InventoryTransaction 风格一致）
- 不要混用，否则 MyBatis resultMap 映射会出错

## 4. DDL 脚本必须兼容 MySQL 5.7

- GQC 环境是 MySQL 8.0，但生产可能是 5.7
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 在 MySQL 5.7 不支持，需要用 PREPARE STATEMENT 方式
- `CREATE TABLE IF NOT EXISTS` 可以正常使用
- MySQL 保留字（如 `match`）必须加反引号

## 5. Spock 测试中 Groovy 的 import 不会自动提示

- `java.util.concurrent.TimeUnit` 需要手动 import，Groovy 不会自动导入
- Mock 类型要写全限定名：`Stub(com.yami.core.common.RedissonClientImp)`

## 6. INSERT ON DUPLICATE KEY UPDATE 比 查询+判断+插入/更新 更安全

- 并发场景下 `if (exists) update else insert` 有竞态条件
- 改用 `INSERT ... ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)` 原子操作
- 需要有唯一索引支撑

## 7. Redis 原子自增的过期时间设置

- 不要用 `isExists() + set(0)` 的方式初始化，有竞态条件
- 正确做法：直接 `incrementAndGet()`，当返回值为 1 时设置过期时间
- Redis INCR 命令在 key 不存在时自动从 0 开始

## 8. SQL 扣减必须加非负保护条件

- `UPDATE ... SET quantity = quantity - #{qty} WHERE ... AND quantity >= #{qty}`
- 配合 CHECK 约束 `CHECK (quantity >= 0)` 双重保护
- allocated_qty 同理：`AND allocated_qty + #{allocatedQty} >= 0`

## 9. 批次处理异常不应阻塞主流程（视场景而定）

- 收货创建批次失败 → 不抛异常，归入 LOT_LEGACY（向后兼容）
- 预占批次失败 → 只记 warn 日志，不影响预占主流程
- 出库记录消耗失败 → 不抛异常，避免影响出库
- 但批次库存扣减/增加失败 → 必须抛异常回滚（数据一致性）
