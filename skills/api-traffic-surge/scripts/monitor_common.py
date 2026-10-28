"""Shared configuration, Elasticsearch queries and half-hour surge calculations (stdlib only)."""
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HALF_HOUR = 1_800_000
DAY = 86_400_000
# Legacy object namespace is retained so renaming the skill preserves dashboard IDs.
MANAGED_BY = 'personal-api-surge-dashboard'


class ConfigError(ValueError):
    pass


class SourceError(RuntimeError):
    pass


def load_config(path):
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ConfigError('Cannot read configuration: ' + str(path)) from exc
    return normalize_config(raw)


def normalize_config(raw):
    if not isinstance(raw, dict):
        raise ConfigError('Configuration must be a JSON object')
    cfg = dict(raw)
    cfg.setdefault('surge_k', 3)
    cfg.setdefault('peak_ratio', 2.0)
    cfg.setdefault('surge_min_count', 200)
    for key in ('surge_k', 'peak_ratio', 'surge_min_count'):
        x = cfg[key]
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0:
            raise ConfigError(key + ' must be a positive finite number')
    if int(cfg['surge_min_count']) != cfg['surge_min_count']:
        raise ConfigError('surge_min_count must be an integer')
    cfg['timezone'] = cfg.get('timezone', '+08:00')
    tz = cfg['timezone']
    if tz == 'UTC':
        offset = 0
    else:
        m = re.fullmatch(r'([+-])(\d{2}):(\d{2})', str(tz))
        if not m or int(m[2]) > 14 or int(m[3]) >= 60 or (int(m[2]) == 14 and int(m[3]) != 0):
            raise ConfigError('timezone must be UTC or a fixed offset such as +08:00 (no DST zones)')
        offset = (int(m[2]) * 60 + int(m[3])) * (1 if m[1] == '+' else -1) * 60_000
    if offset % HALF_HOUR:
        raise ConfigError('timezone offset must align to a half-hour boundary')
    cfg['timezone_offset_ms'] = offset
    cfg['tzinfo'] = timezone(timedelta(milliseconds=offset))
    cfg['time_field'] = cfg.get('time_field', '@timestamp')
    cfg['message_field'] = cfg.get('message_field', 'message')
    for key in ('time_field', 'message_field'):
        if not isinstance(cfg[key], str) or not re.fullmatch(r'[\w@.-]+', cfg[key]):
            raise ConfigError('Invalid ' + key)
    key = cfg.get('dashboard_key')
    if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', key):
        raise ConfigError('Set a unique dashboard_key using lowercase letters, digits and hyphens')
    if cfg.get('space') is not None and (not isinstance(cfg['space'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', cfg['space'])):
        raise ConfigError('space must be a nonempty Kibana space ID')
    cfg.setdefault('dashboard_title', '接口半小时对比与突增检测')
    if not isinstance(cfg['dashboard_title'], str) or not cfg['dashboard_title'].strip():
        raise ConfigError('dashboard_title must be nonempty text')
    if not isinstance(cfg.get('apis'), list) or not cfg['apis'] or len(cfg['apis']) > 50:
        raise ConfigError('apis must contain 1–50 entries; split larger sets into dashboards')
    apis = []
    names = set()
    for i, a in enumerate(cfg['apis']):
        if not isinstance(a, dict) or not isinstance(a.get('name'), str) or not a['name'].strip():
            raise ConfigError('Each API needs a nonempty name')
        if a['name'] in names:
            raise ConfigError('Duplicate API name: ' + a['name'])
        names.add(a['name'])
        path = a.get('path')
        if a.get('match') is not None:
            if not isinstance(a['match'], str):
                raise ConfigError('match must be text')
            m = re.fullmatch(r'Request URL\s*:\s*(/\S+?)(?:\s+Request Method)?\s*', a['match'])
            if not m:
                raise ConfigError('match must be Request URL : /path, not an arbitrary keyword')
            if path is not None and path != m[1]:
                raise ConfigError('path and match disagree for ' + a['name'])
            path = m[1]
        if not isinstance(path, str) or not path.startswith('/') or re.search(r'\s', path):
            raise ConfigError('Each API needs a path such as /webhook (without service prefix)')
        service = a.get('service', '')
        index = a.get('index')
        if index is None:
            if not isinstance(service, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', service):
                raise ConfigError('Each API needs service or index')
            index = 'k8s-' + service + '-log-*'
        if not isinstance(index, str) or not re.fullmatch(r'[a-z0-9_*?.-]+', index):
            raise ConfigError('index must be one index pattern, without commas or URL components')
        apis.append({'name': a['name'], 'service': service or index, 'source_id': index,
                     'index': index, 'path': path, 'ordinal': i,
                     'phrase': 'Request URL : ' + path + ' Request Method'})
    cfg['apis'] = apis
    cfg['sources'] = sorted({a['index'] for a in apis})
    return cfg


def endpoint(cfg, kind, override=None):
    env = 'ELASTICSEARCH_URL' if kind == 'es' else 'KIBANA_URL'
    value = override or os.environ.get(env) or cfg.get(kind + '_url')
    p = urllib.parse.urlsplit(value or '')
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ConfigError('Set ' + env + ' or ' + kind + '_url; credentials must be environment headers, not URL text')
    return value.rstrip('/')


def request_json(base, path, body=None, method=None, kind='es'):
    headers = {'Content-Type': 'application/json'}
    auth_name = 'ELASTICSEARCH_AUTHORIZATION' if kind == 'es' else 'KIBANA_AUTHORIZATION'
    if os.environ.get(auth_name):
        headers['Authorization'] = os.environ[auth_name]
    if kind == 'kibana':
        headers['kbn-xsrf'] = 'true'
    req = urllib.request.Request(base + path,
        data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
        headers=headers, method=method or ('POST' if body is not None else 'GET'))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and method == 'GET':
            return None
        raise SourceError(kind + ' request returned HTTP ' + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise SourceError(kind + ' request failed (' + type(exc).__name__ + ')') from None


def histogram(cfg, minimum, maximum, daily=False):
    return {'date_histogram': {'field': cfg['time_field'], 'fixed_interval': '24h' if daily else '30m',
        'time_zone': cfg['timezone'], 'min_doc_count': 0,
        'extended_bounds': {'min': minimum, 'max': maximum}}}


def build_query(cfg, api=None, dashboard=False, anchor_ms=None, window_start=None, window_end=None):
    """A complete response preserves timeout/shard status and server/selected time bounds."""
    if dashboard:
        lo = {'%timefilter%': 'min', 'shift': -169, 'unit': 'hour'}
        hi = {'%timefilter%': 'max'}
        clock = {'from': {'%timefilter%': 'min'}, 'to': hi}
    elif window_start is not None:
        lo, hi = window_start - 7 * DAY, window_end
        clock = {'from': anchor_ms, 'to': anchor_ms + 1000}
    else:
        lo, hi = 'now-8d/d', 'now'
        clock = {'from': 'now', 'to': 'now+1s'}
    aggs = {'clock': {'date_range': {'field': cfg['time_field'], 'ranges': [clock]}}}
    if api:
        aggs['target'] = {'filter': {'match_phrase': {cfg['message_field']: api['phrase']}},
                          'aggs': {'slots': histogram(cfg, lo, hi)}}
        aggs['coverage'] = histogram(cfg, lo, hi, daily=True)
    else:
        aggs['apis'] = {'filters': {'filters': {a['name']: {'bool': {'filter': [
            {'wildcard': {'_index': a['index']}}, {'match_phrase': {cfg['message_field']: a['phrase']}}
        ]}} for a in cfg['apis']}}, 'aggs': {'slots': histogram(cfg, lo, hi)}}
        aggs['coverage'] = {'filters': {'filters': {idx: {'wildcard': {'_index': idx}} for idx in cfg['sources']}},
                           'aggs': {'days': histogram(cfg, lo, hi, daily=True)}}
    return {'size': 0, 'track_total_hits': False, 'timeout': '25s' if api else '45s',
        'query': {'bool': {'filter': [
            {'range': {cfg['time_field']: {'gte': lo, 'lte': hi}}},
            {'match_phrase': {cfg['message_field']: 'Request URL'}}]}},
        'aggs': {'all': {'filters': {'filters': [{'match_all': {}}]}, 'aggs': aggs}}}


def require_complete_response(response):
    if not isinstance(response, dict) or response.get('timed_out') is not False:
        raise SourceError('Elasticsearch response missing success status or timed out; no result is valid')
    shards = response.get('_shards', {})
    if not isinstance(shards.get('failed'), int) or shards['failed'] != 0:
        raise SourceError('Elasticsearch shard failure; no result is valid')
    try:
        data = response['aggregations']['all']['buckets'][0]
        clock = data['clock']['buckets'][0]['from']
        if not isinstance(clock, (int, float)) or isinstance(clock, bool) or not math.isfinite(clock):
            raise SourceError('Elasticsearch clock is missing or invalid')
        return data
    except (KeyError, TypeError, IndexError):
        raise SourceError('Required Elasticsearch aggregations are missing') from None


def surge_metrics(calls, history, k, ratio, minimum, covered=True):
    complete = covered and len(history) == 7 and all(x is not None for x in history)
    if not complete:
        return {'complete': False, 'mean': None, 'sigma': None, 'peak': None, 'surge': False}
    mean = sum(history) / 7
    sigma = math.sqrt(sum((x - mean) ** 2 for x in history) / 7)
    peak = max(history)
    surge = calls >= minimum and (peak == 0 or (calls > mean + k * sigma and calls > peak * ratio))
    return {'complete': True, 'mean': mean, 'sigma': sigma, 'peak': peak,
            'stat_threshold': mean + k * sigma, 'peak_threshold': peak * ratio, 'surge': surge}


def compare(calls, previous):
    if previous is None:
        return {'percent': None, 'status': 'missing'}
    if previous == 0:
        return {'percent': None, 'status': 'new' if calls else 'both_zero'}
    return {'percent': (calls / previous - 1) * 100, 'status': 'comparable'}


def evaluate_response(cfg, response, start=None, end=None):
    data = require_complete_response(response)
    try:
        clock = data['clock']['buckets'][0]['from']
        end = int(clock // HALF_HOUR * HALF_HOUR) if end is None else end
        start = end - DAY if start is None else start
        if end <= start or (end - start) % HALF_HOUR or start % HALF_HOUR:
            raise SourceError('Requested window must contain complete half-hours')
        output = []
        offset = cfg['timezone_offset_ms']
        for a in cfg['apis']:
            slots = {b['key']: b['doc_count'] for b in data['apis']['buckets'][a['name']]['slots']['buckets']}
            days = {b['key']: b['doc_count'] for b in data['coverage']['buckets'][a['source_id']]['days']['buckets']}
            rows = []
            for t in range(start, end, HALF_HOUR):
                if t not in slots:
                    raise SourceError('Actual half-hour bucket is missing for ' + a['name'])
                hist = [slots.get(t - n * DAY) for n in range(1, 8)]
                covered = all(days.get((t - n * DAY + offset) // DAY * DAY - offset, 0) > 0 for n in range(1, 8))
                calls = slots[t]
                metrics = surge_metrics(calls, hist, cfg['surge_k'], cfg['peak_ratio'], cfg['surge_min_count'], covered)
                rows.append({'start_ms': t, 'end_ms': t + HALF_HOUR,
                    'label': datetime.fromtimestamp(t / 1000, cfg['tzinfo']).isoformat(),
                    'calls': calls, 'history': hist, **metrics,
                    'weekly': hist[-1] if days.get((t - 7 * DAY + offset) // DAY * DAY - offset, 0) > 0 else None,
                    'mom': compare(calls, slots.get(t - HALF_HOUR)),
                    'week_comparison': compare(calls, hist[-1] if days.get((t - 7 * DAY + offset) // DAY * DAY - offset, 0) > 0 else None)})
            output.append({'name': a['name'], 'service': a['service'], 'path': a['path'],
                           'total': sum(r['calls'] for r in rows), 'slots': rows})
    except (KeyError, TypeError, IndexError) as exc:
        raise SourceError('Incomplete or invalid aggregation structure') from exc
    surges = [{'name': a['name'], 'slot': r} for a in output for r in a['slots'] if r['surge']]
    return {'status': 'ok', 'timezone': cfg['timezone'], 'window_start_ms': start, 'window_end_ms': end,
        'slots_count': (end - start) // HALF_HOUR, 'parameters': {k: cfg[k] for k in ('surge_k', 'peak_ratio', 'surge_min_count')},
        'has_surge': bool(surges), 'surges': surges,
        'baseline_incomplete_slots': sum(not r['complete'] for a in output for r in a['slots']), 'apis': output}


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
