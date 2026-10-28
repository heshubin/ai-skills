---
inclusion: auto
name: sonar_coverage_rule
description: 补单测、提 PR 前检查覆盖率、Sonar Quality Gate 不过时使用。触发词：覆盖率, Sonar, SonarQube, Quality Gate, 补测试, 单测覆盖, 80%
---

# SonarQube 单测覆盖率规范

## 门槛要求

- **新代码覆盖率 ≥ 80%**（SonarQube Quality Gate）
- SonarQube 地址：`sonarqube.yamibuy.net`
- 适用于所有 Java/Kotlin 微服务项目

## 覆盖率检查时机

1. **编写新代码后**：立即为新增/修改的方法编写单测
2. **提交代码前**：运行相关测试确认通过
3. **合并 PR 前**：确认 SonarQube 扫描通过

## 工作流程

### Step 1: 定位未覆盖的新代码

```bash
# 查看当前分支相对于 master 的新代码
git diff origin/master..HEAD --stat
git diff origin/master..HEAD -- "src/main/java/**"
```

### Step 2: 编写单测

- 优先覆盖新代码（SonarQube 只检查新代码覆盖率）
- 关注覆盖率最低的文件优先补测
- 覆盖所有分支：if/else、异常处理、空值判断

### Step 3: 运行验证

```powershell
# Maven 项目运行单个测试
D:\maven\apache-maven-3.9.11\bin\mvn.cmd test -pl <模块名> -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" "-Dtest=完整类名"
```

## 测试编写规范（Java 项目通用）

| 项目 | 测试框架 | 测试文件后缀 |
|------|----------|-------------|
| wms-cloud-service | Spock (Groovy) | `*Test.groovy` |
| central-packing-service | Spock (Groovy) | `*Test.groovy` |
| 其他 Java 服务 | JUnit / Spock | `*Test.java` 或 `*Test.groovy` |

## 覆盖率提升策略

1. **优先覆盖新代码**：SonarQube 只检查新代码（自上次扫描基线以来的变更）
2. **关注覆盖率最低的文件**：从 SonarQube 指标页面找到覆盖率最低的文件优先补测
3. **Mock 私有字段**：Groovy 中用 `service.@fieldName = mock` 或反射方式注入
4. **覆盖所有分支**：if/else、异常处理、空值判断都需要测试用例
5. **静态方法 Mock**：使用 `Mockito.mockStatic()` 或 `StaticMockHelper`

## 常见踩坑点

- Lombok `@Data` 生成的字段在 Groovy 中用驼峰访问（如 `lotId` 而非 `lot_id`）
- Spy 模式下无法通过 `@` 语法访问 private 字段，需要用反射
- 依赖 `TokenUtil` 等静态工具类的方法需要 MockedStatic
- 方法内部调用链过深时，考虑拆分方法或用 Spy + doReturn 方式绕过
