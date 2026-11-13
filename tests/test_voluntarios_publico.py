import unittest
from datetime import date

from voluntarios_publico import parse_list

PAGE='''<table><thead><tr><th>Vaga</th><th>Área de trabalho na vaga</th><th>Modo de trabalho</th><th>Local</th><th>Causa</th><th>Inscrições</th></tr></thead><tbody>{}</tbody></table>'''
ROW='''<tr><td><a href="/vaga/111-222-333">Instrutor de software</a></td><td>Ensino, Tecnologia</td><td>Presencial</td><td>Barbacena-MG</td><td>Educação</td><td>01/01/2026 a 31/12/2026</td></tr>'''


class VoluntariosPublicoTests(unittest.TestCase):
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
