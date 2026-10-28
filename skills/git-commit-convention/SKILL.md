---
name: git-commit-convention
description: 编写或审查 commit message 时使用，基于 Conventional Commits 并强制 [OP-XXXXX] 前缀。触发词：提交信息, commit message, git commit, 提交规范, conventional commits, OP 前缀
---
# Git 提交信息规范

编写 commit message 时使用。基于 Conventional Commits 规范，适配团队工作流。

## 触发场景

- 编写 git commit message
- 审查提交历史
- 提到"提交信息"、"commit message"、"git commit"时

## 提交格式

```
[OP-XXXXX]<type>(<scope>): <subject>

[可选 body]

[可选 footer]
```

- `[OP-XXXXX]` 前缀必填，与 steering `git_commit_op_prefix.md` 一致：`]` 与 type 之间无空格；OP 号必须由用户确认，禁止编造
- `(<scope>)` 可选，没有明确模块时写成 `[OP-XXXXX]<type>: <subject>`

### type 类型

| 类型 | 说明 | 示例 |
|------|------|------|
| feat | 新功能 | feat(lot): 新增批次库存扣减逻辑 |
| fix | 修复 Bug | fix(picking): 修复拣货数量计算错误 |
| refactor | 重构（不改变功能） | refactor(location): 简化库位转移判断逻辑 |
| perf | 性能优化 | perf(inventory): 批量查询替代循环查询 |
| docs | 文档变更 | docs: 更新批次追踪方案设计文档 |
| style | 代码格式（不影响逻辑） | style: 统一缩进和空行 |
| test | 测试相关 | test(lot): 新增批次创建单元测试 |
| chore | 构建/工具/依赖变更 | chore: 升级 Spring Boot 版本 |
| revert | 回滚提交 | revert: 回滚批次扣减逻辑变更 |

### scope 范围

scope 对应模块或功能区域，常用值：
- 后端：`lot`、`inventory`、`picking`、`location`、`receive`、`packing`、`order`
- 前端：`wh-web`、`rn-app`、`react-web`
- 通用：`config`、`deps`、`ci`

### subject 规则

- 使用中文描述
- 不超过 50 个字符
- 不以句号结尾
- 使用祈使语气（"新增"而非"新增了"）

### 关联 OP 号

OP 号放在 subject 前的 `[OP-XXXXX]` 前缀里（必填）；footer 中的 `OP: #12345` 可选保留，便于检索：

```
[OP-12345]feat(lot): 新增批次库存查询接口

实现按仓库、SKU、批次号查询批次库存的 REST 接口

OP: #12345
```

## 提交粒度

- 一个 commit 只做一件事
- 禁止单次 commit 包含不相关的多个变更
- 大功能拆分为多个小 commit，每个 commit 可独立编译通过

## 示例

```
[OP-12345]feat(lot): 新增批次主表和库存表 DDL

新增 wh_lot_master 和 wh_lot_inventory 两张表，
支持批次创建、库存追踪功能。

OP: #12345
```

```
[OP-12346]fix(picking): 修复多批次拣货时数量分配错误

FIFO 排序后未正确累减剩余需求量，导致最后一个批次
被多扣。增加剩余量归零判断。

OP: #12346
```
