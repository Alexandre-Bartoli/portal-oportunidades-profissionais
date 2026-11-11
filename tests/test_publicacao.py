import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import core


class PublicacaoTests(unittest.TestCase):
    def test_ashby_publication_date_is_preserved(self):
        item=core.make_job('ashby','empresa',{'id':'a','title':'Estágio',
            'jobUrl':'https://jobs.ashbyhq.com/empresa/a', 'publishedAt':'2026-11-10T12:00:00Z'})
        self.assertEqual(item['published_at'],'2026-11-10T12:00:00Z')

    def test_recent_filter_keeps_unknown_dates_and_excludes_old(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'DB', Path(tmp)/'jobs.sqlite3'):
            jobs = []
            for ident, when in (('new', now - timedelta(days=2)), ('old', now - timedelta(days=40)), ('unknown', None)):
                job = core.make_job('lever', 'acme', {'id':ident, 'text':'Estágio',
                    'hostedUrl':'https://example.org/'+ident, 'country':'BR'})
                job['published_at'] = when.isoformat() if when else None
                jobs.append(job)
            core.save(jobs)
            self.assertEqual({x['external_id'] for x in core.query(kind='', published_days=7)}, {'new','unknown'})
            self.assertEqual(len(core.query(kind='')), 3)

    def test_invalid_age_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            core.query(published_days='100000')

    def test_public_search_form_offers_recent_filter(self):
        from interface_publica import render_search
        f={'q':'','kind':'all','country':'','region':'','mode':'','area':'','uf':'',
           'municipality':'','radius_km':'','published_days':'7'}
        page=render_search([],f,[],[],[],[],False)
        self.assertIn('name="published_days"',page)
        self.assertIn('Sem data informada',page)

    def test_public_api_applies_the_selected_period(self):
        import app
        import json
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        with tempfile.TemporaryDirectory() as tmp, patch.object(core, 'DB', Path(tmp)/'jobs.sqlite3'):
            jobs = []
            for ident, days in (('new', 2), ('old', 40)):
                job = core.make_job('lever', 'acme', {'id':ident, 'text':'Estágio',
                    'hostedUrl':'https://example.org/'+ident, 'country':'BR'})
                job['published_at'] = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
                jobs.append(job)
            core.save(jobs)
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/api/jobs?kind=all&published_days=7') as response:
                    result=json.load(response)
                self.assertEqual([row['external_id'] for row in result['results']], ['new'])
            finally:
                server.shutdown();server.server_close();thread.join(3)
