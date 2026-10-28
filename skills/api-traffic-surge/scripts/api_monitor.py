#!/usr/bin/env python3
"""Read-only half-hour statistics. No scheduler, push, cache or automatic deletion."""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from monitor_common import (ConfigError, SourceError, HALF_HOUR, DAY, load_config, endpoint,
    request_json, build_query, evaluate_response, require_complete_response, write_json)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='api-monitor-config.json', help='Configuration path (default: current directory)')
    parser.add_argument('--es-url', help='Override es_url / ELASTICSEARCH_URL')
    parser.add_argument('--date', help='A completed local calendar day, YYYY-MM-DD; default: last 24 complete hours')
    parser.add_argument('--output', help='Also save the successful JSON result to this path')
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        base = endpoint(cfg, 'es', args.es_url)
        if args.date:
            try:
                start_dt = datetime.strptime(args.date, '%Y-%m-%d').replace(tzinfo=cfg['tzinfo'])
            except ValueError:
                raise ConfigError('--date must be YYYY-MM-DD') from None
            # Ask ES for its time; never treat today/future as a completed reporting day.
            probe = request_json(base, '/' + quote(','.join(cfg['sources']), safe='*,-_.') + '/_search?allow_partial_search_results=false', build_query(cfg))
            server_ms = require_complete_response(probe)['clock']['buckets'][0]['from']
            start = int(start_dt.timestamp() * 1000)
            end = start + DAY
            if end > int(server_ms // HALF_HOUR * HALF_HOUR):
                raise ConfigError('--date must name a fully completed local calendar day')
            query = build_query(cfg, anchor_ms=server_ms, window_start=start, window_end=end)
        else:
            start = end = None
            query = build_query(cfg)
        response = request_json(base, '/' + quote(','.join(cfg['sources']), safe='*,-_.') + '/_search?allow_partial_search_results=false', query)
        result = evaluate_response(cfg, response, start, end)
        if args.output:
            write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ConfigError, SourceError, OSError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc), 'has_surge': None}, ensure_ascii=False), file=sys.stderr)
        return 2 if isinstance(exc, ConfigError) else 3


if __name__ == '__main__':
    sys.exit(main())
