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

## worktree remove 报 Permission denied，但其实已经删完了（2026-11-09 加）
Bug#10880 收尾时遇到两次：
- `wdb-10880`（已拆掉联接）执行 `git worktree remove`，报 `failed to delete '<路径>': Permission denied`。
- `was-10880`（没有联接）也一样。

查下来，git 已经注销了 worktree，目录里的文件也删光了，只剩一个空目录。用 `cmd /c rmdir "<worktree>"`（不带 `/s`）再删，报「另一个程序正在使用此文件」。说明有进程把这个目录当作当前目录，或者开着它的句柄，常见是之前步骤留下的终端会话。

怎么判断删除已经完成：
```powershell
git -C <主仓库> worktree list                                     # 列表里没有这个 worktree
Test-Path <主仓库>\.git\worktrees\<worktree名>                    # False
[System.IO.Directory]::GetFileSystemEntries('<worktree>').Count   # 0
```
三项都满足，就说明只剩空目录。这时：
- 可以继续执行 `git branch -d` 删本地分支。
- 不要加 `--force` 重跑，也不要去杀不确定的进程。
- 空目录留着没有影响。在报告里写明，等占用它的会话关闭后，再用 `cmd /c rmdir "<worktree>"` 删掉。不带 `/s` 的 rmdir 只能删空目录，不会误删内容。

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
- hook 从下一个会话开始生效。workflow 的每个步骤都是新会话，会自动加载。
- 修改脚本后要做回归：
  1. 建沙箱：在 `docs/tmp/_guard_wt/app/wms-rn/node_modules` 用 `mklink /J` 建一个联接，指向 `docs/tmp/_guard_target`。目标目录里放一个 `canary.txt`，另外建一个空目录 `docs/tmp/_guard_wt/plain`。
  2. 跑用例：用例在 `d:/code/kiroWP/docs/scripts/guard-junction-delete.cases.json`，共 7 条。把每条的 command 包成 `{tool_name, tool_input:{command}}`，通过管道传给脚本，核对 exit code 是否和 expect 一致。命令要从文件里读，不能直接写进命令行，不然当前会话的 hook 会把测试命令本身拦下来。
  3. 确认 canary 没被删。
  4. 收尾：先 `cmd /c rmdir` 拆掉联接，再删除沙箱。

## 推送后把主目录同步到远端（2026-11-08 加）
在 worktree 里改代码，再 `git push origin <临时分支>:<目标分支>` 推上去，远端会前进，但主目录（例如 `D:\code\wms-cloud-service`）的本地分支不会跟着动。主人打开主目录看不到新代码，要自己 `git pull`，容易误以为改动丢了。

每次推送、删除 worktree 之后，都要同步主目录：
1. 只在主目录**当前分支就是推送的目标分支**、并且**没有未提交的已跟踪改动**时执行：`git -C <主目录> merge --ff-only origin/<目标分支>`。
2. 主目录在别的分支上，或者有未提交改动时，不要去动主目录，在报告里写明「主目录落后 N 个提交，请自行 pull」。
3. 禁止用 `reset`、`checkout -f`、`stash` 这类会动到主人工作区的手段来强行同步。

## npm install 会改 yarn.lock
在同时有 package-lock.json 和 yarn.lock 的仓库里跑 `npm install`（npm 7 及以上），npm 会顺手改写 yarn.lock。只撤销 package-lock 是不够的。装完要 `git status` 检查，**两个 lock 文件都要撤销**：`git checkout -- package-lock.json yarn.lock`。2026-11-08 给 central-picking-app 补依赖时，就漏撤了 yarn.lock，多出 545 行改动。
