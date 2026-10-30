---
name: react-native-dev-guide
description: 开发或审查 React Native 仓库 App（WMS App、Picking App）页面/组件，排查卡顿、白屏、内存泄漏时使用。触发词：react native, RN, 仓库app, 移动端, 手持设备, PDA, 扫码, BroadcastScanner, 导航
---
# React Native 仓库 App 开发指南

开发 React Native 仓库管理 App 时使用。涵盖 RN 特有的性能优化、导航、原生交互、仓库场景最佳实践。

## 触发场景

- 开发 React Native 仓库 App 页面或组件
- 审查 RN 代码变更
- 排查 RN 性能问题（卡顿、白屏、内存泄漏）
- 提到"react native"、"RN"、"仓库app"、"移动端"、"手持设备"时

## 仓库 App 特殊场景

> WMS-front-end（wms-rn）项目约束：**禁止使用 React Native 的 `Alert`**，提示用 `MessageService.getInstance().showTip()`，确认框用 `ConfirmDialog` 组件或 `MessageService.getInstance().showConfirm()`（返回 `Promise<boolean>`）。以仓库自带 `.kiro/steering`（init.md、rn-component-rules.md）为准。

### 扫码处理
- 扫码是仓库 App 最高频操作，必须保证响应速度
- 扫码回调中避免重复触发（加防抖或状态锁）
- 扫码失败要有明确的声音/震动反馈
- 使用 `BroadcastScanner` 时，`isActive` 必须绑定 `useIsFocused()`，禁止硬编码 `isActive={true}`：React Navigation 栈中底层页面不会卸载，否则 A 页面的扫码回调会在 B 页面被触发
- `BroadcastScanner` 内部的 onScan/onError 回调用 `useRef` 保持最新引用，避免闭包拿到过期 props
- 商品图片轮播/标题展示用 `@/components/businessCommon` 的 `ProductImageCarousel`、`ProductTitle`，不要手写轮播

```tsx
const isFocused = useIsFocused();
<BroadcastScanner isActive={isFocused} onScan={handleBarcodeScan} onError={() => {}} visible={false} />
```

```tsx
const [scanning, setScanning] = useState(false);

const handleBarcodeScan = useCallback(async (barcode: string) => {
  if (scanning) return; // 防止重复扫码
  setScanning(true);
  try {
    await processBarcode(barcode);
    // 成功反馈：短震动
    Vibration.vibrate(100);
  } catch (error) {
    // 失败反馈：长震动 + 提示
    Vibration.vibrate(500);
    MessageService.getInstance().showTip('扫码失败，请重试');
  } finally {
    setScanning(false);
  }
}, [scanning]);
```

### 离线支持
- 仓库网络环境不稳定，关键操作需支持离线缓存
- 使用 AsyncStorage 或 MMKV 缓存待提交数据
- 网络恢复后自动同步，提供手动重试入口

### 大列表性能
- 库存列表、拣货列表等使用 FlatList，不用 ScrollView
- 必须设置 keyExtractor、getItemLayout（固定高度时）
- 超过 500 条数据考虑分页加载

## FlatList 优化

```tsx
<FlatList
  data={inventoryList}
  keyExtractor={(item) => String(item.id)}
  renderItem={renderItem}
  // 性能优化配置
  initialNumToRender={15}
  maxToRenderPerBatch={10}
  windowSize={5}
  removeClippedSubviews={true}
  // 固定高度时设置，大幅提升滚动性能
  getItemLayout={(data, index) => ({
    length: ITEM_HEIGHT,
    offset: ITEM_HEIGHT * index,
    index,
  })}
/>
```

### renderItem 优化
- renderItem 中的组件用 React.memo 包裹
- 避免在 renderItem 中创建内联函数和对象

```tsx
// ❌ 每次渲染都创建新函数
renderItem={({ item }) => (
  <TouchableOpacity onPress={() => handlePress(item.id)}>
    <Text>{item.name}</Text>
  </TouchableOpacity>
)}

// ✅ 抽取为独立组件
const InventoryItem = React.memo(({ item, onPress }: ItemProps) => (
  <TouchableOpacity onPress={() => onPress(item.id)}>
    <Text>{item.name}</Text>
  </TouchableOpacity>
));

renderItem={({ item }) => (
  <InventoryItem item={item} onPress={handlePress} />
)}
```

## 导航规范

### React Navigation 结构
```
RootNavigator (Stack)
├── AuthStack (未登录)
│   └── LoginScreen
├── MainTab (已登录)
│   ├── HomeScreen
│   ├── ReceiveStack (收货)
│   │   ├── ReceiveListScreen
│   │   └── ReceiveDetailScreen
│   ├── PickingStack (拣货)
│   │   ├── PickingListScreen
│   │   └── PickingDetailScreen
│   └── InventoryStack (库存)
│       ├── InventoryListScreen
│       └── InventoryDetailScreen
```

### 导航参数类型安全
```tsx
// 定义导航参数类型
type RootStackParamList = {
  ReceiveList: undefined;
  ReceiveDetail: { receiveId: string; warehouseNumber: string };
  LotDetail: { lotId: number };
};

// 使用时有类型提示
navigation.navigate('ReceiveDetail', {
  receiveId: '12345',
  warehouseNumber: 'WH001',
});
```

## 样式规范

- 使用 StyleSheet.create 而非内联样式（性能更好）
- 响应式布局用 Flexbox，不用固定像素
- 仓库手持设备屏幕小，按钮和文字要足够大（最小触摸区域 44x44）
- 颜色、字号、间距定义为主题常量

```tsx
const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  // 仓库场景：按钮要大，方便戴手套操作
  scanButton: {
    height: 56,
    minWidth: 120,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 8,
    backgroundColor: '#1890ff',
  },
  // 列表项：信息密度适中，间距足够
  listItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e8e8e8',
  },
});
```

## 网络请求

- 统一封装 API 请求层，处理 token 刷新、超时、重试
- 请求超时设置为 15-30 秒（仓库网络可能慢）
- 关键操作（提交收货、确认拣货）失败后提供重试机制
- 显示加载状态，避免用户重复点击
- 后端幂等接口返回「已有结果」（如 `reused = true`、`resumed = true`、`already unloaded`）时，App 拿到它的主要场景是首次请求已提交、响应超时丢失后的重试：首次成功时该做的副作用（自动打印标签、推进步骤、更新进度）这时一次都没发生。处理这类分支时要么补做副作用，要么明确提示用户去补打 / 刷新，不能静默当成功（OP-40026 WMS App 审查：Finish loading `reused` 不打印也不提示，Manifest 一张没打、L5 却显示 `Manifest applied`）

```tsx
// 防重复提交
const [submitting, setSubmitting] = useState(false);

const handleSubmit = async () => {
  if (submitting) return;
  setSubmitting(true);
  try {
    await api.confirmReceive(data);
    navigation.goBack();
  } catch (error) {
    setSubmitting(false);
    // 自定义确认框代替 Alert：用户点"重试"时再次提交
    const retry = await MessageService.getInstance().showConfirm('提交失败', '是否重试？', '重试', '取消');
    if (retry) {
      handleSubmit();
    }
    return;
  }
  setSubmitting(false);
};
```

## 调试与排查

- 使用 Flipper 调试网络请求、AsyncStorage、布局
- 性能问题用 React DevTools Profiler 分析重渲染
- 原生崩溃查看 Xcode Console / Android Logcat
- 线上崩溃接入 Sentry 或 Bugly

## 常见陷阱

| 陷阱 | 说明 | 解决方案 |
|------|------|---------|
| ScrollView 嵌套 FlatList | 滚动冲突、性能差 | FlatList 的 ListHeaderComponent |
| 内存泄漏 | 组件卸载后异步回调更新 state | useEffect cleanup 中取消请求 |
| 键盘遮挡输入框 | 仓库场景常需要输入 | KeyboardAvoidingView + ScrollView |
| 安卓返回键 | 未处理硬件返回键 | BackHandler 或 navigation 自动处理 |
| 图片内存溢出 | 加载大量商品图片 | FastImage + 缓存策略 + 缩略图 |
| 热更新失败 | CodePush 更新包过大 | 拆分 bundle、增量更新 |
