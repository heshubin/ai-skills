---
inclusion: fileMatch
fileMatchPattern: '**/*.java'
---

# 代码质量规则（强制）

## 1. 禁止使用全限定类名

在 Java 文件中声明字段、参数、局部变量时，**必须使用 import 导入类名**，禁止使用全限定名。

```java
// ❌ 禁止
private com.yamibuy.wms.cloud.service.lot.LotInventoryService lotInventoryService;

// ✅ 正确
import com.yamibuy.wms.cloud.service.lot.LotInventoryService;
private LotInventoryService lotInventoryService;
```

## 2. 新增 @Autowired 字段时必须同步添加 import

每次新增 `@Autowired` 注入时，必须：
1. 在文件顶部添加对应的 import 语句
2. 确认 import 没有使用通配符 `import xxx.*`（除非项目已有此风格）

## 3. strReplace 后必须验证

每次使用 strReplace 修改文件后，必须立即用以下方式之一验证改动已生效：
1. `grepSearch` 搜索新增的关键代码
2. `readFile` 读取修改区域确认内容
3. `getDiagnostics` 检查编译错误

## 4. 禁止使用 PowerShell Set-Content 修改 Java 文件

PowerShell 的 `Set-Content` 会破坏 UTF-8 编码（丢失 BOM 或转换编码）。
修改 Java 文件内容只能使用 `strReplace` 或 `fsWrite`。

## 5. 编译验证必须覆盖所有受影响模块

修改代码后编译验证时，必须编译所有依赖链上的模块：
```
wms-cloud-api → wms-cloud-service → wms-cloud-rest
```
如果修改了 wms-cloud-api，需要先 `mvn install -pl wms-cloud-api`，再编译下游模块。

## 6. 新增方法必须同步添加到接口和实现类

在接口中添加方法签名后，必须立即在实现类中添加实现，并确认编译通过。
