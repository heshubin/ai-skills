---
name: wms-database-guide
description: 查询或分析 yamibuy_wh 仓储库（订单、库存、拣货、打包、出入库）时使用，含核心表关系、枚举和关联 SQL。触发词：订单查询, wh_order, 库存, 入库, 出库, 拣货, 打包, 预占, 仓库数据, wms数据库, yamibuy_wh, wh_picking_task, 订单状态
---
# WMS 仓储数据库查询指南

## 触发词
订单查询, wh_order, 库存, 入库, 出库, 拣货, 打包, 预占, 仓库数据, wms数据库, yamibuy_wh, order_info, order_goods, picking, packing, inbound, outbound, inventory, 订单状态, 物流, tracking

## 数据库信息
- 数据库: `yamibuy_wh`（yamibuy_master 中的 WMS 仓储库）
- 连接: g3 只读 Slave 库
- 服务代码: `wms-cloud-service`
- 仓库编号: `001`（仓库1）、`002`（仓库2）

---

## 核心表关系图

```
订单生命周期:
  wh_order_info (订单主表)
    ├── wh_order_goods (订单商品明细)
    ├── wh_order_pool (订单池/调度)
    ├── wh_order_process_record (订单流转时间记录)
    ├── wh_preoccupancy_info (预占信息)
    │
    ├── wh_batch → wh_batch_order (批次)
    ├── wh_picking_order → wh_picking_task (拣货)
    ├── wh_picking_order_item (拣货商品明细)
    │
    ├── wh_packing_order_info (打包订单)
    ├── wh_packing_order_goods (打包商品)
    ├── wh_packing_ship_record (运输记录)
    │
    └── wh_outbound → wh_outbound_transaction (出库)

库存体系:
  wh_inventory_master (库存主表)
    ├── wh_inventory_transaction (库存事务)
    ├── wh_inventory_transaction_log (库位转移日志)
    ├── wh_storage_location (库位表)
    ├── wh_storage_location_item (库位商品映射)
    └── wh_sellable_inventory_log (可售库存变化日志)

入库体系:
  wh_inbound (入库单)
    ├── wh_inbound_batch (入库批次)
    ├── wh_inbound_transaction (入库事务)
    ├── wh_pre_receive (预收货)
    └── wh_seller_shipment (发货单)
```

---

## 一、订单表 (wh_order_info)

### 表说明
订单主表，存储从 EC 系统同步过来的订单信息。通过 `order_id` 关联所有下游表。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| rec_id | bigint | 自增主键 |
| order_id | bigint | 订单ID（核心关联键） |
| order_sn | varchar(20) | 订单编号（用户可见） |
| user_id | bigint | 用户ID |
| order_status | tinyint | 订单状态 |
| shipping_status | tinyint | 物流状态 |
| pay_status | tinyint | 支付状态 |
| order_type | tinyint | 订单类型 |
| source_flag | int | 订单来源 |
| from_ad | smallint | 广告来源 |
| abnormal | smallint | 异常标记 |
| hold_status | tinyint | 拦截状态 |
| warehouse_number | varchar(20) | 仓库编号 |
| shipping_id | int | 运输方式ID |
| goods_amount | decimal | 商品金额 |
| shipping_fee | decimal | 运费 |
| order_amount | decimal | 订单总金额 |
| add_time | int | 下单时间（时间戳秒） |
| pay_time | int | 支付时间 |
| shipping_time | int | 发货时间 |
| tracking_number | varchar(600) | 物流单号 |
| in_dtm | int | 入仓时间 |

### 枚举值

#### 订单状态组合（order_status + shipping_status + pay_status 三字段联合判断）

| order_status | shipping_status | pay_status | 业务含义 |
|:---:|:---:|:---:|------|
| 1 | 0 | 0 | 已下单未支付 |
| 1 | 0 | 1 | 已支付未验证 |
| 1 | 0 | 2 | 已支付已验证未入库 |
| 1 | 2 | 2 | 已支付已预占 |
| 1 | 3 | 2 | 已支付拣货中 |
| 1 | 5 | 2 | 已支付已拣货未发货 |
| 1 | 7 | 2 | 商家已确认可自提 |
| 5 | 1 | 2 | 已发货（正常完成） |
| 4 | 8 | 4 | 部分退款 |
| 4 | 8 | 3 | 全部退款 |
| 2 | 0 | 0 | 未支付超时取消 |

#### order_status 单字段含义
| 值 | 含义 |
|----|------|
| 1 | 进行中（未完成） |
| 2 | 超时取消 |
| 4 | 已取消/已退款 |
| 5 | 已完成（已发货） |

#### shipping_status 单字段含义
| 值 | 含义 |
|----|------|
| 0 | 未发货/未入库 |
| 1 | 已发货 |
| 2 | 已预占 |
| 3 | 拣货中 |
| 5 | 已拣货未发货 |
| 7 | 商家确认可自提 |
| 8 | 已取消发货/退款 |

#### pay_status 单字段含义
| 值 | 含义 |
|----|------|
| 0 | 未支付 |
| 1 | 已支付未验证 |
| 2 | 已支付已验证 |
| 3 | 全部退款 |
| 4 | 部分退款 |

#### order_type 订单类型
| 值 | 含义 |
|----|------|
| 0 | 普通订单 |
| 5 | 自营订单 |
| 6 | 特殊订单 |
| 8 | 3PL 订单 |

#### source_flag 订单来源（快速定位订单渠道）
| 值 | 含义 | 数据量 |
|----|------|--------|
| 0 | 默认/主站 | 最多 |
| 1 | 移动端 | |
| 2 | App | |
| 3 | 第三方平台 | |
| 9 | 内部测试 | |
| 11 | 渠道A | |
| 12 | 渠道B | |
| 13 | 3PL | |
| 15 | 特殊渠道 | |
| -1 | 未标记（默认值） | |

#### hold_status 拦截状态
| 值 | 含义 |
|----|------|
| 0 | 正常 |
| 1 | 已拦截 |

#### warehouse_number 仓库编号
| 值 | 含义 |
|----|------|
| 001 | 仓库1 |
| 002 | 仓库2 |

### 常用查询

```sql
-- 查询某订单完整信息
SELECT * FROM yamibuy_wh.wh_order_info WHERE order_id = ?;
SELECT * FROM yamibuy_wh.wh_order_info WHERE order_sn = ?;

-- 查询最近 N 天的订单量（按天统计）
SELECT DATE(FROM_UNIXTIME(add_time)) AS dt, COUNT(*) AS cnt
FROM yamibuy_wh.wh_order_info
WHERE add_time >= UNIX_TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 7 DAY))
GROUP BY dt ORDER BY dt;

-- 按来源统计订单
SELECT source_flag, COUNT(*) AS cnt
FROM yamibuy_wh.wh_order_info
WHERE add_time >= UNIX_TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 30 DAY))
GROUP BY source_flag ORDER BY cnt DESC;

-- 查询未发货订单
SELECT order_id, order_sn, add_time, warehouse_number
FROM yamibuy_wh.wh_order_info
WHERE shipping_status = 0 AND order_status = 1;
```

---

## 二、订单商品表 (wh_order_goods)

### 表说明
订单商品明细表，一个订单可以有多条商品记录。通过 `order_id` 关联 `wh_order_info`。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| rec_id | bigint | 自增主键 |
| order_id | bigint | 订单ID（关联 wh_order_info） |
| goods_id | bigint | 商品ID |
| goods_name | varchar(512) | 商品中文名 |
| goods_ename | varchar(512) | 商品英文名 |
| goods_number | int | 购买数量 |
| goods_price | decimal | 商品单价 |
| deal_price | decimal | 成交价 |
| send_number | smallint | 实发数量 |
| is_gift | smallint | 是否赠品（0=否, 1=是） |
| vendor_id | int | 供应商ID |
| weight | decimal | 重量 |
| cost | decimal | 成本价 |
| exp_date | int | 保质期（时间戳） |

### 常用查询

```sql
-- 查询订单包含的所有商品
SELECT goods_id, goods_name, goods_number, goods_price, deal_price, is_gift
FROM yamibuy_wh.wh_order_goods WHERE order_id = ?;

-- 查询某商品的近期销量
SELECT goods_id, goods_name, SUM(goods_number) AS total_qty
FROM yamibuy_wh.wh_order_goods og
JOIN yamibuy_wh.wh_order_info oi ON og.order_id = oi.order_id
WHERE oi.add_time >= UNIX_TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 7 DAY))
  AND goods_id = ?
GROUP BY goods_id, goods_name;

-- 热销商品 TOP 20
SELECT goods_id, goods_name, SUM(goods_number) AS total_qty, COUNT(DISTINCT og.order_id) AS order_cnt
FROM yamibuy_wh.wh_order_goods og
JOIN yamibuy_wh.wh_order_info oi ON og.order_id = oi.order_id
WHERE oi.add_time >= UNIX_TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 7 DAY))
GROUP BY goods_id, goods_name
ORDER BY total_qty DESC;
```

---

### 手工改 goods_number 前必读：各环节读的是哪份数量（2026-11-07 核查）

down 单后用脚本改 `wh_order_goods.goods_number`（如价格配错只发 1 件），WMS 各环节的数量来源：

| 环节 | 数量来源 | 改后效果 |
|---|---|---|
| 预占 `PreoccupancyService.getPreoccupanySellableInfo` | `wh_order_goods`（按 item SUM，合并赠品） | 按新数量判断 bin 够不够 |
| 组批 goods_seq_info / 拣货 `item_quantity` | `wh_preoccupancy_log.qty`（action=1） | 跟随预占数量 |
| 打包台显示 | `wh_picking_order_item` 实拣数 | 跟随拣货 |
| 出库缺发 `dealOOSPack`（central-packing） | `goods_number - 实拣数` > 0 才调 RMA `oosShiping` 退款 | 改小后**不会**对差额触发缺发退款 |
| 出库 `so_outStock` MQ 的 oos_list | 同上 | 差额不进 oos_list |
| 回写 `send_number` + 通知 SO | 实拣数 | SO 收到发 1 件 |
| 预分配 shipping method 重量（wms-cloud `listOrderGoodsWeightLb`） | **`yamibuy_master.xysc_order_goods`** | 仍按原数量算重，可能只剩 UPS/USPS 等重货 method |
| 打包生成面单重量（central-packing `listOrderGoodsWeightLb`） | `wh_order_goods` | 按新数量 |
| 发货邮件 `queryShippingMailInfo` | **`yamibuy_master.xysc_order_goods`** | 邮件仍显示原数量 |

要点：
- 必须在预占成功前改（`wh_order_pool.status=-5` 且 `batch_id=0`）。预占成功后再改，拣货仍按预占数量出库。
- 已出库（`order_status=5`、`send_number>0`）的订单不要改。
- WMS 代码里没有任何地方回写 `goods_number`（只有 down 单 insert），SO 的 hold/release MQ 也不重刷商品明细。
- 差额的退款、前台库存释放不会由 WMS 触发，需要 SO/客服侧处理。

## 三、订单池表 (wh_order_pool)

### 表说明
订单在仓库内的调度池，记录订单从进入仓库到完成发货的全流程状态。通过 `order_no` 关联 `wh_order_info.order_id`。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| order_no | bigint | 订单ID（关联 wh_order_info.order_id） |
| warehouse_number | varchar(20) | 仓库编号 |
| status | tinyint | 订单池状态 |
| batch_id | int | 批次ID（关联 wh_batch） |
| cancel | tinyint | 是否取消（0=否, 1=是） |
| is_hold | int | 是否拦截 |
| expected_delivery_dtm | int | 预计送达时间 |
| expected_shipping_dtm | int | 预计发货时间 |
| tracking_number | varchar(600) | 物流单号 |

### status 订单池状态（订单在仓库内的流转阶段）
| 值 | 含义 | 说明 |
|----|------|------|
| -5 | 已取消 | 订单被取消 |
| 0 | 待处理 | 刚进入订单池 |
| 5 | 已预占 | 库存已预占 |
| 10 | 已分批 | 已分配到批次 |
| 15 | 待拣货 | 等待拣货 |
| 20 | 拣货中 | 正在拣货 |
| 25 | 拣货完成 | 拣货已完成 |
| 30 | 待打包 | 等待打包 |
| 35 | 打包中 | 正在打包 |
| 40 | 已打包 | 打包完成 |
| 45 | 已发货 | 已出库发货 |
| 55 | 异常 | 订单异常 |

---

## 四、预占表 (wh_preoccupancy_info)

### 表说明
库存预占信息，订单确认后锁定库位上的商品数量。通过 `reference_id` 关联订单。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| reference_id | varchar(20) | 关联ID（订单号等） |
| goods_id | int | 商品ID |
| item_number | varchar(15) | SKU 编号 |
| location_no | varchar(20) | 库位号 |
| type | tinyint | 预占类型 |
| qty | int | 预占数量 |
| status | tinyint | 预占状态（0=有效） |

---

## 五、库存主表 (wh_inventory_master)

### 表说明
商品库存汇总表，每个 SKU 一条记录。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| item_number | varchar(15) | SKU 编号（唯一） |
| qty | int | 总库存数量 |
| safety_qty | int | 安全库存 |
| allocated_qty | int | 已分配数量（被预占） |
| unsellable_qty | int | 不可售数量 |

### 常用查询

```sql
-- 查询某 SKU 库存
SELECT item_number, qty, allocated_qty, unsellable_qty,
       (qty - allocated_qty - unsellable_qty) AS available_qty
FROM yamibuy_wh.wh_inventory_master WHERE item_number = ?;

-- 库存不足的商品（可用量 < 安全库存）
SELECT item_number, qty, allocated_qty, unsellable_qty, safety_qty,
       (qty - allocated_qty - unsellable_qty) AS available_qty
FROM yamibuy_wh.wh_inventory_master
WHERE (qty - allocated_qty - unsellable_qty) < safety_qty AND safety_qty > 0;
```

---

## 六、入库表 (wh_inbound)

### 表说明
入库单主表，记录 PO 收货入库信息。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| inbound_number | varchar(20) | 入库单号 |
| vendor_id | int | 供应商ID |
| warehouse_number | varchar(20) | 仓库编号 |
| inbound_type | int | 入库类型 |
| reference_id | varchar(20) | 关联单号（PO号等） |
| inbound_status | int | 入库状态 |
| acounting_qty | int | 入库数量 |
| case_id | varchar(20) | Case ID |
| receive_dtm | int | 收货时间 |
| close_dtm | int | 关闭时间 |

---

## 七、出库表 (wh_outbound)

### 表说明
出库单主表，记录订单出库发货信息。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| outbound_number | varchar(20) | 出库单号 |
| warehouse_number | varchar(20) | 仓库编号 |
| outbound_type | int | 出库类型 |
| reference_id | varchar(20) | 关联单号（订单号等） |
| tracking_no | varchar(100) | 物流单号 |
| shipping_fee | decimal | 运费 |
| outbound_status | int | 出库状态 |
| outbound_dtm | int | 出库时间 |

---

## 八、拣货表

### wh_picking_order（拣货订单）
| 字段 | 说明 |
|------|------|
| batch_id | 批次ID（关联 wh_batch） |
| picking_task_id | 拣货任务ID（关联 wh_picking_task） |
| order_no | 订单ID |
| tote_no | Tote 编号 |
| cart_no | 拣货车编号 |
| warehouse_number | 仓库编号 |

### wh_picking_task（拣货任务）
| 字段 | 说明 |
|------|------|
| picking_user | 拣货员 |
| cart_no | 拣货车编号 |
| status | 任务状态 |
| warehouse_number | 仓库编号 |

---

### 撤销误领的拣货任务

领取时写了哪些表、普通 / 单 Zone / 跨 Zone 三种场景的撤销脚本，见 skill `wms-picking-task-rollback`（`D:\code\kiro-knowledge\skills\wms-picking-task-rollback\SKILL.md`）。

## 九、打包表

### wh_packing_order_info（打包订单）
| 字段 | 说明 |
|------|------|
| order_id | 订单ID |
| order_sn | 订单编号 |
| order_status | 订单状态 |
| shipping_status | 物流状态 |
| tracking_no | 物流单号 |
| lock_order | 锁定状态 |
| carrier_id | 承运商ID |
| pack_station_id | 打包工位 |

---

## 十、订单流转记录 (wh_order_process_record)

### 表说明
记录订单在仓库内每个操作节点的时间，用于追踪订单处理效率。

### 关键字段

| 字段 | 类型 | 说明 |
|------|------|------|
| order_id | bigint | 订单ID |
| operation_type | int | 操作类型 |
| start_time | int | 开始时间 |
| end_time | int | 结束时间 |
| memo | varchar(50) | 备注 |
| isFinished | bit | 是否完成 |

### 常用查询

```sql
-- 查询订单完整流转记录
SELECT order_id, operation_type, 
       FROM_UNIXTIME(start_time) AS start_at,
       FROM_UNIXTIME(end_time) AS end_at,
       (end_time - start_time) AS duration_sec, memo
FROM yamibuy_wh.wh_order_process_record
WHERE order_id = ?
ORDER BY start_time;
```

---

## 十一、历史归档表

大部分核心表都有按年归档的历史表，命名规则为 `{表名}_{年份}`：

| 主表 | 归档表示例 | 说明 |
|------|-----------|------|
| wh_order_info | wh_order_info_2024, wh_order_info_2023 | 订单历史 |
| wh_order_goods | wh_order_goods_2023, wh_order_goods_2022 | 订单商品历史 |
| wh_order_pool | wh_order_pool_2024, wh_order_pool_2023 | 订单池历史 |
| wh_picking_order | wh_picking_order_2024, wh_picking_order_2023 | 拣货历史 |
| wh_picking_task | wh_picking_task_2023, wh_picking_task_2022 | 拣货任务历史 |
| wh_packing_order_info | wh_packing_order_info_2024 | 打包历史 |
| wh_order_process_record | wh_order_process_record_2025 | 流转记录（当年） |
| wh_inbound_batch | wh_inbound_batch_2024 | 入库批次历史 |
| wh_inventory_transaction_log | wh_inventory_transaction_log_2025 | 库存变动（当年） |
| wh_count_info | wh_count_info_2025 | 盘点记录（当年） |

**查询历史数据时，需要查对应年份的归档表。** 主表只保留当前活跃数据。

---

## 十二、跨表关联查询示例

```sql
-- 订单 + 商品 + 订单池状态（完整订单视图）
SELECT oi.order_id, oi.order_sn, oi.order_status, oi.shipping_status,
       op.status AS pool_status, oi.warehouse_number,
       og.goods_id, og.goods_name, og.goods_number, og.deal_price
FROM yamibuy_wh.wh_order_info oi
LEFT JOIN yamibuy_wh.wh_order_pool op ON oi.order_id = op.order_no
LEFT JOIN yamibuy_wh.wh_order_goods og ON oi.order_id = og.order_id
WHERE oi.order_sn = ?;

-- 订单全链路追踪（从下单到发货）
SELECT oi.order_sn, oi.order_id,
       FROM_UNIXTIME(oi.add_time) AS order_time,
       op.status AS pool_status,
       po.picking_task_id, pt.picking_user,
       pi.order_status AS pack_status, pi.tracking_no,
       ob.outbound_number, FROM_UNIXTIME(ob.outbound_dtm) AS ship_time
FROM yamibuy_wh.wh_order_info oi
LEFT JOIN yamibuy_wh.wh_order_pool op ON oi.order_id = op.order_no
LEFT JOIN yamibuy_wh.wh_picking_order po ON oi.order_id = po.order_no
LEFT JOIN yamibuy_wh.wh_picking_task pt ON po.picking_task_id = pt.rec_id
LEFT JOIN yamibuy_wh.wh_packing_order_info pi ON oi.order_id = pi.order_id
LEFT JOIN yamibuy_wh.wh_outbound ob ON CAST(oi.order_id AS CHAR) = ob.reference_id
WHERE oi.order_sn = ?;

-- 某商品的库存 + 预占 + 库位分布
SELECT im.item_number, im.qty AS total_qty, im.allocated_qty, im.unsellable_qty,
       (im.qty - im.allocated_qty - im.unsellable_qty) AS available_qty,
       sli.location_no, sli.qty AS location_qty
FROM yamibuy_wh.wh_inventory_master im
LEFT JOIN yamibuy_wh.wh_storage_location_item sli ON im.item_number = sli.item_number
WHERE im.item_number = ?;
```

---

## 十三、调拨装车表（wh_transship_truck / wh_transship_truck_out_pallet）

调拨（Transship）与 Zone Picking 一期跨 Zone 上车共用这两张表，识别或回填某一类行时注意（2026-10，OP-40026 第 3 轮审查实查）：

- `wh_transship_truck_out_pallet` **没有 warehouse_number 列**（`TSTruckMapper.insertOutPallet` 只写 manifest、location_no、seal_no、in_user、in_dtm、status），按仓库筛只能靠 location_no 关联到该仓的库位或车，或经 manifest / seal_no 关联 `wh_transship_truck.warehouse_number`。
- 调拨托盘行的 **manifest 可能为空**：`TSTruckService.createTruckRecord` 只在 seal_no 为空时生成 manifest，按 seal_no 建车的旧流程，`loadPallet2Truck` 写入的托盘行 manifest 为空；调拨查询因此用 `ttpo.manifest = tt.manifest OR ttpo.seal_no = tt.seal_no` 关联车次。
- 一期 Zone 上车写入的行 manifest 也为空，location_no 是 Zone 2 Tote 或 Cart 号（无 Tote 的车以 Cart 号占位）。所以「manifest 为空」不能单独作为「Zone 行」的判据，必须再限定 location_no 属于该仓 Zone 2 的 Tote（location_type = 6、zone_id = 2）或 Zone 2 车（`wh_picking_cart.zone_id = 2`）。
- status：0 = 未下车 / 未收货，1 = 已下车 / 已收货。

---

## 时间字段说明

所有时间字段均为 Unix 时间戳（秒），查询时使用 `FROM_UNIXTIME()` 转换：

```sql
-- 时间戳转日期
SELECT FROM_UNIXTIME(add_time) AS order_date FROM yamibuy_wh.wh_order_info;

-- 按日期范围查询
WHERE add_time >= UNIX_TIMESTAMP('2025-04-01')
  AND add_time < UNIX_TIMESTAMP('2025-04-02');

-- 最近 N 天
WHERE add_time >= UNIX_TIMESTAMP(DATE_SUB(CURDATE(), INTERVAL 7 DAY));
```
