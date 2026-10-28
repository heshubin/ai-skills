---
inclusion: auto
name: data-anomaly-audit-first
description: 数据状态与代码逻辑矛盾、怀疑数据被人工或其他系统改过时使用。触发词：数据异常, 数据和代码矛盾, 谁改了数据, batchEdit, 人工修改, 审计日志, edit_dtm, restockable, 搜不到
---
# 数据异常排查：先查"谁改了数据"，再推演代码

## 背景（2026-09 X42611 案例）

现象：bin 库位 X42611 的 restockable=0，却挂着一条 JOB 生成的补货任务，导致上架校验返回"库位不可用"。

我的实际排查路径（绕了远路）：
1. 解析 Kibana 链接、查 trace、查 DB，定位到补货任务挡住了上架 ✅
2. 默认相信"restockable 初始化就是 0、没改过"，开始在代码里找"为什么 restockable=0 还能被选中"
3. 翻遍 GenerateRestockMapper / LRMapper / LRService，所有选 bin SQL 都有 `restockable=1`，陷入"数据和代码互相矛盾"
4. 查 batchEdit 日志时用 `X42611` 做关键字，0 条，误判为"没人改过"
5. 用 JOB 日志里带 `restockable = 1` 的 SQL + 返回了 X42611 做反证，推出"生成时是 1，后来被改"
6. 用户用 `"location/batchEdit" and "request args:" and *386426*` 一条查询直接找到人工修改记录

**根因不在代码，在数据被人工中途修改。** 第 3 步出现矛盾时，就该立刻做第 6 步。

---

## 规则1：数据与代码矛盾时，第一步查数据变更审计

当出现"代码逻辑上不可能产生这个数据，但它确实存在"时，按以下优先级判断：

```
1. 数据被人工/其他系统中途改过      ← 最常见，最先查
2. 线上代码版本与本地不一致
3. 代码存在未覆盖的分支
```

**禁止**在没有查审计日志之前，就长时间深挖代码分支。

## 规则2：编辑接口按主键 rec_id 检索，不按业务编号

管理后台的编辑接口通常只传主键，不传业务编号：

| 字段 | 修改入口 | 请求里的标识 |
|---|---|---|
| restockable / max_sku / size_id / zone_id | `/location/batchEdit` | `locationId` = wh_storage_location.rec_id |
| 锁定 / 解锁（warehouse_number 加减 Lock） | `batchLockOrUnLock` | `locationIds` = rec_id |

Kibana 检索模板（central-wms-service）：

```
"location/batchEdit" and "request args:" and *<rec_id>*
```

时间窗：从数据创建（或最后一次可信状态）到异常动作发生时刻，宁宽勿窄。

## 规则3："搜不到"不等于"没发生"

检索结果为 0 时，先怀疑关键字，不要直接下结论：

- 至少换 2 种标识再判断：业务编号（X42611）、主键（386426）、接口路径
- 确认索引对不对（`k8s-central-wms-service-log-*` 和 `k8s-job-central-wms-job-log-*` 是两个索引）
- 确认时间窗覆盖到了（日志和 DB 时间戳都是 UTC）

## 规则4：edit_dtm / edit_user 不能证明"没人改过"

`edit_dtm`、`edit_user` 只记录**最后一次**写入，会被后续 JOB 覆盖。
本案库位 edit_user=MERGE_JOB，掩盖了之前的人工 batchEdit。

- ❌ "edit_dtm 只有一个值，所以字段没被改过"
- ✅ 字段历史值只能靠审计日志（接口请求日志 / binlog）确认

## 规则5：用户给的"初始值"要验证，不能当事实

用户说"初始化就是 0"，往往只描述了创建那一刻。中途是否被人改过，用户自己也可能不知道。
把它当假设，用审计日志确认后再作为推理前提。

## 规则6：时间换算必须用工具算

本案我两次脑算时间戳出错。Unix 时间戳 ↔ UTC ↔ 北京时间一律用 PowerShell 算：

```powershell
[DateTimeOffset]::FromUnixTimeSeconds(1790258183).UtcDateTime
```

---

## 标准排查顺序（数据状态异常类问题）

```
1. 确认现象：Kibana trace 定位接口 + 返回 0 的 SQL
2. 查 DB 当前状态：异常记录 + 关联记录（in_user / in_dtm / edit_user）
3. 查"谁在什么时候写的"：
   - 关联数据的生成方（JOB 看 k8s-job-*，接口看 k8s-central-*）
   - 异常字段的修改入口（按 rec_id 检索编辑接口日志）
4. 对齐时间线（工具换算 UTC）
5. 仍解释不通，再深挖代码分支
```

## 自检清单

- [ ] 数据与代码矛盾时，是否先查了编辑接口审计日志？
- [ ] 检索用的是 rec_id 还是业务编号？两种都试了吗？
- [ ] 检索 0 条时，是否排查了关键字 / 索引 / 时间窗？
- [ ] 有没有把 edit_dtm / edit_user 当成"没被修改"的证据？
- [ ] 用户给的初始状态，是否验证过？
- [ ] 时间戳是否用工具换算？
