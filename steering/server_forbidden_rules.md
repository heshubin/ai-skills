---
inclusion: always
---
# 禁止行为清单

以下行为严格禁止，任何情况下都不得违反（示例与案例见 `server_coding_examples.md`，下称 examples，编辑 Java/Groovy/XML 时自动加载）：

1. **禁止 SQL/命令字符串拼接** — 防止注入攻击，必须使用参数化查询或 MyBatis `#{}` 占位符
2. **禁止在循环中逐条查询数据库（N+1 问题）** — 必须使用批量查询（IN 查询或 batch 操作）
   - 识别信号：`for (id : ids) { dao.queryById(id) }`。修复范式（批量 DAO + `<foreach>` + `<choose>` 空集合守卫）与 Bug#10360 见 examples
3. **禁止使用 SELECT \*** — 只查询需要的字段，避免过度获取
4. **禁止硬编码魔法数字/字符串** — 必须定义为命名常量或枚举，**写代码时就要做，不等审查提醒**
   - 强制自问：裸露的 `0/1/2/-1`、`"S"/"Y"`，读者能一眼看懂业务含义吗？不能 → 立刻提取常量
5. **禁止mybatis的xml字段映射和Java类有转换** - 保持数据库字段的原始映射到Java实体类
6. **禁止全路径导包（通配符导入）** — 禁止使用 `import xxx.*`，必须明确导入具体类名
7. **禁止代码无注释** — 所有类、方法、关键逻辑必须添加注释，确保代码可读性和可维护性
8. **`Collectors.toMap` 必须提供 merge function** — 重复 key 会抛 `IllegalStateException`（Sonar Bug 规则）
