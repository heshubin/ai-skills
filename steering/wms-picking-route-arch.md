---
inclusion: auto
name: wms-picking-route-arch
description: 当需要修改/分析 WMS 拣货路线（batch 拣货库位排序、过道蛇形顺序、双边拣货分组、002/NJ 仓三号路线 partThree、LA/ON 仓路线）时使用。触发词：拣货路线, 拣货顺序, 蛇形, 过道, 双边拣货, BinSortingHandler, PickGroupEnum, PickSeqEnum, partThree, pathPlan, 库位排序, bin_sn 排序
---

# WMS 拣货路线架构（wms-cloud-service）

> 下次说"改拣货路线/调整过道/加货架到拣货顺序"直接按本文件动手，不需要再介绍背景。
> 代码仓库：`d:\code\wms-cloud-service`

## 1. 三个核心文件（改路线只碰这三个 + 测试）

| 文件 | 作用 |
|------|------|
| `wms-cloud-service/.../service/batch/handler/BinSortingHandler.java` | 排序入口 `sortBin` + 各仓分区正则 + `dealBinSeq`（分组内升降序）+ `njResort` |
| `wms-cloud-service/.../service/batch/enums/PickGroupEnum.java` | **过道分组**：相邻两排货架面对面＝一条过道（双边拣货），用正则数组登记 |
| `wms-cloud-service/.../service/batch/enums/PickSeqEnum.java` | **每条过道升/降序**：登记在 `binStrs` 的货架走降序，未登记走升序 |
| `wms-cloud-service/src/test/java/.../BinSortingNjPathThreeTest.groovy` | 002 PATH_THREE partThree 回归测试（锁过道顺序 + 方向交替） |

## 2. 入口与仓库分流

`BinSortingHandler.sortBin(wh, orderItems, isYml)`：
- `wh=002`(NJ) → `binSorting4NJ`
- `wh=101`(ON) → `binSorting4ON`
- LA → `binSorting4LAV2`（开关 `laPickRouteV2` 开）/ 否则 `binSorting4LANew`

**各仓完全独立**：改某仓路线不影响其它仓。LA/ON 走自己的 `PickGroupEnum`(`LA_GROUP_*`/`ON_GROUP`) 和 `PickSeqEnum`(`DESC_LA*`/`DESC_ON`)。

## 3. 库位编号(bin_sn)格式

统一 6 位：**货架2位 + bay2位 + 层1位 + 列1位**
例：`U10611` = 货架 `U1` + bay `06` + 层 `1` + 列 `1`；`P30429` = `P3`+`04`+`2`+`9`。
排序里"货架前两位"= `bin_sn.substring(0,2)`，bay = `substring(2,4)`。

## 4. NJ(002) 拣货路线：三条 pathPlan

Apollo/配置 `wms:nj:pathPlan`（`Constant.NJ_PICK_PATH_PLANE`）取值：
`NJ_PICK_PATH_ONE` / `NJ_PICK_PATH_TWO` / `NJ_PICK_PATH_THREE`。
**002 仓现网实际走 `NJ_PICK_PATH_THREE`。**

PATH_THREE 分三区（`binSorting4NJ` 的 switch 里按正则把库位分到三个 list）：

| 分区 | 正则 | 升降序配置 | njResort |
|------|------|-----------|----------|
| partOne | `PLANE_THREE_PART_ONE` = `[ABCDEFGHIJK]\d(1[3-9]|2[0-9]|30)\d\d[A-Za-z]?`（A~K 行 bay13-30） | `DESC_NJ_THREE_PART1` | true |
| **partThree** | `PLANE_THREE_PART_3`（P/Q/R/S/T/U/X/Y 独立蛇形通道区） | `DESC_NJ_THREE_PART3` | **false** |
| partTwo | 其余兜底 | `DESC_NJ_THREE_PART2` | true |

## 5. 核心机制（改之前必须理解）

### 5.1 双边拣货 = 过道分组（PickGroupEnum）
相邻两排货架面对面构成一条过道，拣货员一次走一条过道两侧都拣。用正则把两排归一组：
- 同字母相邻：`"P[12]"`（P1、P2）、`"X[34]"`
- **跨字母面对面**：`"(T3|T4)"`、`"(U3|X2)"`、`"(Z1|Z2)"` —— 物理上面对面但货架字母不同，跨字母配一组
- `"Y[12]"` 常是末端过道（End 出口）

### 5.2 归一化 key（最容易踩坑的点）
`dealBinSeq` 给每条过道算一个 key = **组内字母序最小的货架编号**。
→ 判断该过道升/降序时，用这个 key 去 `DESC_NJ_THREE_PART3` 查。
→ **所以降序过道的两侧货架都要在 `DESC_NJ_THREE_PART3` 里成对登记**：若某 batch 只命中过道的一侧（另一侧无商品），key 会落到实际命中的那一侧，两侧都登记才能稳定命中降序。这就是 B/C/D 老分区也成对登记的原因。

### 5.3 升/降序 + 蛇形交替
- `DESC_NJ_THREE_PART3.binStrs` 里登记的货架 → 该过道 bay 走**降序**(29→06)；未登记 → **升序**(06→29)。
- 过道访问顺序 = 分组 key 的**字母正序**（partThree 不走 njResort）。
- **相邻过道方向必须严格交替**（升降升降…蛇形）。连续两条同向＝操作员要空跑一整条过道，是 bug。

### 5.4 njResort —— partThree 必须禁用
`njResort` 是给 NJ 主仓区（B~K 行 + X/Y/Z 高架区混排）设计的，会把 X 及之后的分组前置。
partThree 自成一条连续蛇形（P→Q→R→S→T→U→X→Y），分组 key 字母正序本身就是拣货顺序。
→ partThree 调用 `dealBinSeq(..., needNjResort=false)`，否则 X/Y 过道会被甩到 P 前面打乱整条路线。
（`dealBinSeq` 有 4 参和 5 参两个重载，4 参默认 `needNjResort=true`，只有 partThree 传 false。）

### 5.5 正则用精确货架位排除 Tote
`T0/T5/T6` 是 Batch Picking Tote（`location_type=6`），编号格式和拣货库位**完全一样**，只能靠货架位区分。
→ partThree 正则用精确枚举 `T[1-4]`、`U[1-3]`、`X[2-8]`、`Y[12]`，**不要**用 `[TUXY]\d`。
→ `Z1~Z4` 是 YML 专区，不进 partThree，走 partTwo。

## 6. 改拣货路线的标准步骤（partThree 为例）

1. **`BinSortingHandler.PLANE_THREE_PART_3`**：决定哪些货架进 partThree 蛇形区（新增一排货架先在这里放行）。
2. **`PickGroupEnum.NJ_GROUP`**（partThree 段）：按"相邻两排一条过道"配对。注意数组顺序——分组按数组顺序**首个命中即返回**，跨字母配对（如 `(U3|X2)`）要排在该字母的其它分组（如 `X[34]`）**之前**，否则 X2 会被 `X[34]` 之类抢先匹配。
3. **`PickSeqEnum.DESC_NJ_THREE_PART3`**：登记降序过道，**两侧货架成对登记**。
4. **`BinSortingNjPathThreeTest.groovy`**：更新 `AISLE_KEYS_IN_ROUTE_ORDER`（过道顺序）+ 方向交替断言 + 新配对/单侧命中用例。
5. **自检**：把全部过道方向排一遍，确认"首条升序、之后严格交替"，无连续同向断点。

## 7. 历史改动（真实案例，帮助理解演进）

- **2026-09 ZP-0909**：partThree 从只覆盖 P/Q/R/S 扩成 20 条过道蛇形，纳入 T/X/Y；P/Q 区方向整体翻转以适配新布局。
- **2026-10 OP-39609**：T/X 间新增 T4/U1/U2/U3；原 `(T3|X2)` 一条过道拆成三条：`(T3|T4)` 降序、`(U1|U2)` 升序、`(U3|X2)` 降序（X2 从与 T3 配对改为与 U3 配对）；过道 20→22 条。
  - 对应登记：`DESC_NJ_THREE_PART3` 中登记 T3/T4、U3/X2（降序）；U1/U2 不登记（升序）。

## 8. 三仓共性心智模型（LA/ON 同样适用）

不管哪个仓，拣货排序都是同一套套路，理解这套就能快速看懂任意仓：

1. **先切区**：用正则把一个 batch 的库位切成几个"区"（partOne/partTwo…或 upper/lower/az/v…）。**区的拼接顺序 = 拣货大方向**（先拣哪个区后拣哪个区）。
2. **区内分组+升降序**：每个区丢给 `dealBinSeq` → 用 `PickGroupEnum` 做"相邻两排一条过道"的双边分组 → 用 `PickSeqEnum` 决定每条过道升序还是降序 → 过道按归一化 key 字母序访问。
3. **特殊区单独处理**：高价值区(V)、独立区(G1)、Roller 通道等往往不走 `dealBinSeq`，直接按 bay 正/倒序排好塞进结果（通常排在最前或最后）。

两个关键重载要分清：
- `dealBinSeq(list, isShelfDesc, wh, PickSeqEnum)` —— **4 参**，分组枚举靠"遍历 `PickGroupEnum.values()` 取第一个 warehouse 匹配的"自动选。NJ 和 LA 旧版用它。
- `dealBinSeq(list, isShelfDesc, wh, PickSeqEnum, PickGroupEnum)` —— **5 参(带 PickGroupEnum)**，**显式指定**用哪套分组。LA V2、ON 用它（因为同一个仓有多套 group）。
- 另有 NJ 专用的 `dealBinSeq(..., needNjResort)` —— 5 参(带 boolean)，只为 partThree 关 njResort，别和上面那个 5 参搞混。

`isShelfDesc`：控制**货架前两位**的排列方向（区内货架 A→G 还是 G→A）；`PickSeqEnum.binStrs`：控制**每条过道 bay** 的升/降序。两者独立。

> 一个仓可以有多套 `PickGroupEnum`/`PickSeqEnum`（如 LA 有 `LA_GROUP_NEW`/`LA_GROUP_NEW_2`/`LA_GROUP_YML_V2`），靠显式传参或声明顺序选中——改 LA 时务必确认改的是当前生效的那一套。

### ⚠️ 8.1 改之前必须先查 DB/配置确认"当前实际走哪一套"，不要凭代码猜

代码里有开关/多版本分支（如 `laPickRouteV2`、NJ 的 `pathPlan`、LA 的新旧版），**但某个仓当前只会走配置指定的那一套，其余分支对这个仓就是不生效的历史代码**。

- **禁止**：看到 `if (laPickRouteV2) {...V2...} else {...旧版...}` 就以为两条路径都要改、或默认走某一条。
- **必须**：动手前先查 DB/配置中心，拿到该仓当前实际取值，锁定唯一生效的那套 `binSorting4XXX` + `PickGroupEnum` + `PickSeqEnum`，只改它。改了不生效的分支＝白改，还可能误导。
- 典型配置来源：
  - NJ 路线：`wh_config` 的 `wms:nj:pathPlan`（`Constant.NJ_PICK_PATH_PLANE`），002 当前 = `NJ_PICK_PATH_THREE`。
  - LA 版本：`laPickRouteV2`（`@WMSConfig`，Apollo），决定走 V2 还是旧版 `binSorting4LANew`。
  - 任何 `@WMSConfig` 开关都以**线上配置实际值**为准，不以代码默认值为准。
- 查到后在动手前先跟我确认一句"当前走的是 X 套"，避免改错分支。

## 9. LA 仓拣货路线

LA 有**新旧两版**，开关 `laPickRouteV2`（`@WMSConfig`）：
- `laPickRouteV2=false` → `binSorting4LANew`（旧版，用 `LA_GROUP_NEW` + `DESC_LA_NEW`）
- `laPickRouteV2=true` → `binSorting4LAV2`（V2，再按 isYml 分 `binSorting4LAV2Normal` / `binSorting4LAV2Yml`，用 `LA_GROUP_NEW_2`/`LA_GROUP_YML_V2` + `DESC_LA_NEW_2`/`DESC_LA_YML_V2`）

### 9.1 binSorting4LANew（旧版，5 区）
按正则切区，区顺序即拣货顺序：
| 区 | 正则字段 | 方向 |
|----|---------|------|
| 第一区 上半 | `partFour` = `(C[2-6](0[4-9]|1[0-2])|[D-G]\d(0[0-9]|1[0-2]|0[A-Z]))\d\d[A-Z]?` | 货架正序 |
| 第二区 下半 | `partSix` = `([A-G]\d(1[3-9]|2[0-5]))\d\d[A-Z]?` | 货架倒序(isShelfDesc=true) |
| 第三区 右上 | `partEight` = `(A[Z0-6]|B[1-6]|C1)(0[4-9]|1[0-2])\d{2}[A-Z]?` | 货架正序 |
| 高价值区 | `partFive` = `V\d{5}[A-Z]?` | 单独 |
| 兜底 | 都不匹配 | 原样塞末尾 |
isYml 时额外有 `ymlAppendZoneOne/Two/Three`（U1/W/X/Y 补充区），最后 `ymlAfterSortDeal` 把 AZ/A0-A3 的 bay06-12 提到最前。

### 9.2 binSorting4LAV2Normal（V2 自营，5 区 + Roller）
区顺序：**上半(bay00-12,正序A→G,含Roller) → 下半(bay14-26,倒序G→A) → AZ区(bay降序) → HJ区 → V区(high value,最后)**，再兜底。
- 分区正则：`LA_V2_UPPER` / `LA_V2_LOWER` / `AZ开头` / `LA_V2_HJ`(H1-H8/J1 bay06-08) / `LA_V2_V`(V1 bay01-12)。匹配时 **V/HJ/AZ 要先于 UPPER/LOWER**，避免被宽正则误捕获。
- **Roller 特殊库位**：5 条跨货架通道 `(C6|C5)/(C4|C3)/(C2|C1)/(A6|A5)/(A4|A3)`，面对面但靠 **bin_sn 第6位列号**区分朝向（2=朝通道一侧，1=另一侧，见 `LA_V2_ROLLER_*`）。先于分区提取，再用 `dealBinSeqWithRoller` 倒序后插到指定分组之后（C4C3/C6C5 插在 `C[23]` 后，C2C1 插在 `B[45]` 后，A4A3/A6A5 插在 `A[23]` 后）。上半区为空也要用 `appendRollerBinsIfNotEmpty` 兜底不丢。

### 9.3 binSorting4LAV2Yml（V2 YML，3 段）
`AZ-A3(bay03-26) → U1区(倒序) → (G4/G5双边bay倒序 + X区bay升序)`，用 `LA_GROUP_YML_V2` + `DESC_LA_YML_V2`；G4/G5 不走 dealBinSeq，直接 `sortRollerBinsDesc` 倒序。

## 10. ON 仓（101）拣货路线

`binSorting4ON`，**4 区**，区顺序即拣货方向：
`下半区(bay25~99) → G1区 → 上半区(bay08~23) → V区`
- 下半区：`dealBinSeq(..., isShelfDesc=false, DESC_ON, ON_GROUP)` —— bay 升序方向，双边拣货
- 上半区：`dealBinSeq(..., isShelfDesc=true, DESC_ON, ON_GROUP)` —— bay 倒序方向，双边拣货（和下半区形成蛇形回转）
- **G1 区**：独立，直接 `bin_sn` 倒序，不走 dealBinSeq
- **V 区**：`V\d{5}`，直接 `bin_sn` 升序，排最后拣
- 分组 `ON_GROUP`：`(C2|C3)(C4|C5)…(F6|F7)` 双边配对 + `F8`、`G1` 单独；`DESC_ON` 登记降序的双边组（取组内字母序小的一侧生效）。
- bay 用 `bin_sn.substring(2,4)` 判断上/下半区，未匹配的塞上半区末尾。

## 11. 快速排查

- **第一步永远是查 DB/配置确认当前生效的那一套**（见 8.1）：NJ 看 `wh_config.wms:nj:pathPlan`（002 = `NJ_PICK_PATH_THREE`）、LA 看 `laPickRouteV2`。不生效的分支不要改。
- 方向错/路线乱：先看 `PickGroupEnum` 分组是否对（过道配对），再看 `DESC_NJ_THREE_PART3` 降序登记是否两侧成对，最后确认 partThree 没误开 njResort。
- 某货架没进蛇形区：检查 `PLANE_THREE_PART_3` 正则是否放行该货架前缀。
- 新增货架方向与蛇形反向：按"相邻两排一条过道 + 逐条交替"补登记，使配置自洽。
