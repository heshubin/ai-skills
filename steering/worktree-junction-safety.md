---
inclusion: auto
name: worktree-junction-safety
description: 删除 git worktree、清理 node_modules 目录联接（junction）时使用，防止顺着联接把主仓库的 node_modules 删掉。触发词：worktree remove, 删除 worktree, node_modules 联接, junction, mklink /J, 清理 worktree
---

# 删除 worktree 前先拆 node_modules 联接

## 事故（2026-11-05，OP-40026）
worktree 里的 `node_modules` 是指向主仓库的目录联接（`mklink /J`），这样就不用重复 `npm install`。编排者对 `WMS-front-end-ver` 和 `central-picking-app-ver` 执行了 `git worktree remove --force`。git 删目录时顺着联接进入了主仓库：
- `D:\code\WMS-front-end\wms-rn\node_modules` 被删掉一部分，`.bin`、`@babel`、`@eslint`、`@react-native/*` 都没了。删到一半，因为路径太长（Filename too long）中断。
- `D:\code\central-picking-app\node_modules` 被删空。

后果是后面的 workflow 跑不了 eslint，Metro 也打不了包，只能重新 `npm install`。

## 正确的删除顺序
1. 先只删联接本身：`cmd /c rmdir "<worktree>\node_modules"`。WMS App 的 node_modules 在 `<worktree>\wms-rn\node_modules`。`rmdir` 删联接时不会碰目标目录里的内容。
2. 确认联接已经没了：`Test-Path "<worktree>\node_modules"` 的结果是 False。
3. 再执行 `git -C <主仓库> worktree remove <worktree路径>`。
4. 主仓库的 node_modules 还在，可以用 `Get-ChildItem <主仓库>\node_modules\.bin` 抽查。

## 禁止
- 联接还在的时候执行 `git worktree remove --force`
- 用 `Remove-Item -Recurse` 删除联接或者联接所在的目录
- 删除失败（Filename too long、Permission denied）之后换更强的命令重试。应该先查清楚有没有联接、是谁占用了文件

## 怎么查有没有联接
```powershell
Get-ChildItem <worktree> -Recurse -Depth 2 -Directory -Force | Where-Object { $_.LinkType -eq 'Junction' } | Select-Object FullName, Target
```

## 恢复
在主仓库执行 `npm install --no-audit --no-fund`，按现有的 package-lock 补齐依赖。装完用 `git status` 确认 package.json 和 package-lock.json 没有改动；有改动就用 `git checkout --` 撤销。

## 机械拦截（2026-11-08 加）
光靠规则提醒不够，执行的 agent 可能读不到这份 steering。所以 kiroWP 工作区加了 PreToolUse hook `.kiro/hooks/guard-junction-delete.json`，调用脚本 `d:/code/kiroWP/docs/scripts/guard-junction-delete.ps1`：
- 执行 `git worktree remove`，或 `Remove-Item`/`ri`/`rm` 带 `-r`/`-Recurse` 之前，检查目标目录 3 层以内有没有目录联接。查找时不进入 `.git`、`node_modules`、`target` 这几个目录。
- 发现联接就以 exit 2 拦下命令，提示先用 `cmd /c rmdir` 拆掉联接。
- 递归删除的目标本身就是联接时，也会拦下。
- 脚本自身出错时直接放行，不影响正常工作。
- hook 从下一个会话开始生效。修改脚本后，用沙箱 `docs/tmp/_guard_wt`（里面放一个假联接，指向 `docs/tmp/_guard_target`）跑 7 个用例回归，确认 canary 文件没被删。
