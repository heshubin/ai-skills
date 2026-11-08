# kiro-knowledge · 个人 Kiro 全局经验库

把 `d:\code\kiroWP\.kiro`（A）、`D:\workspace\myBot\.kiro`（B）、`C:\Users\Willi\.kiro\steering`（C）三处积累的 steering / skill / hook / agent 合并成一份，作为所有 Yamibuy WMS 项目共用的全局规则源。服务的第一个项目是 WMS Zone Picking 二期，入口见 `steering/zone-picking-hub.md`。

## 目录

```
kiro-knowledge\
├── steering\         平铺，挂载为 ~/.kiro/steering（全局 steering）
├── skills\<name>\    每个 skill 一个目录（SKILL.md + 附带资源），挂载为 ~/.kiro/skills
├── templates\hooks\  hook 模板，不挂载，按项目拷到工作区 .kiro\hooks\
├── templates\agents\ agent 模板，按需拷到 ~/.kiro/agents 或工作区 .kiro\agents\
├── .gitignore
└── README.md
```

分层只体现在下面的索引里：**第1层 = 通用**（任何项目都适用），**第2层 = WMS 业务**（Yamibuy WMS 架构、表、App、流程）。两层都挂全局，靠 inclusion 控制何时加载：

- `always`：每次对话都注入，只留 6 个硬性规则，保持精简
- `auto`：Kiro 按 description 里的触发场景和触发词自动加载（必须有 name + description）
- `fileMatch`：打开/编辑匹配 `fileMatchPattern` 的文件时注入
- `manual`：对话中用 `#文件名` 手动引用

只对单个项目有效的知识（如 myBot 的 wecom-bot 规则、SOP 自动化、MCP 恢复）仍留在该项目工作区的 `.kiro\` 下，不进本库。

## Steering 索引（42 个）

| 文件 | 层级 | inclusion | 一句话用途 |
|---|---|---|---|
| global_forbidden_rules.md | 通用 | always | 通用禁止清单 29 条（流程/安全/质量/Git/MCP 配置），第 2、3 条标注了仅适用老工作方式 |
| global_guide.md | 通用 | always | 身份、中文、终端、提交与 push、docs 分区、知识即时沉淀 |
| server_forbidden_rules.md | 通用 | always | 后端 8 条禁令（拼接 SQL、N+1、SELECT *、魔法数字、通配符导入、toMap merge 等） |
| file-encoding-rules.md | 通用 | always | 禁止 PowerShell 读写含中文代码文件；str_replace 混合换行符检查与恢复 |
| git_commit_op_prefix.md | 通用 | always | commit 必须以 `[OP-XXXXX]type:` 开头，OP 号由用户确认 |
| code_author.md | 通用 | always | Java/Groovy `@author` 固定 William.He |
| server_coding_examples.md | 通用 | fileMatch `**/*.java,**/*.groovy,**/mapper/*.xml` | server_forbidden_rules 的代码示例、MyBatis 批量模板、Bug#10360 案例 |
| test-maintenance-rules.md | 通用 | fileMatch `**/src/test/**/*.groovy,**/*Test.groovy,**/*Spec.groovy` | Spock 单测失败四类根因与提交前自检 |
| code_quality_rules.md | 通用 | fileMatch `**/*.java` | 禁全限定名、import 同步、改后验证、多模块编译 |
| karpathy_coding_principles.md | 通用 | fileMatch `**/*.java,**/*.groovy,**/*.xml` | 中文版编码行为准则 |
| mysql_compatibility.md | 通用 | fileMatch `**/*.sql` | MySQL 5.7/8.0 DDL 兼容与索引命名 |
| central_web.md | 通用 | fileMatch `src/**/*.{ts,tsx,js,jsx}` | React + Ant Design 中后台反模式（RN 项目忽略） |
| yami-skills.md | 通用 | auto | yami-ai-cli 公共 skill 索引（56 条） |
| db_table_design_rule.md | 通用 | auto | 表设计规则 |
| find_project.md | 通用 | auto | 查找不在工作区的项目 |
| skills-path-find-guide.md | 通用 | auto | 定位 skill 脚本与资源路径 |
| sub-agent-guide.md | 通用 | auto | 选择和委派 sub-agent |
| sonar_coverage_rule.md | 通用 | auto | Sonar 新代码覆盖率 ≥80% 流程 |
| bug-analysis-methodology.md | 通用 | auto | 四层递进 bug 分析链路 |
| code-evolution-analysis.md | 通用 | auto | 共用方法调用方枚举、防御代码三问 |
| cross-module-flow-analysis.md | 通用 | auto | 新接口兼容性、跨模块调用链、分支变量命名 |
| data-anomaly-audit-first.md | 通用 | auto | 数据与代码矛盾时先查人工修改审计 |
| problem-solving-principles.md | 通用 | auto | 先试后判、先抓真实数据、不规避问题 |
| superpowers.md | 通用 | auto | 头脑风暴 → TDD → 系统化调试 → 写计划 |
| html-document-design.md | 通用 | manual | Markdown 转单页 HTML 展示规范 |
| best-practice-research.md | 通用 | manual | 动手前先搜业内最佳实践（例子来自 wecom-bot） |
| java_dev_env.md | WMS | fileMatch `**/*.java,**/*.groovy,**/pom.xml,**/*.sql` | Maven/JDK 路径、GQC 启动参数（账号密码已改为占位符） |
| wms_coding_pitfalls.md | WMS | fileMatch `**/wms-cloud-service/**` | WMS 编码踩坑（RedissonClientImp、XML 参数名等） |
| wms_project_conventions.md | WMS | fileMatch `**/wms-cloud-service/**,**/central-packing-service/**` | 模块结构、跨服务同名类同步、adjustLocation 主链路 |
| zone-picking-code-rules.md | WMS | fileMatch（wms/packing 的 Java 与 Mapper XML） | Zone Picking 红线（约束 26 开关短路）与 Cart/Tote 口径 |
| web-core-umi-guide.md | WMS | fileMatch `**/*.{ts,tsx,jsx,less,scss,css}` | UmiJS + web-core Portal 规范（正文自带适用性判断） |
| zone-picking-hub.md | WMS | auto | Zone Picking 二期知识导航 + 一期踩坑清单 |
| query-side-filter-principles.md | WMS | auto | 历史数据不动、查询侧过滤、多服务同步修复 |
| bug_pattern_registry.md | WMS | auto | 45+ 个批次/库存 bug 模式与自查清单 |
| wms_inventory_sync_rule.md | WMS | auto | 两套库存表同步铁律、SQL 方法职责对照 |
| picking-app-arch.md | WMS | auto | Picking App 无 token、@VestaIgnore、90008 排查 |
| wms-pw-sorting-arch.md | WMS | auto | PW Sorting 跨 Zone 初始化约束（Bug#10360） |
| wms-zone-oos-arch.md | WMS | auto | Zone 预建任务 × OOS 保护缺口 |
| wms-picking-route-arch.md | WMS | auto | 拣货路线 BinSortingHandler / PickGroupEnum |
| tpl-order-repush.md | WMS | auto | 3PL 订单补推必须复刻的副作用 |
| op-create-template.md | WMS | auto | tech-team OP 创建模板（API key 走环境变量） |
| android-app-testing.md | WMS | auto | WMS/Picking App 打包、Metro、logcat、Appium 登录 SOP |

## Skill 索引（25 个）

| skill | 层级 | inclusion | 一句话用途 |
|---|---|---|---|
| db-table-design-principles | 通用 | skill（按 description 发现） | 表设计原则展开（主键/索引/类型） |
| frontend-api-integration | 通用 | skill | React/RN 请求封装与错误处理 |
| git-commit-convention | 通用 | skill | Conventional Commits，已加 `[OP-XXXXX]` 前缀 |
| java-code-review-checklist | 通用 | skill | Java CR 清单 |
| karpathy-coding-principles | 通用 | skill | 英文版 4 条编码准则 |
| mybatis-best-practices | 通用 | skill | Mapper/DAO 最佳实践 |
| react-dev-guide | 通用 | skill | React Web 规范 |
| rest-api-design-guide | 通用 | skill | REST 接口设计 |
| troubleshooting-guide | 通用 | skill | 线上排查五步 |
| typescript-patterns | 通用 | skill | TS 类型模式 |
| adb-screen-recorder | 通用 | skill | adb 录屏 |
| android-screenshot | 通用 | skill | 安全截图（避免 PNG 损坏） |
| api-traffic-surge | 通用 | skill | ES/Kibana 接口突增看板（凭证走环境变量） |
| defensive-code-review | 通用 | skill | 防御代码留/删判断 |
| slow-sql-diagnosis | 通用 | skill | 慢 SQL 诊断 |
| systematic-flow-analysis | 通用 | skill | 流程兼容性/根因分析 |
| react-native-dev-guide | WMS | skill | RN 仓库 App 指南（已去掉 Alert，补 BroadcastScanner 规则） |
| wms-inventory-transfer-guide | WMS | skill | adjustLocation 链路 |
| wms-lot-tracking-guide | WMS | skill | 批次追踪开发 |
| wms-spec-review-checklist | WMS | skill | WMS spec 审查清单 |
| wms-database-guide | WMS | skill | yamibuy_wh 核心表、枚举、关联 SQL（复制自 myBot 的 wecom-bot-wms-database） |
| wms-app-login | WMS | skill | Appium 自动登录 WMS App（账号/密码/设备号走环境变量） |
| pd-meeting-doc | WMS | skill | PD 双周例会文档（OpenProject key 走环境变量） |
| wms-batch-priority-guide | WMS | skill | batch_priority 三层来源（自动 / 订单优先级 / Central ↑）、生产几百万值的读法、选批排序坑、二期分层排序方案（来自 OP-40026 调研） |
| wms-picking-task-rollback | WMS | skill | 撤销误领的拣货任务：普通 / 单 Zone / 跨 Zone 场景判断，领取写入表清单，带状态守卫和期望行数的生产脚本（跨 Zone 退回待领取，不删 Task） |

skill 需要的环境变量：`WMS_APP_USER`、`WMS_APP_PASSWORD`、`WMS_DEVICE_UDID`、可选的 `WMS_SCREENSHOT_DIR`（wms-app-login，不设时截图写到当前目录下的 `docs\tmp\wms_test`）、`OPENPROJECT_API_KEY`（pd-meeting-doc、op-create-template）、`ELASTICSEARCH_AUTHORIZATION` / `KIBANA_AUTHORIZATION`（api-traffic-surge）。真值通过 yami-skills 的 account-password-query 获取，用户级环境变量设置一次即可。

## 模板索引

| 文件 | 来源 | 说明 |
|---|---|---|
| templates/hooks/auto-unit-test-check.kiro.hook | A | agentStop：登记待补单测清单（WMS Java） |
| templates/hooks/verify-java-write.kiro.hook | A | 写 Java/Mapper 后验证落盘与编译 |
| templates/hooks/java-code-review-after-write.kiro.hook | A | 写 Java 后自动质检 |
| templates/hooks/bug-fix-doc-sync.kiro.hook | A | 手动：缺陷登记与经验沉淀 |
| templates/hooks/auto-continue-on-stop.kiro.hook | A | 已禁用，勿轻易开启 |
| templates/hooks/code-commit.kiro.hook | A=B | 手动：生成 commit。注意其 prompt 未带 `[OP-XXXXX]` 前缀且用 `git add -A`，与 git_commit_op_prefix 冲突，执行时以 steering 为准 |
| templates/hooks/update-readme-docs.kiro.hook | A=B | 手动：更新一级目录 README |
| templates/hooks/mcp-backup-reminder.kiro.hook | B | **myBot 专用**：备份命令写死 myBot 路径，别的项目不要拷 |
| templates/hooks/regression-test-guard.kiro.hook | B | **myBot 专用**：跑 `myBot\wecom-bot` 的 pytest，别的项目不要拷 |
| templates/agents/dev-figma-plugin.json | A=B | Figma 插件开发 agent |
| templates/agents/qa-autoqa-executor.json | A=B | AutoQA 执行 agent |

## 常用操作

### 新增经验
1. 判断层级：任何项目都适用 → 通用；Yamibuy WMS 专属 → WMS；只对一个项目有效 → 放该项目 `.kiro\`，不进本库。
2. 规则类写 `steering\<名字>.md`，流程/工具类写 `skills\<名字>\SKILL.md`。
3. 文件头必须写 front-matter：
   - steering：`inclusion` 必填；`auto` 必须带 `name` 和 `description`（写清触发场景 + 中文触发词）；`fileMatch` 必须带 `fileMatchPattern`。新增 always 前先想清楚，always 只放硬性规则。
   - skill：`name`（与目录名一致）+ `description`。
4. 用 Kiro 的 fs_write / str_replace 写文件，禁止用 PowerShell 写含中文的文件；写完 read_file 抽查中文。
5. 在本 README 索引表加一行，然后提交（commit message 带 `[OP-XXXXX]` 前缀）。

### 给新项目拷 hooks 模板
```powershell
# 在新项目工作区根目录执行；只拷需要的，myBot 专用的两个不要拷
New-Item -ItemType Directory -Force -Path '.kiro\hooks' | Out-Null
Copy-Item 'D:\code\kiro-knowledge\templates\hooks\verify-java-write.kiro.hook' '.kiro\hooks\'
Copy-Item 'D:\code\kiro-knowledge\templates\hooks\java-code-review-after-write.kiro.hook' '.kiro\hooks\'
Copy-Item 'D:\code\kiro-knowledge\templates\hooks\auto-unit-test-check.kiro.hook' '.kiro\hooks\'
```
拷完在 Kiro 的 Agent Hooks 面板确认已识别。`Copy-Item` 是字节级复制，不会破坏中文。

### 挂载（后续步骤执行，执行前需确认）
计划用目录联接把 `~/.kiro/steering`、`~/.kiro/skills` 指向本库：
```powershell
# 示例：先把原目录移走（已备份），再建联接
New-Item -ItemType Junction -Path 'C:\Users\Willi\.kiro\steering' -Target 'D:\code\kiro-knowledge\steering'
New-Item -ItemType Junction -Path 'C:\Users\Willi\.kiro\skills'   -Target 'D:\code\kiro-knowledge\skills'
```
挂载后需从 kiroWP、myBot 工作区 `.kiro\steering`、`.kiro\skills` 移除已迁入本库的同名副本，否则同一规则会注入两份。

### 回滚
迁移前的完整备份：`D:\code\kiro-knowledge-backup\20261027-162407\`（A = kiroWP/.kiro，B = myBot/.kiro，C = ~/.kiro/steering，`removed-from-workspace\` 存放从工作区移走的文件）。
```powershell
# 1. 删除联接本身（用 rmdir 只删联接，不会删除本库内容；不要对联接用 Remove-Item -Recurse）
cmd /c rmdir "C:\Users\Willi\.kiro\steering"
cmd /c rmdir "C:\Users\Willi\.kiro\skills"
# 2. 恢复原全局 steering
New-Item -ItemType Directory -Force -Path 'C:\Users\Willi\.kiro\steering' | Out-Null
Copy-Item 'D:\code\kiro-knowledge-backup\20261027-162407\C\*' 'C:\Users\Willi\.kiro\steering\'
# 3. 若工作区副本已被移除，从备份拷回（A/B 同理）
Copy-Item 'D:\code\kiro-knowledge-backup\20261027-162407\A\steering\*' 'd:\code\kiroWP\.kiro\steering\' -Recurse
```
本库自身的改动用 git 回滚（`git log` / `git checkout <commit> -- <file>`）。

## 合并与调整说明

- **四个 A/B 分叉文件已合并**：global_forbidden_rules（A 27 条 + B 独有 2 条 MCP 规则，编号 28/29 追加在末尾，1–27 编号不变）、global_guide（规则 2 统一 OP 前缀口径、规则 10 并入 B 的知识即时沉淀）、server_forbidden_rules（B 的示例与案例拆到 server_coding_examples.md）、yami-skills（以 A 的 56 条为准，B 的 50 条全部逐字包含其中）。
- **file-encoding-rules**：以 C 为底本统一成中文，补入 A 的危险写法示例、乱码样例与 BOM 根因，保留 C 的「str_replace 混合换行符」一节。
- **global_guide 规则 7（push）**：保留 A 的「commit 后自动 push」。B 原为「commit 后先问是否 push」，合并后 myBot 也会按自动 push 执行；如需恢复先问再 push，改这一条即可。
- **global_guide 规则 8**：docs 路径改为「主工作空间（第一个 workspace folder）下的 docs/」，分区约定不变；kiroWP 即 `d:\code\kiroWP\docs`。
- **always 从 A 8 个 / B 14 个降到 6 个**：方法论、架构、业务知识改 auto，Groovy 单测规则改 fileMatch。降级后这些规则只在触发时生效，例如 superpowers 的「批准设计前不写代码」不再每轮注入。

## 与各仓库自带 .kiro 规则的重叠

Kiro 规定工作区规则与全局规则冲突时，**工作区规则优先**。只有 wms-cloud-service、WMS-front-end（含 wms-rn 子目录）自带 `.kiro/steering`；central-picking-app 及其余仓库没有，picking-app-arch.md 是 Picking App 唯一的规则来源。

| 仓库规则 | 与全局的关系 |
|---|---|
| wms-cloud-service/java-code-quality.md（always） | 与 server_forbidden_rules、global_forbidden #18/#22、code_quality_rules 大量重叠。**冲突**：方法长度 80 行（仓库）vs 120 行（全局 #22），在该仓库按 80 行。仓库独有：嵌套 ≤3 层、UPDATE 必带任务级约束、布尔变量命名 |
| wms-cloud-service/spring-mvc-interface-rules.md（always） | 与 picking-app-arch 互补：仓库管「路由只写 Interface」，全局管认证 |
| wms-cloud-service/test-location-rules.md（always） | 与 test-maintenance-rules、sonar_coverage_rule 互补：仓库规定新增测试只放 `src/test/java` |
| WMS-front-end/init.md（always） | 与 global_guide #1/#3、global_forbidden #5 重复。**冲突 1**：「不要生成测试目录和文件」vs superpowers TDD / sonar_coverage_rule，在该仓库按仓库规则。**冲突 2**：E2E 截图用 `adb exec-out screencap -p > x.png`，PowerShell 下会损坏 PNG，以 android-screenshot skill 为准 |
| WMS-front-end/dev-environment-cleanup.md（always） | 与 android-app-testing 的 8081 端口一节重叠 |
| WMS-front-end/logging-standards.md（always） | 与 global_forbidden #19 一致，仓库版更细 |
| WMS-front-end/redux-refactoring-rules.md（always） | 仓库独有 |
| WMS-front-end/rn-component-rules.md（always） | react-native-dev-guide 已补 useIsFocused 与 ProductImageCarousel 规则，以仓库版为准 |
| WMS-front-end/e2e-testing-rules.md、wms-rn/e2e-testing-rules.md（fileMatch） | 与 android-app-testing、wms-app-login、android-screenshot 重叠；第 5 条截图路径是其他同事的桌面目录 |
| WMS-front-end/wms-rn/ui-review-workflow.md、ui-style-rules.md | 仓库独有 |
