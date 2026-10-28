"""Offline tests only: no network, saved-object changes, cache or cleanup."""
import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import monitor_common as common
import gen_vega_dashboard as gen
import api_monitor as monitor


def configuration():
    return common.normalize_config({'dashboard_key': 'offline-test', 'apis': [
        {'name': 'demo/webhook', 'service': 'demo-service', 'path': '/webhook'},
        {'name': 'demo/webhook/child', 'service': 'demo-service', 'match': 'Request URL : /webhook/child'}]})


def fixture(cfg, chart=False):
    anchor = int(datetime(2026, 10, 22, 9, 5, tzinfo=timezone.utc).timestamp() * 1000)
    end = anchor // common.HALF_HOUR * common.HALF_HOUR
    begin = end - common.DAY
    minimum = begin - 7 * common.DAY - common.HALF_HOUR * 2
    def slots():
        return [{'key': t, 'doc_count': 100} for t in range(minimum, end + common.HALF_HOUR, common.HALF_HOUR)]
    off = cfg['timezone_offset_ms']
    first_day = (minimum + off) // common.DAY * common.DAY - off
    days = [{'key': t, 'doc_count': 1000} for t in range(first_day, end + common.DAY, common.DAY)]
    data = {'clock': {'buckets': [{'from': begin if chart else anchor, 'to': anchor}]}}
    if chart:
        data.update(target={'slots': {'buckets': slots()}}, coverage={'buckets': days})
    else:
        data.update(apis={'buckets': {a['name']: {'slots': {'buckets': slots()}} for a in cfg['apis']}},
                    coverage={'buckets': {s: {'days': {'buckets': copy.deepcopy(days)}} for s in cfg['sources']}})
    return {'timed_out': False, '_shards': {'failed': 0, 'successful': 1, 'total': 1},
            'aggregations': {'all': {'buckets': [data]}}}


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.cfg = configuration()

    def test_default_parameters(self):
        self.assertEqual((self.cfg['surge_k'], self.cfg['peak_ratio'], self.cfg['surge_min_count']), (3, 2, 200))

    def test_duplicate_names_rejected(self):
        with self.assertRaises(common.ConfigError):
            common.normalize_config({'dashboard_key': 'x', 'apis': [{'name':'a','service':'s','path':'/a'}]*2})

    def test_bad_parameters_rejected(self):
        for key, value in [('surge_k', True), ('peak_ratio', float('nan')), ('surge_min_count', 1.5)]:
            with self.subTest(key=key), self.assertRaises(common.ConfigError):
                common.normalize_config({'dashboard_key':'x',key:value,'apis':[{'name':'a','service':'s','path':'/a'}]})

    def test_legacy_match_is_anchored_once(self):
        c = common.normalize_config({'dashboard_key':'x','apis':[{'name':'a','service':'s','match':'Request URL : /foo Request Method'}]})
        self.assertEqual(c['apis'][0]['phrase'], 'Request URL : /foo Request Method')

    def test_arbitrary_keyword_not_silently_supported(self):
        with self.assertRaises(common.ConfigError):
            common.normalize_config({'dashboard_key':'x','apis':[{'name':'a','service':'s','match':'OtherClass'}]})

    def test_parent_child_queries_distinct(self):
        q = common.build_query(self.cfg)['aggs']['all']['aggs']['apis']['filters']['filters']
        self.assertEqual(q['demo/webhook']['bool']['filter'][1]['match_phrase']['message'], 'Request URL : /webhook Request Method')
        self.assertIn('/webhook/child', json.dumps(q['demo/webhook/child']))

    def test_full_24h_excludes_current_slot(self):
        r = common.evaluate_response(self.cfg, fixture(self.cfg))
        self.assertEqual(r['slots_count'], 48)
        self.assertEqual(r['apis'][0]['slots'][-1]['label'], '2026-10-22T16:30:00+08:00')
        self.assertEqual(r['apis'][0]['slots'][0]['label'], '2026-10-21T17:00:00+08:00')
        self.assertEqual(r['apis'][0]['slots'][0]['mom']['percent'], 0)

    def test_zero_history_boundary(self):
        for current, expected in [(0, False),(199,False),(200,True)]:
            with self.subTest(current=current):
                self.assertEqual(common.surge_metrics(current,[0]*7,3,2,200)['surge'], expected)

    def test_strict_peak_boundary(self):
        self.assertFalse(common.surge_metrics(200,[100]*7,3,2,200)['surge'])
        self.assertTrue(common.surge_metrics(201,[100]*7,3,2,200)['surge'])

    def test_all_three_gates(self):
        self.assertFalse(common.surge_metrics(199,[50]*7,3,2,200)['surge'])
        self.assertFalse(common.surge_metrics(285,[0,0,140,140,140,140,140],3,2,200)['surge'])

    def test_missing_history_not_zero(self):
        self.assertFalse(common.surge_metrics(1000,[0]*7,3,2,200,False)['surge'])
        self.assertIsNone(common.surge_metrics(1000,[None]*7,3,2,200)['mean'])

    def test_population_standard_deviation(self):
        self.assertEqual(common.surge_metrics(200,[94,96,98,100,102,104,106],3,2,200)['sigma'], 4)

    def test_partial_response_rejected(self):
        for modifier in ({'timed_out':True},{'_shards':{'failed':1}}, {'aggregations':{}}):
            response=fixture(self.cfg); response.update(modifier)
            with self.subTest(modifier=modifier), self.assertRaises(common.SourceError):
                common.evaluate_response(self.cfg,response)

    def test_source_day_gap_blocks_false_new_api_alert(self):
        response=fixture(self.cfg);data=response['aggregations']['all']['buckets'][0]
        for slot in data['apis']['buckets']['demo/webhook']['slots']['buckets']:
            slot['doc_count']=1000 if slot['key']>=data['clock']['buckets'][0]['from']//common.HALF_HOUR*common.HALF_HOUR-common.DAY else 0
        for day in data['coverage']['buckets'][self.cfg['sources'][0]]['days']['buckets']:day['doc_count']=0
        result=common.evaluate_response(self.cfg,response)
        self.assertFalse(result['has_surge']);self.assertGreater(result['baseline_incomplete_slots'],0)

    def test_zero_denominators(self):
        self.assertEqual(common.compare(10,0)['status'],'new')
        self.assertEqual(common.compare(0,0)['status'],'both_zero')
        self.assertEqual(common.compare(10,None)['status'],'missing')

    def test_graph_has_four_series_and_configured_thresholds(self):
        self.cfg.update(surge_k=4,peak_ratio=3,surge_min_count=250)
        graph=gen.make_spec(self.cfg,self.cfg['apis'][0]);table=gen.make_spec(self.cfg)
        self.assertEqual(next(d for d in graph['data'] if d['name']=='long')['transform'][0]['fields'],['calls','mean','weekly','peak'])
        for spec in (graph,table):
            sig={s['name']:s.get('value') for s in spec['signals']}
            self.assertEqual((sig['surgeK'],sig['peakRatio'],sig['minCount']),(4,3,250))
            self.assertGreater(len(spec['marks']),0)
            self.assertNotIn('${',json.dumps(spec))

    def test_generated_ids_stable_and_references_complete(self):
        a=gen.build_objects(self.cfg);b=gen.build_objects(self.cfg)
        self.assertEqual([o['id'] for o in a],[o['id'] for o in b])
        self.assertTrue(all(r['id'] in {o['id'] for o in a} for r in a[-1]['references']))

    def test_generator_default_is_offline(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'config.json';p.write_text(json.dumps({'dashboard_key':'offline-test','apis':[{'name':'a','service':'s','path':'/a'}]}))
            with patch.object(gen,'request_json',side_effect=AssertionError('Unexpected network')), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gen.main([str(p),'--out',str(Path(td)/'out')]),0)
            self.assertTrue((Path(td)/'out/dashboard.ndjson').is_file())

    def test_no_write_on_foreign_id_collision(self):
        calls=[]
        def transport(*args,**kwargs):
            calls.append(kwargs.get('method'))
            return {'attributes':{'description':'someone else'}}
        with patch.object(gen,'request_json',transport), self.assertRaises(common.SourceError):
            gen.apply_objects(self.cfg,gen.build_objects(self.cfg),'https://example.invalid',True)
        self.assertEqual(calls,['GET'])

    def test_owned_update_uses_version_and_readback(self):
        objects=gen.build_objects(self.cfg);state={o['id']:{**copy.deepcopy(o),'version':'version-1'} for o in objects};writes=[]
        def transport(base,path,body=None,method=None,kind=None):
            oid=path.rsplit('/',1)[-1]
            if method=='GET':return copy.deepcopy(state.get(oid))
            self.assertEqual(body['version'],'version-1');writes.append(method)
            state[oid].update(copy.deepcopy(body));return copy.deepcopy(state[oid])
        with patch.object(gen,'request_json',transport):receipt=gen.apply_objects(self.cfg,objects,'https://example.invalid',True)
        self.assertEqual(receipt['status'],'saved');self.assertTrue(all(x=='PUT' for x in writes))

    def test_partial_apply_not_reported_saved(self):
        def transport(base,path,body=None,method=None,kind=None):
            if method=='GET':return None
            raise common.SourceError('test write failed')
        with patch.object(gen,'request_json',transport):r=gen.apply_objects(self.cfg,gen.build_objects(self.cfg),'https://example.invalid')
        self.assertEqual(r['status'],'partial_failure')

    def test_monitor_source_failure_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'c.json';p.write_text(json.dumps({'dashboard_key':'x','es_url':'https://example.invalid','apis':[{'name':'a','service':'s','path':'/a'}]}))
            bad=fixture(self.cfg);bad['timed_out']=True
            with patch.object(monitor,'request_json',return_value=bad),contextlib.redirect_stderr(io.StringIO()) as err,contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(monitor.main(['--config',str(p)]),3)
            self.assertEqual(out.getvalue(),'');self.assertIsNone(json.loads(err.getvalue())['has_surge'])


if __name__ == '__main__':
    unittest.main()
