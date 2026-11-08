import unittest
from unittest.mock import patch
from gupy import build_url, normalize_item, safe_job_url, fetch
from signals import analyze
from core import category, make_job

class GupyTests(unittest.TestCase):
 def test_unknown_state_does_not_imply_brazil(self):
  from gupy import normalize_item
  raw={'id':'1','name':'Estágio','type':'vacancy_type_internship',
       'jobUrl':'https://acme.gupy.io/jobs/1','state':'Ontario'}
  self.assertIsNone(normalize_item(raw, 'internship')['country'])
 def sample(self):
  return {'id':123, 'name':'Estágio em Agronomia', 'type':'vacancy_type_internship', 'jobUrl':'https://empresa.gupy.io/jobs/123', 'city':'Barbacena','state':'Minas Gerais','workplaceType':'hybrid'}
 def test_endpoint(self):
  u=build_url('estágio',state='Minas Gerais')
  self.assertIn('type=vacancy_type_internship',u)
  self.assertIn('state=Minas+Gerais',u)
 def test_unknown_contract_rejected(self):
  with self.assertRaises(ValueError):build_url('',contract='other')
 def test_external_url_blocked(self):
  self.assertEqual(safe_job_url('https://evil.example/job/123'),'')
 def test_explicit_classification(self):
  self.assertEqual(normalize_item(self.sample(),'internship')['kind'],'internship')
  self.assertIsNone(normalize_item(self.sample(),'employment'))
 def test_normalized_db_job(self):
  raw=normalize_item(self.sample(),'internship')
  job=make_job('gupy','estagio',raw)
  self.assertIsNone(job['country'])
  self.assertEqual(job['kind'],'internship')
 def test_bad_response_fails(self):
  with self.assertRaises(ValueError):fetch('estágio',get_json=lambda _: {'unexpected':[]})
 def test_fetch_fixture(self):
  data={'data':[self.sample()]}
  rows=fetch('estágio',get_json=lambda _: data)
  self.assertEqual(len(rows),1)
 def test_signals_mismatch(self):
  flags=analyze('Vaga em tecnologia','Modelo de trabalho híbrido', 'remote')
  self.assertIn('modalidade_inconsistente',[x['type'] for x in flags])
 def test_payment_flag(self):
  self.assertIn('pagamento_suspeito',[x['type'] for x in analyze('Vaga','Pague via pix uma taxa de inscrição')])
 def test_classification_three_categories(self):
  self.assertEqual(category('Auxiliar',employment_type='vacancy_type_temporary'),'temporary')
  self.assertEqual(category('Desenvolvedor',employment_type='vacancy_type_effective'),'employment')
  self.assertEqual(category('Estágio em Saúde'),'internship')

if __name__=='__main__': unittest.main()
