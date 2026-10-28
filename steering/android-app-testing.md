---
inclusion: auto
name: android-app-testing
description: 打包安装或调试 WMS App/Picking App、Metro 热更新、logcat、真机截图、Appium 自动登录时使用。触发词：启动 WMS, 启动 Picking, 打包, Release 包, Debug 包, Metro, 8081, adb, logcat, 真机, Appium, 安装 apk
---

# Android App 测试 SOP

用于测试 WMS / Picking 两个 Android App：代码改动判断 → 打包安装 → 实时日志监控。

---

## APP 信息

| APP | 包名 | Activity | 代码目录 | 签名 keystore |
|-----|------|----------|---------|--------------|
| WMS App | `com.wmsrn` | `com.wmsrn/.MainActivity` | `d:\code\WMS-front-end\wms-rn` | — |
| Picking App | `com.picking` | `com.picking/.MainActivity` | `d:\code\central-picking-app` | `android/app/my-release-key.keystore`（密码见 gradle.properties）|

> 用户说"启动 WMS"就用 `com.wmsrn`，说"启动 Picking"就用 `com.picking`，不需要再确认。

---

## ⚠️ Windows 端口限制（按需处理）

Windows 系统会动态保留一段端口范围（通常由 Hyper-V/WSL 触发），8081 可能被保留。

**验证当前是否可用**：
```powershell
$test = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, 8081)
try { $test.Start(); $test.Stop(); Write-Host "✅ 8081 可用" }
catch { Write-Host "❌ 8081 被系统保留，改用 8180" }
```

- **8081 可用** → 直接用默认端口，无需额外配置
- **8081 被占用** → 改用 **8180**（重启电脑后通常恢复正常）

查看当前保留范围：
```powershell
cmd /c "netsh int ipv4 show excludedportrange protocol=tcp"
```

---

## 一、改动类型判断

| 改动类型 | 处理方式 | 耗时 |
|---------|---------|------|
| 只改 `.ts` / `.tsx` | Metro 热更新，Dev Menu → Reload | **2-3秒** ✅ |
| 改了 `android/` 目录（含 AndroidManifest.xml）| 必须重新打包 | 1-3分钟 |
| 新增/删除 npm 包（含 native 代码）| 必须重新打包 | 3-5分钟 |

---

## 二、日常调试 — Metro 热更新（推荐）

### 初始化（只做一次）

```powershell
# 1. 启动 Metro（默认 8081，不可用时改 --port 8180）
cd D:\code\central-picking-app
npx react-native start          # 或 npx react-native start --port 8180

# 2. 另开终端设置端口转发（端口要和上面一致）
adb reverse tcp:8081 tcp:8081   # 或 adb reverse tcp:8180 tcp:8180
```

**首次连接**：手机摇一摇 → Dev Menu → Settings → Debug server host → 输入 `127.0.0.1:8081`（或 `127.0.0.1:8180`）→ Reload

### 日常改代码 → 立即看效果

改完 `.tsx` 文件后，在手机 Dev Menu 点 **Reload**，2-3秒生效。

---

## 三、打 Debug 包（有 console.log，用于排查问题）

```powershell
cd D:\code\central-picking-app\android
.\gradlew.bat assembleDebug
# 输出：android\app\build\outputs\apk\debug\app-debug.apk
```

安装：
```powershell
adb uninstall com.picking   # 签名不同时先卸载
adb install android\app\build\outputs\apk\debug\app-debug.apk
adb shell am start -n com.picking/.MainActivity
```

> **注意**：Debug 包需要 Metro 提供 JS bundle，否则白屏。  
> 如果要内置 bundle（不依赖 Metro）：
> ```powershell
> npx react-native bundle --platform android --dev true --entry-file index.js \
>   --bundle-output android/app/src/main/assets/index.android.bundle \
>   --assets-dest android/app/src/main/res
> ```
> 然后再 `assembleDebug`，这样 App 不需要 Metro 也能运行（console.log 保留）。

---

## 四、打 Release 包（生产包，无 console.log）

### 前提：Metro 必须运行中

Gradle Release 构建会自动调 Metro 打 bundle，必须先启动 Metro：

```powershell
# 终端1：启动 Metro
cd D:\code\central-picking-app
npx react-native start --port 8180
```

### 编译签名 Release APK

```powershell
# 终端2：编译
cd D:\code\central-picking-app\android
.\gradlew.bat assembleRelease
# 输出：android\app\build\outputs\apk\release\app-release.apk（约59MB）
```

签名配置在 `android/gradle.properties`：
```
MYAPP_RELEASE_STORE_FILE=my-release-key.keystore
MYAPP_RELEASE_KEY_ALIAS=my-key-alias
MYAPP_RELEASE_STORE_PASSWORD=<见 d:\code\central-picking-app\android\gradle.properties>
MYAPP_RELEASE_KEY_PASSWORD=<见 d:\code\central-picking-app\android\gradle.properties>
```

安装 Release 包：
```powershell
adb uninstall com.picking
adb install android\app\build\outputs\apk\release\app-release.apk
adb shell am start -n com.picking/.MainActivity
```

---

## 五、截图 & 读屏（快速查看手机界面）

```powershell
# 截图（推荐方式，文件完整）
adb shell screencap -p /sdcard/screen.png
New-Item -ItemType Directory -Force "<主工作空间>\docs\tmp\wms_test" | Out-Null   # <主工作空间> = 第一个 workspace folder
adb pull /sdcard/screen.png "<主工作空间>\docs\tmp\wms_test\screen_now.png"
# 截完后在 Kiro Explorer 直接点击图片文件即可预览，无需额外操作
```

---

## 六、日志监控

### Android Studio Logcat（推荐）

在 Android Studio 里过滤 `ReactNativeJS`，可看到：
- 所有 `console.log` 输出
- API 请求/响应完整内容（包含 URL、参数、返回值）
- JS 错误堆栈

### adb logcat（命令行）

```powershell
# 获取 App 的 PID
$pid = adb shell pidof com.picking
Write-Host "Picking PID: $pid"

# 只看该 App 的 JS 层日志
adb logcat --pid=$pid -s ReactNativeJS:V

# 只看崩溃堆栈
adb logcat -d | Select-String "FATAL EXCEPTION|AndroidRuntime" | Select-Object -Last 30
```

---

## 七、环境切换（Picking App 专用）

Picking App 支持扫码切换 API 环境，扫以下条码：

| 条码 | 环境 | API 地址 |
|------|------|---------|
| `GQC` | 测试 | `gqc-centralapi.yamibuy.tech` |
| `UAT` | 验收 | `uat-centralapi.yamibuy.tech` |
| `DEV` | 开发 | `dev-centralapi.yamibuy.tech` |
| `ADMINPRD` | 生产 | `centralapi.yamibuy.net` |

> ⚠️ 条码前后不能有空格，否则会被当做工卡号处理。

---

## 八、常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| App 启动白屏（无 bundle） | Debug 包没有内置 bundle，且 Metro 未启动 | 先启动 Metro：`npx react-native start --port 8180`，然后 `adb reverse tcp:8180 tcp:8180`，手机 Dev Menu → Reload |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 设备已装不同签名的包 | `adb uninstall com.picking` 后重装 |
| Metro 报 `EADDRINUSE :8081` | 8081 被 Windows 系统动态保留（重启后通常恢复）| 验证：`$t=New-Object Net.Sockets.TcpListener('0.0.0.0',8081);try{$t.Start();$t.Stop();'可用'}catch{'改用 8180'}`；或直接重启电脑 |
| Release 构建失败 `createBundleReleaseJsAndAssets` | Metro 未运行 | 先在另一个终端启动 Metro，再 `assembleRelease` |
| 扫码切换环境失败，触发了 checkUser | 条码带空格（如 ` UAT`）| 扫码设备设置去掉前缀/后缀空格，或联系设备管理员 |
| 升级弹窗无法关闭（只有 UPDATE 按钮）| `forceUpdateFlag=Y` 时没有 Later 按钮 | 修改 `DownloadManager.tsx` 强制加 Later 按钮，或把 `versionName` 改成服务器最新版本号 |
| Gradle build 缓存导致改动未生效 | `packageDebug UP-TO-DATE` | 删除 `android/app/build` 目录后重新编译 |
| adb 进程僵死，所有命令挂起 | 多个僵尸 adb 进程 | `Get-Process adb \| Stop-Process -Force`，再 `adb start-server` |

---

## 九、快速命令

```powershell
# 设备检查
adb devices

# 端口转发（8180）
adb reverse tcp:8180 tcp:8180

# 强制停止 App
adb shell am force-stop com.picking
adb shell am force-stop com.wmsrn

# 启动 App
adb shell am start -n com.picking/.MainActivity
adb shell am start -n com.wmsrn/.MainActivity

# 卸载
adb uninstall com.picking
adb uninstall com.wmsrn

# 截图
adb shell screencap -p /sdcard/s.png; adb pull /sdcard/s.png "<主工作空间>\docs\tmp\picking_test\s.png"

# adb 重置（进程卡死时）
Get-Process adb -ErrorAction SilentlyContinue | Stop-Process -Force
adb start-server
adb devices
```

---

## 十一、WMS App 自动登录（Appium 方案）

触发词：**"登录 wms app"** 或 **"登录 wms"**

用户说触发词时，Kiro 会询问账号密码和仓库，然后直接执行自动登录。

### 执行步骤

```powershell
# 1. 启动 Appium（如未运行，后台启动）
Start-Process -FilePath "appium" -ArgumentList "--port 4723" -NoNewWindow
Start-Sleep -Seconds 3

# 2. 运行登录脚本（替换账号密码）
python "D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py" `
  --user <用户名> --pwd "<密码>" --warehouse <仓库名>

# 带导航目标
python "D:\code\kiro-knowledge\skills\wms-app-login\wms_login.py" `
  --user <用户名> --pwd "<密码>" --warehouse NJ --target consolidation
```

### 可用 target

| target | 说明 |
|--------|------|
| `consolidation` | 进入 Consolidation 模块 |
| `load-truck` | 进入 Load Truck 界面 |
| `unload-truck` | 进入 Unload Truck 界面 |
| `receiving` | 进入 Receiving 界面 |

### 设计原则（关键，不用坐标）

- 全部用 `resource-id` / XPATH class+text 定位，**不用屏幕坐标**
- 输入后 `hide_keyboard()` 避免键盘遮挡
- 点击 React Native 按钮时找 `clickable=true` 的 ViewGroup 父元素
- 全局处理升级弹窗（"Later" 按钮）

### Skill 位置

`D:\code\kiro-knowledge\skills\wms-app-login\`（全局经验库，挂载后即 `~/.kiro/skills/wms-app-login/`）
- `SKILL.md` — 说明文档  
- `wms_login.py` — Appium Python 脚本

### 首次使用安装依赖

```powershell
pip install Appium-Python-Client selenium
```


切换到 WMS App（`d:\code\WMS-front-end\wms-rn`）时，流程完全一样，替换包名即可：
- Debug 包：`assembleDebug` → `adb install ... app-debug.apk`
- 热更新端口：同样用 8180（或检查 WMS 项目的可用端口）
- 日志过滤：改为 `com.wmsrn` 或 `ReactNativeJS`
