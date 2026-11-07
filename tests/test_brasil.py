import unittest
from unittest.mock import patch
from brasil import PORTALS, import_rows
from feeds_brasil import validate_feed, fetch_feed, collect_feed

class BrasilTests(unittest.TestCase):
    def test_portals(self):
        self.assertEqual(len(PORTALS), 6)
    def test_feed_rejects_http(self):
        with self.assertRaises(ValueError):
            validate_feed({'portal':'ciee','url':'http://example.com/test.csv','allowed_host':'example.com','format':'csv'})
    def test_feed_rejects_host_mismatch(self):
        with self.assertRaises(ValueError):
            validate_feed({'portal':'ciee','url':'https://example.com/test.csv','allowed_host':'other.example','format':'csv'})
    def test_feed_rejects_port(self):
        with self.assertRaises(ValueError):
            validate_feed({'portal':'ciee','url':'https://example.com:8443/test.csv','allowed_host':'example.com','format':'csv'})
    def test_inactive_doesnt_fetch(self):
        self.assertEqual(collect_feed({'portal':'ciee','enabled':False}),0)
    def test_import_invalid_link(self):
        with self.assertRaises(ValueError):
            import_rows([{'portal':'iel','titulo':'Estágio em Administração','url':'javascript:alert(1)'}])
    @patch('core.save')
    def test_import_csv_rows(self, save):
        n=import_rows([{'portal':'nube','id_externo':'123','titulo':'Estágio em Psicologia','descricao':'Atividades','url':'https://www.nube.com.br/vaga/123','localidade':'São Paulo','pais':'BR'}])
        self.assertEqual(n,1)
        job=save.call_args.args[0][0]
        self.assertEqual(job['review_status'],'review')
        self.assertEqual(job['provider'],'nube')
    @patch('core.save')
    def test_exclude_non_intern(self, save):
        self.assertEqual(import_rows([{'portal':'ciee','titulo':'Engenheiro Sênior','url':'https://portal.ciee.org.br/vaga/1'}]),0)
        save.assert_called_once_with([])

if __name__=='__main__': unittest.main()