import unittest
from unittest.mock import patch

import core
from source_quality import validate_sources


class NewSourceTests(unittest.TestCase):
    def test_remotive_preserves_source_url_and_does_not_guess_country(self):
        payload={'jobs':[{'id':123,'title':'Administrative Assistant','job_type':'full_time',
            'url':'https://remotive.com/remote-jobs/admin/example-123',
            'candidate_required_location':'Worldwide','company_name':'Example',
            'publication_date':'2026-11-01T12:00:00'}]}
        with patch('core.get_json',return_value=payload),patch('source_limits.acquire'):
            jobs=core.fetch_source('remotive','feed')
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['kind'],'employment')
        self.assertEqual(jobs[0]['mode'],'remote')
        self.assertIsNone(jobs[0]['country'])
        self.assertEqual(jobs[0]['location'],'Elegibilidade geográfica informada: Worldwide')
        self.assertIn('remotive.com',jobs[0]['url'])
        self.assertEqual(jobs[0]['company'],'Example')
        self.assertEqual(jobs[0]['published_at'],'2026-11-01T12:00:00')
        self.assertFalse(jobs.complete)

    def test_persist_company_and_date_without_affecting_old_records(self):
        import tempfile
        from pathlib import Path
        payload={'jobs':[{'id':1,'title':'Analyst','job_type':'full_time',
            'url':'https://remotive.com/remote-jobs/admin/example-1',
            'company_name':'Example','publication_date':'2026-11-01T12:00:00'}]}
        with tempfile.TemporaryDirectory() as root,patch.object(core,'DB',Path(root)/'jobs.sqlite3'),patch('core.get_json',return_value=payload),patch('source_limits.acquire'):
            jobs=core.fetch_source('remotive','feed');core.save(jobs)
            item=core.query(kind='')[0]
        self.assertEqual(item['company'],'Example')
        self.assertEqual(item['published_at'],'2026-11-01T12:00:00')

    def test_missing_or_invalid_metadata_does_not_overwrite_existing_values(self):
        import tempfile
        from pathlib import Path
        raw={'id':'7','title':'Internship','url':'https://apply.workable.com/acme/j/7/',
             'kind':'internship','company':'Example','published_at':'2026-11-01'}
        with tempfile.TemporaryDirectory() as root,patch.object(core,'DB',Path(root)/'jobs.sqlite3'):
            core.save([core.make_job('workable','acme',raw)])
            raw.update(company='',published_at='invalid')
            core.save([core.make_job('workable','acme',raw)])
            item=core.query(kind='')[0]
        self.assertEqual(item['company'],'Example')
        self.assertEqual(item['published_at'],'2026-11-01')

    def test_workable_company_listing_is_partial(self):
        payload={'jobs':[{'shortcode':'ABC','title':'Internship in healthcare',
            'url':'https://apply.workable.com/acme/j/ABC/', 'city':'Toronto','country':'CA'}]}
        with patch('core.get_json',return_value=payload):
            jobs=core.fetch_source('workable','acme')
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['kind'],'internship')
        self.assertFalse(jobs.complete)

    def test_solides_respects_explicit_type_and_leaves_country_unknown(self):
        payload={'data':[{'id':10,'title':'Estágio de Administração',
            'recruitmentContractType':[{'name':'Estágio'}],
            'city':{'name':'Barbacena'},'state':{'code':'MG'},'jobType':'hibrido'}]}
        with patch('core.get_json',return_value=payload):
            jobs=core.fetch_source('solides','estagio')
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]['kind'],'internship')
        self.assertEqual(jobs[0]['mode'],'hybrid')
        self.assertIsNone(jobs[0]['country'])
        self.assertFalse(jobs.complete)

    def test_invalid_responses_and_unsafe_destinations_fail(self):
        samples=[('remotive','feed',{'jobs':[None]}),
                 ('remotive','feed',{'jobs':[{'id':1,'title':'Internship','job_type':'internship','url':'https://remotive.com/'}]}),
                 ('workable','acme',{'jobs':[{'shortcode':'1','title':'Internship',
                                              'url':'https://evil.example/1'}]}),
                 ('solides','estagio',{'data':[{'id':1}]})]
        for provider,slug,payload in samples:
            with self.subTest(provider=provider),patch('core.get_json',return_value=payload),patch('source_limits.acquire'):
                with self.assertRaises(ValueError):core.fetch_source(provider,slug)

    def test_sources_are_not_enabled_automatically(self):
        import json
        config=json.loads((core.BASE/'sources.json').read_text())
        validate_sources(config)
        for provider in ('solides','remotive','workable'):
            self.assertFalse(any(x['enabled'] for x in config['sources'] if x['provider']==provider))

    def test_new_source_is_not_probed_without_documented_review(self):
        import tempfile
        from pathlib import Path
        from homologacao import collect_staging
        config={'sources':[{'provider':'solides','slug':'estagio','enabled':True}]}
        with tempfile.TemporaryDirectory() as root:
            with patch.object(core,'DB',Path(root)/'main.sqlite3'):
                result=collect_staging(config,db_path=Path(root)/'stage.sqlite3',
                    report_path=Path(root)/'report.json',min_sources=1,
                    fetcher=lambda *_:self.fail('fonte não revisada consultada'))
        self.assertEqual(result['sources'][0]['status'],'pending_review')

    def test_read_only_audit_also_requires_review(self):
        from source_validation import verify_config
        config={'sources':[{'provider':'remotive','slug':'feed','enabled':True}]}
        result=verify_config(config,min_sources=1,fetcher=lambda *_:self.fail('rede consultada'))
        self.assertEqual(result['sources'][0]['status'],'pending_review')
        self.assertFalse(result['criteria']['met'])

    def test_documented_technical_review_allows_staging_probe(self):
        import tempfile
        from pathlib import Path
        from homologacao import collect_staging
        from providers_extra import ListingBatch
        entry={'provider':'remotive','slug':'feed','enabled':True,
               'usage_review':'approved','usage_evidence_url':'https://example.org/terms',
               'usage_reviewed_by':'tester','usage_reviewed_at':'2020-01-01',
               'usage_scope':'technical_access'}
        item=core.make_job('remotive','feed',{'id':'1','title':'Internship',
            'url':'https://remotive.com/remote-jobs/internship/1','kind':'internship'})
        with tempfile.TemporaryDirectory() as root,patch.object(core,'DB',Path(root)/'main.sqlite3'):
            report=collect_staging({'sources':[entry]},db_path=Path(root)/'stage.sqlite3',
                report_path=Path(root)/'report.json',min_sources=1,
                fetcher=lambda *_:ListingBatch([item],complete=False,raw_count=1))
        self.assertEqual(report['sources'][0]['status'],'partial')
        self.assertEqual(report['active_real_jobs_in_staging_db'],1)
        self.assertFalse(report['criteria']['met'])

    def test_legacy_collect_command_also_requires_review(self):
        import app
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)
            (path/'sources.json').write_text(json.dumps({'sources':[
                {'provider':'gupy','slug':'estagio','enabled':True}]}))
            with patch('app.BASE',path),patch('sys.argv',['app.py','collect']),patch('app.fetch_source') as fetch:
                app.main()
            fetch.assert_not_called()

    def test_remotive_detail_identifies_intermediary(self):
        import tempfile
        import threading
        import urllib.request
        from pathlib import Path
        from http.server import ThreadingHTTPServer
        import app
        payload={'jobs':[{'id':123,'title':'Analyst','job_type':'full_time',
                         'url':'https://remotive.com/remote-jobs/admin/example-123',
                         'company_name':'Example','publication_date':'2026-11-01'}]}
        with tempfile.TemporaryDirectory() as root,patch.object(core,'DB',Path(root)/'jobs.sqlite3'),patch('core.get_json',return_value=payload),patch('source_limits.acquire'):
            jobs=core.fetch_source('remotive','feed');core.save(jobs)
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port)+'/vaga?id='+jobs[0]['id']) as response:
                    page=response.read().decode('utf-8')
                self.assertIn('Consultar anúncio na Remotive',page)
                self.assertIn('Empresa: Example',page)
                self.assertIn('Data de publicação: 2026-11-01',page)
                self.assertNotIn('Consultar anúncio original',page)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)
