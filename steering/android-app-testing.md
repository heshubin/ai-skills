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

## 本机安卓模拟器启动踩坑（2026-11-03，主人 Windows 开发机）

- 现象：`emulator -avd Pixel` 报 `It seems too many emulator instances are running on this machine. Aborting.`，可本机一个模拟器都没开。
- 根因：Windows（Hyper-V / WinNAT）把 TCP 端口段保留掉了，`netsh interface ipv4 show excludedportrange protocol=tcp` 能看到 5484–5583、5584–5683 都在保留段里，模拟器默认的 console/adb 端口（5554–5585）一个都绑不上。保留段每次开机可能变化。
- 解法：用 `-ports <console>,<adb>` 指定保留段以外的端口，先用 `netstat -ano` 确认没人占用。6000 被本机 postgres 占着（console 绑不上会打 `bind: not connected`，adb 一直 offline），现在用的是 `-ports 6200,6201`，adb 设备名是 `emulator-6200`。模拟器会警告 adb 端口不在推荐范围，实际能用；如果 `adb devices` 同时列出 `127.0.0.1:6201` 和 `emulator-6200`，`adb disconnect 127.0.0.1:6201` 只留一个。
- 旧快照与新版模拟器不兼容时会报 `Failed to load snapshot 'default_boot'` 然后卡住，adb 一直 offline：加 `-no-snapshot-load` 冷启动。
- 实际用的命令：`D:\ADT\Android\android-sdk-windows\emulator\emulator.exe -avd Pixel -memory 2048 -no-boot-anim -no-snapshot-load -no-snapshot-save -no-audio -ports 6200,6201`（Pixel：Android 8.0、x86、1080x1920；另有 Medium_Phone_API_36.0，更重）。
- 内存：qemu 进程约占 2.6 GB。本机 31 GB 内存，曾 3 次因多个 Maven 全量测试同时跑而死机；模拟器开着时同一时间只跑 1 个 Maven/Gradle 构建。
- 模拟器镜像默认是飞行模式：Metro 用 `adb reverse tcp:8081 tcp:8081` 连，不依赖模拟器联网。

## adb 服务卡死与恢复（2026-11-03/04，模拟器用非默认端口 6200/6201 时）

- 现象：两次在走查收尾时（另一个会话同时在跑 `adb ... pm list packages`），adb 服务对所有命令都不再响应，`adb devices` 也不返回；`reverse --remove-all`、`reverse --remove tcp:8081`、`reverse --list` 全部挂住。模拟器本身正常。
- 恢复：
  1. 结束所有 `adb.exe`（服务和挂起的客户端），`adb start-server`。
  2. 非默认端口的模拟器不会被新服务自动发现（服务只扫 5555–5585）：执行 `adb connect 127.0.0.1:6201`，之后 `adb devices` 会同时列出 `127.0.0.1:6201` 和 `emulator-6200`，再 `adb disconnect 127.0.0.1:6201` 只留 `emulator-6200`。
  3. 重启会清空所有 `adb reverse` 规则，用 Metro 的会话要重新执行 `adb reverse tcp:8081 tcp:8081`。
- 预防：多个会话共用一台设备时，同一时刻只让一个会话发 adb 命令（设备锁）；每条 adb 命令加超时（PowerShell：`Start-Process -PassThru` 加 `WaitForExit(30000)`，超时就 `Kill()`），避免一条挂住的命令把整个会话拖死；不用不带 `-d` 的 `adb logcat`。
- 在 Kiro 的 execute_pwsh 里，含多条 adb 调用的长命令常常提前返回 `^C`、退出码 -1，命令其实仍在跑；拆成短命令分别执行，结果更可靠。
- 第三次卡死（11/04 00:41）后的推测原因：三次都发生在走查收尾、**Metro 已经停掉之后**。RN Debug 包在 Metro 停掉后会持续重连 localhost:8081（packager websocket），这些连接经 `adb reverse tcp:8081 tcp:8081` 涌向已关闭的主机端口，疑似把 adb 服务拖死，之后连 `adb devices` 都不返回。收尾顺序改为：① `adb shell am force-stop <包名>` 先停 App；② `adb reverse --remove-all`；③ 删设备上的临时文件；④ 最后停 Metro。
- 用 mock 走查过的 App，在模拟器恢复联网之前要 `adb shell pm clear <包名>`：离线期间排队的 Firebase 等埋点事件会在联网后发往线上。

## WMS App 模拟器走查踩坑（2026-11-04，OP-40026 B12 批 0/1 走查）

- **模拟扫码的广播参数**：页面用的是 `components/scanner/BroadcastScanner.tsx`，action 和 data key 取 Redux 里的扫码配置，默认值在 `services/scanner/ScannerConfigService.ts`：`android.intent.ACTION_DECODE_DATA` + `barcode_string`。命令：`adb -s emulator-6200 shell am broadcast -a android.intent.ACTION_DECODE_DATA --es barcode_string <码>`。`services/scanner/BroadcastScanner.ts` 里的 `com.android.server.scannerservice.broadcast` / `scannerdata` 是旧类的默认值，页面收不到。两次扫码间隔要大于 2 秒，换步骤后 300 ms 内的扫码会被丢弃。
- **worktree 里起 Metro**：node_modules 是目录联接时，`metro.config.js` 临时加 `resolver.nodeModulesPaths` 与 `watchFolders` 指向主目录 node_modules，路径必须写成大写盘符 `path.resolve('D:/code/WMS-front-end/wms-rn/node_modules')`。写成小写 `d:/...` 会报 `Unable to resolve module @babel/runtime/helpers/interopRequireDefault`（文件明明存在）。改 metro 配置要重启 Metro，重启前先 `am force-stop` App。
- **改 mock 开关会让 Debug 包闪退**：编辑 `zoneMockConfig.ts` 这类非组件模块会触发整包重载，Debug 包随后崩溃（`IllegalStateException: Tried to access a JS module before the React instance was fully set up`，来自 react-native-vision-camera 的 `CameraDevicesManager`）。这是开发重载的竞态，正式包没有热重载、不受影响。改完开关直接重新 `monkey -p com.wmsrn -c android.intent.category.LAUNCHER 1` 冷启动即可。
- **拍"加载中"这类短暂状态**：execute_pwsh 每次调用本身要 3 秒以上，分两次调用拍不到 3 秒的 mock 延迟。要在同一条命令里顺序执行「广播 → `Start-Sleep -Milliseconds 1500` → screencap」（仍是一次只跑一条 adb）。
- **停 Metro**：Metro 是挂在 execute_pwsh 宿主 PowerShell 下的后台进程链（cmd → node → cmd → node）。用 `Stop-Process -Id` 逐个结束这四个 PID；`taskkill /T` 会连带打断当前会话的命令。
- **一屏一条 adb 命令**：并行发两条 tool 调用会让 adb 同时跑两条命令（违反设备锁约定），截图与拉取要分开、按顺序发。

补充（2026-11-04 B12 批 2 第 2 轮走查）：
- **改 mock 开关不闪退的做法**：先 `am force-stop com.wmsrn`，再改 `zoneMockConfig.ts`，再 `monkey` 冷启动。App 不在运行时 Metro 不会推热更新，冷启动直接拿到新包，批 2 两次改开关都没有闪退。收尾撤销临时文件也要在 App 和 Metro 都停了之后做，否则热更新会把生产默认地址推进 App。
- **截图与拉取放进同一条命令**：一条 PowerShell 命令里依次 `Start-Process screencap` → `WaitForExit(30000)` → `Start-Process pull` → `WaitForExit(30000)`，既按顺序只跑一条 adb，又少一次工具调用。
- **execute_pwsh 里的 `Start-Sleep` 容易让调用提前返回 `^C`、退出码 -1**（`Start-Sleep 15`、`Start-Sleep 2` 各一次）。命令其实已经执行。改用 `[System.Threading.Thread]::Sleep(800)` 后没有再出现。遇到 `^C` 先用 `Get-CimInstance Win32_Process -Filter "Name='adb.exe'"` 确认只剩 adb 服务进程，再截图看状态，不要直接重发。
- **拍 3 秒加载态**：mock 延迟 3000 ms 时，在同一条命令里「广播 → `Thread.Sleep(800)` → screencap」，截图结束时离广播约 1 秒，稳定拍到。
- **logcat 缓冲区很小**：`logcat -d` 只留最后几条请求，请求核对要以 Metro 终端日志为准；Metro 运行中日志文件被占用，`ReadAllBytes` 会失败，停 Metro 后再统计。logcat 里的格式是 `'[API Request]', 'POST', ...`，Metro 日志是 `[API Request] POST ...`，正则要分开写。
- **Metro 由上一个步骤启动时**：它的父 PowerShell 已退出，`Stop-Process` 要按 `ParentProcessId` 递归找出整棵 node 进程树（批 2 是 1 个主进程 + 10 个 worker）一起结束，再确认 8081 无监听。
补充（2026-11-04 B12 批 3 走查）：
- **mock 要返回能显示的商品图**：模拟器是飞行模式，也不能请求生产图床。把图片拷进 worktree 的 `wms-rn/walkthrough-tmp/`（临时目录，不提交），mock 返回 `http://localhost:8081/assets/walkthrough-tmp/<名>.png?platform=android`。Metro 0.80 的 `/assets/` 路由按项目根的相对路径直接读文件，不需要 hash；图片经 `adb reverse tcp:8081` 加载。先在本机 `curl` 一次确认 200。FastImage 不走 axios，图片请求不会出现在 `[MOCK]` 日志里，报告里要写明。收尾时连目录一起删掉。
- **冷启动前先确认模拟器亮屏**：息屏时（`dumpsys power` 里 `mWakefulness=Asleep`）`monkey` 冷启动，截图全黑。唤醒后 Debug 包弹 LogBox `Possible unhandled promise rejection: current activity is null`（`AppNavigator.tsx` 的 `applyNavigationBarColor` → `setBarMode`），状态栏变灰。先 `input keyevent 224` 唤醒，再 force-stop、冷启动。
- **共通组件 `ProductTitle` 的样式写死**：13 号、`#333`、居中、不限行数，没有样式参数。放进左对齐的卡片时，会和下面左对齐的字段对不齐；名称很长时会一直撑高卡片。

## 模拟器 / 真机自动走查的完整做法

本机启动模拟器、装 mock 免登录、模拟扫码与点击、截图对比设计稿、核对请求、收尾顺序、adb 卡死恢复、多人共用一台设备的锁规则，都整理在 skill `rn-app-emulator-walkthrough`（`D:\code\kiro-knowledge\skills\rn-app-emulator-walkthrough\SKILL.md`）。要在模拟器上走查页面时先加载它。
