---
name: java-code-review-checklist
description: 提交 PR 前自查或审查他人 Java 代码（Spring Boot + MyBatis）时使用，含 SOLID、异常、事务、性能检查项。触发词：代码审查, code review, CR, 自查, Java 审查, 提 PR 前检查
---
# Java 代码审查清单

提交代码前自查或审查他人 Java 代码时使用。基于 Spring Boot + MyBatis 项目实践总结。

## 触发场景

- 提交 PR 前的代码自查
- 审查他人的 Java 代码变更
- 重构或优化现有代码
- 提到"代码审查"、"code review"、"CR"、"自查"时

## SOLID 原则检查

### 单一职责（SRP）
- [ ] 每个类只负责一个业务领域
- [ ] Service 方法不超过 120 行，超过则拆分为 private 方法
- [ ] Controller 只做参数校验和调用 Service，不含业务逻辑

### 开闭原则（OCP）
- [ ] 新增功能通过扩展实现，而非修改已有代码
- [ ] 使用策略模式/模板方法替代大量 if-else 分支

### 依赖倒置（DIP）
- [ ] 依赖接口而非具体实现
- [ ] 通过构造器注入而非字段注入（推荐 @RequiredArgsConstructor）

## 异常处理规范

- [ ] 禁止空 catch 块，必须记录日志或向上抛出
- [ ] 业务异常使用自定义异常类，携带错误码
- [ ] 不要用 try-catch 包裹整个方法体，只包裹可能出错的代码段
- [ ] finally 块中不要有 return 语句
- [ ] 区分可恢复异常（业务校验失败）和不可恢复异常（系统错误）

```java
// ❌ 错误
try {
    doSomething();
} catch (Exception e) {
    // 空 catch，吞掉异常
}

// ✅ 正确
try {
    doSomething();
} catch (BusinessException e) {
    log.warn("业务校验失败: {}", e.getMessage());
    throw e;
} catch (Exception e) {
    log.error("系统异常", e);
    throw new SystemException("操作失败", e);
}
```

## 并发安全检查

- [ ] 共享可变状态是否有同步保护
- [ ] Spring Bean 默认单例，成员变量是否线程安全
- [ ] 数据库操作是否在事务内，事务边界是否合理
- [ ] 是否存在死锁风险（多表更新顺序是否一致）
- [ ] 乐观锁/悲观锁选择是否合理

## SQL 与数据访问

- [ ] 使用 `#{}` 参数化查询，禁止 `${}` 拼接（防 SQL 注入）
- [ ] 禁止 SELECT *，只查需要的字段
- [ ] 禁止循环内逐条查询（N+1 问题），使用 IN 批量查询
- [ ] 大批量操作使用分批处理（每批 500-1000 条）
- [ ] 查询是否命中索引，避免全表扫描

## 日志规范

- [ ] 关键业务操作有入口日志（方法入参）和出口日志（结果）
- [ ] 日志级别正确：业务警告用 warn，系统错误用 error，调试用 debug
- [ ] 日志中不包含敏感信息（密码、手机号、身份证等需脱敏）
- [ ] 使用占位符 `{}` 而非字符串拼接
- [ ] 禁止提交 System.out.println

```java
// ❌ 错误
log.info("处理订单：" + orderId + "，金额：" + amount);

// ✅ 正确
log.info("处理订单: orderId={}, amount={}", orderId, amount);
```

## 方法设计

- [ ] 方法参数不超过 5 个，超过则封装为对象
- [ ] 方法只做一件事，名称能准确描述其行为
- [ ] 避免布尔参数控制方法行为，拆分为两个方法
- [ ] 返回值不要返回 null 表示"没有数据"，使用 Optional 或空集合
- [ ] 集合参数和返回值做防御性校验（null check）

## 命名规范

- [ ] 类名：大驼峰，名词（如 OrderService、LotInventory）
- [ ] 方法名：小驼峰，动词开头（如 findByOrderId、calculateTotal）
- [ ] 常量：全大写下划线分隔（如 MAX_RETRY_COUNT）
- [ ] 布尔变量/方法：is/has/can 前缀（如 isValid、hasPermission）
- [ ] 禁止拼音命名，使用有意义的英文
