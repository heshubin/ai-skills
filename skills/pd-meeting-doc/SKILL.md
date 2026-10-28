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
- chris li — Packing, 物流
- Jun Qu（ID: 469）— BPM, 盘点, RMA
- nikki ma（ID: 75）— QA 测试

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

**重要限制**：
- query_id=82 是全公司 Operations Channel，不只是 PD 小组，不要拉全量
- 只写 **本期有 Launched Date 或 updatedAt 在周期内** 的工单
- 不要写 New 状态（没开始做的）

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

### 步骤 3: 写入模板文档（暂存）

使用 `mcp_google_docs_replaceDocumentWithMarkdown` 写入**模板文档**：
- documentId: `10zY9LPzQpqYfUWx3hLAKhC0RonJeJBrrrVRkbTe0PHQ`
- `firstHeadingAsTitle: true`（第一行 `#` 渲染为 Title 大标题）

```
mcp_google_docs_replaceDocumentWithMarkdown(
  documentId="10zY9LPzQpqYfUWx3hLAKhC0RonJeJBrrrVRkbTe0PHQ",
  markdown="{上面的模板内容}",
  firstHeadingAsTitle=True
)
```

**已验证的格式效果**（2026-08-27）：
- `#` 标题 → Title 大字体
- `参加者:` → Normal text 小字
- `---` → 分隔线
- `## 各方向更新` → Heading 2（⚠️ 会出现在大纲里，见步骤4修复）
- `- **ICQA**` → bullet list，加粗正确
- `  - 子项` → 二级 bullet

### 步骤 4: 修复大纲（节标题降为 Normal text）

`replaceDocumentWithMarkdown` 会把所有 `##` 都变成 Heading 2，出现在文档大纲。
需要把节标题改回 Normal text，只保留时间标题：

```python
# 需要改为 Normal text 的段落（用 findText 定位）
节标题列表 = [
    "各方向更新",
    "1. 技术 - PD重点方向",
    "2. 其它",
    "3. 人员状态",
    "4. Support",
    "5. 待办"
]
# 对每个节标题调用：
mcp_google_docs_applyParagraphStyle(
  documentId="10zY9LPzQpqYfUWx3hLAKhC0RonJeJBrrrVRkbTe0PHQ",
  style={"namedStyleType": "NORMAL_TEXT"},
  target={"textToFind": "各方向更新"}
)
# ... 重复6次
```

### 步骤 5: 复制内容到正式文档

正式例会文档 `18DKShN...` 中，新内容插入在文档顶部（最新期在最上面）。

**方法**：
1. 读取正式文档当前顶部内容的起始 index（通常是 1）
2. 在 index 1 处 `replaceRangeWithMarkdown`（从 1 到 2，即插入到最前面）
3. 插入后同样执行步骤 4 的节标题降级

**直接写入正式文档**（不需要模板中转）：
```python
# 先找到上一期标题的位置作为插入终点
mcp_google_docs_findElement(documentId="18DKShN...", textQuery="上一期日期")
# 然后 replaceRangeWithMarkdown(startIndex=1, endIndex=上一期位置-1, markdown=内容)
```

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

---

## 快速启动提示词

用户说：**"帮我写这期例会，8月7号到8月26号"**

你的流程：
1. 问用户有没有导出 OP Excel（有的话直接读取，最快）
2. 没有则 API 查5个人本期工单（按 ID 逐个查）
3. 过滤出 Launched/Done/In testing/In progress 状态
4. 套用上方模板，写入模板文档
5. 修复节标题为 Normal text
6. 通知用户去正式文档 `18DKShN...` 里查看（或直接写入）

