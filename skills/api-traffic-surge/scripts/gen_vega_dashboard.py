#!/usr/bin/env python3
"""Generate a portable Kibana 7.15 NDJSON bundle; apply only with --apply."""
import argparse
import copy
import json
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import quote
from monitor_common import ConfigError, SourceError, MANAGED_BY, load_config, endpoint, request_json, build_query, write_json

ROOT = Path(__file__).resolve().parents[1]


def render(value, params):
    if isinstance(value, dict):
        return {k: render(v, params) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, params) for v in value]
    if not isinstance(value, str):
        return value
    full = re.fullmatch(r'\$\{([a-z_]+)\}', value)
    if full:
        if full[1] not in params:
            raise ConfigError('Unresolved template parameter: ' + full[1])
        return params[full[1]]
    def sub(m):
        if m[1] not in params:
            raise ConfigError('Unresolved template parameter: ' + m[1])
        return str(params[m[1]])
    return re.sub(r'\$\{([a-z_]+)\}', sub, value)


def make_spec(cfg, api=None):
    params = {k: cfg[k] for k in ('surge_k', 'peak_ratio', 'surge_min_count', 'timezone_offset_ms')}
    params.update(timezone_label=cfg['timezone'], index_patterns=','.join(cfg['sources']), api_count=len(cfg['apis']))
    if api:
        params.update(api_name=api['name'], api_name_json=json.dumps(api['name'], ensure_ascii=False), index_pattern=api['index'])
    filename = 'tpl_single_api.vega.json' if api else 'tpl_surge_table.vega.json'
    spec = render(json.loads((ROOT / 'references' / filename).read_text(encoding='utf-8')), params)
    spec['data'][0]['url']['body'] = build_query(cfg, api=api, dashboard=bool(api))
    if not api:
        next(d for d in spec['data'] if d['name'] == 'api')['values'] = [
            {'name': a['name'], 'service': a['source_id'], 'service_name': a['service'],
             'path': a['path'], 'ordinal': a['ordinal']} for a in cfg['apis']]
        next(d for d in spec['data'] if d['name'] == 'coverage')['values'] = [{'service': x} for x in cfg['sources']]
    return spec


def object_id(cfg, label):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, MANAGED_BY + ':' + cfg['dashboard_key'] + ':' + label))


def build_objects(cfg):
    marker = MANAGED_BY + '; key=' + cfg['dashboard_key']
    objects = []
    def visualization(label, title, vis):
        obj = {'type': 'visualization', 'id': object_id(cfg, label), 'attributes': {
            'title': title, 'description': marker, 'visState': json.dumps(vis, ensure_ascii=False),
            'uiStateJSON': '{}', 'version': 1,
            'kibanaSavedObjectMeta': {'searchSourceJSON': json.dumps({'query': {'query': '', 'language': 'kuery'}, 'filter': []})}}, 'references': []}
        objects.append(obj)
        return obj
    n = len(cfg['apis'])
    intro = ('**' + str(n) + ' 个接口；默认近24小时，共48个完整半小时。**\n\n'
        '蓝柱：实际调用量；橙线：7天同段均值；绿虚线：上周同期调用量；灰虚线：7天同段峰值。突增柱标红，悬停查看数值。\n\n'
        '突增需同时满足：当前量 > μ+' + str(cfg['surge_k']) + 'σ、> 峰值×' + str(cfg['peak_ratio']) +
        '、≥' + str(cfg['surge_min_count']) + '。历史七个值全零且覆盖齐全时，达到最低量即标记。同比/环比仅展示。\n\n'
        '时区 ' + cfg['timezone'] + '。顶部时间选择器控制对比图，未完成时段不计入。最近时段判定表在图表后；手动刷新，无后台推送。')
    intro_obj = visualization('intro', '半小时对比说明', {'title': '半小时对比说明', 'type': 'markdown', 'params': {'markdown': intro, 'fontSize': 12}, 'aggs': []})
    entries = [(intro_obj, 0, 0, 48, 10)]
    for i, a in enumerate(cfg['apis']):
        title = a['name'] + ' · 半小时对比'
        obj = visualization('api:' + a['name'], title, {'title': title, 'type': 'vega', 'params': {'spec': json.dumps(make_spec(cfg, a), ensure_ascii=False)}, 'aggs': []})
        entries.append((obj, (i % 2) * 24, 10 + (i // 2) * 19, 24, 19))
    table_title = '最近完整半小时 · 突增判定'
    table = visualization('table', table_title, {'title': table_title, 'type': 'vega', 'params': {'spec': json.dumps(make_spec(cfg), ensure_ascii=False)}, 'aggs': []})
    y = 10 + ((n + 1) // 2) * 19
    table_h = max(20, (n * 25 + 220 + 25) // 27)
    entries.append((table, 0, y, 48, table_h))
    details = ('**统计口径**\n\n调用量按指定索引中 Request URL 路径后紧邻 Request Method 标记的日志条数统计，不按请求ID去重。'
        '默认最近24小时，起止向下对齐半小时。表格固定最近一个完整半小时；图表跟随时间选择器。顶部KQL/过滤器不参与固定接口口径计算。\n\n'
        '历史基线为前7天同一半小时，σ使用总体标准差（除以7）。7个桶及各历史日的服务Request URL源日志都需存在；否则不判突增。'
        '有源日志不代表采集绝对完整；本方案不具备独立采集健康检查。\n\n'
        '零分母时，当前有量显示“新增”，两者都零显示“—”；参考数据缺失留空。没有调度、消息推送或外部JSON热更新；配置改变后需重新生成并更新看板。\n\n'
        '|接口|索引|日志path|\n|---|---|---|\n' + '\n'.join('|'+a['name'].replace('|','\\|')+'|`'+a['index']+'`|`'+a['path'].replace('|','\\|')+'`|' for a in cfg['apis']))
    note = visualization('scope', '统计口径与接口清单', {'title': '统计口径与接口清单', 'type': 'markdown', 'params': {'markdown': details, 'fontSize': 12}, 'aggs': []})
    entries.append((note, 0, y + table_h, 48, max(20, 15 + n)))
    panels, refs = [], []
    for i, (obj, x, y0, w, h) in enumerate(entries):
        idx = str(i)
        panels.append({'version': '7.15.0', 'type': 'visualization', 'gridData': {'x': x, 'y': y0, 'w': w, 'h': h, 'i': idx},
            'panelIndex': idx, 'embeddableConfig': {}, 'panelRefName': 'panel_' + idx})
        refs.append({'name': idx + ':panel_' + idx, 'type': 'visualization', 'id': obj['id']})
    objects.append({'type': 'dashboard', 'id': object_id(cfg, 'dashboard'), 'attributes': {
        'title': cfg['dashboard_title'], 'description': marker, 'panelsJSON': json.dumps(panels, ensure_ascii=False),
        'optionsJSON': json.dumps({'useMargins': True, 'hidePanelTitles': False}), 'version': 1, 'timeRestore': True,
        'timeFrom': 'now-24h', 'timeTo': 'now', 'refreshInterval': {'pause': True, 'value': 0},
        'kibanaSavedObjectMeta': {'searchSourceJSON': json.dumps({'query': {'query': '', 'language': 'kuery'}, 'filter': []})}}, 'references': refs})
    return objects


def apply_objects(cfg, objects, base, update=False):
    prefix = '/s/' + quote(cfg['space'], safe='') if cfg.get('space') else ''
    marker = MANAGED_BY + '; key=' + cfg['dashboard_key']
    existing = {}
    # All collisions are checked before the first write. A marker prevents overwriting unrelated dashboards.
    for obj in objects:
        path = prefix + '/api/saved_objects/' + obj['type'] + '/' + obj['id']
        old = request_json(base, path, method='GET', kind='kibana')
        if old:
            if old.get('attributes', {}).get('description') != marker:
                raise SourceError('ID collision with an unrelated saved object; nothing was written')
            if not update:
                raise SourceError('Managed objects already exist; review the NDJSON, then use --apply --update')
            if not old.get('version'):
                raise SourceError('Existing object has no concurrency version; nothing was written')
        existing[obj['id']] = old
    receipt = {'status': 'applying', 'created': [], 'updated': [], 'before': [x for x in existing.values() if x]}
    try:
        for obj in objects:
            old = existing[obj['id']]
            body = {'attributes': obj['attributes'], 'references': obj['references']}
            if old:
                body['version'] = old['version']
            path = prefix + '/api/saved_objects/' + obj['type'] + '/' + obj['id']
            result = request_json(base, path, body, method='PUT' if old else 'POST', kind='kibana')
            if not isinstance(result, dict) or result.get('error') or result.get('id') != obj['id']:
                raise SourceError('Kibana did not confirm the saved object')
            receipt['updated' if old else 'created'].append({'type': obj['type'], 'id': obj['id']})
        for obj in objects:
            path = prefix + '/api/saved_objects/' + obj['type'] + '/' + obj['id']
            saved = request_json(base, path, method='GET', kind='kibana')
            if not saved or saved.get('attributes') != obj['attributes'] or saved.get('references', []) != obj['references']:
                raise SourceError('Saved object read-back did not match the requested content')
        receipt['status'] = 'saved'
    except SourceError as exc:
        receipt.update(status='partial_failure', error=str(exc))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', help='Path to api-monitor-config.json')
    parser.add_argument('--out', default='api-surge-output', help='Output directory; does not contact servers by default')
    parser.add_argument('--apply', action='store_true', help='Create this configuration’s objects in Kibana')
    parser.add_argument('--update', action='store_true', help='Update existing managed objects; requires --apply')
    parser.add_argument('--kibana-url')
    args = parser.parse_args(argv)
    try:
        if args.update and not args.apply:
            raise ConfigError('--update requires --apply')
        cfg = load_config(args.config)
        objects = build_objects(cfg)
        dest = Path(args.out)
        dest.mkdir(parents=True, exist_ok=True)
        ndjson = dest / 'dashboard.ndjson'
        # Migration versions make the file directly importable by the intended Kibana 7.15.
        exported = [{**obj, 'migrationVersion': {obj['type']: '7.14.0' if obj['type'] == 'visualization' else '7.15.0'}, 'coreMigrationVersion': '7.15.0'} for obj in objects]
        ndjson.write_text(''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in exported), encoding='utf-8')
        summary = {'status': 'generated', 'dashboard_id': objects[-1]['id'], 'objects': len(objects), 'api_charts': len(cfg['apis']),
                   'output': str(ndjson.resolve()), 'render_verified': False}
        if args.apply:
            base = endpoint(cfg, 'kibana', args.kibana_url)
            receipt = apply_objects(cfg, objects, base, args.update)
            write_json(dest / 'apply-receipt.json', receipt)
            summary.update(status=receipt['status'], dashboard_url=base + ('/s/' + quote(cfg['space'], safe='') if cfg.get('space') else '') + '/app/dashboards#/view/' + objects[-1]['id'])
            if receipt['status'] != 'saved':
                summary['error'] = receipt['error']
        write_json(dest / 'manifest.json', summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary['status'] in ('generated', 'saved') else 4
    except (ConfigError, SourceError, OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2 if isinstance(exc, ConfigError) else 4


if __name__ == '__main__':
    sys.exit(main())
