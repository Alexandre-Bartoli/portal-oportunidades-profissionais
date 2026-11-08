import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core


def job(ident, location, country='BR'):
    return core.make_job('lever', 'acme', {'id': ident, 'text': 'Estágio',
        'hostedUrl': 'https://example.org/' + ident, 'country': country,
        'categories': {'location': location}})


class GeographyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = patch.object(core, 'DB', Path(self.tmp.name) / 'jobs.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)
        core.save([job('1', 'Barbacena, MG'), job('2', 'Juiz de Fora, MG'),
                   job('3', 'Barbacena, MG / Belo Horizonte, MG'),
                   job('4', 'Barbacena, MG', None), job('5', 'São Paulo, SP')])

    def test_state_and_city_filters_exclude_unconfirmed_locations(self):
        rows = core.query(kind='', uf='MG')
        self.assertEqual({r['external_id'] for r in rows}, {'1', '2'})
        rows = core.query(kind='', uf='MG', municipality='3105608')
        self.assertEqual({r['external_id'] for r in rows}, {'1'})

    def test_radius_uses_city_seats_and_excludes_uncertain(self):
        rows = core.query(kind='', uf='MG', municipality='3105608', radius_km=100)
        self.assertEqual({r['external_id'] for r in rows}, {'1', '2'})
        self.assertTrue(all('distance_km' in row for row in rows))
        self.assertAlmostEqual(next(r['distance_km'] for r in rows if r['external_id']=='1'), 0)

    def test_radius_can_cross_state_border_and_excludes_remote(self):
        core.save([job('6', 'Petrópolis, RJ')])
        remote = core.make_job('lever', 'acme', {'id': '7', 'text': 'Estágio',
            'hostedUrl': 'https://example.org/7', 'country': 'BR', 'workplaceType': 'remote',
            'categories': {'location': 'Juiz de Fora, MG'}})
        core.save([remote])
        rows = core.query(kind='', uf='MG', municipality='3136702', radius_km=90)
        self.assertIn('6', {r['external_id'] for r in rows})
        self.assertNotIn('7', {r['external_id'] for r in rows})

    def test_remote_or_ambiguous_place_not_geocoded(self):
        from geografia import locate
        self.assertIsNone(locate('Remote, Barbacena, MG', 'BR'))
        self.assertIsNone(locate('Barbacena, MG', None))
        self.assertEqual(locate('BARBACENA, mg', 'BR'), '3105608')

    def test_invalid_geographic_filters_are_rejected(self):
        for args in ({'uf':'XX'}, {'municipality':'3105608'},
                     {'uf':'SP', 'municipality':'3105608'}, {'uf':'MG','radius_km':10},
                     {'uf':'MG','municipality':'3105608','radius_km':float('nan')},
                     {'uf':'MG','municipality':'3105608','radius_km':-1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                core.query(kind='', **args)

    def test_legacy_records_remain_unlocated_until_refreshed(self):
        with core.connect() as db:
            db.execute("update jobs set geo_municipio=null where external_id='1'")
        self.assertNotIn('1', {r['external_id'] for r in core.query(kind='', uf='MG')})
        core.save([job('1', 'Barbacena, MG')])
        self.assertIn('1', {r['external_id'] for r in core.query(kind='', uf='MG')})

    def test_geographic_migration_is_versioned(self):
        with core.connect() as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)

    def test_http_interface_and_api_apply_geographic_filters(self):
        import app
        import json
        import threading
        import urllib.request
        import urllib.error
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = 'http://127.0.0.1:' + str(server.server_port)
        params = '?kind=all&uf=MG&municipality=3105608&radius_km=100'
        with urllib.request.urlopen(base + '/api/jobs' + params) as response:
            result = json.load(response)
        self.assertEqual({r['external_id'] for r in result['results']}, {'1', '2'})
        with urllib.request.urlopen(base + '/' + params) as response:
            page = response.read().decode('utf-8')
        self.assertIn('Barbacena', page)
        self.assertIn('linha reta', page)
        self.assertIn('name="municipality"', page)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + '/api/jobs?uf=XX')
        self.assertEqual(error.exception.code, 400)
