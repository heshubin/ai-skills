---
inclusion: auto
name: yami-skills
description: 当需要通过 yami-ai-cli 加载团队公共 skill（Spock 单测、接口测试、SQL 查询、Kibana 日志、OP 管理、PR 创建/发布、Apollo、发布文档、知识图谱、文档/表格处理）时使用。触发词：yami-ai-cli, skill, 加载技能, 单元测试, spock, 接口测试, api-test, sql 查询, 查日志, kibana, OP, openproject, PR, apollo, 发布文档, 知识图谱, docx, xlsx
---

# 可用 Skills

以下 skills 可通过 `yami-ai-cli read` 命令按需加载。当用户要求执行相关任务时，请使用对应的 skill。

## 使用方式

- 调用: `yami-ai-cli read <skill-name>`（在终端中运行）
  - 多个 skill: `yami-ai-cli read skill-one,skill-two`
- skill 内容会输出详细的任务指令
- 输出中包含 Base directory，用于解析 skill 附带的资源文件（references/、scripts/、assets/）

## 注意事项

- 通过 yami-ai-cli 加载时，仅使用下方列出的 skills；`~/.kiro/skills`（即 `D:\code\kiro-knowledge\skills\`）下的本地 skill 同样可用
- 本文件以 kiroWP 版（56 条）为准，已核对 myBot 版 50 条全部逐字包含其中
- 不要重复加载已在上下文中的 skill

## Skills 列表

- **wirte-java-unit-test** — 当需要为 Java 代码编写 Spock 单元测试、Mock 测试、Groovy 测试时使用。触发词：spock, mock, unit test, 单元测试, java test, groovy test
- **account-password-query** — 当需要查询账号、密码、登录凭证、访问权限、数据库连接信息时使用。触发词：账号, 密码, 登录, 凭证, credentials, password
- **api-test** — 对 Yamibuy 微服务进行 HTTP 接口测试。支持 UAT、DEV、GQC 多环境切换，自动携带 token 和 headers。当用户需要测试接口、验证 API 返回、调试服务时使用。
- **apollo-config-sync** — 当需要同步 Apollo 配置、拉取微服务配置、查看远程配置到本地时使用。触发词：apollo, 配置同步, 拉取配置, app.id
- **app/api-creator** — 在 Flutter 项目的 a_api 目录下创建 DTO、dto_extension、Service 方法。当用户需要新增 API 接口、创建数据模型、添加 DTO 扩展方法时使用。也适用于用户提到"创建 DTO"、"新增接口"、"添加 service 方法"、"写 api"、"对接接口"等场景。
- **app/git-manager** — 管理三仓库（iOS/Android/Flutter）的 Git 分支命名和流转。当用户提到"创建分支"、"切分支"、"新建分支"、"封版"、"打 tag"、"hotfix"、"提测"、"预发布"、"上线"、"git branch"、"分支管理"时使用。
- **app/l10n-manager** — 管理 Flutter 项目的国际化文案（arb 文件）。支持添加、移除、翻译、清理文案。当用户提到"添加文案"、"国际化"、"l10n"、"arb"、"多语言"、"翻译文案"、"删除文案"、"清理未使用文案"、"i18n"时使用。
- **app/update-app-version** — 修改 iOS 和 Android 项目版本号。当需要升级、降级或设置 app 版本号时使用。也适用于用户提到"发版"、"升版本"、"改版本号"、"bump version"、"release"、"iOS 版本"、"Android 版本"等场景。
- **autoqa-code-helper** — 当需要基于测试用例文档和操作录制文档生成自动化测试脚本、创建 Selenium action 和 case、自动化测试代码生成时使用。
- **autoqa-codebase-doc-generator** — 当需要分析代码库结构和逻辑、生成代码说明书文档、理解项目架构、模块功能和代码细节时使用。
- **autoqa-flutter-qa-attributes-tagger** — 当需要为 Flutter 代码添加 autoQaId 测试属性、识别按钮文本和可点击元素、方便自动化测试定位元素时使用。
- **autoqa-react-qa-attributes-tagger** — 当需要为 React 代码添加 data-qa-* 测试属性、识别按钮文本和可点击元素、方便自动化测试定位元素时使用。
- **bilibili-downloader** — 使用 yt-dlp 工具下载 Bilibili 视频。当用户想要下载 Bilibili 视频或询问 Bilibili 视频下载时调用。
- **brainstorming** — You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation.
- **cdn-upload** — 
- **code-branch-diff** — 当需要对比分支代码差异、查看代码变更、分析提交记录、生成 diff 报告时使用。触发词：diff, 代码对比, 分支差异, git diff, 代码变更
- **code-module-analyzer** — 当需要分析代码模块、理解代码结构、追踪调用链、生成代码文档时使用。触发词：这段代码, 帮我看看, 分析一下, 这个模块, 什么意思, 怎么实现的, 代码分析
- **code-simplifier** — 当需要简化代码、重构代码、优化代码结构、提升代码可读性、清理冗余代码时使用。触发词：simplify, refactor, clean code, 代码简化, 重构, 代码优化
- **control-browser** — 当需要使用浏览器、操作网页、验证前端效果、截图测试时使用。触发词：浏览器, 打开网页, 截图, 页面验证, playwright, chrome
- **deep-research-agent** — 当需要进行深度研究、生成研究报告、文献调研、信息综合、系统性分析某个主题时使用。触发词：research, 深度研究, 报告生成, 研究项目, 文献调研
- **dev-doc-generator** — 当需要生成开发发布文档、查看多仓库代码变更、生成技术变更报告、准备上线文档时使用。触发词：dev doc, 开发文档, 发布文档, 代码变更, 技术文档
- **developer-evaluator** — 当需要评估开发者代码能力、为晋升提供量化依据、分析 GitHub PR 历史时使用。触发词：代码评估, 晋升评估, 开发者能力, 代码质量, github 分析
- **doc-coauthoring** — Guide users through a structured workflow for co-authoring documentation. Use when user wants to write documentation, proposals, technical specs, decision docs, or similar structured content. This workflow helps users efficiently transfer context, refine content through iteration, and verify the doc works for readers. Trigger when user mentions writing docs, creating proposals, drafting specs, or similar documentation tasks.
- **docx** — Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers include: any mention of 'Word doc', 'word document', '.docx', or requests to produce professional documents with formatting like tables of contents, headings, page numbers, or letterheads. Also use when extracting or reorganizing content from .docx files, inserting or replacing images in documents, performing find-and-replace in Word files, working with tracked changes or comments, or converting content into a polished Word document. If the user asks for a 'report', 'memo', 'letter', 'template', or similar deliverable as a Word or .docx file, use this skill. Do NOT use for PDFs, spreadsheets, Google Docs, or general coding tasks unrelated to document generation.
- **executing-plans** — Use when you have a written implementation plan to execute in a separate session with review checkpoints
- **explore-knowledge-graph** — 当用户提问时自动触发，从知识图谱中检索相关的业务规则、服务关系、配置约定、代码位置、业务枚举、业务术语，为回答提供上下文。触发词：业务规则, 服务关系, 配置约定, 代码位置, 业务枚举, 业务术语, 知识图谱
- **figma-plugin-architect** — 开发 Figma 插件时使用。生成 manifest.json、code.ts、ui.html 标准架构代码，包含 Variables API、双线程通信、类型安全最佳实践。
- **find-skills** — Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
- **fix-eslint** — Automatically fix ESLint errors by modifying code to comply with linting rules. For small codebases (≤20 errors), fixes directly. For larger codebases (>20 errors), spawns parallel agents per directory for efficient processing. Never disables rules or adds ignore comments.
- **frontend-design** — Create distinctive, production-grade frontend interfaces with high design quality. Use this skill when the user asks to build web components, pages, artifacts, posters, or applications (examples include websites, landing pages, dashboards, React components, HTML/CSS layouts, or when styling/beautifying any web UI). Generates creative, polished code and UI design that avoids generic AI aesthetics.
- **grafana-alerts** — Grafana 监控告警分析工具。查询告警规则及其监控 SQL、查看当前触发的告警、搜索 Dashboard 面板、直接查询数据源。当收到 Grafana 告警或需要排查监控问题时使用。
- **grafana-query** — Grafana 监控查询工具。查询告警规则及其监控 SQL、查看当前触发的告警、搜索 Dashboard 面板、直接查询数据源。当收到 Grafana 告警或需要排查监控问题时使用。
- **java-toolkit-guide** — 当编写 com.yamibuy 包下的 Java 代码，需要使用 yami-core、ec-core、central-core 库，
- **manage-openproject** — 当需要查询 OP、创建 OP、更新 OP、查看项目工作包、管理工作包状态时使用。
- **manage-session-memory** — 当需要保存对话记忆、检索历史知识、查看决策记录、回忆踩坑经验、管理 LLM 记忆时使用。
- **mcp-builder** — Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK).
- **pdf** — Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting PDFs, extracting images, and OCR on scanned PDFs to make them searchable. If the user mentions a .pdf file or asks to produce one, use this skill.
- **pptx** — Use this skill any time a .pptx file is involved in any way — as input, output, or both. This includes: creating slide decks, pitch decks, or presentations; reading, parsing, or extracting text from any .pptx file (even if the extracted content will be used elsewhere, like in an email or summary); editing, modifying, or updating existing presentations; combining or splitting slide files; working with templates, layouts, speaker notes, or comments. Trigger whenever the user mentions \"deck,\" \"slides,\" \"presentation,\" or references a .pptx filename, regardless of what they plan to do with the content afterward. If a .pptx file needs to be opened, created, or touched, use this skill.
- **pr-create** — 当需要创建 PR、推送分支、提交代码到远程仓库时使用。触发词：pr, pull request, 创建pr, push pr, git push, 提交代码
- **pr-publish** — 当需要生成发布邮件、填写上线通知、查看 PR 合并记录、扫描 GitHub 仓库已合并 PR 时使用。触发词：发布邮件, 上线通知, PR合并, release, 发布TAG, 回滚TAG, Google Sheets 模板, gh pr list
- **query-kibana-logs** — 当需要搜索微服务日志、查看 Elasticsearch/Kibana 日志、排查线上问题、追踪订单日志、查找错误异常、做日志聚合统计时使用。
- **review-code-changes** — 当需要对当前分支的 git 变更进行（PR Review）代码审查、检查 SOLID 违规、安全风险、代码质量问题时使用。
- **save-db-knowledge** — 当回答用户的问题, 或者任务处理完成后，分析本次对话是否涉及数据库相关知识（表结构、枚举值定义、表关联关系、SQL示例、业务规则、查询意图），如有则保存到数据库知识图谱。触发词：保存表结构, 记录枚举值, 数据库知识, SQL知识, 表关系保存
- **save-knowledge-graph** — 当回答用户的问题, 或者任务处理完成后，分析本次对话是否涉及业务知识（业务规则、服务关系、配置约定、代码位置映射、业务枚举、业务术语），如有则保存到知识图谱。触发词：保存知识, 记录业务, 知识图谱, 业务沉淀
- **skill-creator** — Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.
- **skill-creator-kiro** — Create new Agent Skills or improve existing ones for Kiro. Use when users want to create a skill from scratch, update or optimize an existing skill, or learn how to write effective skills. Also use when users mention "创建 skill"、"写一个 skill"、"新建技能" or similar.
- **sql-query** — 当需要查询数据库、查看表结构、确认代码枚举值是否正确、搜索知识图谱时使用。触发词：sql, 数据库, 查询, mysql, 枚举, yamibuy, 业务数据
- **steering-creator** — Create or improve Kiro steering files following official specifications. Use when users want to create a new steering file, update an existing one, or learn about steering conventions. Also use when users mention "创建 steering"、"写 steering"、"新建 steering" or similar.
- **ui-ux-pro-max** — UI/UX design intelligence. 50 styles, 21 palettes, 50 font pairings, 20 charts, 9 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui). Actions: plan, build, create, design, implement, review, fix, improve, optimize, enhance, refactor, check UI/UX code. Projects: website, landing page, dashboard, admin panel, e-commerce, SaaS, portfolio, blog, mobile app, .html, .tsx, .vue, .svelte. Elements: button, modal, navbar, sidebar, card, table, form, chart. Styles: glassmorphism, claymorphism, minimalism, brutalism, neumorphism, bento grid, dark mode, responsive, skeuomorphism, flat design. Topics: color palette, accessibility, animation, layout, typography, font pairing, spacing, hover, shadow, gradient. Integrations: shadcn/ui MCP for component search and examples.
- **using-git-worktrees** — Use when starting feature work that needs isolation from current workspace or before executing implementation plans - creates isolated git worktrees with smart directory selection and safety verification
- **verification-before-completion** — Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
- **workspace-switcher** — 当需要切换 workspace 项目、加载项目到工作区、减少 Kiro 卡顿、管理工作区项目时使用。
- **writing-plans** — Use when you have a spec or requirements for a multi-step task, before touching code
- **xlsx** — Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .csv, or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data); create a new spreadsheet from scratch or from other data sources; or convert between tabular file formats. Trigger especially when the user references a spreadsheet file by name or path — even casually (like \"the xlsx in my downloads\") — and wants something done to it or produced from it. Also trigger for cleaning or restructuring messy tabular data files (malformed rows, misplaced headers, junk data) into proper spreadsheets. The deliverable must be a spreadsheet file. Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration, even if tabular data is involved.
- **yami-public-toolkit** — 当需要使用 Redis 缓存注解、接口限流、分布式锁、文件上传、AB测试等公共工具时使用。触发词：yami-public, 工具包, 缓存, 限流, 分布式锁, AB测试, 文件上传, CacheableRedis, RequestLimit, RedisLockClient, BatchTask, Segment, SpringEL, 算法
- **yamibuy-order-flow** — 当需要了解亚米网下单流程、订单状态流转、MQ 消息追踪、预占机制、风控流程、支付回调、订单落库时使用。触发词：亚米网, 订单流程, ec-so, central-so, ec-payment, RabbitMQ, 预占, 风控, order_status, shipping_status, pay_status, abnormal, persistence.order_v2, order.finish
