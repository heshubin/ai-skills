---
name: mysql-nowait-row-lock
description: "用 MySQL 8 的 SELECT ... FOR UPDATE NOWAIT 做「撞到才拒绝」的行级加锁、替换按仓库等粗粒度 Redisson 锁时使用；含 3572 经 Spring/MyBatis 的异常类型、识别写法、H2 单测的限制。触发词：NOWAIT, FOR UPDATE NOWAIT, 3572, ER_LOCK_NOWAIT, CannotAcquireLockException, 行级加锁, 不等待加锁, 去掉仓库级锁, Operation in progress"
---

# MySQL NOWAIT 行级加锁（Spring Boot + MyBatis）

来源：OP-40026 B55（2026-11-18），把 Group 组建 / 打散的按仓 Redisson 锁改成只锁涉及的 wh_batch 行。

## 什么时候用

- 主人要求「数据不撞到一起就不互相影响，撞到才控制」，不要按仓库号、按动作加大锁。
- 操作的第一句本来就是按主键升序 `SELECT ... FOR UPDATE` 锁一组行（锁序第一步）。

## 落地要点

1. **不要直接改共用语句**。先查这条 FOR UPDATE 语句有几个调用方（领取、作废等）。只给需要「不等待」的场景新增一条 `...Nowait` 语句，列与条件完全相同，只在末尾多 `NOWAIT`。领取等仍用等待式语句。
2. **NOWAIT 只加在事务第一句**（锁序第一张表）。第一句失败时还没有写入，回滚即零写入。
3. 版本：MySQL 8.0.1 起支持；Aurora 3.x（8.0.2x）可用；MySQL 5.7 会报 1064 语法错误。

## 异常识别（关键坑）

- MySQL NOWAIT 冲突：错误码 **3572**（ER_LOCK_NOWAIT），SQLSTATE `HY000`。
- spring-jdbc 5.3 的 `sql-error-codes.xml`，MySQL 的 `cannotAcquireLockCodes = 1205,3572`。经 mybatis-spring 的 `MyBatisExceptionTranslator` 后，3572 和 **1205（锁等待超时）都变成 `CannotAcquireLockException`**。
- 所以**不能按异常类型判断**「被占用」。要沿 cause 链找 `SQLException.getErrorCode() == 3572`，并用 `IdentityHashMap` 去重防止 cause 成环。错误码定义成常量。
- 直接用 SqlSession（单测、无 Spring）时是 `PersistenceException`，cause 同样是这个 `SQLException`。
- 在事务方法内部捕获、转成业务异常（如 `XxxBusyException`）再抛出；异常穿过 `@Transactional` 代理时回滚。调用方：系统路径跳过本条数据、下一轮重试；手动路径返回「Operation in progress, please retry」。

## 单测

- **H2 1.4.200 能解析 `FOR UPDATE NOWAIT`，但不实现立即失败**：撞到同一行时等 H2 自己的锁超时（实测约 4 秒），错误码也不是 3572。
- 因此：
  - SQL 文本用 `XMLMapperBuilder` + `getBoundSql` 断言（含 NOWAIT，去掉 NOWAIT 后与等待式语句逐字相同，等待式语句不含 NOWAIT）。
  - H2 只证明「不重叠不互等」：另开连接 `autoCommit=false` 锁住 A 行不提交，被测操作只碰 B 行，能照常完成。
  - 3572 的识别用 mock 抛 `new CannotAcquireLockException(msg, new SQLException(msg, "HY000", 3572))`。另做 1205、1213、1064、连接断开的反例，断言它们原样外抛。
- 真实行为在测试环境（如 gqc）用两个会话实测一次。

## 选 NOWAIT 而不是「短等几秒」的理由

短等只能 `SET SESSION innodb_lock_wait_timeout = N`。连接池里的连接会把它带给后续业务，必须在 finally 里改回，而且它对整个事务的后续语句都生效。NOWAIT 是单条语句，没有这些副作用。
