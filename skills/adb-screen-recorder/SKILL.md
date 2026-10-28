---
name: adb-screen-recorder
description: 通过 adb 录制已连接 Android 设备（手机/PDA）屏幕操作视频，无需 Appium/Root，适用 WMS App、Picking App 操作演示。触发词：录制视频, 录屏, 录制操作, screenrecord, adb 录制, 录制 app, 录制演示, record screen
---
# Skill: adb-screen-recorder

## 用途
通过 adb 录制已连接 Android 设备（手机/PDA）的屏幕操作视频，无需 Appium、无需 Root。
适用于录制 WMS App、Picking App 等任意安卓应用的操作演示视频。

---

## 触发词
录制视频, 录屏, 录制操作, screenrecord, adb 录制, 录制 app, 录制演示, record screen

---

## 前置条件

1. **adb 已连接设备**：运行 `adb devices` 确认设备在线
2. **手机已解锁**：录制期间保持屏幕亮起
3. **存储空间**：设备 /sdcard 至少有 200MB 空闲空间

---

## 标准流程

### 第一步：确认设备连接
```powershell
adb devices
```
期望输出包含 `device`（不是 `offline` 或 `unauthorized`）。

### 第二步：清理旧文件（可选）
```powershell
adb shell "rm -f /sdcard/<文件名>.mp4"
```

### 第三步：后台启动录制
使用 `control_pwsh_process` 工具（action: start）启动后台进程：
```
command: adb shell screenrecord --bit-rate 4000000 /sdcard/<文件名>.mp4
```
> ⚠️ **必须用后台进程启动**，不能用普通 execute_pwsh（会阻塞等待）

### 第四步：等待用户操作
告知用户：
- 🔴 录制已开始，请在手机上操作
- 操作完成后说"**停止录制**"
- 最长 **3 分钟**自动停止（screenrecord 限制）
- 超过 3 分钟需重新录制

### 第五步：停止录制
用户说停止后，使用 `control_pwsh_process`（action: stop）终止进程，再等待 1 秒：
```powershell
Start-Sleep -Seconds 1
adb shell ls -lh /sdcard/<文件名>.mp4  # 确认文件存在
```

### 第六步：拉取视频到本地
```powershell
New-Item -ItemType Directory -Force -Path "<本地目标目录>"
adb pull /sdcard/<文件名>.mp4 "<本地目标路径>/<文件名>.mp4"
```

### 第七步：清理设备上的临时文件（可选）
```powershell
adb shell "rm -f /sdcard/<文件名>.mp4"
```

---

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--bit-rate` | `4000000`（4Mbps） | 视频码率，越高画质越好、文件越大 |
| `--size` | 不设置（使用设备分辨率） | 可指定如 `1080x1920` |
| `--time-limit` | 180（3分钟） | 最长录制秒数，最大 180 |

调整码率示例：
- 高质量演示：`--bit-rate 8000000`（8Mbps）
- 小文件快速分享：`--bit-rate 2000000`（2Mbps）

---

## 默认存储路径规范

| 用途 | 本地保存路径 |
|------|------------|
| WMS App 演示 | `<主工作空间>\docs\tmp\wms_test\wms_con\` |
| 临时录制 | `<主工作空间>\docs\tmp\wms_test\` |
| 其他（按用途命名） | `<主工作空间>\docs\tmp\wms_test\<子目录>\` |

`<主工作空间>` 指当前第一个 workspace folder（与 global_guide 规则 8 一致）。目录不存在时先 `New-Item -ItemType Directory -Force <目录>`，否则 adb pull 会失败。

文件命名建议：`<功能描述>_<日期>.mp4`，如 `consolidation_flow_20260919.mp4`

---

## 完整示例对话

```
用户：帮我录制一下 WMS App 的 Unload Truck 操作

AI执行：
1. adb devices → 确认设备在线
2. adb shell rm -f /sdcard/unload_demo.mp4
3. [后台启动] adb shell screenrecord --bit-rate 4000000 /sdcard/unload_demo.mp4
4. 告知用户：🔴 录制已开始，操作完成后说"停止录制"
5. [用户操作手机...]
6. 用户说"停止录制"
7. [停止后台进程]
8. Start-Sleep 1 → 确认文件大小
9. adb pull → 保存到本地
10. 告知用户：✅ 视频已保存到 <主工作空间>\docs\tmp\wms_test\wms_con\unload_demo.mp4
```

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 文件大小为 0 或极小 | 进程被立即终止 | 确认后台进程正常启动，等待至少 2 秒再停止 |
| `unable to open /sdcard/xxx.mp4` | 存储权限问题 | 检查 adb shell 是否有 sdcard 写权限 |
| 视频画面黑屏 | 录制期间屏幕锁定 | 保持屏幕常亮，关闭自动锁屏 |
| 3 分钟不够用 | screenrecord 限制 | 分段录制，每段 3 分钟内，结束后 pull 再重新开始 |
| `adb: not found` | adb 未加入 PATH | 使用完整路径或先配置 Android SDK PATH |
