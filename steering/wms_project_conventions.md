---
inclusion: fileMatch
fileMatchPattern: '**/wms-cloud-service/**,**/central-packing-service/**'
---

# WMS/Central-Packing 项目约定

## 项目结构

### wms-cloud-service（多模块 Maven 项目）
- `wms-cloud-api/` — 实体类、DTO、枚举、请求/响应对象
- `wms-cloud-service/` — Service 层、DAO 层、MyBatis XML
- `wms-cloud-rest/` — Controller 层（REST 接口）
- `wms-cloud-job/` — 定时任务

### central-packing-service（多模块 Maven 项目）
- `central-packing-api/` — 实体类（与 wms-cloud-api 有同名类需同步）
- `central-packing-service/` — Service 层
- `central-packing-rest/` — Controller 层

## 跨服务同步

wms-cloud-api 和 central-packing-api 中有同名的请求对象（如 AdjustLocationRequest、LocationItemRequest），新增字段时两边必须同步修改：
- `wms-cloud-api/.../request/AdjustLocationRequest.java`
- `central-packing-api/.../request/AdjustLocationRequest.java`
- `wms-cloud-api/.../request/LocationItemRequest.java`
- `central-packing-api/.../request/LocationItemRequest.java`
- `wms-cloud-api/.../InventoryTransactionLog.java`（entity + response 两个）
- `central-packing-api/.../InventoryTransactionLog.java`

## 核心调用链

LocationService.adjustLocation() 是所有库存流转的统一入口：
```
checkLocation → dealInventoryTransaction → dealLotInventoryTransaction → saveInventoryTransactionLog → adjustLocationTrans
```

## 枚举体系

- `LocationProcessEnum` — 操作类型编码（80+ 个 actionType）
- `LocationProcessRelationEnum` — 流转关系（from/to 库位类型 + 操作类型）
- `LocationTypeEnum` — 库位类型（code < 0 为虚拟库位）
- Opera 字段（ADD/SUBTRACT/CONSTANT）在代码中未使用，不要依赖它

## 数据库约定

- 时间字段用 int 存储 Unix 时间戳（秒）
- 所有 SQL 使用 `#{}` 参数化查询，禁止 `${}`
- 表名带 `yamibuy_wh.` 前缀
- 新增字段默认值：int 用 0，varchar 用 ''

## 测试约定

- 测试框架：Spock（Groovy）
- 测试文件位置：`wms-cloud-service/src/test/java/`
- 测试文件后缀：`.groovy`
- Mock 用 `Mock()`，Stub 用 `Stub()`
