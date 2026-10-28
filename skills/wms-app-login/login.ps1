param(
    [string]$Target = ""   # 可选: consolidation, load-truck, unload-truck
)

$WMS_PKG     = "com.wmsrn"
$WMS_ACT     = "com.wmsrn/.MainActivity"
# 截图/UI dump 输出目录：优先环境变量 WMS_SCREENSHOT_DIR，否则用当前目录（主工作空间根）下的 docs\tmp\wms_test
$SCREENSHOT_DIR = if ($env:WMS_SCREENSHOT_DIR) { $env:WMS_SCREENSHOT_DIR } else { Join-Path (Get-Location) "docs\tmp\wms_test" }
New-Item -ItemType Directory -Force -Path $SCREENSHOT_DIR | Out-Null
# 账号密码从环境变量读取，不在脚本中保存明文
$USERNAME    = $env:WMS_APP_USER
$PASSWORD    = $env:WMS_APP_PASSWORD
if ([string]::IsNullOrEmpty($USERNAME) -or [string]::IsNullOrEmpty($PASSWORD)) {
    Write-Host "❌ 缺少环境变量 WMS_APP_USER / WMS_APP_PASSWORD"
    exit 1
}

# 屏幕分辨率 720x1344 下的坐标（如换设备需重新 dump）
$USER_INPUT_X  = 392; $USER_INPUT_Y  = 656
$PASS_INPUT_X  = 348; $PASS_INPUT_Y  = 816
$LOGIN_BTN_X   = 360; $LOGIN_BTN_Y   = 976

function Screenshot($name) {
    adb shell screencap -p /sdcard/s.png | Out-Null
    adb pull /sdcard/s.png "$SCREENSHOT_DIR\$name.png" | Out-Null
    Write-Host "📸 截图: $SCREENSHOT_DIR\$name.png"
}

function DumpUI($name) {
    adb shell uiautomator dump /sdcard/ui.xml | Out-Null
    adb pull /sdcard/ui.xml "$SCREENSHOT_DIR\$name.xml" | Out-Null
}

function GetNodeBounds($xmlPath, $keyword) {
    $content = Get-Content $xmlPath -Raw
    $pattern = "text=""$keyword""[^>]+bounds=""(\[\d+,\d+\]\[\d+,\d+\])"
    if ($content -match $pattern) {
        $bounds = $Matches[1]  # [x1,y1][x2,y2]
        if ($bounds -match "\[(\d+),(\d+)\]\[(\d+),(\d+)\]") {
            $cx = ([int]$Matches[1] + [int]$Matches[3]) / 2
            $cy = ([int]$Matches[2] + [int]$Matches[4]) / 2
            return @{ x = [int]$cx; y = [int]$cy; found = $true }
        }
    }
    return @{ found = $false }
}

function TapByResourceId($xmlPath, $resId) {
    $content = Get-Content $xmlPath -Raw
    $pattern = "resource-id=""$resId""[^>]+bounds=""(\[\d+,\d+\]\[\d+,\d+\])"
    if ($content -match $pattern) {
        $bounds = $Matches[1]
        if ($bounds -match "\[(\d+),(\d+)\]\[(\d+),(\d+)\]") {
            $cx = ([int]$Matches[1] + [int]$Matches[3]) / 2
            $cy = ([int]$Matches[2] + [int]$Matches[4]) / 2
            adb shell input tap $cx $cy | Out-Null
            return $true
        }
    }
    return $false
}

Write-Host "🚀 启动 WMS App..."
adb shell am force-stop $WMS_PKG | Out-Null
Start-Sleep -Seconds 1
adb shell am start -n $WMS_ACT | Out-Null
Start-Sleep -Seconds 3

Screenshot "01_startup"

Write-Host "⌨️  输入用户名: $USERNAME"
adb shell input tap $USER_INPUT_X $USER_INPUT_Y | Out-Null
Start-Sleep -Milliseconds 600
adb shell input keyevent 123  # KEYCODE_MOVE_END
adb shell input keyevent --longpress 67  # 长按 BACKSPACE 清空（退而求其次）
# 更可靠的清空方式：全选后删除
adb shell input keyevent 277  # KEYCODE_CTRL_A (select all)
Start-Sleep -Milliseconds 200
adb shell input text $USERNAME | Out-Null
Start-Sleep -Milliseconds 400

Write-Host "🔑 输入密码"
adb shell input tap $PASS_INPUT_X $PASS_INPUT_Y | Out-Null
Start-Sleep -Milliseconds 600
adb shell input keyevent 277  # KEYCODE_CTRL_A select all
Start-Sleep -Milliseconds 200

# 密码可能含 @ 特殊字符，adb input text 不支持直接输入 @
# 方案：按 @ 分段输入，段与段之间用 keyevent 打 @（keycode 77 = AT，即 @）
$KEYCODE_AT = 77
$pwdSegments = $PASSWORD.Split('@')
for ($i = 0; $i -lt $pwdSegments.Length; $i++) {
    if ($i -gt 0) {
        adb shell input keyevent $KEYCODE_AT | Out-Null
        Start-Sleep -Milliseconds 200
    }
    if ($pwdSegments[$i] -ne "") {
        adb shell input text $pwdSegments[$i] | Out-Null
        Start-Sleep -Milliseconds 200
    }
}
Start-Sleep -Milliseconds 200
Screenshot "02_input_done"

Write-Host "🖱️  点击 Login 按钮"
# 优先用 resource-id 定位，更稳定
DumpUI "login_page_dump"
$tapped = TapByResourceId "$SCREENSHOT_DIR\login_page_dump.xml" "login-button"
if (-not $tapped) {
    Write-Host "  ⚠️  resource-id 未找到，用坐标点击"
    adb shell input tap $LOGIN_BTN_X $LOGIN_BTN_Y | Out-Null
}
Start-Sleep -Seconds 5

Screenshot "03_after_login"
DumpUI "after_login_dump"

# 检查登录是否成功
$uiContent = Get-Content "$SCREENSHOT_DIR\after_login_dump.xml" -Raw
if ($uiContent -match "Home|NJ|Consolidation|Receiving") {
    Write-Host "✅ 登录成功！当前已进入主页"
} elseif ($uiContent -match "User|password|Login") {
    Write-Host "❌ 登录失败，仍在登录页，请检查账号密码或 Metro 是否启动"
    exit 1
} elseif ($uiContent -match "Select.*Warehouse|仓库") {
    Write-Host "⚠️  需要选择仓库，尝试选择 NJ..."
    $njPos = GetNodeBounds "$SCREENSHOT_DIR\after_login_dump.xml" "NJ"
    if ($njPos.found) {
        adb shell input tap $njPos.x $njPos.y | Out-Null
        Start-Sleep -Seconds 2
        Screenshot "04_warehouse_selected"
        Write-Host "✅ 已选择 NJ 仓"
    } else {
        Write-Host "  未找到 NJ，请手动选择仓库"
    }
} else {
    Write-Host "⚠️  登录状态未知，截图已保存，请查看: $SCREENSHOT_DIR\03_after_login.png"
}

# ── 导航到目标界面 ──────────────────────────────
if ($Target -eq "") { exit 0 }

Write-Host ""
Write-Host "🧭 导航到: $Target"

DumpUI "home_dump"
$homeUI = Get-Content "$SCREENSHOT_DIR\home_dump.xml" -Raw

switch ($Target) {
    "consolidation" {
        $pos = GetNodeBounds "$SCREENSHOT_DIR\home_dump.xml" "Consolidation"
        if ($pos.found) {
            adb shell input tap $pos.x $pos.y | Out-Null
            Start-Sleep -Seconds 2
            Screenshot "05_consolidation"
            Write-Host "✅ 已进入 Consolidation"
        } else {
            Write-Host "❌ 未找到 Consolidation 入口，请检查截图"
        }
    }
    "load-truck" {
        # 先进 Consolidation
        $pos = GetNodeBounds "$SCREENSHOT_DIR\home_dump.xml" "Consolidation"
        if ($pos.found) {
            adb shell input tap $pos.x $pos.y | Out-Null
            Start-Sleep -Seconds 2
            DumpUI "consolidation_dump"
            $loadPos = GetNodeBounds "$SCREENSHOT_DIR\consolidation_dump.xml" "Load Truck"
            if ($loadPos.found) {
                adb shell input tap $loadPos.x $loadPos.y | Out-Null
                Start-Sleep -Seconds 2
                Screenshot "05_load_truck"
                Write-Host "✅ 已进入 Load Truck"
            } else {
                Write-Host "❌ 未找到 Load Truck 入口"
            }
        }
    }
    "unload-truck" {
        $pos = GetNodeBounds "$SCREENSHOT_DIR\home_dump.xml" "Consolidation"
        if ($pos.found) {
            adb shell input tap $pos.x $pos.y | Out-Null
            Start-Sleep -Seconds 2
            DumpUI "consolidation_dump"
            $unloadPos = GetNodeBounds "$SCREENSHOT_DIR\consolidation_dump.xml" "Unload Truck"
            if ($unloadPos.found) {
                adb shell input tap $unloadPos.x $unloadPos.y | Out-Null
                Start-Sleep -Seconds 2
                Screenshot "05_unload_truck"
                Write-Host "✅ 已进入 Unload Truck"
            } else {
                Write-Host "❌ 未找到 Unload Truck 入口"
            }
        }
    }
    default {
        Write-Host "⚠️  未知目标: $Target（可选: consolidation, load-truck, unload-truck）"
    }
}
