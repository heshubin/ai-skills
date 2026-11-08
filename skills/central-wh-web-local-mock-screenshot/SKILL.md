---
name: central-wh-web-local-mock-screenshot
description: 不启动后端、不碰 gqc/生产，在本机打开 central-wh-web（AngularJS，wh 模块）页面并用 Playwright 假数据截图验证。适用 worktree 里改了 orderRecord 等页面要截图时。触发词：central-wh-web 截图, wh 页面本地验证, page.route mock, 本地起 central, orderRecord 截图, Batch Manage 截图
---

# central-wh-web 本机假数据截图（2026-11-08，Bug#10874 实测一次跑通）

## 关键事实
- `app/wh/index.html` 依赖 `../hub2/`（被 .gitignore 排除，只在主仓库 `d:/code/central-wh-web/app/hub2`）和 `../../bower_components/`（主仓库根目录）。worktree 里没有这两个目录。
- hub2 的 `config.js` 默认就是 GQC（`COMMON_SERVICE_HOST: https://gqc-centralapi.yamibuy.tech/`），wh 的 `js/config.js` 也是 GQC，不需要改文件。
- 登录判定只看 `localStorageService.get('token') != null`，angular-local-storage 前缀是 `ls.`：在 `addInitScript` 里写 `localStorage.setItem('ls.token', '"mock-token"')` 即可免登录。
- 端口 63342 常被 IDE 占用，换别的端口（如 18342），`HTTP_HOST` 不影响页面渲染。
- Playwright MCP 的 `browser_run_code_unsafe` 里没有 `require`/`process`，不能直接读本地文件，所以静态文件要靠本机 node 服务。
- `globalThis` 在两次 `browser_run_code_unsafe` 之间不共享，日志要在同一次调用里返回。

## 步骤
1. 后台起只读静态服务（`node -e` 直接跑，不落脚本文件），只监听 127.0.0.1，路径映射：
   - `/central/app/hub2/*` → 主仓库 `app/hub2`
   - `/central/bower_components/*` → 主仓库 `bower_components`
   - `/central/app/*` → worktree 的 `app`
2. Playwright：`page.route('**/*')`，本机地址 `route.continue()`；`gqc-centralapi.yamibuy.tech` 一律 `route.fulfill` 本地假数据（`{messageId:10000, body}`，带 CORS 头，OPTIONS 回 204）；其他域名 `route.abort()`。这样没有任何请求离开本机。
3. 打开 `http://localhost:<端口>/central/app/wh/index.html#/wh/orderRecord`，点 tab 文字（英文）如 `Batch Manage`。
4. orderRecord 页加载时会请求：`inventory/inventoryWH/queryAllWarehourseSimpleList`（仓库列表，给 `isCurrentWarehouse:'true'`）、`wms/api/v1/zone/switch`（`{zone_picking_enabled, phase2_enabled}`）、`wms/zone-batch-manage/list`（BaseResponsePage）、`wms/zone-batch-manage/counts`、`wms/batch/queryPoolOrderInfos` 等；其余接口回 `body: []` 不影响 Batch 页。
5. 截图前先用 `page.evaluate` 量 DOM（文字、`getBoundingClientRect`），确认数据和对齐，再截 1 张。视口 1700 宽时 Batch 表的 Volume/Action 列在横向滚动区外，需要看最右列时把视口加宽或先横向滚动。
6. 结束：关浏览器，`netstat -ano | findstr 127.0.0.1:<端口>` 找 PID 后 `taskkill`。
