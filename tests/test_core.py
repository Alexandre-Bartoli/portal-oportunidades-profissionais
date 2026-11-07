import unittest
from core import classify, areas_for, make_job
class Tests(unittest.TestCase):
 def test_intern(self):self.assertEqual(classify('Software Engineering Internship')[0],'internship')
 def test_estagio(self):self.assertEqual(classify('Estágio em Enfermagem')[0],'internship')
 def test_trainee_not_intern(self):self.assertEqual(classify('Management Trainee')[0],'other')
 def test_job_not_intern(self):self.assertEqual(classify('Senior Software Engineer')[0],'other')
 def test_area(self):self.assertIn('Administração',areas_for('Estágio em Administração'))
 def test_empty_link(self):self.assertIsNone(make_job('greenhouse','company',{'id':1,'title':'Internship','absolute_url':''}))
 def test_greenhouse(self):
  j=make_job('greenhouse','company',{'id':123,'title':'Research Internship','absolute_url':'https://example.org/1','location':{'name':'Remote'}})
  self.assertEqual(j['country'],None);self.assertEqual(j['review_status'],'review')
 def test_ashby_untrusted_job(self):
  j=make_job('ashby','company',{'title':'Summer Intern','jobUrl':'https://example.org/jobs/1','location':'London'})
  self.assertEqual(j['kind'],'internship')
if __name__=='__main__':unittest.main()