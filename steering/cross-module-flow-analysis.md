---
inclusion: auto
name: cross-module-flow-analysis
description: 前后端联调、多服务协作、新接口复用已有方法、同一入口多模式分支时使用。触发词：联调, 跨模块, 调用链, 接口能调通流程不通, 新接口兼容, 前后端, 需求确认, 分支变量, 模式区分
---
# 跨模块流程分析规则

## 背景
分析前后端联调、多服务协作的流程时，经常出现"接口能调通但流程不通"的问题，根因是没有系统性地梳理完整调用链。

---

## 规则1：新接口引入前，必须验证它与现有流程的兼容性

引入一个新接口（尤其是复用已有服务方法）时，按以下顺序验证：

### 验证清单
- [ ] **该方法原来是为哪条路径设计的？** 找到它最早的调用方和设计意图
- [ ] **新路径的前置状态与原路径的前置状态是否一致？** 重点检查写库时机
- [ ] **该方法之后的步骤，是否依赖某些字段不被该方法改变？** 逆向检查后置校验
- [ ] **方法内是否有字段内容判断（非状态枚举）？** 这类判断最容易因字段复用而失效

### 示例（本次案例）
```
复用 bindZoneCartToSlot 给 PW 流程使用
  ✅ 原路径：pickingTaskFinish（Batch 拣完带 slot 提交）
  ❌ 新路径：PW 拣完后单独扫 CON slot，再扫 COMPLETE
  
  原路径：dealGenPickingFinish 在 bindZoneCartToSlot 之前 → parking_slot 始终为空
  新路径：bindZoneCartToSlot 在 dealGenPickingFinish 之前 → parking_slot 有值了

  漏查了后置校验：dealGenPickingFinish 里的 parking_slot 非空判断
  → 触发阻断
```

---

## 规则2：跨模块流程必须画完整调用链

涉及前端 → 接口 → 服务方法 → DB 的完整流程时，必须画出新旧两条链并对比。

### 格式模板
```
【旧流程】
用户动作A
  → POST /api/xxx
  → ServiceImpl.methodA()
    ├─ 前置状态：字段X=空，字段Y=OCCUPY
    ├─ 校验C：if(X非空) → 不触发 ✅
    └─ 写库：task.status=FINISH

【新流程】
用户动作A
  → 【新增】POST /api/bind-zone-cart-to-slot
  → ConsolidationService.bindZoneCartToSlot()
    └─ 写库：parking_slot="CON001", park_type=2  ← 前置状态改变了
  → POST /api/xxx
  → ServiceImpl.methodA()
    ├─ 前置状态：字段X="CON001"（有值！）
    ├─ 校验C：if(X非空) → 触发 ❌
    └─ 抛异常
```

---

## 规则3：前后端接口联调时的确认顺序

联调新接口前，按此顺序确认：

1. **接口入参** — 前端能提供哪些字段（PickingData 里有什么）
2. **后端服务方法签名** — 需要哪些参数，类型是否匹配
3. **前置条件** — 调用该接口时，数据库里的相关字段应该是什么状态
4. **后置影响** — 调用完成后，哪些字段会被写入/修改
5. **后续步骤** — 调用之后前端要做什么，后续接口是否依赖这里写入的字段

---

## 规则4：需求确认的5个问题模板

当接到一个涉及现有流程改造的需求时，按顺序问清楚这5个问题：

```
Q1: 复用的是哪个已有接口/方法？原来是为哪个场景设计的？
Q2: 新场景下，调用时序（before/after）和原场景有何不同？
Q3: 新步骤会改变哪些数据库字段的值？
Q4: 后续步骤中有没有依赖这些字段的校验？
Q5: 失败时是否可以重试？重试前是否需要回滚前一步的写入？
```

这5个问题覆盖了本次案例中所有需要确认的边界。

---

## 规则5：中间页面（中间步骤）的设计原则

当业务流程中需要插入一个强制中间步骤时（如本次的 PwConsolidationSlot 页面）：

- **成功才能离开**：中间步骤失败（接口报错），不允许跳过进入下一步
- **状态持久化**：通过本地缓存（PickingData）标记当前阶段，App 重启后能正确恢复到中间步骤
- **完成后清标记**：中间步骤完成后，清除缓存中的触发标志（如 `go_consolidation_slot=false`），防止下次进入时重复执行
- **兜底跳转**：进入中间页面时检查触发标志，不满足条件时直接 `replace` 到下一页，不留死路

```typescript
// 标准模式
useFocusEffect(useCallback(() => {
  const init = async () => {
    const data = await LocalDataStorage.getPickingandUserData();
    if (!data?.go_consolidation_slot) {
      navigation.replace(RootRoutes.PutWallFinish);  // 兜底
      return;
    }
    // 正常初始化...
  };
  init();
}, []));
```

---

## 规则6：同一入口支持多种模式时，分支变量必须用模式名区分，不能用行为名

### 背景（Bug#10279）

`confirm-arrival` 接口同时支持 Batch 模式（明细有 tote_no）和 PW 模式（明细 tote_no 为空）。两种模式都可以扫 Cart，但走不同的 UPDATE SQL：

| 模式 | 扫描对象 | 更新条件 | 说明 |
|------|---------|---------|------|
| Batch 扫单 Tote | Tote 编号 | tote_no + picking_task_id | 精确命中 |
| Batch 扫 Cart | Cart 编号 | cart_no + warehouse（批量） | 一台 Cart 多个 Tote |
| PW 扫 Cart | Cart 编号 | picking_task_id + cart_no | 精确，防 Cart 复用误更 |

错误命名 `isCartArrival` 覆盖了后两行，导致 PW 模式被错误地走进 Batch Cart 的宽泛 SQL，存在 Cart 复用误更风险。

### 规则

**同一个入口参数（如 Cart 编号）在不同模式下走不同路径时，分支变量名必须包含模式标识：**

```java
// ❌ 只描述行为（Cart 到达），模式不明确
final boolean isCartArrival = ...

// ✅ 包含模式名（Batch Cart），与 isPwArrival 形成清晰对照
final boolean isBatchCartArrival = !CollectionUtils.isEmpty(cartDetails)
        && cartDetails.stream().anyMatch(d -> StringUtils.hasText(d.getTote_no()));
```

### 扩展原则

新增一个分支时，先问：**"这个条件在其他模式下也能被满足吗？"**
- 能 → 名字里必须加模式限定词
- 不能 → 名字可以只描述行为
