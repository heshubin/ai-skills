---
name: frontend-api-integration
description: React / React Native 项目对接后端 API 时使用，涵盖请求封装、错误处理、状态管理、数据转换。触发词：对接接口, API调用, 请求封装, axios, fetch, 接口错误处理, 前端联调
---
# 前端 API 对接规范

React / React Native 项目对接后端 API 时使用。涵盖请求封装、错误处理、状态管理、数据转换。

## 触发场景

- 前端对接后端 REST 接口
- 封装 API 请求层
- 处理接口错误和异常状态
- 提到"对接接口"、"API调用"、"请求封装"、"axios"、"fetch"时

## 请求层封装

### 基础 Axios 实例
```tsx
import axios, { AxiosError, AxiosRequestConfig } from 'axios';

const request = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截：自动携带 token
request.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截：统一错误处理
request.interceptors.response.use(
  (response) => {
    const { code, message, data } = response.data;
    if (code !== 0) {
      // 业务错误
      return Promise.reject(new BusinessError(code, message));
    }
    return response.data;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // token 过期，跳转登录
      redirectToLogin();
    }
    return Promise.reject(error);
  }
);
```

### API 模块化组织
```
src/api/
├── request.ts          # axios 实例和拦截器
├── types.ts            # 通用类型（ApiResponse、PaginatedData）
├── lot.ts              # 批次相关接口
├── inventory.ts        # 库存相关接口
└── picking.ts          # 拣货相关接口
```

```tsx
// api/lot.ts
import request from './request';
import type { ApiResponse, PaginatedData } from './types';

/** 批次主表 */
export interface LotMaster {
  lotId: number;
  lotNo: string;
  sku: string;
  status: string;
}

/** 查询批次列表 */
export function getLotList(params: {
  page: number;
  pageSize: number;
  warehouseNumber?: string;
  sku?: string;
}): Promise<ApiResponse<PaginatedData<LotMaster>>> {
  return request.get('/api/lot-masters', { params });
}

/** 查询批次详情 */
export function getLotDetail(lotId: number): Promise<ApiResponse<LotMaster>> {
  return request.get(`/api/lot-masters/${lotId}`);
}
```

## 错误处理策略

### 三层错误处理
```
1. 请求层（拦截器）：处理网络错误、401/403、通用业务错误码
2. Hook/Service 层：处理特定业务错误、转换错误信息
3. 组件层：展示错误 UI（Toast、Alert、错误页面）
```

### 错误类型区分
```tsx
// 自定义业务错误
class BusinessError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

// 组件中处理
try {
  await submitReceive(data);
} catch (error) {
  if (error instanceof BusinessError) {
    // 业务错误：展示具体提示
    Toast.show(error.message);
  } else if (axios.isAxiosError(error)) {
    // 网络错误
    Toast.show('网络异常，请检查网络连接');
  } else {
    // 未知错误
    Toast.show('操作失败，请重试');
  }
}
```

## 数据请求 Hook

```tsx
// 通用列表请求 Hook
function usePagedList<T>(
  fetcher: (params: { page: number; pageSize: number }) => Promise<ApiResponse<PaginatedData<T>>>,
  pageSize = 20
) {
  const [list, setList] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchPage = useCallback(async (p: number, isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const res = await fetcher({ page: p, pageSize });
      if (p === 1) {
        setList(res.data.list);
      } else {
        setList(prev => [...prev, ...res.data.list]);
      }
      setTotal(res.data.total);
      setPage(p);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [fetcher, pageSize]);

  const refresh = () => fetchPage(1, true);
  const loadMore = () => {
    if (!loading && list.length < total) {
      fetchPage(page + 1);
    }
  };

  return { list, total, loading, refreshing, refresh, loadMore };
}
```

## 数据转换

- 后端返回的时间戳（秒）在前端转换为可读格式
- 后端枚举值在前端映射为中文标签
- 金额字段注意精度（使用整数分，前端展示时除以 100）

```tsx
// 时间戳转换
function formatTimestamp(ts: number): string {
  if (!ts) return '-';
  return dayjs.unix(ts).format('YYYY-MM-DD HH:mm:ss');
}

// 枚举映射
const LOT_STATUS_MAP: Record<string, { label: string; color: string }> = {
  active: { label: '正常', color: 'green' },
  frozen: { label: '冻结', color: 'orange' },
  expired: { label: '过期', color: 'red' },
};
```

## 防重复提交

```tsx
// Hook 封装
function useSubmit<T>(submitFn: () => Promise<T>) {
  const [submitting, setSubmitting] = useState(false);

  const run = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      return await submitFn();
    } finally {
      setSubmitting(false);
    }
  }, [submitting, submitFn]);

  return { run, submitting };
}
```

## 注意事项

- 所有 API 函数必须有 TypeScript 类型定义（入参和返回值）
- 接口文档变更时同步更新前端类型定义
- 开发环境使用代理解决跨域，不要在代码中写死后端地址
- 敏感信息（token）不要打印到 console
