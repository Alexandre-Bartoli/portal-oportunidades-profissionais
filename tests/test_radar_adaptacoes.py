import json
import unittest
from unittest.mock import patch
import urllib.error

import gupy
import inhire
import core
from source_quality import validate_sources


class RadarAdaptacoesTests(unittest.TestCase):
    def test_gupy_detail_enriches_and_uses_only_explicit_country(self):
        job = {'id':'12','title':'Estágio','url':'https://empresa.gupy.io/jobs/12',
               'description':'Resumo','location':'','country':None}
        payload = {'props':{'pageProps':{'job':{'id':12,'description':'<p>Descrição</p>',
                   'responsibilities':'<p>Atividades</p>', 'prerequisites':'<p>Requisitos</p>',
                   'addressCity':'Barbacena','addressState':'Minas Gerais','addressCountry':'Brasil'}}}}
        page = '<script id="__NEXT_DATA__" type="application/json">'+json.dumps(payload)+'</script>'
        result = gupy.enrich_detail(job, page)
        self.assertIn('Atividades', result['description'])
        self.assertIn('Requisitos', result['description'])
        self.assertEqual(result['country'], 'BR')
        self.assertEqual(result['location'], 'Barbacena, Minas Gerais')
        self.assertEqual(job['description'], 'Resumo')

    def test_gupy_detail_rejects_different_job_or_malformed_page(self):
        job = {'id':'12','url':'https://empresa.gupy.io/jobs/12'}
        with self.assertRaises(ValueError):
            gupy.enrich_detail(job, '<script id="__NEXT_DATA__">{}</script>')
        with self.assertRaises(ValueError):
            gupy.enrich_detail(job, '<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'job':{'id':13,'description':'other'}}}})+'</script>')

    def test_inhire_fetch_normalizes_and_remains_partial(self):
        def fake(url, *, headers):
            self.assertEqual(headers, {'X-Tenant':'empresa'})
            if url.endswith('/pages'):
                return {'tenantName':'Empresa', 'jobsPage':[{'jobId':'abc'}]}
            return {'jobId':'abc', 'displayName':'Estágio de Psicologia', 'description':'<p>Trabalho</p>',
                    'location':'Brasil', 'contractType':['Estágio'], 'tenantName':'Empresa'}
        jobs = inhire.fetch('empresa', fake)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['kind'],'internship')
        self.assertEqual(jobs[0]['url'],'https://empresa.inhire.app/vagas/abc/estagio-de-psicologia')
        self.assertFalse(jobs.complete)

    def test_inhire_rejects_malformed_identifiers_and_config(self):
        with self.assertRaises(ValueError): inhire.fetch('bad/host', lambda *a, **k: {})
        with self.assertRaises(ValueError): validate_sources({'sources':[{'provider':'inhire','slug':'bad/host','enabled':True}]})
        with self.assertRaises(ValueError): inhire.fetch('empresa', lambda *a, **k: {'jobsPage':[{'jobId':'..'}]})

    def test_gupy_detail_failure_keeps_listing_and_reports_count(self):
        response = {'data':[{'id':12,'name':'Estágio','type':'vacancy_type_internship',
                              'jobUrl':'https://empresa.gupy.io/jobs/12'}]}
        with patch('core.get_json',return_value=response), patch('core.get_gupy_detail',side_effect=urllib.error.URLError('offline')):
            jobs = core.fetch_source('gupy','estagio')
        self.assertEqual(len(jobs),1)
        self.assertIsNone(jobs[0]['country'])
        self.assertEqual(jobs.details_attempted,1)
        self.assertEqual(jobs.details_succeeded,0)
        self.assertFalse(jobs.complete)

    def test_gupy_detail_host_allowlist_rejects_untrusted_urls(self):
        for url in ('https://evil.example/jobs/12','https://portal.gupy.io/jobs/12',
                    'https://empresa.gupy.io.evil.example/jobs/12','https://empresa.gupy.io/jobs/12?next=x'):
            with self.subTest(url=url), self.assertRaises(ValueError): core.get_gupy_detail(url)

    def test_inhire_source_is_normalized_for_portal(self):
        def fake(url, **kwargs):
            if url.endswith('/pages'): return {'jobsPage':[{'jobId':'abc'}]}
            return {'jobId':'abc','displayName':'Estágio','description':'Descrição', 'contractType':['Estágio']}
        with patch('core.get_json',side_effect=fake):
            jobs=core.fetch_source('inhire','empresa')
        self.assertEqual(jobs[0]['provider'],'inhire')
        self.assertEqual(jobs[0]['kind'],'internship')
        self.assertFalse(jobs.complete)

    def test_failed_detail_does_not_erase_previously_enriched_content(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        base={'id':'12','title':'Estágio','url':'https://empresa.gupy.io/jobs/12',
              'kind':'internship','description':'Conteúdo integral','country':'BR','detail_enriched':True}
        with TemporaryDirectory() as directory, patch.object(core,'DB',Path(directory)/'jobs.sqlite3'):
            core.save([core.make_job('gupy','estagio',base)])
            base.update(description='Resumo', country=None, detail_enriched=False)
            core.save([core.make_job('gupy','estagio',base)])
            job=core.query(kind='')[0]
        self.assertEqual(job['description'],'Conteúdo integral')
        self.assertEqual(job['country'],'BR')


if __name__ == '__main__':
    unittest.main()
