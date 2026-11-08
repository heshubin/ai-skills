---
name: rn-app-emulator-walkthrough
description: 在本机安卓模拟器或真机上，用 adb + Metro + 本地 mock 自动走查 WMS App / Picking App 的页面流程：启动模拟器、装 mock 保证不碰生产、免登录进入页面、模拟扫码与点击输入、截图并和设计稿对比、核对每个请求都走了 mock、按顺序收尾。多个 agent 共用一台设备时的锁与内存规则也在这里。触发词：模拟器走查, 启动模拟器, 安卓模拟器, emulator, 真机走查, 自动操作 App, 模拟扫码, adb 走查, mock 走查, 截图对比设计稿, 设备锁, 360 dp, 窄屏
---

# RN App 模拟器 / 真机自动走查

## 0 原理（没有特殊工具）

全部是现成的东西拼起来的：

| 要做的事 | 用什么 |
|---|---|
| 让 App 跑起来、改代码立刻生效 | 安卓模拟器（或 USB 真机）+ Debug 包 + Metro，经 `adb reverse tcp:8081 tcp:8081` 连本机 |
| 不碰生产、不依赖后端 | 临时挂一个 axios mock adapter：命中的接口本地返回，没命中就抛 `MOCK MISS` |
| 跳过登录 | 开发构建下临时让 `AuthService` 直接返回一个假用户 |
| 操作 App | `adb shell input tap / text / swipe / keyevent`；扫码用 `am broadcast` 模拟扫码枪广播 |
| 看到界面 | `screencap` 存到设备再 `pull`，agent 用 read_file 打开 PNG 看，决定下一步点哪里 |
| 证明没碰生产 | 走查前后各导一次 `logcat`，数 `[MOCK]`、`MOCK MISS`、生产域名 |

agent 的循环就是：截图 → 看图 → 按坐标点 / 广播扫码 → 再截图。

和其他技能的分工：要用真实账号登录真实环境，用 `wms-app-login`（Appium）；只截图用 `android-screenshot`；录屏用 `adb-screen-recorder`。本技能用于「本地 mock、不连后端」的界面走查与验收。

## 1 硬约束（先读 steering `no-production-access`）

- 任何请求都不能发往生产（`centralapi.yamibuy.net` 等）。baseURL 临时改成 gqc，再装「没命中就抛错」的 mock；临时改动一律不提交，走完 `git checkout --` 撤销。
- 记录三个时间，顺序必须是：mock 写入 → Metro 启动 → App 重装。
- 走查前后各导一次 `adb logcat -d -s ReactNativeJS:V`，逐条核对每个请求都有 `[MOCK]`、没有 MOCK MISS、没有生产域名。
- 恢复联网之前先 `adb shell pm clear <包名>`：飞行模式下排队的 Firebase 等埋点事件，联网后会发往线上。

## 2 启动模拟器（本机实测：主人的 Windows 开发机）

```powershell
$sdk = 'D:\ADT\Android\android-sdk-windows'
& "$sdk\emulator\emulator.exe" -list-avds      # Pixel（Android 8.0，1080x1920，420 dpi ≈ 411 dp 宽）、Medium_Phone_API_36.0（更重）
# 默认端口 5554/5555 被 Hyper-V 保留（netsh interface ipv4 show excludedportrange protocol=tcp 可看到 5484–5683），6000 又被本机 postgres 占着
& "$sdk\emulator\emulator.exe" -avd Pixel -memory 2048 -no-boot-anim -no-snapshot-load -no-snapshot-save -no-audio -ports 6200,6201
```

- 用后台进程启动（Kiro 里用 control_pwsh_process start），不要在前台命令里跑。
- 等开机：`adb -s emulator-6200 shell getprop sys.boot_completed` 返回 `1`。设备名是 `emulator-6200`，所有命令都带 `-s emulator-6200`。
- 报 `too many emulator instances` 却一个都没开：端口被保留，换 `-ports`；`Pixel.avd` 下残留的 `*.lock` 在没有模拟器进程时可以删。
- 报 `Failed to load snapshot` 后 adb 一直 offline：加 `-no-snapshot-load` 冷启动。
- 屏幕休眠时冷启动 App，可能弹 LogBox `current activity is null`：先 `input keyevent 224` 亮屏再启动。
- 内存：qemu 约占 2.6 GB。本机曾 3 次因内存耗尽死机，模拟器开着时同一时间只跑 1 个 Maven / Gradle 构建，空闲内存低于 2 GB 就先关模拟器。
- 真机：USB 连上后 `adb devices` 能看到序列号，下面的步骤把 `-s` 换成序列号即可，其余一样（真机通常联网，mock 和 `pm clear` 更要做）。

## 3 装 mock、免登录（临时改动，不提交）

**WMS App（`WMS-front-end/wms-rn`，包名 `com.wmsrn`）**，OP-40026 走查用过的 7 处：
1. 新建 `src/services/api/walkthroughMockAdapter.ts`：axios adapter，按 URL 返回本地数据，命中打 `[MOCK] <method> <url>`，没命中打 `MOCK MISS <url>` 并抛错。至少要接住 `wms/app/getAppVersion/...`（否则会弹升级）。
2. `src/services/api/apiClient.ts`：`axios.create` 时挂上这个 adapter。
3. `src/constants/api.ts`、`src/services/config/ServerConfigService.ts`：默认地址临时改 `https://gqc-centralapi.yamibuy.tech/`。
4. `src/services/auth/AuthService.ts`：`initializeAuthState` 在开发构建下直接返回目标仓（如 002）的假用户。
5. `src/services/api/NetworkService.ts`：开发构建下 `isConnected` 返回 true（模拟器是飞行模式）。
6. `metro.config.js`：在 worktree 里跑、`node_modules` 是目录联接时，`watchFolders`、`nodeModulesPaths` 加上主目录的 `node_modules`。
7. 各场景的临时开关（例如让某个接口返回错误、返回带图片的数据）。

**Picking App（`central-picking-app`，包名 `com.picking`）**：`src/lib/client/instance.ts` 的 baseURL 默认就是生产，临时改 gqc 并在末尾挂同样的 adapter；`metro.config.js` 同第 6 条。

adapter 骨架（临时文件，用完删除）：

```ts
import type { AxiosAdapter, AxiosRequestConfig } from 'axios';

type Handler = (body: unknown) => unknown;
const ROUTES: Array<[RegExp, Handler]> = [
  [/wms\/app\/getAppVersion/, () => ({ messageId: '10000', body: { version: '2.1.4', url: '', forceUpdateFlag: 'N' } })],
  // [/wms\/api\/v1\/zone-truck\/scan-slot/, (b) => ({ messageId: '10000', body: { ... } })],
];

const parse = (cfg: AxiosRequestConfig) => (typeof cfg.data === 'string' ? JSON.parse(cfg.data) : cfg.data);

export const walkthroughMockAdapter: AxiosAdapter = async (cfg) => {
  const url = cfg.url ?? '';
  const hit = ROUTES.find(([re]) => re.test(url));
  if (!hit) {
    console.log(`MOCK MISS ${url}`);
    throw new Error(`MOCK MISS ${url}`);
  }
  console.log(`[MOCK] ${cfg.method} ${url}`);
  return { data: hit[1](parse(cfg)), status: 200, statusText: 'OK', headers: {}, config: cfg };
};
```

技巧：
- mock 数据按「一个完整业务场景」准备（例如 1 个 Group 车、2 个成员 Tote、4 行拣货），走查才能一路走到完成页。
- 图片可以放在 worktree 里，经 Metro 用 `http://localhost:8081/assets/...` 访问。
- 改 mock 配置会触发整包重载，Debug 包偶尔闪退（react-native-vision-camera 的竞态，与业务无关），冷启动即可。

## 4 Metro 与安装 App

```powershell
# 在 worktree 的 App 目录（wms-rn 或 picking app 根目录）
npx react-native start --reset-cache          # 后台进程；输出存日志文件
adb -s emulator-6200 reverse tcp:8081 tcp:8081
```

- 优先复用已有 Debug APK，不跑 Gradle（纯 JS 改动都由 Metro 热更新）：设备上已装过就 `adb shell pm path com.wmsrn` 找到 `base.apk` 并 `pull` 存一份，之后每轮 `adb install -r` 它；只有原生改动或设备上没装才跑 Gradle（构建槽规则见第 8 节）。
- Picking App 首次装好后，如果连不上 Metro，可用 `run-as com.picking` 写 `debug_http_host = localhost:8081`。WMS App（`com.wmsrn`）同理：`pm clear` 之后重装会丢这项，App 报 `Unable to load script` 且 Metro 日志没有 BUNDLE 行时，push 一个 `shared_prefs/com.wmsrn_preferences.xml`（`<string name="debug_http_host">localhost:8081</string>`）再 `run-as com.wmsrn cp` 进去（10816 实测）。
- worktree 里启动 Metro 时盘符要用大写 `D:\`（`cd /d D:\code\...`）。用小写 `d:\` 启动、而 `metro.config.js` 的 watchFolders 写 `D:/` 时，Metro 报 `Unable to resolve module @babel/runtime/helpers/interopRequireDefault`，文件明明存在（10816 实测）。
- 记重装时间：`adb shell dumpsys package com.wmsrn` 里的 `lastUpdateTime`（GMT）。
- 启动：`adb shell monkey -p com.wmsrn -c android.intent.category.LAUNCHER 1`（或 `am start`）；冷启动前先 `am force-stop`。
- npx 往 stderr 打 `npm warn ...` 时，PowerShell 把它当错误打断管道：先重定向到文件，再读文件。

## 5 操作 App

| 动作 | 命令（都加 `adb -s emulator-6200 shell`） |
|---|---|
| 扫码（WMS App） | `am broadcast -a android.intent.ACTION_DECODE_DATA --es barcode_string <码>`（`ScannerConfigService` 默认值；App 里改过扫码设置就以当前值为准） |
| 点击 | `input tap <x> <y>`：坐标是截图像素（1080x1920），从上一张截图量 |
| 精确找控件 | `uiautomator dump /sdcard/ui.xml` 再 `pull`，按 `text` / `resource-id` 读 `bounds` |
| 输入 | `input text T50432`（空格写成 `%s`），再 `input tap` 点 Submit |
| 滑动 | `input swipe 540 1450 540 950 400`（上滑看下面的内容） |
| 返回 / 亮屏 | `input keyevent 4` / `input keyevent 224` |
| 模拟 360 dp 窄屏（CT58S） | `wm density 480`（1080 px 宽 → 360 dp），拍完 `wm density reset` |

- 两次扫码广播至少隔 2.5 秒：`BroadcastScanner` 丢弃 2 秒内的第二次扫码，换步骤后 300 ms 内的也丢弃。
- 扫码和手输各走一次，两条入口都要验。

## 6 看结果、和设计稿对比

- 截图：`adb shell screencap -p /sdcard/x.png` 再 `adb pull /sdcard/x.png <本地路径>`，不要用 PowerShell 重定向 `exec-out`（PNG 会写坏）。每张都用 read_file 打开看：页面对不对、有没有数据、有没有空白、乱码、灰框、被底栏挡住。
- 设计稿（WMS 手持原型 http://98.152.200.34:2027/warehouse-mobile/#/preview）：用独立的 playwright-core 会话截 `.device-app` 元素（360x720）；多个 agent 共用 Playwright MCP 浏览器会互相改页面状态（hub #193）。
- 报告里放「设计稿 / App」并排表：每屏写清沿用了什么、哪里做得更好、哪里按 App 风格改了。
- 请求核对：走查前 `logcat -G 16M` 加大缓冲，前后各 `logcat -d -s ReactNativeJS:V > <文件>`，统计 `[API Request]`、`[MOCK]`、`MOCK MISS`、生产域名四个数。
- `Pixel`（API 26）模拟器上 `logcat -c` 会报 `failed to clear the 'main' log`，缓冲区清不掉，日志里会混着上一个 App / 上一轮的行。统计时按进程号（logcat 第 3 列）过滤，或者按冷启动后的时间戳截断（OP-40026 版本标识修复轮实测）。

## 7 收尾顺序（顺序错了容易把 adb 拖死）

1. `am force-stop <包名>`（先停 App）
2. `adb reverse --remove-all`
3. 删设备上的临时文件（截图、xml）
4. 最后才停 Metro
5. `git checkout -- <临时改动的文件>`，删 adapter 等新增临时文件，`git status` 干净
6. 要恢复联网前 `pm clear <包名>`
7. 释放设备锁；模拟器由启动它的人关（停后台进程，再查有没有残留的 qemu / emulator 进程和 `Pixel.avd\*.lock`）

原因：Metro 停了以后，Debug 包会不停重连 localhost:8081，这些连接经 adb reverse 涌向已关闭的端口，三次 adb 卡死都发生在这之后。

## 8 稳定性与多人共用

**每条 adb 命令都加超时**，一条挂住不会拖死整个会话：

```powershell
$adb = 'D:\ADT\Android\android-sdk-windows\platform-tools\adb.exe'
function AdbT([string[]]$a, [int]$ms = 30000) {
  $o = Join-Path $env:TEMP ('adbt_' + [guid]::NewGuid().ToString('N') + '.txt'); $e = "$o.err"
  $p = Start-Process -FilePath $adb -ArgumentList $a -NoNewWindow -PassThru -RedirectStandardOutput $o -RedirectStandardError $e
  if ($p.WaitForExit($ms)) { $r = ((Get-Content $o -Raw) + (Get-Content $e -Raw)).Trim() } else { try { $p.Kill() } catch {}; $r = "TIMEOUT: adb $($a -join ' ')" }
  Remove-Item $o, $e -ErrorAction SilentlyContinue; return $r
}
AdbT @('-s','emulator-6200','shell','getprop','sys.boot_completed')
```

**adb 服务卡死**（`adb devices` 都不返回）的恢复：
1. 结束所有 `adb.exe`，`adb start-server`。
2. 非默认端口的模拟器不会被自动发现：`adb connect 127.0.0.1:6201`，之后会同时列出 `127.0.0.1:6201` 和 `emulator-6200`，`adb disconnect 127.0.0.1:6201` 只留一个。
3. 所有 reverse 规则已清空，用 Metro 的要重做 `reverse tcp:8081 tcp:8081`。

**多个 agent / workflow 共用一台设备**：
- 设备锁：用 `New-Item -ItemType Directory <locks>\device.lock` 抢锁（已存在会失败，是原子的），里面写 owner.txt（谁、哪一步、时间）。只有持锁的人能发 adb 命令，连 `adb devices` 都不行；同一时刻只发一条。
- 模拟器只由编排者启动、关闭；其他步骤需要时发 warning 请编排者开，不要自己起第二个。
- 构建槽：模拟器开着时编排者占一个槽，其余步骤同时最多跑 1 个 Maven / Gradle。

**Kiro 终端的坑**：execute_pwsh 遇到较长的命令（循环、sleep、多条 adb）常提前返回 `^C`、退出码 -1，命令其实还在跑。拆成短命令，一条一条执行，再用输出文件、截图或进程列表确认结果。

## 9 走查记录模板（`screens/walkthrough.md`）

1. 时间顺序表：mock 写入、Metro 启动、App 重装（lastUpdateTime）、冷启动、走查前日志、走查、走查后日志、Metro 停止、临时改动撤销、设备收尾。
2. 请求核对表：每个日志文件的 `API Request` / `[MOCK]` / `MOCK MISS` / 生产域名计数，加按接口分类的请求数。
3. 截图清单：文件名 → 屏 → 看点。
4. 与设计稿对照表：设计稿截图 / App 截图 / 沿用 / 做得更好 / 按 App 风格改。
5. 走查中发现的问题（分「业务代码」和「走查环境」两类），以及操作上的偏差（如实记录）。

## 10 已知的环境现象（不是 Bug）

- worktree 里 `node_modules` 用目录联接时，顶栏默认返回箭头的 PNG 显示不出来；真机正式包正常。
- 删除带目录联接的 worktree 前，先用 `cmd /c rmdir <联接>` 删联接本身，否则可能顺着联接删掉主目录的 `node_modules`；PowerShell 5.1 的 `Remove-Item -Recurse` 不要用在联接上。删完用 `(Get-Item <路径> -Force).LinkType` 确认联接已不存在，再 `git worktree remove`，禁止加 `--force`（11/05 `git worktree remove --force` 顺着联接删掉了主目录的 `.bin`、`@babel`、`@eslint` 等，eslint 和 Metro 全部起不来，只能在主仓库 `npm install --no-audit --no-fund` 补齐后撤销 package-lock 改动）。
- Picking App 的 Group 车 mock：`createPickingTask` 返回的 `picking_order` 要带 `tote_no`（Group 的 Tote 由后端预绑），否则 ScanOos / ScanTote 上的 Tote 号是空的（10846 实测）。
- PowerShell 里 `git show <rev>:<file> | npx eslint --stdin` 会把内容按 CRLF 重新拼接，报满屏 `Delete ␍`；要按原始字节检查就用 `cmd /c "git show ... | npx eslint --stdin --stdin-filename <file>"`，前后对比 eslint 数字才可信（10846 实测）。
- 模拟器没有可用相机时，走查拍照功能可以临时把 `launchCamera` 换成返回固定 asset（`file:///sdcard/xxx.jpg`），mock adapter 按调用次数轮换几种响应，一次走查覆盖多个分支（10816 实测）。
- 测「跳页空档里的扫码」时，两条广播间隔太短或撞上页面切换，JS 可能收不到（原生日志有 `Barcode received`，JS 没有 `Received barcode content`）；要以设备 logcat 的时间戳为准判断那次扫码落在哪个页面，必要时重试（10846 B37 实测：拣够后约 100 ms 发 Tote，JS 在 release 之后 1.2 s 才处理，正好落在空档里）。
- 连续广播每步只隔 3 秒时，ScanTote → ScanBin 偶尔读到旧的 locationIndex（报 `WRONG BIN` 但 Expected 是上一行），属于存储写入时序，不是业务改动引起；换行后先截图确认页面再扫。
- 后台起 Metro 用的 `cmd /c "cd /d <worktree> && ..."`，停 Metro 后目录句柄可能还被占着：`git worktree remove` 会卡在 `Deletion of directory ... failed. Should I try again? (y/n)` 等输入，Kiro 终端直到超时。遇到时结束 git 进程，`git worktree prune` 清记录，剩下的空目录等句柄释放后再删（先确认里面已经没有联接）。

## 相关

- steering：`no-production-access`（硬约束）、`android-app-testing`（打包、Metro、logcat、Appium）
- skill：`android-screenshot`、`adb-screen-recorder`、`wms-app-login`、`react-native-dev-guide`
- zone-picking-hub：#190（App 界面改动要求）、#193（原型走查）、#194（浅色卡片不要叠阴影）
- 实例：`d:/code/kiroWP/docs/tmp/OP-40026-bugs/` 下 10801、10805、ui-rework 各批的 `screens/walkthrough.md`
