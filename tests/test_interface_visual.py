import unittest
from interface_publica import render_search, render_detail


class InterfaceVisualTests(unittest.TestCase):
    def test_complementary_search_links_include_course_and_kind(self):
        from html import unescape
        from urllib.parse import urlsplit, parse_qs
        import re
        filters={'q':'','kind':'internship','country':'','region':'','mode':'','area':'','uf':'','municipality':'','radius_km':'','course':'psicologia'}
        page=render_search([],filters,[],[],[],[],False)
        self.assertIn('Pesquisa complementar no Google',page)
        links=re.findall(r'href="(https://www\.google\.com/search\?[^"]+)"',page)
        self.assertEqual(len(links),3)
        queries=[parse_qs(urlsplit(unescape(link)).query)['q'][0] for link in links]
        self.assertTrue(all('psicologia' in q and 'estágio' in q for q in queries))
        self.assertTrue(any('site:gupy.io' in q for q in queries))

    def test_course_evidence_is_specific_and_absence_is_explained(self):
        job={'title':'Estágio em tecnologia','description':'Apoio em banco de dados e programação web','company':'Exemplo','provider':'gupy','id':'a','kind':'internship','areas':['Tecnologia']}
        page=render_detail(job,None,'',[],course='sistemas_informacao')
        self.assertIn('banco de dados',page)
        self.assertIn('Confira os requisitos no anúncio',page)
        other=dict(job,title='Estágio administrativo',description='Apoio aos clientes')
        page=render_detail(other,None,'',[],course='psicologia')
        self.assertIn('Não foram identificados termos',page)
        self.assertNotIn('100%',page.split('</head>',1)[1])

    def test_course_context_is_kept_for_regular_and_pending_results(self):
        filters={'q':'','kind':'all','country':'','region':'','mode':'','area':'','uf':'','municipality':'','radius_km':'','course':'psicologia'}
        job={'id':'a','title':'Estágio','location':'','country':None,'kind':'internship','areas':[],'provider':'gupy','demo':0}
        page=render_search([job],filters,[],[],[],[],False,pending_jobs=[(job,['País não confirmado'])])
        self.assertEqual(page.count('/vaga?id=a&amp;course=psicologia'),3)

    def test_evidence_respects_word_boundaries(self):
        from interface_publica import course_evidence
        self.assertEqual(course_evidence({'title':'Análise financeira','description':'Organização'},'psicologia'),[])
        self.assertIn('psicólogo',course_evidence({'title':'Psicólogo','description':''},'psicologia'))

    def test_detail_page_receives_selected_course(self):
        import tempfile, threading, urllib.request
        from pathlib import Path
        from http.server import ThreadingHTTPServer
        from unittest.mock import patch
        import core, app
        with tempfile.TemporaryDirectory() as tmp, patch.object(core,'DB',Path(tmp)/'jobs.sqlite3'):
            job=core.make_job('gupy','emprego',{'id':'1','title':'Psicólogo','description':'Atuação em saúde mental','url':'https://empresa.gupy.io/jobs/1','kind':'employment'})
            core.save([job])
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/vaga?id={job["id"]}&course=psicologia') as response:
                    page=response.read().decode('utf-8')
                self.assertIn('Relação com Psicologia',page)
                self.assertIn('saúde mental',page)
            finally:
                server.shutdown();server.server_close();thread.join(3)

    def test_course_options_are_displayed_and_selected(self):
        filters={'q':'','kind':'all','country':'','region':'','mode':'','area':'','uf':'','municipality':'','radius_km':'','course':'psicologia'}
        page=render_search([],filters,[],[],[],[],False)
        for name in ('Sistemas de Informação','Tecnólogo em Sistemas para Internet','Psicologia'):
            self.assertIn(name,page)
        self.assertIn('value="psicologia" selected',page)

    def test_search_keeps_selected_filters_and_escapes_user_input(self):
        filters={'q':'<script>alert(1)</script>', 'kind':'temporary', 'country':'BR', 'region':'brazil',
                 'mode':'remote', 'area':'', 'uf':'MG', 'municipality':'3105608', 'radius_km':'20'}
        page=render_search([], filters, [], [('MG','MG')], [('3105608','Barbacena')], [], True)
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertIn('name="kind" value="temporary" checked', page)
        self.assertIn('value="3105608" selected', page)
        for name in filters:
            self.assertIn('name="'+name+'"', page)

    def test_results_are_escaped_and_demo_is_visible(self):
        filters={'q':'','kind':'all','country':'','region':'','mode':'','area':'','uf':'','municipality':'','radius_km':''}
        jobs=[{'id':'a','title':'Vaga <exemplo>','location':'Barbacena','country':'BR',
               'kind':'internship','areas':[],'provider':'gupy','demo':1}]
        page=render_search(jobs, filters, [], [], [], [], False)
        self.assertIn('Vaga &lt;exemplo&gt;',page)
        self.assertIn('EXEMPLO FICTÍCIO',page)
        self.assertIn('/vaga?id=a',page)
