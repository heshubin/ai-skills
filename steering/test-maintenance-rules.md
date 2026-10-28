---
inclusion: fileMatch
fileMatchPattern: "**/src/test/**/*.groovy,**/*Test.groovy,**/*Spec.groovy"
---
# 单测维护规范（全局）

## 背景

2026-08 OP-37299 项目 CI 构建连续失败多轮，同类错误反复出现，整理成规范避免后续再犯。

---

## 四类常见失败根因

### 第1类：方法签名参数数量不匹配（最常见）
Java 实现新增/删除参数后，测试文件里所有 mock 该方法的地方都必须同步修改。

失败特征：Spock 报 "Too few invocations" 或 "Too many arguments"

常见遗漏：
- 只改了全 wildcard 的 mock（如 `(_, _, _, _)`），漏掉了带具体值的（如 `(_, _, "keyword", _)`）
- 改了 `then:` 验证，忘了 `given:` 里的 stub
- 改了 `setup()` 里的委托，忘了各个测试里的单独覆盖 stub
- 只改了一个测试文件，忘了另一个也有同名方法的 mock

修复步骤：
1. grep_search 搜索方法名，找出所有测试文件中的全部出现位置
2. 逐一检查：setup()、given:、then:、辅助方法
3. 并行调用 str_replace 一次性全部修完

### 第2类：文件编码破坏（中文乱码）
见全局 steering：file-encoding-rules.md

### 第3类：实现行为变更，测试期望值未同步
Java 实现逻辑改了，但测试能编译通过、运行时断言失败。

失败特征：`Condition not satisfied: result.x == y`，实际返回值与预期不同
检查方向：对比实现当前行为，更新测试期望值，加注释说明新行为

典型案例：`resolveToteNoForArrival` 从"返回 Tote 编号"改为"直接返回 Cart 编号（批量到达模式）"，
测试仍期望 Tote 编号，需要更新期望值。

### 第4类：Spock then: strict interaction 覆盖 setup() 委托
Spock 中 `then:` 块里的 `1 * mock.method(...)` 会覆盖 `setup()` 里设置的 `>> { ... }` 委托，
导致委托内部逻辑不执行，间接调用（如 `correctStatusByDerived`）也就不会被触发。

失败特征：`correctStatusByDerived` 显示 "0 invocations"，但代码看起来应该被调用

解决方案：当某个 case 需要"验证方法被调用"同时"执行委托逻辑"时：
- 在该 case 的 `given:` 里单独 stub 委托（`>> { svc.checkAndPromoteToReady(taskId) }`）
- `then:` 里只验证最终结果，不写 strict interaction（去掉 `1 * confirmToteArrivalInTx(...)`）

---

## 提交前自检清单

修改测试文件后，git commit 之前必须执行：

- [ ] grep_search 搜索方法名，确认所有出现位置都已修改
- [ ] 分别检查了 setup()、given:、then: 和辅助方法
- [ ] 同时修改了全 wildcard 参数和带具体值的参数两种形式
- [ ] 本次会话改了几个测试文件，就 read_file 检查几个文件的中文字符

---

## Spock 测试失败快速诊断

| 失败信息 | 最可能的原因 | 解决方向 |
|---|---|---|
| "Too few invocations (0 invocations)" | 参数数量不匹配 / strict 覆盖委托 / 值不匹配 | grep_search 找所有 mock，检查参数数量 |
| "Too many arguments" | 参数数量多了 | 减少参数 |
| "Condition not satisfied: result.x == y" | 实现行为变更 | 对比实现，更新期望值 |
| "Unexpected character" | 中文字符乱码 | git checkout 干净版本，用 str_replace 重改 |
