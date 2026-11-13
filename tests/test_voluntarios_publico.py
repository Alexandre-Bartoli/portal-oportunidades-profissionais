import unittest
from datetime import date

from voluntarios_publico import parse_list
import voluntarios_publico
import core
import tempfile
from pathlib import Path
from unittest.mock import patch

PAGE='''<table><thead><tr><th>Vaga</th><th>Área de trabalho na vaga</th><th>Modo de trabalho</th><th>Local</th><th>Causa</th><th>Inscrições</th></tr></thead><tbody>{}</tbody></table>'''
ROW='''<tr><td><a href="/vaga/111-222-333">Instrutor de software</a></td><td>Ensino, Tecnologia</td><td>Presencial</td><td>Barbacena-MG</td><td>Educação</td><td>01/01/2026 a 31/12/2026</td></tr>'''


class VoluntariosPublicoTests(unittest.TestCase):
    def test_failed_refresh_does_not_replace_saved_details(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(core,'DB',Path(tmp)/'jobs.sqlite3'):
            job=parse_list(PAGE.format(ROW),today=date(2026,11,13))[0]
            enriched=dict(job,description='Atividades completas',detail_enriched=True)
            core.save([enriched])
            core.save([job])
            with core.connect() as db:
                saved=db.execute('SELECT description FROM jobs').fetchone()[0]
            self.assertEqual(saved,'Atividades completas')

    def test_detail_preserves_sections_and_entity(self):
        page='''<h1>Instrutor de software</h1><div class="registro">
        <p><label>Carga horária: </label> 4 horas semanais</p>
        <h3 class="secao"><span>Atividades</span></h3><p>Ensinar<br>Orientar</p>
        <h3 class="secao"><span>Requisitos</span></h3><p>Experiência</p>
        <h3 class="secao"><span>Entidade: <a href="/entidade/1">Instituto Escola</a></span></h3><p>Projeto educativo</p>
        <h3 class="secao"><span>Inscrições</span></h3><p>Sem data limite</p></div>'''
        job=parse_list(PAGE.format(ROW),today=date(2026,11,13))[0]
        result=voluntarios_publico.enrich_detail(job,page)
        self.assertEqual(result['company'],'Instituto Escola')
        for value in ('4 horas semanais','Atividades','Ensinar','Orientar','Requisitos','Experiência','Projeto educativo'):
            self.assertIn(value,result['description'])
        with self.assertRaises(ValueError):
            voluntarios_publico.enrich_detail(job,page.replace('Instrutor de software','Outra vaga'))

    def test_unavailable_detail_keeps_listing(self):
        import urllib.error
        from email.message import Message
        class Response:
            headers=Message()
            headers['Content-Type']='text/html'
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,*args): return PAGE.format(ROW).encode()
        class Opener:
            calls=0
            def open(self,*args,**kwargs):
                self.calls+=1
                if self.calls==1:return Response()
                raise urllib.error.URLError('indisponível')
        progress=[]
        with patch('urllib.request.build_opener',return_value=Opener()):
            result=voluntarios_publico.fetch(lambda done,total:progress.append((done,total)))
        self.assertEqual(len(result),1)
        self.assertEqual((result.details_attempted,result.details_succeeded),(1,0))
        self.assertEqual(progress,[(0,1),(1,1)])
        self.assertIn('Área informada',result[0]['description'])

    def test_extracts_public_listing_and_maps_filters(self):
        rows=parse_list(PAGE.format(ROW),today=date(2026,11,13))
        self.assertEqual(len(rows),1)
        job=rows[0]
        self.assertEqual((job['kind'],job['mode'],job['geo_municipio']),('volunteer','onsite','3105608'))
        self.assertEqual(job['url'],'https://voluntarios.com.br/vaga/111-222-333')
        self.assertIn('Tecnologia',job['areas'])
        self.assertIn('Educação',job['areas'])
        self.assertFalse(rows.complete)

    def test_expired_not_imported_and_bad_shape_is_error(self):
        self.assertEqual(len(parse_list(PAGE.format(ROW),today=date(2027,1,1))),0)
        self.assertEqual(len(parse_list(PAGE.format(ROW),today=date(2025,12,31))),0)
        with self.assertRaises(ValueError):parse_list('<html>Erro no servidor</html>')
        with self.assertRaises(ValueError):parse_list(PAGE.format(ROW.replace('/vaga/111-222-333','https://evil.example/x')))
