---
inclusion: auto
name: sub-agent-guide
description: 当需要委派子任务、使用代理、选择Sub-Agent、分析代码模块、排查线上问题、生成发布文档、生成测试用例时使用。触发词：sub-agent, 代理, 委派任务, context-gatherer, code-analyzer, issue-investigator, release-doc-generator, test-case-generator, 代码探索, 模块分析, 问题排查
---

# 代理（Sub-Agent）使用选择指南

根据任务类型选择合适的代理，避免在主代理中处理复杂且相干性低的子任务：

| 代理名称 | 适用场景 | 何时使用 |
|---------|---------|---------|
| `context-gatherer` | 代码探索、文件定位、调用链梳理 | 不熟悉代码库时，先用它收集上下文，再动手改代码。每次会话最多调用一次 |
| `code-analyzer` | 模块架构分析、调用链追踪、SQL 链路映射 | 需要理解某个模块的完整架构和依赖关系时，指定模块路径即可自动生成文档 |
| `issue-investigator` | 线上问题排查、错误日志追踪、异常数据分析 | 排查线上问题时，描述现象（错误信息、订单号、服务名），自动执行排查流程 |
| `release-doc-generator` | 发布文档生成、多仓库代码变更扫描 | 准备上线文档、查看多仓库变更时使用 |
| `test-case-generator` | 前端测试用例生成 | 为前端功能生成浏览器测试计划时使用 |

选择原则：
1. 优先使用专用代理（如 `code-analyzer`、`issue-investigator`），而非通用代理
2. 复杂且与主任务相干性低的子任务，委派给 sub-agent 处理，不要阻塞主流程
3. `context-gatherer` 是探索未知代码的首选，但收集完上下文后应回到主代理继续工作
