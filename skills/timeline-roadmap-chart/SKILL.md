# 项目时间线 / 甘特路线图（展示级 SVG）

## 触发词
计划图, 时间线, 路线图, roadmap, 甘特图, timeline, 排期图, 周期图, 阶段图, phase 计划, 开发测试计划, 画个计划

## 概述
用纯手写 SVG（create_artifact kind=svg）画**展示级**的项目时间线/路线图，用于对业务方、管理层做汇报。
风格来自 Zone Picking Phase II 计划图：浅灰渐变底 + 月份带 + 周卡片刻度 + 渐变甘特条 + 白色胶囊人员标签 + 虚线重叠框 + 底部里程碑轴。

**两种典型用途**：
1. **未来排期图**（Phase 计划）：开发/测试/验收等阶段，带并行重叠、里程碑节点。
2. **回顾全景图**（已发生的工作）：多条分类泳道铺在时间轴上，标注节假日、当前位置。

---

## 设计规范（固定不动的视觉语言）

| 元素 | 规格 |
|------|------|
| 画布 | 阶段图 1024×530；泳道多/内容丰富用 1400×820 |
| 字体 | `'Segoe UI','Helvetica Neue',Arial,sans-serif` |
| 背景 | 线性渐变 `#f6f8fc → #eef2f9`（id=bg，左上到右下） |
| 标题 | 30px 800 粗，深色 `#0f172a`；关键词用 `<tspan fill="#2f6bed">` 高亮（如 Phase II） |
| 副标题 | 13.5px `#64748b`，一行写清：周期 / 关键节点 / 规则（如 5 working days/week） |
| 分隔线 | 标题下 `#e2e8f0` 1px |
| 月份带 | 高 22 圆角 5；OCT 用蓝 `#dbe5fb`/字 `#3b63c4`，NOV 用橙 `#fde7cf`/字 `#c87f2b`，letter-spacing=1 |
| 周卡片 | 白底圆角 8，描边 `#e5eaf2`；上行 W1 13px 700 `#334155`，下行日期 11px `#94a3b8` |
| 甘特条 | 高 40 圆角 12，渐变填充 + 阴影 `filter=url(#sh)`；条内左侧：阶段名 13.5px 700 白 + 日期 10.5px 浅色 |
| 人员胶囊 | 白底圆角 11（rx=11，高 22），opacity 0.92；字 11.5px 600，颜色=该泳道主色；贴在条形右端内部或条外 |
| 重叠框 | 无填充，橙描边 `#f59e0b` 1.8，`stroke-dasharray="6 4"`；下方标 `Overlap Nw` 11px 700 `#d97706` |
| 里程碑轴 | 底部水平线 `#cbd5e1` 1.5；普通节点彩色圆 r=7；关键节点（上线）红菱形 `path d="M x,y-11 l13,13 l-13,13 l-13,-13 z" fill="#dc2626"` |
| 节点标签 | 名称 12.5px 700 `#1e293b`，日期 11px `#64748b`，text-anchor=middle（末节点用 end） |
| 图例 | 底部一行，15×11 圆角 3 色块 + 12px `#475569` 文字 |

### 三色主题（阶段/泳道配色）
- **蓝 Development**：渐变 `#2f6bed → #5b8ef7`，主色 `#2f6bed`
- **紫 QA Testing**：渐变 `#8b3df0 → #b06cf7`，主色 `#8b3df0`
- **青 BSA / 验收**：渐变 `#0e9f8c → #19c2a6`，主色 `#0e9f8c`
- 需要更多分类时追加：橙 `#f59e0b→#fbbf24`、红 `#dc2626→#ef4444`、灰青 `#0891b2→#22d3ee`

---

## 核心方法：时间 → X 坐标的线性映射

**所有条形、节点、重叠框的 X 必须用同一个线性公式算，不能目测。**

```
时间轴起点 X0（第一周卡片左边 x，如 170）
每周宽度 Wk（相邻周卡片 x 之差，如 162）
每周含义：一周 = 5 个工作日（展示时按自然周对齐，周一~周五）

某日期落在第 N 周（N 从 1 开始）起点  →  X = X0 + (N-1) * Wk
阶段持续 D 周，条宽  →  width = D * Wk - gap（gap≈8，留卡片间隙则用卡片宽 154）
```

**对齐原则（展示用，关键）**：
- 按**自然周（周一~周五）对齐**，不按"从启动日连续数 5 个工作日"，否则边界落在周中、图不整齐。
- 启动日若是周中（如周五），首周卡片仍从该周画起，视觉上整齐，备注里说明首周实际工作日。
- **日期一律用 shell 先算星期和周边界**，禁止心算：

```powershell
foreach ($ds in "2026-10-16","2026-10-30","2026-11-19") {
  $d = Get-Date $ds; Write-Output ($ds + " " + $d.DayOfWeek)
}
```

---

## 操作流程

### 1. 先把排期算清楚，列成表给用户确认
周期起止、每阶段几周、并行重叠关系、里程碑日期、各阶段人员。**先出表、让用户确认，再画图**（改图成本高，改表成本低）。

### 2. 用 shell 校验所有关键日期的星期和周边界（见上）

### 3. 定映射参数
确定 X0、Wk、周数，把每个阶段/节点的日期换算成 X。写在注释里（如 `<!-- Dev 10/16..11/05 = 170..648 -->`），方便后续改。

### 4. 用 create_artifact kind=svg 画，套用下方模板

### 5. 自检遮挡（最容易翻车的一步，见下）

### 6. 交付后主动问是否导出 PNG
SVG 在不同机器字体渲染有差异，贴 PPT 建议导出 PNG。

---

## 遮挡自检清单（画完必查，踩过坑）

- [ ] **半透明覆盖层（节假日带/斜纹）绝不能盖住条形文字** → 分三层：底层淡背景带(0.5) → 条形(中层) → 条上只叠极淡斜纹(≤0.32)；文字永远在最上层
- [ ] **人员胶囊不压条内阶段名/日期** → 胶囊靠条右端，或移到条形外部右侧；条内长文字（如"QA Testing (early entry)"）要给胶囊留出空间
- [ ] **拥挤的窄条**（如 1 周条同时放文字+胶囊）→ 胶囊移到条外
- [ ] **里程碑轴独立成行**，不与泳道、图例挤在一起
- [ ] **text 元素不要用 cy 属性**（无效）；菱形用 path，圆点用 circle
- [ ] **末端节点标签** text-anchor 用 end，防止超出右边界
- [ ] 画布不够就加大（优先加宽），留足白

---

## 定制清单（用户常改的点，快速定位）

| 用户要改什么 | 改哪里 |
|------|------|
| 阶段起止/时长 | 重算 X 映射 → 改对应 `<rect>` 的 x/width |
| 提前/延后介入 | 改该泳道条的起点 x 和重叠框范围 |
| 某节点日期（如 System Ready） | 改里程碑节点的 cx + 标签文字 |
| 两节点合一（Ready=上线） | 删一个节点，保留红菱形，标签写合并文案 |
| 人员增减/改名 | 改胶囊 rect 宽度 + text |
| 压缩/拉长总周期 | 改周数、删多余月份带/周卡片，重算 Wk |
| 中英文切换 | 全量替换文案；英文更"专业"，对外汇报优先英文 |
| 配色 | 改 defs 里的 linearGradient stop 颜色 |

---

## 可复用 SVG 模板（Phase 计划图，5 周 3 阶段带重叠）

> 直接改文案、日期、X 坐标即可。这是最终定稿版（Zone Picking Phase II），结构完整、无遮挡。

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="530" viewBox="0 0 1024 530" font-family="'Segoe UI','Helvetica Neue',Arial,sans-serif">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f6f8fc"/><stop offset="1" stop-color="#eef2f9"/>
    </linearGradient>
    <linearGradient id="dev" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#2f6bed"/><stop offset="1" stop-color="#5b8ef7"/>
    </linearGradient>
    <linearGradient id="qa" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#8b3df0"/><stop offset="1" stop-color="#b06cf7"/>
    </linearGradient>
    <linearGradient id="bsa" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#0e9f8c"/><stop offset="1" stop-color="#19c2a6"/>
    </linearGradient>
    <filter id="sh" x="-20%" y="-30%" width="140%" height="160%">
      <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#1e293b" flood-opacity="0.16"/>
    </filter>
  </defs>

  <rect width="1024" height="530" fill="url(#bg)"/>

  <!-- Title -->
  <text x="40" y="52" font-size="30" font-weight="800" fill="#0f172a">Zone Picking <tspan fill="#2f6bed">Phase II</tspan></text>
  <text x="41" y="78" font-size="13.5" fill="#64748b">Delivery Plan · Kickoff 2026/10/16 · Dev 3w -> QA (early entry) -> BSA 1w · System ready = Go-Live on 11/19</text>
  <line x1="40" y1="92" x2="984" y2="92" stroke="#e2e8f0" stroke-width="1"/>

  <!-- month band -->
  <rect x="170" y="104" width="486" height="22" rx="5" fill="#dbe5fb"/>
  <text x="413" y="119" font-size="12.5" font-weight="700" fill="#3b63c4" text-anchor="middle" letter-spacing="1">OCT</text>
  <rect x="662" y="104" width="318" height="22" rx="5" fill="#fde7cf"/>
  <text x="821" y="119" font-size="12.5" font-weight="700" fill="#c87f2b" text-anchor="middle" letter-spacing="1">NOV</text>

  <!-- week cards (X0=170, Wk=162) -->
  <g>
    <rect x="170" y="132" width="154" height="44" rx="8" fill="#fff" stroke="#e5eaf2"/>
    <text x="247" y="151" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">W1</text>
    <text x="247" y="168" font-size="11" fill="#94a3b8" text-anchor="middle">Oct 16-22</text>
    <rect x="332" y="132" width="154" height="44" rx="8" fill="#fff" stroke="#e5eaf2"/>
    <text x="409" y="151" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">W2</text>
    <text x="409" y="168" font-size="11" fill="#94a3b8" text-anchor="middle">Oct 23-29</text>
    <rect x="494" y="132" width="154" height="44" rx="8" fill="#fff" stroke="#e5eaf2"/>
    <text x="571" y="151" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">W3</text>
    <text x="571" y="168" font-size="11" fill="#94a3b8" text-anchor="middle">Oct 30-Nov 5</text>
    <rect x="656" y="132" width="154" height="44" rx="8" fill="#fff" stroke="#e5eaf2"/>
    <text x="733" y="151" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">W4</text>
    <text x="733" y="168" font-size="11" fill="#94a3b8" text-anchor="middle">Nov 6-12</text>
    <rect x="818" y="132" width="154" height="44" rx="8" fill="#fff" stroke="#e5eaf2"/>
    <text x="895" y="151" font-size="13" font-weight="700" fill="#334155" text-anchor="middle">W5</text>
    <text x="895" y="168" font-size="11" fill="#94a3b8" text-anchor="middle">Nov 13-19</text>
  </g>

  <!-- lane labels -->
  <text x="40" y="214" font-size="14" font-weight="700" fill="#2f6bed">Development</text>
  <text x="40" y="276" font-size="14" font-weight="700" fill="#8b3df0">QA Testing</text>
  <text x="40" y="338" font-size="14" font-weight="700" fill="#0e9f8c">BSA On-site</text>

  <!-- Dev bar 10/16..11/05 = 170..648 -->
  <g filter="url(#sh)"><rect x="170" y="194" width="478" height="40" rx="12" fill="url(#dev)"/></g>
  <text x="196" y="212" font-size="13.5" font-weight="700" fill="#fff">Dev · 3w</text>
  <text x="196" y="228" font-size="10.5" fill="#dbe7ff">Oct 16 - Nov 5</text>
  <rect x="470" y="203" width="78" height="22" rx="11" fill="#fff" opacity="0.92"/>
  <text x="509" y="218" font-size="11.5" font-weight="600" fill="#2f6bed" text-anchor="middle">William</text>
  <rect x="556" y="203" width="56" height="22" rx="11" fill="#fff" opacity="0.92"/>
  <text x="584" y="218" font-size="11.5" font-weight="600" fill="#2f6bed" text-anchor="middle">Jun</text>

  <!-- QA bar 10/30..11/19 = 494..980 -->
  <g filter="url(#sh)"><rect x="494" y="256" width="486" height="40" rx="12" fill="url(#qa)"/></g>
  <text x="520" y="274" font-size="13.5" font-weight="700" fill="#fff">QA Testing (early entry)</text>
  <text x="520" y="290" font-size="10.5" fill="#f1e5ff">Oct 30 - Nov 19</text>
  <rect x="800" y="265" width="68" height="22" rx="11" fill="#fff" opacity="0.92"/>
  <text x="834" y="280" font-size="11.5" font-weight="600" fill="#8b3df0" text-anchor="middle">Nikki</text>
  <rect x="876" y="265" width="64" height="22" rx="11" fill="#fff" opacity="0.92"/>
  <text x="908" y="280" font-size="11.5" font-weight="600" fill="#8b3df0" text-anchor="middle">Luke</text>

  <!-- BSA bar 11/13..11/19 = 818..980 -->
  <g filter="url(#sh)"><rect x="818" y="318" width="162" height="40" rx="12" fill="url(#bsa)"/></g>
  <text x="836" y="336" font-size="13" font-weight="700" fill="#fff">BSA · 1w</text>
  <text x="836" y="351" font-size="10" fill="#d6fff6">Nov 13 - 19</text>
  <rect x="904" y="327" width="66" height="22" rx="11" fill="#fff" opacity="0.92"/>
  <text x="937" y="342" font-size="11.5" font-weight="600" fill="#0e9f8c" text-anchor="middle">Sophie</text>

  <!-- overlap boxes -->
  <rect x="494" y="188" width="154" height="114" rx="10" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="6 4"/>
  <text x="571" y="314" font-size="11" font-weight="700" fill="#d97706" text-anchor="middle">Overlap 1w</text>
  <rect x="818" y="250" width="162" height="114" rx="10" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="6 4"/>
  <text x="899" y="378" font-size="11" font-weight="700" fill="#d97706" text-anchor="middle">Overlap 1w</text>

  <!-- milestones -->
  <line x1="170" y1="430" x2="980" y2="430" stroke="#cbd5e1" stroke-width="1.5"/>
  <circle cx="170" cy="430" r="7" fill="#2f6bed"/>
  <text x="170" y="456" font-size="12.5" font-weight="700" fill="#1e293b" text-anchor="middle">Kickoff</text>
  <text x="170" y="472" font-size="11" fill="#64748b" text-anchor="middle">Oct 16</text>
  <circle cx="494" cy="430" r="7" fill="#8b3df0"/>
  <text x="494" y="456" font-size="12.5" font-weight="700" fill="#1e293b" text-anchor="middle">Handover to QA</text>
  <text x="494" y="472" font-size="11" fill="#64748b" text-anchor="middle">Oct 30</text>
  <path d="M980 419 l13 13 l-13 13 l-13 -13 z" fill="#dc2626"/>
  <text x="980" y="459" font-size="12.5" font-weight="800" fill="#dc2626" text-anchor="end">System Ready / Go-Live</text>
  <text x="980" y="474" font-size="11" font-weight="700" fill="#dc2626" text-anchor="end">Nov 19</text>

  <!-- legend -->
  <g font-size="12" fill="#475569">
    <rect x="40" y="500" width="15" height="11" rx="3" fill="url(#dev)"/><text x="61" y="510">Development</text>
    <rect x="150" y="500" width="15" height="11" rx="3" fill="url(#qa)"/><text x="171" y="510">QA Testing</text>
    <rect x="252" y="500" width="15" height="11" rx="3" fill="url(#bsa)"/><text x="273" y="510">BSA On-site</text>
    <rect x="356" y="500" width="15" height="11" rx="3" fill="none" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="4 3"/><text x="377" y="510">Overlap</text>
  </g>
</svg>
```

---

## 回顾全景图的额外约定（多分类泳道 + 节假日）

- 每条分类泳道一行，条形按该类工作实际进行的时间段铺开；人员胶囊统一放条形**右侧外部**，避免压字。
- **节假日带**：底层淡背景竖带（如中秋 3 天、国庆 7 天），opacity ≤0.5，斜纹叠加 ≤0.32，画在条形**下层**。能直观体现工作被假期切断。
- 调查/排查类被假期打断的，拆成两段条（如"节前 3 天 + 节后 4 天"），中间虚线跨过假期带连起来。
- 右端用红虚线标"今天 X/XX"，并可画一个衔接节点指向下一阶段（如"Phase II 启动"）。
- 日期一律 shell 校验，节假日天数问清楚（中国法定：国庆 10/1–10/7 共 7 天；中秋通常 3 天）。

---

## 常见错误（必须避免）
1. 半透明节假日/斜纹层盖住甘特条文字 → 分层，文字置顶
2. 人员胶囊压住条内阶段名 → 靠右端或移到条外
3. 心算日期星期/周边界出错 → 一律 shell 算
4. text 元素误用 cy 属性 → 无效，text 用 x/y
5. 画布太挤不留白 → 内容多就加大画布（优先加宽到 1400）
6. 不先出排期表就直接画 → 改图成本高，先表后图
7. 对外汇报用中文混排不够专业 → 优先全英文
