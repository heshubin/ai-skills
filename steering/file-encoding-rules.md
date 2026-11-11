---
inclusion: always
---
# 文件编码操作规范（全局）

## 🚨 核心禁令：禁止用 PowerShell 读写/修改含中文的代码文件

### 根因

PowerShell 的 `Get-Content`/`Set-Content` 默认编码是 Windows-1252 或系统 ANSI，读写中文 UTF-8 字符时会把多字节序列截断，写回时编码丢失，导致 Groovy/Java 编译报错 `Unexpected character: '"'`。即使加 `-Encoding UTF8`，在某些情况下仍会写入带 BOM 的 UTF-8，与项目期望的无 BOM UTF-8 不一致。

### 真实案例（2026-08）

批量修复测试文件参数签名时，用了 PowerShell `-replace` + `Set-Content`：

```powershell
# ❌ 危险操作：会破坏文件中的中文字符
$content = Get-Content $filePath -Raw
$content = $content -replace 'old', 'new'
Set-Content -Path $filePath -Value $content -NoNewline
```

**结果**：ConsolidationServiceImplTest.groovy 和 Zone2PrintServiceImplTest.groovy 的中文方法名都被破坏为乱码（如 `一条` 变成 `一锟?`），Groovy 编译报错：
```
Unexpected character: '"' @ line 156, column 9.
def "createTasks - 正确创建主表记录，每个订单一锟?() {
```
CI 连续失败两次，排查成本很高。

---

## 速查表：只用 Kiro 提供的工具操作代码文件

| 操作类型 | 正确工具 | 禁止方式 |
|---|---|---|
| 精确替换少量内容 | `str_replace` | PowerShell `-replace` + Set-Content |
| 创建新文件 | `fs_write` | PowerShell Out-File / Set-Content |
| 追加内容 | `fs_append` | PowerShell Add-Content |
| 批量替换 3 处及以上 | 并行调用多次 `str_replace` | PowerShell 对整个文件做正则批量替换 |

---

## 关键决策规则：批量修改时的第一反应

当 3 处及以上需要做同一种修改时：
- ✅ 正确：先 `grep_search`（或 Select-String 只读查看）找到所有位置、确认行号和精确内容，再对每处并行调用 `str_replace`
- ❌ 禁止：`Get-Content` → `-replace` 批量替换 → `Set-Content` 写回

为什么不能"一行搞定"？
代码文件里有中文注释/中文方法名，PowerShell 编码**一定会**破坏它们。而且破坏是静默的，直到 CI 编译失败才暴露，修复成本极高。

---

## 批量修改的标准流程

1. `grep_search` 找出所有位置（确认每一行的精确内容）
2. 每处调用一次 `str_replace`（可并行发出），每次只针对一处精确匹配，不写正则
3. 改完后 `read_file` 抽查 2–3 行含中文的内容，目视确认没有乱码
4. 确认无误后才 `git add` + `commit`（禁止先提交、后检查）

---

## 出现编码问题后的恢复方法

```powershell
# 从最后一个干净的 commit 恢复该文件（不影响其他文件）
git checkout <clean-commit-hash> -- path/to/file.groovy

# 确认恢复是否正确（查看中文是否正常）
# 然后用 str_replace 重新做精确修改
```

---

## str_replace 可能把混合换行符统一化（2026-09）

CRLF/LF 混用的文件（如 wms-cloud-service 的 Constant.java）经过 `str_replace` 后，可能被整体改写成同一种换行符。diff 里会出现可见文本完全相同、却被标记为修改的行。

每次修改后检查：
- `git diff --stat` 和 `git diff --ignore-cr-at-eol --stat` 的行数必须一致。不一致 = 换行符被动过。

恢复方法（只用字节级 git 操作，禁止用 PowerShell 文本读写）：
```
git diff --ignore-cr-at-eol --output=<patch-file> -- <file>
git checkout -- <file>
git apply --whitespace=nowarn <patch-file>
```
然后删除 patch 文件，再次核对上面两个 `--stat` 输出。

补充（2026-10-31，OP-40026 任务 1.3 实测）：
- 上面的补丁法在 CRLF 段里会失败：`git apply` 报 `patch does not apply`，而 `git checkout` 已经把改动丢掉了。执行补丁法之前先另存一份要改的内容。
- 更稳的做法是一开始就别动已有行的行尾：在混合换行文件里**插入**内容时，`oldStr` 选插入点**下一行的行首片段**（不含行尾），`newStr` = 新内容 + 换行 + 该片段。这样被匹配的行保留原来的 CR，新行是 LF，两条 `--stat` 一致。
- 反例：`oldStr` 选插入点**上一行**，`newStr` 在它后面追加新内容，该行行尾的 CR 会被挪到新内容末尾，上一行变成 LF，`--stat` 多出 1 删 1 增。

---

## 📋 提交前自检清单

- [ ] 本次修改没有使用 PowerShell Set-Content / Out-File / Add-Content / `-replace` 写代码文件
- [ ] 修改后用 `read_file` 读取关键行，目视确认中文字符未乱码
- [ ] 涉及中文注释/方法名的 `.groovy`/`.java` 文件尤其要检查
- [ ] `git diff --stat` 与 `git diff --ignore-cr-at-eol --stat` 行数一致
- [ ] 以上全部通过后才执行 `git commit`

---

## 在 agent 终端里跑 git 查看命令（2026-11）

- **中文乱码**：PowerShell 默认按 GBK 解码 git 输出，提交信息里的中文会显示成「浜屾湡鏋氫妇」这类乱码。命令开头先加 `[Console]::OutputEncoding = [Text.Encoding]::UTF8;`。这只影响显示，不影响仓库内容。
- **命令卡住到超时**：`git show`、`git log`、`git diff` 输出较长时会调起分页器（less），等待按键，命令一直挂到超时（exit -1、没有输出）。查看类命令一律写成 `git --no-pager -C <仓库> ...`。
