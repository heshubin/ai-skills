---
name: typescript-patterns
description: 编写 React / React Native 项目 TypeScript 代码、设计类型定义、处理泛型或类型推导时使用。触发词：typescript, TS, 类型, 泛型, interface, type, 工具类型
---
# TypeScript 实用类型与模式

编写 React / React Native 项目的 TypeScript 代码时使用。涵盖类型设计、泛型模式、常用工具类型。

## 触发场景

- 设计 TypeScript 类型定义
- 处理复杂的泛型或类型推导
- 审查 TS 类型相关代码
- 提到"typescript"、"类型"、"泛型"、"interface"、"type"时

## 类型定义规范

### interface vs type
- 对象结构用 interface（可扩展、可合并声明）
- 联合类型、交叉类型、映射类型用 type
- API 响应/请求体用 interface

```tsx
// 对象结构 → interface
interface LotMaster {
  lotId: number;
  lotNo: string;
  sku: string;
  quantity: number;
  status: LotStatus;
  createdAt: number;
}

// 联合类型 → type
type LotStatus = 'active' | 'frozen' | 'expired';

// 组合类型 → type
type LotWithInventory = LotMaster & {
  inventory: LotInventory[];
};
```

### 常用工具类型

```tsx
// Partial — 所有属性变为可选（用于更新接口）
type UpdateLotRequest = Partial<LotMaster>;

// Pick — 选取部分属性
type LotSummary = Pick<LotMaster, 'lotId' | 'lotNo' | 'status'>;

// Omit — 排除部分属性
type CreateLotRequest = Omit<LotMaster, 'lotId' | 'createdAt'>;

// Record — 键值对映射
type StatusCountMap = Record<LotStatus, number>;

// Required — 所有属性变为必填
type StrictLotConfig = Required<LotConfig>;
```

## API 类型设计

```tsx
// 统一响应类型
interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

// 分页响应
interface PaginatedData<T> {
  list: T[];
  total: number;
  page: number;
  pageSize: number;
}

// 使用
type LotListResponse = ApiResponse<PaginatedData<LotMaster>>;

// API 函数签名
async function getLotList(
  params: LotQueryParams
): Promise<ApiResponse<PaginatedData<LotMaster>>> {
  return request.get('/api/lot-masters', { params });
}
```

## 泛型模式

### 泛型组件
```tsx
// 通用列表组件
interface ListProps<T> {
  data: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  keyExtractor: (item: T) => string;
  loading?: boolean;
  emptyText?: string;
}

function GenericList<T>({ data, renderItem, keyExtractor, loading, emptyText }: ListProps<T>) {
  if (loading) return <Spinner />;
  if (data.length === 0) return <Empty text={emptyText} />;
  return <>{data.map((item, i) => <div key={keyExtractor(item)}>{renderItem(item, i)}</div>)}</>;
}

// 使用时自动推导 T
<GenericList
  data={lots}
  renderItem={(lot) => <LotCard lot={lot} />}  // lot 自动推导为 LotMaster
  keyExtractor={(lot) => String(lot.lotId)}
/>
```

### 泛型 Hook
```tsx
// 通用数据请求 Hook
function useRequest<T>(
  fetcher: () => Promise<ApiResponse<T>>,
  deps: any[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetcher();
      setData(res.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '请求失败');
    } finally {
      setLoading(false);
    }
  }, deps);

  return { data, loading, error, run };
}
```

## 类型守卫

```tsx
// 自定义类型守卫
function isLotExpired(lot: LotMaster): lot is LotMaster & { status: 'expired' } {
  return lot.status === 'expired';
}

// 区分联合类型
type ScanResult =
  | { type: 'barcode'; value: string }
  | { type: 'qrcode'; value: string; metadata: Record<string, string> };

function handleScan(result: ScanResult) {
  if (result.type === 'qrcode') {
    // TypeScript 自动收窄，可以访问 metadata
    console.log(result.metadata);
  }
}
```

## 枚举替代方案

```tsx
// ❌ 避免 enum（tree-shaking 不友好，运行时有开销）
enum Status { Active, Frozen, Expired }

// ✅ 推荐：const 对象 + typeof
const LOT_STATUS = {
  ACTIVE: 'active',
  FROZEN: 'frozen',
  EXPIRED: 'expired',
} as const;

type LotStatus = typeof LOT_STATUS[keyof typeof LOT_STATUS];
// 结果: 'active' | 'frozen' | 'expired'
```

## 常见类型错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `Type 'X' is not assignable to 'Y'` | 类型不匹配 | 检查属性是否完整、类型是否正确 |
| `Object is possibly 'undefined'` | 可选链未处理 | 使用 `?.` 或 `!`（确定非空时） |
| `Property does not exist on type` | 类型收窄不够 | 添加类型守卫或断言 |
| `Argument of type 'string' is not assignable to parameter of type 'X'` | 字面量类型丢失 | 使用 `as const` 或明确类型注解 |
