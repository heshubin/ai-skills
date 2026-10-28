---
inclusion: fileMatch
fileMatchPattern: '**/*.{ts,tsx,jsx,less,scss,css}'
---
# UmiJS + web-core Portal 项目开发规范

适用于基于 UmiJS Max + `@yami/admin-web-core` + `@yami/biz-common` 的 Yami 中后台管理系统（Portal / Admin）项目。以 `web-core/apps/umi-demo` 为参考实现。

判断是否适用：项目依赖中包含 `@umijs/max` 或 `@yami/admin-web-core` 或 `@yami/biz-common` 时，本规范生效。C 端项目（ec-website、ec-mobilesite 等）不适用。

---

## 1. UmiJS 使用规范

### 运行时配置（app.tsx）

- `app.tsx` 是唯一的运行时配置入口，禁止在其他文件中导出 `getInitialState`、`layout`、`request`、`rootContainer` 等运行时 API
- `request` 配置必须使用 `createUmiRequestConfig()` 工厂函数，禁止自行拼装拦截器
- `rootContainer` 必须包裹 `BizConfigProvider` → `AuthProvider` 的嵌套结构，顺序不可颠倒
- `render` 函数中，公开页面（登录、OAuth 回调、500）必须直接 `oldRender()` 跳过权限加载
- `render` 函数中必须调用 `setGlobalBizConfig()` 初始化全局单例，在 `getPermissions()` 之前

### 路由

- 静态路由定义在 `config/routes.ts`，禁止在页面组件中硬编码路由跳转路径
- 公开页面路由必须设置 `layout: false`
- 动态路由通过 `patchClientRoutes` 注入，数据来源为后端权限菜单（`MenuTreeNode[]`）
- 动态页面组件必须使用 `React.lazy(() => import('@/pages/xxx'))` 加载，配合 `Suspense` 兜底

### 构建配置（config/config.ts）

- 全局变量通过 `define` 注入，禁止在业务代码中使用 `process.env` 读取自定义变量
- `define` 中声明的变量必须在 `typings.d.ts` 中补充全局类型声明
- 开发环境 `alias` 指向包源码路径（`packages/*/src/index.ts`），确保热更新生效
- 调试 workspace 包时必须设置 `mfsu: false`
- 代理配置集中在 `config/proxy.ts`，按环境分组（dev / test / pre）

### 国际化

- UmiJS 内置 `locale` 插件管理应用级翻译，资源文件放 `src/locales/`
- 页面中使用 `useIntl()` 获取翻译函数，禁止直接 `import` locale 文件做字符串拼接
- 语言切换时必须同时调用 `setLocale(lang, false)` 和 `dispatchLocaleChange()`，同步 UmiJS 与 web-core 两套体系
- 动态菜单的国际化通过 `localesLoader(menus)` 注入，在 `render` 函数中权限加载后执行

### ProLayout

- 布局配置通过 `layout` 运行时导出，默认主题设置集中在 `config/defaultSettings.ts`
- `actionsRender` 中使用 `@yami/biz-common` 提供的布局组件（`OrganizationSelector`、`ThemeSelector`）
- `avatarProps` 中使用 `AvatarDropdown`、`AvatarName`、`UserAvatar`，退出登录通过 `onLogoutRedirect` 回调跳转
- `footerRender` 使用 `<Footer />`，禁止各项目自行实现页脚

### 页面与组件

- 页面文件放 `src/pages/`，按功能模块建子目录
- 应用级组件（依赖 `@umijs/max` 的）放 `src/components/`
- 工具函数放 `src/util/`
- 禁止在页面中直接 `import` `@umijs/max` 的内部模块（如 `@@/`），只用公开 API

---

## 2. web-core 使用规范

### @yami/admin-web-core

- 必须通过 `BizConfigProvider` 注入 `request`、`locale`、`message`，禁止在业务组件中直接 `import` 全局单例函数做请求
- `setGlobalBizConfig()` 仅在 `app.tsx` 的 `render` 函数中调用一次，禁止多处调用或运行时动态修改
- Token 管理统一使用 `getToken()` / `setToken()` / `clearToken()`，禁止直接操作 `localStorage.getItem('token')`
- 请求适配器自动处理 Token 注入和业务错误码，禁止在页面中重复实现 Token 拦截或错误弹窗逻辑
- `ApiResponse<T>` 是标准响应类型，业务数据从 `resp.body` 取，禁止自定义响应包装类型
- 公开接口（无需 Token）在 `RequestOptions` 中设置 `skipAuth: true`

### @yami/biz-common

- 认证页面必须使用 `AuthPage` 组件，通过 `portalConfig` 配置登录方式（密码、Google OAuth、注册），禁止自行实现登录表单
- `AuthProvider` 必须包裹在 `BizConfigProvider` 内部，公开页面设置 `autoFetch={false}` 跳过用户信息获取
- 用户信息通过 `useAuthContext()` 获取，禁止自行维护用户状态或重复请求用户接口
- 权限菜单通过 `getPermissions()` 获取，返回 `AuthPermissionInfo`，菜单树为 `MenuTreeNode[]`
- 布局组件（`AvatarDropdown`、`Footer`、`ThemeSelector`、`OrganizationSelector`）从 `@yami/biz-common` 导入，禁止各项目重复实现
- 权限控制使用 `<Authorized>` 组件包裹受保护内容

### 类型使用

- 从 `@yami/admin-web-core` 导入：`ApiResponse`、`Locale`、`RequestFunction`、`BizConfigProps`
- 从 `@yami/biz-common` 导入：`MenuTreeNode`、`AuthPermissionInfo`、`AuthUserInfo`、`LoginCredentials`
- 禁止在业务项目中重新定义这些类型，必须从包中导入

---

## 3. 公开页面处理

- 公开页面路径集中定义为常量数组 `PUBLIC_PATHS`，通过 `isPublicPage()` 判断
- 公开页面必须满足三个条件：路由 `layout: false`、`AuthProvider` 的 `autoFetch={false}`、`render` 中直接 `oldRender()`
- 新增公开页面时必须同步更新 `PUBLIC_PATHS`

---

## 4. 禁止项

- 禁止绕过 `createUmiRequestConfig()` 自行配置请求拦截器
- 禁止在 `BizConfigProvider` 外部使用 `@yami/biz-common` 的组件或 hooks
- 禁止在多处调用 `setGlobalBizConfig()`
- 禁止直接操作 `localStorage` 管理 Token
- 禁止自行实现登录表单、退出登录、密码重置等认证流程
- 禁止在页面中重复实现请求错误处理（已由适配器统一处理）
- 禁止重新定义 `@yami/*` 包已导出的类型
- 禁止在 `config.ts` 的 `define` 中声明变量后不在 `typings.d.ts` 中补类型
- 禁止语言切换时只调 `setLocale` 不调 `dispatchLocaleChange()`
