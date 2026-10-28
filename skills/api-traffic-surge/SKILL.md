---
name: api-traffic-surge
description: "基于 Elasticsearch 的 Request URL 应用日志，生成或更新 Kibana 半小时接口调用对比与突增判定看板，并查询只读监控结果。用于接口调用量、7天同段均值、上周同期、历史峰值和突增规则；不用于通用日志搜索或自动配置消息推送。触发词：接口突增, 调用量, Kibana 看板, 突增判定, 7天均值, 上周同期, 历史峰值"
---

# API Traffic Surge

目标环境为 Elasticsearch / Kibana 7.15，Python 3.9+，运行脚本仅用标准库。其他版本需要在目标环境验证 API、导入和渲染，不能仅凭 HTTP 成功就声称看板可用。

## 输入与范围

先确定目标 ES/Kibana、服务索引、接口路径和看板用途。已有任务明确的配置与授权可以直接复用。只有接收方有相应网络和账号权限时，技能才可操作其环境；技能不提供访问权限。

- 配置格式见 [配置示例](references/api-monitor-config.sample.json)。复制到工作区再修改，不把访问凭证写入配置或 skill。
- 接口信息须由日志的 `Request URL : /path  Request Method : ...` 文本提供。`path` 去掉服务前缀；也兼容旧配置的 `match: "Request URL : /path"`。
- 用 `Request Method` 后置标记约束短语，避免 `/webhook` 包含 `/webhook/child`。这是 ES 分词后的短语匹配；若业务要求区分分析器归一化后的符号/大小写，应先提供独立 keyword 路径字段并改造查询，不能宣称逐字节精确。
- 日志条数不等于按 request ID 去重的调用数。数据需保留至少 8 天及当前窗口；历史不足时不判突增。
- 一服务一看板、多服务合并都支持，遵从用户选择。单看板最多 50 个接口，超出时拆分。

## 统计口径

详见 [算法与边界](references/algorithm.md)。默认近 24 小时、48 个**完整半小时**，未完成时段不参与判定。每接口单独显示：实际量（蓝柱）、前7天同段均值（橙线）、上周同期调用量（绿虚线）、前7天同段峰值（灰虚线）；突增柱标红。

三项同时满足：`当前 > μ + surge_k×σ`、`当前 > peak×peak_ratio`、`当前 ≥ surge_min_count`。默认 `3 / 2 / 200`；历史7个值全零且数据覆盖齐全时，达到最低量即标记。σ使用总体标准差。同比、环比仅参考。

时区可设 `UTC` 或半小时对齐的固定偏移（默认 `+08:00`），不支持夏令时地区名称。对比图遵从顶部时间范围并向下对齐半小时；判定表固定最近完整半小时。顶部 KQL/过滤器不参与固定接口口径计算。

## 生成与发布

相对路径均以本 skill 目录为基准；命令中的配置和输出路径应换为当前工作区的实际路径。

1. 填写工作区配置，选择独一的 `dashboard_key`。相同 key 和接口名产生稳定 ID，可重复更新；不同人的看板应使用不同 key。
2. 默认先生成本地导入文件，**不发网络请求**：
   ```bash
   python3 scripts/gen_vega_dashboard.py /path/to/api-monitor-config.json --out /path/to/output
   ```
   得到 `dashboard.ndjson` 和 `manifest.json`。生成器实际加载附带的两个完整 Vega 模板，参数、接口和查询统一从配置注入。
3. 发布前，使用下面的只读查询核对数据。如果用户已要求创建/更新目标看板，按既有授权继续，不重复索要确认；未授权外部写入时停在生成文件。
4. 将 NDJSON 在 Kibana Saved Objects 中导入，或显式使用 API 创建：
   ```bash
   python3 scripts/gen_vega_dashboard.py /path/to/api-monitor-config.json --out /path/to/output --apply
   ```
   更新同一配置管理的对象需 `--apply --update`。脚本先检查所有 ID，拒绝覆盖无本技能标记的对象，更新时带版本防止覆盖并发修改；全部保存后回读核对。参数 `space` 可指定 Kibana 空间。
5. 若发布中途失败，检查 `apply-receipt.json`：它记录已写对象和更新前快照。停止并说明实际部分结果，不自动重试写入或删除对象。NDJSON 手工导入不具备脚本的所有权检查，导入前应检查冲突，勿直接勾选覆盖陌生对象。
6. 打开目标看板检查图表、图例、标签和数值，必要时截图。`saved` 只代表 API 保存与回读成功；只有页面实际渲染后，才称看板完成。Manifest 的 `render_verified` 默认 false，避免冒称已完成 UI 验证。

生成器不会更新未列出的旧接口对象，也不会删除移除接口的可视化；旧对象可由用户另行清理，避免误删共享对象。参照 [验证方法](references/validation.md) 验证。

## 只读监控

```bash
python3 scripts/api_monitor.py --config /path/to/api-monitor-config.json --output /path/to/result.json
python3 scripts/api_monitor.py --config /path/to/api-monitor-config.json --date 2026-10-21
```

默认查询近24小时完整时段。`--date` 是配置时区中的已结束自然日，不允许把当天/未来当成完整一天。结果为 JSON，包含每接口各半小时、基线、周同比、环比和突增列表。

- ES 超时、分片失败、实际桶/聚合结构缺失：退出非零；`has_surge` 为 null，不能解释为正常。
- 服务历史日源日志不足：具体时段 `complete=false`，不标突增；接口正常零流量仍保留零桶。
- 不写历史缓存、不自动删除文件、不含调度或消息推送。有额外推送需求时，另行明确接收方、触发周期与去重规则。若外部任务每半小时运行，仅处理最新完成时段，并以“接口+时段起点”去重，勿重复推送全天旧异常。

## 连接与分享

`es_url` / `kibana_url` 可放在接收方私有配置中，或分别用环境变量 `ELASTICSEARCH_URL` / `KIBANA_URL`。命令行 `--es-url` / `--kibana-url` 优先于环境变量，环境变量优先于配置。

如需认证，在当前进程环境设置 `ELASTICSEARCH_AUTHORIZATION` / `KIBANA_AUTHORIZATION`，值为服务支持的完整 Authorization 头（例如 `ApiKey ...`、`Bearer ...` 或 `Basic ...`）。不要打印凭证、嵌入URL、写入SKILL或分享包。脚本不读取浏览器 Cookie，不关闭证书校验，不调整账号权限。

分享本文件、scripts、references、tests、agents 即可；不要打包个人配置、结果数据、凭证、缓存、`.DS_Store` 或 `__pycache__`。当前示例只含虚构地址/接口。收件人将整个目录安装到自己的 skill 目录，或直接按脚本命令运行。
