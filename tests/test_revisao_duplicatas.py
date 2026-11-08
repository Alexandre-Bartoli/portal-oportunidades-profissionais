import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core


class DuplicateReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = patch.object(core, 'DB', Path(self.tmp.name)/'jobs.sqlite3')
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def _job(self, source, ident, description, location='Barbacena, MG', title='Estágio de Administração'):
        return core.make_job('lever', source, {'id':ident, 'text':title,
            'hostedUrl':f'https://example.org/{source}/{ident}', 'descriptionPlain':description,
            'country':'BR', 'categories':{'location':location}})

    def test_matching_long_descriptions_flagged_without_merging(self):
        from revisao_duplicatas import inspect
        text='Atividades administrativas e acompanhamento de projetos. ' * 6
        first=self._job('empresa1','1',text)
        second=self._job('empresa2','2',text)
        core.save([first,second])
        result=inspect(core.DB)
        self.assertEqual(len(result['groups']),1)
        self.assertEqual({r['id'] for r in result['groups'][0]['jobs']},{first['id'],second['id']})
        self.assertEqual(len(core.query(kind='')),2)

    def test_similar_titles_alone_are_not_evidence(self):
        from revisao_duplicatas import inspect
        core.save([self._job('a','1','A'*180),self._job('b','2','B'*180),
                   self._job('c','3',''),self._job('d','4','')])
        self.assertEqual(inspect(core.DB)['groups'],[])

    def test_same_description_different_city_is_not_grouped(self):
        from revisao_duplicatas import inspect
        text='Trabalho em equipe e atendimento ao público. '*8
        core.save([self._job('a','1',text),self._job('b','2',text,location='São Paulo, SP')])
        self.assertEqual(inspect(core.DB)['groups'],[])

    def test_legacy_or_inactive_items_are_not_mutated(self):
        from revisao_duplicatas import inspect
        text='Suporte a projetos e conferência de documentos. '*8
        a=self._job('a','1',text);b=self._job('b','2',text)
        core.save([a,b])
        with core.connect() as db:db.execute('UPDATE jobs SET active=0 WHERE id=?',(b['id'],))
        self.assertEqual(inspect(core.DB)['groups'],[])
        with core.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],2)
