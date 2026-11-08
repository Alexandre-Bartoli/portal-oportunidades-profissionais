"""Testes de coleta e ciclo de vida com dados simulados, sem Internet."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error
import core
from automatico import collect_once


def record(external_id):
    return core.make_job('lever','empresa-teste',{
        'id':external_id, 'text':'Estágio em Administração',
        'hostedUrl':f'https://example.org/jobs/{external_id}',
        'country':'BR', 'categories':{'location':'Belo Horizonte'},
    })


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.original_db=core.DB
        core.DB=Path(self.tmp.name)/'jobs.sqlite3'
        core.init()

    def tearDown(self):
        core.DB=self.original_db
        self.tmp.cleanup()

    def test_source_lifecycle_two_successful_misses(self):
        job=record('1')
        core.save([job])
        self.assertEqual(len(core.query()),1)
        core.mark_missing('lever','empresa-teste',set())
        self.assertEqual(len(core.query()),1)
        core.mark_missing('lever','empresa-teste',set())
        self.assertEqual(len(core.query()),0)
        core.save([job])
        self.assertEqual(len(core.query()),1)

    def test_source_isolation(self):
        job=record('1')
        core.save([job])
        core.mark_missing('lever','outra-empresa',set())
        core.mark_missing('lever','outra-empresa',set())
        self.assertEqual(len(core.query()),1)

    def test_retry_after_transient_http_error(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self, size=-1):return b'{"jobs": []}'
        failure=urllib.error.HTTPError('https://api.lever.co',503,'unavailable',{},None)
        with patch('core.urllib.request.build_opener') as factory:
            opener=factory.return_value.open
            opener.side_effect=[failure,Response()]
            waits=[]
            result=core.get_json('https://api.lever.co',wait=waits.append)
        self.assertEqual(result['jobs'],[])
        self.assertEqual(opener.call_count,2)
        self.assertEqual(waits,[1])

    def test_no_retry_for_404(self):
        failure=urllib.error.HTTPError('https://api.lever.co',404,'not found',{},None)
        with patch('core.urllib.request.build_opener') as factory:
            opener=factory.return_value.open
            opener.side_effect=failure
            with self.assertRaises(urllib.error.HTTPError):
                core.get_json('https://api.lever.co',wait=lambda _:None)
        self.assertEqual(opener.call_count,1)

    def test_reject_invalid_provider_response(self):
        with patch('core.get_json',return_value={'error':'bad response'}):
            with self.assertRaises(ValueError):
                core.fetch_source('ashby','empresa')

    def test_failed_collection_keeps_old_vacancies(self):
        job=record('1')
        core.save([job])
        with patch('automatico.fetch_source',side_effect=OSError('offline')):
            collect_once()
        self.assertEqual(len(core.query()),1)

if __name__=='__main__':
    unittest.main()
