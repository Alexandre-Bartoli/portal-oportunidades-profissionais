import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core
from busca_online import SearchManager, _plan
from interface_publica import render_search


class VoluntariadoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        (root/'sources.json').write_text(json.dumps({'sources':[{'provider':'ashby','slug':'org','enabled':True,'region':'BR'}, {'provider':'gupy','slug':'emprego','enabled':True,'experimental_access':True,'region':'BR'}]}))
        for name,value in [('BASE',root),('DB',root/'data'/'jobs.sqlite3')]:
            p=patch.object(core,name,value);p.start();self.addCleanup(p.stop)
        self.filters={'q':'','kind':'volunteer','country':'BR','region':'brazil','mode':'onsite','area':'Tecnologia','uf':'MG','municipality':'','radius_km':'','published_days':''}

    def test_volunteer_recognition_requires_explicit_signal(self):
        self.assertEqual(core.category('Desenvolvedor','', 'Volunteer'),'volunteer')
        self.assertEqual(core.category('Voluntário de tecnologia'),'volunteer')
        self.assertNotEqual(core.category('Coordenador de voluntários','','FullTime'),'volunteer')

    def test_volunteer_source_plan_does_not_use_gupy_employment(self):
        self.assertEqual([(p,s) for p,s,_ in _plan(self.filters)],[('ashby','org')])

    def test_search_filters_and_directory_are_shown(self):
        raw={'id':'1','title':'Voluntário de desenvolvimento de software','jobUrl':'https://jobs.ashbyhq.com/org/1','employmentType':'Volunteer','workplaceType':'OnSite','location':'Barbacena, MG','address':{'postalAddress':{'addressCountry':'BR'}}}
        job=core.make_job('ashby','org',raw)
        with patch('core.fetch_source',return_value=[job]):
            manager=SearchManager();ident=manager.start(self.filters);manager.wait(ident,3)
        state=manager.status(ident)
        result=core.query(kind='volunteer',uf='MG',mode='onsite',area='Tecnologia',only_ids=state['ids'])
        self.assertEqual(len(result),1)
        page=render_search(result,self.filters,list(core.AREAS),[('MG','MG')],[],[],False)
        self.assertIn('Voluntariado',page)
        self.assertIn('vol.org.br',page)
        self.assertIn('não são consultados automaticamente',page)
