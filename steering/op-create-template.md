---
inclusion: auto
name: op-create-template
description: 当需要创建 OpenProject 工作包（OP）、新建 tech-team 项目 OP、按模板填写 OP 参数时使用。触发词：创建OP, 建OP, 新建工作包, 帮我创建OP, OpenProject, tech-team
---

# OpenProject (OP) 创建模板（tech-team 项目）

> 来源：参照 william 创建的 OP 39698 / 39701 固化。
> 目的：用户只需给出「标题 + 描述内容」，即可按本模板一键创建 OP。

## 使用方式

用户给出 OP 内容（标题 + 现象/原因/方案）后，直接调用 `openproject_create_work_package`，
按下方「默认参数」填写，无需再逐项追问。创建后把链接返回给用户。

## 标准执行流程（每次创建严格按此走）

1. **取当前日期和周编号**：先跑一次 PowerShell（见下方周编号脚本），同时得到 `yyyy-MM-dd` 和 `年份+周数`。
2. **组装标题和描述**：
   - 标题（subject）用用户给的；若用户只给了一句话，提炼成简短标题。
   - 描述（description）至少 10 字；用户没写详细方案时，按「现象/需求 + 方案」两段补全。
3. **按默认参数一次性调用** `openproject_create_work_package`，自定义字段严格照下方清单填。
   - **cf17 (Launched Date) 绝不带入**，创建时直接省略该字段。
   - cf11 填第 1 步算出的周编号；start_date / due_date 填当前日期。
4. **返回结果**：OP ID + 链接 + 一张核对小表（Requestor / Symbol / Requirement type / 日期）。
5. 用户若说某字段要改（Channel / Theme / Requirement type 等），用 `openproject_update_work_package` 单独改，不重建。

## 不要做的事

- ❌ 不要逐项追问默认字段（PIC、Channel、Theme、Trimester 等都有默认值，直接用）。
- ❌ 不要凭记忆猜周编号，必须用脚本算。
- ❌ 创建时不要带 cf17 (Launched Date)。
- ❌ 不要在 start_date / due_date 用 39698 的旧日期，始终用当前日期。
- ✅ 只有当用户明确点名某字段用别的值时才覆盖默认。

## 默认参数（全部复用，除非用户另行指定）

| 字段 | tool 参数 | 默认值 | 说明 |
|---|---|---|---|
| 项目 | `project_id` | `"3"` | tech-team (T-PMAD) |
| 类型 | `type_id` | `8` | Project |
| 优先级 | `priority_id` | `8` | Normal |
| 指派人 | `assignee_id` | `15` | william he |
| 开始/截止日期 | `start_date` / `due_date` | **当前日期** | 用 `Get-Date -Format "yyyy-MM-dd"` 取，两个都填同一天 |

## 默认自定义字段（custom_fields）

| field_id | 名称 | 默认值 | 额外标志 |
|---|---|---|---|
| 9 | PIC | `"15"`（william he） | — |
| 16 | Requestor | `"15"`（william he） | 先填自己，用户后续手动调整 |
| 51 | PM | `"15"`（william he） | — |
| 1 | Channel | `"239"`（Operations） | `is_array: true` |
| 54 | Theme | `"245"`（Improvement 改进） | — |
| 62 | Dept. | `"270"`（Tech） | — |
| 18 | Project Type | `"42"`（Business） | — |
| 19 | Test Case Analyze | `"45"`（无影响） | — |
| 89 | Requirement type | `"335"`（**New Feature**，默认值） | — |
| 126 | Trimester | `"687"`（T2 2026） | `is_array: true` |
| 87 | Is reporting | `"true"` | `is_bool: true` |
| 11 | Symbol | **当前周编号**，如 `"202641"` | `is_text: true`，见下方周编号规则 |
| 17 | Launched Date | **不填（留空）** | 发布时用户手动填截图时间，创建时不要带此字段 |

## 周编号规则（cf11 / Symbol）

格式 = `年份(4位) + ISO周数(2位，补零)`，例如 2026 年第 41 周 = `202641`。

创建前用 PowerShell 取当前 ISO 周数：

```powershell
$d = Get-Date
$week = [System.Globalization.ISOWeek]::GetWeekOfYear($d)
"{0}{1:D2}" -f $d.Year, $week
```

> ⚠️ 部分 PowerShell 环境取不到 `[System.Globalization.ISOWeek]`（报 `TypeNotFound`）。
> 这种情况用 Calendar 版本（已在 2026-10 实测可用）：
>
> ```powershell
> $d = Get-Date
> $cal = [System.Globalization.CultureInfo]::InvariantCulture.Calendar
> $day = $cal.GetDayOfWeek($d)
> if ($day -eq [System.DayOfWeek]::Sunday) { $d2 = $d.AddDays(-3) } else { $d2 = $d.AddDays(3 - (([int]$day + 6) % 7)) }
> $week = $cal.GetWeekOfYear($d2, [System.Globalization.CalendarWeekRule]::FirstFourDayWeek, [System.DayOfWeek]::Monday)
> "{0}{1:D2}" -f $d2.Year, $week
> ```

## 创建后处理

1. 创建成功后返回 OP ID 和链接给用户。
2. 用一张小表列出关键填入值（Requestor / Symbol / Requirement type / 日期），方便用户核对。
3. 若用户指定了与默认不同的字段（如 Channel、Theme、Requirement type），以用户指定为准。

## 常见覆盖项

- Requirement type (cf89)：默认 New Feature(335)。可选：UI(333)/UI-UX(334)/Epic(336)/Data(337)/Bug Fix(338)/Tech(339)/Support(340)
- Channel (cf1)：常用 Operations(239)、SSS-3P(603)、SSS-1P(602)
- Theme (cf54)：Improvement(245)、Organic growth(242)、Improved profitability(243)、Marketing efficiency(244)、Analyse/Data report(246)
- Trimester (cf126)：T2 2026(687)、T3 2026(688)、T1 2026(656)

## 基于已有 OP 派生创建（2026-10 实践）

当用户说「基于某个 OP 创建一个 OP」「照着 XXX 建一个」时，按以下要点处理：

### 1. 先读源 OP，照搬业务字段
- 用 `openproject_get_work_package`（`response_format: "json"`）读源 OP，拿到它的 Channel / Theme / Requirement type / Requestor 等字段的真实值和用户 ID。
- 新 OP 的这些字段**跟随源 OP**，而不是用本模板的默认值（例如源 OP 是 Bug Fix，新 OP 的 cf89 也填 Bug Fix(338)）。
- 从源 OP 的 JSON 里取用户 ID：`author`（创建人）和 `customField16`（Requestor）节点下的 `id`。`list_users` 工具无权限，只能这样取。

### 2. Requestor（cf16）复用源 OP 的 requestor
- 用户要求「创建人设置成原始 requestor」时，改的是 **Requestor (cf16)**，填源 OP 的 cf16 用户 ID。
- ⚠️ **系统创建人（author）无法通过 API 修改**，它由调用 API 的账号（本 key = william he）自动决定。要让 author 真正变成别人，只能用那个人的账号重建。向用户说明这一点，不要假装改成功了。

### 3. 设置父级（parent）——update 工具不支持，用 REST API
`openproject_update_work_package` 没有 parent 参数。设置父级要直接 PATCH：

```powershell
$key = $env:OPENPROJECT_API_KEY
if (-not $key) { throw "缺少环境变量 OPENPROJECT_API_KEY" }
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("apikey:$key"))
$headers = @{ Authorization = "Basic $auth" }
# 先取当前 lockVersion（每次改动后会 +1，必须用最新值）
$wp = Invoke-RestMethod -Uri "https://openproject.yamibuy.net/api/v3/work_packages/<新OP_ID>" -Headers $headers -Method Get
$body = @{ lockVersion = $wp.lockVersion; _links = @{ parent = @{ href = "/api/v3/work_packages/<父OP_ID>" } } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "https://openproject.yamibuy.net/api/v3/work_packages/<新OP_ID>" -Headers $headers -Method Patch -ContentType "application/json" -Body $body
```

- 设置成功后，源 OP 的 `children` 会出现新 OP，新 OP 的 `parent` / `ancestors` 指向源 OP。读一次 json 确认。

### 4. 附件不会自动带过来
源 OP 的截图 / 附件不会随派生创建复制。用户需要时，单独下载源 OP 附件再上传到新 OP，并提醒用户这一点。

## 完整调用示例（照抄此结构，仅改 subject / description）

```json
{
  "project_id": "3",
  "type_id": 8,
  "priority_id": 8,
  "assignee_id": 15,
  "subject": "<用户给的标题>",
  "description": "现象/需求：<...>\n\n方案：<...>",
  "start_date": "<当前日期 yyyy-MM-dd>",
  "due_date": "<当前日期 yyyy-MM-dd>",
  "custom_fields": [
    { "field_id": 9,  "value": "15" },
    { "field_id": 16, "value": "15" },
    { "field_id": 51, "value": "15" },
    { "field_id": 1,  "value": "239", "is_array": true },
    { "field_id": 54, "value": "245" },
    { "field_id": 62, "value": "270" },
    { "field_id": 18, "value": "42" },
    { "field_id": 19, "value": "45" },
    { "field_id": 89, "value": "335" },
    { "field_id": 126, "value": "687", "is_array": true },
    { "field_id": 87, "value": "true", "is_bool": true },
    { "field_id": 11, "value": "<当前周编号，如 202641>", "is_text": true }
  ]
}
```

> 注意：示例里**故意没有 cf17 (Launched Date)**，创建时就是不填。

## 参考

- 查某字段全部可选值：`openproject_get_schema`，`project_id=3, type_id=8`
- 用户 ID：william he = 15；James Wu = 377；Sally Jia = 106
- OpenProject API Key：走环境变量 `OPENPROJECT_API_KEY`（真值用 account-password-query 查，禁止从 MCP 备份文件里读明文）；Base URL：`https://openproject.yamibuy.net`（REST API 直连设置父级时要用）
