---
inclusion: auto
name: picking-app-arch
description: 给 Picking App（com.picking）新增或排查后端接口、遇到 90008/Token is Invalid、配置认证或路由时使用。触发词：Picking App, picking, com.picking, @VestaIgnore, Vesta, 90008, Token is Invalid, site_code, orderPick, 工牌登录, scan-totes, bindToteNumber, 绑 Tote, PA-CHK, eslint CRLF
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

## 规则5：`scan-totes.tsx` 绑 Tote 成功分支依赖「原地改订单对象」（OP-40026 实现时发现）

`bindToteNumber` 成功后先 `setPickingData(() => { updatedOrders[i].tote_no = tote_no; ... })`，绑完（`isBindToteFinish == 1`）时再用**本次闭包里的** `pickingData` 组装 `data` 写缓存。`updatedOrders` 只是数组浅拷贝，`tote_no` 是直接改在共享的订单对象上，所以闭包里的 `pickingData.picking_order` 也带上了最后一个刚绑的 Tote。

- 改这段时不要换成 `map(o => ({...o, tote_no}))` 这种不可变写法：缓存会丢掉最后一个 Tote，`scan-tote.tsx` 按 order_no 找目标 Tote 时这些订单取到空串，拣货员每扫一次都报 `WRONG Tote!`。
- 未绑完时这里不写缓存，续拣靠后端 `createPickingTask` 返回的 `bindToteIndex` 与已绑 `tote_no` 恢复。

## 规则6：本机跑 eslint 时先剔除 CRLF 噪音再对比

central-picking-app 仓库里文件是 LF，本机 `core.autocrlf=true` 检出为 CRLF，`prettier/prettier` 会对每一行报 ``Delete `␍` ``（单个文件几百条）。PA-CHK「不新增错误与警告」要用 `-f json -o <文件>` 输出，去掉 message 恰为 ``Delete `␍` `` 的条目后按规则与消息对比；提交后 `git ls-files --eol` 应仍是 `i/lf`。

## 规则7：没有真机也能在模拟器上走 App 内 mock（OP-40026 二轮验证时打通）

「本机没有设备」不是跳过 App 内走查的理由：`D:\ADT\Android\android-sdk-windows\emulator\emulator.exe -list-avds` 有 `Pixel`（API 26 x86）与 `Medium_Phone_API_36.0`。

- **装包**：`android\app\build\outputs\apk\debug\app-debug.apk` 含 x86 库、不内置 bundle；没有原生改动时直接 `adb install -r` 复用，JS 从 Metro 取。Metro 用 `npx react-native start --reset-cache`（工具会拦带 `--port` 的命令）+ `adb reverse tcp:8081 tcp:8081`。
- **扫码**：`BarcodeScannerModule` 监听广播 `android.intent.ACTION_DECODE_DATA`、读 extra `barcode_string`，所以 `adb shell am broadcast -a android.intent.ACTION_DECODE_DATA --es barcode_string <条码>` 就等于扫一次，工卡、车、库位、Tote、`OOS`、`COMPLETE` 都能这样扫。
- **不打生产**：`instance.ts` 默认 baseURL 是生产，mock 的 adapter 对未列出的接口必须直接失败，不能回落真实请求；模拟器再开飞行模式断外网（Pixel 是 production 镜像，`adb root`、`svc wifi disable` 都无效，只能在设置页点开关）。走完 `adb shell pm clear com.picking` 清掉本地缓存与未发出的 Firebase 事件。
- **断网后连 Metro**：App 默认连 `10.0.2.2:8081`，飞行模式下不通。debug 包可 `run-as`：把含 `<string name="debug_http_host">localhost:8081</string>` 的 `com.picking_preferences.xml` 推到 `/data/local/tmp` 再 `adb shell run-as com.picking cp … shared_prefs/`，重启 App 即走 adb reverse。
- **看缓存**：`adb shell "run-as com.picking cat databases/RKStorage > /data/local/tmp/rk.db"` 后 pull，用 Python sqlite3 读 `catalystLocalStorage` 表的 `pickingData` / `routeName`，可以直接核对绑 Tote 后缓存里每单的 `tote_no`、`floor`（规则 5 的缓存问题就靠这个看）。
- **截图**：`adb shell screencap -p /sdcard/s.png` + `adb pull`（不要 `exec-out >`）；截到全黑先 `input keyevent KEYCODE_WAKEUP`、`svc power stayon true`。

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
