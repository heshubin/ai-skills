---
inclusion: auto
name: zone-picking-hub
description: WMS Zone Picking（分区拣货）二期开发的知识导航与一期踩坑清单。开始二期需求、写 spec、改跨 Zone 拣货/合并/转运/OOS 代码、补测试、UAT 联调时使用。触发词：zone picking, Zone Picking, 二期, 分区拣货, 跨 Zone, Zone1, Zone2, Main_Zone, Secondary_Zone, 合并, consolidation, 格口, tote, cart, Zone_Task, OP-37299
---
# Zone Picking 二期 · 知识导航

一期（OP-37299）功能已上线 002 仓。本文件只做导航和踩坑提炼，细节以下面列出的原文为准。路径均为绝对路径；全局经验库挂载后 `D:\code\kiro-knowledge\steering|skills` 即 `~/.kiro/steering|skills`。

## 一、一期交接文档与权威源

| 文件 | 何时看 |
|---|---|
| `d:\code\kiroWP\docs\active\OP-37299-zone-picking\HANDOFF.md` | 二期开工第一份必读：红线、高危耦合点（§12.3）、UAT 初始化状态（§13）、代码路径索引（§15.5） |
| `d:\code\kiroWP\docs\active\OP-37299-zone-picking\REMAINING-TEST-WORK.md` | 一期遗留测试债作业单；也是各 Service 依赖字段全集、接口签名、文案常量、枚举位置的速查表 |
| `d:\code\kiroWP\.kiro\specs\zone-picking\requirements.md` | 查验收标准 AC x.y、约束 1–32 时定点 grep，禁止通读（116KB） |
| `d:\code\kiroWP\.kiro\specs\zone-picking\design.md` | 查裁决 D1–D30、Correctness Property 时定点 grep；二期（OP-40026）新裁决从 D31 编号（D29、D30 已被一期占用） |
| `d:\code\kiroWP\docs\active\OP-40026-zone-picking-phase2\` | 二期 PRD V2.3 快照（`PRD-V2.3-snapshot.md`）、附件与原型素材汇总（`PRD-materials-digest.md`：流程图、Label、WMS/Central 原型走查、优先级公式原文、版本演变）、一期基线与差距分析（`phase1-baseline-and-gap-analysis.md`） |
| `d:\code\kiroWP\.kiro\specs\zone-picking\tasks.md` | 查某任务的落地记录与「改造裁决」标注；只允许勾复选框或按 HANDOFF §12 追加变更记录 |
| `d:\code\zone-picking-material\zone-picking\readme.md` | 需求方原始业务说明（二期需求对照用） |
| `d:\code\zone-picking-material\zone-picking\sql\zone-picking-ddl-v3-full.sql` | 查 Zone 相关表结构最快；Part 3 有三处已知坑（见踩坑 #12） |
| `d:\code\wms-cloud-service\docs\20260814_zone_picking_*_ddl.sql`（3 个） | 一期增量 DDL，UAT/上线前执行顺序见 HANDOFF §13.2 |

## 二、相关 steering（D:\code\kiro-knowledge\steering\）

| 文件 | 加载方式 | 何时看 |
|---|---|---|
| `zone-picking-code-rules.md` | fileMatch（wms/packing 的 Java、Mapper XML） | 动任何 Zone Picking 链路代码：约束 26 开关短路、Cart/Tote 模型口径 |
| `wms-zone-oos-arch.md` | auto | Zone 预建 status=0 任务与 OOS 交互、Scan Tote 报 Allocated Qty Less Than |
| `wms-pw-sorting-arch.md` | auto | PW Sorting / Putwall 初始化跨 Zone 商品不全（Bug#10360） |
| `picking-app-arch.md` | auto | 给 Picking App 加后端接口、遇到 90008 / Token is Invalid |
| `query-side-filter-principles.md` | auto | 合并完成后 tote 被复用查出多单、想改 tote_no 等历史字段之前 |
| `test-maintenance-rules.md` | fileMatch（Groovy 测试） | 改 Spock 测试、签名变更后 mock 批量同步 |
| `sonar_coverage_rule.md` | auto | 补单测、PR 前 Sonar 新代码覆盖率 ≥80% |
| `code-evolution-analysis.md` | auto | 新流程改变共用方法/老校验的前置状态（含 Zone Picking 案例） |
| `cross-module-flow-analysis.md` | auto | 前后端联调、同一入口多模式分支（Batch/PW/单 Tote）变量命名 |
| `bug_pattern_registry.md` | auto | 动预占、拣货扣减、OOS 取消预占、批次日志前自查 |
| `wms_inventory_sync_rule.md` | auto | 拣货/预占涉及两套库存表同步时 |
| `wms-picking-route-arch.md` | auto | 改拣货路线、库位排序 |
| `wms_coding_pitfalls.md`、`wms_project_conventions.md` | fileMatch（wms-cloud-service 等） | WMS 编码坑与跨服务同名类同步 |
| `java_dev_env.md` | fileMatch | Maven/JDK 路径、GQC 启动参数 |
| `android-app-testing.md` | auto | WMS App / Picking App 打包、Metro、logcat、真机联调 |
| `server_forbidden_rules.md` + `server_coding_examples.md` | always + fileMatch | N+1 批量模板、魔法数字、toMap merge function |

仓库自带规则（Kiro 中工作区规则优先于全局）：`d:\code\wms-cloud-service\.kiro\steering\`（java-code-quality：方法 ≤80 行、UPDATE 必带任务级约束；spring-mvc-interface-rules；test-location-rules）、`d:\code\WMS-front-end\.kiro\steering\`（禁用 Alert、BroadcastScanner、文案原样）。

## 三、相关 skill

| skill | 何时用 |
|---|---|
| `D:\code\kiro-knowledge\skills\wms-database-guide\` | 查 wh_picking_task / wh_picking_order / wh_order_pool 等表关系与枚举 |
| `D:\code\kiro-knowledge\skills\wms-spec-review-checklist\` | 二期写完 requirements/design/tasks 后做设计审查 |
| `D:\code\kiro-knowledge\skills\wms-batch-priority-guide\` | 改 Batch / Zone / Group 优先级、选批排序、Central 提权之前 |
| `D:\code\kiro-knowledge\skills\systematic-flow-analysis\` | 二期在一期流程中插新步骤前做兼容性分析 |
| `D:\code\kiro-knowledge\skills\defensive-code-review\` | 一期老校验与二期需求冲突，判断改还是删 |
| `D:\code\kiro-knowledge\skills\wms-inventory-transfer-guide\` | 拣货完成走 adjustLocation 链路时 |
| `D:\code\kiro-knowledge\skills\react-native-dev-guide\` | 改 WMS App consolidation 页面或 Picking App |
| `D:\code\kiro-knowledge\skills\wms-app-login\`、`android-screenshot\`、`adb-screen-recorder\` | 真机自动登录、截图、录屏验证 |
| yami-skills：`wirte-java-unit-test`、`sql-query`、`query-kibana-logs`、`api-test` | Spock 单测生成、查 UAT 数据、查日志、接口验证（`yami-ai-cli read <name>`） |

## 四、一期关键踩坑清单

**业务红线**
1. **约束 26 兼容性红线**：Zone Picking 只上 002 仓，001/101 行为必须与上线前一致。所有 Zone 逻辑放在 `ZonePickingSwitchGuard.isDisabled(zoneConfigService, wh)` 短路之后；测试构造 001 仓场景时断言「零 DB 访问、零写操作」。
2. **代码与 spec 冲突不自行选边**：把「Dxx 说 A，代码是 B」摆给用户裁决。用户要求改实现时走 HANDOFF §12 五步流程，最后一步必须同步 spec（tasks 加变更记录、design 追加 D31+），否则后续会话会把改动「修」回去。
3. **禁止为了让测试变绿回退实现**：一期剩余失败几乎都是断言过时，先读 tasks.md 对应任务确认新口径再改测试。

**高危耦合点（改之前把牵连位置全看一遍，详见 HANDOFF §12.3）**
4. Cart 释放唯一入口 `CartReleaseService.releaseIfEmpty`，唯一触发点是打包完成钩子；上车链路恒不释放 Cart。
5. Slot 释放 `SlotReleaseService.releaseIfNoCart` 只有两个触发点（Cart 上车、合并完成）；OOS 与 Batch 解散禁止调用；换绑后的原格口释放必须在事务提交后调用。
6. `bindZoneCartToSlot` 被 `handleCrossZonePickingFinish` 三个分支共用，主从差异只在入口内按 `is_primary` 区分；只有 Main_Zone 侧同步主表快照和推进就绪。
7. 格口校验两层 vs 三层：三层（含 Zone 归属）只用于 `pickingTaskFinish` 带 Slot 与 `bindZoneCartToSlot`；`confirmToteArrival`、`changeConsolidationSlot`、`scanSlot` 用两层，给它们加 Zone 判据会线上误拒。
8. 判定口径一律取 `wh_consolidation_task_detail`；主表 `primary_cart_no`/`consolidation_no` 只是 Main_Zone 侧冗余快照。

**数据与 SQL**
9. **历史数据不动，查询侧过滤**：`wh_picking_order.tote_no` 记录真实使用过的 tote，合并完成后 tote 被复用导致「reference to multiple orders」时，在 SQL 加 `NOT EXISTS`（`is_primary=0` 且 `ct.status=80`）排除，不要改字段（改成 Zone1 tote 会让 Cart 永不释放）。逐个 tote 合并时警惕中间状态污染下一次判断。
10. **多服务同名逻辑要一起改**：`queryPackingInfoList` 在 wms-cloud-service 与 central-packing-service 各有一份，修一处立即 grep 另一处。
11. UPDATE 明细必须带 `picking_task_id` 等任务级约束，只按 `cart_no` 更新会在 Cart 复用时误更历史任务（Bug#10279）。
12. UAT 初始化（2026-10-28 实查已更新）：一期增量 DDL 已执行，`location_type=51` 已有 40 个格口 `Z1CS001~020`、`Z2CS001~020`（格口编码正则 `^Z(\d+)CS(\d+)$`，DDL 注释里的 `CON` 前缀已过时），HANDOFF §13「半初始化」描述过时。全量脚本 Part 3 有三处坑：`wh_zone_config` 写的是 001（应为 002，漏改会导致全部库位被判无 Zone 而拒绝拆分）、`wh_location_type` 用 `INSERT INTO` 非 `INSERT IGNORE`、库名 `Yamibuy_WH` 与 `yamibuy_wh` 大小写不一致。DDL/数据初始化按发布流程走，模型不代执行。
13. 跨 Zone sorting 不要循环逐 task 查明细（Bug#10360 N+1），用批量 `queryOrderItemByTaskIds`。

**OOS / 库存**
14. OOS 清理 Consolidation 任务有领取状态门控（任务 15.1），两侧均未领取才清理；已领取场景零写操作。
15. 取消预占调用 `prepareBatchRelease` 时 quantity 必须为正数（BUG-016）；拣货扣减的 lot 必须从预占日志反推，与预占一致（BUG-037）；批次影子表操作用 `REQUIRES_NEW`（BUG-035）。
16. `resultType="map"` 的数字字段禁止 `(Integer)` 硬强转，用 `((Number) v).intValue()`（BUG-045）。

**测试与工具**
17. 改方法签名后，测试里所有 mock 都要同步：setup()、given:、then:、辅助方法，全 wildcard 与带具体值两种形式都要改；多个测试文件可能 mock 同名方法。
18. Spock `then:` 里的 `1 * mock.method(...)` 会覆盖 setup() 的委托，导致间接调用 0 invocations；需要委托逻辑时在 given: 单独 stub，then: 只验结果。
19. 实现口径变了（如 `resolveToteNoForArrival` 改为直接返回 Cart 编号），更新期望值并加注释说明新行为。
20. 禁止用 PowerShell Get-Content/Set-Content/-replace 改含中文的文件（一期 ConsolidationServiceImplTest、Zone2PrintServiceImplTest 被改成乱码，CI 连挂两次）；用 str_replace/fs_write，改后 read_file 抽查中文，并对比 `git diff --stat` 与 `--ignore-cr-at-eol --stat`。
21. `str_replace` 可能返回成功但没写入（BUG-006），改完要重新读文件或 grep 验证。
22. Groovy joint compilation 下 `mvn compile` 会放过未 import 的类型（一期 `ProcessLogService.queryOrderZoneDetail` 运行时 `NoClassDefFoundError`）；改 Java 后额外跑 `get_diagnostics`。`grep_search` 在多工作区会漏命中，改公共方法签名后必须全量编译。
23. Maven 用绝对路径、`-pl wms-cloud-service -am` 的 `-am` 不能省、不要 `mvn clean`、PowerShell 中 `-D` 参数用单引号包裹（命令见 HANDOFF §5）。
24. 测试目录：一期旧测试散落在 `src/test/java` 与 `src/test/groovy` 两处，定位时两处都搜；二期新增测试按 wms-cloud-service 的 test-location-rules 只放 `src/test/java`。
25. `WarehouseValueConfigTest` 的 9 个 error 是 JDK 反射限制，master 同样失败，不计入目标，不要修。

**接口与前端**
26. Picking App 接口必须加 `@VestaIgnore`；路由只写在 Interface，Impl 只 `@Override`，否则路径前缀叠加成 `/orderPick/orderPick/...`，表现为 90008 Token is Invalid（一期 `bindZoneCartToSlot` 真实案例）。
27. 分支：WMS-front-end 用 `<OP号>-RN`，从 `RN-Refactor` 拉；其余仓库用 `<OP号>`，从 master 最新代码拉（一期 `OP-37299-RN` / `OP-37299`，二期 `OP-40026-RN` / `OP-40026`）；commit 前缀 `[OP-XXXXX]type:` 中间无空格。
28. RN 端禁用 `Alert`（用 ConfirmDialog/MessageService），`BroadcastScanner` 的 `isActive` 绑定 `useIsFocused()`，文案与旧系统逐字一致。

**二期新增（OP-40026）**
29. 优先级不要只看 Sheet 的「梯度×100 + x/y×100」：那只是自动层（几百）。生产 002 仓几百万到上千万的值是 Central「↑」按 `1,000,000 + 全仓 status=1 最大值` 逐级叠出来的，每周 13%–33% 的 Batch 被 ↑。新加权不能直接加在 `batch_priority` 上（`+100000` 对 ↑ 过的 Batch 无效）。改优先级前先读 skill `wms-batch-priority-guide` 和 `docs/active/OP-40026-zone-picking-phase2/priority-analysis.md`。
30. 格口一格多车：Consolidation Slot（`location_type=51`，`Z1CS/Z2CS`）与 Parking Slot（`wh_parking_slot`，`PRK*`/`Z1PS*`）都允许多台车同时停放，车与格口关系在 `wh_picking_cart.parking_slot` + `park_type`（2=Consolidation，1=Parking）。实查 `Z2CS006` 停 10 台、`Z1CS004` 停 68 台。
31. 无 Tote 的车库存在车上：PW 车（`wh_picking_order` 无 tote_no，库存在与车同号的 `location_type=33` PW 框）与全 2-Day / HI、AK 的单 Zone Zone 2 Batch 车（Bug#10363）都不绑 Tote，一期以 Cart 号作 Tote 占位（`toteNo==cartNo`，`TruckManagementServiceImpl` 约 703–724 行）直上卡车，PW 合单以 Zone 2 PW 车为转出库位。凡是「上车释放车」「按 Tote 上托盘」「按 Tote 识别上车记录」的设计都要单独处理这类车，否则订单卡死或库存挂在空闲车上（OP-40026 审查 H1）。
32. PW 车号 = PW 框号：`OrderPickService.bindToteForCartNo` 用车号查 `location_type=33` 的框（查不到报 `this tote not exists`），所以 PRD 里 Putwall 车 `Z2PW…` 与 PW Tote `Z2PW…` 同号是设计如此，不是扫码冲突；初始化新 PW 车时必须同时建同号的 33 类库位。`wh_batch_zone.status` 只有 0 待拉取 / 1 已拉取，没有完成态。

