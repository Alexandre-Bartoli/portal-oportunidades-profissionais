import unittest
from interface_publica import render_search


class InterfaceVisualTests(unittest.TestCase):
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
