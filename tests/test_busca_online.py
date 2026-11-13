import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import core
from providers_extra import ListingBatch


class BuscaOnlineTests(unittest.TestCase):
    def setUp(self):
        from busca_online import SearchManager
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'sources.json').write_text(json.dumps({'sources':[
            {'provider':'gupy','slug':'emprego','enabled':True,'experimental_access':True,'region':'BR'},
            {'provider':'ashby','slug':'cohere','enabled':True,'region':'international'}]}))
        for obj,name,value in ((core,'BASE',self.root),(core,'DB',self.root/'data'/'jobs.sqlite3')):
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        self.manager=SearchManager()

    def filters(self, **changes):
        f={'q':'','kind':'employment','country':'','region':'brazil','mode':'','area':'',
           'uf':'MG','municipality':'','radius_km':'','published_days':''}
        f.update(changes);return f

    def test_selected_state_and_category_are_used_and_progress_is_visible(self):
        started=threading.Event();release=threading.Event();calls=[]
        def fetch(provider,slug,**kwargs):
            calls.append((provider,slug,kwargs));started.set();release.wait(3)
            return ListingBatch([],complete=False,raw_count=0)
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters())
            self.assertTrue(started.wait(2))
            state=self.manager.status(ident)
            self.assertEqual((state['done'],state['total'],state['status']),(0,1,'running'))
            release.set();self.manager.wait(ident,3)
        state=self.manager.status(ident)
        self.assertEqual((state['done'],state['total'],state['status']),(1,1,'completed'))
        self.assertEqual(calls[0][0:2],('gupy','emprego-mg'))
        self.assertEqual(calls[0][2]['detail_limit'],5)

    def test_repeated_search_is_reused_after_restart_until_expiration(self):
        from busca_online import SearchManager
        job=core.make_job('gupy','emprego-mg',{'id':'100','title':'Analista','kind':'employment','url':'https://empresa.gupy.io/jobs/100','country':'BR','location':'Barbacena, MG','mode':'onsite'})
        with patch('core.fetch_source',return_value=ListingBatch([job],complete=False)) as fetch:
            ident=self.manager.start(self.filters());self.manager.wait(ident,3)
            first=self.manager.status(ident)
            self.manager=SearchManager()
            ident=self.manager.start(self.filters());self.manager.wait(ident,3)
            second=self.manager.status(ident)
            self.assertEqual(fetch.call_count,1)
            self.assertEqual(first['ids'],second['ids'])
            self.assertTrue(second['cached'])
            from interface_publica import render_progress
            self.assertIn('Resultados armazenados',render_progress(second,ident))
            with core.connect() as db:
                db.execute('UPDATE search_cache SET created_at=created_at-86401')
                db.execute('UPDATE source_cache SET created_at=created_at-86401')
            ident=self.manager.start(self.filters());self.manager.wait(ident,3)
            self.assertEqual(fetch.call_count,2)
        with patch('core.fetch_source',return_value=ListingBatch([],complete=False)) as fetch:
            for word in ('analista','professor'):
                ident=self.manager.start(self.filters(q=word));self.manager.wait(ident,3)
            self.assertEqual(fetch.call_count,2)

    def test_different_filters_and_failures_do_not_use_cache(self):
        with patch('core.fetch_source',side_effect=OSError('offline')) as fetch:
            for _ in range(2):
                ident=self.manager.start(self.filters());self.manager.wait(ident,3)
            self.assertEqual(fetch.call_count,2)

    def test_provider_results_are_reused_when_local_filter_changes(self):
        config={'sources':[{'provider':'voluntarios','slug':'publico','enabled':True,'experimental_access':True,'region':'BR'}]}
        (self.root/'sources.json').write_text(json.dumps(config))
        def job(ident,title):
            return core.make_job('voluntarios','publico',{'id':ident,'title':title,'kind':'volunteer','url':'https://voluntarios.com.br/vaga/'+ident,'mode':'remote','description':'Comunicação' if ident=='1' else 'software'})
        jobs=ListingBatch([job('1','Comunicação'),job('2','Tecnologia')],complete=False)
        with patch('core.fetch_source',return_value=jobs) as fetch:
            for word,expected in [('Comunicação','Comunicação'),('Tecnologia','Tecnologia')]:
                ident=self.manager.start(self.filters(kind='volunteer',region='',uf='',q=word))
                self.manager.wait(ident,3)
                state=self.manager.status(ident)
                found=core.query(kind='volunteer',only_ids=state['ids'])
                self.assertEqual([x['title'] for x in found],[expected])
            self.assertEqual(fetch.call_count,1)
            self.assertTrue(state['sources'][0]['cached'])
            from admin_history import source_health
            health=source_health()
            self.assertEqual(health[0]['attempts'],1)
            self.assertEqual(health[0]['partial'],1)

    def test_progress_updates_while_a_source_details_jobs(self):
        started=threading.Event();release=threading.Event()
        def fetch(provider,slug,**kwargs):
            kwargs['progress_callback'](2,5)
            started.set();release.wait(3)
            return ListingBatch([],complete=False,raw_count=0)
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters())
            self.assertTrue(started.wait(2))
            current=self.manager.status(ident)
            self.assertEqual((current['detail_done'],current['detail_total']),(2,5))
            from interface_publica import render_progress
            self.assertIn('value="40" max="100"',render_progress(current,ident))
            release.set();self.manager.wait(ident,3)

    def test_international_search_only_saves_selected_country(self):
        def fetch(provider,slug,**kwargs):
            return [core.make_job('ashby',slug,{'id':str(i),'title':'Analista',
                    'jobUrl':f'https://jobs.ashbyhq.com/{slug}/{i}', 'employmentType':'FullTime',
                    'address':{'postalAddress':{'addressCountry':country}}})
                    for i,country in enumerate(('Canada','United States'))]
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters(uf='',region='international',country='CA'))
            self.manager.wait(ident,3)
        self.assertEqual([x['country'] for x in core.query(kind='employment')],['CA'])

    def test_brazilian_company_sources_are_filtered_to_chosen_state(self):
        path=self.root/'sources.json';config=json.loads(path.read_text())
        config['sources'].append({'provider':'inhire','slug':'empresa','enabled':True,
                                  'region':'BR','experimental_access':True})
        path.write_text(json.dumps(config))
        def fetch(provider,slug,**kwargs):
            if provider=='gupy':return []
            return [core.make_job('inhire',slug,{'id':str(i),'title':'Analista','kind':'employment',
                    'url':f'https://empresa.inhire.app/vagas/{i}/analista','country':'BR',
                    'location':location,'mode':'onsite'}) for i,location in enumerate(('Barbacena, MG','São Paulo, SP'))]
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters())
            self.manager.wait(ident,3)
        state=self.manager.status(ident)
        self.assertEqual(state['total'],2)
        self.assertEqual([job['location'] for job in core.query(kind='employment',only_ids=state['ids'])],['Barbacena, MG'])

    def test_results_include_only_jobs_checked_in_this_search(self):
        old=core.make_job('ashby','cohere',{'id':'old','title':'Analista',
            'jobUrl':'https://jobs.ashbyhq.com/cohere/old','employmentType':'FullTime',
            'address':{'postalAddress':{'addressCountry':'Canada'}}})
        fresh=core.make_job('ashby','cohere',{'id':'new','title':'Analista',
            'jobUrl':'https://jobs.ashbyhq.com/cohere/new','employmentType':'FullTime',
            'address':{'postalAddress':{'addressCountry':'Canada'}}})
        core.save([old])
        with patch('core.fetch_source',return_value=[fresh]):
            ident=self.manager.start(self.filters(uf='',region='international',country='CA'))
            self.manager.wait(ident,3)
        state=self.manager.status(ident)
        results=core.query(kind='employment',only_ids=list(state['pending']))
        self.assertEqual([job['external_id'] for job in results],['new'])

    def test_incomplete_location_is_pending_but_known_wrong_state_is_excluded(self):
        from busca_online import _classify
        base={'kind':'employment','country':'BR','mode':'onsite','title':'Analista','description':'','areas':[],'location':'','geo_municipio':None}
        self.assertIn('Localização insuficiente para confirmar a região',_classify(base,self.filters()))
        other={**base,'location':'São Paulo, SP','geo_municipio':'3550308'}
        self.assertIsNone(_classify(other,self.filters()))
        unknown={**base,'mode':'unknown'}
        self.assertIn('Modalidade não informada',_classify(unknown,self.filters(mode='remote')))

    def test_remote_volunteer_without_location_appears_in_unrestricted_search(self):
        from voluntarios_publico import parse_list
        from datetime import date
        page='''<table><thead><tr><th>Vaga</th><th>Área de trabalho na vaga</th><th>Modo de trabalho</th><th>Local</th><th>Causa</th><th>Inscrições</th></tr></thead><tbody><tr><td><a href="/vaga/123-456-789">Voluntário remoto</a></td><td>Comunicação</td><td>Remoto</td><td>-</td><td>Educação</td><td>01/01/2026 a 31/12/2026</td></tr></tbody></table>'''
        rows=parse_list(page,today=date(2026,11,13))
        config={'sources':[{'provider':'voluntarios','slug':'publico','enabled':True,'experimental_access':True,'region':'BR'}]}
        (self.root/'sources.json').write_text(json.dumps(config))
        with patch('core.fetch_source',return_value=rows):
            ident=self.manager.start(self.filters(kind='volunteer',mode='remote',region='',uf=''))
            self.manager.wait(ident,3)
        state=self.manager.status(ident)
        found=core.query(kind='volunteer',mode='remote',only_ids=state['ids'])
        self.assertEqual([job['title'] for job in found],['Voluntário remoto'])
        self.assertEqual(state['pending'],{})

    def test_remote_without_location_remains_pending_with_geographic_filter(self):
        from busca_online import _classify
        job={'kind':'volunteer','country':None,'mode':'remote','title':'Voluntário','description':'','areas':[],'location':'','geo_municipio':None}
        result=_classify(job,self.filters(kind='volunteer',mode='remote'))
        self.assertIn('Localização insuficiente para confirmar a região',result)
        self.assertIn('País não confirmado',result)

    def test_course_suggestion_uses_known_area_without_personal_data(self):
        from busca_online import course_area
        self.assertEqual(course_area('informatica_internet'),'Tecnologia')
        self.assertEqual(course_area(''),'')
        with self.assertRaises(ValueError):course_area('curso_inexistente')

    def test_search_cache_does_not_extend_age_of_reused_source(self):
        from busca_online import _read_cache, _write_cache
        from datetime import datetime, timezone
        old=datetime.fromtimestamp(100_000,timezone.utc).isoformat()
        result={'ids':[],'pending':{},'sources':[{'checked_at':old}],'saved':0}
        with patch('busca_online.time.time',return_value=100_000+86_399):
            _write_cache('test',result)
            self.assertIsNotNone(_read_cache('test'))
        with patch('busca_online.time.time',return_value=100_000+86_400):
            self.assertIsNone(_read_cache('test'))

    def test_search_resolves_existing_duplicate_to_persisted_identity(self):
        raw={'id':'77','title':'Analista','kind':'employment','country':'BR',
             'url':'https://empresa.gupy.io/jobs/77','location':'Barbacena, MG','mode':'onsite'}
        existing=core.make_job('gupy','emprego',raw)
        refreshed=core.make_job('gupy','emprego-mg',raw)
        core.save([existing])
        with patch('core.fetch_source',return_value=[refreshed]):
            ident=self.manager.start(self.filters())
            self.manager.wait(ident,3)
        results=core.query(kind='employment',uf='MG',only_ids=self.manager.status(ident)['ids'])
        self.assertEqual([job['id'] for job in results],[existing['id']])

    def test_city_and_workplace_are_sent_to_selected_gupy_search(self):
        calls=[]
        def fetch(provider,slug,**kwargs):
            calls.append(kwargs);return ListingBatch([],complete=False,raw_count=0)
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters(municipality='3105608',mode='hybrid'))
            self.manager.wait(ident,3)
        self.assertEqual(calls[0]['city'],'Barbacena')
        self.assertEqual(calls[0]['workplace'],'hybrid')

    def test_radius_search_also_queries_nearby_states(self):
        calls=[]
        def fetch(provider,slug,**kwargs):
            calls.append((provider,slug));return ListingBatch([],complete=False,raw_count=0)
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters(municipality='3136702',radius_km='90'))
            self.manager.wait(ident,3)
        self.assertIn(('gupy','emprego-mg'),calls)
        self.assertIn(('gupy','emprego-rj'),calls)

    def test_network_failure_is_visible_and_does_not_erase_existing_jobs(self):
        with patch('core.fetch_source',side_effect=OSError('offline')):
            ident=self.manager.start(self.filters())
            self.manager.wait(ident,3)
        state=self.manager.status(ident)
        self.assertEqual((state['status'],state['failed']),('completed',1))

    def test_detail_failures_are_reported_to_the_user(self):
        rows=ListingBatch([],complete=False,raw_count=2)
        rows.details_attempted=2;rows.details_succeeded=1
        with patch('core.fetch_source',return_value=rows):
            ident=self.manager.start(self.filters());self.manager.wait(ident,3)
        state=self.manager.status(ident)
        self.assertEqual(state['details_failed'],1)
        from interface_publica import render_progress
        self.assertIn('detalhes não puderam ser consultados',render_progress(state,ident))

    def test_source_summary_distinguishes_complete_partial_and_failed(self):
        config={'sources':[{'provider':'ashby','slug':slug,'enabled':True,'region':'international'}
                           for slug in ('complete','partial','offline')]}
        (self.root/'sources.json').write_text(json.dumps(config))
        def fetch(provider,slug,**kwargs):
            if slug=='offline':raise OSError('informação privada')
            return ListingBatch([],complete=slug=='complete',raw_count=0)
        with patch('core.fetch_source',side_effect=fetch):
            ident=self.manager.start(self.filters(uf='',region='international',country='CA'))
            self.manager.wait(ident,3)
        state=self.manager.status(ident)
        self.assertEqual([(x['slug'],x['status'],x['matched']) for x in state['sources']],
                         [('complete','ok',0),('partial','partial',0),('offline','failed',None)])
        from interface_publica import render_progress,render_source_results
        html=render_progress(state,ident)
        for label in ('Consulta concluída','Resultado parcial','Falha na consulta'):self.assertIn(label,html)
        self.assertNotIn('informação privada',html)
        self.assertIn('não indica que não existam outras vagas',render_source_results(state['sources']))
        state['sources'].clear()
        self.assertEqual(len(self.manager.status(ident)['sources']),3)

    def test_conflicting_location_is_rejected(self):
        with self.assertRaises(ValueError):self.manager.start(self.filters(country='CA'))

    def test_post_rejects_duplicate_origin_headers(self):
        import app
        import http.client
        from http.server import ThreadingHTTPServer
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
            conn.putrequest('POST','/buscar-agora')
            conn.putheader('Origin',f'http://127.0.0.1:{server.server_port}')
            conn.putheader('Origin','https://site-externo.example')
            conn.putheader('Content-Type','application/x-www-form-urlencoded')
            conn.putheader('Content-Length','0');conn.endheaders()
            self.assertEqual(conn.getresponse().status,403);conn.close()
        finally:
            server.shutdown();server.server_close();thread.join(3)

    def test_http_search_displays_progress_and_rejects_cross_origin(self):
        import app
        import urllib.parse
        import urllib.request
        import urllib.error
        from http.server import ThreadingHTTPServer
        started=threading.Event();release=threading.Event()
        stale=core.make_job('ashby','cohere',{'id':'old','title':'Estágio antigo',
            'jobUrl':'https://jobs.ashbyhq.com/cohere/old','employmentType':'Intern',
            'address':{'postalAddress':{'addressCountry':'Canada'}}})
        core.save([stale])
        def fetch(*args,**kwargs):
            started.set();release.wait(3)
            return ListingBatch([],complete=False,raw_count=0)
        server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        body=urllib.parse.urlencode(self.filters()).encode()
        try:
            with patch('core.fetch_source',side_effect=fetch):
                request=urllib.request.Request(base+'/buscar-agora',data=body,headers={'Origin':base})
                with urllib.request.urlopen(request,timeout=3) as response:
                    page=response.read().decode();self.assertEqual(response.status,200)
                self.assertTrue(started.wait(2))
                self.assertIn('<progress',page)
                self.assertIn('Atualizando oportunidades',page)
                request=urllib.request.Request(base+'/buscar-agora',data=body,headers={'Origin':'https://site-externo.example'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,403)
                conflicting=urllib.parse.urlencode(self.filters(country='CA')).encode()
                request=urllib.request.Request(base+'/buscar-agora',data=conflicting,headers={'Origin':base})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,400)
                self.assertIn('incompatíveis',error.exception.read().decode())
                release.set()
                ident=next(iter(server.search_manager.jobs))
                server.search_manager.wait(ident,3)
                with urllib.request.urlopen(base+'/busca-progresso?id='+ident) as response:
                    completed=response.read().decode()
                self.assertIn('search_id=',completed)
                with urllib.request.urlopen(base+'/?kind=all&search_id='+ident) as response:
                    results=response.read().decode()
                self.assertNotIn('Estágio antigo',results)
        finally:
            release.set();server.shutdown();server.server_close();thread.join(3)
