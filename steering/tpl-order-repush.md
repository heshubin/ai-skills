---
inclusion: auto
name: tpl-order-repush
description: 当需要补推/修复 central-tpl-service 3PL 订单（lasfit 等 API 创单失败、callPurchaseCreateOrder 中断、wh_tpl_order_info / wh_tpl_ship_record 补数据）时使用。触发词：3PL, 补推, 重推, 创单失败, lasfit, central-tpl-service, callPurchaseCreateOrder, wh_tpl_order_info, wh_tpl_ship_record
---

# TPL 3PL 订单补推修复约束

## 背景（2026-10-04 Vesta 故障，lasfit 54 单）

`CentralTokenService.getToken` 登录失败（Vesta 重启风暴），`callPurchaseCreateOrder` 在 try 块之前中断：
TPL 订单已写入且停在 APPROVED(1)，yami 订单未创建，物流记录未写入。
补推时只调了 SO 建单，漏掉物流记录，且状态写成了不存在的 3，前端订单状态、运单号都显示空。

## 规则1：补推必须复刻 callPurchaseCreateOrder 的全部副作用

| 步骤 | 代码 | 写什么 |
|---|---|---|
| 1 | `postRequest(/so/order/third/submit/physical/v2)` | SO 建 yami 订单 + so_channel_order |
| 2 | `fillYamiOrderId` | `wh_tpl_order_info.yami_order_id` |
| 3 | `saveTrackInfo` → `saveTrackLabelList` | `wh_tpl_ship_record`（status=9，含 tracking_code / shipping_label_data） |
| 4 | `markTplOrderStatus(1 → 10)` | `wh_tpl_order_info.status=10` + `wh_tpl_order_log` 一条 |

只做第 1 步，订单能建出来，但仓库没有面单，前端也看不到状态和运单号。

## 规则2：状态码必须读 `TplAuditStatus` 枚举，禁止凭记忆写

`PENDING_REVIEW=0, APPROVED=1, EXCEPTION=5, PENDING_SHIPMENT=10, SHIPPED=15, INTERCEPTING=20, CANCELLING=21, CANCELLED=25, RELEASED=30`

## 规则3：物流数据从入口日志取

- API 创单的物流信息在 `SystemLogAspect` 的 `Request URL : /order/createOrder` 日志 `Request args` 里（明文 JSON，snake_case：`shipping_info_list.service_code / carrier / tracking_code / label_str`）
- 单条日志可达 100KB+，`label_str` 是完整 PDF base64，可直接入库
- lasfit 会重推：同一订单可能有多次请求、多个面单。FedEx/OnTrac/DHL（service_code=yami）的旧面单会被 `Shipping3PLService` 置为 `CANCEL_LABEL=2`，取最后一次请求的面单
- 工具：`docs/tpl-createOrder-faild/tools/extract_shipping.py`、`gen_fix_sql.py`

## 规则4：TPL 索引检索 trace 用 `"traceId,spanId"` 整体短语

单独搜 traceId 或 spanId 在 `k8s-central-tpl-service-log-*` 会 0 命中，**0 命中不代表日志不存在**。

## wh_tpl_ship_record.status

| 值 | 含义 | 写入方 |
|---|---|---|
| 0 | 询价缓存（rates_data） | central-packing |
| 1 | yami 代买面单已生成 | central-packing GENERATE_LABEL |
| 2 | 面单已取消 | central-packing CANCEL_LABEL |
| 9 | TPL 外部面单（订单正式物流） | central-tpl TPL_OUTER_LABEL |

queryOrder 列表运单号 = `IFNULL(wh_order_info.tracking_number, wts.tracking_code)`，wts 只取 status IN (9,1)。

## 打包报 `3PL order has not provided label data.`（2026-10-07 229663105）

- 抛出点：`central-packing TplLogisticsService.ship`，按 `wh_tpl_ship_record.yami_reference_id = yami 订单号` 查不到任何记录（不看 status）
- 3PL 订单（`wh_order_info.order_type=8`）打包时只能用客户提供的面单，不会回落到 USPS 等自购面单，所以换 carrier 重试也没用
- 物流记录只在 `callPurchaseCreateOrder → saveTrackInfo` 写入，数据来自 `shippingInfoList`
  - API 创单：`validateTplOrderTracking` 强制要求 shippingInfoList，正常都有记录
  - Portal 创单（source=2 单个创建 / 3 批量 / 4 平台）：**不校验物流**，前端没传就不写 ship_record → 必然在打包报这个错
  - 其他：Vesta 等故障导致 `callPurchaseCreateOrder` 中断（见上文 54 单）
- 判断方法：tpl 日志里 `fillYamiOrderId` 之后紧跟 `updateStatusTplByOrderId(10)`，中间没有 `ShippingRecordDao.insertList`，就是 shippingInfoList 为空
- `ShippingRecordService.uploadTrackLabel`（事后补传面单）没有任何 Controller 调用，客户无法自助补传；且它写入不带 `yami_reference_id`
- 7/1~10/7 lasfit 只有这一单是 Portal 创建（API 73,447 单全部有物流记录）
