import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import core
from source_quality import validate_sources


def posting(i):
    return {'id': i, 'name': 'Analista', 'type': 'vacancy_type_effective',
            'jobUrl': f'https://empresa.gupy.io/jobs/{i}', 'city': 'Barbacena',
            'state': 'Minas Gerais', 'workplaceType': 'on-site'}


def detail(i, country='Brasil'):
    payload = {'props': {'pageProps': {'job': {'id': i, 'description': 'Atividades',
               'addressCity': 'Barbacena', 'addressState': 'Minas Gerais', 'addressCountry': country}}}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(payload) + '</script>'


class GupyEstadoTests(unittest.TestCase):
    def test_state_search_validates_slug_and_passes_full_state_name(self):
        validate_sources({'sources': [{'provider':'gupy', 'slug':'emprego-mg', 'enabled':True,
                                       'experimental_access':True}]})
        urls = []
        def get(url):
            urls.append(url)
            return {'data':[posting(1)]}
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DB', Path(directory)/'x.sqlite3'), \
             patch('core.get_json', side_effect=get), patch('core.get_gupy_detail', return_value=detail(1)):
            jobs = core.fetch_source('gupy', 'emprego-mg')
            core.save(jobs)
            found = core.query(kind='employment', region='brazil', uf='MG')
        self.assertEqual(parse_qs(urlsplit(urls[0]).query)['state'], ['Minas Gerais'])
        self.assertEqual([x['external_id'] for x in found], ['1'])
        self.assertFalse(jobs.complete)

    def test_never_guesses_country_when_detail_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DB', Path(directory)/'x.sqlite3'), \
             patch('core.get_json', return_value={'data':[posting(1)]}), \
             patch('core.get_gupy_detail', side_effect=ValueError('sem detalhe')):
            jobs = core.fetch_source('gupy', 'emprego-mg')
            core.save(jobs)
            self.assertEqual(core.query(kind='employment', uf='MG'), [])
            self.assertIsNone(jobs[0]['country'])

    def test_next_collect_prioritizes_details_not_yet_enriched(self):
        rows = [posting(i) for i in range(1, 13)]
        with tempfile.TemporaryDirectory() as directory, patch.object(core, 'DB', Path(directory)/'x.sqlite3'), \
             patch('core.get_json', return_value={'data':rows}), \
             patch('core.get_gupy_detail', side_effect=lambda url: detail(int(url.rsplit('/',1)[1]))):
            first = core.fetch_source('gupy', 'emprego-mg')
            core.save(first)
            second = core.fetch_source('gupy', 'emprego-mg')
            self.assertEqual(first.details_succeeded, 10)
            self.assertTrue(all(job['detail_enriched'] for job in second[-2:]))
            core.save(second)
            self.assertEqual(len(core.query(kind='employment', uf='MG')), 12)

    def test_invalid_state_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_sources({'sources':[{'provider':'gupy','slug':'emprego-xx','enabled':True}]})
