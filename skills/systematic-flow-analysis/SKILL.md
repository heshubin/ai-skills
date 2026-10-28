---
name: systematic-flow-analysis
description: 在现有流程插入新步骤判断兼容性、分析"接口能调通但流程不通"、新代码触发旧校验的 bug 根因、联调前确认调用顺序和字段依赖时使用。触发词：流程分析, 兼容性, 流程不通, 根因分析, 调用顺序, 字段依赖, 新步骤插入
---
# Skill: 系统化流程分析

## 触发场景
- 需求要求在现有流程中插入新步骤，不确定是否兼容
- 新接口/方法上线后出现"接口能调通但流程不通"的问题
- 需要分析一个 bug 的根因：新代码触发了旧校验
- 联调前需要确认前后端的调用顺序和字段依赖关系

## 使用方式
告诉我：
1. 是新需求分析还是 bug 根因分析
2. 涉及的接口/方法名称（或业务操作名称）
3. 涉及的服务模块（如 wms-cloud-service / central-picking-app）

我会按照以下步骤完成分析。

---

## 分析步骤

### Step 1：识别核心路径
- 找出所有相关的接口和服务方法
- 确认被复用/改动的方法的所有调用方（grep 搜索）
- 标记新路径和旧路径的入口

### Step 2：画新旧调用链对比图
```
【旧流程】
用户操作
  → POST /api/xxx（接口）
  → ServiceImpl.method()（服务方法）
    ├─ 前置状态：字段A=值, 字段B=值
    ├─ 校验：if(条件) → 触发/不触发
    └─ 写库：字段变更

【新流程】
用户操作
  → 【新增步骤】POST /api/new（新接口）
    └─ 写库：字段A=新值  ← 前置状态改变点
  → POST /api/xxx
  → ServiceImpl.method()
    ├─ 前置状态：字段A=新值（与旧流程不同！）
    ├─ 校验：触发/不触发 → 结果
    └─ 后续
```

### Step 3：逆向检查后置校验
对新流程中每个"写库动作"，检查后续步骤里是否有依赖该字段的校验：
- 查找该字段在后续代码中的所有引用
- 判断新写入的值是否会触发这些校验

### Step 4：输出结论
- ✅ 兼容：新流程不影响现有校验
- ❌ 冲突：指出冲突点，给出修复方案
- ⚠️ 需关注：有潜在风险，建议补充测试

### Step 5（可选）：需求确认问题清单
如果是需求分析阶段，输出5个确认问题：
```
Q1: 复用的方法原来为哪个场景设计？
Q2: 新场景的调用时序与原场景有何不同？
Q3: 新步骤会改变哪些数据库字段？
Q4: 后续步骤是否有依赖这些字段的校验？
Q5: 失败时是否可以重试？是否需要回滚？
```

---

## 真实案例参考

**案例：PW 跨Zone拣货完成流程（Zone Picking 需求）**

```
问题：PW Cart 扫 CON Slot 后，再扫 COMPLETE 报错 "this pickcart status is invalid"

旧流程：
  扫 COMPLETE
  → pickingTaskFinishForPw()
  → dealGenPickingFinish()
    ├─ parking_slot = ""（PW 不走停车场，始终为空）
    ├─ if(isNotEmpty(parking_slot)) → 不触发 ✅
    └─ task.status = FINISH

新流程（Zone Picking 新增步骤后）：
  扫 CON Slot（新增中间步骤）
  → bindZoneCartToSlot()
    └─ 写库：parking_slot = "CON002010001"  ← 前置状态改变了！
  扫 COMPLETE
  → pickingTaskFinishForPw()
  → dealGenPickingFinish()
    ├─ parking_slot = "CON002010001"（有值了！）
    ├─ if(isNotEmpty(parking_slot)) → 触发 ❌
    └─ 抛异常

根因：旧校验从未被触发过（空转代码），Zone Picking 改变了前置状态后首次被触发
修复：删除冗余校验（status 校验已完全覆盖同一场景）
```
