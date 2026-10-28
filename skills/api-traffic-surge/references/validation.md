# 验证方法

## 离线回归（不访问任何服务）

从 skill 目录执行：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/gen_vega_dashboard.py references/api-monitor-config.sample.json --out /tmp/api-surge-preview
```

Python单元测试覆盖完整窗口、总体标准差、严格阈值、零历史、父子路径查询、缺失数据、查询失败、可重复ID、默认不联网、所有权保护和部分发布失败。它们不证明目标环境的查询和页面渲染成功。

## 目标环境验证

1. 准备私有配置，确认目标是预期ES/Kibana/空间。先运行只读统计，确认 `status=ok`，检查 `baseline_incomplete_slots`。
2. 用相同索引、相同 `Request URL : /path Request Method` 短语、相同毫秒起止（`gte=start, lt=end`）直接查询ES，核对一个高流量和一个零流量接口。不要拿滚动now-1h与对齐后的两桶直接比较。
3. 每接口应有实际柱、7天均值线、上周同期线、7天峰值线；默认48个完整桶。检查最左桶的7天基线、跨日、零分母、参数变化是否同步。全零曲线会重合，需悬停核对值和图例。
4. 核对三门槛及全零历史特例。历史缺失或查询失败不能出现健康的0或突增标记。
5. `--apply` 或手工导入后，打开页面逐张检查。Saved Objects保存成功只验证存储，不能替代渲染。
6. 现有对象更新使用不同参数时，确认更新前快照、稳定ID和版本约束。运行失败时按receipt报告实际已写范围，不把部分保存称为完成。

## 版本范围

模板沿用在Kibana 7.15环境验证过的Vega表达式与聚合结构。生成器的当前版本做了本地模拟与渲染验证；接收方目标环境的认证、索引映射、导入迁移和浏览器渲染仍需按以上步骤核对。其他Kibana主版本不能默认兼容。

Kibana官方参考：[Saved Objects](https://www.elastic.co/docs/explore-analyze/find-and-organize/saved-objects)、[Vega](https://www.elastic.co/docs/explore-analyze/visualize/custom-visualizations-with-vega)。
