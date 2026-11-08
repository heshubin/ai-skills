---
inclusion: always
---
# 我是谁
1. 我是`主人`，我的角色是开发者

# 全局规则
1. 必须全程使用中文进行表述和回复，确保信息传递的准确性和一致性。
2. 生成Github提交信息，使用中文生成。commit message 必须以 `[OP-XXXXX]` 工单号开头，格式以 `git_commit_op_prefix.md` 为准（`[OP-XXXXX]type: 描述`，`]` 与 type 之间无空格）。工单号可先从当前分支名中提取作为候选，取不到或不确定时询问主人，禁止编造。
3. 在执行系统命令行操作时，根据当前操作系统选择终端：Windows 使用 PowerShell，macOS/Linux 使用 bash
4. 如果要获取当前时间，请一定使用shell脚本获取当前时间
5. 数据库时间字段设计请使用时间戳，单位秒
6. 快速了解项目的方式：阅读每个文件夹下，或者每个git项目下的README.md文件
7. 如果当前是git项目每个小任务结束，创建一个git commit提交；git commit 之后**先询问主人是否 push**，主人确认后再 git push 到远端 origin 分支，禁止未经确认自动 push
8. 所有生成的文件（含临时文件）按用途放入主工作空间（第一个 workspace folder）下的 `docs/` 固定分区，禁止直接堆在 docs 根目录：
   - `docs/active/<需求名>/` — 进行中需求的方案、SQL、报告（需求名与 OP 号或 spec 名对应）
   - `docs/archive/<需求名>/` — 已上线/已结束的需求，从 active 移入
   - `docs/scripts/` — 可复用脚本（生成文档、写表格、发 wiki 等）
   - `docs/tmp/` — 一次性中间数据（导出的 json/csv/日志），可随时清空，建议加入 .kiroignore
9. 发现好的通用规则或 WMS 业务知识时，创建到 `D:\code\kiro-knowledge\skills\`（全局经验库）下作为 skill（每个 skill 一个目录，包含 SKILL.md）；只对某一个项目有效的专属知识，放该项目工作区的 `.kiro/skills/`
10. **知识即时沉淀原则**：在解决问题的过程中，一旦发现以下任何一类知识点，必须**当场**沉淀，不等事后：
    - 架构约束（如：某个 App 没有 token 体系，必须用 @VestaIgnore）
    - 排查规律（如：90008 = 部署版本落后，不是代码错误）
    - 踩坑经验（如：接口路径前缀影响网关认证策略）
    - 共用方法的隐藏副作用（如：新流程改变了旧校验的前置状态）
    沉淀位置：通用/WMS 业务知识 → `D:\code\kiro-knowledge\steering\` 或 `D:\code\kiro-knowledge\skills\`（全局经验库）；只对单个项目有效的知识 → 该项目工作区 `.kiro/steering/` 或 `.kiro/skills/`；通用思维方法 → `global_guide.md` 或 `superpowers.md`
    **禁止**：发现了关键知识点但只用于当次判断，不沉淀，等用户追问才补上。
    **提交**：`D:\code\kiro-knowledge` 是一个 git 仓库（origin 为 heshubin/ai-skills，分支 master）。写进 skills、steering、templates 的内容，在 kiroWP 工作区由 Stop hook `kiro-knowledge-autocommit` 在每轮回复结束时自动提交并推送：
    - 提交信息为「更新技能：<改动项>」；
    - 只要有一处疑似密钥就整批不提交；
    - 日志位于 `D:\code\kiroWP\docs\tmp\kiro-knowledge-autocommit.log`。
    所以写完不用手动提交，但内容里禁止出现 token、密码、私钥。不在 kiroWP 工作区时，hook 不会触发，写完要手动执行 `powershell -NoProfile -ExecutionPolicy Bypass -File d:/code/kiroWP/docs/scripts/kiro-knowledge-autocommit.ps1`。
