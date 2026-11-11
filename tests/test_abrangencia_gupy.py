import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import core
import gupy
from geografia import locate


def row(number, **updates):
    result={'id':number,'name':'Vaga','type':'vacancy_type_internship',
            'jobUrl':f'https://empresa.gupy.io/jobs/{number}'}
    result.update(updates)
    return result


class AbrangenciaGupyTests(unittest.TestCase):
    def test_collects_multiple_pages_and_keeps_inventory_partial(self):
        calls=[]
        def getter(url):
            params=parse_qs(urlsplit(url).query,keep_blank_values=True)
            offset=int(params['offset'][0]); limit=int(params['limit'][0]);calls.append(offset)
            return {'data':[row(i+1) for i in range(offset,min(offset+limit,60))]}
        with patch('core.get_json',side_effect=getter), patch('core.get_gupy_detail',side_effect=ValueError('sem detalhe')):
            result=core.fetch_source('gupy','estagio')
        self.assertGreater(len(result),25)
        self.assertEqual(calls,[0,25,50])
        self.assertFalse(result.complete)

    def test_listing_uses_only_explicit_country(self):
        item=gupy.normalize_item(row(1,city='Barbacena',state='Minas Gerais',country='Brasil'),'internship')
        self.assertEqual(item['country'],'BR')
        self.assertEqual(locate(item['location'],item['country']),'3105608')
        unknown=gupy.normalize_item(row(2,city='Barbacena',state='Minas Gerais'),'internship')
        self.assertIsNone(unknown['country'])
        self.assertIsNone(locate(unknown['location'],unknown['country']))

    def test_full_state_name_requires_confirmed_brazil(self):
        self.assertEqual(locate('Barbacena, Minas Gerais','BR'),'3105608')
        self.assertIsNone(locate('Barbacena, Minas Gerais',None))
        self.assertIsNone(locate('Barbacena, Minas Gerais','CA'))
        self.assertIsNone(locate('Barbacena, Minas Gerais / São Paulo, SP','BR'))

    def test_gupy_country_city_and_radius_search_end_to_end(self):
        import json
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        import app
        with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',Path(directory)/'x.sqlite3'):
            items=[row(1,city='Barbacena',state='Minas Gerais',country='Brasil'),
                   row(2,city='Juiz de Fora',state='Minas Gerais',country='BR'),
                   row(3,city='Barbacena',state='Minas Gerais'),
                   row(4,city='Barbacena',state='Minas Gerais',country='BR',workplaceType='remote')]
            core.save([core.make_job('gupy','estagio',gupy.normalize_item(x,'internship')) for x in items])
            server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/api/jobs?kind=all&uf=MG&municipality=3105608&radius_km=100'
                with urllib.request.urlopen(url) as response: data=json.load(response)
                self.assertEqual({x['external_id'] for x in data['results']},{'1','2'})
            finally:
                server.shutdown();server.server_close();thread.join(3)

    def test_progressively_selects_not_enriched_jobs(self):
        raw=[gupy.normalize_item(row(i),'internship') for i in range(1,6)]
        with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',Path(directory)/'x.sqlite3'):
            first=dict(raw[0],detail_enriched=True)
            core.save([core.make_job('gupy','estagio',first)])
            selected=core.select_gupy_details('estagio',raw,3)
        self.assertEqual([x['id'] for x in selected],['2','3','4'])

    def test_failure_on_later_page_is_not_silently_treated_as_complete(self):
        calls=[]
        def getter(url):
            calls.append(url)
            if len(calls)==1:return {'data':[row(i) for i in range(1,26)]}
            raise ValueError('falha na página')
        with patch('core.get_json',side_effect=getter), patch('core.get_gupy_detail',side_effect=ValueError('sem detalhe')), self.assertRaises(ValueError):
            core.fetch_source('gupy','estagio')


if __name__=='__main__':unittest.main()
