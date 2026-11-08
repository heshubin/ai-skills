---
name: pd-meeting-doc
description: 整理 Promise Delivery (PD) 团队双周例会文档，从 OpenProject 拉取本期进展写入 Google Docs 例会记录时使用。触发词：例会, PD例会, 写例会, 例会文档, biweekly meeting, 双周例会, meeting notes
---
# PD 例会文档撰写

## 触发词
例会, PD例会, 写例会, 例会文档, biweekly meeting, 双周例会, meeting notes

## 概述
Promise Delivery (PD) 团队每两周开一次例会，需要将本期工作进展整理成固定格式的文档，写入 Google Docs 例会文档。

---

## 关键信息

- **目标文档（正式例会记录）**: https://docs.google.com/document/d/18DKShNRlfo3GetfKisauUuyHF7MRaUOwCSL0FMeZJjM/edit
- **模板文档（格式参考）**: https://docs.google.com/document/d/10zY9LPzQpqYfUWx3hLAKhC0RonJeJBrrrVRkbTe0PHQ/edit
- **OpenProject 看板**: https://openproject.yamibuy.net/projects/tech-team/work_packages?query_id=82
- **周期**: 每两周一次
- **参加者**: Eaven Wang, Jeff Gu, Sally Jia, magi ma, Evan Niu, William He

## PD 小组成员（技术 William 部分）

只写这5个人的工单，其他人不写：
- william he（ID: 15）— Zone Picking, EXDD, 保质期
- aiden duan（ID: 36）— WMS App
- chris li（ID: 56）— Packing, 物流
- Jun Qu（ID: 469）— BPM, 盘点, RMA
- nikki ma（ID: 75）— QA 测试

> 5 人 ID 速查：`15, 36, 56, 469, 75`（2026-11-04 已全部核实）。
> 查某人 ID：`GET /api/v3/principals?filters=[{"name":{"operator":"~","values":["chris"]}}]`

---

## 操作流程

### 步骤 1: 获取 OP 数据

**方法 A（推荐）：用户导出 Excel**

用户在 OP 看板 query_id=82 导出 xls 文件后，读取方式：
```powershell
# 保存为 csv
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false; $excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open("路径.xls")
$wb.SaveAs("路径.csv", 6)
$wb.Close($false); $excel.Quit()

# 读取并过滤团队成员
$csv = Import-Csv "路径.csv" -Encoding Default
$team = @("aiden duan","william he","chris li","nikki ma","Jun Qu")
$csv | Where-Object { $_.'受理人' -in $team }
```

**注意**：xls 中文字段名为"受理人"，英文字段用 assignee。Subject 列可能乱码，用 ID 对照 API 拿标题。

**方法 B：API 查询（每人单独查）**

```powershell
$apiKey = $env:OPENPROJECT_API_KEY
if (-not $apiKey) { throw "缺少环境变量 OPENPROJECT_API_KEY" }
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("apikey:$apiKey"))
$headers = @{ "Authorization" = "Basic $auth" }

# 每人单独查（按 ID），合并结果
$memberIds = @(15, 36, 469, 75)  # william, aiden, Jun Qu, nikki（chris li ID 待确认）
foreach ($uid in $memberIds) {
    $filters = "[{`"updatedAt`":{`"operator`":`"<>d`",`"values`":[`"{起始}T00:00:00Z`",`"{结束}T23:59:59Z`"]}},{`"assigneeOrGroup`":{`"operator`":`"=`",`"values`":[`"$uid`"]}}]"
    $url = "https://openproject.yamibuy.net/api/v3/work_packages?pageSize=100&filters=$([uri]::EscapeDataString($filters))"
    Invoke-RestMethod -Uri $url -Headers $headers
}
```

**方法 C（2026-11-04 实战验证，最可靠）：Playwright 借用浏览器登录会话查 OP API**

当 mcp.json 里的 OP API key 失效（curl 返回 401）、或 openproject MCP 连不上时，用这个方法——借用户 Chrome 里已登录的 OP 会话，一次查询就带上「本期更新时间 + 5 人」双过滤，直接拿到全部工单：

```
# 1. 列出标签页，别打断用户正在用的页面
mcp_playwright_browser_tabs(action="list")
# 2. 新开标签页到 OP 看板（让会话 cookie 生效）
mcp_playwright_browser_tabs(action="new", url="https://openproject.yamibuy.net/projects/tech-team/work_packages?query_id=82")
# 3. 在页面内 fetch，带 credentials:'include' 用登录态；输出大，写文件
mcp_playwright_browser_evaluate(
  filename="docs/tmp/op-pd-period.json",
  function="""async () => {
    const filters = encodeURIComponent(JSON.stringify([
      {updatedAt:{operator:'<>d',values:['{起始}T00:00:00Z','{结束}T23:59:59Z']}},
      {assigneeOrGroup:{operator:'=',values:['15','36','56','469','75']}}
    ]));
    const url = 'https://openproject.yamibuy.net/api/v3/work_packages?pageSize=200&filters=' + filters;
    const r = await fetch(url, { headers:{Accept:'application/json'}, credentials:'include' });
    const j = await r.json();
    const els = (j._embedded && j._embedded.elements) || [];
    const items = els.map(e=>({id:e.id, subject:e.subject,
      assignee:e._links&&e._links.assignee&&e._links.assignee.title,
      status:e._links&&e._links.status&&e._links.status.title,
      updatedAt:e.updatedAt, startDate:e.startDate, dueDate:e.dueDate}));
    return JSON.stringify({total:j.total, count:j.count, items}, null, 2);
  }"""
)
```

坑：
- 跨域会被拦。fetch 必须在 **openproject.yamibuy.net 这个源的页面里**执行（所以要先 new 一个 OP 标签页）。在别的站点页面里 fetch OP API 会 `TypeError: Failed to fetch`。
- `assigneeOrGroup` + `values:['15',...]` 一次过滤 5 人，比逐人查快得多，`<>d` 是日期区间算子。

**重要限制**：
- query_id=82 是全公司 Operations Channel，不只是 PD 小组，**total 有两万多条，绝不能拉全量**，必须用上面的双过滤
- 只写 **本期有 Launched Date 或 updatedAt 在周期内** 的工单
- 不要写 New 状态（没开始做的）

### 步骤 1.5: 确认本期周期

- 周期起点 = 上一期的「终点日」次日。读正式文档顶部最新一期标题（`get_doc_as_markdown` 或 `get_doc_content`），拿到上期区间，接着往后排。
- 2026-10-14 那期是 9/17~10/14；本次就是 10/15~11/04。
- 周期终点以用户在 OP 看板上设置的 updatedAt 过滤区间为准（用户会直接告诉你，如「2026-10-15 - 2026-11-04」）。

### 步骤 2: 撰写内容

**内容规则（严格遵守）**：
1. **只写 OP 里有的** — 不编造任何内容，没有的不写
2. **只写本期周期内** — 不继承历史工单，加拿大开仓等历史内容不展开
3. **不写人名分组** — "其它"部分直接平铺所有工单，不按人名分组
4. **ICQA/OE/Trans 方向** — 只写用户告知的内容，没有就留空或省略

**文档格式**（以下是正确的 Markdown 模板）：

```markdown
# {年}年{月}月{日}日 | PD例会({起始日期}~{结束日期}  {天数}天)

参加者: Eaven Wang  Jeff Gu  Sally Jia  magi ma  Evan Niu  William He

---

## 各方向更新

- **ICQA** - Claire/Ziyi
  - {ICQA 本期更新，没有就写"暂无"}
- **OE** - Eaven/Sophie
  - {OE 本期更新}
- **Trans** - Jeff/Magi
  - {Trans 本期更新}
- **技术** - William

---

## 1. 技术 - PD重点方向

- **{重点项目名}**  **{状态}**
  - {子项}  **{状态}**
  - ...

---

## 2. 其它

- [OP-{id}] {标题}   {状态}
- [OP-{id}] {标题}   {状态}
- ...
- James相关需求  若干

---

## 3. 人员状态

**{人员动态，如：无变动，持续招聘中 / X月X日新入职1人}**

---

## 4. Support

- {support 事项，没有就省略这节}

---

## 5. 待办

- [ ] {待办事项}
```

### 步骤 3: 选对 Google Docs 工具链（重要，2026-11-04 更新）

本任务有两套 Google MCP，**优先用 `google_workspace`**：

| MCP | 状态 | 说明 |
|-----|------|------|
| `google_workspace`（工具前缀 `mcp_google_workspace_*`） | ✅ 可用 | OAuth 弹窗授权，账号 `william.he@yamibuy.com`。首次用会弹授权链接，让用户完成后重试。**所有调用都要带 `user_google_email`** |
| `google-docs`（工具前缀 `mcp_google_docs_*`） | ❌ 常失效 | token 过期后直接返回 `invalid_grant (400)`，且不给重新授权入口，自己修不了。别依赖它 |

> 「MCP 面板显示已连接」≠「能调 API」。连接指进程管道通，但背后的 OAuth token 可能过期。判断依据永远是「实际调一次 API 看返回」，不是面板颜色。

**不走模板中转，直接写正式文档。** 正式文档 `18DKShNRlfo3GetfKisauUuyHF7MRaUOwCSL0FMeZJjM`，最新一期在最顶部。

### 步骤 4: 写入正式文档（google_workspace，三步法，已验证）

```
# 4.1 在文档最顶部（index=1）插入本期标题行（结尾带 \n）
mcp_google_workspace_modify_doc_text(
  user_google_email="william.he@yamibuy.com",
  document_id="18DKShNRlfo3GetfKisauUuyHF7MRaUOwCSL0FMeZJjM",
  start_index=1,
  text="2026年11月4日 | PD例会(2026年10月15日~2026年11月4日  21天)\n"
)

# 4.2 把标题行设为 Heading 1（end_index=标题文本长度+1）
mcp_google_workspace_update_paragraph_style(
  user_google_email="william.he@yamibuy.com",
  document_id="18DKShN...",
  start_index=1, end_index=47,
  named_style_type="HEADING_1"
)

# 4.3 用 heading 模式把本期正文（Markdown）填到标题下方
#     heading 传刚插入的完整标题文本，工具自动定位到该节并替换/追加
mcp_google_workspace_modify_doc_text(
  user_google_email="william.he@yamibuy.com",
  document_id="18DKShN...",
  heading="2026年11月4日 | PD例会(2026年10月15日~2026年11月4日  21天)",
  heading_level=1,
  text="{本期正文 markdown}"
)
```

- 返回 `Replaced section under heading ...` = 干净替换（无重复）；`Appended to section ...` = 追加。重跑 4.3 修内容是安全的（它替换整节，不会叠加）。
- 每次写完 `get_doc_content(tab_id="")` 读回，确认：① 本期在最顶部 ② 上一期内容完好 ③ 无重复。

### 步骤 5: ⚠️ 嵌套列表会被拍平（本次最大的坑）

`modify_doc_text` 的 heading 模式 Markdown 渲染器 **不支持多级列表嵌套**：无论用 2 空格还是 4 空格缩进，所有 `- ` bullet 都会被拍平成同一层级，父子关系丢失。

**解决方案：分组父项用「加粗整行」，不要用 bullet；OP 子项才用 bullet。** 这样不依赖嵌套也能看出层级：

```markdown
1\. 技术 - PD重点方向

**Zone Picking Phase 2（分区拣货二期）**  进行中

- [OP-40026] Zone Picking Phase 2 主需求  进行中
- [OP-40130] 后端开发  进行中
- [OP-40383] Zone 2 ... Tote 复用无法自动释放  已上线

**EXDD（效期优化）**

- [OP-38175] EXDD优化项目  已上线
- [OP-40132] EXDD 实验优化 V2  已上线

2\. 其它

- [OP-39775] 上架接口逻辑重构  已上线
- ...
```

其它渲染注意：
- 节编号用 `1\. ` `2\. `（反斜杠转义），否则会被当成有序列表项。
- 不要用 `##` 开节标题（会进大纲），用纯文本 `1. 技术 - PD重点方向` 即可。
- `get_doc_content` / `get_doc_as_markdown` 多 tab 文档要带 `tab_id=""` 才读全；输出常超限会自动存文件，用 `read_file` / `Get-Content` 看落地文件。

---

## 状态词对照

| OP 状态 | 例会写法 |
|---------|---------|
| Launched | 已上线 |
| Done / Closed | 已完成 |
| In testing | 测试中 |
| In progress | 进行中 |
| Ready | 待发布 |
| New | 不写（没开始） |
| On hold | 不写（暂停中） |

---

## 常见错误（必须避免）

1. ❌ 写入 OP 里没有的内容（如 mTLS、加拿大配置、Relay Picking 废弃等）
2. ❌ 把全公司 query_id=82 的工单全部写进去
3. ❌ 继承上期的"加拿大开仓"历史子项列表
4. ❌ 节标题用 `##` 导致出现在文档大纲
5. ❌ 按人名分组（不需要，平铺即可）
6. ❌ 写 New 状态工单（那是排期中，没做）
7. ❌ 用 `yami-ai-cli add` 安装新工具前不备份 mcp.json
8. ❌ 分组子项用缩进 bullet 想做嵌套（会被拍平，改用「加粗父行 + bullet 子项」，见步骤5）
9. ❌ 依赖 `google-docs` MCP（token 常失效），应首选 `google_workspace`
10. ❌ 看到 MCP 面板"已连接"就以为能用——必须实际调一次 API 验证
11. ❌ 一次性拉 query_id=82 全量（两万多条），必须带「时间+5人」双过滤

---

## 环境故障速查（2026-11-04 实战）

| 症状 | 根因 | 处理 |
|------|------|------|
| openproject MCP 连不上 / 无日志 | `yami-openproject-mcp` 依赖 mcp SDK 1.x，uvx 默认装了 2.x 导致 `ModuleNotFoundError: mcp.server.fastmcp`，进程启动即崩 | mcp.json 的 openproject.args 里加 `"--with","mcp>=1.0,<2.0"`（和 yearning 一样钉版本），重连 |
| OP API 返回 401 Unauthenticated | mcp.json 里的 `OPENPROJECT_API_KEY` 过期/被重置（服务器可达、key 长度对也会 401） | 让用户在 OP「我的账户→访问令牌」重置 API token，更新 mcp.json，重连。`.kiro/settings/` 受保护，Agent 改不了，要用户手动改 |
| google-docs 工具 `invalid_grant 400` | 该 MCP 的 OAuth token 过期且无重授权入口 | 改用 `google_workspace`，首次会弹授权链接让用户完成 |
| 用 curl 验证 OP key | `curl.exe -u ("apikey:"+$key) URL`，看 `-w "%{http_code}"`。200=好，401=失效 | — |

---

## 快速启动提示词

用户说：**"帮我写这期例会，从 OP 看板读数据"**，并给出周期（如「2026-10-15 - 2026-11-04」）

验证过的流程（2026-11-04）：
1. 读正式文档顶部最新一期，确认本期周期接续（步骤 1.5）
2. 用 **Playwright 借浏览器会话查 OP**（方法 C），一次带「时间+5人(15,36,56,469,75)」双过滤，结果写 `docs/tmp/op-pd-period.json`
3. 过滤出 Launched/Done/In testing/In progress 状态（New/On hold 不写）
4. 套模板组织内容：重点方向（Zone Picking、EXDD 等）用「加粗父行 + bullet 子项」，其它平铺
5. 用 **google_workspace** 三步法直接写正式文档顶部（步骤 4），注意嵌套拍平坑（步骤 5）
6. `get_doc_content` 读回核对，把「ICQA/OE/Trans、人员状态、待办」这几处非技术内容列给用户确认
   - 人员状态会跨期延续（如产假区间覆盖本期要保留），主动和上一期对照

## 本期数据特征（参考，判断过滤是否合理）
- 正常一期技术侧约 15~25 条工单；若查出几百条，一定是过滤没生效或拉了全量
- 本期(10/15~11/04) 实得 24 条，可作量级基准

