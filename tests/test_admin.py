import base64
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import app
import core


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base_patch = patch.object(core, 'BASE', self.root)
        self.base_patch.start()
        self.addCleanup(self.base_patch.stop)
        self.db_patch = patch.object(core, 'DB', self.root / 'data' / 'jobs.sqlite3')
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        (self.root / 'sources.json').write_text(json.dumps({'sources': [
            {'provider': 'lever', 'slug': 'acme', 'enabled': True},
            {'provider': 'gupy', 'slug': 'estagio', 'enabled': False}]}), encoding='utf-8')
        self.env = patch.dict(os.environ, {'PORTAL_ADMIN_USER': 'operador',
                                           'PORTAL_ADMIN_PASSWORD': 'x' * 40})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 3)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def request(self, path, credentials=None):
        headers = {}
        if credentials is not None:
            headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
        return urllib.request.urlopen(urllib.request.Request(self.base + path, headers=headers), timeout=3)

    def test_anonymous_cannot_view_administrative_routes(self):
        for path in ('/admin', '/api/admin', '/api/collection-status', '/api/staging-status'):
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as error:
                self.request(path)
            self.assertEqual(error.exception.code, 401)

    def test_home_links_to_administrative_login(self):
        core.init()
        with self.request('/') as response:
            page=response.read().decode('utf-8')
        self.assertIn('href="/admin"',page)

    def test_missing_configuration_disables_administration(self):
        with patch.dict(os.environ, {'PORTAL_ADMIN_PASSWORD': ''}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/admin')
        self.assertEqual(error.exception.code, 503)

    def test_weak_password_disables_administration(self):
        with patch.dict(os.environ, {'PORTAL_ADMIN_PASSWORD': 'short'}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/admin', 'operador:short')
        self.assertEqual(error.exception.code, 503)

    def test_authenticated_panel_shows_sources_and_missing_data(self):
        with self.request('/admin', 'operador:' + 'x' * 40) as response:
            self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')
            page = response.read().decode('utf-8')
        self.assertIn('lever/acme', page)
        self.assertIn('gupy/estagio', page)
        self.assertIn('Não registrado', page)
        self.assertNotIn('x' * 40, page)

    def test_invalid_credentials_cannot_access_data(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/admin', 'operador:' + 'incorrect')
        self.assertEqual(error.exception.code, 401)

    def test_panel_rejects_mutating_requests(self):
        request=urllib.request.Request(self.base+'/admin', data=b'change=1', method='POST')
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 501)

    def test_rate_limit_after_repeated_bad_credentials(self):
        for _ in range(5):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/admin', 'operador:incorrect')
            self.assertEqual(error.exception.code, 401)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/admin', 'operador:incorrect')
        self.assertEqual(error.exception.code, 429)

    def test_read_only_status_reports_last_collection(self):
        data = self.root / 'data'
        data.mkdir()
        (data / 'ultima_coleta.json').write_text(json.dumps({
            'finished_at': '2026-11-08T10:00:00Z', 'collected': 3,
            'real_jobs_active': 2, 'sources': [
                {'source': 'lever/acme', 'status': 'ok', 'jobs': 3, 'raw_count': 4}]}))
        with self.request('/api/admin', 'operador:' + 'x' * 40) as response:
            report = json.load(response)
        self.assertEqual(report['last_collection']['collected'], 3)
        self.assertEqual(report['sources'][0]['status'], 'ok')
        self.assertEqual(report['sources'][0]['received'], 4)
        self.assertEqual(report['history'], 'not_recorded')

    def test_suggested_sources_are_displayed_without_activation(self):
        data = self.root / 'data'
        data.mkdir()
        (data/'fontes_sugeridas.json').write_text(json.dumps({'candidates':[
            {'provider':'ashby','slug':'neworg','enabled':False,'status':'pendente_de_validacao'}]}))
        with self.request('/api/admin', 'operador:' + 'x' * 40) as response:
            report=json.load(response)
        self.assertEqual(report['suggestions'][0]['source'], 'ashby/neworg')
        self.assertEqual(report['suggestions'][0]['status'], 'pendente_de_validacao')

    def test_history_records_only_summaries(self):
        import admin_history
        core.init()
        admin_history.record({'checked_at':'2026-11-08T10:00:00Z', 'mode':'local',
            'collected':3, 'active':2, 'success':1, 'errors':0})
        with self.request('/api/admin', 'operador:' + 'x' * 40) as response:
            report=json.load(response)
        self.assertEqual(len(report['history']), 1)
        self.assertEqual(report['history'][0]['collected'], 3)

    def test_admin_can_review_possible_duplicates_without_merging(self):
        text='Atendimento e conferência de documentos para a equipe. '*6
        for source in ('one','two'):
            item=core.make_job('lever',source,{'id':'1','text':'Estágio administrativo',
                'hostedUrl':'https://example.org/'+source, 'descriptionPlain':text,
                'country':'BR','categories':{'location':'Barbacena, MG'}})
            core.save([item])
        with self.request('/api/admin', 'operador:' + 'x' * 40) as response:
            result=json.load(response)
        self.assertEqual(len(result['possible_duplicates']['groups']),1)
        with self.request('/admin', 'operador:' + 'x' * 40) as response:
            page=response.read().decode('utf-8')
        self.assertIn('Possíveis duplicatas',page)

    def test_corrupt_history_is_reported_as_unavailable(self):
        core.DB.parent.mkdir(parents=True)
        core.DB.write_bytes(b'not a sqlite database')
        with self.request('/api/admin', 'operador:' + 'x' * 40) as response:
            report=json.load(response)
        self.assertEqual(report['history'], 'unavailable')
        self.assertTrue(any('Histórico indisponível' in alert for alert in report['alerts']))

    def test_staging_dashboard_reads_separate_report_and_backups(self):
        stage=self.root/'data'
        stage.mkdir()
        (stage/'homologacao_status.json').write_text(json.dumps({
            'checked_at':'2026-11-08T11:00:00Z','records_processed':7,
            'active_real_jobs_in_staging_db':6,'sources':[]}))
        backups=stage/'backups'
        backups.mkdir()
        (backups/'homologacao-20261108T120000000001Z.sqlite3').write_bytes(b'example')
        (stage/'auditoria_links.json').write_text(json.dumps({
            'checked_at':'2026-11-08T12:00:00Z','sampled':2,'statuses':{'not_checked':2}}))
        with patch('app.STAGING_MODE',True), patch.dict(os.environ, {'PORTAL_STAGING_DIR':str(stage)}), patch.object(core,'DB',stage/'homologacao.sqlite3'):
            with self.request('/api/admin', 'operador:' + 'x' * 40) as response:
                report=json.load(response)
        self.assertEqual(report['mode'],'homologacao')
        self.assertEqual(report['last_collection']['collected'],7)
        self.assertEqual(report['backups']['count'],1)
        self.assertEqual(report['link_check']['statuses'],{'not_checked':2})

    def test_html_escapes_external_source_names(self):
        import admin
        report={'mode':'local', 'last_collection':{'checked_at':None,'collected':None,'active':None}, 'history':'not_recorded',
                'suggestions_count':None, 'backups':{'count':0,'latest':None},
                'link_check':None, 'review_status':'pending', 'sources':[
                    {'source':'<script>alert(1)</script>','enabled':True,'status':None,
                     'checked_at':None,'received':None,'eligible':None,'duplicates':None,
                     'reason':None,'review':'pending'}]}
        page=admin.render(report)
        self.assertNotIn('<script>',page)
        self.assertIn('&lt;script&gt;',page)
