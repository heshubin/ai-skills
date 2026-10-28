---
name: wms-app-login
description: 通过 Appium + UiAutomator2 自动登录 WMS App 并导航到指定功能界面（consolidation、load truck 等），账号密码从环境变量读取。触发词：登录 wms app, 登录 wms, 打开 wms app 并登录, 进入 consolidation, 打开 load truck, Appium 登录
---
# wms-app-login Skill

## 触发词
- "登录 wms app"
- "登录 wms"
- "打开 wms app 并登录"
- "进入 consolidation"
- "打开 load truck"

## 用途
通过 Appium + UiAutomator2 自动完成 WMS App 登录，并可导航到指定功能界面。

---

## 默认账号（从环境变量读取）

| 环境变量 | 含义 | 备注 |
|--------|------|------|
| `WMS_APP_USER` | 默认用户名（UAT / NJ 仓） | 真值见 account-password-query skill |
| `WMS_APP_PASSWORD` | 默认密码 | 真值见 account-password-query skill，不要写进本文件或脚本 |
| `WMS_DEVICE_UDID` | 设备序列号 | `adb devices` 显示的 ID |
| `WMS_SCREENSHOT_DIR` | 截图/UI dump 输出目录（可选） | 不设时为当前目录（主工作空间根）下的 `docs\tmp\wms_test`，脚本会自动创建 |

## 执行方式

已设置上述环境变量时，用户说"登录 wms app"直接执行，**无需询问账号密码**；未设置时先请用户提供或设置环境变量：

```powershell
# 只登录到主页
python "D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py"

# 登录并进入 Consolidation
python "D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py" --target consolidation

# 登录并进入 Load Truck
python "D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py" --target load-truck

# 换账号时才需要指定参数
python "D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py" --user <用户名> --pwd "<密码>" --warehouse NJ
```

可用 target：`consolidation` / `load-truck` / `unload-truck` / `receiving`

---

## 关键设计原则（来自 sop-automation-rules.md）

1. **不用坐标定位** — 全部用 `resource-id` 或 `class + text` 的 XPATH
2. **输入后关键盘** — `driver.hide_keyboard()` 避免键盘遮挡后续元素
3. **点 clickable=true 的父元素** — React Native 按钮是 ViewGroup，不是 TextView
4. **全局处理升级弹窗** — 每次操作后检查是否有 "Later" 按钮
5. **显式等待，不用 sleep** — `WebDriverWait + expected_conditions`
6. **no_reset=True** — 保留 App 状态，不清数据

---

## 脚本位置

`D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py`（全局经验库，挂载后即 `~/.kiro/skills/wms-app-login/`）

---

## 前提条件

1. 设备 USB 连接：`adb devices` 能看到设备，且其 ID 与环境变量 `WMS_DEVICE_UDID` 一致
2. Appium 已安装：`appium --version`
3. Metro 已启动（`npx react-native start`），否则 App 白屏
4. Python 依赖：`pip install Appium-Python-Client selenium`

---

## 登录流程说明（两步，来自代码分析）

```
第一步：POST wms/common/loginWithoutWarehouseNum
  ↓ 返回 warehouseList
  ├─ 1个仓库 → 直接 completeLogin，无需用户选择
  └─ ≥2个仓库 → LoginScreen 内显示 Dropdown（testID="warehouse_number-dropdown"）
                用户选仓库后再次点 Login
                          ↓
第二步：completeLogin（带 warehouse）
  → POST wms/common/confirmLogin?site_code=<siteCode>
  → 保存 loginUser，进入主页
```

脚本检测逻辑：
- 点击第一步 Login 后，查找 `resource-id="warehouse_number-dropdown"`
- 找到 → 多仓库流程：选择匹配的仓库，再次点 Login
- 未找到 → 单仓库流程：已直接完成登录
