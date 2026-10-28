---
name: android-screenshot
description: 安全截取并查看 Android 设备（手机/PDA）当前界面，避免 PowerShell 重定向导致 PNG 损坏；用于验证 App 页面效果、调试 UI。触发词：截图, 截个图, 看一下 App 界面, 看看效果, screencap, adb 截图, 手机截图, PDA 截图
---
# Android 设备截图查看技能

## 触发时机
- 需要查看 Android 设备（手机/PDA）当前界面时
- 测试验证 App 页面效果、调试 UI 问题时
- 用户说"看一下 App 界面"、"截个图"、"看看效果"时

## ⚠️ 关键规则（必须遵守，否则图片损坏）

### ❌ 禁止方式
```powershell
# 这种方式在 Windows PowerShell 下会因编码问题导致 PNG 文件损坏
adb exec-out screencap -p > screen.png
```

### ✅ 正确方式
```powershell
# 步骤1：截图保存到设备
adb shell screencap -p /sdcard/screen_now.png

# 步骤2：从设备 pull 到本地（<主工作空间> = 当前第一个 workspace folder，目录不存在时 adb pull 会失败）
New-Item -ItemType Directory -Force "<主工作空间>\docs\tmp\picking_test\screenshots" | Out-Null
adb pull /sdcard/screen_now.png "<主工作空间>\docs\tmp\picking_test\screenshots\screen_now.png"
```

## 完整流程

### Step 1：截图
```powershell
adb shell screencap -p /sdcard/screen_now.png
New-Item -ItemType Directory -Force "<主工作空间>\docs\tmp\picking_test\screenshots" | Out-Null
adb pull /sdcard/screen_now.png "<主工作空间>\docs\tmp\picking_test\screenshots\screen_now.png"
```

### Step 2：验证文件（可选，排查问题时用）
```powershell
$bytes = [System.IO.File]::ReadAllBytes("<主工作空间>\docs\tmp\picking_test\screenshots\screen_now.png")
$header = $bytes[0..3] | ForEach-Object { $_.ToString("X2") }
Write-Host "PNG头: $($header -join ' ')"
# 正确输出应为: 89 50 4E 47
```

### Step 3：启动 HTTP Server（如果还没启动）
```powershell
# 后台启动，端口 9988，目录指向截图文件夹
# 使用 control_pwsh_process start 启动
python -m http.server 9988 --directory "<主工作空间>\docs\tmp\picking_test\screenshots"
```

### Step 4：用 Playwright 打开查看
```
browser_navigate: http://localhost:9988/screen_now.png
browser_take_screenshot
```

## 截图存储规则

| App | 存储目录 |
|-----|---------|
| Picking App (com.picking) | `<主工作空间>\docs\tmp\picking_test\screenshots\` |
| WMS App (com.wmsrn) | `<主工作空间>\docs\tmp\wms_test\` |

- `<主工作空间>` 指当前第一个 workspace folder（与 global_guide 规则 8 一致），截图属一次性中间数据，放 `docs\tmp\`

- 文件名统一使用 `screen_now.png`（当前界面）
- 历史对比截图使用有意义的名称，如 `screen_before_fix.png`

## 多设备场景
```powershell
# 查看连接的设备
adb devices

# 指定设备截图
adb -s <device_id> shell screencap -p /sdcard/screen_now.png
adb -s <device_id> pull /sdcard/screen_now.png "目标路径"
```

## HTTP Server 复用
- 同一会话内 HTTP Server 只需启动一次（端口 9988）
- 每次截新图后直接刷新 `http://localhost:9988/screen_now.png` 即可
- 会话结束后 stop 掉 process

## 常见错误排查

| 现象 | 原因 | 解决 |
|------|------|------|
| PIL UnidentifiedImageError | 用了 `exec-out` 导致编码损坏 | 改用 `shell screencap + pull` |
| 文件头不是 `89 50 4E 47` | 同上 | 同上 |
| 图片显示空白/broken icon | HTTP server 未启动或端口被占 | 重启 server |
| 图片全黑 | 设备锁屏 | 解锁后重新截图 |
