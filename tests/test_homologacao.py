"""Ciclo completo de homologação, somente com respostas simuladas."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import core
from homologacao import collect_staging, staging_database, staging_status
from providers_extra import ListingBatch


def config(*sources):
    return {'sources':[{'provider':p,'slug':slug,'enabled':on}
                       for p,slug,on in sources]}


def job(provider, slug, extid, url, title='Estágio em Administração'):
    if provider == 'lever':
        return core.make_job('lever',slug,{'id':extid,'text':title,
            'hostedUrl':url,'categories':{'location':'Barbacena'}})
    return core.make_job('ashby',slug,{'id':extid,'title':title,
        'jobUrl':url,'location':'Barbacena'})


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original = core.DB
        self.main = self.root/'main.sqlite3'
        self.stage = self.root/'stage.sqlite3'
        self.report = self.root/'report.json'
        core.DB = self.main

    def tearDown(self):
        core.DB = self.original
        self.tmp.cleanup()

    def run_staging(self, cfg, fetch):
        return collect_staging(cfg, fetcher=fetch, db_path=self.stage,
                               report_path=self.report,min_sources=1)

    def test_staging_isolated_and_exposes_real_jobs_only(self):
        cfg = config(('lever','acme',True))
        j=job('lever','acme','1','https://jobs.lever.co/acme/1')
        report=self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        self.assertEqual(report['mode'],'simulated_no_external_network')
        self.assertTrue(report['criteria']['met'])
        self.assertEqual(report['active_real_jobs_in_staging_db'],1)
        self.assertFalse(self.main.exists())
        with staging_database(self.stage):
            self.assertEqual(len(core.query(exclude_demo=True)),1)
            from admin_history import recent
            self.assertEqual(recent()[0]['mode'],'homologacao')
        self.assertEqual(core.DB,self.main)
        self.assertEqual(staging_status(self.report)['summary']['ok'],1)
        self.assertFalse((self.root/'report.json.tmp').exists())

    def test_duplicate_same_url_from_two_sources_is_one_vacancy(self):
        cfg=config(('lever','one',True),('ashby','two',True))
        jobs={('lever','one'):job('lever','one','1','https://example.org/jobs/10?utm_source=lever'),
              ('ashby','two'):job('ashby','two','2','https://example.org/jobs/10')}
        report=self.run_staging(cfg,lambda p,s:ListingBatch([jobs[(p,s)]],raw_count=1))
        self.assertEqual(report['active_real_jobs_in_staging_db'],1)
        self.assertEqual(report['source_aliases_in_staging_db'],2)
        with staging_database(self.stage):
            self.assertEqual(len(core.query(exclude_demo=True)),1)

    def test_error_does_not_delete_prior_job(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        def offline(*_):raise urllib.error.URLError('offline')
        report=self.run_staging(cfg,offline)
        self.assertEqual(report['summary']['error'],1)
        self.assertEqual(report['active_real_jobs_in_staging_db'],1)
        self.assertFalse(report['criteria']['met'])

    def test_invalid_data_does_not_update_existing_job(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        invalid=dict(j, title='Titulo incorreto', url='http://inseguro.example/1')
        report=self.run_staging(cfg,lambda *_:ListingBatch([invalid],raw_count=1))
        self.assertEqual(report['sources'][0]['reason'],'invalid_response')
        with staging_database(self.stage):
            self.assertEqual(core.query()[0]['title'],j['title'])

    def test_partial_inventory_does_not_expire_missing(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        report=self.run_staging(cfg,lambda *_:ListingBatch([],complete=False,raw_count=15))
        self.assertEqual(report['summary']['partial'],1)
        self.assertEqual(report['active_real_jobs_in_staging_db'],1)
        with staging_database(self.stage):
            with core.connect() as db:
                self.assertEqual(db.execute('SELECT misses FROM job_aliases').fetchone()[0],0)

    def test_no_match_is_not_empty_and_expires_after_two_complete_passes(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        def no_match(*_):return ListingBatch([],raw_count=20)
        first=self.run_staging(cfg,no_match)
        self.assertEqual(first['summary']['no_match'],1)
        self.assertEqual(first['active_real_jobs_in_staging_db'],1)
        second=self.run_staging(cfg,no_match)
        self.assertEqual(second['active_real_jobs_in_staging_db'],0)

    def test_run_twice_is_idempotent(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        fn=lambda *_:ListingBatch([j],raw_count=1)
        self.run_staging(cfg,fn)
        second=self.run_staging(cfg,fn)
        self.assertEqual(second['active_real_jobs_in_staging_db'],1)
        self.assertEqual(second['source_aliases_in_staging_db'],1)

    def test_fictional_ads_rejected_before_write(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        j['demo']=1
        report=self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        self.assertEqual(report['summary']['error'],1)
        self.assertEqual(report['active_real_jobs_in_staging_db'],0)

    def test_source_mismatch_rejected(self):
        cfg=config(('lever','acme',True))
        j=job('lever','other','1','https://example.org/jobs/1')
        report=self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        self.assertEqual(report['summary']['error'],1)
        self.assertEqual(report['source_aliases_in_staging_db'],0)

    def test_invalid_count_prevents_storage(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        report=self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=0))
        self.assertEqual(report['summary']['error'],1)
        self.assertEqual(report['active_real_jobs_in_staging_db'],0)

    def test_disabled_sources_not_queried(self):
        cfg=config(('lever','acme',True),('gupy','estagio',False))
        seen=[]
        def fetch(p,s):
            seen.append((p,s))
            return ListingBatch([],raw_count=0)
        self.run_staging(cfg,fetch)
        self.assertEqual(seen,[('lever','acme')])

    def test_refuses_main_database_path(self):
        with self.assertRaises(ValueError):
            with staging_database(self.main):
                pass
        self.assertEqual(core.DB,self.main)

    def test_report_does_not_contain_descriptions_or_urls(self):
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://private.example/unique-secret')
        j['description']='SENSITIVE DESCRIPTION FOR TEST'
        self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        text=self.report.read_text()
        self.assertNotIn('private.example',text)
        self.assertNotIn('SENSITIVE DESCRIPTION',text)
        self.assertNotIn('candidate',text.lower().replace('candidate_profiles_stored',''))

    def test_local_staging_http_reads_only_staged_records(self):
        import app
        import base64
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from urllib.request import urlopen
        cfg=config(('lever','acme',True))
        j=job('lever','acme','1','https://example.org/jobs/1')
        self.run_staging(cfg,lambda *_:ListingBatch([j],raw_count=1))
        with patch('app.STAGING_MODE',True), patch('homologacao.STAGING_REPORT',self.report), patch.dict('os.environ', {'PORTAL_ADMIN_USER':'operator', 'PORTAL_ADMIN_PASSWORD':'x'*40}):
            with staging_database(self.stage):
                server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
                worker=Thread(target=server.serve_forever,daemon=True)
                worker.start()
                base='http://127.0.0.1:'+str(server.server_port)
                try:
                    with urlopen(base+'/api/health',timeout=3) as res:
                        health=json.load(res)
                    self.assertEqual(health['mode'],'homologacao')
                    with urlopen(base+'/api/jobs?kind=internship',timeout=3) as res:
                        payload=json.load(res)
                    self.assertEqual(payload['count'],1)
                    self.assertEqual(payload['results'][0]['demo'],0)
                    from urllib.request import Request
                    auth=base64.b64encode(('operator:'+('x'*40)).encode()).decode()
                    with urlopen(Request(base+'/api/staging-status',headers={'Authorization':'Basic '+auth}),timeout=3) as res:
                        stage=json.load(res)
                    self.assertEqual(stage['active_real_jobs_in_staging_db'],1)
                finally:
                    server.shutdown()
                    server.server_close()
                    worker.join(timeout=3)

    def test_invalid_config_fails_before_db_write(self):
        with self.assertRaises(ValueError):
            self.run_staging({'sources':[{'provider':'fake','slug':'x','enabled':True}]},
                             lambda *_: self.fail('unexpected fetch'))
        self.assertFalse(self.stage.exists())


if __name__ == '__main__':unittest.main()
