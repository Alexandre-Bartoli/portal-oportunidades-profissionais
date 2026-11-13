import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import core
from busca_online import SearchManager


class AuditoriaConfiabilidade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = patch.object(core, 'DB', Path(self.tmp.name) / 'data' / 'jobs.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)

    def test_invalid_batch_is_rejected_without_partial_writes(self):
        good = core.make_job('gupy', 'emprego', {'id':'1', 'title':'Analista', 'kind':'employment',
            'url':'https://empresa.gupy.io/jobs/1', 'location':'Barbacena, MG', 'country':'BR', 'mode':'onsite'})
        invalid = dict(good, id='bad', areas={'valor':'inesperado'})
        with self.assertRaises(ValueError):
            core.save([good, invalid])
        self.assertEqual(core.query(kind='employment'), [])

    def test_unexpected_worker_failure_is_terminal_and_allows_retry(self):
        manager = SearchManager()
        with patch('busca_online._plan', return_value=[('gupy', 'emprego', {})]), \
             patch.object(manager, '_run', side_effect=RuntimeError('interrompido')):
            ident = manager.start({})
            manager.wait(ident, 3)
            self.assertEqual(manager.status(ident)['status'], 'failed')
            another = manager.start({})
            manager.wait(another, 3)
            self.assertEqual(manager.status(another)['status'], 'failed')

    def test_expired_live_worker_cannot_overlap_new_search(self):
        manager=SearchManager(timeout=60)
        entered=threading.Event();release=threading.Event()
        def blocked(*args,**kwargs):
            entered.set();release.wait(3);return []
        with patch('busca_online._plan',return_value=[('gupy','emprego',{})]), \
             patch('core.fetch_source',side_effect=blocked):
            ident=manager.start({})
            self.assertTrue(entered.wait(2))
            with manager.lock:manager.jobs[ident]['started_monotonic']-=61
            self.assertEqual(manager.status(ident)['status'],'failed')
            with self.assertRaises(ValueError):manager.start({})
            release.set();manager.wait(ident,3)
            self.assertEqual(manager.status(ident)['status'],'failed')
