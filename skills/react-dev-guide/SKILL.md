---
name: react-dev-guide
description: 开发或审查 React Web 页面/组件、排查渲染性能问题时使用，涵盖组件设计、状态管理、Hooks 最佳实践。触发词：react, 组件, hooks, 状态管理, react web, 渲染性能, useEffect
---
# React 开发规范指南

开发 React Web 项目时使用。涵盖组件设计、状态管理、性能优化、Hooks 最佳实践。

## 触发场景

- 开发 React Web 页面或组件
- 审查 React 代码变更
- 排查 React 渲染性能问题
- 提到"react"、"组件"、"hooks"、"状态管理"、"react web"时

## 组件设计原则

### 函数组件优先
- 始终使用函数组件 + Hooks，不使用 Class 组件
- 每个组件文件只导出一个组件

### 组件拆分标准
- 单个组件不超过 300 行
- 超过 3 层嵌套的 JSX 应拆分子组件
- 可复用的 UI 片段抽取为独立组件
- 业务逻辑抽取为自定义 Hook

```tsx
// ✅ 推荐：逻辑与视图分离
function useLotInventory(warehouseId: string) {
  const [data, setData] = useState<LotInventory[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await lotApi.getInventory(warehouseId);
      setData(result);
    } finally {
      setLoading(false);
    }
  }, [warehouseId]);

  return { data, loading, fetchData };
}

// 组件只负责渲染
function LotInventoryTable({ warehouseId }: Props) {
  const { data, loading, fetchData } = useLotInventory(warehouseId);
  // ...渲染逻辑
}
```

## Hooks 最佳实践

### useState
- 相关联的状态合并为一个对象，避免过多独立 state
- 复杂状态逻辑使用 useReducer

### useEffect
- 每个 effect 只做一件事
- 必须正确声明依赖数组
- 需要清理的副作用必须返回 cleanup 函数
- 避免在 effect 中直接修改 state 导致无限循环

```tsx
// ❌ 错误：缺少依赖
useEffect(() => {
  fetchData(warehouseId);
}, []); // warehouseId 变化时不会重新请求

// ✅ 正确
useEffect(() => {
  fetchData(warehouseId);
}, [warehouseId, fetchData]);
```

### useMemo / useCallback
- 不要过度使用，只在确实有性能问题时才加
- 计算量大的派生数据用 useMemo
- 传给子组件的回调函数用 useCallback（配合 React.memo）

### 自定义 Hook
- 命名以 `use` 开头
- 封装可复用的状态逻辑（数据请求、表单处理、定时器等）
- 一个 Hook 只做一件事

## 状态管理

### 状态分层
```
组件内部状态 → useState / useReducer
跨组件共享   → Context + useReducer / Zustand / Redux
服务端状态   → React Query / SWR
全局配置     → Context（主题、语言、用户信息）
```

### 状态提升原则
- 状态放在需要它的最近公共祖先
- 不要把所有状态都放到全局 store
- 服务端数据优先用 React Query 管理（自带缓存、重试、失效）

## TypeScript 规范

```tsx
// Props 类型定义
interface LotTableProps {
  warehouseId: string;
  onSelect?: (lot: LotMaster) => void;
  className?: string;
}

// 事件处理
const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => { ... };
const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => { ... };

// API 响应类型
interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}
```

## 性能优化

- [ ] 列表渲染使用稳定唯一的 key（不用 index）
- [ ] 大列表使用虚拟滚动（react-virtualized / react-window）
- [ ] 频繁变化的子组件用 React.memo 包裹
- [ ] 避免在 render 中创建新对象/数组作为 props
- [ ] 图片懒加载
- [ ] 路由级别代码分割（React.lazy + Suspense）

```tsx
// ❌ 每次渲染都创建新对象，导致子组件重渲染
<ChildComponent style={{ color: 'red' }} />

// ✅ 提取为常量或 useMemo
const style = useMemo(() => ({ color: 'red' }), []);
<ChildComponent style={style} />
```

## 常见反模式

| 反模式 | 问题 | 正确做法 |
|--------|------|---------|
| Props 透传超过 3 层 | 维护困难 | 使用 Context 或组合模式 |
| useEffect 当 watch 用 | 不必要的渲染 | 在事件处理函数中直接处理 |
| 在 render 中请求数据 | 无限循环 | 在 useEffect 或事件中请求 |
| 条件渲染中使用 Hook | 违反 Hook 规则 | Hook 必须在顶层调用 |
| 直接修改 state 对象 | 不触发重渲染 | 创建新对象/数组 |
