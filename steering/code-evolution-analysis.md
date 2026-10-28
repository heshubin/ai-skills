---
inclusion: auto
name: code-evolution-analysis
description: 改共用方法或老校验前、新需求改变前置状态、判断防御代码留还是删时使用。触发词：共用方法, 调用方, 老校验, 防御代码, 空转代码, 前置状态, 状态机, 业务开关, 历史遗留
---

# 代码演化分析规则

## 背景
本规则来自一次真实案例的沉淀：Zone Picking 新需求引入后，一段历史遗留的空转防御代码因业务状态变化被意外触发，阻断了正常流程。经过多轮分析才定位根因并找到最优解。

---

## 规则1：在新需求改动前，必须先找出所有「共用方法」

当需要改一个被多条路径调用的私有/共用方法时，**必须先枚举所有调用方**，分析每条路径在调用该方法时的前置状态。

```
检查步骤：
1. grep 搜索方法名，找出所有调用点
2. 对每个调用点，画出调用链（入参从哪里来，前置状态是什么）
3. 判断改动是否会影响每条路径的行为
```

反面案例（本次 bug）：
- `dealGenPickingFinish` 被 `pickingTaskFinish`（Batch）和 `pickingTaskFinishForPw`（PW）共用
- Zone Picking 新增 `bindZoneCartToSlot` 改变了 PW 路径的前置状态（`parking_slot` 有值了）
- 没有分析共用方法的影响范围，导致旧校验阻断新流程

---

## 规则2：防御代码三问，判断留还是删

每次遇到防御性校验时，问以下三个问题：

**Q1：它防御的场景真的会发生吗？**
- 是 → 继续问 Q2
- 否 → 可以考虑删除，但需要说明理由

**Q2：它防御的场景是否已被其他校验覆盖？**
- 是 → 这是冗余代码，应该删除
- 否 → 继续问 Q3

**Q3：它的判断依据是否稳定（不随业务演化而改变语义）？**
- 稳定（如状态机枚举）→ 保留
- 不稳定（如字段内容字符串判断）→ 重构为更稳定的方式

```
本次案例结论：
parking_slot 非空校验
  Q1: PW 路径下 parking_slot 会有值 → Zone Picking 前：否。Zone Picking 后：是
  Q2: status 校验已经覆盖同一场景 → 是（Cart 停放后 status 必然不是 OCCUPY）
  结论：冗余，直接删除
```

---

## 规则3：共用方法的职责边界

当一个方法被多条业务路径共用时，**方法只允许关心最小公共契约**，不允许掺入任何路径特有的业务状态判断。

```java
// ❌ 错误：dealGenPickingFinish 掺入了 Parking Slot 的业务含义
if (StringUtils.isNotEmpty(dbPickingCart.getParking_slot())) {
    throw ...
}

// ✅ 正确：只关心状态机，不关心业务位置
if (dbPickingCart.getStatus() != OCCUPY || dbPickingTask.getStatus() != PICKING) {
    throw ...
}
```

**识别信号**：如果一个共用方法里出现了 `if (XXX路径特有字段)` 的判断，就是越权了。

---

## 规则4：新需求改变「前置状态」时的必查项

当新需求在调用链中间插入一个新步骤，且该步骤会写库/改状态时，必须：

1. 检查后续步骤的所有校验（特别是共用方法里的校验）
2. 确认新写入的字段/状态是否会触发后续校验
3. 画出完整的新旧调用链对比图

```
模板：
旧流程：步骤A → 步骤B → 校验C（此时字段X = ""）→ 步骤D
新流程：步骤A → 【新步骤N（写入字段X = "CON001"）】 → 步骤B → 校验C（此时字段X 有值！）→ ❌
```

---

## 规则5：状态机判断优于字段内容判断

数据库字段的内容可能随业务演化而复用（如 `parking_slot` 被复用存 CON Slot 编码），但专门设计的状态枚举字段（如 `park_type`）语义是稳定的。

```
优先级：
1. 状态枚举字段（park_type、status）→ 最优，不随内容改变语义
2. 字段是否为空（isNotEmpty）→ 次优，但容易因字段复用而失效
3. 字段内容字符串匹配（startsWith("CON")）→ 避免，脆弱
```

---

## 规则6：用数据本身做判断，不用业务开关

当需要判断"是否执行某段补偿/扩展逻辑"时，**判据应该是相关数据是否存在，而不是业务功能开关的状态**。

**原因：开关控制"新增功能是否启用"，不控制"已有数据的后续处理"。**

```
典型场景：
  - Zone Picking 开关：控制「新订单是否走分 Zone 拆分」
  - 不控制：「已完成合并的跨 Zone 订单能否正确 sorting/打包」

  开关关闭时，已拆分的历史订单仍在数据库里。
  若补偿逻辑依赖开关，这些订单将永远卡在中间状态，无法打包。
```

```java
// ❌ 错误：用开关短路
if (ZonePickingSwitchGuard.isDisabled(zoneConfigService, warehouseNumber)) {
    return;  // 开关关闭 → 跨 Zone 订单永远 sorting 不了
}

// ✅ 正确：用数据本身短路
List<Integer> otherTaskIds = consolidationDetailMapper
        .selectOtherZonePickingTaskIds(orderNos, zone1TaskId, warehouseNumber);
if (ListUtils.isNullorEmpty(otherTaskIds)) {
    return;  // 没有跨 Zone 数据 → 非跨 Zone 场景 / 非 Zone Picking 仓库，天然短路
}
```

**适用场景**：
- 新功能引入的补偿逻辑
- 判断"该订单是否属于某种类型"（如跨 Zone、跨仓库、特殊渠道）
- 任何"有数据才执行，没数据跳过"的逻辑

**开关的正确用法**：只用于"是否开启新功能的入口"（如是否生成跨 Zone 任务），不用于"已生成的数据如何处理"。

---

## 适用场景

以上规则适用于以下场景触发时的自检：
- 需求要求在现有流程中插入新步骤
- 需要修改一个被多个业务路径调用的共用方法
- 发现一段防御性代码逻辑不清晰
- 新需求与老代码发生冲突，找不到根因
- **判断某段补偿/扩展逻辑的触发条件时**（用数据还是用开关）
