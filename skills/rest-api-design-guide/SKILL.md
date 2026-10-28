---
name: rest-api-design-guide
description: 设计或审查 REST 接口、Controller 层代码、前后端接口联调时使用（Spring Boot 后端）。触发词：接口设计, API, REST, controller, URL 命名, 响应结构, 错误码
---
# RESTful API 设计规范

设计或审查 REST 接口时使用。适用于 Spring Boot 后端 + 前端对接场景。

## 触发场景

- 设计新的 REST 接口
- 审查 Controller 层代码
- 前后端接口联调
- 提到"接口设计"、"API"、"REST"、"controller"时

## URL 命名规范

```
# 资源命名：复数名词，小写，连字符分隔
GET    /api/lot-masters          # 查询列表
GET    /api/lot-masters/{id}     # 查询单个
POST   /api/lot-masters          # 创建
PUT    /api/lot-masters/{id}     # 全量更新
PATCH  /api/lot-masters/{id}     # 部分更新
DELETE /api/lot-masters/{id}     # 删除

# 操作类接口：动词放在资源后面
POST   /api/lot-masters/{id}/activate    # 激活
POST   /api/lot-masters/{id}/deactivate  # 停用
POST   /api/inventory/transfer           # 库存转移（非 CRUD 操作）
```

### 命名禁忌
- ❌ `/api/getLotMaster` — 不要用动词做资源名
- ❌ `/api/lot_masters` — 不要用下划线
- ❌ `/api/LotMasters` — 不要用大驼峰
- ❌ `/api/lot-master/list` — 不需要 /list，GET 复数资源即表示列表

## HTTP 方法选择

| 方法 | 语义 | 幂等性 | 请求体 |
|------|------|--------|--------|
| GET | 查询，不修改数据 | 幂等 | 无 |
| POST | 创建资源或执行操作 | 非幂等 | 有 |
| PUT | 全量替换资源 | 幂等 | 有 |
| PATCH | 部分更新资源 | 幂等 | 有 |
| DELETE | 删除资源 | 幂等 | 无 |

## 状态码使用

```
200 OK              — 成功（查询、更新）
201 Created         — 创建成功
204 No Content      — 删除成功，无返回体
400 Bad Request     — 参数校验失败
401 Unauthorized    — 未认证
403 Forbidden       — 无权限
404 Not Found       — 资源不存在
409 Conflict        — 资源冲突（如重复创建）
422 Unprocessable   — 业务校验失败
500 Internal Error  — 服务器内部错误
```

## 请求/响应体结构

### 统一响应格式
```json
{
    "code": 0,
    "message": "success",
    "data": { ... }
}
```

### 分页响应
```json
{
    "code": 0,
    "message": "success",
    "data": {
        "list": [ ... ],
        "total": 1000,
        "page": 1,
        "pageSize": 20
    }
}
```

### 分页/排序/过滤参数
```
GET /api/lot-masters?page=1&pageSize=20&sort=createdAt,desc&status=1&keyword=LOT
```

## 错误响应格式

```json
{
    "code": 40001,
    "message": "参数校验失败",
    "errors": [
        { "field": "itemNumber", "message": "不能为空" },
        { "field": "quantity", "message": "必须大于0" }
    ]
}
```

- 错误码分段管理：40xxx 参数错误，41xxx 认证错误，42xxx 业务错误，50xxx 系统错误
- 禁止在错误响应中暴露堆栈、SQL、文件路径等内部信息

## 参数校验

```java
// 使用 @Valid + JSR 303 注解
@PostMapping("/lot-masters")
public Result<LotMaster> create(@Valid @RequestBody CreateLotRequest request) {
    // ...
}

public class CreateLotRequest {
    @NotBlank(message = "SKU不能为空")
    private String sku;

    @NotNull(message = "数量不能为空")
    @Min(value = 1, message = "数量必须大于0")
    private Integer quantity;
}
```

## 版本控制

- URL 路径版本：`/api/v1/lot-masters`、`/api/v2/lot-masters`
- 新版本只在有 breaking change 时才升级
- 旧版本保持向后兼容，设置废弃时间

## 安全规范

- 敏感操作使用 POST（不要用 GET 修改数据）
- Token/密码通过 Header 传递，不放在 URL 参数中
- 响应中不返回密码、密钥等敏感字段
- 设置合理的请求超时和限流
