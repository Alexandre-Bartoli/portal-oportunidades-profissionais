import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core
import automatico
from providers_extra import ListingBatch


class DiscoveryRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.original_db=core.DB
        self.original_base=automatico.BASE
        self.original_state=automatico.STATE
        core.DB=Path(self.tmp.name)/'jobs.sqlite3'
        automatico.BASE=Path(self.tmp.name)
        automatico.STATE=automatico.BASE/'data'/'ultima_coleta.json'
        (automatico.BASE/'sources.json').write_text(json.dumps({'sources':[
            {'provider':'lever','slug':'old','enabled':True},
            {'provider':'smartrecruiters','slug':'new','enabled':False}]}),encoding='utf-8')

    def tearDown(self):
        core.DB=self.original_db
        automatico.BASE=self.original_base
        automatico.STATE=self.original_state
        self.tmp.cleanup()

    def job(self):
        return core.make_job('lever','old',{'id':'1','text':'Estágio em Computação',
            'hostedUrl':'https://jobs.ashbyhq.com/novacompanhia/123'})

    def test_collection_emits_disabled_candidates(self):
        with patch('automatico.fetch_source',return_value=[self.job()]):
            out=automatico.collect_once()
        self.assertEqual(out['suggested_sources'],1)
        dest=automatico.BASE/'data'/'fontes_sugeridas.json'
        found=json.loads(dest.read_text(encoding='utf-8'))['candidates']
        self.assertEqual(found[0]['slug'],'novacompanhia')
        from admin_history import recent
        self.assertEqual(recent()[0]['collected'],1)
        self.assertFalse(found[0]['enabled'])
        # Ainda não entrou em sources.json, mesmo após coleta.
        self.assertEqual(len(json.loads((automatico.BASE/'sources.json').read_text())['sources']),2)

    def test_partial_inventory_must_not_expire_jobs(self):
        j=self.job()
        core.save([j])
        with patch('automatico.fetch_source',return_value=ListingBatch([],complete=False)):
            for _ in range(3):
                out=automatico.collect_once()
        self.assertEqual(out['sources'][0]['status'],'partial')
        self.assertEqual(len(core.query()),1)


if __name__=='__main__': unittest.main()
