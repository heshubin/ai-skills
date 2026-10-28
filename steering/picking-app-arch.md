---
inclusion: auto
name: picking-app-arch
description: 给 Picking App（com.picking）新增或排查后端接口、遇到 90008/Token is Invalid、配置认证或路由时使用。触发词：Picking App, picking, com.picking, @VestaIgnore, Vesta, 90008, Token is Invalid, site_code, orderPick, 工牌登录
---
# Picking App 架构约束（自动加载）

## 核心认知：Picking App 没有 token 体系

Picking App（包名 `com.picking`）是仓库 PDA 设备上的专用 App：
- 用户通过**扫工牌 barcode** 登录，不走标准的 OAuth/JWT 流程
- **所有 HTTP 请求 Headers 里只有 `site_code`，没有任何 token 字段**
- Vesta 认证体系对 picking app 完全无效

```
// interceptors.ts 里只做这一件事
config.headers.set('site_code', userData.site_code);
// 没有 Authorization，没有 wms_token，没有任何 token
```

---

## 规则1：给 Picking App 新增后端接口，必须加 @VestaIgnore

**每一个**供 picking app 调用的后端接口，无论在哪个 Controller 里，**都必须加 `@VestaIgnore`**。

```java
// ✅ 正确
@VestaIgnore
@PostMapping("/your-new-endpoint")
public BaseResponse<String> yourNewEndpoint(...) { ... }

// ❌ 漏加 @VestaIgnore → 前端收到 {"messageId":"90008","enError":"Token is Invalid"}
@PostMapping("/your-new-endpoint")
public BaseResponse<String> yourNewEndpoint(...) { ... }
```

**错误症状**：前端日志出现 `messageId: 90008 / Token is Invalid`，但其他同 Controller 的接口正常。

---

## 规则2：接口路由必须走 picking-accessible 的路径

Central-api 网关对不同路径有不同的认证策略。Picking App 调用的接口必须走以下路径前缀之一：

| 路径前缀 | 认证要求 | Picking App 可用 |
|---------|---------|----------------|
| `wms/orderPick/` | `@VestaIgnore` 绕过 | ✅ 可用 |
| `wms/api/v1/` | `@VestaIgnore` 绕过 | ✅ 可用（但需确认部署生效） |
| `wms/general/` | `@VestaIgnore` 绕过 | ✅ 可用 |
| WMS App 专用路径 | 需要 WMS session token | ❌ 不可用 |

**⚠️ 特别注意**：`wms/api/v1/` 路径理论上 `@VestaIgnore` 有效，但历史上出现过因部署版本落后导致注解未生效的问题（返回 90008）。
**保险做法**：新接口优先放到 `wms/orderPick/` 下，或在 `OrderPickRestImpl` 里加一个转发入口。

---

## 规则3：排查 picking app 接口 90008 的标准流程

遇到 `messageId: 90008` 时，按以下顺序排查：

```
1. 确认其他同 Controller 的接口是否正常（无 90008）
   ↓ 其他接口正常，说明 Controller 类级别认证没问题
2. 确认该接口有没有 @VestaIgnore 注解
   ↓ 有注解但仍 90008
3. 确认 UAT 部署的是否是包含该注解的最新代码版本
   → 用 curl/PowerShell 对比同 Controller 旧接口和新接口的响应差异
   → 若旧接口返回业务错误（99998），新接口返回 90008，说明是部署版本落后
4. 重新部署最新代码到 UAT
```

---

## 规则4：Picking App 接口 URL 命名约定

| 接口类型 | URL 前缀 | 示例 |
|---------|---------|------|
| 拣货核心流程 | `wms/orderPick/` | `wms/orderPick/createPickingTask` |
| 通用工具接口 | `wms/general/` | `wms/general/checkItemUPC` |
| Zone Picking 配置 | `wms/api/v1/zone/` | `wms/api/v1/zone/config` |
| Consolidation（新） | `wms/orderPick/` | `wms/orderPick/bindZoneCartToSlot` |

**原则**：不要给 picking app 新接口用 WMS App 专属的路径，容易因认证体系差异导致问题。

---

## 附：Picking App 认证架构一览

```
用户扫工牌 barcode
    ↓
POST wms/checkUser/{barcode}
    ↓ 返回 user_id, warehouse_number, site_code
    ↓ 存入 AsyncStorage
    ↓
后续所有请求：
  Headers: { site_code: "us" }  ← 仅此一个，无 token
  后端：@VestaIgnore             ← 每个接口都要加
```
