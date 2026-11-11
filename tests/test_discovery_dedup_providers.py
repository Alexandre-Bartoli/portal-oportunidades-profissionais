"""Testes do módulo 0.6 sem rede ou credenciais externas."""
import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core
from discover_sources import detect, from_urls, from_html, from_database
from providers_extra import smartrecruiters, breezy, read_public_json, ListingBatch
from source_quality import validate_sources


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_db = core.DB
        core.DB = Path(self.temp.name) / 'jobs.sqlite3'

    def tearDown(self):
        core.DB = self.original_db
        self.temp.cleanup()

    def make(self, provider, source, extid, url, title='Estágio em Administração'):
        if provider == 'lever':
            return core.make_job('lever', source, {'id': extid, 'text': title,
                'hostedUrl': url, 'categories': {'location': 'Barbacena'}})
        return core.make_job('smartrecruiters', source, {'id': extid,
            'title': title, 'url': url, 'location': 'Barbacena', 'kind': 'internship'})

    def test_cross_provider_same_canonical_url_is_one_job(self):
        first = self.make('lever', 'empresa1', '1', 'https://example.org/jobs/12?utm_source=lever')
        second = self.make('smartrecruiters', 'empresa2', '12', 'https://example.org/jobs/12')
        core.save([first, second])
        self.assertEqual(len(core.query()), 1)
        with core.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM job_aliases').fetchone()[0], 2)
        self.assertEqual(core.query()[0]['id'], first['id'])

    def test_one_source_closed_does_not_hide_other(self):
        a = self.make('lever', 'a', '1', 'https://example.org/jobs/12')
        b = self.make('smartrecruiters', 'b', '2', 'https://example.org/jobs/12')
        core.save([a, b])
        core.mark_missing('lever', 'a', set())
        core.mark_missing('lever', 'a', set())
        self.assertEqual(len(core.query()), 1)
        core.mark_missing('smartrecruiters', 'b', set())
        core.mark_missing('smartrecruiters', 'b', set())
        self.assertEqual(len(core.query()), 0)
        core.save([a])
        self.assertEqual(len(core.query()), 1)

    def test_url_change_same_source_retains_original_id(self):
        a = self.make('lever', 'a', '1', 'https://example.org/jobs/a')
        b = self.make('lever', 'a', '1', 'https://example.org/jobs/b')
        self.assertNotEqual(a['id'], b['id'])
        core.save([a]);core.save([b])
        self.assertEqual(len(core.query()), 1)
        self.assertEqual(core.query()[0]['id'], a['id'])
        core.mark_missing('lever', 'a', {b['id']})
        self.assertEqual(len(core.query()), 1)

    def test_different_ids_different_urls_not_merged_by_title(self):
        a=self.make('lever','a','1','https://example.org/jobs/1')
        b=self.make('lever','a','2','https://example.org/jobs/2')
        core.save([a,b])
        self.assertEqual(len(core.query()),2)

    def test_legacy_database_migrates_without_changing_job_id(self):
        job=self.make('lever','old','9','https://example.org/jobs/9')
        with closing(sqlite3.connect(core.DB)) as db, db:
            db.execute('''CREATE TABLE jobs (id TEXT PRIMARY KEY, provider TEXT, source TEXT,
              external_id TEXT,title TEXT,description TEXT,url TEXT,location TEXT,country TEXT,
              mode TEXT,kind TEXT,review_status TEXT,areas TEXT,last_seen TEXT,demo INTEGER DEFAULT 0,
              active INTEGER DEFAULT 1, misses INTEGER DEFAULT 0,first_seen TEXT)''')
            db.execute('''INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (job['id'],job['provider'],job['source'],job['external_id'],job['title'],'',job['url'],
                 'Barbacena',None,'unknown','internship','review','[]',job['last_seen'],0,1,0,job['last_seen']))
        core.init()
        self.assertEqual(core.query()[0]['id'],job['id'])
        with core.connect() as db:
            self.assertEqual(db.execute('SELECT job_id FROM job_aliases').fetchone()[0],job['id'])
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
        core.init()  # idempotência
        self.assertEqual(len(core.query()),1)

    def test_existing_duplicates_are_reported_not_deleted(self):
        a = self.make('lever','a','1','https://example.org/jobs/1')
        core.save([a])
        with core.connect() as db:
            db.execute('''INSERT INTO jobs
              (id,provider,source,external_id,title,description,url,location,country,
               mode,kind,review_status,areas,last_seen,demo,active,misses,first_seen,canonical_url)
              SELECT 'historic-duplicate',provider,source, 'another',title,description,url,
              location,country,mode,kind,review_status,areas,last_seen,demo,active,misses,
              first_seen,canonical_url FROM jobs WHERE id=?''',(a['id'],))
        groups = core.audit_legacy_duplicates()
        self.assertEqual(len(groups),1)
        with core.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)

    def test_discover_from_collected_job_urls_without_network(self):
        j=self.make('lever','a','2','https://jobs.smartrecruiters.com/NovaEmpresa/2345')
        core.save([j])
        with core.connect() as db:
            found=from_database(db,configured=[{'provider':'lever','slug':'a'}])
        self.assertEqual(found[0]['provider'],'smartrecruiters')
        self.assertFalse(found[0]['enabled'])


class DiscoveryTests(unittest.TestCase):
    def test_host_patterns(self):
        self.assertEqual(detect('https://jobs.ashbyhq.com/example/123'),
                         {'provider':'ashby','slug':'example'})
        self.assertEqual(detect('https://jobs.lever.co/example/123')['provider'],'lever')
        self.assertEqual(detect('https://empresa.breezy.hr/p/abc')['slug'],'empresa')
        self.assertEqual(detect('https://careers.smartrecruiters.com/Empresa')['slug'],'Empresa')

    def test_rejects_host_spoofing_and_ip(self):
        for url in ['https://jobs.ashbyhq.com.evil.test/demo',
                    'https://jobs.lever.co@internal.local/abc',
                    'https://localhost/jobs', 'http://jobs.lever.co/x',
                    'https://a.breezy.hr.evil.test/p/1',
                    'https://jobs.lever.co:8443/x',
                    'javascript:alert(1)']:
            with self.subTest(url=url):
                self.assertIsNone(detect(url))

    def test_only_proposes_disabled_new_sources(self):
        links=['https://jobs.ashbyhq.com/example/1',
               'https://jobs.ashbyhq.com/example/2',
               'https://jobs.lever.co/already/job',
               'https://unknown.example/jobs/1']
        found=from_urls(links,configured=[{'provider':'lever','slug':'already'}])
        self.assertEqual(len(found),1)
        self.assertFalse(found[0]['enabled'])
        self.assertEqual(found[0]['status'],'pendente_de_validacao')

    def test_html_extracts_at_most_known_ats(self):
        text='<a href="https://jobs.ashbyhq.com/acme/9">vaga</a><a href="javascript:alert(1)">bad</a>'
        self.assertEqual(from_html('https://company.example/carreiras',text)[0]['slug'],'acme')


class ProviderTests(unittest.TestCase):
    def test_smartrecruiters_only_explicit_categories(self):
        response={'content':[
            {'id':'x','name':'Designer', 'typeOfEmployment':{'label':'Full-time'},
             'location': {'city':'Barbacena','country':'BR'}},
            {'id':'y','name':'Anúncio sem contrato', 'location':{}},
            {'id':'z','name':'Estágio em Psicologia','location':{}}]}
        found=smartrecruiters('company',get_json=lambda u:response)
        self.assertEqual([x['kind'] for x in found],['employment','internship'])
        self.assertTrue(found.complete)
        self.assertEqual(core.make_job('smartrecruiters','company',found[0])['kind'],'employment')

    def test_smartrecruiters_truncated_inventory_is_partial(self):
        response={'content':[{'id':str(i),'name':'Estágio','typeOfEmployment':{'label':'Internship'}}
                             for i in range(100)]}
        found=smartrecruiters('company',get_json=lambda _:response,max_pages=1)
        self.assertFalse(found.complete)

    def test_breezy_normalization_and_url_safety(self):
        response=[{'name':'Estágio de Enfermagem','id':'abc','url':'https://abc.breezy.hr/p/abc',
                   'location':{'name':'Barbacena','is_remote':True}},
                  {'name':'Estágio','url':'https://abc.breezy.hr.evil.test/p/1'},
                  {'name':'Emprego sem tipo','url':'https://abc.breezy.hr/p/2'}]
        found=breezy('abc',get_json=lambda _:response)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['mode'],'remote')
        self.assertEqual(core.make_job('breezy','abc',found[0])['kind'],'internship')

    def test_invalid_public_api_response_fails(self):
        with self.assertRaises(ValueError):smartrecruiters('company',get_json=lambda _:[])
        with self.assertRaises(ValueError):breezy('company',get_json=lambda _:{})
        with self.assertRaises(ValueError):smartrecruiters('a/b',get_json=lambda _: {})
        with self.assertRaises(ValueError):read_public_json('https://localhost/private')
        with self.assertRaises(ValueError):read_public_json('https://foo.breezy.hr.evil.test/json')

    def test_new_provider_configuration_is_valid_but_not_enabled(self):
        config={'sources':[{'provider':'smartrecruiters','slug':'example','enabled':False},
                           {'provider':'breezy','slug':'example','enabled':False}]}
        self.assertEqual(validate_sources(config)['enabled'],0)


if __name__ == '__main__':
    unittest.main()
