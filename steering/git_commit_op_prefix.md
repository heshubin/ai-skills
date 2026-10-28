---
inclusion: always
---
# Git Commit OP 号前缀规范

## 规则

每次执行 `git commit` 时，commit message 必须以 `[OP-XXXXX]` 格式的 OP 号作为前缀。

## 格式

```
[OP-XXXXX]<type>: <description>
```

示例：
```
[OP-34445]feat: 新增批次库存服务
[OP-34445]fix: 修复FIFO排序逻辑
[OP-12345]docs: 更新README文档
```

## 执行流程

1. 首次提交前，询问用户当前任务的 OP 号（如果上下文中没有）
2. 用户提供 OP 号后，在当前会话中记住该 OP 号，后续提交自动使用
3. 如果用户切换了任务/分支，主动确认是否需要更换 OP 号
4. commit message 中 `[OP-XXXXX]` 紧跟 type 前缀（feat/fix/docs/chore 等），中间无空格

## 禁止行为

- 禁止提交不带 `[OP-*]` 前缀的 commit message
- 禁止编造 OP 号，必须由用户确认
