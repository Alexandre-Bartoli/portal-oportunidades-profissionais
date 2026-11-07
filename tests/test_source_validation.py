"""Validação externa independente do banco e sem chamadas de rede reais."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import core
from providers_extra import ListingBatch, smartrecruiters, breezy
from source_quality import audit_result, audit_summary
from source_validation import verify_config, write_report


def config(*sources):
    return {'sources': [dict(provider=provider, slug=slug, enabled=enabled)
                        for provider, slug, enabled in sources]}


def posting(provider='lever', source='acme', id='12', url=None):
    return {'id': id, 'provider': provider, 'source': source,
            'title': 'Estágio de Administração', 'kind': 'internship',
            'url': url or f'https://empresa.example/jobs/{id}'}


class AuditTests(unittest.TestCase):
    def test_success_without_eligible_jobs_is_not_empty_source(self):
        items = ListingBatch([], complete=True, raw_count=14)
        x = audit_result('lever', 'acme', items=items)
        self.assertEqual((x['status'], x['raw_count'], x['jobs']), ('no_match', 14, 0))

    def test_truly_empty_source(self):
        x = audit_result('lever', 'acme', items=ListingBatch([], raw_count=0))
        self.assertEqual(x['status'], 'empty')

    def test_partial_inventory_never_counts_as_full_success(self):
        x = audit_result('lever', 'acme', items=ListingBatch([posting()], complete=False, raw_count=99))
        self.assertEqual(x['status'], 'partial')

    def test_aggregated_summary_has_no_match(self):
        x = audit_summary([audit_result('lever', 'a', ListingBatch([], raw_count=10)),
                           audit_result('lever', 'b', ListingBatch([], raw_count=0))])
        self.assertEqual((x['no_match'], x['empty']), (1, 1))


class ExternalValidationTests(unittest.TestCase):
    def test_two_complete_independent_sources_meet_criterion(self):
        c = config(('lever','one',True), ('ashby','two',True))
        def fetch(provider, slug):
            return ListingBatch([posting(provider,slug,slug)], raw_count=10)
        result = verify_config(c, fetcher=fetch, now='2026-11-07T00:00:00Z')
        self.assertTrue(result['criteria']['met'])
        self.assertEqual(result['criteria']['sources_with_valid_jobs'],2)
        self.assertEqual(result['summary']['ok'],2)
        self.assertEqual(result['sources'][0]['raw_count'],10)

    def test_one_source_with_vacancies_is_not_enough(self):
        c = config(('lever','one',True),('ashby','two',True))
        def fetch(provider,slug):
            return ListingBatch([posting(provider,slug)],raw_count=4) if provider=='lever' else ListingBatch([],raw_count=2)
        result = verify_config(c, fetcher=fetch)
        self.assertFalse(result['criteria']['met'])
        self.assertEqual(result['sources'][1]['status'],'no_match')

    def test_dns_error_does_not_count_as_empty_or_accepted(self):
        c=config(('ashby','bad',True))
        def fetch(*_):raise urllib.error.URLError('DNS indisponível')
        result=verify_config(c,fetcher=fetch,min_sources=1)
        self.assertEqual(result['sources'][0]['reason'],'network_error')
        self.assertEqual(result['summary']['empty'],0)
        self.assertFalse(result['criteria']['met'])

    def test_partial_list_is_not_validated_even_with_jobs(self):
        result=verify_config(config(('gupy','estagio',True)),fetcher=lambda *_:ListingBatch([posting()],complete=False,raw_count=100),min_sources=1)
        self.assertEqual(result['summary']['partial'],1)
        self.assertFalse(result['criteria']['met'])

    def test_invalid_data_prevents_approval(self):
        result=verify_config(config(('lever','one',True)),fetcher=lambda *_:ListingBatch([{'id':'123'}],raw_count=1),min_sources=1)
        self.assertEqual(result['sources'][0]['status'],'invalid_data')
        self.assertEqual(result['sources'][0]['malformed'],1)
        self.assertFalse(result['criteria']['met'])

    def test_duplicate_url_rejected(self):
        rows=[posting(id='1',url='https://exemplo.org/jobs/1'),
              posting(id='2',url='https://exemplo.org/jobs/1?utm_source=ad')]
        result=verify_config(config(('lever','one',True)),fetcher=lambda *_:ListingBatch(rows,raw_count=2),min_sources=1)
        self.assertEqual(result['sources'][0]['status'],'invalid_data')
        self.assertEqual(result['sources'][0]['duplicate_records'],1)

    def test_inconsistent_raw_count_rejected(self):
        rows=ListingBatch([posting(),posting(id='2')],raw_count=1)
        r=verify_config(config(('lever','one',True)),fetcher=lambda *_:rows,min_sources=1)
        self.assertEqual(r['sources'][0]['reason'],'invalid_response')

    def test_disabled_is_not_probed(self):
        fetched=[]
        def fetch(p,s):fetched.append(s);return ListingBatch([posting()],raw_count=1)
        verify_config(config(('lever','enabled',True),('ashby','disabled',False)),fetcher=fetch,min_sources=1)
        self.assertEqual(fetched,['enabled'])

    def test_invalid_config_fails_before_request(self):
        with self.assertRaises(ValueError):
            verify_config(config(('unknown','x',True)),fetcher=lambda *_:self.fail('network called'))

    def test_verify_does_not_modify_existing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(core,'DB',Path(directory)/'jobs.sqlite3'):
                job=core.make_job('lever','acme',{'id':'7','text':'Estágio em Administração',
                           'hostedUrl':'https://empresa.example/jobs/7', 'categories':{'location':'MG'}})
                core.save([job])
                before=core.query()
                verify_config(config(('lever','acme',True)),fetcher=lambda *_:ListingBatch([],raw_count=0),min_sources=1)
                self.assertEqual(core.query(),before)

    def test_write_report_is_atomic_json(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'reports'/'audit.json'
            report={'schema_version':1,'sources':[]}
            write_report(report,dest)
            self.assertEqual(json.loads(dest.read_text()),report)
            self.assertFalse((dest.parent/'audit.json.tmp').exists())

    def test_invalid_minimum(self):
        for bad in (0,-1,21,1.5,True):
            with self.subTest(value=bad),self.assertRaises(ValueError):
                verify_config(config(('lever','acme',True)),fetcher=lambda *_:[],min_sources=bad)


class RawCountPropagationTests(unittest.TestCase):
    def test_greenhouse_with_full_board_no_match(self):
        with patch('core.get_json',return_value={'jobs':[{'id':1,'title':'Senior VP',
                            'absolute_url':'https://empresa.example/1'}]}):
            items=core.fetch_source('greenhouse','empresa')
        self.assertEqual((len(items),items.raw_count,items.complete),(0,1,True))

    def test_breezy_full_board_with_unclassified_jobs(self):
        rows=[{'id':'1','name':'Analista de Dados',
               'url':'https://acme.breezy.hr/p/1','location':{}}]
        result=breezy('acme',get_json=lambda _:rows)
        self.assertEqual((len(result),result.raw_count,result.complete),(0,1,True))

    def test_smartrecruiters_raw_count_includes_unclassified(self):
        rows={'content':[{'id':'1','name':'Analista de Dados','location':{}}]}
        result=smartrecruiters('acme',get_json=lambda _:rows)
        self.assertEqual((len(result),result.raw_count,result.complete),(0,1,True))

    def test_ashby_listed_count(self):
        payload={'jobs':[{'id':'1','title':'Estágio em Desenvolvimento','jobUrl':'https://empresa.example/1'},
                         {'id':'2','title':'Analista','isListed':False}]}
        with patch('core.get_json',return_value=payload):
            result=core.fetch_source('ashby','acme')
        self.assertEqual((len(result),result.raw_count,result.complete),(1,1,True))


if __name__ == '__main__':
    unittest.main()
