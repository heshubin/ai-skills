---
inclusion: auto
name: skills-path-find-guide
description: 当需要执行 Skill 脚本、读取 Skill 参考文档、定位 Skill 资源文件路径时使用。触发词：skill脚本, scripts/, references/, examples/, assets/, discloseContext, skill资源
---

## Skill 资源路径定位规则

当 `discloseContext` 返回 SKILL.md 正文后，如果正文中引用了 `scripts/`、`references/`、`examples/`、`assets/` 等相对路径资源，按以下规则定位实际文件。

### 定位步骤

已知 skill 名称为 `<name>`（即 `discloseContext` 的 `name` 参数），Skill 根目录按优先级查找：

1. `<workspace>/.kiro/skills/<name>/` — 工作区级别，优先使用
2. `~/.kiro/skills/<name>/` — 用户全局级别，工作区不存在时使用

找到存在的目录后，该目录即为 Skill 根目录，所有相对路径基于此目录解析。

### 路径模板

| 资源类型 | 相对路径 | 完整路径示例 (Windows) |
|----------|----------|----------------------|
| 参考文档 | `references/xxx.md` | `<skill-root>\references\xxx.md` |
| 脚本 | `scripts/xxx.py` | `<skill-root>\scripts\xxx.py` |
| 示例 | `examples/xxx.java` | `<skill-root>\examples\xxx.java` |
| 资产 | `assets/template.xlsx` | `<skill-root>\assets\template.xlsx` |

### 执行脚本时

```powershell
# <skill-root> = 找到的 Skill 根目录
python "<skill-root>\scripts\xxx.py" <args>
```
