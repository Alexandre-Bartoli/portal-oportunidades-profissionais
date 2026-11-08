import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core


class SearchFiltersTests(unittest.TestCase):
    def test_unverified_location_does_not_assign_country(self):
        job = core.make_job('lever', 'acme', {'id': '4', 'text': 'Estágio',
            'hostedUrl': 'https://example.org/4', 'categories': {'location': 'Rio de Janeiro, elsewhere'}})
        self.assertIsNone(job['country'])

    def test_database_rejects_orphan_job_alias(self):
        import sqlite3
        core.init()
        with core.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO job_aliases (provider,source,external_id,source_job_id,job_id) VALUES (?,?,?,?,?)',
                           ('lever', 'acme', 'x', 'x', 'missing'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(core, 'DB', Path(self.temp.name) / 'jobs.sqlite3')
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        rows = [
            ('1', 'Estágio em Administração', 'BR', 'remote'),
            ('2', 'Estágio em Enfermagem', 'CA', 'onsite'),
            ('3', 'Estágio em Administração', None, 'unknown'),
        ]
        jobs = []
        for ident, title, country, mode in rows:
            job = core.make_job('lever', 'acme', {
                'id': ident, 'text': title, 'hostedUrl': 'https://example.org/' + ident,
                'country': country, 'categories': {'location': 'Não informado'}})
            job['mode'] = mode
            jobs.append(job)
        core.save(jobs)

    def test_combined_filters(self):
        rows = core.query(kind='internship', region='brazil', mode='remote', area='Administração')
        self.assertEqual([r['external_id'] for r in rows], ['1'])

    def test_international_excludes_unknown_country(self):
        rows = core.query(kind='internship', region='international')
        self.assertEqual([r['external_id'] for r in rows], ['2'])

    def test_pagination_returns_distinct_results(self):
        first = core.query(kind='internship', limit=1, offset=0)
        second = core.query(kind='internship', limit=1, offset=1)
        self.assertNotEqual(first[0]['id'], second[0]['id'])

    def test_invalid_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            core.query(mode='planet')

    def test_http_filters_and_invalid_parameters(self):
        import app
        import json
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port) + '/api/jobs?kind=all'
        with urllib.request.urlopen(base + '&region=brazil&mode=remote') as response:
            result = json.load(response)
        self.assertEqual([r['external_id'] for r in result['results']], ['1'])
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + '&mode=planet')
        self.assertEqual(error.exception.code, 400)

    def test_html_combines_filters(self):
        import app
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = 'http://127.0.0.1:' + str(server.server_port) + '/?kind=all&region=brazil&mode=remote'
        with urllib.request.urlopen(url) as response:
            page = response.read().decode('utf-8')
        self.assertIn('Estágio em Administração', page)
        self.assertNotIn('Estágio em Enfermagem', page)
        self.assertIn('name="region"', page)

    def test_detail_page_shows_description_and_unknown_job_404(self):
        import app
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        job_id = core.query(region='brazil')[0]['id']
        base = 'http://127.0.0.1:' + str(server.server_port)
        with urllib.request.urlopen(base + '/vaga?id=' + job_id) as response:
            page = response.read().decode('utf-8')
        self.assertIn('Estágio em Administração', page)
        self.assertIn('Última verificação', page)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + '/vaga?id=inexistente')
        self.assertEqual(error.exception.code, 404)

    def test_details_do_not_return_inactive_or_staging_demo_jobs(self):
        row = core.query(region='brazil')[0]
        with core.connect() as db:
            db.execute('UPDATE jobs SET demo=1 WHERE id=?', (row['id'],))
        self.assertIsNone(core.job_details(row['id'], exclude_demo=True))
        with core.connect() as db:
            db.execute('UPDATE jobs SET active=0 WHERE id=?', (row['id'],))
        self.assertIsNone(core.job_details(row['id']))

    def test_result_navigation_preserves_filters(self):
        import app
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        for n in range(35):
            job = core.make_job('lever', 'acme', {'id': 'p'+str(n), 'text': 'Estágio',
                'hostedUrl': 'https://example.org/p'+str(n), 'country': 'BR'})
            core.save([job])
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port)
        with urllib.request.urlopen(base + '/?kind=all&region=brazil') as response:
            page = response.read().decode('utf-8')
        self.assertIn('Próxima página', page)
        self.assertIn('offset=30', page)
        with urllib.request.urlopen(base + '/?kind=all&region=brazil&offset=30') as response:
            second = response.read().decode('utf-8')
        self.assertIn('Página anterior', second)


if __name__ == '__main__':
    unittest.main()
